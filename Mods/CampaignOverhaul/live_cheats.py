"""Validated scalar campaign edits, committed on the game's own UI thread."""
import ctypes as c
from ctypes import wintypes as w
import hashlib
import json
from pathlib import Path
import re
import struct
import time
import weekly_runtime as rt
import week_display as memory
from hull_rules import patch, unique

REPORT = Path(__file__).with_name("live_cheats_report.json")
MAX_EDITS = 24
BULK_MAX_EDITS = 120024  # 10,000 ships, all captured guards, plus scalar settings.


def literal_refs(blob, base, key):
    pointers = []
    for match in re.finditer(re.escape(key.encode("utf-16-le")+b"\0\0"), blob):
        off = match.start()
        if off >= 4 and struct.unpack_from("<I", blob, off-4)[0] == len(key):
            pointers.append(struct.pack("<I", base+off))
    return [m.start() for pointer in pointers for m in re.finditer(re.escape(pointer), blob)
            if blob[m.start()-1] in (0xb9, 0x68)]


def load_field(blob, base, key, width=4, reader=None, global_value=False, region=None):
    candidates = []
    store = rb"\xa3(.{4})" if global_value else (rb"\x89(?:\x83(.{4})|\x43(.))" if width == 4 else rb"\x88(?:\x83(.{4})|\x43(.))")
    for ref in literal_refs(blob, base, key):
        if region is not None and not region[0] <= ref < region[1]: continue
        # Stop before the next property's load: the field follows its own read.
        for match in re.finditer(rb"\xe8(.{4})"+store, blob[ref+4:ref+0x45], re.DOTALL):
            call = base+ref+4+match.start()
            target = call+5+struct.unpack("<i", match.group(1))[0]
            if reader is None or target == reader:
                raw_field = match.group(2) if match.group(2) is not None else match.group(3)
                candidates.append((int.from_bytes(raw_field, "little"), target))
                break
    candidates = sorted(set(candidates))
    if len(candidates) != 1:
        raise ValueError(f"Unsupported live {key} field: {len(candidates)} candidates.")
    return candidates[0]


def discover_yard_fields(blob, base):
    # Read-only discovery also works with an existing UI-idle hook installed.
    progress, reader = load_field(blob, base, "BuildProgress")
    refs = [ref for ref in literal_refs(blob, base, "BuildProgress")
            if any(base+ref+4+m.start()+5+struct.unpack("<i", m.group(1))[0] == reader
                   for m in re.finditer(rb"\xe8(.{4})\x89\x83", blob[ref+4:ref+0x45], re.DOTALL))]
    if len(refs) != 1: raise ValueError("Cannot verify the ship yard field reader.")
    region = (refs[0]-0x1000, refs[0]+0x1000)
    fields = {key: load_field(blob, base, key, reader=reader, region=region)[0]
              for key in ("RepairTime", "TimeToRefit")}
    repair, due = fields["RepairTime"], fields["TimeToRefit"]
    if not (0 < repair < 128 and 0 < due < 128 and repair != due):
        raise ValueError("Unsupported ship refit field offsets.")
    start = rt.method_address(blob, base, "SendToRefit")-base
    body = blob[start:start+0xa0]
    # Independently cross-check the native refit routine: busy test, duration
    # assignment, nation adjustment and separate 60-month maintenance reset.
    required = (b"\x83\x7b"+bytes([repair])+b"\x00",
                b"\xc7\x43"+bytes([repair])+struct.pack("<I", 3),
                b"\xc7\x43"+bytes([repair])+struct.pack("<I", 2),
                b"\x01\x73"+bytes([repair]),
                b"\xc7\x43"+bytes([due])+struct.pack("<I", 60))
    if not all(part in body for part in required):
        raise ValueError("Native refit timer verification failed; no yard cheats enabled.")
    # Campaign ships do NOT have the unrelated class's Sunk byte at +1a.
    # The same strategic timer uses 100=sunk, 101=scrapped; independently check
    # both mutators before using it to filter the player fleet or edit projects.
    sink = rt.method_address(blob, base, "SinkShip")-base
    scrap = rt.method_address(blob, base, "ScrapShip")-base
    if (b"\xc7\x42"+bytes([repair])+struct.pack("<I", 100) not in blob[sink:sink+16]
            or b"\xc7\x43"+bytes([repair])+struct.pack("<I", 101) not in blob[scrap:scrap+0x400]):
        raise ValueError("Native campaign sunk/scrapped status verification failed.")
    return fields


