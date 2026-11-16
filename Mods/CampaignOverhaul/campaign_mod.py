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


def render_events():
    original = (HERE / "vanilla" / "Events.dat").read_bytes()
    groups = parse_events(original)
    pack = json.loads((HERE / "events.json").read_text(encoding="utf-8"))
    seen = set()
    for event in pack:
        number = event["slot"]
        if number in seen or not 0 <= number < len(groups):
            raise ValueError(f"Duplicate or invalid event slot {number}.")
        seen.add(number)
        group = groups[number]
        if event["match"] not in group[0][0]:
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
    newline = "\r\n" if b"\r\n" in original else "\n"
    rendered = newline.join(";".join(row) for group in groups for row in group)
    if original.endswith((b"\r", b"\n")):
        rendered += newline
    output = rendered.encode("latin-1")
    parsed = parse_events(output)
    baseline = parse_events(original)
    if len(parsed) != len(baseline):
        raise ValueError("Event count changed.")
    for after, before in zip(parsed, baseline):
        if any(a[1:] != b[1:] for a, b in zip(after, before)):
            raise ValueError("An engine condition or outcome changed.")
    return output, len(seen), len(groups)


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
    marker = b"Campaign Overhaul: reworked naval staff briefings and choices are active. Engine turns remain monthly unless the experimental weekly runtime mod is attached.\r\n"
    tip_dest = GAME / "Data" / "Tips.txt"
    known_tips = current.get("tips_sha256") or digest(HERE / "vanilla" / "Tips.txt")
    if digest(tip_dest) != known_tips:
        raise ValueError("Tips.txt has untracked edits.")
    tip_dest.write_bytes(marker + tips)
    current.update(events=True, events_sha256=digest(dest), tips_sha256=digest(tip_dest))
    save_json(STATE, current)
    print(f"Applied {changed} reworked events within the original {total} event slots.")
    print("All original event conditions, dates, targets and game effects preserved.")


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
        print(f"Event validation passed: {changed} reworked, {total} total; all mechanics preserved.")
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
