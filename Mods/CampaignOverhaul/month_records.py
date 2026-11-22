"""Monthly campaign statistics past 1990 (part of timeline-2030).

TfrmBuildCamp, the campaign window and the game's main object, keeps a [year][month] table of 100-byte month
records (the statistics graphs, the summary and the war history) at main+0x795B+row*1200+month*100, row = year-1900,
inside its own 0x2245C bytes: 1890 to 1990. The native campaign stopped in 1990. Past it, each month's record went
beyond the object, over the next heap blocks (the campaign window's labels), and the VCL later crashed reading one of
them in TControl.GetAction ("Access violation ... Read of address 6C000100", in DoTurn2 or DoStrategicTurn).

All 80 instructions that index the table address it as [main + row*1200 + index*4 + field]: 52 with row = year-1900,
28 with row = the year itself and field less 1900*1200 (the battle result screen and the battle window's close, peace
talks and peace, revolutions, resigning). Adding one constant to their 32-bit field offsets moves the whole table
into a zeroed allocation for 1890 to 2060. No code addresses the table as a whole; only the window's compiler-made
cleanup still walks the old place, where the strings in the records (fields +0x10 and +0x18) stay nil.
Until 2026-11-22 the 28 were missed: past 1990 every battle's result screen wrote beyond the window ("Error in
ShowResultScreen ... Read of address C95DA410"), and so did every peace and revolution.
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
FIELDS = (0x794F, 0x79C0)            # field offsets in a month record, as row = year-1900 instructions hold them
YEAR = 1900*ROW                      # what the calendar-year instructions take off their field offsets
# (instruction, size, offset of its 32-bit field displacement): every reference to the table.
SITES = ((0x6F1C03, 7, 3), (0x6F1E24, 8, 3), (0x6F1E51, 7, 3), (0x6F1E8E, 8, 3), (0x6F1EAF, 7, 3), (0x6F1ECA, 7, 3),
         (0x6F1F02, 8, 3), (0x6F21B7, 8, 3), (0x6F21DC, 7, 3), (0x6F2283, 8, 3), (0x6F22DE, 7, 3), (0x6F2343, 7, 3),
         (0x6F2366, 7, 3), (0x6F297D, 7, 3), (0x6F29CB, 7, 3), (0x6F2EC0, 7, 3), (0x6F2F0F, 7, 3), (0x7DA50C, 8, 3),
         (0x7DA519, 7, 3), (0x7DA525, 7, 3), (0x7DA573, 8, 3), (0x7DA580, 7, 3), (0x7DA58C, 7, 3), (0x7DA5F7, 7, 3),
         (0x7DA629, 7, 3), (0x7DA660, 7, 3), (0x7DA832, 7, 3), (0x7DA85E, 7, 3), (0x7DA88A, 7, 3), (0x7DA8B6, 7, 3),
         (0x7DA8E2, 7, 3), (0x7DA909, 7, 3), (0x7DA935, 7, 3), (0x7DA972, 7, 3), (0x7DA9A8, 7, 3), (0x7DAB58, 7, 3),
         (0x7DAB7E, 7, 3), (0x7DABA4, 7, 3), (0x7DABCA, 7, 3), (0x7DABF0, 7, 3), (0x7DAC16, 7, 3), (0x7DAC31, 7, 3),
         (0x7DAC57, 7, 3), (0x7DAC86, 7, 3), (0x7DDF2C, 7, 3), (0x7DFBCB, 7, 3), (0x81DE07, 8, 3), (0x81DE28, 7, 3),
         (0x81DE41, 7, 3), (0x81DE5A, 7, 3), (0x81DE84, 7, 3), (0x81DE9F, 8, 3),
         # by calendar year: NegotiatePeace, DoPeace, CheckForRevolutionInEnemyNation, resign, DoRevolutionInPlayerNation,
         # ShowResultScreen, the battle window's FormClose
         (0x78B419, 11, 3), (0x78B7BF, 11, 3), (0x78B8E5, 11, 3), (0x78B995, 11, 3), (0x78BAAB, 11, 3), (0x78BBD6, 11, 3),
         (0x78C747, 8, 3), (0x78C77D, 11, 3), (0x78CD95, 8, 3), (0x79617D, 7, 3), (0x796238, 7, 3), (0x7AEC05, 8, 3),
         (0x7AEC12, 11, 3), (0x7CFB9C, 11, 3), (0x895D80, 7, 3), (0x895DD8, 7, 3), (0x895E25, 7, 3), (0x895E52, 11, 3),
         (0x895E81, 7, 3), (0x895EDF, 7, 3), (0x895F0F, 7, 3), (0x895F41, 7, 3), (0x89D873, 7, 3), (0x89D8AE, 8, 3),
         (0x89D8FC, 7, 3), (0x89D950, 7, 3), (0x89D982, 7, 3), (0x89D9AD, 7, 3))
DIGEST = "b0e3dc6313f1ea0df50757513f7b15724c3f5e49126106416be3a46ac7db3f7b"   # the 80 instructions, normalized


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
