"""Modern fleet details: ASW torpedoes, composite superstructures, USVs, nuclear shells and frigates.

Hooks for the modern-research adapter, each gated by its own research (modern_tree) or year:
- ASW: destroyers, escorts and cruisers with a torpedo mount gain ASW_BONUS with lightweight ASW torpedoes
  (the native rule needs two mounts and stays), and ships with a VLS bank gain it again with vertical-launch
  ASW rockets (ASROC in the cells).
- Composite superstructures: a light (aluminium) superstructure on a ship designed from COMPOSITE's year by a
  researching nation is composite instead: lighter and costlier in the designer, and free of aluminium's battle
  fire penalties (all five native aluminium checks).
- USVs: a researching nation's MTB squadrons use Data/IDes/USV.sdf and are named USV.
- Lasers and aircraft: each laser mount adds LASER_AA to the ship's AA value against air attacks.
- Nuclear shells and aircraft: a ship that may fire nuclear shells (calibre, research, the player's doctrine) has
  NUCLEAR_HAA more heavy AA value against air attacks.
- Nuclear shells: each main battery of NUCLEAR_SHELLS calibre or more fires one nuclear shell per battle, its
  first hit, which reaches HandleHit as a NUCLEAR_SHELLS-inch hit (the native >20-inch damage path).
- Frigates: from FRIGATE_YEAR (a data slot) the KE type reads FF (the US Navy's 1975 reclassification); the type reader
  accepts FF, so design files written either way load.
- BBV hybrids: a BB or BC (and an AV: modern_carrier lets its jet deck take VTOL fighters) with a flight deck and
  aircraft counts as a carrier wherever the game asks IsCarrier
  (air groups, strikes, CAP, deck cycles, flight deck damage and fires, campaign air group management), except
  for the battle's tactical callers in BBV_TACTICAL (start positions, formation spacing and contact, stance,
  course, objectives, convoy behaviour, gun target choice), which keep seeing a battleship.
Part of the modern-research adapter; imported lazily.
"""
import hashlib
import struct
import modern_tree as tree
import modern_combat as combat
import modern_extension as extension
from hull_rules import patch

