"""Super-superfiring turrets: up to three B and three X turrets, shown as B, BB, BBB and X, XX, XXX.

A turret's position is one letter (turret +8h) that the game's rules read everywhere: bearing, arcs, weight,
raised status (B, V and X are raised), the 3D view. Where it is drawn is stored apart (+0Ah angle, +0Eh
distance). So BB and BBB are B turrets in every rule and in the save, a copy of B as the player sees it, and XX and
XXX copies of X; only the designer knows them apart:
- The Add turret list (0x5B9208) offers "BB - Forward super-superfiring" after B while one B turret exists and
  "BBB - ..." while two do, and XX/XXX after X the same way. The designer takes a chosen line's first letter as
  the position (bnAddTurretClick), so these make B and X turrets.
- Placement: the game puts a new turret on its position's default spot (0x83F41C). A BB/BBB/XX/XXX line moves it
  one or two turret spacings towards midships: the A-to-B spacing for BB, the Y-to-X one for XX.
- The main gun list labels the second and third B (X) in list order BB and BBB (XX and XXX).
- Weight: the game makes a B turret x1.10 and an X turret x1.05 for its taller barbette (GetTurretWeight); each
  higher copy adds that step again (BB x1.20, BBB x1.30, XX x1.10, XXX x1.15).
- Crowding: the designer allows 7 centreline gun and torpedo mounts on any ship over 1,200 t (crowded, ROF -2, at
  the limit); every full 15,000 t above 10,000 t allows one more, up to 12.
The native height model has one raised level, so BB and BBB stand as high as B; they fire on B's arcs.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
import time

import ai_runtime
import live_cheats as live
import week_display as memory
import weekly_runtime as rt
from hull_rules import patch

REPORT = Path(__file__).with_name("super_superfiring_report.json")
ADAPTER_VERSION = 3
BASE = 0x301000
LETTERS = {"B": ("A", "Forward super-superfiring"), "X": ("Y", "Aft super-superfiring")}   # copy: (spacing from, name)
NATIVE = dict(add_item=(0x5B8DD0, "558bec51538955fc"), name=(0x91C5D8, "538bda0fb7c083c0"),
              location=(0x83F41C, "558bec83c4f05356"), assign=(0x30BCCC, "85d27426837af800"),
              limit=(0x948BE0, "8b402c3d59020000"))     # centreline mounts allowed, by displacement
DESIGNER_LOAD = (0x5B8DF6, "a1", "8b00")        # AddPositionItem: mov eax, [designer variable]; mov eax, [eax]
SITES = (   # (name, site, context start, context bytes): the hooked instruction is inside the checked context
    ("list_B", 0x5B92CC, 0x5B92C7, "8b55e48bc3e8fffaffff"),           # AddPositionItem(dialog, "B - ...")
    ("list_X", 0x5B958E, 0x5B9586, "8b955cffffff8bc3e83df8ffff"),     # AddPositionItem(dialog, "X - ...")
    ("place", 0x5CCA32, 0x5CCA2D, "e8ea2927008b45e889430a8b45ec89430e"),   # new turret's default spot stored
    ("label", 0x5CCC27, 0x5CCC20, "8d55ec0fb74308e8acf93400"),       # main gun list: name of the position
    ("weight", 0x950C7D, 0x950C7A, "89431766837b0856752c"),          # GetTurretWeight past its B and X terms
    ("crowd", 0x94897A, 0x948978, "8bc3e8610200008944240c"))         # CheckCentrelineMounts: its limit
REPLACED = dict(list_B=5, list_X=5, place=12, label=5, weight=5, crowd=5)
JUMPS = ("place", "weight")                                          # replaced by a jump; the rest are calls
DESIGN, TURRETS, ITEMS, CODE, GUNS, DISTANCE = 0xE6C, 0x9A, 0x2D8, 8, 4, 0xE   # designer/design/turret fields
POSITIONS, WEIGHT, TONS = 0x44C, 0x17, 0x2C                         # TdlgAddTurret.lbPosition, turret, design
STEPS = {"B": 11, "X": 21}                       # B x1.10 = 11/10: BB 12/11 more, BBB 13/11; X x1.05: 22/21, 23/21
CROWD_FROM, CROWD_STEP, CROWD_MAX = 10000, 15000, 12


def discover(blob, text_base):
    delta = text_base-BASE
    def at(address, size): return blob[address-BASE:address-BASE+size]
    if rt.method_address(blob, text_base, "bnAddTurretClick") != 0x5CC938+delta:
        raise ValueError("Super-superfiring refuses a changed ship designer (Add turret).")
    for name, (address, prologue) in NATIVE.items():
        if at(address, len(prologue)//2).hex() != prologue:
            raise ValueError("Super-superfiring refuses changed native code: "+name)
    for name, site, start, context in SITES:
        if at(start, len(context)//2).hex() != context:
            raise ValueError("Super-superfiring refuses changed native code: "+name)
    load, opcode, after = DESIGNER_LOAD
    if at(load, 1).hex() != opcode or at(load+5, 2).hex() != after:
        raise ValueError("Super-superfiring refuses changed native code: designer variable")
    info = {name: address+delta for name, (address, _) in NATIVE.items()}
    info["designer"] = struct.unpack_from("<I", blob, load-BASE+1)[0]
    info["sites"] = {name: site+delta for name, site, _, _ in SITES}
    info["originals"] = {name: at(site, REPLACED[name]).hex() for name, site, _, _ in SITES}
    return info


def delphi_string(value):
    return struct.pack("<HHiI", 1200, 2, -1, len(value)) + value.encode("utf-16-le") + b"\0\0"


def literals(address):
    """The texts at address: ({key: text pointer}, bytes)."""
    texts = {}
    for letter, (_, name) in LETTERS.items():
        for count in (2, 3):
            texts[("line", letter, count)] = f"{letter*count} - {name}"
            texts[("label", letter, count)] = letter*count
        texts[("name", letter)] = name
    data, pointers = bytearray(), {}
    for key, text in texts.items():
        pointers[key] = address+len(data)+12
        data += delphi_string(text)
        data += bytes(-len(data) % 4)
    return pointers, bytes(data)


def count_turrets(c, info, letter, stop_at=None):
    """EDX := the design's main turrets with letter (before the turret in stop_at, when given). Uses EAX, ECX,
    ESI, EDI."""
    count, counted = "count_"+letter, "counted_"+letter
    c.emit(b"\xa1"); c.u32(info["designer"]); c.emit(b"\x8b\x00\x8b\x80"); c.u32(DESIGN)
    c.emit(b"\x8b\x80"); c.u32(TURRETS); c.emit(b"\x8b\x48\x08\x8b\x70\x04\x33\xd2\x33\xff")   # ECX count, ESI items
    c.mark(count)
    c.emit(b"\x3b\xf9"); c.branch(b"\x0f\x8d", counted); c.emit(b"\x8b\x04\xbe\x47")         # EAX = items[EDI++]
    if stop_at:
        c.emit(b"\x3b"+stop_at); c.branch(b"\x0f\x84", counted)
    c.emit(b"\x66\x83\x78"+bytes([CODE, ord(letter)])); c.branch(b"\x0f\x85", count); c.emit(b"\x42")
    c.branch(b"\xe9", count)
    c.mark(counted)


def list_thunk(address, info, letter, texts):
    """Replaces AddPositionItem(EAX dialog, EDX line) for letter: the native line, then BB/BBB (XX/XXX)."""
    from campaign_security import Code
    c = Code(address)
    c.emit(b"\x50"); c.branch(b"\xe8", info["add_item"]); c.emit(b"\x58\x60\x8b\xd8")   # EBX dialog
    count_turrets(c, info, letter)
    for count in (2, 3):
        c.emit(b"\x83\xfa"+bytes([count-1])); c.branch(b"\x0f\x85", f"not{count}")
        c.emit(b"\xba"); c.u32(texts[("line", letter, count)]); c.branch(b"\xe9", "add")
        c.mark(f"not{count}")
    c.branch(b"\xe9", "done")
    c.mark("add"); c.emit(b"\x8b\x83"); c.u32(POSITIONS); c.emit(b"\x8b\x80"); c.u32(ITEMS)
    c.emit(b"\x8b\x08\xff\x51\x3c")                                                    # Items.Add(EDX)
    c.mark("done"); c.emit(b"\x61\xc3")
    return c.finish()


def place_thunk(address, info, back):
    """bnAddTurretClick (ESI designer, EBX the new turret, [EBP-10h] its line, [EBP-18h] its default spot):
    stores the spot, then a BB/BBB/XX/XXX line moves it one or two spacings towards midships."""
    from campaign_security import Code
    c = Code(address)
    c.emit(bytes.fromhex("8b45e889430a8b45ec89430e60"))             # the replaced stores; pushad
    c.emit(b"\x8b\x45\xf0\x85\xc0"); c.branch(b"\x0f\x84", "done")
    c.emit(b"\x0f\xb7\x08\x66\x3b\x48\x02"); c.branch(b"\x0f\x85", "done")   # "BB..." / "XX..."
    c.emit(b"\xbf\x01\x00\x00\x00\x66\x3b\x48\x04"); c.branch(b"\x0f\x85", "steps"); c.emit(b"\x47")   # EDI steps
    c.mark("steps")
    for letter, (spacing, _) in LETTERS.items():
        c.emit(b"\xba"); c.u32(ord(spacing)); c.emit(b"\x83\xf9"+bytes([ord(letter)])); c.branch(b"\x0f\x84", "spot")
    c.branch(b"\xe9", "done")
    c.mark("spot")                                                     # the spacing letter's own default spot
    c.emit(b"\x83\xec\x08\x8b\xc4\x6a\x01\x50\x8b\x4b"+bytes([GUNS])+b"\x8b\x86"); c.u32(DESIGN)
    c.branch(b"\xe8", info["location"])
    c.emit(b"\x8b\x44\x24\x04\x83\xc4\x08\x8b\x4b"+bytes([DISTANCE]))   # EAX its distance, ECX ours
    c.emit(b"\x2b\xc1\x0f\xaf\xc7\x2b\xc8\x83\xf9\x01"); c.branch(b"\x0f\x8d", "keep")
    c.emit(b"\xb9\x01\x00\x00\x00")                                    # never 0: 0 asks for a default spot
    c.mark("keep"); c.emit(b"\x89\x4b"+bytes([DISTANCE]))
    c.mark("done"); c.emit(b"\x61"); c.branch(b"\xe9", back)
    return c.finish()


def label_thunk(address, info, texts):
    """Replaces the main gun list's name call (EAX letter, EDX name variable, EBX turret; the letter's text pushed
    at [ESP+4] for the caption): the second and third B or X in list order read BB/BBB, XX/XXX."""
    from campaign_security import Code
    c = Code(address)
    c.branch(b"\xe8", info["name"]); c.emit(b"\x60\x0f\xb7\x4b"+bytes([CODE]))
    for letter in LETTERS:
        c.emit(b"\x83\xf9"+bytes([ord(letter)])); c.branch(b"\x0f\x84", "rank_"+letter)
    c.branch(b"\xe9", "done")
    for letter in LETTERS:
        c.mark("rank_"+letter)
        count_turrets(c, info, letter, stop_at=b"\xc3")               # cmp eax, ebx: the turrets before this one
        c.emit(b"\x83\xfa\x01"); c.branch(b"\x0f\x8c", "done")
        c.emit(b"\xb8"); c.u32(texts[("label", letter, 2)]); c.branch(b"\x0f\x84", "second_"+letter)
        c.emit(b"\xb8"); c.u32(texts[("label", letter, 3)])
        c.mark("second_"+letter); c.emit(b"\x89\x44\x24\x28\xba"); c.u32(texts[("name", letter)])
        c.branch(b"\xe9", "named")
    c.mark("named"); c.emit(b"\x8d\x45\xec"); c.branch(b"\xe8", info["assign"])  # the name variable [EBP-14h]
    c.mark("done"); c.emit(b"\x61\xc3")
    return c.finish()


def weight_thunk(address, back):
    """GetTurretWeight (EBX turret, EDI design, [EBX+17h] its weight with the native B or X factor): the second
    and third B or X in the design's list order weigh one and two more steps; then the replaced 'cmp ...,"V"'."""
    from campaign_security import Code
    c = Code(address)
    c.emit(b"\x60\x0f\xb7\x4b"+bytes([CODE]))
    for letter in STEPS:
        c.emit(b"\x83\xf9"+bytes([ord(letter)])); c.branch(b"\x0f\x84", "count")
    c.branch(b"\xe9", "done")
    c.mark("count"); c.emit(b"\x8b\x87"); c.u32(TURRETS); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "done")
    c.emit(b"\x8b\x68\x08\x8b\x70\x04\x33\xd2\x33\xff")                 # EBP count, ESI items, EDX before it
    c.mark("next"); c.emit(b"\x3b\xfd"); c.branch(b"\x0f\x8d", "done")  # not in the list: as native
    c.emit(b"\x8b\x04\xbe\x47\x3b\xc3"); c.branch(b"\x0f\x84", "found")
    c.emit(b"\x66\x39\x48"+bytes([CODE])); c.branch(b"\x0f\x85", "next"); c.emit(b"\x42"); c.branch(b"\xe9", "next")
    c.mark("found"); c.emit(b"\x85\xd2"); c.branch(b"\x0f\x84", "done")
    c.emit(b"\x83\xfa\x02"); c.branch(b"\x0f\x8e", "capped"); c.emit(b"\xba\x02\x00\x00\x00")
    c.mark("capped"); c.emit(b"\xbe"); c.u32(STEPS["B"]); c.emit(b"\x83\xf9"+bytes([ord("B")])); c.branch(b"\x0f\x84", "scale")
    c.emit(b"\xbe"); c.u32(STEPS["X"])
    c.mark("scale"); c.emit(b"\x8d\x0c\x16\x8b\x43"+bytes([WEIGHT])+b"\x0f\xaf\xc1\x99\xf7\xfe\x89\x43"+bytes([WEIGHT]))
    c.mark("done"); c.emit(b"\x61\x66\x83\x7b"+bytes([CODE, ord("V")])); c.branch(b"\xe9", back)
    return c.finish()


