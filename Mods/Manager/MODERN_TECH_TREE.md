# Modern Research Through 2030

This experimental package adds **104 researchable technologies** in the game's
original **Research** screen: 83 appended to 21 existing branches (1980-2030)
and 21 in two new branches that use the game's two reserved branch slots
(1965-2030). It is not another manager-only designer or a list of cosmetic
weapon renames.

Enable **Expanded Timeline - Modern Research to 2030, Campaign to 2050** (which now also contains the 2030-2050 calendar and VLS
cells), then use **Play with mods**.
The manager installs the research table with a backup; the reviewed runtime
adapter supplies the additional effects at startup. Restart before loading a
campaign. Existing original technologies are neither moved nor replaced.

## Progression and effects

Every new technology has a native prerequisite: the first extends the branch's
last original technology, and later entries require the preceding new entry.
Year, research cost, priority, budget and breakthrough processing remain native.
Costs increase from 20 native cost units for a branch's first new entry to as
many as 40 for its sixth entry. Native date variation and national research
differences remain; these are availability targets, not guaranteed completion dates.
All 2030 entries are explicitly labelled **projected**.

| Existing research branch | Added | Total slots used |
| --- | ---: | ---: |
| Machinery development | 4 | 36 / 36 |
| Armour development | 4 | 32 / 36 |
| Hull construction | 4 | 31 / 36 |
| Fire control | 4 | 36 / 36 |
| Subdivision and damage control | 4 | 28 / 36 |
| Turrets and gun mountings | 4 | 33 / 36 |
| Ship design | 2 | 36 / 36 |
| AP projectiles | 4 | 31 / 36 |
| Light forces and torpedo warfare | 2 | 36 / 36 |
| Torpedo technology | 2 | 36 / 36 |
| Submarines | 3 | 34 / 36 |
| Anti-submarine warfare | 5 | 28 / 36 |
| Explosive shells | 4 | 30 / 36 |
| Fleet tactics | 3 | 36 / 36 |
| Anti-aircraft artillery | 4 | 33 / 36 |
| Radar and electronics | 6 | 30 / 36 |
| Naval aviation, lighter than air | 0 | 8 / 36 |
| Naval aviation, heavier than air | 3 | 32 / 36 |
| Shipboard aircraft operation | 5 | 30 / 36 |
| Missile technology | 6 | 32 / 36 |
| Amphibious operations | 4 | 13 / 36 |
| Missile countermeasures | 6 | 14 / 36 |
| **Vertical launch systems** (new, 22) | 10 | 10 / 36 |
| **Naval combat systems** (new, 23) | 11 | 11 / 36 |

Gun manufacture, which the game generates after the ordinary branches, moves
from slot 22 to 24.

Lighter-than-air research stays a historical dead end. Its spare slots are not
filled with fictional modern airship improvements merely to make every branch longer.

Machinery, armour, hull, fire control, AP, ASW, carrier and amphibious entries
advance the original national research-level calculations. Other new entries
contribute to ten reviewed native integer results:

| Native result | Maximum extra points with all relevant research |
| --- | ---: |
| Gun rate-of-fire modifier | 5 |
| Damage-control modifier | 6 |
| SAM quality | 10 |
| SSM quality | 10 |
| Anti-missile countermeasure quality | 10 |
| Airborne ECM quality | 3 |
| Submarine attack-accuracy modifier | 5 |
| Light AA quality | 4 |
| Medium AA quality | 4 |
| Heavy AA quality | 5 |

No result gains more than 10 points. SSM quality adds native missile range, so
the new Naval combat systems branch improves guns, AA and damage control
instead of adding more missile quality.

These are **native modifier points, not percentage-point changes to hit chance**.
The research entry describes the actual result it affects. Native ranges,
mounts, equipment requirements, ammunition, firing checks and final combat
resolution remain in effect. Airborne ECM still requires the native support
aircraft. Submarine accuracy is calculated when native boats are created;
existing campaign boats are not rewritten. New battle data uses the nation's
current researched results; already-running battles are not retroactively rebuilt.

For example, phased-array combat-system integration adds a SAM-quality point.
It does not create a new selectable radar class or reproduce a complete Aegis
simulation. Countermeasure technologies improve the native defensive modifier;
they are not invisibility or an implemented radar-cross-section model.

The same calculations read **the owning nation's** completed technologies for
player and AI. There are no player-only free unlocks, AI grants or automated
personal-save edits in this package.

## New branches

**Vertical launch systems (22)** unlocks and improves banks in the VLS Cells mod
(see [VLS_CELLS.md](VLS_CELLS.md)); without that mod only 2207 has an effect.

| ID | Year | Technology | Effect |
| ---: | ---: | --- | --- |
| 2347 | 1953 | Aerial refuelling (needs 1728 Improved jet engines) | Land-based aircraft +50% range (see Tankers) |
| 2341 | 1965 | Anti-radiation missiles (needs 1907 Early air to surface missiles) | Jet strike aircraft suppress SAMs (see Electronic warfare and SEAD) |
| 2342 | 1967 | Self-protection jamming pods (needs 1523 Improved ECM systems) | Strike aircraft jam SAMs (see Electronic warfare and SEAD) |
| 2338 | 1969 | Vertical take-off jet fighters (needs 1823 Steam catapults) | Light jet fighters are VTOL (see Ski jump) |
| 2201 | 1974 | Vertical launch cells (needs 1919 Improved launcher technology) | 8-cell VLS banks |
| 2202 | 1977 | Modular VLS magazines | 16-cell banks |
| 2203 | 1980 | Canister exhaust management | 32-cell banks |
| 2204 | 1983 | Large VLS magazines | 64-cell banks |
| 2343 | 1984 | High-speed anti-radiation missiles (needs 2341) | Jet strike aircraft suppress SAMs more (see Electronic warfare and SEAD) |
| 2344 | 1985 | Hybrid diesel-electric propulsion (needs 17 Turbo electric drive) | Diesel ships spare power for railguns and lasers; quiet electric drive +2 ASW (see Railguns, Anti-submarine weapons) |
| 2205 | 1986 | Lightweight composite launch cells | Cells 20% lighter |
| 2206 | 1988 | Hull-integrated VLS modules | 1 cell per 64 t instead of 80 t |
| 2349 | 1989 | Gun-missile close-in weapon systems (needs 2107 Improved close in defence weapons) | Gun-missile CIWS mounts (see Point defence) |
| 2207 | 1990 | Universal VLS fire control | SSM quality +1 |
| 2350 | 1991 | Rolling airframe missiles (needs 1925 Improved Light SAM) | RAM launchers tick box (see Point defence) |
| 2208 | 1992 | Compact self-defence VLS modules | Cells another 10% lighter |
| 2211 | 1993 | Vertical-launch ASW rockets | Ships with a VLS bank +2 ASW value (see Anti-submarine weapons) |
| 2209 | 2005 | Peripheral VLS integration | 1 cell per 51 t |
| 2353 | 2013 | Anti-torpedo torpedoes (needs 1119 Improved ASW torpedoes) | ATT launchers (see Undersea warfare) |
| 2351 | 2008 | SeaRAM self-contained launchers (needs 2350) | SeaRAM mounts (see Point defence) |
| 2352 | 2016 | Enlarged point-defence magazines (needs 2349) | SeaRAM and gun-missile mounts carry 50% more missiles |
| 2339 | 2017 | Low-observable anti-ship missiles (needs 1917 Effective cruise missiles) | Stealthy SSMs (see Hypersonic missiles) |
| 2340 | 2025 | Hypersonic interceptors (needs 2208) | SAMs better against hypersonic missiles (see Hypersonic missiles) |
| 2348 | 2027 | Unmanned carrier tankers (needs 2347) | A carrier with its special squadron: its aircraft +30% range (see Tankers) |
| 2346 | 2026 | Hypervelocity anti-air projectiles (needs 2340) | Railgun main batteries of any calibre count as heavy AA, from three times as far, two aircraft a hit (see Railguns) |
| 2210 | 2030 | Next-generation VLS modules [projected] | Cells another 10% lighter |

**Naval combat systems (23)**

| ID | Year | Technology | Effect |
| ---: | ---: | --- | --- |
| 2334 | 1958 | Nuclear gun projectiles (needs 1222 Large HEAT warheads) | Nuclear shells (see below) |
| 2301 | 1965 | Naval tactical data processing (needs 1524 Tactical data system) | Heavy AA +1 |
| 2331 | 1966 | Lightweight ASW torpedo tubes (needs 1119 Improved ASW torpedoes) | Torpedo mounts +2 ASW value (see Anti-submarine weapons) |
| 2302 | 1967 | Automated threat evaluation | Light AA +1 |
| 2303 | 1969 | Integrated combat direction system | Medium AA +1 |
| 2304 | 1972 | Electronic support measures suite | ESM hears enemy radars at 3x their range (see Range and over-the-horizon targeting), Light AA +1 |
| 2305 | 1975 | Phased-array fire control radar | Heavy AA +1 |
| 2323 | 1976 | Ocean surveillance satellites | Satellite fixes beyond radar range (see Range and over-the-horizon targeting) |
| 2319 | 1977 | Wake-homing and wire-guided torpedoes (needs 822 Modern torpedo control systems) | Guided torpedoes (see below) |
| 2324 | 1978 | Turbofan anti-ship missiles (needs 1917 Effective cruise missiles) | SSM range +50% |
| 2306 | 1979 | Integrated damage-control systems | Damage control +1 |
| 2325 | 1980 | Extended-range SAMs | Medium and heavy SAM range x2 |
| 2307 | 1996 | Cooperative engagement capability | Medium and heavy AA +1 |
| 2308 | 1987 | Radar cross-section reduction | Ships designed from 1990: enemy radar range -20%; jets developed from 1990 are stealth models |
| 2332 | 1995 | Composite superstructures | Composite instead of aluminium (see below) |
| 2309 | 2000 | Ship self-defence system integration | Light AA +1 |
| 2318 | 1998 | Active electronically scanned array radar | AESA radar (see below) |
| 2326 | 2005 | Shipborne UAVs | UAV models beside floatplane scouts (see below) |
| 2320 | 2012 | Guided gun projectiles | Guided shells (see below) |
| 2327 | 2013 | Long-range anti-ship missiles | SSM range another +50% |
| 2328 | 2014 | Active-seeker long-range SAMs | Medium and heavy SAM range another +50% |
| 2310 | 2008 | Low-observable ship design | Ships designed from 2015: enemy radar range another -20% |
| 2313 | 2003 | Integrated power system | Gas turbine ships spare 50% of horsepower as railgun power (was 25%); extra generators in the designer |
| 2321 | 2009 | Electromagnetic aircraft launch system (needs 1823 Steam catapults) | EMALS (see below) |
| 2312 | 2020 | Electromagnetic railgun (needs 2313) | Railgun main batteries (see below) |
| 2345 | 2021 | Interceptor drone swarms (needs 2326) | Ships with helicopters, catapults or a flight deck: +15% to stop incoming missiles, +4 heavy AA; carriers count as having an AEW squadron (see Interceptor drones) |
| 2316 | 2022 | Shipboard high-energy lasers (needs 2313) | Laser mounts (see below) |
| 2317 | 2023 | Hypersonic anti-ship missiles (needs 1917 Effective cruise missiles) | Hypersonic SSMs option (see below) |
| 2333 | 2024 | Explosive unmanned surface vessels | MTB squadrons become USVs (see below) |
| 2314 | 2025 | Compact pulsed-power storage | Railguns need 25% less power; mounts +25% instead of +50% |
| 2322 | 2026 | Guided heavy-calibre projectiles [projected] (needs 2320) | Guns over 6 inches hit 1.5 times as often (see Guided shells) |
| 2329 | 2027 | Railgun secondary batteries [projected] | Railgun secondaries and tertiaries (see Railguns) |
| 2315 | 2028 | Superconducting pulsed power [projected] | Railguns need another 25% less power; mounts only +10% |
| 2330 | 2029 | Railgun point defence [projected] | DP railguns shoot at incoming missiles (see Railguns) |
| 2311 | 2030 | Adaptive combat-system automation [projected] | Damage control +1, rate of fire +1 |

