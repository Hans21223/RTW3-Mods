"""Audited player-only research and aircraft cheat plans; no writes here."""
from pathlib import Path
import hashlib
import re
import struct
import big_guns
import modern_research as audit
import modern_tree
import weekly_runtime as rt


def discover(blob, base):
    normalized = audit.normalize(blob, base)
    bodies = {name: audit.native_body(blob, base, name, normalized)[:2] for name in (
        "HasResearchId", "CountResearchLevels", "LoadGlobalResearchAreas")}
    (_, has), (count_at, count), (_, load) = (bodies[key] for key in bodies)
    ids = list(re.finditer(rb"\xc7\x44\x24\x08(.{4})", has, re.DOTALL))
    counts = [struct.unpack("<I", m[1])[0] for m in re.finditer(
        rb"\xa3(.{4})\x83\x3d(.{4})\x18", load, re.DOTALL) if m[1] == m[2]]
    # Guns[c] at nation + base + 4c; Big Guns moves the base, so the live instruction says where it is.
    gun = re.search(rb"\x8b\x94\x83(\x1d\x01\x00\x00|\x00\xbc\x00\x00)", count)
    if len(ids) != 1 or len(counts) != 1 or not gun:
        raise ValueError("Unsupported native research/gun layout.")
    table = struct.unpack("<I", ids[0][1])[0]
    if b"\x80\xbc\x33\x36\x03\x00\x00\x00" not in has:
        raise ValueError("Unsupported native completed-research flags.")
    # Cross-check the player's pending aircraft request countdown and the
    # prototype list, owner index and timer against the native turn processor.
    at = rt.method_address(blob, base, "CheckAircraftDevelopment")-base
    body = blob[at:at+0x190]
    if (b"\x83\xb8\xa9\x4a\x00\x00\x00" not in body
            or b"\xff\x88\xa9\x4a\x00\x00" not in body
            or b"\x83\xb8\x84\x00\x00\x00\x00" not in body
            or b"\x8b\x98\x88\x00\x00\x00" not in body):
        raise ValueError("Unsupported native aircraft development countdowns.")
    slots = re.findall(rb"\xa1(.{4})\x8b\x00\x8b\x40\x08", body, re.DOTALL)
    if len(slots) != 1: raise ValueError("Cannot verify the aircraft prototype list.")
    return dict(table_id_base=table, area_count=counts[0], table_stride=0x414,
                record_stride=0x1d, flag_base=0x336, nation_stride=0x35,
                gun_read=count_at+gun.start()+3, max_levels=36, aircraft_list=struct.unpack("<I", slots[0])[0],
                request_timer=0x4aa9, prototype_timer=0x84, prototype_owner=0x88)


def get_layout(saved, handle):
    if "gun_read" in saved["layout"].get("research_cheats", {}): return saved["layout"]["research_cheats"]
    base, blob = rt.text_section(handle, saved["base"])
    saved["layout"]["research_cheats"] = discover(blob, base)
    return saved["layout"]["research_cheats"]


