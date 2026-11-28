"""Undersea warfare in battle: guided torpedoes home, anti-torpedo torpedoes, submarines move.

- Guided torpedoes (modern_tree.GUIDED_TORPEDOES, 1977): modern_combat records a researching nation's ship torpedoes
  and their target at FireTorpedo; sub_launch records a submarine's (FireSubTorpedo; the nation of its battle side)
  in the same table. MoveMe natively steers only missiles; homing steers a recorded torpedo at its target every step
  while that ship is afloat (wire guidance, then the wake homer). Its range still runs out, and modern_combat's wider
  hit window stays.
- Anti-torpedo torpedoes (tree.ANTI_TORPEDO, 2013; point_defence's ATT box, launchers in data bits 12-13): when an
  enemy torpedo comes within ATT_YARDS of a ship with launchers and ATTs left (point_defence.ATT load a launcher;
  the ones fired are the low byte of the battle flags dword), the ship fires one at it: ATT_CHANCE% for one launcher,
  +ATT_STEP% a launcher more, at most ATT_CAP%. A torpedo is engaged once (ENGAGED_SLOTS remembered, by address and
  remaining range, so a later torpedo at the same address is new). modern_combat's hit test asks att.
- Moving submarines: natively a battle's submarines never move. Each battle minute every submarine still in the
  fight (counted from the second call of a battle; a clock jump of more than MAX_MINUTES starts the count again)
  closes on the nearest enemy ship that is afloat (not a land battery, not neutral) at SUB_SPEED knots
  (NUCLEAR_SPEED for SSN and SSBN, by nuclear_subs' name rule) until that ship is within HOLD_PERCENT% of its
  torpedo range; then it holds and attacks as before. A submarine only hears ships within HEAR_YARDS, and the
  player's ships from twice as far while their sonar is ACTIVE.
- Sonar: natively the battle map never draws enemy torpedoes. One is drawn while a ship of the player's side is
  within reach of it: its wake by eye (WAKE yards; QUIET_WAKE when the firing nation has oxygen or electric
  torpedoes), or by ear (LISTEN, the player's best hydrophone or sonar research; 50% farther with ACTIVE sonar).
  nuclear_strike's SONAR button (right of EMCON) switches the player's sonar between PASSIVE and ACTIVE.
Part of the modern-research adapter; imported lazily.
"""
import hashlib
import struct
import modern_tree as tree
import modern_extension as extension
import point_defence

BASE = 0x301000
ATT_YARDS, ATT_CHANCE, ATT_STEP, ATT_CAP = 1500, 40, 10, 60
ENGAGED_SLOTS = 64
SUB_SPEED, NUCLEAR_SPEED, HOLD_PERCENT, MAX_MINUTES, HEAR_YARDS = 8, 20, 66, 10, 12000
WAKE, QUIET_WAKE, QUIET_TORPEDOES = 1500, 400, (916, 929)       # yards; Oxygen fuelled, Electric torpedoes
LISTEN = ((1107, 1000), (1113, 2000), (1122, 3000), (1140, 4000))   # hydrophones, Enhanced sonar, digital passive
YARDS_PER_KNOT_MINUTE = (2025, 60)       # a knot is 2,025 yards an hour
SUB = dict(name=4, side=8, state=0x10, position=0x14, torpedo_range=0x40)   # battle TSubmarine
OUT = 0x7FFFFFFF                          # its state when it is out of the fight
SHIP = dict(side=0xA55, kind=0x9D3, position=0xA1C, out=0xA9F)
NEUTRAL, LAND = 3, 12
SITES = (("homing", 0x925BEF, "8bc3e8eaffffff"),      # MoveMe: mov eax,ebx; call IsMissile
         ("sub_launch", 0x8766B9, "8b43143b463c"),     # FireSubTorpedo: mov eax,[ebx+14h]; cmp eax,[esi+3Ch]
         ("submarines", 0x89F87A, "a12c749f00"),       # the battle's submarine pass: mov eax,[submarines]
         ("seen", 0x89DDC1, "8bc3e8187e0800"))         # drawing shots, an enemy one: mov eax,ebx; call IsMissile
