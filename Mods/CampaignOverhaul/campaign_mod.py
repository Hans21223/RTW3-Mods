"""Reversible Steam-copy update and campaign event pack. Python standard library only."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import shutil
import sys


HERE = Path(__file__).resolve().parent
GAME = HERE.parent.parent
STATE = HERE / "state.json"
EXCLUDE = {"Mods", ".git", ".agents", ".codex", "Save", "_TimeStretch_Backup"}
BASE_FILES = ("Events.dat", "Tips.txt", "ResearchAreas3.dat", "AircraftBasicData3.dat")
EVENT_BASE = HERE / "event_mechanics_base.dat"
EVENT_OUTCOMES = HERE / "event_outcomes.json"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save_json(path, value):
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def state():
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}


def source_files(source):
    for item in sorted(source.rglob("*")):
        rel = item.relative_to(source)
        if any(part in EXCLUDE for part in rel.parts):
            continue
        if item.is_file() and item.name not in {"TimeStretchMod.py", "ErrorLog.txt", "ErrorLogOld.txt"}:
            yield item, rel


def upgrade(source):
    source = source.resolve(strict=True)
    if source == GAME or GAME in source.parents or source in GAME.parents:
        raise ValueError("The Steam source must be a separate installation.")
    if not (source / "RTW3.exe").is_file():
        raise ValueError("No RTW3.exe in the Steam source.")
    if state().get("upgrade"):
        raise ValueError("This copy was already updated. Restore it before another update.")
    source_plan = list(source_files(source))
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = HERE / "backups" / stamp
    backup.mkdir(parents=True)
    original = {}
    # Full pre-update snapshot: includes earlier experiments and custom content.
    for item in sorted(GAME.rglob("*")):
        rel = item.relative_to(GAME)
        if rel.parts[0] in {"Mods", ".git", ".agents", ".codex"} or not item.is_file():
            continue
        dest = backup / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, dest)
        original[rel.as_posix()] = digest(dest)
    record = {
        "version": 1, "source": str(source), "backup": str(backup),
        "original": original, "installed": {}, "complete": False,
    }
    current = {"upgrade": record, "events": False}
    save_json(STATE, current)
    for item, rel in source_plan:
        dest = GAME / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, dest)
        if digest(item) != digest(dest):
            raise ValueError(f"Copy verification failed: {rel}")
        record["installed"][rel.as_posix()] = digest(dest)
    # The Steam copy already has a prior time-stretch mod. Use its original
    # tables, but keep the executable and all other updated assets byte exact.
    for name in BASE_FILES:
        clean = source / "Data" / "_TimeStretch_Backup" / name
        if clean.is_file():
            shutil.copy2(clean, GAME / "Data" / name)
            record["installed"][f"Data/{name}"] = digest(clean)
        baseline = HERE / "vanilla" / name
        baseline.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(GAME / "Data" / name, baseline)
    record["complete"] = True
    record["steam_exe_sha256"] = digest(source / "RTW3.exe")
    manifest = source.parent.parent / "appmanifest_2008100.acf"
    if manifest.exists():
        shutil.copy2(manifest, HERE / "steam_build.acf")
    save_json(STATE, current)
    print(f"Updated {len(source_plan)} files from {source}")
    print(f"Original installation backed up to {backup}")
    print(f"Steam executable unchanged: {digest(GAME / 'RTW3.exe')}")


def parse_events(raw):
    lines = raw.decode("latin-1").splitlines()
    if len(lines) % 4:
        raise ValueError("Expected question plus three responses per event.")
    groups = []
    for i in range(0, len(lines), 4):
        rows = [line.split(";") for line in lines[i:i + 4]]
        if len(rows[0]) != 9 or any(len(row) != 6 for row in rows[1:]):
            raise ValueError(f"Invalid event structure at line {i + 1}.")
        for row in rows[1:]:
            if row == ["", "", "", "", "", "0"]:
                continue
            for value in row[1:]:
                if value.strip():
                    int(value)
        groups.append(rows)
    return groups


EVENT_CONSEQUENCES = {
    1: "technology-sharing agreement",
    2: "treaty negotiations",
    3: "submarine build requirement",
    4: "submarine build requirement",
    5: "destroyer build requirement",
    6: "destroyer build requirement",
    7: "cruiser build requirement",
    8: "cruiser build requirement",
    9: "battleship build requirement",
    10: "reduced battleship build requirement",
    11: "social reform proposal",
    12: "unrest increase",
    13: "technology leak risk",
    14: "technology gain",
    15: "possible unrest increase",
    16: "possible unrest relief",
    20: "sabotage operation",
    25: "possession rebellion risk",
    30: "cruiser colonial deployment",
    31: "battleship colonial deployment",
    40: "arms-control talks",
    41: "stronger arms-control talks",
    50: "peace negotiations",
    51: "low-chance peace negotiations",
    52: "peace on victory terms",
    53: "peace on defeat terms",
    54: "peace negotiations",
    55: "peace with gains",
    56: "continue the war",
    60: "army setback risk",
    61: "army victory chance",
    65: "revolution risk",
    66: "crew-quality improvement, half-maintenance cost",
    70: "base resources -500",
    71: "base resources +500",
    72: "half-maintenance cost",
}


def event_effect_hint(row):
    """One response's effects: its non-zero Budget, Prestige and Tension and its special outcome."""
    parts = [f"{label} {int(value):+d}" for label, value in zip(("Budget", "Prestige", "Tension"), row[1:4])
             if value.strip() and int(value)]
    condition = int(row[5]) if row[5].strip() else 0
    if condition:
        parts.append(EVENT_CONSEQUENCES.get(condition, f"native condition {condition}"))
    return ", ".join(parts) or "no change"


