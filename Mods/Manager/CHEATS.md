# Campaign testing controls

Open **RTW3 Mod Manager.exe**. The top tabs separate **LIVE CHEATS / F10**
from the **SAVE EDITOR**; they are not buttons in the game's Preferences window.

## Live cheats while playing

Enable **Live Cheats - In-game F10 Menu**, choose **Play with mods**, then load
a campaign. A small movable **CHEATS / F10** window appears while RTW3 is active.
Click it or press **F10**. You can also use the manager's **LIVE CHEATS** tab.
If another program has reserved F10, the launcher reads **CHEATS / CLICK**.
It hides and releases the hotkey when you switch away from the game, and exits
with that game session. This is a companion launcher, not a native Preferences
button. Starting RTW3.exe directly does not load these runtime tools.

Refresh after loading a campaign. Changes apply to the current player's funds,
income inputs, dock size, prestige/unrest, global research speed and a selected
ship's remaining build, rebuild or refit / repair turns. Edits are queued for the game's own UI
thread; all original values and the current player are checked before any
change is committed, then the native budget panel refreshes. If the campaign
changed, refresh instead of reusing stale values. A pending request must finish
before another can be sent. Use the campaign map rather than an active turn
calculation or battle transition.

Live changes do not rewrite a save file themselves. Save normally in RTW3 to
keep them; reload a previous save to undo them. Construction changes preserve
total cost/progress and adjust spending, clearing Halted/Hurry. Research speed
is campaign-wide. There is no automatic full campaign backup for a live edit;
make a separate test save before using it.

### Fast build and fast refit

In **LIVE CHEATS / F10**, refresh, then choose a **Ship / yard project**.
**Fast build (1 turn)** stages a new construction project; **Fast refit (1 turn)**
stages a major rebuild or a normal refit / repair. Press **Apply live changes**
to commit. The same shortcuts are available in the saved campaign's quick controls.
These are one-shot shortcuts for the selected ship, not permanent fleet-wide toggles.
Changing the selection clears the staged project edit.

Builds and major rebuilds retain their full remaining cost: spending is increased
to target one remaining turn and Halted/Hurry are cleared. Sufficient funds,
native yard rules and random construction delays still matter; this is not free
or guaranteed instant completion. Normal refits share the native `RepairTime`
countdown with damage repairs, so these are labelled **refit / repair** in the
picker. Only the selected ship's current countdown changes, never its separate
`TimeToRefit` maintenance-due counter. Status values of 100 or more are excluded.
Finish or cancel existing yard work before starting a new project normally.

Automated fixture tests cover both shortcuts, saved-file backups and guarded live
transactions. Completion after advancing a real campaign turn remains unverified;
no personal campaign was changed or advanced to test these additions.

### Refill ship ammunition

During a battle, pause, open **F10 / LIVE CHEATS**, click **Refresh live game**,
then **Refill ship ammo ALL** below the battle weather switches. It applies
immediately; no separate Apply click is needed. Other staged cheats stay pending.
The button is disabled outside a battle.

This restores surviving player ships' main, secondary and tertiary gun
magazines to nominal fitted capacity using the current ammunition doctrine.
It also fills the loaded torpedo/missile tubes on surviving mounts. It leaves
enemy and allied ships alone, excludes sunk/sinking ships, and preserves weapon
damage, jamming and firing/reload cooldowns. Reserve reloads, aircraft weapons
stores and mines are not refilled. Already-full magazines are left alone.

The action uses the existing all-or-nothing native UI-thread transaction. A
battle transition, ship-list change or ammo use before commit cancels the edit;
pause, refresh and retry. No new native hook or disk executable patch is added.
Native code signatures were verified against the running game and a read-only
plan was checked in a real battle. Transaction and native gun-ammo readback were
tested in an emulator; no ammo was changed in the user's battle for testing.

### Reveal enemy ships in battle

Restart RTW3 through **Play with mods** with **Live Cheats** enabled. In
**LIVE CHEATS / F10**, tick **Reveal all enemy ships (battle-map markers)**,
then press **Apply live changes**. Untick and Apply to restore normal map
visibility. This is off by default, is not written to saves, and resets when
RTW3 exits. An already-running older session shows the option disabled until
you restart; the manager never installs these display hooks during a loaded battle.

This displays position circles for non-sunk ships in the battle map at every
zoom, including ships the player has not spotted. Pan or zoom out to find distant
enemies. It does not unlock hidden-ship inspection, ship names, target solutions,
enemy aircraft, torpedoes or mines. Native spotting and AI knowledge are unchanged;
the cheat changes only the player's ship-marker drawing path (four guarded sites),
not the engine's broad debug / ShowAll mode. The AI-fairness mods stay independent.

At close zoom, extra circles are drawn only for hidden ships. Already visible
ships keep their native drawing instead of receiving a duplicate marker pass.
At far zoom, normal known-ship marker rules are retained. This removes redundant
overlay drawing work; it is not a measured FPS guarantee. The optimization needs
a fresh game launch. No detection, mine, torpedo, battle-speed or simulation
settings are reduced for performance.

