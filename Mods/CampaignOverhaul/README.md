# RTW3 Campaign Overhaul

This installation was updated from your installed Steam copy, build **24739009**.
It is a snapshot of that installation, not a check for newer Steam downloads.
The official RTW3 executable and Steam libraries were copied unchanged. Steam
must be installed, signed in, and able to authenticate your game normally.

## Play

Open **RTW3 Mod Manager.exe** in `D:\Games\RTW3`. The manager now owns the
event pack and runtime mod. Select your mods and choose **Play with mods**.
Start a new campaign to ensure the new event text loads. See
`Mods/Manager/MODDING.md` for the current loader and package format.

The 100 event groups cover stock campaign incidents, naval policy and
procurement, plus modern and Cold War scenarios. Each group now offers three
responses, with compact Budget, Prestige and Tension notes so trade-offs are
visible before choosing. Targeted changes remove duplicate or lopsided
responses; other dates, triggers, targets and native special conditions stay
as authored. The event system still uses the game's fixed set of three
response rows and its existing effect rules. See
`Mods/Manager/EVENT_DECISIONS.md` for the authored changes and limitations.

## Weekly experiment

**Play Experimental Weekly.cmd** starts an optional seven-day calendar mode.
It attaches after the official game starts through Steam, discovers both turn
methods in the loaded game, checks their original instructions, and replaces
their calendar arithmetic in memory. The executable file remains unchanged.
Restarting the game removes the runtime patch.

**This is a calendar prototype, not a balanced weekly simulation.** Budgets,
research, construction, AI, attrition and some durations still process on their
original per-turn schedules. More turns per calendar year can therefore greatly
accelerate those systems. Use a separate test campaign. Do not assume saves made
with the weekly clock will behave the same when continued in monthly mode.

The hidden week-length control in the game is not used as evidence that all
systems support weekly turns. A full conversion still needs monthly systems
audited and rebalanced, followed by multi-year campaign testing.

## Historical independence

The optional **Historical Decolonization - Player and AI** mod adds automatic,
date-led transfers for listed territories on both sides. It also prevents the
native rebellion system from granting independence to core regions such as
Western USA, and suppresses random secession from territories with a scheduled
historical release. The mod's dated transfers bypass that protection. Other
native possession events remain active. RTW3 represents many independent
territories as Neutral and cannot create playable countries, so this does not
create their government, fleet or diplomacy. See
`Mods/Manager/DECOLONIZATION.md` for details.

## What was preserved

- User saves and preferences; the update does not copy Steam's `Save` directory.
- The separate Steam installation's files.
- Pre-update installation files, saved under `backups/` with a SHA-256 manifest.

The copied Steam folder had an earlier time-stretch mod. Its original backed-up
technology, aircraft and event tables were used, avoiding the known loss of late
content caused by stretching release years beyond the game's campaign end.
The campaign end date itself has not been extended.

## Manage and restore

Use the manager to verify the installation, restore original Steam-era events,
or reapply the event pack. Choose **No mods** and **Apply** before a full update
rollback. Changes made outside the manager are detected before it overwrites them.

Full rollback to this folder's pre-update installation:

```powershell
python .\Mods\CampaignOverhaul\campaign_mod.py restore-update
```

Rollback verifies the backup and stops if installed files have untracked edits.
Files introduced by the update are moved into `rolled-back-update/` for recovery.
Saves and personal custom files are not rolled back.

Read the current runtime patch addresses or remove an attachment:

```powershell
python .\Mods\CampaignOverhaul\weekly_runtime.py clock
python .\Mods\CampaignOverhaul\weekly_runtime.py detach
```

## Validation

The update manifest verifies every copied game file. Event validation checks
the four-line record format, original event count, every unchanged mechanical
field, and exact generated output. Runtime inspection checks both named turn
methods and their shared calendar address instead of reusing old build offsets.
See `validation.json` for the actual test results and remaining limitations.
