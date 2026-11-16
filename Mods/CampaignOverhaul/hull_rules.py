"""Guarded, build-discovered class limits and extended machinery table.

No absolute game addresses are stored here. Error strings anchor the private
validators; public methods are located using the game's Delphi metadata.
"""
import re
import struct
import weekly_runtime as rt

# DD: Zumwalt ~15,900t full load. CL: CG(X) cruiser studies ~25,000t. CA: Alaska 29,800t standard,
# 34,300t full load. KE: Type 26 frigate ~8,000t. CVL: America-class LHA ~45,000t.
LIMITS = {"DD": 16000, "CL": 25000, "CA": 35000, "KE": 8000,
          "CVL": 45000, "CV": 150000, "overall": 200000, "CVL_aircraft": 80}
# Alaska: 12"/50 guns, 9" belt. The native suggestion turns cruisers with 11-inch guns, an 8-inch
# belt or 20,000t+ into BC/BB. Belt (+0x40) is stored in half-inches.
CA_MAX_CALIBRE, CA_MAX_BELT = 12, 20
# Large-hulls allocation: input hook +0, interpolation +0x100, class suggestion here, designer visuals from +0x400.
SUGGESTION_OFFSET = 0x180
MODERN_TORPEDO_YEAR = 1950    # from this campaign year a KE may carry torpedoes (ASW tubes); before it the native ban


def unique(blob, pattern, label):
    found = [m.start() for m in re.finditer(re.escape(pattern), blob)]
    if len(found) != 1:
        raise ValueError(f"Unsupported game build: {label} has {len(found)} matches.")
    return found[0]


def message_refs(blob, base, message):
    raw = message.encode("utf-16-le") + b"\0\0"
    offset = unique(blob, raw, message)
    if struct.unpack_from("<I", blob, offset-4)[0] != len(message):
        raise ValueError("Unexpected Delphi message layout.")
    pointer = struct.pack("<I", base+offset)
    return [m.start() for m in re.finditer(re.escape(pointer), blob)
            if blob[m.start()-1] in (0xb8, 0xba, 0xb9, 0x68)]


def message_ref(blob, base, message):
    candidates = message_refs(blob, base, message)
    if len(candidates) != 1:
        raise ValueError(f"Cannot uniquely locate validator for {message}")
    return candidates[0]


def dpi_scaled(value, reference, design):
    """EDX := value, a position or size at 96 DPI, scaled like the form's own controls: x the reference control's
    width now ([EBX+reference], TControl.Width at +58h) / its design width. RTW3 is PerMonitorV2 DPI-aware, so with
    Windows display scaling above 100% it enlarges its forms; controls a mod adds must follow. Uses EAX and ECX."""
    return (b"\x8b\x83"+struct.pack("<I", reference)+b"\x8b\x40\x58\xba"+struct.pack("<i", value)
            +b"\xf7\xea\xb9"+struct.pack("<I", design)+b"\xf7\xf9\x8b\xd0")


def dpi_scale_routine(reference, design):
    """dpi_scaled as a routine, for code short of room: call it with EDX = value; it keeps every other register."""
    return (b"\x50\x51\x8b\x83"+struct.pack("<I", reference)+b"\x8b\x40\x58\xf7\xea\xb9"+struct.pack("<I", design)
            +b"\xf7\xf9\x8b\xd0\x59\x58\xc3")


def patch(label, address, original, replacement):
    if len(original) != len(replacement):
        raise ValueError("A code patch must retain its original length.")
    return {"label": label, "address": address, "original": original.hex(),
            "replacement": replacement.hex()}