def crowd_thunk(address, info):
    """Replaces CheckCentrelineMounts' call limit(EAX design): one more centreline mount for every full CROWD_STEP
    tons above CROWD_FROM, up to CROWD_MAX."""
    from campaign_security import Code
    c = Code(address)
    c.emit(b"\x50"); c.branch(b"\xe8", info["limit"]); c.emit(b"\x59\x8b\x49"+bytes([TONS])+b"\x81\xe9"); c.u32(CROWD_FROM)
    c.branch(b"\x0f\x8c", "done")
    c.emit(b"\x50\x8b\xc1\x33\xd2\xb9"); c.u32(CROWD_STEP); c.emit(b"\xf7\xf1\x8b\xc8\x58\x03\xc1\x83\xf8"+bytes([CROWD_MAX]))
    c.branch(b"\x0f\x8e", "done"); c.emit(b"\xb8"); c.u32(CROWD_MAX)
    c.mark("done"); c.emit(b"\xc3")
    return c.finish()


def build(allocation, info):
    texts, data = literals(allocation)
    sites = info["sites"]
    at = dict(list_B=allocation+0x400, list_X=allocation+0x500, place=allocation+0x600, label=allocation+0x700,
              weight=allocation+0x900, crowd=allocation+0xA00)
    code = dict(list_B=list_thunk(at["list_B"], info, "B", texts), list_X=list_thunk(at["list_X"], info, "X", texts),
                place=place_thunk(at["place"], info, sites["place"]+REPLACED["place"]),
                label=label_thunk(at["label"], info, texts),
                weight=weight_thunk(at["weight"], sites["weight"]+REPLACED["weight"]),
                crowd=crowd_thunk(at["crowd"], info))
    room = dict(list_B=0x100, list_X=0x100, place=0x100, label=0x200, weight=0x100, crowd=0x80)
    if len(data) > 0x400 or any(len(code[k]) > room[k] for k in code):
        raise ValueError("Super-superfiring code exceeds its reservation.")
    blocks = [dict(name="Super-superfiring: texts", address=allocation, bytes=data.hex())]
    blocks += [dict(name="Super-superfiring: "+k, address=at[k], bytes=v.hex()) for k, v in code.items()]
    plans = []
    for name, site, _, _ in SITES:
        original = bytes.fromhex(info["originals"][name])
        opcode = b"\xe9" if name in JUMPS else b"\xe8"
        jump = opcode+struct.pack("<i", at[name]-sites[name]-5)
        plans.append(patch("Super-superfiring: "+name, sites[name], original, jump+b"\x90"*(len(original)-5)))
    return blocks, plans


