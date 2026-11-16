"""Native gun calibres 21-40 in. Phase 1: the gun data table. Phase 2: each nation's gun quality levels.

The game keeps one 0x100-byte block per calibre 2-20 at 0xA23634: a vertical-penetration header and 30
vertical penetrations (Data/VerPen.dat), 30 deck penetrations at +0x7C (HorPen.dat), and the rate of fire as a
float at +0xF4 and the maximum range at +0xFC (Gundata.dat). The native loader reads those files at startup,
before adapters attach, and stops at 20 in. This module moves the table to a block for calibres 2-40: the native
rows are copied, rows 21-40 come from the same files with the loader's own conversions, and the loader, every
calibre-scaled read and the 20 in clamps and guards are pointed at it.

Each nation (TBuilderNation) holds a quality level per calibre, Guns[2..20] at +0x125 (-2..2 developed, 9 not
yet), with other fields right after it. The array moves past the native object: the class's NewInstance slot
allocates Guns[0..41] there, and every access to it is pointed at the new place. Nations are created only from
main-menu actions, after adapters attach. Saves keep the Guns<c> keys, now to 40 (older saves read 9 for 21-40).

Phase 3 makes 21-40 in reachable. Research develops them in order after 20 in, each no earlier than
FIRST_YEAR + YEARS_PER_INCH per inch (scaled by the campaign's research speed like the native gates). The
designer's ordnance records (Data/OrdnanceTable.dat: gun and turret weight, cost, shell weight) move to a block
for 0-42; rows 21-40 come from OrdnanceTable40.dat, because the native loader warns about any row above 20. The
main calibre box goes to 40, and crew per gun, the overgunned and wing-position displacement minimums and the
low-ammunition note treat 21-40 in as bigger guns instead of falling to their defaults. In battle the game uses
calibres 30-33 as missile codes and the railgun adapter's super-heavy missile hits as 40, so only shells fired by
FireGuns use the table above 20 in: missiles and bombs keep the native 20 in clamp and code conversion.
"""
import json
import struct
import time
from pathlib import Path

REFERENCE = 0x301000
TABLE = 0xA23634                 # calibre 2 block
BLOCK, NATIVE_MAX, MAX_CALIBRE = 0x100, 20, 40
VERPEN_FACTOR = 0xA7CAA8         # loader: first VerPen field * [this] / 10
ROF_DIVISOR = 0x9200C8           # loader: Gundata rate of fire / this float (10.0)
# Instructions holding a table address: (site, native bytes with the reference address, offset of that address).
TABLE_REFS = (
    (0x91FB6E, "c745ec3436a200", 3),          # loader: VerPen rows
    (0x91FC66, "beb036a200", 1),              # loader: HorPen rows (+0x7C)
    (0x91FD15, "bb2837a200", 1),              # loader: Gundata rows (+0xF4)
    (0x91D904, "8d04c53436a200", 3),          # penetration accessor: vertical
    (0x91D91A, "8d04c53436a200", 3),          # penetration accessor: deck
    (0x8EF8DE, "693cc53434a200e8030000", 3),  # GetHitChance: VerPen header
    (0x8F7213, "693cc53434a200e8030000", 3),  # HandleHit: VerPen header
    (0x8F37FB, "d804c52835a200", 3),          # GetROF: rate of fire
    (0x9163BC, "db04c53035a200", 3),          # SelectAmmoType: maximum range
    (0x93172B, "691cc53035a200e8030000", 3),  # GetShipTypeHintText: maximum range
)
# Calibre limits: (site, native bytes, offset of the immediate, immediate size, new value).
LIMITS = (
    (0x91FBFA, "837df015", 3, 1, MAX_CALIBRE+1),     # loader loops end after 20
    (0x91FCAD, "837df015", 3, 1, MAX_CALIBRE+1),
    (0x91FD78, "837df015", 3, 1, MAX_CALIBRE+1),
    (0x916309, "83fa14", 2, 1, MAX_CALIBRE),         # SetCalibre (battle ship from its design) clamps to 2..20
    (0x916318, "83fa14", 2, 1, MAX_CALIBRE),
    (0x91631D, "ba14000000", 1, 4, MAX_CALIBRE),
    (0x93171D, "83e813", 2, 1, MAX_CALIBRE-1),       # GetShipTypeHintText: calibre-2 below 19
)   # The penetration clamp and HandleHit's table guard also serve missiles: hooks below (pen_clamp, hit_table).

