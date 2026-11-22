"""Nuclear attack (SSN) and ballistic missile (SSBN) submarines.

The game has five submarine roles and no spare one, so the two new kinds are native roles with a mark in the boat's
name, which the game copies to the battle and to every torpedo and missile the boat fires:
- SSN: a long range submarine named "... SSN". Its torpedo hits can be nuclear.
- SSBN: a missile submarine named "... SSBN". Where a missile submarine launches one missile it launches
  SSBN_MISSILES (the native launch call repeated), and one hit of the salvo can be nuclear.
Building: the Build submarine list gets the two kinds once their research (modern_tree.SSN, SSBN) is done; the
list text decides the role (SubTypeFromListText) and the name gets its mark at the build call. An SSN costs
COST[1] times its native role, to build and to keep, an SSBN COST[2] times (the six calls of the submarine cost
routine); building time is the native role's.
Computer nations: their build calls (three in the monthly building, one in the starting fleet) pass the same
routine with a role and a name. With the research, AI_SSBN% of the medium and long range boats they order become
SSBNs and the next AI_SSN% SSNs, and AI_MISSILE% of their missile submarines SSBNs. In the monthly building only
for a nation that earns more than it spends; the starting fleet does not ask (its funds are no measure).
Player automatic monthly builds: after the SSN/SSBN research is available, native long-range and missile auto-build
orders receive the matching class-name suffix, so their generated boats keep the new kind through construction.
Classes: a boat keeps the two qualities it is built with (StartBuildingSubmarine: +8 availability, 40 + 3 a
submarine technology level; +0Ch accuracy, -2 to 1). A nuclear boat gets AVAILABILITY more of the first (no
snorkelling, fast transits, long patrols) and an SSN one more of the second, to the native best (sonar and fire
control of a hunter). On the adapter's spare page.
Nuclear hits follow the shell doctrine (shell_doctrine.py: the player's tick boxes and costs, the ban treaty, the
tension afterwards): the target takes a NUCLEAR-calibre hit and every other ship within BLAST_YARDS a
BLAST_CALIBRE-inch one, through the native HandleHit.
Mission kill: every missile hit (the same entry) also runs the native radar damage MISSION_KILL% of the time,
so hit ships lose their radar, and with it their SAM chances and phased-array advantages, more often.
Part of the modern-research adapter; imported lazily.
"""
import hashlib
import struct

import modern_tree as tree
import shell_doctrine as doctrine_rules
import weekly_runtime as rt

