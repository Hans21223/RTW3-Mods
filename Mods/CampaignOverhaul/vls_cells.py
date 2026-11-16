"""Native designer VLS banks using saved missile mounts and finite ammunition.

A SAM/SSM mount with 8/16/32/64 tubes is a VLS bank (native launchers stop at
5 tubes): centreline mounts, and side mounts on hulls of SIDE_VLS_TONS and up. Each tube is
one loaded cell, with no reserve reloads. Each size needs its Modern Research
technology, and a hull carries about one cell per 80 tons. Cells weigh like
real loaded VLS cells and cost one topside point per 8 cells. Native missile
identities, cost per weight, damage, detection and range rules remain in use.
Medium SSM box launchers weigh 4 t a missile (and reload) instead of 8.
No sidecar save.
"""
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import time

import modern_research as audit
import modern_tree as tree
import weekly_runtime as rt
from campaign_security import Code
from hull_rules import patch, LIMITS

BASE = 0x301000
REPORT = Path(__file__).with_name("vls_cells_report.json")
CELLS = (8, 16, 32, 64)
# Loaded cell weight in tenths of tons by MountType: heavy/medium/light SAM,
# heavy/medium/light SSM (Mk 41 strike module ~14.5 t per 8 cells empty).
CELL_TENTHS = (50, 35, 10, 100, 35, 15)
QUAD_WEIGHT = 2      # a quad-packed light SAM cell: 2 t instead of 1
# CalcWeight's medium SSM launcher case: (tubes + reloads) x 8 t natively, almost a heavy SSM's x 10 for about half
# its damage (26 against 32 inches); x 4 (Harpoon-class canisters) makes a ton of them outhit a ton of heavies.
MEDIUM_BOX = (0x951312, "c1e203", "c1e202")   # shl edx,3 -> shl edx,2
TONS_PER_CELL = 80   # modern_tree.VLS_DENSE research packs cells closer
# Hulls laid down earlier lack the deep magazine volume (the 1980s Iowa refits got
# box launchers, not VLS). New classes, even developed from old ones, get the
# current year as BuildYear; editing an existing class keeps its own.
VLS_HULL_YEAR = 1960
# Mk 41-style 8-cell modules (2 cells across an uptake, 4 along: 2.6 x 3.4 m),
# laid out across x along: 8 = 1x1, 16 = 2x1, 32 = 2x2, 64 = 4x2. Side banks run
# along the hull edge instead (Zumwalt's peripheral VLS): 16 = 1x2, 32 = 1x4,
# 64 = 2x4. Native mount shapes draw at about 100 units per metre.
MODULES = {8: (1, 1), 16: (2, 1), 32: (2, 2), 64: (4, 2)}
SIDE_MODULES = {8: (1, 1), 16: (1, 2), 32: (1, 4), 64: (2, 4)}
SIDE_VLS_TONS = 10000   # side (wing) mounts can become VLS banks on hulls this size and up
# Design-report rules in this adapter's verified window that only restrict size or type (hull_rules.FREED_ERRORS
# frees the others): (name, error block, bytes replaced, where its guard jumps when the rule is met).
FREED_RULES = (("carriers may carry heavy SAMs", 0x5D6843, 2, 0x5D685F),
               ("side launchers and tubes on ships below 1200 t", 0x5D6A70, 5, 0x5D6AF3),
               ("side launchers and tubes on ships below 6000 t", 0x5D6B17, 2, 0x5D6B95))
UNITS_PER_M, ANGLE_PER_DEGREE, VERTICES = 100, 5_400_000, 25
# AI designs (AIDesignShip, after its second AdjustAIDesignWeights) turn their missile launchers into VLS banks:
# the smallest researched bank that holds the launcher's whole load (tubes x (1 + reloads)), else the largest
# with at least its tubes, within the designer's rules (this year as the hull year, position, missile type,
# cells per ton) and the weight left. AIDesignShip also serves the designer's own AI-design button.
# Starting fleets (1980 and 2000) are raw templates that never see AIDesignShip: START_SITE gives them the pass.
# Destroyers: every DD template is 3,800 t or less, and the last template era is the 1960s. From GROW's years
# a DD hull may grow to tons/3800 of its template (within the nation's dock and the DD class limit), its SAM
# launchers take the largest bank that fits, and the hull shrinks back to what the cells (cells per ton) and
# the weight need. In game this runs after AIDesignShip's own hull trim (GROW_SITE), which would undo it.
# Weight still unused on a hull that stayed larger goes into speed, then belt and deck armour, up to the era's
# limits: the fast gas-turbine destroyers of the 1970s, the slower and better protected ones after them.
AI_SITE, START_SITE, GROW_SITE = 0x7B6AD4, 0x81A1E7, 0x7B6B2D
GROW = ((1975, 6000, 34, 1), (1985, 8000, 32, 2), (2000, 9500, 31, 3))   # from, tons, knots, armour (half inches)
SPEED, DESIGN_SPEED, BELT, DECK, AIR, FUNDS = 0x38, 0xA20, 0x40, 0x44, 0x9E0, 0x1B5
# The other types grow in new classes (after the hull trim) when the economy carries it, and only with
# large-hulls loaded (the DD limit above its native 3,800 t): TIERS percent of the designed hull, for a nation
# that earns more than it spends and holds a month of budget in cash / with a surplus of a tenth of its monthly
# budget and three months in cash; within its dock and the class limit. The weight goes into the largest SAM
# banks, aircraft on carriers (to AIR_PERCENT), KNOTS more speed, then belt and deck; the rest of the hull is
# given back. A starting fleet's classes take the first tier: a starting nation's funds are no measure.
# type: (class limit, half inches more armour)
TIERS, KNOTS, AIR_PERCENT, AIR_STEP = (120, 140), 2, 130, 5
CAPITAL = {0: (LIMITS["overall"], 6), 1: (LIMITS["overall"], 4), 3: (LIMITS["CA"], 3), 4: (LIMITS["CL"], 2),
           5: (LIMITS["CV"], 2), 6: (LIMITS["CVL"], 1)}     # BB, BC, CA, CL, CV, CVL