NATION_VMT, NATION_SIZE = 0x6FF20C, 0xBC00      # TBuilderNation (no subclasses); InstanceSize stays native
NATIVE_GUNS, GUNS = 0x11D, NATION_SIZE          # Guns[c] at nation + base + 4c: native 2-20, moved 0-41
GUN_SLOTS, UNDEVELOPED = MAX_CALIBRE+2, 9       # 41 too: the AI checks one calibre up
NEW_INSTANCE, GET_MEM, INIT_INSTANCE = 0x3099B4, 0x306EB0, 0x309AE0
NEW_INSTANCE_CODE = "538bd88b43cce8f1d4ffff8bd08bc3e8180100005bc3"   # GetMem(InstanceSize); InitInstance
GUN_LOOPS = (                                                          # loops over Guns[2..20]
    (0x72091F, "83ff15", 2, 1, MAX_CALIBRE+1),     # LoadMe: Guns<c> keys while c < 21
    (0x72527D, "837dfc15", 3, 1, MAX_CALIBRE+1),   # SaveMe
    (0x71F060, "83fa15", 2, 1, MAX_CALIBRE+1),     # GetLargestGunCalibre (designer, AI design)
    (0x71E155, "83f815", 2, 1, MAX_CALIBRE+1),     # CountResearchLevels
    (0x76157C, "83fb15", 2, 1, MAX_CALIBRE+1),     # DisplayNationData: developed calibres
    (0x7B4A19, "837de415", 3, 1, MAX_CALIBRE+1),   # BuyTechnology offers
    (0x79CDE9, "83fb15", 2, 1, MAX_CALIBRE+1),     # DoGunResearch: first undeveloped calibre (year gate hook)
    (0x5AA244, "83fb15", 2, 1, MAX_CALIBRE+1),     # FillResearchList (dispersion flag hook)
    (0x957EF3, "83f814", 2, 1, MAX_CALIBRE),       # AI design: a battery may change to calibres 2..20
    (0x76D9A2, "b813000000", 1, 4, MAX_CALIBRE+1), # SpySuccess gun theft: calibre = Random(19) ...
    (0x76D9F8, "b813000000", 1, 4, MAX_CALIBRE+1),
    (0x76DA4A, "b813000000", 1, 4, MAX_CALIBRE+1),
    (0x76DA73, "b813000000", 1, 4, MAX_CALIBRE+1),
    (0x76D9B3, "83e813", 2, 1, MAX_CALIBRE-1),     # ... used while calibre-2 < 19 ...
    (0x76DA09, "83e813", 2, 1, MAX_CALIBRE-1),
    (0x76DA5B, "83e813", 2, 1, MAX_CALIBRE-1),
    (0x76DA84, "83e813", 2, 1, MAX_CALIBRE-1),
    (0x76DAD4, "83fe15", 2, 1, MAX_CALIBRE+1),     # ... and below 21
    (0x957CFA, "83fe14", 2, 1, MAX_CALIBRE),       # AI SetBatteryCalibre: above 20 shows an error box
    (0x957E75, "b812000000", 1, 4, MAX_CALIBRE),   # AI battleship calibre cap 18 (upsizing past 16: ai_bigger)
)
# Every nation Guns access (site, native instruction): [r + r*4 + 0x11D] by calibre (0x115, 0x119, 0x121 for
# two down, one down, one up) and [r + 0x125..0x16D] for one calibre, in research, spies, the designer, AI
# design and rebuilds, custom-battle years, the fort list, and the nation's load and save.
GUN_SITES = (
    (0x5aa1d8, "8bbc981d010000"), (0x5aa571, "8b8c821d010000"), (0x5be046, "83bc901d01000009"), (0x5ccedc, "8b94911d010000"),
    (0x5ccf06, "8b94911d010000"), (0x5ccf30, "8b94911d010000"), (0x5d0749, "8b94911d010000"), (0x5d0823, "8b94911d010000"),
    (0x5d083f, "8b94911d010000"), (0x5d0897, "8b94911d010000"), (0x5d14c4, "c784821d01000002000000"), (0x5d4482, "8b84821d010000"),
    (0x5d4c3c, "83bc821d01000002"), (0x5d5e7c, "83bc821d01000009"), (0x5d5eee, "83bc821d01000009"), (0x5d6e1b, "83bc821d01000003"),
    (0x5d6e39, "8b84821d010000"), (0x5d6ea3, "8b84821d010000"), (0x5e5ab0, "8b94911d010000"), (0x5e5af0, "8b84821d010000"),
    (0x5e5b0c, "8b84821d010000"), (0x5e5b6e, "8b94911d010000"), (0x5e5da0, "8b94911d010000"), (0x5e5de3, "8b84821d010000"),
    (0x5e5dff, "8b84821d010000"), (0x5e5e60, "8b94911d010000"), (0x5ebf65, "8b84901d010000"), (0x5f7f9c, "8b84821d010000"),
    (0x5f7fed, "83bcb81d01000009"), (0x5f8086, "8b94911d010000"), (0x6a9838, "898235010000"), (0x6a9848, "898249010000"),
    (0x6a9850, "89824d010000"), (0x6a9858, "89823d010000"), (0x6a9860, "898241010000"), (0x6a9868, "898245010000"),
    (0x6a9878, "898251010000"), (0x6a9888, "898255010000"), (0x6a9898, "898259010000"), (0x6a98a8, "89825d010000"),
    (0x6a98b6, "c7823501000001000000"), (0x6a98d3, "898265010000"), (0x6e2ca9, "83bb3101000009"), (0x6e2cde, "83bb3901000009"),
    (0x6e2cfd, "83bb3d01000009"), (0x6e2d1c, "83bb4101000009"), (0x6e2d3b, "83bb4501000009"), (0x6e2d5a, "83bb4901000009"),
    (0x6e2d79, "83bb4d01000009"), (0x6e2da8, "8b834d010000"), (0x6e2dcb, "8b8351010000"), (0x6e2dee, "8b8355010000"),
    (0x71e131, "8b94831d010000"), (0x71f04c, "8b8c901d010000"), (0x720917, "8984bb1d010000"), (0x723578, "83bc901d01000009"),
    (0x725216, "8b84831d010000"), (0x7614c3, "8b849e1d010000"), (0x762033, "8b84bb1d010000"), (0x76209e, "8b84bb1d010000"),
    (0x763e0c, "83bb5101000009"), (0x763e15, "83bb51010000ff"), (0x763e1e, "83bb5501000009"), (0x763e27, "83bb55010000ff"),
    (0x7645ea, "83bb3501000000"), (0x7645f3, "83bb3101000000"), (0x76462d, "8994831d010000"), (0x764646, "83bb4901000000"),
    (0x76464f, "83bb4d01000000"), (0x764699, "8994831d010000"), (0x7646af, "83bb3d01000000"), (0x7646b8, "83bb4101000000"),
    (0x7646f2, "8994831d010000"), (0x765bdc, "83bb5101000009"), (0x765be5, "83bb51010000ff"), (0x765bf2, "83bb5501000009"),
    (0x765bfb, "83bb55010000ff"), (0x765cae, "83bcb31d01000009"), (0x765d0e, "8984b31d010000"), (0x765d36, "83bb5901000009"),
    (0x765d3f, "83bb59010000ff"), (0x765d4c, "83bb5d01000009"), (0x765d55, "83bb5d010000ff"), (0x765e08, "83bcb31d01000009"),
    (0x765e68, "8984b31d010000"), (0x76639f, "83bcb31d010000ff"), (0x7663b6, "c784b31d010000ffffffff"), (0x766466, "83bc831d01000000"),
    (0x76647b, "8994831d010000"), (0x7664a4, "83bc831d01000000"), (0x7664b7, "c784831d01000001000000"), (0x76658a, "83bcb31d01000000"),
    (0x7665ab, "8984b31d010000"), (0x766644, "83bcb31d01000000"), (0x766650, "8984b31d010000"), (0x76666d, "83bb3501000000"),
    (0x7666b3, "898335010000"), (0x7667a0, "83bcb31d01000000"), (0x7667aa, "83bb3501000000"), (0x7667d8, "83bcb31d01000000"),
    (0x7667fa, "83bc831d01000000"), (0x766816, "83bb3501000000"), (0x76685f, "83bcb31d01000001"), (0x766874, "c784b31d01000001000000"),
    (0x76d740, "83bcb01d01000009"), (0x76d758, "83bcb01d01000009"), (0x76d76f, "8b84b01d010000"), (0x76d782, "3b94b01d010000"),
    (0x76d803, "8b84b01d010000"), (0x76d816, "3b94b01d010000"), (0x76d9c5, "83bcb01d01000009"), (0x76d9d8, "83bcb01d010000ff"),
    (0x76d9ec, "8b84b01d010000"), (0x76da17, "83bcb01d01000009"), (0x76da2a, "83bcb01d010000ff"), (0x76da3e, "8b84b01d010000"),
    (0x76da69, "83bcb01d01000009"), (0x76da92, "83bcb01d01000009"), (0x76daa5, "8b84b01d010000"), (0x76dab8, "3b94b01d010000"),
    (0x76db20, "8b84b01d010000"), (0x76db72, "ffb4b01d010000"), (0x76db84, "8994b01d010000"), (0x77739e, "8b84b31d010000"),
    (0x7773ef, "8b84b31d010000"), (0x77863e, "83b831010000ff"), (0x77864a, "83b83101000009"), (0x779755, "83bc822101000009"),
    (0x779902, "83bc822101000009"), (0x77aa91, "83bc901d01000009"), (0x77aafc, "83bc901d01000009"), (0x77df6c, "83bc9e1d01000009"),
    (0x77df97, "83bc9e1d01000009"), (0x77f858, "83bc821d010000fe"), (0x77f87e, "83bc822101000000"), (0x77f88e, "83bc822101000009"),
    (0x77f8a3, "8b848219010000"), (0x77f8bf, "8b848215010000"), (0x780426, "8b84901d010000"), (0x79c9b0, "83bc9e1d01000009"),
    (0x79cb82, "c7849e1d01000001000000"), (0x79cb9e, "c7849e1d010000ffffffff"), (0x79cbad, "89849e1d010000"), (0x79cbdb, "c7849e1d010000ffffffff"),
    (0x79cbf9, "c7849e1d010000ffffffff"), (0x79cc17, "c7849e1d010000ffffffff"), (0x79cc35, "c7849e1d010000ffffffff"), (0x79cc53, "c7849e1d010000ffffffff"),
    (0x79cc71, "c7849e1d010000ffffffff"), (0x79cc8f, "c7849e1d010000ffffffff"), (0x79ccad, "c7849e1d010000ffffffff"), (0x79ccc5, "c7849e1d010000ffffffff"),
    (0x79ccdd, "c7849e1d010000feffffff"), (0x79cd0b, "c7849e1d010000feffffff"), (0x79cd18, "c7849e1d010000ffffffff"), (0x79cd47, "8b849e1d010000"),
    (0x79d00c, "83bc811d01000000"), (0x79d0a7, "83b84d01000000"), (0x79d0b3, "83b84901000000"), (0x79d0e7, "83b83101000000"),
    (0x79d19d, "83b84d010000ff"), (0x79d1b3, "8b84b81d010000"), (0x79d1c7, "83b84d010000ff"), (0x79d1e9, "83b849010000ff"),
    (0x79d215, "83b84d01000009"), (0x79d221, "83b84901000009"), (0x79d234, "83b84501000009"), (0x79d24c, "83bcb81d01000001"),
    (0x79d28e, "8b84b81d010000"), (0x79d2ee, "83bcb81d010000ff"), (0x79d32c, "83bcb81d010000ff"), (0x79d369, "8b84b81d010000"),
    (0x79d378, "c784b81d010000feffffff"), (0x79d38d, "c784b81d010000ffffffff"), (0x79d3aa, "8b84b81d010000"), (0x79d3b9, "c784b81d010000feffffff"),
    (0x79d3ce, "c784b81d010000ffffffff"), (0x79d3e3, "8994b81d010000"), (0x79d495, "c784b81d01000001000000"), (0x79d511, "c784b81d01000002000000"),
    (0x7b4531, "83bc901d01000009"), (0x7b454b, "8b84901d010000"), (0x7b455b, "3b848a1d010000"), (0x7b458b, "8b9c901d010000"),
    (0x7b464e, "8b84901d010000"), (0x7b475c, "8b84901d010000"), (0x7b476c, "8984931d010000"), (0x7b47e9, "83bc901d01000009"),
    (0x7b4800, "83bc901d01000009"), (0x7b482d, "8b84901d010000"), (0x7b49a8, "899c901d010000"), (0x7d3e70, "83bb4d01000009"),
    (0x7d3e79, "8b834d010000"), (0x7d3e7f, "3b8349010000"), (0x7e4779, "83b83501000000"), (0x7e478e, "83b83101000000"),
    (0x7eeb60, "83bc821d01000005"), (0x7eeb6d, "83bc821901000005"), (0x7eeb80, "8b84821d010000"), (0x7eeb90, "8b84821d010000"),
    (0x81a24f, "8b84861d010000"), (0x81a266, "8b84861d010000"), (0x94c1cf, "8b848221010000"), (0x955208, "83bc901d01000009"),
    (0x955227, "83bc821501000009"), (0x9552b1, "8b84821d010000"), (0x9561b7, "83bc821d01000009"), (0x95621f, "83bc821d01000009"),
    (0x9562a2, "83bc821d01000009"), (0x956745, "83bc821d010000ff"), (0x9567a2, "83bc822101000000"), (0x9567b4, "83bc822101000009"),
    (0x956816, "83bc821901000000"), (0x956828, "83bc821901000009"), (0x957d41, "8b84b01d010000"), (0x957f00, "8b94821d010000"),
    (0x957f0f, "83bc821d01000003"),
)