def class_patches(blob, base, allocation, limits=LIMITS):
    patches, strings = [], bytearray()

    def add_string(value):
        while len(strings) % 4:
            strings.append(0)
        address = allocation + 0x8000 + len(strings) + 12
        strings.extend(struct.pack("<HHiI", 1200, 2, -1, len(value)))
        strings.extend(value.encode("utf-16-le") + b"\0\0")
        return address

    def rule(label, message, instruction, new_value, new_message):
        ref = message_ref(blob, base, message)
        start = max(0, ref-0x50)
        offset = start + unique(blob[start:ref], instruction, label)
        replacement = instruction[:-4] + int(new_value).to_bytes(4, "little")
        patches.append(patch(label, base+offset, instruction, replacement))
        patches.append(patch(label+" message", base+ref, blob[ref:ref+4],
                             struct.pack("<I", add_string(new_message))))
        return offset

    rule("DD class ceiling", "A DD must not be larger than 3800 tons, have a speed of at least 20 knots and have torpedoes.",
         b"\x81\x7e\x2c"+struct.pack("<I", 3800), limits["DD"],
         f"A DD must be no larger than {limits['DD']} tons, have at least 20 knots and have torpedoes.")
    rule("Protected CL ceiling", "A protected cruiser CL must be larger than 2000 tons, have a speed of at least 17 knots and be no larger than 9000 tons.",
         b"\x3d"+struct.pack("<I", 11000), limits["CL"],
         f"A protected CL must be larger than 2000 tons, no larger than {limits['CL']} tons and have at least 17 knots.")
    first_cl = rule("Pre-1928 CL ceiling", "A CL must be larger than 2000 tons, have a speed of at least 17 knots and until 1928 be smaller than 8000 tons.",
         b"\x3d"+struct.pack("<I", 8000), limits["CL"],
         f"A CL must be larger than 2000 tons, no larger than {limits['CL']} tons and have at least 17 knots.")
    special = b"\x81\x7e\x2c"+struct.pack("<I", 14000)
    offset = first_cl-0x40 + unique(blob[first_cl-0x40:first_cl], special, "special CL ceiling")
    patches.append(patch("Special CL ceiling", base+offset, special, special[:-4]+struct.pack("<I", limits["CL"])))
    for old in (10000, 12000):
        rule(f"CL {old} ceiling", f"A CL must be larger than 2000 tons, no larger than {old} tons and have a speed of at least 17 knots.",
             b"\x3d"+struct.pack("<I", old), limits["CL"],
             f"A CL must be larger than 2000 tons, no larger than {limits['CL']} tons and have at least 17 knots.")
    ke = rule("KE class ceiling", "A KE must be no larger than 2500 tons and have no torpedoes.",
              b"\x81\xff"+struct.pack("<I", 2500), limits["KE"],
              f"A KE must be between 200 and {limits['KE']} tons, and before {MODERN_TORPEDO_YEAR} have no torpedoes.")
    # its torpedo test (after the size tests: jg, cmp edi,200, jl, mov eax,esi) and the year the CL rule reads
    year = re.search(rb"\x8b\x15(.{4})\x81\x3a\x94\x07\x00\x00", blob[ke-0xC0:ke], re.S)
    if blob[ke+6:ke+18] != bytes.fromhex("7f1381ffc80000007c0b8bc6") or blob[ke+18] != 0xE8 or not year:
        raise ValueError("Unsupported KE class torpedo test.")
    ke_torpedoes = (ke+18, base+ke+23+struct.unpack_from("<i", blob, ke+19)[0], struct.unpack("<I", year.group(1))[0])
    cvl_msg = "A CVL must have at least 4 aircraft and no more than 34 aircraft and have Displacement no more than 16 000 tons."
    cvl = rule("CVL class ceiling", cvl_msg, b"\x81\x7e\x2c"+struct.pack("<I", 16000), limits["CVL"],
               f"A CVL must carry 4 to {limits['CVL_aircraft']} aircraft and displace no more than {limits['CVL']} tons.")
    aircraft = b"\x83\xfa\x22"
    offset = cvl-0x10 + unique(blob[cvl-0x10:cvl], aircraft, "CVL class aircraft")
    patches.append(patch("CVL class aircraft", base+offset, aircraft, aircraft[:-1]+bytes([limits["CVL_aircraft"]])))
    # Keep every hull-research tier. Only the hard maximum above the final
    # destroyer technology is raised; no unconditional success return is used.
    dd = rt.method_address(blob, base, "CheckDDSize") - base
    instruction = b"\x81\xfe"+struct.pack("<I", 3800)
    offset = dd + unique(blob[dd:dd+0x30], instruction, "DD research hard maximum")
    patches.append(patch("DD research hard maximum", base+offset, instruction, instruction[:-4]+struct.pack("<I", limits["DD"])))
    # Override just these designer calls, not the getter used by AI planning.
    ref = message_ref(blob, base, "Error:  Building nation cannot build carriers larger than ")
    getter = rt.method_address(blob, base, "GetMaxCarrierDisplacement")
    calls = []
    for off in range(ref-0x30, ref+0x40):
        if blob[off] == 0xe8 and base+off+5+struct.unpack_from("<i", blob, off+1)[0] == getter:
            calls.append(off)
    if len(calls) != 2:
        raise ValueError("Unexpected designer carrier displacement checks.")
    for index, off in enumerate(calls):
        patches.append(patch(f"Designer CV limit {index+1}", base+off, blob[off:off+5], b"\xb8"+struct.pack("<I", limits["CV"])))
    patches += freed_error_patches(blob, base)+[catapult_patch(blob, base)]
    while len(strings) % 16:
        strings.append(0)
    clamp, calls = dp_mount_clamp(blob, base, allocation+0x8000+len(strings))   # code after the messages
    strings.extend(clamp)
    while len(strings) % 16:
        strings.append(0)
    # The KE torpedo test (EAX design -> AL torpedoes found): none count from the modern year.
    site, native, year = ke_torpedoes
    thunk = allocation+0x8000+len(strings)
    code = (b"\x51\x8b\x0d"+struct.pack("<I", year)+b"\x81\x39"+struct.pack("<I", MODERN_TORPEDO_YEAR)
            + b"\x59\x7c\x03\x33\xc0\xc3\xe9")
    strings.extend(code+struct.pack("<i", native-(thunk+len(code)+4)))
    calls.append(patch("KE torpedoes from the modern year", base+site, blob[site:site+5],
                       b"\xe8"+struct.pack("<i", thunk-(base+site+5))))
    return patches+calls, bytes(strings)


