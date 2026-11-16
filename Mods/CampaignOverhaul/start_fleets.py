"""Historical starting fleets for the later start years (part of start_years / timeline-2030).

AIBuildInitialFleet(main, year, nation) spends a nation's starting funds on classes by year rules written for
1890-1935. For a later start year and a nation in FLEETS it builds that nation's real fleet instead: one
AIBuildInitialShips(main, nation, type, count, 0) call per class (the native helper picks a design of the start
year's era and lays down count ships), with funds out of the way and restored after, then the native tail (air
groups, radar, colonial stations). Submarines, aircraft and batteries keep their own native builders.

Batteries: BuildInitialBatteries gives each nation's home area an 8 in battery (and some a 6 in one) from 1935
on, and uses the result unchecked; the builder returns nothing when the nation cannot pay, which a poor minor
power cannot. Both places get the missing check.

Counts are active major warships on 1 January (superstates: their members' sum), with destroyers capped at 60
and escorts at 40 a nation: the game slows with huge fleets and Campaign QoL stops AI building at 400 ships.
"""
import hashlib
import struct

import modern_research as audit

BASE = 0x301000
WINDOWS = ((0x773708, 0x40, "4dc49693523a1c5f24078c687bfd6fda95b9929111de0306088157de902c6e02"),   # AIBuildInitialFleet
           (0x777BFC, 0x40, "0e5bc6801292cdff6a2cdb77f4a57c485ab4b43ce0159a8c7b283bd8fbe8d58c"),   # AIBuildInitialShips
           (0x77413D, 0x20, "ef397e02a04ce16026565d14bcf3306f49994ed842e39996bd0d409851efc075"),   # the fleet tail
           (0x79722E, 0x100, "a6e23040d05dfb146cdb96d888fc3322c7c5c20b6cb6fa5726f8468b76eb6495"))  # BuildInitialBatteries: home batteries