def discover_ship_name(blob, base):
    # Several classes expose GetTypeAndName. This is the campaign-ship one:
    # type at +14, name at +0c. +04 is a numeric ID, not a string pointer.
    candidates = set()
    for match in re.finditer(b"\x0eGetTypeAndName", blob):
        at = match.start()
        if at < 6: continue
        size, address = struct.unpack_from("<HI", blob, at-6)
        if not 21 <= size < 1200 or not base <= address < base+len(blob): continue
        body = blob[address-base:address-base+0x60]
        if (b"\x0f\xb6\x5f\x14\x80\xfb\x0c\x75\x0c\x8b\xc6\x8b\x57\x0c\xe8" in body
                and b"\xff\x77\x0c\x8b\xc6\xba\x03\x00\x00\x00" in body):
            candidates.add(address)
    if len(candidates) != 1: raise ValueError("Cannot verify campaign ship-name field.")
    return 0x0c


def discover(blob, base):
    update = rt.method_address(blob, base, "UpdateBudgetNumbers")
    off = update-base
    pattern = rb"\x8b\x83(.{4})\xff\x70\x04"
    fields = list(re.finditer(pattern, blob[off:off+0x50], re.DOTALL))
    if len(fields) != 1:
        raise ValueError("Cannot identify current player nation.")
    player_field, = struct.unpack("<I", fields[0].group(1))
    roots = []
    for match in re.finditer(rb"\xa1(.{4})\xe8(.{4})", blob, re.DOTALL):
        call = base+match.start()+5
        if call+5+struct.unpack("<i", match.group(2))[0] == update:
            root, = struct.unpack("<I", match.group(1))
            if root % 4 == 0 and base <= root < base+len(blob)+0x400000:
                roots.append(root)
    if len(set(roots)) != 1:
        raise ValueError("Cannot uniquely verify main campaign object.")
    nation = {}
    nation["funds"], reader = load_field(blob, base, "Funds")
    for key, saved_key in (("income_level", "BudgetModifier"), ("income_resources", "BaseResources"),
                           ("dock_tons", "DockSize"), ("prestige", "Prestige"), ("unrest", "UnrestLevel")):
        nation[key], _ = load_field(blob, base, saved_key, reader=reader)
    research, _ = load_field(blob, base, "ResearchSpeed", reader=reader, global_value=True)
    ship = {}
    anchors = [ref for ref in literal_refs(blob, base, "BuildProgress")
               if any(base+ref+4+m.start()+5+struct.unpack("<i", m.group(1))[0] == reader
                      for m in re.finditer(rb"\xe8(.{4})\x89\x83", blob[ref+4:ref+0x45], re.DOTALL))]
    if len(anchors) != 1: raise ValueError("Cannot identify ship-save field layout.")
    ship_region = (anchors[0]-0x1000, anchors[0]+0x1000)
    for key in ("Cost", "BuildProgress", "MonthlyCost", "YearBuilt"):
        ship[key], _ = load_field(blob, base, key, reader=reader, region=ship_region)
    for key in ("Halted", "Hurry", "Rebuild"):
        ship[key], _ = load_field(blob, base, key, width=1, region=ship_region)
    ship.update(discover_yard_fields(blob, base))
    # Verify the native player-nation list accessor and list item layout.
    accessors = list(re.finditer(rb"\x53\x56\x8b\xf2\x8b\xd8\x8b\x83(.{4})\x8b\xd6\xe8(.{4})\x5e\x5b\xc3", blob, re.DOTALL))
    named_ships = set()
    for name_match in re.finditer(re.escape(b"\x07GetShip"), blob):
        pos = name_match.start()
        if pos >= 6:
            length, address = struct.unpack_from("<HI", blob, pos-6)
            if 14 <= length < 1200 and base <= address < base+len(blob): named_ships.add(address)
    valid = []
    for match in accessors:
        if base+match.start() not in named_ships: continue
        call = base+match.start()+14
        getter = call+5+struct.unpack("<i", match.group(2))[0]
        body = blob[getter-base:getter-base+0x30]
        if b"\x8b\x43\x04\x8b\x04\xb0" in body and b"\x8b\x43\x08\x3b\xc6" in body:
            valid.append(struct.unpack("<I", match.group(1))[0])
    if len(set(valid)) != 1:
        raise ValueError("Cannot verify player ship list.")
    year = rt.method_address(blob, base, "lb1900Click")-base
    year_slot, = struct.unpack_from("<I", blob, year+unique(blob[year:year+0x30], b"\x8b\x35", "campaign year")+2)
    wrapper = rt.method_address(blob, base, "DoApplicationIdle")
    calls = list(re.finditer(rb"\x8b\xd4\xe8(.{4})\x83\xc4\x1c\xc3", blob[wrapper-base:wrapper-base+0x40], re.DOTALL))
    if len(calls) != 1: raise ValueError("Cannot verify the native application idle dispatcher.")
    idle = wrapper+calls[0].start()+7+struct.unpack("<i", calls[0].group(1))[0]
    original = blob[idle-base:idle-base+6]
    if original != b"\x55\x8b\xec\x83\xc4\xf0":
        raise ValueError("Unsupported main-thread idle handler.")
    return {"main_slot": roots[0], "player_field": player_field, "nation": nation,
            "research": research, "ship": ship, "ship_list": valid[0], "year_slot": year_slot,
            "update": update, "idle": idle, "original": original.hex(),
            "ship_name": discover_ship_name(blob, base)}