Native discovery, disabled-path equivalence and marker-gate behavior are tested
in an emulator. Seeing the markers in a real battle remains unverified.

### Daytime and clear weather

Restart RTW3 through **Play with mods** with **Live Cheats** enabled, then load
your campaign and open **F10 / LIVE CHEATS**. Refresh, tick **Force daytime
(battle clock keeps running)** and/or **Clear weather / calm seas (both sides)**,
then press **Apply live changes**. Scroll down if Apply is below the window.
You can set them before a battle or during a paused battle. An older running
session shows these controls disabled until RTW3 is restarted through the manager.

Force daytime makes native calculations for the current battle time return
daylight, removes the battle map's night shading, and applies daylight to
aircraft launch and predicted arrival/return checks. Aircraft planning colours
also show daytime. The date, elapsed minutes, sortie schedules and battle clock
continue normally. Sunrise/sunset searches retain natural future-time answers.
Version 0.5.1 fixes the earlier current-time-only override, which could leave
aircraft blocked by an expected night landing and leave the map shaded as night.
Clear weather sets the native precipitation to clear skies and the sea state
to calm, updates native weather labels/colours and uses the native clear-sky
day and night visibility calculations, with their average used for twilight.
Weather changes pause while this setting is on.
Aircraft still obey their other native readiness and flight-operation rules.
These conditions affect both sides; they do not reveal hidden contacts.

Untick and Apply to return to natural daylight or restore the weather and
visibility captured when clear weather was enabled. Leaving the battle also
restores captured weather. Both switches stay selected for later battles in
the same session and reset when RTW3 exits. The switches are not save-editor
fields; saving a battle while forcing weather can retain its current combat
conditions in that save.

The extension verifies native code signatures and installs five hooks only at
the title screen. Offline checks cover daylight scoping, forecast handling,
clock/register preservation, weather restoration, battle transitions, address
relocation, guarded Apply and the manager controls. The native aircraft launch
readiness and return-warning decisions are exercised with a future night
landing, including times after midnight; natural sunrise searches are preserved.
Map shading checks preserve its output solar vector and original stack cleanup.
An older running session shows a restart notice for this fix.
A real battle walkthrough
remains for the user to test; no campaign was loaded or advanced for validation.

The adapter's guarded commit, stale-data handling, byte-sized flags and native
prologue replay are emulated in automated tests. Main-thread request dispatch
is also checked with a no-campaign request that is safely refused. A positive
cheat application in a real loaded campaign and interactive F10 walkthrough
remain unverified; no personal campaign was changed for these tests.

## Research progress and aircraft shortcuts

F10 now includes an installed-technology progress bar, per-branch completion,
**Research ALL technologies**, and **Fast aircraft requests (1 turn)**.
The floating in-game companion also shows overall progress. Both quick actions
apply immediately and leave unrelated edits pending. They affect only your
nation; aircraft completion still uses the next turn and native delay rules.
The separate Campaign QoL package automates the two specific prompts and bounds
AI procurement. See [RESEARCH_AND_QOL.md](RESEARCH_AND_QOL.md) for scope and settings.

## Saved campaign: quick controls

1. Save your campaign and close RTW3.
2. Open **SAVE EDITOR > Quick controls** and select the slot/nation. The newest save is listed first.
3. Edit the values and choose **Back up and apply**.
4. Start RTW3 again and load that same save.

The editor supports:

- **Funds:** set the treasury or use the +100,000 button.
- **Income:** change the native naval budget level and national resource base.
  The game still calculates the final income with its fleet-size, possession,
  political and wartime modifiers. These are native income inputs, not a fixed
  monthly-income override. For example, doubling the budget level generally
  increases income, while preserving the native income calculation.
- **Shipyard size:** change DockSize, the maximum hull tonnage a dock supports.
  Total yard throughput is still calculated by the game from dock size and other
  modifiers; it is not a separately stored fixed number in this editor.
- **Build time:** choose a ship under construction and a target number of
  remaining turns. This changes its per-turn construction spending while
  preserving total cost and progress already paid. Hurry and Halted are cleared.
  Native rounding can affect the exact displayed remaining time.
- **Fast refit / rebuild:** select an active yard project and use the one-turn
  shortcut, or set a custom duration. Normal refit / repair countdowns accept
  1-99 turns; construction and major rebuild targets accept 1-1200.
- **Research speed:** edit the campaign's ResearchSpeed setting, normally 100.
  This is a global campaign setting and affects every nation.
- **Prestige and unrest:** additional controls for testing campaign situations.

The whole selected save slot, including design and associated files, is copied
to `Mods/Manager/save-backups/` before any write. Edits preserve the original
encoding/BOM, line endings and unrelated fields. A changed-save fingerprint
blocks stale writes. The editor refuses to edit while RTW3 is running.

