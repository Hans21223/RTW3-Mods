"""Nuclear strike console in battle: a NUKE button, a target picked on the map, an arming key and a red LAUNCH button.

The battle screen (TfrmMain) gets, at FormShow, a NUKE speed button right of the toolbar's last button
(sbAutoRunBattle) and a hidden console panel under it. NUKE (when the player's nation has the Ballistic missile
submarines research and an SSBN in service, and has not struck yet this battle; any number with Nuclear Armageddon)
switches the map to a crosshair: the next click on it marks the target (GlobeMouseUp, the way the strike dialog
picks a target location) and the map shows the two blast zones. The console is a backdrop picture with live labels,
gauges, a key switch (FRAMES pictures, turned by a TTimer) and LAUNCH; turned to ARM, the key lights LAUNCH; LAUNCH
pays the price of a nuclear missile under shell_doctrine's rules (a ban treaty forbids it, funds must cover it, it
counts as the player's first nuclear missile for the computer's no-first-use and raises next month's tension), then
the blast:
- every ship within FULL_YARDS of the target, either side, takes the nuclear hit (nuclear_subs' strike: the
  HandleHit a nuclear shell gets), every ship within RING_YARDS a BLAST_CALIBRE-inch hit;
- every air formation within RING_YARDS loses its aircraft;
- a line in the battle log, and on the map a fireball and a shock ring for a few seconds (a TTimer redraws).
Computer nations never use the console. The battle's mark is STRIKE_BIT in the player's ships' extension data.
Part of the modern-research adapter; imported lazily.
"""
import hashlib
import struct

import modern_tree as tree
import shell_doctrine as doctrine_rules

BASE = 0x301000
FULL_YARDS, RING_YARDS, BLAST_CALIBRE, NUCLEAR_CALIBRE = 2000, 5000, 12, tree.NUCLEAR_SHELLS[2]
PRICE = doctrine_rules.MISSILE_COST
# The warheads the console offers (a click on WARHEAD cycles them): its name on the console, price, the radius in which
# every ship sinks (the nuclear hit, then no buoyancy and a sinking timer of one: the game's own debug Sink), the radius
# of the nuclear hit, warheads (a MIRV's others go to enemy ships the player has contact on within MIRV_YARDS of the
# mark, outside the earlier warheads' kill radius), the first year. Air formations inside the hit radius are lost.
WARHEADS = (("A-BOMB", PRICE, FULL_YARDS, RING_YARDS, 1, 0),
            ("H-BOMB", 4000, 6000, 15000, 1, 0),
            ("MIRV", 6000, FULL_YARDS, RING_YARDS, 4, 1970))
MIRV_YARDS = 40000
SINK = dict(buoyancy=0xB0A, timer=0xB35)   # Tship: remaining buoyancy; minutes until it goes down (CheckSunk)
SIGHTED = dict(visual=0xD55, radar=0xD59)   # Tship: how the other side sees it (the missile target checks read them)
STRIKE_BIT = 0x2000                    # fighting ship extension data: this battle's strike is spent
TIMER_MS, FLASH, SHOCK, GLOW = 100, 6, 20, 80   # effect ticks: the fireball grows, the shock ring grows, the end
POINTS = 36                            # the fireball polygon
COLOURS = dict(white=0xFFFFFF, yellow=0x00FFFF, orange=0x0080FF, red=0x0000FF, dark=0x000080, grey=0x808080)
NATIVE = dict(form_show=0x8B22FC, render=0x85C83D, pick=0x85B5B9, pick_native=0x85B5C6, pick_done=0x85B66A,
              device_to_ll=0x57DA04, set_cursor=0x451EC8, set_visible=0x451B54, set_text=0x451CA0, set_left=0x450EF0,
              set_top=0x450F24, set_width=0x450F5C, set_height=0x450F90, set_show_hint=0x451DCC, assign=0x30BCCC,
              message=0x4D7124, font_color=0x41EE9C, font_style=0x41F234, brush_color=0x41FA20, brush_style=0x41FBA0,
              brush_get_color=0x41FA18, brush_get_style=0x41FB98, pen_color=0x41F63C, pen_width=0x41F798,
              pen_style=0x41F760, pen_get_color=0x41F634, pen_get_width=0x41F790, pen_get_style=0x41F758,
              shape_type=0x4DDF94, timer_enabled=0x4DEF6C, timer_interval=0x4DEF7C, units=0x55C894,
              ll_distance=0x5733F4, to_unit=0x55C844, point_at=0x57319C, bearing=0x8EC090, get_sub=0x72C484,
              list_get=0x3B6D6C, inflict=0x96686C, has_research=0x729FA4, battle_log=0xA80114,
              # the console's pictures and labels: TBitmap.Create, FileExists, TImage.SetPicture/SetStretch,
              # TCustomLabel.SetTransparent, TFont.SetSize/SetName (published-property RTTI), IntToStr
              bitmap_create=0x426EDC, file_exists=0x3298A0, image_picture=0x4DE5DC, image_stretch=0x4DE5E8,
              label_transparent=0x476CFC, font_size=0x41F1FC, font_name=0x41F184, int_to_str=0x328C80,
              cat3=0x30C694,                   # UStrCat3(EAX the result's variable, EDX, ECX)
              label_wrap=0x476D58)             # TCustomLabel.SetWordWrap (published-property RTTI)
VMTS = dict(panel=0x4DAE4C, shape=0x4D92E4, button=0x46DDCC, speed=0x588394, timer=0x4DA7DC, checkbox=0x46EF68,
            label=0x467348, image=0x4D9A2C, bitmap=0x41AC60)
LOAD_FROM_FILE = 0x58                  # TGraphic.LoadFromFile, a virtual slot
VARS = dict(ships=(0x8761E3, 1), air=(0x91ABC3, 1), side=(0x960E9B, 2), main=(0x8ED02C, 1))   # instruction, offset
FORM = dict(toolbar=0x438, globe=0x498, last_button=0x610)        # TfrmMain: Panel1, Globe, sbAutoRunBattle
REFERENCE_WIDTH = 28                                                # sbAutoRunBattle at 96 DPI: the scale
GLOBE = dict(projection=0x2E0, renderer=0x2E4, redraw=0x1A0, circle=0x1D0, polygon=0x1C4)
CANVAS = dict(pen=0x44, brush=0x48)
CONTROL = dict(tag=0xC, left=0x50, top=0x54, width=0x58, height=0x5C, hint=0x90, font=0x74, on_click=0x120,
               create=0x3C, set_parent=0xA0, set_enabled=0x9C, get_checked=0x16C, set_checked=0x170,
               shape_pen=0x1E0, shape_brush=0x1E4, on_timer=0x48,
               set_autosize=0x94)              # TControl.SetAutoSize, a virtual slot (the RTTI setter FE000094h)
SHIP = dict(nation=0x14, kind=0x9D3, out=0xA9F, side=0xA55, position=0xA1C)
AIR = dict(count=0x18, destroyed=0x8D, position=0x2C)
# TSubmarine, as its SaveMe (0x82EC0C) writes it: RemainingBuildTime +15h, Sunk +1Ah. Until 2026-11-22 "gone" read
# +20h, InPlay, which is 1 for every boat in the campaign: no SSBN ever counted and NUKE stayed greyed out.
SUB = dict(name=4, sunk=0x1A, months=0x15)
NATION = dict(subs=0x111, funds=doctrine_rules.FUNDS)
LAND, CIRCLE, CROSS, YARDS, DESTROYED, AA_LOSS = 12, 5, 0xFFFD, 12, 12, 1
KINDS = dict(nuke="speed", console="panel", backdrop="image", gauge_target="shape", gauge_arm="shape", ssbns="label",
             target="label", status="label", info="label", key1="image", key2="image", launch="image", tgt="shape",
             cancel="shape", timer="timer", key_timer="timer", warhead="label", warhead_hit="shape")
TAGS = {name: 0x4E554B31+i for i, name in enumerate(KINDS)}
# At 96 DPI: the console's size and its gap under the toolbar (it opens centred under NUKE, kept inside the window),
# the NUKE button's gap after sbAutoRunBattle, and the console's controls (left, top, width, height) over its
# backdrop picture, which nuke_console_art.py draws to this layout (title, captions, the price, gauge frames, ABORT).
# Two keys (both at ARM arm the strike), LAUNCH in the middle under a glass cover (a click opens it, the next fires),
# TGT a button (it picks the target, as NUKE does), the readouts in a strip along the bottom.
CONSOLE, GAP, NUKE_GAP = (460, 284), 4, 6
LAYOUT = dict(backdrop=(0, 0, 460, 284), key1=(14, 44, 110, 92), key2=(336, 44, 110, 92),
              gauge_target=(136, 50, 12, 118), tgt=(128, 42, 28, 158), launch=(160, 40, 140, 140),
              gauge_arm=(312, 50, 12, 118), ssbns=(14, 230, 110, 20), target=(234, 230, 110, 20),
              status=(344, 230, 110, 20), info=(14, 252, 334, 28), cancel=(360, 254, 86, 22),
              warhead=(124, 230, 110, 20), warhead_hit=(122, 208, 106, 44))