DD, DD_TONS, DD_LIMIT, DOCK, TYPE, WEIGHT_LEFT = 9, 3800, 0x72A607, 0x11D, 0x9D3, 0xB20
PASS = 0x40                       # the pass inside the ai_design routine, after its hook
CONVERT, START, AFTER_TRIM = 0, 5, 3   # pass modes: 1 destroyers grow, 2 after the hull trim, 4 the start
WINDOWS = (
    (0x5EE794, 369, "e223e9bc2ae171ec01adbac5f2a9dde76b95bd909e0ff4a899d72874114edaac"),
    # bnAddMissileClick: medium and heavy SAM launchers off the centreline only on carriers (CV, CVL).
    (0x5EEB3D, 0x2E, "3937d4f6a883e2462f58538f060fb1fbd744d2994c4c7ccf541e4afc8367e1d2"),
    (0x5EF2D4, 174, "54ac3a2d49205d6339e640ccdabee8be7a28a2a7a51dc06866ee9f2e66beb927"),
    (0x5F6834, 158, "b6515df233f315484e3045bb34029542d92444415876316d26583d40fa3c17ed"),
    (0x5D67E4, 1053, "bc4436d965e183522089e4dbb0362b2539282af3e8490f006feb709336748418"),
    (0x7297D8, 97, "a8e3bb0b5f06f219293da8529e735c6b0ae9924ff6eaea4c3a6fed72a0f0a3db"),
    (0x9253B4, 1308, "50f4f870b031b6c825dd4d972098443a9cfc6717f682931e6fd89377d8bf80af"),
    (0x8D48D3, 17, "9291a82222e385a9310e9421a2bd4a2378e1aeaa7e95de0de4aea1914515a6e3"),
    (0x917F54, 324, "65339838e3728f21b3c4e7f1886c1bc032b253e74855f5cc67ddacca044441ad"),
    (0x6CB931, 102, "3d0bb8ea7ec9de3f2d3908c8f30439e9073299a4adbe02d61df39c8c52f8675f"),
    (0x9511BC, 718, "47a7f6ff919b85c3ffda78b88339055590141af65fbfa139e33da651cfaae1c0"),
    (0x52729C, 132, "9646bdddf036eb19c126d1fb228ea7b5a86aa5cc164e821ee3627afbb7c3a81f"),
    (0x52AF2C, 32, "e6769f79674b299448dd3efc6f0576e4512ee57cd521e20cda129671a1e8d8f3"),
    (0x52A91C, 116, "175f1359ae57a062a2274e559a9c12ae2bd79edc91a1b1487f2450c0a6480821"),
    (0x94A23C, 830, "855a4fd9f6b6dbe0fe46ee73b3239cf7e34d0e2c8e535942ecce2dc03a9cc355"),
    (0x83E5D0, 1958, "9be775750dabdcd12d0dd134887777749673a5d8a181d779b076bde488383223"),
    # AIDesignShip: ECX = GetBNation(main, design.Nation), EDX = design, call AdjustAIDesignWeights.
    (0x7B6AC0, 0x19, "fa85ad01d7142c28927df51abb3dbb761c0cc9d98ab053eab30597f8a51feaa1"),
    # The start's class from a template: after 1970, call its modern fit (main, design, nation).
    (0x81A1D4, 0x1A, "82f37672b95dab7ea8e71dc70f347709b0e110e225736e3f17e1eb387f0c2fcd"),
    (0x77DCFC, 0x20, "abaf1b7cb9c588798c6735a912f458c08f72abf925d75969c99dd50950e029c5"),
    (0x950318, 0x20, "a48c3c4e31246315e7f78b7c3780733e88c497746ab0d1d8d9f886f3ccfdfbcb"),   # redraw a resized hull
    # AIDesignShip after its hull trim: mov eax,[ebp-18h] / cmp byte [eax+0BBFh],0
    (0x7B6B2D, 0x14, "6b3f2b4808525b65c7042b59715e2693521e46666cc4b0747a797c81f3a9dccf"),
)


def discover(blob, base):
    normal = audit.normalize(blob, base)
    for address, size, digest in WINDOWS:
        if hashlib.sha256(normal[address-BASE:address-BASE+size]).hexdigest() != digest:
            raise ValueError("VLS refuses changed native code at " + hex(address))
    # Class and published field metadata, not guessed free object bytes.
    mount_fields = blob[0x9339E7-BASE:0x933AD8-BASE]
    ship_fields = blob[0x9343A0-BASE:0x9346E0-BASE]
    for fields, name, offset in ((mount_fields, "Tubes", 4), (mount_fields, "MountType", 0xE),
                                 (mount_fields, "Reloads", 0xF), (mount_fields, "Weight", 0xA),
                                 (ship_fields, "Displacement", 0x2C), (ship_fields, "TorpedomountList", 0x9E)):
        key = bytes([len(name)])+name.encode()+b"\x02\x00\x02"
        matches = list(re.finditer(re.escape(key), fields))
        if len(matches) != 1 or struct.unpack_from("<I", fields, matches[0].start()-4)[0] != offset:
            raise ValueError("Unsupported VLS mount field: " + name)
    if normal[0x933B1E-BASE:0x933B1E-BASE+14] != b"\x0dTTorpedomount":
        raise ValueError("Unsupported native missile mount class.")
    delta = base-BASE
    info = {k: v+delta for k, v in dict(
        menu_vmt=0x52450C, menu_create=0x52729C, menu_add=0x52AF2C,
        menu_caption=0x52A91C, selected=0x4BC49C, centreline=0x952694,
        missile_allowed=0x747478, refresh=0x5EE794, recalculate=0x9395F8,
        refresh_design=0x5E9D88, sync_preview=0x5E765C, message=0x4D7124,
        mount_vmt=0x9339D4, sam_single=0x918036, sam_double=0x918052,
        has_research=0x729FA4, topside_points=0x94A41C, bearing=0x8EC340, carrier=0x950090,
        draw_vertex=0x83ECEB, adjust_weights=0x77F2F4, year=0x9F7328,
        monthly_balance=0x72D2EC, modified_budget=0x71F06C,
        modern_fit=0x77DCFC, rescale=0x950318, get_nation=0x750040, dd_limit=DD_LIMIT).items()}
    # CheckDDSize's hard maximum (cmp esi, 3800), read when a design is made: large-hulls raises it.
    if rt.method_address(blob, base, "CheckDDSize") != info["dd_limit"]-11 or blob[DD_LIMIT-2-BASE:DD_LIMIT-BASE] != b"\x81\xfe":
        raise ValueError("Unsupported native destroyer size check for VLS.")
    if rt.method_address(blob, base, "HasResearchId") != info["has_research"]:
        raise ValueError("Unsupported native research lookup for VLS.")
    # CalcWeight's own design-form pointer: the nation whose research it checks.
    info["design_form"] = struct.unpack_from("<I", blob, 0x951212-BASE)[0]
    if blob[MEDIUM_BOX[0]-BASE:MEDIUM_BOX[0]-BASE+3].hex() != MEDIUM_BOX[1]:
        raise ValueError("VLS refuses changed native code: the medium SSM launcher weight.")
    info["medium_box"] = MEDIUM_BOX[0]+delta
    info["sites"] = [{"name": name, "address": address+delta,
                      "original": blob[address-BASE:address-BASE+size].hex()}
                     for name, address, size in (
                         ("refresh", 0x5EE794, 8), ("arc", 0x9253B4, 6),
                         ("nation_limit", 0x7297D8, 5), ("remaining", 0x8D48D3, 6),
                         ("reload_button", 0x5EF2D4, 5), ("reload_menu", 0x5F6834, 5),
                         ("cell_label", 0x5EE87B, 5), ("sam_remaining", 0x918030, 6),
                         ("weight", 0x9511BC, 6), ("topside", 0x94A37C, 5),
                         ("drawing", 0x83EBD0, 6), ("side_tubes", 0x5D6A02, 6), ("side_sam", 0x5EEB4A, 5),
                         ("ai_design", AI_SITE, 5), ("ai_start", START_SITE, 5), ("ai_grow", GROW_SITE, 10))]
    info["freed"] = [{"name": name, "address": address+delta, "end": end+delta,
                      "original": blob[address-BASE:address-BASE+size].hex()} for name, address, size, end in FREED_RULES]
    return info


def is_vls(address, info):
    """EAX mount -> bool. Preserve other registers, including EDX bearing."""
    c = Code(address); c.emit(bytes.fromhex("53528bd885db")); c.branch(b"\x0f\x84", "no")
    c.emit(bytes.fromhex("0fb6430e48")); c.emit(b"\x83\xf8\x05"); c.branch(b"\x0f\x87", "no")
    c.emit(bytes.fromhex("8b4304"))
    for cells in CELLS:
        c.emit(b"\x83\xf8"+bytes([cells])); c.branch(b"\x0f\x84", "vls")
    c.branch(b"\xe9", "no")
    c.mark("vls"); c.emit(b"\xb8\x01\x00\x00\x00"); c.branch(b"\xe9", "done")   # any position
    c.mark("no"); c.emit(bytes.fromhex("31c0"))
    c.mark("done"); c.emit(bytes.fromhex("5a5bc3")); return c.finish()