BASE = 0x301000
SSBN_MISSILES = 4
AVAILABILITY, BEST_ACCURACY = 15, 1          # a nuclear boat's class qualities, see above
BOAT = dict(name=4, availability=8, accuracy=0xC)
AI_SSBN, AI_SSN, AI_MISSILE = 10, 40, 50      # percent of a computer nation's orders, see above
COST = {1: (5, 2), 2: (4, 1)}                # kind: cost multiplier as (times, divided by): SSN 2.5, SSBN 4
MISSION_KILL = 35                            # % of missile hits that also run the native radar damage (disabled, or destroyed)
NUCLEAR = tree.NUCLEAR_SHELLS[2]
BLAST_YARDS, BLAST_CALIBRE = doctrine_rules.BLAST_YARDS, doctrine_rules.BLAST_CALIBRE
WINDOWS = (
    (0x6E323C, 0xD8, None),   # FillSubList
    (0x6E2B7D, 0x18, None),   # ExecuteSub: its call
    (0x6E46D4, 0x90, None),   # SubTypeFromListText
    (0x6E3EA2, 0x52, None),   # build: name, type, StartBuildingSubmarine
    (0x8D5413, 0xC0, None),   # CheckMissileFiringForSubmarines: the salvo and its message
    (0x8C1B4B, 0x50, None),   # missile hit: HandleHit
    (0x8C2A34, 0x30, None),   # torpedo hit decided
    (0x8765E4, 0xC0, None),   # submarine torpedo launch: the torpedo carries the boat's name
    (0x92F478, 0x40, None),   # tactical submarine display name
    (0x909871, 0x10, None),   # FireGuns: the target's value HandleHit takes
    (0x918098, 0x40, None),   # radar damage (disabled for a while, 10% destroyed)
    (0x796D84, 0xF3, None),   # submarine cost by role
    (0x71F4B1, 0x1B, None), (0x7958CE, 0x1A, None), (0x796C14, 0x32, None), (0x6E4819, 0x13, None), (0x6E4897, 0x13, None),
    # the computer's orders: name, role (AI choice), StartBuildingSubmarine; the last is AIBuildInitialSubs
    (0x77B82D, 0x27, None), (0x77B918, 0x27, None), (0x77B9F0, 0x27, None), (0x7E438B, 0x1B, None),
    (0x796B6C, 0x8B, None),   # StartBuildingSubmarine, to its exception tail
    (0x7A9100, 0x78, None),   # AdvanceShipConstruction: player's automatic monthly submarine build
)
DIGESTS = (
    "e6a1d31a905525823930a9713deb2dcc0726034385971dfd98e912bd85d55716",
    "73980692b1165647bdfa0235c6b1f8f1cac8bc12aaece26cc8bf4f75e84309b0",
    "8eada1456c46765fdf80e1346d69321032981c26c55091b2adce1053f5c7ecb1",
    "e294e7232b6e7bc2c471e729290784b143b83a8893f89a8bb2a1bc15b3f2b464",
    "da7311f37c1103a6bd4a6a02938bc9350aec125b9d8750d80b4c7c698450f993",
    "bf970b4bc89622ce6a9a012e8038c9b09f2d59585de47dea1b99f28903d2a709",
    "4cf8f15a0aad57243e13c5c7d48685600c8d5f26720bb1aa039fb6595ea68093",
    "116dc7ea3cd121684546de90f3d44911831d12614caf0d504102b872e344f84a",
    "07c61f4b2cfe83f9014318c3658ad960d95a1a5e8c9d9e61d05c4fbb925ed8e9",
    "9cd4aeee8b9d6b989e65122735386df2defca8f84809731c332fa602411c5c9c",
    "02acea5990a4f860ed735189bc276af10c4da4b0e645820d14e5616c199a8278",
    "41ac921ef0f4342177d557e7aa8bceb6271f0160f57ffbb40cb25f8947efc889",
    "9e003b7c16c5db97c6fb17408a02d406d0a57df58dc983df3e79eb9076a34503",
    "90202b1417965ebd47fea21d4be217a72ba0228605a2dad407c720586f64b471",
    "e310bef7618904994bb7bcc84bf2f87d0b5c437a1867c0f65971412bdb730fbc",
    "b2812f7ead9067ab61c8551999a5e4b570f4c36f2b2d81267ff0b7cb937ce1a5",
    "ae348ac94cc8072822ade16ab47ad8793b1627445045dcb546e17de1e67d77a3",
    "2be0db17fa05cba69f291539424c86bdf29a6ede7414310c6b9c5156d0809fe3",
    "17fd01ad210689b86b12e266ca107d2199f22946534a8bef70c17388607d97a3",
    "6d2977e273bfeca168702c9d09bee5c59411217ac07ec8b2067e672cb002d07a",
    "ea24a8d95f8c5d4a90d7bf94ef4f12f12f2f5c9f26a22b9126e3b6d7011b5341",
    "bccec693c50f745e4a29b12351dfe0b095256d4856404789d9db96bbf1c50ba4",
    "51a97185eac189cb5360e78b8df7120531a4a08d87a191bbb170138d3e1abe0a",
)
# name, address, bytes replaced, kind
SITES = (("list", 0x6E2B88, 5, "call"), ("kind", 0x6E46D4, 5, "jump"), ("build", 0x6E3EEA, 5, "call"),
         ("salvo", 0x8D5463, 5, "call"), ("torpedo", 0x8C2A40, 6, "jump"),
         # the submarine cost routine's callers: the boat in EBX or ESI, or the build dialog's chosen kind
         ("cost_month", 0x71F4C7, 5, "call"), ("cost_list", 0x7958E3, 5, "call"), ("cost_built", 0x796C24, 5, "call"),
         ("cost_building", 0x796C41, 5, "call"), ("cost_dialog", 0x6E4827, 5, "call"), ("cost_dialog2", 0x6E48A5, 5, "call"),
         ("ai_sub1", 0x77B84F, 5, "call"), ("ai_sub2", 0x77B93A, 5, "call"), ("ai_sub3", 0x77BA12, 5, "call"),
         ("ai_first", 0x7E43A1, 5, "call"), ("class", 0x796BD0, 6, "jump"),
         ("player_auto", 0x7A9159, 5, "call"))
