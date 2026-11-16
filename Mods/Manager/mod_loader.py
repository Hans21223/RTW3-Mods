"""RTW3 data and runtime mod loader. Uses only Python's standard library."""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile


HERE = Path(__file__).resolve().parent
GAME = HERE.parent.parent
LIBRARY = GAME / "Mods" / "Library"
STATE = HERE / "state.json"
ALLOWED_ROOTS = {"data", "designs", "flags", "images", "scenarios", "shipparts", "sounds"}
CONTENT_EXTENSIONS = {".dat", ".txt", ".bmp", ".png", ".jpg", ".jpeg", ".gif", ".wav", ".mp3", ".ogg", ".sdf", ".des", ".acs", ".lyr", ".act", ".ndt", ".nsc", ".ini", ".ttp", ".tdf", ".hus", ".tus", ".eqs"}
RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}
MAX_PACKAGE_BYTES = 256 * 1024 * 1024
RELEASE_EXE = "355e55650b0eb565bfda5ba71e2a9a6697371a2ba612582dbf9bd769f242a4f2"   # Steam build 24739009, 1.01.44
sys.path.insert(0, str(GAME / "Mods" / "CampaignOverhaul"))
import campaign_mod
import weekly_runtime
import runtime_registry

# Compatibility for package validation and external tooling. The reviewed
# registry is the single source of schemas, invocation and launch ordering.
ADAPTERS = runtime_registry.SCHEMAS


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def load_state():
    if not STATE.exists():
        raise ValueError("Manager not initialized. Run bootstrap first.")
    return json.loads(STATE.read_text(encoding="utf-8"))


def safe_relative(value):
    if not isinstance(value, str) or not value or "\\" in value or ":" in value or "\x00" in value:
        raise ValueError(f"Invalid relative path: {value!r}")
    rel = PurePosixPath(value)
    if rel.is_absolute() or any(part in {"..", "."} or part.rstrip(" .") != part or part.split(".")[0].lower() in RESERVED for part in rel.parts):
        raise ValueError(f"Unsafe relative path: {value}")
    if str(rel) != value or any(ord(char) < 32 or char in '<>"|?*' for char in value):
        raise ValueError(f"Non-canonical relative path: {value}")
    return rel


def inside(root, rel):
    candidate = root.joinpath(*safe_relative(rel).parts)
    if not candidate.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Path escapes {root}: {rel}")
    # Reject reparse points/symlinks even when their final target is in the root.
    for part in (candidate, *candidate.parents):
        if part == root:
            break
        if part.is_symlink() or (part.exists() and getattr(part, "is_junction", lambda: False)()):
            raise ValueError(f"Linked paths are not allowed: {rel}")
    return candidate


def target_path(value):
    rel = safe_relative(value)
    if len(rel.parts) < 2 or rel.parts[0].lower() not in ALLOWED_ROOTS:
        raise ValueError(f"Mods can replace game content folders only: {value}")
    if rel.suffix.lower() not in CONTENT_EXTENSIONS:
        raise ValueError(f"Unsupported content file: {value}")
    return inside(GAME, value)


def runtime_entries(mod):
    """A runtime package's adapters: one {"adapter": ...} object, or a list of them (merged packages)."""
    runtime = mod.get("runtime")
    return runtime if isinstance(runtime, list) else [runtime]


def runtime_settings(runtime_mods):
    return {entry["adapter"]: {key: value for key, value in entry.items() if key != "adapter"}
            for mod in runtime_mods for entry in runtime_entries(mod)}