def unhooked_text(pid, handle):
    """Live code with this adapter's own idle hook undone in a local copy only.

    discover() requires the native idle prologue, so adapters attaching after
    live-cheats must discover from this copy instead of the hooked live code.
    """
    module, _ = rt.module_info(pid); base, raw = rt.text_section(handle, module); blob = bytearray(raw)
    if REPORT.exists():
        current = json.loads(REPORT.read_text(encoding="utf-8"))
        if current.get("pid") == pid and current.get("base") == module and current.get("attached") and rt.report_is_current(REPORT, pid):
            item = current["patch"]; at = item["address"]-base; replacement = bytes.fromhex(item["replacement"])
            if blob[at:at+len(replacement)] != replacement: raise ValueError("Live adapter changed during discovery.")
            blob[at:at+len(replacement)] = bytes.fromhex(item["original"])
    return module, base, bytes(blob)


def idle_thunk(address, mailbox, layout):
    code, labels, fixups = bytearray(b"\x9c\x60"), {}, []

    def mark(name): labels[name] = len(code)
    def jump(op, name):
        code.extend(op); fixups.append((len(code), name)); code.extend(b"\0"*4)
    def abs32(op, slot): code.extend(op+struct.pack("<I", slot))
    # Optional fixed, reviewed in-process module dispatcher. Zero until the
    # submarine adapter is attached; this keeps all native dialogs on this UI
    # thread without subclassing a window from a foreign thread.
    abs32(b"\xa1", mailbox+0x700); code.extend(b"\x85\xc0")
    jump(b"\x0f\x84", "scalars")
    code.extend(b"\xff\xd0")
    mark("scalars")
    abs32(b"\x83\x3d", mailbox); code.extend(b"\x01"); jump(b"\x0f\x85", "done")
    abs32(b"\x8b\x1d", layout["main_slot"])
    abs32(b"\x3b\x1d", mailbox+4); jump(b"\x0f\x85", "fail")
    code.extend(b"\x85\xdb"); jump(b"\x0f\x84", "fail")
    code.extend(b"\x8b\x83"+struct.pack("<I", layout["player_field"]))
    code.extend(b"\x85\xc0"); jump(b"\x0f\x84", "fail")
    abs32(b"\x3b\x05", mailbox+8); jump(b"\x0f\x85", "fail")
    abs32(b"\x8b\x0d", mailbox+12)
    code.extend(b"\x81\xf9"+struct.pack("<I", layout.get("max_edits", MAX_EDITS))); jump(b"\x0f\x87", "fail")
    code.extend(b"\x85\xc9"); jump(b"\x0f\x84", "fail")
    code.extend(b"\xbe"+struct.pack("<I", mailbox+layout.get("records_offset", 32)))
    mark("check")
    code.extend(b"\x8b\x06\x8b\x56\x04\x83\x7e\x0c\x01")
    jump(b"\x0f\x84", "check_byte")
    code.extend(b"\x83\x7e\x0c\x04"); jump(b"\x0f\x85", "fail")
    code.extend(b"\x39\x10"); jump(b"\x0f\x85", "fail"); jump(b"\xe9", "next_check")
    mark("check_byte"); code.extend(b"\x38\x10"); jump(b"\x0f\x85", "fail")
    mark("next_check"); code.extend(b"\x83\xc6\x10\x49"); jump(b"\x0f\x85", "check")
    abs32(b"\xc7\x05", mailbox); code.extend(struct.pack("<I", 3))
    abs32(b"\x8b\x0d", mailbox+12)
    code.extend(b"\xbe"+struct.pack("<I", mailbox+layout.get("records_offset", 32)))
    mark("write"); code.extend(b"\x8b\x06\x8b\x56\x08\x83\x7e\x0c\x01")
    jump(b"\x0f\x84", "write_byte")
    code.extend(b"\x89\x10"); jump(b"\xe9", "next_write")
    mark("write_byte"); code.extend(b"\x88\x10")
    mark("next_write"); code.extend(b"\x83\xc6\x10\x49"); jump(b"\x0f\x85", "write")
    code.extend(b"\x8b\xc3\xe8")
    code.extend(struct.pack("<i", layout["update"]-(address+len(code)+4)))
    abs32(b"\xc7\x05", mailbox); code.extend(struct.pack("<I", 2)); jump(b"\xe9", "done")
    mark("fail"); abs32(b"\xc7\x05", mailbox); code.extend(struct.pack("<I", 4))
    mark("done")
    # Apply battle settings after the transaction, including while paused.
    # This fixed reviewed helper runs on the same native UI thread.
    if layout.get("environment_sync"):
        code.extend(b"\xe8"+struct.pack("<i", layout["environment_sync"]-(address+len(code)+5)))
    code.extend(b"\x61\x9d"+bytes.fromhex(layout["original"])+b"\xe9")
    code.extend(struct.pack("<i", layout["idle"]+len(bytes.fromhex(layout["original"]))-(address+len(code)+4)))
    for off, target in fixups:
        struct.pack_into("<i", code, off, labels[target]-off-4)
    return bytes(code)


