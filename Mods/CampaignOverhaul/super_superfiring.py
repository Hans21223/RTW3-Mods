"""Add extra raised turret positions and route them through RTW3's native raised-position check.

RTW3 stores raised/not-raised as a boolean, so Z is an additional raised mount
position, not a separately simulated third elevation layer.
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
ADAPTER_VERSION = 2
ADDED_POSITIONS = ("Z", "F", "G", "H", "I")
PATCH_LENGTH = 7  # movzx eax,[eax+8]; sub ax,0x42


def discover(blob, text_base):
    method = rt.method_address(blob, text_base, "IsSuperimposed")
    original = blob[method-text_base:method-text_base+PATCH_LENGTH]
    if original.hex() != "0fb740086683e8":
        raise ValueError("Unknown native turret-height check; no added raised positions installed.")
    return {"method": method, "original": original,
            "native_positions": ["B", "V", "X"], "added_positions": list(ADDED_POSITIONS),
            "height_model": "raised boolean; no third numeric elevation in the native turret record"}


def relative_jump(address, destination):
    return b"\xe9" + struct.pack("<i", destination-address-5)


def trampoline(address, original, resume):
    return original + relative_jump(address+len(original), resume)


def raised_position_thunk(address, passthrough):
    code = bytearray()
    raised_fixups = []
    for position in ADDED_POSITIONS:
        code.extend(b"\x66\x81\x78\x08" + struct.pack("<H", ord(position)))
        code.extend(b"\x0f\x84")
        raised_fixups.append(len(code))
        code.extend(b"\0"*4)
    code.extend(b"\xe9")
    code.extend(struct.pack("<i", passthrough-(address+len(code)+4)))
    raised = len(code)
    code.extend(bytes.fromhex("b801000000c3"))  # return true
    for fixup in raised_fixups:
        struct.pack_into("<i", code, fixup, raised-(fixup+4))
    return bytes(code)


def attach(wait=30):
    memory.configure()
    rt.configure_api()
    deadline = time.monotonic()+wait
    while True:
        games = [(pid,path) for pid,path in rt.process_candidates()
                 if path.resolve() == (rt.GAME/"RTW3.exe").resolve()]
        if len(games) == 1:
            break
        if time.monotonic() >= deadline:
            raise ValueError("Open this local RTW3 copy through Play with mods first.")
        time.sleep(0.5)
    pid,_ = games[0]
    handle = rt.K.OpenProcess(0x438, False, pid)
    if not handle:
        raise rt.win_error("Cannot open RTW3 for the super-superfiring turret patch")
    try:
        module,base,_ = live.unhooked_text(pid,handle)
        if REPORT.exists():
            prior = json.loads(REPORT.read_text(encoding="utf-8"))
            if (prior.get("adapter_version")==ADAPTER_VERSION and prior.get("attached")
                    and prior.get("pid")==pid and prior.get("base")==module
                    and rt.report_is_current(REPORT,pid)):
                ai_runtime.verify(handle,prior["patches"],"replacement")
                return prior
        _,text_base,blob = live.unhooked_text(pid,handle)
        info = discover(blob,text_base)
        layout = live.discover(blob,text_base)
        ai_runtime.require_title_screen(handle,layout)
        allocation = rt.K.VirtualAllocEx(handle,None,0x1000,0x3000,0x40)
        if not allocation:
            raise rt.win_error("Cannot allocate the raised-turret hook")
        allocation = int(allocation)
        item = None
        try:
            thunk_address = allocation+0x100
            trampoline_address = allocation+0x200
            thunk = raised_position_thunk(thunk_address,trampoline_address)
            original = info["original"]
            saved_trampoline = trampoline(trampoline_address,original,info["method"]+len(original))
            memory.write(handle,thunk_address,thunk)
            memory.write(handle,trampoline_address,saved_trampoline)
            rt.K.FlushInstructionCache(handle,thunk_address,len(thunk))
            rt.K.FlushInstructionCache(handle,trampoline_address,len(saved_trampoline))
            replacement = relative_jump(info["method"],thunk_address)+b"\x90"*(len(original)-5)
            item = patch("Treat added turret positions as superimposed",info["method"],original,replacement)
            ai_runtime.verify(handle,[item],"original")
            rt.write_code(handle,item["address"],bytes.fromhex(item["original"]),
                          bytes.fromhex(item["replacement"]))
            ai_runtime.verify(handle,[item],"replacement")
            saved = {"adapter":"super-superfiring-turret","adapter_version":ADAPTER_VERSION,
                     "attached":True,"pid":pid,"base":module,
                     "allocation":allocation,"patches":[item],"added_positions":list(ADDED_POSITIONS),
                     "existing_superimposed_positions":["B","V","X"],
                     "height_model":"The game treats each added position as raised, like B/V/X; there is no separate third-height field.",
                     "campaign_gameplay_verified":False}
            REPORT.write_text(json.dumps(saved,indent=2)+"\n",encoding="utf-8")
            return saved
        except Exception:
            if item is not None and rt.read(handle,item["address"],len(info["original"])) == bytes.fromhex(item["replacement"]):
                rt.write_code(handle,item["address"],bytes.fromhex(item["replacement"]),info["original"])
            rt.K.VirtualFreeEx(handle,allocation,0,0x8000)
            raise
    finally:
        rt.K.CloseHandle(handle)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command",choices=("attach",))
    args = parser.parse_args()
    try:
        print(json.dumps(attach()))
    except (OSError,ValueError,TypeError) as error:
        print(json.dumps({"ok":False,"message":str(error)}))
        raise SystemExit(1)