def research_state(saved, handle, player):
    import live_cheats as live
    layout = get_layout(saved, handle)
    raw = (rt.GAME/"Data/ResearchAreas3.dat").read_bytes()
    areas = modern_tree.parse(raw)
    if live.integer(handle, layout["area_count"]) != len(areas):
        raise ValueError("Loaded research areas differ from the installed table. Restart with mods.")
    # One contiguous flag read and one gun read keep the periodic overlay poll
    # lightweight; commit still revalidates every original value atomically.
    flags = rt.read(handle, player+layout["flag_base"], len(areas)*layout["nation_stride"])
    gun_base = struct.unpack("<I", rt.read(handle, layout["gun_read"], 4))[0]
    if gun_base not in (big_guns.NATIVE_GUNS, big_guns.GUNS): raise ValueError("Unsupported native gun layout.")
    last = big_guns.MAX_CALIBRE if gun_base == big_guns.GUNS else big_guns.NATIVE_MAX   # Big Guns: 2-40 in
    gun_values = struct.unpack(f"<{last-1}i", rt.read(handle, player+gun_base+8, (last-1)*4))
    records, rows, completed, total = [], [], 0, 0
    for area in areas:
        done, loaded_ids = 0, set()
        start = layout["table_id_base"]-21+area["area"]*layout["table_stride"]
        block = rt.read(handle, start, layout["table_stride"])
        expected_ids = {node["id"] for node in area["rows"]}
        for slot in range(layout["max_levels"]):
            offset = slot*layout["record_stride"]
            name = struct.unpack_from("<I", block, offset)[0]
            if not name: continue
            ident = struct.unpack_from("<i", block, offset+21)[0]
            year = struct.unpack_from("<i", block, offset+8)[0]
            if ident not in expected_ids or ident in loaded_ids or not 1850 <= year <= 2100:
                raise ValueError("Loaded research does not match the installed table. Restart with mods.")
            loaded_ids.add(ident)
            table = start+offset+21
            flag = player+layout["flag_base"]+area["area"]*layout["nation_stride"]+slot
            old = flags[area["area"]*layout["nation_stride"]+slot]
            if old not in (0, 1): raise ValueError("Invalid completed-research flag. No research cheat applied.")
            # Table guards and all flags (including already completed ones)
            # participate in the same all-or-nothing UI-thread transaction.
            records.extend(((table, ident, ident, 4), (table-13, year, year, 4), (flag, old, 1, 1)))
            done += old
        if loaded_ids != expected_ids: raise ValueError("Loaded research IDs differ from the installed table. Restart with mods.")
        size = len(area["rows"]); total += size; completed += done
        rows.append(dict(area=area["area"], name=area["name"], completed=done,
                         total=size, percent=100*done//size if size else 100))
    guns = []
    for calibre in range(2, last+1):
        address = player+gun_base+calibre*4
        quality = gun_values[calibre-2]
        if quality not in (-2, -1, 0, 1, 2, 9): raise ValueError("Unsupported native gun quality.")
        guns.append(dict(calibre=calibre, quality=quality))
        records.append((address, quality, 2, 4))
    return dict(available=True, completed=completed, total=total,
                percent=100*completed//total if total else 100,
                areas=rows, guns_maxed=sum(g["quality"] == 2 for g in guns), guns_total=len(guns),
                future_technologies_included=True, data_sha256=hashlib.sha256(raw).hexdigest()), records


def aircraft_state(saved, handle, main):
    import live_cheats as live
    layout = get_layout(saved, handle)
    records, prototypes = [], 0
    timer = live.integer(handle, main+layout["request_timer"])
    if not 0 <= timer <= 1200: raise ValueError("Unsupported aircraft-request countdown.")
    if timer:
        records.append((main+layout["request_timer"], timer, 1, 4))
    root = live.integer(handle, layout["aircraft_list"]) & 0xffffffff
    fleet = live.integer(handle, root) & 0xffffffff if root else 0
    if fleet:
        count = live.integer(handle, fleet+8)
        entries = live.integer(handle, fleet+4) & 0xffffffff
        if not 0 <= count <= 20000: raise ValueError("Aircraft list is changing. Refresh and retry.")
        list_guards = [(layout["aircraft_list"], root, root, 4), (root, fleet, fleet, 4),
                       (fleet+4, entries, entries, 4), (fleet+8, count, count, 4)]
        pointers = struct.unpack("<"+"I"*count, rt.read(handle, entries, count*4)) if count else []
        for i, pointer in enumerate(pointers):
            owner = live.integer(handle, pointer+layout["prototype_owner"])
            remaining = live.integer(handle, pointer+layout["prototype_timer"])
            if owner == 0 and 0 < remaining <= 1200:
                prototypes += 1
                records.extend(((entries+i*4, pointer, pointer, 4),
                                (pointer+layout["prototype_owner"], owner, owner, 4),
                                (pointer+layout["prototype_timer"], remaining, 1, 4)))
        if prototypes: records = list_guards+records
    return dict(available=True, pending_request=bool(timer), prototypes=prototypes), records


def status(saved, handle, main, player):
    research, _ = research_state(saved, handle, player)
    aircraft, _ = aircraft_state(saved, handle, main)
    return research, aircraft


def plan(action, saved, handle, before):
    if action == "research-all":
        summary, records = research_state(saved, handle, before["player"])
        return records, (f"Researched all {summary['total']} installed technologies and maximized "
                         f"2-{summary['guns_total']+1} inch gun quality for your nation.")
    if action == "fast-aircraft":
        summary, records = aircraft_state(saved, handle, before["main"])
        return records, f"Set your pending aircraft request and {summary['prototypes']} prototypes to 1 remaining turn. Native completion events and random delays still apply."
    raise ValueError("Unsupported campaign cheat action.")