These replace the separate Research Expansion package, merged here on
4 November 2026 with the same IDs and slots. On 6 November 2026 four technologies
(2318-2321) were inserted in year order, which moves the later entries' slots;
campaigns saved before then lose those entries' progress (accepted: the
campaign they were made for is finished). On 21 November 2026 2345 (2021) and
2346 (2026) were inserted the same way: a campaign that has researched the
later entries of those two branches (2316-2311, and 2210) has their progress
shifted by one. The same day 2347 (1953) and 2348 (2027) joined the Vertical
launch systems branch: there every entry from 1957 on moves one row, so a
campaign past 1953 sees that branch's progress shifted (decided 2026-11-21).
Its Naval combat systems entries 2301-2307 gave SAM, SSM and anti-missile
points; here they give the AA, rate-of-fire and damage-control points above.

## Aegis radar and ship stealth

**Search radar 6, "Phased-array search (Aegis)".** The game's search radar
class (1-5) is a count of five radar technologies: 1501, 1502, 1506, 1511 and
1512. A nation that has all five plus Phased-array combat-system integration
(1540, 1983, Radar and electronics branch) reaches class 6. The designer
already allows **Radar limit 6** (200 t); set it to 6 to fit the radar, and
refits upgrade ships whose radar limit allows it. Radar limit 6 needs a hull laid
down from 1975, as older hulls lacked the power, cooling and topside structure; the
designer keeps such a hull at 5 and says why. New classes count as new hulls.

| Search radar | Battle detection range | Detection chance | Sighting range |
| --- | --- | --- | --- |
| 5, Very advanced search | 38,000 yd | 42% | 35,000 yd |
| 6, Phased-array search (Aegis) | 40,000 yd | 55% | 38,000 yd |

Native rules add 5% range after 1958. The radar horizon still limits surface
detection, so the range gain is small; the gain is in reliability. The game also
uses the radar class in other formulas: the per-check detection roll (40% +
5% per class, so 70%), the SAM-versus-missile intercept roll, CAP and fatigue.
Class 6 improves all of these.

**Ship stealth.** Radar cross-section reduction (2308, 1990) and Low-observable
ship design (2310, 2015), in Naval combat systems, cut the radar range at which
enemy ships detect yours by 20% each (64% with both). A ship qualifies when it
was designed in or after that year (its design year) and its nation has the
technology. Older ships are not retrofitted. Visual detection is unchanged.

**Stealth aircraft.** With Radar cross-section reduction, every light jet
fighter, heavy jet fighter or jet attack prototype the nation develops from 1990
on is a stealth model. It is a separate model, built from its own rows in
`AircraftBasicData3.dat`: STEALTH LIGHT JET FIGHTER, STEALTH HEAVY JET FIGHTER and
STEALTH JET ATTACK, 1990-2030. Compared with the normal jet of the same year it
has 95% of the top speed and 75% of the bomb loads (internal bays), +2
firepower (first look) and +1 toughness. It keeps the jet's role, so carriers,
missions, development requests and the AI use it like any other jet. Its
name reads like any jet's: the game renames prototypes and new types, so the
stealth mark is kept in a saved field of the aircraft type that the game
itself never uses (CruiseAltitude).

In battle, the defending fleet's radar-based CAP interception range against a
stealth formation is 35% shorter, and the radar bonus a defending ship adds to
its AA against a stealth attacker is halved. Older jets stay normal models;
develop new ones to get stealth.

**Unmanned strike aircraft.** With **Shipborne UAVs** as well, a jet attack
model developed from 2020 is an unmanned stealth aircraft (X-47B, MQ-25
class). It uses its own rows, UNMANNED JET ATTACK
2020-2030: the stealth jet attack with half as much endurance again and 80%
of its manoeuvrability. It keeps every stealth effect. Fighters stay manned.

These are native-code hooks in the battle detection routine, the radar class
count, the radar range, sighting-range and name tables, aircraft prototype
creation and its data lookup, CAP interception and AA strength.

## Aircraft after 1970

The game builds each new aircraft prototype from `Data/AircraftBasicData3.dat`:
the row for that type and year, or the year before. Vanilla rows stop in 1970,
and later years reuse the 1970 row plus 1%, so aircraft stopped improving. This
package installs the table with a row every two years to 2030 for light and
heavy jet fighters, jet attack aircraft, helicopters and medium bombers. Values
are interpolated between historical anchors, for example:

| Type | 1970 | 1990 | 2030 |
| --- | --- | --- | --- |
| Light jet fighter (F-16, F/A-18 class) | 1,188 mph, 170 min, firepower 18, agility 15 | 1,300 mph, 200 min, 24, 21 | 1,320 mph, 230 min, 30, 24 |
| Heavy jet fighter (F-14, F-15, F-22 class) | 1,360 mph, 212 min, 18, 13 | 1,500 mph, 250 min, 26, 19 | 1,500 mph, 280 min, 32, 22 |
| Jet attack (A-7 to F/A-18E, F-35C) | 748 mph, bombs 9/18/36 | 1,000 mph, 11/22/42 | 1,200 mph, 13/26/48 |
| Helicopter (SH-3 to SH-60, NH90) | 162 mph, 300 min | 182 mph, 307 min | 200 mph, 320 min |
| Medium bomber (Tu-22M class) | 565 mph, 720 min | 1,100 mph, 740 min | 1,150 mph, 780 min |

Endurance is the light-load value; medium and heavy loads rise with it, as do
toughness and the other two bomb loads. Columns whose meaning was not traced
(including the loadout columns after radar) repeat the 1970 values. Existing
aircraft keep their stats; only prototypes developed after 1970 use the new rows.
Naval patrol aircraft, whose vanilla rows stop in 1950, are unchanged.

## Nuclear propulsion

**Naval nuclear propulsion** (ID 40, 1961) is the first added Machinery
technology and follows Gas turbines (1960). It adds **Nuclear** to the ship
designer's propulsion list. Choosing it without the research shows a message and
sets the design back to Oil + Turbine. A nuclear design:

- has 60% heavier machinery that costs three times as much (reactor, shielding
  and steam plant), only 30% heavier once the designing nation has Thorium
  molten-salt naval reactors (43, 2030, projected): the molten-salt loop runs
  near atmospheric pressure, so no heavy pressure vessel. Thorium reactors are
  real but not yet naval: Oak Ridge's molten-salt reactor ran on thorium-bred
  uranium-233 in 1968-69, and China's TMSR-LF1 test reactor went critical in
  2023. The designer applies it whenever it recalculates a design, using the
  research of the nation in the designer; built ships keep their weights;
- carries the same fuel weight at every range setting: 70% of the Medium figure,
  less than an oil-fired ship at Short range. The designer greys out the Range
  box for a nuclear design, and enables it again when another propulsion is
  chosen (unless the design is locked, as for a refit);
- always reports 100% fuel and burns none in battle, so it is never slowed to
  5 knots "at minimum fuel level" however fast it steams; and
- is not affected by oil supply shortages, the rule the game already applies to
  coal-fired ships.

These are native-code hooks in the designer's
FormShow and propulsion change handler, the machinery weight and cost
calculation, the range weight factor, the oil-shortage check, the fuel
percentage and the battle fuel turn.

## Railguns

**Electromagnetic railgun** (ID 2312, 2020, after Low-observable ship design,
the Zumwalt link) adds a **Railgun** checkbox to the main-gun panel, right of DP.
It turns the whole main battery, any calibre, into railguns. A **Power** readout
beside the hull data shows MW needed / MW spare:

- needed: 16 MW per 5-inch railgun (the US Navy's 32 MJ gun at about 10 rounds
  a minute with pulsed-power losses), growing with calibre squared, so a 16-inch
  railgun needs about 164 MW; Compact pulsed-power storage (2025) and
  Superconducting pulsed power (2028, projected) each cut this by 25%;
- spare: with Nuclear propulsion all of the ship's horsepower in MW (reactors run
  at full output indefinitely, and nuclear ships carry big generating plants:
  Ford has about three times Nimitz's), rising with the later Machinery
  technologies, renamed for reactor generations (same IDs, years and machinery
  effect): Life-of-ship reactor cores (41, 1995) 125%, Third-generation naval
  reactors (42, 2010) 150%, Thorium molten-salt naval reactors (43, 2030,
  projected) 200%.
  With Gas turbine a quarter (generators sized to propulsion: Zumwalt could feed
  about one railgun), half with Integrated power system (2003). Diesel ships
  spare the same once their nation has **Hybrid diesel-electric propulsion**
  (ID 2344, 1985, CODLAG: diesel generators feed electric motors), and may then
  mount railguns; other plants spare nothing.

Ticking the box without the research, without electric drive or without enough
power shows why and leaves it unticked. Later changes that break the rule make
the design illegal, listed in the design report.

A railgun battery:

- reaches twice the native maximum range;
- penetrates armour like a gun 4 inches larger at half the range (hypervelocity
  rounds keep their speed); past the game's 20-inch penetration tables (16-inch
  railguns and up) the 20-inch value grows with calibre, so every size gains;
- with DP ticked, counts 1.5 times in the heavy AA factor (three times shorter
  flight time outweighs about half the rate of fire); with Hypervelocity
  anti-air projectiles it counts as heavy AA at any calibre, DP or not (below);
- fires inert rounds: a railgun ship's main magazines and turrets never flash or
  explode, including diving-shell magazine hits; secondary magazines keep the
  native rules;
- weighs 50% more per mount (25% with Compact pulsed-power storage, 10% with
  Superconducting pulsed power: lighter energy storage) and costs 2.5 times as
  much (pulsed power and rails), and its ammunition weighs half (no propellant).

**Railgun secondary batteries** (ID 2329, 2027, projected) adds **Railgun
secondaries** and **Railgun tertiaries** tick boxes at the bottom left of
Additional armament. Those batteries become railguns in battle: twice the range
and the railgun penetration. Each gun needs power like a main-battery railgun of
its calibre, plus 1 t and 50 cost of pulsed-power storage per MW, and the plant
or the extra generators must supply it (the design report lists missing power
and research). Any propulsion works if the generators cover it. Their magazines
keep the native rules, and the heavy AA bonus stays main-battery only.