def eligible(address, info, editable=True):
    """EAX editable form -> selected centreline missile mount, or zero."""
    c = Code(address); c.emit(bytes.fromhex("53568bd8"))
    if editable:
        c.emit(bytes.fromhex("80bb670e000000")); c.branch(b"\x0f\x84", "no")
    c.emit(bytes.fromhex("8b836c0e000085c0")); c.branch(b"\x0f\x84", "no")
    c.emit(bytes.fromhex("8b83b409000085c0")); c.branch(b"\x0f\x84", "no")
    c.branch(b"\xe8", info["selected"]); c.emit(bytes.fromhex("85c0")); c.branch(b"\x0f\x84", "no")
    c.emit(bytes.fromhex("8b702885f6")); c.branch(b"\x0f\x84", "no")
    c.emit(b"\x81\x3e"); c.u32(info["mount_vmt"]); c.branch(b"\x0f\x85", "no")
    c.emit(bytes.fromhex("0fb6460e48")); c.emit(b"\x83\xf8\x05"); c.branch(b"\x0f\x87", "no")
    if editable:   # a new bank: centreline, or a side mount on a big hull
        c.emit(bytes.fromhex("8bc6")); c.branch(b"\xe8", info["centreline"])
        c.emit(b"\x84\xc0"); c.branch(b"\x0f\x85", "position")
        c.emit(b"\x8b\x83"); c.u32(0xE6C); c.emit(b"\x81\x78\x2c"); c.u32(SIDE_VLS_TONS); c.branch(b"\x0f\x8c", "no")
        c.mark("position")
        c.emit(bytes.fromhex("8b83630c00000fb6560e")); c.branch(b"\xe8", info["missile_allowed"])
        c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "no")
    c.emit(b"\x8b\xc6"); c.branch(b"\xe9", "done")
    c.mark("no"); c.emit(b"\x31\xc0")
    c.mark("done"); c.emit(bytes.fromhex("5e5bc3")); return c.finish()


def ensure_menu(address, state, info, captions, handlers):
    c = Code(address); c.emit(bytes.fromhex("5356578bd8"))
    c.emit(b"\x3b\x1d"); c.u32(state); c.branch(b"\x0f\x84", "done")
    c.emit(bytes.fromhex("8b8b3c0a000085c9")); c.branch(b"\x0f\x84", "done")
    # Parent and children are ordinary owned VCL TMenuItems.
    def create(caption, handler=None):
        c.emit(b"\xb8"); c.u32(info["menu_vmt"]); c.emit(bytes.fromhex("b2018bcb"))
        c.branch(b"\xe8", info["menu_create"]); c.emit(b"\x8b\xf0")
        if handler is not None:
            c.emit(bytes.fromhex("c78698000000")); c.u32(handler)
            c.emit(bytes.fromhex("899e9c000000"))
        c.emit(b"\xba"); c.u32(caption); c.emit(b"\x8b\xc6"); c.branch(b"\xe8", info["menu_caption"])
    create(captions[0]); c.emit(b"\x8b\xfe")
    for caption, handler in zip(captions[1:], handlers):
        create(caption, handler); c.emit(bytes.fromhex("8bc78bd6")); c.branch(b"\xe8", info["menu_add"])
    c.emit(bytes.fromhex("8b833c0a00008b40448bd7")); c.branch(b"\xe8", info["menu_add"])
    c.emit(b"\x89\x1d"); c.u32(state)
    c.mark("done"); c.emit(bytes.fromhex("5f5e5bc3")); return c.finish()


def convert(address, info, eligibility, predicate, cells, texts):
    c = Code(address); c.emit(bytes.fromhex("9c608bd8")); c.branch(b"\xe8", eligibility)
    c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "invalid")
    c.emit(b"\x8b\xf0\x8b\x83"); c.u32(0xC63); c.emit(b"\xba"); c.u32(tree.VLS_CELLS[cells])
    c.branch(b"\xe8", info["has_research"]); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "research")
    c.emit(b"\x8b\x83"); c.u32(0xE6C); c.emit(b"\x81\xb8"); c.u32(0xE4); c.u32(VLS_HULL_YEAR)   # BuildYear
    c.branch(b"\x0f\x8c", "age")
    # Cells of the design's other VLS banks plus this one, against Displacement.
    c.emit(b"\x6a\x00\x8b\xbb"); c.u32(0xE6C); c.emit(b"\x8b\xbf"); c.u32(0x9E); c.emit(b"\x31\xed")
    c.mark("loop"); c.emit(b"\x3b\x6f\x08"); c.branch(b"\x0f\x8d", "counted")
    c.emit(bytes.fromhex("8b47048b04a83bc6")); c.branch(b"\x0f\x84", "next")
    c.emit(b"\x50"); c.branch(b"\xe8", predicate); c.emit(b"\x59\x84\xc0"); c.branch(b"\x0f\x84", "next")
    c.emit(bytes.fromhex("8b4104010424"))
    c.mark("next"); c.emit(b"\x45"); c.branch(b"\xe9", "loop")
    # Restore EBP (pushad copy) before native calls; it was the loop index.
    c.mark("counted"); c.emit(b"\x5f\x8b\x6c\x24\x08\x83\xc7"+bytes([cells])+b"\x68"); c.u32(TONS_PER_CELL)
    for index, (ident, tons) in enumerate(tree.VLS_DENSE):   # later research packs denser
        c.emit(b"\x8b\x83"); c.u32(0xC63); c.emit(b"\xba"); c.u32(ident); c.branch(b"\xe8", info["has_research"])
        c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", f"dense{index}")
        c.emit(b"\xc7\x04\x24"); c.u32(tons)
        c.mark(f"dense{index}")
    c.emit(b"\x59\x0f\xaf\xf9\x8b\x83"); c.u32(0xE6C); c.emit(b"\x3b\x78\x2c")
    c.branch(b"\x0f\x8f", "hull")
    c.emit(b"\xc7\x46\x04"); c.u32(cells)
    c.emit(bytes.fromhex("c7460f000000008b836c0e0000")); c.branch(b"\xe8", info["recalculate"])
    c.emit(b"\x8b\xc3"); c.branch(b"\xe8", info["refresh"])
    c.emit(b"\x8b\xc3"); c.branch(b"\xe8", info["refresh_design"])
    c.emit(bytes.fromhex("8bc3b201")); c.branch(b"\xe8", info["sync_preview"])
    c.branch(b"\xe9", "done")
    for label, text in zip(("invalid", "research", "hull", "age"), texts):
        c.mark(label); c.emit(b"\xb8"); c.u32(text)
        c.emit(bytes.fromhex("83caff83c9ff")); c.branch(b"\xe8", info["message"]); c.branch(b"\xe9", "done")
    c.mark("done"); c.emit(bytes.fromhex("619dc3")); return c.finish()


