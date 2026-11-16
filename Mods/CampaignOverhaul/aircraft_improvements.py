"""Native aircraft context-menu improvements, using the original request dialog.

The game constructs the successor. Only that scoped call is redirected from the
turn-local scratch list into the saved aircraft list and scheduled as a prototype.
No custom campaign persistence or managed UI is needed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import time

import weekly_runtime as rt
import modern_research as audit
from campaign_security import Code
from hull_rules import patch

REPORT = Path(__file__).with_name("aircraft_improvements_report.json")
REFERENCE = 0x301000
# Reviewed code ranges from the authenticated 1.01.44 Steam build. Normalize PE
# relocations before comparison; never discover by a short, unchecked signature.
AUDITED = {
    "menu_create": (0x52729c, 132, "9646bdddf036eb19c126d1fb228ea7b5a86aa5cc164e821ee3627afbb7c3a81f"),
    "menu_add": (0x52af2c, 32, "e6769f79674b299448dd3efc6f0576e4512ee57cd521e20cda129671a1e8d8f3"),
    "menu_caption": (0x52a91c, 116, "175f1359ae57a062a2274e559a9c12ae2bd79edc91a1b1487f2450c0a6480821"),
    "menu_enabled": (0x52a9e4, 116, "89b72c7fbb6c46f866bcd384288b8bffd7b0120d0ddc8952e6f260cb266af261"),
    "form_show": (0x62c4b4, 85, "51a80435f78255f87929e6df7ef6e52b54d7dec98cce9933f9bcee5842676ad4"),
    "popup": (0x62c600, 55, "9c0035c2e1c7caeba2bf10fa05319bdc18214ef71990cad18d3b73896ba7ad48"),
    "request_click": (0x62a790, 141, "9ac26bbf17f9d0fdcb500551875fb0c293ebba1449b7dd23e8f9370e838ee159"),
    "request_execute": (0x628b48, 161, "9c70930cb212497f513ee8391f9b9f9a4ecfc4636f0cc5d2b2013a89310d951a"),
    "request_ok": (0x628880, 543, "565c39e23eb190205e2b14948c75cacac26a3a6b2fd38f9df1f2a201f7914883"),
    "variant": (0x96bc18, 1932, "b5c1d8438222dabf4bab5a4f0055f21c689ca5b647b93b536a7162c045c9297d"),
    "copy": (0x979aec, 238, "b918cac8f1afc87864ace14c5056b30982ced68a4ee57c4c55ecca1984bf603a"),
    "priorities": (0x96a71c, 2135, "47534192c739f9740e0c0aad1860e9f601429a1f2183cdb991c24b050dbab15b"),
    "development": (0x7ed0b4, 508, "46cdea2a3794322292090c1a972d63cee972c03395ad7f2f9dfa598557553be9"),
}

# Shared state is touched only on the native UI thread. A modal request cannot
# run another improvement. No raw aircraft pointer is kept as pending save data.
MODE, FORM, MENU, SOURCE, SOURCE_ID, MAIN, OLD_VERSION, CLONE, DELAY = range(0, 36, 4)


def discover(blob, base):
    import timeline_2030   # its year-table bytes may already be in place inside these windows
    normalized = timeline_2030.native_year_bytes(bytearray(audit.normalize(blob, base)))
    delta = base-REFERENCE
    for name, (address, size, digest) in AUDITED.items():
        start = address-REFERENCE
        if hashlib.sha256(normalized[start:start+size]).hexdigest() != digest:
            raise ValueError("Aircraft improvement refuses changed native code: " + name)
    if rt.method_address(blob, base, "bnRequestClick") != 0x62a790+delta:
        raise ValueError("Unsupported aircraft request entry.")
    # Cross-check class and property metadata used to create a genuine VCL menu.
    checks = {0x524f04: b"\x07\x09TMenuItem", 0x628780: b"\x13TdlgAircraftRequest",
              0x6294f8: b"\x11TfrmAircraftTypes"}
    for address, expected in checks.items():
        off = address-REFERENCE
        if normalized[off:off+len(expected)] != expected:
            raise ValueError("Unsupported native aircraft/menu metadata.")
    pointers = {"menu_vmt": 0x52450c, "aircraft_vmt": 0x9596b8,
                "main_root": 0x9f7a70, "dialog_root": 0x9f6dc4,
                "aircraft_root": 0x9f7048, "selected": 0x4bc49c,
                "refresh": 0x62a420, "explain": 0x62ca60, "message": 0x4d7124}
    pointers.update({name: values[0] for name, values in AUDITED.items()})
    info = {name: value+delta for name, value in pointers.items()}
    sites = [("Aircraft native menu", 0x62c4f2, 6), ("Aircraft menu availability", 0x62c600, 9),
             ("Improvement request role", 0x62a7ec, 8), ("Save native improvement prototype", 0x96c156, 7),
             ("Defer improvement availability", 0x96c162, 13)]
    info["sites"] = [{"label": label, "address": address+delta,
                      "original": blob[address-REFERENCE:address-REFERENCE+length].hex()} for label, address, length in sites]
    info["variant_quiet_return"] = 0x96c318+delta
    info["variant_foreign_branch"] = 0x96c284+delta
    return info


def abs32(code, opcode, address):
    code.emit(opcode); code.u32(address)


def main_object(code, info):
    abs32(code, b"\xa1", info["main_root"]); code.emit(b"\x8b\x00")


def eligible(address, state, info):
    """EAX=form -> EAX=selected player aircraft or zero; preserve nonvolatiles."""
    c = Code(address); c.emit(b"\x53\x56\x8b\xd8")
    abs32(c, b"\x83\x3d", state+MODE); c.emit(b"\x00"); c.branch(b"\x0f\x85", "no")
    main_object(c, info); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "no")
    c.emit(bytes.fromhex("83b8a94a000000")); c.branch(b"\x0f\x85", "no")
    c.emit(bytes.fromhex("83b80432000000")); c.branch(b"\x0f\x84", "no")
    c.emit(bytes.fromhex("8b833804000085c0")); c.branch(b"\x0f\x84", "no")
    c.branch(b"\xe8", info["selected"]); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "no")
    c.emit(b"\x8b\x40\x28\x85\xc0"); c.branch(b"\x0f\x84", "no")
    c.emit(b"\x81\x38"); c.u32(info["aircraft_vmt"]); c.branch(b"\x0f\x85", "no")
    for field in (0x88, 0x84):
        c.emit(b"\x83\xb8"); c.u32(field); c.emit(b"\x00"); c.branch(b"\x0f\x85", "no")
    c.emit(bytes.fromhex("83b88c00000005")); c.branch(b"\x0f\x83", "no")
    c.emit(bytes.fromhex("80b89000000000")); c.branch(b"\x0f\x85", "no")
    c.branch(b"\xe9", "done")
    c.mark("no"); c.emit(b"\x31\xc0")
    c.mark("done"); c.emit(b"\x5e\x5b\xc3"); return c.finish()


def ensure_menu(address, state, info, caption, handler):
    c = Code(address); c.emit(b"\x53\x56\x8b\xd8")
    abs32(c, b"\x3b\x1d", state+FORM); c.branch(b"\x0f\x84", "done")
    c.emit(bytes.fromhex("8b8b4c04000085c9")); c.branch(b"\x0f\x84", "done")
    c.emit(b"\xb8"); c.u32(info["menu_vmt"]); c.emit(b"\xb2\x01\x8b\xcb")
    c.branch(b"\xe8", info["menu_create"]); c.emit(b"\x8b\xf0")
    abs32(c, b"\xc7\x86\x98\x00\x00\x00", handler)
    c.emit(bytes.fromhex("899e9c000000"))
    c.emit(b"\xba"); c.u32(caption); c.emit(b"\x8b\xc6"); c.branch(b"\xe8", info["menu_caption"])
    c.emit(bytes.fromhex("8b834c0400008b40448bd6")); c.branch(b"\xe8", info["menu_add"])
    abs32(c, b"\x89\x35", state+MENU); abs32(c, b"\x89\x1d", state+FORM)
    c.mark("done"); c.emit(b"\x5e\x5b\xc3"); return c.finish()


def menu_hook(address, state, info, target, availability=False):
    site = info["sites"][1 if availability else 0]
    c = Code(address); c.emit(b"\x9c\x60")
    c.emit(b"\x8b\x44\x24\x1c" if availability else b"\x8b\xc3")
    c.branch(b"\xe8", target)
    if availability:
        c.emit(b"\x85\xc0\x0f\x95\xc2")
        abs32(c, b"\xa1", state+MENU); c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "done")
        c.branch(b"\xe8", info["menu_enabled"])
        c.mark("done")
    c.emit(b"\x61\x9d"+bytes.fromhex(site["original"]))
    c.branch(b"\xe9", site["address"]+len(bytes.fromhex(site["original"]))); return c.finish()


def dispatch_hook(address, state, info):
    c = Code(address)
    abs32(c, b"\x83\x3d", state+MODE); c.emit(b"\x01"); c.branch(b"\x0f\x85", "normal")
    # EBX holds the modal request form during Execute. Its role control is
    # disabled only for this call; the native dialog fills/selects the role.
    c.emit(b"\x53\x8b\xd8\x8b\x83\x48\x04\x00\x00\x31\xd2\x8b\x08\xff\x91\x9c\x00\x00\x00")
    abs32(c, b"\xa1", state+SOURCE); c.emit(bytes.fromhex("0fb690810000008bc3"))
    c.branch(b"\xe8", info["request_execute"])
    c.emit(bytes.fromhex("8b8348040000b2018b08ff919c0000005b"))
    c.branch(b"\xe9", "return")
    c.mark("normal"); c.emit(b"\x83\xca\xff"); c.branch(b"\xe8", info["request_execute"])
    c.mark("return"); c.branch(b"\xe9", info["sites"][2]["address"]+8); return c.finish()


def click_handler(address, state, info, eligibility, error_text):
    c = Code(address); c.emit(b"\x9c\x60\x8b\xd8"); c.branch(b"\xe8", eligibility)
    c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "done")
    abs32(c, b"\xa3", state+SOURCE)
    c.emit(bytes.fromhex("8b9099000000")); abs32(c, b"\x89\x15", state+SOURCE_ID)
    c.emit(bytes.fromhex("8b908c000000")); abs32(c, b"\x89\x15", state+OLD_VERSION)
    main_object(c, info); abs32(c, b"\xa3", state+MAIN)
    abs32(c, b"\xc7\x05", state+MODE); c.u32(1)
    c.emit(b"\x8b\xc3\x31\xd2"); c.branch(b"\xe8", info["request_click"])
    main_object(c, info); abs32(c, b"\x3b\x05", state+MAIN); c.branch(b"\x0f\x85", "clear")
    c.emit(bytes.fromhex("8b90a94a000085d2")); c.branch(b"\x0f\x8e", "clear")
    abs32(c, b"\x89\x15", state+DELAY)
    abs32(c, b"\xc7\x05", state+CLONE); c.u32(0)
    abs32(c, b"\xa1", state+SOURCE); abs32(c, b"\x8b\x15", state+SOURCE_ID)
    c.emit(bytes.fromhex("399099000000")); c.branch(b"\x0f\x85", "cancel_request")
    abs32(c, b"\xc7\x05", state+MODE); c.u32(2)
    c.branch(b"\xe8", info["variant"])
    abs32(c, b"\x83\x3d", state+CLONE); c.emit(b"\x00"); c.branch(b"\x0f\x85", "cancel_request")
    # A caught native constructor error must not leave the source superseded.
    abs32(c, b"\xa1", state+SOURCE); abs32(c, b"\x8b\x15", state+OLD_VERSION)
    c.emit(bytes.fromhex("89908c000000"))
    c.emit(b"\xb8"); c.u32(error_text); c.emit(bytes.fromhex("83caff83c9ff")); c.branch(b"\xe8", info["message"])
    c.mark("cancel_request"); main_object(c, info); c.emit(bytes.fromhex("c780a94a000000000000"))
    # Refresh the genuine list with the same argument contract as Obsolete1.
    c.emit(bytes.fromhex("6a0f6a006a018b937504000031c98bc3")); c.branch(b"\xe8", info["refresh"])
    c.emit(b"\x8b\xc3"); c.branch(b"\xe8", info["explain"])
    c.mark("clear"); abs32(c, b"\xc7\x05", state+MODE); c.u32(0)
    abs32(c, b"\xc7\x05", state+SOURCE); c.u32(0)
    c.mark("done"); c.emit(b"\x61\x9d\xc3"); return c.finish()


def prototype_hook(address, state, info):
    c = Code(address); c.emit(b"\x9c")
    abs32(c, b"\x83\x3d", state+MODE); c.emit(b"\x02"); c.branch(b"\x0f\x85", "normal")
    abs32(c, b"\x3b\x35", state+SOURCE); c.branch(b"\x0f\x85", "normal")
    c.emit(b"\x60\x8b\x07\x31\xd2\xb9\x01\x00\x00\x00"); c.branch(b"\xe8", info["priorities"])
    main_object(c, info); c.emit(bytes.fromhex("8b90043200000fb68e81000000"))
    c.branch(b"\xe8", info["development"])
    abs32(c, b"\x03\x05", state+DELAY)
    c.emit(bytes.fromhex("8b17898284000000"))
    # The new prototype is saved immediately, with no turn-local scratch entry.
    c.emit(b"\x61\x9d\x8b\x17")
    abs32(c, b"\xa1", info["aircraft_root"]); c.emit(b"\x8b\x00")
    c.branch(b"\xe9", info["sites"][3]["address"]+7)
    c.mark("normal"); c.emit(b"\x9d"+bytes.fromhex(info["sites"][3]["original"]))
    c.branch(b"\xe9", info["sites"][3]["address"]+7); return c.finish()


def feedback_hook(address, state, info):
    c = Code(address); c.emit(b"\x9c")
    abs32(c, b"\x83\x3d", state+MODE); c.emit(b"\x02"); c.branch(b"\x0f\x85", "normal")
    abs32(c, b"\x3b\x35", state+SOURCE); c.branch(b"\x0f\x85", "normal")
    c.emit(b"\x60\x8b\x07"); abs32(c, b"\xa3", state+CLONE); c.emit(b"\x61\x9d")
    # No premature "available" announcement or obsoletion of the in-service
    # source. The native prototype completion event runs after development.
    c.branch(b"\xe9", info["variant_quiet_return"])
    c.mark("normal"); c.emit(bytes.fromhex("9d83be8800000000"))
    c.branch(b"\x0f\x85", info["variant_foreign_branch"])
    c.branch(b"\xe9", info["sites"][4]["address"]+13); return c.finish()


def build(allocation, info):
    state = allocation+0xf000
    locations = {"eligible": allocation, "ensure": allocation+0x800, "click": allocation+0x1000,
                 "show": allocation+0x1800, "popup": allocation+0x2000, "dispatch": allocation+0x2800,
                 "prototype": allocation+0x3000, "feedback": allocation+0x3800}
    payloads = []
    def literal(offset, value):
        data = struct.pack("<HHiI", 1200, 2, -1, len(value))+value.encode("utf-16-le")+b"\0\0"
        payloads.append({"address": allocation+offset, "bytes": data.hex()})
        return allocation+offset+12
    caption = literal(0xe000, "Improve aircraft model...")
    error = literal(0xe200, "Aircraft improvement could not be created. No new request is pending.")
    routines = {
        "eligible": eligible(locations["eligible"], state, info),
        "ensure": ensure_menu(locations["ensure"], state, info, caption, locations["click"]),
        "click": click_handler(locations["click"], state, info, locations["eligible"], error),
        "show": menu_hook(locations["show"], state, info, locations["ensure"]),
        "popup": menu_hook(locations["popup"], state, info, locations["eligible"], True),
        "dispatch": dispatch_hook(locations["dispatch"], state, info),
        "prototype": prototype_hook(locations["prototype"], state, info),
        "feedback": feedback_hook(locations["feedback"], state, info),
    }
    blocks = []
    for name, data in routines.items():
        if len(data) > 0x800: raise ValueError("Aircraft improvement routine exceeds its reservation: " + name)
        blocks.append({"name": name, "address": locations[name], "bytes": data.hex()})
    plans = []
    for site, name in zip(info["sites"], ("show", "popup", "dispatch", "prototype", "feedback")):
        original = bytes.fromhex(site["original"])
        replacement = b"\xe9"+struct.pack("<i", locations[name]-site["address"]-5)+b"\x90"*(len(original)-5)
        plans.append(patch(site["label"], site["address"], original, replacement))
    return {"state": state, "locations": locations, "patches": plans, "code_blocks": blocks, "literals": payloads}


def attach(wait=30):
    import ai_runtime as ai
    import live_cheats as live
    import week_display as memory
    ai.checked_game(); memory.configure(); deadline = time.monotonic()+wait
    while True:
        games = [(pid, path) for pid, path in rt.process_candidates() if path == rt.GAME/"RTW3.exe"]
        if len(games) == 1: break
        if time.monotonic() >= deadline: raise ValueError("Start one local game through Play with mods.")
        time.sleep(0.5)
    pid = games[0][0]; handle = rt.K.OpenProcess(0x438, False, pid)
    if not handle: raise rt.win_error("Cannot open the aircraft improvement adapter")
    try:
        module, _ = rt.module_info(pid)
        if REPORT.exists():
            old = json.loads(REPORT.read_text(encoding="utf-8"))
            if old.get("attached") and old.get("pid") == pid and old.get("base") == module and rt.report_is_current(REPORT, pid):
                ai.verify(handle, old["patches"], "replacement"); return old
        base, blob = rt.text_section(handle, module)
        info = discover(blob, base); ai.require_title_screen(handle, live.discover(blob, base))
        allocation = rt.K.VirtualAllocEx(handle, None, 0x10000, 0x3000, 0x40)
        if not allocation: raise rt.win_error("Cannot allocate aircraft improvement routines")
        applied = []
        try:
            product = build(allocation, info)
            for block in product["code_blocks"]+product["literals"]:
                memory.write(handle, block["address"], bytes.fromhex(block["bytes"]))
            rt.K.FlushInstructionCache(handle, allocation, 0x10000)
            ai.verify(handle, product["patches"], "original")
            for item in product["patches"]:
                rt.write_code(handle, item["address"], bytes.fromhex(item["original"]), bytes.fromhex(item["replacement"]))
                applied.append(item)
            ai.verify(handle, product["patches"], "replacement")
            saved = dict(product, attached=True, pid=pid, base=module, allocation=allocation, details=info,
                         version=1, personal_saves_modified=False, native_menu=True, native_request_options=True,
                         native_variant=True, pending_prototype_saved_natively=True, gameplay_verified=False)
            REPORT.write_text(json.dumps(saved, indent=2)+"\n", encoding="utf-8"); return saved
        except Exception:
            for item in reversed(applied):
                rt.write_code(handle, item["address"], bytes.fromhex(item["replacement"]), bytes.fromhex(item["original"]))
            # Retain any published buffers until exit, even after rollback.
            if not applied: rt.K.VirtualFreeEx(handle, allocation, 0, 0x8000)
            raise
    finally:
        rt.K.CloseHandle(handle)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__); p.add_argument("command", choices=("attach",)); args = p.parse_args()
    try: print(json.dumps(attach()))
    except (OSError, ValueError) as error: print(json.dumps({"ok": False, "message": str(error)})); raise SystemExit(1)