BASE = 0x301000
WINDOWS = (
    (0x813ED5, 0x28, "baa40aa57553cfe9f0b98167d6baad38819a06545b3be22897de42a045f20e6f"),   # ASW value epilogue
    (0x939660, 0x40, "00116f1f91561181e3de3c72315a2c4929177acfd57cb0cf843e97a25eb47df3"),   # aluminium weight
    (0x93A3A0, 0x30, "b3de81d53ab7b40bf8d1625032dae06e675905f038cdcae5d1267bcc07e38cb7"),   # aluminium cost
    (0x913087, 0x10, "d4f48d77c801e52c07cacfc6b6b6b5b473645734d891015e53209a0da5132952"),   # aluminium in battle
    (0x9132C7, 0x10, "0b3730af9849a3fb9c48aa42f3deccce4839e3a0960db1ddd0b015e7a7cbc767"),
    (0x9134FB, 0x10, "80076a1311b1ef8754bdd11792da7dd5369bfa204498db656a5642806f283b1c"),
    (0x91363D, 0x10, "67a1e93590a3d597305428fe69593f37fed65e72b3adc69d9a5bb1ae02d4d86b"),
    (0x9137EE, 0x10, "802842ca67e1d6d08479303d73ca7fec2028180539f21715fabaf20ba124ea07"),
    (0x6C1A63, 0x70, "a68b3123739e0a26cf12f8ef490230db9d3b8528f6164d28ecd4189cd23992b7"),   # newest MTB squadrons
    (0x90991A, 0x2C, "f15406948b86fb5abf1efb3e6a33f456830cec964d211ed23e01c12a5f4935b5"),   # FireGuns: HandleHit args
    (0x9514E0, 0x130, "ba1d8969160973d4be8898c39e05f90ea3057f0100e89895ba770583f685157c"),  # ship type abbreviation
    (0x951B0E, 0x30, "7e1aa93c817bad6a9feabc0462608feb4a7838bf1498013895acb1accab9eed1"),   # ship type reader: unknown
    (0x950090, 0x10, "37acde6a552d53652a871876e0b8d1050b244bafeee6c2c6901d8f7d0490bfe0"),   # IsCarrier: CV, CVL
    (0x916F90, 0x60, "9b630e265d4bbb5e0bafce313bea31d56a7153cd7886493106011b5e86ed1a79"),   # ship AA values (heavy)
    (0x960D8F, 0x10, "90f57e32d8e694d35f3d4f3099521936c2bc85248039aa30b4496ff158db98d3"),   # air attack: heavy AA of each ship near the target
    (0x960E14, 0x10, "b053d6efd2bc3180de971e2bfd4ef2c3c209baef89011044683594d14cf8e4b1"),
    (0x960F78, 0x10, "d197c0477eef9f8fc47910543cb7a7ab966e3026d192631bed6d13937e77d223"),
)
# IsCarrier call sites in battle tactics, where a BBV still behaves as a battleship: division moves and objectives
# (7), convoy scatter, formation contact (3), stance, going home, course, convoy lure, gun target of the same
# size, temporary objectives (3), keep-away distance, formation spacing (6), battle-start distance (2), start
# stance, start carrier count.
BBV_TACTICAL = (0x866BEE, 0x868D63, 0x868FA0, 0x86C36B, 0x86CE8C, 0x86D0C3, 0x86DBDF, 0x87CC3C, 0x88195C, 0x88197F,
                0x881C72, 0x890278, 0x89174A, 0x892B5C, 0x8C85D0, 0x863F23, 0x924F7B, 0x924FCC, 0x92506B, 0x927670,
                0x92B3A7, 0x92B425, 0x92B4BE, 0x92B5E4, 0x92B88B, 0x92B909, 0x6B011F, 0x6B01C2, 0x6BB7D6, 0x6C536C)
BBV_TYPES = (0, 1)   # BB, BC
AV = 8               # an AV with a flight deck is a hybrid too (VTOL fighters, modern_carrier)
NATIVE = dict(asw_back=0x813EDC, weight_factor=0x93973C, cost_factor=0x93A67C, nuclear_back=0x90991F,
              type_back=0x95160A, reader_back=0x951B1E, reader_found=0x951B36, equal=0x30C7CC)
SITES = (("asw", 0x813ED5, 7), ("weight", 0x93967D, 6), ("cost", 0x93A3BB, 6), ("fire1", 0x913087, 7),
         ("fire2", 0x9132C7, 7), ("fire3", 0x9134FB, 7), ("fire4", 0x91363D, 7), ("fire5", 0x9137EE, 7),
         ("usv_name", 0x6C1AA2, 5), ("usv_design", 0x6C1AC1, 5), ("nuclear", 0x90991A, 5), ("type_name", 0x951605, 5),
         ("type_reader", 0x951B18, 6), ("is_carrier", 0x950090, 7),
         ("haa1", 0x960D91, 5), ("haa2", 0x960E16, 5), ("haa3", 0x960F7A, 5))
CALLS = {"weight": "weight", "cost": "cost", **{f"fire{i}": "fire" for i in range(1, 6)},   # call sites, not jumps
         **{f"haa{i}": "haa" for i in range(1, 4)}}
YEAR_LOAD = 0x91AC81                  # mov eax, [current year pointer] in the missile range routine
ASW_TYPES, ASW_BONUS, VLS_CELLS = (3, 4, 9, 10, 15), 2, (8, 16, 32, 64)   # CA, CL, DD, KE, FF (frigate_type.py)
COMPOSITE_WEIGHT, COMPOSITE_COST = 0.85, 1.30   # aluminium: 0.92 and 1.15 (native)
FRIGATE_YEAR, KE = 1975, 10
USV_DESIGN = "\\Data\\Ides\\USV.sdf"
LASER_AA = 4                          # AA value a laser mount adds against air attacks (drones and aircraft)
NUCLEAR_HAA = 60                      # heavy AA value added to a ship that may fire nuclear shells (a DP gun adds 1-5)
AA_VALUES = 0x916F90                  # ship AA values: EAX ship, EDX quality, CL heavy, stack: flag, result record
NUCLEAR_USED_BIT = 0x1000             # fighting ship's battle flags (modern_extension.BATTLE_FLAGS): shell spent


