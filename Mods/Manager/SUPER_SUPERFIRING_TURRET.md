# Super-Superfiring Turrets (BB/BBB/XX/XXX)

Enable **Super-Superfiring Turrets (BB/BBB/XX/XXX)** and restart through **Play with mods**. In the ship designer,
add a main turret at B as usual; the **Add turret** list then also offers **BB - Forward super-superfiring**, and
once BB is on the ship, **BBB**. X works the same way: XX, then XXX. A ship can have up to three raised turrets
forward and three aft.

## What they are

BB and BBB are copies of B; XX and XXX are copies of X. In every game rule they are B and X turrets: the same
firing arcs, nominal bearing and raised level (the game has one raised level, so BB stands as high as B), and
they are saved as B and X. What differs:

- **Placement.** A new BB is placed one turret spacing (the distance from A to B) further towards midships than B,
  and BBB two. XX and XXX step forward from X by the X-to-Y spacing. Move them as you would any turret.
- **Labels.** The main gun list names the second and third B on the ship BB and BBB, in list order (XX and XXX
  likewise). Delete the first B and the old BB becomes B: all three are the same kind of turret.
- **Weight.** The game already makes a raised turret heavier for its taller barbette: B x1.10 and X x1.05 of a plain
  turret. Each higher copy adds the same step again: BB x1.20 and BBB x1.30, XX x1.10 and XXX x1.15. More weight
  this high also means more top weight.
- **Crowding.** The designer counts centreline gun and torpedo mounts. On any ship over 1,200 t the game allows 7:
  at 7 the design report warns "Heavy or crowded centreline gun and torpedo mounts" and the ship loses ROF, and an
  8th is refused. With this mod a big ship has room for more: one more mount for every full 15,000 t above
  10,000 t (8 from 25,000 t, 9 from 40,000 t, 10 from 55,000 t), up to 12. Smaller ships keep the game's numbers.

Every other check that applies to B or X applies to each copy, and a nation can still only build as many centreline
turrets as its research allows.

## Limits

- Battle reports and the ship information screen name a copy "B" or "X", as the game does for any B or X turret.
- The computer's designs never use the copies.
- Tried in the ship designer; not yet played in battle or a long campaign. Try it on a test design first.

## How it works

The game keeps a turret's position as one letter, read by its rules everywhere, and where it is drawn separately.
The runtime adapter (`Mods/CampaignOverhaul/super_superfiring.py`) hooks the Add turret list (after B and X),
the new turret's placement, the main gun list labels, the turret weight after the game's B and X terms, and the
design report's centreline limit. Closing RTW3 removes the hooks.

Before 1.0.0 this mod (Codex, 0.2.0) added Z/F/G/H/I to `Data/gunpos.txt`, which the game never reads, and
treated F-I as raised; F-I are the game's own wing positions. 1.0.0 drops both.