# Designer ordnance records, one per calibre: Cal, Cat letter, weight and cost*3 floats, shell weight, turret factors
# (casemate, 1-3 barrels). Native records 0-20 at 0xA7FDE4; aircraft globals follow at 0xA80104.
ORDNANCE, RECORD, ORDNANCE_SLOTS = 0xA7FDE4, 0x26, MAX_CALIBRE+3     # 41, 42: CalChangeOK reads two calibres up
ORDNANCE_FILE = "OrdnanceTable40.dat"                                  # rows 21-40, same columns as OrdnanceTable.dat
ORDNANCE_REFS = (                                                       # (site, native, offset of the address)
    (0x93BF90, "d80445eefda700", 3), (0x93BFDF, "d80c45eefda700", 3), (0x93C006, "d80445eefda700", 3),
    (0x93C2F0, "d80c45eefda700", 3), (0x93C3BA, "d80c45eefda700", 3), (0x93C472, "d80c45eefda700", 3),
    (0x93C504, "d80c45eefda700", 3),                                   # GetArmamentWeights: cost
    (0x93CA1D, "db0475fafda700", 3), (0x93CA4D, "d90475eafda700", 3), (0x93CBB5, "d90475eafda700", 3),   # secondary
    (0x946358, "8b0445f2fda700", 3), (0x9463B8, "8b0445f2fda700", 3), (0x946429, "8b0445f2fda700", 3),   # ammo
    (0x9497B1, "8d145530fea700", 3), (0x949713, "bf30fea700", 1),     # GetOKGunCombos, CalChangeOK
    (0x94E46D, "890455e4fda700", 3), (0x94E48C, "66890455e8fda700", 4), (0x94E4B7, "d91c45eafda700", 3),
    (0x94E4E5, "d91c45eefda700", 3), (0x94E50A, "890455fafda700", 3), (0x94E52E, "890455fefda700", 3),
    (0x94E552, "89045502fea700", 3), (0x94E576, "890455f6fda700", 3), (0x94E59A, "890455f2fda700", 3),   # loader
    (0x950B17, "d80c45eefda700", 3), (0x950B46, "8b0445fafda700", 3), (0x950B7D, "d90445eafda700", 3),  # cost, turret
)
ORDNANCE_TOP = (0x949794, "c745f4f200a800", 3)          # GetOKGunCombos starts at the 20 in record's TF1 ...
ORDNANCE_LIMITS = ((0x94979F, "bb14000000", 1, 4, MAX_CALIBRE),)   # ... and counts down from 20