def weight(address, site, info, predicate, table):
    """CalcWeight(EAX mount): a VLS bank weighs its loaded cells, not a launcher."""
    c = Code(address); c.emit(b"\x50"); c.branch(b"\xe8", predicate); c.emit(b"\x84\xc0\x58")
    c.branch(b"\x0f\x84", "native")
    # tenths = Tubes * CELL_TENTHS[MountType-1]; 1..6 is guaranteed by the predicate.
    c.emit(bytes.fromhex("5351528bd80fb64b0e8b43040faf048d")); c.u32(table-4)
    # A quad-packed light SAM cell (four missiles, modern_tree.QUAD_PACK) weighs QUAD_WEIGHT times a single one.
    c.emit(b"\x83\xf9\x03"); c.branch(b"\x0f\x85", "single"); c.emit(b"\x50\xa1"); c.u32(info["design_form"])
    c.emit(b"\x8b\x00\x8b\x80"); c.u32(0xC63); c.emit(b"\xba"); c.u32(tree.QUAD_PACK)
    c.branch(b"\xe8", info["has_research"]); c.emit(b"\x84\xc0\x58"); c.branch(b"\x0f\x84", "single")
    c.emit(b"\x6b\xc0"+bytes([QUAD_WEIGHT]))
    c.mark("single")
    c.emit(b"\x50\x6a\x64")   # [esp] = percent of full weight, [esp+4] = tenths
    for index, (ident, lighter) in enumerate(tree.VLS_LIGHT):
        c.emit(b"\xa1"); c.u32(info["design_form"])
        c.emit(b"\x8b\x00\x8b\x80"); c.u32(0xC63); c.emit(b"\xba"); c.u32(ident)
        c.branch(b"\xe8", info["has_research"]); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", f"light{index}")
        c.emit(b"\x83\x2c\x24"+bytes([lighter]))
        c.mark(f"light{index}")
    # Whole tons, rounded up: (tenths * percent + 999) / 1000.
    c.emit(bytes.fromhex("59580fafc105e703000033d2b9e8030000f7f189430a5a595bc3"))
    c.mark("native"); c.emit(bytes.fromhex(site["original"])); c.branch(b"\xe9", site["address"]+6)
    return c.finish()


def shapes():
    """Native mount polygons: per size, an outline pass then a grid-line pass.

    Points are (angle, distance) around the mount; unused points repeat (distance 0).
    The grid pass zigzags along the lines and ends on the border, so its closing
    edge lies on the outline.
    """
    table = []
    for cells, (across, along) in [(n, layout[n]) for layout in (MODULES, SIDE_MODULES) for n in CELLS]:
        y, x = across*130, along*170   # half-widths in cm
        lines_y = [-y+130*i for i in range(1, 2*across)]
        # Every cell row along the bank where it fits in 25 points, else module rows only.
        lines_x = [-x+85*i for i in range(1, 4*along)]
        if 2*(len(lines_y)+len(lines_x))+2 > VERTICES: lines_x = [-x+340*i for i in range(1, along)]
        outline = [(-x, -y), (x, -y), (x, y), (-x, y)]
        grid = []
        for i, ly in enumerate(lines_y):
            grid += [(-x, ly), (x, ly)] if i % 2 == 0 else [(x, ly), (-x, ly)]
        end = grid[-1][0]; side = y
        grid.append((end, side))
        for lx in sorted(lines_x, reverse=end > 0):
            grid += [(lx, side), (lx, -side)]; side = -side
        grid.append((-x, side))
        for points in (outline, grid):
            assert len(points) <= VERTICES
            for px, py in points+[(0, 0)]*(VERTICES-len(points)):
                distance = round(math.hypot(px, py)*UNITS_PER_M/100)
                angle = round(math.degrees(math.atan2(py, px))*ANGLE_PER_DEGREE) if distance else 0
                table.append(struct.pack("<ii", angle, distance))
    return b"".join(table)


def drawing(address, site, info, predicate, table):
    """Per polygon point: VLS banks use the cell-grid shapes, aligned with the ship."""
    c = Code(address); c.emit(b"\x50\x51\x52\x8b\xc3"); c.branch(b"\xe8", predicate)
    c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "native")
    # Cells do not train: use the ship's heading, not the stored launcher bearing.
    c.emit(b"\x8b\x45\x08\x8b\x80"); c.u32(0xA28); c.emit(b"\x31\xd2"); c.branch(b"\xe8", info["bearing"])
    # Point index ((size*2 + pass)*25 + point); size 0-3 from 8/16/32/64 cells, 4-7 for side banks.
    c.emit(bytes.fromhex("8945ec8bc3")); c.branch(b"\xe8", info["centreline"])
    c.emit(bytes.fromhex("0fb6c883f101c1e102"))                       # ecx = 4 off the centreline
    c.emit(bytes.fromhex("8b43040fbdc083e80303c1d1e083c0022b85")); c.u32(-0x15C & 0xFFFFFFFF)
    c.emit(b"\x6b\xc0"+bytes([VERTICES])+b"\x03\x85"); c.u32(-0x154 & 0xFFFFFFFF)
    c.emit(b"\x8b\x14\xc5"); c.u32(table); c.emit(b"\x89\x55\xf0")
    c.emit(b"\x8b\x14\xc5"); c.u32(table+4); c.emit(b"\x89\x55\xe8\x5a\x59\x58")
    c.branch(b"\xe9", info["draw_vertex"])
    c.mark("native"); c.emit(b"\x5a\x59\x58"+bytes.fromhex(site["original"])); c.branch(b"\xe9", site["address"]+6)
    return c.finish()


def side_tubes(address, site, predicate):
    """Design report: a side VLS bank is cells, not a side torpedo mount over 4 tubes."""
    c = Code(address); c.emit(b"\x8b\xc7"); c.branch(b"\xe8", predicate)       # EDI mount
    c.emit(b"\x84\xc0"); c.branch(b"\x0f\x85", site["address"]+0x46)           # next check
    c.emit(b"\x83\x7f\x04\x04"); c.branch(b"\x0f\x8e", site["address"]+0x46)  # native: tubes <= 4
    c.branch(b"\xe9", site["address"]+6)                                          # native error line
    return c.finish()


def side_sam(address, site, info):
    """Adding a medium or heavy SAM launcher off the centreline (ESI form, EAX design): carriers natively,
    and any hull once the designing nation has Vertical launch cells, so the mount can become a side bank."""
    c = Code(address); c.branch(b"\xe8", info["carrier"]); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x85", "done")
    c.emit(b"\x8b\x86"); c.u32(0xC63); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "done")   # no nation: native
    c.emit(b"\xba"); c.u32(tree.VLS_CELLS[8]); c.branch(b"\xe8", info["has_research"])
    c.mark("done"); c.branch(b"\xe9", site["address"]+5); return c.finish()


def topside(address, site, info, predicate):
    """VLS cells sit below deck: one topside point per 8 cells, no launcher extras."""
    c = Code(address); c.emit(bytes.fromhex("518b0350")); c.branch(b"\xe8", predicate)
    c.emit(b"\x84\xc0\x58\x59"); c.branch(b"\x0f\x84", "native")
    c.emit(bytes.fromhex("8b400483c007c1e8038906")); c.branch(b"\xe9", info["topside_points"])
    c.mark("native"); c.emit(bytes.fromhex(site["original"])); c.branch(b"\xe9", site["address"]+5)
    return c.finish()


def wrapper(address, site, helper, mode):
    c = Code(address); old = bytes.fromhex(site["original"])
    if mode == "refresh":
        c.emit(bytes.fromhex("9c60")); c.branch(b"\xe8", helper); c.emit(bytes.fromhex("619d")+old)
    elif mode in ("arc", "nation_limit"):
        c.emit(b"\x50")
        if mode == "nation_limit": c.emit(b"\x8b\xc1")  # ECX is the mount in this method.
        c.branch(b"\xe8", helper); c.emit(b"\x84\xc0\x58"); c.branch(b"\x0f\x84", "native")
        c.emit(b"\xb0\x01"+(b"\xc2\x04\x00" if mode == "nation_limit" else b"\xc3"))
        c.mark("native"); c.emit(old)
    elif mode == "remaining":
        # Only VLS needs a total-cell bound as well as the requested salvo size.
        c.emit(bytes.fromhex("51528bc6")); c.branch(b"\xe8", helper)
        c.emit(bytes.fromhex("84c08b4604")); c.branch(b"\x0f\x84", "counted")
        c.emit(bytes.fromhex("3b86f1000000")); c.branch(b"\x0f\x8e", "counted")
        c.emit(bytes.fromhex("8b86f1000000"))
        c.mark("counted"); c.emit(bytes.fromhex("5a593b4508"))
    else: raise ValueError("Unknown VLS wrapper")
    c.branch(b"\xe9", site["address"]+len(old)); return c.finish()