# (site, where its loop goes on): mov esi,eax / mov byte [esi+0x41],1 after StartBuildingFort
BATTERIES = ((0x797269, 0x797285), (0x797308, 0x797324))
BATTERY = "8bf0c6464101"
NATIVE = dict(site=0x773739, early=0x773781, late=0x773742, tail=0x77413D, build=0x777BFC, equal=0x30C7CC)
ORIGINAL = "817dfc8f0700007c3f"          # cmp [ebp-4],1935 / jl early
FUNDS, NAME = 0x1B5, 4                    # nation fields
BB, BC, CA, CL, CV, CVL, DD, KE = 18, 2, 3, 4, 5, 6, 9, 10   # AIBuildInitialShips types
CLASS = 10                                # most ships of one design
# start year: nation: (type, ships)...
FLEETS = {
    1947: {   # the Cold War blocs (coldwar_data.py); European NATO is its members' sum
        "United States of America": ((BB, 4), (CV, 12), (CVL, 8), (CA, 14), (CL, 22), (DD, 60), (KE, 30)),
        "European NATO": ((BB, 9), (CV, 6), (CVL, 7), (CA, 12), (CL, 35), (DD, 60), (KE, 40)),
        "Warsaw Pact": ((BB, 3), (CA, 2), (CL, 8), (DD, 40), (KE, 20)),
        "Communist China": ((CL, 1), (DD, 2), (KE, 10)),
        "State of Japan": ((KE, 6),),                         # disarmed: a minesweeping force
        "Republic of India": ((CL, 1), (KE, 6)),
        "Indonesia": ((KE, 4),),
        "Brazil": ((BB, 2), (CL, 1), (DD, 6), (KE, 8)),
        "Argentina": ((BB, 2), (CA, 2), (CL, 1), (DD, 12), (KE, 8)),
        "Iran": ((KE, 2),),
    },
    1960: {
        "United States of America": ((CV, 14), (CVL, 9), (CA, 12), (CL, 6), (DD, 60), (KE, 40)),
        "European NATO": ((BB, 1), (CV, 5), (CVL, 6), (CA, 1), (CL, 19), (DD, 60), (KE, 40)),
        "Warsaw Pact": ((CL, 20), (DD, 60), (KE, 40)),
        "Communist China": ((DD, 4), (KE, 12)),
        "State of Japan": ((DD, 16), (KE, 16)),
        "Republic of India": ((CL, 2), (DD, 3), (KE, 12)),
        "Indonesia": ((DD, 4), (KE, 12)),
        "Brazil": ((CVL, 1), (CL, 2), (DD, 12), (KE, 8)),
        "Argentina": ((CVL, 1), (CL, 3), (DD, 10), (KE, 8)),
        "Iran": ((KE, 4),),
    },
    1980: {
        "United States of America": ((CV, 13), (CA, 27), (DD, 60), (KE, 40)),
        "European NATO": ((CV, 2), (CVL, 4), (CL, 4), (DD, 57), (KE, 40)),
        "Warsaw Pact": ((CVL, 4), (CA, 26), (DD, 60), (KE, 40)),
        "Communist China": ((DD, 11), (KE, 16)),
        "State of Japan": ((DD, 32), (KE, 15)),
        "Republic of India": ((CVL, 1), (CL, 1), (DD, 3), (KE, 20)),
        "Indonesia": ((KE, 10),),
        "Brazil": ((CVL, 1), (DD, 12), (KE, 6)),
        "Argentina": ((CVL, 1), (CL, 1), (DD, 9), (KE, 6)),
        "Iran": ((DD, 3), (KE, 8)),
    },
    2000: {
        "United States": ((CV, 12), (CA, 27), (DD, 54), (KE, 35)),
        "Russian Federation": ((CV, 1), (CA, 6), (DD, 16), (KE, 14)),
        "People's Republic of China": ((DD, 20), (KE, 40)),
        "European Union": ((CV, 1), (CVL, 5), (DD, 40), (KE, 40)),
        "East Asian Federation": ((DD, 60), (KE, 40)),
        "Southeast Asian Union": ((CVL, 1), (DD, 2), (KE, 40)),
        "India": ((CVL, 1), (DD, 8), (KE, 12)),
        "Middle East Federation": ((DD, 4), (KE, 40)),
        "United African States": ((KE, 8),),
        "South American Union": ((CVL, 1), (CL, 1), (DD, 8), (KE, 30)),
    },
}


def classes(fleet):
    """(type, ships) per AIBuildInitialShips call: big groups become several classes."""
    out = []
    for kind, ships in fleet:
        while ships > 0:
            size = min(CLASS, ships) if ships <= CLASS or ships >= 2*CLASS else (ships+1)//2
            out.append((kind, size)); ships -= size
    return out


