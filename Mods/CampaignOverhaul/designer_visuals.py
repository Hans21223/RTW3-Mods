"""Guarded large-hull visual scale and designer-only gun foreground rendering.

The native geometry factor falls from its last class-specific value to 20 at
101,000t. Preserve the entire original range; extend visual size by D^(1/3).
Saved drawings stay explicit. A native context-menu command can reset only an
old hull outline, retaining fitted weapons, equipment and superstructure. A second
command draws a new superstructure (6 layers and funnels) from the game's own AI
design template closest to the design, scaled to its hull.
"""
import hashlib
from pathlib import Path
import struct
import modern_research as audit
from campaign_security import Code
from hull_rules import patch

REFERENCE = 0x301000
BOUNDARY = 100900
MAXIMUM = 280000
STRIDE = MAXIMUM // 1000 + 1
ANCHORS = (27, 27, 24, 29, 29, 27, 29, 29, 29, 32, 32, 29)
WINDOWS = (
    (0x952908, 2258, "b32669c8eb2b61e9c7c7a0ba98483cf8c3c8e3a8c011c2c96736d96f3f7e1fdf"),
    (0x950318, 240, "7fb0b68cf8c96829e88a9b2a32192b29753594c23126fd14ae63723aac2d841f"),
    (0x91aae8, 113, "37101e090c20333fbc11c456a17e92ce3efe6ae2540426b13f3fd8c0ef14e370"),
    (0x5ce434, 21, "e487f064e09841644161a3e38db549c66832afbe5b40faa39d452ea3b2747e66"),
    (0x5f39e8, 132, "645f707dd8d0ca7cff514be263260459c055f6d9326c22e8353afc3c119e7f9c"),
    (0x5e765c, 30, "5cb62aac5c1d7d11da07cd5dbcef3718a4fe10b4a4b62fbaffaefd5f0b6f8489"),
    (0x83e1bc, 369, "34a88b24b2798fe6ed0a9d1e001674cc19c5dc4bcafec0d427eca9db5e761df8"),
    (0x840d78, 288, "5bd2389beeb16d27cb95fe2258f8ff11e59ae250777c5c30948c2eec64d64a71"),
    (0x840d2c, 76, "10cfd87437ff6236d141f24afb261d311f78482fe6f8370c1d241448e6fb354d"),
    (0x83f300, 220, "b987a30c220262f53ed149805c877fd3552f450f0f109378726f0003fd4965a8"),
    (0x83f22c, 212, "609aab80a43354b57f40dd4d42d7ba4d768f731e47e5b94be2c9dff318fab76a"),   # missile mounts
    (0x52729c, 132, "9646bdddf036eb19c126d1fb228ea7b5a86aa5cc164e821ee3627afbb7c3a81f"),
    (0x52af2c, 32, "e6769f79674b299448dd3efc6f0576e4512ee57cd521e20cda129671a1e8d8f3"),
    (0x52a91c, 116, "175f1359ae57a062a2274e559a9c12ae2bd79edc91a1b1487f2450c0a6480821"),
    (0x52a9e4, 116, "89b72c7fbb6c46f866bcd384288b8bffd7b0120d0ddc8952e6f260cb266af261"),
    (0x842e58, 156, "d03bcd84f3fa26c6be0247f3b4133dcadfa70a13834bb29b99dc2f4ddda28620"),   # superstructure/funnel layout
)
# AI design templates (Data/IDes/*.tdf) by ShipType. CV and CVL are left out: the native carrier tools draw their
# flight decks. KE templates also serve the frigate type (15) of frigate_type.py.
TEMPLATE_TYPES = {"BB": 0, "BC": 1, "B": 2, "CA": 3, "CL": 4, "AMC": 7, "AV": 8, "DD": 9, "KE": 10, "TR": 11, "LT": 12,
                  "MTB": 13}
FRIGATE, CORVETTE = 15, 10
COLORS = {"clsilver": 0xC0C0C0, "clgray": 0x808080, "clwhite": 0xFFFFFF, "cllightgray": 0xD3D3D3, "clblack": 0}
ENTRY = 1288          # type, year, tons, bow; 6 layers x 25 points; IsLine; Color; 4 funnels; funnel ovals
YEAR_WEIGHT = 4       # template score: 4 per year apart + 1 per percent of displacement apart


