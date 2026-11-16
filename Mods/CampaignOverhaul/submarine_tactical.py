"""Experimental friendly-submarine course/speed orders on native battle time.

Only position is changed, through a guarded native UI-thread mailbox. Native
attacks and ASW remain active. This is not a depth or manual-fire simulation.
"""
import argparse
import ctypes as c
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import sys
import time
import weekly_runtime as rt
import week_display as memory

HERE=Path(__file__).resolve().parent
MANAGER=HERE.parent/"Manager"
REPORT=HERE/"submarine_control_report.json"
ORDERS=MANAGER/"submarine-orders"
POINT_UNITS=5_400_000


def only(pattern,body,label):
    matches=list(re.finditer(pattern,body,re.DOTALL))
    if len(matches)!=1: raise ValueError("Cannot verify tactical submarine "+label+".")
    return matches[0]


def discover(blob,base):
    start=rt.method_address(blob,base,"CheckAirSubmarineSighting")-base
    body=blob[start:start+0x300]
    listing=only(rb"\xa1(.{4})\x8b\x00\x8b\x78\x08\x4f\x85\xff",body,"list")
    clock=only(rb"\xa1(.{4})\xff\x70\x04\xff\x30\x8d\x46\x14",body,"battle clock")
    side=only(rb"\x8b\x43\x38\x8b\x15(.{4})\x3b\x02",body,"player side")
    if b"\x8b\x46\x08\x3b\x43\x38" not in body or b"\x83\x7e\x10\x00" not in body:
        raise ValueError("Unsupported submarine side/downtime fields.")
    missile=rt.method_address(blob,base,"CheckImprovedMissileSubs")-base
    if b"\x80\x7b\x4c\x04" not in blob[missile:missile+0x20]:
        raise ValueError("Unsupported submarine role field.")
    # Native fixed-point geographic scale, inspected in the GIS distance code.
    # Refuse unknown point formats instead of treating coordinates as floats.
    if struct.pack("<QH",16004540465035435006,16354) not in blob:
        raise ValueError("Unsupported native fixed-point coordinate scale.")
    return {"list_slot":struct.unpack("<I",listing.group(1))[0],"clock_slot":struct.unpack("<I",clock.group(1))[0],
            "side_slot":struct.unpack("<I",side.group(1))[0],"position":0x14,"side":8,"downtime":0x10,"role":0x4c,
            "units_per_degree":POINT_UNITS}


def mailbox_thunk(address,mailbox,layout):
    code=bytearray(b"\x9c\x60");labels={};fixups=[]
    def mark(name): labels[name]=len(code)
    def jump(op,name): code.extend(op);fixups.append((len(code),name));code.extend(b"\0"*4)
    def abs32(op,value): code.extend(op+struct.pack("<I",value))
    abs32(b"\x83\x3d",mailbox);code.extend(b"\x01");jump(b"\x0f\x85","done")
    abs32(b"\xa1",layout["list_slot"]);code.extend(b"\x85\xc0");jump(b"\x0f\x84","fail")
    code.extend(b"\x8b\x00\x85\xc0");jump(b"\x0f\x84","fail")
    abs32(b"\x3b\x05",mailbox+4);jump(b"\x0f\x85","fail")
    abs32(b"\x8b\x0d",mailbox+12)
    code.extend(b"\x3b\x48\x08");jump(b"\x0f\x83","fail")
    code.extend(b"\x81\x78\x08\x10\x27\x00\x00");jump(b"\x0f\x87","fail")
    code.extend(b"\x8b\x40\x04\x85\xc0");jump(b"\x0f\x84","fail")
    code.extend(b"\x8b\x1c\x88\x85\xdb");jump(b"\x0f\x84","fail")
    abs32(b"\x3b\x1d",mailbox+8);jump(b"\x0f\x85","fail")
    abs32(b"\xa1",layout["side_slot"]);code.extend(b"\x85\xc0");jump(b"\x0f\x84","fail")
    code.extend(b"\x8b\x00\x83\xf8\x01");jump(b"\x0f\x87","fail")
    abs32(b"\x3b\x05",mailbox+16);jump(b"\x0f\x85","fail")
    code.extend(b"\x3b\x43\x08");jump(b"\x0f\x85","fail")
    code.extend(b"\x81\x7b\x10\xff\xff\xff\x7f");jump(b"\x0f\x84","fail")
    abs32(b"\xa1",mailbox+20);code.extend(b"\x3b\x43\x14");jump(b"\x0f\x85","fail")
    abs32(b"\xa1",mailbox+24);code.extend(b"\x3b\x43\x18");jump(b"\x0f\x85","fail")
    abs32(b"\xc7\x05",mailbox);code.extend(struct.pack("<I",3))
    abs32(b"\xa1",mailbox+28);code.extend(b"\x89\x43\x14")
    abs32(b"\xa1",mailbox+32);code.extend(b"\x89\x43\x18")
    abs32(b"\xc7\x05",mailbox);code.extend(struct.pack("<I",2));jump(b"\xe9","done")
    mark("fail");abs32(b"\xc7\x05",mailbox);code.extend(struct.pack("<I",4))
    mark("done");code.extend(b"\x61\x9d\xc3")
    for off,label in fixups: struct.pack_into("<i",code,off,labels[label]-off-4)
    return bytes(code)


