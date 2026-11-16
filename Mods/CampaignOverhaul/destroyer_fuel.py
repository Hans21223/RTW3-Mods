"""Extend the native DD fuel-capacity size band, without changing consumption.

SetOriginalEndurance has a DD-only 1000..5000t final band. Beyond it no capacity
is assigned, leaving new tactical ships with 0/0 fuel. Continue that same native
band through the configured DD class ceiling; keep older size bands, year and
starting-percentage processing unchanged. Loaded zero/zero records also need
repair: deserialization does not call SetOriginalEndurance. SetStartingEndurance
duplicates the size bands and applies range/technology modifiers afterwards;
leaving its cap unchanged scales an already scaled capacity a second time and
overflows the signed starting-fuel multiplication.
"""
import hashlib
import struct

import modern_research as audit
import weekly_runtime as rt
from hull_rules import patch

REFERENCE = 0x301000
METHOD = 0x9161E4
SIZE = 286
DIGEST = "6e3cc34482a4114b9f793aa4ef902797a5d06e1c3334ff72fac64846785f935d"
SITE = 0x91622E
NATIVE_CEILING = 5000
STARTING_METHOD = 0x6C6968
STARTING_SIZE = 644
STARTING_DIGEST = "e6e23e4890219c5c6d982c9588ea983f4942bacbaf0534691990058f51c9086e"
STARTING_SITE = 0x6C6A4D
RECOVERY_WINDOWS = (
    ("GetMaxSpeed", 0x9040C0, 778, "8d09d951ed9884553478491543fc80b2d8a69213b640c12eb17258068a3ff94d", 7),
    ("GetFuelPercentage", 0x9145FC, 49, "5bef5cdaceae9ea81f875d46e95aa4cb38505246bcacdf7b77d6e707637d47c6", 5),
    ("GetRemaningRange", 0x914634, 332, "ae3f6c930f3668620aa4d015cad1f3ad77b0588041777cdb3913dd023bef7b5e", 6),
)


def discover(blob, base, dd_tons):
    if type(dd_tons) is not int or not 3800 <= dd_tons <= 280000:
        raise ValueError("DD fuel extension requires a 3800-280000 ton class limit.")
    normal = audit.normalize(blob, base)
    start = METHOD - REFERENCE
    if (rt.method_address(blob, base, "SetOriginalEndurance") != base + start
            or hashlib.sha256(normal[start:start+SIZE]).hexdigest() != DIGEST):
        raise ValueError("DD fuel extension refuses changed native endurance code.")
    original = b"\x2d" + struct.pack("<I", NATIVE_CEILING - 1000 + 1)
    offset = SITE - REFERENCE
    if blob[offset:offset+5] != original:
        raise ValueError("Unsupported DD fuel-capacity size band.")
    ceiling = max(NATIVE_CEILING, dd_tons)
    replacement = b"\x2d" + struct.pack("<I", ceiling - 1000 + 1)
    plan = patch("DD fuel capacity above native size range", base+offset, original, replacement)
    starting = STARTING_METHOD-REFERENCE
    if (hashlib.sha256(normal[starting:starting+STARTING_SIZE]).hexdigest() != STARTING_DIGEST
            or blob[STARTING_SITE-REFERENCE:STARTING_SITE-REFERENCE+5] != original):
        raise ValueError("DD fuel extension refuses changed native battle-start endurance code.")
    starting_plan = patch("DD battle-start range/technology fuel capacity", base+STARTING_SITE-REFERENCE,
                          original, replacement)
    recovery = []
    for name, address, size, digest, stolen in RECOVERY_WINDOWS:
        start = address - REFERENCE
        if (rt.method_address(blob, base, name) != base+start
                or hashlib.sha256(normal[start:start+size]).hexdigest() != digest):
            raise ValueError("DD fuel recovery refuses changed native " + name + " code.")
        recovery.append(dict(name=name, address=base+start,
                             original=blob[start:start+stolen].hex()))
    return [plan, starting_plan], dict(native_max_tons=NATIVE_CEILING, extended_max_tons=ceiling,
                        native_capacity_band_preserved=True,
                        native_year_and_starting_fuel_preserved=True,
                        fuel_consumption_changed=False, other_classes_changed=False,
                        applies_at="native initialization and loaded tactical ship queries",
                        existing_zero_capacity_battle_records_rewritten=True,
                        recovery_starting_percent=100,
                        recovery_only="Oversized alive DD: zero capacity or 1000x inflated native capacity",
                        battle_start_range_and_technology_preserved=True,
                        duplicate_initializer_patched=True,
                        inflated_capacity_repair="35M..180M divisible by 1000; divide capacity by 1000; keep plausible positive fuel, otherwise restore full once",
                        initializer=base+METHOD-REFERENCE, recovery=recovery)


