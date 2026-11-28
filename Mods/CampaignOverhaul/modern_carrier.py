"""Ski-jump flight decks (a designer option) and VTOL light jet fighters, for the modern-research adapter.

Ski jump: a "Ski jump" checkbox under Flight deck in the designer's Flight installations. It needs Ski-jump
flight decks research (modern_tree.SKI_JUMP) and a flight deck. A ski jump is a jet deck (Invincible, Kuznetsov), so
ticking it also ticks Jet capable; unticking Jet capable removes it. It is stored in the JetCapable byte (Tship+0x9DF,
copied to TCampaignShip+0xF3): bit 0 jet capable, bit 1 ski jump. Every native consumer tests that byte for zero
(audited for build 1.01.44: rules, weights, the Yes/No texts, copies), so 3 reads as jet capable. Its five save and
load calls (design files, campaign ships) write and read it as an integer instead of a Boolean: 0/1 files are
byte-identical. modern_combat gives a ski-jump deck without catapults SKI_JUMP spot, and lets an angled ski-jump deck
fly heavy jets without catapults (STOBAR). STOBAR price: on a ski-jump deck without catapults heavy jets and jet
attack aircraft take 1.5 deck slots, as the game already charges them on carriers under 40,000 tons (the game keeps
no link from an air strike to its carrier, so the lighter take-off load itself is not modelled).
AI carriers: the AI designer makes a flight deck jet capable only from 30,000-40,000 tons; with the ski-jump research
its other carriers get a ski jump (jet capable, air capacity trimmed to the weight as the native jet path does), and
its jet decks without catapults get one too.

VTOL: with VTOL research (modern_tree.VTOL), a nation's light jet fighters (aircraft role 10) are VTOL (Harrier): a
carrier need not be jet capable for them, in the air-group screen (two refusals) and in deck space (the native 1.5
slots a light jet takes on a carrier that is not jet capable). The air unit's nation decides.
AV: an AV with a flight deck counts as a carrier for air operations (modern_navy's hybrid rule) and its air group may
hold light jet fighters besides its floatplane scouts when its deck is jet capable (the heat-proof deck) and the air
unit's nation has VTOL research. A refit adds the flight deck and Jet capable.
UAV request: the aircraft request dialog lists "UAV" under the roles once the player has Shipborne UAVs research and
can develop floatplane scouts. The request is kept as role 16 in the game's request byte (saved as an integer); the
role names read 16 as "UAV"; when it completes the game develops floatplane scouts and modern_sensors makes them UAV
models (modern_sensors.UAV_REQUEST). The player's other floatplane requests give floatplanes. UAV models (their
modern_sensors.UAV_MARK) read "UAV" in the aircraft lists and the prototype choice, as do the request's messages.
Special squadrons: a jet one (aircraft role 10-12) is an EW squadron (EA-6B, EA-18G), any other an AEW squadron (E-2,
Ka-31). The battle's "has a special squadron" checks ask for the kind they need: the radar and the three CAP vectoring
bonuses an AEW squadron, the enemy's jamming of CAP vectoring and the airborne ECM against SAMs an EW squadron; rescue
after battle any. A carrier carries one of each for both.
SEAD: SAMs firing at an air formation are less effective against a nation with modern_tree.SEAD research: jet strike
aircraft with anti-radiation missiles (then HARM), any aircraft with jamming pods; the battle log says so.
Fleet air defence fix (all eras, both sides): the game's nearest-enemy-air finder (NEAREST_AIR) tracked the closest
formation but never returned it, so every caller saw none: CAP never vectored onto raids (CAPIntercept), never moved
its station toward an approaching raid (AdjustCourseToTarget), carriers never scrambled CAP on enemy air nearing
radar range (the launch process) and IsCloseEnemyAir was always false. One in-place fix returns the formation.
Part of the modern-research adapter; imported lazily.
"""
import hashlib
import struct

import modern_tree as tree
from hull_rules import patch, dpi_scale_routine