The Power readout counts what is actually railgun, plus lasers: a conventional
main battery no longer counts, so a laser-armed ship with ordinary guns is no
longer reported short of power. Ticking Railgun still checks that the main
battery would fit.

**Railgun point defence** (ID 2330, 2029, projected): after the laser layer and
before CIWS, each DP railgun battery (main, secondary or tertiary) gives 20% to
shoot an incoming missile down with hypervelocity rounds, at most 50%, and a
third of that against hypersonic missiles. The log reads "Incoming missile shot
down by railgun."

**Hypervelocity anti-air projectiles** (ID 2346, 2026, after Hypersonic
interceptors; the HVP round developed for 5-inch guns and railguns). The game
counts only 3- to 6-inch guns as heavy AA, and a main battery only when it is
DP, which bigger guns cannot be. With this research a railgun main battery of
any calibre, DP or not, fires air-burst hypervelocity rounds at aircraft
(`modern_air_defence.py`):

- **Value:** each railgun counts 20 heavy AA (a 5-inch DP gun counts 9 to 12),
  or its native value if that is higher. The designer, the ship screens and
  battles all show it; a ship's heavy AA still grows more slowly past 40.
- **Range:** heavy AA fires at an incoming air strike in the long-range phase,
  before it attacks, from every ship near the target within its heavy AA range
  (about 5,000-6,000 yards; full rate within half of it). A hypervelocity ship's
  range is three times that, so it covers the other ships of its group.
- **Spread:** the phase pools the shots of all ships and rolls each. The shots
  of hypervelocity ships are counted apart, and a hit is theirs with their
  share: it destroys or damages two aircraft instead of one, and the attack
  loses both.

Ticking Railgun also ticks Increased elevation
(railguns fire high-angle for range; unticking Increased elevation removes the
railgun). Refitting an existing class to railguns counts as a gun change.
Computer nations do not design railgun ships.

In battle the log says "railguns" for a railgun main battery ("fires 2 6in
railguns at ..."), for your ships and for enemy ships seen firing. The three ship
information screens add **(EML)** (electromagnetic launcher) after the main gun
line, for example "14 - 6 inch. (DP) (EML)"; "(R)" already marks radar-guided
medium AA there.

The setting is stored as value 2 in the main battery's Increased elevation flag,
which the game treats as true everywhere. Campaign saves and design files write
that flag as a number instead of 1/0, so the railgun survives saving; files
without railguns are unchanged. Without this mod a railgun ship loads without
railguns or increased elevation.

## Range and over-the-horizon targeting

The game's missile ranges come from a 1950s-60s formula: heavy SSMs reach 25,000
yards plus 5,000 per range level, times 1.6 and 1.2 after 1960 (about 20-50 nm),
SAMs about 26,000-31,000 yards. Search radar sees surface ships out to about
15,000 + 4,000 yards per radar class (Aegis: 39,000 yards, the radar horizon).
Four research steps stretch missiles toward modern figures:

| Research | Year | Effect |
| --- | --- | --- |
| Turbofan anti-ship missiles (Harpoon, Exocet MM40) | 1978 | SSM range +50% |
| Long-range anti-ship missiles (NSM, LRASM) | 2013 | SSM range another +50% |
| Extended-range SAMs (SM-2ER, S-300F) | 1981 | Medium and heavy SAM range x2 |
| Active-seeker long-range SAMs (SM-6) | 2014 | Medium and heavy SAM range another +50% |

They apply wherever the game asks for a missile range: firing, the AI, missile
flight and the battle screen. (The Missile ranges table button still shows the
native figures.)

Battles also start further apart. The battle set-up moves each force back
until it is a minimum distance from the scenario's reference point (natively
30,000 yards for a close start, 50,000 medium and 90,000 long, less before
1938). From 1960 that minimum is one and a half times as far, from 1972 three
times, up to 130,000 yards, so missile-era forces start beyond each other's
radar and beyond what ESM hears (forces on opposite sides start up to 260,000
yards apart; an AESA radar is heard to 129,000), and whoever finds the enemy
first can fire first. Land and enemy bases still stop the move, and the game's
"forces are far apart" question still comes only after half the scenario time,
beyond 280,000 yards.

