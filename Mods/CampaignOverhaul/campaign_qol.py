"""Specific prompt automation and bounded AI procurement, title-screen install."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import time
import weekly_runtime as rt
import modern_research as audit
from campaign_security import Code
from hull_rules import patch

REPORT = Path(__file__).with_name("campaign_qol_report.json")
DEFAULTS = dict(max_active_ships=400, max_building_ships=24, min_procurement_days=28, invade_possessions=1)
# Player invasions (both invasion buttons): any possession may be invaded except a nation's main home region, and
# home areas no longer need the invading nation to be blockaded. Natively possessions worth 10 or more (every home
# region and the big colonies) were closed. Main home regions, by possession name in the native map files:
HOMELANDS = ("United Kingdom", "Germany", "Western France", "Northwestern Spain", "Italian West Coast", "Austria-Hungary",
             "Japan", "Western Russia", "Eastern USA", "Northern China", "Turkey", "Argentina", "Brazil", "Persia",
             "India", "Java", "South Afriica")   # the last three are home areas only in the superstate start
DOCK_LIMIT = 200000                               # largest dock the Build button reaches (native 90,000)
HOME_VALUE = 200                                  # a home area's Value; a homeland worth less is ordinary land
INVASION = (dict(site=0x6E6327, ok=0x6E6342, end=0x6E63E9, blockade=0x6E6351),    # bnInvasionClick
            dict(site=0x6F6148, ok=0x6F6163, end=0x6F6228, blockade=0x6F6172))    # bnInvasionTargetClick
HOMELAND_TEXT = "A nation's main home area cannot be invaded. Its other regions and possessions can."
# The invasion range routine also gives possessions worth more than 10 no range. Only for the two player buttons
# (by return address) it now applies the main home region rule; the AI's invasion planning keeps the native rule.
INVASION_RANGE = dict(site=0x7F2DC4, ok=0x7F2DDF, zero=0x7F2DCD, players=(0x6E62E6, 0x6F61B5))
# Colonising and big targets. Possession details enables "Set invasion target" natively only for owned
# possessions worth 15 or less; the turn processing re-checks the player's target each turn (its owner's
# relation, then worth over 15 clears it) and lands with a weather roll, the blockade rule, force and margin
# rolls, or schedules an invasion battle against the owner. Neutral targets (no owner, which those checks and
# the battle would read) take the weather and blockade rules, the native minimum force and any enemy fleets
# in the area, then land; landing on a neutral possession makes it the player's (owner pointer, and the owner
# name that SetPossessionOwners resolves on load). Big owned targets stay open unless a main homeland.
# Invasion code in the 0x3000-byte allocation: (offset, room). The name checks compare against all the main
# homelands, so each needs more than 0x100 bytes.
INVASION_CODE = dict(ui=(0x2000, 0x200), turn=(0x2200, 0x300), success=(0x1580, 0x80), range=(0x1600, 0x200),
                     invasions=((0x1800, 0x200), (0x1A00, 0x200)), literals=(0x2500, 0x800))
COLONY = dict(ui=0x7B9B78, ui_set=0x7B9B96, turn=0x7C95B1, proceed=0x7C95D8, skip=0x7C98D9, weather=0x7C87C4,
              weather_delay=0x7C95E3, blockade_delay=0x7C9667, force_delay=0x7C986B, landed=0x7C9786,
              blockade=0x8203B8, strength=0x7326CC, success=0x7C97D5, success_native=0x7C97DC, success_done=0x7C97E2)
# Designer mouse wheel: FormShow installs a form OnMouseWheel handler that steps the box under the
# mouse pointer (Vcl.Controls.FindVCLWindow), whatever has the focus: a TSpinEdit by its Increment through
# its own SetValue, a TSpinButton through its own click events, an armour list (TComboBox whose OnChange
# is cbBChange) by one item and its OnChange. Range clamps and change handlers run natively. Published
# field offsets and ItemIndex accessor slots are confirmed in the game's RTTI, the classes by name;
# TStrings.GetCount is VMT slot 14h (native Items.Count calls) and TComponent.FOwner +4 (Name is +8).
WHEEL = dict(form_show=0x5cd03c, spin_vmt=0x58f214, get_value=0x590c6c, set_value=0x590cc4, find_window=0x44fa44,
             combo_vmt=0x46bb60, button_vmt=0x58e93c)
WHEEL_FIELDS = dict(on_mouse_wheel=0x150, increment=0x310, owner=4, combo_change=0x2e0, combo_items=0x304,
                    up_click=0x2d8, down_click=0x2e0, get_index=0x16c, set_index=0x170, count_slot=0x14)
PICTURE = dict(globe=0x7cc, rotate_button=0x350, middle=2)   # TMouseZoomButton: mzbLeft, mzbRight, mzbMiddle, mzbNone


def published(blob, name):
    """Field offsets read directly by published properties called `name` (GetProc $FFxxxxxx)."""
    needle = bytes([len(name)])+name.encode()
    getters = [struct.unpack_from("<I", blob, m.start()-22)[0] for m in re.finditer(re.escape(needle), blob)]
    return {get & 0xFFFFFF for get in getters if get >> 24 == 0xFF}


def discover(blob, base, settings=None):
    import live_cheats as live
    values = dict(DEFAULTS, **(settings or {}))
    limits = dict(max_active_ships=(50,10000), max_building_ships=(1,1000), min_procurement_days=(1,90), invade_possessions=(0,1))
    if values.keys() != DEFAULTS.keys() or any(type(v) is not int or not limits[k][0] <= v <= limits[k][1] for k,v in values.items()):
        raise ValueError("Unsupported AI procurement limits.")
    normal = audit.normalize(blob, base)
    delta = base-0x301000
    windows = ((0x97ba3c,97,"2bd02a7e3e8b8ddbcda4b7f8d6dfcf63c82815eb50f1279cd214b197ea1fce99"),
               (0x78063c,124,"7c8acf3d6b4ebad37444a10b89bca2e7d5a77bd914a8c10082299759f026d09d"),
               (0x7b694c,147,"4238c36f79ba031e64e1c424a997815f8f852270ebbe48ba9d60f7ec2c3a607b"),
               (0x4d86c0,46,"201574693b0123d66640adcd17043685c5c94009d727ae52fb34861430a406f4"),
               (0x5cd03c,20,"863884e32ebbdcf4af1ef30c12fabd6b0819acc4f5bcf39f2f329e68c8ade544"),   # designer FormShow
               (0x44fa44,58,"5f0d6a27f2c458326e9ffc5eba904bbd0d08ec6b33e1676e090d01a6b33f3937"),   # FindVCLWindow
               (0x6e6327,44,"8b950e0fb87d8507e5c452f052789fdd5085208122afbc9fa39436235c199955"),   # invasion checks
               (0x6f6148,44,"35e52b129092e0980478c2cf2d4538d03e9b4b79c9f6eb493cf781717b728caf"),
               (0x7f2dc4,27,"f87ecc09d8a24a349059072b9837dd076741f52b974c076c41d66dcfebc7c0a1"),   # invasion range
               (0x7b9b6d,41,"9d77a1ed0e2252be2464055d00cdee15735d030d6d95d355b125dcb23d08c5bf"),   # invasion target button
               (0x7c95a3,605,"1b92b54fa001e9eefa51a29a455a1f34e34aedb88d3f7f819ce4c7cc21af1770"),  # turn-time invasion
               (0x7c87c4,94,"78b4a279bd6abf3cc750c1eb6e0e9bb702b67a5bca86def15a00d5ea4e22d122"),   # invasion weather
               (0x8203b8,101,"98d2d969340b1150ab8eb3b5b83a96402c4707aca4d87b6c9d63cbac3ac83eec"),  # blockade rule
               (0x7326cc,61,"239dec07547803219970b3bcc273a38edae9fd04d574e3f7ae0cb7735661ae6e"))   # fleet strength
    for reference,size,digest in windows:
        at = reference-0x301000
        if hashlib.sha256(normal[at:at+size]).hexdigest() != digest:
            raise ValueError("Prompt automation refuses changed native code.")
    # This one MessageDlg has one help-context stack argument and compares its
    # answer with mrYes=6. Replay the exact mrNo=7 outcome and caller cleanup.
    strike = 0x97ba8d+delta
    plans = [patch("Keep current strike target without the confirmation", strike,
                   blob[strike-base:strike-base+8], bytes.fromhex("586a075883f80690"))]
    dock = 0x72b26e+delta            # BuildDock: cmp [nation dock size], 90000 / jl build
    if blob[dock-base:dock-base+12].hex() != "81be1d010000905f01007c1d": raise ValueError("Unsupported native dock size limit.")
    plans.append(patch("Docks can be built up to 200,000 tons", dock, blob[dock-base:dock-base+10],
                       blob[dock-base:dock-base+6]+struct.pack("<I", DOCK_LIMIT)))
    layout = live.discover(blob, base)
    build, monthly = (rt.method_address(blob, base, n) for n in ("AIBuildShip", "AIMonthlyBuild"))
    initial, initial_end = (rt.method_address(blob, base, n) for n in ("AIBuildInitialShips", "GetFileExtensionForNation"))
    if not 0 < initial_end-initial < 0x10000:
        raise ValueError("Unsupported initial fleet routine boundaries.")
    if blob[build-base:build-base+5].hex() != "558bec6a00" or blob[monthly-base:monthly-base+8].hex() != "558becb916000000":
        raise ValueError("Unsupported AI procurement entry contract.")
    update = rt.method_address(blob, base, "UpdateBudgetNumbers")-base
    clocks = [struct.unpack("<I", m[2])[0] for m in re.finditer(
        rb"\xff\x35(.{4})\xff\x35(.{4})\x8d\x4d", blob[update:update+0x100], re.DOTALL)
        if struct.unpack("<I",m[1])[0] == struct.unpack("<I",m[2])[0]+4]
    if len(clocks) != 1: raise ValueError("Cannot verify the native campaign date for procurement.")
    wheel = {k: v+delta for k, v in WHEEL.items()}
    def class_name(vmt):
        at = struct.unpack_from("<I", blob, vmt-0x38-base)[0]-base   # vmtClassName
        return blob[at+1:at+1+blob[at]]
    value = [m.start() for m in re.finditer(re.escape(b"\x05Value"), blob)
             if struct.unpack_from("<II", blob, m.start()-22) == (wheel["get_value"], wheel["set_value"])]
    index = [m.start() for m in re.finditer(re.escape(b"\x09ItemIndex"), blob)
             if struct.unpack_from("<II", blob, m.start()-22) == (0xFE000000 | WHEEL_FIELDS["get_index"],
                                                                 0xFE000000 | WHEEL_FIELDS["set_index"])]
    count = re.escape(b"\x8b\x80"+struct.pack("<I", WHEEL_FIELDS["combo_items"])+b"\x8b\x10\xff\x52"+bytes([WHEEL_FIELDS["count_slot"]]))
    if ([class_name(wheel[k]) for k in ("spin_vmt", "combo_vmt", "button_vmt")] != [b"TSpinEdit", b"TComboBox", b"TSpinButton"]
            or len(value) != 1 or not index or len(re.findall(count, blob)) < 10
            or any(offset not in published(blob, field) for field, offset in
                   (("OnMouseWheel", WHEEL_FIELDS["on_mouse_wheel"]), ("Increment", WHEEL_FIELDS["increment"]),
                    ("OnChange", WHEEL_FIELDS["combo_change"]), ("Items", WHEEL_FIELDS["combo_items"]),
                    ("OnUpClick", WHEEL_FIELDS["up_click"]), ("OnDownClick", WHEEL_FIELDS["down_click"])))
            or 8 not in published(blob, "Name")):
        raise ValueError("Unsupported designer number boxes for the mouse wheel.")
    wheel["armour_change"] = rt.method_address(blob, base, "cbBChange")
    # Ship picture: the designer's TGlobe4 (its native wheel zoom reads it at [form+7CCh], Projection +2E0h)
    # rotates its spherical view, which pans the drawing, with MouseRotateButton; the DFM leaves it mzbNone.
    zoom = 0x5E84CC+delta
    if (blob[zoom-base:zoom-base+6] != b"\x8b\x83"+struct.pack("<I", PICTURE["globe"])
            or PICTURE["rotate_button"] not in published(blob, "MouseRotateButton") or 0x2E0 not in published(blob, "Projection")):
        raise ValueError("Unsupported designer ship picture.")
    return dict(settings=values, static_patches=plans, clock=clocks[0],
                main_slot=layout["main_slot"], player_field=layout["player_field"],
                ship_list=layout["ship_list"], ship=layout["ship"], funds=layout["nation"]["funds"],
                year_slot=layout["year_slot"], build=build, build_original=blob[build-base:build-base+5].hex(),
                monthly=monthly, monthly_original=blob[monthly-base:monthly-base+8].hex(),
                initial=initial, initial_end=initial_end,
                name_calls=[0x7806b3+delta,0x7b69da+delta], string_assign=0x30bccc+delta,
                form_show_original=blob[wheel["form_show"]-base:wheel["form_show"]-base+7].hex(), **wheel, **WHEEL_FIELDS,
                picture=PICTURE["globe"], rotate_button=PICTURE["rotate_button"], pan_button=PICTURE["middle"],
                invasions=[{k: v+delta for k, v in item.items()} for item in INVASION], message=0x4d7124+delta,
                invasion_range={k: (tuple(x+delta for x in v) if isinstance(v, tuple) else v+delta) for k, v in INVASION_RANGE.items()},
                colony=dict({k: v+delta for k, v in COLONY.items()},
                            minimum=struct.unpack_from("<I", blob, 0x7C96C9+delta-base)[0]),   # its MOV EAX,[minimum force]
                string_equal=0x30c7cc+delta,
                player_orders_limited=False, existing_ships_deleted=False)


def name_thunk(address, info):
    c=Code(address)
    c.emit(bytes.fromhex("8b4424048bd1")); c.branch(b"\xe8", info["string_assign"])
    c.emit(bytes.fromhex("c20400")); return c.finish()


def wheel_handler(address, info):
    """Form OnMouseWheel (EAX form, ECX Shift; stack @Handled, @MousePos, WheelDelta; ret 0Ch): step the box
    under the mouse pointer, ten times with Shift, up when the wheel turns away. Anything else (the picture
    zoom, lists) stays native, and focus no longer matters: moving off a box ends its wheel input."""
    c=Code(address)
    c.emit(b"\x53\x56\x57\x55\x8b\xe8\xbe\x01\x00\x00\x00")                    # EBP form, ESI steps
    c.emit(b"\xf6\xc1\x01"); c.branch(b"\x0f\x84","sign"); c.emit(b"\xbe\x0a\x00\x00\x00")   # ssShift
    c.mark("sign"); c.emit(b"\x83\x7c\x24\x1c\x00"); c.branch(b"\x0f\x8f","find"); c.emit(b"\xf7\xde")   # WheelDelta
    c.mark("find"); c.emit(b"\x8b\x44\x24\x18"); c.branch(b"\xe8",info["find_window"])   # FindVCLWindow(MousePos)
    c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84","done"); c.emit(b"\x8b\xd8")
    c.emit(b"\x8b\x43"+bytes([info["owner"]])+b"\x3b\xc5"); c.branch(b"\x0f\x84","owned")   # this form's control,
    c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84","done")                                       # or one of its
    c.emit(b"\x3b\x68"+bytes([info["owner"]])); c.branch(b"\x0f\x85","done")               # controls' parts
    c.mark("owned")
    for vmt, kind in ((info["spin_vmt"], "spin"), (info["button_vmt"], "button")):
        c.emit(b"\x8b\xc3\xba"); c.u32(vmt); c.branch(b"\xe8","is"); c.branch(b"\x0f\x85",kind)
    c.emit(b"\x8b\xc3\xba"); c.u32(info["combo_vmt"]); c.branch(b"\xe8","is"); c.branch(b"\x0f\x84","done")
    c.emit(b"\x81\xbb"); c.u32(info["combo_change"]); c.u32(info["armour_change"]); c.branch(b"\x0f\x85","done")
    c.emit(b"\x8b\xc3\x8b\x10\xff\x92"); c.u32(info["get_index"]); c.emit(b"\x8b\xe8\x8d\x3c\x2e")   # EBP index, EDI wanted
    c.emit(b"\x8b\x83"); c.u32(info["combo_items"]); c.emit(b"\x8b\x10\xff\x52"+bytes([info["count_slot"]]))
    c.emit(b"\x48"); c.branch(b"\x0f\x8c","done")                                # empty list
    c.emit(b"\x3b\xf8\x0f\x4f\xf8\x33\xc0\x85\xff\x0f\x4c\xf8")                  # clamp to 0..Count-1
    c.emit(b"\x3b\xfd"); c.branch(b"\x0f\x84","handled")
    c.emit(b"\x8b\xd7\x8b\xc3\x8b\x08\xff\x91"); c.u32(info["set_index"])
    c.emit(b"\x8b\xd3\x8b\x83"); c.u32(info["combo_change"]+4); c.emit(b"\xff\x93"); c.u32(info["combo_change"])
    c.branch(b"\xe9","handled")
    c.mark("spin"); c.emit(b"\x8b\xbb"); c.u32(info["increment"]); c.emit(b"\x0f\xaf\xfe\x8b\xc3"); c.branch(b"\xe8",info["get_value"])
    c.emit(b"\x8d\x14\x38\x8b\xc3"); c.branch(b"\xe8",info["set_value"]); c.branch(b"\xe9","handled")
    c.mark("button"); c.emit(b"\xbf"); c.u32(info["up_click"]); c.emit(b"\x85\xf6"); c.branch(b"\x0f\x8f","clicks")
    c.emit(b"\xbf"); c.u32(info["down_click"]); c.emit(b"\xf7\xde")
    c.mark("clicks"); c.emit(b"\x83\x3c\x3b\x00"); c.branch(b"\x0f\x84","done")      # no click handler
    c.mark("click"); c.emit(b"\x8b\xd3\x8b\x44\x3b\x04\xff\x14\x3b\x4e"); c.branch(b"\x0f\x85","click")
    c.mark("handled"); c.emit(b"\x8b\x44\x24\x14\xc6\x00\x01")                      # Handled := True
    c.mark("done"); c.emit(b"\x5d\x5f\x5e\x5b\xc2\x0c\x00")
    c.mark("is"); c.emit(b"\x8b\x00")                    # EAX object, EDX class: ZF clear for it or a descendant
    c.mark("class"); c.emit(b"\x3b\xc2"); c.branch(b"\x0f\x84","yes")
    c.emit(b"\x8b\x40\xd0\x85\xc0"); c.branch(b"\x0f\x84","no")               # vmtParent (-30h): parent reference
    c.emit(b"\x8b\x00\x85\xc0"); c.branch(b"\x0f\x85","class")
    c.mark("no"); c.emit(b"\x33\xc0\xc3")
    c.mark("yes"); c.emit(b"\x83\xc8\x01\xc3")
    return c.finish()


def wheel_hook(address, handler, info):
    """Designer FormShow, EBX form: install the wheel handler unless the form already has another one."""
    c=Code(address); c.emit(b"\x8b\x83"); c.u32(info["on_mouse_wheel"]); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84","set")
    c.emit(b"\x3d"); c.u32(handler); c.branch(b"\x0f\x85","native")
    c.mark("set"); c.emit(b"\xc7\x83"); c.u32(info["on_mouse_wheel"]); c.u32(handler)
    c.emit(b"\x89\x9b"); c.u32(info["on_mouse_wheel"]+4)
    c.mark("native"); c.emit(b"\x8b\x83"); c.u32(info["picture"]); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84","shown")
    c.emit(b"\xc6\x80"); c.u32(info["rotate_button"]); c.emit(bytes([info["pan_button"]]))   # middle-drag pans the picture
    c.mark("shown"); c.emit(bytes.fromhex(info["form_show_original"])); c.branch(b"\xe9",info["form_show"]+7)
    return c.finish()


def invasion_thunk(address, item, names, text, info):
    """Invasion button, EAX selected possession, in place of its CMP [EAX+58h],10 / JL: small possessions pass
    natively; bigger ones pass unless their name is a main home region."""
    c=Code(address); c.emit(b"\x83\x78\x58\x0a"); c.branch(b"\x0f\x8c",item["ok"]); c.emit(b"\x50")
    c.emit(b"\x81\x78\x58"); c.u32(HOME_VALUE); c.branch(b"\x0f\x85","pass")
    for name in names:
        c.emit(b"\x8b\x04\x24\x8b\x40\x54\xba"); c.u32(name); c.branch(b"\xe8",info["string_equal"]); c.branch(b"\x0f\x84","home")
    c.mark("pass"); c.emit(b"\x58"); c.branch(b"\xe9",item["ok"])
    c.mark("home"); c.emit(b"\x58\x83\xc9\xff\x83\xca\xff\xb8"); c.u32(text); c.branch(b"\xe8",info["message"]); c.branch(b"\xe9",item["end"])
    return c.finish()


def range_thunk(address, item, names, info):
    """Invasion range routine, frame EBP, [ebp-0Ch] possession, [ebp+4] caller: in place of its value check.
    Small possessions pass; bigger ones get no range unless a player button asks and they are no main homeland."""
    c=Code(address); c.emit(b"\x8b\x45\xf4\x83\x78\x58\x0a"); c.branch(b"\x0f\x8e",item["ok"])
    c.emit(b"\x8b\x4d\x04")
    for player in item["players"]:
        c.emit(b"\x81\xf9"); c.u32(player); c.branch(b"\x0f\x84","player")
    c.branch(b"\xe9",item["zero"])
    c.mark("player"); c.emit(b"\x50")
    c.emit(b"\x81\x78\x58"); c.u32(HOME_VALUE); c.branch(b"\x0f\x85","pass")
    for name in names:
        c.emit(b"\x8b\x04\x24\x8b\x40\x54\xba"); c.u32(name); c.branch(b"\xe8",info["string_equal"]); c.branch(b"\x0f\x84","home")
    c.mark("pass"); c.emit(b"\x58"); c.branch(b"\xe9",item["ok"])
    c.mark("home"); c.emit(b"\x58"); c.branch(b"\xe9",item["zero"])
    return c.finish()


def target_button_thunk(address, item, names, info):
    """Possession details, EBX possession: DL := "Set invasion target" enabled, then the native SetEnabled call.
    Neutral: yes (colonising). Owned: the native relation test, then big possessions unless a main homeland."""
    c=Code(address); c.emit(b"\x8b\x43\x61\x85\xc0"); c.branch(b"\x0f\x84","enabled")
    c.emit(b"\x81\xb8"); c.u32(0x256); c.u32(0x28); c.branch(b"\x0f\x8e","disabled")
    c.emit(b"\x83\x7b\x58\x0f"); c.branch(b"\x0f\x8e","enabled")
    c.emit(b"\x81\x7b\x58"); c.u32(HOME_VALUE); c.branch(b"\x0f\x85","enabled")
    for name in names:
        c.emit(b"\x8b\x43\x54\xba"); c.u32(name); c.branch(b"\xe8",info["string_equal"]); c.branch(b"\x0f\x84","disabled")
    c.mark("enabled"); c.emit(b"\xb2\x01"); c.branch(b"\xe9",item["ui_set"])
    c.mark("disabled"); c.emit(b"\x33\xd2"); c.branch(b"\xe9",item["ui_set"])
    return c.finish()


def turn_thunk(address, item, names, info):
    """Turn processing at the player's invasion target, EBX campaign, ESI the possession slot, EBP the frame
    ([ebp-14h] sea area, [ebp-1Ch] enemy strength there): in place of its owner checks (see COLONY)."""
    c=Code(address); c.emit(b"\x8b\x06\x8b\x50\x61\x85\xd2"); c.branch(b"\x0f\x84","neutral")
    c.emit(b"\x81\xba"); c.u32(0x256); c.u32(0x28); c.branch(b"\x0f\x8e",item["skip"])
    c.emit(b"\x83\x78\x58\x0f"); c.branch(b"\x0f\x8e",item["proceed"])
    c.emit(b"\x81\x78\x58"); c.u32(HOME_VALUE); c.branch(b"\x0f\x85",item["proceed"])
    for name in names:
        c.emit(b"\x8b\x06\x8b\x40\x54\xba"); c.u32(name); c.branch(b"\xe8",info["string_equal"]); c.branch(b"\x0f\x84","home")
    c.branch(b"\xe9",item["proceed"])
    c.mark("home"); c.emit(b"\x33\xc0\x89\x83"); c.u32(0x4a8c); c.branch(b"\xe9",item["skip"])
    c.mark("neutral"); c.emit(b"\x55"); c.branch(b"\xe8",item["weather"]); c.emit(b"\x59\x84\xc0"); c.branch(b"\x0f\x84",item["weather_delay"])
    c.emit(b"\x8b\x83"); c.u32(0x3204); c.emit(b"\x80\xb8"); c.u32(0x1c5); c.emit(b"\x00"); c.branch(b"\x0f\x84","force")
    c.emit(b"\x8b\x93"); c.u32(0x3204); c.emit(b"\x33\xc9\x8b\x45\xec"); c.branch(b"\xe8",item["blockade"])
    c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84",item["blockade_delay"])
    c.mark("force"); c.emit(b"\x8b\x4d\xec\x8b\x93"); c.u32(0x3204); c.emit(b"\x8b\xc3"); c.branch(b"\xe8",item["strength"])
    c.emit(b"\x8b\x15"); c.u32(item["minimum"]); c.emit(b"\x03\xd2\x42\x3b\xd0"); c.branch(b"\x0f\x8d",item["force_delay"])
    c.emit(b"\x39\x45\xe4"); c.branch(b"\x0f\x8d",item["force_delay"])
    c.branch(b"\xe9",item["landed"])
    return c.finish()


def colony_thunk(address, item, info):
    """Turn-time landing, ESI the target's slot, EBX campaign: a neutral possession becomes the player's;
    others are marked invaded as native."""
    c=Code(address); c.emit(b"\x8b\x06\x83\x78\x61\x00"); c.branch(b"\x0f\x85","native")
    c.emit(b"\x8b\x93"); c.u32(0x3204); c.emit(b"\x89\x50\x61\x8d\x40\x65\x8b\x52\x04"); c.branch(b"\xe8",info["string_assign"])
    c.branch(b"\xe9",item["success_done"])
    c.mark("native"); c.emit(b"\x33\xd2\x89\x50\x75"); c.branch(b"\xe9",item["success_native"])
    return c.finish()


def monthly_thunk(address, state, info):
    c=Code(address); c.emit(b"\x9c\x60\x3b\x90"); c.u32(info["player_field"])
    c.branch(b"\x0f\x84","native")
    c.emit(b"\x8b\x98"); c.u32(info["player_field"])
    c.emit(b"\x39\x05"); c.u32(state); c.branch(b"\x0f\x85","clear")
    c.emit(b"\x39\x1d"); c.u32(state+4); c.branch(b"\x0f\x84","ready")
    c.mark("clear"); c.emit(b"\xa3"); c.u32(state)
    c.emit(b"\x89\x1d"); c.u32(state+4)
    c.emit(b"\xbf"); c.u32(state+0x100); c.emit(b"\x31\xc0\xb9"); c.u32(18); c.emit(b"\xfc\xf3\xab")
    c.mark("ready"); c.emit(b"\x83\xec\x04\xdd\x05"); c.u32(info["clock"])
    c.emit(bytes.fromhex("db1c248b1c2483c404be")); c.u32(state+0x100)
    c.emit(b"\xb9"); c.u32(9)
    c.mark("find"); c.emit(b"\x39\x16"); c.branch(b"\x0f\x84","found")
    c.emit(b"\x83\x3e\x00"); c.branch(b"\x0f\x84","claim")
    c.emit(b"\x83\xc6\x08\x49"); c.branch(b"\x0f\x85","find"); c.branch(b"\xe9","native")
    c.mark("claim"); c.emit(bytes.fromhex("8916c7460400000000"))
    c.mark("found"); c.emit(b"\x8b\x7e\x04\x85\xff"); c.branch(b"\x0f\x84","allow")
    c.emit(b"\x3b\xdf"); c.branch(b"\x0f\x8c","allow")
    c.emit(b"\x8b\xc3\x2b\xc7\x3d"); c.u32(info["settings"]["min_procurement_days"])
    c.branch(b"\x0f\x82","blocked")
    c.mark("allow"); c.emit(b"\x89\x5e\x04")
    c.mark("native"); c.emit(b"\x61\x9d"+bytes.fromhex(info["monthly_original"]))
    c.branch(b"\xe9",info["monthly"]+8)
    c.mark("blocked"); c.emit(b"\xff\x05"); c.u32(state+8); c.emit(b"\x61\x9d\xc3")
    return c.finish()


def build_thunk(address, state, info):
    f=info["ship"]; c=Code(address); c.emit(b"\x9c\x60\x3b\x90"); c.u32(info["player_field"])
    c.branch(b"\x0f\x84","native")
    # AIBuildShip also creates the starting fleet. Exempt calls from that
    # audited routine; the procurement caps must not truncate a new campaign.
    c.emit(bytes.fromhex("8b4c242481f9")); c.u32(info["initial"])
    c.branch(b"\x0f\x82", "regular")
    c.emit(b"\x81\xf9"); c.u32(info["initial_end"])
    c.branch(b"\x0f\x82", "native")
    c.mark("regular")
    c.emit(b"\x85\xd2"); c.branch(b"\x0f\x84","native")
    c.emit(b"\x83\xba"); c.u32(info["funds"]); c.emit(b"\x00"); c.branch(b"\x0f\x8c","blocked")
    c.emit(b"\x8b\x2d"); c.u32(info["year_slot"]); c.emit(b"\x8b\x6d\x00\x8b\x82"); c.u32(info["ship_list"])
    c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84","native")
    c.emit(b"\x8b\x48\x08\x81\xf9"); c.u32(10000); c.branch(b"\x0f\x87","blocked")
    c.emit(b"\x8b\x58\x04\x31\xf6\x31\xff\x85\xc9"); c.branch(b"\x0f\x84","native")
    c.mark("loop"); c.emit(b"\x8b\x13\x83\xba"); c.u32(f["RepairTime"]); c.emit(b"\x64")
    c.branch(b"\x0f\x8d","next"); c.emit(b"\x46\x81\xfe"); c.u32(info["settings"]["max_active_ships"])
    c.branch(b"\x0f\x8d","blocked")
    c.emit(b"\x8b\x82"); c.u32(f["Cost"]); c.emit(b"\x3b\x82"); c.u32(f["BuildProgress"])
    c.branch(b"\x0f\x8e","next")
    c.emit(b"\x83\xba"); c.u32(f["MonthlyCost"]); c.emit(b"\x00"); c.branch(b"\x0f\x8e","next")
    c.emit(b"\x83\xba"); c.u32(f["BuildProgress"]); c.emit(b"\x00"); c.branch(b"\x0f\x8f","project")
    c.emit(b"\x39\xaa"); c.u32(f["YearBuilt"]); c.branch(b"\x0f\x8f","project")
    c.emit(b"\x80\xba"); c.u32(f["Rebuild"]); c.emit(b"\x00"); c.branch(b"\x0f\x84","next")
    c.mark("project"); c.emit(b"\x47\x81\xff"); c.u32(info["settings"]["max_building_ships"])
    c.branch(b"\x0f\x8d","blocked")
    c.mark("next"); c.emit(b"\x83\xc3\x04\x49"); c.branch(b"\x0f\x85","loop")
    c.mark("native"); c.emit(b"\x61\x9d"+bytes.fromhex(info["build_original"]))
    c.branch(b"\xe9",info["build"]+5)
    c.mark("blocked"); c.emit(b"\xff\x05"); c.u32(state+12); c.emit(bytes.fromhex("619d31c0c20400"))
    return c.finish()


def attach(wait=30, settings=None):
    import ai_runtime
    import live_cheats as live
    import week_display as memory
    ai_runtime.checked_game(); memory.configure(); deadline=time.monotonic()+wait
    while True:
        games=[(pid,path) for pid,path in rt.process_candidates() if path==rt.GAME/"RTW3.exe"]
        if len(games)==1: break
        if time.monotonic()>=deadline: raise ValueError("Open the local game with mods first.")
        time.sleep(.5)
    pid,_=games[0]; handle=rt.K.OpenProcess(0x438,False,pid)
    if not handle: raise rt.win_error("Cannot open campaign QoL engine")
    try:
        module,_=rt.module_info(pid)
        if REPORT.exists():
            previous=json.loads(REPORT.read_text(encoding="utf-8"))
            if previous.get("attached") and previous.get("pid")==pid and previous.get("base")==module and rt.report_is_current(REPORT,pid):
                ai_runtime.verify(handle,previous["patches"],"replacement"); return previous
        base,blob=rt.text_section(handle,module); info=discover(blob,base,settings)
        ai_runtime.require_title_screen(handle,info)
        allocation=rt.K.VirtualAllocEx(handle,None,0x3000,0x3000,0x40)
        if not allocation: raise rt.win_error("Cannot allocate campaign QoL rules")
        state=allocation+0x1000; plans=list(info["static_patches"]); applied=[]
        try:
            code=name_thunk(allocation,info); memory.write(handle,allocation,code)
            rt.K.FlushInstructionCache(handle,allocation,len(code))
            for site in info["name_calls"]:
                old=blob[site-base:site-base+5]
                plans.append(patch("Accept generated ship-name fallback",site,old,b"\xe8"+struct.pack("<i",allocation-site-5)))
            for offset,key,factory in ((0x400,"monthly",monthly_thunk),(0x800,"build",build_thunk)):
                target=allocation+offset; code=factory(target,state,info)
                if len(code)>0x400: raise ValueError("QoL rules exceed the reserved code area.")
                memory.write(handle,target,code); rt.K.FlushInstructionCache(handle,target,len(code))
                old=bytes.fromhex(info[key+"_original"])
                plans.append(patch("Bounded AI procurement: "+key,info[key],old,
                                   b"\xe9"+struct.pack("<i",target-info[key]-5)+b"\x90"*(len(old)-5)))
            handler,hook=allocation+0xc00,allocation+0xe00
            for target,code in ((handler,wheel_handler(handler,info)),(hook,wheel_hook(hook,handler,info))):
                if len(code)>0x200: raise ValueError("QoL rules exceed the reserved code area.")
                memory.write(handle,target,code); rt.K.FlushInstructionCache(handle,target,len(code))
            if info["settings"]["invade_possessions"]:
                start,room=INVASION_CODE["literals"]; cursor=allocation+start; names=[]
                for value in HOMELANDS+(HOMELAND_TEXT,):
                    data=struct.pack("<HHiI",1200,2,-1,len(value))+value.encode("utf-16-le")+b"\0\0"
                    memory.write(handle,cursor,data); names.append(cursor+12); cursor+=(len(data)+15)&~15
                if cursor>allocation+start+room: raise ValueError("QoL rules exceed the reserved code area.")
                item=info["colony"]
                for name,key,size,code_of in (
                        ("Invasion target button: neutral and big possessions","ui",6,
                         lambda t: target_button_thunk(t,item,names[:-1],info)),
                        ("Turn-time invasion: neutral and big possessions","turn",5,
                         lambda t: turn_thunk(t,item,names[:-1],info)),
                        ("Colonise neutral possessions","success",7,lambda t: colony_thunk(t,item,info))):
                    offset,room=INVASION_CODE[key]; target=allocation+offset;code=code_of(target)
                    if len(code)>room: raise ValueError("QoL rules exceed the reserved code area.")
                    memory.write(handle,target,code); rt.K.FlushInstructionCache(handle,target,len(code))
                    plans.append(patch(name,item[key],blob[item[key]-base:item[key]-base+size],
                                       b"\xe9"+struct.pack("<i",target-item[key]-5)+b"\x90"*(size-5)))
                offset,room=INVASION_CODE["range"]
                item=info["invasion_range"];target=allocation+offset;code=range_thunk(target,item,names[:-1],info)
                if len(code)>room: raise ValueError("QoL rules exceed the reserved code area.")
                memory.write(handle,target,code); rt.K.FlushInstructionCache(handle,target,len(code))
                plans.append(patch("Invasion range for big possessions (player)",item["site"],blob[item["site"]-base:item["site"]-base+9],
                                   b"\xe9"+struct.pack("<i",target-item["site"]-5)+b"\x90"*4))
                for (offset,room),item in zip(INVASION_CODE["invasions"],info["invasions"]):
                    target=allocation+offset; code=invasion_thunk(target,item,names[:-1],names[-1],info)
                    if len(code)>room: raise ValueError("QoL rules exceed the reserved code area.")
                    memory.write(handle,target,code); rt.K.FlushInstructionCache(handle,target,len(code))
                    plans.append(patch("Invade any possession but a main home region",item["site"],blob[item["site"]-base:item["site"]-base+6],
                                       b"\xe9"+struct.pack("<i",target-item["site"]-5)+b"\x90"))
                    plans.append(patch("Home areas without a blockade",item["blockade"],blob[item["blockade"]-base:item["blockade"]-base+2],
                                       b"\xeb"+blob[item["blockade"]-base+1:item["blockade"]-base+2]))
            old=bytes.fromhex(info["form_show_original"])
            plans.append(patch("Designer mouse wheel on the box under the pointer",info["form_show"],old,
                               b"\xe9"+struct.pack("<i",hook-info["form_show"]-5)+b"\x90"*(len(old)-5)))
            ai_runtime.verify(handle,plans,"original")
            for plan in plans:
                rt.write_code(handle,plan["address"],bytes.fromhex(plan["original"]),bytes.fromhex(plan["replacement"])); applied.append(plan)
            ai_runtime.verify(handle,plans,"replacement")
            saved=dict(attached=True,pid=pid,base=module,allocation=allocation,state=state,patches=plans,details=info,
                       personal_saves_modified=False,campaign_gameplay_verified=False)
            REPORT.write_text(json.dumps(saved,indent=2)+"\n",encoding="utf-8"); return saved
        except Exception:
            for plan in reversed(applied): rt.write_code(handle,plan["address"],bytes.fromhex(plan["replacement"]),bytes.fromhex(plan["original"]))
            if not applied: rt.K.VirtualFreeEx(handle,allocation,0,0x8000)
            raise
    finally: rt.K.CloseHandle(handle)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("command",choices=("attach",)); p.add_argument("--settings",default="{}"); args=p.parse_args()
    try: print(json.dumps(attach(settings=json.loads(args.settings))))
    except (OSError,ValueError) as error:
        print(json.dumps(dict(ok=False,message=str(error)))); raise SystemExit(1)