def attach(wait=30):
    memory.configure()
    deadline = time.monotonic()+wait
    while True:
        games = [g for g in rt.process_candidates() if g[1] == rt.GAME/"RTW3.exe"]
        if len(games) == 1: break
        if time.monotonic() >= deadline: raise ValueError("Open the local game first.")
        time.sleep(0.5)
    pid, _ = games[0]
    handle = rt.K.OpenProcess(0x438, False, pid)
    if not handle: raise rt.win_error("Cannot open local game")
    try:
        base, _ = rt.module_info(pid)
        if REPORT.exists():
            old = json.loads(REPORT.read_text(encoding="utf-8"))
            if old.get("pid") == pid and old.get("base") == base and old.get("attached") and rt.report_is_current(REPORT, pid):
                item = old["patch"]
                if rt.read(handle, item["address"], len(bytes.fromhex(item["replacement"]))).hex() != item["replacement"]:
                    raise ValueError("Existing live-cheat hook changed.")
                return old
        while True:
            try:
                base, _ = rt.module_info(pid)
                text_base, blob = rt.text_section(handle, base)
                layout = discover(blob, text_base)
                import battle_reveal
                reveal_details = battle_reveal.discover(blob, text_base)
                import battle_environment
                environment_details = battle_environment.discover(blob, text_base)
                break
            except (OSError, ValueError):
                if time.monotonic() >= deadline: raise
                time.sleep(0.5)
        main = integer(handle, layout["main_slot"]) & 0xffffffff
        if not main or integer(handle, main+layout["player_field"]):
            raise ValueError("Restart through Play with mods before loading a campaign to install the battle-map cheat safely.")
        import research_cheats
        layout.update(max_edits=BULK_MAX_EDITS, records_offset=0x1000,
                      research_cheats=research_cheats.discover(blob, text_base))
        allocation = rt.K.VirtualAllocEx(handle, None, 0x2000+BULK_MAX_EDITS*16, 0x3000, 0x40)
        if not allocation: raise rt.win_error("Cannot allocate live-cheat mailbox")
        mailbox = allocation+0x1000
        environment, environment_blocks = battle_environment.plan(allocation, mailbox, environment_details)
        layout["environment_sync"] = environment["sync"]
        code = idle_thunk(allocation, mailbox, layout)
        if len(code) > 0x400: raise ValueError("Live dispatcher exceeds its reserved code area.")
        memory.write(handle, allocation, code)
        rt.K.FlushInstructionCache(handle, allocation, len(code))
        for target, code, _ in environment_blocks:
            memory.write(handle, target, code)
            rt.K.FlushInstructionCache(handle, target, len(code))
        reveal = {"state": mailbox+0x780, "details": reveal_details, "patches": []}
        for index, site in enumerate(reveal_details["sites"]):
            target = allocation+0x400+index*0x100
            code = battle_reveal.thunk(target, reveal["state"], site, reveal_details["sunk_field"])
            if len(code) > 0x100: raise ValueError("Battle marker hook exceeds its code area.")
            memory.write(handle, target, code)
            rt.K.FlushInstructionCache(handle, target, len(code))
            original = bytes.fromhex(site["original"])
            reveal["patches"].append(patch("Battle map: "+site["label"], site["address"], original,
                                          b"\xe9"+struct.pack("<i", target-site["address"]-5)+b"\x90"*(len(original)-5)))
        item = patch("Main-thread live cheats", layout["idle"], bytes.fromhex(layout["original"]),
                     b"\xe9"+struct.pack("<i", allocation-layout["idle"]-5)+b"\x90")
        installed = []
        try:
            for change in [item]+reveal["patches"]+environment["patches"]:
                rt.write_code(handle, change["address"], bytes.fromhex(change["original"]), bytes.fromhex(change["replacement"]))
                installed.append(change)
            saved = {"pid": pid, "base": base, "allocation": allocation, "mailbox": mailbox,
                     "layout": layout, "patch": item, "battle_reveal": reveal,
                     "battle_environment": environment,
                     "attached": True, "commit_thread": "native UI idle", "dispatcher_version": 2}
            REPORT.write_text(json.dumps(saved, indent=2)+"\n", encoding="utf-8")
            return saved
        except Exception:
            if installed:
                for change in reversed(installed):
                    rt.write_code(handle, change["address"], bytes.fromhex(change["replacement"]), bytes.fromhex(change["original"]))
            else: rt.K.VirtualFreeEx(handle, allocation, 0, 0x8000)
            raise
    finally: rt.K.CloseHandle(handle)