WINDOWS = ((0x925BE0, 0x32, "d1e4d0680b7b4db0b98d376bd9a2b3c8de6e1e8f34439bfd0c8403286801c337"),   # IsMissile, MoveMe aim
           (0x8766A3, 0x22, "106218c6fd1a13aad0696ad87b898103f5cc158695074af96d697223085050ed"),   # FireSubTorpedo tail
           (0x89F86C, 0x2C, "2f45f0e3a2faec906a182c80fc07b703e814b1b379961ba5198c5982068b73fc"),   # submarine pass head
           (0x89DDA1, 0x3A, "3ad014d3ce191eb900b5c0512579b70d72e6ee33f53936a44682567b87ab3e54"))                                                         # which shots are drawn
NATIVE = dict(is_missile=0x925BE0, aim=0x925C01, straight=0x925C12, missile=0x925BFA, afloat=0x90E46C,
              sub_back=0x8766BF, pass_back=0x89F87F, submarines=0x9F742C, ships=0x9F79D8, minute=0x9F71B8, player_side=0x9F7008,
              distance=0x90F18C, bearing=0x573314, move=0x57319C, globe_units=0x55C894, random=0x307834,
              name=0x9045A8, cat_n=0x30C71C, list_get=0x3B6D6C, seven=0x8C3784, draw=0x89DDD0, hide=0x89DF71)
TEXT = dict(att=" fires an anti-torpedo torpedo: incoming torpedo destroyed!")
OFFSETS = dict(att=0x100, targets=0x800, sonar_button=0x600)   # modern_combat's, nuclear_strike's SONAR code


def addresses(page):
    return {name: page+offset for name, offset in OFFSETS.items()}


