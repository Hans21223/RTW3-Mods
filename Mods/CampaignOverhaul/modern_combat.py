"""Guided shells and torpedoes, hypersonic missile speed and electromagnetic catapults (EMALS).

Battle hooks for the modern-research adapter, each gated by its own research (modern_tree):
- Guided gun projectiles: guns of GUIDED_SHELLS calibre and less of a researching nation hit twice as often
  (FireGuns, after the native hit chance); larger guns 1.5 times as often with HEAVY_GUIDED_SHELLS.
- Railgun main batteries (modern_railgun) fire "railguns" in the battle log and show "(EML)" after their gun
  line in the three ship information screens.
- Wake-homing and wire-guided torpedoes: torpedoes fired by a researching nation's ships hit ships they
  pass at 2.5 times the native distance (recorded at launch, applied where the native hit distance is tested).
- Hypersonic SSMs (modern_railgun's launch record) fly HYPER_SPEED times as fast; a step that would carry a
  missile past its target ends inside the native 3,000-yard hit window instead.
- EMALS: carriers laid down from 2017 by a researching nation get 4 spot per catapult instead of 1, and heavy
  jets need 24,000 tons instead of the steam-catapult 30,000 (the native check uses the player's research).
- Ski jump (STOBAR, Kuznetsov): heavy jets also go on jet-capable angled-deck carriers without catapults that have
  the designer's ski jump (modern_carrier: bit 1 of the JetCapable byte), and a ski-jump flight deck without
  catapults readies SKI_JUMP more aircraft per strike.
Part of the modern-research adapter; imported lazily.
"""
import hashlib
import re
import struct
import weekly_runtime as rt
import modern_tree as tree
import modern_carrier as carrier
from hull_rules import patch

BASE = 0x301000
HYPER_SPEED = 5                # hypersonic missiles (Mach 4-5 glide and cruise) against native 320-550 knots
TORPEDO_SLOTS = 128            # most recent guided torpedo launches remembered by object address
TORPEDOES, CURSOR = 0x810, 0x808   # page offsets of that table and its cursor (undersea reads and fills them)
WINDOWS = (
    (0x908409, 0x3A, "4ef18b37addca429469a234e201ff8f4e17673463b23e528bfb535cf22c97f85"),   # FireGuns hit chance
    (0x876488, 0xA5, "90e8559b83bb5099983e5286603b6dfbe814f9de4161b637cc04141d794a563e"),   # FireTorpedo
    (0x8C2A08, 0x32, "98b55ca8c65ab9f443fbe77f04a3596e9bfe61a5a78a94ebca2370daccccda8f"),   # torpedo hit distance
    (0x925BE8, 0x8B, "7741802734ce5042d846fd641e72795d78575d0b682baf68ab21fc43c8276a8a"),   # MoveMe
    (0x8C0BA0, 0x3B, "33341dc0b20716fe5eeb84dfd4c8f4250f2e09fcd0215206c43786b3fd1a8d21"),   # missile proximity
    (0x9500A0, 0x1CF, "7b2e10bcb19d589eaabc15bc2e8c188c70a3357dccd315b5334d4d32702b1c05"),  # GetSpotValue
    (0x97D408, 0x60, "fd2d00ba91c2ff63da4a6772060235a77b25ba2ba4912fb191fa3ae8eddafc2d"),   # heavy jet carriers
    (0x909137, 0x8E, "27065827eb2262ce52e6595f9c9db4277906030e9a9a6d1c457dbbe375bf14f0"),   # FireGuns log: own ships
    (0x90930E, 0x70, "1579344c5626bbf53d0b81f707bbade5ad6ee059fbe7a6eff0d116504e20dee4"),   # FireGuns log: seen firing
    # Main gun line and its " (DP)" in three ship information screens (Text get/set, UStrCat verified here).
    (0x6CF9F4, 0x44, "e24bfcec80924e98029e4938242f9e933c5f1c08ec23870b183f97c4a9dddbf8"),
    (0x6D3AA6, 0x3F, "f351392a34b9e0ae690283797c315bbf441dd836965333991560c25b8b8383b5"),
    (0x6D4D9B, 0x3F, "0191fb01f1b9cbf69c57678be1331c41ab7bf83a094867ebf925f92ee9268dec"),
    # Heavy jet carrier rule (jet capable, angled deck, catapults): the air-group screen (EBX carrier) and the
    # air-unit check (EDI unit, [unit+1Ch] its nation index, ESI carrier).
    (0x631A7C, 0x49, "a825407b6ba04fa952379c6bd789c5ce310e1df8b8679e993748c5f73cc0dd1d"),
    (0x97D1B4, 0x1D, "d037fef8a69cfcca50c8dfb68fb287d84dcd4d7b1ed2509e2cc61d1e5a4c10a1"),
    (0x97D327, 0x39, "ec789378de07b065fb506b239165e0d69269f1796197f8fac5ab2e53f820979d"),
)
RAILGUN_BYTE, RAILGUN = 0x9A6, 2   # modern_railgun: the main battery's Increased elevation byte holds 2
# Ship information screens: (site, bytes replaced, ship local, form local, string local, label field)
TAGS = (("tag_battle", 0x6CFA33, 5, -0xC, -8, -0xE4), ("tag_info", 0x6D3ADC, 9, -8, -4, -0x50),
        ("tag_view", 0x6D4DD1, 9, -0x10, -8, -0x68))