def read_manifest(folder):
    manifest = json.loads((folder / "mod.json").read_text(encoding="utf-8-sig"))
    if manifest.get("schema") != 1:
        raise ValueError("Unsupported mod manifest schema.")
    ident = manifest.get("id", "")
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,63}", ident):
        raise ValueError("Mod ID must use 2-64 lower-case letters, digits, dots, underscores or hyphens.")
    for key in ("name", "version", "description"):
        if not isinstance(manifest.get(key), str) or not manifest[key].strip():
            raise ValueError(f"Mod {ident} needs {key}.")
    if manifest.get("kind") not in {"data", "runtime"}:
        raise ValueError(f"Unsupported mod kind in {ident}.")
    for key in ("requires", "conflicts", "overrides"):
        values = manifest.get(key, [])
        if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
            raise ValueError(f"Invalid {key} in {ident}.")
    seen = set()
    if not isinstance(manifest.get("files", []), list):
        raise ValueError("Manifest files must be an array.")
    for item in manifest.get("files", []):
        source, target = item["source"], item["target"]
        if not inside(folder, source).is_file():
            raise ValueError(f"Missing packaged file: {source}")
        target_path(target)
        key = target.casefold()
        if key in seen:
            raise ValueError(f"Duplicate target in {ident}: {target}")
        seen.add(key)
    if manifest["kind"] == "runtime":
        entries = runtime_entries(manifest)
        if not entries or any(not isinstance(runtime, dict) or runtime.get("adapter") not in ADAPTERS for runtime in entries):
            raise ValueError("Unknown runtime adapter.")
        if len({runtime["adapter"] for runtime in entries}) != len(entries):
            raise ValueError(f"{ident} lists a runtime adapter twice.")
        for runtime in entries:
            for key, value in runtime.items():
                if key == "adapter":
                    continue
                if key not in ADAPTERS[runtime["adapter"]]:
                    raise ValueError(f"Unknown {runtime['adapter']} setting: {key}")
                low, high = ADAPTERS[runtime["adapter"]][key]
                if type(value) is not int or not low <= value <= high:
                    raise ValueError(f"{runtime['adapter']} {key} must be a whole number from {low} to {high}.")
            if runtime["adapter"] == "calendar-days" and not manifest.get("experimental"):
                raise ValueError("The calendar runtime mod must be marked experimental.")
    manifest["folder"] = str(folder)
    return manifest


def catalog():
    valid, invalid = {}, []
    LIBRARY.mkdir(parents=True, exist_ok=True)
    for folder in sorted(LIBRARY.iterdir()):
        if not folder.is_dir() or folder.name.startswith("."):
            continue
        try:
            mod = read_manifest(folder)
            if mod["id"] in valid:
                raise ValueError("Duplicate mod ID.")
            valid[mod["id"]] = mod
        except (OSError, ValueError, KeyError, TypeError) as error:
            invalid.append({"folder": folder.name, "error": str(error)})
    return valid, invalid


def running_games():
    if sys.platform != "win32":
        return []
    weekly_runtime.configure_api()
    return [{"pid": pid, "path": str(path)} for pid, path in weekly_runtime.process_candidates()]


def ensure_closed():
    if running_games():
        raise ValueError("Close RTW3 before applying or restoring data mods.")


@contextlib.contextmanager
def operation_lock():
    lock = HERE / "operation.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise ValueError("Another mod operation is in progress. If a previous run crashed, inspect operation.lock before removing it.")
    try:
        os.write(fd, str(os.getpid()).encode("ascii"))
        os.close(fd)
        yield
    finally:
        lock.unlink(missing_ok=True)


