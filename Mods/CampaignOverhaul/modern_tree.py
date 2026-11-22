"""Append-only, native-capacity research definitions for the modern-era mod.

Appends to the 22 original branches and fills the two reserved branch slots
(22 Vertical launch systems, 23 Naval combat systems; gun manufacture moves to
24). This is a research/effect extension, not new laser, railgun or stealth physics.
"""
import hashlib
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
BASELINE = HERE/"vanilla/ResearchAreas3.dat"
if not BASELINE.exists():   # a release install: the mod loader's backup of the player's own original file
    BASELINE = HERE.parent/"Manager/baseline/Data/ResearchAreas3.dat"
VANILLA_SHA256 = "d9d7f33f7b7458f9fc93a42c4ff8e1d3a7a237cec4e6d756b3eefec01babb043"   # 1.01.44, no time-stretch
PACKAGE = HERE.parent/"Library/timeline-2030"   # merged Expanded Timeline package
MAX_LEVELS = 36

NATIVE = {
    0: "Native machinery research +1 (lower machinery weight)",
    1: "Native armour-quality research +1",
    2: "Native hull research +1 (lower hull weight)",
    3: "Native fire-control research +1 (accuracy progresses every two levels)",
    7: "Native AP-penetration research +1",
    11: "Native ASW research +1",
    18: "Native carrier-design research +1 (carrier size allowance)",
    20: "Native amphibious research +1 (invasion range)",
}
LABELS = {
    "GetROFMod": "National gun ROF modifier +1",
    "GetDamageControlMod": "Damage-control modifier +1 beyond the native research ceiling",
    "GetSAMQ": "SAM quality +1",
    "GetSSMQ": "SSM quality +1",
    "GetAntiMissile": "Anti-missile countermeasure quality +1",
    "GetAirborneECMLevel": "Airborne ECM quality +1 (native support-aircraft requirements retained)",
    "GetSubAccuracy": "New submarine attack-accuracy modifier +1",
    "GetLAAQ": "Light AA quality +1",
    "GetMAAQ": "Medium AA quality +1",
    "GetHAAQ": "Heavy AA quality +1",
}

