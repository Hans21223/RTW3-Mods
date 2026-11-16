"""Research budget scaling: ahead-of-era projects stop stalling, money keeps mattering.

Three changes in the native DoResearch path, identical for player and AI:
setbacks cost one turn's gain instead of halving the project, effort above the
20%-of-cost turn limit still counts at a reduced rate, and the national point
total saturates instead of wrapping at extreme budgets. Attach at the title screen.
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

REPORT = Path(__file__).with_name("research_budget_report.json")
DEFAULTS = dict(overflow_percent=50, max_turn_progress_percent=60)
BOUNDS = dict(overflow_percent=(0,100), max_turn_progress_percent=(20,100))
# Points beyond this cannot raise any area past its ceiling; it also bounds the
# native round-robin distribution loop, which runs once per few points.
TOTAL_LIMIT = 20000000
WINDOWS = (
    (0x7627dc,39,"3a514e2609dd7b1f4cde879f6ca3eac589280d90e86c74b316ed87f0a1aadefc"),  # points*140*speed/100
    (0x762a7a,18,"d26d1b39e1604ba1f835ed3c1c1112cd20246ebac26da5a7d5990bb2a6099405"),  # [ebp-2c] = tech cost
    (0x762df1,46,"6358200577ecc19ddf5baa8d8aa599eae0bce466166d96c6b91adac47180f60b"),  # effort = min(effort, cost/5)
    (0x76310b,28,"74f6897e806f79dec5beb1af8e46d6a95518fe615a5ca3c18531ae8625fe7eda"),  # player setback halving
    (0x76333e,28,"74f6897e806f79dec5beb1af8e46d6a95518fe615a5ca3c18531ae8625fe7eda"),  # AI setback halving
    (0x76377c,73,"e867e267a813badcf6a6253bae3cb78344a9f2df7630d3669cb6809e44eabf38"),  # ahead-of-era 8% halving
    (0x7638e0,19,"efdbb011016df326d3c444f005efddb4cd0f4937656d69292c4e35e54acdcd12"),  # progress += effort
)
# Each halving is "progress = progress/2 + 1". Setbacks keep their messages and
# native effort reduction; only the accumulated project is no longer halved.
SETBACKS = (
    (0x76310b,28,b"\xeb\x1a","Player research setback keeps accumulated progress"),
    (0x76333e,28,b"\xeb\x1a","AI research setback keeps accumulated progress"),
    (0x7637a9,28,b"\xc7\x45\xd8\x00\x00\x00\x00\xeb\x13","Ahead-of-era setback loses one turn, not half the project"),
)


def discover(blob, base, settings=None):
    values = dict(DEFAULTS, **(settings or {}))
    if values.keys() != DEFAULTS.keys() or any(type(v) is not int or not BOUNDS[k][0] <= v <= BOUNDS[k][1] for k,v in values.items()):
        raise ValueError("Unsupported research budget settings.")
    normalized = audit.normalize(blob, base)
    for address,size,digest in WINDOWS:
        start = address-0x301000
        if hashlib.sha256(normalized[start:start+size]).hexdigest() != digest:
            raise ValueError("Research budget refuses changed native code at "+hex(address)+".")
    delta = base-0x301000
    if rt.method_address(blob,base,"DoResearch") != 0x76225c+delta:
        raise ValueError("Unsupported national research entry.")
    def raw(address,size): return blob[address-0x301000:address-0x301000+size]
    static = [patch(label,address+delta,raw(address,size),code.ljust(size,b"\x90")) for address,size,code,label in SETBACKS]
    return dict(settings=values,static_patches=static,
                total_site=0x7627dc+delta,total_original=raw(0x7627dc,7).hex(),total_exit=0x762803+delta,
                speed=struct.unpack("<I",raw(0x7627e5,4))[0],total_limit=TOTAL_LIMIT,
                cap_site=0x762df1+delta,cap_original=raw(0x762df1,8).hex(),cap_exit=0x762e1f+delta,
                cost_local=-0x2c,effort_local=-0x28,points_local=-0x24,
                applies_to="player and AI nations",native_era_penalties_preserved=True,
                native_completion_hold_preserved=True,setback_messages_preserved=True,
                research_speed_setting_changed=False,save_values_changed=False)


def total_thunk(address, state, info):
    # Native: points*140*ResearchSpeed in 32 bits, then /100. Do it in 80-bit
    # precision (exact here) and saturate, so a huge budget cannot wrap negative.
    c=Code(address);c.emit(b"\x9c\x60\xdb\x45\xdc\x68");c.u32(140);c.emit(b"\xda\x0c\x24\x58")
    c.emit(b"\xda\x0d");c.u32(info["speed"])
    c.emit(b"\x68");c.u32(100);c.emit(b"\xda\x34\x24\x58")
    c.emit(b"\x68");c.u32(info["total_limit"]);c.emit(b"\xda\x14\x24\xdf\xe0\x9e")
    c.branch(b"\x0f\x86","round")
    c.emit(b"\xdd\xd8\xdb\x04\x24\xff\x05");c.u32(state+4)
    c.mark("round");c.emit(b"\x58\x83\xec\x08\xdf\x3c\x24\x9b\x58\x5a\x89\x45\xdc\x61\x9d")
    c.branch(b"\xe9",info["total_exit"]);return c.finish()


def cap_thunk(address, state, info):
    # cap = native cost/5. Effort above it counts at overflow_percent, up to
    # max_turn_progress_percent of cost. 20% or 0% reproduces the native clamp.
    c=Code(address);c.emit(bytes.fromhex("9c608b4dd48bc1ba67666666f7ead1fa8bdac1eb1f03da8b75d83bde"))
    c.branch(b"\x0f\x8d","done");c.emit(b"\x85\xdb");c.branch(b"\x0f\x8e","clamp")
    c.emit(b"\x8b\xc1\xba");c.u32(info["settings"]["max_turn_progress_percent"])
    c.emit(b"\xf7\xe2\xbf");c.u32(100);c.emit(b"\xf7\xf7\x2b\xc3");c.branch(b"\x0f\x8e","clamp")
    c.emit(b"\x8b\xc8\x8b\xc6\x2b\xc3\xba");c.u32(info["settings"]["overflow_percent"])
    c.emit(b"\xf7\xe2\xf7\xf7\x3b\xc1");c.branch(b"\x0f\x86","add");c.emit(b"\x8b\xc1")
    c.mark("add");c.emit(b"\x03\xc3\x89\x45\xd8\xff\x05");c.u32(state);c.branch(b"\xe9","done")
    c.mark("clamp");c.emit(b"\x89\x5d\xd8")
    c.mark("done");c.emit(b"\x61\x9d");c.branch(b"\xe9",info["cap_exit"]);return c.finish()


def attach(wait=30, settings=None):
    import ai_runtime as ai
    import live_cheats as live
    import week_display as memory
    ai.checked_game();memory.configure();deadline=time.monotonic()+wait
    while True:
        games=[g for g in rt.process_candidates() if g[1]==rt.GAME/"RTW3.exe"]
        if len(games)==1:break
        if time.monotonic()>=deadline:raise ValueError("Start this local game with mods first.")
        time.sleep(.5)
    pid,_=games[0];handle=rt.K.OpenProcess(0x438,False,pid)
    if not handle:raise rt.win_error("Cannot open research budget adapter")
    try:
        module,_=rt.module_info(pid)
        if REPORT.exists():
            saved=json.loads(REPORT.read_text())
            if saved.get("attached") and saved.get("pid")==pid and saved.get("base")==module and rt.report_is_current(REPORT,pid):
                ai.verify(handle,saved["patches"],"replacement");return saved
        base,blob=rt.text_section(handle,module);info=discover(blob,base,settings)
        layout=live.discover(blob,base);ai.require_title_screen(handle,layout)
        allocation=rt.K.VirtualAllocEx(handle,None,0x2000,0x3000,0x40)
        if not allocation:raise rt.win_error("Cannot allocate research budget rules")
        state=allocation+0x1000;plans=list(info["static_patches"]);blocks=[];applied=[]
        try:
            for offset,make,site,original in ((0,total_thunk,info["total_site"],info["total_original"]),
                                              (0x400,cap_thunk,info["cap_site"],info["cap_original"])):
                code=make(allocation+offset,state,info)
                if len(code)>0x400:raise ValueError("Research budget code exceeds its reserved area.")
                memory.write(handle,allocation+offset,code);rt.K.FlushInstructionCache(handle,allocation+offset,len(code))
                blocks.append(dict(address=allocation+offset,bytes=code.hex()))
                size=len(bytes.fromhex(original))
                plans.append(patch("Research budget scaling",site,bytes.fromhex(original),
                                   b"\xe9"+struct.pack("<i",allocation+offset-site-5)+b"\x90"*(size-5)))
            ai.verify(handle,plans,"original")
            for p in plans:
                rt.write_code(handle,p["address"],bytes.fromhex(p["original"]),bytes.fromhex(p["replacement"]));applied.append(p)
            ai.verify(handle,plans,"replacement")
            saved=dict(attached=True,pid=pid,base=module,allocation=allocation,state=state,patches=plans,
                       code_blocks=blocks,details=info,personal_saves_modified=False,campaign_gameplay_verified=False)
            REPORT.write_text(json.dumps(saved,indent=2)+"\n");return saved
        except Exception:
            for p in reversed(applied):rt.write_code(handle,p["address"],bytes.fromhex(p["replacement"]),bytes.fromhex(p["original"]))
            rt.K.VirtualFreeEx(handle,allocation,0,0x8000);raise
    finally:rt.K.CloseHandle(handle)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("command",choices=("attach",));p.add_argument("--settings",default="{}")
    a=p.parse_args()
    try:print(json.dumps(attach(settings=json.loads(a.settings))))
    except (ValueError,OSError,TypeError) as e:print(json.dumps(dict(ok=False,message=str(e))));raise SystemExit(1)