def build(allocation, info):
    """Repair once on the game thread before native speed/fuel/range queries.

    Zero capacity cannot represent a depleted tank. A 1000x inflated capacity
    comes from the second native initializer skipping the oversized-DD band.
    Repair that scale and the unusable overflow result once. Ordinary depleted
    tanks stay empty. Preserve plausible positive raw fuel in inflated records.
    Both sides use the same rule; no damage or speed order is overwritten.
    """
    helper = allocation+0xD00
    code = bytearray(b"\x9c\x60")  # pushfd / pushad: preserve even volatile arguments.
    skips = []; branches = []; labels = {}

    def branch(condition, label):
        code.extend(condition); branches.append((len(code), label)); code.extend(b"\0\0\0\0")

    def check(instruction, condition):
        code.extend(instruction+condition)
        skips.append(len(code))
        code.extend(b"\0\0\0\0")

    check(b"\x80\xb8"+struct.pack("<I", 0x9D3)+b"\x09", b"\x0f\x85")
    check(b"\x81\x78\x2c"+struct.pack("<I", NATIVE_CEILING), b"\x0f\x8e")
    check(b"\x81\x78\x2c"+struct.pack("<I", info["extended_max_tons"]), b"\x0f\x8f")
    for offset, width in ((0xA9F, 1), (0xB35, 4)):
        check((b"\x80\xb8" if width == 1 else b"\x83\xb8")+struct.pack("<I", offset)+b"\0", b"\x0f\x85")
    code.extend(bytes.fromhex("8b90500a000085d2")); branch(b"\x0f\x84", "zero")
    # Native capacities are at most 180k for a DD. The broken second routine
    # scales a previous 35k..180k capacity by 1000 instead of resetting its band.
    code.extend(b"\x81\xfa"+struct.pack("<I", 35000000)); branch(b"\x0f\x8c", "done")
    code.extend(b"\x81\xfa"+struct.pack("<I", 180000000)); branch(b"\x0f\x8f", "done")
    code.extend(bytes.fromhex("8bc88bc233d2bb")+struct.pack("<I",1000)+bytes.fromhex("f7f385d2"))
    branch(b"\x0f\x85", "done")
    code.extend(bytes.fromhex("8981500a00008b914c0a000085d2")); branch(b"\x0f\x8e", "restore")
    code.extend(bytes.fromhex("3bd0")); branch(b"\x0f\x8e", "done")
    labels["restore"] = len(code); code.extend(bytes.fromhex("89814c0a0000")); branch(b"\xe9", "done")
    labels["zero"] = len(code)
    code.extend(bytes.fromhex("83b84c0a000000")); branch(b"\x0f\x8f", "done")
    code.extend(b"\xba"+struct.pack("<I", 100)+b"\xe8")
    code.extend(struct.pack("<i", info["initializer"]-(helper+len(code)+4)))
    end = len(code)
    labels["done"] = end
    code.extend(b"\x61\x9d\xc3")
    for offset in skips:
        struct.pack_into("<i", code, offset, end-offset-4)
    for offset, label in branches:
        struct.pack_into("<i", code, offset, labels[label]-offset-4)
    if len(code) > 0x100:
        raise ValueError("DD fuel recovery exceeds its reserved allocation.")
    blocks = [dict(name="DD fuel recovery helper", address=helper, bytes=code.hex())]
    plans = []
    for index, entry in enumerate(info["recovery"]):
        wrapper = allocation+0xE00+index*0x40
        original = bytes.fromhex(entry["original"])
        body = b"\xe8"+struct.pack("<i", helper-wrapper-5)+original
        body += b"\xe9"+struct.pack("<i", entry["address"]+len(original)-(wrapper+len(body)+5))
        replacement = b"\xe9"+struct.pack("<i", wrapper-entry["address"]-5)+b"\x90"*(len(original)-5)
        blocks.append(dict(name="DD fuel recovery "+entry["name"], address=wrapper, bytes=body.hex()))
        plans.append(patch("Loaded DD zero-capacity recovery: "+entry["name"],
                           entry["address"], original, replacement))
    return dict(blocks=blocks, patches=plans)
