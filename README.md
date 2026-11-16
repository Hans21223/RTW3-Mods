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

### PowerShell (build scripts)

Two scripts in `Mods/Manager` compile the older C# tools with the C# compiler built into Windows
(.NET Framework 4 `csc.exe`), so no Visual Studio is needed:

- `build_manager.ps1` builds `RTW3 Mod Manager.exe` into the game folder: the original Windows
  Forms mod manager, with the F10 Live Cheats window and the save editor (`ModManager.cs`,
  `CheatMenu.cs`, `GameTools.cs`, `AdvancedSaveEditor.cs`). Add
  `-OutputName 'RTW3 Mod Manager Updated.exe'` to build the second copy.
- `build_submarine_module.ps1` builds `RTW3.SubmarineDesigner.dll`, the 32-bit in-game panel of
  the In-game Submarine Designer mod. With `-LayoutTest` it builds and runs a layout check instead.

Neither is needed for the alpha: the Mod Manager players use is the Python one in `Mods/ModManager`,
and Live Cheats and the In-game Submarine Designer are not in this release.