# Stable order is part of saved-campaign compatibility. Never renumber these
# entries or insert a technology before an already released appended entry.
# Third item: native count effect, or one or more reviewed integer getters.
BRANCHES = {
    # Slot 32 was "Combined gas-turbine plant refinement" (1980) until 2026-11-05;
    # same ID and slot, now the reactor that enables nuclear propulsion.
    0: [(1961, "Naval nuclear propulsion", "native"),
        # IDs 41-43, renamed 2026-11-05 (same years and native effect): reactor generations for railgun power.
        # 43 renamed again 2026-11-06 (same ID, year and slot): thorium reactors, see THORIUM.
        (1995, "Life-of-ship reactor cores", "native"),
        (2008, "Third-generation naval reactors", "native"),
        (2030, "Thorium molten-salt naval reactors [projected]", "native")],
    1: [(1980, "Modern ballistic-steel quality control", "native"),
        (1995, "Improved structural armour metallurgy", "native"),
        (2010, "Advanced armour manufacturing control", "native"),
        (2030, "Optimized protective steel [projected]", "native")],
    2: [(1980, "Computer-aided structural optimization", "native"),
        (1995, "Precision modular hull construction", "native"),
        (2010, "Digital structural weight management", "native"),
        (2030, "Integrated lightweight hull design [projected]", "native")],
    3: [(1980, "Digital gun fire-control computation", "native"),
        (1995, "Integrated electro-optical gun tracking", "native"),
        (2010, "Multi-sensor gunnery track fusion", "native"),
        (2030, "Adaptive gunnery prediction [projected]", "native")],
    4: [(1980, "Distributed fire and flooding detection", "GetDamageControlMod"),
        (1995, "Integrated damage-control monitoring", "GetDamageControlMod"),
        (2010, "Networked emergency response systems", "GetDamageControlMod"),
        (2030, "Predictive damage-control support [projected]", "GetDamageControlMod")],
    5: [(1980, "Electronic ammunition-handling control", "GetROFMod"),
        (1995, "Modern automatic naval gun mechanisms", "GetROFMod"),
        (2010, "Continuous ammunition-flow monitoring", "GetROFMod"),
        (2030, "Advanced conventional gun automation [projected]", "GetROFMod")],
    6: [(1990, "Integrated sensor and weapon-system design", "GetSAMQ"),
        (2030, "Distributed combat-system integration [projected]", "GetSSMQ")],
    7: [(1980, "Modern penetrator manufacturing tolerances", "native"),
        (1995, "Improved naval penetrator metallurgy", "native"),
        (2010, "Computer-optimized AP projectile shaping", "native"),
        (2030, "Advanced naval AP projectiles [projected]", "native")],
    8: [(1990, "Automated light-force missile targeting", "GetSSMQ"),
        (2030, "Cooperative littoral engagement [projected]", "GetSSMQ")],
    9: [(1990, "Digital submarine torpedo fire control", "GetSubAccuracy"),
        (2030, "Adaptive submarine torpedo processing [projected]", "GetSubAccuracy")],
    10: [(1980, "Integrated submarine combat-system processing", "GetSubAccuracy"),
         (2005, "Modern submarine sonar-track fusion", "GetSubAccuracy"),
         (2030, "Distributed submarine sensor processing [projected]", "GetSubAccuracy")],
    11: [(1980, "Digital passive-sonar processing", "native"),
         (1995, "Integrated towed-array processing", "native"),
         (2005, "Multistatic ASW coordination", "native"),
         (2020, "Broadband ASW track fusion", "native"),
         (2030, "Distributed ASW processing [projected]", "native")],
    12: [(1980, "Optimized defensive missile fragmentation", "GetSAMQ"),
         (1995, "Improved anti-ship missile warhead consistency", "GetSSMQ"),
         (2010, "Precision defensive missile fuzing", "GetSAMQ"),
         (2030, "Advanced missile warhead integration [projected]", "GetSSMQ")],
    13: [(1983, "Coordinated fleet electronic defence", "GetAntiMissile"),
         (2005, "Networked countermeasure coordination", "GetAntiMissile"),
         (2030, "Adaptive fleet electronic defence [projected]", "GetAntiMissile")],
    14: [(1980, "Electro-optical light AA tracking", "GetLAAQ"),
         (1995, "Digital medium-calibre AA tracking", "GetMAAQ"),
         (2010, "Multi-sensor naval AA directors", "GetHAAQ"),
         (2030, "Integrated conventional AA fire control [projected]", "GetMAAQ/GetHAAQ")],
    15: [(1978, "Phased-array combat-system integration", "GetSAMQ"),
         (1990, "Digital ship-to-ship engagement links", "GetSSMQ"),
         (2000, "Cooperative air-defence track processing", "GetSAMQ"),
         (2010, "Digital electronic-support processing", "GetAntiMissile"),
         (2020, "Active-array engagement management", "GetSAMQ"),
         (2030, "Distributed air-defence sensor fusion [projected]", "GetSAMQ")],
    # Lighter-than-air aviation remains a historical dead end, not a source of
    # fictional modern gunships or bonuses from obsolete airship research.
    17: [(1980, "Digital airborne escort jamming", "GetAirborneECMLevel"),
         (2005, "Integrated airborne electronic attack", "GetAirborneECMLevel"),
         (2030, "Cooperative airborne electronic attack [projected]", "GetAirborneECMLevel")],
    18: [(1980, "Integrated carrier deck-cycle planning", "native"),
         (1995, "Computer-assisted carrier layout", "native"),
         (2005, "Digital carrier aircraft-space management", "native"),
         (2020, "Integrated carrier support-space design", "native"),
         (2030, "Optimized carrier aviation layout [projected]", "native")],
    19: [(1980, "Improved terminal anti-ship missile guidance", "GetSSMQ"),
         (1990, "Digital naval SAM guidance", "GetSAMQ"),
         (2000, "Improved anti-ship seeker discrimination", "GetSSMQ"),
         (2010, "Modern medium-SAM engagement processing", "GetSAMQ"),
         (2020, "Multi-mode anti-ship seeker processing", "GetSSMQ"),
         (2030, "Adaptive naval SAM guidance [projected]", "GetSAMQ")],
    20: [(1980, "Modern amphibious logistics planning", "native"),
         (1995, "Integrated ship-to-shore logistics", "native"),
         (2010, "Digital expeditionary support planning", "native"),
         (2030, "Distributed amphibious sustainment [projected]", "native")],
    21: [(1980, "Digital defensive electronic warfare", "GetAntiMissile"),
         (1990, "Integrated chaff and decoy control", "GetAntiMissile"),
         (1999, "Active offboard missile decoy integration", "GetAntiMissile"),
         (2010, "Digital radio-frequency countermeasures", "GetAntiMissile"),
         (2020, "Multi-sensor soft-kill coordination", "GetAntiMissile"),
         (2030, "Adaptive terminal defence coordination [projected]", "GetAntiMissile")],
}


