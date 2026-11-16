"""Exports the source to a clone of Hans21223/RTW3-Mods: the mod code, the loader, tools, tests and docs, the
Mod Manager's own source, and the mod packages (manifest and declared files, as the release ships them). Never game
files or the game-code dump the tests use, saves, local state, backups, reports or third-party binaries.

  python export_source.py <clone folder>      then commit and push in that folder
"""
import json
import os
from pathlib import Path
import re
import sys

MODS = Path(__file__).resolve().parents[1]
PATTERNS = ("CampaignOverhaul/*.py", "CampaignOverhaul/README.md", "CampaignOverhaul/events.json",
            "CampaignOverhaul/frigate_type_sites.json", "CampaignOverhaul/historical_hulls.json",
            "Manager/*.py", "Manager/*.md", "Manager/*.cs", "Manager/*.ps1",
            "ModManager/modman.pyw", "ModManager/updates.py", "ModManager/README.txt", "ModManager/LICENSE",
            "ModManager/Mod Manager._pth")
README = """# RTW3-Mods

Rule the Waves 3 mods (alpha) and the RTW3 Mod Manager. Testers install from the shared ZIP; the Mod Manager
updates itself from this repository's releases.

`Mods/` mirrors the game folder:

- `CampaignOverhaul/` the mods' runtime code (patches applied to the running game) and the generators of their data
- `Manager/` the mod loader (`mod_loader.py`), tools, tests, docs and `build_beta_release.py`
- `ModManager/` the Mod Manager (`modman.pyw`, `updates.py`), modified from the Sprocket Mod Manager (LGPL-3.0)
- `Library/` the mod packages

Not in the repository: the game's files, third-party packages (capstone 5.0.9 and, for tests, unicorn 2.1.4 in
`Manager/vendor/`), the Python runtime the Mod Manager carries (from Sprocket Mod Manager 1.4.0), and
`Manager/native-designer-inspection.text.bin`/`.json`, the game-code dump the tests read (`native_designer.py`
makes it from your own copy of Rule the Waves 3 1.01.44).
"""


def secrets():
    """Byte strings no exported file may contain: this PC's user name and Git identity, user paths, tokens."""
    found = [os.environ.get("USERNAME", Path.home().name)]
    for key in ("user.name", "user.email"):
        value = os.popen(f"git config --global {key}").read().strip()
        if value and "noreply" not in value: found += [value] + value.split()
    markers = ["c:\\" + "users\\", "c:/" + "users/", "gh" + "p_", "gh" + "o_"]   # split: this file must pass too
    return [s.lower().encode() for s in found + markers if len(s) > 3]


def files():
    """{repository path: file}."""
    found = {p for pattern in PATTERNS for p in MODS.glob(pattern) if p.is_file()}
    for manifest in (MODS/"Library").glob("*/mod.json"):
        found.add(manifest)
        found.update(manifest.parent/item["source"] for item in json.loads(manifest.read_text(encoding="utf-8-sig")).get("files", []))
    exported = {"Mods/" + p.relative_to(MODS).as_posix(): p for p in found}
    forbidden = secrets()
    for name, path in exported.items():
        data = path.read_bytes().lower()
        if any(s in data for s in forbidden):
            raise ValueError(f"{name} contains personal data or a token; nothing was exported")
        if re.search(r"(^|/)(vanilla|backups|baseline|vendor|__pycache__)/|\.(exe|dll|bin)$|_report\.json$|state\.json$", name):
            raise ValueError(f"Not source: {name}")
    return exported


def export(target):
    target, exported = Path(target), files()
    old = [p for p in (target/"Mods").rglob("*") if p.is_file()] if (target/"Mods").is_dir() else []
    for path in old:
        if path.relative_to(target).as_posix() not in exported:
            path.unlink()   # dropped from the source since the last export
    for name, path in exported.items():
        (target/name).parent.mkdir(parents=True, exist_ok=True)
        (target/name).write_bytes(path.read_bytes())
    (target/"README.md").write_text(README, encoding="utf-8")
    (target/".gitattributes").write_text("* -text\n", encoding="utf-8")   # game data files stay byte-exact
    return len(exported)


if __name__ == "__main__":
    print(f"Exported {export(sys.argv[1])} files to {sys.argv[1]}")
