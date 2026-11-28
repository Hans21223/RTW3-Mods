"""Air defence: interceptor drone swarms, hypervelocity anti-air rounds for railguns, and nuclear SAMs.

Interceptor drones (modern_tree.DRONE_SWARMS research): a ship with a helicopter deck, a catapult or a flight deck
carries AI interceptor drones (Coyote, Roadrunner). drone_ship(ship) answers it for other modules:
- modern_defence's decoy roll (the game's DoesECM, against each incoming missile and guided bomb) adds the percent;
- modern_navy's long-range heavy AA (the three GetHeavyAAFactor calls of the air attack) adds the AA value;
- CAP and radar: aew(carrier) stands in for the battle's AEW squadron checks (modern_carrier's has_special): a
  carrier of a researching nation counts as having one (longer CAP vectoring and radar).
Hypervelocity anti-air rounds (modern_tree.HVP_AA research), for a railgun main battery of any calibre (natively
only 3- to 6-inch guns count as heavy AA, and only DP ones; a DP railgun counts 1.5 times, modern_railgun):
- value: GetHeavyAAFactor's main-battery share becomes at least the battery's guns times HVP value (designer, ship
  information and battle all read it);
- range: in the air attack's long-range phase (AttackShips), such a ship engages from its heavy AA range times
  the range factor: strikes on other ships of its group too, and more often in the full-rate half;
- spread: the phase's shots are pooled into one count before the hit rolls; the shots of hypervelocity ships are
  counted apart, and a hit is theirs with that share: it strikes the spread number of aircraft (destroyed or
  damaged as the native roll decided) and the attack loses as many aircraft.
Nuclear SAMs (the Nuclear Armageddon sub-mod switches shell_doctrine's armageddon flag): a heavy SAM of a nation
with the nuclear warhead research (modern_tree.NUCLEAR_SHELLS) may be nuclear when the doctrine's "nuclear
missiles" choice lets its nation fire and pay one (shell_doctrine.use_missile, the cost of a nuclear missile):
- against aircraft (the air attack's SAM fire): a hit strikes up to NUCLEAR_SAM_AIRCRAFT aircraft of the formation
  instead of the native two, with a line in the battle log;
- against an incoming missile (DoesSAMvsMissile, through modern_defence's hook after FireSAM): it is shot down.
Heavy DP guns: the game lets 3- to 6-inch guns be DP (DPPossible 0x95274C, the rule for the designer's DP boxes,
its legality check and the computer's designs; never in triple or quadruple turrets) and gives only those calibres
a heavy AA value (GetCalibreAAvalue 0x950270). 7- and 8-inch guns may be DP too once the nation has both researches
in HEAVY_DP_RESEARCH (6 in DP mounts and the 7 and 8 in autoloader: the rapid-fire 8-inch of 1945), in any battery,
and a DP gun of those calibres counts HEAVY_DP heavy AA (one more autoloaded; the 6-inch counts 5, or 6).
Tankers (modern_tree.AERIAL_REFUELLING, CARRIER_TANKERS): a battle formation's range is its fuel (+28h, set from its
aircraft's endurance by SetFullFuelLoad at each mission and refuelling) and, for planning, its aircraft's combat
radius (GetCombatRadiusInNm, a third of the endurance). tanker(formation) gives the percent for its base (+4Dh): an
airfield (type 12) of a nation with aerial refuelling, or a carrier of a nation with tanker drones that has its
special squadron (the game's special squadrons belong to carriers). The fuel and every range check that has the
formation (AI strike targets, land air priorities, the launch and escort menus, the formation's own status) use it.
Part of the modern-research adapter; imported lazily.
"""
import hashlib
import struct

import modern_tree as tree

BASE = 0x301000
RAILGUN, HEAVY_SAM, AEW = 2, 1, 1          # Increased elevation byte of a railgun main battery; SAM kind; squadron kind
NUCLEAR_SAM_AIRCRAFT = 10
SHIP = dict(nation=0x14, catapults=0x9DB, flight_deck=0x9D9, helicopters=0x9E5, elevation=0x9A6, sec_dp=0x86)
FORMATION = dict(aircraft=0x18, destroyed=0x8D)
# Page layout: other modules call drone_ship, aew and nuclear_sam by these offsets before this page is built.
OFFSETS = dict(drone_ship=0x000, aew=0x060, is_hvp=0x0C0, value=0x100, range=0x180, reset=0x1C0, add=0x1E0,
               spread=0x240, nuclear_sam=0x300, sam_air=0x380, shots=0x400, text=0x440, nuclear_ssm=0x4C0,
               dp_rule=0x540, aa_value=0x5C0, tanker=0x620, fuel=0x700, radius=0x740)