FRAMES, GLASS, KEY_MS = 8, 4, 60       # a key's pictures SAFE to ARM; the glass cover's, shut to open; ms between
PICTURES = (("backdrop",)+tuple(f"key{i}" for i in range(FRAMES))           # nuke_console/<name>.bmp
            +tuple(f"launch{g}{lit}" for g in range(GLASS) for lit in "sa"))  # s: the button dark, a: lit (armed)
LAUNCH_PICTURE = 1+FRAMES              # PICTURES index of launch0s; +2 a glass frame, +1 lit
FONT, LABEL_PT, INFO_PT = "Bahnschrift", 11, 8
HAND = 0xFFEB                          # crHandPoint over the console's buttons
PALETTE = dict(value=0x40D0F0, label=0xE0DACD, info=0xBFB8A9, cyan=0xC8C33C, fill=0x7A73D9)   # BGR (TColor)
TEXT = dict(nuke="NUKE", none="NONE", marked="MARKED", safe="SAFE", armed="ARMED", font=FONT,
            picking="Click the target area on the map.",
            ready="Target marked. Turn both keys, open the glass, LAUNCH.",
            hint=f"Nuclear strike: A-bomb, H-bomb or MIRV, {PRICE:,} to {max(w[1] for w in WARHEADS):,}. "
                 "Needs an SSBN in service.",
            unavailable="No nuclear strike: it needs the Ballistic missile submarines research and an SSBN in service.",
            spent="This battle's nuclear strike has been launched.",
            no_target="Click NUKE, then the target area on the map.",
            unarmed="Turn both keys to ARM first.",
            treaty="A nuclear ban treaty is in force.",
            funds="Not enough money for this warhead.",
            strike="Nuclear strike",
            empty="2Nuclear strike: the warheads hit empty sea, nothing within reach",
            **{f"name{i}": f"{name} {price:,}" if count == 1 else f"{name} x{count} {price:,}"
               for i, (name, price, kill, ring, count, year) in enumerate(WARHEADS)},
            **{f"about{i}": (f"{name}: sinks every ship within {kill:,} yards, the nuclear hit to {ring:,}. {price:,}."
                             if count == 1 else
                             f"{name}: {count} warheads on enemy ships in contact within {MIRV_YARDS:,} yards of the mark"
                             f" (from {year}). {price:,}.")
               for i, (name, price, kill, ring, count, year) in enumerate(WARHEADS)},
            **{f"log{i}": (f"2Nuclear strike: an {name} detonates over the marked area" if count == 1 else
                           f"2Nuclear strike: MIRV warheads detonate over the mark and nearby enemies")
               for i, (name, price, kill, ring, count, year) in enumerate(WARHEADS)})
WINDOWS = (
    (0x8B22D2, 0x40),   # TfrmMain.FormShow past its prologue (live-cheats' battle environment hooks that)
    (0x85C7D0, 0x80),   # GlobeRender: prologue, day and night shadow, past the hook
    (0x85AE2C, 0x28),   # GlobeMouseUp: Self, X and Y
    (0x85B5B9, 0xB8),   # GlobeMouseUp: the pick-location check, its body, the next check
)
DIGESTS = (
    "b6ae6cab76a69c6c105850f38a2fe620fa6c22a2416add9f268840b220bb773e",
    "5ce7d2549957c823a1dc1a726978fe5716f11d349deb1d3b0795d354e6d9896c",
    "da9e7a8af2df4811016db9fc9e346c3483a1026980629d68dd0805c60d680a78",
    "11d8c08320b31766a095d2b0408c0128932f79ae85510e83c8a6c1a46970694e",
)
ORIGINALS = dict(form_show="8b83a8040000", render="a12c779f00", pick="80bbcc070000000f84a4000000")
# Code page offsets (each ends at the next), the console page's (CONSOLE_CODE), and the data page: the state, the
# fireball points, the console's state and pictures (TBitmaps, loaded once a session). The texts have a page of their own.
CODE = dict(timer=0x000, available=0x100, blast=0x180, setkind=0x400, nuke=0x500, pick=0x5C0, launch=0x690, tick=0x940, render=0x970,
            used=0xC10, mark=0xC90, units=0xDF0, distance=0xE10, ring=0xE30,
            disc=0xE50, find=0xEB0, scale=0xEF0, redraw=0xF10, info=0xF30, end=0xF60)
CONSOLE_CODE = dict(show=0x000, load=0x980, refresh=0xA00, key1=0xC00, key2=0xC20, glass=0xC40, key_tick=0xC80,
                    cancel=0xD80, look=0xDE0, warhead=0xE10, aim=0xE80, end=0x1000)
# key_frame/key_target: two bytes each, KEY 1 then KEY 2; glass_*: the cover; names: the pictures' file names.
DATA = dict(pick=0x000, has_target=0x001, active=0x002, caught=0x003, step=0x004, target=0x008, centre=0x014, player=0x020,
            pen=0x024, brush=0x030, points=0x040, armed=0x200, loaded=0x201, glass_frame=0x202, glass_target=0x203,
            key_frame=0x204, key_target=0x206, count=0x208, number=0x20C, path=0x210, pictures=0x214,
            names=0x258, kind=0x29C, blasts=0x29D, here=0x2A0, kill=0x2A4, ring=0x2A8, centres=0x2AC,
            warheads=0x2DC)
# warheads: per warhead 8 dwords: price, kill, ring, count, year, its name, about and log texts.
WARHEAD_SIZE = 32
assert DATA["names"] == DATA["pictures"]+4*len(PICTURES) and DATA["centres"]+12*max(w[4] for w in WARHEADS) <= DATA["warheads"]
assert DATA["warheads"]+WARHEAD_SIZE*len(WARHEADS) <= 0x1000


def digests(blob):
    import modern_research as audit
    normal = audit.normalize(blob, BASE)
    return [hashlib.sha256(normal[a-BASE:a-BASE+n]).hexdigest() for a, n in WINDOWS]


def discover(blob, base, normalized):
    for (address, size), digest in zip(WINDOWS, DIGESTS):
        if hashlib.sha256(normalized[address-BASE:address-BASE+size]).hexdigest() != digest:
            raise ValueError("Nuclear strike refuses changed native code at "+hex(address)+".")
    delta = base-BASE
    info = {k: v+delta for k, v in {**NATIVE, **VMTS}.items()}
    for name, (address, offset) in VARS.items():
        info[name] = struct.unpack_from("<I", blob, address-BASE+offset)[0]
    info["render_original"] = blob[NATIVE["render"]-BASE:NATIVE["render"]-BASE+5].hex()   # mov eax, [a global]
    return info


def literal(text):
    return struct.pack("<HHiI", 1200, 2, -1, len(text))+text.encode("utf-16-le")+b"\0\0"


def picture_folder():
    from pathlib import Path
    return str(Path(__file__).resolve().parent/"nuke_console")+"\\"


def picture_path(name): return picture_folder()+f"{name}.bmp"