def discover(blob, base):
    normal = audit.normalize(blob, base)
    for address, size, expected in WINDOWS:
        start = address - REFERENCE
        if hashlib.sha256(normal[start:start+size]).hexdigest() != expected:
            raise ValueError("Designer visuals refuses changed native code at " + hex(address) + ".")
    if normal[0x524f04-REFERENCE:0x524f04-REFERENCE+11] != b"\x07\x09TMenuItem":
        raise ValueError("Unsupported native designer menu class.")
    delta = base - REFERENCE
    info = {name: value+delta for name, value in dict(
        scale=0x952908, render=0x84111c, main_guns=0x83e1bc,
        secondary_guns=0x840d78, tertiary_guns=0x840d2c, equipment_guns=0x83f300, missiles=0x83f22c,
        reset_outline=0x91aae8, sync_preview=0x5e765c, refresh=0x5e9d88, year=0x9f7328,
        menu_vmt=0x52450c, menu_create=0x52729c, menu_add=0x52af2c,
        menu_caption=0x52a91c, menu_enabled=0x52a9e4).items()}
    info["sites"] = [dict(label=label, address=address+delta,
                          original=blob[address-REFERENCE:address-REFERENCE+size].hex())
                     for label, address, size in (
                         ("Large-hull visual scale", 0x952908, 5),
                         ("Designer guns above graphics", 0x5ce444, 5),
                         ("Designer outline reset menu", 0x5f39e8, 9))]
    return info


def scale_table():
    values = [round(anchor * (max(BOUNDARY, bucket*1000)/BOUNDARY)**(1/3))
              for anchor in ANCHORS for bucket in range(STRIDE)]
    return struct.pack("<" + "I"*len(values), *values)


def scaling_thunk(address, table, original):
    c = Code(address)
    c.emit(b"\x52\x53\x8b\xd8\x83\xe3\x7f\x81\xfa"); c.u32(BOUNDARY)
    c.branch(b"\x0f\x8e", "native")
    c.emit(b"\x83\xfb\x0b"); c.branch(b"\x0f\x87", "native")
    c.emit(b"\x8b\xc2\x3d"); c.u32(MAXIMUM); c.branch(b"\x0f\x8e", "bounded")
    c.emit(b"\xb8"); c.u32(MAXIMUM)
    c.mark("bounded"); c.emit(b"\x31\xd2\xb9"); c.u32(1000)
    c.emit(b"\xf7\xf1\x69\xdb"); c.u32(STRIDE)
    c.emit(b"\x01\xd8\x8b\x04\x85"); c.u32(table)
    c.emit(b"\x5b\x5a\xc3")
    c.mark("native"); c.emit(b"\x5b\x5a\xb9"); c.u32(20)
    c.branch(b"\xe9", original+5)
    return c.finish()


def foreground_thunk(address, info):
    """After the native picture (layers with their visuals, guns and torpedo mounts interleaved, then missiles,
    then funnels): the added visuals of layers 1-6 above every layer, funnel and torpedo mount, then missile
    mounts and guns above the visuals."""
    c = Code(address)
    # Store the incoming ship/globe independently of native scratch registers.
    c.emit(b"\x52\x50"); c.branch(b"\xe8", info["render"])
    c.emit(b"\x9c\x60\x8b\x5c\x24\x24\x8b\x74\x24\x28")
    def draw(name, mode=None):
        c.emit(b"\x8b\xc3\x8b\xd6")
        if mode is not None: c.emit(b"\xb1" + bytes([mode]))
        c.branch(b"\xe8", info[name])
    for layer in range(1, 7):
        c.emit(b"\x8b\xc3\x8b\xd6\xb9"); c.u32(layer)
        c.branch(b"\xe8", info["equipment_guns"])
    draw("missiles")
    draw("main_guns", 0)
    draw("secondary_guns", 0)  # turret/shield mounts; casemates (pass 1) stay under superstructure layer 1
    draw("tertiary_guns")
    # Preserve the original renderer's return registers/flags, not the last redraw.
    c.emit(b"\x61\x9d\x8d\x64\x24\x08\xc3")
    return c.finish()


