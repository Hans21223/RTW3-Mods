# RTW3 Mod Manager and Loader

Framework 2 adds one reviewed adapter registry, a shared startup host, guarded
hook ownership and a **Diagnostics** button. See [FRAMEWORK.md](FRAMEWORK.md) for
extension contracts, read-only diagnostics, performance scope and recovery.

Open **RTW3 Mod Manager.exe** in the game folder. Check the mods you want and
choose **Play with mods**. The manager applies the selection, checks conflicts,
backs up the affected files, and launches this updated game copy with Steam.
Choose **No mods** or **Restore vanilla** to remove managed mods.

**Play from Steam.** This copy runs the same Steam executable as the Steam
installation, with Steam's DRM wrapper, and the mods attach after Steam unpacks
it. To start it with Steam's own **Play** button, open Steam > Library > Rule the
Waves 3 > Properties > Launch options and enter
`"D:\Games\RTW3\Play from Steam.cmd" %command%`. Play then applies nothing new:
it launches this copy with the mods last applied in the manager, exactly like
Play with mods. The Steam installation's files are never changed. Clear the
launch option to play the unmodded Steam installation again.

The manager was built for this updated installation (Steam build 24739009).
It does not update the Steam client or fetch new game builds. It requires an
installed Python 3.11+; this computer already has Python 3.14. If another Python
is needed, set the `RTW3_PYTHON` environment variable to its executable path.

## Included mods

- **Aircraft - Improve Model in Right-click Menu:** opens the native request
  priorities for a selected player model, with its role fixed. Develops a native
  successor prototype while preserving existing aircraft. See
  [AIRCRAFT_IMPROVEMENTS.md](AIRCRAFT_IMPROVEMENTS.md).
- **Naval Staff Briefings:** 24 rewritten events in the original 81 slots.
  Since 7 November 2026 the events that ended in 1999 run to 2050 (the
  extended campaign had none after 1999), and 13 modern events (1950-2050)
  were added: oil crises, missile tests, satellites, piracy, cyber intrusions,
  missile arms talks, freedom-of-navigation patrols, drone boats, shipyard
  automation, nuclear port visits, hypersonic missiles, space programmes and
  defence reviews. They use only the native conditions and effects listed in
  `Data/BuldCampEventConditions.txt`; the game reads at most 100 events.
  Since 13 November 2026 six Cold War events (1947-1990) fill the last slots:
  a blockaded city, a nationalised canal, island missiles, a seized
  intelligence ship, a grounded submarine and incidents at sea.
- **Seven-Day Calendar and Week Display:** an experimental runtime mod that adds
  seven days per turn and shows `Week 1` to `Week 5` beside the native campaign
  month/year (merged from Week Beside Month, 16 November 2026). **Economy,
  construction, research, AI and durations are not rebalanced.** Use a separate
  test campaign. This is not yet a complete weekly simulation.
- **Historical and Paper Hulls - 200,000t:** expands actual class ceilings and
  CVL aircraft limits using researched built and unbuilt examples. Preserves
  native machinery through 90,000 tons and uses a documented estimate above it.
  See `HISTORICAL_HULLS.md` for limits, sources and retained design restrictions.
- **Manual Legacy Fleet - All Start Years:** exposes the optional native manual
  fleet checkbox in 1890, 1900, 1920 and 1935, with the correct previous design year.
- **Live Cheats - In-game F10 Menu:** a visible companion launcher/hotkey for
  player campaign edits while playing, also available in the manager's Live tab.
- **Expanded Timeline - Modern Research to 2030, Campaign to 2050:** one package (merged from Campaign Through 2030, Modern Research
  Through 2030 and VLS Cells). Moves the end offer to December 2050 and the
  forced stop to 2051; research runs to 2030 with new technologies, modern
  weapons and VLS cell banks (right-click a missile mount). See
  `MODERN_TECH_TREE.md` and [VLS_CELLS.md](VLS_CELLS.md), and keep it enabled
  when continuing an extended save.
- **AI - Battle AI, Fair Rules and Torpedo Tactics:** one package (merged on
  7 November 2026 from Battle AI, Fair AI, More Decisive Torpedo AI and
  Detection-only Torpedo Evasion; the adapters and their settings are
  unchanged):
  - battle AI: missile range and formation discipline, contact memory, air
    operations and sunk-target guards (`BATTLE_AI.md`);
  - more frequent automatic torpedo opportunity assessments, with the native
    final firing checks, accuracy and ammunition unchanged;
  - fair rules: the six audited uses of the AI advantage setting and the AI
    budget emergency grant are disabled. National budgets, technology and earned
    training remain different (`AI_RULES.md`);
  - detection-only torpedo evasion: no predictive torpedo turnaways or inherited
    turns; native last-minute evasion and mine detection stay (`HAZARD_FOG.md`).
- **Research - Budget Scaling and Stronger National Traits:** one package
  (merged the same day from Research Budget Scaling and Stronger Research
  Advantages): setbacks cost a turn's gain instead of half the progress, budget
  above the native limit still counts, and research advantages and technical
  excellence add 50% and 25% (`RESEARCH_BUDGET.md`, `RESEARCH_TRAITS.md`).