def discover(blob, base, normalized):
    for (name, address, original), (window, size, digest) in zip(SITES, WINDOWS):
        if normalized[address-BASE:address-BASE+len(original)//2].hex() != original:
            raise ValueError("Undersea warfare refuses changed native code: "+name)
        if hashlib.sha256(normalized[window-BASE:window-BASE+size]).hexdigest() != digest:
            raise ValueError("Undersea warfare refuses changed native code near "+hex(window))
    delta = base-BASE
    info = {k: v+delta for k, v in NATIVE.items()}
    for key, operand in (("submarines", 0x89F87B), ("ships", 0x8B80C8), ("minute", 0x89F8C0), ("player_side", 0x89DDA6)):
        info[key] = struct.unpack_from("<I", blob, operand-BASE)[0]   # data pointers, as the code loads them
    info["sites"] = [dict(name=name, address=address+delta, original=blob[address-BASE:address-BASE+len(original)//2].hex())
                     for name, address, original in SITES]   # as loaded: the pass's MOV carries an absolute address
    import modern_combat as combat
    info["main"] = struct.unpack_from("<I", blob, combat.MAIN_LOAD-BASE+1)[0]
    info["nation"], info["has_research"] = combat.NATIVE["nation"]+delta, combat.NATIVE["has_research"]+delta
    return info


def build(page, info, combat_page, ext, side_nation, is_kind, sonar=None):
    """One page. combat_page: modern_combat's (its guided torpedo table and cursor); side_nation: modern_recon's;
    is_kind: nuclear_subs' (EAX name -> EAX 0, 1 SSN, 2 SSBN); sonar: nuclear_strike's flag byte (1: the player's
    sonar is ACTIVE; its button's code goes at addresses()["sonar_button"]). Returns blocks, patches, and the
    targets table that modern_combat's launch hook fills."""
    from campaign_security import Code   # imported late: campaign_security imports modern_research
    from hull_rules import patch
    import modern_combat as combat
    n = info
    at = dict(homing=page, att=page+OFFSETS["att"], sub_launch=page+0x300, submarines=page+0x380, move=page+0x400,
              targets=page+0x800, engaged=page+0xA00, engaged_cursor=page+0xC00, last_minute=page+0xC04,
              elapsed=page+0xC08, text=page+0xC40, seen=page+0x780, detected=page+0xD00)
    torpedoes, cursor = combat_page+combat.TORPEDOES, combat_page+combat.CURSOR
    slots, code = combat.TORPEDO_SLOTS, {}
    delta = at["targets"]-torpedoes

    # MoveMe, EBX shot: a missile aims at its target natively; a recorded torpedo aims at its afloat target.
    c = Code(at["homing"]); c.emit(b"\x8b\xc3"); c.branch(b"\xe8", n["is_missile"]); c.emit(b"\x84\xc0")
    c.branch(b"\x0f\x85", n["missile"])
    c.emit(b"\xb9"); c.u32(slots); c.emit(b"\xba"); c.u32(torpedoes)
    c.mark("scan"); c.emit(b"\x39\x1a"); c.branch(b"\x0f\x84", "found"); c.emit(b"\x83\xc2\x04\x49"); c.branch(b"\x0f\x85", "scan")
    c.branch(b"\xe9", n["straight"])
    c.mark("found"); c.emit(b"\x8b\xb2"); c.u32(delta & 0xFFFFFFFF); c.emit(b"\x85\xf6"); c.branch(b"\x0f\x84", n["straight"])
    c.emit(b"\x8b\xc6"); c.branch(b"\xe8", n["afloat"]); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", n["straight"])
    c.branch(b"\xe9", n["aim"])                                                          # ESI target: aim at it
    code["homing"] = c.finish()

    def record(c):   # EBX torpedo, [ebp-4] its target: forget the address, then remember both (as modern_combat)
        c.emit(b"\xb9"); c.u32(slots); c.emit(b"\xbf"); c.u32(torpedoes)
        c.mark("forget"); c.emit(b"\x39\x1f"); c.branch(b"\x0f\x85", "kept"); c.emit(b"\xc7\x07\x00\x00\x00\x00")
        c.mark("kept"); c.emit(b"\x83\xc7\x04\x49"); c.branch(b"\x0f\x85", "forget")
        c.emit(b"\xa1"); c.u32(cursor); c.emit(b"\x89\x1c\x85"); c.u32(torpedoes)
        c.emit(b"\x8b\x55\xfc\x89\x14\x85"); c.u32(at["targets"])
        c.emit(b"\x40\x25"); c.u32(slots-1); c.emit(b"\xa3"); c.u32(cursor)

    # FireSubTorpedo, EBX new torpedo, ESI submarine, [ebp-4] target: a guided one when its side's nation has it.
    c = Code(at["sub_launch"]); c.emit(b"\x60\x8b\x56"+bytes([SUB["side"]])); c.branch(b"\xe8", side_nation)
    combat.researched(c, n, b"", tree.GUIDED_TORPEDOES[0], "asked"); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "done")
    record(c)
    c.mark("done"); c.emit(b"\x61"+bytes.fromhex(SITES[1][2])); c.branch(b"\xe9", n["sub_back"])
    code["sub_launch"] = c.finish()

    # att(EBX torpedo, ESI ship, EBP the hit test's frame: [ebp-18h] yards, [ebp-0Ch] battle form, [ebp-2Ch] and
    # [ebp-28h] its string locals) -> AL 1 when the ship's anti-torpedo torpedo destroyed it (the battle log says so).
    c = Code(at["att"]); c.emit(b"\x60\x81\x7d\xe8"); c.u32(ATT_YARDS); c.branch(b"\x0f\x8f", "no")
    c.emit(b"\x8b\x43\x3e\x83\xf8\x02"); c.branch(b"\x0f\x8c", "side"); c.emit(b"\x83\xe8\x02")   # a submarine's: side+2
    c.mark("side"); c.emit(b"\x3b\x86"); c.u32(SHIP["side"]); c.branch(b"\x0f\x84", "no")
    c.emit(b"\x8b\xc6"); c.branch(b"\xe8", ext); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "no"); c.emit(b"\x8b\xf8")
    att = point_defence.ATT
    c.emit(b"\x8b\x0f\xc1\xe9"+bytes([att["shift"]])+b"\x83\xe1"+bytes([att["mask"]])); c.branch(b"\x0f\x84", "no")
    c.emit(b"\x6b\xd1"+bytes([att["load"]])+b"\x0f\xb6\x47"+bytes([extension.BATTLE_FLAGS])+b"\x3b\xc2")
    c.branch(b"\x0f\x8d", "no")                                                            # none left
    c.emit(b"\x51\xba"); c.u32(at["engaged"]); c.emit(b"\xb8"); c.u32(ENGAGED_SLOTS)          # [esp] launchers
    c.mark("scan"); c.emit(b"\x39\x1a"); c.branch(b"\x0f\x85", "other")
    c.emit(b"\x8b\x4b\x1c\x39\x4a\x04"); c.branch(b"\x0f\x8d", "seen")                    # this torpedo: engaged
    c.mark("other"); c.emit(b"\x83\xc2\x08\x48"); c.branch(b"\x0f\x85", "scan")
    c.emit(b"\xa1"); c.u32(at["engaged_cursor"]); c.emit(b"\x89\x1c\xc5"); c.u32(at["engaged"])
    c.emit(b"\x8b\x53\x1c\x89\x14\xc5"); c.u32(at["engaged"]+4)
    c.emit(b"\x40\x25"); c.u32(ENGAGED_SLOTS-1); c.emit(b"\xa3"); c.u32(at["engaged_cursor"])
    c.emit(b"\xfe\x47"+bytes([extension.BATTLE_FLAGS])+b"\x59")                          # one fired; ECX launchers
    c.emit(b"\x8b\xc1\x48\x6b\xc0"+bytes([ATT_STEP])+b"\x83\xc0"+bytes([ATT_CHANCE])+b"\x83\xf8"+bytes([ATT_CAP]))
    c.branch(b"\x0f\x8e", "capped"); c.emit(b"\xb8"); c.u32(ATT_CAP)
    c.mark("capped"); c.emit(b"\x50\xb8\x64\x00\x00\x00"); c.branch(b"\xe8", n["random"]); c.emit(b"\x5a\x3b\xc2")
    c.branch(b"\x0f\x8d", "no")
    c.emit(b"\x68"); c.u32(n["seven"]); c.emit(b"\x8d\x55\xd4\x8b\xc6"); c.branch(b"\xe8", n["name"])     # '7', name, text
    c.emit(b"\xff\x75\xd4\x68"); c.u32(at["text"]+12); c.emit(b"\x8d\x45\xd8\xba\x03\x00\x00\x00"); c.branch(b"\xe8", n["cat_n"])
    c.emit(b"\x8b\x55\xd8\x8b\x45\xf4\x8b\x80"); c.u32(0x7F8); c.emit(b"\x8b\xce\x8b\x30\xff\x56\x40")
    c.emit(b"\xc7\x44\x24\x1c\x01\x00\x00\x00\x61\xc3")
    c.mark("seen"); c.emit(b"\x59")
    c.mark("no"); c.emit(b"\xc7\x44\x24\x1c\x00\x00\x00\x00\x61\xc3")
    code["att"] = c.finish()

    # The submarine pass: move them first, then the native pass.
    c = Code(at["submarines"]); c.branch(b"\xe8", at["move"]); c.emit(b"\xa1"); c.u32(n["submarines"])
    c.branch(b"\xe9", n["pass_back"])
    code["submarines"] = c.finish()

    # move(): the battle minutes since the last call (none in a new battle), then each submarine closes in.
    per_minute, per_hour = YARDS_PER_KNOT_MINUTE
    c = Code(at["move"]); c.emit(b"\x60\xa1"); c.u32(n["minute"]); c.emit(b"\x8b\x00\x8b\xd0\x2b\x15"); c.u32(at["last_minute"])
    c.emit(b"\xa3"); c.u32(at["last_minute"]); c.emit(b"\x85\xd2"); c.branch(b"\x0f\x8e", "done")
    c.emit(b"\x83\xfa"+bytes([MAX_MINUTES])); c.branch(b"\x0f\x8f", "done")                 # a jump: a new clock
    c.emit(b"\x89\x15"); c.u32(at["elapsed"])
    c.emit(b"\xa1"); c.u32(n["submarines"]); c.emit(b"\x8b\x00\x85\xc0"); c.branch(b"\x0f\x84", "done")
    c.emit(b"\x8b\x48\x08\x85\xc9"); c.branch(b"\x0f\x8e", "done")
    c.mark("sub"); c.emit(b"\x49"); c.branch(b"\x0f\x88", "done"); c.emit(b"\x51")          # [esp] index
    c.emit(b"\xa1"); c.u32(n["submarines"]); c.emit(b"\x8b\x00\x8b\x40\x04\x8b\x1c\x88")   # EBX submarine
    c.emit(b"\x81\x7b"+bytes([SUB["state"]])); c.u32(OUT); c.branch(b"\x0f\x8d", "next")
    # the nearest enemy afloat: ESI ship, EBP its yards
    c.emit(b"\x33\xf6\xbd\xff\xff\xff\x7f\xa1"); c.u32(n["ships"]); c.emit(b"\x8b\x00\x85\xc0"); c.branch(b"\x0f\x84", "chosen")
    c.emit(b"\x8b\x78\x08")
    c.mark("ship"); c.emit(b"\x4f"); c.branch(b"\x0f\x88", "chosen")
    c.emit(b"\xa1"); c.u32(n["ships"]); c.emit(b"\x8b\x00\x8b\x40\x04\x8b\x04\xb8")       # EAX ship
    c.emit(b"\x8b\x90"); c.u32(SHIP["side"]); c.emit(b"\x83\xfa"+bytes([NEUTRAL])); c.branch(b"\x0f\x84", "ship")
    c.emit(b"\x3b\x53"+bytes([SUB["side"]])); c.branch(b"\x0f\x84", "ship")
    c.emit(b"\x80\xb8"); c.u32(SHIP["kind"]); c.emit(bytes([LAND])); c.branch(b"\x0f\x84", "ship")
    c.emit(b"\x50"); c.branch(b"\xe8", n["afloat"]); c.emit(b"\x84\xc0\x58"); c.branch(b"\x0f\x84", "ship")
    c.emit(b"\x50\x8d\x53"+bytes([SUB["position"]])); c.branch(b"\xe8", n["distance"]); c.emit(b"\x5a")
    c.emit(b"\x3d"); c.u32(HEAR_YARDS); c.branch(b"\x0f\x8e", "heard")                     # within hearing
    if sonar:   # the player's pinging ships are heard twice as far
        c.emit(b"\x80\x3d"); c.u32(sonar); c.emit(b"\x00"); c.branch(b"\x0f\x84", "ship")
        c.emit(b"\x8b\x0d"); c.u32(n["player_side"]); c.emit(b"\x8b\x09\x3b\x8a"); c.u32(SHIP["side"]); c.branch(b"\x0f\x85", "ship")
        c.emit(b"\x3d"); c.u32(2*HEAR_YARDS); c.branch(b"\x0f\x8e", "heard")
    c.branch(b"\xe9", "ship")
    c.mark("heard"); c.emit(b"\x3b\xc5"); c.branch(b"\x0f\x8d", "ship"); c.emit(b"\x8b\xe8\x8b\xf2"); c.branch(b"\xe9", "ship")
    c.mark("chosen"); c.emit(b"\x85\xf6"); c.branch(b"\x0f\x84", "next")
    c.emit(b"\x8b\x43"+bytes([SUB["torpedo_range"]])+b"\x85\xc0"); c.branch(b"\x0f\x8f", "range"); c.emit(b"\xb8\xa0\x0f\x00\x00")
    c.mark("range"); c.emit(b"\x6b\xc0"+bytes([HOLD_PERCENT])+b"\xb9\x64\x00\x00\x00\x99\xf7\xf9\x3b\xe8"); c.branch(b"\x0f\x8e", "next")
    # yards this time: knots x minutes x 2025 / 60, at most the gap left
    c.emit(b"\x8b\x43"+bytes([SUB["name"]])); c.branch(b"\xe8", is_kind)
    c.emit(b"\xb9"); c.u32(SUB_SPEED); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "speed"); c.emit(b"\xb9"); c.u32(NUCLEAR_SPEED)
    c.mark("speed"); c.emit(b"\x0f\xaf\x0d"); c.u32(at["elapsed"]); c.emit(b"\x69\xc9"); c.u32(per_minute)
    c.emit(b"\x8b\xc1\x99\xb9"); c.u32(per_hour); c.emit(b"\xf7\xf9\x3b\xc5"); c.branch(b"\x0f\x8e", "step"); c.emit(b"\x8b\xc5")
    c.mark("step"); c.emit(b"\x50\xdb\x04\x24\x83\xc4\xf8\xdb\x3c\x24\x9b\xb0\x0c"); c.branch(b"\xe8", n["globe_units"])
    c.emit(b"\x50")                                                                      # [esp] globe units
    c.emit(b"\x8d\x96"); c.u32(SHIP["position"]); c.emit(b"\x8d\x43"+bytes([SUB["position"]])); c.branch(b"\xe8", n["bearing"])
    c.emit(b"\x59\x83\xec\x0c\x8b\xd4\x52\x8b\xd0\x8d\x43"+bytes([SUB["position"]])); c.branch(b"\xe8", n["move"])
    c.emit(b"\x8b\x04\x24\x89\x43"+bytes([SUB["position"]])+b"\x8b\x44\x24\x04\x89\x43"+bytes([SUB["position"]+4]))
    c.emit(b"\x8b\x44\x24\x08\x89\x43"+bytes([SUB["position"]+8])+b"\x83\xc4\x0c")
    c.mark("next"); c.emit(b"\x59\x85\xc9"); c.branch(b"\x0f\x85", "sub")
    c.mark("done"); c.emit(b"\x61\xc3")
    code["move"] = c.finish()

    # Drawing shots, EBX an enemy shot (EDI the form): missiles natively, torpedoes once detected.
    c = Code(at["seen"]); c.emit(b"\x8b\xc3"); c.branch(b"\xe8", n["is_missile"]); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x85", n["draw"])
    c.branch(b"\xe8", at["detected"]); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x85", n["draw"]); c.branch(b"\xe9", n["hide"])
    code["seen"] = c.finish()
    # detected(EBX torpedo) -> AL 1 when a ship of the player's side sees its wake or hears it. Keeps the rest.
    c = Code(at["detected"]); c.emit(b"\x60\x8b\x53\x3e\x83\xfa\x02"); c.branch(b"\x0f\x8c", "firer"); c.emit(b"\x83\xea\x02")
    c.mark("firer"); c.branch(b"\xe8", side_nation); c.emit(b"\x52\xbd"); c.u32(WAKE)          # [esp] the firer's nation
    for ident in QUIET_TORPEDOES:
        c.emit(b"\x8b\x14\x24"); combat.researched(c, n, b"", ident, f"asked{ident}"); c.emit(b"\x84\xc0")
        c.branch(b"\x0f\x85", "quiet")
    c.branch(b"\xe9", "woke")
    c.mark("quiet"); c.emit(b"\xbd"); c.u32(QUIET_WAKE)
    c.mark("woke"); c.emit(b"\x5a\x8b\x15"); c.u32(n["player_side"]); c.emit(b"\x8b\x12\x52"); c.branch(b"\xe8", side_nation)
    c.emit(b"\x52\x33\xff")                                                                 # [esp] the player's nation
    for ident, yards in LISTEN:
        c.emit(b"\x8b\x14\x24"); combat.researched(c, n, b"", ident, f"listen{ident}"); c.emit(b"\x84\xc0")
        c.branch(b"\x0f\x84", f"deaf{ident}"); c.emit(b"\xbf"); c.u32(yards); c.mark(f"deaf{ident}")
    c.emit(b"\x5a")
    if sonar:
        c.emit(b"\x80\x3d"); c.u32(sonar); c.emit(b"\x00"); c.branch(b"\x0f\x84", "passive"); c.emit(b"\x8b\xc7\xd1\xe8\x03\xf8")
        c.mark("passive")
    c.emit(b"\x3b\xfd"); c.branch(b"\x0f\x8e", "reach"); c.emit(b"\x8b\xef")
    c.mark("reach"); c.emit(b"\xa1"); c.u32(n["ships"]); c.emit(b"\x8b\x00\x85\xc0"); c.branch(b"\x0f\x84", "unseen")
    c.emit(b"\x8b\x78\x08")                                                                 # [esp] the player's side
    c.mark("ship"); c.emit(b"\x4f"); c.branch(b"\x0f\x88", "unseen")
    c.emit(b"\xa1"); c.u32(n["ships"]); c.emit(b"\x8b\x00\x8b\x40\x04\x8b\x34\xb8")       # ESI ship
    c.emit(b"\x8b\x86"); c.u32(SHIP["side"]); c.emit(b"\x3b\x04\x24"); c.branch(b"\x0f\x85", "ship")
    c.emit(b"\x8b\xc6"); c.branch(b"\xe8", n["afloat"]); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "ship")
    c.emit(b"\x8b\xc6\x8d\x53\x04"); c.branch(b"\xe8", n["distance"]); c.emit(b"\x3b\xc5"); c.branch(b"\x0f\x8f", "ship")
    c.emit(b"\x5a\xc7\x44\x24\x1c\x01\x00\x00\x00\x61\xc3")
    c.mark("unseen"); c.emit(b"\x5a\xc7\x44\x24\x1c\x00\x00\x00\x00\x61\xc3")
    code["detected"] = c.finish()

    room = dict(homing=0x80, att=0x200, sub_launch=0x80, submarines=0x20, move=0x200, seen=0x40, detected=0x300)
    blocks = []
    for name, body in code.items():
        if len(body) > room[name]: raise ValueError(f"Undersea code exceeds its reservation: {name} ({len(body):#x})")
        blocks.append(dict(name="Undersea: "+name, address=at[name], bytes=body.hex()))
    blocks.append(dict(name="Undersea: targets", address=at["targets"], bytes="00"*4*slots))
    blocks.append(dict(name="Undersea: engaged", address=at["engaged"], bytes="00"*(8*ENGAGED_SLOTS+12)))
    text = TEXT["att"]
    blocks.append(dict(name="Undersea: text", address=at["text"],
                       bytes=(struct.pack("<HHiI", 1200, 2, -1, len(text))+text.encode("utf-16-le")+b"\0\0").hex()))
    plans = []
    for site in info["sites"]:
        old = bytes.fromhex(site["original"])
        plans.append(patch("Undersea: "+site["name"], site["address"], old,
                           b"\xe9"+struct.pack("<i", at[site["name"]]-site["address"]-5)+b"\x90"*(len(old)-5)))
    return blocks, plans, at["targets"]
