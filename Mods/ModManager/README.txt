Rule the Waves 3 mods - beta test build

Needs Rule the Waves 3 version 1.01.44 from Steam (build 24739009) on Windows. Nothing else to install: the
Mod Manager brings its own Python.

INSTALL
1. In Steam, right-click Rule the Waves 3 > Properties > Installed Files > Verify integrity of game files,
   so the mods start from the game's original files.
2. Right-click Rule the Waves 3 > Manage > Browse local files. Extract this whole ZIP into that folder,
   so the Mods folder sits next to RTW3.exe.
3. Open Mods\ModManager\Mod Manager.exe.

USE
- Close the game, then double-click a mod to turn it on or off. Frigate Type needs Expanded Timeline on first.
- Click Launch to start the game with the mods (Steam must be running). The manager stays on top while the mods
  load (about 10 seconds): don't start or load a campaign until it says "Mods loaded".
- Always start the game with Launch while mods are on: starting it from Steam leaves out the mods' game changes.
- Most mods are experimental. Play them in a separate test campaign and keep copies of saves you care about.
- Select a mod to read what it does.
- Add mod adds a mod from a ZIP, a folder or game files (for example your own ResearchAreas3.dat). Loose game files
  go where the game keeps them; a file another mod also has replaces that mod's copy while both are on. Remove mod
  takes an added mod out again.

UPDATES
When a new version is out, the manager offers it when it opens. Close the game and click Yes: it downloads the
update, checks it, turns your mods back on and restarts itself.

UNINSTALL
Click Disable all (your original game files come back), close the manager, then delete the Mods folder.

REPORTING PROBLEMS
Say which mods were on, what you did and what happened. If the manager shows an error it also saves it in
Mods\ModManager\modman-error.log; startup problems are in Mods\CampaignOverhaul\runtime_host_report.json.

The Mod Manager is a modified Sprocket Mod Manager by Hans21223 (LGPL-3.0, see Mods\ModManager\LICENSE).
