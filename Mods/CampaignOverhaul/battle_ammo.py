"""Player battle magazine refill plans, committed by the existing UI mailbox.

Restore nominal gun loads using the current native ammunition doctrine, plus
one loaded salvo in surviving torpedo/missile mounts. Reserve reloads, mines,
aircraft stores, weapon damage, jamming and firing cooldowns stay unchanged.
"""
import hashlib
import struct
import modern_research as audit
import weekly_runtime as rt
import battle_reveal

WINDOWS = (
    (0x6cb6d4, 1184, "015bd472c83631c57e0ef406d0263259338fb9c3c881fcb8b7c0dad2c8a4135b"),
    (0x90f398, 249, "cb5b8419e6ca29e939b562bf9ee8f05920e55b6c02887a21e4d0beeacdfcd3ad"),
    (0x917df0, 167, "cfe3baff6e3b74b5818a4b1f58ceee91da7673e2706d391fbed4a0ab93120af6"),
    (0x91d30c, 25, "17d14c0e0702e9cb9398d54879261b6016887c1aba1a087c6ad41efb3a0e29e9"),
    (0x9258cc, 117, "ca8b8573689b12733290aa2686d4997bee00f500c11711a0243f210685e52dc8"),
    (0x85d5b8, 47, "6491a0e431474b3172a9e30590b572ed07e56fa307e04edf36122c307f1cb9c5"),
    (0x90f4ef, 14, "b2f6f1997e5d8d0dfa6a037b728a4f920906385e317e021f5e1140c5747babac"),
    (0x9312fc, 49, "e8132a0941a441ef1e91a4864e23b23a6b0f9a8bc54822fdf1baf84e1e7c061e"),
    (0x93461c, 32, "3a61329d6c7188a37e0f998c7d96e9576a897066a4ac4ed075d733f7b95febbd"),
    (0x934683, 37, "5735700847a49588d4ab808eeeec43c8157c9cb7a360f8213e14a4d341dac8ed"),
    (0x93440b, 27, "e3ace9088112f8a2bbb47cf206f3a5a7828cb64b870916e2fe2d64dfdc34ba30"),
    (0x8e4a60, 42, "59037b58f5183489c2c90fd3504c4db03b7140f74267e2c423ea17f8dfaa596e"),
)


def discover(blob, base):
    normal = audit.normalize(blob, base)
    for address, size, expected in WINDOWS:
        start = address - 0x301000
        if hashlib.sha256(normal[start:start+size]).hexdigest() != expected:
            raise ValueError("Ammo refill refuses changed native code at " + hex(address) + ".")
    for name, offset in (("Ammo", 0xb7b), ("InitialAmmo", 0xb9f),
                         ("Sunk", 0xa9f), ("Sinking", 0xb35), ("Side", 0xa55)):
        if battle_reveal.field(blob, name) != offset:
            raise ValueError("Unsupported tactical ammo field: " + name)
    delta = base - 0x301000
    return dict(ships_slot=0x9f79d8+delta, side_slot=0xa23630+delta,
                form_slot=0xa23274+delta)


def get_layout(saved, handle):
    if "battle_ammo" not in saved["layout"]:
        base, blob = rt.text_section(handle, saved["base"])
        saved["layout"]["battle_ammo"] = discover(blob, base)
    return saved["layout"]["battle_ammo"]


def battle(saved, handle, layout):
    import live_cheats as live
    environment = saved.get("battle_environment")
    if not environment:
        raise ValueError("Restart through Play with mods to enable battle ammo refill.")
    form = live.integer(handle, environment["state"]+8)
    if not form or form != live.integer(handle, layout["form_slot"]):
        raise ValueError("Open a battle, pause it, then refresh live cheats to refill ammo.")
    return form


def status(saved, handle):
    try:
        layout = get_layout(saved, handle)
        battle(saved, handle, layout)
        return dict(available=True, message="Refill all player ship magazines and ready torpedo/missile tubes.")
    except (OSError, ValueError, KeyError, struct.error) as error:
        return dict(available=False, message=str(error))


def loadout(capacity, calibre, dual_purpose, doctrine):
    """Native AP/HE/SAP categories; calibre 2-6 maps to doctrine row zero."""
    if calibre < 4 or (dual_purpose and calibre < 6):
        weights = (0, 100, 0)
    elif dual_purpose:
        weights = (0, 90, 10)
    else:
        group = 0 if calibre < 7 else 2 if calibre < 11 else 3
        weights = doctrine[group*3:group*3+3]
    if len(weights) != 3 or any(not 0 <= v <= 100 for v in weights) or sum(weights) != 100:
        raise ValueError("Invalid native ammo doctrine. No ammo changed.")
    # Native x87 uses nearest-even rounding. Distribute any rounding remainder
    # so a refill never exceeds the fitted magazine's nominal capacity.
    result = [round(capacity*w/100) for w in weights]
    while sum(result) != capacity:
        direction = 1 if sum(result) < capacity else -1
        candidates = [i for i in range(3) if weights[i] and (direction > 0 or result[i])]
        index = max(candidates, key=lambda i: (capacity*weights[i]/100-result[i])*direction)
        result[index] += direction
    return result


