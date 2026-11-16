# Campaign Security

Enable **Campaign Security - Counterintelligence and Closed Yards** and **Live
Cheats**, then restart through **Play with mods**. These changes cannot be
installed into an already-loaded campaign. The official executable stays intact.

## Counterintelligence

Open **F10 / CHEATS**, refresh the loaded campaign, set **Counterintelligence
budget % (0-10)**, and choose **Apply live changes**. This is paid spending,
not a free defensive bonus.

- Starts at **0% each game launch**. It is session-wide, not saved in a campaign.
  Reapply it after restarting; it also follows you if you load another campaign
  in the same session.
- Each percentage point allocates 1% of the current naval budget and gives an
  additional 8% chance to stop an otherwise successful foreign spy operation
  against the player. At 10%, interception is 80%, not perfect immunity.
- Cost is `floor(native annual naval budget * percent / 1200)` per campaign
  turn, added to the native **Intelligence** expense. The normal monthly-balance
  calculation deducts it once. The F10 panel shows the last calculated extra
  cost. Native overseas intelligence spending is separate and unchanged.
- Weekly Calendar currently still charges the native monthly economy per turn;
  counterintelligence follows that same per-turn economy. It does not correct
  weekly economic balance.
- Protects the native `SpySuccess` information/industrial-espionage path. It does
  not promise to prevent every sabotage, random event or ordinary military
  observation. The percentage/chance relationship is an experimental mod rule,
  not a historical intelligence model.

## Closed player yards

AI foreign-yard selection skips the player's yards. A second guard rejects new
AI orders using an older design assigned to the player's yard, before a ship is
created or money is charged. Player ship orders and AI orders at other nations'
yards remain permitted. Existing construction contracts are not cancelled,
transferred or refunded.

## No stolen technology

All nations, including the player, skip the industrial-espionage branch that
copies gun quality, grants completed technology, or steals research progress.
Other spy information remains. Ordinary research, technology purchases,
agreements and learning from foreign-built ships are not removed. Previously
acquired technology is not rolled back.

## Fast all-ships buttons

Both the F10 live panel and saved-campaign editor include:

- **Fast build ALL (1 turn):** all eligible new ship builds of the selected nation.
- **Fast refit ALL (1 turn):** all eligible refits/repairs and major rebuilds of
  that nation. Native refits and repairs share one countdown.

Click an **ALL** button to apply that action immediately. No separate Apply
click is needed. It refreshes the selected nation first, sends no unrelated
pending scalar/selected-ship edits, and preserves staged money/budget/reveal
inputs. The single-ship shortcuts still stage their edit for **Apply**.
These are one-time edits, not
permanent automatic-completion switches. Sunk/finished ships and native status
sentinels are excluded. Unstarted designs and submarines' separate build queues
are not surface-ship yard projects and are not included. Construction/rebuild
cost is preserved, with the remaining spending accelerated; native delays and
yard constraints still apply. The all-build operation resumes halted eligible
construction, as the selected-build shortcut already did.

Live edits validate the complete batch before any write and commit on the
game's own UI thread. A changed captured ship cancels the batch. The larger
mailbox uses a separate record pool, leaving submarine and reveal state intact.
Older running sessions must restart to use it. Save edits back up the entire
slot and replace only the requested nation's eligible fields. Personal saves
are not changed until the user explicitly applies an edit.

## Verification boundary

Native-code discovery is tied to the authenticated Steam-derived build, with
address relocations normalized and complete reviewed routine hashes checked.
Isolated x86 tests cover budget math, interception boundaries, yard/order
guards, theft dispatch and bulk atomicity. Save tests use temporary fixtures.
These checks are not evidence of long-campaign balance or player battle FPS.

Installed validation on 2026-10-23: all 145 automated tests passed; both manager
copies compiled and the isolated live/saved button fixture passed. A fresh
title-screen session read back all five security hook sites and all three code
pages, plus bulk dispatcher version 2 with capacity 120,024 records. Initial
counterintelligence allocation and extra cost were both zero. No campaign was
loaded, no turn advanced, and no personal save was modified by validation.
See `campaign-security-validation.json` and `fast-cheats-ui-test.json`.

### 0.3.1 ship-list / direct-action correction

The cheat ship selector now shows all non-sunk campaign ships, with active jobs
first and actual names. Name is the strategic ship's string at +0c, not its
numeric ID at +04. Campaign sunk/scrapped states are RepairTime 100/101, verified
against native SinkShip and ScrapShip; the unrelated tactical Sunk byte at +1a
is no longer read. Existing version-2 sessions receive this read-only layout
correction without a game restart. Reopen the updated manager/cheat window.

Both ALL buttons now refresh and apply their own action directly. They do not
submit unrelated staged scalars or selected-ship edits. Automated checks pass
for direct button events, preserved pending values, serving-only fleets,
actual-name discovery, loss sentinels, stale guards, and backed-up save edits.
Full regression run: 157 tests passed. Personal campaign inspection was
read-only; no cheat, save or turn was applied during this correction.