def reload_guard(address, site, info, eligibility, predicate, error_text):
    c = Code(address); c.emit(bytes.fromhex("9c60")); c.branch(b"\xe8", eligibility)
    c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "normal")
    c.branch(b"\xe8", predicate); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "normal")
    c.emit(b"\xb8"); c.u32(error_text); c.emit(bytes.fromhex("83caff83c9ff")); c.branch(b"\xe8", info["message"])
    c.emit(bytes.fromhex("619dc3"))
    c.mark("normal"); c.emit(bytes.fromhex("619d")+bytes.fromhex(site["original"]))
    c.branch(b"\xe9", site["address"]+len(bytes.fromhex(site["original"]))); return c.finish()


def label_wrapper(address, site, predicate, text):
    c = Code(address); c.emit(bytes.fromhex("9c608bc3")); c.branch(b"\xe8", predicate)
    c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "normal")
    c.emit(bytes.fromhex("619d68")); c.u32(text); c.branch(b"\xe9", "done")
    c.mark("normal"); c.emit(bytes.fromhex("619d")+bytes.fromhex(site["original"]))
    c.mark("done"); c.branch(b"\xe9", site["address"]+5); return c.finish()


def sam_remaining(address, predicate, info):
    """A native two-SAM burst must use one shot when a VLS has one cell left."""
    c = Code(address); c.emit(bytes.fromhex("9c608bc3")); c.branch(b"\xe8", predicate)
    c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "normal")
    c.emit(bytes.fromhex("83bbf100000001")); c.branch(b"\x0f\x85", "normal")
    c.emit(bytes.fromhex("619d")); c.branch(b"\xe9", info["sam_single"])
    c.mark("normal"); c.emit(bytes.fromhex("619d803c2400"))
    c.branch(b"\x0f\x84", info["sam_double"])
    c.branch(b"\xe9", info["sam_single"]); return c.finish()


def ai_hook(address, site, native, pass_address, scratch, mode, rescale=None):
    """Replaces a call native(EAX main, EDX design, ECX nation): the call, then the pass in this mode."""
    c = Code(address)
    c.emit(b"\x52\x51"); c.branch(b"\xe8", native); c.emit(b"\x59\x5a")
    c.emit(b"\x60\x8b\xda\x8b\xf1\xc7\x05"); c.u32(scratch+0x18); c.u32(mode)              # EBX design, ESI nation
    c.branch(b"\xe8", pass_address)
    if rescale:   # a grown hull is drawn at its new size (AIDesignShip does this itself)
        c.emit(b"\x8b\x15"); c.u32(scratch+0x10); c.emit(b"\x85\xd2"); c.branch(b"\x0f\x84", "same")
        c.emit(b"\x8b\xc3"); c.branch(b"\xe8", rescale); c.mark("same")
    c.emit(b"\x61"); c.branch(b"\xe9", site["address"]+5); return c.finish()