# New branches in the two reserved native slots: (id, year, prerequisite, chance,
# cost units, name, effect). Effect is reviewed getters, or a description of a
# rule implemented elsewhere (vls_cells, modern_* read the IDs below). Rows are in
# year order; since 2026-11-06 new rows may be inserted (older saves no longer matter).
NEW_AREAS = (
    ("Vertical launch systems", "MissileBattery.jpg", (
        # Naval combat systems is full (36 levels); the missile boats sit with the launch systems.
        (2336, 1952, 1012, 60, 40, "Nuclear attack submarines",
         "Build nuclear attack submarines (SSN): long range boats whose torpedoes can carry nuclear warheads"),
        # 1953: inserted 2026-11-21, so campaigns past 1953 have this branch's later progress shifted by one row.
        (2347, 1953, 1728, 70, 12, "Aerial refuelling",
         "Land-based aircraft have 50% more range: tankers refuel them on the way out (KC-97, probe and drogue). Not carrier aircraft"),
        (2337, 1957, 1028, 60, 40, "Ballistic missile submarines",
         "Build ballistic missile submarines (SSBN): missile boats launching 4 missiles where a missile submarine launches one, one of them nuclear if allowed"),
        (2338, 1969, 1823, 70, 14, "Vertical take-off jet fighters",
         "Light jet fighters are VTOL (Harrier): a carrier need not be jet capable to fly them"),
        (2341, 1965, 1907, 70, 14, "Anti-radiation missiles",
         "Jet strike aircraft carry anti-radiation missiles (Shrike): enemy SAMs are a quarter less effective against them"),
        (2342, 1967, 1523, 70, 14, "Self-protection jamming pods",
         "Strike aircraft carry jamming pods (ALQ-71, ALQ-119): enemy SAMs are a fifth less effective against them"),
        (2201, 1974, 1919, 90, 10, "Vertical launch cells", "Enables 8-cell VLS banks: below-deck cells, one missile each, no reloads"),
        (2202, 1977, 2201, 90, 10, "Modular VLS magazines", "Enables 16-cell VLS banks"),
        (2203, 1980, 2202, 90, 12, "Canister exhaust management", "Enables 32-cell VLS banks"),
        (2204, 1983, 2203, 90, 12, "Large VLS magazines", "Enables 64-cell VLS banks"),
        (2343, 1984, 2341, 70, 18, "High-speed anti-radiation missiles",
         "HARM, Kh-31P: jet strike aircraft suppress enemy SAMs another fifth"),
        (2344, 1985, 17, 70, 12, "Hybrid diesel-electric propulsion",
         "Diesel ships spare a quarter of their horsepower as railgun and laser power (half with Integrated power system) and may mount railguns, and escorts and cruisers designed from 1985 with diesel or gas-turbine drive run quiet on electric motors: ASW value +2 (CODLAG: Type 23, FREMM)"),
        (2205, 1986, 2204, 70, 14, "Lightweight composite launch cells", "VLS cells weigh 20% less"),
        (2206, 1988, 2205, 70, 14, "Hull-integrated VLS modules", "Hulls can carry 25% more VLS cells"),
        (2207, 1990, 2206, 70, 16, "Universal VLS fire control", "GetSSMQ"),
        (2208, 1992, 2207, 70, 20, "Compact self-defence VLS modules", "VLS cells weigh another 10% less and light SAM cells hold four missiles (quad-packed, ESSM)"),
        (2211, 1993, 2207, 70, 20, "Vertical-launch ASW rockets",
         "Ships with a VLS bank gain ASW value: some cells carry ASW torpedo rockets (VL-ASROC)"),
        (2209, 2005, 2208, 70, 24, "Peripheral VLS integration", "Hulls can carry 25% more VLS cells again"),
        (2339, 2017, 1917, 70, 28, "Low-observable anti-ship missiles",
         "Stealthy SSMs (LRASM, NSM, JSM): enemy SAMs, CIWS and radar-guided AA stop a third fewer of them"),
        (2340, 2025, 2208, 70, 30, "Hypersonic interceptors",
         "SAMs keep 60% of their kills against hypersonic missiles instead of 30% (SM-6 Sea-Based Terminal, S-500)"),
        # Prerequisites come from the original tree or an earlier row of the same new branch (native load order).
        (2346, 2026, 2340, 70, 30, "Hypervelocity anti-air projectiles",
         "Railgun main batteries of any calibre fire hypervelocity air-burst rounds at aircraft: 20 heavy AA a gun (a 5-inch DP gun gives 9 to 12), they engage air strikes from three times as far, and their hits strike two aircraft"),
        (2348, 2027, 2347, 70, 30, "Unmanned carrier tankers",
         "A carrier's special squadron also flies tanker drones (MQ-25 Stingray): that carrier's aircraft have 30% more range"),
        (2210, 2030, 2209, 70, 28, "Next-generation VLS modules [projected]", "VLS cells weigh another 10% less"))),
    # SAM, SSM and anti-missile quality already reach their reviewed +10 maximum
    # through the appended branches, so this branch improves guns and ship systems.
    ("Naval combat systems", "Radar.jpg", (
        (2334, 1958, 1222, 50, 40, "Nuclear gun projectiles",
         "Main batteries of 16 inches or more fire one nuclear shell per battle, their first hit (W23 Katie for the Iowas, W33): it wrecks almost any ship"),
        (2301, 1965, 1524, 70, 10, "Naval tactical data processing", "GetHAAQ"),
        (2331, 1966, 1119, 70, 10, "Lightweight ASW torpedo tubes",
         "Destroyers, escorts and cruisers with any torpedo mount gain ASW value (Mk 32 tubes, Mk 46 torpedo)"),
        (2302, 1967, 2301, 70, 10, "Automated threat evaluation", "GetLAAQ"),
        (2303, 1969, 2302, 70, 12, "Integrated combat direction system", "GetMAAQ"),
        (2304, 1972, 2303, 70, 12, "Electronic support measures suite", "GetLAAQ"),
        (2305, 1975, 2304, 70, 14, "Phased-array fire control radar", "GetHAAQ"),
        (2323, 1976, 2304, 70, 14, "Ocean surveillance satellites",
         "Radar ships get occasional satellite fixes on enemy surface ships beyond radar range (US-A Legenda, White Cloud): they count as spotted and missiles can engage them"),
        (2319, 1977, 822, 70, 14, "Wake-homing and wire-guided torpedoes",
         "Torpedoes your ships fire home on ships they pass: they hit from two and a half times as far away"),
        (2324, 1978, 1917, 70, 14, "Turbofan anti-ship missiles", "SSM range +50% (Harpoon, Exocet MM40)"),
        (2306, 1979, 2305, 70, 14, "Integrated damage-control systems", "GetDamageControlMod"),
        (2335, 1974, 1823, 70, 16, "Ski-jump flight decks",
         "Ski jump option for flight decks: a jet deck that readies 2 more aircraft per strike without catapults, and flies heavy jets from an angled deck without catapults (Invincible, Kuznetsov)"),
        (2325, 1980, 2303, 70, 16, "Extended-range SAMs", "Medium and heavy SAM range doubled (SM-2ER, S-300F)"),
        (2307, 1996, 2306, 70, 16, "Cooperative engagement capability", "GetMAAQ/GetHAAQ"),
        (2308, 1987, 2306, 70, 20, "Radar cross-section reduction", "Ships designed from 1987: enemy radar range -20%, jets developed from 1990 are stealth models"),
        (2332, 1995, 2308, 70, 22, "Composite superstructures",
         "Light (aluminium) superstructures on ships designed from 1995 are composite: lighter, costlier, no aluminium fire risk (La Fayette, Visby)"),
        (2309, 2000, 2308, 70, 24, "Ship self-defence system integration", "GetLAAQ"),
        (2318, 1998, 2305, 70, 26, "Active electronically scanned array radar",
         "Search radar class 7 (radar limit 7, hulls laid down from 1998): range and detection +20% over Aegis, enemy stealth halved against it"),
        (2326, 2005, 2309, 70, 26, "Shipborne UAVs",
         "New floatplane scouts are UAV models (ScanEagle, Fire Scout: slow, long endurance, radar), and ships of a nation with one launch and recover scouts without stopping, as from a catapult"),
        (2320, 2012, 2309, 70, 28, "Guided gun projectiles",
         "Guns of 6 inches and less fire guided shells: twice the hit chance"),
        (2327, 2013, 2324, 70, 28, "Long-range anti-ship missiles", "SSM range another +50% (NSM, LRASM)"),
        (2328, 2014, 2325, 70, 28, "Active-seeker long-range SAMs", "Medium and heavy SAM range another +50% (SM-6)"),
        (2310, 2008, 2309, 70, 28, "Low-observable ship design", "Ships designed from 2008: enemy radar detection range another -20%"),
        # Zumwalt (low-observable, integrated electric power) was the railgun ship. Power techs sit in year
        # order around the railgun, all before the projected 2311 (slots 10-14).
        (2313, 2003, 2309, 70, 28, "Integrated power system",
         "Gas turbine ships spare 50% of their horsepower as railgun power instead of 25% (integrated electric drive: Type 45, Zumwalt) and any ship can fit extra generators"),
        (2321, 2009, 1823, 70, 30, "Electromagnetic aircraft launch system",
         "Carriers laid down from 2009 with catapults: each catapult adds 4 aircraft per strike instead of 1, and heavy jets need 24,000 tons instead of 30,000"),
        (2312, 2020, 2313, 70, 30, "Electromagnetic railgun",
         "Enables railgun main batteries: twice the range, penetration as a gun 4 inches larger at half the range, inert rounds, needs Nuclear or Gas turbine power"),
        (2345, 2021, 2326, 70, 30, "Interceptor drone swarms",
         "Ships with a helicopter deck, catapult or flight deck launch AI interceptor drones (Coyote, Roadrunner): 15% more chance to stop each incoming missile, +4 heavy AA against air attacks, and carriers count as having an AEW squadron for radar and CAP"),
        (2316, 2022, 2313, 70, 30, "Shipboard high-energy lasers",
         "Enables laser mounts (HELIOS, DragonFire): a first layer against incoming missiles, 1 MW each, needs Nuclear or Gas turbine power"),
        (2317, 2023, 1917, 70, 30, "Hypersonic anti-ship missiles",
         "Hypersonic SSMs option (Zircon, Conventional Prompt Strike): SAMs, CIWS, radar AA and lasers stop only 30% as many, heavier VLS cells, and aircraft developed from 2023 launch hypersonic ASMs (Kinzhal, YJ-21)"),
        (2333, 2024, 2326, 70, 30, "Explosive unmanned surface vessels",
         "MTB squadrons become fast USV squadrons (Black Sea drone boats)"),
        (2314, 2025, 2312, 70, 30, "Compact pulsed-power storage",
         "Railguns need 25% less power and their mounts weigh 25% more instead of 50%"),
        (2322, 2026, 2320, 70, 30, "Guided heavy-calibre projectiles [projected]",
         "Guns over 6 inches fire guided shells too: one and a half times the hit chance"),
        (2329, 2027, 2312, 70, 32, "Railgun secondary batteries [projected]",
         "Railgun secondaries and tertiaries options: those batteries become railguns (twice the range, penetration as a gun 4 inches larger), drawing power and adding 1 t and 50 cost per MW"),
        (2315, 2028, 2314, 70, 32, "Superconducting pulsed power [projected]",
         "Railguns need another 25% less power and their mounts weigh only 10% more"),
        (2330, 2029, 2312, 70, 32, "Railgun point defence [projected]",
         "DP railgun batteries engage incoming missiles before CIWS with hypervelocity projectiles: 20% per DP railgun battery, up to 50%, a third of that against hypersonic missiles"),
        (2311, 2030, 2310, 70, 32, "Adaptive combat-system automation [projected]", "GetDamageControlMod/GetROFMod"))),
)
VLS_CELLS = {8: 2201, 16: 2202, 32: 2203, 64: 2204}   # cells -> required research
PHASED_ARRAY = 1540                                     # search radar class 6 (modern_sensors)
STEALTH = ((2308, 1987, 20), (2310, 2008, 20))          # research, design year from, % less radar range
AIRCRAFT_STEALTH = (2308, 1990)                         # research, prototype year from (modern_sensors)
NUCLEAR_PROPULSION = 40                                 # designer propulsion "Nuclear" (modern_propulsion)
RAILGUN = 2312                                          # main-gun Railgun checkbox (modern_railgun)
LASERS = 2316                                           # Lasers box in the AA panel (modern_railgun)
HYPERSONIC = 2317                                       # Hypersonic SSMs box under the missile launchers (modern_railgun)
STEALTH_SSM = (2339, 67)        # research; % of SAM, CIWS and radar-AA kills that stand against that nation's SSMs
HYPERSONIC_SAM = (2340, 60)     # research; % of that nation's SAM kills that stand against hypersonic missiles (else 30)
HYPERSONIC_AIRCRAFT_YEAR = 2023  # aircraft models from this year, of a nation with HYPERSONIC, launch hypersonic ASMs
# SEAD (modern_carrier): research, % less SAM effectiveness against the attacking formation, jets (roles 10-12) only.
SEAD = ((2341, 25, True), (2343, 20, True), (2342, 20, False))
# Hybrid diesel-electric drive: research, ships designed from (ASW), ASW value of quiet running (modern_navy); diesel
# ships then spare power like gas turbines and may mount railguns (modern_railgun).
HYBRID = (2344, 1985, 2)
SUPER_HEAVY = 1917   # native Effective cruise missiles (1960): over-the-horizon targeting enables super heavy SSMs
# Nuclear spare power for railguns, % of horsepower; newest owned generation wins (base: NUCLEAR_PROPULSION).
REACTOR_GENERATIONS = ((43, 200), (42, 150), (41, 125))
NUCLEAR_SPARE = 100
# Research, nuclear machinery weight % (modern_propulsion; 160 without it): a molten-salt reactor runs at
# near-atmospheric pressure, so it needs no heavy pressure vessel and less shielding and steam plant.
THORIUM = (43, 130)
INTEGRATED_POWER = (2313, 50)          # gas turbine spare % with integrated electric drive (else 25); extra generators
AESA = (2318, 1998, 120)               # research, first hull year, % of Aegis: search radar class 7 (modern_sensors)
GUIDED_TORPEDOES = (2319, 250)         # research, hit distance % for torpedoes a nation's ships fire (modern_combat)
GUIDED_SHELLS = (2320, 6, 200)         # research, largest calibre in inches, hit chance % (modern_combat)
HEAVY_GUIDED_SHELLS = (2322, 150)      # research, hit chance % for guns over GUIDED_SHELLS calibre (modern_combat)
# modern_recon: (research, missile types low-high, range %): SSM types 4-6, medium/heavy SAM types 1-2.
# Electronic warfare suites (modern_defence): research, ships designed from, percent more decoy chance
EW_SUITES = ((2304, 1972, 10), (2309, 2000, 10))
EW_SEEKER = (2327, 10)             # the attacker's imaging seekers: percent less
ASBM = 2327                        # coastal missile batteries fire anti-ship ballistic missiles (modern_defence)
MISSILE_FLIGHT = (2324, 2327)   # sea-skimming (Harpoon, Exocet), terminal manoeuvres (NSM, LRASM): modern_defence
MISSILE_RANGES = ((2324, 4, 6, 150), (2327, 4, 6, 150), (2325, 1, 2, 200), (2328, 1, 2, 150))
SATELLITES = (2323, 5)                 # research, per-mille chance per radar ship's pass over a far enemy surface ship
UCAV_YEAR = 2020                       # stealth jet attack prototypes from this year are unmanned, with UAVS
UAVS = 2326                            # floatplane scouts launch and recover like catapult UAVs
UAV_YEAR = 2005                        # floatplane scout prototypes from this year are UAV models, with UAVS (modern_sensors)
ASW_TORPEDOES, VL_ASW = 2331, 2211     # ASW value for torpedo mounts and VLS banks (modern_navy)
COMPOSITE = (2332, 1995)               # research, design year from: light superstructures are composite (modern_navy)
USV = 2333                             # MTB squadrons become USVs (modern_navy, Data/IDes/USV.sdf)
SKI_JUMP = (2335, 2)                   # research for the designer's Ski jump (modern_carrier), spot it adds without catapults (modern_combat)
VTOL = 2338                            # light jet fighters are VTOL: no jet-capable deck needed (modern_carrier)
NUCLEAR_SHELLS = (2334, 16, 64)         # research, smallest main calibre, the hit's calibre for HandleHit (modern_navy)
QUAD_PACK = 2208                       # light SAM VLS cells hold four missiles (modern_defence)
SSN, SSBN = 2336, 2337                 # Build submarine list entries, nuclear torpedoes and missiles (nuclear_subs)
RAILGUN_SECONDARIES = 2329             # Railgun secondaries / tertiaries options (modern_railgun)
RAILGUN_POINT_DEFENCE = (2330, 20, 50)   # research, % per DP railgun battery against incoming missiles, cap %
# Interceptor drones (modern_air_defence): research; % more chance a drone ship stops an incoming missile (the decoy
# roll), heavy AA value it adds against air attacks. Carriers of the nation also count as having an AEW squadron.
DRONE_SWARMS = (2345, 15, 4)
# Hypervelocity AA rounds (modern_air_defence): research; heavy AA a railgun main gun counts, AA range factor, aircraft
# a hit strikes.
HVP_AA = (2346, 20, 3, 2)
# Tankers (modern_air_defence): research, range % of land-based aircraft (an airfield's formations); research, range %
# of a carrier's aircraft while the carrier has its special squadron (the tanker drones fly with it).
AERIAL_REFUELLING, CARRIER_TANKERS = (2347, 150), (2348, 130)
EMALS = (2321, 2009, 24000, 4)         # research = laid-down year gate, heavy-jet carrier tons, spot per catapult
RAILGUN_EFFICIENCY = (2314, 2315)      # each: railguns need 25% less power
LIGHTER_MOUNTS = ((2315, 110), (2314, 125))   # railgun mount weight %, newest first (base 150)
NOTES = {PHASED_ARRAY: "Search radar 6: Aegis-type phased array (needs all five search radars)",
         NUCLEAR_PROPULSION: "Enables Nuclear propulsion: any range for less fuel weight than Short, never short of fuel or oil, machinery 60% heavier and 3x the cost",
         **{ident: f"Nuclear ships spare {percent}% of their horsepower as railgun power" for ident, percent in REACTOR_GENERATIONS}}