def session(pid=None, writable=False, project_fields=True):
    memory.configure()
    if not REPORT.exists(): raise ValueError("Enable Live Cheats in the manager and start the game with mods.")
    saved = json.loads(REPORT.read_text(encoding="utf-8"))
    if pid is not None and int(pid) != saved["pid"]: raise ValueError("The game session changed. Refresh live cheats.")
    if not saved.get("attached") or dict(rt.process_candidates()).get(saved["pid"]) != rt.GAME/"RTW3.exe":
        raise ValueError("Start the local game with Live Cheats enabled.")
    if rt.module_info(saved["pid"])[0] != saved["base"]: raise ValueError("The attached game session ended.")
    handle = rt.K.OpenProcess(0x438 if writable else 0x410, False, saved["pid"])
    if not handle: raise rt.win_error("Cannot open the live game")
    try:
        item = saved["patch"]
        if rt.read(handle, item["address"], len(bytes.fromhex(item["replacement"]))).hex() != item["replacement"]:
            raise ValueError("Live-cheat adapter is no longer attached.")
        yard_upgrade = project_fields and (not {"RepairTime", "TimeToRefit"} <= saved["layout"]["ship"].keys() or "Sunk" in saved["layout"]["ship"])
        name_upgrade = project_fields and "ship_name" not in saved["layout"]
        if yard_upgrade or name_upgrade:
            text_base, blob = rt.text_section(handle, saved["base"])
        if yard_upgrade:
            saved["layout"]["ship"].update(discover_yard_fields(blob, text_base))
            saved["layout"]["ship"].pop("Sunk", None)
        if name_upgrade:
            saved["layout"]["ship_name"] = discover_ship_name(blob, text_base)
        for change in saved.get("battle_reveal", {}).get("patches", []):
            if rt.read(handle, change["address"], len(bytes.fromhex(change["replacement"]))).hex() != change["replacement"]:
                raise ValueError("The battle-map cheat hooks changed. Restart with mods.")
        for change in saved.get("battle_environment", {}).get("patches", []):
            if rt.read(handle, change["address"], len(bytes.fromhex(change["replacement"]))).hex() != change["replacement"]:
                raise ValueError("The battle environment hooks changed. Restart with mods.")
        return saved, handle
    except Exception:
        rt.K.CloseHandle(handle)
        raise


def integer(handle, address, width=4):
    return int.from_bytes(rt.read(handle, address, width), "little", signed=width == 4)


def text_value(handle, address, fallback):
    try:
        pointer = integer(handle, address) & 0xffffffff
        if not pointer: return fallback
        length = integer(handle, pointer-4)
        if not 0 < length <= 160: return fallback
        return rt.read(handle, pointer, length*2).decode("utf-16-le")
    except (OSError, ValueError, UnicodeError): return fallback


def environment_notice(saved):
    environment = saved.get("battle_environment")
    if environment and environment.get("version", 1) < 2:
        return " Restart RTW3 through Play with mods: the aircraft daylight and map-shading fix is not loaded in this older session."
    return ""