def discover(blob, base):
    normal = audit.normalize(blob, base)
    for address, size, digest in WINDOWS:
        if hashlib.sha256(normal[address-BASE:address-BASE+size]).hexdigest() != digest:
            raise ValueError("Start fleets refuse changed native code at "+hex(address))
    info = {k: v+base-BASE for k, v in NATIVE.items()}
    info["original"] = blob[NATIVE["site"]-BASE:NATIVE["site"]-BASE+len(ORIGINAL)//2].hex()
    for site, _ in BATTERIES:
        if blob[site-BASE:site-BASE+6].hex() != BATTERY: raise ValueError("Start fleets refuse changed native code.")
    info["batteries"] = [(site+base-BASE, after+base-BASE) for site, after in BATTERIES]
    if info["original"] != ORIGINAL: raise ValueError("Start fleets refuse changed native code.")
    return info


def literal(text):
    return struct.pack("<HHiI", 1200, 2, -1, len(text))+text.encode("utf-16-le")+b"\0\0"


def build(page, info):
    """Code at page, data after it (0x2000 bytes in all); returns blocks and the one patch."""
    from campaign_security import Code
    from hull_rules import patch
    blocks, cursor, rows, names = [], page+0x100, [], {}
    for year, nations in FLEETS.items():
        for nation, fleet in nations.items():
            if nation not in names:
                data = literal(nation); names[nation] = cursor+12
                blocks.append(dict(name="Fleet nation "+nation, address=cursor, bytes=data.hex())); cursor += (len(data)+3) & ~3
            body = b"".join(bytes(pair) for pair in classes(fleet))+b"\0\0"
            blocks.append(dict(name=f"Fleet {year} {nation}", address=cursor, bytes=body.hex()))
            rows.append((year, names[nation], cursor)); cursor += (len(body)+3) & ~3
    table = cursor
    blocks.append(dict(name="Fleet table", address=table, bytes=(b"".join(struct.pack("<3I", *row) for row in rows)+bytes(12)).hex()))
    if table+len(rows)*12+12 > page+0x1F80: raise ValueError("Start fleets exceed their pages.")
    # In AIBuildInitialFleet after its frame: EBX nation, ESI main, [EBP-4] the year (the start year or the one before).
    c = Code(page)
    c.emit(b"\x60\xbf"); c.u32(table)
    c.mark("row"); c.emit(b"\x8b\x07\x85\xc0"); c.branch(b"\x0f\x84", "native")
    c.emit(b"\x2b\x45\xfc\x83\xf8\x01"); c.branch(b"\x0f\x87", "next")
    c.emit(b"\x8b\x43"+bytes([NAME])+b"\x8b\x57\x04"); c.branch(b"\xe8", info["equal"]); c.branch(b"\x0f\x84", "found")
    c.mark("next"); c.emit(b"\x83\xc7\x0c"); c.branch(b"\xe9", "row")
    c.mark("found"); c.emit(b"\x8b\x7f\x08\xff\xb3"); c.u32(FUNDS); c.emit(b"\xc7\x83"); c.u32(FUNDS); c.u32(0x3FFFFFFF)
    c.mark("class"); c.emit(b"\x0f\xb6\x47\x01\x85\xc0"); c.branch(b"\x0f\x84", "built")
    c.emit(b"\x50\x6a\x00\x0f\xb6\x0f\x8b\xd3\x8b\xc6"); c.branch(b"\xe8", info["build"])      # the callee pops both
    c.emit(b"\xc7\x83"); c.u32(FUNDS); c.u32(0x3FFFFFFF)
    c.emit(b"\x83\xc7\x02"); c.branch(b"\xe9", "class")
    c.mark("built"); c.emit(b"\x8f\x83"); c.u32(FUNDS); c.emit(b"\x61"); c.branch(b"\xe9", info["tail"])
    c.mark("native"); c.emit(b"\x61\x81\x7d\xfc\x8f\x07\x00\x00"); c.branch(b"\x0f\x8c", info["early"]); c.branch(b"\xe9", info["late"])
    code = c.finish()
    if len(code) > 0x100: raise ValueError("Start fleet code exceeds its slot.")
    blocks.append(dict(name="Start fleets", address=page, bytes=code.hex()))
    old = bytes.fromhex(info["original"])
    checks = []
    for index, (site, after) in enumerate(info["batteries"]):          # no battery built: skip its set-up
        c = Code(page+0x1F80+index*0x20)
        c.emit(b"\x8b\xf0\x85\xf6"); c.branch(b"\x0f\x84", after)
        c.emit(b"\xc6\x46\x41\x01"); c.branch(b"\xe9", site+6)
        blocks.append(dict(name=f"Start battery check {index}", address=page+0x1F80+index*0x20, bytes=c.finish().hex()))
        checks.append(patch(f"Start batteries: check {index}", site, bytes.fromhex(BATTERY),
                            b"\xe9"+struct.pack("<i", page+0x1F80+index*0x20-site-5)+b"\x90"))
    return blocks, checks+[patch("Start fleets: historical classes", info["site"], old,
                          b"\xe9"+struct.pack("<i", page-info["site"]-5)+b"\x90"*(len(old)-5))]