Use **LIVE CHEATS / F10** for running-campaign changes. Use **SAVE EDITOR**
for backed-up saved-campaign edits, with quick controls and a searchable advanced
view covering settings, economy, research progress, training and ship details.
Close RTW3 before applying saved edits and reload that save afterward.
See `CHEATS.md` for units, behavior and recovery steps.

## Two loader layers

**Content loader.** A mod declares the files it replaces. The manager keeps the
original bytes, verifies backups, detects overlapping files, and restores the
previous selection if an install operation fails. Mods can supply supported
content files under Data, Designs, Flags, Images, Scenarios, ShipParts and Sounds,
including built-in ship designs (`Data/IDes/*.tdf`) and hull, turret and equipment
shapes (`Data/Graphics/*.hus`, `*.tus`, `*.eqs`). Executable/DLL replacements and arbitrary plugin scripts are not loaded by this
version of the manager. Imports never execute package code.

**Runtime loader.** Runtime adapters attach after the official Steam-authenticated
game starts. The calendar adapter discovers both calendar methods from Delphi
metadata and checks their instructions before changing the running process. It
does not edit RTW3.exe, intercept Steam authentication, or use fixed offsets from
the old build. Closing the game resets the hook.

Keep RTW3 closed while applying or restoring content mods. The loader refuses
to replace a managed file that has untracked edits. Imported mods are disabled
until you select and apply them. Conflicting mods are blocked, not silently
overwritten by load order.

## Make a data mod

Create a folder in `Mods/Library/your-mod-id/` containing `mod.json` and your
content files. Example:

```text
your-mod-id/
  mod.json
  Files/
    Data/
      Tips.txt
```

```json
{
  "schema": 1,
  "id": "your-mod-id",
  "name": "My Naval Tips",
  "version": "1.0.0",
  "author": "Your name",
  "description": "Replaces the title-screen tips with my naval notes.",
  "kind": "data",
  "experimental": false,
  "requires": [],
  "conflicts": ["campaign-events"],
  "files": [
    {"source": "Files/Data/Tips.txt", "target": "Data/Tips.txt"}
  ]
}
```

Use forward slashes and relative paths. The loader blocks traversal, symbolic
links, paths outside the game, duplicate ZIP entries and oversized archives.
Use ASCII or the original game's encoding for game data; a UTF-8 BOM can break
older Delphi parsers. Do not assume all engine formats are text.

Press **Refresh** after creating a folder. Select the new mod and **Export selected**
to produce a ZIP. Others can use **Import ZIP**. A ZIP must contain exactly one
mod.json, either at its root or inside one mod folder. Existing mod IDs are
never overwritten by imports.

Dependencies use mod IDs in `requires`. Incompatibilities use IDs in `conflicts`.
If two enabled mods declare the same target file, combine the changes into a
separate compatibility mod and disable the originals.

## Extend the runtime loader

The adapters are implemented in `Mods/CampaignOverhaul/weekly_runtime.py`,
`week_display.py`, `large_hulls.py`, `legacy_fleet.py`, `live_cheats.py` and
`timeline_2030.py`, `in_game_submarines.py` and `submarine_factory.py`.
The two reviewed AI adapters use `ai_runtime.py` and `ai_rules.py`; they attach
before a campaign is loaded and do not edit saved options or personal saves.
The detection-only option also uses the reviewed `hazard_rules.py` discovery
module; imports do not enable arbitrary package-supplied scripts.
Modern research uses `modern_tree.py` for its deterministic append-only data
package and `modern_research.py` for ten reviewed, symmetric integer-result
extensions. Its runtime and content components must be enabled together.
New runtime behavior needs a reviewed adapter, explicit compatibility checks,
and tests before the manifest validator accepts it. The reviewed adapters are
listed in `ADAPTERS` in `mod_loader.py`.

### Runtime settings

A runtime mod can change the engine values its adapter patches. Add whole-number
settings beside `adapter`; leave one out to keep its default. The manager rejects
unknown settings and values outside the range when it reads the mod. Settings
apply on the next **Play with mods**, so restart RTW3 after changing them.

| Adapter | Setting | Default | Range | Native value it replaces |
| --- | --- | ---: | --- | --- |
| `calendar-days` | `days` | 7 | 1-28 | One month per turn. 28 days or fewer never skips a month. |
| `timeline-2030` | `end_year` | 2050 in the package (adapter default 2030) | 1890-9998 | December 1970 end offer |
| `timeline-2030` | `cutoff_year` | `end_year` + 1 | 1891-9999 | Forced stop at the start of 1990. Must be later than `end_year`. |
| `large-hulls` | `max_tons` | 200000 | 90000-280000 | Machinery above 90,000t uses the documented estimate; visual sizes continue past the native 100,900t range. Designer visuals draw above layers and torpedoes, under missiles and guns. |
| `large-hulls` | `dd_tons` | 10000 | 3800-280000 | DD class ceiling |
| `large-hulls` | `cl_tons` | 20000 | 14000-280000 | CL class ceilings |
| `large-hulls` | `ke_tons` | 6000 | 2500-280000 | KE class ceiling |
| `large-hulls` | `cvl_tons` | 30000 | 16000-280000 | CVL ceiling |
| `large-hulls` | `cv_tons` | 150000 | 16000-280000 | Nation's carrier-size ceiling in the designer. Carrier inventions still apply. |
| `large-hulls` | `cvl_aircraft` | 80 | 34-127 | 34 CVL aircraft |
| `torpedo-initiative` | `roll` | 75 | 1-255 | Random(100) torpedo opportunity roll. Lower values assess more often. |

