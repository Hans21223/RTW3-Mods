"""Load the reviewed x86 designer module into the local authenticated RTW3.

Uses Windows' CLR hosting interface. Does not replace a Steam DLL, bypass a
license check, modify the disk executable, or edit campaign files.
"""
import argparse
import ctypes as c
from ctypes import wintypes as w
import hashlib
import json
from pathlib import Path
import struct
import time
import uuid
import weekly_runtime as rt
import week_display as memory
import submarine_factory as factory

HERE=Path(__file__).resolve().parent
ASSEMBLY=rt.GAME/"Mods/Manager/RTW3.SubmarineDesigner.dll"
CONFIG=HERE/"in_game_submarines_session.json"
REPORT=HERE/"in_game_submarines_ui.json"


def modules(pid):
    snapshot=rt.K.CreateToolhelp32Snapshot(0x18,pid)
    if snapshot==c.c_void_p(-1).value:raise rt.win_error("Cannot inspect native modules")
    try:
        entry=rt.MODULEENTRY32();entry.dwSize=c.sizeof(entry)
        more=rt.K.Module32FirstW(snapshot,c.byref(entry));result={}
        while more:
            result[entry.szModule.lower()]=(entry.modBaseAddr,entry.modBaseSize)
            more=rt.K.Module32NextW(snapshot,c.byref(entry))
        return result
    finally:rt.K.CloseHandle(snapshot)


def export(handle,loaded,module,name,depth=0):
    if depth>6:raise ValueError("Native export forwarding loop.")
    if not module.lower().endswith(".dll"):module+=".dll"
    if module.lower() not in loaded:raise ValueError("Required native module is not loaded: "+module)
    base,size=loaded[module.lower()];header=rt.read(handle,base,4096)
    pe=struct.unpack_from("<I",header,0x3c)[0]
    if header[:2]!=b"MZ" or header[pe:pe+4]!=b"PE\0\0" or struct.unpack_from("<H",header,pe+24)[0]!=0x10b:
        raise ValueError("The in-game designer requires a 32-bit native host.")
    rva,length=struct.unpack_from("<II",header,pe+24+96)
    directory=rt.read(handle,base+rva,40)
    ordinal_base,count,names,functions,name_table,ordinals=struct.unpack_from("<6I",directory,16)
    if not 0<names<=count<100000:raise ValueError("Unsupported export table.")
    if name.startswith("#"):index=int(name[1:])-ordinal_base
    else:
        addresses=struct.unpack("<"+"I"*names,rt.read(handle,base+name_table,names*4))
        index=None
        for n,pointer in enumerate(addresses):
            if rt.read(handle,base+pointer,min(256,size-pointer)).split(b"\0",1)[0].decode("ascii")==name:
                index=struct.unpack("<H",rt.read(handle,base+ordinals+n*2,2))[0];break
        if index is None:raise ValueError("Native export was not found: "+name)
    if not 0<=index<count:raise ValueError("Invalid export ordinal.")
    target=struct.unpack("<I",rt.read(handle,base+functions+index*4,4))[0]
    if rva<=target<rva+length:
        forward=rt.read(handle,base+target,min(256,size-target)).split(b"\0",1)[0].decode("ascii")
        next_module,next_name=forward.rsplit(".",1)
        return export(handle,loaded,next_module,next_name,depth+1)
    if not 0<target<size:raise ValueError("Export is outside its native module.")
    return base+target


def configure():
    memory.configure()
    rt.K.CreateRemoteThread.argtypes=[w.HANDLE,c.c_void_p,c.c_size_t,c.c_void_p,c.c_void_p,w.DWORD,c.POINTER(w.DWORD)]
    rt.K.CreateRemoteThread.restype=w.HANDLE
    rt.K.WaitForSingleObject.argtypes=[w.HANDLE,w.DWORD];rt.K.WaitForSingleObject.restype=w.DWORD
    rt.K.GetExitCodeThread.argtypes=[w.HANDLE,c.POINTER(w.DWORD)];rt.K.GetExitCodeThread.restype=w.BOOL