BASE = 0x301000
SKI_BIT, JET_BITS = 2, 3            # JetCapable byte: bit 1 ski jump; ticking it sets jet capable too
LIGHT_JET = 10                      # aircraft role (Purpose, TAircraftType+0x81): Light jet fighter
MAGIC_SKI = 0x52474E3B              # Tag of the checkbox (unique among the designer boxes: modern_railgun's 31-3A)
SKI_BOUNDS = (24, 58, 90, 14)       # Flight installations group, under Flight deck (96 DPI)
GROUP_WIDTH = 313                    # the Flight installations group at 96 DPI: the display-scaling reference
NATION_ENTRY = 0x20                 # vtol routine: entry that skips the aircraft-type test
WINDOWS = (
    (0x82AA39, 0x55, "d5ac182c41b3dff2ede47958102f72ff956c2b209ff91ec21e7969a4903274bf"),   # deck space of jets
    (0x957950, 0x8B, "8b7d3727aa1b4257d13f5cd7e2e92ce034e477fce7f63985fc9dda26e6940698"),   # AI carrier jet decks
    (0x97D498, 0x45, "0310a821fd99ee7368bbeaa5fb927b4fc24ee10cea519a22c559ee186ca13ba2"),   # AV air group rule
    (0x628D2C, 0x55, "5384c0ecd53c82b1ef82087d3824883c26279ec6354613b07be630f010ac9603"),   # request dialog roles
    (0x6288C3, 0x60, "24579e7af5871ad337d955ad6a09b043505144db0ac64b5acf4297d0af93d4ec"),   # request dialog OK
    (0x970254, 0x16, "5d60aefe2444c1be1fb01528c91cb84b9af03e0790fa9875af12a11f2a595cb0"),   # role names
    (0x7EBF78, 0x14, "54a3713a8b67522277e46018e26785df4bf9f030d5ce830cc9e67d35b9a51f65"),   # request completion
    (0x631041, 0x40, "61a0817dfe4716859fb30fd91cde3f69b42f53b7bbe5cf2a4ad436e11dd61ed9"),   # jet refusal, unit picked
    (0x633F3D, 0x40, "11afa81cc5dbcf271d4335cb178c5d9f204687cf2ac4daea0dd9a43c3d75146f"),   # jet refusal, type picked
    (0x61988C, 0x0F, "c24a1f3abdb8aea58999f0caa0dcb03930c275fc5e78800b435f19cd15f2b424"),   # aircraft types list: role
    (0x62B92D, 0x0F, "86c3b77cc17d212df9a6b5556f6926ded5e3c81cab22b20ab1dbbc2821ddb87d"),   # role in the types dialog, prototype choice
    (0x7EB9F5, 0x0F, "513db1c2f4cb75ca78453187c2a66dc4ead5665cb7a115a158e9e6bde8ed6fbf"),   # request completion: prototypes ready
    (0x7EBBE4, 0x0F, "e658e99346b96aabf0a3e8ab951cb4f98e1e2458cce748079938ada6b8cc7ed5"),   # request completion: no prototype
    (0x7EB8E2, 0xEA, "4535b8263a4a6de2ecc0aa4b6bbe2c460d754d8a179c2a8e8e106046fb1d0d45"),   # request: the prototype loop
    (0x97D068, 0x20, "8b9c0bf8e427687f28a49ba514bed3d9c98b8ab21a02d8fa58e371baa27c942b"),   # SAMs against aircraft: the end
    (0x977788, 0x7F, "694d93e42719ceea820794b7531198dc6985c9ee2cd572b8b1ef060a12eae9b6"),   # nearest enemy air formation
)
# Native routines: designer (as modern_railgun), save/load helpers, research.
NATIVE = dict(has_research=0x729FA4, nation=0x750040, message=0x4D7124, recompute=0x9395F8, update=0x5CCB88,
              refresh=0x5E9D88, assign=0x30BCCC, set_text=0x451CA0, set_left=0x450EF0, set_top=0x450F24,
              set_width=0x450F5C, set_height=0x450F90, set_show_hint=0x451DCC, checkbox_vmt=0x46EF68,
              ini_bool_writer=0x845BB4, ini_int_writer=0x845C68, ini_bool_reader=0x846F2C, ini_int_reader=0x846B48,
              big_bool_writer=0x586DF0, big_int_writer=0x586EA4, big_bool_reader=0x58738C, big_int_reader=0x586FC8,
              space_back=0x82AA7E, space_ok=0x82AA8B, unit_back=0x631074, unit_ok=0x631097,
              type_back=0x633F6D, type_ok=0x633F8D, stobar_penalty=0x82AA4C, stobar_skip=0x82AA64,
              ai_back=0x9579DB, dec_min=0x587744, av_ok=0x97D4DD, av_refuse=0x97D4B7, add_role=0x628CAC,
              list_back=0x628D7D, can_develop=0x734BC8, role_from_name=0x9708B8, store_back=0x62891F,
              role_default=0x970388, role_jump=0x970263, complete=0x7EB810, air_units=0x9F7834, list_get=0x3B6D6C,
              special_min=0x97C9F8, has_special=0x91ABB8, battle_log=0xA80114, sam_air_back=0x97D07E,
              prototype_skip=0x7EB9C3, name_taken=0x7EB788, prototype_back=0x7EB917)
UAV_ROLE, SCOUT = 16, 3            # the request byte's UAV value; the floatplane scout role
REQUEST = 0x4AA8                   # main campaign object: the player's requested aircraft role (byte)
AI_JETS = 0x718                     # the native research the AI designer asks before making a deck jet capable
# JetCapable save and load calls: (name, call site, Boolean routine, integer routine).
KEYS = (("design_save", 0x93F7D4, "ini_bool_writer", "ini_int_writer"),
        ("design_load", 0x942855, "ini_bool_reader", "ini_int_reader"),
        ("design_load2", 0x8ED64D, "ini_bool_reader", "ini_int_reader"),
        ("ship_save", 0x8228FE, "big_bool_writer", "big_int_writer"),
        ("ship_load", 0x82488F, "big_bool_reader", "big_int_reader"))
# VTOL sites: cmp byte [carrier+0F3h],0 / jne ok (9 bytes); carrier and air unit registers (ModRM r/m codes).
SITES = (("space", 0x82AA75, 9), ("unit", 0x63106B, 9), ("type", 0x633F64, 9),
         ("stobar", 0x82AA43, 9), ("ai", 0x9579D4, 7),    # heavy jets' deck slots; AI designer after its jet block
         ("av_rule", 0x97D4B2, 5), ("request_list", 0x628D74, 9), ("request_role", 0x6288E0, 5),
         ("request_store", 0x628919, 6), ("role_name", 0x97025A, 9), ("request_done", 0x7EBF87, 5),
         ("types_role", 0x61988C, 7), ("item_role", 0x62B92D, 7), ("ready_role", 0x7EB9F5, 7), ("none_role", 0x7EBBE4, 7),
         ("sam_air", 0x97D077, 7), ("prototype_nil", 0x7EB90E, 9))
CALLS = ("request_role", "request_done", "types_role", "item_role", "ready_role", "none_role")   # call sites
# The battle's HasSpecialSquadron(EAX carrier) calls, by the squadron they need (the rescue call stays native).
AEW, EW = 1, 2
HAS_SPECIAL = 0xC40   # page offset of has_special(EAX carrier, ECX kind) -> AL (modern_air_defence's AEW check calls it)
SKI_WEIGHT = 0xF80    # page offset of ski_weight(EDX design) (modern_railgun's ammunition hook calls it)
SKI_PERCENT, SKI_MIN_TONS, SKI_COST_PER_TON = 15, 150, 10   # tenths of a percent of displacement; the armament rate
SPECIAL = ((0x91973A, AEW), (0x962EAE, AEW), (0x962EE8, AEW),   # radar; CAP vectoring x2
           (0x962FA9, EW), (0x97CF30, EW))                       # enemy ECM against CAP; against SAMs
