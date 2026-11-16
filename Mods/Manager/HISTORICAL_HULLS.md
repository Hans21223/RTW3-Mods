# Historical and Paper Hulls

Select **Historical and Paper Hulls - 200,000t** in **RTW3 Mod Manager.exe**,
then choose **Play with mods**. Restart the game to load an updated adapter.
This replaces the earlier input-only Large Hulls mod under the same mod ID.
Change displacement once after opening a design to initialize the larger input
range. Use a separate testing campaign; full gameplay validation is outstanding.

## What changes

Version 0.3.4 fixes the **second** native battle-start fuel routine as well.
It had a separate 5,000-ton DD band and applied range/technology multipliers
after it. An oversized DD could retain an already scaled capacity, multiply
it by 1,000 again, then overflow the signed starting-fuel calculation. This
reproduces the observed **180,000,000 capacity with zero remaining fuel**.
Both initialization paths now cover the configured DD limit, with native
range, technology, starting percentage and raw-fuel inputs preserved.

Loaded oversized DDs with the matching inflated-capacity signature (35M..180M,
exactly divisible by 1,000) have capacity divided by 1,000. Plausible positive
remaining fuel is retained. A zero, negative or out-of-range overflow result
is restored to full once because the original value cannot be recovered.
Normal positive capacities, including genuinely empty tanks, are unchanged.
Fuel consumption remains native. Back up and reload the battle after a restart
through **Play with mods**; the old session cannot install this code update.

Version 0.3.3 also repairs **loaded** oversized DDs with invalid **0/0 fuel**.
Version 0.3.1 only fixed initialization; saved battle fuel values bypassed it.
Before the native maximum-speed, fuel-percentage or remaining-range query,
an alive, non-sinking DD above 5,000 tons and within the selected ceiling gets
its native fuel initialized if **both current fuel and capacity are zero**.
The old record contains no recoverable starting percentage, so recovery uses
100% once, with the native pre-1910 capacity reduction. Both sides follow the
same rule. A valid tank with zero remaining fuel is never refilled.

This removes the false no-fuel 5-knot maximum; damage can still reduce speed.
Existing current speed and orders are retained: increase the division's speed
if its saved order is still 5 knots. Restart through **Play with mods** to load
the new adapter. Recovery in the running battle persists when saved normally.

Version 0.3.2 fixes the separate **7,000-ton centreline torpedo-mount limit**
that could reject a 10,000-ton DD even when its hull/class checks passed.
For DDs only, the final mount limit now follows the configured DD ceiling
(16,000 tons by default, never below the native 7,000-ton mount allowance).
Other classes keep the original 7,000-ton limit. The earlier 2,500/3,500-ton
torpedo technology checks, AMC restrictions, mount types, fitted quantity and
all remaining design checks stay in effect. The native error message shows
the class-specific limits. Restart through **Play with mods**, reopen the
design and run the design check again; existing designs are not rewritten.

Version 0.3.1 extends the native destroyer fuel-capacity initializer through the
configured DD displacement limit. The original designer limit is 3,800 tons,
but the tactical fuel bands actually end at 5,000 tons. Larger DDs, such as a
7,000-ton design, skipped every band and began battles with **0/0 endurance**.
The final native DD band now continues through the selected class ceiling
(16,000 tons by default). Smaller DD capacity, other classes, pre-1910 reduction,
starting fuel percentage and fuel consumption remain native. This uses the
last existing DD capacity, rather than multiplying fuel by displacement.

The initializer continues to preserve the native starting fuel percentage
for new battles. Version 0.3.3 adds the separate loaded-record recovery above;
installing the adapter itself does not edit save files on disk.

Version 0.3.0 fixes the native visual-scaling cliff: several classes used their
small default factor again at **101,000 tons**, after working through 100,900.
Native visual sizes through 100,900 tons are preserved. Above that point,
class-specific size factors grow with the cube root of displacement, rounded
in 1,000-ton buckets, through the supported 280,000-ton setting range. This is
a continuation of the game's visual proportions, not a ship dimension calculator.