def discover(blob, base, normalized):
    for address, size, digest in WINDOWS:
        if hashlib.sha256(normalized[address-BASE:address-BASE+size]).hexdigest() != digest:
            raise ValueError("Modern fleet refuses changed native code at "+hex(address)+".")
    if normalized[YEAR_LOAD-BASE] != 0xA1:
        raise ValueError("Unsupported native campaign year.")
    delta = base-BASE
    info = {k: v+delta for k, v in {**NATIVE, **{k: combat.NATIVE[k] for k in ("has_research", "nation")}}.items()}
    info["main"] = struct.unpack_from("<I", blob, combat.MAIN_LOAD-BASE+1)[0]
    info["year"] = struct.unpack_from("<I", blob, YEAR_LOAD-BASE+1)[0]
    info["aa_values"] = AA_VALUES+delta
    import modern_railgun as rail   # the battle's weather, which its laser missile layer reads too
    info["precipitation"], info["sea"] = rail.NATIVE["precipitation"]+delta, rail.NATIVE["sea"]+delta
    if any(blob[at-BASE] != 0xE8 or at+5+struct.unpack_from("<i", blob, at-BASE+1)[0] != 0x950090 for at in BBV_TACTICAL):
        raise ValueError("Modern fleet: unexpected carrier check in battle tactics.")
    info["bbv_tactical"] = [at+5+delta for at in BBV_TACTICAL]   # return addresses
    info["sites"] = [dict(name=name, address=address+delta, original=blob[address-BASE:address-BASE+size].hex())
                     for name, address, size in SITES]
    return info


def literal(text): return struct.pack("<HHiI", 1200, 2, -1, len(text))+text.encode("utf-16-le")+b"\0\0"