def snapshot(saved, handle):
    import project_cheats as projects
    layout = saved["layout"]
    main = integer(handle, layout["main_slot"]) & 0xffffffff
    if not main: raise ValueError("Load a campaign first, then refresh live cheats.")
    player = integer(handle, main+layout["player_field"]) & 0xffffffff
    if not player: raise ValueError("Load a campaign first, then refresh live cheats.")
    year_ptr = integer(handle, layout["year_slot"]) & 0xffffffff
    year = integer(handle, year_ptr)
    if not 1850 <= year <= 2100: raise ValueError("The campaign is not ready for live cheats.")
    values = {key: integer(handle, player+offset) for key, offset in layout["nation"].items()}
    values["research_speed"] = integer(handle, layout["research"])
    import campaign_security
    security = campaign_security.attached_state(saved, handle)
    if security:
        percent = integer(handle, security)
        if not 0 <= percent <= 10: raise ValueError("Invalid counterintelligence allocation. Restart with mods.")
        values["counterintelligence_percent"] = percent
    if saved.get("battle_reveal"):
        flag = integer(handle, saved["battle_reveal"]["state"])
        if flag not in (0, 1): raise ValueError("The battle-map cheat state is invalid. Restart with mods.")
        values["reveal_enemy_ships"] = flag
    if saved.get("battle_environment"):
        import battle_environment
        for key, offset in battle_environment.FLAGS.items():
            flag = integer(handle, saved["battle_environment"]["state"]+offset)
            if flag not in (0, 1): raise ValueError("Invalid battle environment setting. Restart with mods.")
            values[key] = flag
    ships, fleet_ships = [], []
    fleet = integer(handle, player+layout["ship_list"]) & 0xffffffff
    if fleet:
        count = integer(handle, fleet+8)
        entries = integer(handle, fleet+4) & 0xffffffff
        if not 0 <= count <= 10000: raise ValueError("The fleet is changing. Refresh after the game finishes its update.")
        pointers = struct.unpack("<"+"I"*count, rt.read(handle, entries, count*4)) if count else []
        for index, ship_ptr in enumerate(pointers):
            row = {key: integer(handle, ship_ptr+offset, projects.SHIP_WIDTHS[key])
                   for key, offset in layout["ship"].items()}
            project = projects.describe(row, year)
            if not projects.fleet_visible(row): continue
            item = {"index": index, "name": text_value(handle, ship_ptr+layout["ship_name"], "Ship "+str(index)),
                    "type": "", "kind": project["kind"] if project else "inactive",
                    "remaining_turns": project["remaining_turns"] if project else 0}
            fleet_ships.append(item)
            if project:
                ships.append({**item, **project,
                              "pointer": ship_ptr, "entry": entries+index*4, "raw": row})
    identity = {"pid": saved["pid"], "base": saved["base"], "main": main, "player": player,
                "year": year, "values": values, "ships": ships}
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    name = text_value(handle, player+4, "Player nation")
    try:
        import research_cheats
        research, aircraft = research_cheats.status(saved, handle, main, player)
    except (OSError, ValueError, KeyError, struct.error) as error:
        research = aircraft = dict(available=False, message=str(error))
    import battle_ammo
    ammunition = battle_ammo.status(saved, handle)
    return {"ok": True, "pid": saved["pid"], "sha256": digest, "nation": "Player", "nation_name": name,
            "nations": [{"id": "Player", "name": name}], "values": values, "ships": ships,
            "fleet_ships": fleet_ships,
            "environment_version": saved.get("battle_environment", {}).get("version", 0),
            "research_progress": research, "aircraft_progress": aircraft,
            "battle_ammo": ammunition,
            "main": main, "player": player, "year": year,
            "security_state": security,
            "counterintelligence_cost": integer(handle, security+4) if security else None,
            "bulk_projects": saved.get("dispatcher_version", 1) >= 2,
            "note": "LIVE: ALL, Research ALL and Fast aircraft buttons apply their own action immediately. Other edits use Apply. The list shows your non-sunk fleet; only active yard jobs can be sped up. Construction costs and native delays remain. Refits include repairs and rebuilds." +
                    (" Restart RTW3 through Play with mods to enable battle reveal." if not saved.get("battle_reveal") else " Battle reveal resets when RTW3 closes.") +
                    (" Daytime and clear weather affect both sides during battles and reset at launch. The clock keeps running. Turning clear weather off restores the captured conditions." if saved.get("battle_environment") else
                     " Restart RTW3 through Play with mods to enable daytime and clear-weather cheats.") + environment_notice(saved)}


def inspect(pid=None):
    saved, handle = session(pid)
    try: return snapshot(saved, handle)
    finally: rt.K.CloseHandle(handle)