# Research: calibres above 20 come no earlier than FIRST_YEAR + YEARS_PER_INCH per inch (40 in: 2000).
FIRST_YEAR, YEARS_PER_INCH = 1943, 3
YEAR_GATE = 0x84AD98            # native: year adjusted for the campaign's research speed
FIREGUNS_RET = 0x909974         # HandleHit's return address for shells fired by FireGuns
PENCHECK_RET = 0x91E249         # the penetration accessor's return address inside PenetrationCheck
INT_TO_STR = 0x328C80
# Hooks: (name, site, native bytes, kind). jmp: E9 to the code page and NOPs; ja: the jump's target moves there.
HOOKS = (
    ("research_gate", 0x79C9BE, "83fb117405", "jmp"),               # DoGunResearch: cmp ebx,17; je
    ("research_list", 0x5AA20E, "83fb087c23", "jmp"),               # FillResearchList: dispersion flags from 8 in
    ("hit_table", 0x8F71F1, "837d24140f8f8f000000", "jmp"),         # HandleHit: VerPen table path up to 20 in
    ("hit_code", 0x8F72A9, "8b45248945fc", "jmp"),                  # HandleHit: hit code kept for missile checks
    ("hit_log", 0x901CEC, "8b45fce88c6fa2ff", "jmp"),               # HandleHit: damage log "N in ... yds"
    ("pen_clamp", 0x91D8D5, "837dfc147e07c745fc14000000", "jmp"),   # penetration accessor: calibre to 20
    ("crew", 0x93E6D7, "0f87cd000000", "ja"),                       # crew per gun: above 20 -> 10
    ("overgunned", 0x94782A, "0f87d7000000", "ja"),                 # CheckOvergunned: above 20 -> 5000 t
    ("improve", 0x79D20D, "83ff0d7c37", "jmp"),                     # ImproveExistingGuns: calibre picked (2-17)
    ("ai_bigger", 0x779364, "837b6d100f8d3d010000", "jmp"),         # AI battleship upsizing stops at 16 in
)
IMPROVE_SHARE, RANDOM = 4, 0x307834   # 1 in 4 improvements go to a developed 21-40 in gun below quality 2
# The AI keeps upsizing a battleship's main guns past 16 in only while it earns more than it spends each month and
# holds RESERVE_MONTHS of budget in cash; spare tonnage, development and quality checks stay native.
MONTHLY_BALANCE, MODIFIED_BUDGET, FUNDS, RESERVE_MONTHS = 0x72D2EC, 0x71F06C, 0x1B5, 2
# Ship type rules (SuggestShipType: a battleship needs 3+ main turrets or 8+ main guns) count a main gun above
# 20 in as (calibre/20)^3 guns, its shell weight against a 20 in gun (user's choice 2026-11-08).
COUNT_GUNS = 0x94F564
FIREPOWER_CALLS = ((0x94674E, "e8118e0000"), (0x9467E5, "e87a8d0000"), (0x946A52, "e80d8b0000"), (0x946B9A, "e8c5890000"),
                   (0x946C2C, "e833890000"), (0x946C5D, "e802890000"), (0x946D78, "e8e7870000"), (0x946E33, "e82c870000"),
                   (0x946F3F, "e820860000"), (0x946FB7, "e8a8850000"), (0x94700A, "e855850000"))
# In-place switch defaults (site, native ja, new target): above 20 in as 20 in.
RETARGETS = ((0x732957, "0f87e3000000", 0x732A37),     # GunPosOK: wing positions need 40000 t
             (0x5D6EE9, "0f87b4000000", 0x5D6F8D))     # cbTypeChange: "ammo allowance on the low side" below 70
CODE = dict(allocator=0x000, research_gate=0x080, research_list=0x100, hit_table=0x180, hit_code=0x200,
            hit_log=0x280, pen_clamp=0x300, crew=0x380, overgunned=0x400, improve=0x480, ai_bigger=0x580,
            firepower=0x600, size=0x680)
MAIN, NATIONS, SPIN_VMT, SPIN_MAX = 0xA23000, 0xAE4, 0x58F214, 0x30C   # main global, its nation TList, TSpinEdit
LAYOUT = dict(table=0x0000, ordnance=0x2800, code=0x3000, size=0x4000)
REPORT = Path(__file__).with_name("big_guns_report.json")


def limited(native, at, size, value):
    return native[:at]+value.to_bytes(size, "little")+native[at+size:]


def moved(native):
    """A nation Guns access with its displacement moved from the native array to GUNS."""
    hits = [d for d in range(NATIVE_GUNS-8, NATIVE_GUNS+4*NATIVE_MAX+1, 4) if native.count(struct.pack("<I", d)) == 1]
    if len(hits) != 1: raise ValueError("Not a nation gun level access: "+native.hex())
    return native.replace(struct.pack("<I", hits[0]), struct.pack("<I", hits[0]-NATIVE_GUNS+GUNS))


def limit_changes(limits):
    return [(site, bytes.fromhex(native), limited(bytes.fromhex(native), at, size, value))
            for site, native, at, size, value in limits]


def gun_changes():
    return [(site, bytes.fromhex(native), moved(bytes.fromhex(native))) for site, native in GUN_SITES]+limit_changes(GUN_LOOPS)


