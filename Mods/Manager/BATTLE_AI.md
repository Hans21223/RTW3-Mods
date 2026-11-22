# Battle AI - experimental missile tactics, formation, steering and air operations

Enable **Battle AI - Missile Range and Formation**, then
restart through **Play with mods** before loading a campaign. The manager can
stay open; these controls do not require a new manager executable. Changes are
memory-only for this authenticated managed build. Disable the package and
restart to restore native behavior.

## Version 0.5.1: missile regression correction

Version 0.5.0 made firing too restrictive and did not reliably control courses.
Its custom firing replacement and 4/12 missile budgets with a three-minute
reassessment delay are no longer installed. Automatic surface missile attacks
again use the native contact selection and launch routines, including researched
SAM surface attacks. Native firing arcs, minimum/maximum ranges, readiness,
ammunition, friendly-line checks and launch timing remain. The native fallback
that searches the global ship list runs again (it was skipped from 0.5.1 until
2026-11-22, and ships under Fire at will then held their missiles at enemies
their own sensors did not track): it picks enemies your side has spotted,
behind the nation's missile research and the native identification check. Its
one-in-500 pick of a friendly ship is removed. Manual missile targeting is
unchanged.

**Missile blind fire** (2026-11-22). A ship that launches missiles gives its
position away for 10 battle minutes: the global search may then pick it although
nobody has sighted it. Ships under Fire at will (and the computer's ships) answer
launches from beyond their own sensors, if the launcher is within their missile
range. Arcs, ranges, research and the rest of the native search still apply, and
both sides get the same rule. A new battle (its clock below the last minute
seen) forgets the last battle's launches, whose ships' addresses may be reused.

Missile range discipline now runs inside **SetNewCourse**, after its input checks
and before its original terrain checks. It covers AI surface combatants in
roles 0-4, including the role 4 used by the user's destroyer screen. Merely
changing a Hold/Increase label is insufficient for screen/objective navigation.
A long theoretical gun maximum also no longer disqualifies missile range control.

While dedicated anti-ship missiles remain loaded, a known opponent inside 75%
of native missile range causes an **actual away course**. Between 75% and 90%,
the course turns across the opponent to maintain separation, choosing the beam
that exposes a loaded launcher using native arc/range checks. Outside that band,
native navigation continues. This also works inside 5,000 yards and on ordinary
Rapid Close/No Enemy labels when the flagship actually has a current contact.
Manual divisions, disengagement, explicit withdrawal, torpedo/threat evasion,
noncombatant flagships, and ships without loaded SSMs retain their native path.
Native turning, land and shallow-water checks still apply after the correction.

The 0.5.0 target-priority controller, cached salvo limits and their tests were
removed. `missile_ai.py` now holds only the native audits and loaded-range/arc
helpers that the active `missile_range.py` reuses. `missile_standoff_percent`
is the only missile setting; the three old salvo keys were removed, so a
custom manifest still setting them is refused until those keys are deleted.

The captured 1946 battle has destroyers in role 4 and surviving oversized DDs
with **OriginalEndurance=0, CurrentEndurance=0 and 5-knot orders**. Those existing
battle records predate fuel initialization with the hull correction. This AI
update does not refill or rewrite them; they cannot be expected to outrun faster
enemies. The earlier DD fuel fix applies when ships initialize for a new battle.
No personal campaign or saved battle is modified by installing these changes.

The regression harness executes the actual native 1946 range calculation,
launcher-arc/minimum-range checks, missile firing routine and ammo decrement.
Projectile allocation/flight, geometry distances, random rolls and UI/logging
are controlled boundaries; this is not a live battle replay. It verifies heavy
and medium SSM launches, permitted SAM surface fire, minimum-range refusals,
actual away/beam course values for screen DDs, close-distance cases, manual and
emergency exclusions, native course continuation, and relocated code.
Real battle behavior remains unverified. The earlier test count did not prove
that the mocked geometry/launch assumptions worked in the game.

## Keep battleships and battlecruisers with their line

Version 0.2 adds a guard at the native tactical stance dispatcher for AI-controlled
B/BB/BC divisions in independent, core or support roles. It only changes **Close**
and **Close rapidly** orders:

- Once a currently known enemy is within **75% of the flagship's native main-gun
  range**, the division uses the native **Hold** stance. It can still close from
  outside that distance and fight using the original gunnery navigation.
- A core/support division more than **6,000 yards** from its assigned lead's
  trailing capital ship regroups if it is also more than **1,500 yards closer to
  that known enemy** than the trailing ship. Divisions catching up from behind
  are not pulled back. The lead must belong to the same side and remain afloat.
- Regrouping uses the original course and land/mine-clearance helpers. If that
  return route is blocked, the division holds instead of continuing its charge.
- Capital ships no longer receive this mod's direct pursuit of a remembered
  contact when no enemy is currently in sight. Their native force/objective
  navigation remains in charge in that situation.

The stance guard checks the flagship's current contact list before reading an
enemy. It does not scan hidden ships or reuse a stale report's live-object pointer.
Both sides use the same rule. Manual control, retreat, threat/torpedo avoidance,
and explicit scout/screen/patrol roles retain their original paths. Native
special-mission paths handled before stance dispatch also remain unchanged.

This controls division orders. It does not replace individual ship collision,
damage-control or formation-following logic, and cannot guarantee that every
risky maneuver or formation problem is eliminated. It also does not impose an
absolute 6,000-yard tether: the rule applies specifically to running ahead toward
a known enemy while trying to close.

## Version 0.4: fewer flip-flops, no blind charges, less early retreat

These come from reading the native stance choosers (one each for big ships,
light cruisers, destroyers and auxiliaries, all called through one dispatcher)
and the force-withdrawal routine. Same rules for both sides; manual (non-AI)
divisions keep native behavior.

**Stance commitment (dancing).** The native choosers re-roll a division's stance
every few minutes, several times with plain coin flips: a big ship inside its
desired range picks INCREASE or HOLD 50/50, "enemy fire getting uncomfortable"
picks INCREASE or HOLD 50/50, a cruiser on frustrated hold increases 50% of the
time, and out-of-range CLOSE fights uncomfortable-fire INCREASE. Divisions
therefore weave. Now, for `stance_commit_minutes` (default 10 battle minutes)
after a recorded change, the dispatcher undoes only these reversals:
INCREASE to HOLD/CLOSE and HOLD to INCREASE/CLOSE. Always allowed: DISENGAGE,
threat/torpedo avoidance, no-enemy, CLOSE RAPIDLY, anything leaving CLOSE,
divisions at 30%+ average damage and any enemy contact inside 5,000 yards.

**No blind bow-on courses for capitals.** Rejoin, objective, go-home,
report-chase and HOLD course choices ignore where the enemy is, so an AI B/BB/BC
could sail straight into the enemy line. Unless its stance is CLOSE/CLOSE
RAPIDLY or a threat/torpedo evasion, a course within 45 degrees of the nearest
currently sighted enemy B/BB/BC/CA inside `capital_gun_range_percent` of its
main-gun range is turned to keep that ship 60 degrees off the bow, on the side
the course already leaned. Native land avoidance still runs afterwards. Only
the flagship's current contact list is read.

**Uncomfortable fire means outgunned.** Big ships turned away or held when the
enemy's hit chance on the flagship passed 3-4%, which is ordinary in any gun
duel, whenever the enemy was at least half as strong. Now the enemy must be at
least as strong (native strength sums) before that rule fires.

**Withdrawal dead zone.** Each tick the native force-withdrawal routine adds up
reasons (average ammo under 50%: +20, fewer capital ships: +20, enemy 1.2x /
1.5x / 2x stronger: +10-20 each, and so on), then raises the force's withdrawal
level with chance score/(level+1) against a roll, and never lowers it. Any
lasting small disadvantage therefore ended in a retreat. The first
`withdraw_dead_zone` points (default 10) are now ignored; clear disadvantages
still escalate.

**No daylight boredom charges by light ships.** An independent destroyer or
light-cruiser division holding with its target out of gun range rolls a
"frustrated hold" CLOSE, even at an intact battleship in daylight, and the
native daylight rule then pulls it back out: a cycle of creeping in under heavy
fire. In daylight that roll no longer starts a charge at a B/BB/BC/CA under 60%
damage. Night, crippled targets, lighter targets and the separate native
torpedo-attack decisions are unchanged.

## Detached ships stop rejoining and leaving in a loop

Version 0.3 fixes a native flip-flop seen in a real 1930 battle log. The game
detaches a ship that cannot keep up (more than 2 knots below division speed and
falling 5,000-8,000 yards behind), is low on fuel (under 15% and short of range
home) or is over 90% damaged. Every 15-minute check it also re-attaches any
detached ship that is within about 3,000 yards of its old division, without
asking why it left. The same destroyer was therefore detached for low fuel,
re-attached, and detached again about 20 times in one night, turning back and
forth each time; a torpedoed cruiser did the same as a straggler.

A detached ship now rejoins only if those native detach checks would let it
stay: fuel at least 15%, damage at most 90% and maximum speed no more than
2 knots below its old division's speed. Otherwise it stays detached and follows
the native detached-ship orders (go home, rejoin later, and so on). Everything
else in the native rejoin rule is unchanged, including distance and the
survivor-rescue exception. It applies to both sides and to player divisions.
A ship whose old division slows down, or that is repaired, can still rejoin.

## Local pathfinding / steering

This repairs three concrete errors in the native candidate-course checker:

- Both port and starboard half-distance samples now follow the candidate
  heading, rather than checking the original heading again.
- A port candidate with a blocked far point is rejected, matching the
  starboard branch, instead of sometimes being accepted.

The native course increments, turn constraints, map geometry and side-specific
mine-knowledge queries remain intact. Both AI sides, including AI-controlled
player divisions, use this shared helper. It is also used for flight-operation
steering. The fix does not turn off collisions, shallow-water checks or mines.

This is a local-steering repair, **not** a replacement A* / navmesh planner or
a promise to solve every island, coastline, traffic or formation problem. The
bypassed global coastal-route routine is deliberately left bypassed; merely
enabling dormant native code is not evidence that it works safely or quickly.

## Contact memory / object permanence

When an independent, AI-controlled lighter surface combat division has no current
contacts, it can steer toward a recent opposing surface-contact report.
Defaults are **20 battle minutes** and a **45,000-yard** radius. Fresher reports
are preferred; equal-age reports are resolved by distance. The search stops
using that report when it expires or the division gets within 2,000 yards.

Only the report's stored position, timestamp, recipient side and reported ship
composition are read. The associated live enemy-object pointer is never
dereferenced. There is no exact hidden-position tracking, automatic new contact,
extra spotting, forced firing solution or new mine/torpedo knowledge. An enemy
may have moved elsewhere: these are last reported locations, not guaranteed
interception points. Existing native report errors and uncertainty remain.

Manual divisions, escorts/supporting formations, withdrawing forces, damaged
divisions (30% or higher native division-damage result), carriers, airfields and
auxiliaries retain native course selection. Current visible contacts retain
normal combat navigation. Searching also has to pass the native clear-course
check; if it fails, normal navigation is used. No reports means no memory bonus.
The rule applies equally to both sides and stores no cross-battle object pointers.

The optional manifest settings are:

| Setting | Default | Allowed range |
| --- | ---: | --- |
| `contact_memory_minutes` | 20 | 1-60 |
| `memory_radius_yards` | 45000 | 5000-100000 |
| `capital_max_advance_yards` | 6000 | 2000-20000 |
| `capital_gun_range_percent` | 75 | 50-90 |
| `missile_standoff_percent` | 75 | 50-85 |
| `stance_commit_minutes` | 10 | 0-60 (0 disables) |
| `withdraw_dead_zone` | 10 | 0-50 (0 is native) |
| `catapult_strikes` | 1 | 0-1 (0 is native) |

Edit `Mods/Library/battle-ai/mod.json` while the game is closed and restart for
new settings. These are bounded search rules, not an unrestricted learning AI.

## Catapult launches without turning into the wind

Natively a carrier with flight deck catapults launches its CAP and search
flights by catapult without turning, but turns into the wind for every strike,
and a nearby enemy ("enemy presence prevents turning into the wind") delays any
launch. With `catapult_strikes` 1 such a carrier launches strikes by catapult
too, keeps its course, and is not delayed by enemy presence. Carriers without
catapults, seaplane carriers and floatplane ships keep the native rules, and
every carrier still turns into the wind to recover aircraft. Launch timing and
deck spotting are native.

## Aircraft during auto-run battle

Use the game's **Auto-run battle** command. Starting it initializes the native
air-search plan for player carriers as well as the enemy. While auto-run is
active, four permission gates let the native strike scheduler select player
carrier squadrons and process ready strikes, including previously manual-ready
squadrons. No extra launch button or F10 cheat is needed.

Stopping auto-run immediately restores the original permission decisions for
new orders. Aircraft already launched, or orders already prepared by the native
scheduler, are not rewound. The generated routine search plan can remain until
you change it in normal air operations.

Weather/light, range, aircraft suitability, availability, readiness, deck
capacity, launch/recovery and native timing/random-assessment rules remain.
This does not guarantee an immediate launch, endless sorties, night operations
without the required capability, or perfect targets. It does not automate
unrelated confirmation dialogs. Outside auto-run, player carrier launch
permissions behave as before; existing enemy air operations remain native.

## Stop wasting ammunition on sunk targets

The native `Sunk` flag is cross-checked against both battle save and load code.
Sunk targets are rejected by the two automatic target-preference selectors,
and guards reject them before gun firing, torpedo-mount launch and missile-mount
launch. That also prevents launching from a stale target cached before a sinking.
Zero / position-only target pointers keep their native behavior.

The gun engine already has its own sunk-target guard; it is retained, with the
new check occurring before its larger firing routine. Heavy damage, fire,
immobility, silence or the appearance of a wreck is **not** treated as proof of
sinking. Such ships can still be legitimate targets. Existing shells, torpedoes,
missiles and aircraft already in flight are not deleted or redirected by this
rule. It does not promise to eliminate overkill before a sinking is confirmed.

## Verification and limits

The focused tests execute the actual native steering function with controlled
geometry/mine-query fixtures. One fixture reproduces an unsafe port course in
the original and selects a clear course after patching. Additional tests cover
both midpoints, blocked routes, symmetric report-only memory, expired/future/
foreign-recipient/air-only reports, manual/retreat/escort/damage exclusions, auto-run on/off
gates, native search-plan dispatch, sunk-target guards and their stack cleanup,
address randomization, changed-code refusal and settings bounds.

Capital tests execute the generated x86 guard with controlled division orders,
native call fixtures and current-contact lists. They cover both sides and all
three capital classes, main-battery distance boundaries, legitimate closing,
formation regrouping, ships catching up from behind, blocked routes, manual and
emergency exclusions, foreign/dead leads, and an unreadable hidden enemy pointer.
A retained native-dispatch fixture continues Close while the guarded fixture
switches an in-range charge to Hold. This is not a replay of a real battle.

The current offline validation is in `capital-formation-validation.json`.
Version 0.2 has 16 hook sites and 12 code blocks. Installation files are ready for
the next **Play with mods** restart; hooks are never swapped into a running
battle. No personal campaign was advanced or saved for these checks. Actual
battle behavior, formation effectiveness and performance remain for user testing.

Runtime diagnostics are in `Mods/CampaignOverhaul/battle_ai_report.json`.
An `attached` report proves installed code/readback, not successful battle play.
Counters in its session state track memory steering (+0), auto-run permissions
(+4), rejected sunk targets (+8), capital closing orders limited (+12), capital
regroup orders (+16), refused rejoin-loop re-attachments (+20), undone stance
reversals (+24), capital courses turned off a bow-on approach (+28) and stopped
light-ship boredom charges (+32). They are not campaign statistics or saved data.
Version 0.4 has 25 hook sites. Emulator tests cover the rejoin guard's fuel,
damage and speed boundaries, every blocked and allowed stance transition with
the damage, 5,000-yard, stale-record and manual-division exemptions, bow-on
rotation on both sides of north and its stance/class/side/range exclusions,
the withdrawal dead zone against the native division, the outgunned check
against the native branch, and the light-ship gate by daylight, class and damage.
None of this is a replay of a real battle; it needs playtesting.

Historical version 0.5.0 added one automatic-missile call hook and a final stand-off policy
inside the existing stance wrapper. Missile tests execute the generated x86
decision code with controlled native range, arc, geometry and launch callbacks;
they do not replay the full missile/air-defence simulation. Tests cover both
sides, target priorities and identification, hidden-list non-access, blocked
arcs/friendly lines, loaded-ammo limits, preserved SAMs, shared budgets and cache
collisions, failed launches, clock changes, manual/auto-run behavior, stand-off
exemptions, stance-commitment integration, relocated builds and changed-code
refusal. Existing steering, formation and air-operation tests still run.
Actual battle behavior, balance, missile effectiveness and FPS remain unverified.
New state counters record successful salvo decisions (+40), native-reported
missiles launched (+44) and stand-off decisions (+48).

Version 0.5.1 withdraws that firing replacement and its code. Counter +48 records actual missile-range course changes; +40/+44 are unused.

## Version 0.7: missile ships with empty launchers withdraw

A computer-controlled division whose flagship has SAM or SSM launchers, no
missile left in any of them (loaded or reload) and no main gun over 5 inches
takes the DISENGAGE stance at every stance decision, as the native choosers do
for ships low on gun ammunition. Gun-armed ships and divisions under manual
control are unchanged. The check is the first thing in the stance commitment
hook; test: `test_an_ai_missile_ship_with_empty_launchers_disengages`.
