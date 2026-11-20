"""Builds the beta ZIP: Mods/ModManager (the window and its own Python), the loader and runtime code the shipped
mods import, and each shipped mod's manifest and declared files. Nothing else: no tests, docs, saves, backups,
reports or game files.

  python build_beta_release.py      -> Mods/Release/RTW3-Mods-Beta-<version>.zip and its .sha256

The version is Mods/ModManager/updates.py's VERSION, which the manager compares with its GitHub releases; the ZIP
lists its own files (updates.MANIFEST) so an update can remove what a release drops.
"""
import hashlib
import json
import modulefinder
import os
from pathlib import Path
import sys
import zipfile

MODS = Path(__file__).resolve().parents[1]
MANAGER, OVERHAUL, LIBRARY, WINDOW = MODS/"Manager", MODS/"CampaignOverhaul", MODS/"Library", MODS/"ModManager"
SHIPPED = ("aircraft-improvements", "battle-ai", "big-guns", "campaign-events", "campaign-qol", "extended-ship-graphics",
           "frigate-test", "historical-decolonization", "large-hulls", "legacy-fleet", "research-budget",
           "super-superfiring-turret", "timeline-2030", "weekly-calendar")
CLI_ONLY = ("advanced_saves", "custom_decisions", "submarine_designs", "submarine_factory")   # mod_loader commands the window never runs
DATA = (OVERHAUL/"frigate_type_sites.json", MANAGER/"vendor/capstone/lib/capstone.dll",
        MANAGER/"vendor/capstone-5.0.9.dist-info/LICENSE.TXT")


def manifest(ident):
    return json.loads((LIBRARY/ident/"mod.json").read_text(encoding="utf-8-sig"))


def code_files():
    """mod_loader, the launcher and the shipped mods' adapters, with every module of ours they import."""
    sys.path.insert(0, str(OVERHAUL))
    import runtime_registry
    entries = [m.get("runtime") or [] for m in map(manifest, SHIPPED)]
    modules = {runtime_registry.REGISTRY[e["adapter"]].module for runtime in entries
               for e in (runtime if isinstance(runtime, list) else [runtime])}
    finder = modulefinder.ModuleFinder(path=[str(MANAGER), str(OVERHAUL), str(MANAGER/"vendor")] + sys.path[1:],
                                       excludes=[*CLI_ONLY, "unicorn"])
    roots = [MANAGER/"mod_loader.py", OVERHAUL/"launch.py", *(OVERHAUL/f"{name}.py" for name in sorted(modules))]
    for script in roots:
        finder.run_script(str(script))   # recorded as __main__, so the roots are added below
    found = {Path(m.__file__).resolve() for m in finder.modules.values() if getattr(m, "__file__", None)}
    return sorted(p for p in found | set(roots) if p.is_relative_to(MODS))


def release_files():
    """{name in the ZIP: file on disk}."""
    for ident in SHIPPED:
        missing = set(manifest(ident).get("requires", [])) - set(SHIPPED)
        if missing:
            raise ValueError(f"{ident} needs mods that are not shipped: {', '.join(sorted(missing))}")
    files = [LIBRARY/ident/"mod.json" for ident in SHIPPED]
    files += [LIBRARY/ident/item["source"] for ident in SHIPPED for item in manifest(ident).get("files", [])]
    files += code_files() + list(DATA)
    files += [p for p in WINDOW.rglob("*") if p.is_file() and "__pycache__" not in p.parts
              and p.name not in ("README.txt", "modman-error.log", "hang-report.txt")]
    shipped = {"Mods/" + p.relative_to(MODS).as_posix(): p for p in files}
    shipped["README.txt"] = WINDOW/"README.txt"
    user = os.environ.get("USERNAME", Path.home().name).lower().encode()
    for name, path in shipped.items():
        if path.name.startswith("test_") or path.name == "state.json" or path.name.endswith("_report.json"):
            raise ValueError(f"Not a release file: {name}")
        if len(user) > 2 and user in path.read_bytes().lower():
            raise ValueError(f"{name} contains this PC's user name")
    return shipped


def build(output=None):
    sys.path.insert(0, str(WINDOW))
    import updates
    output = Path(output or MODS/"Release"/f"RTW3-Mods-Beta-{updates.VERSION}.zip")
    shipped = release_files()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, path in sorted(shipped.items()):
            archive.write(path, name)
        archive.writestr(updates.MANIFEST, "\n".join(sorted([*shipped, updates.MANIFEST]))+"\n")
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_name(output.name+".sha256").write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    return output


if __name__ == "__main__":
    path = build(sys.argv[1] if len(sys.argv) > 1 else None)
    print(f"{path} ({path.stat().st_size/1e6:.1f} MB)")
