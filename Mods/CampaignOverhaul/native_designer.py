"""Read-only discovery of the original Delphi ship-design form and its fields."""
import json
from pathlib import Path
import re
import struct
import sys
import weekly_runtime as rt


def discover(blob,base,read):
    command=rt.method_address(blob,base,"btbnDesignClick")
    body=blob[command-base:command-base+0x80]
    roots=list(re.finditer(rb"\xa1(.{4})\x8b\x00\x83\xc9\xff\xe8(.{4})",body,re.DOTALL))
    if len(roots)!=1:raise ValueError("Cannot verify the native Ship design form root.")
    root=struct.unpack("<I",roots[0].group(1))[0]
    get=lambda a:struct.unpack("<I",read(a,4))[0]
    slot=get(root);obj=get(slot);vmt=get(obj)
    name_ptr=get(vmt-56);length=read(name_ptr,1)[0];name=read(name_ptr+1,length).decode("ascii")
    if name!="TfrmDesignMain2":raise ValueError("Unsupported native designer class: "+name)
    table=get(vmt-68);count=struct.unpack("<H",read(table,2))[0]
    if not 20<count<1000:raise ValueError("Unsupported native designer field count.")
    offset=table+6;fields={}
    for _ in range(count):
        entry=read(offset,7);field,index,length=struct.unpack("<IHB",entry)
        field_name=read(offset+7,length).decode("ascii")
        if not re.fullmatch("[A-Za-z_][A-Za-z0-9_]*",field_name) or not 0<field<0x4000:raise ValueError("Invalid native designer field metadata.")
        fields[field_name]=field;offset+=7+length
    method_table=get(vmt-64);methods={}
    count=struct.unpack("<H",read(method_table,2))[0];offset=method_table+2
    if not 10<count<1000:raise ValueError("Unsupported native designer method table.")
    for _ in range(count):
        entry=read(offset,7);size,address,length=struct.unpack("<HIB",entry)
        if not 7+length<=size<1200:raise ValueError("Invalid native designer method metadata.")
        methods[read(offset+7,length).decode("ascii")]=address;offset+=size
    needed=("cbType","seDisplacement","seSpeed")
    if any(key not in fields for key in needed) or "cbTypeChange" not in methods:raise ValueError("Native design controls are incomplete.")
    type_body=blob[methods["cbTypeChange"]-base:methods["cbTypeChange"]-base+0x80]
    flags=list(re.finditer(rb"\x80\xbe(.{4})\x00",type_body,re.DOTALL))
    if len(flags)!=1:raise ValueError("Cannot verify the native designer update guard.")
    editing=struct.unpack("<I",flags[0].group(1))[0]
    speed=blob[methods["seSpeedChange"]-base:methods["seSpeedChange"]-base+0x30]
    if b"\x80\xbb"+struct.pack("<I",editing)+b"\x00" not in speed:raise ValueError("Designer editing guards disagree.")
    return {"root":root,"slot":slot,"vmt":vmt,"class_name":name,"fields":fields,"methods":methods,"design_command":command,"editing_field":editing}


def gate(address,state,original,continuation,signal=0,stack_bytes=0):
    """Guard a native event while SS mode is active, preserving normal events.

    state: active, expected form, signal. No managed callback runs in this hook.
    The original control handler is never fed the added SS surface-type index.
    """
    code=bytearray(b"\x9c\x83\x3d"+struct.pack("<I",state)+b"\x01\x0f\x85\0\0\0\0")
    offsets=[len(code)-4]
    code.extend(b"\x3b\x05"+struct.pack("<I",state+4)+b"\x0f\x85\0\0\0\0");offsets.append(len(code)-4)
    if signal:code.extend(b"\xc7\x05"+struct.pack("<II",state+8,signal))
    code.extend(b"\x9d"+(b"\xc2"+struct.pack("<H",stack_bytes) if stack_bytes else b"\xc3"))
    normal=len(code)
    if original[:1]==b"\xe8" and len(original)==5:
        destination=continuation+struct.unpack_from("<i",original,1)[0]
        original=b"\xe8"+struct.pack("<i",destination-(address+normal+1+5))
    code.extend(b"\x9d"+original+b"\xe9");code.extend(struct.pack("<i",continuation-(address+len(code)+4)))
    for off in offsets:struct.pack_into("<i",code,off,normal-off-4)
    return bytes(code)