COST_SITES = dict(cost_month="ebx", cost_list="esi", cost_built="ebx", cost_building="ebx", cost_dialog=None, cost_dialog2=None)
MISSILE_ENTRY = 0x2C0                        # in the page: modern_railgun's missile-hit hook asks it (EBX missile, ESI ship)
STRIKE_ENTRY = 0x440                         # in the page: strike (nuclear_strike hits ships with it)
NATIVE = dict(monthly_balance=0x72D2EC, asg=0x30BCCC, cost=0x796D84, random=0x307834, damage_radar=0x918098, launch=0x876374, fill=0x6E323C, start=0x796B6C, has_research=0x729FA4, pos=0x30C958, cat=0x30C63C, list_get=0x3B6D6C,
              ship_distance=0x8ECD20, handle_hit=0x8F7068)
SHIPS_LOAD = 0x8761E3
LIST_ITEMS = (0x440, 0x2D8)                  # the dialog's list box, its Items; TStrings.Add is slot 3Ch
SUB_NAME, SHOT_NAME, SHOT_KIND, SHOT_NATION = 4, 0x2C, 0x28, 0x3E   # tactical submarine; missile or torpedo object
HEAVY_SSM = 31                               # a heavy SSM's code (its HandleHit calibre); 30 other, 32-33 medium, light
SHIP = doctrine_rules.SHIP
TEXTS = dict(list_ssn="Nuclear attack submarine (SSN)", list_ssbn="Ballistic missile submarine (SSBN)",
             find_ssn="SSN", find_ssbn="SSBN", mark_ssn=" SSN", mark_ssbn=" SSBN")


def digests(blob):
    import modern_research as audit
    normal = audit.normalize(blob, BASE)
    return [hashlib.sha256(normal[a-BASE:a-BASE+n]).hexdigest() for a, n, _ in WINDOWS]


def literal(text):
    return struct.pack("<HHiI", 1200, 2, -1, len(text))+text.encode("utf-16-le")+b"\0\0"


def discover(blob, base, normalized):
    for (address, size, _), digest in zip(WINDOWS, DIGESTS):
        if hashlib.sha256(normalized[address-BASE:address-BASE+size]).hexdigest() != digest:
            raise ValueError("Nuclear submarines refuse changed native code at "+hex(address)+".")
    if rt.method_address(blob, base, "AdvanceShipConstruction") != base+(0x7A87EC-BASE):
        raise ValueError("Nuclear submarines refuse a changed automatic-build method.")
    delta = base-BASE
    info = {k: v+delta for k, v in NATIVE.items()}
    info["ships"] = struct.unpack_from("<I", blob, SHIPS_LOAD-BASE+1)[0]
    info["sites"] = {name: dict(address=address+delta, original=blob[address-BASE:address-BASE+size].hex(), kind=kind)
                     for name, address, size, kind in SITES}
    return info


