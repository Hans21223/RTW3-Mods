"""Player-map position markers only. Never alter spotting, AI or ship state."""
import re
import struct
import weekly_runtime as rt
from hull_rules import unique


def field(blob, name):
    # Extended Delphi field RTTI: type pointer, field offset, short name, flags.
    key = bytes([len(name)])+name.encode()+b"\x02\x00\x02"
    offsets = {struct.unpack_from("<I", blob, m.start()-4)[0]
               for m in re.finditer(re.escape(key), blob) if m.start() >= 8
               and 0x900 < struct.unpack_from("<I", blob, m.start()-4)[0] < 0x1000}
    if len(offsets) != 1: raise ValueError("Cannot verify tactical ship field: "+name)
    return offsets.pop()


def discover(blob, base):
    hidden, sunk, newly = (field(blob, name) for name in ("Hidden", "Sunk", "Newlysighted"))
    prologue = b"\x55\x8b\xec\x83\xc4\xdc\x53\x56\x57\x8b\xd8\x33\xd2\x55\x68"
    marker = b"\x6a\x48\x8d\x96\x1c\x0a\x00\x00\x8b\x83\x98\x04\x00\x00\xb9\x88\x13\x00\x00\x8b\x38\xff\x97\xd0\x01\x00\x00"
    starts = [m.start() for m in re.finditer(re.escape(prologue), blob)
              if marker in blob[m.start():m.start()+0x620]]
    if len(starts) != 1: raise ValueError("Cannot uniquely verify the battle-map ship marker renderer.")
    start = starts[0]
    renderer = base+start
    body = blob[start:start+0x620]
    # Verify this is called by the native GlobeRender event, not an AI routine.
    callers = set()
    name = b"GlobeRender"
    for match in re.finditer(bytes([len(name)])+name, blob):
        at = match.start()
        if at < 6: continue
        size, address = struct.unpack_from("<HI", blob, at-6)
        if not 7+len(name) <= size < 1200 or not base <= address < base+len(blob): continue
        for call in re.finditer(rb"\xe8(.{4})", blob[address-base:address-base+0x200], re.DOTALL):
            if address+call.start()+5+struct.unpack("<i", call.group(1))[0] == renderer:
                callers.add(address)
    if len(callers) != 1: raise ValueError("Cannot verify the battle map render caller.")
    # A native marker uses the real ship coordinate and a TGlobe circle draw.
    marker_at = unique(body, marker, "real-position ship circle")
    zoom = unique(body, b"\x81\x78\x10\xe8\x03\x00\x00\x0f\x8e", "marker zoom entry")
    hide = unique(body, b"\x80\xbe"+struct.pack("<I", hidden)+b"\x00\x0f\x85", "hidden marker gate")
    draw = unique(body, b"\x81\x78\x10\xd0\x07\x00\x00\x7f", "marker detail zoom")
    sight = unique(body, b"\x80\xbe"+struct.pack("<I", newly)+b"\x00\x74", "new sighting bookkeeping")
    plans = []
    for label, at, length, force in (("zoom entry", zoom, 13, "fall"),
                                     ("hidden marker", hide, 13, "fall"),
                                     ("detail zoom", draw, 9, "taken"),
                                     ("new sighting bookkeeping", sight, 9, "taken")):
        original = body[at:at+length]
        delta = struct.unpack("<i", original[9:13])[0] if length == 13 else struct.unpack("<b", original[8:9])[0]
        taken = renderer+at+length+delta
        plans.append(dict(label=label, address=renderer+at, original=original.hex(),
                          prefix=original[:7].hex(), condition=original[8] if length == 13 else original[7]+0x10,
                          taken=taken, fall=renderer+at+length, force=force, hidden_field=hidden))
    if not (zoom < hide < draw < marker_at and plans[2]["taken"] == renderer+marker_at):
        raise ValueError("Unexpected map marker branch boundaries.")
    if not zoom < sight < hide or plans[3]["taken"] != renderer+hide:
        raise ValueError("Unexpected map sighting bookkeeping boundaries.")
    # Hidden ships still obey sunk filtering in the cheat; RTTI and native
    # detailed-render comparisons must agree on the separate sunk flag.
    if b"\x80\xb8"+struct.pack("<I", sunk)+b"\x00\x0f\x85" not in blob:
        raise ValueError("Cannot cross-check the tactical sunk flag.")
    return {"renderer": renderer, "map_event": callers.pop(), "hidden_field": hidden,
            "sunk_field": sunk, "sites": plans, "display_only": True,
            "known_ship_rendering_preserved": True,
            "close_zoom_extra_markers": "hidden non-sunk ships only",
            "spotting_changed": False, "ai_information_changed": False,
            "ship_details_unlocked": False, "battle_gameplay_verified": False}


def thunk(address, state, site, sunk):
    code = bytearray(b"\x9c\x83\x3d"+struct.pack("<I", state)+b"\x01\x0f\x84\0\0\0\0")
    cheat_fix = len(code)-4

    def jump(op, target):
        code.extend(op+struct.pack("<i", target-(address+len(code)+len(op)+4)))

    # Normal rendering exactly replays the original compare and branch.
    code.extend(b"\x9d"+bytes.fromhex(site["prefix"]))
    jump(b"\x0f"+bytes([site["condition"]]), site["taken"])
    jump(b"\xe9", site["fall"])
    struct.pack_into("<i", code, cheat_fix, len(code)-cheat_fix-4)
    code.extend(b"\x9d")
    if site["label"] == "new sighting bookkeeping":
        # The native far-zoom loop maintains newly sighted contacts. When the
        # cheat adds this loop at close zoom, skip those otherwise-new writes.
        # At native far zoom keep the original legitimate sighting processing.
        code.extend(b"\x50\x8b\x83\x98\x04\x00\x00\x8b\x80\xe0\x02\x00\x00\x81\x78\x10\xe8\x03\x00\x00\x58")
        jump(b"\x0f\x8e", site["taken"])
        code.extend(bytes.fromhex(site["prefix"]))
        jump(b"\x0f"+bytes([site["condition"]]), site["taken"])
        jump(b"\xe9", site["fall"])
        return bytes(code)
    if site["label"] == "hidden marker":
        code.extend(b"\x80\xbe"+struct.pack("<I", sunk)+b"\x00")
        jump(b"\x0f\x85", site["taken"])
        code.extend(bytes.fromhex(site["prefix"]))
        # Hidden ships need the overlay. At close zoom, known ships are already
        # drawn by the native detailed renderer: do not draw a second marker or
        # execute its repeated GDI pen/color/property calls for those ships.
        hidden_jump = len(code)
        code.extend(b"\x0f\x85\0\0\0\0")
        code.extend(b"\x50\x8b\x83\x98\x04\x00\x00\x8b\x80\xe0\x02\x00\x00\x81\x78\x10\xe8\x03\x00\x00\x58")
        jump(b"\x0f\x8e", site["taken"])
        struct.pack_into("<i", code, hidden_jump+2, len(code)-hidden_jump-6)
    elif site["label"] == "detail zoom":
        code.extend(b"\x80\xbe"+struct.pack("<I", site["hidden_field"])+b"\x00")
        hidden_jump = len(code)
        code.extend(b"\x0f\x85\0\0\0\0")
        code.extend(bytes.fromhex(site["prefix"]))
        jump(b"\x0f"+bytes([site["condition"]]), site["taken"])
        jump(b"\xe9", site["fall"])
        struct.pack_into("<i", code, hidden_jump+2, len(code)-hidden_jump-6)
    code.extend(bytes.fromhex(site["prefix"]))
    jump(b"\xe9", site[site["force"]])
    return bytes(code)
