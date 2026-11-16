"""Reach beyond the horizon: longer missile ranges, satellite fixes and shipborne UAVs.

Battle hooks for the modern-research adapter, each gated by its own research (modern_tree):
- Missile range(EAX nation, EDX missile type), used by firing, AI, flight and the battle screen, is rebuilt
  around the native table routine and multiplied for each researched range technology (MISSILE_RANGES).
- Satellites: when a radar ship's spotting pass finds an enemy surface ship beyond its radar band, the
  observer's nation gets a fix with SATELLITES per-mille chance. The target counts as spotted and joins the
  observer's contacts, the native rule for spotted ships, so missiles can engage it.
- UAVs: a researching nation's floatplane ships launch and recover without stopping or slowing, as if they had
  a catapult; the launch prompt and the AI treat them as catapult launches and the prompt calls them UAVs.
- Start distance: the battle set-up moves each force back until it is a minimum distance from the scenario's
  reference point (30,000 yards close, 50,000 medium, 90,000 long, less before 1938). From START_DISTANCES' years
  that minimum grows, capped at START_CAP, so missile-era forces start beyond each other's radar and scouting
  decides who fires first. Land and enemy bases still stop the move as natively.
- Datalink: when the player's strike is about to be asked whether to adjust its final target location (strikes
  aim at a location, not a ship), a nation with the Tactical data system (DATALINK) aims it instead at the nearest
  spotted enemy surface ship within DATALINK_REACH yards of the old aim point and logs it; otherwise native.
Part of the modern-research adapter; imported lazily.
"""
import hashlib
import struct
import modern_tree as tree
import modern_combat as combat
from hull_rules import patch

BASE = 0x301000
WINDOWS = (
    (0x91AC14, 0xDA, "44515e11e58777acfbae09fd6d4cda555847de1c948e94e56ef038570e9a18c3"),   # missile range routines
    (0x89AB17, 0x3B, "9ed319f436f694d16c69242773ce4d1a1230a451be4316b3cb3dace9e91a34c0"),   # spotting: radar band
    (0x918FB8, 0x38, "9040a943945bc69bfcee69be4808ca9f180658a52783795cb3681543a913b3a2"),   # must stop for aircraft
    (0x91901D, 0x60, "33d1b72d1c33ff83b175df3a19fdfdc138c224a756262b6d59b142f421f60539"),   # scout launch prompt
    (0x92A2EF, 0x16, "7aa0d286284b143ba2e8556909b8faff3b76f85037b63ee932faffa1c655b33a"),   # AI scout launch
    (0x6B1606, 0x14, "1112af58b77460152d798054a6235eabce32b7fc7f42d2685ab2390e14c043c3"),   # battle start distance
    (0x97B92A, 0x14, "e922de44d69c058888561fd49dc55f8c43dd3aa5d4fb7c179de51a41f8ddc61e"),   # final strike target
    (0x97BABD, 0x10, "e13dda4794973caf55fbd736f3501f5b65fdd914094ee1433f122138539588af"),   # its "no" answer
)
NATIVE = dict(range_table=0x91AC14, random=0x307834, index_of=0x3B6E0C, add=0x3B6B8C, radar_far=0x89AF15,
              radar_near=0x89AB52, catapults=0x91BB74, start_back=0x6B160E, year=0x9F7328, ships=0x9F79D8,
              list_get=0x3B6D6C, afloat=0x90E46C, distance=0x90F18C, battle_log=0xA80114, prompt_back=0x97B939,
              strike_kept=0x97BABD)
SITES = (("missile_range", 0x91ACCC, 7), ("satellite", 0x89AB4C, 6), ("must_stop", 0x918FB8, 6),
         ("prompt_text", 0x919057, 5), ("prompt_count", 0x91904E, 5), ("ai_count", 0x92A2F1, 5),
         ("start_distance", 0x6B1606, 8), ("datalink", 0x97B934, 5))
CALLS = ("prompt_count", "ai_count")   # native calls of the catapult count, retargeted (not jumps)
TABLES = (0x91ACD6, 0x91ACDE)          # the range wrapper's per-nation level and flag tables (absolute)
UAV_TEXT = "Launch search UAV(s) from "
TYPES_LOAD = 0x974276   # FindAircraftType: MOV EAX,[the game's aircraft list]
START_DISTANCES = ((1975, 200), (1960, 150))   # from these campaign years, % of the native start distance
START_CAP = 120000      # yards from the reference point: well inside the 280,000-yard "forces far apart" test
DATALINK, DATALINK_REACH = 1524, 40000   # native Tactical data system (1963); yards from the old aim point
DATALINK_TEXT = "2Strike retargeted by datalink"