def bootstrap():
    with operation_lock():
        if STATE.exists():
            return status()
        ensure_closed()
        legacy = campaign_mod.state()
        if not legacy.get("upgrade"):   # a release install: the player's own game folder, no Steam-copy update
            import modern_tree
            if sha(GAME / "RTW3.exe") != RELEASE_EXE:
                raise ValueError("These mods need Rule the Waves 3 1.01.44 (Steam build 24739009). Update the game in Steam.")
            if sha(GAME / "Data" / "ResearchAreas3.dat") != modern_tree.VANILLA_SHA256:
                raise ValueError("Data/ResearchAreas3.dat is not the game's original file. In Steam, verify the integrity "
                                 "of the game files, then open the Mod Manager again.")
            write_json(STATE, {"schema": 1, "enabled": [], "applied": {}, "originals": {}, "history": [],
                               "game_sha256": RELEASE_EXE, "build": "24739009"})
            return status()
        if not legacy.get("upgrade", {}).get("complete"):
            raise ValueError("Finish the local Steam-copy update before initializing the manager.")
        event_data, changed, total = campaign_mod.render_events()
        event_folder = LIBRARY / "campaign-events" / "Files" / "Data"
        event_folder.mkdir(parents=True, exist_ok=True)
        (event_folder / "Events.dat").write_bytes(event_data)
        tips = (campaign_mod.HERE / "vanilla" / "Tips.txt").read_bytes()
        (event_folder / "Tips.txt").write_bytes(b"Naval Staff Briefings: 24 reworked campaign decisions are active.\r\n" + tips)
        was_enabled = legacy.get("events", False)
        if was_enabled:
            with contextlib.redirect_stdout(io.StringIO()):
                campaign_mod.restore_events()
        write_json(STATE, {"schema": 1, "enabled": [], "applied": {}, "originals": {}, "history": [],
                           "game_sha256": legacy["upgrade"]["steam_exe_sha256"], "build": "24739009"})
    if was_enabled:
        return apply(["campaign-events"])
    return status()


def resolve_plan(enabled):
    mods, errors = catalog()
    if len(enabled) != len(set(enabled)):
        raise ValueError("A mod was selected twice.")
    plan = {}
    runtime = []
    selected = set(enabled)
    for ident in enabled:
        if ident not in mods:
            raise ValueError(f"Selected mod is missing or invalid: {ident}")
        mod = mods[ident]
        missing = set(mod.get("requires", [])) - selected
        if missing:
            raise ValueError(f"{mod['name']} requires: {', '.join(sorted(missing))}")
        conflicts = set(mod.get("conflicts", [])) & selected
        if conflicts:
            raise ValueError(f"{mod['name']} conflicts with: {', '.join(sorted(conflicts))}")
        for item in mod.get("files", []):
            key = item["target"].casefold()
            # A sub-mod lists the mods whose files it replaces ("overrides"); whichever is enabled first, it wins.
            if key in plan and plan[key]["owner"] not in mod.get("overrides", []):
                if ident in mods[plan[key]["owner"]].get("overrides", []):
                    continue
                raise ValueError(f"File conflict: {item['target']} is supplied by {plan[key]['owner']} and {ident}. Choose one mod.")
            plan[key] = {"target": item["target"], "source": str(inside(Path(mod["folder"]), item["source"])), "owner": ident}
        if mod["kind"] == "runtime":
            runtime.append(mod)
    adapters = [entry["adapter"] for mod in runtime for entry in runtime_entries(mod)]
    if len(adapters) != len(set(adapters)):
        raise ValueError("Only one mod per runtime adapter can be enabled.")
    runtime_registry.plan(adapters, runtime_settings(runtime))
    return mods, plan, runtime


def original_record(rel):
    dest = target_path(rel)
    record = {"target": rel, "exists": dest.exists()}
    if dest.exists():
        record["sha256"] = sha(dest)
        backup = inside(HERE / "baseline", rel)
        backup.parent.mkdir(parents=True, exist_ok=True)
        if backup.exists() and sha(backup) != record["sha256"]:
            raise ValueError(f"A different baseline already exists for {rel}.")
        shutil.copy2(dest, backup)
    return record


def check_managed_files(current):
    for key, record in current["originals"].items():
        dest = target_path(record["target"])
        expected = current["applied"].get(key, record)
        if expected.get("exists", True):
            if not dest.is_file() or sha(dest) != expected["sha256"]:
                raise ValueError(f"Untracked changes in {record['target']}. Back up your edits before applying mods.")
        elif dest.exists():
            raise ValueError(f"A new file appeared at {record['target']}. It will not be overwritten.")