Strikes aim at a location, not a ship, so a target that moves can be missed.
The game asks whether to adjust a strike's final target location (Campaign QoL
answers no for you). A nation with the native **Tactical data system** (1963)
updates it by datalink instead: the strike aims at the nearest spotted enemy
surface ship within 40,000 yards of its old aim point, and the battle log says
"Strike retargeted by datalink". With no such ship, or without the research,
the native question (or Campaign QoL's no) comes as before.

Beyond the horizon a ship needs someone else's contact. The game already lets
ships with Tactical data system fire at targets spotted by aircraft or other
ships. **Ocean surveillance satellites** (ID 2323, 1976: the Soviet US-A
"Legenda" and the US "White Cloud" satellites) add satellite fixes: whenever a
radar-equipped ship's spotting pass finds an enemy surface ship beyond its radar
band, its nation gets a fix with a 0.5% chance per pass. The target then counts
as spotted and joins that ship's contacts, so missiles in range can engage it.
Submarines and land targets are never fixed.

**ESM and EMCON** (like Sea Power's EM emission tracks). With the **Electronic
support measures suite** (ID 2304, 1972), a ship hears enemy surface ships whose
search radar is on out to three times that radar's own range: 15,000 + 4,000
yards per radar class, times 3 (a class 5 set is heard at 105,000 yards, an
AESA at 129,000). A heard ship becomes a radar contact (unknown until it is
identified the usual way) and joins the listener's contacts, so missiles in
range can engage it; the battle log says "ESM: enemy radar emissions detected"
when one of your ships gains a new one. Ships whose radar is damaged, destroyed
or switched off are silent; submarines and land targets are not heard. The
computer's ships listen by the same rule.

The battle toolbar has a **RADAR ON / EMCON** button right of NUKE (shown when
any of your ships has a search radar). EMCON switches the radars of all your
ships off: enemy ESM cannot hear them, but they also make no radar sightings
and lose everything the game ties to a working radar (radar gunnery and blind
fire, radar-directed AA, SAMs against aircraft, part of their missile defence,
the radar range circles on the map) and the satellite fixes of radar ships; they
still see visually, still listen with ESM, and still get contacts from aircraft
and datalink. Underneath, EMCON adds 1,000 to
each ship's radar damage, so every native radar check sees the set as down;
hits taken while it is off still add damage, radar repairs wait until it is
back on, and the ship panel shows "(EMCON)" instead of "(X)". Click again for
RADAR ON. Each battle starts with radars on.

**Computer EMCON.** A computer surface ship whose nation has the ESM research
keeps its radars off until your side sees it (eyes, aircraft, radar or your
ESM: any sighting level from the last spotting pass), then switches them on and
keeps them on while it stays seen. Until then it hunts with its own ESM: it hears
your radars and can fire at them without being heard itself. Submarines, land
batteries and ships without a search radar are left alone.

**Hearing is not seeing.** A missile fired at a ship its side only hears (not
seen by anyone, and outside the range of every working radar of the side:
ESM contacts, satellite fixes, launch positions) may lock on to the wrong ship:
half the time its seeker takes the nearest other ship of the target's side
within 10,000 yards (an escort, or a decoy ship) instead. A lone ship is found
anyway. Seen targets, or targets inside your own radar range, are never mixed
up.

**Anti-radiation seekers.** With **High-speed anti-radiation missiles** (1984),
your anti-ship missiles home on a target whose radar is on: its decoys cannot
fool them, and an only-heard target is not mixed up. Against a ship in EMCON, or
one whose radar is damaged, they are ordinary missiles. Both sides get it from
their research.

**A missile's nation.** A missile records its launcher's battle side (0 or 1),
not its nation. The research and doctrine checks of the earlier missile rules
(sea-skimming flight, imaging seekers, nuclear heavy SSMs, the SSBN salvo's
nuclear hit) read that side as a nation index until 1.46.0, so the computer's
missiles used the research of whichever nation came second in the campaign's
list. They now use the nation of the side's ships.

**Shipborne UAVs** (ID 2326, 2005: ScanEagle, Fire Scout). With the research,
the aircraft request dialog (Aircraft types > Request) lists **UAV** under the
roles. A UAV request develops UAV models (all the prototypes it offers), built from its
own data (SHIPBORNE UAV): 120-150 mph, 10-15 hours in the air, a search radar
like the late floatplanes', no bombs, easy to shoot down. A Floatplane scout
request still gives a floatplane, and floatplane models already built stay
floatplanes. Computer nations develop their floatplane scouts as UAV models
from 2005, and so does a UAV request: the UAV data starts then, so a request
completed earlier in the game's aircraft years (behind the calendar at a slow
research pace) develops floatplane scouts. If any prototype's data fails to
load, the request skips that prototype instead of stopping the turn with
"Error in ResolveAircraftRequest". Once a nation has a UAV model in service (developed and not
withdrawn), its ships launch and recover their scouts without stopping or
slowing, as if they had a catapult, and the launch prompt reads "Launch search
UAV(s) from"; until then they handle floatplanes as before. A UAV's radar
contact is shared like any aircraft's: ships with Tactical data system can fire
missiles at it beyond their own horizon. The aircraft lists, the prototype
choice, a pending request and its messages show UAV models as "UAV".
Underneath, a UAV model keeps the floatplane scout role (a separate role number
would touch some 330 places where the game reads the role) and a UAV mark in
the same saved field as the stealth mark, so it survives the game's renaming
(XS-25, later a service name). Helicopters are unchanged.

## AESA radar

**Active electronically scanned array radar** (ID 2318, 2002: the Dutch APAR
went to sea in 2002, Japan's FCS-3 and the US SPY-6 followed) is its own search
radar, class 7, for a nation that has Aegis radar and this research. Set **radar
limit 7** in the designer: it needs a hull laid down from 2002 and weighs 200 t,
like Aegis. Older classes keep limit 6 and Aegis radar; ships with limit 7 get
AESA at their next radar upgrade. It sees 48,000 yd with a 66% chance per check
(Aegis: 40,000 yd, 55%), sights at 45,600 yd, and halves enemy stealth cuts: a
low-observable ship designed from 2015 is seen at 81% of the normal range
instead of 64%. The AI reserves one radar class ahead as the native game does,
so its Aegis-era ships fit AESA once researched; that reserve now weighs 200 t
(natively nothing).

## Designer names follow research

When the designer's nation has the research and the design is new enough, the
native captions change to what replaced the module: **Aluminium superstructure**
becomes **Composite superstructure** (Composite superstructures, designs from
1996), **Seaplane/helicopter hangar** becomes **UAV/helicopter hangar**
(Shipborne UAVs) and **Catapults** becomes **EMALS catapults** (hulls laid down
from 2017). Names only; the rules are unchanged.

## Extra generators

From **Integrated power system** (2016) the designer shows a **Generators (MW)**
box under the Power readout: extra gas-turbine generator sets of the Zumwalt and
Type 45 kind, 0 to 2,550 MW in 10 MW steps. Each 10 MW weighs 40 t and costs
200, counted with the armament beside the lasers. They add to the MW the plant
can spare for railguns and lasers on any propulsion; railguns still need Nuclear
or Gas turbine drive. Without the research the box stays at 0 and the design
report lists the missing research.

## Guided shells and torpedoes

**Guided gun projectiles** (ID 2320, 2012: Excalibur, Vulcano, the HVP studies):
guns of 6 inches and less, in any battery, of a nation with the research hit
twice as often. Ammunition counts, ranges and damage are unchanged.

**Guided heavy-calibre projectiles** (ID 2322, 2026, projected): larger guns of a
nation with the research hit 1.5 times as often. No navy fields guided shells
above 155 mm yet; the smaller gain reflects their long flight times and few
rounds.

**Wake-homing and wire-guided torpedoes** (ID 2319, 1977: the Soviet wake-homing
53-65K, Sweden's wire-guided Tp 613): torpedoes fired by the ships and
submarines of a nation with the research steer at their target every step while
it is afloat, as missiles do (natively torpedoes always run straight), and they
hit ships they pass at two and a half times the native distance. Their range
still runs out, so a long stern chase misses. Speed, damage and malfunctions are
native.

## Undersea warfare

`CampaignOverhaul/undersea.py`.

**Anti-torpedo torpedoes** (ID 2353, 2013: Russia's Paket-NK, the US SSTD
trials): an **ATT** box (0-3 launchers) at the end of the point-defence strip.
Each launcher carries 4 and weighs 6 t, costs 120 and adds 2 topside points.
When an enemy torpedo comes within 1,500 yards, the ship fires one at it: 40%
for one launcher, +10% a launcher more, at most 60%. Each torpedo is engaged
once. The battle log says when one is destroyed. Computer designs fit them too
(see AI designs).

**Submarines move.** Natively a battle's submarines never move. Now, each battle
minute, every submarine still in the fight closes on the nearest enemy ship it
can hear (12,000 yards, or 24,000 for your ships while their sonar is ACTIVE) at
8 knots, or 20 knots for an SSN or SSBN, until that ship is inside two thirds of
its torpedo range. Then it holds and attacks as before.

**Sonar.** Natively the battle map never shows enemy torpedoes. Now one is drawn
while one of your ships can see or hear it:

| Detection | Range |
| --- | --- |
| Its wake, by eye | 1,500 yards; 400 when the firing nation has Oxygen fuelled or Electric torpedoes |
| Early hydrophones (1107) | 1,000 yards |
| Improved hydrophones (1113) | 2,000 yards |
| Enhanced sonar systems (1122) | 3,000 yards |
| Digital passive-sonar processing (1140) | 4,000 yards |

A **SONAR** button right of EMCON (shown once you have Early hydrophones)
switches your ships between **PASSIVE** and **ACTIVE**. ACTIVE hears torpedoes
50% farther, but enemy submarines hear your ships twice as far away and close
in. Each battle starts PASSIVE.

## Hypersonic speed and EMALS

Hypersonic SSMs (see below) now fly five times as fast as the native missile of
their type. A step that would carry one past its target ends half a native step
short instead, inside the game's 3,000-yard hit window, so it still reaches the
interception layers and its hit roll.

**Electromagnetic aircraft launch system** (ID 2321, 2017: Gerald R. Ford, then
Fujian): carriers laid down from 2017 by a nation with the research get 4 spot
(aircraft readied per strike) for each catapult instead of 1, and heavy jets need
a carrier of 24,000 tons instead of the steam-catapult 30,000 (that native check
uses the player's research, as before).

**Ski jump** (research 2335 Ski-jump flight decks, 1974). The designer's
Flight installations gain a **Ski jump** box under Flight deck. It needs the
research and a flight deck, and any hull may have one (Hermes got hers in a
refit). A ski jump is a jet deck, so ticking it ticks Jet capable too;
unticking Jet capable removes the ski jump. The ramp weighs 1.5% of the
displacement (at least 150 t), counted with the armament at the armament cost
per ton (since 1.46.0; it was free before). A ski-jump deck:

- readies 2 more aircraft per strike when it has no catapults (Invincible);
- flies heavy jets and jet attack aircraft without catapults when it also has
  an angled flight deck (STOBAR: Kuznetsov's Su-33s). The tonnage minimum still
  applies. Without catapults those heavy jets take 1.5 deck slots each, as the
  game charges them on carriers under 40,000 tons: the price of a ski-jump
  launch. (The lighter take-off load itself is not modelled: the game keeps no
  link from an air strike to the carrier it flew from.)

AI carriers: the AI designer makes a flight deck jet capable only from 30,000
tons (40,000 without a lucky roll or steam catapults). With the ski-jump
research its smaller carriers get a ski jump instead, which makes them jet
capable (air capacity trimmed to the weight, as the native jet decks are), and
its jet decks without catapults get one too. Saved designs and
ships keep the ski jump in their JetCapable key, which now holds 0, 1 or 3
(3: jet capable with a ski jump); files without ski jumps are unchanged. Until
2026-11-14 every flight deck laid down from 1973 without catapults counted as a
ski jump; now only decks with the box do.

**Vertical take-off jet fighters** (ID 2338, 1969: Harrier). A nation's light
jet fighters are VTOL: a carrier need not be jet capable to fly them, so the
air group screen accepts them and they take one deck slot instead of the 1.5 a
light jet takes on a carrier that is not jet capable. The air unit's nation
decides. Heavy jets and jet attack aircraft are unchanged.

**AV ships with VTOL fighters** (LPH/LHD style). An AV with a flight deck
counts as a carrier for air operations, like the BB/BC hybrids: it launches
strikes and CAP from its air group, while battle tactics still treat it as an
AV. Its air group may hold VTOL light jet fighters besides its floatplane
scouts and UAVs when its deck is jet capable (the heat-proof deck for jet
exhaust) and the air unit's nation has the VTOL research. An existing AV needs a
refit that adds the flight deck and Jet capable; the designer may then suggest
reclassifying it as a CVL (answer No to keep it an AV).

## Anti-submarine weapons

The native **Improved ASW torpedoes** (1950) already give +2 ASW value to ships
with two or more torpedo mounts. **Lightweight ASW torpedo tubes** (ID 2331,
1966: Mk 32 tubes, Mk 46 torpedo) give destroyers, escorts and cruisers +2 more
with any torpedo mount, and **Vertical-launch ASW rockets** (ID 2211, 1993:
VL-ASROC) give them +2 when they carry a VLS bank (some cells hold ASW rockets).
**Hybrid diesel-electric propulsion** (ID 2344, 1985: CODLAG, Type 23, FREMM)
gives them +2 when they are designed from 1985 with Diesel or Gas turbine
propulsion: they creep on quiet electric motors while their sonar listens.

## Composite superstructures

**Composite superstructures** (ID 2332, 1996: La Fayette's GRP panels, Visby's
carbon fibre, the Zumwalt deckhouse): a light superstructure (the Aluminium box)
on a ship designed from 1996 by a researching nation is composite. The designer
cuts that weight to 85% instead of aluminium's 92%, at 130% of the cost instead
of 115%, and in battle composite ships skip all five aluminium fire penalties.

## Heavy DP guns (7 and 8 inch)

The game lets only 3- to 6-inch guns be dual-purpose, and gives only those
calibres a heavy AA value. 7- and 8-inch guns may now be DP too, the heavy
anti-aircraft ship of the late 1940s studies (`modern_air_defence.py`):

- **When:** once the nation has 6 in dual purpose mounting (1934) and 7 and 8
  in autoloader (1945, the rapid-fire 8-inch of the Des Moines class). Any
  battery: main, secondary or tertiary.
- **Turrets:** single or twin only, as for every DP gun; twin mounts also need
  3 and 4 in twin dual purpose mounting, as the native rule asks.
- **Heavy AA:** 5 a gun for 7 inches and 4 for 8 inches, one more when
  autoloaded (a 6-inch DP gun counts 5, or 6; a 5-inch 9 plus gun quality). An
  autoloaded main battery counts 1.5 times again, as natively. They count as
  ordinary heavy AA: the game has light, medium and heavy AA only.
- **Weight:** DP mounts weigh more, as for smaller DP guns.

Computer nations follow the same rule, but their designs only make main
batteries DP on destroyers, light cruisers and carriers, so their heavy
cruisers keep plain 8-inch guns.

Without this mod a design with 7- or 8-inch DP guns keeps its DP mark, but
those guns give no AA and the designer's checks treat the mounts as not
allowed.

## Tankers

A formation's range in battle is its fuel, filled from its aircraft's
endurance at each mission and refuelling, and for planning its aircraft's
combat radius, a third of the endurance (`modern_air_defence.py`).

- **Aerial refuelling** (ID 2347, 1953, after Improved jet engines; KC-97,
  probe and drogue): aircraft flying from an airfield of a researching nation
  have 50% more fuel and range. A land tanker can top up a whole strike on the
  way out. Carrier aircraft are not refuelled by it.
- **Unmanned carrier tankers** (ID 2348, 2027, after Aerial refuelling; MQ-25
  Stingray, about 15,000 lb of fuel 500 nm out, a quarter of a Super Hornet's
  internal fuel for each of four): a carrier's special squadron also flies
  tanker drones, so while the carrier has its special squadron its aircraft
  have 30% more fuel and range. The game's special squadrons belong to
  carriers; airfields have none, which is why land tankers come with the
  research itself.

Every range check that knows the formation uses it: the computer's strike
targets, land air priorities, the launch and escort menus (their ranges show
the bonus) and a formation's own status. The estimates of enemy air ranges
stay native. Floatplanes from cruisers and tenders get nothing. It acts in
battle; campaign air rules do not use aircraft range.

## Interceptor drones

**Interceptor drone swarms** (ID 2345, 2021, after Shipborne UAVs; Coyote and
Roadrunner): every ship with a helicopter deck, a catapult or a flight deck
carries AI interceptor drones (`modern_air_defence.py`). There are no drones to
manage and no count: it is a research effect.

- **Missile defence:** 15 more percent in the countermeasure roll each
  incoming missile (and guided bomb) has to pass, the roll jamming and decoys
  use (4% plus 9% a level of hidden ECM, plus the electronic warfare suites).
- **Air defence:** 4 more heavy AA value against air strikes, like one laser.
- **CAP and radar:** a carrier counts as having an AEW squadron wherever the
  battle asks for one (longer radar, CAP vectoring onto raids from further out,
  earlier scrambles), without giving deck space to AEW aircraft.

Computer nations get all of it with the research.

## USVs, nuclear shells and frigates

**Explosive unmanned surface vessels** (ID 2333, 2024: the Black Sea drone
boats): a nation's newest MTB squadrons use the USV design
(`Data/IDes/USV.sdf`, 45 knots) and are named "USV".

**Nuclear gun projectiles** (ID 2334, 1958: the W23 "Katie" 16-inch shell for
the Iowas): main batteries of 16 inches or more fire one nuclear
shell per battle, their first hit, which the game resolves as a 64-inch hit. It
wrecks almost any ship. Computer nations can research it too; the research is
expensive and uncertain (50% chance per attempt).

**Frigates:** from 1975 the KE type reads **FF** (the US Navy's 1975
reclassification of ocean escorts). Design files written after that say FF and
load as KE, with or without the date; older files are unchanged.

## BBV hybrids

A **BB or BC with a flight deck and aircraft** (tick Flight deck in Flight
installations and give it an aircraft capacity) is a hybrid battleship-carrier
(the Ise conversions, and the many paper hybrids). Everywhere the game asks
"is this a carrier?" it now answers yes: it gets an air group, launches strikes,
CAP and scouts, cycles its deck, and its flight deck takes carrier damage and
fires. In battle tactics it stays a battleship: it starts with the battle line
instead of 3,000-9,000 yards back, keeps battleship formation spacing and
stance, chooses courses and objectives like a battleship, and picks gun targets
as one. Its type stays BB or BC everywhere else (lists, counts, AI building).
No research is needed. Computer nations do not design BBVs.

## Lasers

**Shipboard high-energy lasers** (ID 2316, 2022, after Integrated power system;
HELIOS went to sea in 2022, DragonFire follows) adds a **Lasers** box under AA
directors in the anti-aircraft panel: 0 to 8 laser mounts. Each mount weighs
20 t (10 t before 1.46.0), costs 100, adds 3 topside load points and needs 1 MW
from the Power budget (railguns and lasers share it). Without the research the
box stays at 0; the design report lists missing research or power.

In battle the lasers are a close-in layer against each incoming missile, after
SeaRAM and gun-missile mounts and ahead of the gun CIWS, and they need a free
fire-control channel (see Point defence): 15% per mount, at most 60%. Rain or mist halves that, heavy seas halve it
again, and against a hypersonic missile it is only 30% of the result. Like CIWS,
lasers are knocked out by superstructure damage. Lasers have unlimited
magazines. Against air attacks (aircraft and drones) each laser mount adds 4
to the ship's AA value; rain or mist halves that, and heavy seas halve it
again, as for missiles.

Laser counts (and future per-ship systems) are kept in a small extension of
the native ship objects: designs and the ships built from them carry it into
battle, and design files and campaign saves store it with the main battery's
elevation value. Ships without lasers save exactly as before.

## Point defence

SeaRAM, gun-missile CIWS (Kashtan, Kortik) and RAM launchers, with fire-control
channels that limit how many close-in systems engage one missile
(`CampaignOverhaul/point_defence.py`). A strip under the armament tabs, beside
Topside load, holds the controls and a readout:

| Control | Research | Per mount |
| --- | --- | --- |
| **SeaRAM** 0-3 | 2351 SeaRAM self-contained launchers (2008) | 8 t, cost 150, 5 topside points, 11 missiles |
| **Gun-missile CIWS** 0-7 | 2349 Gun-missile close-in weapon systems (1989) | 15 t, cost 200, 6 topside points, 32 missiles |
| **Spare missiles** 0-3 | a design with either mount | each step half a load more: 3 t a SeaRAM, 5 t a gun-missile mount, cost 40 a mount |
| **RAM launchers** tick box | 2350 Rolling airframe missiles (1991) | light SAM launchers weigh 20% more (cost 10 a ton added) |
| **ATT** 0-3 | 2353 Anti-torpedo torpedoes (2013) | 6 t, cost 120, 2 topside points, 4 anti-torpedo torpedoes (see Undersea warfare) |

Enlarged point-defence magazines (2352, 2016) adds half a load to every mount
with no extra weight. The readout line says, for example, "Point defence: 3
systems / 2 channels - too few channels.   Missiles: SeaRAM 22, gun-missile 0".
The topside report lists the point-defence load (lasers count 3 a mount).

**Fire-control channels.** Each close-in system that engages an incoming missile
uses one channel, in the order SeaRAM, gun-missile, lasers, gun CIWS; systems
past the channels hold fire against that missile. A ship has 2 channels, +1 for
each AA director (up to +2), +1 with a working phased-array (Aegis) search
radar and +2 with AESA. A radar that is damaged or switched off (EMCON) gives no
channels. A system knocked out with the superstructure, or a SeaRAM mount with
no missiles left, uses none. Railgun point defence is gunfire and needs none. So
SeaRAM with a gun CIWS works on any ship, and lasers on top need a director or
a modern radar.

**In battle.** After the SAMs and decoys, SeaRAM fires 2 missiles at the incoming
missile: 40% for one mount, +10% a mount, at most 60%. Gun-missile mounts fire 2
missiles (35%, +5% a mount, at most 50%), then their 30 mm guns (20%, +5% a
mount, at most 35%); with no missiles left the guns still fire. Like the native
CIWS, the odds fall with every missile the ship has already met this turn
(the roll is out of 100 + 30 for each), and the kills follow the hypersonic and
low-observable SSM rules (see Hypersonic missiles). A mount's missiles last the
battle: 11 a SeaRAM and 32 a gun-missile mount, half a load more for each spare
step and for Enlarged point-defence magazines.

**RAM launchers.** With the box ticked, the ship's light SAMs are Rolling
Airframe Missiles: fire and forget with an infrared seeker, so they count half
the missiles already met this turn (see Missile defence). This applies to every
light SAM mount of that ship, launchers and VLS cells alike.

The values are stored in the ship extension; its bits 24-29 ride in the spare
bits 2-7 of the saved elevation integer, so older saves load with none.
Computer designs fit point defence by the nation's real-world style (see AI
designs). Adding the four rows shifts the Vertical launch systems progress of
campaigns past 1989 by up to four rows.

## Hypersonic missiles

**Hypersonic anti-ship missiles** (ID 2317, 2023, after Effective cruise
missiles; Zircon entered service in 2023, and the US Navy's Conventional Prompt
Strike is planned for Zumwalt) adds a **Hypersonic SSMs** box under the Missile
launchers group in the Additional armament panel. A ticked design fires
hypersonic SSMs from all of its launchers. Each SSM VLS cell weighs about 50%
more (heavy +5 t, medium +2 t, light +1 t) and costs 20 more; box launchers are
unchanged. Without the research the box cannot be ticked, and the design report
lists the missing research.

In battle, SAMs, CIWS, radar-guided AA and lasers keep only 30% of their kills
against these missiles. Decoys and countermeasures work as before. They fly five
times as fast as native missiles without stepping past their targets (see
Hypersonic speed and EMALS). A battle saved with hypersonic missiles in flight
loads them as ordinary missiles. The option is
stored in the ship extension with the laser count.

Aircraft get them too: an aircraft model developed from 2023 by a nation with
the research launches hypersonic anti-ship missiles (Kinzhal, YJ-21), with the
same odds against SAMs, CIWS, radar-guided AA and lasers and the same speed.
Older models keep their ordinary missiles; develop new ones to get them.

**Low-observable anti-ship missiles** (ID 2339, 2017, after Effective cruise
missiles; LRASM entered service in 2018, NSM and JSM are shaped the same way)
make all of a nation's anti-ship missiles stealthy, its aircraft's too: a third of the kills that enemy
SAMs (the target's and its neighbours'), CIWS and radar-guided AA score against
them fail. On a hypersonic missile this comes on top of the hypersonic rule.
Lasers track by heat and railgun point defence keeps its own odds, so neither
changes.

**Hypersonic interceptors** (ID 2340, 2025, after Compact self-defence VLS
modules; SM-6 for Sea-Based Terminal defence, Russia's S-500) let a nation's SAMs,
its ships' own and their neighbours', keep 60% of their kills against hypersonic
missiles instead of 30%. CIWS, guns and lasers keep the 30%.

## Electronic warfare and SEAD

**Special squadrons** (a carrier's Special air unit) come in two kinds, decided by
the aircraft type the squadron flies. A jet squadron (light or heavy jet
fighters, jet attack: EA-6B, EA-18G) is an **EW squadron**: its jamming disrupts
enemy CAP vectoring against its strikes and makes enemy SAMs less effective
against them. Any other squadron (propeller aircraft, helicopters: E-2
Hawkeye, Ka-31) is an **AEW squadron**: it extends its carrier's radar and
improves its own CAP vectoring. Both rescue downed aircrew after a battle, and
each still needs the game's minimum size (a sixth of the air capacity, 6 to
20 aircraft). A carrier that wants both flies one of each. Before, one Special
squadron of any type did all of it.

**Suppression of enemy air defences.** SAMs firing at an attacking air formation
are less effective when the formation's nation has:

| Research | Year | Effect |
| --- | --- | --- |
| Anti-radiation missiles (Shrike) | 1965 | Against jet aircraft (light, heavy jet fighters, jet attack): SAMs 25% less effective |
| Self-protection jamming pods (ALQ-71, ALQ-119) | 1967 | Against any aircraft: SAMs 20% less effective |
| High-speed anti-radiation missiles (HARM, Kh-31P) | 1984 | Against jet aircraft: another 20% less |

The cuts multiply: a jet strike with all three faces SAMs at about half their
strength, before the EW squadron's jamming. Anti-radiation missiles suppress
rather than destroy: they do not knock out the target's radar. The battle log
says "Anti-radiation missiles suppress SAMs" and "Jamming pods reduce SAM
effectiveness" once for each attacking formation (until 1.46.0 every SAM salvo
logged them, the first twice with both ARM researches: over a thousand lines in
a big air battle). Unsupported strikes meet modern SAMs at full
strength.

**Fleet air defence fix** (all eras, both sides). The game has a routine that
finds the enemy air formation nearest a point. It tracked the nearest one but
never returned it, so everything that asked always heard "none". Four native
behaviours therefore never happened, and now do:

- **CAP vectoring:** a CAP formation flies out toward the nearest enemy raid
  within its vectoring range (its carrier's radar, longer with an AEW squadron,
  shorter against enemy jamming).
- **Forward CAP stations:** when a raid comes within reach of the force a CAP
  covers, the CAP moves its station halfway toward it, between the raid and
  the ships (a barrier CAP).
- **Scrambles:** a carrier launches CAP when enemy air comes within its radar
  range.
- **Close enemy air** checks, used by formations in flight, now see enemy
  formations.

This code never ran in the released game, so it is the least tested part of
the mod. Expect CAP to matter much more in every era.

## Super heavy missiles

A **Super heavy SSMs** box sits right of Hypersonic SSMs: the P-500 Bazalt and
the P-700 Granit of the Kirov battlecruisers. It needs the native **Effective
cruise missiles** research (1960; over-the-horizon targeting, used by the first
super heavy missiles from 1962) and a CA, BC or BB hull; the design report lists
either failure. It upgrades every heavy SSM mount on the ship, launchers and VLS
banks alike, which then weigh twice as much (cost 10 per extra ton).

In battle that ship's heavy SSMs reach twice the native range, both when the
ship and the AI decide to fire and in flight, and each hit lands as a 40-inch
shell equivalent instead of the heavy SSM's 32 (damage grows with calibre cubed:
about twice as much). Medium and light SSMs, SAMs and other ships are unchanged.
It combines with Hypersonic SSMs. The map's range circles and "only in range"
target filter still show native ranges, and the Battle AI mod's missile stand-off
distance still uses the native heavy SSM range.

## AI designs

AI ships use these options too (`CampaignOverhaul/ai_modern.py`). After AIDesignShip's weight passes, one pass per
AI design applies what the nation has researched, as far as its economy and the ship allow:

- **Economy.** A nation that spends more than it earns, or holds less than a month of budget in cash, changes
  nothing. One that earns more than it spends and holds a month of budget fits hypersonic SSMs and half the
  lasers. With a monthly surplus of a tenth of its budget and three months in cash it also fits Nuclear
  propulsion, railgun main batteries, super heavy SSMs and the full laser fit.
- **Practical ships.** Nuclear only on BB, BC, CA, CV and CVL hulls of 20,000 t or more; railguns only with gas
  turbine or nuclear power and the MW for them; super heavy SSMs only on CA, BC and BB hulls that carry heavy
  SSMs; hypersonic SSMs only on ships with SSMs; lasers 2, 4 or 8 by size (below 8,000 t, below 20,000 t,
  larger), fewer when the plant cannot power them. The designer's research, hull, drive and power rules hold.
- **Weight.** Each option is undone if the design comes out overweight; the AI's hull-trim loop then turns the
  remaining spare weight back into hull. Eligible designs take Nuclear, railguns and super heavy SSMs 50-60% of
  the time and hypersonic SSMs 80%, so fleets stay varied.

- **Point defence**, on ships of 1,500 t or more once the nation earns more than it spends, in its real-world
  style. A nation whose name contains Russia, Soviet, Pact or India fits gun-missile CIWS mounts: 1 below
  6,000 t, 2 below 15,000 t, 4 below 30,000 t, else 6. Every other nation ticks RAM launchers on ships with
  light SAMs (80% of the time) and fits SeaRAM: 1 below 8,000 t, 2 below 40,000 t, else 3. With three months
  in cash they carry one spare-missile step. The mounts are undone when the design comes out overweight or
  over its topside capacity.
- **Anti-torpedo torpedoes**, on the same ships, half of them, any nation with the research: 1 launcher below
  3,000 t, 2 below 30,000 t, else 3. Fitted after point defence and undone the same way (since 1.46.0).

Extra generators, railgun secondaries and railgun point defence, BBV hybrids and larger hull sizes stay player
options (decided 2026-11-08). AI designs also turn their missile launchers into VLS banks once they earn more
than they spend (VLS_CELLS.md, "AI designs").

## Special shell doctrine

Guided and nuclear shells are a choice with a price for the player
(`shell_doctrine.py`).

- **Where.** Doctrine and training, a new **Special shells** box between
  Torpedo usage options and AP shell design priority (which moves down; the
  window is taller), with two tick boxes: Use guided shells and Use nuclear
  shells. Like the torpedo tick boxes they are grey until the research is
  done, and they are stored when the window is closed.
- **Default.** No special shells: a new game, and a save from before this
  version, start without them. The research is still needed.
- **Cost.** Each time a battery with guided shells fires a salvo the player
  pays 1; each nuclear shell (a heavy main battery's first hit of a battle)
  costs 500. Without the money the shell is an ordinary one.
- **Other nations** fire what their research allows, as before, free. Nuclear
  weapons (shells, SSN torpedoes, SSBN missiles) they never fire first: only
  after you have fired one (see "No first use" below).
- **Nuclear blast.** The nuclear hit also strikes every other ship within
  1,500 yards of the target, friend or enemy, with a 12-inch hit (the firing
  ship is spared). Against aircraft see Heavy AA below.
- **Save.** The choice (1 guided, 2 nuclear, 3 both) rides on the save's
  `UseMissileTorps` value (choice x 256 added). A save with a choice, loaded without the mod, would switch on
  the game's unfinished missile-torpedo option: set No special shells and
  save before removing the mod.

Tests: `Manager/test_shell_doctrine.py`.

## Missile defence: radar class, doctrine and mission kills

The game already resolves a missile attack as a small salvo model: for each
incoming missile the target fires two SAMs of each kind it has, medium and
heavy launchers that fired this turn are busy 60% of the time, and each
shot's chance falls by a third for every missile the ship has already had to
deal with this turn. Every ship had the same fire control in it. Now
(`modern_defence.py`):

| | Radar 1-5 | Phased array (6) | AESA (7) |
|---|---|---|---|
| Launcher busy after firing this turn | 60% | 24% | 9% |
| Earlier missiles this turn that count against a shot | all | half | a quarter |

- The radar must be working: a disabled or destroyed radar gives the old
  values.
- **Fire one SAM at each incoming missile** (the player's fifth tick box):
  each engagement spends one missile instead of two. Cells last twice as
  long; each engagement is weaker. Computer nations always fire two.
- **Missile flight.** A medium or light SSM (ship- or air-launched) whose
  nation has **Turbofan anti-ship missiles** (1978: sea-skimming, Harpoon and
  Exocet) is seen late: the target
  treats it as if it already had one more missile to deal with, which takes a
  third off every SAM shot. **Long-range anti-ship missiles** (2013: terminal
  manoeuvres, NSM and LRASM) add one more. The radar class divides the count
  afterwards, so Aegis halves the penalty and AESA nearly removes it. Both
  sides get it from their research. Heavy SSMs (P-700, P-500 class) cruise high
  and get neither; CIWS and AA guns already hit them more easily.
- **RAM launchers** (see Point defence). A ship with the RAM launchers box
  ticked counts half of that total (missiles met plus flight) for its light
  SAMs, before the radar class divides it.
- **Electronic warfare.** The game already decoys some missiles by a hidden
  ECM level (4% plus 9% a level). Ships designed from 1972 by a nation with
  **Electronic support measures suite** add 10% (jammers and chaff), ships
  designed from 2000 with **Ship self-defence system integration** another 10%
  (active decoys, Nulka). A missile from a nation with **Long-range anti-ship
  missiles** (imaging seekers) takes 10% back. There is no designer box: like
  stealth, the suite comes with the design year, so rebuild or redesign old
  classes to get it.
- **Anti-ship ballistic missiles.** The game's coastal Missile Batteries, for
  a nation with **Long-range anti-ship missiles** (2013; DF-21D entered service
  about 2010), launch ballistic missiles: they fly five times as fast and SAMs,
  CIWS, radar AA and lasers stop only 30% as many, as with hypersonic SSMs.
  Their range is still the native missile range.
- **Mission kill.** Every missile hit also runs the game's own radar damage
  35% of the time (radar disabled for a while, one time in ten destroyed). A
  hit ship then loses its SAM chances and its phased-array advantages, as a
  real ship loses its combat system before it sinks.
- Correction: a missile submarine launches one missile an attack. (The "2" in
  its launch is an aiming error level; an earlier version of this mod raised
  it for SSBNs by mistake, making them less accurate.) An SSBN now launches
  four missiles.

- **Quad-packed light SAMs** (Compact self-defence VLS modules, 1992): a light
  SAM VLS bank holds four missiles a cell. The game spends whole missiles from
  a bank, so three engagements in four the light SAMs fired go back into the
  bank: the cells last four times as long, against missiles and aircraft alike
  (before 1.43.5 only missile defence got them back). The designer, the ship
  information and the battle panel still count cells, so 8 cells show as 8.
- **Missiles left.** In battle, the ship panel's status line (where "On fire!"
  and "No flight ops!" appear) shows `SAM n, SSM n` for a ship with missile
  launchers when it has nothing else to say: loaded missiles and reloads,
  without destroyed mounts. A quad-packed bank counts its cells, not its
  missiles.
- **Empty ships withdraw** (Battle AI): a computer-controlled division whose
  flagship has missile launchers, no missile left in any of them and no main
  gun over 5 inches disengages, as the game already does for ships low on gun
  ammunition. This also applies to your own divisions under AI control.

Not built: mixed missile types in one VLS bank.

Tests: `Manager/test_modern_defence.py`.

## Research dates checked against real ships

`Manager/test_real_ships.py` lists 24 real ships with the year each was laid
down and the research its design needs in this mod (propulsion, launchers,
radar class, hull and deck features). Every such research must be dated no
later than the keel laying and no more than 8 years before its first ship.
Dates corrected by that check:

| Research | Was | Now | Real ship |
|---|---|---|---|
| Nuclear attack submarines | 1958 | 1952 | Nautilus, laid down 1952 |
| Ballistic missile submarines | 1962 | 1957 | George Washington, 1957 |
| Vertical launch cells (8) | 1966 | 1974 | Kirov, 1974 |
| VLS 16 / 32 / 64 cells | 1968 / 1970 / 1973 | 1977 / 1980 / 1983 | Bunker Hill (Mk 41), 1984 |
| Later VLS rows | 1976-1985 | 1986-1990 | follow the cells |
| Ski-jump flight decks | 1980 | 1974, any flight deck | Invincible, 1973 |
| Phased-array (Aegis) radar | 1983 | 1978 | Ticonderoga, 1980 |
| Extended-range SAMs | 1981 | 1980 | Kirov's S-300F, 1980 |
| Radar cross-section reduction | 1990 | 1987 | Arleigh Burke, 1988 |
| Composite superstructures | 1996 | 1995 | Visby, 1995 |
| Cooperative engagement | 1984 | 1996 | in service 1996 |
| AESA radar | 2002 | 1998 | De Zeven Provincien, 1998 |
| Integrated power system | 2016 | 2003 | HMS Daring, 2003 |
| Low-observable ship design | 2015 | 2008 | Zumwalt, 2011 |
| Third-generation reactors | 2010 | 2008 | Gerald R. Ford, 2009 |
| EMALS | 2017 | 2009 | Gerald R. Ford, 2009 |

Known gap: nuclear propulsion stays at 1961 because it follows the game's own
last machinery row (1960), so Long Beach and Enterprise (laid down 1957-58)
come when they were completed. The rows of the two new branches are written
out in year order whatever order the code lists them in; a save from before
this version has its progress in those branches shifted.

## Nuclear submarines, aftermath and the ban treaty

**New submarine kinds** (`nuclear_subs.py`). The game has five submarine roles
and no room for more, so the new kinds are native roles with a mark at the end
of the boat's name:

| Kind | Research | Native role | Mark | Special |
|---|---|---|---|---|
| Nuclear attack submarine (SSN) | 2336, 1952 | long range | name ends " SSN" | torpedo hits can be nuclear |
| Ballistic missile submarine (SSBN) | 2337, 1957 | missile | name ends " SSBN" | launches 4 missiles where a missile submarine launches one; one hit of the salvo can be nuclear |

- They appear in the Build submarine list once researched. An SSN costs 2.5
  times a long range submarine to build and to keep, an SSBN 4 times a
  missile submarine; building time is the native role's. Do not remove the mark from a boat's name:
  it is what makes it an SSN or SSBN. A boat you name with such an ending
  yourself becomes one.
- Player auto-build uses the native long-range and missile role selectors. Once
  researched, auto-built long-range boats receive the ` SSN` name mark and
  auto-built missile boats receive ` SSBN`; without the matching research they
  remain ordinary native types. This closes the gap where the automatic build
  routine created a conventional class from a nuclear-sub selection.
- Computer nations build them too once they have the research: of the medium
  and long range submarines they order, 10% become SSBNs and 40% SSNs, and half
  of their missile submarines become SSBNs. In the monthly building only a
  nation that earns more than it spends does this; the starting fleets of 1980
  and 2000 get the same shares without that test. They pay the same higher cost.
- The two research rows are the first two of the Vertical launch systems
  branch (Naval combat systems is full). A save made before this version has
  its progress in that branch shifted by two rows.
- **Nuclear hits.** The target takes the same hit as from a nuclear shell and
  every other ship within 1,500 yards a 12-inch hit. A torpedo is nuclear once
  it comes within hit distance of a ship, at most once a torpedo.
- **Doctrine.** The Special shells box has five tick boxes now: guided shells,
  nuclear shells, nuclear torpedoes on SSN (800 each), nuclear missiles on
  SSBN (1,500 each), and Fire one SAM at each incoming missile (below).

**Classes.** The game gives every boat two qualities when it is built and
keeps them for its life: availability (40 plus 3 for each submarine technology
level: how much of the time the boat is on station) and accuracy (-2 to 1).
A nuclear boat is built with 15 more availability (no snorkelling, fast
transits, long patrols), and an SSN with one more accuracy, up to the native
best. Boats built before this version keep what they had. Speed, diving depth
and silencing are not separate values in the game; this is the whole of a
submarine class.

**Heavy AA.** Instead of a blast on aircraft, a ship that may fire nuclear
shells (16-inch guns, the research, the player's tick box, no ban treaty)
has 60 more heavy AA value against every air attack (a dual-purpose gun adds
about 1 to 5).

**Aftermath.** When any nuclear weapon was fired, by anyone, the next turn
raises every nation's tension by 3 and reports it in the news. One time in
three the powers then propose a treaty banning nuclear weapons for 15 years.
If you sign, nobody fires nuclear weapons until it runs out (the tick boxes
stay but have no effect); if you refuse, nothing more happens. The treaty's
last year is kept in the save with the doctrine choice.

**No first use.** Computer nations have the same nuclear shells, torpedoes
and missiles as you, but do not fire them (nor get the nuclear heavy AA
value) until you have fired and paid for a nuclear weapon, and then only in kind:
your nuclear shell frees their shells (and the heavy AA value), your SSN
torpedo their torpedoes, your SSBN missile their missiles. They fire those
kinds in every battle until the war ends. At peace the slate is wiped:
in the next war they again wait for you. A signed ban treaty wipes it too.
The mark is kept in the save with the doctrine choice.

Tests: `Manager/test_nuclear_subs.py`, `Manager/test_shell_doctrine.py`.

**Nuclear Armageddon** is a separate sub-mod (Library `nuclear-armageddon`,
[NUCLEAR_ARMAGEDDON.md](NUCLEAR_ARMAGEDDON.md)): nuclear weapons without the
one-a-battle limits, at the same prices, and nuclear warheads for heavy SSMs and
heavy SAMs. Without it, everything above stands.

## Nuclear strike console

The battle screen has a red **NUKE** button right of the toolbar's last button
(auto battle). It is greyed out unless your nation has **Ballistic missile
submarines** (2337) and at least one SSBN in service (built and not lost).

1. Click **NUKE**. The map cursor becomes a crosshair and the console opens
   centred under the button (kept inside the window).
2. Click the target area on the map, the way you pick a target for an air
   strike. Two dashed red circles show the blast: 2,000 and 5,000 yards. The
   console's TARGET reads MARKED and the TGT gauge fills. Click **TGT** (the
   gauge, or the crosshair under it) to pick a new target at any time.
3. Turn **KEY 1** and **KEY 2**: click each; it turns from SAFE to ARM (about
   half a second) and the ARM gauge fills with both. Only both keys at ARM arm
   the strike: STATUS reads ARMED and the LAUNCH button lights red. Click a
   key again to turn it back.
4. Click the **glass cover** over LAUNCH: it lifts. Click **LAUNCH** under it
   to fire. **ABORT** closes the console without firing; the keys go back to
   SAFE and the glass shuts (also after a launch).

The console (460 x 284 at 96 DPI) shows the two keys, LAUNCH under its glass in
the middle, the TGT and ARM gauges, and along the bottom SSBNs READY (your SSBNs
built and not lost), the warhead cost, TARGET, STATUS, the message line and
ABORT. Its pictures are `Mods/CampaignOverhaul/nuke_console/*.bmp`, drawn by
`nuke_console_art.py` from the console's own layout; if they are missing the
console still works, without them.

The strike is a ballistic missile from one of your SSBNs, so no launcher needs
to be in the battle. Aim at ships you can see: the log says "the missile
detonates over empty sea" when nothing was within 5,000 yards.

- **Warheads.** Click **WARHEAD** in the bottom strip to cycle them; the target
  circles show the chosen warhead's reach:

  | Warhead | Price | Every ship sinks within | Nuclear hit within |
  | --- | ---: | ---: | ---: |
  | A-BOMB | 1,500 | 2,000 yards | 5,000 yards |
  | H-BOMB | 4,000 | 6,000 yards | 15,000 yards |
  | MIRV (from 1970) | 6,000 | 2,000 yards a warhead | 5,000 yards a warhead |

  A MIRV's 4 warheads go to the mark, then to enemy ships your side has
  contact on (seen or on radar) within 40,000 yards of it, each outside the
  earlier warheads' kill radius; fewer such ships, fewer warheads. A ship
  that sinks is gone within the minute (no buoyancy, the game's own sinking
  timer at one). Without the money nothing is fired.
- **One a battle.** After the strike NUKE greys out until the battle ends.
  With Nuclear Armageddon there is no limit.
- **Blast.** Every ship within the hit radius, friend or foe, takes the nuclear
  shell's hit (64 inch), and inside the kill radius it sinks; every air
  formation within the hit radius loses its aircraft.
  The battle log reports the detonation, and the map shows a fireball and a
  growing shock ring for about eight seconds.
- **Rules.** It is a nuclear missile in every other way: no strike while a ban
  treaty you signed runs, it frees the computer's nuclear missiles (no first
  use) and raises tension at the next turn (every turn checks since
  2026-11-22; before, only the turns whose events ran the tension changes
  did, so the news often never came). The Use nuclear SSBN tick box is not
  needed: the console is your direct order.
- Computer nations never use the console. Saves are not changed.

Tests: `Manager/test_nuclear_strike.py`. Not yet tried in a live battle.

## Starting fleets and economies of the later starts

**Fleets.** In 1947, 1960, 1980 and 2000 each nation starts with its real
fleet instead of whatever its funds buy under the game's 1890-1935 rules: the
number of active carriers, light carriers, battleships, cruisers, destroyers
and escorts on 1 January of that year (`start_fleets.py`). Examples: the USA
has 12 carriers, 14 heavy and 22 light cruisers in 1947 and 13 carriers and
27 cruisers in 1980; the Soviet Union 20 cruisers in 1960; the United States
12 carriers, 27 cruisers and 54 destroyers in 2000. The superstates get their
members' combined fleets. Ships are of designs from the start year's era, in
classes of up to 10. Destroyers are capped at 60 and escorts at 40 a nation,
because huge fleets slow the game and Campaign QoL stops AI building at 400
ships. Germany and Japan in 1947 have only a minesweeping force. Submarines,
aircraft and coastal batteries come from the game's own builders. The fleet
is free: a nation keeps its starting funds. In 1947-1980 the lists are for
the Cold War blocs.

**Economies.** Base resources follow each nation's share of world output in
the start year (Maddison GDP; for the superstates their members' sum), with
the USA at 60,000 in 1947, 70,000 in 1960, 85,000 in 1980 and 100,000 in
2000. The game's growth modifier (`GGP`, 1% more growth a year outside
depressions) is on for the fast-growing economies of the time: Germany, Japan,
Italy, France and the Soviet Union in 1947 and 1960 (Spain too in 1960), Japan,
China and Spain in 1980, and China, India and the Southeast Asian Union in
2000.

**Scripted rebellions.** The game makes Cuba and the Philippines rebel, now and
then, while Spain owns them. Where Spain is not a nation (the 2000
superstates), its owner test matched an unowned region and the turn stopped
with "Error in CheckForceOnForeignStations"; the rebellion now needs Spain to
exist.

## Superstates (the 2000 start)

The **2000** box on the New game year screen starts a fictional world of ten
blocs. (The historical 2000 start is gone; 1947, 1960 and 1980 are the Cold
War worlds below.) Each bloc takes one of the game's ten nation slots:

| Slot | Bloc | Home area | Other regions |
|---|---|---|---|
| USA | United States | Eastern USA | the rest of the USA and its islands |
| Soviet Union | Russian Federation | Western Russia | Far East, the north, Kaliningrad |
| China | People's Republic of China | Northern China | Southern China and the coast |
| Germany | European Union | Germany | United Kingdom, France, Spain, Italy, Austria, islands |
| Japan | East Asian Federation | Japan | Southern Korea, Hokkaido, Formosa |
| Great Britain | Southeast Asian Union | Java | Singapore, the Philippines, Malaya, Indochina, Burma |
| Austria-Hungary | India | India | Ceylon |
| Italy | Middle East Federation | Turkey | Persia, Egypt, North Africa, Yemen |
| France | United African States | South Africa | Nigeria, Kenya and the rest of Africa |
| Spain | South American Union | Brazil | Argentina, Chile, Peru, Venezuela, Cuba, Panama, Jamaica, Hispaniola, Trinidad |

- **One home area each.** A home area is a possession of value 200. Each bloc
  has exactly one, and Campaign QoL's invasion rule keeps only that one closed:
  every other region, however big, can be invaded.
- **Nine nations in a campaign.** The game takes the player's nation and the
  eight enemies named in its battle file. Asian blocs' files (India, Southeast
  Asia, East Asia, China) leave out the South American Union; the others leave
  out the Southeast Asian Union. So Southeast Asia exists only when you play an
  Asian bloc, and its land is neutral otherwise; South America is neutral land
  when you play an Asian bloc.
- **Names.** Every bloc has a new name, the three unchanged powers too: the
  game finds a nation's battle, ship-name and officer files by its name, and
  the native files list Germany, Japan and the rest as enemies. Rules the game
  ties to native names (China's concessions, a few AI design habits) do not
  apply; map colours follow the slot.
- **Battles** are fleet, cruiser and light-force meetings in the two blocs'
  nearest home waters; there are no scripted raids, convoys or bombardments yet.
- **Flags.** EU, African Union, Arab League, UNASUR flags and India's naval
  ensign come from Wikimedia Commons; the Southeast Asian and East Asian
  ensigns are drawn for the mod.
- Needs Campaign QoL (its map, extra ports and invasion rule).
  `superstates_data.py` rebuilds every file.

## Campaign statistics after 1990

The game keeps a record for every month (statistics graphs, the summary and war history) in a
[year][month] table inside the campaign window object, for 1890 to 1990 only. Past 1990 each month's
record was written beyond the object, over the campaign window's labels. The game then crashed in turn
processing ("Error in DoTurn2 / DoStrategicTurn procedure") or on exit, with "Access violation ... in
TControl.GetAction". `CampaignOverhaul/month_records.py` moves the table, at the title screen, into its own
allocation for 1890 to 2060 by shifting the 52 instructions that index it. Saves are unchanged
(`RTWGame<n>.sta`). Months recorded before this fix may show odd values in the graphs.
Tests: `Manager/test_month_records.py`.

## Cold War blocs (the 1947, 1960 and 1980 starts)

The three earlier boxes no longer hold the ten native nations. Western
Europe's navies are one bloc and the Soviet side another, and the five slots
that frees hold minor naval powers (`coldwar_data.py`):

| Slot | Nation | Home area | Other land |
|---|---|---|---|
| USA | United States of America | Eastern USA | the rest of the USA, its islands, Korea in 1947 |
| Great Britain | European NATO | United Kingdom | Germany, France, Spain, Italy, Greece, Turkey, Norway, Iceland, and the members' colonies until independence |
| Soviet Union | Warsaw Pact | Western Russia | Eastern Germany, East Prussia, Baltic States, the Far East |
| China | Communist China | Northern China | Southern China and the coast |
| Japan | State of Japan | Japan | Hokkaido |
| Austria-Hungary | Republic of India | India | - |
| Germany | Indonesia | Java | Sumatra, Borneo, Celebes and Moluccas |
| Spain | Brazil | Brazil | - |
| France | Argentina | Argentina | - |
| Italy | Iran | Persia | - |

- **Names.** One name for all three years, though NATO dates from 1949 and the
  Warsaw Pact from 1955, and China is called Communist China in 1947 too: the
  game finds a nation's battle and name files by its name, so a nation has one
  name and one set of files, different from the native nations' and the 2000
  blocs'.
- **Nine nations in a campaign.** Asian players (China, Japan, India,
  Indonesia, Iran) do not meet Argentina; the others do not meet Indonesia.
  The missing nation's land is neutral.
- **History by year.** Colonies follow the dates under "Later start years":
  Egypt is NATO land in 1947 and neutral from 1960, Kenya neutral in 1980.
  Economies, admirals, governments, friends and enemies change by year (Iran
  has a Shah and is a US friend until 1980; Argentina's enemy is NATO in 1980).
- **Economies** of the minors are their share of world output with a floor of
  2,500: Brazil grows from 3,700 to 12,800, India from 9,000 to 13,000.
- **Fleets** are in `start_fleets.py`: European NATO has its members' sum
  (9 battleships and 13 carriers in 1947), Argentina two battleships in 1947
  and a light carrier later, Iran a few escorts.
- **Flags.** NATO, Indonesia, Brazil, Argentina and Iran ensigns are drawn for
  the mod (simple shapes). Ship and officer names are in
  `superstates_names.py`; European NATO mixes its members' native lists.
- The rules of the 2000 start apply: one home area a nation, plain meeting
  battles only, Campaign QoL needed.

## Later start years

The sections below describe the historical state of each year. The package
files now put blocs into it (Cold War blocs above, superstates in 2000); land
no bloc claims keeps the owner listed here.

New game's year screen gets a second row: **1947, 1960, 1980 and 2000**
(`CampaignOverhaul/start_years.py`, attached with the timeline adapter). The
package installs the picture with the extra boxes as `Images/StartYears.jpg`.
Without that file the screen stays native.

A later start follows the 1935 start, with its own year:

- **Nations.** Each year has its own `Data/BNat<year>.dat`: the 1935 nations
  as they stood on 1 January of that year.
  - Germany, Italy and Japan are post-war democracies, flying the Bundesmarine,
    Marina Militare and JMSDF ensigns. Japan has no kamikaze trait.
  - Spain is Francoist in 1947 and 1960 and a democracy in 1980 and 2000.
  - China is the Kuomintang republic in 1947 and the PRC afterwards.
  - In 2000 the Soviet Union is the Russian Federation: limited democracy, a
    President, the Duma and the St Andrew's ensign. It keeps the name "Soviet
    Union", because the game's per-nation war and name files and every other
    nation's war data use it, and the game's own RussiaWarInfo20.dat is
    incomplete.
  - Admiral names are the naval chiefs of the time, and Friend/Enemy follow
    the Cold War line-up.
  - Economies follow each nation's share of world output, and BudgetModifier
    sets each navy's share of it. The leading economy is 60,000-95,000, the
    range natural campaigns reach in local saves.
  - Austria-Hungary stays the game's own alternate-history state.
- **Possessions.** `Data/MapData<year>.dat` holds the owners on 1 January.
  - After 1945: Korea is split between Soviet and US occupation, and Soviet
    gains include East Prussia, the Baltic States, Sakhalin and Port Arthur.
  - Italy's colonies are under British administration; the Philippines are
    independent.
  - Decolonisation follows: India 1947, Indochina 1954, most of Africa from
    1956, Hong Kong to China in 1997.
  - The dominions (Canada, Australia, New Zealand, South Africa) stay British,
    as in the game's 1935 world, until 1960, and are independent from 1980.
  - `CampaignOverhaul/start_years_data.py` writes both kinds of file from the
    game's 1935 and 1920 files.
- **Options.** As 1935: no slow-aircraft or historical-resources choice, and no
  1920 treaty.
- **Technology.** Every technology dated before the start year, for every
  nation (the game's SetTechForYear with that year).
- **Fleets.** Fleets, starting aircraft and coastal batteries come from the
  game's year-generic builders, the same path as custom battles. Ships come
  from design templates of years up to 15 before the start. The timeline's
  year tables keep 2000-era templates in the last era.
- **1935-only rules.** Versailles limits for Germany, Soviet fleet losses and
  Germany's 1935 ships stay with 1920 and 1935. The two one-time notices a 1935
  start has already had are marked seen: first ship of a new kind completed,
  and the military's smaller share of growing spending.

The campaign starts on 1 January of that year and runs to the 2050 end.
Starting fleets come from the game's generator, sized by each navy's budget, not
from historical orders of battle. Tests: `Manager/test_start_years.py`.

## Save compatibility and recovery

The engine supports 36 technology slots per area and 25 branch records. The
package stays inside both limits, preserving every original line, ID,
prerequisite and slot index. New IDs do not collide with the original table or
the audited immediate native research-ID queries. No executable-file patch is made.

Older saves have 23 research records, with gun manufacture at 22. When one
loads with this package, its gun research is read into record 24 and the two
new branches start empty; each nation is checked for its own `Research24Prio`
key. The next save writes the 25-record layout. An unmodified game reads a
converted save's Vertical launch systems record as gun manufacture and loses
the real gun research on its next save, so keep this package enabled.

Local saves on 4 November 2026: Game4 (December 1948) is already converted.
Game9 holds an unconverted copy of it from July 1947. Game9's earlier unplayed
1890 start is backed up in `Mods/Manager/backups/saves/20261104-042442-Game9`.

Keep a separate pre-mod test save. Once you research the added technologies,
**keep both modern research and the timeline package enabled for that campaign**.
Disabling the data package is not a conversion back to vanilla: a saved campaign
can retain the appended research flags, which vanilla level-count calculations
would still count even though their technology labels are absent. To return to
vanilla safely, disable the packages with RTW3 closed and load a pre-mod save.
The mod manager backs up replaced game data, not your unsaved campaign progress.

The runtime checks the installed table, complete audited getter bodies, native
field layout, title-screen state, patch bytes and return contracts. Each added
bonus also checks that its native table slot still contains the expected new ID.
Patching is rolled back if installation fails. Closing RTW3 unloads the hooks.
The separate Steam installation and RTW3.exe on disk stay unchanged.

## Historical ship names

For the United States, Europe, Russia (Warsaw Pact), China and Japan (East
Asian Federation), in every later start, each ship name list now begins with
real post-war ships, lead ships of their classes first: Forrestal, Kitty Hawk,
Nimitz; Sverdlov, Slava, Kirov, Sovremenny, Udaloy; Sheffield, Leander,
Clemenceau; Liaoning, Nanchang; Kongo, Izumo. The game takes names from the
top of a list more often than from further down, so starting fleets and new
classes mostly carry them, though not in historical order and not tied to the
start year (a bloc has one name file for all its start years). The designs
themselves are still the game's templates, grown and refitted by the mod.
The other blocs keep their existing real-name pools.

## What is not implemented

This research package does not add laser dwell time, railgun
projectile flight or reload limits, or shared mixed-missile VLS cell allocation. Those need separate engine and designer work. Modern research uses explicit, working native
abstractions rather than advertising those absent systems as completed features.
The **VLS Cells - Native Ship Designer** mod adds fixed-type cell banks using
existing SAM/SSM weapons and requires this package's Vertical launch systems
branch; see [VLS_CELLS.md](VLS_CELLS.md).
Weekly economic/research pacing and a full campaign through 2030 remain unbalanced
and unverified. The package is optional and experimental.

## Historical anchors and verification

The years are gameplay availability presets, not universal national service dates.
Specific anchors include the U.S. Navy's [Aegis history](https://www.navy.mil/Resources/Fact-Files/Display-FactFiles/Article/2166739/aegis-weapon-system/),
which places its first operational ship in 1983, and its [Nulka fact file](https://www.navy.mil/DesktopModules/ArticleCS/Print.aspx?Article=2167877&ModuleId=724&PortalId=1),
which dates production approval and initial installations to 1999. The Navy's
[ESSM fact file](https://www.navy.mil/Resources/Fact-Files/Display-FactFiles/Article/2168978/evolved-seasparrow-missile-block-1-essm-rim-162d/lang/evolved-seasparrow-missile-block-1-essm-rim-162d/)
provides another modern missile-system reference; this mod does not claim to
reproduce its classified performance.

Automated tests execute the original x86 getters and native research-ID lookup
with the appended table in an emulator. They check each new direct-effect flag,
all bonuses, identical baseline results without new research, player/AI ownership,
register/stack/flag preservation, wrong-ID rejection, original-slot preservation,
and native machinery/hull weight, accuracy, penetration, carrier-size and invasion
range changes. This is stronger than checking labels, but it is not a completed
long-campaign, save/reload or battle-balance playthrough.

Further tests run the native research save and load loops in the emulator:
an older 23-record save loads with gun research in record 24 and empty new
branches, and new-layout saves round-trip unchanged. An earlier normally
authenticated title-screen startup verified the 83 appended IDs, names, dates,
costs and prerequisites in the game's loaded table, all ten installed effect
hooks and the optimized reveal hooks; the merged 104-entry table has not had
that live check. The old-save conversion itself ran in a real campaign with the
earlier Research Expansion package (Game4, 1947 to 1948). Windows address randomization is supported by
normalizing the authenticated image's relocation entries for code validation;
deliberate code changes still fail the audited-method checks. No campaign was
loaded, saved or advanced for this startup check, and battle FPS was not measured.

The complete technology inventory is in
`Mods/Library/timeline-2030/research-index.json`.