def render_events():
    if not EVENT_BASE.is_file() or not EVENT_OUTCOMES.is_file():
        raise ValueError("The full event baseline or authored outcome table is missing.")
    original = EVENT_BASE.read_bytes()
    groups = parse_events(original)
    stock_groups = parse_events((HERE / "vanilla" / "Events.dat").read_bytes())
    pack = json.loads((HERE / "events.json").read_text(encoding="utf-8"))
    outcomes = json.loads(EVENT_OUTCOMES.read_text(encoding="utf-8"))
    if len(groups) != 100:
        raise ValueError(f"Expected the complete 100-event table; found {len(groups)} groups.")
    disabled_questions = outcomes.get("disabled_questions", [])
    if (not isinstance(disabled_questions, list) or
            any(type(slot) is not int or not 0 <= slot < len(groups) for slot in disabled_questions) or
            len(set(disabled_questions)) != len(disabled_questions)):
        raise ValueError("Disabled event questions must be a unique list of valid event slots.")
    for slot in disabled_questions:
        question = groups[slot][0]
        if slot != 46 or "Socialists in Parliament" not in question[0] or question[5] != "21":
            raise ValueError(f"Refusing to disable an unrecognized high-funds parliamentary event in slot {slot}.")
        # The engine has no disabled-event flag. Move this trigger outside the
        # supported campaign era while preserving its response records.
        question[6:8] = ["9999", "9999"]
    seen = set()
    for event in pack:
        number = event["slot"]
        if number in seen or not 0 <= number < len(groups):
            raise ValueError(f"Duplicate or invalid event slot {number}.")
        seen.add(number)
        group = groups[number]
        if number >= len(stock_groups) or event["match"] not in stock_groups[number][0][0]:
            raise ValueError(f"Event slot {number} changed in this game build.")
        # Keep every trigger, year window, target nation, government flag and
        # numeric response unchanged. Special engine event indexes stay valid.
        text = [event["question"], *event["answers"]]
        if len(text) != 4:
            raise ValueError(f"Expected exactly three answers for slot {number}.")
        for row, caption in zip(group, text):
            caption.encode("ascii")
            if not caption and not row[0]:
                continue
            if not caption or not row[0] or any(c in caption for c in ";\r\n"):
                raise ValueError(f"Invalid caption for slot {number}.")
            row[0] = caption

    for slot_text, response in outcomes.get("add_responses", {}).items():
        slot = int(slot_text)
        if not 0 <= slot < len(groups):
            raise ValueError(f"Invalid response slot {slot}.")
        answer = int(response["answer"])
        if answer not in (0, 1, 2):
            raise ValueError(f"Invalid answer index {answer} in slot {slot}.")
        row = groups[slot][answer + 1]
        if row != ["", "", "", "", "", "0"]:
            raise ValueError(f"Slot {slot}, answer {answer} is not an unused response.")
        effect = response["outcome"]
        if len(effect) != 5 or any(not isinstance(value, int) for value in effect):
            raise ValueError(f"Invalid effect values for slot {slot}, answer {answer}.")
        row[0] = response["caption"]
        row[1:] = [str(value) for value in effect]
        row[0].encode("ascii")

    for slot_text, responses in outcomes.get("overrides", {}).items():
        slot = int(slot_text)
        if not 0 <= slot < len(groups):
            raise ValueError(f"Invalid outcome override slot {slot}.")
        for answer_text, effect in responses.items():
            answer = int(answer_text)
            if answer not in (0, 1, 2) or len(effect) != 5 or any(not isinstance(value, int) for value in effect):
                raise ValueError(f"Invalid outcome override for slot {slot}, answer {answer}.")
            row = groups[slot][answer + 1]
            if row == ["", "", "", "", "", "0"]:
                raise ValueError(f"Cannot override an unused response in slot {slot}, answer {answer}.")
            row[1:] = [str(value) for value in effect]

    for slot_text, responses in outcomes.get("captions", {}).items():
        slot = int(slot_text)
        if not 0 <= slot < len(groups):
            raise ValueError(f"Invalid caption slot {slot}.")
        for answer_text, caption in responses.items():
            answer = int(answer_text)
            if answer not in (0, 1, 2) or not caption or any(c in caption for c in ";\r\n"):
                raise ValueError(f"Invalid caption for slot {slot}, answer {answer}.")
            caption.encode("ascii")
            groups[slot][answer + 1][0] = caption

    for slot, group in enumerate(groups):
        active = [row for row in group[1:] if row != ["", "", "", "", "", "0"]]
        if len(active) != 3:
            raise ValueError(f"Slot {slot} must present three distinct, active responses; found {len(active)}.")
        # The answer buttons are one line 737/849/737 px wide and clip what doesn't fit (XX/YY grow into nation
        # names); the question label wraps over five lines, and every question plus this fits in four.
        group[0][0] += " Effects: " + " ".join(f"({n}) {event_effect_hint(row)}." for n, row in enumerate(active, 1))

    newline = "\r\n" if b"\r\n" in original else "\n"
    rendered = newline.join(";".join(row) for group in groups for row in group)
    if original.endswith((b"\r", b"\n")):
        rendered += newline
    output = rendered.encode("latin-1")
    parsed = parse_events(output)
    baseline = parse_events(original)
    if len(parsed) != len(baseline):
        raise ValueError("Event count changed.")
    additions = {(int(slot), int(response["answer"]))
                 for slot, response in outcomes.get("add_responses", {}).items()}
    overrides = {(int(slot), int(answer))
                 for slot, responses in outcomes.get("overrides", {}).items()
                 for answer in responses}
    for slot, (after, before) in enumerate(zip(parsed, baseline)):
        expected_question = before[0][1:]
        if slot in disabled_questions:
            expected_question[5:7] = ["9999", "9999"]
        if after[0][1:] != expected_question:
            raise ValueError(f"Question mechanics changed in event {slot}.")
        for answer, (a, b) in enumerate(zip(after[1:], before[1:])):
            if (slot, answer) in additions:
                if b != ["", "", "", "", "", "0"]:
                    raise ValueError(f"Added answer overwrote a native response in event {slot}.")
                continue
            if (slot, answer) not in overrides and a[1:] != b[1:]:
                raise ValueError(f"Undeclared event effect change in event {slot}, answer {answer}.")
    return output, len(groups), len(groups)