def atomic_copy(source, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    temporary = dest.with_name(dest.name + ".rtwmod-tmp")
    if temporary.exists():
        raise ValueError(f"A previous temporary file needs inspection: {temporary}")
    try:
        shutil.copy2(source, temporary)
        temporary.replace(dest)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def apply(enabled):
    with operation_lock():
        ensure_closed()
        current = load_state()
        mods, plan, runtime = resolve_plan(enabled)
        if sha(GAME / "RTW3.exe") != current["game_sha256"]:
            raise ValueError("The game executable changed. Recheck compatibility before loading mods.")
        check_managed_files(current)
        for key, item in plan.items():
            if key not in current["originals"]:
                current["originals"][key] = original_record(item["target"])
        # Persist new baselines before installation so a failed copy remains recoverable.
        write_json(STATE, current)
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
        transaction = HERE / "backups" / stamp
        transaction.mkdir(parents=True)
        before = {}
        for key, original in current["originals"].items():
            rel = original["target"]
            dest = target_path(rel)
            before[key] = {"target": rel, "exists": dest.exists()}
            if dest.exists():
                saved = inside(transaction / "before", rel)
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dest, saved)
                before[key]["sha256"] = sha(saved)
        write_json(transaction / "transaction.json", {"before": before, "previous_state": current, "selected": enabled, "complete": False})
        after = {}
        try:
            for key, original in current["originals"].items():
                rel = original["target"]
                dest = target_path(rel)
                if key in plan:
                    item = plan[key]
                    atomic_copy(Path(item["source"]), dest)
                    after[key] = {"target": rel, "owner": item["owner"], "sha256": sha(dest), "exists": True}
                    if sha(dest) != sha(item["source"]):
                        raise ValueError(f"Post-install verification failed: {rel}")
                elif original["exists"]:
                    saved = inside(HERE / "baseline", rel)
                    if sha(saved) != original["sha256"]:
                        raise ValueError(f"Baseline verification failed: {rel}")
                    atomic_copy(saved, dest)
                elif dest.exists():
                    displaced = inside(transaction / "removed-mod-files", rel)
                    displaced.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(dest), str(displaced))
        except Exception:
            for key, record in before.items():
                dest = target_path(record["target"])
                if record["exists"]:
                    atomic_copy(inside(transaction / "before", record["target"]), dest)
                elif dest.exists():
                    displaced = inside(transaction / "failed-new-files", record["target"])
                    displaced.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(dest), str(displaced))
            raise
        current.update(enabled=enabled, applied=after)
        current["history"].append({"when": stamp, "enabled": enabled, "backup": str(transaction)})
        current.pop("runtime_pending_pids", None)
        current.pop("runtime_pending_mods", None)
        write_json(STATE, current)
        write_json(transaction / "transaction.json", {"before": before, "selected": enabled, "complete": True})
        return {"ok": True, "message": f"Applied {len(enabled)} mod(s). {len(after)} content files active.", "backup": str(transaction), "status": status()}


def status():
    current = load_state()
    mods, errors = catalog()
    running = running_games()
    pending = bool(set(current.get("runtime_pending_pids", [])) & {game["pid"] for game in running})
    rows = []
    for ident, mod in mods.items():
        row = {k: v for k, v in mod.items() if k not in {"files", "runtime"}}
        row["enabled"] = ident in current["enabled"]
        row["pending_restart"] = pending and ident in current.get("runtime_pending_mods", [])
        row["targets"] = [item["target"] for item in mod.get("files", [])]
        rows.append(row)
    return {"ok": True, "game": str(GAME), "build": current["build"], "mods": rows, "invalid_mods": errors,
            "enabled": current["enabled"], "running": running, "runtime_restart_required": pending, "history_count": len(current["history"]),
            "weekly_limit": "Calendar only: monthly economy, AI and timers are not rebalanced."}


