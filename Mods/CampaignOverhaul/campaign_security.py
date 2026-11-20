"""Opt-in campaign security: paid counterintelligence, closed yards, no tech theft.

All changes are session-only, installed before a campaign is loaded. The native
Intel expense includes the added defensive spending, so the ordinary monthly
balance charges it exactly once. No save layout or disk executable is changed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import time
import weekly_runtime as rt
import modern_research as audit
from hull_rules import patch

REPORT = Path(__file__).with_name("campaign_security_report.json")
AUDITED = {
    "SpySuccess": (6664, "d69e1fee18e6d7d54780f66d224fc826f61dc3ea7a758a4acfcf83bf82fb0cf9"),
    "GetIntelCostForPlayerNation": (52, "b3d0419987bd7081bd15cc93ad5bf76934d80682516fc4a97f958a7b4885cd1f"),
    "CheckAIBuildingShipAbroad": (659, "45320d9433626270a819e1771812ee4963374eb2c4de05615ca88eb18d4bf7d5"),
    "LayDownAIShip": (615, "861c92f8a619f1b3babfee27be8c8cb2954d6b301a2a9912effede7efdda2124"),
    "GetModifiedBudget": (512, "4bf65a29f0e3b13eaa6c515eccce6c3572d66e2b91d1a96e596cdb613d7c7efa"),
}


class Code:
    def __init__(self, address):
        self.address, self.data, self.labels, self.fixups = address, bytearray(), {}, []

    def emit(self, data): self.data.extend(data)
    def u32(self, value): self.emit(struct.pack("<I", value))
    def mark(self, name): self.labels[name] = len(self.data)

    def branch(self, opcode, target):
        self.emit(opcode)
        if isinstance(target, str):
            self.fixups.append((len(self.data), target)); self.u32(0)
        else:
            self.emit(struct.pack("<i", target-self.address-len(self.data)-4))

    def finish(self):
        for offset, target in self.fixups:
            struct.pack_into("<i", self.data, offset, self.labels[target]-offset-4)
        return bytes(self.data)


def discover(blob, base):
    import live_cheats as live
    normalized = audit.normalize(blob, base)
    methods = {}
    for name, (size, digest) in AUDITED.items():
        address = rt.method_address(blob, base, name)
        start = address-base
        if hashlib.sha256(normalized[start:start+size]).hexdigest() != digest:
            raise ValueError("Campaign security refuses changed native code: "+name)
        methods[name] = address
    layout = live.discover(blob, base)
    spy, intel, yard = (methods[name] for name in (
        "SpySuccess", "GetIntelCostForPlayerNation", "CheckAIBuildingShipAbroad"))
    lay = methods["LayDownAIShip"]
    # Resolve the internal construction routine through its reviewed caller.
    call = lay+0xfd
    if blob[call-base] != 0xe8: raise ValueError("Unknown AI construction call.")
    build = call+5+struct.unpack_from("<i", blob, call-base+1)[0]
    if hashlib.sha256(normalized[build-base:build-base+2314]).hexdigest() != "5c3a57adeb851fb8eab7d4f964ba690de03b2dc21528bd4bb656ed98021e63bb":
        raise ValueError("Unknown native ship-order routine.")
    entry = blob[spy-base:spy-base+9]
    tail = blob[intel-base+46:intel-base+52]
    gate = blob[build-base+0xed:build-base+0xf6]
    if entry.hex() != "558bec51b926000000" or tail.hex() != "8bc75f5e5bc3" or gate.hex() != "8bf080bff832000002":
        raise ValueError("Unsupported security hook registers.")
    theft = spy+0x12e
    if blob[theft-base:theft-base+6].hex() != "0f82dd100000":
        raise ValueError("Unsupported espionage research dispatch.")
    # Delphi System.Random is resolved from a reviewed call in SpySuccess.
    rand_call = spy+0xa1
    if blob[rand_call-base] != 0xe8: raise ValueError("Unknown espionage random source.")
    random = rand_call+5+struct.unpack_from("<i", blob, rand_call-base+1)[0]
    return dict(methods=methods, main_slot=layout["main_slot"], player_field=layout["player_field"],
                spy=spy, spy_original=entry.hex(), random=random,
                intel=intel+46, intel_original=tail.hex(), budget=methods["GetModifiedBudget"],
                build=build+0xed, build_original=gate.hex(), build_cleanup=build+0xd5,
                static_patches=[
                    patch("No espionage gun/technology/progress theft", theft,
                          blob[theft-base:theft-base+6],
                          b"\x0f\x82"+struct.pack("<i", spy+0x196f-theft-6)),
                    patch("Skip player nation as an AI foreign yard", yard+0xca,
                          b"\x7e\x71", b"\xeb\x71")],
                default_budget_percent=0, maximum_budget_percent=10,
                block_chance_per_percent=8, charges="native Intel expense; annual naval budget * percent / 1200 per turn",
                technology_purchases_removed=False, existing_orders_removed=False)


def budget_thunk(address, state, info):
    c = Code(address)
    c.emit(b"\x9c\x52\x51\xc7\x05"); c.u32(state+4); c.u32(0)
    c.emit(b"\x8b\x0d"); c.u32(state)
    c.emit(b"\x83\xf9\x0a"); c.branch(b"\x0f\x87", "done")
    c.emit(b"\x85\xc9"); c.branch(b"\x0f\x84", "done")
    c.emit(b"\x8b\x86"); c.u32(info["player_field"])
    c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84", "done")
    c.emit(b"\x51"); c.branch(b"\xe8", info["budget"]); c.emit(b"\x59")
    c.emit(b"\x85\xc0"); c.branch(b"\x0f\x8e", "done")
    # 64-bit numerator avoids overflow at large cheat budgets.
    c.emit(b"\xf7\xe1\xb9"); c.u32(1200); c.emit(b"\xf7\xf1\xa3"); c.u32(state+4)
    c.emit(b"\x03\xf8")  # add edi,eax; original intelligence cost in EDI
    c.mark("done"); c.emit(b"\x59\x5a\x9d"+bytes.fromhex(info["intel_original"]))
    return c.finish()


def spy_thunk(address, state, info):
    c = Code(address); c.emit(b"\x9c\x60")
    # EDX = stealing/observing nation, ECX = target nation. Player is index 0.
    c.emit(b"\x85\xc9"); c.branch(b"\x0f\x85", "native")
    c.emit(b"\x83\xfa\x01"); c.branch(b"\x0f\x82", "native")
    c.emit(b"\x83\xfa\x08"); c.branch(b"\x0f\x87", "native")
    c.emit(b"\x8b\x0d"); c.u32(state)
    c.emit(b"\x85\xc9"); c.branch(b"\x0f\x84", "native")
    c.emit(b"\x83\xf9\x0a"); c.branch(b"\x0f\x87", "native")
    c.emit(b"\x6b\xc9\x08\x51\xb8"); c.u32(100)
    c.branch(b"\xe8", info["random"]); c.emit(b"\x59\x3b\xc1")
    c.branch(b"\x0f\x82", "blocked")
    c.mark("native"); c.emit(b"\x61\x9d"+bytes.fromhex(info["spy_original"]))
    c.branch(b"\xe9", info["spy"]+9)
    c.mark("blocked"); c.emit(b"\xff\x05"); c.u32(state+8)
    c.emit(b"\x61\x9d\xc3")
    return c.finish()


def yard_thunk(address, info):
    c = Code(address); c.emit(b"\x8b\xf0\x9c\x50")
    c.emit(b"\x8b\x45\xf4\x3b\x87"); c.u32(info["player_field"])
    c.branch(b"\x0f\x84", "native")
    c.emit(b"\x85\xf6"); c.branch(b"\x0f\x84", "native")
    c.emit(b"\x83\x7e\x1c\x00"); c.branch(b"\x0f\x85", "native")
    # Reject an AI order using an existing player-yard design too. Enter the
    # routine's existing early-abort cleanup before ship creation or payment.
    c.emit(b"\x58\x9d"); c.branch(b"\xe9", info["build_cleanup"])
    c.mark("native"); c.emit(b"\x58\x9d"+bytes.fromhex(info["build_original"])[2:])
    c.branch(b"\xe9", info["build"]+len(bytes.fromhex(info["build_original"])))
    return c.finish()


def attached_state(saved, handle):
    if not REPORT.exists(): return None
    current = json.loads(REPORT.read_text(encoding="utf-8"))
    if not current.get("attached") or any(current.get(key) != saved.get(key) for key in ("pid", "base")):
        return None
    import ai_runtime
    ai_runtime.verify(handle, current["patches"], "replacement")
    return current["state"]


def attach(wait=30):
    import ai_runtime
    import live_cheats as live
    import week_display as memory
    memory.configure()
    deadline = time.monotonic()+wait
    while True:
        games = [(pid, path) for pid, path in rt.process_candidates() if path == rt.GAME/"RTW3.exe"]
        if len(games) == 1: break
        if time.monotonic() >= deadline: raise ValueError("Open this local game with mods first.")
        time.sleep(.5)
    pid, _ = games[0]
    handle = rt.K.OpenProcess(0x438, False, pid)
    if not handle: raise rt.win_error("Cannot open campaign security engine")
    try:
        module, _ = rt.module_info(pid)
        if REPORT.exists():
            previous = json.loads(REPORT.read_text(encoding="utf-8"))
            if previous.get("attached") and previous.get("pid") == pid and previous.get("base") == module and rt.report_is_current(REPORT, pid):
                ai_runtime.verify(handle, previous["patches"], "replacement"); return previous
        base, blob = rt.text_section(handle, module)
        info = discover(blob, base)
        ai_runtime.require_title_screen(handle, info)
        allocation = rt.K.VirtualAllocEx(handle, None, 0x2000, 0x3000, 0x40)
        if not allocation: raise rt.win_error("Cannot allocate campaign security controls")
        state = allocation+0x1000
        plans = list(info["static_patches"])
        applied = []
        try:
            for offset, name, factory in ((0, "intel", budget_thunk), (0x400, "spy", spy_thunk), (0x800, "build", None)):
                target = allocation+offset
                code = factory(target, state, info) if factory else yard_thunk(target, info)
                if len(code) > 0x400: raise ValueError("Campaign security code exceeds its reserved area.")
                memory.write(handle, target, code); rt.K.FlushInstructionCache(handle, target, len(code))
                original = bytes.fromhex(info[name+"_original"])
                plans.append(patch("Campaign security: "+name, info[name], original,
                                   b"\xe9"+struct.pack("<i", target-info[name]-5)+b"\x90"*(len(original)-5)))
            ai_runtime.verify(handle, plans, "original")
            for plan in plans:
                rt.write_code(handle, plan["address"], bytes.fromhex(plan["original"]), bytes.fromhex(plan["replacement"]))
                applied.append(plan)
            ai_runtime.verify(handle, plans, "replacement")
            saved = dict(attached=True, pid=pid, base=module, allocation=allocation, state=state,
                         patches=plans, details=info, personal_saves_modified=False,
                         campaign_gameplay_verified=False)
            REPORT.write_text(json.dumps(saved, indent=2)+"\n", encoding="utf-8")
            return saved
        except Exception:
            for plan in reversed(applied):
                rt.write_code(handle, plan["address"], bytes.fromhex(plan["replacement"]), bytes.fromhex(plan["original"]))
            if not applied: rt.K.VirtualFreeEx(handle, allocation, 0, 0x8000)
            raise
    finally: rt.K.CloseHandle(handle)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("attach",))
    args = parser.parse_args()
    try: print(json.dumps(attach()))
    except (OSError, ValueError) as error:
        print(json.dumps({"ok": False, "message": str(error)})); raise SystemExit(1)