def project(x,y,heading,speed,seconds):
    if not all(math.isfinite(float(v)) for v in (x,y,heading,speed,seconds)):
        raise ValueError("Movement contains a non-finite value.")
    if not -180*POINT_UNITS<=x<=180*POINT_UNITS or not -90*POINT_UNITS<=y<=90*POINT_UNITS:
        raise ValueError("Native submarine position is outside the world.")
    if not 0<=heading<360 or not 0<=speed<=45 or not 0<=seconds<=300:
        raise ValueError("Unsupported submarine course, speed or time step.")
    if speed==0 or seconds==0:return int(x),int(y)
    lon,lat=math.radians(x/POINT_UNITS),math.radians(y/POINT_UNITS)
    bearing=math.radians(heading);angular=speed*1852*seconds/3600/6_371_008.8
    new_lat=math.asin(max(-1,min(1,math.sin(lat)*math.cos(angular)+math.cos(lat)*math.sin(angular)*math.cos(bearing))))
    new_lon=lon+math.atan2(math.sin(bearing)*math.sin(angular)*math.cos(lat),math.cos(angular)-math.sin(lat)*math.sin(new_lat))
    return round(((math.degrees(new_lon)+180)%360-180)*POINT_UNITS),round(math.degrees(new_lat)*POINT_UNITS)


def snapshot(saved,handle):
    import live_cheats as live
    layout=saved["layout"].get("submarines")
    if not layout: raise ValueError("Enable Tactical Submarine Course Control and restart through Play with mods.")
    def integer(address):return live.integer(handle,address)
    root=integer(layout["list_slot"]) & 0xffffffff
    fleet=(integer(root)&0xffffffff) if root else 0
    if not fleet: raise ValueError("Start a tactical battle with submarines, then refresh.")
    count=integer(fleet+8);entries=integer(fleet+4)&0xffffffff
    if not 0<=count<=10000: raise ValueError("The tactical list is changing. Refresh.")
    side_ptr=integer(layout["side_slot"])&0xffffffff
    side=integer(side_ptr) if side_ptr else -1
    if side not in (0,1): raise ValueError("A player-controlled battle side is not ready.")
    clock_ptr=integer(layout["clock_slot"])&0xffffffff
    if not clock_ptr: raise ValueError("Battle time is not ready.")
    clock=struct.unpack("<d",rt.read(handle,clock_ptr,8))[0]
    if not math.isfinite(clock) or not 1<=clock<=100000: raise ValueError("Battle time is not valid.")
    year=(dt.datetime(1899,12,30)+dt.timedelta(days=clock)).year
    rows=[]
    pointers=struct.unpack("<"+"I"*count,rt.read(handle,entries,count*4)) if count else []
    for index,pointer in enumerate(pointers):
        if not pointer: continue
        data=rt.read(handle,pointer,0x51)
        owner,availability,downtime=struct.unpack_from("<iii",data,8)
        if owner!=side or downtime==0x7fffffff: continue
        role=data[0x4c]
        if not 0<=role<=4: continue
        x,y=struct.unpack_from("<ii",data,0x14)
        if abs(x)>180*POINT_UNITS or abs(y)>90*POINT_UNITS: continue
        name=live.text_value(handle,pointer+4,"")
        if not name:continue
        rows.append({"index":index,"pointer":pointer,"name":name,"type":role,"availability":availability,"downtime":downtime,
                     "x":x,"y":y,"longitude":round(x/POINT_UNITS,5),"latitude":round(y/POINT_UNITS,5)})
    identity={"pid":saved["pid"],"base":saved["base"],"allocation":saved["allocation"],"fleet":fleet,"entries":entries,"side":side,
              "boats":[{k:r[k] for k in ("index","pointer","name","type")} for r in rows]}
    token=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
    return {"ok":True,"pid":saved["pid"],"sha256":token,"fleet":fleet,"entries":entries,"side":side,"clock":clock,"year":year,"boats":rows,
            "course_speed_control":True,"depth_control":False,"manual_fire_control":False,
            "note":"Experimental movement only. Native attacks and ASW remain automatic. Paused battle time means no movement."}