def retarget_changes():
    return [(site, bytes.fromhex(native), b"\x0f\x87"+struct.pack("<i", target-site-6)) for site, native, target in RETARGETS]


def checked(blob, base, changes, label):
    """Patch plans for in-place changes (none holds an address, so they do not relocate)."""
    from hull_rules import patch
    delta, out = base-REFERENCE, []
    for site, old, new in changes:
        if blob[site+delta-base:site+delta-base+len(old)] != old:
            raise ValueError(f"Unsupported native code for {label} at {site:#x}.")
        out.append(patch(f"{label} ({site:#x})", site+delta, old, new))
    return out


def address_plans(blob, base, refs, old_table, new_table, label, shift=0):
    """Patch plans moving instructions that hold an address in old_table to the same offset in new_table (+shift)."""
    from hull_rules import patch
    delta, out = base-REFERENCE, []
    for site, native, at in refs:
        old = bytearray.fromhex(native)
        reference = struct.unpack_from("<I", old, at)[0]
        struct.pack_into("<I", old, at, reference+delta)
        if blob[site+delta-base:site+delta-base+len(old)] != old: raise ValueError(f"Unsupported native {label} at {site:#x}.")
        new = bytearray(old); struct.pack_into("<I", new, at, new_table+reference-old_table+shift)
        out.append(patch(f"{label} ({site:#x})", site+delta, bytes(old), bytes(new)))
    return out


def plans(blob, base, new_table):
    """Patch plans pointing the game at new_table (the calibre-2 block of a table for 2-40)."""
    return (address_plans(blob, base, TABLE_REFS, TABLE, new_table, f"gun table for calibres to {MAX_CALIBRE} in")
            + checked(blob, base, limit_changes(LIMITS), f"Calibre limit {MAX_CALIBRE} in"))


def ordnance_plans(blob, base, new_ordnance):
    """Patch plans pointing the designer at new_ordnance (record 0 of records 0-42)."""
    label = f"ordnance records to {MAX_CALIBRE} in"
    return (address_plans(blob, base, ORDNANCE_REFS, ORDNANCE, new_ordnance, label)
            + address_plans(blob, base, (ORDNANCE_TOP,), ORDNANCE, new_ordnance, label, (MAX_CALIBRE-NATIVE_MAX)*RECORD)
            + checked(blob, base, limit_changes(ORDNANCE_LIMITS), label))


def allocator(address, base):
    """TBuilderNation.NewInstance at address: the native object plus Guns[0..41], 9 (not developed) except 2-20,
    which start at 0 as InitInstance leaves the native array."""
    from campaign_security import Code
    delta, c = base-REFERENCE, Code(address)
    c.emit(b"\x53\x8b\xd8\xb8"); c.u32(GUNS+4*GUN_SLOTS); c.branch(b"\xe8", GET_MEM+delta)   # EBX class
    c.emit(b"\x57\x8b\xd0\x8d\xb8"); c.u32(GUNS); c.emit(b"\xb8"); c.u32(UNDEVELOPED)
    c.emit(b"\xb9"); c.u32(GUN_SLOTS); c.emit(b"\xf3\xab")                                    # Guns[0..41] := 9
    c.emit(b"\x8d\xba"); c.u32(GUNS+8); c.emit(b"\x33\xc0\xb9"); c.u32(NATIVE_MAX-1)
    c.emit(b"\xf3\xab\x5f\x8b\xc3"); c.branch(b"\xe8", INIT_INSTANCE+delta); c.emit(b"\x5b\xc3")   # (class, object)
    return c.finish()