def progress(pid=None):
    import research_cheats
    saved, handle = session(pid, project_fields=False)
    try:
        layout = saved["layout"]
        main = integer(handle, layout["main_slot"]) & 0xffffffff
        player = integer(handle, main+layout["player_field"]) & 0xffffffff if main else 0
        if not player: return {"ok": True, "research_progress": {"available": False, "message": "Load a campaign"}}
        data, _ = research_cheats.research_state(saved, handle, player)
        return {"ok": True, "research_progress": data}
    finally: rt.K.CloseHandle(handle)


class THREADENTRY32(c.Structure):
    _fields_ = [("dwSize", w.DWORD), ("cntUsage", w.DWORD), ("th32ThreadID", w.DWORD),
                ("th32OwnerProcessID", w.DWORD), ("tpBasePri", w.LONG), ("tpDeltaPri", w.LONG), ("dwFlags", w.DWORD)]


def wake(pid):
    # WM_NULL only wakes the native message queue; no input is synthesized.
    user = c.WinDLL("user32", use_last_error=True)
    user.PostThreadMessageW.argtypes = [w.DWORD, w.UINT, w.WPARAM, w.LPARAM]
    for name in ("Thread32First", "Thread32Next"):
        getattr(rt.K, name).argtypes = [w.HANDLE, c.POINTER(THREADENTRY32)]
    snapshot_handle = rt.K.CreateToolhelp32Snapshot(4, 0)
    if snapshot_handle == c.c_void_p(-1).value: raise rt.win_error("Cannot wake the game UI thread")
    try:
        entry = THREADENTRY32(); entry.dwSize = c.sizeof(entry)
        more = rt.K.Thread32First(snapshot_handle, c.byref(entry))
        while more:
            if entry.th32OwnerProcessID == pid: user.PostThreadMessageW(entry.th32ThreadID, 0, 0, 0)
            more = rt.K.Thread32Next(snapshot_handle, c.byref(entry))
    finally: rt.K.CloseHandle(snapshot_handle)


def project_records(ship, fields, turns):
    import project_cheats as projects
    changes = projects.changes(ship, turns)
    records = [(ship["entry"], ship["pointer"], ship["pointer"], 4)]
    # Guard every captured field, including refit vs rebuild, status sentinels,
    # sunk state and maintenance-due counter. All guards pass before any write.
    for key, old in ship["raw"].items():
        records.append((ship["pointer"]+fields[key], old, changes.get(key, old), projects.SHIP_WIDTHS[key]))
    return records


