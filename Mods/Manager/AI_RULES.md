# Torpedo initiative and AI fairness - experimental v0.1

The separate **Battle AI** package adds local steering repairs, bounded
report-only contact memory, auto-run carrier air operations and sunk-target
guards. See [BATTLE_AI.md](BATTLE_AI.md). The scope below describes the torpedo
initiative and fairness packages alone, not every effect of that additional mod.

These are two independent runtime mods in the existing manager. Start with a
separate test campaign. They change native decisions, not just UI labels.

The separate detection-only torpedo-evasion option is documented in
`HAZARD_FOG.md`. It removes preventative AI turnaways; it does not add a wake
spotting model or claim that every mine-information path has been audited.

## What actually changes

**More Decisive Torpedo AI - Both Sides** changes the two automatic opportunity
assessment rolls from `Random(100)` to `Random(75)`. The original willingness
threshold still depends on the target, range and other native factors. For
example, a threshold of 40 now passes 40/75 assessments instead of 40/100.
Zero and negative thresholds still never pass. These are assessment chances,
NOT hit chances or a promise of a particular increase in torpedoes fired.

Both player ships with automatic torpedo fire and enemy ships use the same
change. The complete final automatic firing routine is byte-identical to the
original: its visibility/identification gates, geometry, solution uncertainty,
fast/slow torpedo range checks, friendly-fire-line checks, available mount
checks and actual launch remain native. Damage, accuracy, torpedo stocks,
reload times and officer/training benefits are not altered. Manual firing is
not changed. This is a focused initiative improvement, not new formation,
pathfinding, carrier, research or strategic-planning AI.

**Fair AI - No Optional Advantage or Emergency Grant** makes six audited
decision reads of the campaign's `AiAdvantage` option behave as if it were off.
Five are conditional checks and one changes diplomatic weighting. The option
can still appear checked in the native campaign UI or save; the runtime
override takes precedence while this mod is loaded. The saved setting is not
edited, so turning the mod off restores its original meaning.

The mod also skips the entire emergency event in `AINationAdjustBudget` that
can add 2,000 funds when an AI nation's funds are below -10,000. Its accompanying
report is skipped too. Normal budget adjustments and spending decisions remain.
This can leave bankrupt AI nations weaker; it is a fairness change, not a
promise that difficulty will remain unchanged.

Different national resources, research advantages, officer skills, training,
weapon technology and legitimate uncertainty remain. This is NOT a claim that
every possible engine asymmetry has been identified or removed. It does not
force all nations to have the player's income or technology. It does not give
the AI new access to unseen ships or torpedoes.

## Evidence and limits

The installed supported executable is the Steam-authenticated 1.01.44 build,
SHA-256 `355e55650b0eb565bfda5ba71e2a9a6697371a2ba612582dbf9bd769f242a4f2`.
The code is discovered using named Delphi methods, independently checked
serialized fields, complete instruction signatures and expected consumer
counts. No remembered absolute address is used to patch a new process.

The native `TorpedoShotPossible`, `FireMount` and
`IsFriendlyShipInLineOfFire` methods anchor both automatic launch paths.
The `AiAdvantage` load and save agree on the field used by all six audited
decision reads. The emergency grant uses the independently discovered nation's
`Funds` field, not a guessed economy offset.

Offline tests exercise the actual supported code snapshot and run the changed
branches in an x86 emulator. They check symmetric initiative, rejected targets,
unchanged final launch/hit code, disabled-option flags/registers, no rescue
write or report, mismatched-build refusal, patch conflicts and rollback.
These checks are NOT battle gameplay or long-campaign balance verification.
Runtime reports explicitly record `battle_gameplay_verified: false`.

The developers describe automated firing solutions with era/technology-dependent
uncertainty and AI evasion based on threatening destroyer positions, not on
reading torpedoes in the water. That explanation is not evidence that every
engine rule is symmetric, and the mods do not claim to have disproved or fixed
every report of cheating. Source: [official torpedo developer diary](https://www6.slitherine.com/news/rule-the-waves-3-torpedo-dev-diary).

The installed manual also explains automated firing, training and officer
influences. Those paid/earned advantages are deliberately retained.
:codex-file-citation{path="D:/Games/RTW3/Manuals/Rule the Waves 3 Manual Patch 2026.pdf" purpose="source"}

## Enable, disable and test

Refresh the manager, select either or both mods, then use **Play with mods**.
They must attach at the title screen before a campaign is loaded. Changes are
memory-only; RTW3.exe on disk and personal save files are never edited by the
adapters. Normal play and saving can of course record the resulting campaign
outcomes. Close the game and deselect a mod to restore its native rules.

For a meaningful comparison use copies of the same test battle and compare
torpedoes fired, valid opportunities, hits, friendly-fire incidents and ship
losses over repeated runs. Torpedo use should be compared with the torpedo mod
off/on while keeping fairness, nation, doctrine, training, weather, year and
realism settings constant. A single battle is not sufficient evidence of a
better AI or a statistically higher hit rate.

The existing seven-day calendar still runs economy, AI and timers once per turn.
These mods do not repair that separate pacing limitation. Monthly turns are the
cleaner baseline for testing the AI changes.

Runtime diagnostics: `Mods/CampaignOverhaul/torpedo_initiative_report.json` and
`fair_ai_report.json`. `attached: true` proves patch installation/readback only,
not that a battle has been tested. A mismatched build or changed code is refused
before any write; an interrupted install attempts to restore its original bytes.