def ensure_menu(address, state, info, caption, handler, has_template=None):
    c = Code(address); c.emit(b"\x53\x56\x8b\xd8")
    c.emit(b"\x3b\x1d"); c.u32(state); c.branch(b"\x0f\x84", "availability")
    c.emit(b"\x8b\x8b\xdc\x07\x00\x00\x85\xc9"); c.branch(b"\x0f\x84", "done")
    c.emit(b"\xb8"); c.u32(info["menu_vmt"]); c.emit(b"\xb2\x01\x8b\xcb")
    c.branch(b"\xe8", info["menu_create"]); c.emit(b"\x8b\xf0")
    c.emit(b"\xc7\x86\x98\x00\x00\x00"); c.u32(handler)
    c.emit(b"\x89\x9e\x9c\x00\x00\x00\xba"); c.u32(caption)
    c.emit(b"\x8b\xc6"); c.branch(b"\xe8", info["menu_caption"])
    c.emit(b"\x8b\x83\xdc\x07\x00\x00\x8b\x40\x44\x8b\xd6")
    c.branch(b"\xe8", info["menu_add"])
    c.emit(b"\x89\x35"); c.u32(state+4)
    c.emit(b"\x89\x1d"); c.u32(state)
    c.mark("availability")
    c.emit(b"\x31\xd2\x80\xbb\x67\x0e\x00\x00\x00"); c.branch(b"\x0f\x84", "enabled")
    c.emit(b"\x8b\x83\x6c\x0e\x00\x00\x85\xc0"); c.branch(b"\x0f\x84", "enabled")
    if has_template is None:   # outline reset: hulls above the native visual range
        c.emit(b"\x81\x78\x2c"); c.u32(BOUNDARY); c.emit(b"\x0f\x9f\xc2")
    else:                      # auto superstructure: a ship type with templates
        c.emit(b"\x0f\xb6\x80"); c.u32(0x9D3); c.emit(b"\x83\xf8\x0f"); c.branch(b"\x0f\x87", "enabled")
        c.emit(b"\x8a\x90"); c.u32(has_template)
    c.mark("enabled"); c.emit(b"\xa1"); c.u32(state+4)
    c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "done")
    c.branch(b"\xe8", info["menu_enabled"])
    c.mark("done"); c.emit(b"\x5e\x5b\xc3")
    return c.finish()


def popup_thunk(address, ensures, site):
    c = Code(address); c.emit(b"\x9c\x60")
    for ensure in ensures:
        c.emit(b"\x8b\x44\x24\x1c"); c.branch(b"\xe8", ensure)
    c.emit(b"\x61\x9d" + bytes.fromhex(site["original"]))
    c.branch(b"\xe9", site["address"]+len(bytes.fromhex(site["original"])))
    return c.finish()


def reset_thunk(address, state, info):
    c = Code(address); c.emit(b"\x9c\x60\x8b\xd8")
    c.emit(b"\x3b\x1d"); c.u32(state); c.branch(b"\x0f\x85", "done")
    c.emit(b"\x80\xbb\x67\x0e\x00\x00\x00"); c.branch(b"\x0f\x84", "done")
    c.emit(b"\x8b\x83\x6c\x0e\x00\x00\x85\xc0"); c.branch(b"\x0f\x84", "done")
    c.emit(b"\x81\x78\x2c"); c.u32(BOUNDARY); c.branch(b"\x0f\x8e", "done")
    c.branch(b"\xe8", info["reset_outline"])
    c.emit(b"\x8b\xc3\xb2\x01"); c.branch(b"\xe8", info["sync_preview"])
    c.emit(b"\x8b\xc3"); c.branch(b"\xe8", info["refresh"])
    c.mark("done"); c.emit(b"\x61\x9d\xc3")
    return c.finish()


def literal(text):
    """A native constant UnicodeString; its characters start 12 bytes in."""
    return struct.pack("<HHiI", 1200, 2, -1, len(text))+text.encode("utf-16-le")+b"\0\0"


