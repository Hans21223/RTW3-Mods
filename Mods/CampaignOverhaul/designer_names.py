"""Designer captions follow the research that replaces a native module (part of the modern-research adapter).

Aluminium superstructure -> Composite superstructure, Seaplane/helicopter hangar -> UAV/helicopter hangar,
Catapults -> EMALS catapults: when the designer's nation has the research and the design is new enough for it,
checked on every designer refresh (modern_railgun's sync calls sync here). Names only; the rules are modern_navy's,
modern_recon's and the EMALS code's.
"""
import struct
import modern_tree as tree

FORM = dict(nation=0xC63, design=0xE6C, cbAluminium=0xA98, cbHangar=0x96C, GroupBox8=0x938)   # TfrmDesignMain2 RTTI
HINT = 0x90                # TControl.FHint
DESIGN_YEAR, BUILD_YEAR = 0xB28, 0xE4
# control, hint?, native text, replacement, research, (design field, first year) or None
NAMES = (
    ("cbAluminium", False, "Aluminium superstructure", "Composite superstructure", tree.COMPOSITE[0], (DESIGN_YEAR, tree.COMPOSITE[1])),
    ("cbAluminium", True, "Saves weight but increases fire hazard", "Composite: saves more weight, costs more, no fire hazard",
     tree.COMPOSITE[0], (DESIGN_YEAR, tree.COMPOSITE[1])),
    ("cbHangar", False, "Seaplane/helicopter hangar", "UAV/helicopter hangar", tree.UAVS, None),
    ("GroupBox8", False, "Catapults", "EMALS catapults", tree.EMALS[0], (BUILD_YEAR, tree.EMALS[1])),
)


def literal(text):
    return struct.pack("<HHiI", 1200, 2, -1, len(text))+text.encode("utf-16-le")+b"\0\0"


def build(address, info):
    """sync(EAX form) at address, texts after it (0xC00 bytes in all); info has has_research, set_text, assign."""
    from campaign_security import Code
    blocks, texts, offset = [], [], address+0x200
    for _, _, native, new, _, _ in NAMES:
        pair = []
        for text in (native, new):
            body = literal(text); pair.append(offset+12)
            blocks.append(dict(name="Designer name: "+text, address=offset, bytes=body.hex()))
            offset += (len(body)+15) & ~15
        texts.append(pair)
    if offset > address+0xC00: raise ValueError("Designer names exceed their reservation.")
    c = Code(address)
    c.emit(b"\x53\x56\x8b\xd8\x8b\xb3"); c.u32(FORM["design"]); c.emit(b"\x85\xf6"); c.branch(b"\x0f\x84", "done")
    for index, ((control, hint, _, _, research, year), (native, new)) in enumerate(zip(NAMES, texts)):
        c.emit(b"\xba"); c.u32(native)
        if year:
            c.emit(b"\x81\xbe"); c.u32(year[0]); c.u32(year[1]); c.branch(b"\x0f\x8c", f"set{index}")
        c.emit(b"\x52\x8b\x83"); c.u32(FORM["nation"]); c.emit(b"\xba"); c.u32(research); c.branch(b"\xe8", info["has_research"])
        c.emit(b"\x5a\x84\xc0"); c.branch(b"\x0f\x84", f"set{index}")
        c.emit(b"\xba"); c.u32(new)
        c.mark(f"set{index}"); c.emit(b"\x8b\x83"); c.u32(FORM[control])
        if hint:
            c.emit(b"\x05"); c.u32(HINT); c.branch(b"\xe8", info["assign"])
        else:
            c.branch(b"\xe8", info["set_text"])
    c.mark("done"); c.emit(b"\x5e\x5b\xc3")
    body = c.finish()
    if len(body) > 0x200: raise ValueError("Designer names code exceeds its reservation.")
    return blocks+[dict(name="Designer names: sync", address=address, bytes=body.hex())]
