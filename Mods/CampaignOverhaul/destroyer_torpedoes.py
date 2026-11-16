"""DD-only extension of the final centreline-torpedo displacement check.

Retain the native 2500/3500t research checks and other ship classes' 7000t cap.
The comparison trampoline changes no registers/stack and returns to the native
JLE with the selected class limit's flags. Installs with the large-hulls adapter.
"""
import hashlib
import struct

import modern_research as audit
from campaign_security import Code
from hull_rules import message_ref, patch

REFERENCE = 0x301000
VALIDATOR = 0x5E6264
SIZE = 858
DIGEST = "6925f77cc83ddd89af567f266020b8603f12dbb1486ecbc2bb954185209e31b3"
SITE = 0x5E63E1
MESSAGE = "Centreline torpedo mounts can only be used on ships of 7000 tons displacement or less."
CODE_OFFSET = 0xC00
TEXT_OFFSET = 0xF400


def discover(blob, base, dd_tons):
    if type(dd_tons) is not int or not 3800 <= dd_tons <= 280000:
        raise ValueError("DD torpedo extension requires a 3800-280000 ton class limit.")
    normal = audit.normalize(blob, base)
    start = VALIDATOR - REFERENCE
    if hashlib.sha256(normal[start:start+SIZE]).hexdigest() != DIGEST:
        raise ValueError("DD torpedo extension refuses changed native mount-validation code.")
    delta = base - REFERENCE
    original = bytes.fromhex("817f2c581b0000")
    if blob[SITE-REFERENCE:SITE-REFERENCE+7] != original:
        raise ValueError("Unsupported centreline torpedo displacement comparison.")
    ref = message_ref(blob, base, MESSAGE)
    if base+ref != 0x5E6410+delta:
        raise ValueError("Unexpected torpedo-validation message owner.")
    return dict(site=SITE+delta, original=original.hex(), resume=SITE+delta+7,
                message_ref=base+ref, message_original=blob[ref:ref+4].hex(),
                dd_limit=max(7000, dd_tons), other_classes_limit=7000,
                native_research_checks_preserved=True,
                saved_designs_rewritten=False, battle_behavior_changed=False)


def comparison_thunk(address, info):
    c = Code(address)
    c.emit(bytes.fromhex("80bfd309000009"))  # original design is in EDI
    c.branch(b"\x0f\x85", "native")
    c.emit(bytes.fromhex("817f2c")); c.u32(info["dd_limit"])
    c.branch(b"\xe9", info["resume"])
    c.mark("native"); c.emit(bytes.fromhex(info["original"]))
    c.branch(b"\xe9", info["resume"])
    return c.finish()


def build(allocation, info):
    address, literal_address = allocation+CODE_OFFSET, allocation+TEXT_OFFSET
    code = comparison_thunk(address, info)
    text = (f"Centreline torpedo mounts require DD displacement of {info['dd_limit']} tons or less; "
            "other ship types are limited to 7000 tons.")
    literal = struct.pack("<HHiI", 1200, 2, -1, len(text))+text.encode("utf-16-le")+b"\0\0"
    if len(code) > 0x100 or len(literal) > 0x400:
        raise ValueError("DD torpedo extension exceeds its allocation reservation.")
    jump = b"\xe9"+struct.pack("<i", address-info["site"]-5)+b"\x90\x90"
    changes = [patch("DD centreline torpedo displacement limit", info["site"],
                     bytes.fromhex(info["original"]), jump),
               patch("Centreline torpedo displacement message", info["message_ref"],
                     bytes.fromhex(info["message_original"]), struct.pack("<I", literal_address+12))]
    return dict(patches=changes,
                blocks=[dict(name="dd_torpedo_limit", address=address, bytes=code.hex()),
                        dict(name="dd_torpedo_message", address=literal_address, bytes=literal.hex())],
                dd_limit=info["dd_limit"], other_classes_limit=7000,
                native_research_checks_preserved=True,
                saved_designs_rewritten=False, battle_behavior_changed=False,
                gameplay_verified=False)