def superstructure_handler(address, state, info, table):
    """Menu click (EAX form): the template of the design's type with the lowest score (YEAR_WEIGHT per year from the
    campaign year, else the design's build year, plus 1 per percent of displacement) gives its 6 superstructure
    layers, IsLine, Color and 4 funnels to the design; distances scale by design bow / template bow."""
    c = Code(address); c.emit(b"\x9c\x60\x8b\xd8")
    c.emit(b"\x3b\x1d"); c.u32(state); c.branch(b"\x0f\x85", "done")
    c.emit(b"\x80\xbb\x67\x0e\x00\x00\x00"); c.branch(b"\x0f\x84", "done")        # the designer is updating itself
    c.emit(b"\x8b\xb3\x6c\x0e\x00\x00\x85\xf6"); c.branch(b"\x0f\x84", "done")    # esi = design
    c.emit(b"\x83\xbe\xdf\x05\x00\x00\x00"); c.branch(b"\x0f\x85", "hull")         # no hull drawn yet:
    c.emit(b"\x8b\xc6"); c.branch(b"\xe8", info["reset_outline"])                      # the class default outline
    c.mark("hull"); c.emit(b"\x83\xec\x14")                     # [esp] type, +4 year, +8 tons, +0C best, +10 scratch
    c.emit(b"\x0f\xb6\x86"); c.u32(0x9D3); c.emit(b"\x89\x04\x24")
    c.emit(b"\xa1"); c.u32(info["year"]); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "build_year")
    c.emit(b"\x8b\x00\x3d"); c.u32(1880); c.branch(b"\x0f\x8d", "year")
    c.mark("build_year"); c.emit(b"\x8b\x86\xe4\x00\x00\x00\x3d"); c.u32(1880); c.branch(b"\x0f\x8d", "year")
    c.emit(b"\xb8"); c.u32(1900)
    c.mark("year"); c.emit(b"\x89\x44\x24\x04\x8b\x46\x2c\x83\xf8\x01"); c.branch(b"\x0f\x8d", "tons")
    c.emit(b"\xb8\x01\x00\x00\x00")
    c.mark("tons"); c.emit(b"\x89\x44\x24\x08\xc7\x44\x24\x0c\xff\xff\xff\x7f")
    c.emit(b"\x33\xff\x8b\x0d"); c.u32(table); c.emit(b"\xbd"); c.u32(table+4)
    c.mark("next"); c.emit(b"\x85\xc9"); c.branch(b"\x0f\x84", "chosen")
    c.emit(b"\x0f\xb6\x45\x00\x3b\x04\x24"); c.branch(b"\x0f\x85", "skip")
    c.emit(b"\x8b\x45\x04\x2b\x44\x24\x04\x99\x33\xc2\x2b\xc2")                # |year - template year|
    c.emit(b"\x6b\xc0" + bytes([YEAR_WEIGHT]) + b"\x89\x44\x24\x10")
    c.emit(b"\x8b\x45\x08\x2b\x44\x24\x08\x99\x33\xc2\x2b\xc2")                # |tons - template tons|
    c.emit(b"\x6b\xc0\x64\x99\xf7\x7c\x24\x08")                                     # x100 / tons
    c.emit(b"\x03\x44\x24\x10\x3b\x44\x24\x0c"); c.branch(b"\x0f\x8d", "skip")
    c.emit(b"\x89\x44\x24\x0c\x8b\xfd")
    c.mark("skip"); c.emit(b"\x81\xc5"); c.u32(ENTRY); c.emit(b"\x49"); c.branch(b"\xe9", "next")
    c.mark("chosen"); c.emit(b"\x83\xc4\x14\x85\xff"); c.branch(b"\x0f\x84", "done")
    c.emit(b"\x8b\x4f\x0c\x85\xc9"); c.branch(b"\x0f\x8e", "done")                   # ecx = template bow
    c.emit(b"\x33\xed")
    c.mark("point")                                                                    # 150 points: angle, distance
    c.emit(b"\x8b\x44\xef\x10\x89\x84\xee"); c.u32(0x10D)
    c.emit(b"\x8b\x44\xef\x14\xf7\xae\xdf\x05\x00\x00\xf7\xf9\x89\x84\xee"); c.u32(0x111)
    c.emit(b"\x45\x81\xfd"); c.u32(150); c.branch(b"\x0f\x85", "point")
    c.emit(b"\x8b\x87\xc0\x04\x00\x00\x89\x86\xbd\x05\x00\x00")                  # IsLine, 6 bytes
    c.emit(b"\x66\x8b\x87\xc4\x04\x00\x00\x66\x89\x86\xc1\x05\x00\x00")
    for layer in range(6):                                                             # Color
        c.emit(b"\x8b\x87"); c.u32(0x4C8+4*layer); c.emit(b"\x89\x86"); c.u32(0x5C3+4*layer)
    for n in range(1, 5):                                                              # funnels 1-4
        c.emit(b"\x8b\x87"); c.u32(0x4E0+8*(n-1)); c.emit(b"\x89\x86"); c.u32(0xE1+8*n)
        c.emit(b"\x8b\x87"); c.u32(0x4E4+8*(n-1)); c.emit(b"\xf7\xae\xdf\x05\x00\x00\xf7\xf9\x89\x86"); c.u32(0xE5+8*n)
        c.emit(b"\x8a\x87"); c.u32(0x500+n-1); c.emit(b"\x88\x86"); c.u32(0x108+n)
    c.emit(b"\x8b\xc3\xb2\x01"); c.branch(b"\xe8", info["sync_preview"])
    c.emit(b"\x8b\xc3"); c.branch(b"\xe8", info["refresh"])
    c.mark("done"); c.emit(b"\x61\x9d\xc3")
    return c.finish()


