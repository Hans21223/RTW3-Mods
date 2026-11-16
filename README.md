# RTW3-Mods

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