In the **Ship design** preview, three final drawing passes run in this order:

1. Added visuals (Graphics > Add visual, layers 1-6). They draw above every
   superstructure layer, the funnels and the torpedo mounts.
2. Missile mounts, including VLS banks.
3. Main guns, secondary turret and shield mounts, and tertiary guns.

So visuals sit above the superstructure and torpedoes but under missiles and
guns. Casemate guns are not redrawn: as in the game's own picture they sit under
superstructure layer 1. Positions, firing arcs, damage and combat rules do not change. The
battle visibility renderer is not patched by this drawing fix.

**Existing oversized designs:** saved hull points retain their old drawing;
the mod does not silently rewrite personal classes. To replace an old shrunken
outline, open the design, choose **Graphics**, right-click the **Equipment**
list, and choose **Reset hull outline (keep fitted weapons)**. The command is
enabled above 100,900 tons and rebuilds the class-default hull outline at the
current tonnage. **It replaces any custom hull outline.** Guns, mount positions,
equipment, superstructure and weights are retained; inspect their placement
afterwards. Changes remain in the current design until saved normally. The
reset is repeatable without repeatedly enlarging the same outline.

**Auto superstructure:** right-click the **Equipment** list and choose **Auto
superstructure (AI template)**. It draws a new superstructure (all 6 layers,
their colours and line settings, and funnels 1-4) from the game's own AI design
template (`Data/IDes`) of the same ship type that is closest in year (the
campaign year, else the design's build year; 4 points per year) and size (1
point per percent of displacement), scaled to the design's hull length. If no
hull is drawn yet it first draws the class-default outline. The hull outline,
guns, equipment and visuals stay, so it also redraws a ship for a refit; move or
resize the superstructure afterwards if it covers a turret. **It replaces the
current superstructure and funnels.** Frigates use corvette templates; carriers
(CV, CVL) and submarines have none, so the item is greyed out for them. The
templates are read from the player's own game files at launch (cached in
`Mods/CampaignOverhaul/superstructure_templates.bin`); nothing from the game is
shipped with the mod.

Native code emulation checks the original size curve, the 101,000-ton failure,
extended monotonic growth, outline rebuilding, drawing order, menu behavior,
register/stack preservation and relocated builds. Actual in-game visual testing
remains separate; no campaign is loaded, advanced or saved by these checks.

| Ship class | New displacement allowance |
| --- | ---: |
| DD | 16,000 tons (Zumwalt is about 15,900 tons full load), still requiring the native highest DD hull technology for the largest sizes |
| CL, including protected cruisers | 25,000 tons (the CG(X) cruiser studies); old 8,000/10,000/12,000-ton class ceilings lifted |
| CA | 35,000 tons (Alaska: 29,800 tons standard, 34,300 full load); native designer ceiling 26,000 tons. A ship you select as CA stays a CA with main guns up to 12 inches and a belt up to 10 inches (Alaska: 12-inch guns, 9-inch belt); natively, 11-inch guns, an 8-inch belt or 20,000+ tons turned it into a BC or BB |
| KE | 8,000 tons (Type 26 frigate class); no torpedoes before 1950, then torpedoes allowed (ASW tubes on modern corvettes and frigates) |
| AV | No designer ceiling (native 14,000 tons) |
| CVL | 45,000 tons (America-class LHA) and up to 80 aircraft |
| Gun mounts on every type | Centreline and superimposed (B, X, V) mounts and double, triple or quadruple turrets on any type, KE included (hybrid carriers such as Ise or Kiev); the turret research still applies |
| DD and KE dual purpose main guns | Any calibre (native 5 inches; Zumwalt carries 155 mm); the dual purpose research is still needed |
| CV | 150,000 tons in the designer; carrier inventions still required |
| BB, BC, CA and overall input/calculation ceiling | 200,000 tons, subject to their remaining native rules |

These are generous **mod allowances**, not claims that every historical ship
class had exactly these limits. No new restrictive CA/BB/BC cap is introduced.
The designer respects your explicitly selected class in the expanded range;
the AI's automatic class-suggestion calls are unchanged.