NOTES[THORIUM[0]] = f"Nuclear machinery only {THORIUM[1]-100}% heavier (not 60%), " + NOTES[THORIUM[0]].lower()
VLS_LIGHT = ((2205, 20), (2208, 10), (2210, 10))        # research -> % lighter cells
VLS_DENSE = ((2206, 64), (2209, 51))                    # research -> tons per cell


def parse(raw):
    if raw.startswith(b"\xef\xbb\xbf"): raise ValueError("Research data must not have a UTF-8 BOM.")
    areas, current, ids = [], None, set()
    for line in raw.decode("ascii").splitlines(keepends=True):
        if line.startswith("["):
            match = re.fullmatch(r"\[(.+) (\d+)\]\r?\n?", line)
            if not match or int(match[2]) != len(areas): raise ValueError("Invalid research area order.")
            current = {"area": int(match[2]), "name": match[1], "lines": [line], "rows": []}
            areas.append(current)
        elif current is None: raise ValueError("Research data must start with an area.")
        else:
            current["lines"].append(line)
            if ";" in line:
                parts = line.rstrip("\r\n").split(";")
                if len(parts) not in (7, 8) or parts[2] not in ("Y", "N"):
                    raise ValueError("Unsupported research row.")
                year, chance, cost, ident = (int(parts[i]) for i in (1, 3, 4, 5))
                if ident in ids or not 1850 <= year <= 2030 or not 1 <= chance <= 100 or not 1 <= cost <= 100:
                    raise ValueError("Duplicate ID or invalid research value.")
                ids.add(ident)
                current["rows"].append({"name": parts[0], "year": year, "id": ident,
                                        "prerequisite": int(parts[7]) if len(parts) == 8 else -1})
    # 22 original branches, or 24 with the reserved slots filled: the native loader
    # and nation records reserve 25 records including generated gun manufacture.
    if len(areas) not in (22, 24) or any(len(a["rows"]) > MAX_LEVELS for a in areas):
        raise ValueError("Research table exceeds the supported native capacity.")
    return areas