def lead(*parts):
    """Instructions that may come before a rule's message load: bytes literally, an int that many any bytes."""
    return re.compile(b"".join(re.escape(p) if isinstance(p, bytes) else b".{%d}" % p for p in parts)+rb"\Z", re.S)


# The designer's checks that hold freed rules: what may come before a rule's message load (tried in
# order) and the store that marks the design or mount as not allowed. Only the designer form calls
# these checks (callers audited in build 1.01.44); the AI's own designs never pass through them.
CHECKS = dict(
    report=((lead(b"\x8d\x45\xfc"), lead(b"\xc6\x45\xfa\x00"), lead(b"\x33\xd2\x8b\x45\xf4\x8b\x08\xff\x51\x3c")),
            b"\xc6\x45\xfa\x00"),                                                        # the design report
    turrets=((lead(b"\x8b\x45\xfc"), lead(b"\xc6\x45\xfb\x00")), b"\xc6\x45\xfb\x00"),     # TurretCheck
    mount=((lead(b"\x8b\x45\x08"), lead(b"\xc6\x45\xff\x00")), b"\xc6\x45\xff\x00"),      # mount guns, position, superimposed
    armour=((lead(b"\x8b\xc7"), lead(b"\x33\xdb")), b"\x33\xdb"),
    balance=((lead(b"\x8b\x04\x24"),), b"\xc6\x44\x24\x04\x00"),
    launchers=((lead(b"\x8d\x45\xf0\x0f\xb7\x56\x08\xe8", 4, b"\x8b\x4d\xf0\x8b\x45\xfc"),), b"\xc6\x45\xfb\x00"),
)
# Design-report errors that only restrict a ship type or size. Weight, cost, stability, topside
# and the report's notes already price these choices. Research, treaty, dock, overweight,
# top-heavy, naming, data-limit and physical-consistency errors stay, as do the class
# definitions that decide which type a design is. vls_cells frees the side-mount and carrier
# heavy SAM rules, whose code it verifies and hooks. (message, references)
FREED_ERRORS = (
    ("Error: A seaplane carrier cannot have displacement of more than 14 000 tons!", 1),
    ("Ship type cannot have unit machinery", 1), ("Ship type cannot have TPS", 1),
    ("Hull is too narrow for speed > 21 kt and triple/quad turrets in A or Y positions and TPS more than 1.", 1),
    ("Hull is too narrow for speed > 23 kt and triple/quad turrets in A or Y positions and TPS more than 0.", 1),
    ("Error: A ship with this displacement can have a maximum total of ", 1),
    ("Error: Carriers cannot have armour scheme protected cruiser", 1),
    ("Error:  A CVL must have at least 4 aircraft!", 1), ("Error: A CVL cannot have more than 34 aircraft!", 1),
    ("Error: A CVL cannot have displacement of more than 16 000 tons!", 1),
    ("Error: A CV must have more than 34 aircraft or more than 16 000 tons displacement!", 1),
    ("Error: A CV must have more than 24 aircraft!", 1), ("Error: A CVL must have a displacement of at least 6 000 tons!", 1),
    ("Error: A CVL must have a speed of at least 15 knots!", 1), ("Error: A CV must have a speed of at least 20 knots!", 1),
    ("Error:  The design board will not authorise such a large ship without at least 8 x 8 in guns!", 1),
    ("Error:  The design board will not authorise such a large ship without at least 8 x 6 in guns!", 1),
    ("Error: Displacement of at least 500 tons is necessary for depth charge throwers!", 1),
    ("Error: Displacement of at least 900 tons is necessary to carry 4 depth charge throwers!", 1),
    ("Error: Only DD and KE can carry depth charge throwers! Depth charge throwers removed", 1),
    ("Error:  Displacement of 600 tons is necessary for ASW mortars!", 1),
    ("Error:  Ship type cannot carry ASW mortars/rockets! ASW mortar removed.", 1),
    ("Error:  Displacement of 300 tons is necessary for extra depth charge storage!", 1),
    ("Error:  Only DD and KE can carry depth charges! Extra depth charges removed.", 1),
    ("Error:  Only DD and KE can carry minesweeping gear! Minesweeping gear removed.", 1),
    ("Error: Ships of type KE have max speed 24 knots (unless missile corvettes and tech developed).", 1),
    ("Error: Aircraft carriers cannot have aluminium superstructure.", 1),
    ("Error! Ships of type ", 2),   # BB, BC and CA without an armour deck
    ("Error: Destroyers cannot be armoured!", 1),
    ("Error: AMC cannot have speed above 21 knots before 1925!", 1), ("Error: AMC cannot have speed above 25 knots!", 1),
    ("Error: Ships with all or nothing armour scheme cannot have narrow belt!", 1),
    ("Error: Protected cruisers cannot have narrow belt!", 1),
    ("Error: Ships with this armour scheme cannot have upper belt!", 1),
    ("Error: If a ship has cross deck fire, it cannot have more than 4 secondary guns above 3 in calibre not in casemates!", 1),
    ("Error: Long range ships cannot have low freeboard!", 1), ("Error: Long range ships cannot have cramped accomodation!", 1),
    ("Error: AMC cannot be larger than 26000 tons!", 1), ("Error: CA cannot be larger than 26000 tons!", 1),
    ("Error: Ship type cannot be equipped with catapults!", 1),
    ("Error: Ships must have at least 10 000 tons displacement to operate heavy SAM systems!", 1),
    ("Error: Ships must have at least 3 600 tons displacement to operate medium SAM systems!", 1),
    ("Error: 6 inch dual purpose guns can not be used as main amament for DD.", 1),
    ("Error: Dual purpose guns as main amament not allowed for AMC.", 1),
    ("Error: Destroyers cannot be specially fitted for colonial service!", 1),
    ("Error: Ships fitted for colonial service cannot have cramped accomodation!", 1),
    ("Error: Ships fitted for colonial service cannot have short range!", 1),
    ("Error: Ships fitted for colonial service must have a displacement of at least 1500 tons!", 1),
    ("Error: Only ships of type CL, DD, KE or AMC can carry mines! Mines removed.", 1),
    ("Error: Ship can carry a maximum of ", 1),
    ("Error: Too many and/or too heavy secondary guns for displacement!", 3),
    ("Error: Too many tertiary guns for displacement!", 1),
    ("Error: Director for secondary guns not developed for ships smaller than CA.", 1),
    ("Error: Unarmoured ships can have a maximum gun calibre of 6 inches", 1),
    ("Error: This ship has too many medium or heavy turrets!", 1), ("Error: This ship has too many heavy turrets!", 1),
    ("Error: Triple secondary turrets not possible for this ship type!", 1),
    ("Error: Ship has to much unused displacement! Maximum is 5%, which on this ship means ", 1),
)
# (check, message): rules inside the designer's turret, mount, armour and balance checks. Freeing
# the centreline and superimposed rules lets every type (KE included) mount guns there.
FREED_REASONS = (
    ("turrets", "Cannot have guns in casemates on ships smaller than 1200 tons!"),
    ("turrets", "Casemate guns cannot be larger than 10 in!"),
    ("turrets", "Triple or quadruple gun mounts not allowed on this ship type!"),
    ("turrets", "Cannot have double wing turrets with long guns > 8 inches on ships smaller than 15 000 tons!"),
    ("turrets", "Cannot have double wing turrets for main battery guns > 7 inches on ships smaller than 10 000 tons!"),
    ("turrets", "Ship type can not have centerline gun mounts!"),
    ("turrets", "Protected cruisers can have a maximum of 2 centerline turrets"),
    ("mount", "Triple mounts not allowed for DD"), ("mount", "Quadruple mounts not allowed for CL"),
    ("mount", "Only single turrets are allowed for this ship type"),
    ("mount", "Only single turrets allowed in positions 1,2,3 or 4 if long guns and displacement < 14 000 tons"),
    ("mount", "Superimposed turrets for this ship type not allowed"),
    ("armour", "Belt extended armour cannot be thicker than belt!"),
    ("armour", "Upper belt armour cannot be thicker than belt!"),
    ("armour", "Deck extended armour cannot be more than two inches thicker than deck armor!"),
    ("armour", "Deck extended armour cannot be thicker than deck!"),
    ("armour", "Deck armour cannot be thicker than belt armour!"),
    ("armour", "Ship must have belt armour if it has armoured guns"),
    ("balance", "Turrets are not balanced!"),
    ("launchers", "Torpedo mounts, missiles or catapults are not balanced! Mount: "),
)
# (check, prefix, message): messages built as prefix + turret position + reason; the block starts at the prefix.
FREED_PREFIXED = (
    ("report", "Error: Turret ", ": Protected cruisers can have double turrets in position A and Y only!"),
    ("report", "Error: Turret ", ": Triple or quadruple turrets not allowed in wing positions!"),
    ("report", "Error: Turret ", ": Double turrets for calibres larger than 6 in not allowed on CL!"),
    ("turrets", "Error: Turret: ", ". Twin DP 5 inch guns not allowed on ships below 1800 tons."),
)