def build(page, info, doctrine, spare, player_auto_page=None, nuclear_ssm=None):
    """Submarine hooks and text on the nuclear-sub page; the player auto-build bridge gets its own page.
    doctrine: shell_doctrine's entry points (use_torpedo, use_missile, used, armageddon). nuclear_ssm:
    modern_air_defence's nuclear_ssm(EBX missile) -> AL."""
    from campaign_security import Code
    from hull_rules import patch
    if player_auto_page is None:
        player_auto_page = page+0x12000
    at = dict(is_kind=page, list=page+0x80, kind=page+0x100, build=page+0x1C0, salvo=page+0x240,
              missile=page+MISSILE_ENTRY, torpedo=page+0x380, strike=page+STRIKE_ENTRY, blast=page+0x4C0,
              chosen=page+0x600, last=page+0x604, slot=page+0x60C, record=page+0x640, texts=page+0x800,
              player_auto=player_auto_page, player_auto_texts=player_auto_page+0x100,
              cost_scale=page+0x580, **{name: page+0xA00+0x20*i for i, name in enumerate(COST_SITES)})
    n, code, texts, cursor, site = info, {}, {}, at["texts"], info["sites"]
    blocks = [dict(name="Nuclear submarines: data", address=at["chosen"], bytes="00"*0x140)]
    for key, text in TEXTS.items():
        body = literal(text); texts[key] = cursor+12
        blocks.append(dict(name="Nuclear submarines: "+key, address=cursor, bytes=body.hex())); cursor += (len(body)+3) & ~3
    for key, text in (("auto_ssn", " SSN"), ("auto_ssbn", " SSBN")):
        body = literal(text); texts[key] = cursor+12
        blocks.append(dict(name="Nuclear submarines: "+key, address=cursor, bytes=body.hex()))
        cursor += (len(body)+3) & ~3

    # is_kind: EAX a name -> EAX 0, 1 (ends in SSN) or 2 (ends in SSBN). Clobbers ECX.
    c = Code(at["is_kind"]); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "none"); c.emit(b"\x8b\x48\xfc")
    c.emit(b"\x83\xf9\x04"); c.branch(b"\x0f\x8c", "ssn")
    c.emit(b"\x81\x7c\x48\xf8"); c.u32(0x00530053); c.branch(b"\x0f\x85", "ssn")
    c.emit(b"\x81\x7c\x48\xfc"); c.u32(0x004E0042); c.branch(b"\x0f\x85", "ssn")
    c.emit(b"\xb8\x02\x00\x00\x00\xc3")
    c.mark("ssn"); c.emit(b"\x83\xf9\x03"); c.branch(b"\x0f\x8c", "none")
    c.emit(b"\x66\x83\x7c\x48\xfa\x53"); c.branch(b"\x0f\x85", "none")
    c.emit(b"\x81\x7c\x48\xfc"); c.u32(0x004E0053); c.branch(b"\x0f\x85", "none")
    c.emit(b"\xb8\x01\x00\x00\x00\xc3")
    c.mark("none"); c.emit(b"\x33\xc0\xc3")
    code["is_kind"] = c.finish()

    # FillSubList(EAX dialog, EDX nation), then the researched new kinds.
    c = Code(at["list"]); c.emit(b"\x50\x52"); c.branch(b"\xe8", n["fill"]); c.emit(b"\x5a\x58\x60\x8b\xf0\x8b\xfa")
    for ident, key in ((tree.SSN, "list_ssn"), (tree.SSBN, "list_ssbn")):
        c.emit(b"\x8b\xc7\xba"); c.u32(ident); c.branch(b"\xe8", n["has_research"]); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "no_"+key)
        c.emit(b"\x8b\x86"); c.u32(LIST_ITEMS[0]); c.emit(b"\x8b\x80"); c.u32(LIST_ITEMS[1])
        c.emit(b"\xba"); c.u32(texts[key]); c.emit(b"\x8b\x08\xff\x51\x3c"); c.mark("no_"+key)
    c.emit(b"\x61\xc3")
    code["list"] = c.finish()

    # SubTypeFromListText(EAX dialog, EDX text): remember the new kind; SSBN is role 4, SSN role 3.
    c = Code(at["kind"]); c.emit(b"\xc7\x05"); c.u32(at["chosen"]); c.u32(0); c.emit(b"\x60\x8b\xf2")
    c.emit(b"\xb9\x01\x00\x00\x00\x8b\xd6\xb8"); c.u32(texts["find_ssbn"]); c.branch(b"\xe8", n["pos"])
    c.emit(b"\x85\xc0"); c.branch(b"\x0f\x8e", "try"); c.emit(b"\xc7\x05"); c.u32(at["chosen"]); c.u32(2); c.branch(b"\xe9", "known")
    c.mark("try"); c.emit(b"\xb9\x01\x00\x00\x00\x8b\xd6\xb8"); c.u32(texts["find_ssn"]); c.branch(b"\xe8", n["pos"])
    c.emit(b"\x85\xc0"); c.branch(b"\x0f\x8e", "known"); c.emit(b"\xc7\x05"); c.u32(at["chosen"]); c.u32(1)
    c.mark("known"); c.emit(b"\x61\x83\x3d"); c.u32(at["chosen"]); c.emit(b"\x02"); c.branch(b"\x0f\x85", "not2")
    c.emit(b"\xb8\x04\x00\x00\x00\xc3")
    c.mark("not2"); c.emit(b"\x83\x3d"); c.u32(at["chosen"]); c.emit(b"\x01"); c.branch(b"\x0f\x85", "native")
    c.emit(b"\xb8\x03\x00\x00\x00\xc3")
    c.mark("native"); c.emit(bytes.fromhex(site["kind"]["original"])); c.branch(b"\xe9", site["kind"]["address"]+5)
    code["kind"] = c.finish()

    # The build call (the name is the caller's [ebp-8] and the stack argument): mark the name of a new kind.
    c = Code(at["build"]); c.emit(b"\x83\x3d"); c.u32(at["chosen"]); c.emit(b"\x00"); c.branch(b"\x0f\x84", "go")
    c.emit(b"\x60\xba"); c.u32(texts["mark_ssn"]); c.emit(b"\x83\x3d"); c.u32(at["chosen"]); c.emit(b"\x02"); c.branch(b"\x0f\x85", "mark")
    c.emit(b"\xba"); c.u32(texts["mark_ssbn"])
    c.mark("mark"); c.emit(b"\x8d\x45\xf8"); c.branch(b"\xe8", n["cat"]); c.emit(b"\x61\x50\x8b\x45\xf8\x89\x44\x24\x08\x58")
    c.mark("go"); c.branch(b"\xe9", n["start"])
    code["build"] = c.finish()

    # The missile launch in CheckMissileFiringForSubmarines (EBX the submarine, seven stack arguments, which the
    # launch drops): an SSBN launches SSBN_MISSILES. The last stack argument, 2, is an aiming error level, not a
    # number of missiles: every launch makes one missile.
    c = Code(at["salvo"]); c.emit(b"\x50\x51\x8b\x43"+bytes([SUB_NAME])); c.branch(b"\xe8", at["is_kind"]); c.emit(b"\x83\xf8\x02\x59\x58")
    c.branch(b"\x0f\x85", "go"); c.emit(b"\x6a"+bytes([SSBN_MISSILES-1]))
    c.mark("more"); c.emit(b"\xff\x74\x24\x20"*7+b"\x8d\x4b\x14\x8b\x53\x08\x8b\x45\xfc"); c.branch(b"\xe8", n["launch"])
    c.emit(b"\xff\x0c\x24"); c.branch(b"\x0f\x85", "more")
    c.emit(b"\x83\xc4\x04\x8d\x4b\x14\x8b\x53\x08\x8b\x45\xfc")
    c.mark("go"); c.branch(b"\xe9", n["launch"])
    code["salvo"] = c.finish()

    # strike: EAX ship, EDX nation, ECX the firer's name, stack: calibre. A hit through HandleHit, from a random
    # bearing (a blast has no firing ship; GetIncomingBearing needs one in EDX, and its error handler then names a
    # nation index as a ship: the 2026-11-21 ResolveMissileHit crashes).
    c = Code(at["strike"]); c.emit(b"\x53\x56\x57\x8b\xd8\x8b\xf2\x8b\xf9\xff\x74\x24\x10\x68"); c.u32(0x1388)
    c.emit(b"\x6a\x00\x56\x6a\x01\xb8"); c.u32(360); c.branch(b"\xe8", n["random"]); c.emit(b"\x50\x6a\x00\x68"); c.u32(at["record"])
    c.emit(b"\x33\xd2\x8b\xcf\x8b\xc3"); c.branch(b"\xe8", n["handle_hit"]); c.emit(b"\x5f\x5e\x5b\xc2\x04\x00")
    code["strike"] = c.finish()

    # blast: EAX target, EDX nation, ECX name: every other ship within BLAST_YARDS takes a BLAST_CALIBRE hit.
    c = Code(at["blast"]); c.emit(b"\x60\x8b\xe8\x6a\x00")                       # EBP target; [esp] index; saved EDX, ECX above
    c.mark("ship"); c.emit(b"\xa1"); c.u32(n["ships"]); c.emit(b"\x8b\x00\x8b\x0c\x24\x3b\x48\x08"); c.branch(b"\x0f\x8d", "end")
    c.emit(b"\x8b\xd1"); c.branch(b"\xe8", n["list_get"]); c.emit(b"\x8b\xd8\x85\xdb"); c.branch(b"\x0f\x84", "next")
    c.emit(b"\x3b\xdd"); c.branch(b"\x0f\x84", "next")
    c.emit(b"\x80\xbb"); c.u32(SHIP["kind"]); c.emit(b"\x0c"); c.branch(b"\x0f\x84", "next")
    c.emit(b"\x80\xbb"); c.u32(SHIP["out"]); c.emit(b"\x00"); c.branch(b"\x0f\x85", "next")
    c.emit(b"\x8b\xc5\x8b\xd3"); c.branch(b"\xe8", n["ship_distance"])
    c.emit(b"\x85\xc0"); c.branch(b"\x0f\x88", "next"); c.emit(b"\x3d"); c.u32(BLAST_YARDS); c.branch(b"\x0f\x8f", "next")
    c.emit(b"\x6a"+bytes([BLAST_CALIBRE])+b"\x8b\x4c\x24\x20\x8b\x54\x24\x1c\x8b\xc3"); c.branch(b"\xe8", at["strike"])
    c.mark("next"); c.emit(b"\xff\x04\x24"); c.branch(b"\xe9", "ship")
    c.mark("end"); c.emit(b"\x83\xc4\x04\x61\xc3")
    code["blast"] = c.finish()

    # A missile hit (EBX missile, ESI ship), asked by modern_railgun's hook on the hit's HandleHit call: AL = 1
    # when it is nuclear (one hit of an SSBN's salvo, when the doctrine allows); the blast is done here. Under
    # Nuclear Armageddon (shell_doctrine's armageddon flag) every SSBN hit may be, and so may a heavy SSM's
    # (nuclear_ssm: modern_air_defence), both as the doctrine's nuclear missiles.
    armageddon = doctrine.get("armageddon")
    c = Code(at["missile"]); c.emit(b"\x60\xb8\x64\x00\x00\x00"); c.branch(b"\xe8", n["random"])   # mission kill: the radar
    c.emit(b"\x83\xf8"+bytes([MISSION_KILL])); c.branch(b"\x0f\x8d", "radar"); c.emit(b"\x8b\xc6"); c.branch(b"\xe8", n["damage_radar"])
    c.mark("radar"); c.emit(b"\x8b\x43"+bytes([SHOT_NAME])); c.branch(b"\xe8", at["is_kind"]); c.emit(b"\x83\xf8\x02")
    c.branch(b"\x0f\x85", "heavy" if nuclear_ssm else "plain")
    if armageddon: c.emit(b"\x80\x3d"); c.u32(armageddon); c.emit(b"\x00"); c.branch(b"\x0f\x85", "pay")
    c.emit(b"\x8b\x43"+bytes([SHOT_NAME])+b"\x39\x05"); c.u32(at["last"]); c.branch(b"\x0f\x84", "plain")   # a salvo's missiles share one name string
    c.mark("pay"); c.emit(b"\x8b\x53"+bytes([SHOT_NATION])); c.branch(b"\xe8", doctrine["use_missile"]); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "plain")
    c.emit(b"\x8b\x43"+bytes([SHOT_NAME])+b"\xa3"); c.u32(at["last"]); c.branch(b"\xe9", "nuclear")
    if nuclear_ssm:
        c.mark("heavy"); c.branch(b"\xe8", nuclear_ssm); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "plain")
    c.mark("nuclear"); c.emit(b"\xc7\x05"); c.u32(doctrine["used"]); c.u32(1)
    c.emit(b"\x8b\x53"+bytes([SHOT_NATION])+b"\x8b\x4b"+bytes([SHOT_NAME])+b"\x8b\xc6"); c.branch(b"\xe8", at["blast"])
    c.emit(b"\x61\xb0\x01\xc3")
    c.mark("plain"); c.emit(b"\x61\x33\xc0\xc3")
    code["missile"] = c.finish()
    if at["missile"] != page+MISSILE_ENTRY: raise ValueError("Nuclear submarines: the missile entry moved.")

    # A torpedo hit (EBX torpedo, ESI ship): an SSN's torpedo is nuclear when the doctrine allows. A submarine's
    # torpedo holds its nation index plus 2.
    c = Code(at["torpedo"]); c.emit(b"\x60\x8b\x43"+bytes([SHOT_NAME])); c.branch(b"\xe8", at["is_kind"]); c.emit(b"\x83\xf8\x01")
    c.branch(b"\x0f\x85", "plain"); c.emit(b"\x39\x1d"); c.u32(at["last"]+4); c.branch(b"\x0f\x84", "plain")   # once a torpedo
    c.emit(b"\x89\x1d"); c.u32(at["last"]+4)
    c.emit(b"\x8b\x53"+bytes([SHOT_NATION])+b"\x83\xea\x02"); c.branch(b"\xe8", doctrine["use_torpedo"]); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "plain")
    c.emit(b"\xc7\x05"); c.u32(doctrine["used"]); c.u32(1)
    c.emit(b"\x6a"+bytes([NUCLEAR])+b"\x8b\x53"+bytes([SHOT_NATION])+b"\x83\xea\x02\x8b\x4b"+bytes([SHOT_NAME])+b"\x8b\xc6"); c.branch(b"\xe8", at["strike"])
    c.emit(b"\x8b\x53"+bytes([SHOT_NATION])+b"\x83\xea\x02\x8b\x4b"+bytes([SHOT_NAME])+b"\x8b\xc6"); c.branch(b"\xe8", at["blast"])
    c.mark("plain"); c.emit(b"\x61"+bytes.fromhex(site["torpedo"]["original"])); c.branch(b"\xe9", site["torpedo"]["address"]+6)
    code["torpedo"] = c.finish()

    # The cost routine's callers: its result times COST for a new kind. The caller's return address waits in a slot
    # (the routine drops one stack argument); the routine is not re-entered.
    c = Code(at["cost_scale"])                                                    # EAX cost, ECX kind
    for kind, (times, over) in COST.items():
        c.emit(b"\x83\xf9"+bytes([kind])); c.branch(b"\x0f\x85", f"not{kind}")
        c.emit(b"\x6b\xc0"+bytes([times])+b"\x99\xb9"); c.u32(over); c.emit(b"\xf7\xf9"); c.branch(b"\xe9", "done")
        c.mark(f"not{kind}")
    c.mark("done"); c.emit(b"\xff\x25"); c.u32(at["slot"])
    code["cost_scale"] = c.finish()
    for name, register in COST_SITES.items():
        c = Code(at[name]); c.emit(b"\x8f\x05"); c.u32(at["slot"]); c.branch(b"\xe8", n["cost"])
        if register:
            c.emit(b"\x50\x8b"+(b"\x43" if register == "ebx" else b"\x46")+bytes([4])); c.branch(b"\xe8", at["is_kind"]); c.emit(b"\x8b\xc8\x58")
        else:
            c.emit(b"\x8b\x0d"); c.u32(at["chosen"])
        c.branch(b"\xe9", at["cost_scale"])
        code[name] = c.finish()

    # A computer nation's order (EAX main, EDX nation, CL role, the name on the stack): the new kinds' share.
    # Two free corners of the page: the roll, and (tail) the missile submarines' share and the name mark.
    at.update(ai_sub=page+0x740, ai_tail=page+0xB80, ai_name=page+0xBFC)
    blocks.append(dict(name="Nuclear submarines: ai_name", address=at["ai_name"], bytes="00000000"))

    def researched(ident, miss):
        c.emit(b"\x8b\xc6\xba"); c.u32(ident); c.branch(b"\xe8", n["has_research"]); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", miss)
    c = Code(at["ai_tail"])                                                       # ESI nation, EBX role, EDI the roll
    c.emit(b"\x83\xff"+bytes([AI_MISSILE])); c.branch(b"\x0f\x8d", "go"); researched(tree.SSBN, "go")
    c.emit(b"\xba"); c.u32(texts["mark_ssbn"])
    # EDX mark: the marked name in our own string variable replaces the stack argument; the role the saved ECX
    c.mark("mark"); c.emit(b"\x52\xb8"); c.u32(at["ai_name"]); c.emit(b"\x8b\x54\x24\x28"); c.branch(b"\xe8", n["asg"])
    c.emit(b"\x5a\xb8"); c.u32(at["ai_name"]); c.branch(b"\xe8", n["cat"])
    c.emit(b"\xa1"); c.u32(at["ai_name"]); c.emit(b"\x89\x44\x24\x24\x89\x5c\x24\x18")
    c.mark("go"); c.emit(b"\x61"); c.branch(b"\xe9", n["start"])
    code["ai_tail"] = c.finish(); mark = at["ai_tail"]+c.labels["mark"]
    c = Code(at["ai_sub"])
    c.emit(b"\x60\x8b\xf2\x0f\xb6\xd9\x85\xf6"); c.branch(b"\x0f\x84", "go")
    c.emit(b"\x8b\xc6"); c.branch(b"\xe8", n["monthly_balance"]); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x8e", "go")
    c.branch(b"\xe9", "roll")
    c.mark("first"); c.emit(b"\x60\x8b\xf2\x0f\xb6\xd9\x85\xf6"); c.branch(b"\x0f\x84", "go")
    c.mark("roll"); c.emit(b"\xb8\x64\x00\x00\x00"); c.branch(b"\xe8", n["random"]); c.emit(b"\x8b\xf8")
    c.emit(b"\x83\xfb\x04"); c.branch(b"\x0f\x84", at["ai_tail"]); c.emit(b"\x85\xdb"); c.branch(b"\x0f\x84", "attack")
    c.emit(b"\x83\xfb\x03"); c.branch(b"\x0f\x85", "go")
    c.mark("attack"); c.emit(b"\x83\xff"+bytes([AI_SSBN])); c.branch(b"\x0f\x8d", "ssn"); researched(tree.SSBN, "ssn")
    c.emit(b"\xbb\x04\x00\x00\x00\xba"); c.u32(texts["mark_ssbn"]); c.branch(b"\xe9", mark)
    c.mark("ssn"); c.emit(b"\x83\xff"+bytes([AI_SSBN+AI_SSN])); c.branch(b"\x0f\x8d", "go"); researched(tree.SSN, "go")
    c.emit(b"\xbb\x03\x00\x00\x00\xba"); c.u32(texts["mark_ssn"]); c.branch(b"\xe9", mark)
    c.mark("go"); c.emit(b"\x61"); c.branch(b"\xe9", n["start"])
    code["ai_sub"] = c.finish()
    at.update(ai_sub1=at["ai_sub"], ai_sub2=at["ai_sub"], ai_sub3=at["ai_sub"], ai_first=at["ai_sub"]+c.labels["first"])

    # StartBuildingSubmarine, EDI the new boat with its name and qualities, ESI the nation: a nuclear boat's class.
    at["class"] = spare
    c = Code(at["class"]); c.emit(b"\x60\x8b\x47"+bytes([BOAT["name"]])); c.branch(b"\xe8", at["is_kind"])
    c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "out"); c.emit(b"\x83\x47"+bytes([BOAT["availability"], AVAILABILITY]))
    c.emit(b"\x83\xf8\x01"); c.branch(b"\x0f\x85", "out")
    c.emit(b"\x83\x7f"+bytes([BOAT["accuracy"], BEST_ACCURACY])); c.branch(b"\x0f\x8d", "out"); c.emit(b"\xff\x47"+bytes([BOAT["accuracy"]]))
    c.mark("out"); c.emit(b"\x61"+bytes.fromhex(site["class"]["original"])); c.branch(b"\xe9", site["class"]["address"]+6)
    code["class"] = c.finish()

    # The player's auto-build path enters AdvanceShipConstruction with the native role in CL and a generated
    # name on the stack. Preserve that route, but mark researched long-range/missile boats before the native start.
    # At this call site [ebp-0xAC] owns the generated Delphi string; update the pushed argument after UStrCat.
    c = Code(at["player_auto"]); c.emit(b"\x9c\x60")
    c.emit(b"\x8b\x44\x24\x18\x83\xf8\x03"); c.branch(b"\x0f\x85", "maybe_ssbn")
    c.emit(b"\x8b\x44\x24\x14\xba"); c.u32(tree.SSN); c.branch(b"\xe8", n["has_research"])
    c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "done"); c.branch(b"\xe9", "append_ssn")
    c.mark("maybe_ssbn"); c.emit(b"\x83\xf8\x04"); c.branch(b"\x0f\x85", "done")
    c.emit(b"\x8b\x44\x24\x14\xba"); c.u32(tree.SSBN); c.branch(b"\xe8", n["has_research"])
    c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "done"); c.branch(b"\xe9", "append_ssbn")
    c.mark("append_ssn"); c.emit(b"\xba"); c.u32(texts["auto_ssn"]); c.branch(b"\xe9", "append")
    c.mark("append_ssbn"); c.emit(b"\xba"); c.u32(texts["auto_ssbn"])
    c.mark("append"); c.emit(b"\x8b\x85"+struct.pack("<i", -0xAC)); c.branch(b"\xe8", at["is_kind"])
    c.emit(b"\x85\xc0"); c.branch(b"\x0f\x85", "done")
    c.emit(b"\x8d\x85"+struct.pack("<i", -0xAC)); c.branch(b"\xe8", n["cat"])
    c.emit(b"\x8b\x85"+struct.pack("<i", -0xAC)+b"\x89\x44\x24\x28")
    c.mark("done"); c.emit(b"\x61\x9d"); c.branch(b"\xe9", n["start"])
    code["player_auto"] = c.finish()

    room = dict(**{"class": 0x80}, ai_sub=0xC0, ai_tail=0x7C, cost_scale=0x40, player_auto=0x100, **dict.fromkeys(COST_SITES, 0x20), is_kind=0x80, list=0x80, kind=0xC0, build=0x80, salvo=0x80, missile=0xC0, torpedo=0xC0,
                strike=0x80, blast=0x100)
    for name, body in code.items():
        if len(body) > room[name]: raise ValueError("Nuclear submarines code exceeds its reservation: "+name)
        blocks.append(dict(name="Nuclear submarines: "+name, address=at[name], bytes=body.hex()))
    plans = []
    for name, s in site.items():
        old = bytes.fromhex(s["original"])
        new = (b"\xe8" if s["kind"] == "call" else b"\xe9")+struct.pack("<i", at[name]-s["address"]-5)+b"\x90"*(len(old)-5)
        plans.append(patch("Nuclear submarines: "+name, s["address"], old, new))
    return blocks, plans