def ai_grow(address, site, info, pass_address, scratch):
    """AIDesignShip after its hull trim (EDI main, [EBP-18h] design): destroyers grow; then the replaced code."""
    c = Code(address)
    c.emit(b"\x60\x8b\x5d\xe8\x8b\x53\x1c\x8b\xc7"); c.branch(b"\xe8", info["get_nation"]); c.emit(b"\x8b\xf0")
    c.emit(b"\xc7\x05"); c.u32(scratch+0x18); c.u32(AFTER_TRIM); c.branch(b"\xe8", pass_address)
    c.emit(b"\x61"+bytes.fromhex(site["original"])); c.branch(b"\xe9", site["address"]+len(site["original"])//2)
    return c.finish()


def ai_pass(address, info, predicate, scratch):
    """EBX design, ESI nation, [scratch+18h] mode: launchers become VLS banks; a destroyer may grow for them."""
    capacity, mount, old_tubes, old_reloads, original, per_cell, mode, knots, armour, air = (
        scratch+4*i for i in range(10))
    c = Code(address)

    def recalculate(): c.emit(b"\x8b\xc3"); c.branch(b"\xe8", info["recalculate"])
    c.emit(b"\xc7\x05"); c.u32(original); c.u32(0)                                     # the hull has not grown
    c.emit(b"\x85\xf6"); c.branch(b"\x0f\x84", "done")
    # Every caller gives the new class this year's BuildYear after AIDesignShip; until then it holds the template's.
    c.emit(b"\xa1"); c.u32(info["year"]); c.emit(b"\x81\x38"); c.u32(VLS_HULL_YEAR); c.branch(b"\x0f\x8c", "done")
    c.emit(b"\x80\xbb"); c.u32(TYPE); c.emit(bytes([DD])); c.branch(b"\x0f\x84", "destroyer")
    c.emit(b"\xf6\x05"); c.u32(mode); c.emit(b"\x06"); c.branch(b"\x0f\x84", "cells")
    # After the hull trim or at the start, another type: its tier (EDI percent), then its class limit and armour.
    c.emit(b"\x81\x3d"); c.u32(info["dd_limit"]); c.u32(DD_TONS); c.branch(b"\x0f\x8e", "same")
    c.emit(b"\x83\xbb"); c.u32(WEIGHT_LEFT); c.emit(b"\x00"); c.branch(b"\x0f\x8c", "same")
    c.emit(b"\xbf"); c.u32(TIERS[0]); c.emit(b"\xf6\x05"); c.u32(mode); c.emit(b"\x02"); c.branch(b"\x0f\x84", "tier")
    c.emit(b"\x8b\xc6"); c.branch(b"\xe8", info["monthly_balance"]); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x8e", "done")
    c.emit(b"\x50\x8b\xc6"); c.branch(b"\xe8", info["modified_budget"]); c.emit(b"\x59")     # EAX budget, ECX balance
    c.emit(b"\x8b\x96"); c.u32(FUNDS); c.emit(b"\x6b\xd2\x0c\x3b\xd0"); c.branch(b"\x0f\x8c", "done")
    c.emit(b"\xbf"); c.u32(TIERS[0]); c.emit(b"\x6b\xc9\x78\x3b\xc8"); c.branch(b"\x0f\x8c", "tier")
    c.emit(b"\x8b\x96"); c.u32(FUNDS); c.emit(b"\xc1\xe2\x02\x3b\xd0"); c.branch(b"\x0f\x8c", "tier")
    c.emit(b"\xbf"); c.u32(TIERS[1])
    c.mark("tier"); c.emit(b"\x0f\xb6\x83"); c.u32(TYPE)
    for kind, (limit, plate) in CAPITAL.items():
        c.emit(b"\x3c"+bytes([kind])); c.branch(b"\x0f\x85", f"kind{kind}")
        c.emit(b"\xb9"); c.u32(limit); c.emit(b"\xba"); c.u32(plate); c.branch(b"\xe9", "capital"); c.mark(f"kind{kind}")
    c.mark("same"); c.emit(b"\xf6\x05"); c.u32(mode); c.emit(b"\x02"); c.branch(b"\x0f\x85", "done")   # no growth:
    c.branch(b"\xe9", "cells")                                                    # the start still converts
    c.mark("capital"); c.emit(b"\x03\x53"+bytes([BELT])+b"\x89\x15"); c.u32(armour)
    c.emit(b"\x8b\x83"); c.u32(DESIGN_SPEED); c.emit(b"\x83\xc0"+bytes([KNOTS])+b"\xa3"); c.u32(knots)
    c.emit(b"\x8b\x83"); c.u32(AIR); c.emit(b"\x69\xc0"); c.u32(AIR_PERCENT); c.emit(b"\x33\xd2\x51\xb9"); c.u32(100)
    c.emit(b"\xf7\xf1\x59\xa3"); c.u32(air)
    c.emit(b"\x8b\x43\x2c\x0f\xaf\xc7\x33\xd2\x51\xb9"); c.u32(10000); c.emit(b"\xf7\xf1\x59\x6b\xc0\x64")
    c.emit(b"\x3b\xc1"); c.branch(b"\x0f\x8e", "dock"); c.emit(b"\x8b\xc1"); c.branch(b"\xe9", "dock")
    c.mark("destroyer"); c.emit(b"\xf6\x05"); c.u32(mode); c.emit(b"\x01"); c.branch(b"\x0f\x84", "cells")
    c.emit(b"\x81\x7b\x2c"); c.u32(DD_TONS); c.branch(b"\x0f\x8f", "cells")             # not a native-size template
    c.emit(b"\x83\xbb"); c.u32(WEIGHT_LEFT); c.emit(b"\x00"); c.branch(b"\x0f\x8c", "cells")
    c.emit(b"\xa1"); c.u32(info["year"]); c.emit(b"\x8b\x08\x33\xc0")                   # ECX year, EAX tons
    for year, tons, speed, plate in GROW:
        c.emit(b"\x81\xf9"); c.u32(year); c.branch(b"\x0f\x8c", "tons"); c.emit(b"\xb8"); c.u32(tons)
        c.emit(b"\xc7\x05"); c.u32(knots); c.u32(speed); c.emit(b"\xc7\x05"); c.u32(armour); c.u32(plate)
    c.mark("tons"); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "cells")
    c.emit(b"\x0f\xaf\x43\x2c\x33\xd2\xb9"); c.u32(DD_TONS*100); c.emit(b"\xf7\xf1\x6b\xc0\x64")   # whole hundreds
    c.emit(b"\x8b\x0d"); c.u32(info["dd_limit"]); c.emit(b"\x3b\xc1"); c.branch(b"\x0f\x8e", "dock"); c.emit(b"\x8b\xc1")
    c.mark("dock"); c.emit(b"\x3b\x86"); c.u32(DOCK); c.branch(b"\x0f\x8e", "docked"); c.emit(b"\x8b\x86"); c.u32(DOCK)
    c.mark("docked"); c.emit(b"\x3b\x43\x2c"); c.branch(b"\x0f\x8e", "cells")
    c.emit(b"\x8b\x4b\x2c\x89\x0d"); c.u32(original); c.emit(b"\x89\x43\x2c"); recalculate()
    c.emit(b"\x83\xbb"); c.u32(WEIGHT_LEFT); c.emit(b"\x00"); c.branch(b"\x0f\x8d", "cells")
    c.emit(b"\xa1"); c.u32(original); c.emit(b"\x89\x43\x2c\xc7\x05"); c.u32(original); c.u32(0); recalculate()
    c.mark("cells"); c.emit(b"\xb9"); c.u32(TONS_PER_CELL)
    for ident, tons in tree.VLS_DENSE:
        c.emit(b"\x51\x8b\xc6\xba"); c.u32(ident); c.branch(b"\xe8", info["has_research"]); c.emit(b"\x59\x84\xc0")
        c.branch(b"\x0f\x84", f"dense{ident}"); c.emit(b"\xb9"); c.u32(tons)
        c.mark(f"dense{ident}")
    c.emit(b"\x89\x0d"); c.u32(per_cell); c.emit(b"\x8b\x43\x2c\x99\xf7\xf9\xa3"); c.u32(capacity)   # cells the hull holds
    c.emit(b"\x33\xed\x33\xff")                                                        # EBP cells used, EDI index
    c.mark("count"); c.emit(b"\x8b\x83"); c.u32(0x9E); c.emit(b"\x3b\x78\x08"); c.branch(b"\x0f\x8d", "counted")
    c.emit(b"\x8b\x40\x04\x8b\x04\xb8\x50"); c.branch(b"\xe8", predicate); c.emit(b"\x59\x84\xc0")
    c.branch(b"\x0f\x84", "count_next"); c.emit(b"\x03\x69\x04")
    c.mark("count_next"); c.emit(b"\x47"); c.branch(b"\xe9", "count")
    c.mark("counted"); c.emit(b"\x33\xff")
    c.mark("mount"); c.emit(b"\x8b\x83"); c.u32(0x9E); c.emit(b"\x3b\x78\x08"); c.branch(b"\x0f\x8d", "trim")
    c.emit(b"\x8b\x40\x04\x8b\x04\xb8\xa3"); c.u32(mount)
    c.emit(b"\x81\x38"); c.u32(info["mount_vmt"]); c.branch(b"\x0f\x85", "next")
    c.emit(b"\x0f\xb6\x48\x0e\x49\x83\xf9\x05"); c.branch(b"\x0f\x87", "next")       # SAM or SSM
    c.emit(b"\x50"); c.branch(b"\xe8", predicate); c.emit(b"\x84\xc0\x58"); c.branch(b"\x0f\x85", "next")
    c.emit(b"\x50"); c.branch(b"\xe8", info["centreline"]); c.emit(b"\x84\xc0\x58"); c.branch(b"\x0f\x85", "position")
    c.emit(b"\x81\x7b\x2c"); c.u32(SIDE_VLS_TONS); c.branch(b"\x0f\x8c", "next")
    c.mark("position"); c.emit(b"\x0f\xb6\x50\x0e\x8b\xc6"); c.branch(b"\xe8", info["missile_allowed"])
    c.emit(b"\x84\xc0"); c.branch(b"\x0f\x84", "next")
    c.emit(b"\x83\x3d"); c.u32(original); c.emit(b"\x00"); c.branch(b"\x0f\x84", "load")   # a grown hull's SAMs:
    c.emit(b"\xa1"); c.u32(mount); c.emit(b"\x80\x78\x0e\x03"); c.branch(b"\x0f\x86", "largest")   # the largest bank
    c.mark("load"); c.emit(b"\xa1"); c.u32(mount); c.emit(b"\x8b\x48\x0f\x41\x0f\xaf\x48\x04")     # ECX = whole load
    for cells in CELLS:
        c.emit(b"\x83\xf9"+bytes([cells])); c.branch(b"\x0f\x8f", f"load{cells}")
        c.emit(b"\x51\xb8"); c.u32(cells); c.branch(b"\xe8", "fits"); c.emit(b"\x59\x84\xc0"); c.branch(b"\x0f\x85", f"take{cells}")
        c.mark(f"load{cells}")
    c.mark("largest"); c.emit(b"\xa1"); c.u32(mount); c.emit(b"\x8b\x48\x04")           # ECX = tubes
    for cells in reversed(CELLS):
        c.emit(b"\x83\xf9"+bytes([cells])); c.branch(b"\x0f\x8f", "next")
        c.emit(b"\x51\xb8"); c.u32(cells); c.branch(b"\xe8", "fits"); c.emit(b"\x59\x84\xc0"); c.branch(b"\x0f\x85", f"take{cells}")
    c.branch(b"\xe9", "next")
    for cells in CELLS:
        c.mark(f"take{cells}"); c.emit(b"\xb9"); c.u32(cells); c.branch(b"\xe9", "take")
    c.mark("take"); c.emit(b"\xa1"); c.u32(mount); c.emit(b"\x8b\x50\x04\x89\x15"); c.u32(old_tubes)
    c.emit(b"\x8b\x50\x0f\x89\x15"); c.u32(old_reloads); c.emit(b"\x89\x48\x04\xc7\x40\x0f\x00\x00\x00\x00\x51\x8b\xc3")
    c.branch(b"\xe8", info["recalculate"]); c.emit(b"\x59\x83\xbb"); c.u32(WEIGHT_LEFT); c.emit(b"\x00")
    c.branch(b"\x0f\x8c", "undo"); c.emit(b"\x03\xe9"); c.branch(b"\xe9", "next")       # used += cells
    c.mark("undo"); c.emit(b"\xa1"); c.u32(mount); c.emit(b"\x8b\x15"); c.u32(old_tubes)
    c.emit(b"\x89\x50\x04\x8b\x15"); c.u32(old_reloads); c.emit(b"\x89\x50\x0f"); recalculate()
    c.mark("next"); c.emit(b"\x47"); c.branch(b"\xe9", "mount")
    # A grown hull gives back what neither the weight nor the cells (EBP of them, per_cell tons each) need.
    c.mark("trim"); c.emit(b"\x83\x3d"); c.u32(original); c.emit(b"\x00"); c.branch(b"\x0f\x84", "done")
    # A destroyer keeps only the hull its cells need and fits out what is left; another type fits out first.
    c.emit(b"\x80\xbb"); c.u32(TYPE); c.emit(bytes([DD])); c.branch(b"\x0f\x85", "fit_first")
    c.branch(b"\xe8", "smaller"); c.branch(b"\xe8", "fit"); c.emit(b"\xc3")
    c.mark("fit_first"); c.branch(b"\xe8", "fit"); c.branch(b"\xe8", "smaller")
    c.mark("done"); c.emit(b"\xc3")
    c.mark("smaller"); c.emit(b"\x83\xbb"); c.u32(WEIGHT_LEFT); c.emit(b"\x64"); c.branch(b"\x0f\x8e", "back")
    c.emit(b"\x8b\x43\x2c\x83\xe8\x64\x3b\x05"); c.u32(original); c.branch(b"\x0f\x8c", "back")
    c.emit(b"\x8b\xcd\x0f\xaf\x0d"); c.u32(per_cell); c.emit(b"\x3b\xc1"); c.branch(b"\x0f\x8c", "back")
    c.emit(b"\x89\x43\x2c"); recalculate(); c.branch(b"\xe9", "smaller")
    # A hull that stayed larger: its unused weight becomes aircraft (carriers), speed, then armour, a step at a
    # time while it fits.
    c.mark("fit"); c.emit(b"\x8b\x43\x2c\x3b\x05"); c.u32(original); c.branch(b"\x0f\x8e", "back")
    c.emit(b"\x0f\xb6\x83"); c.u32(TYPE); c.emit(b"\x2c\x05\x3c\x01"); c.branch(b"\x0f\x87", "faster")   # CV, CVL
    c.mark("wing"); c.emit(b"\x8b\x83"); c.u32(AIR); c.emit(b"\x3b\x05"); c.u32(air); c.branch(b"\x0f\x8d", "faster")
    c.emit(b"\x83\x83"); c.u32(AIR); c.emit(bytes([AIR_STEP])); recalculate()
    c.emit(b"\x83\xbb"); c.u32(WEIGHT_LEFT); c.emit(b"\x00"); c.branch(b"\x0f\x8d", "wing")
    c.emit(b"\x83\xab"); c.u32(AIR); c.emit(bytes([AIR_STEP])); recalculate()

    def speed(step):   # inc or dec the design speed; AIDesignShip ends by copying it to Speed, the start does not
        c.emit(b"\xff"+bytes([step])); c.u32(DESIGN_SPEED); c.emit(b"\x8b\x83"); c.u32(DESIGN_SPEED)
        c.emit(b"\x89\x43"+bytes([SPEED])); recalculate()
    c.mark("faster"); c.emit(b"\x8b\x83"); c.u32(DESIGN_SPEED); c.emit(b"\x3b\x05"); c.u32(knots); c.branch(b"\x0f\x8d", "thicker")
    speed(0x83); c.emit(b"\x83\xbb"); c.u32(WEIGHT_LEFT); c.emit(b"\x00"); c.branch(b"\x0f\x8d", "faster"); speed(0x8b)
    c.mark("thicker"); c.emit(b"\x8b\x43"+bytes([BELT])+b"\x3b\x05"); c.u32(armour); c.branch(b"\x0f\x8d", "back")
    c.emit(b"\xff\x43"+bytes([BELT])+b"\xff\x43"+bytes([DECK])); recalculate()
    c.emit(b"\x83\xbb"); c.u32(WEIGHT_LEFT); c.emit(b"\x00"); c.branch(b"\x0f\x8d", "thicker")
    c.emit(b"\xff\x4b"+bytes([BELT])+b"\xff\x4b"+bytes([DECK])); recalculate()
    c.mark("back"); c.emit(b"\xc3")
    c.mark("fits")          # EAX cells -> AL: researched, and room for them
    c.emit(b"\x50")
    for cells, ident in tree.VLS_CELLS.items():
        c.emit(b"\x83\xf8"+bytes([cells])); c.branch(b"\x0f\x85", f"size{cells}"); c.emit(b"\xba"); c.u32(ident)
        c.branch(b"\xe9", "known"); c.mark(f"size{cells}")
    c.emit(b"\x58"); c.branch(b"\xe9", "no")
    c.mark("known"); c.emit(b"\x8b\xc6"); c.branch(b"\xe8", info["has_research"]); c.emit(b"\x84\xc0\x58")
    c.branch(b"\x0f\x84", "no"); c.emit(b"\x8d\x4c\x05\x00\x3b\x0d"); c.u32(capacity); c.branch(b"\x0f\x8f", "no")
    c.emit(b"\xb0\x01\xc3")
    c.mark("no"); c.emit(b"\x33\xc0\xc3")
    return c.finish()