def order_path(saved):return ORDERS/(str(saved["pid"])+"-"+str(saved["allocation"])+".json")


def read_orders(saved):
    path=order_path(saved)
    if not path.exists():return {"schema":1,"pid":saved["pid"],"allocation":saved["allocation"],"orders":{}}
    result=json.loads(path.read_text(encoding="utf-8"))
    if result.get("schema")!=1 or result.get("pid")!=saved["pid"] or result.get("allocation")!=saved["allocation"] or not isinstance(result.get("orders"),dict):
        raise ValueError("Submarine orders belong to a different session.")
    return result


def controller_available(saved):
    if not REPORT.exists():return False
    data=json.loads(REPORT.read_text(encoding="utf-8"))
    if data.get("pid")!=saved["pid"] or data.get("allocation")!=saved["allocation"]:return False
    handle=rt.K.OpenProcess(0x1000,False,data.get("controller_pid",0))
    if not handle:return False
    try:
        code=c.c_ulong();return bool(rt.K.GetExitCodeProcess(handle,c.byref(code)) and code.value==259)
    finally:rt.K.CloseHandle(handle)


def inspect(pid=None):
    import live_cheats as live
    saved,handle=live.session(pid)
    try:
        result=snapshot(saved,handle);result["orders"]=read_orders(saved)["orders"];result["controller_available"]=controller_available(saved)
        return result
    finally:rt.K.CloseHandle(handle)


def set_order(pid,index,heading,speed,ident,revision,expected_hash,release=False):
    import live_cheats as live
    import submarine_designs as designs
    saved,handle=live.session(pid)
    try:
        current=snapshot(saved,handle)
        if current["sha256"]!=expected_hash:raise ValueError("Tactical submarine identity changed. Refresh before issuing orders.")
        boat=next((r for r in current["boats"] if r["index"]==index),None)
        if boat is None:raise ValueError("Choose a friendly, surviving tactical submarine.")
        if not controller_available(saved):raise ValueError("The tactical movement service is not running. Restart with the submarine control mod enabled.")
        data=read_orders(saved);key=str(index)
        if release:data["orders"].pop(key,None)
        else:
            profile=designs.read_library()["blueprints"].get(ident)
            if not profile or profile["revision"]!=revision:raise ValueError("The selected class changed. Refresh class profiles.")
            design=profile["design"];result=designs.evaluate(design)
            if not result["valid"] or result["native"]["type"]!=boat["type"]:raise ValueError("Choose a valid class with the same native submarine role.")
            if design["year"]>current["year"]:raise ValueError("Class design year is later than this battle.")
            if isinstance(heading,bool) or not isinstance(heading,int) or not 0<=heading<360:raise ValueError("Course must be 0-359 degrees.")
            if isinstance(speed,bool) or not isinstance(speed,(int,float)) or not math.isfinite(speed) or not 0<=speed<=design["submerged_speed"]:
                raise ValueError("Speed exceeds the selected class's projected submerged speed.")
            data["orders"][key]={"context":current["sha256"],"pointer":boat["pointer"],"name":boat["name"],"type":boat["type"],
                                  "heading":heading,"speed":speed,"blueprint_id":ident,"revision":revision,"design":design}
        ORDERS.mkdir(exist_ok=True);designs.atomic_json(order_path(saved),data)
        return {"ok":True,"message":"Control released after any already-queued step." if release else "Course/speed order accepted. Movement follows native battle time; attacks remain automatic."}
    finally:rt.K.CloseHandle(handle)