def superstructure_templates(folder, cache=None):
    """(table, has_template) from the player's own AI templates: a count, then ENTRY-byte records sorted by file
    name; has_template is 16 bytes, 1 for each ship type with a template. Cached by the folder's file list."""
    import hashlib as digest
    files = sorted(Path(folder).glob("*.tdf"))
    signature = digest.sha256(repr([(f.name, f.stat().st_size, f.stat().st_mtime_ns) for f in files]).encode()).digest()
    if cache and Path(cache).is_file() and Path(cache).read_bytes()[:32] == signature:
        table = Path(cache).read_bytes()[32:]
    else:
        entries = []
        for path in files:
            entry = template_entry(path.read_bytes())
            if entry:
                entries.append(entry)
                if entry[0] == CORVETTE: entries.append(bytes([FRIGATE])+entry[1:])
        table = struct.pack("<I", len(entries))+b"".join(entries)
        if cache: Path(cache).write_bytes(signature+table)
    has = bytearray(16)
    for at in range(4, len(table), ENTRY): has[table[at]] = 1
    return table, bytes(has)


def template_entry(raw):
    try: text = raw.decode("utf-8-sig")
    except UnicodeDecodeError: text = raw.decode("latin-1")
    sections, current = {}, {}
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("[") and line.endswith("]"): current = sections.setdefault(line[1:-1], {})
        elif "=" in line:
            key, value = line.split("=", 1); current[key] = value.strip()
    def number(table, key, default=0):
        try: return int(table.get(key, default))
        except ValueError: return default
    data, hull, funnels = sections.get("Data", {}), sections.get("HullPoints", {}), sections.get("Funnels", {})
    kind = TEMPLATE_TYPES.get(data.get("ShipType"))
    year, tons, bow = number(data, "BuildYear"), number(data, "Displacement"), number(hull, "HullPoint0Distance")
    if kind is None or year <= 0 or tons <= 0 or bow <= 0: return None
    layers = [sections.get(f"Superstructure{layer}", {}) for layer in range(6)]
    points = [number(layer, f"Point{i}{part}") for layer in layers for i in range(25) for part in ("Angle", "Distance")]
    lines = bytes(1 if layer.get("IsLine", "0").lower() in ("1", "true") else 0 for layer in layers)
    def color(value):
        value = value.strip()
        if value.startswith("$"): return int(value[1:], 16) & 0xFFFFFFFF
        if value.lstrip("-").isdigit(): return int(value) & 0xFFFFFFFF
        return COLORS.get(value.lower(), 0xC0C0C0)
    colors = [color(layer.get("Color", "clSilver")) for layer in layers]
    pairs = [number(funnels, f"Funnel{n}{part}") for n in range(1, 5) for part in ("Angle", "Distance")]
    ovals = bytes(1 if funnels.get(f"Funnel{n}Oval", "0").lower() in ("1", "true") else 0 for n in range(1, 5))
    entry = (struct.pack("<B3xiii", kind, year, tons, bow)+struct.pack("<300i", *points)+lines+b"\0\0"
             +struct.pack("<6I", *colors)+struct.pack("<8i", *pairs)+ovals+b"\0"*4)
    assert len(entry) == ENTRY
    return entry