def nation_plans(blob, base, new_instance):
    """Patch plans giving every nation Guns[0..41] past its native fields (new_instance: allocator's address)."""
    from hull_rules import patch
    delta = base-REFERENCE
    def live(site, size): return blob[site+delta-base:site+delta-base+size]
    slot = struct.pack("<I", NEW_INSTANCE+delta)
    if (struct.unpack("<i", live(NATION_VMT-0x34, 4))[0] != NATION_SIZE or live(NATION_VMT-0x0C, 4) != slot
            or live(NEW_INSTANCE, len(NEW_INSTANCE_CODE)//2) != bytes.fromhex(NEW_INSTANCE_CODE)):
        raise ValueError("Unsupported native nation class.")
    return ([patch("Nation gun levels: allocator", NATION_VMT-0x0C+delta, slot, struct.pack("<I", new_instance))]
            + checked(blob, base, gun_changes(), f"Nation gun levels to {MAX_CALIBRE} in"))


def code(page, base):
    """{name: code} for the code page: the nation allocator and every hook (each within its CODE slot)."""
    from campaign_security import Code
    d, out = base-REFERENCE, dict(allocator=allocator(page+CODE["allocator"], base))
    def at(name): return Code(page+CODE[name])
    fire = struct.pack("<I", FIREGUNS_RET+d)

    c = at("research_gate")   # EBX the first undeveloped calibre, EDI the year pointer
    c.emit(b"\x83\xfb"+bytes([NATIVE_MAX])); c.branch(b"\x0f\x8e", "native")
    c.emit(b"\x6b\xc3"+bytes([YEARS_PER_INCH])+b"\x05"); c.u32(FIRST_YEAR-(NATIVE_MAX+1)*YEARS_PER_INCH)
    c.branch(b"\xe8", YEAR_GATE+d); c.emit(b"\x3b\x07"); c.branch(b"\x0f\x8f", 0x79C9EE+d)   # too early: no research
    c.branch(b"\xe9", 0x79C9C3+d)
    c.mark("native"); c.emit(b"\x83\xfb\x11"); c.branch(b"\x0f\x84", 0x79C9C8+d); c.branch(b"\xe9", 0x79C9C3+d)
    out["research_gate"] = c.finish()

    c = at("research_list")   # EBX calibre: the dispersion flags exist for 8-20 in only
    c.emit(b"\x83\xfb\x08"); c.branch(b"\x0f\x8c", 0x5AA236+d)
    c.emit(b"\x83\xfb"+bytes([NATIVE_MAX])); c.branch(b"\x0f\x8f", 0x5AA236+d); c.branch(b"\xe9", 0x5AA213+d)
    out["research_list"] = c.finish()

    c = at("hit_table")       # HandleHit frame: [ebp+24h] calibre, [ebp+4] caller
    c.emit(b"\x83\x7d\x24"+bytes([NATIVE_MAX])); c.branch(b"\x0f\x8e", 0x8F71FB+d)
    c.emit(b"\x83\x7d\x24"+bytes([MAX_CALIBRE])); c.branch(b"\x0f\x8f", 0x8F728A+d)
    c.emit(b"\x81\x7d\x04"+fire); c.branch(b"\x0f\x85", 0x8F728A+d); c.branch(b"\xe9", 0x8F71FB+d)
    out["hit_table"] = c.finish()

    c = at("hit_code")        # [ebp-4] keeps the hit code; a big shell reads as 20 in there (missiles: 30-33)
    c.emit(b"\x8b\x45\x24\x83\xf8"+bytes([NATIVE_MAX])); c.branch(b"\x0f\x8e", "store")
    c.emit(b"\x81\x7d\x04"+fire); c.branch(b"\x0f\x85", "store"); c.emit(b"\xb8"); c.u32(NATIVE_MAX)
    c.mark("store"); c.emit(b"\x89\x45\xfc"); c.branch(b"\xe9", 0x8F72AF+d)
    out["hit_code"] = c.finish()

    c = at("hit_log")         # the damage log names the shell's own calibre
    c.emit(b"\x8b\x45\xfc\x83\xf8"+bytes([NATIVE_MAX])); c.branch(b"\x0f\x85", "text"); c.emit(b"\x8b\x45\x24")
    c.mark("text"); c.branch(b"\xe8", INT_TO_STR+d); c.branch(b"\xe9", 0x901CF4+d)
    out["hit_log"] = c.finish()

    c = at("pen_clamp")       # accessor frame: [ebp-4] calibre; PenetrationCheck -> HandleHit -> caller
    c.emit(b"\x83\x7d\xfc"+bytes([NATIVE_MAX])); c.branch(b"\x0f\x8e", "back")
    c.emit(b"\x81\x7d\x04"); c.u32(PENCHECK_RET+d); c.branch(b"\x0f\x85", "gun")   # designer lists: guns
    c.emit(b"\x8b\x45\x00\x8b\x00\x81\x78\x04"+fire); c.branch(b"\x0f\x84", "gun")
    c.emit(b"\xc7\x45\xfc"); c.u32(NATIVE_MAX); c.branch(b"\xe9", "back")           # missiles, bombs: native
    c.mark("gun"); c.emit(b"\x83\x7d\xfc"+bytes([MAX_CALIBRE])); c.branch(b"\x0f\x8e", "back")
    c.emit(b"\xc7\x45\xfc"); c.u32(MAX_CALIBRE)
    c.mark("back"); c.branch(b"\xe9", 0x91D8E2+d)
    out["pen_clamp"] = c.finish()

    c = at("crew")            # EAX calibre above 20 (unsigned): 2 more per inch from 56 at 20 in
    c.emit(b"\x83\xf8"+bytes([MAX_CALIBRE])); c.branch(b"\x0f\x87", 0x93E7AA+d)
    c.emit(b"\x8d\x04\x45"); c.u32(16); c.emit(b"\xc3")
    out["crew"] = c.finish()

    c = at("overgunned")      # EAX adjusted calibre, EDI design, ESI minimum displacement
    c.emit(b"\x83\x7f\x6d"+bytes([NATIVE_MAX])); c.branch(b"\x0f\x8e", 0x947907+d)   # native designs: native
    c.emit(b"\x69\xf0"); c.u32(2000); c.emit(b"\x81\xee"); c.u32(8000); c.branch(b"\xe9", 0x947907+d)
    out["overgunned"] = c.finish()

    c = at("improve")         # EDI the calibre ImproveExistingGuns picked, [ebp-4] the nation
    def big_level(reg, skip):  # [edx+ebx*4+GUNS] into reg (0 eax, 1 ecx): skip unless -3..1 (improvable)
        c.emit(bytes([0x8b, 0x84 | reg << 3, 0x9a])); c.u32(GUNS)
        c.emit(bytes([0x83, 0xf8 | reg, 0x01])); c.branch(b"\x0f\x8f", skip)
        c.emit(bytes([0x83, 0xf8 | reg, 0xfd])); c.branch(b"\x0f\x8c", skip)
    c.emit(b"\x53\x8b\x55\xfc\x33\xc9\xbb"); c.u32(NATIVE_MAX+1)              # count improvable 21-40 in guns
    c.mark("count"); big_level(0, "next"); c.emit(b"\x41")
    c.mark("next"); c.emit(b"\x43\x83\xfb"+bytes([MAX_CALIBRE+1])); c.branch(b"\x0f\x8c", "count")
    c.emit(b"\x85\xc9"); c.branch(b"\x0f\x84", "native")
    c.emit(b"\x51\xb8"); c.u32(IMPROVE_SHARE); c.branch(b"\xe8", RANDOM+d); c.emit(b"\x59\x85\xc0"); c.branch(b"\x0f\x85", "native")
    c.emit(b"\x8b\xc1"); c.branch(b"\xe8", RANDOM+d)                            # which one
    c.emit(b"\x8b\x55\xfc\xbb"); c.u32(NATIVE_MAX+1)
    c.mark("find"); big_level(1, "skip"); c.emit(b"\x48"); c.branch(b"\x0f\x88", "found")
    c.mark("skip"); c.emit(b"\x43\x83\xfb"+bytes([MAX_CALIBRE+1])); c.branch(b"\x0f\x8c", "find"); c.branch(b"\xe9", "native")
    c.mark("found"); c.emit(b"\x8b\xfb\x5b"); c.branch(b"\xe9", 0x79D249+d)    # improve it like any other gun
    c.mark("native"); c.emit(b"\x5b\x83\xff\x0d"); c.branch(b"\x0f\x8c", 0x79D249+d); c.branch(b"\xe9", 0x79D212+d)
    out["improve"] = c.finish()

    c = at("ai_bigger")       # AddStuffToAIDesign, battleship types: EBX design, [ebp-0Ch] nation
    c.emit(b"\x83\x7b\x6d\x10"); c.branch(b"\x0f\x8c", 0x77936E+d)                  # below 16 in: native
    c.emit(b"\x53\x8b\x5d\xf4\x8b\xc3"); c.branch(b"\xe8", MONTHLY_BALANCE+d)
    c.emit(b"\x85\xc0"); c.branch(b"\x0f\x8e", "no")                                # spends more than it earns
    c.emit(b"\x8b\xc3"); c.branch(b"\xe8", MODIFIED_BUDGET+d)                       # yearly budget
    c.emit(b"\x6b\xc0"+bytes([RESERVE_MONTHS])+b"\x8b\x8b"); c.u32(FUNDS)
    c.emit(b"\x6b\xc9\x0c\x3b\xc8"); c.branch(b"\x0f\x8c", "no")                    # funds*12 < budget*months
    c.emit(b"\x5b"); c.branch(b"\xe9", 0x77936E+d)                                   # native checks, then +1 in
    c.mark("no"); c.emit(b"\x5b"); c.branch(b"\xe9", 0x7794AB+d)
    out["ai_bigger"] = c.finish()

    c = at("firepower")       # CountGuns(EAX design) for the ship type rules: guns * calibre^3 / 8000 above 20 in
    c.emit(b"\x53\x8b\xd8"); c.branch(b"\xe8", COUNT_GUNS+d)
    c.emit(b"\x8b\x4b\x6d\x83\xf9"+bytes([NATIVE_MAX])); c.branch(b"\x0f\x8e", "done")
    c.emit(b"\x8b\xd1\x0f\xaf\xd1\x0f\xaf\xd1\x0f\xaf\xc2\x33\xd2\xb9"); c.u32(NATIVE_MAX**3); c.emit(b"\xf7\xf1")
    c.mark("done"); c.emit(b"\x5b\xc3")
    out["firepower"] = c.finish()

    for name, body in out.items():
        if len(body) > min(v for k, v in CODE.items() if v > CODE[name])-CODE[name]:
            raise ValueError("Big guns code exceeds its slot: "+name)
    return out


def hook_plans(blob, base, page):
    """Patch plans sending each hook site to its code on the page, and the in-place switch defaults."""
    from hull_rules import patch
    delta, out = base-REFERENCE, []
    for name, site, native, kind in HOOKS:
        old, at = bytes.fromhex(native), site+delta
        if blob[at-base:at-base+len(old)] != old: raise ValueError(f"Unsupported native code for big guns: {name}.")
        if kind == "jmp": new = b"\xe9"+struct.pack("<i", page+CODE[name]-at-5)+b"\x90"*(len(old)-5)
        else: new = b"\x0f\x87"+struct.pack("<i", page+CODE[name]-at-6)
        out.append(patch(f"Big guns: {name}", at, old, new))
    for site, native in FIREPOWER_CALLS:
        old, at = bytes.fromhex(native), site+delta
        if blob[at-base:at-base+5] != old: raise ValueError(f"Unsupported native ship type rule at {site:#x}.")
        out.append(patch(f"Big guns: firepower ({site:#x})", at, old, b"\xe8"+struct.pack("<i", page+CODE["firepower"]-at-5)))
    return out+checked(blob, base, retarget_changes(), "big guns switch default")


def native_bytes(code):
    """Normalized .text (reference addresses) with this module's code changes read back as native, so other
    adapters' audits of the same functions still match while it is attached. Unchanged code comes back as is.
    Hooks are recognised by shape (E9 and NOPs, or 0F 87): their targets depend on where the page was allocated."""
    out = None
    def restore(at, old):
        nonlocal out
        if out is None: out = bytearray(code)
        out[at:at+len(old)] = old
    for site, old, new in limit_changes(LIMITS+ORDNANCE_LIMITS)+gun_changes()+retarget_changes():
        if code[site-REFERENCE:site-REFERENCE+len(new)] == new: restore(site-REFERENCE, old)
    for name, site, native, kind in HOOKS:
        old, at = bytes.fromhex(native), site-REFERENCE
        now = code[at:at+len(old)]
        hooked = (now[:1] == b"\xe9" and now[5:] == b"\x90"*(len(old)-5)) if kind == "jmp" else now[:2] == b"\x0f\x87"
        if hooked and now != old: restore(at, old)
    for site, native in FIREPOWER_CALLS:
        old, at = bytes.fromhex(native), site-REFERENCE
        if code[at:at+1] == b"\xe8" and code[at:at+5] != old: restore(at, old)
    return code if out is None else bytes(out)


def rows(path):
    """{calibre: [fields]} from a native tab-separated table (header line first; blank fields count as 0)."""
    out = {}
    for line in Path(path).read_text(encoding="latin-1").splitlines()[1:]:
        fields = line.split("\t")
        if fields and fields[0].strip().isdigit():
            out[int(fields[0])] = [int(f) if f.strip().lstrip("-").isdigit() else 0 for f in fields]
    return out


def field(row, number):
    """The loader's 1-based field access (missing trailing fields read as 0)."""
    return row[number-1] if number-1 < len(row) else 0


def block(verpen, horpen, gundata, factor, divisor):
    """One calibre's table block, built the way the native loader builds it."""
    data = bytearray(BLOCK)
    struct.pack_into("<i", data, 0, int(field(verpen, 3)*factor/10))
    for n in range(1, 31):
        struct.pack_into("<i", data, 4*n, field(verpen, n+3))
        struct.pack_into("<i", data, 0x7C+4*(n-1), field(horpen, n+3))
    struct.pack_into("<f", data, 0xF4, field(gundata, 3)/divisor)
    struct.pack_into("<i", data, 0xFC, field(gundata, 4))
    return bytes(data)


def table(native, data_dir, factor, divisor):
    """Blocks for calibres 2-40: the native blocks for 2-20 as loaded, rows 21-40 from the data files."""
    if len(native) != (NATIVE_MAX-1)*BLOCK: raise ValueError("Unexpected native gun table size.")
    verpen, horpen, gundata = (rows(Path(data_dir)/name) for name in ("VerPen.dat", "HorPen.dat", "Gundata.dat"))
    missing = [c for c in range(NATIVE_MAX+1, MAX_CALIBRE+1) if not all(c in t for t in (verpen, horpen, gundata))]
    if missing: raise ValueError(f"The gun data files have no rows for {missing[0]}-{missing[-1]} in.")
    return native+b"".join(block(verpen[c], horpen[c], gundata[c], factor, divisor)
                           for c in range(NATIVE_MAX+1, MAX_CALIBRE+1))


def record(fields):
    """One ordnance record as the native OrdnanceTable loader stores it (StrToIntDef(field, -1))."""
    def num(n): return int(fields[n]) if fields[n].strip() == fields[n] and fields[n].lstrip("-").isdigit() else -1
    data = bytearray(RECORD)
    struct.pack_into("<iHff", data, 0, num(0), ord(fields[1][0]), float(num(2)), float(3*num(3)))   # Cal, Cat, weight, cost
    struct.pack_into("<5i", data, 0x0E, num(8), num(7), num(4), num(5), num(6))   # shell weight, TFC, TF1-TF3
    return bytes(data)


def ordnance(native, path):
    """Records 0-42: the native 0-20 as loaded, 21-40 from path (OrdnanceTable40.dat), 41-42 repeat 40."""
    if len(native) != (NATIVE_MAX+1)*RECORD: raise ValueError("Unexpected native ordnance table size.")
    found = {}
    for line in Path(path).read_text(encoding="latin-1").splitlines()[1:]:
        fields = line.split("\t")
        if len(fields) >= 9 and fields[0].isdigit(): found[int(fields[0])] = record(fields)
    if sorted(found) != list(range(NATIVE_MAX+1, MAX_CALIBRE+1)): raise ValueError(f"{ORDNANCE_FILE} needs rows 21-40.")
    return native+b"".join(found[c] for c in range(NATIVE_MAX+1, MAX_CALIBRE+1))+found[MAX_CALIBRE]*2


def attach(wait=30):
    import native_designer
    import week_display as memory
    import weekly_runtime as rt
    from hull_rules import patch
    rt.configure_api(); memory.configure()
    deadline = time.monotonic()+wait
    while True:
        games = [g for g in rt.process_candidates() if g[1] == rt.GAME/"RTW3.exe"]
        if len(games) == 1: break
        if time.monotonic() >= deadline: raise ValueError("Open the local game first.")
        time.sleep(0.5)
    pid, _ = games[0]
    handle = rt.K.OpenProcess(0x438, False, pid)
    if not handle: raise rt.win_error("Cannot open local game")
    try:
        module_base, _ = rt.module_info(pid)
        if REPORT.exists():
            saved = json.loads(REPORT.read_text(encoding="utf-8"))
            if saved.get("attached") and saved.get("pid") == pid and saved.get("base") == module_base and rt.report_is_current(REPORT, pid):
                verify(handle, saved["patches"], "replacement")
                return saved
        base, blob = rt.text_section(handle, module_base)
        delta = base-REFERENCE
        def read(address, size): return rt.read(handle, address, size)
        def u32(address): return struct.unpack("<I", read(address, 4))[0]
        main = u32(MAIN+delta)
        nations = u32(main+NATIONS) if main else 0
        if nations and u32(nations+8):
            raise ValueError("Big guns must attach before a campaign or nation is loaded. Restart through Play with mods.")
        form = native_designer.discover(blob, base, read)
        spin = u32(u32(form["slot"])+form["fields"]["seMainCal"])
        if u32(spin) != SPIN_VMT+delta or u32(spin+SPIN_MAX) != NATIVE_MAX:
            raise ValueError("Unsupported native main calibre box.")
        data = rt.GAME/"Data"
        gun = table(read(TABLE+delta, (NATIVE_MAX-1)*BLOCK), data, struct.unpack("<i", read(VERPEN_FACTOR+delta, 4))[0],
                    struct.unpack("<f", read(ROF_DIVISOR+delta, 4))[0])
        records = ordnance(read(ORDNANCE+delta, (NATIVE_MAX+1)*RECORD), data/ORDNANCE_FILE)
        page = rt.K.VirtualAllocEx(handle, None, LAYOUT["size"], 0x3000, 0x40)
        if not page: raise rt.win_error("Cannot allocate the big gun tables")
        memory.write(handle, page+LAYOUT["table"], gun)
        memory.write(handle, page+LAYOUT["ordnance"], records)
        for name, body in code(page+LAYOUT["code"], base).items(): memory.write(handle, page+LAYOUT["code"]+CODE[name], body)
        rt.K.FlushInstructionCache(handle, page+LAYOUT["code"], CODE["size"])
        items = (plans(blob, base, page+LAYOUT["table"]) + ordnance_plans(blob, base, page+LAYOUT["ordnance"])
                 + nation_plans(blob, base, page+LAYOUT["code"]+CODE["allocator"]) + hook_plans(blob, base, page+LAYOUT["code"])
                 + [patch("Main calibre box up to 40 in", spin+SPIN_MAX, struct.pack("<i", NATIVE_MAX), struct.pack("<i", MAX_CALIBRE))])
        verify(handle, items, "original")
        applied = []
        try:
            for item in items:
                rt.write_code(handle, item["address"], bytes.fromhex(item["original"]), bytes.fromhex(item["replacement"]))
                applied.append(item)
            verify(handle, items, "replacement")
        except Exception:
            for item in reversed(applied):
                rt.write_code(handle, item["address"], bytes.fromhex(item["replacement"]), bytes.fromhex(item["original"]))
            raise
        saved = dict(pid=pid, base=module_base, attached=True, page=page, patches=items, max_calibre=MAX_CALIBRE,
                     first_year=FIRST_YEAR, years_per_inch=YEARS_PER_INCH)
        REPORT.write_text(json.dumps(saved, indent=2)+"\n", encoding="utf-8")
        return saved
    finally: rt.K.CloseHandle(handle)


def verify(handle, items, key):
    import weekly_runtime as rt
    for item in items:
        expected = bytes.fromhex(item[key])
        if rt.read(handle, item["address"], len(expected)) != expected:
            raise ValueError("The big guns attachment changed; operation refused.")


def detach():
    import weekly_runtime as rt
    rt.configure_api()
    saved = json.loads(REPORT.read_text(encoding="utf-8"))
    if not saved.get("attached"): return saved
    if dict(rt.process_candidates()).get(saved["pid"]) != rt.GAME/"RTW3.exe": raise ValueError("The attached game session ended.")
    handle = rt.K.OpenProcess(0x438, False, saved["pid"])
    if not handle: raise rt.win_error("Cannot open local game")
    try:
        if rt.module_info(saved["pid"])[0] != saved["base"]: raise ValueError("Game session changed.")
        delta = rt.text_section(handle, saved["base"])[0]-REFERENCE
        def u32(address): return struct.unpack("<I", rt.read(handle, address, 4))[0]
        main = u32(MAIN+delta)
        if main and u32(main+NATIONS) and u32(u32(main+NATIONS)+8):   # their gun levels live past the native object
            raise ValueError("Big guns stays attached while nations are loaded. Close RTW3 to remove it.")
        verify(handle, saved["patches"], "replacement")
        for item in reversed(saved["patches"]):
            rt.write_code(handle, item["address"], bytes.fromhex(item["replacement"]), bytes.fromhex(item["original"]))
        saved["attached"] = False
        REPORT.write_text(json.dumps(saved, indent=2)+"\n", encoding="utf-8")
        return saved
    finally: rt.K.CloseHandle(handle)