def discover(blob, base, normalized):
    for address, size, digest in WINDOWS:
        if hashlib.sha256(normalized[address-BASE:address-BASE+size]).hexdigest() != digest:
            raise ValueError("Modern reconnaissance refuses changed native code at "+hex(address)+".")
    delta = base-BASE
    info = {k: v+delta for k, v in {**NATIVE, **{k: combat.NATIVE[k] for k in ("has_research", "nation")}}.items()}
    info["main"] = struct.unpack_from("<I", blob, combat.MAIN_LOAD-BASE+1)[0]
    # The aircraft list, as FindAircraftType loads it: MOV EAX,[list]
    if blob[TYPES_LOAD-BASE] != 0xA1: raise ValueError("Modern reconnaissance refuses changed native code: the aircraft list.")
    info["aircraft_types"] = struct.unpack_from("<I", blob, TYPES_LOAD-BASE+1)[0]
    info["levels"], info["flags"] = (struct.unpack_from("<I", blob, at-BASE)[0] for at in TABLES)
    info["sites"] = [dict(name=name, address=address+delta, original=blob[address-BASE:address-BASE+size].hex())
                     for name, address, size in SITES]
    return info


def build(page, info):
    from campaign_security import Code   # imported late: campaign_security imports modern_research
    import modern_sensors as sensors
    at = dict(missile_range=page, satellite=page+0x200, must_stop=page+0x300, prompt_text=page+0x380,
              count=page+0x400, uav_text=page+0x480, has_uav=page+0x500, start_distance=page+0x600,
              datalink=page+0x680, datalink_text=page+0x880)
    n, code = info, {}
    site = {s["name"]: s for s in info["sites"]}

    # Range(EAX nation index, EDX missile type) -> EAX yards: the native wrapper, then research multipliers.
    c = Code(at["missile_range"])
    c.emit(b"\x53\x56\x57\x8b\xf0\x8b\xfa\x69\xc8\xa7\x00\x00\x00\x8b\x1c\x4d"); c.u32(n["levels"])
    c.emit(b"\x0f\xb6\x04\x4d"); c.u32(n["flags"])
    c.emit(b"\x8b\xca\x93\x8b\xd3"); c.branch(b"\xe8", n["range_table"]); c.emit(b"\x8b\xd8")
    for i, (ident, low, high, percent) in enumerate(tree.MISSILE_RANGES):
        c.emit(b"\x83\xff"+bytes([low])); c.branch(b"\x0f\x8c", f"next{i}")
        c.emit(b"\x83\xff"+bytes([high])); c.branch(b"\x0f\x8f", f"next{i}")
        combat.researched(c, n, b"\x8b\xd6", ident, f"asked{i}"); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", f"next{i}")
        c.emit(b"\x69\xdb"); c.u32(percent); c.emit(b"\x8b\xc3\x99\xb9\x64\x00\x00\x00\xf7\xf9\x8b\xd8")
        c.mark(f"next{i}")
    c.emit(b"\x8b\xc3\x5f\x5e\x5b\xc3")
    code["missile_range"] = c.finish()

    # Spotting pass, after the radar band test (flags of TEST AL,AL): [ebp-1Ch] observer, [ebp-4] target.
    ident, per_mille = tree.SATELLITES
    c = Code(at["satellite"]); c.branch(b"\x0f\x85", n["radar_near"])
    c.emit(b"\x60\x8b\x75\xe4\x8b\x5d\xfc\x83\xbb"); c.u32(0xD59); c.emit(b"\x00"); c.branch(b"\x0f\x8f", "done")   # spotted
    for kind in (12, 14):   # land targets and submarines
        c.emit(b"\x80\xbb"); c.u32(0x9D3); c.emit(bytes([kind])); c.branch(b"\x0f\x84", "done")
    c.emit(b"\x8b\x83"); c.u32(0xA55); c.emit(b"\x3b\x86"); c.u32(0xA55); c.branch(b"\x0f\x84", "done")        # same side
    c.emit(b"\xb8"); c.u32(1000); c.branch(b"\xe8", n["random"]); c.emit(b"\x3d"); c.u32(per_mille); c.branch(b"\x0f\x8d", "done")
    combat.researched(c, n, b"\x8b\x56\x14", ident, "asked"); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "done")
    c.emit(b"\xc7\x83"); c.u32(0xD59); c.u32(1)
    c.emit(b"\x8b\x86"); c.u32(0xAD9); c.emit(b"\x8b\xd3"); c.branch(b"\xe8", n["index_of"]); c.emit(b"\x40"); c.branch(b"\x0f\x85", "done")
    c.emit(b"\x8b\x86"); c.u32(0xAD9); c.emit(b"\x8b\xd3"); c.branch(b"\xe8", n["add"])
    c.mark("done"); c.emit(b"\x61"); c.branch(b"\xe9", n["radar_far"])
    code["satellite"] = c.finish()

    # has_uav(EDX nation index) -> AL: the nation has a UAV model in service (a floatplane scout with modern_sensors'
    # UAV mark): developed, not obsolete. The game's aircraft list, newest last.
    # Keeps EBX/ESI/EDI.
    c = Code(at["has_uav"]); c.emit(b"\x53\x56\xa1"); c.u32(n["aircraft_types"])
    c.emit(b"\x8b\x48\x08\x8b\x70\x04")                                        # count, items
    c.mark("next"); c.emit(b"\x49"); c.branch(b"\x0f\x88", "no")
    c.emit(b"\x8b\x1c\x8e\x39\x93"); c.u32(0x88); c.branch(b"\x0f\x85", "next")    # Nation
    c.emit(b"\x80\xbb"); c.u32(0x81); c.emit(b"\x03"); c.branch(b"\x0f\x85", "next")  # floatplane scout
    c.emit(b"\x83\xbb"); c.u32(0x84); c.emit(b"\x00"); c.branch(b"\x0f\x85", "next")  # developed
    c.emit(b"\x83\xbb"); c.u32(0x8C); c.emit(b"\x63"); c.branch(b"\x0f\x84", "next")  # not withdrawn
    c.emit(b"\x80\xbb"); c.u32(0x90); c.emit(b"\x00"); c.branch(b"\x0f\x85", "next")
    c.emit(b"\x83\x7b"+bytes([sensors.MARK, sensors.UAV_MARK])); c.branch(b"\x0f\x85", "next")   # a UAV model
    c.emit(b"\xb0\x01\x5e\x5b\xc3")
    c.mark("no"); c.emit(b"\x33\xc0\x5e\x5b\xc3")
    code["has_uav"] = c.finish()

    # MustStopForAircraft(EAX ship, DL mode): ships of a nation with a UAV model never stop or slow for their scouts.
    c = Code(at["must_stop"]); c.emit(b"\x50\x51\x52\x8b\xc8")
    c.emit(b"\x8b\x51\x14"); c.branch(b"\xe8", at["has_uav"]); c.emit(b"\x84\xc0\x5a\x59\x58"); c.branch(b"\x0f\x84", "native")
    c.emit(b"\x33\xc0\xc3")
    c.mark("native"); c.emit(bytes.fromhex(site["must_stop"]["original"])); c.branch(b"\xe9", site["must_stop"]["address"]+6)
    code["must_stop"] = c.finish()
    # Scout launch prompt, ESI ship: "Catapult launch search floatplane(s) from" becomes the UAV text.
    c = Code(at["prompt_text"]); c.emit(bytes.fromhex(site["prompt_text"]["original"])+b"\x50\x51\x52")
    c.emit(b"\x8b\x56\x14"); c.branch(b"\xe8", at["has_uav"]); c.emit(b"\x84\xc0\x5a\x59\x58"); c.branch(b"\x0f\x84", "keep")
    c.emit(b"\xc7\x04\x24"); c.u32(at["uav_text"]+12)
    c.mark("keep"); c.branch(b"\xe9", site["prompt_text"]["address"]+5)
    code["prompt_text"] = c.finish()
    # Catapult count (EAX ship) at the prompt and the AI launch decision: a UAV nation's ship counts one.
    c = Code(at["count"]); c.emit(b"\x50"); c.branch(b"\xe8", n["catapults"]); c.emit(b"\x59\x85\xc0"); c.branch(b"\x0f\x85", "done")
    c.emit(b"\x8b\x51\x14"); c.branch(b"\xe8", at["has_uav"]); c.emit(b"\x0f\xb6\xc0")
    c.mark("done"); c.emit(b"\xc3")
    code["count"] = c.finish()

    # Battle set-up, [EBP-74h] the minimum distance (yards) a force is moved back to: grown in the missile era.
    c = Code(at["start_distance"]); c.emit(b"\x51\xa1"); c.u32(n["year"]); c.emit(b"\x8b\x00")
    for year, percent in START_DISTANCES:
        c.emit(b"\x3d"); c.u32(year); c.emit(b"\xb9"); c.u32(percent); c.branch(b"\x0f\x8d", "scale")
    c.branch(b"\xe9", "native")
    c.mark("scale"); c.emit(b"\x8b\x45\x8c\x0f\xaf\xc1\x99\xb9\x64\x00\x00\x00\xf7\xf9\x3d"); c.u32(START_CAP)
    c.branch(b"\x0f\x8e", "store"); c.emit(b"\xb8"); c.u32(START_CAP)
    c.mark("store"); c.emit(b"\x89\x45\x8c")
    c.mark("native"); c.emit(b"\x59"+bytes.fromhex(site["start_distance"]["original"])); c.branch(b"\xe9", n["start_back"])
    code["start_distance"] = c.finish()

    # The final strike target (EBX the player's strike formation, +51h its aim point, +4Dh its carrier): a datalink
    # nation aims at the nearest spotted enemy surface ship near the old point; the "no" answer then keeps it.
    c = Code(at["datalink"]); c.emit(b"\x60")
    combat.researched(c, n, b"\x8b\x53\x38", DATALINK, "asked"); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "native")
    c.emit(b"\x6a\x00\x68"); c.u32(DATALINK_REACH+1)                       # [esp] nearest so far, [esp+4] its ship
    c.emit(b"\xa1"); c.u32(n["ships"]); c.emit(b"\x8b\x00\x8b\x78\x08")
    c.mark("next"); c.emit(b"\x4f"); c.branch(b"\x0f\x88", "picked")
    c.emit(b"\xa1"); c.u32(n["ships"]); c.emit(b"\x8b\x00\x8b\xd7"); c.branch(b"\xe8", n["list_get"]); c.emit(b"\x8b\xf0")
    c.emit(b"\x8b\x43\x4d\x8b\x80"); c.u32(0xA55); c.emit(b"\x83\xf0\x01\x3b\x86"); c.u32(0xA55)  # the other side
    c.branch(b"\x0f\x85", "next")
    c.emit(b"\x83\xbe"); c.u32(0xD59); c.emit(b"\x00"); c.branch(b"\x0f\x8e", "next")          # spotted
    c.emit(b"\x80\xbe"); c.u32(0x9D3); c.emit(b"\x0e"); c.branch(b"\x0f\x84", "next")          # not a submarine
    c.emit(b"\x8b\xc6"); c.branch(b"\xe8", n["afloat"]); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "next")
    c.emit(b"\x8d\x53\x51\x8b\xc6"); c.branch(b"\xe8", n["distance"])
    c.emit(b"\x3b\x04\x24"); c.branch(b"\x0f\x8d", "next")
    c.emit(b"\x89\x04\x24\x89\x74\x24\x04"); c.branch(b"\xe9", "next")
    c.mark("picked"); c.emit(b"\x58\x5e\x85\xf6"); c.branch(b"\x0f\x84", "native")
    for offset in (0, 4, 8):
        c.emit(b"\x8b\x86"); c.u32(0xA1C+offset); c.emit(b"\x89\x43"+bytes([0x51+offset]))
    c.emit(b"\x8b\x4b\x4d\xba"); c.u32(at["datalink_text"]+12); c.emit(b"\xa1"); c.u32(n["battle_log"])
    c.emit(b"\x8b\x38\xff\x57\x40\x61"); c.branch(b"\xe9", n["strike_kept"])
    c.mark("native"); c.emit(b"\x61"+bytes.fromhex(site["datalink"]["original"])); c.branch(b"\xe9", n["prompt_back"])
    code["datalink"] = c.finish()

    data = struct.pack("<HHiI", 1200, 2, -1, len(UAV_TEXT))+UAV_TEXT.encode("utf-16-le")+b"\0\0"
    blocks = [dict(name="Modern reconnaissance: UAV text", address=at["uav_text"], bytes=data.hex()),
              dict(name="Modern reconnaissance: datalink text", address=at["datalink_text"],
                   bytes=(struct.pack("<HHiI", 1200, 2, -1, len(DATALINK_TEXT))+DATALINK_TEXT.encode("utf-16-le")+b"\0\0").hex())]
    room = dict(missile_range=0x200, satellite=0x100, has_uav=0x100, datalink=0x200)
    for name, body in code.items():
        if len(body) > room.get(name, 0x80): raise ValueError("Modern reconnaissance code exceeds its reservation: "+name)
        blocks.append(dict(name="Modern reconnaissance: "+name, address=at[name], bytes=body.hex()))
    plans = []
    for name, s in site.items():
        old = bytes.fromhex(s["original"])
        target = at["count"] if name in CALLS else at[name]
        new = (b"\xe8" if name in CALLS else b"\xe9")+struct.pack("<i", target-s["address"]-5)+b"\x90"*(len(old)-5)
        plans.append(patch("Modern reconnaissance: "+name, s["address"], old, new))
    return blocks, plans
