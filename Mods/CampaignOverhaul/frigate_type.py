"""Frigate (FF): a true new ship type number, 15, as a separate test mod.

RTW3 has fifteen ship types (0-14) and reads a ship's type byte (+9D3h) in 1,637 places (frigate_type_sites.json,
found in the reference code). Type 15 is new to every one of them, so each read is rerouted through a small routine
that reports type 15 as a corvette (KE, 10): the game's rules, limits, AI, battle and campaign code treat a frigate
as a corvette. IDENTITY reads keep the real number: the type text of the ship window, two lists, four news texts and the
designer's class warning,
the ShipType key of saved designs and ships, the designer's Ship type list selection, and three copies of one
object's type into another (designer working copy, ship copies). VISUAL reads report a frigate as a destroyer
(DD, 9) instead: the ship picture's default hull outline and its size curve (frigates are destroyer-sized).
Type 15's text is FF: a new entry of the type-text routine's jump table. FF reads back as 15 through Expanded
Timeline's type reader, whose two data slots this adapter sets; that also turns off its corvette-to-FF rename, so
KE stays KE. The designer's Ship type list gains "FF - Frigate" when the designer opens (both of its entry routines:
the form itself is made at game start, before any mod attaches). Reads another adapter already hooks stay theirs.
Sizes: the designer's class rule for KE (also the frigate's, through the reroute) takes the real type: a corvette is
KE_SIZE tons, a frigate FF_SIZE, each with the KE torpedo test (Historical Hulls lets modern ones carry torpedoes);
the designer's type suggestion keeps an explicitly chosen KE or FF of its size (else it may offer another type).
Auto design: the designer's button designs types 0-10 only; for a frigate the AI designs a destroyer (DD), which
becomes a frigate before the designer takes it.
Saves: a frigate is saved as ShipType=FF. Without this mod Expanded Timeline loads it as a corvette.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import time

import weekly_runtime as rt

REPORT = Path(__file__).with_name("frigate_type_report.json")
SITES_FILE = Path(__file__).with_name("frigate_type_sites.json")
BASE = 0x301000                       # text base of the reference code the sites were found in
FF, KE, DD, TYPE = 15, 10, 9, 0x9D3
ITEM, TEXT = "FF - Frigate", "FF"
KE_SIZE, FF_SIZE = (200, 8000), (1500, 12000)   # tons: a corvette, a frigate (room for destroyer-sized designs)
SIZE_TEXT = ("A KE (corvette) must be between {} and {} tons and, before 1950, have no torpedoes.",
             "An FF (frigate) must be between {} and {} tons and, before 1950, have no torpedoes.")
# Reads that keep the real type number (see the docstring), reference addresses.
IDENTITY = {
    0x69F4E2: "ship window caption", 0x75CDDB: "list text", 0x94C865: "list text",
    0x7CF6E6: "news text", 0x7E83FE: "news text", 0x7E852B: "news text", 0x7E8805: "news text", 0x7E8932: "news text",
    0x93F595: "ShipType key of saved designs and ships", 0x5E308D: "the designer's class warning",
    0x5EC03A: "designer Ship type list selection",
    0x5E76FC: "designer working copy", 0x83BE65: "ship copy", 0x83C49C: "ship copy",
}
# Reads that draw a frigate as a destroyer: the hull outline reset (range, outline table, size) and the eight reads
# that feed the picture's size curve (designer, render, redraw of a resized hull).
VISUAL = {0x91AAED: "outline range", 0x91AAFF: "default outline", 0x91AB1E: "outline size",
          0x5CFF65: "picture size", 0x8401FE: "picture size", 0x8411DC: "picture size", 0x950327: "picture size",
          0x950338: "picture size", 0x950350: "picture size", 0x95037C: "picture size", 0x9503AB: "picture size",
          0x9503BC: "picture size"}
NATIVE = dict(type_text=0x9514E0, table=0x95150E, default_case=0x9516AC, case_tail=0x95160A, ustr_asg=0x30BCCC,
              ke_rule=0x5E3001, class_ok=0x5E3084, class_error=0x5E301E, suggest=0x5E22E4,
              auto=0x5E284A, auto_done=0x5E29AD)                       # sbAutoBuildClick (ESI the form)
KE_RULE = "7f1381ffc80000007c0b8bc6e8"   # the KE class rule after its ceiling: jg, cmp edi,200, jl, mov eax,esi, call
SUGGEST = "8bd880fb11"                   # after SuggestShipType: mov ebx,eax / cmp bl,11h
AUTO_TYPE = "8bd880fb0a"                 # the listed type: mov ebx,eax / cmp bl,0Ah, then JA "cannot auto design"
AUTO_DESIGN = "8b9e6c0e0000"             # the AI's design: mov ebx,[esi+0E6Ch], before the designer takes it
OPEN_SITES = (0x5D1544, 0x5D1ECF)   # the designer's two entry routines, ESI the form: cmp dword [eax],780h (the year)
YEAR_TEST = "813880070000"
TYPE_TEXT = "0fb6c383f8160f87"   # TypeText: movzx eax,bl / cmp eax,16h / ja
CB_TYPE, ITEMS, ADD = 0x550, 0x304, 0x3C   # TfrmDesignMain2.cbType, TComboBox.Items, TStrings.Add (virtual slot)
SLOTS = ("Modern fleet: frigate year", "Modern fleet: frigate type")
SLOT_VALUES = (0x7FFFFFFF, FF)     # never rename KE; "FF" reads as type 15


def sites():
    data = json.loads(SITES_FILE.read_text(encoding="utf-8"))
    if data["text_base"] != BASE: raise ValueError("Frigate type sites belong to another reference.")
    return [(address, bytes.fromhex(code)) for address, code in data["sites"]]


def decode(code):
    """(form, register, base register, immediate) of a type read; ValueError for anything else."""
    disp = lambda at: struct.unpack_from("<I", code, at)[0]
    if code[:2] == b"\x0f\xb6" and len(code) == 7: form, modrm, rest = "movzx", code[2], 3
    elif code[:1] == b"\x8a" and len(code) == 6: form, modrm, rest = "mov8", code[1], 2
    elif code[:1] == b"\x3a" and len(code) == 6: form, modrm, rest = "cmp_reg", code[1], 2
    elif code[:1] == b"\x80" and len(code) == 7 and (code[1] >> 3) & 7 == 7: form, modrm, rest = "cmp_imm", code[1], 2
    else: raise ValueError("Unsupported type read: "+code.hex())
    if modrm >> 6 != 2 or modrm & 7 == 4 or disp(rest) != TYPE: raise ValueError("Unsupported type operand: "+code.hex())
    return form, (modrm >> 3) & 7, modrm & 7, code[6] if form == "cmp_imm" else None


def thunk(code, seen=KE):
    """A routine called in place of the read: the same result, with type 15 seen as KE (or DD for the picture)."""
    form, reg, base, imm = decode(code)
    mem = lambda r: bytes([0x80 | r << 3 | base])+struct.pack("<I", TYPE)            # [base+9D3h]
    if form == "movzx":                       # flags kept: pushfd/popfd
        return (b"\x9c\x0f\xb6"+mem(reg)+bytes([0x83, 0xF8 | reg, FF, 0x75, 0x05, 0xB8 | reg])+struct.pack("<I", seen)
                + b"\x9d\xc3")
    if form == "mov8":
        return b"\x9c\x8a"+mem(reg)+bytes([0x80, 0xF8 | reg, FF, 0x75, 0x02, 0xB0 | reg, seen])+b"\x9d\xc3"
    taken = {base, reg & 3} if form == "cmp_reg" else {base}
    scratch = next(r for r in (0, 1, 2, 3) if r not in taken)   # a register with a low byte, saved around the read
    body = (bytes([0x50 | scratch, 0x0F, 0xB6])+mem(scratch)+bytes([0x83, 0xF8 | scratch, FF, 0x75, 0x05, 0xB8 | scratch])
            + struct.pack("<I", seen))
    if form == "cmp_imm": body += bytes([0x80, 0xF8 | scratch, imm])                 # cmp scratch8, imm8
    else: body += bytes([0x3A, 0xC0 | reg << 3 | scratch])                           # cmp r8, scratch8
    return body+bytes([0x58 | scratch, 0xC3])


def literal(text):
    return struct.pack("<HHiI", 1200, 2, -1, len(text))+text.encode("utf-16-le")+b"\0\0"


def discover(blob, base, owned=()):
    """Live text (other adapters' hooks in place) -> the sites to reroute and the native addresses, live.
    owned: (address, size) ranges other adapters hold; a read inside one is skipped."""
    delta = base-BASE
    at = lambda address: blob[address-base:]
    n = {key: value+delta for key, value in NATIVE.items()}
    if at(n["type_text"]+0x1B)[:8].hex() != TYPE_TEXT or at(n["type_text"]+0x27)[:3] != b"\xff\x24\x85":
        raise ValueError("Frigate type refuses changed native code: the type text routine.")
    if struct.unpack_from("<I", at(n["type_text"]+0x2A))[0] != n["table"]:
        raise ValueError("Frigate type refuses changed native code: the type text table.")
    table = struct.unpack_from("<23I", at(n["table"]))
    if table[FF] != n["default_case"] or table[16] != n["default_case"] or at(n["case_tail"])[:1] != b"\xe8":
        raise ValueError("Frigate type refuses changed native code: the type text cases.")
    if n["case_tail"]+5+struct.unpack_from("<i", at(n["case_tail"]+1))[0] != n["ustr_asg"]:
        raise ValueError("Frigate type refuses changed native code: the type text assignment.")
    items = b"\x8b\x86"+struct.pack("<I", CB_TYPE)+b"\x8b\x80"+struct.pack("<I", ITEMS)   # mov eax,[esi+550h]; ...Items
    n["open"] = [site+delta for site in OPEN_SITES]
    for site in n["open"]:
        if at(site-5)[:1] != b"\xa1" or at(site)[:6].hex() != YEAR_TEST or at(site+6)[:1] != b"\x7f" or at(site+8)[:12] != items:
            raise ValueError("Frigate type refuses changed native code: the designer's Ship type list.")
    if at(n["ke_rule"])[:13].hex() != KE_RULE or at(n["suggest"])[:5].hex() != SUGGEST or at(n["class_error"])[:1] != b"\xe8":
        raise ValueError("Frigate type refuses changed native code: the designer's KE class rule.")
    if (at(n["auto"])[:5].hex() != AUTO_TYPE or at(n["auto"]+5)[:1] != b"\x77" or at(n["auto_done"])[:6].hex() != AUTO_DESIGN
            or any(site < a+s and a < site+6 for site in (n["auto"], n["auto_done"]) for a, s in owned)):
        raise ValueError("Frigate type refuses changed native code: the designer's auto design.")
    torpedo = n["ke_rule"]+12                                                           # Historical Hulls may hold it
    n["torpedoes"] = torpedo+5+struct.unpack_from("<i", at(torpedo+1))[0]
    reroute, skipped = [], []
    for address, code in sites():
        live = address+delta
        if address in IDENTITY: continue
        if at(live)[:len(code)] != code or any(live < a+s and a < live+len(code) for a, s in owned):
            skipped.append(live); continue
        reroute.append((live, code))
    return dict(delta=delta, native=n, reroute=reroute, skipped=skipped)


def build(allocation, info):
    """Code at allocation: the type-15 text case, texts and the designer hook in the first page, then the read
    routines. Returns (code bytes, patches)."""
    from campaign_security import Code
    from hull_rules import patch
    n = info["native"]
    at = dict(case=allocation, add=allocation+0x40, open=allocation+0x80, text=allocation+0x100, item=allocation+0x140,
              added=allocation+0x180, size=allocation+0x1C0, suggest=allocation+0x280, ke_text=allocation+0x300,
              ff_text=allocation+0x400, auto=allocation+0x500, auto_done=allocation+0x540, auto_flag=allocation+0x580,
              thunks=allocation+0x1000)
    image = bytearray(at["thunks"]-allocation)
    put = lambda address, body: image.__setitem__(slice(address-allocation, address-allocation+len(body)), body)
    put(at["text"], literal(TEXT)); put(at["item"], literal(ITEM))
    put(at["ke_text"], literal(SIZE_TEXT[0].format(*KE_SIZE))); put(at["ff_text"], literal(SIZE_TEXT[1].format(*FF_SIZE)))
    c = Code(at["case"]); c.emit(b"\x8b\xc6\xba"); c.u32(at["text"]+12); c.branch(b"\xe9", n["case_tail"])   # like case KE
    put(at["case"], c.finish())
    # add(EAX form): the Ship type list gains the item once per list object (added: the last list it went to).
    c = Code(at["add"]); c.emit(b"\x8b\x80"); c.u32(CB_TYPE); c.emit(b"\x8b\x80"); c.u32(ITEMS)
    c.emit(b"\x3b\x05"); c.u32(at["added"]); c.branch(b"\x0f\x84", "done"); c.emit(b"\xa3"); c.u32(at["added"])
    c.emit(b"\xba"); c.u32(at["item"]+12); c.emit(b"\x8b\x08\xff\x51"+bytes([ADD]))
    c.mark("done"); c.emit(b"\xc3")
    put(at["add"], c.finish())
    plans = [patch("Frigate type: text case", n["table"]+4*FF, struct.pack("<I", n["default_case"]), struct.pack("<I", at["case"]))]
    for index, site in enumerate(n["open"]):   # the year test, then back after it
        c = Code(at["open"]+0x20*index); c.emit(b"\x60\x8b\xc6"); c.branch(b"\xe8", at["add"])
        c.emit(b"\x61"+bytes.fromhex(YEAR_TEST)); c.branch(b"\xe9", site+6)
        put(at["open"]+0x20*index, c.finish())
        plans.append(patch("Frigate type: Ship type list item", site, bytes.fromhex(YEAR_TEST),
                           b"\xe9"+struct.pack("<i", at["open"]+0x20*index-site-5)+b"\x90"))
    # The KE class rule (EDI tons, ESI design): each type its size, then the torpedo test, each its message.
    c = Code(at["size"]); c.emit(b"\x0f\xb6\x86"); c.u32(TYPE)
    for kind, (low, high) in ((FF, FF_SIZE), (KE, KE_SIZE)):
        if kind == FF: c.emit(b"\x83\xf8"+bytes([FF])); c.branch(b"\x0f\x85", "ke")
        else: c.mark("ke")
        c.emit(b"\x81\xff"); c.u32(high); c.branch(b"\x0f\x8f", f"error{kind}")
        c.emit(b"\x81\xff"); c.u32(low); c.branch(b"\x0f\x8c", f"error{kind}")
        c.emit(b"\x8b\xc6"); c.branch(b"\xe8", n["torpedoes"]); c.emit(b"\x84\xc0"); c.branch(b"\x0f\x85", f"error{kind}")
        c.branch(b"\xe9", n["class_ok"])
    for kind, text in ((FF, at["ff_text"]), (KE, at["ke_text"])):
        c.mark(f"error{kind}"); c.emit(b"\x8d\x45\xfc\xba"); c.u32(text+12); c.branch(b"\xe9", n["class_error"])
    put(at["size"], c.finish())
    plans.append(patch("Frigate type: KE and FF sizes", n["ke_rule"], bytes.fromhex(KE_RULE[:20]),
                       b"\xe9"+struct.pack("<i", at["size"]-n["ke_rule"]-5)+b"\x90"*5))
    # After SuggestShipType (EAX its type, ESI the design): a KE or FF of its own size stays what was chosen.
    c = Code(at["suggest"]); c.emit(b"\x51\x52\x0f\xb6\x8e"); c.u32(TYPE); c.emit(b"\x8b\x56\x2c")
    for kind, (low, high) in ((FF, FF_SIZE), (KE, KE_SIZE)):
        c.emit(b"\x83\xf9"+bytes([kind])); c.branch(b"\x0f\x85", f"not{kind}")
        c.emit(b"\x81\xfa"); c.u32(low); c.branch(b"\x0f\x8c", "keep")
        c.emit(b"\x81\xfa"); c.u32(high); c.branch(b"\x0f\x8f", "keep")
        c.emit(b"\xb8"+struct.pack("<I", KE)); c.branch(b"\xe9", "keep")        # the game reads a frigate as KE
        c.mark(f"not{kind}")
    c.mark("keep"); c.emit(b"\x5a\x59"+bytes.fromhex(SUGGEST)+b"\xc3")
    put(at["suggest"], c.finish())
    plans.append(patch("Frigate type: type suggestion", n["suggest"], bytes.fromhex(SUGGEST),
                       b"\xe8"+struct.pack("<i", at["suggest"]-n["suggest"]-5)))
    # Auto design: a listed frigate is designed as a destroyer (the flag remembers it), then the new design is retyped
    # before the designer takes it, so the type suggestion and the class rule see a frigate.
    c = Code(at["auto"]); c.emit(b"\x8b\xd8\xc6\x05"); c.u32(at["auto_flag"]); c.emit(b"\x00")
    c.emit(b"\x80\xfb"+bytes([FF])); c.branch(b"\x0f\x85", "native")
    c.emit(b"\xc6\x05"); c.u32(at["auto_flag"]); c.emit(b"\x01\xb3"+bytes([DD]))
    c.mark("native"); c.emit(b"\x80\xfb\x0a"); c.branch(b"\xe9", n["auto"]+5)
    put(at["auto"], c.finish())
    c = Code(at["auto_done"]); c.emit(bytes.fromhex(AUTO_DESIGN))
    c.emit(b"\x80\x3d"); c.u32(at["auto_flag"]); c.emit(b"\x00"); c.branch(b"\x0f\x84", "back")
    c.emit(b"\xc6\x83"); c.u32(TYPE); c.emit(bytes([FF]))
    c.mark("back"); c.branch(b"\xe9", n["auto_done"]+6)
    put(at["auto_done"], c.finish())
    for name, code, label in (("auto", AUTO_TYPE, "auto design as a destroyer"), ("auto_done", AUTO_DESIGN, "auto design to frigate")):
        old = bytes.fromhex(code)
        plans.append(patch("Frigate type: "+label, n[name], old,
                           b"\xe9"+struct.pack("<i", at[name]-n[name]-5)+b"\x90"*(len(old)-5)))
    cursor = at["thunks"]
    for address, code in info["reroute"]:
        body = thunk(code, DD if address-info["delta"] in VISUAL else KE); image += body
        plans.append(patch("Frigate type: read", address, code, b"\xe8"+struct.pack("<i", cursor-address-5)+b"\x90"*(len(code)-5)))
        cursor += len(body)
    return bytes(image), plans


def owned_ranges(pid):
    """Hooks the other adapters of this launch already hold (the runtime host's report)."""
    import runtime_host
    if not runtime_host.REPORT.exists(): return []
    report = json.loads(runtime_host.REPORT.read_text(encoding="utf-8"))
    if (report.get("session") or {}).get("pid") != pid: return []
    return [(hook["address"], hook["size"]) for hook in report.get("hooks", []) if hook.get("owner") != "frigate-type"]


def navy_slots(pid, module):
    import modern_research
    saved = json.loads(modern_research.REPORT.read_text(encoding="utf-8")) if modern_research.REPORT.exists() else {}
    if not (saved.get("attached") and saved.get("pid") == pid and saved.get("base") == module):
        raise ValueError("The frigate type needs Expanded Timeline attached first.")
    blocks = {block["name"]: block["address"] for block in saved.get("code_blocks", [])}
    if any(name not in blocks for name in SLOTS):
        raise ValueError("The frigate type needs Expanded Timeline 1.31.0 or later.")
    return [blocks[name] for name in SLOTS]


def attach(wait=30):
    import week_display as memory
    import live_cheats as live
    memory.configure()
    deadline = time.monotonic()+wait
    while True:
        games = [(pid, path) for pid, path in rt.process_candidates() if path == rt.GAME/"RTW3.exe"]
        if len(games) == 1: break
        if time.monotonic() >= deadline: raise ValueError("Open the local game through Play with mods first.")
        time.sleep(0.5)
    pid, _ = games[0]
    handle = rt.K.OpenProcess(0x438, False, pid)
    if not handle: raise rt.win_error("Cannot open the local game")
    try:
        module, _ = rt.module_info(pid)
        if REPORT.exists():
            saved = json.loads(REPORT.read_text(encoding="utf-8"))
            if saved.get("attached") and saved.get("pid") == pid and saved.get("base") == module and rt.report_is_current(REPORT, pid):
                verify(handle, saved["patches"], "replacement")
                return saved
        module, base, blob = live.unhooked_text(pid, handle)
        info = discover(blob, base, owned_ranges(pid))
        slots = navy_slots(pid, module)
        size = 0x1000+((sum(len(thunk(code)) for _, code in info["reroute"])+0xFFF) & ~0xFFF)
        allocation = rt.K.VirtualAllocEx(handle, None, size, 0x3000, 0x40)
        if not allocation: raise rt.win_error("Cannot allocate the frigate type")
        applied, old_slots = [], [rt.read(handle, slot, 4) for slot in slots]
        try:
            image, plans = build(allocation, info)
            memory.write(handle, allocation, image); rt.K.FlushInstructionCache(handle, allocation, len(image))
            verify(handle, plans, "original")
            for plan in plans:
                rt.write_code(handle, plan["address"], bytes.fromhex(plan["original"]), bytes.fromhex(plan["replacement"]))
                applied.append(plan)
            verify(handle, plans, "replacement")
            for slot, value in zip(slots, SLOT_VALUES): memory.write(handle, slot, struct.pack("<I", value))
            saved = {"pid": pid, "base": module, "attached": True, "allocation": allocation, "patches": plans,
                     "rerouted": len(info["reroute"]), "skipped": info["skipped"], "identity": len(IDENTITY),
                     "slots": [dict(address=slot, old=old.hex()) for slot, old in zip(slots, old_slots)],
                     "code_sha256": hashlib.sha256(image).hexdigest(), "personal_saves_modified": False}
            REPORT.write_text(json.dumps(saved, indent=2)+"\n", encoding="utf-8")
            return saved
        except Exception:
            for slot, old in zip(slots, old_slots): memory.write(handle, slot, old)
            for plan in reversed(applied):
                rt.write_code(handle, plan["address"], bytes.fromhex(plan["replacement"]), bytes.fromhex(plan["original"]))
            if not applied: rt.K.VirtualFreeEx(handle, allocation, 0, 0x8000)
            raise
    finally: rt.K.CloseHandle(handle)


def verify(handle, plans, key):
    for plan in plans:
        data = bytes.fromhex(plan[key])
        if rt.read(handle, plan["address"], len(data)) != data:
            raise ValueError("The frigate type attachment changed; operation refused.")


def detach():
    import week_display as memory
    memory.configure()
    saved = json.loads(REPORT.read_text(encoding="utf-8"))
    if not saved.get("attached"): return saved
    if dict(rt.process_candidates()).get(saved["pid"]) != rt.GAME/"RTW3.exe":
        raise ValueError("The frigate type session has ended.")
    handle = rt.K.OpenProcess(0x438, False, saved["pid"])
    if not handle: raise rt.win_error("Cannot open the local game")
    try:
        if rt.module_info(saved["pid"])[0] != saved["base"]: raise ValueError("The game session changed.")
        verify(handle, saved["patches"], "replacement")
        for slot in saved["slots"]: memory.write(handle, slot["address"], bytes.fromhex(slot["old"]))
        for plan in reversed(saved["patches"]):
            rt.write_code(handle, plan["address"], bytes.fromhex(plan["replacement"]), bytes.fromhex(plan["original"]))
        saved["attached"] = False
        REPORT.write_text(json.dumps(saved, indent=2)+"\n", encoding="utf-8")
        return saved
    finally: rt.K.CloseHandle(handle)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("attach", "detach"))
    args = parser.parse_args()
    print(json.dumps(attach() if args.command == "attach" else detach()))