# CAPIntercept's third AEW check only logs "AEW improves CAP vectoring", once per CAP intercept: with AEW on every
# carrier that was most of a battle's log (27,980 of 32,075 lines), so it now answers no and logs nothing.
AEW_LOG = 0x962F2B
SPECIAL_ROLE = 7   # a battle air unit's mission (+40h) when it is the carrier's special squadron
# NearestEnemyAir(EAX side, EDX fewest aircraft, ECX point): after "cmp edi,eax / jle" a closer formation (EBX) only
# recomputed the distance; it now keeps it (mov edi,eax) and becomes the result (mov [esp+4],ebx).
NEAREST_AIR = (0x9777E7, "8d532c8d442408e801bcbfff8bf8", "8bf8895c2404"+"90"*8)
FORM = dict(group=0x94C, nation=0xC63, ship2=0xC6B, editable=0xE67, design=0xE6C)   # TfrmDesignMain2 (RTTI)
VCL = dict(components=0x10, tag=0xC, hint=0x90, on_click=0x120, create=0x3C, set_parent=0xA0, set_enabled=0x9C,
           get_checked=0x16C, set_checked=0x170)
TEXT = dict(
    caption="Ski jump",
    hint=f"Ski-jump ramp: a jet deck that launches more aircraft without catapults. Weighs {SKI_PERCENT/10:g}% of "
         "displacement.",
    research="A ski jump needs research: Ski-jump flight decks (1974, Naval combat systems).",
    deck="A ski jump needs a flight deck.",
    uav="UAV",
    sead="2Anti-radiation missiles suppress SAMs",
    pods="2Jamming pods reduce SAM effectiveness")


def literal(text):
    return struct.pack("<HHiI", 1200, 2, -1, len(text))+text.encode("utf-16-le")+b"\0\0"


def discover(blob, base, normalized):
    for address, size, digest in WINDOWS:
        if hashlib.sha256(normalized[address-BASE:address-BASE+size]).hexdigest() != digest:
            raise ValueError("Ski jump refuses changed native code at "+hex(address)+".")
    delta = base-BASE
    info = {k: v+delta for k, v in NATIVE.items()}
    keys = []
    for name, site, old, new in KEYS:
        code = blob[site-BASE:site-BASE+5]
        if code[:1] != b"\xe8" or site+5+struct.unpack_from("<i", code, 1)[0] != NATIVE[old]:
            raise ValueError("Ski jump refuses changed native code: the JetCapable "+name+" call.")
        keys.append(dict(name=name, address=site+delta, original=code.hex(), target=NATIVE[new]+delta))
    info["keys"] = keys
    info["sites"] = [dict(name=name, address=address+delta, original=blob[address-BASE:address-BASE+size].hex())
                     for name, address, size in SITES]
    if blob[NEAREST_AIR[0]-BASE:NEAREST_AIR[0]-BASE+14].hex() != NEAREST_AIR[1]:
        raise ValueError("Ski jump refuses changed native code: the nearest enemy air formation.")
    info["nearest_air"] = NEAREST_AIR[0]+delta
    info["special"] = []
    for site, kind in SPECIAL+((AEW_LOG, None),):
        code = blob[site-BASE:site-BASE+5]
        if code[:1] != b"\xe8" or site+5+struct.unpack_from("<i", code, 1)[0] != NATIVE["has_special"]:
            raise ValueError("Ski jump refuses changed native code: a special squadron check.")
        info["special"].append(dict(address=site+delta, original=code.hex(), kind=kind))
    import modern_combat as combat   # campaign pointer, as the battle research lookups
    info["main"] = struct.unpack_from("<I", blob, combat.MAIN_LOAD-BASE+1)[0]
    return info


