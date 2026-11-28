"""Missile defence by radar class and doctrine.

The game resolves each incoming missile against its target's SAMs in SAMIntercept (0x91AD8C): FireSAM spends two
missiles of a kind (medium and heavy launchers that already fired this turn are busy 60% of the time), and each
shot's chance falls by a third for every missile the ship has already had to deal with this turn (ship +E01h).
That is a salvo model with one kind of fire control for every ship. This module makes the search radar class and
the player's doctrine count in it:
- Fire-control channels: a ship with a working phased array (radar class 6) frees its busy medium and heavy
  launchers FREE[6]% of the time before a shot, an AESA ship (class 7) FREE[7]%: busy 24% and 9% instead of 60%.
- Saturation: the count of missiles already dealt with is halved for class 6 and quartered for class 7.
- Missile flight: a medium or light SSM (SKIMMERS; heavy ones cruise high) whose nation has a
  modern_tree.MISSILE_FLIGHT research (sea-skimming, then terminal manoeuvres) counts as one more missile already
  dealt with for each, before the radar class divides the count:
  a third off every SAM shot against it for an old radar, little against AESA. On its own page (flight).
- Doctrine (shell_doctrine's Conserve tick box, the player only): one SAM a shot instead of two, so the cells
  last twice as long and each engagement is weaker.
- Quad-packed light SAMs (modern_tree.QUAD_PACK research): a light SAM VLS bank holds four missiles a cell.
  FireSAM spends whole missiles from a bank, so three engagements in four the light SAMs fired go back into a
  VLS bank that is not full: four times the engagements from the same cells, against missiles and aircraft alike
  (the two anti-aircraft FireSAM calls go through a wrapper; before 1.43.5 only missile defence got them back).
  The displays still count cells: an 8-cell bank shows 8.
- Readout: the battle ship panel's status line (fire and flight-deck warnings), when it is empty, shows the
  missiles a ship with launchers has left, as "SAM n, SSM n" (loaded and reloads, not destroyed mounts).
- Electronic warfare: the game decoys a missile with 4% + 9% a level of its hidden ECM technology (0x91AF38,
  ESI the percent, EBP the ship, EDI the missile's nation). A ship designed from a modern_tree.EW_SUITES
  research's year by a nation that has it adds that suite's percent (jammers, then active decoys); the
  attacker's EW_SEEKER research takes some back. There is no designer box: the suite comes with the design year.
- Anti-ship ballistic missiles: a land battery (type 12) of a nation with modern_tree.ASBM launches its missiles
  with modern_railgun's hypersonic flag (asbm, called from that module's launch wrappers): five times the flight
  speed and defences that stop only 30% as many. Range is the native one.
FireSAM itself is not touched: VLS Cells audits and hooks it.
Mission kills are in nuclear_subs' missile-hit entry: a missile hit damages the radar more often.
Part of the modern-research adapter; imported lazily.
"""
import hashlib
import struct

BASE = 0x301000
ASBM = 0x180                           # offset of asbm in the flight page (modern_railgun calls it)
FREE = {6: 60, 7: 85}
SHIP = dict(nation=0x14, radar=0xA0B, radar_down=0xA0F, busy=0xDE7, handled=0xE01)
WINDOWS = ((0x91AD8C, 0x1A6, None),                        # SAMIntercept
           (0x6D0246, 0x4D, None),                         # battle ship panel: the status line
           (0x91AF38, 0xC8, None))                         # the countermeasures (decoy) roll
DIGESTS = (
    "fe7f027cd477cc4464a55142f634d68e20820cf1d1f4a3cfa869af7e6e9eb2d2",
    "3a78280f30263a73dc669e89d87c1eea3933a07da69f61b0488d6a431405537b",
    "063a5db73b8b6671dcc485e48b2e059ed6eece5f40ede30581237e7ed4aed62a",
)
SITES = (("shots", 0x91ADF1, "33c98bd38bc6"), ("handled", 0x91AE38, "8b8e010e0000"),
         ("fired", 0x91ADFC, "4885c00f8c23010000"), ("readout", 0x6D028C, "33d2e80d1ad8ff"),
         ("decoy", 0x91AFAA, "8bc5e8bb34ffff"))
DESIGN_YEAR, KIND, LAND = 0xB28, 0x9D3, 12
SKIMMERS = (32, 33)   # missile codes (SAMIntercept's 4th argument): medium and light SSMs; 31 heavy, 30 other
NATIVE = dict(operational=0x90E46C, random=0x307834, set_text=0x451CA0, no_shot=0x91AF28, shot=0x91AE05,
              fire_sam=0x917F54)