def plan(saved, handle, before):
    import live_cheats as live
    info = get_layout(saved, handle)
    form = battle(saved, handle, info)
    records, changed_ships = [], 0

    def read(address, width=4):
        return live.integer(handle, address, width)

    def guard(address, width=4, expected=None):
        old = read(address, width)
        if expected is not None and old != expected:
            raise ValueError("Battle changed. Pause, refresh and retry ammo refill.")
        records.append((address, old, old, width))
        return old

    def pointer(address):
        value = guard(address)
        if not 0x10000 <= value < 0x7fff0000:
            raise ValueError("Invalid battle object. No ammo changed.")
        return value

    def members(address, maximum):
        pool = pointer(address)
        count = guard(pool+8)
        if not 0 <= count <= maximum:
            raise ValueError("Unsupported battle collection size. No ammo changed.")
        if not count:
            return []
        entries = pointer(pool+4)
        return [pointer(entries+i*4) for i in range(count)]

    def refill(address, capacity, calibre, dual_purpose, doctrine):
        current = [read(address+i*4) for i in range(3)]
        if not 0 <= capacity <= 10_000_000 or any(not 0 <= v <= 10_000_000 for v in current):
            raise ValueError("Invalid ship magazine. No ammo changed.")
        if not capacity or sum(current) >= capacity:
            return False
        desired = loadout(capacity, calibre, dual_purpose, doctrine)
        records.extend((address+i*4, old, new, 4) for i, (old, new) in enumerate(zip(current, desired)))
        return current != desired

    guard(saved["battle_environment"]["state"]+8, expected=form)
    guard(info["form_slot"], expected=form)
    side = guard(info["side_slot"])
    if side not in (0, 1):
        raise ValueError("Unsupported player battle side. No ammo changed.")
    cell = pointer(info["ships_slot"])
    ships = members(cell, 10000)
    doctrine = [guard(before["player"]+0xc0+i*4) for i in range(12)]
    if any(not 0 <= value <= 100 for value in doctrine):
        raise ValueError("Invalid native ammunition allocation. No ammo changed.")
    seen = set()
    for ship in ships:
        if ship in seen:
            raise ValueError("Duplicate tactical ship pointer. No ammo changed.")
        seen.add(ship)
        # The battle's nation index distinguishes the player from allied ships
        # sharing their side. Never rely on side alone to authorize a refill.
        if read(ship+0xa55) != side or read(ship+0x14) != side:
            continue
        if read(ship+0xa9f, 1) or read(ship+0xb35):
            continue
        guard(ship+0xa55, expected=side); guard(ship+0x14, expected=side)
        guard(ship+0xa9f, 1, 0); guard(ship+0xb35, expected=0)
        guard(ship); guard(ship+0x10); guard(ship+0x18)  # Object/class identity guards.
        changed = False
        rpg, calibre = guard(ship+0x8b), guard(ship+0x6d)
        if not 0 <= rpg <= 10000 or not 0 <= calibre <= 20:
            raise ValueError("Unsupported main magazine capacity. No ammo changed.")
        for turret in members(ship+0x9a, 128):
            if read(turret+0x24, 1):
                continue
            guard(turret+0x24, 1, 0)
            guns = guard(turret+4)
            if not 0 <= guns <= 12:
                raise ValueError("Invalid turret capacity. No ammo changed.")
            changed |= refill(turret+0x29, rpg*max(1, guns), calibre, False, doctrine)
        for battery in (2, 3):
            capacity = guard(ship+0xb9b+battery*4)
            cal = guard(ship+0x69+battery*4)
            dp = guard(ship+0x84+battery, 1)
            if not 0 <= cal <= 20 or dp not in (0, 1):
                raise ValueError("Unsupported secondary magazine. No ammo changed.")
            changed |= refill(ship+0xb6f+battery*12, capacity, cal, bool(dp), doctrine)
        for mount in members(ship+0x9e, 128):
            if read(mount+0xf0, 1):
                continue
            guard(mount+0xf0, 1, 0)
            tubes = guard(mount+4)
            current = read(mount+0xf1)
            if not 0 <= tubes <= 256 or not 0 <= current <= 10000:
                raise ValueError("Invalid torpedo/missile capacity. No ammo changed.")
            if current < tubes:
                records.append((mount+0xf1, current, tubes, 4))
                changed = True
        changed_ships += bool(changed)
    if not changed_ships:
        return [], "Player ship magazines and ready tubes are already full, or no surviving armed player ships are present."
    return records, (f"Refilled ammo for {changed_ships} player ships: gun magazines and loaded torpedo/missile tubes. "
                     "Reserve reloads, aircraft stores and mines are unchanged. Weapon damage and cooldowns are preserved.")