def render(raw=None):
    if raw is None:
        raw = BASELINE.read_bytes()
        if hashlib.sha256(raw).hexdigest() != VANILLA_SHA256:
            raise ValueError("The research table the mods build on is not the game's original ResearchAreas3.dat.")
    areas = parse(raw)
    ids = {row["id"] for a in areas for row in a["rows"]}
    output, nodes = [], []
    for area in areas:
        index = area["area"]
        output.extend(area["lines"])
        if BRANCHES.get(index) and output and not output[-1].endswith(("\n", "\r")):
            output.append("\r\n")
        previous = area["rows"][-1]["id"]
        for step, (year, name, effect) in enumerate(BRANCHES.get(index, [])):
            slot = len(area["rows"])+step
            ident = index*100+40+step
            if slot >= MAX_LEVELS or ident in ids: raise ValueError("Modern research slot or ID collision.")
            ids.add(ident)
            effects = [] if effect == "native" else effect.split("/")
            description = NATIVE[index] if effect == "native" else ", ".join(LABELS[e] for e in effects)
            if ident in NOTES: description = NOTES[ident]+", "+description   # ';' separates columns
            # Cost uses the native units (20,000 research points per unit).
            cost = 20+step*4
            output.append(f"{name};{year};N;70;{cost};{ident};{description};{previous}\r\n")
            nodes.append(dict(area=index, branch=area["name"], slot=slot, id=ident,
                              name=name, year=year, prerequisite=previous, effects=effects,
                              description=description, cost_units=cost))
            previous = ident
    if len(areas) == 22:
        for offset, (branch, picture, techs) in enumerate(NEW_AREAS):
            index = 22+offset
            output.append(f"[{branch} {index}]\r\nPicName={picture}\r\n")
            for slot, (ident, year, previous, chance, cost, name, effect) in enumerate(sorted(techs, key=lambda t: t[1])):
                effects = effect.split("/") if effect.startswith("Get") else []
                description = ", ".join(LABELS[e] for e in effects) if effects else effect
                output.append(f"{name};{year};N;{chance};{cost};{ident};{description};{previous}\r\n")
                nodes.append(dict(area=index, branch=branch, slot=slot, id=ident, name=name, year=year,
                                  prerequisite=previous, effects=effects, description=description, cost_units=cost))
    result = "".join(output).encode("ascii")
    known = {row["id"] for area in parse(result) for row in area["rows"]}
    if any(node["prerequisite"] not in known for node in nodes):
        raise ValueError("Modern research prerequisite is missing.")
    return result, nodes


def build():
    import json
    payload, nodes = render()
    target = PACKAGE/"Files/Data/ResearchAreas3.dat"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    report = {"schema": 1, "new_technologies": len(nodes), "branches_extended": len(BRANCHES),
              "max_levels_per_area": MAX_LEVELS, "last_research_year": 2030,
              "sha256": hashlib.sha256(payload).hexdigest(), "nodes": nodes}
    (PACKAGE/"research-index.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    import json
    r = build()
    print(json.dumps({k: v for k, v in r.items() if k != "nodes"}))
