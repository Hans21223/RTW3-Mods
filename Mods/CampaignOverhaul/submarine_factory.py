"""Native submarine class factory hook; used only during a player build dialog.

UI is loaded separately into the authenticated game's process. This adapter
changes no executable on disk and never opens or writes a personal save file.
"""
import hashlib
import json
from pathlib import Path
import re
import struct
import time
import weekly_runtime as rt
import week_display as memory
import live_cheats as live
from hull_rules import patch,unique

REPORT=Path(__file__).with_name("in_game_submarine_report.json")


def discover(blob,base):
    # Reuse read-only discovery of the campaign object and selected year. The
    # caller reconstructs an existing idle hook only in its local code copy.
    layout=live.discover(blob,base)
    constructor=rt.method_address(blob,base,"StartBuildingSubmarine")
    body=blob[constructor-base:constructor-base+0x100]
    epilogue=b"\x8b\xc3\x5f\x5e\x5b\x5d\xc2\x04\x00"
    end=unique(body,epilogue,"submarine constructor return")
    for expected in (b"\x8b\xf2",b"\x88\x5f\x10",b"\x89\x47\x08",b"\x89\x47\x0c",b"\x89\x47\x15"):
        if expected not in body:raise ValueError("Unsupported native submarine construction fields.")
    # Append the selected class label using the game's own UnicodeString helper,
    # not a foreign heap allocation. Two native comma-append calls must agree.
    surprise=rt.method_address(blob,base,"DoSubSurprise")-base
    appenders=[]
    for match in re.finditer(rb"\x8d\x45[\xf4\xf8]\xba(.{4})\xe8(.{4})",blob[surprise:surprise+0x300],re.DOTALL):
        pointer,=struct.unpack("<I",match.group(1));off=pointer-base
        if 4<=off<len(blob)-6 and blob[off:off+6]==", ".encode("utf-16-le")+b"\0\0" and struct.unpack_from("<I",blob,off-4)[0]==2:
            call=base+surprise+match.start()+8
            appenders.append(call+5+struct.unpack("<i",match.group(2))[0])
    if len(appenders)!=2 or len(set(appenders))!=1:raise ValueError("Cannot verify native Unicode class-label append.")
    click=rt.method_address(blob,base,"btbnBuildSubClick")
    click_body=blob[click-base:click-base+0x140]
    if b"\x8b\xd8" not in click_body[:0x20] or b"\x8b\x83"+struct.pack("<I",layout["player_field"]) not in click_body:
        raise ValueError("Cannot verify the native Build sub command.")
    return {"main_slot":layout["main_slot"],"player_field":layout["player_field"],"year_slot":layout["year_slot"],
            "constructor":constructor,"return_site":constructor+end,"return_original":epilogue.hex(),
            "append":appenders[0],"build_click":click,"design_click":rt.method_address(blob,base,"btbnDesignClick")}


def factory_thunk(address,active_slot,layout):
    code=bytearray(b"\x9c\x60");labels={};fix=[]
    def mark(n):labels[n]=len(code)
    def jump(op,n):code.extend(op);fix.append((len(code),n));code.extend(b"\0"*4)
    def abs32(op,p):code.extend(op+struct.pack("<I",p))
    abs32(b"\x8b\x3d",active_slot);code.extend(b"\x85\xff");jump(b"\x0f\x84","done")
    abs32(b"\xa1",layout["main_slot"]);code.extend(b"\x85\xc0");jump(b"\x0f\x84","done")
    code.extend(b"\x3b\x07");jump(b"\x0f\x85","done")
    code.extend(b"\x8b\x80"+struct.pack("<I",layout["player_field"])+b"\x3b\xf0");jump(b"\x0f\x85","done")
    code.extend(b"\x3b\x47\x04");jump(b"\x0f\x85","done")
    code.extend(b"\x0f\xb6\x43\x10\x3b\x47\x08");jump(b"\x0f\x85","done")
    abs32(b"\xa1",layout["year_slot"]);code.extend(b"\x85\xc0");jump(b"\x0f\x84","done")
    code.extend(b"\x8b\x00\x3b\x47\x0c");jump(b"\x0f\x8c","done")
    code.extend(b"\x8b\x47\x10\x83\xf8\x28");jump(b"\x0f\x8c","done")
    code.extend(b"\x3d\x82\x00\x00\x00");jump(b"\x0f\x8f","done")
    code.extend(b"\x8b\x57\x14\x83\xfa\xfe");jump(b"\x0f\x8c","done")
    code.extend(b"\x83\xfa\x01");jump(b"\x0f\x8f","done")
    code.extend(b"\x89\x43\x08\x89\x53\x0c")
    # Native construction cadence and costs remain unchanged. Prototype speed,
    # displacement and weapon layouts are not written into unrelated fields.
    code.extend(b"\x8b\x57\x18\x85\xd2");jump(b"\x0f\x84","count")
    code.extend(b"\x8d\x43\x04\xe8");code.extend(struct.pack("<i",layout["append"]-(address+len(code)+4)))
    mark("count");abs32(b"\xff\x05",active_slot+4);abs32(b"\x89\x1d",active_slot+8)
    mark("done");code.extend(b"\x61\x9d"+bytes.fromhex(layout["return_original"]))
    for off,name in fix:struct.pack_into("<i",code,off,labels[name]-off-4)
    return bytes(code)