def verify():
    current = load_state()
    if sha(GAME / "RTW3.exe") != current["game_sha256"]:
        raise ValueError("The game executable changed. Recheck compatibility before loading mods.")
    check_managed_files(current)
    mods, plan, runtime = resolve_plan(current["enabled"])
    for key, item in plan.items():
        if sha(item["source"]) != sha(target_path(item["target"])):
            raise ValueError(f"Mod source changed since apply: {item['target']}. Reapply after reviewing.")
    if campaign_mod.state().get("upgrade"):   # the local Steam copy also checks every file its update installed
        with contextlib.redirect_stdout(io.StringIO()):
            campaign_mod.verify()
    return {"ok": True, "message": "Verified the Steam update, every managed content file and all active mod packages. Executable unchanged.", "enabled": current["enabled"]}


def stage_runtime(identifiers):
    """Select empty-file runtime adapters for next launch without touching a running game."""
    with operation_lock():
        current = load_state()
        mods, errors = catalog()
        for ident in identifiers:
            if ident not in mods or mods[ident]["kind"] != "runtime" or mods[ident].get("files"):
                raise ValueError("Only file-free runtime mods can be staged for next launch.")
        enabled = list(dict.fromkeys(current["enabled"]+identifiers))
        resolve_plan(enabled)
        previous = list(current["enabled"])
        current["enabled"] = enabled
        running = running_games()
        if running:
            current["runtime_pending_pids"] = [game["pid"] for game in running]
            current["runtime_pending_mods"] = list(identifiers)
        if enabled != previous:
            current["history"].append({"action": "stage-runtime", "time": dt.datetime.now().isoformat(),
                                       "previous_enabled": previous, "enabled": enabled, "files_changed": False})
        write_json(STATE, current)
        return {"ok": True, "message": "Runtime mods selected for the next manager launch. The running game and campaign were not modified.", "status": status()}


def unpack(package, root):
    """A ZIP into `root`, refusing unsafe or linked paths, duplicates and oversized packages."""
    root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(package) as archive:
        entries = archive.infolist()
        if len(entries) > 10000 or sum(entry.file_size for entry in entries) > MAX_PACKAGE_BYTES:
            raise ValueError("Package exceeds the 256 MB / 10,000 entry limit.")
        names = set()
        for entry in entries:
            name = entry.filename.rstrip("/")
            safe_relative(name)
            if name.casefold() in names:
                raise ValueError("Package contains duplicate file names.")
            names.add(name.casefold())
            if (entry.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("Package contains a symbolic link.")
            dest = inside(root, name)
            if entry.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(entry) as source, dest.open("wb") as output:
                    shutil.copyfileobj(source, output)


def import_package(package):
    if not package.is_file():
        raise ValueError("ZIP package was not found.")
    with operation_lock(), tempfile.TemporaryDirectory(prefix="rtw-import-", dir=HERE) as temp:
        root = Path(temp)
        unpack(package, root)
        manifests = list(root.rglob("mod.json"))
        if len(manifests) != 1:
            raise ValueError("A package must contain exactly one mod.json.")
        mod = read_manifest(manifests[0].parent)
        destination = LIBRARY / mod["id"]
        if destination.exists():
            raise ValueError("A mod with that ID already exists. Disable and archive it before importing another version.")
        shutil.copytree(manifests[0].parent, destination)
        return {"ok": True, "message": f"Imported {mod['name']} {mod['version']}. Select it and Apply to enable it.", "status": status()}


def wrap(root, name, package):
    """A data mod from loose game files, placed as the original Mod Manager placed them: from the first folder named
    like one of the game's (Data/, Images/, ...), or, for a file in no such folder, where the game keeps a file of that
    name. Returns the files it couldn't place; the mod replaces the same files of other mods (overrides)."""
    files, skipped = {}, []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        parts = path.relative_to(root).parts
        start = next((i for i, part in enumerate(parts[:-1]) if part.casefold() in ALLOWED_ROOTS), None)
        if start is not None:
            target = "/".join(parts[start:])
        else:
            found = sorted((len(p.parts), p) for folder in GAME.iterdir()
                           if folder.is_dir() and folder.name.casefold() in ALLOWED_ROOTS
                           for p in folder.rglob(path.name) if p.is_file())
            shallowest = [p for depth, p in found if depth == found[0][0]] if found else []
            target = shallowest[0].relative_to(GAME).as_posix() if len(shallowest) == 1 else None
        try:
            target_path(target or "")
        except ValueError:
            skipped.append("/".join(parts)); continue
        if target.casefold() in {t.casefold() for t in files.values()}:
            raise ValueError(f"Two of its files would both go to {target}.")
        files[path] = target
    if not files:
        raise ValueError("Nothing in it is a game file the mods can change (in Data, Images, Flags and similar folders).")
    ident = re.sub(r"[^a-z0-9._-]+", "-", name.casefold()).strip("-._")[:64]
    ident = ident if len(ident) >= 2 else "added-mod"
    targets = {t.casefold() for t in files.values()}
    mods, _ = catalog()
    overrides = sorted(other for other, mod in mods.items()
                       if any(item["target"].casefold() in targets for item in mod.get("files", [])))
    listed = ", ".join(sorted(files.values())[:6]) + (", ..." if len(files) > 6 else "")
    for path, target in files.items():
        (package/"Files"/target).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, package/"Files"/target)
    write_json(package/"mod.json", {
        "schema": 1, "id": ident, "name": name, "version": "1.0.0",
        "description": f"Added with the Mod Manager: {listed}." + (
            f" Replaces the same files of {', '.join(mods[m]['name'] for m in overrides)} while both are on." if overrides else ""),
        "kind": "data", "experimental": False, "requires": [], "conflicts": [], "overrides": overrides,
        "files": [{"source": "Files/"+target, "target": target} for target in sorted(files.values())]})
    return skipped