def ai_vls(address, site, info, predicate, scratch):
    """Replaces AIDesignShip's call AdjustAIDesignWeights(EAX main, EDX design, ECX nation), then converts."""
    hook = ai_hook(address, site, info["adjust_weights"], address+PASS, scratch, CONVERT)
    if len(hook) > PASS: raise ValueError("VLS AI hook exceeds its slot.")
    return hook.ljust(PASS, b"\xcc")+ai_pass(address+PASS, info, predicate, scratch)


def build(allocation, info):
    locations = {name: allocation+offset for name, offset in dict(
        predicate=0, eligible=0x400, ensure=0x800, refresh=0x1000,
        arc=0x1400, nation_limit=0x1800, remaining=0x1C00,
        reload_button=0x2000, reload_menu=0x2400, cell_label=0x2800,
        sam_remaining=0x2C00, selected_mount=0x4000, weight=0x4400, topside=0x4800,
        cell_tenths=0x4C00, drawing=0x5000, shapes=0x5400, side_tubes=0x6400, side_sam=0x6800, ai_design=0x7000,
        ai_start=0x7800, ai_grow=0x7C00).items()}
    handlers = [allocation+0x3000+i*0x400 for i in range(len(CELLS))]
    state = allocation+0xF000; blocks = []; cursor = allocation+0xE000
    def literal(value):
        nonlocal cursor
        data = struct.pack("<HHiI", 1200, 2, -1, len(value))+value.encode("utf-16-le")+b"\0\0"
        blocks.append(dict(name=value, address=cursor, bytes=data.hex()))
        result = cursor+12; cursor += (len(data)+3)&~3; return result
    captions = [literal("VLS cells (no reloads)")]+[literal(str(n)+" cells") for n in CELLS]
    invalid = literal(f"Select an editable SAM or SSM mount first: centreline, or a side mount on a hull of "
                      f"{SIDE_VLS_TONS:,} t or more. Its missile type must be researched.")
    research = literal("This VLS size needs research in the Vertical launch systems branch: 8 cells - Vertical launch cells, "
                       "16 - Modular VLS magazines, 32 - Canister exhaust management, 64 - Large VLS magazines.")
    hull = literal("Too many VLS cells for this hull: about 1 cell per 80 tons of displacement "
                   "(64 tons with Hull-integrated VLS modules, 51 with Peripheral VLS integration). "
                   "Use fewer cells or a larger hull.")
    age = literal("This hull is too old for VLS cells: it was laid down before 1960 and lacks the deep magazine "
                  "space. Design a new class (it may be developed from this one) to fit VLS.")
    no_reload = literal("VLS cells hold one missile each. Change the cell count to increase capacity; there are no reserve reloads.")
    label = literal(" VLS cells (")
    routines = dict(predicate=is_vls(locations["predicate"], info),
                    eligible=eligible(locations["eligible"], info),
                    selected_mount=eligible(locations["selected_mount"], info, editable=False),
                    ensure=ensure_menu(locations["ensure"], state, info, captions, handlers))
    sites = {site["name"]: site for site in info["sites"]}
    for name in ("refresh", "arc", "nation_limit", "remaining"):
        routines[name] = wrapper(locations[name], sites[name],
                                 locations["ensure" if name == "refresh" else "predicate"], name)
    for name in ("reload_button", "reload_menu"):
        routines[name] = reload_guard(locations[name], sites[name], info, locations["selected_mount"], locations["predicate"], no_reload)
    routines["cell_label"] = label_wrapper(locations["cell_label"], sites["cell_label"], locations["predicate"], label)
    routines["sam_remaining"] = sam_remaining(locations["sam_remaining"], locations["predicate"], info)
    routines["weight"] = weight(locations["weight"], sites["weight"], info, locations["predicate"], locations["cell_tenths"])
    routines["topside"] = topside(locations["topside"], sites["topside"], info, locations["predicate"])
    routines["drawing"] = drawing(locations["drawing"], sites["drawing"], info, locations["predicate"], locations["shapes"])
    routines["side_tubes"] = side_tubes(locations["side_tubes"], sites["side_tubes"], locations["predicate"])
    routines["side_sam"] = side_sam(locations["side_sam"], sites["side_sam"], info)
    routines["ai_design"] = ai_vls(locations["ai_design"], sites["ai_design"], info, locations["predicate"], state+0x100)
    routines["ai_start"] = ai_hook(locations["ai_start"], sites["ai_start"], info["modern_fit"],
                                   locations["ai_design"]+PASS, state+0x100, START, info["rescale"])
    routines["ai_grow"] = ai_grow(locations["ai_grow"], sites["ai_grow"], info, locations["ai_design"]+PASS, state+0x100)
    blocks.append(dict(name="shapes", address=locations["shapes"], bytes=shapes().hex()))
    blocks.append(dict(name="cell_tenths", address=locations["cell_tenths"],
                       bytes=struct.pack("<6I", *CELL_TENTHS).hex()))
    for name, code in routines.items():
        if len(code) > (0x800 if name == "ai_design" else 0x400): raise ValueError("VLS routine exceeds reservation: "+name)
        blocks.append(dict(name=name, address=locations[name], bytes=code.hex()))
    for count, handler in zip(CELLS, handlers):
        code = convert(handler, info, locations["eligible"], locations["predicate"], count, (invalid, research, hull, age))
        if len(code) > 0x400: raise ValueError("VLS conversion exceeds reservation")
        blocks.append(dict(name="convert_"+str(count), address=handler, bytes=code.hex()))
    plans = []
    for name, site in sites.items():
        old = bytes.fromhex(site["original"])
        new = b"\xe9"+struct.pack("<i", locations[name]-site["address"]-5)+b"\x90"*(len(old)-5)
        plans.append(patch("VLS cells: "+name, site["address"], old, new))
    plans.append(patch("VLS cells: medium SSM box launchers", info["medium_box"], bytes.fromhex(MEDIUM_BOX[1]),
                       bytes.fromhex(MEDIUM_BOX[2])))
    for rule in info["freed"]:
        old, distance = bytes.fromhex(rule["original"]), rule["end"]-rule["address"]
        new = b"\xeb"+bytes([distance-2]) if len(old) == 2 else b"\xe9"+struct.pack("<i", distance-5)
        plans.append(patch("VLS cells: "+rule["name"], rule["address"], old, new))
    return dict(blocks=blocks, patches=plans, locations=locations, handlers=handlers,
                state=state, cell_options=list(CELLS), saved_in_native_mounts=True,
                reserve_reloads=False, one_missile_per_cell=True,
                cell_weight_tenths=list(CELL_TENTHS), topside_points="1 per 8 cells",
                research=tree.VLS_CELLS, tons_per_cell=TONS_PER_CELL, both_sides=True,
                mixed_missiles_in_one_bank=False, gameplay_verified=False)