def edit(pid, values, expected_hash, ship_index=None, turns=None, all_projects=None, action=None):
    from save_cheats import FIELDS
    saved, handle = session(pid, True)
    try:
        before = snapshot(saved, handle)
        if not expected_hash or before["sha256"] != expected_hash:
            raise ValueError("The live campaign changed. Refresh before applying cheats.")
        layout, records = saved["layout"], []
        action_message = None
        if action is not None:
            if values or ship_index is not None or all_projects is not None or turns is not None:
                raise ValueError("Quick cheat actions cannot be combined with unrelated edits.")
            if action == "refill-ammo":
                import battle_ammo
                records, action_message = battle_ammo.plan(saved, handle, before)
            else:
                import research_cheats
                records, action_message = research_cheats.plan(action, saved, handle, before)
        for key, value in values.items():
            if key in ("force_daytime", "clear_weather"):
                import battle_environment
                if isinstance(value, bool) or not isinstance(value, int) or value not in (0, 1):
                    raise ValueError("Battle environment settings must be 0 or 1.")
                if not saved.get("battle_environment"):
                    raise ValueError("Restart RTW3 through Play with mods to enable battle environment cheats.")
                if before["values"][key] != value:
                    records.append((saved["battle_environment"]["state"]+battle_environment.FLAGS[key], before["values"][key], value, 4))
                continue
            if key == "counterintelligence_percent":
                if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10:
                    raise ValueError("Counterintelligence must be between 0 and 10 percent.")
                if not before.get("security_state"):
                    raise ValueError("Enable Campaign Security and restart through Play with mods first.")
                if before["values"][key] != value:
                    records.append((before["security_state"], before["values"][key], value, 4))
                continue
            if key == "reveal_enemy_ships":
                if isinstance(value, bool) or not isinstance(value, int) or value not in (0, 1):
                    raise ValueError("Battle reveal must be 0 or 1.")
                if not saved.get("battle_reveal"):
                    raise ValueError("Restart RTW3 through Play with mods to enable battle reveal.")
                if before["values"][key] != value:
                    records.append((saved["battle_reveal"]["state"], before["values"][key], value, 4))
                continue
            if key not in FIELDS or isinstance(value, bool) or not isinstance(value, int): raise ValueError("Unsupported live cheat value.")
            _, minimum, maximum = FIELDS[key]
            if not minimum <= value <= maximum: raise ValueError(f"{key} must be between {minimum} and {maximum}.")
            address = layout["research"] if key == "research_speed" else before["player"]+layout["nation"][key]
            if before["values"][key] != value: records.append((address, before["values"][key], value, 4))
        import project_cheats as projects
        selected = projects.select(before["ships"], ship_index, all_projects)
        for ship in selected:
            records.extend(project_records(ship, layout["ship"], 1 if all_projects else turns))
        if not records: return {"ok": True, "message": (action_message or "No live values changed.") + environment_notice(saved), "save": before}
        if len(records) > layout.get("max_edits", MAX_EDITS):
            raise ValueError("Restart RTW3 through Play with mods to enable the larger all-ships transaction.")
        mailbox = saved["mailbox"]
        if integer(handle, mailbox) in (1, 3): raise ValueError("A live change is already pending. Wait and refresh.")
        # Validate all requested addresses and source values before publishing.
        for address, old, new, width in records:
            if integer(handle, address, width) != old: raise ValueError("Campaign changed while preparing the live edit.")
        payload = struct.pack("<7I", before["main"], before["player"], len(records), 0, 0, 0, 0)
        memory.write(handle, mailbox+4, payload)
        memory.write(handle, mailbox+layout.get("records_offset", 32), b"".join(
            struct.pack("<IIII", address, old & 0xffffffff, new & 0xffffffff, width) for address, old, new, width in records))
        memory.write(handle, mailbox, struct.pack("<I", 1))
        deadline = time.monotonic()+5
        while time.monotonic() < deadline:
            wake(saved["pid"])
            status = integer(handle, mailbox)
            if status == 2: break
            if status == 4: raise ValueError("The native campaign changed before commit. No live values were changed. Refresh and retry.")
            time.sleep(0.05)
        else:
            # Do not race a main-thread commit by cancelling from another thread.
            raise ValueError("The live request may still be pending. Return to the campaign map, wait, and refresh before making another edit.")
        for address, old, new, width in records:
            if integer(handle, address, width) != new: raise ValueError("The game changed a value after commit. Refresh to see the current state.")
        return {"ok": True, "message": (action_message or ("Live changes applied" + (f" to {len(selected)} eligible projects" if all_projects else "") + ".")) + " Save in RTW3 if you want to keep them." + environment_notice(saved), "save": snapshot(saved, handle)}
    finally: rt.K.CloseHandle(handle)


def detach():
    saved, handle = session(writable=True)
    try:
        if integer(handle, saved["mailbox"]+0x700): raise ValueError("The in-game submarine module uses this dispatcher. Close RTW3 to unload both safely.")
        if integer(handle, saved["mailbox"]) in (1, 3): raise ValueError("A live change is pending; wait before detaching.")
        if saved.get("battle_reveal"):
            main = integer(handle, saved["layout"]["main_slot"]) & 0xffffffff
            if main and integer(handle, main+saved["layout"]["player_field"]):
                raise ValueError("Close RTW3 to unload battle-map hooks safely; uncheck Reveal to turn the cheat off now.")
            for change in reversed(saved["battle_reveal"]["patches"]):
                rt.write_code(handle, change["address"], bytes.fromhex(change["replacement"]), bytes.fromhex(change["original"]))
        if saved.get("battle_environment"):
            main = integer(handle, saved["layout"]["main_slot"]) & 0xffffffff
            if main and integer(handle, main+saved["layout"]["player_field"]):
                raise ValueError("Close RTW3 to unload environment hooks safely; uncheck the settings to turn them off now.")
            for change in reversed(saved["battle_environment"]["patches"]):
                rt.write_code(handle, change["address"], bytes.fromhex(change["replacement"]), bytes.fromhex(change["original"]))
        item = saved["patch"]
        rt.write_code(handle, item["address"], bytes.fromhex(item["replacement"]), bytes.fromhex(item["original"]))
        saved["attached"] = False
        REPORT.write_text(json.dumps(saved, indent=2)+"\n", encoding="utf-8")
        return saved
    finally: rt.K.CloseHandle(handle)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("attach", "detach"))
    args = parser.parse_args()
    try: print(json.dumps(attach() if args.command == "attach" else detach()))
    except (OSError, ValueError) as error:
        print(json.dumps({"ok": False, "message": str(error)})); raise SystemExit(1)