Dock size, treaties, carrier inventions, gun availability, the class
definitions (minimum speed and armament, armour classification) and component
weights remain enforced. A larger displacement does not guarantee an exact
replica will satisfy every other rule. Use the cheat menu to enlarge the dock if
needed; this mod does not silently grant a larger shipyard.

## Freed design rules

Rules that only forbid a combination for a ship type or size no longer make a
design illegal; weight, cost, stability, topside load and the design report's
notes already price those choices. The design report no longer lists them:

- carriers: CV and CVL minimum aircraft, speed and size errors, the CVL 34
  aircraft and 16,000-ton errors, aluminium superstructure, the protected cruiser
  armour scheme, and the AV 14,000-ton ceiling (heavy SAMs on carriers are freed
  by VLS Cells, which owns that code);
- type limits: unit machinery and TPS on AMC and KE, KE above 24 knots, armoured
  destroyers, AMC speed, size and dual purpose main guns, CA above 26,000 tons,
  catapults on DD and KE, dual purpose main guns of any calibre on DD and KE,
  secondary directors below CA, triple secondary turrets outside BB and BC (the
  triple-turret research still applies to every type), and the armour deck that
  BB, BC and CA had to carry;
- ASW and mines: depth charge, depth charge thrower, ASW mortar and minesweeping
  gear on any type and size, mines on any type and over the displacement
  allowance;
- armament and armour: narrow-hull limits on fast ships with triple or quadruple
  end turrets, secondary and tertiary gun totals for displacement, the pre-1943
  design board's 8 x 8-inch and 8 x 6-inch demand, all-or-nothing and protected
  cruiser belt combinations, the cross-deck fire secondary limit, long range with
  low freeboard or cramped quarters, colonial service limits, heavy and medium SAM
  minimum displacement, unarmoured ships above 6-inch guns, the 10 heavy and 12
  medium-or-heavy turret limits, and the turret rules for protected cruisers,
  wing positions and CL double turrets over 6 inches;
- turrets and mounts, as each turret is placed and in the report: centreline and
  superimposed mounts by type, single turrets only on AMC and KE, no triple or
  quadruple mounts on AMC, DD and KE, no triple DD or quadruple CL turrets, the
  protected cruiser 2-centreline-turret limit, casemates below 1,200 tons or over
  10 inches, double wing turrets on hulls under 10,000 or 15,000 tons, single
  turrets in positions 1-4 under 14,000 tons, twin 5-inch DP below 1,800 tons;
  dual purpose triple and quadruple mounts now need the twin DP research for
  their calibre instead of being refused (the AI's own designs keep the native
  DP test);
- armour: belt ends or upper belt thicker than the belt, deck ends thicker than
  the deck, a deck thicker than the belt, armoured guns without a belt;
- balance: unbalanced (asymmetric) turrets, torpedo mounts, launchers and
  catapults;
- catapults: any type may carry them in any number (natively none on DD and KE,
  one on CLs under 8,000 tons, two on most types, four on angled-deck carriers);
  the catapult research still applies, and carriers still need Angled flight deck
  research for more than two flight deck catapults;
- unused displacement above 5%.

Still errors: research and inventions (including gun calibres and qualities,
fire control, catapults, turret types, centreline turret counts, wing turrets
and SAM/SSM launchers), treaties, dock size,
oil access, names, builders, displacement steps, impossible speed for the
displacement, negative cost, serious overweight, dangerously top heavy,
secondary and tertiary guns larger than the battery above them, tertiary guns
over 6 inches, 20 main guns and 16 gun mounts, three missile types, the flight
deck, hangar, catapult and helipad combinations (only CV and CVL may have a
flight deck), half-inch armour, extra deck armour without a deck, A/B with 1-2
and X/Y with 3-4 turret positions, submerged and side torpedo tube counts, refit
rules, and the class definitions that decide a design's type. Only the
designer's own checks change; the AI designs ships with the native rules.
Tests check every freed block against the retained native code
(`test_design_rules.py`): each patch skips only its own error, behind the jump
the game itself takes when the rule is met.