def attach(wait=30):
    import ai_runtime as ai
    import live_cheats as live
    import week_display as memory
    ai.checked_game(); memory.configure(); deadline = time.monotonic()+wait
    while True:
        games = [(p,s) for p,s in rt.process_candidates() if s == rt.GAME/"RTW3.exe"]
        if len(games) == 1: break
        if time.monotonic() >= deadline: raise ValueError("Start one local game through Play with mods.")
        time.sleep(0.5)
    pid = games[0][0]; handle = rt.K.OpenProcess(0x438, False, pid)
    if not handle: raise rt.win_error("Cannot open the VLS adapter")
    try:
        module, _ = rt.module_info(pid)
        if REPORT.exists():
            old = json.loads(REPORT.read_text(encoding="utf-8"))
            if old.get("attached") and old.get("pid") == pid and old.get("base") == module and rt.report_is_current(REPORT, pid):
                ai.verify(handle, old["patches"], "replacement"); return old
        # Attaches after live-cheats, whose idle hook would fail live.discover().
        module, base, blob = live.unhooked_text(pid, handle)
        info = discover(blob, base); ai.require_title_screen(handle, live.discover(blob, base))
        allocation = rt.K.VirtualAllocEx(handle, None, 0x10000, 0x3000, 0x40)
        if not allocation: raise rt.win_error("Cannot allocate VLS routines")
        applied = []
        try:
            product = build(allocation, info)
            for block in product["blocks"]:
                memory.write(handle, block["address"], bytes.fromhex(block["bytes"]))
            rt.K.FlushInstructionCache(handle, allocation, 0x10000)
            ai.verify(handle, product["patches"], "original")
            for item in product["patches"]:
                rt.write_code(handle, item["address"], bytes.fromhex(item["original"]), bytes.fromhex(item["replacement"]))
                applied.append(item)
            ai.verify(handle, product["patches"], "replacement")
            saved = dict(product, attached=True, pid=pid, base=module, allocation=allocation,
                         details=info, version=1, personal_saves_modified=False)
            REPORT.write_text(json.dumps(saved, indent=2)+"\n", encoding="utf-8"); return saved
        except Exception:
            for item in reversed(applied):
                rt.write_code(handle, item["address"], bytes.fromhex(item["replacement"]), bytes.fromhex(item["original"]))
            if not applied: rt.K.VirtualFreeEx(handle, allocation, 0, 0x8000)
            raise
    finally: rt.K.CloseHandle(handle)