def build(page, data, info, doctrine, ext, strike, is_kind, console_page, text_page):
    """page: code (0x1000); data: state, points and pictures (0x1000); console_page: the console's code (0x1000);
    text_page: the texts (0x1000), on their own page since the picture folder is the install path (a default Steam
    install's is 98 characters, which overflowed the data page; up to MAX_PATH fits). doctrine: shell_doctrine's entries (lookup, first, year, used, armageddon); ext: modern_extension's
    ext(EAX ship) -> EAX data pointer or 0; strike and is_kind: nuclear_subs' routines."""
    from campaign_security import Code
    from hull_rules import patch, dpi_scale_routine
    n, code = info, {}
    at = {**{k: page+v for k, v in CODE.items()}, **{k: console_page+v for k, v in CONSOLE_CODE.items()}}
    d = {k: data+v for k, v in DATA.items()}
    T, text_bytes = {}, bytearray()
    for key, value in {**TEXT, "folder": picture_folder(), **{"pic_"+name: name+".bmp" for name in PICTURES}}.items():
        body = literal(value); T[key] = text_page+len(text_bytes)+12
        text_bytes += body+bytes(-len(body) % 4)
    if len(text_bytes) > 0x1000: raise ValueError("Nuclear strike texts exceed their page.")

    def call(c, target): c.branch(b"\xe8", target)
    def virtual(c, offset): c.emit(b"\x8b\x08\xff\x91"); c.u32(offset)               # mov ecx,[eax]; call [ecx+offset]
    def message(c, key): c.emit(b"\x83\xc9\xff\x83\xca\xff\xb8"); c.u32(T[key]); call(c, n["message"])
    def player(c):   # EAX the player's nation, or 0 without a campaign
        c.emit(b"\xa1"); c.u32(n["main"]); c.emit(b"\x8b\x00\x85\xc0\x74\x06\x8b\x80"); c.u32(doctrine_rules.PLAYER)
    def find(c, kind): c.emit(b"\x8b\xc3\xba"); c.u32(n[KINDS[kind]]); c.emit(b"\xb9"); c.u32(TAGS[kind]); call(c, at["find"])
    def flag(c, name, value): c.emit(b"\xc6\x05"); c.u32(d[name]); c.emit(bytes([value]))
    def hide_console(c): find(c, "console"); c.emit(b"\x85\xc0\x74\x07\x33\xd2"); call(c, n["set_visible"])   # jz past

    # find(EAX form, EDX vmt, ECX tag) -> EAX the form's component of that class and tag, or 0. Keeps EBX..EBP.
    c = Code(at["find"]); c.emit(b"\x53\x56\x8b\x40\x10\x85\xc0"); c.branch(b"\x0f\x84", "none")
    c.emit(b"\x8b\x70\x08\x8b\x40\x04")
    c.mark("next"); c.emit(b"\x4e"); c.branch(b"\x0f\x88", "none")
    c.emit(b"\x8b\x1c\xb0\x39\x13"); c.branch(b"\x0f\x85", "next")
    c.emit(b"\x39\x4b"+bytes([CONTROL["tag"]])); c.branch(b"\x0f\x85", "next")
    c.emit(b"\x8b\xc3\x5e\x5b\xc3")
    c.mark("none"); c.emit(b"\x33\xc0\x5e\x5b\xc3")
    code["find"] = c.finish()
    code["scale"] = dpi_scale_routine(FORM["last_button"], REFERENCE_WIDTH)   # EBX form, EDX value at 96 DPI
    # redraw(EBX form): the globe redraws its layers and calls GlobeRender.
    c = Code(at["redraw"]); c.emit(b"\x60\x8b\x83"); c.u32(FORM["globe"]); virtual(c, GLOBE["redraw"]); c.emit(b"\x61\xc3")
    code["redraw"] = c.finish()
    # info(EBX form, EDX text): the console's info line.
    c = Code(at["info"]); c.emit(b"\x60\x52"); find(c, "info"); c.emit(b"\x5a\x85\xc0"); c.branch(b"\x0f\x84", "out")
    call(c, n["set_text"])
    c.mark("out"); c.emit(b"\x61\xc3")
    code["info"] = c.finish()

    def create(c, kind, parent, bounds=None):
        """EBX form; parent: a form field, "form" or "console" (EDI) -> ESI the control. bounds: at 96 DPI, or
        None when the caller pushed the on-screen height, width, top and left."""
        c.emit(b"\x8b\xcb\xb2\x01\xb8"); c.u32(n[KINDS[kind]]); c.emit(b"\xff\x50"+bytes([CONTROL["create"]]))
        c.emit(b"\x8b\xf0\xc7\x46"+bytes([CONTROL["tag"]])); c.u32(TAGS[kind])
        if parent == "form": c.emit(b"\x8b\xd3")
        elif parent == "console": c.emit(b"\x8b\xd7")
        else: c.emit(b"\x8b\x93"); c.u32(parent)
        c.emit(b"\x8b\xc6"); virtual(c, CONTROL["set_parent"])
        for i, setter in enumerate(("set_left", "set_top", "set_width", "set_height")):
            if bounds is None: c.emit(b"\x5a")
            else: c.emit(b"\xba"); c.u32(bounds[i]); call(c, at["scale"])
            c.emit(b"\x8b\xc6"); call(c, n[setter])

    def caption(c, key): c.emit(b"\xba"); c.u32(T[key]); c.emit(b"\x8b\xc6"); call(c, n["set_text"])
    def on_click(c, handler): c.emit(b"\xc7\x86"); c.u32(CONTROL["on_click"]); c.u32(handler); c.emit(b"\x89\x9e"); c.u32(CONTROL["on_click"]+4)
    def bold_red(c):
        c.emit(b"\x8b\x46"+bytes([CONTROL["font"]])+b"\xba"); c.u32(COLOURS["red"]); call(c, n["font_color"])
        c.emit(b"\x8b\x46"+bytes([CONTROL["font"]])+b"\xb2\x01"); call(c, n["font_style"])                  # fsBold
    def styled(c, colour, points): c.emit(b"\xba"); c.u32(colour); c.emit(b"\xb9"); c.u32(points); call(c, at["look"])
    def shape_colours(c, pen, brush):   # ESI a TShape
        c.emit(b"\x8b\x86"); c.u32(CONTROL["shape_pen"]); c.emit(b"\xba"); c.u32(pen); call(c, n["pen_color"])
        c.emit(b"\x8b\x86"); c.u32(CONTROL["shape_brush"]); c.emit(b"\xba"); c.u32(brush); call(c, n["brush_color"])
    def stretched(c): c.emit(b"\xb2\x01\x8b\xc6"); call(c, n["image_stretch"])      # ESI a TImage: fills its bounds
    def hand(c): c.emit(b"\x66\xba"+struct.pack("<H", HAND)+b"\x8b\xc6"); call(c, n["set_cursor"])   # ESI: a button
    def safe(c):   # both keys and the glass go back (the timer turns them)
        c.emit(b"\x66\xc7\x05"); c.u32(d["key_target"]); c.emit(b"\x00\x00"); flag(c, "glass_target", 0); call(c, at["timer"])
    def found(c, kind, label):   # EAX the console control of that kind, else on to label
        find(c, kind); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", label)

    # look(ESI a label, EDX colour, ECX points): the console's font, transparent over the backdrop. Keeps all.
    c = Code(at["look"]); c.emit(b"\x60\x52\x51\x8b\x46"+bytes([CONTROL["font"]])+b"\xba"); c.u32(T["font"]); call(c, n["font_name"])
    c.emit(b"\x5a\x8b\x46"+bytes([CONTROL["font"]])); call(c, n["font_size"])
    c.emit(b"\x5a\x8b\x46"+bytes([CONTROL["font"]])); call(c, n["font_color"])
    c.emit(b"\xb2\x01\x8b\xc6"); call(c, n["label_transparent"]); c.emit(b"\x61\xc3")
    code["look"] = c.finish()

    # load(): the pictures, once a session: for each name, folder+name; a TBitmap when the file exists (a missing
    # one shows nothing).
    c = Code(at["load"]); c.emit(b"\x60\x80\x3d"); c.u32(d["loaded"]); c.emit(b"\x00"); c.branch(b"\x0f\x85", "out")
    flag(c, "loaded", 1); c.emit(b"\x33\xf6")
    c.mark("next"); c.emit(b"\xb8"); c.u32(d["path"]); c.emit(b"\xba"); c.u32(T["folder"])
    c.emit(b"\x8b\x0c\xb5"); c.u32(d["names"]); call(c, n["cat3"])                         # path := folder+name
    c.emit(b"\xa1"); c.u32(d["path"]); c.emit(b"\xb2\x01"); call(c, n["file_exists"]); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "skip")
    c.emit(b"\xb2\x01\xb8"); c.u32(n["bitmap"]); call(c, n["bitmap_create"]); c.emit(b"\x89\x04\xb5"); c.u32(d["pictures"])
    c.emit(b"\x8b\x15"); c.u32(d["path"]); c.emit(b"\x8b\x08\xff\x51"+bytes([LOAD_FROM_FILE]))
    c.mark("skip"); c.emit(b"\x46\x83\xfe"+bytes([len(PICTURES)])); c.branch(b"\x0f\x82", "next")
    c.mark("out"); c.emit(b"\x61\xc3")
    code["load"] = c.finish()

    # refresh(EBX form): the console from the state: SSBNs, target and its gauge, status, both keys' pictures, the
    # glass and LAUNCH (lit when armed), the ARM gauge's fill (bottom up with both keys' turn).
    gauge_x, gauge_y, gauge_w, gauge_h = LAYOUT["gauge_arm"]
    c = Code(at["refresh"]); c.emit(b"\x60\xa1"); c.u32(d["count"]); c.emit(b"\xba"); c.u32(d["number"]); call(c, n["int_to_str"])
    found(c, "ssbns", "target"); c.emit(b"\x8b\x15"); c.u32(d["number"]); call(c, n["set_text"])
    c.mark("target"); found(c, "target", "gauge")
    c.emit(b"\xba"); c.u32(T["none"]); c.emit(b"\x80\x3d"); c.u32(d["has_target"]); c.emit(b"\x00\x74\x05\xba"); c.u32(T["marked"])
    call(c, n["set_text"])
    c.mark("gauge"); found(c, "gauge_target", "status")
    c.emit(b"\x0f\xb6\x15"); c.u32(d["has_target"]); call(c, n["set_visible"])
    c.mark("status"); found(c, "status", "warhead")
    c.emit(b"\xba"); c.u32(T["safe"]); c.emit(b"\x80\x3d"); c.u32(d["armed"]); c.emit(b"\x00\x74\x05\xba"); c.u32(T["armed"])
    call(c, n["set_text"])
    c.mark("warhead"); found(c, "warhead", "key1")                # its name and price
    c.emit(b"\x0f\xb6\x15"); c.u32(d["kind"]); c.emit(b"\x6b\xd2"+bytes([WARHEAD_SIZE])+b"\x8b\x92"); c.u32(d["warheads"]+20)
    call(c, n["set_text"])
    for i, kind in enumerate(("key1", "key2")):                 # picture = pictures[1+frame]
        c.mark(kind); found(c, kind, ("key2", "launch")[i])
        c.emit(b"\x8b\xf0\x0f\xb6\x05"); c.u32(d["key_frame"]+i); c.emit(b"\x8b\x14\x85"); c.u32(d["pictures"]+4)
        c.emit(b"\x8b\xc6"); call(c, n["image_picture"])
    c.mark("launch"); found(c, "launch", "arm")                 # picture = pictures[LAUNCH_PICTURE+2*glass+armed]
    c.emit(b"\x8b\xf0\x0f\xb6\x05"); c.u32(d["glass_frame"]); c.emit(b"\x03\xc0\x0f\xb6\x0d"); c.u32(d["armed"])
    c.emit(b"\x03\xc1\x8b\x14\x85"); c.u32(d["pictures"]+4*LAUNCH_PICTURE); c.emit(b"\x8b\xc6"); call(c, n["image_picture"])
    c.mark("arm"); found(c, "gauge_arm", "out")
    c.emit(b"\x8b\xf0\x0f\xb6\x05"); c.u32(d["key_frame"]); c.emit(b"\x0f\xb6\x0d"); c.u32(d["key_frame"]+1)
    c.emit(b"\x03\xc1\x69\xc0"); c.u32(gauge_h)
    c.emit(b"\x99\xb9"); c.u32(2*(FRAMES-1)); c.emit(b"\xf7\xf9\x50\x8b\xd0"); call(c, at["scale"])   # the fill, at 96 DPI
    c.emit(b"\x8b\xc6"); call(c, n["set_height"])
    c.emit(b"\x5a\xf7\xda\x81\xc2"); c.u32(gauge_y+gauge_h); call(c, at["scale"]); c.emit(b"\x8b\xc6"); call(c, n["set_top"])
    c.mark("out"); c.emit(b"\x61\xc3")
    code["refresh"] = c.finish()

    # timer(EBX form): the console's animation timer, made once, runs (key_tick moves the keys and the glass a
    # frame each KEY_MS).
    c = Code(at["timer"]); c.emit(b"\x60"); find(c, "key_timer"); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x85", "run")
    c.emit(b"\x8b\xcb\xb2\x01\xb8"); c.u32(n["timer"]); c.emit(b"\xff\x50"+bytes([CONTROL["create"]]))
    c.emit(b"\xc7\x40"+bytes([CONTROL["tag"]])); c.u32(TAGS["key_timer"])
    c.emit(b"\xc7\x40"+bytes([CONTROL["on_timer"]])); c.u32(at["key_tick"]); c.emit(b"\x89\x58"+bytes([CONTROL["on_timer"]+4]))
    c.emit(b"\x50\xba"); c.u32(KEY_MS); call(c, n["timer_interval"]); c.emit(b"\x58")
    c.mark("run"); c.emit(b"\xb2\x01"); call(c, n["timer_enabled"]); c.emit(b"\x61\xc3")
    code["timer"] = c.finish()

    # KEY 1 and KEY 2 (EAX form): a click turns that key the other way.
    for i, kind in enumerate(("key1", "key2")):
        c = Code(at[kind]); c.emit(b"\x60\x8b\xd8\x80\x35"); c.u32(d["key_target"]+i); c.emit(b"\x01"); call(c, at["timer"])
        c.emit(b"\x61\xc3")
        code[kind] = c.finish()

    # The glass over LAUNCH (EAX form): shut, a click lifts it; open, the click is LAUNCH.
    c = Code(at["glass"]); c.emit(b"\x80\x3d"); c.u32(d["glass_frame"]); c.emit(bytes([GLASS-1])); c.branch(b"\x0f\x84", at["launch"])
    c.emit(b"\x60\x8b\xd8"); flag(c, "glass_target", 1); call(c, at["timer"]); c.emit(b"\x61\xc3")
    code["glass"] = c.finish()

    # key_tick (EAX form, EDX the timer): each key and the glass a frame towards its target; armed with both keys
    # at ARM; the console redrawn when anything moved; the timer stops when everything is there.
    c = Code(at["key_tick"]); c.emit(b"\x60\x8b\xd8\x8b\xf2\x33\xff\x33\xed")             # EDI moved, EBP pending
    for k, (frame, target, top) in enumerate(((d["key_frame"], d["key_target"], FRAMES-1),
                                              (d["key_frame"]+1, d["key_target"]+1, FRAMES-1),
                                              (d["glass_frame"], d["glass_target"], GLASS-1))):
        c.emit(b"\x0f\xb6\x05"); c.u32(target); c.emit(b"\x6b\xc0"+bytes([top])+b"\x0f\xb6\x0d"); c.u32(frame)
        c.emit(b"\x3b\xc8"); c.branch(b"\x0f\x84", f"at{k}"); c.branch(b"\x0f\x8c", f"up{k}")
        c.emit(b"\x49"); c.branch(b"\xe9", f"store{k}")
        c.mark(f"up{k}"); c.emit(b"\x41")
        c.mark(f"store{k}"); c.emit(b"\x88\x0d"); c.u32(frame); c.emit(b"\x83\xcf\x01\x3b\xc8"); c.branch(b"\x0f\x84", f"at{k}")
        c.emit(b"\x83\xcd\x01")
        c.mark(f"at{k}")
    c.emit(b"\x33\xc0\x80\x3d"); c.u32(d["key_frame"]); c.emit(bytes([FRAMES-1])); c.branch(b"\x0f\x85", "armed")
    c.emit(b"\x80\x3d"); c.u32(d["key_frame"]+1); c.emit(bytes([FRAMES-1])+b"\x0f\x94\xc0")
    c.mark("armed"); c.emit(b"\xa2"); c.u32(d["armed"])
    c.emit(b"\x85\xff"); c.branch(b"\x0f\x84", "still"); call(c, at["refresh"])
    c.mark("still"); c.emit(b"\x85\xed"); c.branch(b"\x0f\x85", "out")
    c.emit(b"\x8b\xc6\x33\xd2"); call(c, n["timer_enabled"])
    c.mark("out"); c.emit(b"\x61\xc3")
    code["key_tick"] = c.finish()

    # WARHEAD (EAX form): the next warhead this year allows (A-BOMB always); its radii; the console, its line about
    # it and the marked zones redrawn.
    c = Code(at["warhead"]); c.emit(b"\x60\x8b\xd8\x0f\xb6\x05"); c.u32(d["kind"])
    c.mark("next"); c.emit(b"\x40\x83\xf8"+bytes([len(WARHEADS)])+b"\x72\x02\x33\xc0\x6b\xd0"+bytes([WARHEAD_SIZE]))
    c.emit(b"\x8b\x0d"); c.u32(doctrine["year"]); c.emit(b"\x8b\x09\x3b\x8a"); c.u32(d["warheads"]+16); c.branch(b"\x0f\x8c", "next")
    c.emit(b"\xa2"); c.u32(d["kind"]); call(c, at["setkind"])
    c.emit(b"\x0f\xb6\x15"); c.u32(d["kind"]); c.emit(b"\x6b\xd2"+bytes([WARHEAD_SIZE])+b"\x8b\x92"); c.u32(d["warheads"]+24)
    call(c, at["info"]); call(c, at["refresh"]); call(c, at["redraw"]); c.emit(b"\x61\xc3")
    code["warhead"] = c.finish()

    # aim(): the warheads' centres: the mark, then (a MIRV) enemy ships the player's side has contact on (seen or on
    # radar) within MIRV_YARDS of it and outside every earlier centre's kill radius, while warheads remain. [blasts].
    c = Code(at["aim"]); c.emit(b"\x60")
    for i in (0, 4, 8): c.emit(b"\xa1"); c.u32(d["target"]+i); c.emit(b"\xa3"); c.u32(d["centres"]+i)
    flag(c, "blasts", 1)
    c.emit(b"\x0f\xb6\x05"); c.u32(d["kind"]); c.emit(b"\x6b\xc0"+bytes([WARHEAD_SIZE])+b"\x8b\xa8"); c.u32(d["warheads"]+12)
    c.emit(b"\x33\xdb")                                                                  # EBP warheads, EBX the ship index
    c.mark("ship"); c.emit(b"\x0f\xb6\x05"); c.u32(d["blasts"]); c.emit(b"\x3b\xc5"); c.branch(b"\x0f\x8d", "out")
    c.emit(b"\xa1"); c.u32(n["ships"]); c.emit(b"\x8b\x00\x3b\x58\x08"); c.branch(b"\x0f\x8d", "out")
    c.emit(b"\x8b\xd3"); call(c, n["list_get"]); c.emit(b"\x43\x85\xc0"); c.branch(b"\x0f\x84", "ship"); c.emit(b"\x8b\xf0")
    c.emit(b"\x8b\x0d"); c.u32(n["side"]); c.emit(b"\x8b\x09\x39\x8e"); c.u32(SHIP["side"]); c.branch(b"\x0f\x84", "ship")
    c.emit(b"\x80\xbe"); c.u32(SHIP["kind"]); c.emit(bytes([LAND])); c.branch(b"\x0f\x84", "ship")
    c.emit(b"\x80\xbe"); c.u32(SHIP["out"]); c.emit(b"\x00"); c.branch(b"\x0f\x85", "ship")
    c.emit(b"\x83\xbe"); c.u32(SIGHTED["visual"]); c.emit(b"\x00"); c.branch(b"\x0f\x8f", "contact")
    c.emit(b"\x83\xbe"); c.u32(SIGHTED["radar"]); c.emit(b"\x00"); c.branch(b"\x0f\x8e", "ship")
    c.mark("contact"); c.emit(b"\x8d\x86"); c.u32(SHIP["position"]); c.emit(b"\xba"); c.u32(d["target"]); call(c, at["distance"])
    c.emit(b"\x3d"); c.u32(MIRV_YARDS); c.branch(b"\x0f\x8f", "ship")
    c.emit(b"\x33\xff")                                                                  # EDI: the centres so far
    c.mark("covered"); c.emit(b"\x0f\xb6\x05"); c.u32(d["blasts"]); c.emit(b"\x3b\xf8"); c.branch(b"\x0f\x8d", "add")
    c.emit(b"\x6b\xd7\x0c\x81\xc2"); c.u32(d["centres"]); c.emit(b"\x8d\x86"); c.u32(SHIP["position"]); call(c, at["distance"])
    c.emit(b"\x47\x3b\x05"); c.u32(d["kill"]); c.branch(b"\x0f\x8e", "ship"); c.branch(b"\xe9", "covered")
    c.mark("add"); c.emit(b"\x0f\xb6\x05"); c.u32(d["blasts"]); c.emit(b"\x6b\xc0\x0c\x05"); c.u32(d["centres"])
    for i in (0, 4, 8): c.emit(b"\x8b\x8e"); c.u32(SHIP["position"]+i); c.emit(b"\x89\x48"+bytes([i]))
    c.emit(b"\xfe\x05"); c.u32(d["blasts"]); c.branch(b"\xe9", "ship")
    c.mark("out"); c.emit(b"\x61\xc3")
    code["aim"] = c.finish()

    # FormShow, after its first set-up call (EBX form): the button (enabled when the nation can strike) and the
    # console, found or made; a new battle starts with no target and no effect.
    c = Code(at["show"]); c.emit(b"\x60")
    find(c, "nuke"); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x85", "have_nuke")
    c.emit(b"\x8b\x83"); c.u32(FORM["last_button"]); c.emit(b"\x8b\x50"+bytes([CONTROL["height"]])+b"\x52")   # height
    c.emit(b"\x8d\x14\x12\x52\x8b\x50"+bytes([CONTROL["top"]])+b"\x52")                                   # width, top
    c.emit(b"\x8b\x50"+bytes([CONTROL["left"]])+b"\x03\x50"+bytes([CONTROL["width"]])+b"\x83\xc2"+bytes([NUKE_GAP])+b"\x52")
    create(c, "nuke", FORM["toolbar"])
    caption(c, "nuke"); on_click(c, at["nuke"]); bold_red(c)
    c.emit(b"\x8d\x86"); c.u32(CONTROL["hint"]); c.emit(b"\xba"); c.u32(T["hint"]); call(c, n["assign"])
    c.emit(b"\xb2\x01\x8b\xc6"); call(c, n["set_show_hint"])
    c.emit(b"\x8b\xc6")
    c.mark("have_nuke"); c.emit(b"\x8b\xf8"); player(c); call(c, at["available"])
    c.emit(b"\x8b\xd0\x8b\xc7"); virtual(c, CONTROL["set_enabled"])
    find(c, "console"); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x85", "have_console")
    c.emit(b"\xba"); c.u32(CONSOLE[1]); call(c, at["scale"]); c.emit(b"\x52")                             # height
    c.emit(b"\xba"); c.u32(CONSOLE[0]); call(c, at["scale"]); c.emit(b"\x52")                             # width
    c.emit(b"\x8b\x83"); c.u32(FORM["toolbar"]); c.emit(b"\x8b\x48"+bytes([CONTROL["top"]])+b"\x03\x48"+bytes([CONTROL["height"]]))
    c.emit(b"\x83\xc1"+bytes([GAP])+b"\x51")                                                              # top
    # left: centred under NUKE (EDI), kept inside the window (the toolbar's width); EDX the console's width
    c.emit(b"\x8b\x4f"+bytes([CONTROL["width"]])+b"\xd1\xe9\x03\x4f"+bytes([CONTROL["left"]])+b"\x8b\xc2\xd1\xe8\x2b\xc8")
    c.emit(b"\x8b\x83"); c.u32(FORM["toolbar"]); c.emit(b"\x8b\x40"+bytes([CONTROL["width"]])+b"\x2b\xc2")
    c.emit(b"\x3b\xc8\x7e\x02\x8b\xc8\x85\xc9\x7d\x02\x33\xc9\x51")
    create(c, "console", "form"); c.emit(b"\x8b\xfe"); call(c, at["load"])
    create(c, "backdrop", "console", LAYOUT["backdrop"]); stretched(c)
    c.emit(b"\x8b\x15"); c.u32(d["pictures"]); c.emit(b"\x8b\xc6"); call(c, n["image_picture"])
    for kind in ("gauge_target", "gauge_arm"):
        create(c, kind, "console", LAYOUT[kind]); shape_colours(c, PALETTE["fill"], PALETTE["fill"])
    for kind in ("ssbns", "warhead", "target", "status"):
        create(c, kind, "console", LAYOUT[kind]); styled(c, PALETTE["value"], LABEL_PT)
    # The message line wraps in its box (two lines, clear of ABORT): AutoSize off and WordWrap on before its font
    # is set, which would otherwise size it to its text and run long messages under ABORT.
    create(c, "info", "console", LAYOUT["info"])
    c.emit(b"\x33\xd2\x8b\xc6"); virtual(c, CONTROL["set_autosize"]); c.emit(b"\xb2\x01\x8b\xc6"); call(c, n["label_wrap"])
    styled(c, PALETTE["info"], INFO_PT); caption(c, "picking")
    for kind, handler in (("key1", "key1"), ("key2", "key2"), ("launch", "glass")):   # pictures; a click works them
        create(c, kind, "console", LAYOUT[kind]); stretched(c); on_click(c, at[handler]); hand(c)
    for kind, handler in (("tgt", "nuke"), ("cancel", "cancel"), ("warhead_hit", "warhead")):   # click areas
        create(c, kind, "console", LAYOUT[kind]); on_click(c, at[handler]); hand(c)
        c.emit(b"\x8b\x86"); c.u32(CONTROL["shape_pen"]); c.emit(b"\xb2\x05"); call(c, n["pen_style"])        # psClear
        c.emit(b"\x8b\x86"); c.u32(CONTROL["shape_brush"]); c.emit(b"\xb2\x01"); call(c, n["brush_style"])    # bsClear
    c.emit(b"\x8b\xc7")
    c.mark("have_console"); c.emit(b"\x33\xd2"); call(c, n["set_visible"])
    for name in ("pick", "has_target", "active", "armed", "glass_frame", "glass_target", "kind"): flag(c, name, 0)
    c.emit(b"\x33\xc0"); call(c, at["setkind"])                                             # each battle starts on A-BOMB
    c.emit(b"\xc7\x05"); c.u32(d["key_frame"]); c.u32(0)                                    # both keys' frames and targets
    find(c, "key_timer"); c.emit(b"\x85\xc0\x74\x07\x33\xd2"); call(c, n["timer_enabled"])   # jz past: a new battle's key
    call(c, at["refresh"])
    c.emit(b"\x61"+bytes.fromhex(ORIGINALS["form_show"])); c.branch(b"\xe9", n["form_show"]+6)
    code["show"] = c.finish()

    # NUKE (EAX form): available and not yet struck this battle -> the map picks the target.
    c = Code(at["nuke"]); c.emit(b"\x60\x8b\xd8"); player(c); call(c, at["available"]); c.emit(b"\x84\xc0")
    c.branch(b"\x0f\x85", "can"); message(c, "unavailable"); c.branch(b"\xe9", "out")
    c.mark("can"); call(c, at["used"]); c.emit(b"\x80\x3d"); c.u32(doctrine["armageddon"]); c.emit(b"\x00")
    c.branch(b"\x0f\x85", "pick"); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "pick"); message(c, "spent"); c.branch(b"\xe9", "out")
    c.mark("pick"); flag(c, "pick", 1); flag(c, "has_target", 0)
    c.emit(b"\x8b\x83"); c.u32(FORM["globe"]); c.emit(b"\x66\xba"+struct.pack("<H", CROSS)); call(c, n["set_cursor"])
    c.emit(b"\xba"); c.u32(T["picking"]); call(c, at["info"])
    find(c, "console"); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "drawn"); c.emit(b"\xb2\x01"); call(c, n["set_visible"])
    c.mark("drawn"); call(c, at["redraw"]); call(c, at["refresh"])
    c.mark("out"); c.emit(b"\x61\xc3")
    code["nuke"] = c.finish()

    # GlobeMouseUp at its pick-location check (EBX form, ESI x, EDI y): our pick takes the click, else native.
    c = Code(at["pick"]); c.emit(b"\x80\x3d"); c.u32(d["pick"]); c.emit(b"\x00"); c.branch(b"\x0f\x84", "native")
    c.emit(b"\x60\x68"); c.u32(d["target"]); c.emit(b"\x8b\x83"); c.u32(FORM["globe"]); c.emit(b"\x8b\x80"); c.u32(GLOBE["projection"])
    c.emit(b"\x8b\xcf\x8b\xd6"); call(c, n["device_to_ll"]); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "done")
    flag(c, "pick", 0); flag(c, "has_target", 1)
    c.emit(b"\x8b\x83"); c.u32(FORM["globe"]); c.emit(b"\x33\xd2"); call(c, n["set_cursor"])
    c.emit(b"\xba"); c.u32(T["ready"]); call(c, at["info"]); call(c, at["redraw"]); call(c, at["refresh"])
    c.mark("done"); c.emit(b"\x61"); c.branch(b"\xe9", n["pick_done"])
    c.mark("native"); c.emit(bytes.fromhex(ORIGINALS["pick"][:14])); c.branch(b"\x0f\x84", n["pick_done"]); c.branch(b"\xe9", n["pick_native"])
    code["pick"] = c.finish()

    # LAUNCH (EAX form): target, key, the battle's strike, the treaty and the funds; then pay, mark, blast, show.
    c = Code(at["launch"]); c.emit(b"\x60\x8b\xd8\x80\x3d"); c.u32(d["has_target"]); c.emit(b"\x00"); c.branch(b"\x0f\x85", "target")
    message(c, "no_target"); c.branch(b"\xe9", "out")
    c.mark("target"); c.emit(b"\x80\x3d"); c.u32(d["armed"]); c.emit(b"\x00"); c.branch(b"\x0f\x85", "armed")
    message(c, "unarmed"); c.branch(b"\xe9", "out")
    c.mark("armed"); call(c, at["used"]); c.emit(b"\x80\x3d"); c.u32(doctrine["armageddon"]); c.emit(b"\x00")   # [player]
    c.branch(b"\x0f\x85", "unlimited"); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "unlimited"); message(c, "spent"); c.branch(b"\xe9", "out")
    c.mark("unlimited"); player(c); c.emit(b"\x8b\xf0\x85\xf6"); c.branch(b"\x0f\x84", "out")    # ESI the player's nation
    call(c, doctrine["lookup"])
    c.emit(b"\xc1\xe8\x08\x25\xff\x00\x00\x00"); c.branch(b"\x0f\x84", "no_treaty")             # banned to that year
    c.emit(b"\x05"); c.u32(1900); c.emit(b"\x8b\x0d"); c.u32(doctrine["year"]); c.emit(b"\x3b\x01"); c.branch(b"\x0f\x8c", "no_treaty")
    message(c, "treaty"); c.branch(b"\xe9", "out")
    c.mark("no_treaty"); c.emit(b"\x0f\xb6\x3d"); c.u32(d["kind"]); c.emit(b"\x6b\xff"+bytes([WARHEAD_SIZE])+b"\x8b\xbf")
    c.u32(d["warheads"]); c.emit(b"\x39\xbe"); c.u32(NATION["funds"]); c.branch(b"\x0f\x8d", "pay")   # EDI its price
    message(c, "funds"); c.branch(b"\xe9", "out")
    c.mark("pay"); c.emit(b"\x29\xbe"); c.u32(NATION["funds"])
    c.emit(b"\x6a"+bytes([doctrine_rules.MISSILE])+b"\x8b\xd6"); call(c, doctrine["first"]); c.emit(b"\x83\xc4\x04")
    c.emit(b"\xc7\x05"); c.u32(doctrine["used"]); c.u32(1)
    call(c, at["mark"]); call(c, at["aim"]); flag(c, "caught", 0); c.emit(b"\x33\xff")     # each warhead's blast
    c.mark("warhead"); c.emit(b"\x0f\xb6\x05"); c.u32(d["blasts"]); c.emit(b"\x3b\xf8"); c.branch(b"\x0f\x8d", "log")
    c.emit(b"\x6b\xcf\x0c\x81\xc1"); c.u32(d["centres"]); call(c, at["blast"]); c.emit(b"\x47"); c.branch(b"\xe9", "warhead")
    c.mark("log"); c.emit(b"\x8b\x0d"); c.u32(d["player"]); c.emit(b"\x85\xc9"); c.branch(b"\x0f\x84", "effect")
    c.emit(b"\x0f\xb6\x05"); c.u32(d["kind"]); c.emit(b"\x6b\xc0"+bytes([WARHEAD_SIZE])+b"\x8b\x90"); c.u32(d["warheads"]+28)
    c.emit(b"\x80\x3d"); c.u32(d["caught"]); c.emit(b"\x00\x75\x05\xba"); c.u32(T["empty"])
    c.emit(b"\xa1"); c.u32(n["battle_log"]); c.emit(b"\x8b\x38\xff\x57\x40")
    c.mark("effect")
    c.emit(b"\xc7\x05"); c.u32(d["step"]); c.u32(1); flag(c, "active", 1); flag(c, "has_target", 0)
    find(c, "timer"); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x85", "have_timer")
    c.emit(b"\x8b\xcb\xb2\x01\xb8"); c.u32(n["timer"]); c.emit(b"\xff\x50"+bytes([CONTROL["create"]]))
    c.emit(b"\xc7\x40"+bytes([CONTROL["tag"]])); c.u32(TAGS["timer"])
    c.emit(b"\xc7\x40"+bytes([CONTROL["on_timer"]])); c.u32(at["tick"]); c.emit(b"\x89\x58"+bytes([CONTROL["on_timer"]+4]))
    c.emit(b"\x50\xba"); c.u32(TIMER_MS); call(c, n["timer_interval"]); c.emit(b"\x58")
    c.mark("have_timer"); c.emit(b"\xb2\x01"); call(c, n["timer_enabled"])
    safe(c)                                                                            # the keys back to SAFE, the glass shut
    c.emit(b"\x80\x3d"); c.u32(doctrine["armageddon"]); c.emit(b"\x00"); c.branch(b"\x0f\x85", "button")
    find(c, "nuke"); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "button"); c.emit(b"\x33\xd2"); virtual(c, CONTROL["set_enabled"])
    c.mark("button"); hide_console(c); call(c, at["redraw"]); call(c, at["refresh"])
    c.mark("out"); c.emit(b"\x61\xc3")
    code["launch"] = c.finish()

    # ABORT (EAX form): no target, the keys back to SAFE and the glass shut, the console away.
    c = Code(at["cancel"]); c.emit(b"\x60\x8b\xd8"); flag(c, "pick", 0); flag(c, "has_target", 0)
    c.emit(b"\x8b\x83"); c.u32(FORM["globe"]); c.emit(b"\x33\xd2"); call(c, n["set_cursor"]); safe(c)
    hide_console(c); call(c, at["redraw"]); call(c, at["refresh"]); c.emit(b"\x61\xc3")
    code["cancel"] = c.finish()

    # The timer (EAX form, EDX the timer): one effect step; the last stops it.
    c = Code(at["tick"]); c.emit(b"\x60\x8b\xd8\xff\x05"); c.u32(d["step"]); c.emit(b"\x83\x3d"); c.u32(d["step"]); c.emit(bytes([GLOW]))
    c.branch(b"\x0f\x8c", "draw"); flag(c, "active", 0); c.emit(b"\x8b\xc2\x33\xd2"); call(c, n["timer_enabled"])
    c.mark("draw"); call(c, at["redraw"]); c.emit(b"\x61\xc3")
    code["tick"] = c.finish()

    # units(EAX yards) -> EAX globe units. distance(EAX place, EDX place) -> EAX yards.
    c = Code(at["units"]); c.emit(b"\x50\xdb\x04\x24\x83\xc4\x04\x83\xec\x0c\xdb\x3c\x24\xb0"+bytes([YARDS])); call(c, n["units"]); c.emit(b"\xc3")
    code["units"] = c.finish()
    c = Code(at["distance"]); call(c, n["ll_distance"]); c.emit(b"\xb2"+bytes([YARDS])); call(c, n["to_unit"])
    c.emit(b"\x50\xdb\x1c\x24\x58\xc3")
    code["distance"] = c.finish()
    # ring(EDI globe, EDX place, ECX yards): a circle with the canvas pen. Keeps EBX, ESI, EDI.
    c = Code(at["ring"]); c.emit(b"\x53\x52\x8b\xc1"); call(c, at["units"]); c.emit(b"\x8b\xc8\x5a\x8b\x1f\x68\x90\x00\x00\x00\x8b\xc7")
    c.emit(b"\xff\x93"); c.u32(GLOBE["circle"]); c.emit(b"\x5b\xc3")
    code["ring"] = c.finish()
    # disc(EDI globe, ECX yards): a polygon round the centre, filled with the canvas brush.
    c = Code(at["disc"]); c.emit(b"\x60\x8b\xc1"); call(c, at["units"]); c.emit(b"\x8b\xe8\x33\xdb")    # EBP units, EBX k
    c.mark("point"); c.emit(b"\x6b\xc3"+bytes([360//POINTS])+b"\x50\xdb\x04\x24\xd9\x1c\x24"); call(c, n["bearing"])
    c.emit(b"\x8b\xd0\x6b\xcb\x0c\x81\xc1"); c.u32(d["points"]); c.emit(b"\x51\x8b\xcd\xb8"); c.u32(d["centre"]); call(c, n["point_at"])
    c.emit(b"\x43\x83\xfb"+bytes([POINTS])); c.branch(b"\x0f\x8c", "point")
    c.emit(b"\xba"); c.u32(d["points"]); c.emit(b"\xb9"); c.u32(POINTS-1); c.emit(b"\x8b\xc7\x8b\x18\xff\x93"); c.u32(GLOBE["polygon"])
    c.emit(b"\x61\xc3")
    code["disc"] = c.finish()

    def pen(c, style, width, colour=None):   # ESI the canvas; colour None: popped from the stack
        c.emit(b"\x8b\x46"+bytes([CANVAS["pen"]])+b"\xb2"+bytes([style])); call(c, n["pen_style"])
        c.emit(b"\x8b\x46"+bytes([CANVAS["pen"]])+b"\xba"); c.u32(width); call(c, n["pen_width"])
        c.emit(b"\x8b\x46"+bytes([CANVAS["pen"]]))
        if colour is None: c.emit(b"\x5a")
        else: c.emit(b"\xba"); c.u32(colour)
        call(c, n["pen_color"])

    def grown(c, steps, radius):   # ECX = [radius]*min(step, steps)/steps
        c.emit(b"\xa1"); c.u32(d["step"]); c.emit(b"\x83\xf8"+bytes([steps])+b"\x7e\x05\xb8"); c.u32(steps)
        c.emit(b"\x0f\xaf\x05"); c.u32(d[radius]); c.emit(b"\x99\xb9"); c.u32(steps); c.emit(b"\xf7\xf9\x8b\xc8")

    # GlobeRender, after its day and night shadow ([ebp-4] the form): the marked target's zones, then a blast's
    # shock ring and fireball. The canvas pen and brush are put back as they were.
    c = Code(at["render"]); c.emit(b"\x60\x8b\x5d\xfc\x80\x3d"); c.u32(d["has_target"]); c.emit(b"\x00"); c.branch(b"\x0f\x85", "work")
    c.emit(b"\x80\x3d"); c.u32(d["active"]); c.emit(b"\x00"); c.branch(b"\x0f\x84", "out")
    c.mark("work"); c.emit(b"\x8b\xbb"); c.u32(FORM["globe"]); c.emit(b"\x8b\xb7"); c.u32(GLOBE["renderer"])
    for getter, offset in (("pen_get_color", 0), ("pen_get_width", 4), ("pen_get_style", 8)):
        c.emit(b"\x8b\x46"+bytes([CANVAS["pen"]])); call(c, n[getter]); c.emit(b"\xa3"); c.u32(d["pen"]+offset)
    for getter, offset in (("brush_get_color", 0), ("brush_get_style", 4)):
        c.emit(b"\x8b\x46"+bytes([CANVAS["brush"]])); call(c, n[getter]); c.emit(b"\xa3"); c.u32(d["brush"]+offset)
    c.emit(b"\x8b\x46"+bytes([CANVAS["brush"]])+b"\xb2\x01"); call(c, n["brush_style"])          # bsClear
    c.emit(b"\x80\x3d"); c.u32(d["has_target"]); c.emit(b"\x00"); c.branch(b"\x0f\x84", "blast")
    pen(c, 1, 1, COLOURS["red"])                                                          # psDash: zones to come
    for radius in ("kill", "ring"):
        c.emit(b"\xba"); c.u32(d["target"]); c.emit(b"\x8b\x0d"); c.u32(d[radius]); call(c, at["ring"])
    c.mark("blast"); c.emit(b"\x80\x3d"); c.u32(d["active"]); c.emit(b"\x00"); c.branch(b"\x0f\x84", "restore")
    c.emit(b"\x33\xed")                                                                   # EBP: each warhead's centre
    c.mark("centre"); c.emit(b"\x0f\xb6\x05"); c.u32(d["blasts"]); c.emit(b"\x3b\xe8"); c.branch(b"\x0f\x8d", "restore")
    c.emit(b"\x6b\xc5\x0c\x05"); c.u32(d["centres"])
    for i in (0, 4, 8): c.emit(b"\x8b\x48"+bytes([i])+b"\x89\x0d"); c.u32(d["centre"]+i)
    # The shock ring: orange, it grows to the hit radius in SHOCK steps and stays as a dark red ring.
    c.emit(b"\xba"); c.u32(COLOURS["orange"]); c.emit(b"\x83\x3d"); c.u32(d["step"]); c.emit(bytes([SHOCK]))
    c.branch(b"\x0f\x8c", "ring_colour"); c.emit(b"\xba"); c.u32(COLOURS["dark"])
    c.mark("ring_colour"); c.emit(b"\x52"); pen(c, 0, 3)
    grown(c, SHOCK, "ring"); c.emit(b"\xba"); c.u32(d["centre"]); call(c, at["ring"])
    # The fireball over it: white, yellow, orange, then dark red; it grows to the kill radius in FLASH steps.
    c.emit(b"\xa1"); c.u32(d["step"])
    for limit, colour in ((2, "white"), (FLASH, "yellow"), (SHOCK, "orange")):
        c.emit(b"\xba"); c.u32(COLOURS[colour]); c.emit(b"\x83\xf8"+bytes([limit])); c.branch(b"\x0f\x8c", "fire_colour")
    c.emit(b"\xba"); c.u32(COLOURS["dark"])
    c.mark("fire_colour"); c.emit(b"\x52\x52")
    c.emit(b"\x8b\x46"+bytes([CANVAS["brush"]])+b"\xb2\x00"); call(c, n["brush_style"])          # bsSolid
    c.emit(b"\x8b\x46"+bytes([CANVAS["brush"]])+b"\x5a"); call(c, n["brush_color"])
    pen(c, 0, 1); grown(c, FLASH, "kill"); call(c, at["disc"])
    c.emit(b"\x45"); c.branch(b"\xe9", "centre")
    c.mark("restore")
    for setter, offset in (("pen_color", 0), ("pen_width", 4)):
        c.emit(b"\x8b\x46"+bytes([CANVAS["pen"]])+b"\x8b\x15"); c.u32(d["pen"]+offset); call(c, n[setter])
    c.emit(b"\x8b\x46"+bytes([CANVAS["pen"]])+b"\x8a\x15"); c.u32(d["pen"]+8); call(c, n["pen_style"])
    c.emit(b"\x8b\x46"+bytes([CANVAS["brush"]])+b"\x8b\x15"); c.u32(d["brush"]); call(c, n["brush_color"])
    c.emit(b"\x8b\x46"+bytes([CANVAS["brush"]])+b"\x8a\x15"); c.u32(d["brush"]+4); call(c, n["brush_style"])
    c.mark("out"); c.emit(b"\x61"+bytes.fromhex(n["render_original"])); c.branch(b"\xe9", n["render"]+5)
    code["render"] = c.finish()

    # available(EAX nation) -> AL: the Ballistic missile submarines research and an SSBN in service; [count] the
    # SSBNs in service (the console's SSBNs ON STATION). Keeps EBX..EBP.
    c = Code(at["available"]); c.emit(b"\x53\x56\x57\x33\xff\x8b\xf0\x85\xf6"); c.branch(b"\x0f\x84", "done")
    c.emit(b"\xba"); c.u32(tree.SSBN); call(c, n["has_research"]); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "done")
    c.emit(b"\x33\xdb")
    c.mark("sub"); c.emit(b"\x8b\x86"); c.u32(NATION["subs"]); c.emit(b"\x3b\x58\x08"); c.branch(b"\x0f\x8d", "done")
    c.emit(b"\x8b\xd3\x8b\xc6"); call(c, n["get_sub"]); c.emit(b"\x43\x85\xc0"); c.branch(b"\x0f\x84", "sub")
    c.emit(b"\x80\x78"+bytes([SUB["sunk"]])+b"\x00"); c.branch(b"\x0f\x85", "sub")
    c.emit(b"\x83\x78"+bytes([SUB["months"]])+b"\x00"); c.branch(b"\x0f\x8f", "sub")
    c.emit(b"\x8b\x40"+bytes([SUB["name"]])); call(c, is_kind); c.emit(b"\x83\xf8\x02"); c.branch(b"\x0f\x85", "sub")
    c.emit(b"\x47"); c.branch(b"\xe9", "sub")
    c.mark("done"); c.emit(b"\x89\x3d"); c.u32(d["count"]); c.emit(b"\x33\xc0\x85\xff\x0f\x95\xc0\x5f\x5e\x5b\xc3")
    code["available"] = c.finish()

    def player_ships(c):   # loop head: the next ship of the player's side in ESI (EBX the index); "out" ends it
        c.mark("ship"); c.emit(b"\xa1"); c.u32(n["ships"]); c.emit(b"\x8b\x00\x3b\x58\x08"); c.branch(b"\x0f\x8d", "out")
        c.emit(b"\x8b\xd3"); call(c, n["list_get"]); c.emit(b"\x43\x85\xc0"); c.branch(b"\x0f\x84", "ship")
        c.emit(b"\x8b\xf0\x8b\x0d"); c.u32(n["side"]); c.emit(b"\x8b\x09\x39\x88"); c.u32(SHIP["side"]); c.branch(b"\x0f\x85", "ship")

    # used() -> AL: a ship of the player's side has this battle's mark. [player]: the first ship of that side.
    c = Code(at["used"]); c.emit(b"\x53\x56\x57\xc7\x05"); c.u32(d["player"]); c.u32(0); c.emit(b"\x33\xff\x33\xdb")
    player_ships(c)
    c.emit(b"\x83\x3d"); c.u32(d["player"]); c.emit(b"\x00\x75\x06\x89\x35"); c.u32(d["player"])   # jnz past the store
    c.emit(b"\x8b\xc6"); call(c, ext); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "ship")
    c.emit(b"\xf7\x00"); c.u32(STRIKE_BIT); c.branch(b"\x0f\x84", "ship"); c.emit(b"\x47")
    c.mark("out"); c.emit(b"\x8b\xc7\x5f\x5e\x5b\xc3")
    code["used"] = c.finish()
    # mark(): this battle's strike is spent, on every ship of the player's side with extension data.
    c = Code(at["mark"]); c.emit(b"\x53\x56\x33\xdb")
    player_ships(c)
    c.emit(b"\x8b\xc6"); call(c, ext); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "ship"); c.emit(b"\x81\x08"); c.u32(STRIKE_BIT)
    c.branch(b"\xe9", "ship")
    c.mark("out"); c.emit(b"\x5e\x5b\xc3")
    code["mark"] = c.finish()

    # blast(ECX a warhead's centre, a TPointLL): every ship within [ring] of it takes the nuclear hit, and within
    # [kill] it sinks (no buoyancy and a sinking timer of one, as the game's debug Sink: CheckSunk takes it down at
    # its next minute); air formations within [ring] are lost. EDI the player's nation index (the firer). [caught]
    # is set when anything was within reach.
    c = Code(at["blast"]); c.emit(b"\x60\x89\x0d"); c.u32(d["here"])
    c.emit(b"\x33\xff\xa1"); c.u32(d["player"]); c.emit(b"\x85\xc0\x74\x03\x8b\x78"+bytes([SHIP["nation"]]))
    c.emit(b"\x33\xdb")
    c.mark("ship"); c.emit(b"\xa1"); c.u32(n["ships"]); c.emit(b"\x8b\x00\x3b\x58\x08"); c.branch(b"\x0f\x8d", "air")
    c.emit(b"\x8b\xd3"); call(c, n["list_get"]); c.emit(b"\x43\x85\xc0"); c.branch(b"\x0f\x84", "ship"); c.emit(b"\x8b\xf0")
    c.emit(b"\x80\xbe"); c.u32(SHIP["kind"]); c.emit(bytes([LAND])); c.branch(b"\x0f\x84", "ship")
    c.emit(b"\x80\xbe"); c.u32(SHIP["out"]); c.emit(b"\x00"); c.branch(b"\x0f\x85", "ship")
    c.emit(b"\x8d\x86"); c.u32(SHIP["position"]); c.emit(b"\x8b\x15"); c.u32(d["here"]); call(c, at["distance"])
    c.emit(b"\x3b\x05"); c.u32(d["ring"]); c.branch(b"\x0f\x8f", "ship")
    c.emit(b"\x50"); flag(c, "caught", 1)                                                     # the distance, kept
    c.emit(b"\x6a"+bytes([NUCLEAR_CALIBRE])+b"\x8b\xd7\xb9"); c.u32(T["strike"]); c.emit(b"\x8b\xc6"); call(c, strike)
    c.emit(b"\x58\x3b\x05"); c.u32(d["kill"]); c.branch(b"\x0f\x8f", "ship")
    c.emit(b"\xc7\x86"); c.u32(SINK["buoyancy"]); c.u32(0); c.emit(b"\xc7\x86"); c.u32(SINK["timer"]); c.u32(1)
    c.branch(b"\xe9", "ship")
    c.mark("air"); c.emit(b"\x33\xdb")
    c.mark("unit"); c.emit(b"\xa1"); c.u32(n["air"]); c.emit(b"\x8b\x00\x3b\x58\x08"); c.branch(b"\x0f\x8d", "out")
    c.emit(b"\x8b\xd3"); call(c, n["list_get"]); c.emit(b"\x43\x85\xc0"); c.branch(b"\x0f\x84", "unit"); c.emit(b"\x8b\xf0")
    c.emit(b"\x8b\x4e"+bytes([AIR["count"]])+b"\x2b\x8e"); c.u32(AIR["destroyed"]); c.emit(b"\x85\xc9"); c.branch(b"\x0f\x8e", "unit")
    c.emit(b"\x51\x8d\x46"+bytes([AIR["position"]])+b"\x8b\x15"); c.u32(d["here"]); call(c, at["distance"]); c.emit(b"\x59")
    c.emit(b"\x3b\x05"); c.u32(d["ring"]); c.branch(b"\x0f\x8f", "unit")
    flag(c, "caught", 1)
    c.emit(b"\x6a"+bytes([AA_LOSS])+b"\x8b\xd1\xb1"+bytes([DESTROYED])+b"\x8b\xc6"); call(c, n["inflict"]); c.branch(b"\xe9", "unit")
    c.mark("out"); c.emit(b"\x61\xc3")
    code["blast"] = c.finish()

    # setkind(EAX a warhead): its kill and hit radii.
    c = Code(at["setkind"]); c.emit(b"\x6b\xc0"+bytes([WARHEAD_SIZE])+b"\x8b\x88"); c.u32(d["warheads"]+4)
    c.emit(b"\x89\x0d"); c.u32(d["kill"]); c.emit(b"\x8b\x88"); c.u32(d["warheads"]+8); c.emit(b"\x89\x0d"); c.u32(d["ring"])
    c.emit(b"\xc3")
    code["setkind"] = c.finish()

    names = b"".join(struct.pack("<I", T["pic_"+name]) for name in PICTURES)      # load's list of file names
    warheads = b"".join(struct.pack("<8I", price, kill, ring, count, year, T[f"name{i}"], T[f"about{i}"], T[f"log{i}"])
                        for i, (_, price, kill, ring, count, year) in enumerate(WARHEADS))
    blocks = [dict(name="Nuclear strike: state", address=data, bytes="00"*DATA["names"]),
              dict(name="Nuclear strike: picture names", address=d["names"], bytes=names.hex()),
              dict(name="Nuclear strike: warheads", address=d["warheads"], bytes=warheads.hex()),
              dict(name="Nuclear strike: texts", address=text_page, bytes=bytes(text_bytes).hex())]
    for name, body in code.items():
        table = CONSOLE_CODE if name in CONSOLE_CODE else CODE
        order = sorted(table, key=table.get)
        room = table[order[order.index(name)+1]]-table[name]
        if len(body) > room: raise ValueError(f"Nuclear strike code exceeds its reservation: {name} ({len(body):#x} > {room:#x})")
        blocks.append(dict(name="Nuclear strike: "+name, address=at[name], bytes=body.hex()))
    def jump(site, target, size): return b"\xe9"+struct.pack("<i", target-site-5)+b"\x90"*(size-5)
    plans = [patch("Nuclear strike: the NUKE button", n["form_show"], bytes.fromhex(ORIGINALS["form_show"]),
                   jump(n["form_show"], at["show"], 6)),
             patch("Nuclear strike: the effect on the map", n["render"], bytes.fromhex(n["render_original"]),
                   jump(n["render"], at["render"], 5)),
             patch("Nuclear strike: the target on the map", n["pick"], bytes.fromhex(ORIGINALS["pick"]),
                   jump(n["pick"], at["pick"], 13))]
    return blocks, plans