ROOM = dict(drone_ship=0x60, aew=0x60, is_hvp=0x40, value=0x80, range=0x40, reset=0x20, add=0x60, spread=0xC0,
            nuclear_sam=0x80, sam_air=0x80, nuclear_ssm=0x80, dp_rule=0x80, aa_value=0x60, tanker=0xE0, fuel=0x40,
            radius=0x60)
FORMATION_BASE, FORMATION_NATION, FUEL, AIRFIELD = 0x4D, 0x38, 0x28, 12
RADIUS = 0x96CA6C                        # GetCombatRadiusInNm(EAX aircraft type, EDX load) -> nm
# Its callers with the formation: in EBX (AI strike targets, launch and escort menus, land air priorities, target
# points), at [EBX] (a formation's status), at [EBP-8] (AI strike targets). Estimates of enemy ranges stay native.
RADIUS_CALLS = dict(ebx=(0x8CDA5D, 0x8CDBC0, 0x8CE1E3, 0x8CE8BA, 0x6F8D92, 0x6F912E, 0x6FAEC1, 0x6FAEE1, 0x6FAF01,
                         0x8D57CB, 0x979EDB), slot=(0x964072, 0x9640F9), frame=(0x8CEA1F,))
HEAVY_DP = {7: 5, 8: 4}                  # calibre: heavy AA a DP gun counts (one more with an autoloader)
HEAVY_DP_RESEARCH = (1404, 520)          # 6 in dual purpose mounting (1934), 7 and 8 in autoloader (1945)
DESIGNER_NATION = 0xC63                  # the designer form's nation, which the native DP rule asks
MISSILE = dict(kind=0x28, side=0x3E)       # a missile object: its code (HandleHit calibre), its launcher's battle side
HEAVY_SSM = 31
TEXT = "2Nuclear SAM detonates among the attacking aircraft"
WINDOWS = (
    (0x9170B0, 0x18, "2d4ba6daf5cec74f821f578346413bc5d1fe4f3cb7a5ce3da8adad8b2f88ff8e"),   # GetHeavyAAFactor: after the main battery
    (0x960D10, 0x18, "34318ad7261214f7cfddc637ca5b3cab803db03f3141d2066b52a2168767f9b2"),   # AttackShips: the long-range phase's shot count is cleared
    (0x960DA0, 0x10, "45f9d1018f10c5ff6a76255ca3d463465cca3a37215fa9f5d977c6b387a4c020"),   # each ship's heavy AA range
    (0x960E74, 0x14, "86c73db408e57be948ee15631f97e2a4296fe131445c62c8dca6bd8b94d40f93"),   # a ship's shots join the count (half range)
    (0x960FAA, 0x14, "e1d5eed8c08843e31e5419ace31a1d2dbadc5cd261de93557d67886965514192"),   # (full range)
    (0x9612A8, 0x18, "863d463fe4cdf3e18559c9ee417ee82cf251178c4b16df5a03a4923bd880a729"),   # a hit: destroyed
    (0x961340, 0x18, "7085f5e14d4e43f4f1051c93c7f2978fafb11e2cdd7855eb1d94b3f3f74d7552"),   # a hit: damaged
    (0x95FF20, 0x18, "938a6f3b3cdda84b30ffdac279dbce43be4a6253803c784613c21c73f46b8f57"),   # SAMs at aircraft: aircraft a hit strikes
    (0x95274C, 0x40, "202b0cb4094c139f69cc6a1aea6ac97ba7bab0cf014400e677cffca48b8e2f97"),   # DPPossible: barrels, calibre switch
    (0x950270, 0x20, "6c4f2ac420c910eaffbc21caeda35c0479bd81d08f0c739827f034b20c86aadb"),   # GetCalibreAAvalue: entry, calibre switch
)
SITES = (("value", 0x9170BA, "80be8600000000"), ("range", 0x960DA5, "e8d2edffff"), ("reset", 0x960D18, "33c08945d8"),
         ("add", 0x960E7C, "017dd885ff"), ("add2", 0x960FB2, "017dd885ff"), ("kill", 0x9612B6, "ba01000000"),
         ("damage", 0x96134C, "ba01000000"), ("sam_air", 0x95FF2F, "85f60f8c66010000"),
         ("dp_rule", 0x952778, "83c0fd83e802"), ("aa_value", 0x950270, "53565733db"),
         ("fuel", 0x974CF9, "8943285bc3"))                  # SetFullFuelLoad: mov [ebx+28h],eax / pop ebx / ret
