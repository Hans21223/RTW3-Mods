# VLS cells in the ship designer

VLS cells are part of **Expanded Timeline - Modern Research to 2030, Campaign to 2050**; enable it and restart through **Play with
mods**. Existing ship classes are not converted.

1. Open **Design Ship > Additional armament > Missiles**.
2. Add a normal SAM or SSM launcher at a **centreline** position, or at a side
   (wing) position on a hull of 10,000 t or more (the design report's 4-tube
   limit for side torpedo mounts does not apply to VLS banks). Research the
   missile type first, or use the existing research cheat in a test campaign.
   Medium and heavy SAM launchers may go on side positions once the nation has
   Vertical launch cells (natively only carriers could), so they can become
   side banks.
3. Select that launcher in the missile list and right-click it.
4. Choose **VLS cells (no reloads)**, then **8**, **16**, **32** or **64 cells**.
5. Check displacement, weight, cost and the design report; save normally.

The design report no longer limits side launchers and torpedo tubes on ships
below 1,200 and 6,000 tons, nor heavy SAMs on carriers (see "Freed design
rules" in `HISTORICAL_HULLS.md`).

## Research and hull size

Each bank size needs its technology in the Vertical launch systems branch
(`MODERN_TECH_TREE.md`): 8 cells Vertical launch cells (1974), 16 Modular
VLS magazines (1977), 32 Canister exhaust management (1980), 64 Large VLS
magazines (1983). Without it the game shows what is missing and the mount
stays unchanged.

A hull carries about one cell per 80 tons of displacement, counting every VLS
bank on the design. Hull-integrated VLS modules (1988) raise this to one cell
per 64 tons, close to the densest real cruisers, and Peripheral VLS integration
(2005) to one per 51 tons. Without them a 2,500 t destroyer can carry 24 cells
and a 10,000 t cruiser 120. Both checks run when you choose a cell
count; existing VLS designs stay valid.

VLS cells also need a hull laid down from 1960. Older hulls lack the deep magazine
volume (the 1980s Iowa refits got box launchers, never VLS). A new class has the
current year as its build year, even when developed from an older design, so the
rule only stops editing an existing older class to add cells.

## Weight and topside

A bank weighs its loaded cells, not a trainable launcher and its rails:

| Missile | Tons per cell |
| --- | ---: |
| Heavy SSM | 10 |
| Heavy SAM | 5 |
| Medium SAM, medium SSM | 3.5 |
| Light SSM | 1.5 |
| Light SAM | 1 |

Lightweight composite launch cells (1986) make cells 20% lighter, Compact
self-defence VLS modules (1992) and Next-generation VLS modules (2030) another
10% each. The figures
follow real installations: an empty 8-cell Mk 41 strike module weighs about
14.5 t, and a loaded medium SAM cell about 3.5 t. The total is rounded up to
whole tons. Cost still follows weight in the native formula, so banks cost
less than launchers.

With Compact self-defence VLS modules a light SAM cell is quad-packed (four
missiles, see `MODERN_TECH_TREE.md`) and weighs 2 tons instead of 1.

## Missile cost

A bank's native cost follows its weight alone (about 10 a ton), so a full
magazine was cheap. Every VLS cell now also costs its missile:

| Missile | Cost per cell |
| --- | ---: |
| Heavy SSM | 100 |
| Heavy SAM, medium SSM | 60 |
| Medium SAM | 40 |
| Light SSM | 30 |
| Light SAM | 25 |

A hundred heavy SAM cells add 6,000 to a ship, about doubling what the bank
cost before. The cost is part of the design's armament cost, so it shows in
the designer, in building cost and in upkeep, for existing designs too once
the game recalculates them. Conventional launchers are unchanged.

Cells sit below deck: each bank costs one topside point per 8 cells (64 cells
= 8 points). Conventional launchers keep their native weight and topside,
except medium SSM launchers: 4 t a missile (and reload) instead of 8, against
a heavy SSM's 10 (Harpoon-class canisters). A medium SSM hits like a 26-inch
shell, a heavy one like a 32-inch shell (about twice the damage), so a ton of
medium launchers now does about a third more damage than a ton of heavy ones,
at 80% of the range.

## Ship drawing

On the ship picture, in the designer and in battle, a VLS bank is drawn as
Mk 41-style 8-cell modules: a gray block with its cell lines, two cells across
and four along per module, at the scale of the native launcher drawings. 8
cells is one module (2.6 x 3.4 m), 16 two side by side, 32 a 2 x 2 block and
64 four across by two along; at 64 cells only module rows are lined. Side
banks run along the hull edge like Zumwalt's peripheral VLS: 16 cells are two
modules in a row, 32 four in a row and 64 a 2 x 4 block, lined by module. The bank
stays aligned with the hull, since cells do not train. Damaged banks draw black
like other mounts.

The selected mount becomes one bank containing that many missiles of its
existing type. Each cell holds one missile. Separate banks can carry different
SAM/SSM types, allowing a mixed ship loadout. Change an existing VLS bank's size
using the same menu. To return to a conventional launcher, delete the bank and
add a normal launcher again. The missile list labels these mounts as VLS cells.

## Battle behaviour

VLS banks have all-round launch coverage. Native targeting, automatic missile
decisions, spotting, missile ranges, minimum ranges, damage, defensive fire
control and combat results still apply. Heavy/medium SAM surface-fire abilities
keep their original research rules. Light SAM remains an air-defence weapon.

The cell count is loaded as ready ammunition at battle setup. Both anti-ship
salvos and SAM defensive bursts are bounded by the remaining cells. Empty banks
stay empty; no reserve missiles are loaded at sea. The native reload-edit
commands explain this and leave VLS banks unchanged. The explicit **Refill ship
ammo ALL** cheat can still refill surviving player banks for testing.

Both sides follow the same VLS rules. AI-controlled VLS ships can use the normal
missile and air-defence decisions.

## AI designs

New AI classes get VLS banks too. After AIDesignShip's second weight pass, each SAM
or SSM launcher on the design becomes a VLS bank when all of these hold:

- it is 1960 or later, and the bank size is researched;
- the mount is on the centreline, or the hull is 10,000 t or more, and its missile
  type is allowed;
- the cells fit the hull's cells per ton, counting the design's other banks.

The AI takes the smallest researched size that holds the launcher's whole load
(tubes x (1 + reloads)). If none does, it takes the largest researched size with
at least as many cells as tubes. A bank that would leave the design overweight
is undone. The designer's own AI design button uses the same routine, so it
applies to the player's auto-designs too. (Until 1.23 the nation also had to earn
more than it spent; that test is gone, the missiles' own cost is the brake.)

**Starting fleets.** The ships a 1980 or 2000 start hands out are raw design
templates that never pass through AIDesignShip, so they had no VLS. Each starting
class now gets the same pass when it is made (after the game's own post-1970
refit of the template), for every nation, the player's generated fleet included.

**Destroyers.** Every destroyer template is 3,800 t or less and the last template
era is the 1960s, so AI destroyers never grew. From 1975 a destroyer may grow for
its missiles, at the start and in new classes alike:

| From | A 3,800 t template may reach |
| --- | ---: |
| 1975 | 6,000 t |
| 1985 | 8,000 t |
| 2000 | 9,500 t |

Smaller templates grow in proportion. The hull never exceeds the nation's dock
size or the destroyer class limit (3,800 t without Historical and Paper Hulls, so
nothing grows without that mod; 16,000 t with it). On the larger hull the SAM
launchers take the largest researched bank that fits, SSM launchers keep the
whole-load rule, and the hull then shrinks in 100 t steps to what the cells (cells
per ton) and the weight need: about 5,800 t for 64 SAM and 8 SSM cells. A
destroyer with no missiles, no VLS research or an overweight template stays as it
was. In game this runs after AIDesignShip's own hull trim.

A destroyer whose hull stayed larger spends the weight it has left on speed
first, then on belt and deck armour, one knot or half inch at a time while it
fits, up to its era's limits:

| From | Speed up to | Belt and deck up to |
| --- | ---: | ---: |
| 1975 | 34 kn | 0.5 in |
| 1985 | 32 kn | 1 in |
| 2000 | 31 kn | 1.5 in |

A template that is already faster keeps its speed. A hull that can't make more
speed keeps the fastest speed the game accepts for it: the game itself lowers a
speed the hull can't reach (its "Illegal speed/displacement combination" rule),
and before 1.43.4 the fitting raised it again and again, which froze the turn.
Armoured destroyers need Historical and Paper Hulls, as the growth itself does.

**Other types.** The computer's largest templates are 88,000 t (BB), 70,000 t
(BC), 69,000 t (CV), 26,000 t (CA), 16,000 t (CVL) and 14,000 t (CL). From 1960 a
new BB, BC, CA, CL, CV or CVL class grows when its nation's economy carries it:

| Economy | Hull |
| --- | ---: |
| Earns more than it spends, a month of budget in cash | 120% of the design |
| Surplus of a tenth of its monthly budget, three months in cash | 140% |

The hull stays within the nation's dock size and the Historical and Paper Hulls
class limits (BB and BC 200,000 t, CV 150,000 t, CVL 45,000 t, CA 35,000 t, CL
25,000 t; these are that mod's defaults, and nothing grows without it). The
larger hull is spent in this order, a step at a time while it fits: the largest
SAM banks, on carriers up to 30% more aircraft, up to 2 knots more speed, then
belt and deck (BB 3 in, BC 2 in, CA 1.5 in, CL and CV 1 in, CVL 0.5 in more).
What is still unused is given back as hull, so a class is only as much larger as
its fit needs. The classes of a 1980 or 2000 starting fleet grow to 120%, whatever
the nation's funds: starting funds say nothing about its economy.

## Model and saved designs

This is an experimental extension of the existing missile-mount system. Each
bank has one native missile type. It does not implement a shared magazine with
arbitrary mixed cells, quad-packed SAMs, ASROC, land-attack missiles, new seeker
physics or modern radar-channel simulation.

Cell count, missile type and zero reserve reloads use the existing saved mount
fields. Battle saves keep remaining ammunition in the existing field. No extra
personal save file is created. Keep the VLS mod enabled when using these designs:
an unmodified game applies conventional launcher limits and arcs to their cells.
Installation does not convert existing ships or refit them for free. Use the
normal design/build/refit workflow to put a changed class into service.

## Validation

Tests run the retained native missile firing, automatic contact selection, SAM
defence, initial ammunition and per-mount validation instructions in isolation.
They cover last-cell ammunition bounds, both sides, damaged mounts, retained
range gates, conventional-launcher behaviour, class/research restrictions,
each size's research gate, the hull limit across all banks, cell weights with
each lighter-cell level, native weight and topside for launchers, the native
mount drawing with VLS cell grids and unchanged launcher shapes, the
native menu callbacks, field signatures, allocation bounds and relocated builds.
Native UI/geometry/logging boundaries are supplied by the test harness where
needed. These checks do not substitute for a complete live design/build/battle
or save/reload workflow.

The adapter installs at the title screen after Battle AI has audited the native
arc/firing code. Each changed site is checked and read back; unsupported code
stops installation. Closing RTW3 unloads the hooks. RTW3.exe and the separate
Steam installation are unchanged.
