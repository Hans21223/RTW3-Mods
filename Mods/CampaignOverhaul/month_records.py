"""Monthly campaign statistics past 1990 (part of timeline-2030).

TfrmBuildCamp, the campaign window and the game's main object, keeps a [year][month] table of 100-byte month
records (the statistics graphs, the summary and the war history) at main+0x795B+row*1200+month*100, row = year-1900,
inside its own 0x2245C bytes: 1890 to 1990. The native campaign stopped in 1990. Past it, each month's record went
beyond the object, over the next heap blocks (the campaign window's labels), and the VCL later crashed reading one of
them in TControl.GetAction ("Access violation ... Read of address 6C000100", in DoTurn2 or DoStrategicTurn).

All 52 instructions that index the table address it as [main + row*1200 + index*4 + field]; adding one constant to
their 32-bit field offsets moves the whole table into a zeroed allocation for 1890 to 2060. No code addresses the
table as a whole; only the window's compiler-made cleanup still walks the old place, where the strings in the
records (fields +0x10 and +0x18) stay nil.
"""
import hashlib
import struct

import modern_research as audit

BASE = 0x301000
MAIN = 0xA23000                      # global holding the campaign window (TfrmBuildCamp)
VMT, SIZE = 0x706F94, 0x2245C        # TfrmBuildCamp class and its native InstanceSize
TABLE = 0x4A7B                       # main + this: row -10 (1890), month 0, the table's first byte
FIRST, LAST, ROW = 1890, 2060, 1200  # years the moved table holds; bytes per year (12 months + month 0)
MARGIN = 0x1000
ALLOCATION = (MARGIN+(LAST-FIRST+1)*ROW+MARGIN+0xFFF) & ~0xFFF
FIELDS = (0x795B, 0x79C0)            # field offsets in a month record, as the instructions hold them
# (instruction, size, offset of its 32-bit field displacement): every reference to the table.
SITES = ((0x6F1C03, 7, 3), (0x6F1E24, 8, 3), (0x6F1E51, 7, 3), (0x6F1E8E, 8, 3), (0x6F1EAF, 7, 3), (0x6F1ECA, 7, 3),
         (0x6F1F02, 8, 3), (0x6F21B7, 8, 3), (0x6F21DC, 7, 3), (0x6F2283, 8, 3), (0x6F22DE, 7, 3), (0x6F2343, 7, 3),
         (0x6F2366, 7, 3), (0x6F297D, 7, 3), (0x6F29CB, 7, 3), (0x6F2EC0, 7, 3), (0x6F2F0F, 7, 3), (0x7DA50C, 8, 3),
         (0x7DA519, 7, 3), (0x7DA525, 7, 3), (0x7DA573, 8, 3), (0x7DA580, 7, 3), (0x7DA58C, 7, 3), (0x7DA5F7, 7, 3),
         (0x7DA629, 7, 3), (0x7DA660, 7, 3), (0x7DA832, 7, 3), (0x7DA85E, 7, 3), (0x7DA88A, 7, 3), (0x7DA8B6, 7, 3),
         (0x7DA8E2, 7, 3), (0x7DA909, 7, 3), (0x7DA935, 7, 3), (0x7DA972, 7, 3), (0x7DA9A8, 7, 3), (0x7DAB58, 7, 3),
         (0x7DAB7E, 7, 3), (0x7DABA4, 7, 3), (0x7DABCA, 7, 3), (0x7DABF0, 7, 3), (0x7DAC16, 7, 3), (0x7DAC31, 7, 3),
         (0x7DAC57, 7, 3), (0x7DAC86, 7, 3), (0x7DDF2C, 7, 3), (0x7DFBCB, 7, 3), (0x81DE07, 8, 3), (0x81DE28, 7, 3),
         (0x81DE41, 7, 3), (0x81DE5A, 7, 3), (0x81DE84, 7, 3), (0x81DE9F, 8, 3))
DIGEST = "5e62165620b50ae3ca64119aa662e27c8f804e093b286c8a23cbe28c3515806e"   # the 52 instructions, normalized


def instructions(normal):
    return b"".join(normal[a-BASE:a-BASE+size] for a, size, _ in SITES)


def discover(blob, base):
    normal = audit.normalize(blob, base)
    if hashlib.sha256(instructions(normal)).hexdigest() != DIGEST:
        raise ValueError("Month records refuse changed native code.")
    name = struct.unpack_from("<I", normal, VMT-0x38-BASE)[0]-BASE
    if normal[name:name+14] != b"\x0dTfrmBuildCamp" or struct.unpack_from("<i", normal, VMT-0x34-BASE)[0] != SIZE:
        raise ValueError("Unsupported campaign window class.")
    delta = base-BASE
    return dict(main=MAIN+delta, vmt=VMT+delta,
                sites=[(a+delta+at, struct.unpack_from("<I", normal, a+at-BASE)[0]) for a, _, at in SITES])


def plans(info, main, table):
    """Field offsets moved so that main+TABLE (1890, month 0) becomes table."""
    from hull_rules import patch
    shift = table-(main+TABLE)
    return [patch("Month records past 1990", at, struct.pack("<I", disp), struct.pack("<I", (disp+shift) & 0xFFFFFFFF))
            for at, disp in info["sites"]]