def build_thunk(address,layout):
    code=b"\x55\x8b\xec\x9c\x60\xa1"+struct.pack("<I",layout["main_slot"])+b"\x31\xd2\xe8"
    code+=struct.pack("<i",layout["build_click"]-(address+len(code)+4))
    return code+b"\x61\x9d\x5d\xc3"


def request_thunk(address,queue,active_slot,layout):
    """Run the native modal build handler once on its own UI thread.

    queue: state (0 idle,1 pending,2 complete,3 running,4 stale), packet,
    count-before, count-after. Re-entrant native idle calls see state 3.
    """
    code=bytearray(b"\x9c\x60"); labels={}; fix=[]
    def mark(n):labels[n]=len(code)
    def jump(op,n):code.extend(op);fix.append((len(code),n));code.extend(b"\0"*4)
    def abs32(op,p):code.extend(op+struct.pack("<I",p))
    if "design_click" in layout:
        abs32(b"\x83\x3d",queue+0x40);code.extend(b"\x01");jump(b"\x0f\x85","build")
        abs32(b"\xa1",layout["main_slot"]);code.extend(b"\x85\xc0");jump(b"\x0f\x84","design_fail")
        abs32(b"\x3b\x05",queue+0x44);jump(b"\x0f\x85","design_fail")
        code.extend(b"\x8b\x90"+struct.pack("<I",layout["player_field"])+b"\x85\xd2");jump(b"\x0f\x84","design_fail")
        abs32(b"\x3b\x15",queue+0x48);jump(b"\x0f\x85","design_fail")
        abs32(b"\xc7\x05",queue+0x40);code.extend(struct.pack("<I",3))
        code.extend(b"\x31\xd2\xe8");code.extend(struct.pack("<i",layout["design_click"]-(address+len(code)+4)))
        abs32(b"\xc7\x05",queue+0x40);code.extend(struct.pack("<I",2));jump(b"\xe9","build")
        mark("design_fail");abs32(b"\xc7\x05",queue+0x40);code.extend(struct.pack("<I",4))
        mark("build")
    abs32(b"\x83\x3d",queue);code.extend(b"\x01");jump(b"\x0f\x85","done")
    abs32(b"\x8b\x3d",queue+4);code.extend(b"\x85\xff");jump(b"\x0f\x84","fail")
    abs32(b"\xa1",layout["main_slot"]);code.extend(b"\x85\xc0");jump(b"\x0f\x84","fail")
    code.extend(b"\x3b\x07");jump(b"\x0f\x85","fail")
    code.extend(b"\x8b\x90"+struct.pack("<I",layout["player_field"])+b"\x85\xd2");jump(b"\x0f\x84","fail")
    code.extend(b"\x3b\x57\x04");jump(b"\x0f\x85","fail")
    abs32(b"\xc7\x05",queue);code.extend(struct.pack("<I",3))
    abs32(b"\x89\x3d",active_slot)
    abs32(b"\x8b\x15",active_slot+4);abs32(b"\x89\x15",queue+8)
    code.extend(b"\x31\xd2\xe8");code.extend(struct.pack("<i",layout["build_click"]-(address+len(code)+4)))
    abs32(b"\xc7\x05",active_slot);code.extend(b"\0"*4)
    abs32(b"\xa1",active_slot+4);abs32(b"\xa3",queue+12)
    abs32(b"\xc7\x05",queue);code.extend(struct.pack("<I",2));jump(b"\xe9","done")
    mark("fail");abs32(b"\xc7\x05",queue);code.extend(struct.pack("<I",4))
    mark("done");code.extend(b"\x61\x9d\xc3")
    for off,name in fix:struct.pack_into("<i",code,off,labels[name]-off-4)
    return bytes(code)


