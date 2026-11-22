"""Aegis-type phased-array radar (search radar class 6), AESA (class 7) and ship radar stealth.

Class 6 needs all five native search radars plus modern_tree.PHASED_ARRAY; the
native designer already allows radar limit 6 (weight 200). Stealth: a ship
designed in or after a stealth tech's year, by a nation that has the tech, is
detected by enemy radar at a shorter range. Both act where the native battle
code decides whether one ship's radar detects another (UpdateReport). Part of
the modern-research adapter; imported lazily to keep its import order free.
"""
import hashlib
import struct
import weekly_runtime as rt
import modern_tree as tree
from hull_rules import patch

BASE = 0x301000
WINDOWS = (
    (0x733AA8, 96, "4f52e8f5a3d85706e6c27d9b5c0b68e6fc832f9f264a5c5effcf7113313e0a4a"),   # GetSearchRadarClass
    (0x91963C, 350, "162dfa394869f637f1ea26db6850669dcc9e587760631c93e8e3ffd81e2f95fb"),  # GetRadarRangeAndProb
    (0x8CAB14, 101, "560ed465e7919466d69eb6d59a13aa74e2d84135f5d6e0cb1aceca094fd4d62e"),  # GetRadarSightingRange
    (0x94F928, 296, "30bbc625f7e019dda7a4714faf285a8f52f48dac48ef7ab33744d79e93477606"),  # RadarAsString
    (0x8CA100, 487, "79fb25f82b39eceffe2b2bedb6a88bfb4794faa0b4a6ba158f0e61bf50f5326a"),  # UpdateReport radar check
)
# Native class 5: 38,000 yd, 42% (range +5% after 1958), sighting 35,000 yd.
AEGIS = dict(radar_class=6, range=40000, chance=55, sighting=38000, name="Phased-array search (Aegis)")
# AESA (search radar class 7): a nation with Aegis and the AESA research; radar limit 7 in the designer, on hulls
# laid down from the AESA year, 200 t like Aegis. tree.AESA's percent scales Aegis range, chance and sighting. An AESA
# observer also halves enemy stealth.
AESA_ID, AESA_HULL_YEAR, AESA_PERCENT = tree.AESA
AESA = dict(radar_class=7, range=AEGIS["range"]*AESA_PERCENT//100, chance=AEGIS["chance"]*AESA_PERCENT//100,
            sighting=AEGIS["sighting"]*AESA_PERCENT//100, weight=200, name="AESA phased-array search")
AESA_AGE_TEXT = (f"AESA radar (radar limit 7) needs a hull laid down from {AESA_HULL_YEAR}. "
                 "The limit stays at 6; design a new class to fit it.")
WEIGHT_WINDOW = (0x950A60, 0x46, "8e22ed33185de777a179befbda60cc62e8bbffd9baa16b2abf7cfab4e1f478f1")   # GetRadarWeight
WEIGHT_ADDRESSES = dict(radar_weight=0x950A60, weight_cases=0x950A65, weight_zero=0x950AA3)
SPIN_VMT, SPIN_MAX = 0x58F214, 0x30C          # the designer's radar limit box: TSpinEdit and its FMaxValue
ADDRESSES = dict(class_tail=0x733B03, range_switch=0x91967E, range_after=0x9196E6, range_cases=0x919683,
                 sighting_switch=0x8CAB1C, sighting_done=0x8CAB61, sighting_cases=0x8CAB21,
                 name_switch=0x94F94C, name_default=0x94F9C4, name_cases=0x94F951, name_done=0x94F9DD,
                 assign=0x30BCCC, stealth_site=0x8CA2D5, range_to_ship=0x8ECD20,
                 has_research=0x729FA4, nation=0x750040)
SITES = (("class_tail", 5), ("range_switch", 5), ("sighting_switch", 5), ("name_switch", 5), ("stealth_site", 9))
# Stealth aircraft: prototype decision, its data section and mark, CAP detection, AA radar bonus.
AIRCRAFT_WINDOWS = (
    (0x7ED5E8, 958, "8d04ad2c260dfb4a5d1c5e4185607e14baaf2acdbb9b172362c3c2aa1f8d5b4d"),  # CreateAircraftPrototype
    (0x970FD0, 287, "1dce9b94df2cd3753552030dcd6005212ecff1ab337d4ed18bf0c675fb242535"),  # aircraft data lookup
    (0x962D60, 191, "be95c3443626c3d18cadddfcb129ae032aa8f5effaccc7df54a4b6acb1e648b5"),  # CAPIntercept
    (0x96105E, 31, "d9c2d50d89ab446112d1b16bbb7d97b213843eb42d393f1128e64e39f538700e"),   # AttackShips radar AA bonus
)
AIRCRAFT_ADDRESSES = dict(prototype=0x7ED65F, lookup_name=0x9710DA, label=0x7ED960, cap=0x962DE3, aa=0x961074,
                          type_name=0x970254, randomize=0x96DF4C)
AIRCRAFT_SITES = (("prototype", 6), ("lookup_name", 5), ("label", 7), ("cap", 8), ("aa", 9))
# Designer radar limit: Aegis (limit 6) only on hulls laid down from 1975 (BuildYear;
# new classes get the current year, editing an existing class keeps its own).
AEGIS_HULL_YEAR = 1975
LIMIT_WINDOW = (0x5F6C8C, 53, "6ad79d5532a263de4ed96dc426904fd0a3d5d9bcf0453e56982ff1afdef4fcc7")   # seRadarLimitChange
LIMIT_ADDRESSES = dict(radar_limit=0x5F6CAA, set_value=0x590CC4, message=0x4D7124)
AEGIS_AGE_TEXT = ("Aegis radar (radar limit 6) needs a hull laid down from 1975. "
                  "The limit stays at 5; design a new class to fit it.")   # fits page+0xE00..0xF00
UCAV_NAME = "Unmanned jet attack"   # data section of unmanned stealth jet attack models (modern_aircraft.UCAV)
UAV_NAME = "Shipborne UAV"          # data section of floatplane-scout UAV models (modern_aircraft.UAV)
# A new model's variant mark: TAircraftType+0x1C (CruiseAltitude), saved and copied (Assign) with the type, read by
# no native code (0 in every save). Names cannot carry it: the game renames prototypes and types entering service.
MARK, STEALTH_MARK, UCAV_MARK, UAV_MARK = 0x1C, 1, 2, 3   # the marks are the prototype flag values
UAV_REQUEST = 0xF02   # page offset of a byte: the player's UAV request is being completed (modern_carrier sets it)
STEALTH_NAMES = ("Stealth light jet fighter", "Stealth heavy jet fighter", "Stealth jet attack")   # jet types 10-12
CAP_RANGE_PERCENT = 65


def discover(blob, base, normalized):
    for address, size, digest in WINDOWS:
        if hashlib.sha256(normalized[address-BASE:address-BASE+size]).hexdigest() != digest:
            raise ValueError("Modern sensors refuse changed native radar code at "+hex(address)+".")
    delta = base-BASE
    for name, address in (("GetSearchRadarClass", 0x733AA8), ("GetRadarRangeAndProb", 0x91963C),
                          ("GetRadarSightingRange", 0x8CAB14), ("RadarAsString", 0x94F928),
                          ("HasResearchId", 0x729FA4), ("GetBNation", 0x750040)):
        if rt.method_address(blob, base, name) != address+delta:
            raise ValueError("Unsupported native radar method: "+name)
    # The battle code's own main-campaign pointer (GetFightingShipDataFromDesign).
    load = 0x8ED02C-BASE
    if normalized[load:load+9] != bytes.fromhex("a1707a9f008b008bd6"):
        raise ValueError("Unsupported native campaign pointer.")
    for address, size, digest in AIRCRAFT_WINDOWS:
        if hashlib.sha256(normalized[address-BASE:address-BASE+size]).hexdigest() != digest:
            raise ValueError("Modern sensors refuse changed native aircraft code at "+hex(address)+".")
    for address, size, digest in (LIMIT_WINDOW, WEIGHT_WINDOW):
        if hashlib.sha256(normalized[address-BASE:address-BASE+size]).hexdigest() != digest:
            raise ValueError("Modern sensors refuse changed native designer code at "+hex(address)+".")
    for name, address in (("CreateAircraftPrototype", 0x7ED5E8), ("CAPIntercept", 0x962D60), ("AttackShips", 0x96048C),
                          ("seRadarLimitChange", 0x5F6C8C)):
        if rt.method_address(blob, base, name) != address+delta:
            raise ValueError("Unsupported native aircraft method: "+name)
    every = {**ADDRESSES, **AIRCRAFT_ADDRESSES, **LIMIT_ADDRESSES, **WEIGHT_ADDRESSES}
    info = {k: v+delta for k, v in every.items()}
    info["main"] = struct.unpack_from("<I", blob, load+1)[0]
    info["sites"] = [dict(name=name, address=address+delta,
                          original=blob[address-BASE:address-BASE+size].hex())
                     for name, size in SITES+AIRCRAFT_SITES+(("radar_limit", 6), ("radar_weight", 5))
                     for address in [every[name]]]
    return info


def limit_box(read, blob, base):
    """Data patch: the designer's radar limit box goes to 7 (AESA). read(address, size) reads the game."""
    import native_designer
    from hull_rules import patch
    form = native_designer.discover(blob, base, read)
    u32 = lambda address: struct.unpack("<I", read(address, 4))[0]
    spin = u32(u32(form["slot"])+form["fields"]["seRadarLimit"])
    if u32(spin) != SPIN_VMT+base-BASE or u32(spin+SPIN_MAX) != AEGIS["radar_class"]:
        raise ValueError("Unsupported native radar limit box.")
    return [patch("Modern sensors: radar limit box to 7", spin+SPIN_MAX, struct.pack("<i", AEGIS["radar_class"]),
                  struct.pack("<i", AESA["radar_class"]))]


def build(page, info, aesa_page, spare=None):
    """Code at page+0x400.. of the modern-research loader page and in aesa_page (its own page); returns blocks and
    patches."""
    from campaign_security import Code   # imported late: campaign_security imports modern_research
    at = {name: page+offset for name, offset in
          dict(class_tail=0x400, range_switch=0x480, sighting_switch=0x500, name_switch=0x580,
               stealth_site=0x600, literal=0x800).items()}
    at.update(radar_weight=aesa_page, aesa_literal=aesa_page+0x200)
    code = {}
    c = Code(at["class_tail"])   # EBX nation, ESI native count of the five search radars
    c.emit(b"\x83\xfe\x05"); c.branch(b"\x0f\x85", "done")
    c.emit(b"\x8b\xc3\xba"); c.u32(tree.PHASED_ARRAY); c.branch(b"\xe8", info["has_research"])
    c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "done")
    c.emit(b"\xbe"); c.u32(AEGIS["radar_class"])
    c.emit(b"\x8b\xc3\xba"); c.u32(AESA_ID); c.branch(b"\xe8", info["has_research"])   # Aegis and AESA research
    c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "done")
    c.emit(b"\xbe"); c.u32(AESA["radar_class"])
    c.mark("done"); c.emit(bytes.fromhex("8bc65e5bc3")); code["class_tail"] = c.finish()
    c = Code(at["range_switch"])   # EAX class, ESI range out, EDI chance out
    for radar in (AEGIS, AESA):
        c.emit(b"\x83\xf8"+bytes([radar["radar_class"]])); c.branch(b"\x0f\x85", f"not{radar['radar_class']}")
        c.emit(b"\xc7\x06"); c.u32(radar["range"]); c.emit(b"\xc7\x07"); c.u32(radar["chance"])
        c.branch(b"\xe9", info["range_after"])
        c.mark(f"not{radar['radar_class']}")
    c.emit(b"\x83\xf8\x05"); c.branch(b"\x0f\x87", info["range_after"]); c.branch(b"\xe9", info["range_cases"])
    code["range_switch"] = c.finish()
    c = Code(at["sighting_switch"])   # ECX class, EAX result (0)
    for radar in (AEGIS, AESA):
        c.emit(b"\x83\xf9"+bytes([radar["radar_class"]])); c.branch(b"\x0f\x85", f"not{radar['radar_class']}")
        c.emit(b"\xb8"); c.u32(radar["sighting"]); c.branch(b"\xe9", info["sighting_done"])
        c.mark(f"not{radar['radar_class']}")
    c.emit(b"\x83\xf9\x05"); c.branch(b"\x0f\x87", info["sighting_done"]); c.branch(b"\xe9", info["sighting_cases"])
    code["sighting_switch"] = c.finish()
    c = Code(at["name_switch"])   # EAX class, ESI result string
    for radar, text_at in ((AEGIS, at["literal"]), (AESA, at["aesa_literal"])):
        c.emit(b"\x83\xf8"+bytes([radar["radar_class"]])); c.branch(b"\x0f\x85", f"not{radar['radar_class']}")
        c.emit(b"\x8b\xc6\xba"); c.u32(text_at+12); c.branch(b"\xe8", info["assign"]); c.branch(b"\xe9", info["name_done"])
        c.mark(f"not{radar['radar_class']}")
    c.emit(b"\x83\xf8\x05"); c.branch(b"\x0f\x87", info["name_default"]); c.branch(b"\xe9", info["name_cases"])
    code["name_switch"] = c.finish()
    # GetRadarWeight(EAX design, EDX radar limit) -> EAX tons. The native AI reserves one class above its nation's
    # (limit 7 with Aegis, 8 with AESA); natively those weighed nothing, a free radar.
    c = Code(at["radar_weight"])
    c.emit(b"\x83\xfa"+bytes([AESA["radar_class"]])); c.branch(b"\x0f\x8c", "native")
    c.emit(b"\xb8"); c.u32(AESA["weight"]); c.emit(b"\xc3")
    c.mark("native"); c.emit(b"\x83\xfa\x06"); c.branch(b"\x0f\x87", info["weight_zero"]); c.branch(b"\xe9", info["weight_cases"])
    code["radar_weight"] = c.finish()
    # EBX target ship, ESI observer, [EBP-8] adjusted radar range. An observer with AESA fitted (radar +0xA0B is 7;
    # the campaign caps it at the nation's class and the design's limit) halves the target's stealth cuts.
    c = Code(at["stealth_site"])
    c.emit(b"\x60\x6a\x00\xa1"); c.u32(info["main"]); c.emit(b"\x8b\x00\x85\xc0"); c.branch(b"\x0f\x84", "done")   # [esp] AESA
    c.emit(b"\x83\xbe"); c.u32(0xA0B); c.emit(bytes([AESA["radar_class"]])); c.branch(b"\x0f\x8c", "target")
    c.emit(b"\xc7\x04\x24\x01\x00\x00\x00")
    c.mark("target"); c.emit(b"\xa1"); c.u32(info["main"]); c.emit(b"\x8b\x00")
    c.emit(b"\x8b\x53\x14"); c.branch(b"\xe8", info["nation"]); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "done")
    c.emit(b"\x8b\xf8")
    for index, (ident, year, percent) in enumerate(tree.STEALTH):
        c.emit(b"\x81\xbb"); c.u32(0xB28); c.u32(year); c.branch(b"\x0f\x8c", f"skip{index}")   # DesignYear
        c.emit(b"\x8b\xc7\xba"); c.u32(ident); c.branch(b"\xe8", info["has_research"])
        c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", f"skip{index}")
        c.emit(b"\xb9"); c.u32(100-percent); c.emit(b"\x83\x3c\x24\x00"); c.branch(b"\x0f\x84", f"cut{index}")
        c.emit(b"\xb9"); c.u32(100-percent//2)
        c.mark(f"cut{index}"); c.emit(b"\x8b\x45\xf8\x0f\xaf\xc1\xb9"); c.u32(100); c.emit(b"\x99\xf7\xf9\x89\x45\xf8")
        c.mark(f"skip{index}")
    c.mark("done"); c.emit(b"\x83\xc4\x04\x61\x8b\xd3\x8b\xc6"); c.branch(b"\xe8", info["range_to_ship"])
    c.branch(b"\xe9", info["stealth_site"]+9)
    code["stealth_site"] = c.finish()
    aircraft_blocks = aircraft(page, info, code, at, aesa_page, spare)
    blocks = [dict(name="Aegis radar name", address=at["literal"], bytes=literal(AEGIS["name"]).hex()),
              dict(name="AESA radar name", address=at["aesa_literal"], bytes=literal(AESA["name"]).hex())]
    blocks += aircraft_blocks
    plans = []
    for site in info["sites"]:
        body = code[site["name"]]
        if len(body) > 0x80 and site["name"] not in ("stealth_site", "prototype") or len(body) > 0x200:
            raise ValueError("Modern sensor code exceeds its reservation: "+site["name"])
        blocks.append(dict(name="Modern sensors: "+site["name"], address=at[site["name"]], bytes=body.hex()))
        old = bytes.fromhex(site["original"])
        # The lookup-name site is itself a call: keep a call so the routine can return.
        opcode = b"\xe8" if site["name"] == "lookup_name" else b"\xe9"
        plans.append(patch("Modern sensors: "+site["name"], site["address"], old,
                           opcode+struct.pack("<i", at[site["name"]]-site["address"]-5)+b"\x90"*(len(old)-5)))
    return blocks, plans


def literal(text):
    return struct.pack("<HHiI", 1200, 2, -1, len(text))+text.encode("utf-16-le")+b"\0\0"


def aircraft(page, info, code, at, aesa_page, spare=None):
    """Stealth jet prototypes: built from their own data section and marked (MARK), harder to intercept.
    With room at spare: a stealth jet attack prototype from tree.UCAV_YEAR of a nation with tree.UAVS is unmanned
    (UCAV_MARK): its own section, and it stays a stealth model."""
    from campaign_security import Code
    at.update(prototype=page+0x900, lookup_name=page+0x980, label=page+0xA00, cap=page+0xA80, aa=page+0xB00,
              is_stealth=page+0xB80, names=page+0xD60, flags=page+0xF00, uav_check=page+0xF10, uav_name=page+0xFA0)
    lookup_flag, label_flag = at["flags"], at["flags"]+1
    texts = [page+0xC40+i*0x40 for i in range(3)]
    ident, year = tree.AIRCRAFT_STEALTH
    c = Code(at["prototype"])   # ESI main, EDI nation index, [EBP-0xD] type, [EBP-0x14] data year
    c.emit(b"\x60\x66\xc7\x05"); c.u32(lookup_flag); c.emit(b"\x00\x00")
    c.branch(b"\xe8", at["uav_check"])                                             # a floatplane scout may be a UAV
    c.emit(bytes.fromhex("0fb645f383e80a83f802")); c.branch(b"\x0f\x87", "done")
    c.emit(b"\x81\x7d\xec"); c.u32(year); c.branch(b"\x0f\x8c", "done")
    c.emit(b"\x8b\xc6\x8b\xd7"); c.branch(b"\xe8", info["nation"]); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "done")
    c.emit(b"\xba"); c.u32(ident); c.branch(b"\xe8", info["has_research"])
    c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "done")
    c.emit(b"\x66\xc7\x05"); c.u32(lookup_flag); c.emit(bytes([STEALTH_MARK]*2))
    if spare: c.branch(b"\xe8", spare)
    c.mark("done"); c.emit(bytes.fromhex("610fb645f38bcb")); c.branch(b"\xe9", info["prototype"]+6)
    code["prototype"] = c.finish()
    c = Code(at["lookup_name"])   # replaces the call: EAX type, EDX destination string
    c.emit(b"\x80\x3d"); c.u32(lookup_flag); c.emit(b"\x00"); c.branch(b"\x0f\x84", "native")
    c.emit(b"\x80\x3d"); c.u32(lookup_flag); c.emit(bytes([UAV_MARK])); c.branch(b"\x0f\x85", "not_uav")   # UAV section
    c.emit(b"\xc6\x05"); c.u32(lookup_flag); c.emit(b"\x00\x52\xba"); c.u32(at["uav_name"]+12); c.emit(b"\x58")
    c.branch(b"\xe9", info["assign"])
    c.mark("not_uav")
    if spare:   # MOV keeps the flags of the compare
        c.emit(b"\x80\x3d"); c.u32(lookup_flag); c.emit(bytes([UCAV_MARK])+b"\xc6\x05"); c.u32(lookup_flag); c.emit(b"\x00"); c.branch(b"\x0f\x85", "manned")
        c.emit(b"\x52\xba"); c.u32(spare+0xC0+12); c.emit(b"\x58"); c.branch(b"\xe9", info["assign"])
        c.mark("manned")
    c.emit(b"\xc6\x05"); c.u32(lookup_flag); c.emit(b"\x00")
    c.emit(bytes.fromhex("520fb6c083e80a8b1485")); c.u32(at["names"]); c.emit(b"\x58")
    c.branch(b"\xe9", info["assign"])
    c.mark("native"); c.branch(b"\xe9", info["type_name"])
    code["lookup_name"] = c.finish()
    c = Code(at["label"])   # EBX the new model (a fresh object): the flag value is its mark, 0 when unflagged
    c.emit(b"\x0f\xb6\x05"); c.u32(label_flag); c.emit(b"\x89\x43"+bytes([MARK]))
    c.emit(b"\xc6\x05"); c.u32(label_flag); c.emit(b"\x00")
    c.emit(b"\x8b\xc3"); c.branch(b"\xe8", info["randomize"]); c.branch(b"\xe9", info["label"]+7)
    code["label"] = c.finish()
    # In the prototype hook's PUSHAD (ESI main, EDI nation index, [EBP-0xD] type, [EBP-0x14] data year): a floatplane
    # scout is a UAV model (UAV_MARK) when the player asked for a UAV (the request dialog's UAV entry; the flag stays
    # set for all the request's prototypes, modern_carrier clears it), or for a computer nation from tree.UAV_YEAR
    # with tree.UAVS. The player's other floatplane scouts stay floatplanes.
    request = page+UAV_REQUEST
    c = Code(at["uav_check"]); c.emit(b"\x80\x7d\xf3\x03"); c.branch(b"\x0f\x85", "ret")
    c.emit(b"\x81\x7d\xec"); c.u32(tree.UAV_YEAR); c.branch(b"\x0f\x8c", "ret")   # no UAV data rows before (player too)
    c.emit(b"\x8b\xc6\x8b\xd7"); c.branch(b"\xe8", info["nation"]); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "ret")
    c.emit(b"\x3b\x86"); c.u32(0x3204); c.branch(b"\x0f\x85", "computer")          # the player's nation
    c.emit(b"\x80\x3d"); c.u32(request); c.emit(b"\x00"); c.branch(b"\x0f\x84", "ret")
    c.branch(b"\xe9", "uav")
    c.mark("computer"); c.emit(b"\xba"); c.u32(tree.UAVS); c.branch(b"\xe8", info["has_research"]); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "ret")
    c.mark("uav"); c.emit(b"\x66\xc7\x05"); c.u32(lookup_flag); c.emit(bytes([UAV_MARK]*2))
    c.mark("ret"); c.emit(b"\xc3")
    uav_check = c.finish(); assert len(uav_check) <= at["uav_name"]-at["uav_check"]
    c = Code(at["is_stealth"])   # EAX aircraft model -> AL: its mark is STEALTH_MARK or UCAV_MARK
    c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "no")
    c.emit(b"\x8b\x40"+bytes([MARK]))
    for mark in (STEALTH_MARK, UCAV_MARK):
        c.emit(b"\x83\xf8"+bytes([mark])); c.branch(b"\x0f\x84", "yes")
    c.mark("no"); c.emit(b"\x31\xc0\xc3")
    c.mark("yes"); c.emit(b"\xb0\x01\xc3")
    code["is_stealth"] = c.finish()
    c = Code(at["cap"])   # ESI enemy air formation; [ESP] defender radar range, [ESP+4] chance
    c.emit(b"\x85\xf6"); c.branch(b"\x0f\x84", "native")
    c.emit(b"\x60\x8b\x46\x10"); c.branch(b"\xe8", at["is_stealth"]); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "done")
    c.emit(b"\x8b\x44\x24\x20\x6b\xc0"+bytes([CAP_RANGE_PERCENT])+b"\x99\xb9"); c.u32(100)
    c.emit(b"\xf7\xf9\x89\x44\x24\x20")
    c.mark("done"); c.emit(b"\x61")
    c.mark("native"); c.emit(bytes.fromhex(info_site(info, "cap"))); c.branch(b"\xe9", info["cap"]+8)
    code["cap"] = c.finish()
    c = Code(at["aa"])   # EAX defending ship, [EBP-0xC] attacking formation, [EBP-4] AA total
    c.emit(b"\x8b\x80"); c.u32(0xA0B); c.emit(b"\x50\x8b\x45\xf4\x8b\x40\x10"); c.branch(b"\xe8", at["is_stealth"])
    c.emit(b"\x84\xc0\x58"); c.branch(b"\x0f\x84", "add"); c.emit(b"\xd1\xe8")   # radar bonus halved
    c.mark("add"); c.emit(b"\x01\x45\xfc"); c.branch(b"\xe9", info["aa"]+9)
    code["aa"] = c.finish()
    at.update(radar_limit=page+0xD80, age_text=page+0xE00, aesa_age_text=aesa_page+0x300)
    c = Code(at["radar_limit"])   # EAX new spin value, EBX designer form, ESI ship design
    c.emit(b"\x83\xf8\x06"); c.branch(b"\x0f\x8c", "store")
    c.emit(b"\x81\xbe"); c.u32(0xE4); c.u32(AEGIS_HULL_YEAR); c.branch(b"\x0f\x8c", "aegis")   # BuildYear
    c.emit(b"\x83\xf8"+bytes([AESA["radar_class"]])); c.branch(b"\x0f\x8c", "store")
    c.emit(b"\x81\xbe"); c.u32(0xE4); c.u32(AESA_HULL_YEAR); c.branch(b"\x0f\x8d", "store")
    c.emit(b"\x6a\x06\x68"); c.u32(at["aesa_age_text"]+12); c.branch(b"\xe9", "refuse")   # pushes the limit kept, the text
    c.mark("aegis"); c.emit(b"\x6a\x05\x68"); c.u32(at["age_text"]+12)
    c.mark("refuse"); c.emit(b"\x60\x8b\x44\x24\x20\x83\xca\xff\x83\xc9\xff"); c.branch(b"\xe8", info["message"])
    # Shows the kept limit in the control; the re-entered change handler stores it as well.
    c.emit(b"\x8b\x83"); c.u32(0xA5C); c.emit(b"\x8b\x54\x24\x24"); c.branch(b"\xe8", info["set_value"])
    c.emit(b"\x61\x8b\x44\x24\x04\x83\xc4\x08")
    c.mark("store"); c.emit(b"\x89\x86"); c.u32(0xA13); c.branch(b"\xe9", info["radar_limit"]+6)
    code["radar_limit"] = c.finish()
    blocks = [dict(name="Aegis hull age text", address=at["age_text"], bytes=literal(AEGIS_AGE_TEXT).hex()),
              dict(name="AESA hull age text", address=at["aesa_age_text"], bytes=literal(AESA_AGE_TEXT).hex()),
              dict(name="stealth type names", address=at["names"], bytes=struct.pack("<3I", *(t+12 for t in texts)).hex()),
              dict(name="stealth is-model", address=at["is_stealth"], bytes=code.pop("is_stealth").hex())]
    blocks += [dict(name=n, address=t, bytes=literal(n).hex()) for n, t in zip(STEALTH_NAMES, texts)]
    blocks += [dict(name="UAV prototype", address=at["uav_check"], bytes=uav_check.hex()),
               dict(name="UAV type name", address=at["uav_name"], bytes=literal(UAV_NAME).hex())]
    if spare:   # in the prototype hook's PUSHAD: ESI main, EDI nation index, [EBP-0xD] type, [EBP-0x14] data year
        c = Code(spare); c.emit(b"\x80\x7d\xf3\x0c"); c.branch(b"\x0f\x85", "ret")
        c.emit(b"\x81\x7d\xec"); c.u32(tree.UCAV_YEAR); c.branch(b"\x0f\x8c", "ret")
        c.emit(b"\x8b\xc6\x8b\xd7"); c.branch(b"\xe8", info["nation"]); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "ret")
        c.emit(b"\xba"); c.u32(tree.UAVS); c.branch(b"\xe8", info["has_research"]); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "ret")
        c.emit(b"\x66\xc7\x05"); c.u32(lookup_flag); c.emit(bytes([UCAV_MARK]*2))
        c.mark("ret"); c.emit(b"\xc3")
        body = c.finish(); assert len(body) <= 0x80
        blocks += [dict(name="unmanned prototype", address=spare, bytes=body.hex()),
                   dict(name="unmanned type name", address=spare+0xC0, bytes=literal(UCAV_NAME).hex())]
    return blocks


def info_site(info, name):
    return next(site["original"] for site in info["sites"] if site["name"] == name)