BB and BC hulls with a flight deck and aircraft act as **BBV hybrids** (air
operations as a carrier, battleship tactics); see "BBV hybrids" in
`MODERN_TECH_TREE.md` (part of the Expanded Timeline package).

## Research: actual ships and paper studies

| Benchmark | Displacement and source basis | What it checks |
| --- | --- | --- |
| [Worcester CL-144](https://www.history.navy.mil/research/histories/ship-histories/danfs/w/worcester-ii.html) | 14,700 tons; DANFS does not state load basis in this entry | A real light cruiser above the native 12,000-ton cap |
| [Des Moines CA-134](https://www.history.navy.mil/content/history/nhhc/research/histories/ship-histories/danfs/d/des-moines-ii.html) | 17,000 tons; load basis not stated in this entry | Heavy-cruiser reference point |
| [Saipan CVL-48](https://www.history.navy.mil/research/histories/ship-histories/danfs/s/saipan-i.html) | 14,500 tons, 50+ aircraft; load basis not stated in this entry | A real light carrier exceeding the native 34-aircraft limit |
| [Montana class](https://www.history.navy.mil/our-collections/photography/us-navy-ships/battleships/montana-class-bb-67-71.html) | 60,500 standard; 70,965 full load | Cancelled battleship design; tests use the standard figure |
| [Tillman design #4, S-584-110](https://www.shipscribe.com/styles/S-584/images/s-file/s584110c.htm) | 80,000 **normal** displacement | Unbuilt maximum-battleship study, not an invented production ship |
| [United States CVA-58](https://history.defense.gov/Portals/70/Documents/acquisition_pub/OSDHO-Acquisition-Series-Vol1.pdf) | 65,000 standard; printed page 354 | Cancelled carrier design and the designer carrier-size ceiling |

Source figures keep their original load basis; standard, normal and full load
are not interchangeable. The Tillman normal figure is a stress-test point,
not a claim that its standard displacement was 80,000 tons. Machine-readable
references are in `Mods/CampaignOverhaul/historical_hulls.json`.
These are benchmarks, not included ship-design files or an exhaustive catalogue.

## Machinery above 90,000 tons

The native machinery lookup ends at 90,000 tons. Merely increasing the input
or removing its guard would read outside that table. This adapter allocates a
larger table in memory and redirects only the verified calculation references.
Native rows through 90,000 tons are preserved byte-for-byte.

For larger hulls, each supported speed column is estimated from the 90,000-ton
row as `HP(D) = HP(90000) * (D / 90000)^(2/3)`. Native interpolation and subsequent
machinery modifiers still run. Unsupported speed combinations stay unsupported
(the native largest-hull row does not support speeds above 33 knots).
This is a disclosed extrapolation, **not an empirically calibrated realism
overhaul** or a guarantee of historically correct machinery/ship weight.

## Verification and recovery

Automated tests emulate the actual native class-gate and machinery instructions.
They reproduce the original Worcester/Saipan rejections and the expanded gates'
acceptance, check upper boundaries and retained minimum rules, and compare native
machinery results through 90,000 tons. Additional tests cover the designer-only
class-suggestion hook, including its ordinary-class fallback and registers.
These checks are not a complete-design build, battle or campaign test.

The centreline torpedo correction is tested by executing the complete native
per-mount validator in isolation: both P and V pass at 10,000 tons on a DD
and fail above the configured limit. Native position predicates and technology
gates execute; Delphi string handling and nation research ownership are supplied
by the test harness. Other classes, earlier technology checks, empty mounts and
non-centreline mounts retain their original verdicts. Allocation bounds,
register/stack preservation and relocated builds are checked separately.

Live attachment, repeated attachment, detach and reattachment are checked against
the normally authenticated local game. Each instruction is signature-checked and
read back. Unsupported builds stop instead of applying guessed offsets.
The executable and source Steam installation are not edited. Closing RTW3 removes
all runtime changes. Keep the mod enabled when reopening oversized designs;
the unmodified game may reject them. Tests do not edit personal campaigns.