def build(page, info, uav_request=None, aew=None):
    """One page: designer routines, VTOL checks and texts. Returns (blocks, plans, sync): sync(EAX form) is called
    from the railgun designer sync (modern_railgun's refresh chain). aew: modern_air_defence's AEW check, which
    the battle's AEW squadron calls reach instead (it asks has_special, at page+HAS_SPECIAL, first)."""
    from campaign_security import Code
    n, F, V = info, FORM, VCL
    at = dict(sync=page, find=page+0x100, create=page+0x140, click=page+0x200, vtol=page+0x300, space=page+0x380,
              unit=page+0x3C0, type=page+0x400, stobar=page+0x440, ai=page+0x480, av_rule=page+0x540,
              request_list=page+0x580, request_role=page+0x600, request_store=page+0x640, role_name=page+0x6A0,
              request_done=page+0x6E0, types_role=page+0x720, item_role=page+0x728, role_of=page+0x730,
              ready_role=page+0x760, none_role=page+0x760, prototype_nil=page+0x780, texts=page+0x800, has_special=page+HAS_SPECIAL,
              has_aew=page+0xCE0, has_ew=page+0xCF0, sam_air=page+0xD00, ski_weight=page+SKI_WEIGHT, sead_last=page+0xFF8)
    texts, blocks, offset = {}, [], at["texts"]
    for key, text in TEXT.items():
        body = literal(text); texts[key] = offset+12
        blocks.append(dict(name="Ski jump text: "+key, address=offset, bytes=body.hex()))
        offset += (len(body)+15) & ~15
    if offset > at["has_special"]: raise ValueError("Ski jump texts exceed their room.")
    code = {}

    def call_slot(c, slot): c.emit(b"\x8b\x08\xff\x91"); c.u32(slot)   # mov ecx,[eax]; call [ecx+slot]

    # sync(EAX form): find or create the box, mirror the design without firing OnClick, enable it.
    c = Code(at["sync"])
    c.emit(b"\x53\x56\x57\x8b\xd8")                                       # push ebx/esi/edi; ebx = form
    c.emit(b"\x8b\xc3\xba"); c.u32(n["checkbox_vmt"]); c.emit(b"\xb9"); c.u32(MAGIC_SKI); c.branch(b"\xe8", at["find"])
    c.emit(b"\x85\xc0"); c.branch(b"\x0f\x85", "have_box")
    c.emit(b"\x8b\xc3"); c.branch(b"\xe8", at["create"])
    c.mark("have_box"); c.emit(b"\x8b\xf8")                               # edi = checkbox
    c.emit(b"\x8b\xb3"); c.u32(F["design"]); c.emit(b"\x85\xf6"); c.branch(b"\x0f\x84", "done")
    c.emit(b"\xf6\x86"); c.u32(0x9DF); c.emit(bytes([SKI_BIT])); c.emit(b"\x0f\x95\xc2\x52")   # setnz dl; push edx
    c.emit(b"\x8b\xc7"); call_slot(c, V["get_checked"]); c.emit(b"\x5a\x3a\xc2"); c.branch(b"\x0f\x84", "state_ok")
    c.emit(b"\xff\xb7"); c.u32(V["on_click"]); c.emit(b"\xc7\x87"); c.u32(V["on_click"]); c.u32(0)
    c.emit(b"\x8b\xc7"); call_slot(c, V["set_checked"])
    c.emit(b"\x8f\x87"); c.u32(V["on_click"])
    c.mark("state_ok")
    # Enabled: an editable design with a flight deck, and the research or a ski jump already fitted.
    c.emit(b"\x33\xd2\x80\xbb"); c.u32(F["editable"]); c.emit(b"\x00"); c.branch(b"\x0f\x84", "set_enabled")
    c.emit(b"\x80\xbe"); c.u32(0x9D9); c.emit(b"\x00"); c.branch(b"\x0f\x84", "set_enabled")
    c.emit(b"\xb2\x01\xf6\x86"); c.u32(0x9DF); c.emit(bytes([SKI_BIT])); c.branch(b"\x0f\x85", "set_enabled")
    c.emit(b"\x8b\x83"); c.u32(F["nation"]); c.emit(b"\xba"); c.u32(tree.SKI_JUMP[0]); c.branch(b"\xe8", n["has_research"])
    c.emit(b"\x8b\xd0")
    c.mark("set_enabled"); c.emit(b"\x8b\xc7"); call_slot(c, V["set_enabled"])
    c.mark("done"); c.emit(b"\x5f\x5e\x5b\xc3")
    code["sync"] = c.finish()

    # find(EAX form, EDX class, ECX tag) -> EAX component or 0 (the form's components).
    c = Code(at["find"])
    c.emit(b"\x53\x56\x8b\x40"); c.emit(bytes([V["components"]])); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "none")
    c.emit(b"\x8b\x70\x08\x8b\x40\x04")
    c.mark("next"); c.emit(b"\x4e"); c.branch(b"\x0f\x88", "none")
    c.emit(b"\x8b\x1c\xb0\x39\x13"); c.branch(b"\x0f\x85", "next")
    c.emit(b"\x39\x4b"); c.emit(bytes([V["tag"]])); c.branch(b"\x0f\x85", "next")
    c.emit(b"\x8b\xc3\x5e\x5b\xc3")
    c.mark("none"); c.emit(b"\x33\xc0\x5e\x5b\xc3")
    code["find"] = c.finish()

    # create(EAX form) -> EAX checkbox, in the Flight installations group.
    c = Code(at["create"])
    c.emit(b"\x53\x56\x8b\xd8\x8b\xcb\xb2\x01\xb8"); c.u32(n["checkbox_vmt"]); c.emit(b"\xff\x50"); c.emit(bytes([V["create"]]))
    c.emit(b"\x8b\xf0\xc7\x46"); c.emit(bytes([V["tag"]])); c.u32(MAGIC_SKI)
    c.emit(b"\x8b\x93"); c.u32(F["group"]); c.emit(b"\x8b\xc6"); call_slot(c, V["set_parent"])
    for setter, value in zip(("set_left", "set_top", "set_width", "set_height"), SKI_BOUNDS):
        c.emit(b"\xba"); c.u32(value); c.branch(b"\xe8", "scale"); c.emit(b"\x8b\xc6"); c.branch(b"\xe8", n[setter])
    c.emit(b"\x8d\x86"); c.u32(V["hint"]); c.emit(b"\xba"); c.u32(texts["hint"]); c.branch(b"\xe8", n["assign"])
    c.emit(b"\xb2\x01\x8b\xc6"); c.branch(b"\xe8", n["set_show_hint"])
    c.emit(b"\xba"); c.u32(texts["caption"]); c.emit(b"\x8b\xc6"); c.branch(b"\xe8", n["set_text"])
    c.emit(b"\xc7\x86"); c.u32(V["on_click"]); c.u32(at["click"]); c.emit(b"\x89\x9e"); c.u32(V["on_click"]+4)
    c.emit(b"\x8b\xc6\x5e\x5b\xc3")
    c.mark("scale"); c.emit(dpi_scale_routine(F["group"], GROUP_WIDTH))
    code["create"] = c.finish()

    # OnClick(EAX form, EDX checkbox): tick sets jet capable and ski jump on both designs, untick clears the ski jump.
    c = Code(at["click"])
    c.emit(b"\x60\x8b\xd8\x8b\xfa\x8b\xb3"); c.u32(F["design"]); c.emit(b"\x85\xf6"); c.branch(b"\x0f\x84", "resync")
    c.emit(b"\x80\xbb"); c.u32(F["editable"]); c.emit(b"\x00"); c.branch(b"\x0f\x84", "resync")
    c.emit(b"\x8b\xc7"); call_slot(c, V["get_checked"]); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "untick")
    c.emit(b"\xf6\x86"); c.u32(0x9DF); c.emit(bytes([SKI_BIT])); c.branch(b"\x0f\x85", "resync")   # already fitted
    c.emit(b"\x80\xbe"); c.u32(0x9D9); c.emit(b"\x00\xb8"); c.u32(texts["deck"]); c.branch(b"\x0f\x84", "refuse")
    c.emit(b"\x8b\x83"); c.u32(F["nation"]); c.emit(b"\xba"); c.u32(tree.SKI_JUMP[0]); c.branch(b"\xe8", n["has_research"])
    c.emit(b"\x84\xc0\xb8"); c.u32(texts["research"]); c.branch(b"\x0f\x84", "refuse")
    c.emit(b"\x80\x8e"); c.u32(0x9DF); c.emit(bytes([JET_BITS]))
    c.emit(b"\x8b\x8b"); c.u32(F["ship2"]); c.emit(b"\x85\xc9"); c.branch(b"\x0f\x84", "stored")
    c.emit(b"\x80\x89"); c.u32(0x9DF); c.emit(bytes([JET_BITS])); c.branch(b"\xe9", "stored")
    c.mark("untick"); c.emit(b"\x80\xa6"); c.u32(0x9DF); c.emit(bytes([0xFF ^ SKI_BIT]))
    c.emit(b"\x8b\x8b"); c.u32(F["ship2"]); c.emit(b"\x85\xc9"); c.branch(b"\x0f\x84", "stored")
    c.emit(b"\x80\xa1"); c.u32(0x9DF); c.emit(bytes([0xFF ^ SKI_BIT]))
    c.mark("stored"); c.emit(b"\x8b\xc6"); c.branch(b"\xe8", n["recompute"])
    c.emit(b"\x8b\xc3"); c.branch(b"\xe8", n["update"]); c.emit(b"\x8b\xc3"); c.branch(b"\xe8", n["refresh"])
    c.emit(b"\x61\xc3")
    c.mark("refuse"); c.emit(b"\x83\xca\xff\x83\xc9\xff"); c.branch(b"\xe8", n["message"])
    c.mark("resync"); c.emit(b"\x8b\xc3"); c.branch(b"\xe8", at["sync"]); c.emit(b"\x61\xc3")
    code["click"] = c.finish()

    # vtol(EAX air unit, EDX aircraft type) -> ZF clear when that type is a light jet fighter and the unit's nation
    # has VTOL research; vtol+NATION_ENTRY(EAX air unit) skips the type test. Keeps every register but EFLAGS.
    c = Code(at["vtol"])
    c.emit(b"\x50\x51\x52\x85\xd2"); c.branch(b"\x0f\x84", "no")
    c.emit(b"\x80\xba"); c.u32(0x81); c.emit(bytes([LIGHT_JET])); c.branch(b"\x0f\x85", "no")
    c.branch(b"\xe9", "nation")
    c.emit(b"\x90"*(NATION_ENTRY-len(c.data)))
    c.emit(b"\x50\x51\x52")                                                  # vtol+NATION_ENTRY
    c.mark("nation"); c.emit(b"\x8b\x50\x1c\xa1"); c.u32(n["main"]); c.emit(b"\x8b\x00"); c.branch(b"\xe8", n["nation"])
    c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "no")
    c.emit(b"\xba"); c.u32(tree.VTOL); c.branch(b"\xe8", n["has_research"])
    c.emit(b"\x84\xc0\x5a\x59\x58\xc3")
    c.mark("no"); c.emit(b"\x33\xc0\x5a\x59\x58\xc3")                       # ZF set
    code["vtol"] = c.finish()

    # The three native tests of a carrier's JetCapable: carrier register, air unit register, its type or None.
    def vtol_site(name, carrier, unit, type_of, ok, back):
        c = Code(at[name])
        c.emit(bytes([0x80, 0xB8 | carrier])); c.u32(0xF3); c.emit(b"\x00"); c.branch(b"\x0f\x85", ok)   # cmp byte [r+0F3h],0
        c.emit(b"\x50\x52"+bytes([0x8B, 0xC0 | unit]))                        # push eax/edx; mov eax, unit
        if type_of: c.emit(type_of); c.branch(b"\xe8", at["vtol"])            # edx = its aircraft type
        else: c.branch(b"\xe8", at["vtol"]+NATION_ENTRY)
        c.emit(b"\x5a\x58"); c.branch(b"\x0f\x85", ok); c.branch(b"\xe9", back)
        code[name] = c.finish()
    ESI, EDI, EBX = 6, 7, 3
    vtol_site("space", ESI, EBX, None, n["space_ok"], n["space_back"])          # EBX unit (role 10 tested), ESI carrier
    vtol_site("unit", ESI, EDI, b"\x8b\x57\x0c", n["unit_ok"], n["unit_back"])     # EDI unit, ESI carrier
    vtol_site("type", EDI, ESI, b"\x8b\x56\x0c", n["type_ok"], n["type_back"])     # ESI unit, EDI carrier
    # Deck space of heavy jets and jet attack (ESI carrier): 1.5 slots under 40,000 tons, or on a ski-jump deck
    # without catapults (in place of CMP [ESI+2Bh],9C40h / JGE).
    c = Code(at["stobar"])
    c.emit(b"\x81\x7e\x2b"); c.u32(40000); c.branch(b"\x0f\x8c", n["stobar_penalty"])
    c.emit(b"\xf6\x86"); c.u32(0xF3); c.emit(bytes([SKI_BIT])); c.branch(b"\x0f\x84", n["stobar_skip"])
    c.emit(b"\x83\xbe"); c.u32(0xEF); c.emit(b"\x00"); c.branch(b"\x0f\x85", n["stobar_skip"])
    c.branch(b"\xe9", n["stobar_penalty"])
    code["stobar"] = c.finish()
    # AI designer, after its jet decision ([EDI] design, [EBP-0Ch] nation): with the ski-jump research a flight deck
    # gets a ski jump, jet capable too when it was not (and the jets research is there), trimming air capacity until
    # the weight fits as the native jet path does (13 tries).
    c = Code(at["ai"])
    c.emit(b"\x60\x8b\x37\x80\xbe"); c.u32(0x9D9); c.emit(b"\x00"); c.branch(b"\x0f\x84", "done")
    c.emit(b"\x8b\x45\xf4\xba"); c.u32(tree.SKI_JUMP[0]); c.branch(b"\xe8", n["has_research"])
    c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "done")
    c.emit(b"\xf6\x86"); c.u32(0x9DF); c.emit(b"\x01"); c.branch(b"\x0f\x85", "jet")
    c.emit(b"\x8b\x45\xf4\xba"); c.u32(AI_JETS); c.branch(b"\xe8", n["has_research"])
    c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "done")
    c.emit(b"\x80\x8e"); c.u32(0x9DF); c.emit(bytes([JET_BITS])); c.emit(b"\x8b\xc6"); c.branch(b"\xe8", n["recompute"])
    c.emit(b"\xbb\x0d\x00\x00\x00")
    c.mark("trim"); c.emit(b"\x83\xbe"); c.u32(0xB20); c.emit(b"\x00"); c.branch(b"\x0f\x8d", "next")   # weight left
    c.emit(b"\x8d\x86"); c.u32(0x9E0); c.emit(b"\x33\xc9\xba\x01\x00\x00\x00"); c.branch(b"\xe8", n["dec_min"])
    c.emit(b"\x8b\xc6"); c.branch(b"\xe8", n["recompute"])
    c.mark("next"); c.emit(b"\x4b"); c.branch(b"\x0f\x85", "trim"); c.branch(b"\xe9", "done")
    c.mark("jet"); c.emit(b"\x83\xbe"); c.u32(0x9DB); c.emit(b"\x00"); c.branch(b"\x0f\x85", "done")   # catapults
    c.emit(b"\x80\x8e"); c.u32(0x9DF); c.emit(bytes([SKI_BIT]))
    c.mark("done"); c.emit(b"\x61\xc7\x45\xd0\x10\x00\x00\x00"); c.branch(b"\xe9", n["ai_back"])
    code["ai"] = c.finish()
    # AV air group (EAX its TCampaignShip, EDI air unit, BL role): floatplane scouts as before, and light jet fighters
    # of a VTOL nation when the deck is jet capable (in place of CMP BL,3 / JE).
    c = Code(at["av_rule"])
    c.emit(b"\x80\xfb"+bytes([SCOUT])); c.branch(b"\x0f\x84", n["av_ok"])
    c.emit(b"\x80\xfb"+bytes([LIGHT_JET])); c.branch(b"\x0f\x85", n["av_refuse"])
    c.emit(b"\x80\xb8"); c.u32(0xF3); c.emit(b"\x00"); c.branch(b"\x0f\x84", n["av_refuse"])
    c.emit(b"\x50\x8b\xc7"); c.branch(b"\xe8", at["vtol"]+NATION_ENTRY); c.emit(b"\x58")
    c.branch(b"\x0f\x85", n["av_ok"]); c.branch(b"\xe9", n["av_refuse"])
    code["av_rule"] = c.finish()

    def uav_text(c, register, other):   # ZF set when the UnicodeString in register reads "UAV"
        c.emit(bytes([0x85, 0xC0 | register << 3 | register])); c.branch(b"\x0f\x84", other)
        c.emit(bytes([0x83, 0x78 | register, 0xFC, 3])); c.branch(b"\x0f\x85", other)
        c.emit(bytes([0x81, 0x38 | register])); c.u32(0x00410055); c.branch(b"\x0f\x85", other)
        c.emit(bytes([0x66, 0x83, 0x78 | register, 4, 0x56]))
    # Request dialog roles (in the fill routine's frame, [EBP-4] the dialog): the native last role, then "UAV".
    c = Code(at["request_list"])
    c.emit(b"\x55\xb0\x0d"); c.branch(b"\xe8", n["add_role"]); c.emit(b"\x59")
    c.emit(b"\xa1"); c.u32(n["main"]); c.emit(b"\x8b\x00\x8b\x80"); c.u32(0x3204)
    c.emit(b"\x50\xba"); c.u32(SCOUT); c.branch(b"\xe8", n["can_develop"]); c.emit(b"\x84\xc0\x58"); c.branch(b"\x0f\x84", "back")
    c.emit(b"\xba"); c.u32(tree.UAVS); c.branch(b"\xe8", n["has_research"]); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "back")
    c.emit(b"\x8b\x45\xfc\x8b\x80"); c.u32(0x448); c.emit(b"\x8b\x80"); c.u32(0x2D8)
    c.emit(b"\xba"); c.u32(texts["uav"]); c.emit(b"\x8b\x08\xff\x51\x3c")             # Items.Add
    c.mark("back"); c.branch(b"\xe9", n["list_back"])
    code["request_list"] = c.finish()
    # RoleFromName(EAX text): "UAV" is the floatplane scout role for the dialog's checks.
    c = Code(at["request_role"]); uav_text(c, 0, "native"); c.branch(b"\x0f\x85", "native")
    c.emit(b"\xb8"); c.u32(SCOUT); c.emit(b"\xc3")
    c.mark("native"); c.branch(b"\xe9", n["role_from_name"])
    code["request_role"] = c.finish()
    # The dialog stores the request (EAX main, BL role, [EBP-4] the chosen text): a UAV is kept as UAV_ROLE.
    c = Code(at["request_store"]); c.emit(b"\x51\x8b\x4d\xfc"); uav_text(c, 1, "plain"); c.branch(b"\x0f\x85", "plain")
    c.emit(b"\xc6\x80"); c.u32(REQUEST); c.emit(bytes([UAV_ROLE])); c.branch(b"\xe9", "stored")
    c.mark("plain"); c.emit(b"\x88\x98"); c.u32(REQUEST)
    c.mark("stored"); c.emit(b"\x59"); c.branch(b"\xe9", n["store_back"])
    code["request_store"] = c.finish()
    # Role names (EAX role, EBX the destination string): UAV_ROLE reads "UAV" (the pending request, its messages).
    c = Code(at["role_name"]); c.emit(b"\x83\xf8"+bytes([UAV_ROLE])); c.branch(b"\x0f\x85", "native")
    c.emit(b"\x8b\xc3\xba"); c.u32(texts["uav"]); c.branch(b"\xe8", n["assign"]); c.emit(b"\x5b\xc3")
    c.mark("native"); c.emit(b"\x83\xf8\x0f"); c.branch(b"\x0f\x87", n["role_default"]); c.branch(b"\xe9", n["role_jump"])
    code["role_name"] = c.finish()
    # Request completion (EAX main): a UAV request develops a floatplane scout that modern_sensors makes a UAV model.
    c = Code(at["request_done"])
    c.emit(b"\x80\xb8"); c.u32(REQUEST); c.emit(bytes([UAV_ROLE])); c.branch(b"\x0f\x85", "native")
    if uav_request is None: raise ValueError("Ski jump needs modern_sensors' UAV request flag.")
    c.emit(b"\xc6\x80"); c.u32(REQUEST); c.emit(bytes([SCOUT])); c.emit(b"\xc6\x05"); c.u32(uav_request); c.emit(b"\x01")
    c.branch(b"\xe8", n["complete"]); c.emit(b"\xc6\x05"); c.u32(uav_request); c.emit(b"\x00\xc3")
    c.mark("native"); c.branch(b"\xe9", n["complete"])
    code["request_done"] = c.finish()
    # Shown roles, in place of MOVZX EAX,BYTE [reg+81h] (an aircraft type's role) before the role names: a UAV model
    # reads UAV_ROLE. The completion's two messages (MOVZX EAX,BYTE [ESI+4AA8h]) read it while a UAV request completes.
    import modern_sensors as sensors
    import modern_combat as combat   # battle research lookups by nation index
    c = Code(at["types_role"]); c.emit(b"\x8b\xc6"); c.branch(b"\xe9", at["role_of"]); code["types_role"] = c.finish()
    c = Code(at["item_role"]); c.emit(b"\x8b\xc3"); c.branch(b"\xe9", at["role_of"]); code["item_role"] = c.finish()
    c = Code(at["role_of"])   # EAX aircraft type -> EAX shown role
    c.emit(b"\x80\xb8"); c.u32(0x81); c.emit(bytes([SCOUT])); c.branch(b"\x0f\x85", "plain")
    c.emit(b"\x83\x78"+bytes([sensors.MARK, sensors.UAV_MARK])); c.branch(b"\x0f\x85", "plain")
    c.emit(b"\xb8"); c.u32(UAV_ROLE); c.emit(b"\xc3")
    c.mark("plain"); c.emit(b"\x0f\xb6\x80"); c.u32(0x81); c.emit(b"\xc3")
    code["role_of"] = c.finish()
    # has_special(EAX carrier, ECX AEW or EW) -> AL: HasSpecialSquadron (battle) for that kind: a special squadron of
    # the carrier with its native minimum of aircraft, flying jets for EW, anything else for AEW.
    c = Code(at["has_special"]); c.emit(b"\x53\x56\x57\x55\x8b\xe8\x8b\xf9\xa1"); c.u32(n["air_units"])
    c.emit(b"\x8b\x00\x8b\x70\x08")
    c.mark("next"); c.emit(b"\x4e"); c.branch(b"\x0f\x88", "none")
    c.emit(b"\xa1"); c.u32(n["air_units"]); c.emit(b"\x8b\x00\x8b\xd6"); c.branch(b"\xe8", n["list_get"]); c.emit(b"\x8b\xd8")
    c.emit(b"\x3b\x6b\x4d"); c.branch(b"\x0f\x85", "next")
    c.emit(b"\x80\x7b\x40"+bytes([SPECIAL_ROLE])); c.branch(b"\x0f\x85", "next")
    c.emit(b"\x33\xc9\x8b\x43\x10\x85\xc0"); c.branch(b"\x0f\x84", "kind")       # its aircraft model
    c.emit(b"\x0f\xb6\x80"); c.u32(0x81); c.emit(b"\x83\xe8"+bytes([LIGHT_JET])+b"\x83\xf8\x03\x0f\x92\xc1")   # jet: CL 1
    c.mark("kind"); c.emit(b"\x8d\x41\x01\x3b\xc7"); c.branch(b"\x0f\x85", "next")
    c.emit(b"\x8b\x85"); c.u32(0x9E0); c.branch(b"\xe8", n["special_min"]); c.emit(b"\x3b\x43\x18"); c.branch(b"\x0f\x8f", "next")
    c.emit(b"\xb0\x01"); c.branch(b"\xe9", "out")
    c.mark("none"); c.emit(b"\x33\xc0")
    c.mark("out"); c.emit(b"\x5d\x5f\x5e\x5b\xc3")
    code["has_special"] = c.finish()
    for name, kind in (("has_aew", AEW), ("has_ew", EW)):
        c = Code(at[name])
        if name == "has_aew" and aew: c.branch(b"\xe9", aew)
        else: c.emit(b"\xb9"); c.u32(kind); c.branch(b"\xe9", at["has_special"])
        code[name] = c.finish()
    # SAMs against an air formation, at the end of their effectiveness (EBX, ESI the ship, [EBP-8] the formation):
    # SEAD research of the formation's nation cuts it, each research its percent. The log notes ARMs and pods once
    # per formation (each SAM salvo used to log them, ARMs twice with both researches: over a thousand lines a battle).
    c = Code(at["sam_air"]); c.emit(b"\x57\x33\xff")                                       # EDI: 1 ARMs, 2 pods
    for index, (ident, cut, jets) in enumerate(tree.SEAD):
        if jets:
            c.emit(b"\x8b\x45\xf8\x8b\x40\x10\x85\xc0"); c.branch(b"\x0f\x84", f"skip{index}")
            c.emit(b"\x0f\xb6\x80"); c.u32(0x81); c.emit(b"\x83\xe8"+bytes([LIGHT_JET])+b"\x83\xf8\x02"); c.branch(b"\x0f\x87", f"skip{index}")
        combat.researched(c, n, b"\x8b\x55\xf8\x8b\x52\x38", ident, f"asked{index}")
        c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", f"skip{index}")
        c.emit(b"\x6b\xdb"+bytes([100-cut])+b"\x8b\xc3\x99\xb9\x64\x00\x00\x00\xf7\xf9\x8b\xd8")
        c.emit(b"\x83\xcf"+bytes([1 if jets else 2]))
        c.mark(f"skip{index}")
    c.emit(b"\x8b\x45\xf8\x3b\x05"); c.u32(at["sead_last"]); c.branch(b"\x0f\x84", "noted")
    c.emit(b"\xa3"); c.u32(at["sead_last"]); c.emit(b"\x57")
    for bit, key in ((1, "sead"), (2, "pods")):
        c.emit(b"\xf6\x04\x24"+bytes([bit])); c.branch(b"\x0f\x84", f"quiet{bit}")
        c.emit(b"\x8b\xce\xba"); c.u32(texts[key]); c.emit(b"\xa1"); c.u32(n["battle_log"]); c.emit(b"\x8b\x38\xff\x57\x40")
        c.mark(f"quiet{bit}")
    c.emit(b"\x83\xc4\x04")
    c.mark("noted"); c.emit(b"\x5f"+bytes.fromhex(next(s["original"] for s in n["sites"] if s["name"] == "sam_air")))
    c.branch(b"\xe9", n["sam_air_back"])
    code["sam_air"] = c.finish()
    # ski_weight(EDX design): a ski jump weighs SKI_PERCENT tenths of a percent of the displacement (at least
    # SKI_MIN_TONS), counted with the armament at SKI_COST_PER_TON. Keeps every register.
    c = Code(at["ski_weight"]); c.emit(b"\x60\xf6\x82"); c.u32(0x9DF); c.emit(bytes([SKI_BIT])); c.branch(b"\x0f\x84", "done")
    c.emit(b"\x8b\x42\x2c\x6b\xc0"+bytes([SKI_PERCENT])+b"\x8b\xda\x99\xb9\xe8\x03\x00\x00\xf7\xf9\x3d"); c.u32(SKI_MIN_TONS)
    c.branch(b"\x0f\x8d", "tons"); c.emit(b"\xb8"); c.u32(SKI_MIN_TONS)
    c.mark("tons"); c.emit(b"\x01\x83"); c.u32(0xAA4); c.emit(b"\x6b\xc0"+bytes([SKI_COST_PER_TON])+b"\x01\x83"); c.u32(0xA8C)
    c.mark("done"); c.emit(b"\x61\xc3")
    code["ski_weight"] = c.finish()
    c = Code(at["ready_role"])   # ESI main
    c.emit(b"\x0f\xb6\x86"); c.u32(REQUEST); c.emit(b"\x80\x3d"); c.u32(uav_request); c.emit(b"\x00")
    c.branch(b"\x0f\x84", "ret"); c.emit(b"\xb8"); c.u32(UAV_ROLE)
    c.mark("ret"); c.emit(b"\xc3")
    code["ready_role"] = c.finish()
    # ResolveAircraftRequest after each CreateAircraftPrototype (EBX, in place of PUSH EBP / MOV EAX,[EBX+4] / CALL
    # the name check): a prototype whose aircraft data did not load is nil; it is skipped as the game skips the
    # prototypes it discards, instead of crashing the turn ("Read of address 00000004").
    c = Code(at["prototype_nil"]); c.emit(b"\x85\xdb"); c.branch(b"\x0f\x84", n["prototype_skip"])
    c.emit(b"\x55\x8b\x43\x04"); c.branch(b"\xe8", n["name_taken"]); c.branch(b"\xe9", n["prototype_back"])
    code["prototype_nil"] = c.finish()
    for name, body in code.items():
        end = min([a for a in at.values() if a > at[name]], default=page+0x1000)
        if at[name]+len(body) > end: raise ValueError("Ski jump code overlaps: "+name)

    for name, body in code.items():
        blocks.append(dict(name="Ski jump: "+name, address=at[name], bytes=body.hex()))
    blocks.append(dict(name="Ski jump: sead_last", address=at["sead_last"], bytes="00000000"))
    plans = [patch("Ski jump: JetCapable "+key["name"], key["address"], bytes.fromhex(key["original"]),
                   b"\xe8"+struct.pack("<i", key["target"]-key["address"]-5)) for key in n["keys"]]
    plans.append(patch("Ski jump: nearest enemy air formation returned", n["nearest_air"], bytes.fromhex(NEAREST_AIR[1]),
                       bytes.fromhex(NEAREST_AIR[2])))
    for site in n["special"]:
        if site["kind"] is None:   # AEW_LOG: XOR EAX,EAX in place of the call, so the log is skipped
            plans.append(patch("Ski jump: no AEW vectoring log", site["address"], bytes.fromhex(site["original"]),
                               b"\x33\xc0"+b"\x90"*3))
            continue
        target = at["has_aew" if site["kind"] == AEW else "has_ew"]
        plans.append(patch("Ski jump: special squadron "+("AEW" if site["kind"] == AEW else "EW"), site["address"],
                           bytes.fromhex(site["original"]), b"\xe8"+struct.pack("<i", target-site["address"]-5)))
    for site in n["sites"]:
        old = bytes.fromhex(site["original"])
        label = "Ski jump: "+("VTOL " if site["name"] in ("space", "unit", "type") else "")+site["name"]
        opcode = b"\xe8" if site["name"] in CALLS else b"\xe9"
        plans.append(patch(label, site["address"], old,
                           opcode+struct.pack("<i", at[site["name"]]-site["address"]-5)+b"\x90"*(len(old)-5)))
    return blocks, plans, at["sync"]