def error_skip(blob, base, label, start, inside, check):
    """Jump over one rule. `start` loads its message; the conditional jump just before the
    block skips it when the rule is met, so the block is replaced by a jump to that target."""
    leads, flag = CHECKS[check]
    for pattern in leads:
        found = pattern.search(blob, max(0, start-0x20), start)
        if found:
            start = found.start()
    if 0x70 <= blob[start-2] <= 0x7f:
        end = start+struct.unpack_from("<b", blob, start-1)[0]
    elif blob[start-6] == 0x0f and 0x80 <= blob[start-5] <= 0x8f:
        end = start+struct.unpack_from("<i", blob, start-4)[0]
    else:
        raise ValueError(f"Unsupported game build: no guard for {label}")
    if not start < inside < end or flag not in blob[start:end]:
        raise ValueError(f"Unsupported game build: unexpected rule block for {label}")
    jump = b"\xeb"+bytes([end-start-2]) if end-start-2 < 0x80 else b"\xe9"+struct.pack("<i", end-start-5)
    return patch(label, base+start, blob[start:start+len(jump)], jump)


def freed_error_patches(blob, base):
    patches = []
    for message, count in FREED_ERRORS:
        refs = message_refs(blob, base, message)
        if len(refs) != count:
            raise ValueError(f"Unsupported game build: {message} has {len(refs)} checks.")
        for index, ref in enumerate(refs):
            label = "Freed rule: "+message.replace("Error:", "").replace("Error!", "").strip()+(f" #{index+1}" if count > 1 else "")
            patches.append(error_skip(blob, base, label, ref-1, ref, "report"))
    for check, message in FREED_REASONS:
        ref = message_ref(blob, base, message)
        patches.append(error_skip(blob, base, "Freed rule: "+message.strip(), ref-1, ref, check))
    for check, prefix, message in FREED_PREFIXED:
        literal = struct.pack("<I", len(prefix))+prefix.encode("utf-16-le")+b"\0\0"

        def pushes_prefix(at):   # push <a copy of the prefix literal>
            pointer = struct.unpack_from("<I", blob, at+1)[0]-base
            return blob[at] == 0x68 and 4 <= pointer and blob[pointer-4:pointer-4+len(literal)] == literal
        ref = message_ref(blob, base, message)
        start = max((at for at in range(ref-0x40, ref-1) if pushes_prefix(at)), default=None)
        if start is None:
            raise ValueError(f"Unsupported game build: no message prefix for {message}")
        patches.append(error_skip(blob, base, "Freed rule: Turret"+message, start, ref, check))
    return patches