def step(saved,handle,current,boat,target):
    import live_cheats as live
    mailbox=saved["mailbox"]+0x800
    if live.integer(handle,mailbox) in (1,3):raise ValueError("A submarine movement step is already pending.")
    values=(current["fleet"],boat["pointer"],boat["index"],current["side"],boat["x"],boat["y"],target[0],target[1])
    memory.write(handle,mailbox+4,struct.pack("<8I",*[v&0xffffffff for v in values]))
    memory.write(handle,mailbox,struct.pack("<I",1));live.wake(saved["pid"])
    deadline=time.monotonic()+2
    while time.monotonic()<deadline:
        state=live.integer(handle,mailbox)
        if state==2:return
        if state==4:raise ValueError("The battle changed; submarine movement was refused.")
        time.sleep(0.02)
    raise ValueError("Submarine step is pending; no later step will overwrite it.")


def run(pid):
    import live_cheats as live
    saved,handle=live.session(pid,True)
    if "submarines" not in saved["layout"]:rt.K.CloseHandle(handle);raise ValueError("Restart with the submarine control mod.")
    # One movement service per native adapter allocation, even if the launcher
    # is invoked twice. The OS releases the mutex if this helper exits.
    kernel=c.WinDLL("kernel32",use_last_error=True)
    kernel.CreateMutexW.argtypes=[c.c_void_p,c.c_int,c.c_wchar_p];kernel.CreateMutexW.restype=c.c_void_p
    mutex=kernel.CreateMutexW(None,False,"Local\\RTW3.Submarines."+str(pid)+"."+str(saved["allocation"]))
    if not mutex:rt.K.CloseHandle(handle);raise rt.win_error("Cannot create submarine service guard")
    if c.get_last_error()==183:rt.K.CloseHandle(mutex);rt.K.CloseHandle(handle);return
    report={"pid":pid,"allocation":saved["allocation"],"controller_pid":os.getpid(),"running":True,"movement_steps":0,"last_error":None}
    def publish(): REPORT.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    previous=None;publish()
    try:
        while True:
            code=c.c_ulong()
            if not rt.K.GetExitCodeProcess(handle,c.byref(code)) or code.value!=259:break
            try:
                current=snapshot(saved,handle)
                orders=read_orders(saved)["orders"]
                delta=(current["clock"]-previous["clock"])*86400 if previous and previous["sha256"]==current["sha256"] else 0
                if 0<delta<=300:
                    for boat in current["boats"]:
                        order=orders.get(str(boat["index"]))
                        if not order or order.get("context")!=current["sha256"] or order.get("pointer")!=boat["pointer"]:continue
                        target=project(boat["x"],boat["y"],order["heading"],order["speed"],delta)
                        if target!=(boat["x"],boat["y"]):step(saved,handle,current,boat,target);report["movement_steps"]+=1
                previous=current
                if report["last_error"] is not None:report["last_error"]=None;publish()
            except (OSError,ValueError,KeyError,TypeError) as error:
                previous=None
                if report["last_error"]!=str(error):report["last_error"]=str(error);publish()
            time.sleep(0.15)
    finally:
        report["running"]=False;publish();rt.K.CloseHandle(mutex);rt.K.CloseHandle(handle)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("command",choices=("run",));parser.add_argument("--pid",type=int,required=True)
    args=parser.parse_args()
    try:run(args.pid)
    except (OSError,ValueError) as error: print(str(error),file=sys.stderr);raise SystemExit(1)