def invoke(handle,function,argument,timeout=30000):
    thread=rt.K.CreateRemoteThread(handle,None,0,function,argument,0,None)
    if not thread:raise rt.win_error("Cannot start the reviewed native module")
    try:
        if rt.K.WaitForSingleObject(thread,timeout)!=0:
            # Never reclaim a buffer that a still-running remote thread may use.
            raise ValueError("The native module is still starting. Close RTW3 before retrying; no campaign was edited.")
        code=w.DWORD()
        if not rt.K.GetExitCodeThread(thread,c.byref(code)):raise rt.win_error("Cannot read module startup result")
        return code.value
    finally:rt.K.CloseHandle(thread)


def bootstrap(address,data,create):
    """stdcall thread entry; ICLRMetaHost -> v4 -> ICLRRuntimeHost."""
    code=bytearray(b"\x55\x8b\xec\x53\x56\x57");fail=[]
    def imm(op,value):code.extend(op+struct.pack("<I",value))
    def push(value):imm(b"\x68",value)
    def phase(n):imm(b"\xc7\x05",data["status"]);code.extend(struct.pack("<I",n))
    def check():
        imm(b"\xa3",data["status"]+4);code.extend(b"\x85\xc0\x0f\x88");fail.append(len(code));code.extend(b"\0"*4)
    def com(slot,offset,args):
        imm(b"\x8b\x0d",slot);code.extend(b"\x8b\x01")
        for arg in reversed(args):push(arg)
        code.extend(b"\x51\xff\x50"+bytes([offset]));check()
    phase(1)
    for arg in (data["meta"],data["iid_meta"],data["clsid_meta"]):push(arg)
    imm(b"\xb8",create);code.extend(b"\xff\xd0");check()
    phase(2);com(data["meta"],12,[data["version"],data["iid_info"],data["info"]])
    phase(3);com(data["info"],36,[data["clsid_host"],data["iid_host"],data["host"]])
    phase(4);com(data["host"],12,[])
    phase(5);com(data["host"],44,[data["assembly"],data["type"],data["method"],data["argument"],data["result"]])
    phase(6);code.extend(b"\x31\xc0")
    end=len(code);code.extend(b"\x5f\x5e\x5b\x5d\xc2\x04\x00")
    for off in fail:struct.pack_into("<i",code,off,end-off-4)
    return bytes(code)


def host(pid,config):
    configure()
    handle=rt.K.OpenProcess(0x43a,False,pid)
    if not handle:raise rt.win_error("Cannot load the in-game designer")
    try:
        loaded=modules(pid)
        allocation=rt.K.VirtualAllocEx(handle,None,16384,0x3000,0x40)
        if not allocation:raise rt.win_error("Cannot allocate CLR startup data")
        # Retain this small startup buffer until game exit; timeout paths may
        # still execute it, and default-AppDomain assemblies cannot be unloaded.
        if "mscoree.dll" not in loaded:
            memory.write(handle,allocation+0x1000,"C:\\Windows\\SysWOW64\\mscoree.dll\0".encode("utf-16-le"))
            if not invoke(handle,export(handle,loaded,"kernel32.dll","LoadLibraryW"),allocation+0x1000):
                raise ValueError("The Windows .NET Framework host did not load.")
            loaded=modules(pid)
        data={"status":allocation+0x800,"meta":allocation+0x810,"info":allocation+0x814,"host":allocation+0x818,"result":allocation+0x81c}
        cursor=0x1000
        values={
            "clsid_meta":uuid.UUID("9280188d-0e8e-4867-b30c-7fa83884e8de").bytes_le,
            "iid_meta":uuid.UUID("d332db9e-b9b3-4125-8207-a14884f53216").bytes_le,
            "iid_info":uuid.UUID("bd39d1d2-ba2f-486a-89b0-b4b0cb466891").bytes_le,
            "clsid_host":uuid.UUID("90f1a06e-7712-4762-86b5-7a5eba6bdb02").bytes_le,
            "iid_host":uuid.UUID("90f1a06c-7712-4762-86b5-7a5eba6bdb02").bytes_le,
            "version":"v4.0.30319","assembly":str(ASSEMBLY),"type":"RTW3.Mods.NativeSubmarineEntry","method":"Load","argument":str(config)}
        for name,value in values.items():
            value=(value+"\0").encode("utf-16-le") if isinstance(value,str) else value
            data[name]=allocation+cursor;memory.write(handle,allocation+cursor,value);cursor+=(len(value)+3)&~3
        code=bootstrap(allocation,data,export(handle,loaded,"mscoree.dll","CLRCreateInstance"))
        memory.write(handle,allocation,code);rt.K.FlushInstructionCache(handle,allocation,len(code))
        exit_code=invoke(handle,allocation,0)
        phase,hresult=struct.unpack("<II",rt.read(handle,data["status"],8))
        result=struct.unpack("<I",rt.read(handle,data["result"],4))[0]
        if exit_code or phase!=6 or result:
            raise ValueError(f"In-game module startup stopped at phase {phase}, HRESULT {hresult:#x}, module result {result:#x}.")
        return {"phase":phase,"hresult":hresult,"module_result":result}
    finally:rt.K.CloseHandle(handle)