Class ceilings above `max_tons` have no effect. For example, a separate
fortnightly calendar mod:

```json
{
  "schema": 1,
  "id": "fortnight-calendar",
  "name": "Fortnightly Turns",
  "version": "1.0.0",
  "description": "Advances the campaign 14 days per turn. Not rebalanced.",
  "kind": "runtime",
  "experimental": true,
  "requires": [],
  "conflicts": ["weekly-calendar"],
  "files": [],
  "runtime": {"adapter": "calendar-days", "days": 14}
}
```

Only one enabled mod can use each adapter, so disable the bundled mod for that
adapter or edit its `mod.json` instead.

A full weekly conversion still requires scaling recurring resource flows,
auditing construction/repair timers, adjusting event and attrition chances, and
testing the AI across a multi-year campaign. A manager alone cannot supply
those engine changes.

## Backups and recovery

- `Mods/Manager/baseline/`: original files before the manager first touched them.
- `Mods/Manager/backups/`: per-operation copies and transaction records.
- `Mods/CampaignOverhaul/backups/`: complete installation before the Steam update.
- `Mods/Manager/state.json`: enabled mods, installed hashes and backup history.

Never delete a baseline or state file while its mods are active. If power is
lost during an operation, keep the backups and inspect the most recent
transaction before retrying. The operation lock prevents overlapping writes.
Mod installation never changes the separate Steam installation or personal saves.
Deliberate Save Editor actions modify the selected campaign after backing it up.
Live cheats change memory until you save.
The verifier excludes only the known native `Data/tmpShip.ttp` scratch file
from immutable installation checks; declared managed mod files stay verified.

## Command-line use

From the game folder:

```powershell
python .\Mods\Manager\mod_loader.py status
python .\Mods\Manager\mod_loader.py apply --enabled campaign-events
python .\Mods\Manager\mod_loader.py apply --enabled campaign-events,weekly-calendar
python .\Mods\Manager\mod_loader.py verify
python .\Mods\Manager\mod_loader.py apply --enabled ""
```

The GUI is a small native Windows Forms application. Its source is
`ModManager.cs`; its backend is `mod_loader.py`. Rebuild with `build_manager.ps1`.

The optional in-game submarine designer uses a separate, fixed x86 assembly
`RTW3.SubmarineDesigner.dll`, hosted inside the normally authenticated game by
`in_game_submarines.py`. Rebuild it with `build_submarine_module.ps1` while RTW3
is closed. The manifest importer still rejects arbitrary executable payloads;
this reviewed built-in module is not a general-purpose DLL loading interface.
See `MODERNIZATION.md` for actual native effects and the remaining limitations.

## Campaign security update

The optional `campaign-security` runtime package adds paid counterintelligence
in F10, rejects new AI orders at player yards, and removes espionage technology
theft for all nations. It requires Live Cheats and a restart through Play with
mods. See [CAMPAIGN_SECURITY.md](CAMPAIGN_SECURITY.md).

## Research and campaign QoL update

Live Cheats now shows research completion in its in-game companion overlay and
F10 panel, with player-only Research ALL and one-turn pending aircraft actions.
The optional `campaign-qol` adapter automates two specific prompts and bounds AI
procurement. Its supported runtime settings are `max_active_ships` (50-10000,
default 400), `max_building_ships` (1-1000, default 24), and
`min_procurement_days` (1-90, default 28). It loads after Campaign Security and
before Live Cheats, only at the title screen. See
[RESEARCH_AND_QOL.md](RESEARCH_AND_QOL.md) for exact effects and limitations.

## Battle AI update

The optional `battle-ai` adapter repairs local candidate-course checks, adds
bounded report-only contact memory for eligible AI surface divisions, permits
native carrier strikes during auto-run and rejects sunk weapon targets. It
loads after the campaign adapters and before Live Cheats, only at the title
screen. Settings include `contact_memory_minutes` (1-60, default 20),
`memory_radius_yards` (5000-100000, default 45000) and `catapult_strikes`
(0-1, default 1: catapult carriers launch strikes without turning). See
[BATTLE_AI.md](BATTLE_AI.md) for exact scope and verification limits.

## Stronger national research traits

The optional `research-traits` adapter adds steady branch-advantage and Technical
Excellence research-effort bonuses, shared by player and AI. Its settings are
`research_advantage_bonus_percent` (0-300, default 50) and
`technical_excellence_bonus_percent` (0-200, default 25). Percentages add before
remaining native modifiers and limits. Existing flags, budgets, completed techs
and other trait effects are unchanged. See [RESEARCH_TRAITS.md](RESEARCH_TRAITS.md).