def dp_mount_clamp(blob, base, address):
    """Dual purpose triple and quadruple mounts need the twin mount's research instead of being
    refused: the designer's calls to the native DP test (EAX calibre, EDX guns per mount) ask
    about two guns when a mount has three or four. The AI's own calls stay native."""
    ref = message_ref(blob, base, ". Dual purpose mountings not allowed for triple or quadruple mounts.")
    site = ref-0x60+unique(blob[ref-0x60:ref], b"\x8b\x56\x04\x8b\x43\x6d\xe8", "turret DP test")+6
    test = base+site+5+struct.unpack_from("<i", blob, site+1)[0]
    calls = [site]   # TurretCheck; then the report's secondary and tertiary checks
    for message, setup in (("Error: Secondary guns - Building nation has not developed dual purpose mountings for that calibre or gun combination.",
                            b"\x8b\x93\xb6\x00\x00\x00\x8b\x43\x71\xe8"),
                           ("Error: Tertiary guns - Building nation has not developed dual purpose mountings for that calibre or gun combination.",
                            b"\x8b\x93\xba\x00\x00\x00\x8b\x43\x75\xe8")):
        ref = message_ref(blob, base, message)
        calls.append(ref-0x40+unique(blob[ref-0x40:ref], setup, "report DP test")+len(setup)-1)
    # The form's checkbox states: the design is loaded from the form ([ebx+0E6Ch]) just before.
    designer = {off for m in re.finditer(rb"\x8b[\x83\x93\x9b\xab\xb3\xbb]\x6c\x0e\x00\x00", blob)
                for off in range(m.end(), m.end()+16)
                if blob[off] == 0xe8 and base+off+5+struct.unpack_from("<i", blob, off+1)[0] == test}
    if len(designer) != 8:
        raise ValueError(f"Unsupported game build: {len(designer)} designer DP checkbox tests.")
    code = b"\x83\xfa\x03\x7c\x0a\x83\xfa\x04\x7f\x05\xba\x02\x00\x00\x00\xe9"+struct.pack("<i", test-(address+20))
    plans = [patch("DP triple/quad mounts: twin research", base+off, blob[off:off+5],
                   b"\xe8"+struct.pack("<i", address-(base+off+5))) for off in sorted(set(calls) | designer)]
    return code, plans