def attach(pid):
    import week_display as memory
    import live_cheats as live
    from hull_rules import patch
    memory.configure();handle=rt.K.OpenProcess(0x438,False,pid)
    if not handle:raise rt.win_error("Cannot extend the original ship designer")
    try:
        module,base,blob=live.unhooked_text(pid,handle)
        layout=discover(blob,base,lambda at,n:rt.read(handle,at,n))
        sys.path.insert(0,str(rt.GAME/"Mods/Manager/vendor"))
        import capstone
        dis=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_32)
        # These native event signatures are ordinary Delphi register events;
        # key-down/up additionally pop the stack-passed Shift set (4 bytes).
        events={"cbTypeChange":(0,0),"tcArmamentChange":(0,0),"btbnFinishClick":(1,0),
                "Save1Click":(2,0),"sbSaveClick":(2,0),"bnSaveClick":(2,0),
                "FormKeyDown":(0,4),"FormKeyUp":(0,4),"FormKeyPress":(0,0),"tmrDelayTimer":(0,0),
                "sbCheckClick":(3,0),"sbAutoBuildClick":(0,0),"sbOpenClick":(4,0),
                "lbPreviousClick":(0,0),"lbSetBeltArmorClick":(0,0),
                "FormMouseWheelUp":(0,8),"FormMouseWheelDown":(0,8)}
        verified=[]
        for name,(signal,stack) in events.items():
            address=layout["methods"][name];start=address-base;length=0
            for ins in dis.disasm(blob[start:start+24],address):
                if ins.mnemonic.startswith(("j","ret","loop")) or (ins.mnemonic=="call" and not (length==0 and ins.size==5 and ins.bytes[0]==0xe8)):
                    raise ValueError("Unsupported native event prologue: "+name)
                length+=ins.size
                if length>=5:break
            if length<5:raise ValueError("Incomplete native event prologue.")
            # Verify the native return contract, not merely the event's name.
            returns=[ins for ins in dis.disasm(blob[start:start+0x8000],address) if ins.mnemonic=="ret"]
            if not returns or returns[0].op_str!=(hex(stack) if stack else ""):
                # Capstone prints small immediates in decimal on some versions.
                if not returns or (int(returns[0].op_str or "0",0)!=stack):raise ValueError("Native event stack contract changed: "+name)
            verified.append((name,address,blob[start:start+length],signal,stack))
        allocation=rt.K.VirtualAllocEx(handle,None,0x4000,0x3000,0x40)
        if not allocation:raise rt.win_error("Cannot allocate native designer event guards")
        state=allocation+0x2000;changes=[]
        try:
            for n,(name,address,original,signal,stack) in enumerate(verified):
                target=allocation+n*0x100
                code=gate(target,state,original,address+len(original),signal,stack)
                memory.write(handle,target,code)
                rt.K.FlushInstructionCache(handle,target,len(code))
                item=patch("Native submarine mode: "+name,address,original,b"\xe9"+struct.pack("<i",target-address-5)+b"\x90"*(len(original)-5))
                rt.write_code(handle,address,original,bytes.fromhex(item["replacement"]));changes.append(item)
            layout.update(state=state,allocation=allocation,patches=changes,pid=pid,base=module)
            Path(__file__).with_name("native_designer_report.json").write_text(json.dumps(layout,indent=2)+"\n",encoding="utf-8")
            return layout
        except Exception:
            for item in reversed(changes):rt.write_code(handle,item["address"],bytes.fromhex(item["replacement"]),bytes.fromhex(item["original"]))
            # Published hook buffers are retained until process exit.
            if not changes:rt.K.VirtualFreeEx(handle,allocation,0,0x8000)
            raise
    finally:rt.K.CloseHandle(handle)


if __name__=="__main__":
    import argparse,subprocess,sys
    parser=argparse.ArgumentParser();parser.add_argument("--launch",action="store_true");parser.add_argument("--snapshot",action="store_true");args=parser.parse_args()
    if args.launch:subprocess.run([sys.executable,str(Path(__file__).with_name("launch.py")),"--no-dialog"],check=True)
    rt.configure_api();pid,path=next((p,x) for p,x in rt.process_candidates() if x==rt.GAME/"RTW3.exe")
    handle=rt.K.OpenProcess(0x410,False,pid)
    try:
        module,_=rt.module_info(pid);base,blob=rt.text_section(handle,module)
        result=discover(blob,base,lambda at,n:rt.read(handle,at,n));result.update(pid=pid,base=module,text_base=base)
        out=rt.GAME/"Mods/Manager/native-designer-inspection.json";out.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
        if args.snapshot:
            out.with_suffix(".text.bin").write_bytes(blob)
        print(json.dumps(result,indent=2))
    finally:rt.K.CloseHandle(handle)