def add_package(source):
    """Add mod, as in the original Mod Manager: a ZIP, a folder or one game file. A package with its own mod.json is
    imported as it is; anything else becomes a data mod named after it (see wrap). Remove mod takes it out again."""
    if not source.exists():
        raise ValueError("Choose a mod ZIP, folder or file.")
    with operation_lock(), tempfile.TemporaryDirectory(prefix="rtw-add-", dir=HERE) as temp:
        root, package, skipped = Path(temp)/"in", Path(temp)/"mod", []
        if source.is_dir():
            found = list(source.rglob("*"))
            if any(p.is_symlink() for p in found):
                raise ValueError("The folder contains a link.")
            if len(found) > 10000 or sum(p.stat().st_size for p in found if p.is_file()) > MAX_PACKAGE_BYTES:
                raise ValueError("The mod exceeds the 256 MB / 10,000 file limit.")
            shutil.copytree(source, root)
        elif source.suffix.lower() == ".zip":
            unpack(source, root)
        else:
            if source.stat().st_size > MAX_PACKAGE_BYTES:
                raise ValueError("The file exceeds 256 MB.")
            root.mkdir(); shutil.copy2(source, root/source.name)
        manifests = list(root.rglob("mod.json"))
        if len(manifests) > 1:
            raise ValueError("A package must contain exactly one mod.json.")
        if manifests:
            package = manifests[0].parent
        else:
            package.mkdir(); skipped = wrap(root, source.stem if source.is_file() else source.name, package)
        manifest = json.loads((package/"mod.json").read_text(encoding="utf-8-sig"))
        manifest["added"] = True
        write_json(package/"mod.json", manifest)
        mod = read_manifest(package)
        destination = LIBRARY / mod["id"]
        if destination.exists():
            raise ValueError(f"A mod with the ID {mod['id']} already exists. Remove it first to add another version.")
        shutil.copytree(package, destination)
    message = f"Added {mod['name']}. Double-click it to turn it on."
    if mod.get("overrides"):
        message += f" It replaces the same files of {', '.join(mod['overrides'])} while both are on."
    if skipped:
        message += f" Left out (not game files): {', '.join(skipped[:5])}" + (", ..." if len(skipped) > 5 else "")
    return {"ok": True, "message": message, "status": status()}