def attach(pid=None,self_test=False):
    configure()
    games=[p for p,path in rt.process_candidates() if path==rt.GAME/"RTW3.exe"]
    if len(games)!=1 or (pid is not None and pid!=games[0]):raise ValueError("Start one local RTW3 instance first.")
    pid=games[0]
    raw=ASSEMBLY.read_bytes();pe=struct.unpack_from("<I",raw,0x3c)[0]
    if raw[:2]!=b"MZ" or struct.unpack_from("<H",raw,pe+4)[0]!=0x14c:raise ValueError("Build the x86 submarine module first.")
    if REPORT.exists():
        old=json.loads(REPORT.read_text(encoding="utf-8"))
        if old.get("pid")==pid and old.get("base")==rt.module_info(pid)[0] and rt.report_is_current(REPORT,pid):
            raise ValueError("The submarine UI is already loaded. Close RTW3 before replacing or reloading the module.")
    bridge=factory.attach(pid)
    import native_designer
    designer=native_designer.attach(pid)
    config={"game":str(rt.GAME),"pid":pid,"base":bridge["base"],"queue":bridge["queue"],"main_slot":bridge["layout"]["main_slot"],
            "player_field":bridge["layout"]["player_field"],"nonce":uuid.uuid4().hex,"report":str(REPORT),"self_test":self_test,
            "assembly_sha256":hashlib.sha256(raw).hexdigest(),"native_designer":designer}
    CONFIG.write_text(json.dumps(config,indent=2)+"\n",encoding="utf-8")
    result=host(pid,CONFIG)
    deadline=time.monotonic()+25
    while time.monotonic()<deadline:
        if REPORT.exists():
            try:
                state=json.loads(REPORT.read_text(encoding="utf-8"))
                if state.get("nonce")==config["nonce"]:
                    if state.get("error"):raise ValueError(state["error"])
                    if state.get("ready") and (not self_test or state.get("self_test_complete")):
                        return {"ok":True,"message":"Native Ship design extension loaded. Choose SS - Submarine class in Ship type, or press F11 in a loaded campaign.","hosting":result,"ui":{k:v for k,v in state.items() if k!="native_designer"}}
            except json.JSONDecodeError:pass
        time.sleep(0.1)
    raise ValueError("The game module loaded but did not confirm its UI. Close RTW3 and inspect the module report before retrying.")


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("command",choices=("attach",));parser.add_argument("--pid",type=int);parser.add_argument("--self-test",action="store_true")
    args=parser.parse_args()
    try:print(json.dumps(attach(args.pid,args.self_test)))
    except (OSError,ValueError) as error:print(json.dumps({"ok":False,"message":str(error)}));raise SystemExit(1)
