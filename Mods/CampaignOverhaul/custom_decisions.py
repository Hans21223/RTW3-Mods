"""Player-authored, live campaign decisions backed by the guarded cheat mailbox."""
from __future__ import annotations

import json
from pathlib import Path
import re

import live_cheats
import save_cheats

HERE = Path(__file__).resolve().parent
DEFINITIONS = HERE / "custom_decisions.json"
STATE = HERE.parent / "Manager" / "custom-decisions-state.json"
PROFILE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._-]{0,63}$")
EFFECT_KEYS = {"funds", "income_level", "income_resources", "prestige", "unrest"}


def definitions():
    data = json.loads(DEFINITIONS.read_text(encoding="utf-8-sig"))
    if data.get("schema") != 1 or not isinstance(data.get("decisions"), list):
        raise ValueError("custom_decisions.json needs schema 1 and a decisions list.")
    seen = set()
    for item in data["decisions"]:
        if not isinstance(item, dict):
            raise ValueError("Every custom decision must be an object.")
        ident, name, mode = item.get("id"), item.get("name"), item.get("mode")
        if not isinstance(ident, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,47}", ident) or ident in seen:
            raise ValueError("Decision IDs must be unique lowercase letters, digits, underscores or hyphens.")
        if not isinstance(name, str) or not name.strip() or mode not in {"instant", "annual"}:
            raise ValueError(f"Decision {ident} needs a name and mode instant or annual.")
        seen.add(ident)
        _effects(item.get("effects", {}) if mode == "instant" else item.get("annual_effects", {}), ident)
        if mode == "annual":
            years = item.get("duration_years")
            if type(years) is not int or not 1 <= years <= 30:
                raise ValueError(f"Decision {ident} duration_years must be from 1 to 30.")
            if item.get("completion_effects"):
                _effects(item["completion_effects"], ident)
    return data["decisions"]


def _effects(values, ident):
    if not isinstance(values, dict) or not values:
        raise ValueError(f"Decision {ident} needs at least one effect.")
    for key, amount in values.items():
        if key not in EFFECT_KEYS or type(amount) is not int:
            raise ValueError(f"Decision {ident} has an unsupported effect: {key}.")


def _profile(value):
    value = str(value or "").strip()
    if not PROFILE.fullmatch(value):
        raise ValueError("Enter a campaign profile name using 1-64 letters, numbers, spaces, dots, dashes or underscores.")
    return value.casefold(), value


def _state():
    if not STATE.exists():
        return {"schema": 1, "profiles": {}}
    data = json.loads(STATE.read_text(encoding="utf-8-sig"))
    if data.get("schema") != 1 or not isinstance(data.get("profiles"), dict):
        raise ValueError("The custom-decision progress file is not supported; preserve it before editing.")
    return data


def _write_state(data):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    temp = STATE.with_suffix(STATE.suffix + ".tmp")
    temp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    temp.replace(STATE)


def _absolute_values(current, effects, repeats=1):
    updated = {}
    for key, amount in effects.items():
        _, low, high = save_cheats.FIELDS[key]
        value = current["values"][key] + amount * repeats
        if not low <= value <= high:
            raise ValueError(f"{key.replace('_', ' ')} would become {value:,}; its valid range is {low:,} to {high:,}.")
        updated[key] = value
    return updated


def listing():
    return {"ok": True, "decisions": definitions(), "file": str(DEFINITIONS)}


def status(pid, profile_name):
    key, label = _profile(profile_name)
    current = live_cheats.inspect(pid)
    record = _state()["profiles"].get(key)
    if record and record.get("nation") != current.get("nation_name"):
        raise ValueError(f"Profile {label} belongs to {record.get('nation')}; choose the profile used for this campaign or create a new one.")
    return {"ok": True, "profile": label, "nation": current.get("nation_name"), "year": current["year"],
            "funds": current["values"]["funds"], "progress": record, "sha256": current["sha256"]}


def apply(pid, profile_name, ident, mode):
    key, label = _profile(profile_name)
    catalog = {item["id"]: item for item in definitions()}
    if ident not in catalog:
        raise ValueError("That decision is no longer in custom_decisions.json. Reload the list.")
    item = catalog[ident]
    current = live_cheats.inspect(pid)
    state = _state()
    record = state["profiles"].get(key)
    if record and record.get("nation") != current.get("nation_name"):
        raise ValueError(f"Profile {label} belongs to {record.get('nation')}; choose a different profile for this campaign.")
    if item["mode"] == "instant":
        if mode != "apply":
            raise ValueError("Choose Apply for this one-time decision.")
        values = _absolute_values(current, item["effects"])
        result = live_cheats.edit(pid, values, current["sha256"])
        return {"ok": True, "message": result["message"], "decision": item["name"], "year": current["year"]}

    duration = item["duration_years"]
    annual = item["annual_effects"]
    completion = item.get("completion_effects", {})
    if mode == "start":
        if record and record.get("project", {}).get("active"):
            raise ValueError("This campaign profile already has an active decision project.")
        effects = dict(annual)
        paid = 1
        finished = paid >= duration
        if finished and completion:
            for key, amount in completion.items(): effects[key] = effects.get(key, 0) + amount
        values = _absolute_values(current, effects)
        result = live_cheats.edit(pid, values, current["sha256"])
        project = {"id": ident, "active": not finished, "paid": paid, "last_year": current["year"],
                   "started_year": current["year"], "nation": current.get("nation_name"), "duration_years": duration}
        state["profiles"][key] = {"label": label, "nation": current.get("nation_name"), "project": project}
        _write_state(state)
        return {"ok": True, "message": result["message"] + f" {item['name']}: installment 1 of {duration} recorded for {current['year']}.",
                "progress": state["profiles"][key], "year": current["year"]}
    if mode != "installment":
        raise ValueError("Choose Start or Apply annual installment for this project.")
    if not record or not record.get("project", {}).get("active") or record["project"].get("id") != ident:
        raise ValueError("Start this decision project first.")
    project = record["project"]
    if current["year"] <= project["last_year"]:
        raise ValueError(f"The next installment is available after the campaign reaches {project['last_year'] + 1}.")
    due = min(duration - project["paid"], current["year"] - project["last_year"])
    effects = {key: amount * due for key, amount in annual.items()}
    paid = project["paid"] + due
    finished = paid >= duration
    if finished and completion:
        for key, amount in completion.items(): effects[key] = effects.get(key, 0) + amount
    values = _absolute_values(current, effects)
    result = live_cheats.edit(pid, values, current["sha256"])
    project.update(active=not finished, paid=paid, last_year=current["year"])
    _write_state(state)
    message = result["message"] + f" {item['name']}: {due} annual installment(s) paid; {paid} of {duration} complete."
    if finished:
        message += " Completion effects applied."
    return {"ok": True, "message": message, "progress": state["profiles"][key], "year": current["year"]}