To undo an edit, close RTW3 and copy the backed-up `.bcs` back into its original
slot. Keep the other associated files with the campaign when moving saves.
Do not overwrite a newer campaign without keeping a copy first.

## Saved campaign: advanced fields

Open **SAVE EDITOR > Advanced fields**, select a save, then a section or
**All sections**. Search field names or current values; for example
`ResearchPoints`, `RepairTime`, `Funds`, or a ship's name. Results are paged in
groups of 250. Edit the **New value** cells marked **Editable**, then choose
**Back up and apply edits**. Changes on different pages/sections stay pending
together. The editor reports the count and backs up the whole slot once.

Supported fields, when present and within the editor's allowed range, include:

- Campaign year/month/day, research settings, fleet-size setting, maximum
  airbase size, treaty limits/duration and selected campaign options.
- Every nation's treasury, budget/resources, dock size, prestige/unrest,
  fleet morale, research allocation, intelligence effort and training settings.
- Research-area points, priority and advantage. Current technology levels and
  individual technology flags remain read-only because they need coordinated
  engine changes; the editor does not claim to safely unlock all inventions.
- Ship names/descriptions, crew quality, refit/repair time, construction cost,
  progress/spending, maintenance, Halted/Hurry, build/engine year and battle stars.

IDs, object counts, nation identity, design references, design-linked dimensions
and weapons, and unsupported fields are visible but read-only. A valid calendar
date and consistent construction cost/progress are required. Text uses the
existing byte encoding; unsupported characters and line breaks are refused.
Ranges are conservative editor limits, not a promise that every combination
is a balanced or fully gameplay-tested campaign. Keep separate test saves.

The inspected Game1 example exposes over 6,000 editable existing fields across
its nations and ships. The exact count depends on the campaign. This is a
structured editor, not an unrestricted raw-file replacement or design editor.

**Open Save Editor.cmd** opens the manager directly on its Save Editor tab.

## Manual legacy fleets in every start year

Enable **Manual Legacy Fleet - All Start Years**, then launch through the
manager and begin a **new** campaign. **Manual build of legacy fleet** is
available for 1890, 1900, 1920 and 1935. It stays optional and is not forced on.
Its native starting-prestige and fleet-funding penalties remain.

The manual designer starts at the selected campaign year minus one (1889,
1899, 1919 or 1934), rather than always using 1899. Existing campaigns are not
converted back into a starting-fleet phase. Automated checks cover the native
visibility/selection gates and year hook. Full new-campaign gameplay for each
year remains unverified; use a separate slot.

# Week display and larger hulls

**Seven-Day Calendar and Week Display** (Week Beside Month until it was merged
into the calendar package) adds the week directly to the native campaign-date label:
`Japan, Feb 1890 Week 2`. It reads the decoded campaign day whenever the label
updates. Days 1-7 are Week 1, 8-14 Week 2, 15-21 Week 3, 22-28 Week 4,
and 29-31 Week 5. The display itself does not change the turn length.

**Historical and Paper Hulls - 200,000t** raises the input and calculation ceiling
and expands actual DD/CL/KE/AV/CVL/CV class checks. It also allows 80 CVL aircraft.
It retains component weights, treaties, dock size and other native requirements.
After opening an existing design, change displacement once to initialize the input.
You may also need to enlarge the dock through the cheat menu before building a
larger ship. The mod does not turn a 6,000-ton dock into a 200,000-ton dock.

Machinery lookup rows through 90,000 tons are unchanged; larger hulls use a
documented estimate. This is not a calibrated naval-architecture overhaul.
Each class has its own allowance and retained restrictions; not every class
can validate a 200,000-ton ship. See `HISTORICAL_HULLS.md` for limits and sources.

Both visual/designer changes are runtime hooks removed when RTW3 closes. The
official executable on disk stays unchanged.

## New: all-ships shortcuts and paid counterintelligence

**Fast build ALL** and **Fast refit ALL** immediately apply one turn for every
eligible project of the selected nation; no separate Apply click is needed.
They refresh first and do not apply unrelated pending edits. Refits include
repairs and major rebuilds. Costs are preserved. Restart with mods to enable the larger live
transaction. Saved edits still require RTW3 closed and back up the full slot.

The optional **Campaign Security** mod also adds a paid counterintelligence
percentage in F10. It starts at zero each launch, adds its cost to the native
Intelligence line, blocks new AI contracts at player yards, and disables
espionage technology theft for all nations.

See [CAMPAIGN_SECURITY.md](CAMPAIGN_SECURITY.md) for scope and limitations.

The ship selector shows the full non-sunk fleet, with active yard jobs first and
actual ship names. Ships without active yard jobs remain visible but cannot be
sped up. Campaign ships use RepairTime 100/101 for sunk/scrapped status; the
unrelated tactical Sunk byte is not used. Existing version-2 live sessions only
need the updated manager/cheat window reopened, not a game restart.