def apply_events():
    if (GAME / "Mods" / "Manager" / "state.json").exists():
        raise ValueError("The Mod Manager now owns these files. Enable Naval Staff Briefings there.")
    current = state()
    if not current.get("upgrade", {}).get("complete"):
        raise ValueError("Run the Steam-copy update first.")
    output, changed, total = render_events()
    dest = GAME / "Data" / "Events.dat"
    known = current.get("events_sha256") or digest(HERE / "vanilla" / "Events.dat")
    if digest(dest) != known:
        raise ValueError("Events.dat has untracked edits. Preserve them before applying.")
    dest.write_bytes(output)
    tips = (HERE / "vanilla" / "Tips.txt").read_bytes()
    marker = (b"Naval Staff Briefings: all 100 event groups offer three choices with available Budget, Prestige and Tension effect notes.\r\n"
              b"Special outcomes follow the original RTW3 event rules.\r\n")
    tip_dest = GAME / "Data" / "Tips.txt"
    known_tips = current.get("tips_sha256") or digest(HERE / "vanilla" / "Tips.txt")
    if digest(tip_dest) != known_tips:
        raise ValueError("Tips.txt has untracked edits.")
    tip_dest.write_bytes(marker + tips)
    current.update(events=True, events_sha256=digest(dest), tips_sha256=digest(tip_dest))
    save_json(STATE, current)
    print(f"Applied effect notes and three choices across all {total} event groups.")
    print("Declared outcome adjustments are checked against the saved 100-event baseline.")