def attach(wait=30):
    memory.configure()
    rt.configure_api()
    deadline = time.monotonic()+wait
    while True:
        games = [(pid, path) for pid, path in rt.process_candidates()
                 if path.resolve() == (rt.GAME/"RTW3.exe").resolve()]
        if len(games) == 1:
            break
        if time.monotonic() >= deadline:
            raise ValueError("Open this local RTW3 copy through Play with mods first.")
        time.sleep(0.5)
    pid, _ = games[0]
    handle = rt.K.OpenProcess(0x438, False, pid)
    if not handle:
        raise rt.win_error("Cannot open RTW3 for the super-superfiring turrets")
    try:
        module, base, _ = live.unhooked_text(pid, handle)
        if REPORT.exists():
            prior = json.loads(REPORT.read_text(encoding="utf-8"))
            if (prior.get("adapter_version") == ADAPTER_VERSION and prior.get("attached") and prior.get("pid") == pid
                    and prior.get("base") == module and rt.report_is_current(REPORT, pid)):
                ai_runtime.verify(handle, prior["patches"], "replacement")
                return prior
        _, text_base, blob = live.unhooked_text(pid, handle)
        info = discover(blob, text_base)
        ai_runtime.require_title_screen(handle, live.discover(blob, text_base))
        allocation = rt.K.VirtualAllocEx(handle, None, 0x1000, 0x3000, 0x40)
        if not allocation:
            raise rt.win_error("Cannot allocate the super-superfiring turret code")
        allocation = int(allocation)
        applied = []
        try:
            blocks, plans = build(allocation, info)
            for block in blocks:
                memory.write(handle, block["address"], bytes.fromhex(block["bytes"]))
            rt.K.FlushInstructionCache(handle, allocation, 0x1000)
            ai_runtime.verify(handle, plans, "original")
            for item in plans:
                rt.write_code(handle, item["address"], bytes.fromhex(item["original"]), bytes.fromhex(item["replacement"]))
                applied.append(item)
            ai_runtime.verify(handle, plans, "replacement")
            saved = {"adapter": "super-superfiring-turret", "adapter_version": ADAPTER_VERSION, "attached": True,
                     "pid": pid, "base": module, "allocation": allocation, "patches": plans,
                     "positions": "BB/BBB copy B, XX/XXX copy X; saved as B and X", "campaign_gameplay_verified": False}
            REPORT.write_text(json.dumps(saved, indent=2)+"\n", encoding="utf-8")
            return saved
        except Exception:
            for item in reversed(applied):
                rt.write_code(handle, item["address"], bytes.fromhex(item["replacement"]), bytes.fromhex(item["original"]))
            rt.K.VirtualFreeEx(handle, allocation, 0, 0x8000)
            raise
    finally:
        rt.K.CloseHandle(handle)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("attach",))
    args = parser.parse_args()
    try:
        print(json.dumps(attach()))
    except (OSError, ValueError, TypeError) as error:
        print(json.dumps({"ok": False, "message": str(error)}))
        raise SystemExit(1)