def remove_package(ident):
    """Remove mod, for mods added with Add mod: it must be off, and it moves to backups/removed-mods."""
    with operation_lock():
        mods, _ = catalog()
        if ident not in mods:
            raise ValueError("Select a mod to remove.")
        if not mods[ident].get("added"):
            raise ValueError(f"{mods[ident]['name']} comes with the mods. Turn it off instead.")
        if ident in load_state()["enabled"]:
            raise ValueError("Turn the mod off before removing it.")
        destination = HERE / "backups" / "removed-mods" / f"{ident}-{dt.datetime.now():%Y%m%d-%H%M%S}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(mods[ident]["folder"], str(destination))
    return {"ok": True, "message": f"Removed {mods[ident]['name']}. A copy is in {destination}.", "status": status()}


def export_package(ident, output):
    mods, errors = catalog()
    if ident not in mods:
        raise ValueError("Select one valid mod to export.")
    if output.exists():
        raise ValueError("Export destination already exists. Choose a new filename.")
    folder = Path(mods[ident]["folder"])
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        # Only the manifest and its declared files are needed. Exclude scripts and unrelated files.
        archive.write(folder / "mod.json", "mod.json")
        for item in mods[ident].get("files", []):
            archive.write(inside(folder, item["source"]), item["source"])
    return {"ok": True, "message": f"Exported {mods[ident]['name']} to {output}"}


def launch(accept_experimental=False):
    ensure_closed()
    current = load_state()
    verify()
    mods, plan, runtime = resolve_plan(current["enabled"])
    settings = runtime_settings(runtime)
    weekly = "calendar-days" in settings
    if any(mod.get("experimental") for mod in runtime) and not accept_experimental:
        raise ValueError("Experimental runtime mods selected. Confirm them in the manager before launching.")
    command = [sys.executable, str(campaign_mod.HERE / "launch.py"), "--no-dialog", "--settings", json.dumps(settings)]
    command += [step["flag"] for step in runtime_registry.plan(settings, settings)]
    result = subprocess.run(command, cwd=GAME, capture_output=True, text=True, timeout=130)
    if result.returncode:
        raise ValueError((result.stderr or result.stdout).strip() or "Game launch failed.")
    days = settings.get("calendar-days", {}).get("days", 7)
    return {"ok": True, "message": "Game launched with " + (f"the experimental {days}-day calendar." if weekly else "the selected mods and monthly turns."), "runtime_output": result.stdout.strip(), "status": status()}