def build(page, info, ext, doctrine=None, drones=None):
    """drones: modern_air_defence's drone_ship(EAX ship) -> AL."""
    from campaign_security import Code   # imported late: campaign_security imports modern_research
    at = dict(asw=page, composite=page+0x100, weight=page+0x180, cost=page+0x1C0, fire=page+0x200,
              usv_name=page+0x240, usv_design=page+0x2C0, quiet=page+0x340, nuclear=page+0x600, type_name=page+0x3C0,
              type_reader=page+0x400, is_carrier=page+0x440, bbv_table=page+0x4C0, texts=page+0x800, factors=page+0x7F0,
              haa=page+0x700, haa_slots=page+0x560, frigate_year=page+0x7E0, frigate_type=page+0x7E4)
    n, code = info, {}
    site = {s["name"]: s for s in info["sites"]}
    texts, cursor = {}, at["texts"]
    for key, text in (("usv", "USV "), ("usv_design", USV_DESIGN), ("frigate", "FF")):
        texts[key] = cursor+12; body = literal(text); code["text_"+key] = body; at["text_"+key] = cursor
        cursor += (len(body)+15) & ~15

    # GetASWValue epilogue, EBX ship, EDI nation, ESI value: torpedo mounts and VLS banks, by research.
    c = Code(at["asw"]); c.emit(b"\x60\x33\xed\x0f\xb6\x83"); c.u32(0x9D3)
    c.emit(b"\xb9"); c.u32(sum(1 << kind for kind in ASW_TYPES)); c.emit(b"\x0f\xa3\xc1")   # bt ecx, eax: an ASW type
    c.branch(b"\x0f\x83", "done"); c.branch(b"\xe8", at["quiet"])
    c.emit(b"\x8b\x83"); c.u32(0x9E); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "done")
    c.emit(b"\x8b\x48\x08\x8b\x70\x04\x33\xd2")                                  # ecx count, esi mounts, edx found
    c.mark("next"); c.emit(b"\x49"); c.branch(b"\x0f\x88", "scanned")
    c.emit(b"\x8b\x1c\x8e\x0f\xb6\x43\x0e\x85\xc0"); c.branch(b"\x0f\x85", "missile")
    c.emit(b"\x83\xca\x01"); c.branch(b"\xe9", "next")                          # a torpedo mount
    c.mark("missile"); c.emit(b"\x48\x83\xf8\x05"); c.branch(b"\x0f\x87", "next")
    c.emit(b"\x8b\x43\x04")
    for cells in VLS_CELLS:
        c.emit(b"\x83\xf8"+bytes([cells])); c.branch(b"\x0f\x84", "vls")
    c.branch(b"\xe9", "next")
    c.mark("vls"); c.emit(b"\x83\xca\x02"); c.branch(b"\xe9", "next")
    c.mark("scanned")
    for bit, ident in ((1, tree.ASW_TORPEDOES), (2, tree.VL_ASW)):
        c.emit(b"\xf6\xc2"+bytes([bit])); c.branch(b"\x0f\x84", f"no{bit}")
        c.emit(b"\x52\x8b\xc7\xba"); c.u32(ident); c.branch(b"\xe8", n["has_research"]); c.emit(b"\x5a\x84\xc0")
        c.branch(b"\x0f\x84", f"no{bit}"); c.emit(b"\x83\xc5"+bytes([ASW_BONUS]))
        c.mark(f"no{bit}")
    c.mark("done"); c.emit(b"\x01\x6c\x24\x04\x61"+bytes.fromhex(site["asw"]["original"])); c.branch(b"\xe9", n["asw_back"])
    code["asw"] = c.finish()
    # quiet(EBX ship, EDI nation), inside the ASW epilogue: EBP += the hybrid bonus for a quiet electric drive,
    # diesel (3) or gas turbine (4) on a design from the hybrid year.
    hybrid, hybrid_year, hybrid_asw = tree.HYBRID
    c = Code(at["quiet"]); c.emit(b"\x0f\xb6\x83"); c.u32(0x9D4); c.emit(b"\x83\xe8\x03\x83\xf8\x01"); c.branch(b"\x0f\x87", "loud")
    c.emit(b"\x81\xbb"); c.u32(0xB28); c.u32(hybrid_year); c.branch(b"\x0f\x8c", "loud")
    c.emit(b"\x8b\xc7\xba"); c.u32(hybrid); c.branch(b"\xe8", n["has_research"]); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "loud")
    c.emit(b"\x83\xc5"+bytes([hybrid_asw]))
    c.mark("loud"); c.emit(b"\xc3")
    code["quiet"] = c.finish()

    # is_composite(EAX ship) -> AL, keeps EBX/ESI/EDI/EBP: aluminium, designed from the year, nation research.
    ident, year = tree.COMPOSITE
    c = Code(at["composite"]); c.emit(b"\x80\xb8"); c.u32(0x9AA); c.emit(b"\x00"); c.branch(b"\x0f\x84", "no")
    c.emit(b"\x81\xb8"); c.u32(0xB28); c.u32(year); c.branch(b"\x0f\x8c", "no")
    c.emit(b"\x51\x8b\xc8"); combat.researched(c, n, b"\x8b\x51\x14", ident, "asked"); c.emit(b"\x59\xc3")
    c.mark("no"); c.emit(b"\x33\xc0\xc3")
    code["composite"] = c.finish()
    # Designer weight and cost factors (EBX design), called in place of the native FLD of the aluminium factor.
    for name, native, factor in (("weight", n["weight_factor"], 0), ("cost", n["cost_factor"], 4)):
        c = Code(at[name]); c.emit(b"\x60\x8b\xc3"); c.branch(b"\xe8", at["composite"]); c.emit(b"\x84\xc0\x61")
        c.branch(b"\x0f\x85", "light"); c.emit(b"\xdb\x2d"); c.u32(native); c.emit(b"\xc3")
        c.mark("light"); c.emit(b"\xd9\x05"); c.u32(at["factors"]+factor); c.emit(b"\xc3")
        code[name] = c.finish()
    # Battle aluminium checks (EAX ship), called in place of CMP [EAX+9AAh],0: ZF set when there is no aluminium
    # penalty, so composite ships pass as steel.
    c = Code(at["fire"]); c.emit(b"\x80\xb8"); c.u32(0x9AA); c.emit(b"\x00"); c.branch(b"\x0f\x84", "out")
    c.emit(b"\x60"); c.branch(b"\xe8", at["composite"]); c.emit(b"\x84\xc0\x61"); c.branch(b"\x0f\x84", "aluminium")
    c.emit(b"\x39\xc0\xc3")                                                      # composite: ZF set
    c.mark("aluminium"); c.emit(b"\x85\xe4")                                     # ZF clear
    c.mark("out"); c.emit(b"\xc3")
    code["fire"] = c.finish()

    # Newest MTB squadrons, ESI nation index: a USV nation names them USV and loads the USV design.
    for name, register, text in (("usv_name", b"\xba", "usv"), ("usv_design", b"\xb9", "usv_design")):
        c = Code(at[name]); c.emit(b"\x50\x51\x52"); combat.researched(c, n, b"\x8b\xd6", tree.USV, "asked")
        c.emit(b"\x84\xc0\x5a\x59\x58"); c.branch(b"\x0f\x85", "usv")
        c.emit(bytes.fromhex(site[name]["original"])); c.branch(b"\xe9", site[name]["address"]+5)
        c.mark("usv"); c.emit(register); c.u32(texts[text]); c.branch(b"\xe9", site[name]["address"]+5)
        code[name] = c.finish()

    # FireGuns, a hit about to reach HandleHit: EAX firer, EDX battery; push its calibre.
    ident, minimum, calibre = tree.NUCLEAR_SHELLS
    c = Code(at["nuclear"]); c.emit(b"\x60\x8b\xd8\x83\xfa\x01"); c.branch(b"\x0f\x85", "no")
    c.emit(b"\x83\x7b\x6d"+bytes([minimum])); c.branch(b"\x0f\x8c", "no")
    c.emit(b"\x8b\xc3"); c.branch(b"\xe8", ext); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "no"); c.emit(b"\x8b\xf0")
    if doctrine and "armageddon" in doctrine:   # Nuclear Armageddon: every hit, not one a battle
        c.emit(b"\x80\x3d"); c.u32(doctrine["armageddon"]); c.emit(b"\x00"); c.branch(b"\x0f\x85", "unlimited")
    c.emit(b"\xf7\x46"+bytes([extension.BATTLE_FLAGS])); c.u32(NUCLEAR_USED_BIT); c.branch(b"\x0f\x85", "no")
    c.mark("unlimited")
    combat.researched(c, n, b"\x8b\x53\x14", ident, "asked"); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "no")
    if doctrine:   # shell_doctrine.py: the nation may fire it and pays; the hit also strikes ships near the target
        c.emit(b"\x8b\x53\x14"); c.branch(b"\xe8", doctrine["use_nuclear"]); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "no")
        c.branch(b"\xe8", doctrine["blast"]); c.emit(b"\xc7\x05"); c.u32(doctrine["used"]); c.u32(1)   # tension, treaty
    c.emit(b"\x81\x4e"+bytes([extension.BATTLE_FLAGS])); c.u32(NUCLEAR_USED_BIT); c.emit(b"\xc7\x44\x24\x1c"); c.u32(calibre)
    c.emit(b"\x61\x50"); c.branch(b"\xe9", n["nuclear_back"])
    c.mark("no"); c.emit(b"\x61"+bytes.fromhex(site["nuclear"]["original"])); c.branch(b"\xe9", n["nuclear_back"])
    code["nuclear"] = c.finish()

    # Heavy AA against an air attack (three calls of the ship AA value routine): a ship that may fire nuclear
    # shells adds NUCLEAR_HAA to the record's heavy value. The routine is not re-entered, so three slots hold the
    # return address, the ship and the record.
    slots = at["haa_slots"]
    c = Code(at["haa"]); c.emit(b"\x8f\x05"); c.u32(slots); c.emit(b"\xa3"); c.u32(slots+4)
    c.emit(b"\x50\x8b\x44\x24\x04\xa3"); c.u32(slots+8); c.emit(b"\x58"); c.branch(b"\xe8", info["aa_values"])
    c.emit(b"\x60\x8b\x1d"); c.u32(slots+4); c.emit(b"\x83\x7b\x6d"+bytes([minimum])); c.branch(b"\x0f\x8c", "lasers")
    combat.researched(c, n, b"\x8b\x53\x14", ident, "haa_asked"); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "lasers")
    if doctrine:
        c.emit(b"\x8b\x53\x14"); c.branch(b"\xe8", doctrine["may_nuclear"]); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "lasers")
    c.emit(b"\xa1"); c.u32(slots+8); c.emit(b"\x83\x00"+bytes([NUCLEAR_HAA]))
    # Lasers: LASER_AA a mount, halved in rain or mist and again in heavy seas, as modern_railgun's missile layer.
    # shortcut: laser AA ignores superstructure damage (the missile layer loses the lasers with it); add that test
    # here if wrecked ships' lasers prove too strong.
    import modern_railgun as rail
    c.mark("lasers"); c.emit(b"\x8b\xc3"); c.branch(b"\xe8", ext); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "done")
    c.emit(b"\x0f\xb6\x00\x6b\xc0"+bytes([LASER_AA]))
    c.emit(b"\x8b\x0d"); c.u32(n["precipitation"]); c.emit(b"\x80\x39"+bytes([rail.CLEAR_WEATHER])+b"\x74\x02\xd1\xe8")
    c.emit(b"\x8b\x0d"); c.u32(n["sea"]); c.emit(b"\x83\x39"+bytes([rail.SEA_ROUGH])+b"\x7c\x02\xd1\xe8")
    c.emit(b"\x8b\x15"); c.u32(slots+8); c.emit(b"\x01\x02")
    c.mark("done")
    if drones:   # interceptor drones (modern_air_defence) add their AA value
        c.emit(b"\x8b\xc3"); c.branch(b"\xe8", drones); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "no_drones")
        c.emit(b"\x8b\x15"); c.u32(slots+8); c.emit(b"\x83\x02"+bytes([tree.DRONE_SWARMS[2]]))
        c.mark("no_drones")
    c.emit(b"\x61\xff\x25"); c.u32(slots)
    code["haa"] = c.finish()

    # Type abbreviation for KE: FF from the frigate year; the reader takes FF as KE.
    c = Code(at["type_name"]); c.emit(bytes.fromhex(site["type_name"]["original"])+b"\x50\xa1"); c.u32(n["year"])
    c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "kept")                           # no campaign year yet
    c.emit(b"\x51\x8b\x08\x3b\x0d"); c.u32(at["frigate_year"]); c.emit(b"\x59")    # the year slot: frigate_type.py
    c.branch(b"\x0f\x8c", "kept"); c.emit(b"\x58\xba"); c.u32(texts["frigate"])                # sets it out of reach
    c.branch(b"\xe9", "back")
    c.mark("kept"); c.emit(b"\x58")
    c.mark("back"); c.branch(b"\xe9", n["type_back"])
    code["type_name"] = c.finish()
    c = Code(at["type_reader"]); c.emit(b"\x8b\x45\xfc\xba"); c.u32(texts["frigate"]); c.branch(b"\xe8", n["equal"])
    c.branch(b"\x0f\x85", "unknown"); c.emit(b"\x8a\x1d"); c.u32(at["frigate_type"]); c.branch(b"\xe9", n["reader_found"])
    c.mark("unknown"); c.emit(bytes.fromhex(site["type_reader"]["original"])); c.branch(b"\xe9", n["reader_back"])
    code["type_reader"] = c.finish()

    # IsCarrier(EAX ship) -> EAX 0/1, every other register kept: CV and CVL, and BB/BC with a flight deck and
    # aircraft unless the caller (the return address) is one of the battle's tactical checks.
    table_end = at["bbv_table"]+4*len(info["bbv_tactical"])
    c = Code(at["is_carrier"]); c.emit(b"\x51\x0f\xb6\x88"); c.u32(0x9D3)
    c.emit(b"\x80\xf9\x05"); c.branch(b"\x0f\x84", "yes"); c.emit(b"\x80\xf9\x06"); c.branch(b"\x0f\x84", "yes")
    c.emit(b"\x80\xf9"+bytes([max(BBV_TYPES)])); c.branch(b"\x0f\x86", "hybrid")
    c.emit(b"\x80\xf9"+bytes([AV])); c.branch(b"\x0f\x85", "no")
    c.mark("hybrid")
    c.emit(b"\x80\xb8"); c.u32(0x9D9); c.emit(b"\x00"); c.branch(b"\x0f\x84", "no")             # FlightDeck
    c.emit(b"\x83\xb8"); c.u32(0x9E0); c.emit(b"\x00"); c.branch(b"\x0f\x8e", "no")             # AircraftCapacity
    c.emit(b"\x8b\x4c\x24\x04\x57\xbf"); c.u32(at["bbv_table"])
    c.mark("next"); c.emit(b"\x81\xff"); c.u32(table_end); c.branch(b"\x0f\x83", "carrier")
    c.emit(b"\x39\x0f"); c.branch(b"\x0f\x84", "tactical"); c.emit(b"\x83\xc7\x04"); c.branch(b"\xe9", "next")
    c.mark("tactical"); c.emit(b"\x5f"); c.branch(b"\xe9", "no")
    c.mark("carrier"); c.emit(b"\x5f")
    c.mark("yes"); c.emit(b"\xb8\x01\x00\x00\x00\x59\xc3")
    c.mark("no"); c.emit(b"\x33\xc0\x59\xc3")
    code["is_carrier"] = c.finish()
    del at["haa_slots"]
    blocks = [dict(name="Modern fleet: heavy AA call slots", address=slots, bytes="00"*12),
              dict(name="Modern fleet: BBV tactical callers", address=at["bbv_table"],
                   bytes=struct.pack(f"<{len(info['bbv_tactical'])}I", *info["bbv_tactical"]).hex()),
              dict(name="Modern fleet: frigate year", address=at["frigate_year"], bytes=struct.pack("<I", FRIGATE_YEAR).hex()),
              dict(name="Modern fleet: frigate type", address=at["frigate_type"], bytes=bytes([KE, 0, 0, 0]).hex()),
              dict(name="Modern fleet: composite factors", address=at["factors"],
                   bytes=struct.pack("<ff", COMPOSITE_WEIGHT, COMPOSITE_COST).hex())]
    room = dict(asw=0x100, composite=0x80, usv_name=0x80, usv_design=0x80, quiet=0x80, nuclear=0x100, is_carrier=0x80,
                haa=0xE0)
    for name, body in code.items():
        if not name.startswith("text_") and len(body) > room.get(name, 0x40):
            raise ValueError("Modern fleet code exceeds its reservation: "+name)
        blocks.append(dict(name="Modern fleet: "+name, address=at[name], bytes=body.hex()))
    plans = []
    for name, s in site.items():
        old = bytes.fromhex(s["original"])
        target = at[CALLS.get(name, name)]
        new = (b"\xe8" if name in CALLS else b"\xe9")+struct.pack("<i", target-s["address"]-5)+b"\x90"*(len(old)-5)
        plans.append(patch("Modern fleet: "+name, s["address"], old, new))
    return blocks, plans
