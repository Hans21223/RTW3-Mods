"""Native missile helpers shared by missile_range: audits, loaded-SSM range, launcher arcs.

Uses native launcher resolution, arcs and ranges. The 0.5.0 custom selector,
stance, ledger and salvo budgets were removed; missile_range is the live adapter.
"""
import hashlib
import struct

import modern_research as audit
from campaign_security import Code

BASE = 0x301000
WINDOWS = (
    (0x877068, 1488, "a67f17cd082daebb098f412b4862d766d81d8d9502d9d1bab1fdd11a7f97a9cb"),
    (0x8793CC, 147, "6804b5aa20efe9f9be1b570e3bd3d8869d71ac033e178ef0c873566d926c6ccb"),
    # Body after the existing battle-ai sunk-target entry hook.
    (0x8D472F, 841, "e5629647177d0937c34096f4512539187fec8f459af2f592a881fffcd7c0dba8"),
    (0x91ACCC, 34, "5f54a177a4079e2ffa266bb6c522fe1f9e041c5106ee6c99d8af78c53de40fb9"),
    (0x8CAC34, 448, "a426b4882ecee8c15e7db5fd5933fc8e91359795a54abcab082c37143de0c433"),
    (0x8ECA2C, 144, "429008ce452d8365be29858a2b2f0d0f23c16a891994a1e9d31844beb36f3804"),
    (0x8ECB60, 36, "c6cf7543d125f317b26aebf3b731fe5061f511845aa701c61832d1077e884481"),
    (0x9253B4, 160, "a75db0c7422505776232818800eb194fd6092d0517ef1f7c7e48f5e4653d1ac6"),
    (0x8D34F4, 44, "ba4d020f6857c939afbaa389f4a182a9d5741d2bdfdc943537cc468534f1511c"),
)


def discover(blob, base):
    normal = audit.normalize(blob, base)
    for address, size, digest in WINDOWS:
        if not digest or hashlib.sha256(normal[address-BASE:address-BASE+size]).hexdigest() != digest:
            raise ValueError("Missile AI refuses changed native code at " + hex(address))
    delta = base-BASE
    result = {key: value+delta for key, value in dict(
        selector=0x877068, site=0x87945A, range=0x91ACCC,
        fire=0x8D4718, relative_bearing=0x8ECA2C, true_bearing=0x8ECB60,
        friendly_line=0x8CAC34, clock_slot=0x9F7748,
        arc=0x9253B4, minimum_range=0x8D34F4).items()}
    old = blob[0x87945A-BASE:0x87945A-BASE+5]
    if old[0] != 0xE8 or result["site"]+5+struct.unpack("<i", old[1:])[0] != result["selector"]:
        raise ValueError("Unknown native AI surface missile caller.")
    result["original"] = old.hex()
    return result


def ready_range_thunk(address, info):
    """EAX ship -> maximum native range of loaded, undamaged SSM launchers."""
    c=Code(address); c.emit(bytes.fromhex("535657558bd833ed8b839e00000085c0")); c.branch(b"\x0f\x84","done")
    c.emit(bytes.fromhex("8b780885ff")); c.branch(b"\x0f\x8e","done")
    c.emit(b"\x81\xff"); c.u32(512); c.branch(b"\x0f\x87","done")
    c.emit(bytes.fromhex("8b700485f6")); c.branch(b"\x0f\x84","done")
    c.mark("loop"); c.emit(bytes.fromhex("8b0685c0")); c.branch(b"\x0f\x84","next")
    c.emit(bytes.fromhex("0fb6500e83fa04")); c.branch(b"\x0f\x82","next")
    c.emit(b"\x83\xfa\x06"); c.branch(b"\x0f\x87","next")
    c.emit(bytes.fromhex("80b8f000000000")); c.branch(b"\x0f\x85","next")
    c.emit(bytes.fromhex("83b8f100000000")); c.branch(b"\x0f\x8e","next")
    c.emit(bytes.fromhex("8b4314")); c.branch(b"\xe8",info["range"])
    c.emit(bytes.fromhex("3bc5")); c.branch(b"\x0f\x8e","next")
    c.emit(b"\x3d"); c.u32(2000000); c.branch(b"\x0f\x87","next")
    c.emit(b"\x8b\xe8")
    c.mark("next"); c.emit(bytes.fromhex("83c6044f")); c.branch(b"\x0f\x85","loop")
    c.mark("done"); c.emit(bytes.fromhex("8bc55d5f5e5bc3")); return c.finish()


def engageable_thunk(address, info):
    """EAX ship, EDX relative bearing, ECX range, stack form -> ready mount."""
    c=Code(address); c.emit(bytes.fromhex("5356575583ec108bd8891424894c24048b839e00000085c0")); c.branch(b"\x0f\x84","no")
    c.emit(bytes.fromhex("8b680885ed")); c.branch(b"\x0f\x8e","no")
    c.emit(b"\x81\xfd"); c.u32(512); c.branch(b"\x0f\x87","no")
    c.emit(bytes.fromhex("8b700485f6")); c.branch(b"\x0f\x84","no")
    c.mark("loop"); c.emit(bytes.fromhex("8b3e85ff")); c.branch(b"\x0f\x84","next")
    c.emit(bytes.fromhex("0fb6470e83f804")); c.branch(b"\x0f\x82","next")
    c.emit(b"\x83\xf8\x06"); c.branch(b"\x0f\x87","next")
    c.emit(bytes.fromhex("80bff000000000")); c.branch(b"\x0f\x85","next")
    c.emit(bytes.fromhex("83bff100000000")); c.branch(b"\x0f\x8e","next")
    c.emit(bytes.fromhex("8b14248bc7")); c.branch(b"\xe8",info["arc"])
    c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84","next")
    c.emit(bytes.fromhex("0fb6570e8b4314")); c.branch(b"\xe8",info["range"])
    c.emit(bytes.fromhex("3b442404")); c.branch(b"\x0f\x8e","next")
    c.emit(bytes.fromhex("0fb6570e8b442424")); c.branch(b"\xe8",info["minimum_range"])
    c.emit(bytes.fromhex("39442404")); c.branch(b"\x0f\x8e","next")
    c.emit(b"\xb8\x01\x00\x00\x00"); c.branch(b"\xe9","done")
    c.mark("next"); c.emit(bytes.fromhex("83c6044d")); c.branch(b"\x0f\x85","loop")
    c.mark("no"); c.emit(b"\x33\xc0")
    c.mark("done"); c.emit(bytes.fromhex("83c4105d5f5e5bc20400")); return c.finish()
