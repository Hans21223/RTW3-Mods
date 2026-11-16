# Detection-only torpedo evasion - experimental v0.1

Requested rule: react only after legitimate detection, not complete blindness
after a threat is discovered. This is separate from the optional Fair AI mod.

## Implemented change

The original AI can choose a preventative torpedo-attack avoidance stance from
the position and type of threatening ships. That is not the same as reading
live torpedo tracks. The [official developer diary](https://www6.slitherine.com/news/rule-the-waves-3-torpedo-dev-diary)
explicitly describes ship-based threat assessment and says those decisions do
not use torpedoes in the water.

This optional mod skips all six audited assignments of the predictive torpedo
avoidance stance, including their log messages and threat-pointer changes. It
also stops followers inheriting their leader's predictive torpedo turnaway.
Earlier ordinary stance choices are retained instead of assigning an invented
replacement stance or overriding the player's manual course.

The rule is symmetric for automatically controlled divisions on both sides.
Normal navigation, gunfire-threat reactions, retreat decisions and manual
player orders are not disabled. Consequently, an enemy can still change course
for reasons unrelated to a detected torpedo.

Native last-minute torpedo detection/evasion and hit resolution are unchanged.
There is no new continuous wake-spotting model, detection flag, guaranteed-hit
rule or torpedo damage boost. Removing predictive avoidance makes the AI less
cautious around torpedo-capable ships; it is a requested behaviour change, not
evidence that the original predictive tactic was cheating.

## Mines: inspected, not changed

The three explicit-ship tactical mine-routing calls inspected pass the actual
ship or division flagship into the native mine-area query. With a ship, that
query branches past its editor/no-ship path that checks both layers, and instead
selects a layer using the supplied ship's side. The new adapter verifies those
arguments and that branch before accepting the build.

That is a limited code audit, NOT proof that every tactical/strategic mine
information path is correct. A layer's side alone does not prove how every
minefield was discovered. No direct hidden-player-mine foreknowledge bug was
confirmed in this inspection, so no speculative mine patch was installed.
Native mine detection, reported minefield avoidance, minesweeping, collision,
mine damage and operational mining are unchanged. The full mine-information
audit remains incomplete.

## Use and limitations

Select **Detection-only Torpedo Evasion - Experimental** in the manager and
restart through **Play with mods** before loading a campaign. Start a NEW
battle. Do not resume a saved battle that already contains the old predictive
avoidance stance; this version does not migrate saved battle orders.

The adapter refuses live swaps after a campaign is loaded. It changes only
running memory, never RTW3.exe on disk or personal save files. Normal play can
of course produce different outcomes when you save later. To restore the
original AI, close the game, deselect the mod and restart.

The existing **More Decisive Torpedo AI - Both Sides** mod is compatible: it
changes opportunity assessment, while this mod changes predictive evasive
decisions. Existing mod selections are preserved; the Fair AI option is not
silently re-enabled.

## Verification boundary

Ten new offline tests inspect the supported authenticated native code and
exercise the changed branches in an x86 emulator. They check that no predictive
stance, threat pointer, log or inherited course is written, that stack and
registers survive, that native close-range/mine code remains untouched, that
the three inspected mine calls pass ships, and that changed builds or
overlapping AI mods are rejected. The complete suite passes 104 tests.

On 23 October 2026 the new adapter attached alongside the user's existing
selection, and all seven changed sites verified in a fresh running session.
The campaign-player pointer remained zero: no campaign was loaded and no battle
was played for this check. The separate Fair AI option was left disabled as
selected. Installation verification also passed with RTW3.exe unchanged.

These tests do not prove battle performance, improved realism, mine fairness
across every code path or campaign balance. Runtime startup/readback results,
when available, are recorded separately in
`Mods/CampaignOverhaul/detection_only_evasion_report.json`.