LABEL, TAG = 0x5C4, " (EML)"
NATIVE = dict(has_research=0x729FA4, nation=0x750040, catapults=0x94F7FC, distance=0x5733F4,
              shells_back=0x908443, launch_back=0x876520, hit_back=0x8C2A3A, step_back=0x925C44, torpedo_gone=0x8C29C8,
              spot_back=0x95026A, jets_back=0x97D446, get_text=0x451C50, set_text=0x451CA0, str_cat=0x30C63C,
              jets_ok=0x631AC5, jets_refused=0x631AB0, unit_angled=0x97D34A, unit_refused=0x97D353)
SITES = (("shells", 0x90843C, 7), ("torpedo_launch", 0x876519, 7), ("torpedo_hit", 0x8C2A34, 6),
         ("missile_step", 0x925C3E, 6), ("spot", 0x950261, 9), ("heavy_jets", 0x97D43F, 7),
         ("log_own", 0x909195, 5), ("log_seen", 0x909353, 5), ("jets_ui", 0x631AA7, 9), ("jets_unit", 0x97D341, 9))+tuple((name, site, size) for name, site, size, *_ in TAGS)
MAIN_LOAD = 0x8ED02C   # GetFightingShipDataFromDesign: mov eax, [main campaign pointer]


def discover(blob, base, normalized):
    for address, size, digest in WINDOWS:
        if hashlib.sha256(normalized[address-BASE:address-BASE+size]).hexdigest() != digest:
            raise ValueError("Modern combat refuses changed native code at "+hex(address)+".")
    delta = base-BASE
    for name, address in (("HasResearchId", 0x729FA4), ("GetBNation", 0x750040), ("CountCatapults", 0x94F7FC),
                          ("GetSpotValue", 0x9500A0)):   # MoveMe is two classes' name; its window verifies it
        if rt.method_address(blob, base, name) != address+delta:
            raise ValueError("Unsupported native combat method: "+name)
    if normalized[MAIN_LOAD-BASE:MAIN_LOAD-BASE+9] != bytes.fromhex("a1707a9f008b008bd6"):
        raise ValueError("Unsupported native campaign pointer.")
    texts = [m.start() for m in re.finditer(re.escape(b"\x04Text"), blob)
             if struct.unpack_from("<II", blob, m.start()-22) == (NATIVE["get_text"]+delta, NATIVE["set_text"]+delta)]
    if not texts:
        raise ValueError("Unsupported native control text accessors.")
    info = {k: v+delta for k, v in NATIVE.items()}
    info["main"] = struct.unpack_from("<I", blob, MAIN_LOAD-BASE+1)[0]
    info["sites"] = [dict(name=name, address=address+delta, original=blob[address-BASE:address-BASE+size].hex())
                     for name, address, size in SITES]
    return info


