"""Byte-preserving, backed-up RTW3 campaign save editor for testing."""
from __future__ import annotations
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import shutil
import uuid
import project_cheats as projects

HERE = Path(__file__).resolve().parent
SAVE_ROOT = Path.home() / "Documents" / "My Games" / "Rule the Waves 3" / "Save"
BACKUPS = HERE / "save-backups"
FIELDS = {
    "funds": ("Funds", 0, 1_000_000_000),
    "income_level": ("BudgetModifier", 3, 500),
    "income_resources": ("BaseResources", 1, 10_000_000),
    "dock_tons": ("DockSize", 1000, 1_000_000),
    "research_speed": ("ResearchSpeed", 1, 1000),
    "prestige": ("Prestige", 1, 100),
    "unrest": ("UnrestLevel", 0, 10),
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse(raw):
    lines = raw.decode("latin-1").splitlines(keepends=True)
    sections, positions = {}, {}
    section = None
    for index, line in enumerate(lines):
        text = line.rstrip("\r\n")
        if index == 0 and text.startswith("\xef\xbb\xbf"):
            text = text[3:]
        if text.startswith("[") and text.endswith("]"):
            section = text[1:-1]
            sections.setdefault(section, {})
        elif section and "=" in text:
            key, value = text.split("=", 1)
            if (section, key) in positions:
                raise ValueError(f"Duplicate save field: {section}/{key}")
            sections[section][key] = value
            positions[section, key] = index
    if not {"Year", "Month", "Day"} <= sections.get("General", {}).keys():
        raise ValueError("This is not a supported RTW3 campaign save.")
    return lines, sections, positions


def replace_fields(raw, changes):
    lines, sections, positions = parse(raw)
    for (section, key), value in changes.items():
        if (section, key) not in positions:
            raise ValueError(f"Required save field is missing: {section}/{key}")
        index = positions[section, key]
        line = lines[index]
        ending = line[len(line.rstrip("\r\n")):]
        lines[index] = key + "=" + str(int(value)) + ending
    output = "".join(lines).encode("latin-1")
    _, check, _ = parse(output)
    for (section, key), value in changes.items():
        if check[section][key] != str(value):
            raise ValueError("Save edit failed validation.")
    return output


def resolve_save(value):
    path = Path(value).resolve(strict=True)
    if not path.is_relative_to(SAVE_ROOT.resolve()) or path.suffix.lower() != ".bcs":
        raise ValueError("Choose a .bcs campaign inside the RTW3 Save folder.")
    if path.parent.parent.resolve() != SAVE_ROOT.resolve() or not re.fullmatch(r"Game[1-9]", path.parent.name):
        raise ValueError("The save must belong to a normal Game1-Game9 slot.")
    return path


def list_saves():
    rows = []
    for folder in sorted(SAVE_ROOT.glob("Game[1-9]")):
        for path in sorted(folder.glob("*.bcs")):
            try:
                _, sections, _ = parse(path.read_bytes())
                general = sections["General"]
                rows.append({"path": str(path), "slot": folder.name,
                             "name": folder.name+" / "+path.stem+" / "+sections.get("Nation0", {}).get("Name", "Unknown")+
                             " / "+f"{general['Year']}-{int(general['Month']):02d}-{int(general['Day']):02d}",
                             "modified": path.stat().st_mtime})
            except (OSError, ValueError, KeyError):
                continue
    rows.sort(key=lambda row: -row["modified"])
    return {"ok": True, "saves": rows, "root": str(SAVE_ROOT)}


def inspect(value, nation="Nation0"):
    path = resolve_save(value)
    _, sections, _ = parse(path.read_bytes())
    if not re.fullmatch(r"Nation\d+", nation) or nation not in sections:
        raise ValueError("Select a valid nation in this save.")
    info = sections[nation]
    current = {}
    for label, (key, minimum, maximum) in FIELDS.items():
        owner = "General" if label == "research_speed" else nation
        if key in sections[owner]:
            current[label] = int(sections[owner][key])
    year = int(sections["General"]["Year"])
    ships, fleet_ships = [], []
    data = sections.get(nation+"Ships", {})
    for key in data:
        match = re.fullmatch(r"Ship(\d+)Name", key)
        if not match:
            continue
        number = int(match.group(1))
        prefix = "Ship"+str(number)
        row = {field: int(data.get(prefix+field, "0")) for field in projects.SHIP_WIDTHS}
        project = projects.describe(row, year)
        if not projects.fleet_visible(row): continue
        fleet_ships.append({"index": number, "name": data[key], "type": data.get(prefix+"ShipType", ""),
                            "kind": project["kind"] if project else "inactive",
                            "remaining_turns": project["remaining_turns"] if project else 0})
        if project:
            ships.append({"index": number, "name": data[key], "type": data.get(prefix+"ShipType", ""),
                          **project})
    return {"ok": True, "path": str(path), "sha256": digest(path), "nation": nation, "bulk_projects": True,
            "nation_name": info.get("Name", nation), "values": current, "ships": ships, "fleet_ships": fleet_ships,
            "nations": [{"id": key, "name": item.get("Name", key)} for key, item in sections.items() if re.fullmatch(r"Nation\d+", key)],
            "note": "Close RTW3 before editing a save. ALL buttons back up and apply their own 1-turn action immediately. Other edits use Apply. The list shows the nation's non-sunk fleet; only active yard jobs can be sped up. Construction costs remain. Research speed is campaign-wide."}


def edit(value, nation, values, ship_index=None, turns=None, expected_hash=None, all_projects=None):
    import mod_loader
    if mod_loader.running_games():
        raise ValueError("Close RTW3 before editing a save, then reload it after applying cheats.")
    path = resolve_save(value)
    if not expected_hash or digest(path) != expected_hash:
        raise ValueError("The save changed. Refresh its values before applying cheats.")
    raw = path.read_bytes()
    _, sections, _ = parse(raw)
    if not re.fullmatch(r"Nation\d+", nation) or nation not in sections:
        raise ValueError("Invalid nation.")
    changes = {}
    for label, value in values.items():
        if label not in FIELDS or isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("Unsupported cheat field or non-integer value.")
        key, minimum, maximum = FIELDS[label]
        if not minimum <= value <= maximum:
            raise ValueError(f"{label} must be between {minimum} and {maximum}.")
        owner = "General" if label == "research_speed" else nation
        if int(sections[owner][key]) != value:
            changes[owner, key] = value
    selected = projects.select(inspect(path, nation)["ships"], ship_index, all_projects)
    for ship in selected:
        prefix = f"Ship{ship['index']}"
        owner = nation+"Ships"
        for field, new in projects.changes(ship, 1 if all_projects else turns).items():
            if int(sections[owner][prefix+field]) != new:
                changes[owner, prefix+field] = new
    if not changes:
        return {"ok": True, "message": "No values changed.", "save": inspect(path, nation)}
    output = replace_fields(raw, changes)
    backup = commit(path, output, expected_hash, [{"section": section, "key": key, "value": val} for (section, key), val in changes.items()])
    return {"ok": True, "message": f"Applied {len(changes)} changes" + (f" across {len(selected)} eligible projects" if all_projects else "") + ". Reload this save in RTW3.", "backup": str(backup), "save": inspect(path, nation)}


def commit(path, output, expected_hash, fields):
    """Shared atomic save writer; callers validate their supported field schema."""
    import mod_loader
    if mod_loader.running_games():
        raise ValueError("Close RTW3 before writing a saved campaign.")
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")+"-"+uuid.uuid4().hex[:6]
    backup = BACKUPS / stamp / path.parent.name
    shutil.copytree(path.parent, backup)
    if digest(backup / path.name) != expected_hash:
        raise ValueError("The save backup did not verify. No edit applied.")
    temporary = path.with_name(path.name+".cheat-tmp")
    if temporary.exists():
        raise ValueError("A previous temporary cheat save needs inspection.")
    try:
        temporary.write_bytes(output)
        parse(temporary.read_bytes())
        if digest(path) != expected_hash:
            raise ValueError("The save changed while backing up. No edit applied.")
        if mod_loader.running_games():
            raise ValueError("RTW3 started while preparing the save. No edit applied.")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    record = {"save": str(path), "backup": str(backup), "before_sha256": expected_hash,
              "after_sha256": digest(path), "fields": fields}
    (backup.parent / "changes.json").write_text(json.dumps(record, indent=2)+"\n", encoding="utf-8")
    return backup