def catapult_patch(blob, base):
    """The designer's catapult counts by type (none on DD and KE, one on CLs under 8,000 t, two on
    most types, four on angled-deck carriers) are type and size rules: jump past the type switch to
    its accepting exit. The catapult research check before the switch stays."""
    ref = message_ref(blob, base, "Ship type cannot have catapults")
    start = ref-0x60+unique(blob[ref-0x60:ref], b"\x0f\xb6\x86\xd3\x09\x00\x00\x83\xf8\x0e\x0f\x87", "catapult type switch")
    tail = ref+4+5                          # after the message's string assignment
    if blob[tail:tail+3] != b"\x33\xdb\xe9":   # xor ebx, ebx; jmp exit
        raise ValueError("Unsupported game build: catapult rule exit.")
    exit = tail+7+struct.unpack_from("<i", blob, tail+3)[0]
    return patch("Freed rule: catapult counts by ship type", base+start, blob[start:start+5],
                 b"\xe9"+struct.pack("<i", exit-(start+5)))


def extended_table(original_rows, max_tons=200000):
    """Preserve 1..90kt exactly; extrapolate only supported speed columns.

    Above 90kt this is a transparent estimate, not calibrated historical ship
    machinery: HP(D) = HP(90kt) * (D/90kt)**(2/3). Invalid speeds stay invalid.
    An extra endpoint makes native interpolation at the upper edge safe.
    """
    if len(original_rows) != 90*100:
        raise ValueError("Unexpected native machinery table dimensions.")
    first = struct.unpack_from("<25i", original_rows)
    last = struct.unpack_from("<25i", original_rows, 89*100)
    if first[0] <= 0 or last[0] < first[0] or not any(v > 0 for v in last):
        raise ValueError("The native machinery table is not initialized.")
    out = bytearray(100) + bytearray(original_rows)
    for kilotons in range(91, max_tons//1000+2):
        row = [round(v*(kilotons/90)**(2/3)) if v > 0 else v for v in last]
        out.extend(struct.pack("<25i", *row))
    return bytes(out)


def interpolation_thunk(address, resume, skip, limit=200):
    code = b"\x3d"+struct.pack("<I", limit)+b"\x0f\x8f"
    code += struct.pack("<i", skip-(address+11))
    code += b"\xe9"+struct.pack("<i", resume-(address+16))
    return code


def classification_thunk(address, original, limits=LIMITS):
    """Keep an explicitly selected expanded class in the designer only.

    The native class validator still checks armament, speed and minima. The
    AI's calls to SuggestShipType are deliberately not redirected.
    """
    code, labels, fixups = bytearray(), {}, []

    def label(name):
        labels[name] = len(code)

    def jump(opcode, target):
        code.extend(opcode)
        fixups.append((len(code), target))
        code.extend(b"\0"*4)

    def compare(value):
        code.extend(b"\x81\xf9"+struct.pack("<I", value))  # cmp ecx,imm32

    code.extend(b"\x52\x51\x0f\xb6\x90\xd3\x09\x00\x00\x8b\x48\x2c")
    for value, name in ((9, "DD"), (4, "CL"), (10, "KE"), (6, "CVL"), (3, "CA")):
        code.extend(b"\x83\xfa"+bytes([value]))
        jump(b"\x0f\x84", name)
    jump(b"\xe9", "fallback")
    label("CA")
    compare(4000); jump(b"\x0f\x8e", "fallback")
    compare(limits["CA"]); jump(b"\x0f\x8f", "fallback")
    code.extend(b"\x83\x78\x6d"+bytes([CA_MAX_CALIBRE])); jump(b"\x0f\x8f", "fallback")   # main calibre
    code.extend(b"\x83\x78\x40"+bytes([CA_MAX_BELT])); jump(b"\x0f\x8f", "fallback")      # belt
    code.extend(b"\xb8\x03\x00\x00\x00")
    jump(b"\xe9", "return")
    for kind, lower, result in (("DD", 3800, 9), ("CL", 12000, 4), ("KE", 2500, 10)):
        label(kind)
        compare(lower); jump(b"\x0f\x8e", "fallback")
        compare(limits[kind]); jump(b"\x0f\x8f", "fallback")
        code.extend(b"\xb8"+struct.pack("<I", result))
        jump(b"\xe9", "return")
    label("CVL")
    compare(6000); jump(b"\x0f\x8c", "fallback")
    compare(limits["CVL"]); jump(b"\x0f\x8f", "fallback")
    code.extend(b"\x83\xb8\xe0\x09\x00\x00\x04"); jump(b"\x0f\x8c", "fallback")
    code.extend(b"\x83\xb8\xe0\x09\x00\x00"+bytes([limits["CVL_aircraft"]])); jump(b"\x0f\x8f", "fallback")
    compare(16000); jump(b"\x0f\x8f", "CVL_accept")
    code.extend(b"\x83\xb8\xe0\x09\x00\x00\x22"); jump(b"\x0f\x8e", "fallback")
    label("CVL_accept")
    code.extend(b"\xb8\x06\x00\x00\x00")
    label("return")
    code.extend(b"\x59\x5a\xc3")
    label("fallback")
    code.extend(b"\x59\x5a\xe9")
    code.extend(struct.pack("<i", original-(address+len(code)+4)))
    for offset, target in fixups:
        struct.pack_into("<i", code, offset, labels[target]-offset-4)
    return bytes(code)


def classification_patch(blob, base, allocation, limits=LIMITS):
    getter = rt.method_address(blob, base, "SuggestShipType")
    ref = message_ref(blob, base, "A DD must not be larger than 3800 tons, have a speed of at least 20 knots and have torpedoes.")
    calls = [off for off in range(max(0, ref-0x1000), ref)
             if blob[off] == 0xe8 and base+off+5+struct.unpack_from("<i", blob, off+1)[0] == getter]
    if len(calls) != 1:
        raise ValueError("Cannot uniquely identify designer-only class suggestion.")
    off, address = calls[0], allocation+SUGGESTION_OFFSET
    return patch("Designer class suggestion", base+off, blob[off:off+5],
                 b"\xe8"+struct.pack("<i", address-(base+off+5))), classification_thunk(address, getter, limits)


def machinery_patches(blob, base, allocation, limits=LIMITS):
    ref = message_ref(blob, base, "Illegal displacement")
    start = blob.rfind(b"\x55\x8b\xec", max(0, ref-0x100), ref)
    if start < 0:
        raise ValueError("Cannot identify machinery calculation entry.")
    body = blob[start:start+0x260]
    table_match = list(re.finditer(rb"\x69\x3c\x85(.{4})\xe8\x03\x00\x00", body, re.DOTALL))
    if len(table_match) != 1:
        raise ValueError("Unsupported machinery lookup instructions.")
    native_table, = struct.unpack("<I", table_match[0].group(1))
    new_table = allocation+0x1000
    plans = []
    for delta, expected in ((0, 1), (100, 3)):
        pointer = struct.pack("<I", native_table+delta)
        offsets = [m.start() for m in re.finditer(re.escape(pointer), body)]
        if len(offsets) != expected:
            raise ValueError("Unexpected number of machinery table references.")
        for off in offsets:
            plans.append(patch("Extended machinery table", base+start+off, pointer, struct.pack("<I", new_table+delta)))
    offset = start+unique(body, b"\x83\xf8\x5a\x7f", "machinery interpolation edge")
    branch = struct.unpack_from("<b", blob, offset+4)[0]
    trampoline = allocation+0x100
    # Interpolate up to the last extended kiloton row; extended_table adds its endpoint.
    code = interpolation_thunk(trampoline, base+offset+5, base+offset+5+branch, limits["overall"]//1000)
    plans.append(patch("Machinery interpolation edge", base+offset, blob[offset:offset+5],
                       b"\xe9"+struct.pack("<i", trampoline-(base+offset+5))))
    instruction = b"\x81\x7b\x2c"+struct.pack("<I", 90000)
    offset = start+unique(body, instruction, "machinery hard maximum")
    # Enable the new range only after all lookup references have been redirected.
    plans.append(patch("Machinery hard maximum", base+offset, instruction, instruction[:-4]+struct.pack("<I", limits["overall"])))
    return plans, native_table, new_table, code, base+start