CALLS = {"range": "range", "reset": "reset", "add": "add", "add2": "add", "kill": "spread", "damage": "spread"}
NATIVE = dict(count_guns=0x916F24, value_back=0x9170C1, heavy_range=0x95FB7C, random=0x307834, is_carrier=0x950090,
              battle_log=0xA80114, sam_air_skip=0x96009D, sam_air_back=0x95FF37, dp_back=0x95277E, dp_tail=0x9527DA,
              aa_back=0x950275, has_special=0x91ABB8, radius=RADIUS)
DESIGNER_LOAD = 0x952787                 # DPPossible: mov eax, [designer form variable]


def digest(normalized, address, size):
    return hashlib.sha256(normalized[address-BASE:address-BASE+size]).hexdigest()


def discover(blob, base, normalized):
    for address, size, expected in WINDOWS:
        if digest(normalized, address, size) != expected:
            raise ValueError("Air defence refuses changed native code at "+hex(address)+".")
    for name, address, original in SITES:
        if blob[address-BASE:address-BASE+len(original)//2].hex() != original:
            raise ValueError("Air defence refuses changed native code at "+hex(address)+".")
    import modern_combat as combat
    delta = base-BASE
    info = {k: v+delta for k, v in {**NATIVE, **{k: combat.NATIVE[k] for k in ("has_research", "nation")}}.items()}
    info["main"] = struct.unpack_from("<I", blob, combat.MAIN_LOAD-BASE+1)[0]
    if blob[DESIGNER_LOAD-BASE] != 0xA1:
        raise ValueError("Air defence refuses changed native code at "+hex(DESIGNER_LOAD)+".")
    info["designer"] = struct.unpack_from("<I", blob, DESIGNER_LOAD-BASE+1)[0]
    info["sites"] = {name: address+delta for name, address, _ in SITES}
    info["originals"] = {name: original for name, _, original in SITES}
    for kind, sites in RADIUS_CALLS.items():
        for at in sites:
            if blob[at-BASE] != 0xE8 or at+5+struct.unpack_from("<i", blob, at-BASE+1)[0] != RADIUS:
                raise ValueError("Air defence refuses changed native code at "+hex(at)+".")
    info["radius_calls"] = {kind: [at+delta for at in sites] for kind, sites in RADIUS_CALLS.items()}
    return info


def literal(text):
    return struct.pack("<HHiI", 1200, 2, -1, len(text))+text.encode("utf-16-le")+b"\0\0"


def build(page, info, has_special, doctrine, side_nation=None):
    """Code and data on its own page. has_special: modern_carrier's squadron check; doctrine: shell_doctrine's
    entries (use_missile, used, armageddon)."""
    from campaign_security import Code
    from hull_rules import patch
    import modern_combat as combat
    n, code = info, {}
    at = {name: page+offset for name, offset in OFFSETS.items()}
    drones, drone_percent, drone_aa = tree.DRONE_SWARMS
    hvp, hvp_value, hvp_range, spread = tree.HVP_AA
    warhead = tree.NUCLEAR_SHELLS[0]

    # drone_ship(EAX ship) -> AL: a helicopter deck, a catapult or a flight deck, and the research. Keeps all but EAX.
    c = Code(at["drone_ship"]); c.emit(b"\x51\x52\x8b\xc8\x80\xb9"); c.u32(SHIP["helicopters"]); c.emit(b"\x00")
    c.branch(b"\x0f\x85", "aboard"); c.emit(b"\x83\xb9"); c.u32(SHIP["catapults"]); c.emit(b"\x00"); c.branch(b"\x0f\x85", "aboard")
    c.emit(b"\x80\xb9"); c.u32(SHIP["flight_deck"]); c.emit(b"\x00"); c.branch(b"\x0f\x84", "none")
    c.mark("aboard"); combat.researched(c, n, b"\x8b\x51"+bytes([SHIP["nation"]]), drones, "asked"); c.branch(b"\xe9", "out")
    c.mark("none"); c.emit(b"\x33\xc0")
    c.mark("out"); c.emit(b"\x5a\x59\xc3")
    code["drone_ship"] = c.finish()

    # aew(EAX carrier) -> AL, for the battle's AEW squadron checks: the native squadron, or a carrier of a nation with
    # interceptor drones. Keeps EBX, ESI, EDI, EBP like the native check.
    c = Code(at["aew"]); c.emit(b"\x50\xb9"); c.u32(AEW); c.branch(b"\xe8", has_special); c.emit(b"\x84\xc0")
    c.branch(b"\x0f\x85", "out"); c.emit(b"\x8b\x04\x24"); c.branch(b"\xe8", n["is_carrier"]); c.emit(b"\x84\xc0")
    c.branch(b"\x0f\x84", "out"); c.emit(b"\x8b\x0c\x24")
    combat.researched(c, n, b"\x8b\x51"+bytes([SHIP["nation"]]), drones, "asked")
    c.mark("out"); c.emit(b"\x59\xc3")
    code["aew"] = c.finish()

    # is_hvp(EAX ship) -> AL: a railgun main battery and the hypervelocity research. Keeps all but EAX.
    c = Code(at["is_hvp"]); c.emit(b"\x80\xb8"); c.u32(SHIP["elevation"]); c.emit(bytes([RAILGUN])); c.branch(b"\x0f\x85", "no")
    c.emit(b"\x51\x52\x8b\xc8"); combat.researched(c, n, b"\x8b\x51"+bytes([SHIP["nation"]]), hvp, "asked")
    c.emit(b"\x5a\x59\xc3")
    c.mark("no"); c.emit(b"\x33\xc0\xc3")
    code["is_hvp"] = c.finish()

    # GetHeavyAAFactor after its main-battery share ([ebp-20h], ESI ship), DP or not: hypervelocity railguns count
    # at least their guns times the value; a share that was nothing adds a battery to the count ([ebp-0Ch]).
    c = Code(at["value"]); c.emit(b"\x60\x8b\xc6"); c.branch(b"\xe8", at["is_hvp"]); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "done")
    c.emit(b"\xb2\x01\x8b\xc6"); c.branch(b"\xe8", n["count_guns"]); c.emit(b"\x69\xc0"); c.u32(hvp_value)
    c.emit(b"\x3b\x45\xe0"); c.branch(b"\x0f\x8e", "done")
    c.emit(b"\x83\x7d\xe0\x00"); c.branch(b"\x0f\x8f", "set"); c.emit(b"\xff\x45\xf4")
    c.mark("set"); c.emit(b"\x89\x45\xe0")
    c.mark("done"); c.emit(b"\x61\x80\xbe"); c.u32(SHIP["sec_dp"]); c.emit(b"\x00"); c.branch(b"\xe9", n["value_back"])
    code["value"] = c.finish()

    # A ship's heavy AA range in the air attack (EAX ship) -> EAX: times the factor for hypervelocity railguns.
    c = Code(at["range"]); c.emit(b"\x50"); c.branch(b"\xe8", n["heavy_range"]); c.emit(b"\x87\x04\x24")
    c.branch(b"\xe8", at["is_hvp"]); c.emit(b"\x84\xc0\x58"); c.branch(b"\x0f\x84", "out"); c.emit(b"\x6b\xc0"+bytes([hvp_range]))
    c.mark("out"); c.emit(b"\xc3")
    code["range"] = c.finish()

    # The long-range phase clears its shot count ([ebp-28h]); the hypervelocity shots start again too.
    c = Code(at["reset"]); c.emit(b"\x33\xc0\x89\x45\xd8\xa3"); c.u32(at["shots"]); c.emit(b"\xc3")
    code["reset"] = c.finish()
    # A ship's shots (EDI, [ESI] the ship) join the count; a hypervelocity ship's are counted apart. Flags: TEST EDI.
    c = Code(at["add"]); c.emit(b"\x01\x7d\xd8\x60\x85\xff"); c.branch(b"\x0f\x8e", "done")
    c.emit(b"\x8b\x06"); c.branch(b"\xe8", at["is_hvp"]); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "done")
    c.emit(b"\x01\x3d"); c.u32(at["shots"])
    c.mark("done"); c.emit(b"\x61\x85\xff\xc3")
    code["add"] = c.finish()
    # A hit, in place of MOV EDX,1 before InflictAirLoss (CL kept: destroyed 0Ch, damaged 0Bh): a hypervelocity hit,
    # by its share of the shots, strikes the spread number of aircraft; its counter ([ebp-14h] destroyed or [ebp-18h]
    # damaged) and the attackers ([ebp-24h]) follow.
    c = Code(at["spread"]); c.emit(b"\x51\x80\xf9\x0c\x8d\x4d\xec"); c.branch(b"\x0f\x84", "kind")
    c.emit(b"\x8d\x4d\xe8")
    c.mark("kind"); c.emit(b"\x51\x83\x3d"); c.u32(at["shots"]); c.emit(b"\x00"); c.branch(b"\x0f\x8e", "single")
    c.emit(b"\x8b\x45\xd8\x85\xc0"); c.branch(b"\x0f\x8e", "single")
    c.branch(b"\xe8", n["random"]); c.emit(b"\x3b\x05"); c.u32(at["shots"]); c.branch(b"\x0f\x8d", "single")
    c.emit(b"\x59\x83\x01"+bytes([spread-1]))
    for _ in range(spread-1):
        c.emit(b"\x83\x7d\xdc\x00"); c.branch(b"\x0f\x8e", f"none{_}"); c.emit(b"\xff\x4d\xdc"); c.mark(f"none{_}")
    c.emit(b"\xba"); c.u32(spread); c.branch(b"\xe9", "out")
    c.mark("single"); c.emit(b"\x59\xba\x01\x00\x00\x00")
    c.mark("out"); c.emit(b"\x59\xc3")
    code["spread"] = c.finish()

    # nuclear_sam(EAX ship, EDX kind) -> AL: under the armageddon flag, a heavy SAM of a nation with the warhead
    # research that the doctrine lets fire (and pay for) a nuclear missile. Marks the turn's nuclear use. Keeps all
    # but EAX.
    c = Code(at["nuclear_sam"]); c.emit(b"\x51\x52\x80\x3d"); c.u32(doctrine["armageddon"]); c.emit(b"\x00")
    c.branch(b"\x0f\x84", "no"); c.emit(b"\x83\xfa"+bytes([HEAVY_SAM])); c.branch(b"\x0f\x85", "no")
    c.emit(b"\x8b\xc8\x51"); combat.researched(c, n, b"\x8b\x51"+bytes([SHIP["nation"]]), warhead, "asked"); c.emit(b"\x59")
    c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "no")
    c.emit(b"\x8b\x51"+bytes([SHIP["nation"]])); c.branch(b"\xe8", doctrine["use_missile"]); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "no")
    c.emit(b"\xc7\x05"); c.u32(doctrine["used"]); c.u32(1); c.emit(b"\xb0\x01"); c.branch(b"\xe9", "out")
    c.mark("no"); c.emit(b"\x33\xc0")
    c.mark("out"); c.emit(b"\x5a\x59\xc3")
    code["nuclear_sam"] = c.finish()

    # nuclear_ssm(EBX missile) -> AL, from nuclear_subs' missile hit entry (which marks the use and does the blast):
    # under the armageddon flag, a heavy SSM of a nation with the warhead research that the doctrine lets fire (and
    # pay for) a nuclear missile. Keeps all but EAX.
    c = Code(at["nuclear_ssm"]); c.emit(b"\x51\x52\x80\x3d"); c.u32(doctrine["armageddon"]); c.emit(b"\x00")
    c.branch(b"\x0f\x84", "no"); c.emit(b"\x83\x7b"+bytes([MISSILE["kind"], HEAVY_SSM])); c.branch(b"\x0f\x85", "no")
    c.emit(b"\x8b\x53"+bytes([MISSILE["side"]]))                                 # the side's nation, kept on the stack
    if side_nation: c.branch(b"\xe8", side_nation)
    c.emit(b"\x52"); combat.researched(c, n, b"\x8b\x14\x24", warhead, "asked"); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "drop")
    c.emit(b"\x8b\x14\x24"); c.branch(b"\xe8", doctrine["use_missile"]); c.emit(b"\x83\xc4\x04"); c.branch(b"\xe9", "out")
    c.mark("drop"); c.emit(b"\x83\xc4\x04")
    c.mark("no"); c.emit(b"\x33\xc0")
    c.mark("out"); c.emit(b"\x5a\x59\xc3")
    code["nuclear_ssm"] = c.finish()

    # SAMs at aircraft (a procedure nested in AttackShips: EBX kind, ESI the aircraft a hit strikes less one,
    # [ebp+8] the attack's frame: [-30h] the firing ship, [-0Ch] the formation): a nuclear hit strikes up to
    # NUCLEAR_SAM_AIRCRAFT of the formation's aircraft left.
    c = Code(at["sam_air"]); c.emit(b"\x60\x8b\x45\x08\x8b\x40\xd0\x8b\xd3"); c.branch(b"\xe8", at["nuclear_sam"])
    c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "native_pop")
    c.emit(b"\x8b\x45\x08\x8b\x40\xf4\x8b\x48"+bytes([FORMATION["aircraft"]])+b"\x2b\x88"); c.u32(FORMATION["destroyed"])
    c.emit(b"\x83\xf9"+bytes([NUCLEAR_SAM_AIRCRAFT])); c.branch(b"\x0f\x8e", "few"); c.emit(b"\xb9"); c.u32(NUCLEAR_SAM_AIRCRAFT)
    c.mark("few"); c.emit(b"\x49"); c.branch(b"\x0f\x8d", "count"); c.emit(b"\x33\xc9")
    c.mark("count"); c.emit(b"\x89\x4c\x24\x04")                                   # ESI after POPAD
    c.emit(b"\x8b\x45\x08\x8b\x48\xd0\xba"); c.u32(at["text"]+12); c.emit(b"\xa1"); c.u32(n["battle_log"])
    c.emit(b"\x8b\x38\xff\x57\x40")
    c.mark("native_pop"); c.emit(b"\x61\x85\xf6"); c.branch(b"\x0f\x8c", n["sam_air_skip"]); c.branch(b"\xe9", n["sam_air_back"])
    code["sam_air"] = c.finish()

    # DPPossible's calibre switch (EAX calibre; ESI barrels, triple and quadruple turrets already refused): 7 and 8
    # inches need each HEAVY_DP_RESEARCH, asked of the designer form's nation as the native cases do; the answer
    # goes in EBX to the native tail (twin mounts also need the twin DP mounting).
    c = Code(at["dp_rule"]); c.emit(b"\x83\xf8"+bytes([min(HEAVY_DP)])); c.branch(b"\x0f\x8c", "native")
    c.emit(b"\x83\xf8"+bytes([max(HEAVY_DP)])); c.branch(b"\x0f\x8f", "native")
    for ident in HEAVY_DP_RESEARCH:
        c.emit(b"\xa1"); c.u32(n["designer"]); c.emit(b"\x8b\x00\x8b\x80"); c.u32(DESIGNER_NATION)
        c.emit(b"\xba"); c.u32(ident); c.branch(b"\xe8", n["has_research"]); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "answer")
    c.mark("answer"); c.emit(b"\x0f\xb6\xd8"); c.branch(b"\xe9", n["dp_tail"])
    c.mark("native"); c.emit(bytes.fromhex(n["originals"]["dp_rule"])); c.branch(b"\xe9", n["dp_back"])
    code["dp_rule"] = c.finish()
    # GetCalibreAAvalue(EAX ship, EDX battery, ECX quality) -> EAX at its entry: a 7- or 8-inch gun's value, one
    # more when the battery is autoloaded ([ship+battery+87h], as the native 6-inch case). Keeps EBX, ESI, EDI.
    c = Code(at["aa_value"]); c.emit(b"\x51\x8b\x4c\x90\x69\x83\xf9"+bytes([min(HEAVY_DP)])); c.branch(b"\x0f\x8c", "native")
    c.emit(b"\x83\xf9"+bytes([max(HEAVY_DP)])); c.branch(b"\x0f\x8f", "native")
    c.emit(b"\xb9"); c.u32(HEAVY_DP[8]); c.branch(b"\x0f\x84", "loaded")          # flags still from CMP ECX,8
    c.emit(b"\xb9"); c.u32(HEAVY_DP[7])
    c.mark("loaded"); c.emit(b"\x80\xbc\x10\x87\x00\x00\x00\x00"); c.branch(b"\x0f\x84", "value"); c.emit(b"\x41")
    c.mark("value"); c.emit(b"\x8b\xc1\x59\xc3")
    c.mark("native"); c.emit(b"\x59"+bytes.fromhex(n["originals"]["aa_value"])); c.branch(b"\xe9", n["aa_back"])
    code["aa_value"] = c.finish()

    # tanker(EAX formation) -> EAX range percent (100 without). Keeps EBX, ESI, EDI, EBP.
    (refuel, refuel_percent), (drones, drone_percent) = tree.AERIAL_REFUELLING, tree.CARRIER_TANKERS
    c = Code(at["tanker"]); c.emit(b"\x53\x56\x8b\xf0\x8b\x5e"+bytes([FORMATION_BASE])+b"\x85\xdb"); c.branch(b"\x0f\x84", "none")
    c.emit(b"\x80\xbb"); c.u32(0x9D3); c.emit(bytes([AIRFIELD])); c.branch(b"\x0f\x85", "carrier")
    combat.researched(c, n, b"\x8b\x56"+bytes([FORMATION_NATION]), refuel, "land"); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "none")
    c.emit(b"\xb8"); c.u32(refuel_percent); c.branch(b"\xe9", "out")
    c.mark("carrier"); c.emit(b"\x8b\xc3"); c.branch(b"\xe8", n["is_carrier"]); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "none")
    combat.researched(c, n, b"\x8b\x56"+bytes([FORMATION_NATION]), drones, "drones"); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "none")
    c.emit(b"\x8b\xc3"); c.branch(b"\xe8", n["has_special"]); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "none")
    c.emit(b"\xb8"); c.u32(drone_percent); c.branch(b"\xe9", "out")
    c.mark("none"); c.emit(b"\xb8\x64\x00\x00\x00")
    c.mark("out"); c.emit(b"\x5e\x5b\xc3")
    code["tanker"] = c.finish()
    # SetFullFuelLoad's end (EBX formation, EAX its aircraft's endurance): the fuel, times the tanker percent.
    c = Code(at["fuel"]); c.emit(b"\x89\x43"+bytes([FUEL])+b"\x60\x8b\xc3"); c.branch(b"\xe8", at["tanker"])
    c.emit(b"\x0f\xaf\x43"+bytes([FUEL])+b"\xb9\x64\x00\x00\x00\x99\xf7\xf9\x89\x43"+bytes([FUEL])+b"\x61\x5b\xc3")
    code["fuel"] = c.finish()
    # Called in place of GetCombatRadiusInNm(EAX type, EDX load) where the formation is in EBX, at [EBX] or at
    # [EBP-8]: the radius times the tanker percent.
    c = Code(at["radius"])
    c.mark("ebx"); c.branch(b"\xe8", n["radius"]); c.emit(b"\x50\x8b\xc3"); c.branch(b"\xe9", "scale")
    c.mark("slot"); c.branch(b"\xe8", n["radius"]); c.emit(b"\x50\x8b\x03"); c.branch(b"\xe9", "scale")
    c.mark("frame"); c.branch(b"\xe8", n["radius"]); c.emit(b"\x50\x8b\x45\xf8")
    c.mark("scale"); c.branch(b"\xe8", at["tanker"]); c.emit(b"\x0f\xaf\x04\x24\x59\xb9\x64\x00\x00\x00\x99\xf7\xf9\xc3")
    code["radius"] = c.finish()
    radius_entry = {kind: at["radius"]+c.labels[kind] for kind in RADIUS_CALLS}

    blocks = [dict(name="Air defence: hypervelocity shots", address=at["shots"], bytes="00"*4),
              dict(name="Air defence: nuclear SAM text", address=at["text"], bytes=literal(TEXT).hex())]
    for name, body in code.items():
        if len(body) > ROOM[name]: raise ValueError("Air defence code exceeds its reservation: "+name)
        blocks.append(dict(name="Air defence: "+name, address=at[name], bytes=body.hex()))
    plans = []
    for name, address in n["sites"].items():
        old = bytes.fromhex(n["originals"][name])
        target = at[CALLS.get(name, name)]
        new = (b"\xe8" if name in CALLS else b"\xe9")+struct.pack("<i", target-address-5)+b"\x90"*(len(old)-5)
        plans.append(patch("Air defence: "+name, address, old, new))
    for kind, sites in n["radius_calls"].items():
        for address in sites:
            plans.append(patch("Air defence: tanker range", address, b"\xe8"+struct.pack("<i", n["radius"]-address-5),
                               b"\xe8"+struct.pack("<i", radius_entry[kind]-address-5)))
    return blocks, plans
