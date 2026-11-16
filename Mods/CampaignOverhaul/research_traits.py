"""Stronger national research traits, without changing nation/save values.

Additive bonuses to positive per-area research effort before the original
random modifiers, era restrictions and progress limits. Both sides use the
same native DoResearch path. Attach only at the title screen.
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

REPORT = Path(__file__).with_name("research_traits_report.json")
DEFAULTS = dict(research_advantage_bonus_percent=50, technical_excellence_bonus_percent=25)
BOUNDS = dict(research_advantage_bonus_percent=(0,300), technical_excellence_bonus_percent=(0,200))
WINDOWS = (
    (0x76225c,32,"a06e1c9ef6bd70caff83cdf2deba2cd5a56be580e1985437da8d3e1418326d5d"),
    (0x762a8c,77,"3cf72266422a05068a4b8310586fba17920a0a830a9491f7d0056e94cd7479dd"),
    (0x762df1,109,"d64a5b4356c8906a32add11cc6028252b63e3958d8a1aa15e52aeb4bfb868c5b"),
    (0x7206f5,73,"da18ac308a7f9868edd12cadff14f5c1f8e87dd68500e326ae14d9622de68300"),
    (0x724f2a,83,"e1d67300fa19ac108926862873a776500c90ef7af8fd489cee2000613751bda5"),
    (0x720a64,23,"a5eea50cf278e4b9e8c9504ae9d3f3be8bc8f95667d32863eabb6a4df8243a8e"),
    (0x72551b,61,"46ec18de353ec246be7c02a2f7198f318e1810f280c8cff7bfab39037d045569"),
    (0x762d4a,69,"be04c3bd31e786539bc19be81d6030bb7538c6c60b1ea1929539a0fbe731497b"),
)


def discover(blob, base, settings=None):
    values = dict(DEFAULTS, **(settings or {}))
    if values.keys() != DEFAULTS.keys() or any(type(v) is not int or not BOUNDS[k][0] <= v <= BOUNDS[k][1] for k,v in values.items()):
        raise ValueError("Unsupported research-trait bonus settings.")
    normalized = audit.normalize(blob, base)
    for address,size,digest in WINDOWS:
        start = address-0x301000
        if hashlib.sha256(normalized[start:start+size]).hexdigest() != digest:
            raise ValueError("Research traits refuse changed native code at "+hex(address)+".")
    delta = base-0x301000
    if rt.method_address(blob,base,"DoResearch") != 0x76225c+delta:
        raise ValueError("Unsupported national research entry.")
    site = 0x762a8c+delta
    original = blob[site-base:site-base+8]
    if original.hex() != "8b45ac8b008945d8": raise ValueError("Research effort assignment changed.")
    return dict(settings=values,site=site,original=original.hex(),advantage_base=0x325,
                # 24 covers modern research's two new branches plus gun manufacture;
                # with the original 22-branch tree records 23-24 are never processed.
                research_area_stride=0x35,technical_excellence=0x1cb,max_area_index=24,
                effort_local=-0x28,raw_effort_pointer_local=-0x54,
                applies_to="player and AI nations with the corresponding native trait",
                native_random_bonuses_preserved=True,native_progress_limits_preserved=True,
                native_era_and_prerequisite_checks_preserved=True,
                national_trait_values_changed=False,global_research_speed_changed=False,
                ship_aircraft_and_other_trait_effects_changed=False)


def effort_thunk(address, state, info):
    c=Code(address)
    # Replay the original allocation load, then preserve its register/flag
    # results. Only the local effort value changes; priorities and allocation
    # pools are not written. Empty/negative effort must never create free work.
    c.emit(bytes.fromhex(info["original"])+b"\x9c\x60")
    c.emit(b"\x83\xfe"+bytes([info["max_area_index"]]));c.branch(b"\x0f\x87","done")
    c.emit(bytes.fromhex("8b45d885c0"));c.branch(b"\x0f\x8e","done")
    c.emit(b"\xb9");c.u32(100)
    c.emit(b"\x6b\xd6"+bytes([info["research_area_stride"]]))
    c.emit(b"\x80\xbc\x13");c.u32(info["advantage_base"]);c.emit(b"\x00")
    c.branch(b"\x0f\x84","technical")
    c.emit(b"\x81\xc1");c.u32(info["settings"]["research_advantage_bonus_percent"])
    c.mark("technical");c.emit(b"\x80\xbb");c.u32(info["technical_excellence"]);c.emit(b"\x00")
    c.branch(b"\x0f\x84","calculate")
    c.emit(b"\x81\xc1");c.u32(info["settings"]["technical_excellence_bonus_percent"])
    c.mark("calculate");c.emit(b"\x83\xf9\x64");c.branch(b"\x0f\x84","done")
    c.emit(bytes.fromhex("f7e9"))  # positive signed 64-bit EDX:EAX = effort * percent
    # Limit the positive quotient before DIV to avoid either integer wrap or
    # divide overflow. INT_MAX * 100 = 0x00000031ffffff9c.
    c.emit(b"\x83\xfa\x31");c.branch(b"\x0f\x87","saturate");c.branch(b"\x0f\x82","divide")
    c.emit(b"\x3d");c.u32(0xffffff9c);c.branch(b"\x0f\x87","saturate")
    c.mark("divide");c.emit(b"\xb9");c.u32(100);c.emit(bytes.fromhex("f7f1"));c.branch(b"\xe9","store")
    c.mark("saturate");c.emit(b"\xb8");c.u32(0x7fffffff)
    c.mark("store");c.emit(bytes.fromhex("8945d8ff05"));c.u32(state)
    c.mark("done");c.emit(b"\x61\x9d");c.branch(b"\xe9",info["site"]+8)
    return c.finish()


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
    if not handle:raise rt.win_error("Cannot open research-trait adapter")
    try:
        module,_=rt.module_info(pid)
        if REPORT.exists():
            saved=json.loads(REPORT.read_text())
            if saved.get("attached") and saved.get("pid")==pid and saved.get("base")==module and rt.report_is_current(REPORT,pid):
                ai.verify(handle,saved["patches"],"replacement");return saved
        base,blob=rt.text_section(handle,module);info=discover(blob,base,settings)
        layout=live.discover(blob,base);ai.require_title_screen(handle,layout)
        allocation=rt.K.VirtualAllocEx(handle,None,0x2000,0x3000,0x40)
        if not allocation:raise rt.win_error("Cannot allocate research-trait rules")
        state=allocation+0x1000;applied=False
        try:
            code=effort_thunk(allocation,state,info)
            if len(code)>0x1000:raise ValueError("Research-trait code exceeds its reserved area.")
            plan=patch("Stronger research advantages and TechnicalExcellence",info["site"],bytes.fromhex(info["original"]),
                       b"\xe9"+struct.pack("<i",allocation-info["site"]-5)+b"\x90"*3)
            ai.verify(handle,[plan],"original")
            memory.write(handle,allocation,code);rt.K.FlushInstructionCache(handle,allocation,len(code))
            rt.write_code(handle,plan["address"],bytes.fromhex(plan["original"]),bytes.fromhex(plan["replacement"]));applied=True
            ai.verify(handle,[plan],"replacement")
            saved=dict(attached=True,pid=pid,base=module,allocation=allocation,state=state,patches=[plan],
                       code_blocks=[dict(address=allocation,bytes=code.hex())],details=info,
                       personal_saves_modified=False,campaign_gameplay_verified=False)
            REPORT.write_text(json.dumps(saved,indent=2)+"\n");return saved
        except Exception:
            if applied:rt.write_code(handle,plan["address"],bytes.fromhex(plan["replacement"]),bytes.fromhex(plan["original"]))
            rt.K.VirtualFreeEx(handle,allocation,0,0x8000);raise
    finally:rt.K.CloseHandle(handle)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("command",choices=("attach",));p.add_argument("--settings",default="{}")
    a=p.parse_args()
    try:print(json.dumps(attach(settings=json.loads(a.settings))))
    except (ValueError,OSError,TypeError) as e:print(json.dumps(dict(ok=False,message=str(e))));raise SystemExit(1)