def researched(c, info, nation_from, ident, label):
    """AL := the nation (index loaded into EDX by nation_from, after EAX holds the campaign) has ident.
    Clobbers EAX/ECX/EDX; AL is 0 without a nation object."""
    c.emit(b"\xa1"); c.u32(info["main"]); c.emit(b"\x8b\x00"+nation_from); c.branch(b"\xe8", info["nation"])
    c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", label)
    c.emit(b"\xba"); c.u32(ident); c.branch(b"\xe8", info["has_research"])
    c.mark(label)


def paid(c, doctrine):
    """EDI firer: the shell doctrine (shell_doctrine.py) lets its nation fire guided shells, and charges it."""
    if doctrine:
        c.emit(b"\x8b\x57\x14"); c.branch(b"\xe8", doctrine["use_guided"]); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "done")


def build(page, info, is_hyper, ext, doctrine=None, targets=None, att=None):
    """One page: code, then the torpedo record and constants. is_hyper(EBX missile) sets ZF clear for
    modern_railgun's hypersonic launches; ext is modern_extension's lookup (railgun secondary bits)."""
    from modern_railgun import RAIL_BATTERIES
    from campaign_security import Code   # imported late: campaign_security imports modern_research
    at = dict(shells=page, torpedo_launch=page+0x100, torpedo_hit=page+0x200, missile_step=page+0x280,
              spot=page+0x6A0, heavy_jets=page+0x380, log_own=page+0xA80, log_seen=page+0xB40, tag_battle=page+0x480,
              tag_info=page+0x500, tag_view=page+0x580, own_text=page+0x600, seen_text=page+0x640, tag_text=page+0x680,
              heavy_factor=page+0x7FC, factor=page+0x800, jets_flag=page+0x804, cursor=page+CURSOR, torpedoes=page+TORPEDOES,
              jets_ui=page+0xC00, jets_unit=page+0xC80)
    n, code = info, {}
    original = {site["name"]: bytes.fromhex(site["original"]) for site in info["sites"]}

    # FireGuns, after GetHitChance: [ebp-24h] firer, [ebp+18h] battery (calibre at [firer+69h+battery*4]).
    ident, calibre, percent = tree.GUIDED_SHELLS
    c = Code(at["shells"])
    c.emit(b"\xd9\x5d\xc8\x9b\x60\x8b\x7d\xdc\x8b\x45\x18\x8b\x4c\x87\x69")   # fstp [ebp-38h]; pushad; edi firer; ecx calibre
    c.emit(b"\x83\xf9\x01"); c.branch(b"\x0f\x8c", "done"); c.emit(b"\x83\xf9"+bytes([calibre])); c.branch(b"\x0f\x8f", "heavy")
    researched(c, n, b"\x8b\x57\x14", ident, "asked"); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "done")
    paid(c, doctrine)
    c.emit(b"\xd9\x45\xc8\xd8\x0d"); c.u32(at["factor"]); c.emit(b"\xd9\x5d\xc8")                  # hit chance x factor
    c.branch(b"\xe9", "done")
    c.mark("heavy"); researched(c, n, b"\x8b\x57\x14", tree.HEAVY_GUIDED_SHELLS[0], "heavy_asked")
    c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "done")
    paid(c, doctrine)
    c.emit(b"\xd9\x45\xc8\xd8\x0d"); c.u32(at["heavy_factor"]); c.emit(b"\xd9\x5d\xc8")
    c.mark("done"); c.emit(b"\x61\xd9\x45\xc8"); c.branch(b"\xe9", n["shells_back"])
    code["shells"] = c.finish()

    # FireGuns log lines, where the native code pushes "in guns at " (own ships) or " guns at " (ships seen
    # firing): a railgun main battery says railguns. [ebp-24h] firer, [ebp+18h] battery (1 = main).
    for name, text in (("log_own", "own_text"), ("log_seen", "seen_text")):
        c = Code(at[name]); c.emit(original[name]+b"\x50\x51\x52\x8b\x45\xdc\x83\x7d\x18\x01"); c.branch(b"\x0f\x85", "other")
        c.emit(b"\x80\xb8"); c.u32(RAILGUN_BYTE); c.emit(bytes([RAILGUN])); c.branch(b"\x0f\x85", "keep"); c.branch(b"\xe9", "rail")
        c.mark("other"); c.branch(b"\xe8", ext); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "keep")
        for bit, _, _, number in RAIL_BATTERIES:   # railgun secondaries and tertiaries
            c.emit(b"\x83\x7d\x18"+bytes([number])); c.branch(b"\x0f\x85", f"not{number}")
            c.emit(b"\xf7\x00"); c.u32(bit); c.branch(b"\x0f\x85", "rail"); c.branch(b"\xe9", "keep")
            c.mark(f"not{number}")
        c.branch(b"\xe9", "keep")
        c.mark("rail"); c.emit(b"\xc7\x44\x24\x0c"); c.u32(at[text]+12)                  # replace the pushed text
        c.mark("keep"); c.emit(b"\x5a\x59\x58"); c.branch(b"\xe9", next(s["address"] for s in info["sites"] if s["name"] == name)+5)
        code[name] = c.finish()
    # Ship information: after the main gun line got its native " (DP)", a railgun battery appends " (EML)" the
    # same way (the screen's own string local, label Text get, UStrCat, Text set).
    for name, _, size, ship, form, temp in TAGS:
        site = next(s["address"] for s in info["sites"] if s["name"] == name)
        c = Code(at[name]); c.emit(b"\x8b\x45"+struct.pack("<b", ship)+b"\x80\xb8"); c.u32(RAILGUN_BYTE); c.emit(bytes([RAILGUN]))
        c.branch(b"\x0f\x85", "native")
        c.emit(b"\x8d\x95"+struct.pack("<i", temp)+b"\x8b\x45"+struct.pack("<b", form)+b"\x8b\x98"); c.u32(LABEL)
        c.emit(b"\x8b\xc3"); c.branch(b"\xe8", n["get_text"])
        c.emit(b"\x8d\x85"+struct.pack("<i", temp)+b"\xba"); c.u32(at["tag_text"]+12); c.branch(b"\xe8", n["str_cat"])
        c.emit(b"\x8b\x95"+struct.pack("<i", temp)+b"\x8b\xc3"); c.branch(b"\xe8", n["set_text"])
        c.mark("native"); c.emit(original[name]); c.branch(b"\xe9", site+size)
        code[name] = c.finish()

    # FireTorpedo, EBX new torpedo, ESI firer: forget this address, then remember it when the firer's nation
    # has guided torpedoes.
    ident, radius = tree.GUIDED_TORPEDOES
    c = Code(at["torpedo_launch"])
    c.emit(b"\x60\xb9"); c.u32(TORPEDO_SLOTS); c.emit(b"\xbf"); c.u32(at["torpedoes"])
    c.mark("forget"); c.emit(b"\x39\x1f"); c.branch(b"\x0f\x85", "kept"); c.emit(b"\xc7\x07\x00\x00\x00\x00")
    c.mark("kept"); c.emit(b"\x83\xc7\x04\x49"); c.branch(b"\x0f\x85", "forget")
    researched(c, n, b"\x8b\x56\x14", ident, "asked"); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "done")
    c.emit(b"\xa1"); c.u32(at["cursor"]); c.emit(b"\x89\x1c\x85"); c.u32(at["torpedoes"])
    if targets:   # undersea: the target (FireTorpedo's ECX, kept at [ebp-4]) for homing
        c.emit(b"\x8b\x55\xfc\x89\x14\x85"); c.u32(targets)
    c.emit(b"\x40\x25"); c.u32(TORPEDO_SLOTS-1); c.emit(b"\xa3"); c.u32(at["cursor"])
    c.mark("done"); c.emit(b"\x61"+bytes.fromhex(info["sites"][1]["original"])); c.branch(b"\xe9", n["launch_back"])
    code["torpedo_launch"] = c.finish()
    # Torpedo hit test, EBX torpedo: [ebp-18h] distance, [ebp-14h] native hit distance.
    c = Code(at["torpedo_hit"])
    if att:   # undersea: the ship's anti-torpedo torpedo may destroy it first (logged); the native exit as a wake hit
        c.branch(b"\xe8", att); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x85", n["torpedo_gone"])
    c.emit(b"\x51\x57\xb9"); c.u32(TORPEDO_SLOTS); c.emit(b"\xbf"); c.u32(at["torpedoes"])
    c.mark("scan"); c.emit(b"\x39\x1f"); c.branch(b"\x0f\x84", "guided"); c.emit(b"\x83\xc7\x04\x49"); c.branch(b"\x0f\x85", "scan")
    c.branch(b"\xe9", "native")
    c.mark("guided"); c.emit(b"\x52\x8b\x45\xec\x69\xc0"); c.u32(radius); c.emit(b"\xb9\x64\x00\x00\x00\x99\xf7\xf9\x89\x45\xec\x5a")
    c.mark("native"); c.emit(b"\x5f\x59\x8b\x45\xe8\x3b\x45\xec"); c.branch(b"\xe9", n["hit_back"])
    code["torpedo_hit"] = c.finish()

    # MoveMe, EBX missile, EAX native step: a hypersonic missile steps HYPER_SPEED times as far, but never past
    # its target: the step ends half a native step short, inside the hit window.
    c = Code(at["missile_step"])
    c.emit(b"\x8b\xf0"); c.branch(b"\xe8", is_hyper); c.branch(b"\x0f\x84", "native")
    c.emit(b"\x8b\x4b\x34\x85\xc9"); c.branch(b"\x0f\x84", "free")
    c.emit(b"\x8d\x53\x04\x8d\x81"); c.u32(0xA1C); c.branch(b"\xe8", n["distance"])        # target to missile
    c.emit(b"\x8b\xd6\xd1\xfa\x2b\xc2")                                                   # limit = distance - step/2
    c.emit(b"\x6b\xce"+bytes([HYPER_SPEED])+b"\x3b\xc8"); c.branch(b"\x0f\x8e", "step")
    c.emit(b"\x8b\xc8\x3b\xce"); c.branch(b"\x0f\x8d", "step"); c.emit(b"\x8b\xce")          # never below native
    c.mark("step"); c.emit(b"\x8b\xf1"); c.branch(b"\xe9", "native")
    c.mark("free"); c.emit(b"\x6b\xf6"+bytes([HYPER_SPEED]))
    c.mark("native"); c.emit(b"\x8d\x44\x24\x08"); c.branch(b"\xe9", n["step_back"])
    code["missile_step"] = c.finish()

    # GetSpotValue end, EBX ship, ESI spot: catapults add EMALS spot on ships laid down from the EMALS year; a
    # ski-jump flight deck without catapults adds the ski-jump spot.
    ident, year, tons, spot = tree.EMALS
    c = Code(at["spot"])
    c.emit(b"\x8b\xc3"); c.branch(b"\xe8", n["catapults"]); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x85", "catapults")
    ski_spot = tree.SKI_JUMP[1]
    c.emit(b"\x80\xbb"); c.u32(0x9D9); c.emit(b"\x00"); c.branch(b"\x0f\x84", "add")           # FlightDeck
    c.emit(b"\xf6\x83"); c.u32(0x9DF); c.emit(bytes([carrier.SKI_BIT])); c.branch(b"\x0f\x84", "add")   # ski jump
    c.emit(b"\xb8"); c.u32(ski_spot); c.branch(b"\xe9", "add")
    c.mark("catapults")
    c.emit(b"\x81\xbb"); c.u32(0xE4); c.u32(year); c.branch(b"\x0f\x8c", "add")               # BuildYear
    c.emit(b"\x50"); researched(c, n, b"\x8b\x53\x14", ident, "asked"); c.emit(b"\x84\xc0\x58"); c.branch(b"\x0f\x84", "add")
    c.emit(b"\x6b\xc0"+bytes([spot]))
    c.mark("add"); c.emit(b"\x03\xf0"); c.branch(b"\xe9", n["spot_back"])
    code["spot"] = c.finish()
    # Heavy jets on carriers, EAX carrier record: the steam-catapult minimum falls to EMALS tons (player research,
    # as the native check).
    c = Code(at["heavy_jets"])
    c.emit(b"\x60\xa1"); c.u32(n["main"]); c.emit(b"\x8b\x00\x8b\x80"); c.u32(0x3204)
    c.emit(b"\xba"); c.u32(ident); c.branch(b"\xe8", n["has_research"]); c.emit(b"\xa2"); c.u32(at["jets_flag"]); c.emit(b"\x61")
    c.emit(b"\x80\x3d"); c.u32(at["jets_flag"]); c.emit(b"\x00"); c.branch(b"\x0f\x85", "emals")
    c.emit(b"\x81\x78\x2b"); c.u32(30000); c.branch(b"\xe9", n["jets_back"])
    c.mark("emals"); c.emit(b"\x81\x78\x2b"); c.u32(tons); c.branch(b"\xe9", n["jets_back"])
    code["heavy_jets"] = c.finish()
    # Heavy jets without catapults (in place of CMP [carrier+0EFh],0 and its branch): a ski jump (TCampaignShip
    # +0F3h, the JetCapable copy, bit 1) passes on to the native angled-deck test. Air-group screen: EBX carrier.
    c = Code(at["jets_ui"])
    c.emit(b"\x83\xbb"); c.u32(0xEF); c.emit(b"\x00"); c.branch(b"\x0f\x85", n["jets_ok"])
    c.emit(b"\xf6\x83"); c.u32(0xF3); c.emit(bytes([carrier.SKI_BIT]))
    c.branch(b"\x0f\x85", n["jets_ok"]); c.branch(b"\xe9", n["jets_refused"])
    code["jets_ui"] = c.finish()
    c = Code(at["jets_unit"])   # air unit EDI, carrier ESI
    c.emit(b"\x83\xbe"); c.u32(0xEF); c.emit(b"\x00"); c.branch(b"\x0f\x8f", n["unit_angled"])
    c.emit(b"\xf6\x86"); c.u32(0xF3); c.emit(bytes([carrier.SKI_BIT]))
    c.branch(b"\x0f\x85", n["unit_angled"]); c.branch(b"\xe9", n["unit_refused"])
    code["jets_unit"] = c.finish()

    blocks = [dict(name="Modern combat: guided shell factor", address=at["factor"], bytes=struct.pack("<f", percent/100).hex()),
              dict(name="Modern combat: heavy guided shell factor", address=at["heavy_factor"],
                   bytes=struct.pack("<f", tree.HEAVY_GUIDED_SHELLS[1]/100).hex()),
              dict(name="Modern combat: torpedo record", address=at["jets_flag"], bytes="00"*(0xC+4*TORPEDO_SLOTS))]
    for name, text in (("own_text", "in railguns at "), ("seen_text", " railguns at "), ("tag_text", TAG)):
        data = struct.pack("<HHiI", 1200, 2, -1, len(text))+text.encode("utf-16-le")+b"\0\0"
        blocks.append(dict(name="Modern combat: "+text.strip(), address=at[name], bytes=data.hex()))
    plans = []
    room = dict(shells=0x100, torpedo_launch=0x100, log_own=0xC0, log_seen=0xC0, spot=0x100)
    for site in info["sites"]:
        body = code[site["name"]]
        if len(body) > room.get(site["name"], 0x80):
            raise ValueError("Modern combat code exceeds its reservation: "+site["name"])
        blocks.append(dict(name="Modern combat: "+site["name"], address=at[site["name"]], bytes=body.hex()))
        old = bytes.fromhex(site["original"])
        plans.append(patch("Modern combat: "+site["name"], site["address"], old,
                           b"\xe9"+struct.pack("<i", at[site["name"]]-site["address"]-5)+b"\x90"*(len(old)-5)))
    return blocks, plans