def runtime_info(diagnose=False):
    current = load_state()
    _, _, runtime = resolve_plan(current["enabled"])
    settings = runtime_settings(runtime)
    if diagnose:
        import runtime_host
        return runtime_host.diagnostics(settings, settings)
    return {"ok": True, "framework_api": runtime_registry.API_VERSION,
            "plan": runtime_registry.plan(settings, settings)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("bootstrap", "status", "runtime-plan", "runtime-diagnostics", "apply", "stage-runtime", "verify", "import", "add", "remove", "export", "launch", "cheats-list", "cheats-inspect", "cheats-edit", "live-list", "live-inspect", "live-progress", "live-edit", "advanced-inspect", "advanced-edit", "sub-library", "sub-evaluate", "sub-save", "sub-inspect", "sub-apply", "sub-live-prepare"))
    parser.add_argument("--blueprint-id")
    parser.add_argument("--revision",type=int)
    parser.add_argument("--sub-index",type=int)
    parser.add_argument("--adjust-build",action="store_true")
    parser.add_argument("--section", default="General")
    parser.add_argument("--query", default="")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--changes", default="[]")
    parser.add_argument("--pid", type=int)
    parser.add_argument("--enabled", default="")
    parser.add_argument("--zip", type=Path)
    parser.add_argument("--path", type=Path)
    parser.add_argument("--mod")
    parser.add_argument("--accept-experimental", action="store_true")
    parser.add_argument("--save", type=Path)
    parser.add_argument("--nation", default="Nation0")
    parser.add_argument("--values", default="{}")
    parser.add_argument("--sha")
    parser.add_argument("--ship-index", type=int)
    parser.add_argument("--turns", type=int)
    parser.add_argument("--all-projects", choices=("build", "refit"))
    parser.add_argument("--action", choices=("research-all", "fast-aircraft", "refill-ammo"))
    args = parser.parse_args()
    try:
        if args.command in ("runtime-plan", "runtime-diagnostics"):
            result = runtime_info(args.command == "runtime-diagnostics")
        elif args.command.startswith("sub-"):
            import submarine_designs as submarines
            if args.command=="sub-library": result=submarines.library()
            elif args.command=="sub-live-prepare":
                import submarine_factory
                result=submarine_factory.prepare(args.pid,args.blueprint_id,args.revision)
            elif args.command=="sub-evaluate": result=submarines.evaluate(json.loads(args.values))
            elif args.command=="sub-inspect": result=submarines.inspect_save(args.save,args.nation)
            elif args.command=="sub-save":
                with operation_lock(): result=submarines.save_blueprint(json.loads(args.values),args.blueprint_id,args.revision)
            else:
                with operation_lock(): result=submarines.apply_blueprint(args.save,args.nation,args.sub_index,args.blueprint_id,args.revision,args.sha,args.adjust_build)
        elif args.command.startswith("advanced-"):
            import advanced_saves
            if args.command == "advanced-inspect":
                result = advanced_saves.inspect(args.save, args.section, args.query, args.offset)
            else:
                with operation_lock(): result = advanced_saves.edit(args.save, json.loads(args.changes), args.sha)
        elif args.command.startswith("live-"):
            import live_cheats
            if args.command == "live-list":
                games = [g for g in running_games() if Path(g["path"]) == GAME/"RTW3.exe"]
                result = {"ok": True, "saves": [{"path": str(g["pid"]), "name": "RTW3 - live campaign (load a campaign, then refresh)"} for g in games]}
            elif args.command == "live-inspect":
                result = live_cheats.inspect(args.pid)
            elif args.command == "live-progress":
                result = live_cheats.progress(args.pid)
            else:
                with operation_lock():
                    result = live_cheats.edit(args.pid, json.loads(args.values), args.sha, args.ship_index, args.turns, args.all_projects, args.action)
        elif args.command.startswith("cheats-"):
            import save_cheats
            if args.command == "cheats-list":
                result = save_cheats.list_saves()
            elif args.command == "cheats-inspect":
                result = save_cheats.inspect(args.save, args.nation)
                result["game_running"] = bool(running_games())
            else:
                with operation_lock():
                    result = save_cheats.edit(args.save, args.nation, json.loads(args.values), args.ship_index, args.turns, args.sha, args.all_projects)
        elif args.command == "bootstrap":
            result = bootstrap()
        elif args.command == "status":
            result = status()
        elif args.command == "apply":
            result = apply([value for value in args.enabled.split(",") if value])
        elif args.command == "stage-runtime":
            result = stage_runtime([value for value in args.enabled.split(",") if value])
        elif args.command == "verify":
            result = verify()
        elif args.command == "add":
            if not args.path:
                raise ValueError("Choose a mod ZIP, folder or file.")
            result = add_package(args.path.resolve())
        elif args.command == "remove":
            if not args.mod:
                raise ValueError("Select a mod to remove.")
            result = remove_package(args.mod)
        elif args.command == "import":
            if not args.zip:
                raise ValueError("Choose a ZIP package.")
            result = import_package(args.zip.resolve())
        elif args.command == "export":
            if not args.zip or not args.mod:
                raise ValueError("Choose a mod and an export path.")
            result = export_package(args.mod, args.zip.resolve())
        else:
            result = launch(args.accept_experimental)
        print(json.dumps(result))
        return 0
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile, subprocess.TimeoutExpired) as error:
        print(json.dumps({"ok": False, "message": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