def attach(pid):
    memory.configure()
    if dict(rt.process_candidates()).get(pid)!=rt.GAME/"RTW3.exe":raise ValueError("Choose the local authenticated game.")
    dispatcher=live.attach()
    if dispatcher["pid"]!=pid or dispatcher.get("dispatcher_version") not in (1,2):raise ValueError("Close and restart RTW3 to update its native dispatcher.")
    handle=rt.K.OpenProcess(0x438,False,pid)
    if not handle:raise rt.win_error("Cannot inspect submarine construction")
    try:
        module,base,blob=live.unhooked_text(pid,handle)
        if REPORT.exists():
            prior=json.loads(REPORT.read_text(encoding="utf-8"))
            if prior.get("pid")==pid and prior.get("base")==module and prior.get("attached") and rt.report_is_current(REPORT,pid):
                item=prior["patch"]
                if rt.read(handle,item["address"],9).hex()!=item["replacement"]:raise ValueError("Submarine construction hook changed.")
                return prior
        layout=discover(blob,base)
        allocation=rt.K.VirtualAllocEx(handle,None,4096,0x3000,0x40)
        if not allocation:raise rt.win_error("Cannot allocate submarine construction bridge")
        active_slot=allocation+0x800
        code=factory_thunk(allocation,active_slot,layout)
        queue=allocation+0x900
        dialog=request_thunk(allocation+0x400,queue,active_slot,layout)
        item=patch("Player submarine class factory",layout["return_site"],bytes.fromhex(layout["return_original"]),
                   b"\xe9"+struct.pack("<i",allocation-layout["return_site"]-5)+b"\x90"*4)
        installed=False
        try:
            memory.write(handle,allocation,code);memory.write(handle,allocation+0x400,dialog)
            rt.K.FlushInstructionCache(handle,allocation,0x700)
            rt.write_code(handle,item["address"],bytes.fromhex(item["original"]),bytes.fromhex(item["replacement"]));installed=True
            memory.write(handle,dispatcher["mailbox"]+0x700,struct.pack("<I",allocation+0x400))
            saved={"pid":pid,"base":module,"allocation":allocation,"active_slot":active_slot,"queue":queue,"dispatcher_slot":dispatcher["mailbox"]+0x700,
                   "layout":layout,"patch":item,"attached":True,"personal_saves_modified":False,"native_ui_gameplay_verified":False}
            REPORT.write_text(json.dumps(saved,indent=2)+"\n",encoding="utf-8");return saved
        except Exception:
            memory.write(handle,dispatcher["mailbox"]+0x700,b"\0"*4)
            if installed:rt.write_code(handle,item["address"],bytes.fromhex(item["replacement"]),bytes.fromhex(item["original"]))
            else:rt.K.VirtualFreeEx(handle,allocation,0,0x8000)
            raise
    finally:rt.K.CloseHandle(handle)


def session(pid):
    memory.configure();saved=json.loads(REPORT.read_text(encoding="utf-8"))
    if not saved.get("attached") or saved.get("pid")!=pid or not rt.report_is_current(REPORT,pid) or dict(rt.process_candidates()).get(pid)!=rt.GAME/"RTW3.exe":
        raise ValueError("Restart with In-game Submarine Designer enabled.")
    if rt.module_info(pid)[0]!=saved["base"]:raise ValueError("Game session changed.")
    handle=rt.K.OpenProcess(0x438,False,pid)
    if not handle:raise rt.win_error("Cannot open submarine bridge")
    item=saved["patch"]
    if rt.read(handle,item["address"],9).hex()!=item["replacement"]:
        rt.K.CloseHandle(handle);raise ValueError("Submarine bridge changed. Restart the game.")
    return saved,handle


def prepare(pid,ident,revision):
    import submarine_designs as designs
    stored=designs.read_library()["blueprints"].get(ident)
    if not stored or stored["revision"]!=revision:raise ValueError("Save and reload the selected submarine class first.")
    result=designs.evaluate(stored["design"])
    if not result["valid"]:raise ValueError("The class is over allocation.")
    saved,handle=session(pid)
    try:
        layout=saved["layout"];main=live.integer(handle,layout["main_slot"])&0xffffffff
        player=(live.integer(handle,main+layout["player_field"])&0xffffffff) if main else 0
        if not player:raise ValueError("Load a campaign before ordering submarines.")
        year_ptr=live.integer(handle,layout["year_slot"])&0xffffffff
        if not year_ptr or live.integer(handle,year_ptr)<stored["design"]["year"]:raise ValueError("Class design year is later than the active campaign.")
        allocation=rt.K.VirtualAllocEx(handle,None,4096,0x3000,0x04)
        if not allocation:raise rt.win_error("Cannot prepare an immutable submarine class")
        suffix=" ("+stored["design"]["name"]+")"
        # Static Delphi UnicodeString: owned and retained for this game session.
        payload=struct.pack("<7I",main,player,result["native"]["type"],stored["design"]["year"],
                            result["native"]["availability"],result["native"]["accuracy"]&0xffffffff,allocation+0x10c)
        memory.write(handle,allocation,payload)
        encoded=suffix.encode("utf-16-le")
        memory.write(handle,allocation+0x100,struct.pack("<HHiI",1200,2,-1,len(encoded)//2)+encoded+b"\0\0")
        return {"ok":True,"packet":allocation,"pid":pid,"role":stored["design"]["role"],"class_name":stored["design"]["name"],
                "message":"Choose the matching native role. Native construction costs and research gates remain unchanged."}
    finally:rt.K.CloseHandle(handle)


def detach(pid):
    saved,handle=session(pid)
    try:
        if live.integer(handle,saved["active_slot"])!=0 or live.integer(handle,saved["queue"]) in (1,3):raise ValueError("Close the native submarine build dialog before detaching.")
        memory.write(handle,saved["dispatcher_slot"],b"\0"*4)
        item=saved["patch"];rt.write_code(handle,item["address"],bytes.fromhex(item["replacement"]),bytes.fromhex(item["original"]))
        saved["attached"]=False;REPORT.write_text(json.dumps(saved,indent=2)+"\n",encoding="utf-8");return saved
    finally:rt.K.CloseHandle(handle)