def restore_events():
    current = state()
    manager = GAME / "Mods" / "Manager" / "state.json"
    if manager.exists() and json.loads(manager.read_text(encoding="utf-8")).get("enabled"):
        raise ValueError("Disable the event pack through the Mod Manager.")
    if not current.get("events"):
        print("Event pack is already disabled.")
        return
    for name, key in (("Events.dat", "events_sha256"), ("Tips.txt", "tips_sha256")):
        if digest(GAME / "Data" / name) != current[key]:
            raise ValueError(f"{name} has untracked edits; refusing to overwrite them.")
    for name in ("Events.dat", "Tips.txt"):
        shutil.copy2(HERE / "vanilla" / name, GAME / "Data" / name)
    current.update(events=False)
    current.pop("events_sha256", None)
    current.pop("tips_sha256", None)
    save_json(STATE, current)
    print("Original updated-Steam event tables restored.")


def restore_update():
    manager = GAME / "Mods" / "Manager" / "state.json"
    if manager.exists() and json.loads(manager.read_text(encoding="utf-8")).get("enabled"):
        raise ValueError("Choose No mods and Apply in the Mod Manager before rolling back the update.")
    current = state()
    record = current.get("upgrade")
    if not record:
        raise ValueError("No update backup exists.")
    allowed = dict(record["installed"])
    if current.get("events"):
        allowed.update({"Data/Events.dat": current["events_sha256"], "Data/Tips.txt": current["tips_sha256"]})
    for rel, expected in allowed.items():
        dest = GAME / rel
        if dest.exists() and digest(dest) != expected:
            raise ValueError(f"Untracked changes in {rel}; rollback stopped before changing files.")
    backup = Path(record["backup"])
    for rel, expected in record["original"].items():
        if digest(backup / rel) != expected:
            raise ValueError(f"Backup verification failed: {rel}")
    # Keep files introduced by this update recoverable too.
    displaced = HERE / "rolled-back-update"
    for rel in record["installed"]:
        dest = GAME / rel
        if rel not in record["original"] and dest.exists():
            moved = displaced / rel
            moved.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(dest), str(moved))
    for rel in record["installed"]:
        if rel in record["original"]:
            dest = GAME / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup / rel, dest)
    shutil.copy2(STATE, HERE / "rolled-back-state.json")
    save_json(STATE, {"events": False, "previous_backup": str(backup)})
    print(f"Pre-update installation restored from {backup}")


def verify():
    current = state()
    record = current.get("upgrade")
    if not record or not record["complete"]:
        raise ValueError("Update is not complete.")
    expected = dict(record["installed"])
    # RTW3 rewrites this scratch design during ordinary ship-designer use, and
    # Data/IDes holds starting designs players replace with custom ships. Neither
    # is an immutable installation file and no mod reads them. Explicitly managed
    # mod files are added back below and still receive their normal integrity checks.
    expected.pop("Data/tmpShip.ttp", None)
    expected = {rel: sha for rel, sha in expected.items() if not rel.startswith("Data/IDes/")}
    if current.get("events"):
        expected["Data/Events.dat"] = current["events_sha256"]
        expected["Data/Tips.txt"] = current["tips_sha256"]
    manager = GAME / "Mods" / "Manager" / "state.json"
    if manager.exists():
        for entry in json.loads(manager.read_text(encoding="utf-8")).get("applied", {}).values():
            expected[entry["target"]] = entry["sha256"]
    issues = [rel for rel, sha in expected.items() if not (GAME / rel).is_file() or digest(GAME / rel) != sha]
    if issues:
        raise ValueError("Changed/missing installed files: " + ", ".join(issues[:20]))
    if current.get("events"):
        output, changed, total = render_events()
        if (GAME / "Data" / "Events.dat").read_bytes() != output:
            raise ValueError("Installed events differ from the generated event pack.")
        print(f"Event validation passed: {total} groups, 300 annotated choices; declared outcome changes only.")
    print(f"Verified {len(expected)} installed files. Official Steam executable is byte exact.")
    print(f"Rollback backup: {record['backup']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("upgrade", "apply-events", "restore-events", "restore-update", "verify", "status"))
    parser.add_argument("--source", type=Path, default=Path(r"D:\SteamLibrary\steamapps\common\Rule the Waves 3"))
    args = parser.parse_args()
    try:
        if args.command == "upgrade":
            upgrade(args.source)
        elif args.command == "apply-events":
            apply_events()
        elif args.command == "restore-events":
            restore_events()
        elif args.command == "restore-update":
            restore_update()
        elif args.command == "verify":
            verify()
        else:
            current = state()
            print(json.dumps({"game": str(GAME), "updated": current.get("upgrade", {}).get("complete", False), "events": current.get("events", False), "weekly": "experimental runtime attachment only"}, indent=2))
    except (OSError, ValueError) as error:
        print(f"Stopped: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