# The anti-aircraft FireSAM(ship, kind, 0) calls; the other two callers fire heavy SAMs only (kind 1).
CALLS = (("aa_fire", 0x95FDC4, "e88b81fbff"), ("aa_fire2", 0x95FE18, "e83781fbff"))
MOUNT = dict(tubes=4, kind=0xE, reloads=0xF, destroyed=0xF0, loaded=0xF1)      # a ship's missile mounts: list at +9Eh
MOUNTS, LIGHT_SAM, QUAD = 0x9E, 3, 4


def digests(blob):
    import modern_research as audit
    normal = audit.normalize(blob, BASE)
    return [hashlib.sha256(normal[a-BASE:a-BASE+n]).hexdigest() for a, n, _ in WINDOWS]


def discover(blob, base, normalized):
    for (address, size, _), digest in zip(WINDOWS, DIGESTS):
        if hashlib.sha256(normalized[address-BASE:address-BASE+size]).hexdigest() != digest:
            raise ValueError("Missile defence refuses changed native code at "+hex(address)+".")
    for name, address, original in SITES+CALLS:
        if blob[address-BASE:address-BASE+len(original)//2].hex() != original:
            raise ValueError("Missile defence refuses changed native code.")
    import modern_combat as combat
    delta = base-BASE
    info = {k: v+delta for k, v in {**NATIVE, **{k: combat.NATIVE[k] for k in ("has_research", "nation")}}.items()}
    info["main"] = struct.unpack_from("<I", blob, combat.MAIN_LOAD-BASE+1)[0]
    info["sites"] = {name: address+delta for name, address, _ in SITES}
    info["calls"] = {name: address+delta for name, address, _ in CALLS}
    import modern_extension
    info["fighting_vmt"] = modern_extension.NATIVE["fighting_vmt"]+delta
    return info


def build(page, info, doctrine, flight, drones=None, nuclear_sam=None, side_nation=None, arm_lock=None, ram_sam=None,
          ram_kind=None):
    """Code and data at page (0x400 bytes) and the missile flight routine at flight (its own page).
    doctrine: shell_doctrine's entry points (conserve). modern_air_defence: drones, drone_ship(EAX ship) -> AL;
    nuclear_sam(EAX ship, EDX kind) -> AL. side_nation: modern_recon's side_nation(EDX side) -> EDX nation (a
    missile holds its launcher's battle side, not its nation); arm_lock(EAX ship, EDX nation) -> AL.
    point_defence: ram_kind, where the SAM kind fired is noted, and ram_sam(ESI ship) -> AL, RAM light SAMs."""
    from campaign_security import Code
    from hull_rules import patch
    import modern_combat as combat
    import modern_tree as tree
    at = dict(shots=page, handled=page+0xA0, fired=page+0x100, readout=page+0x200, puts=page+0x300, putn=page+0x320,
              sums=page+0x350, sam=page+0x35C, ssm=page+0x366, line=page+0x374)
    n, code = info, {}
    # SAMIntercept before FireSAM (ESI ship, EBX kind): free busy launchers by radar class; CL = one SAM only.
    c = Code(at["shots"])
    if ram_kind: c.emit(b"\x89\x1d"); c.u32(ram_kind)                                    # the kind, for ram_sam
    c.emit(b"\x60\x83\xbe"); c.u32(SHIP["radar_down"]); c.emit(b"\x00"); c.branch(b"\x0f\x85", "asked")
    c.emit(b"\x8b\x86"); c.u32(SHIP["radar"]); c.emit(b"\x83\xf8\x06"); c.branch(b"\x0f\x8c", "asked")
    c.emit(b"\xbf"); c.u32(FREE[6]); c.emit(b"\x83\xf8\x07"); c.branch(b"\x0f\x8c", "roll"); c.emit(b"\xbf"); c.u32(FREE[7])
    c.mark("roll"); c.emit(b"\xb8\x64\x00\x00\x00"); c.branch(b"\xe8", n["random"]); c.emit(b"\x3b\xc7"); c.branch(b"\x0f\x8d", "asked")
    c.emit(b"\x66\xc7\x86"); c.u32(SHIP["busy"]); c.emit(b"\x00\x00")
    c.mark("asked"); c.emit(b"\x8b\x56"+bytes([SHIP["nation"]])); c.branch(b"\xe8", doctrine["conserve"])
    c.emit(b"\x89\x44\x24\x18\x61\x8b\xd3\x8b\xc6"); c.branch(b"\xe9", n["sites"]["shots"]+6)
    code["shots"] = c.finish()
    # The saturation count (ESI ship) -> ECX. RAM light SAMs (fire and forget) count half.
    c = Code(at["handled"]); c.emit(b"\x8b\x8e"); c.u32(SHIP["handled"]); c.branch(b"\xe8", flight)
    if ram_sam:
        c.emit(b"\x50"); c.branch(b"\xe8", ram_sam); c.emit(b"\x84\xc0\x58"); c.branch(b"\x0f\x84", "radar")
        c.emit(b"\xd1\xe9")
        c.mark("radar")
    c.emit(b"\x83\xbe"); c.u32(SHIP["radar_down"]); c.emit(b"\x00"); c.branch(b"\x0f\x85", "back")
    for level in (6, 7):
        c.emit(b"\x83\xbe"); c.u32(SHIP["radar"]); c.emit(bytes([level])); c.branch(b"\x0f\x8c", "back"); c.emit(b"\xd1\xe9")
    c.mark("back"); c.branch(b"\xe9", n["sites"]["handled"]+6)
    code["handled"] = c.finish()
    # After FireSAM (EAX missiles fired, EBX kind, ESI ship): quad-packed light SAMs go back three times in four.
    c = Code(at["fired"]); c.branch(b"\xe8", "refund"); c.emit(b"\x48\x85\xc0"); c.branch(b"\x0f\x8c", n["no_shot"])
    if nuclear_sam:   # a nuclear heavy SAM (Nuclear Armageddon) shoots the missile down: [ebp-5] the answer
        c.emit(b"\x50\x8b\xc6\x8b\xd3"); c.branch(b"\xe8", nuclear_sam); c.emit(b"\x84\xc0\x58"); c.branch(b"\x0f\x84", "native")
        c.emit(b"\xc6\x45\xfb\x01"); c.branch(b"\xe9", n["no_shot"])
        c.mark("native")
    c.branch(b"\xe9", n["shot"])
    # The anti-aircraft FireSAM(EAX ship, EDX kind, CL) calls come here, so their light SAMs come back too.
    c.mark("wrapper"); c.emit(b"\x53\x56\x8b\xf0\x8b\xda"); c.branch(b"\xe8", n["fire_sam"]); c.branch(b"\xe8", "refund")
    c.emit(b"\x5e\x5b\xc3")
    c.mark("refund"); c.emit(b"\x60\x83\xfb"+bytes([LIGHT_SAM])); c.branch(b"\x0f\x85", "out")
    c.emit(b"\x85\xc0"); c.branch(b"\x0f\x8e", "out"); c.emit(b"\x8b\xf8")
    combat.researched(c, n, b"\x8b\x56"+bytes([SHIP["nation"]]), tree.QUAD_PACK, "asked"); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "out")
    c.emit(b"\xb8"); c.u32(QUAD); c.branch(b"\xe8", n["random"]); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "out")
    c.emit(b"\x8b\x8e"); c.u32(MOUNTS); c.emit(b"\x85\xc9"); c.branch(b"\x0f\x84", "out"); c.emit(b"\x8b\x51\x08\x8b\x49\x04")
    c.mark("mount"); c.emit(b"\x4a"); c.branch(b"\x0f\x88", "out"); c.emit(b"\x8b\x04\x91\x80\x78"+bytes([MOUNT["kind"], LIGHT_SAM]))
    c.branch(b"\x0f\x85", "mount"); c.emit(b"\x83\x78"+bytes([MOUNT["tubes"]])+b"\x08"); c.branch(b"\x0f\x8c", "mount")
    c.emit(b"\x8b\x98"); c.u32(MOUNT["loaded"]); c.emit(b"\x3b\x58"+bytes([MOUNT["tubes"]])); c.branch(b"\x0f\x8d", "mount")
    c.emit(b"\x01\xb8"); c.u32(MOUNT["loaded"])
    c.mark("out"); c.emit(b"\x61\xc3")
    code["fired"] = c.finish()
    wrapper = at["fired"]+c.labels["wrapper"]

    # puts: ESI zero-ended text -> EDI; putn: EAX as decimal -> EDI.
    c = Code(at["puts"]); c.mark("next"); c.emit(b"\x66\xad\x66\x85\xc0"); c.branch(b"\x0f\x84", "end"); c.emit(b"\x66\xab"); c.branch(b"\xe9", "next")
    c.mark("end"); c.emit(b"\xc3"); code["puts"] = c.finish()
    c = Code(at["putn"]); c.emit(b"\x53\x52\xbb\x0a\x00\x00\x00\x33\xc9")
    c.mark("digit"); c.emit(b"\x33\xd2\xf7\xf3\x52\x41\x85\xc0"); c.branch(b"\x0f\x85", "digit")
    c.mark("write"); c.emit(b"\x58\x83\xc0\x30\x66\xab\x49"); c.branch(b"\x0f\x85", "write"); c.emit(b"\x5a\x5b\xc3")
    code["putn"] = c.finish()

    # The battle ship panel's empty status line (EAX the label, [ebp-0Ch] the ship): missiles left.
    sums, line = at["sums"], at["line"]
    c = Code(at["readout"]); c.emit(b"\x60\x8b\x75\xf4\x33\xc0\xa3"); c.u32(sums); c.emit(b"\xa3"); c.u32(sums+4); c.emit(b"\xa3"); c.u32(sums+8)
    c.emit(b"\x8b\x8e"); c.u32(MOUNTS); c.emit(b"\x85\xc9"); c.branch(b"\x0f\x84", "none"); c.emit(b"\x8b\x51\x08\x8b\x49\x04")
    c.mark("mount"); c.emit(b"\x4a"); c.branch(b"\x0f\x88", "counted"); c.emit(b"\x8b\x04\x91\x0f\xb6\x58"+bytes([MOUNT["kind"]]))
    c.emit(b"\x4b\x83\xfb\x05"); c.branch(b"\x0f\x87", "mount"); c.emit(b"\xff\x05"); c.u32(sums+8)             # a launcher
    c.emit(b"\x80\xb8"); c.u32(MOUNT["destroyed"]); c.emit(b"\x00"); c.branch(b"\x0f\x85", "mount")
    c.emit(b"\xbf"); c.u32(sums); c.emit(b"\x83\xfb\x03"); c.branch(b"\x0f\x82", "add"); c.emit(b"\x83\xc7\x04")
    c.mark("add"); c.emit(b"\x8b\x98"); c.u32(MOUNT["loaded"]); c.emit(b"\x03\x58"+bytes([MOUNT["reloads"]])+b"\x01\x1f"); c.branch(b"\xe9", "mount")
    c.mark("counted"); c.emit(b"\x83\x3d"); c.u32(sums+8); c.emit(b"\x00"); c.branch(b"\x0f\x84", "none")
    c.emit(b"\xbf"); c.u32(line+12); c.emit(b"\xbe"); c.u32(at["sam"]); c.branch(b"\xe8", at["puts"]); c.emit(b"\xa1"); c.u32(sums); c.branch(b"\xe8", at["putn"])
    c.emit(b"\xbe"); c.u32(at["ssm"]); c.branch(b"\xe8", at["puts"]); c.emit(b"\xa1"); c.u32(sums+4); c.branch(b"\xe8", at["putn"])
    c.emit(b"\x66\xc7\x07\x00\x00\x81\xef"); c.u32(line+12); c.emit(b"\xd1\xef\x89\x3d"); c.u32(line+8)
    c.emit(b"\x61\xba"); c.u32(line+12); c.branch(b"\xe9", "show")
    c.mark("none"); c.emit(b"\x61\x33\xd2")
    c.mark("show"); c.branch(b"\xe8", n["set_text"]); c.branch(b"\xe9", n["sites"]["readout"]+7)
    code["readout"] = c.finish()

    # Missile flight, in SAMIntercept's frame ([ebp-4] the missile's side, [ebp+8] its code): ECX the count, one
    # more a research of the side's nation (EBX), for medium and light SSMs.
    c = Code(flight); c.emit(b"\x51\x60\x8b\x45\x08\x83\xe8"+bytes([SKIMMERS[0]])+b"\x83\xf8"+bytes([len(SKIMMERS)-1]))
    c.branch(b"\x0f\x87", "done")
    c.emit(b"\x8b\x55\xfc")
    if side_nation: c.branch(b"\xe8", side_nation)
    c.emit(b"\x8b\xda")
    for ident in tree.MISSILE_FLIGHT:
        combat.researched(c, n, b"\x8b\xd3", ident, f"asked{ident}"); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", f"no{ident}")
        c.emit(b"\xff\x44\x24\x20"); c.mark(f"no{ident}")
    c.mark("done"); c.emit(b"\x61\x59\xc3")
    flight_block = dict(name="Missile defence: flight", address=flight, bytes=c.finish().hex())

    # The decoy roll (EBP ship, EDI the missile's side, ESI percent): electronic warfare suites; the attacker's
    # imaging seekers take some back, and its anti-radiation seekers (tree.ARM) leave no decoy against a radar on.
    at["decoy"] = flight+0x80
    c = Code(at["decoy"]); c.emit(b"\x60")                                         # pushad: [esp] EDI, [esp+4] ESI
    for ident, year, percent in tree.EW_SUITES:
        c.emit(b"\x81\xbd"); c.u32(DESIGN_YEAR); c.u32(year); c.branch(b"\x0f\x8c", f"no{ident}")
        combat.researched(c, n, b"\x8b\x55"+bytes([SHIP["nation"]]), ident, f"asked{ident}"); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", f"no{ident}")
        c.emit(b"\x83\x44\x24\x04"+bytes([percent])); c.mark(f"no{ident}")
    if drones:   # interceptor drones (modern_air_defence)
        c.emit(b"\x8b\xc5"); c.branch(b"\xe8", drones); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "no_drones")
        c.emit(b"\x83\x44\x24\x04"+bytes([tree.DRONE_SWARMS[1]]))
        c.mark("no_drones")
    c.emit(b"\x8b\x14\x24")                                                     # the missile's nation: EBX
    if side_nation: c.branch(b"\xe8", side_nation)
    c.emit(b"\x8b\xda")
    combat.researched(c, n, b"\x8b\xd3", tree.EW_SEEKER[0], "seeker"); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "arm")
    c.emit(b"\x83\x6c\x24\x04"+bytes([tree.EW_SEEKER[1]]))
    c.mark("arm")
    if arm_lock:
        c.emit(b"\x8b\xc5\x8b\xd3"); c.branch(b"\xe8", arm_lock); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "out")
        c.emit(b"\xc7\x44\x24\x04\x00\x00\x00\x00")                              # no decoy (ESI after POPAD)
    c.mark("out"); c.emit(b"\x61\x8b\xc5"); c.branch(b"\xe8", n["operational"]); c.branch(b"\xe9", n["sites"]["decoy"]+7)
    code["decoy"] = c.finish()

    # asbm(ECX launcher, EAX its launch flags) -> EAX: a researched land battery launches hypersonic missiles.
    import modern_railgun
    at["asbm"] = flight+ASBM
    c = Code(at["asbm"]); c.emit(b"\x51\x52\x50\x81\x39"); c.u32(n["fighting_vmt"]); c.branch(b"\x0f\x85", "out")
    c.emit(b"\x80\xb9"); c.u32(KIND); c.emit(bytes([LAND])); c.branch(b"\x0f\x85", "out")
    combat.researched(c, n, b"\x8b\x51"+bytes([SHIP["nation"]]), tree.ASBM, "asked"); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "out")
    c.emit(b"\x81\x0c\x24"); c.u32(modern_railgun.HYPER_BIT)
    c.mark("out"); c.emit(b"\x58\x5a\x59\xc3")
    code["asbm"] = c.finish()

    room = dict(asbm=0x80, decoy=0x100, shots=0xA0, handled=0x60, fired=0x100, readout=0x100, puts=0x20, putn=0x30)
    wide = lambda text: (text.encode("utf-16-le")+b"\0\0").hex()
    blocks = [flight_block, dict(name="Missile defence: sums", address=sums, bytes="00"*12),
              dict(name="Missile defence: SAM text", address=at["sam"], bytes=wide("SAM ")),
              dict(name="Missile defence: SSM text", address=at["ssm"], bytes=wide(", SSM ")),
              dict(name="Missile defence: line", address=line, bytes=(struct.pack("<HHiI", 1200, 2, -1, 0)+bytes(0x80)).hex())]
    for name, body in code.items():
        if len(body) > room[name]: raise ValueError("Missile defence code exceeds its reservation: "+name)
        blocks.append(dict(name="Missile defence: "+name, address=at[name], bytes=body.hex()))
    plans = [patch("Missile defence: "+name, n["sites"][name], bytes.fromhex(original),
                   b"\xe9"+struct.pack("<i", at[name]-n["sites"][name]-5)+b"\x90"*(len(original)//2-5))
             for name, _, original in SITES]
    plans += [patch("Missile defence: "+name, n["calls"][name], bytes.fromhex(original),
                    b"\xe8"+struct.pack("<i", wrapper-n["calls"][name]-5)) for name, _, original in CALLS]
    return blocks, plans