def build(allocation, info, extra=None, templates=None):
    """extra: a separate allocation for Auto superstructure (code, then the template table at +0x1000)."""
    addresses = {name: allocation+offset for name, offset in dict(
        scale=0x400, foreground=0x600, ensure=0x800, popup=0xa00, reset=0xb00,
        table=0xb000, caption=0xea00, state=0xf000).items()}
    ensures = [addresses["ensure"]]
    if extra is not None:
        addresses.update(auto_ensure=extra, auto=extra+0x200, auto_caption=extra+0x600, auto_has=extra+0x700,
                         auto_state=extra+0x800, templates=extra+0x1000)
        ensures.append(addresses["auto_ensure"])
    routines = {
        "scale": scaling_thunk(addresses["scale"], addresses["table"], info["scale"]),
        "foreground": foreground_thunk(addresses["foreground"], info),
        "ensure": ensure_menu(addresses["ensure"], addresses["state"], info,
                              addresses["caption"]+12, addresses["reset"]),
        "popup": popup_thunk(addresses["popup"], ensures, info["sites"][2]),
        "reset": reset_thunk(addresses["reset"], addresses["state"], info),
    }
    if extra is not None:
        routines["auto_ensure"] = ensure_menu(addresses["auto_ensure"], addresses["auto_state"], info,
                                              addresses["auto_caption"]+12, addresses["auto"], addresses["auto_has"])
        routines["auto"] = superstructure_handler(addresses["auto"], addresses["auto_state"], info, addresses["templates"])
    blocks = []
    for name, code in routines.items():
        if len(code) > dict(scale=0x200, foreground=0x200, ensure=0x200, auto_ensure=0x200, auto=0x400).get(name, 0x100):
            raise ValueError("Designer visuals routine exceeds its reservation: " + name)
        blocks.append(dict(address=addresses[name], bytes=code.hex(), name=name))
    if extra is not None:
        blocks += [dict(name="auto_caption", address=addresses["auto_caption"],
                        bytes=literal("Auto superstructure (AI template)").hex()),
                   dict(name="auto_has", address=addresses["auto_has"], bytes=templates[1].hex()),
                   dict(name="auto_state", address=addresses["auto_state"], bytes="00"*8)]
    table = scale_table()
    if addresses["table"]+len(table) > addresses["caption"]:
        raise ValueError("Visual scale table exceeds its reserved area.")
    caption = "Reset hull outline (keep fitted weapons)"
    blocks.extend([dict(name="scale_table", address=addresses["table"], bytes=table.hex()),
                   dict(name="caption", address=addresses["caption"], bytes=literal(caption).hex())])
    changes = []
    for name, site in zip(("scale", "foreground", "popup"), info["sites"]):
        original = bytes.fromhex(site["original"])
        opcode = b"\xe8" if name == "foreground" else b"\xe9"
        code = opcode+struct.pack("<i", addresses[name]-site["address"]-5)+b"\x90"*(len(original)-5)
        changes.append(patch(site["label"], site["address"], original, code))
    return dict(patches=changes, blocks=blocks, state=addresses["state"],
                locations=addresses, boundary_tons=BOUNDARY, max_visual_tons=MAXIMUM,
                native_range_preserved=True, extension="class anchor * (D/100900)^(1/3), rounded, 1000t buckets",
                guns_foreground="designer only; added visuals above layers, funnels and torpedo mounts, "
                                "then missile mounts and guns above the visuals; casemates stay under layer 1",
                auto_superstructure=None if extra is None else dict(
                    menu="Auto superstructure (AI template)", templates=struct.unpack_from("<I", templates[0])[0],
                    table=addresses["templates"], keeps="hull outline, weapons and equipment"),
                saved_designs_auto_rewritten=False, reset_menu=caption,
                reset_changes="hull outline only; fitted weapons, equipment, superstructure retained",
                gameplay_verified=False)
