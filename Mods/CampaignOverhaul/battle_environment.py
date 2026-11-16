"""Reviewed, session-only battle daylight and clear-weather cheats.

Keep the native clock intact. Clear weather suspends weather changes while on
and restores the captured sea, precipitation and visibility when switched off.
"""
import hashlib
import struct
import modern_research as audit
from campaign_security import Code
from hull_rules import patch

WINDOWS = (
    (0x9294e0,396,"f31d306840c25329c67a3ee746179f07e6ca39ee7b1ce666493e831bbe7d0268"),
    (0x89e844,2531,"cf73deddf5bd7228a85d993bade31b13c2447fdfce6ae74c0222525283899761"),
    (0x87e42c,138,"1e158512f7f3071cdecf8db636c9b8c8747cd12efc1ec97fb9eeabe53813dc31"),
    (0x87e23c,234,"23ed1a7dde80ffb584b1aaf7f95754995d7cd7125fda102ee0fc72231563700d"),
    (0x87e328,260,"1052869816ce393169fb3f95c869857e4517def74bd02add5be085818617c718"),
    (0x8b1d7c,114,"0dd2aca71ad38d6a46e4a4acaf5b2dd2bb1a71190dbea2157e223fe1a0c0080b"),
    (0x8b22cc,48,"f91e706c840dc7886f508c8d03fe0db4f1d5fceb9769c1cdcfec08d0b6ece780"),
    (0x8c8b98,14,"7dc8984c033e54e2bcd5be53b13b915b33bcea9698e661bb2598dd3a1ff7a970"),
    (0x89fd44,472,"c62263fdd97e8e8030a11eebe9439f06091d518a8b29961c0735e1ab07acea5c"),
    (0x847920,69,"07faf00ab08f8432901d43e5f87de797f5652ac8de075c33279772e0d995ae83"),
    (0x8e1a6c,160,"184cc9aa54ee7a30a3c7b6edfa69a718c6dc7f04dcf2d21e8e1e5ba1b86afaf1"),
    (0x8b5294,15,"89ddb54672a17530ef04b89edc2e1c1425ec97c3e3e92d708c7a17e757e05fa4"),
    (0x566d9c,772,"0d6e537c47842776c238a15f4ed17dfcb9c4daafd47ab9f2db57e8674502a121"),
    (0x85c818,37,"636d056c4980c3baa9c22fe964fca686eb00b6642d165ba618fa194221aae855"),
    (0x918ac8,294,"72de16339a7b4b487a73771a6db75050ef133ebeee6cad8a12f6be6213f676e0"),
    (0x978118,432,"ba4253733e47dfe74fa1d271acae54f6b7aa654b971ebd9b6a3ac5c3bedc25e7"),
    (0x85f934,47,"9524cfdb06680eb97dcdfa51c3ebaff771f08074346b9ee6f1e956fb4fd5c75c"),
    (0x8cda06,41,"191deef75a4f96b19c8b3e6e043225f257250aa2ff325116b63ff4c6f134a368"),
    (0x6fb410,150,"5938254ed8b0a983def0d49b2dcbb35d7dd152f901c09e5151f8d74241bae545"),
)
# Future-time aircraft readiness, return warnings and planning colours. Only
# these reviewed callers get perpetual daylight at future times. The native
# Sun Times search and battle-start time searches keep natural astronomy.
AIR_FORECAST_CALLS=(0x85f956,0x8cda2a,0x918b39,0x918b6c,0x918bbd,0x978217,0x6fb438,0x6fb49a)
FLAGS = {"force_daytime": 0, "clear_weather": 4}
# State: flags, active form, captured flag, original weather/visibility, busy.
ACTIVE, CAPTURED, BACKUP, BUSY = 8, 12, 16, 36


def discover(blob, base):
    normal = audit.normalize(blob, base)
    for address, size, digest in WINDOWS:
        offset = address-0x301000
        if hashlib.sha256(normal[offset:offset+size]).hexdigest() != digest:
            raise ValueError("Battle environment refuses changed native code at "+hex(address)+".")
    delta = base-0x301000
    actual = lambda value: value+delta
    for call in AIR_FORECAST_CALLS:
        offset=call-0x301000
        if blob[offset]!=0xe8 or actual(call)+5+struct.unpack_from("<i",blob,offset+1)[0]!=actual(0x9294e0):
            raise ValueError("Unrecognized aircraft daylight query.")
    # Enum RTTI independently identifies 2=plClear, not 0 (plHeavyMist).
    # The Sun Times handler's phase-1 branch says 'It is daylight'.
    return dict(clock_slot=actual(0x9f7748), form_slot=actual(0xa23274),
                weather_slots=[actual(a) for a in (0x9f7adc,0x9f7b3c,0x9f77ec,0x9f6e04,0x9f7064)],
                widths=[4,1,4,4,4], basic_day_range=actual(0x87e23c),
                basic_night_range=actual(0x87e328),
                air_forecast_returns=[actual(a+5) for a in AIR_FORECAST_CALLS],
                shadow_exit=actual(0x567097),shadow_battle_return=actual(0x85c83d),
                weather_colour=actual(0x847920), set_colour=actual(0x5653d4),
                weather_description=actual(0x89fd44),
                sites={name: dict(address=actual(address), original=blob[address-0x301000:address-0x301000+size].hex())
                       for name,address,size in (("day",0x9294e0,9),("weather",0x89e844,6),
                                                 ("show",0x8b22cc,6),("hide",0x8c8b98,6),
                                                 ("shadow",0x566f32,5))},
                phase_day=1, precipitation_clear=2, sea_calm=0,
                clock_changed=False, weather_progression="suspended while clear weather is on",
                battle_gameplay_verified=False)


def sync_thunk(address, state, info):
    c = Code(address)
    def absolute(op, target): c.emit(op); c.u32(target)
    def restore():
        for i,(slot,width) in enumerate(zip(info["weather_slots"],info["widths"])):
            absolute(b"\x8b\x15",slot); absolute(b"\xa1",state+BACKUP+i*4)
            c.emit(b"\x88\x02" if width==1 else b"\x89\x02")
        absolute(b"\xc7\x05",state+CAPTURED); c.u32(0)
    c.emit(b"\x9c\x60")
    absolute(b"\x83\x3d",state+BUSY); c.emit(b"\x00"); c.branch(b"\x0f\x85","done")
    absolute(b"\xc7\x05",state+BUSY); c.u32(1)
    absolute(b"\x8b\x35",state+ACTIVE); c.emit(b"\x85\xf6"); c.branch(b"\x0f\x84","inactive")
    absolute(b"\x3b\x35",info["form_slot"]); c.branch(b"\x0f\x85","inactive")
    absolute(b"\x83\x3d",state+4); c.emit(b"\x01"); c.branch(b"\x0f\x85","off")
    absolute(b"\x83\x3d",state+CAPTURED); c.emit(b"\x00"); c.branch(b"\x0f\x85","finish")
    for i,(slot,width) in enumerate(zip(info["weather_slots"],info["widths"])):
        absolute(b"\x8b\x15",slot); c.emit(b"\x0f\xb6\x02" if width==1 else b"\x8b\x02")
        absolute(b"\xa3",state+BACKUP+i*4)
    absolute(b"\xc7\x05",state+CAPTURED); c.u32(1)
    absolute(b"\x8b\x15",info["weather_slots"][0]); c.emit(b"\xc7\x02"); c.u32(0)
    absolute(b"\x8b\x15",info["weather_slots"][1]); c.emit(b"\xc6\x02\x02")
    c.emit(b"\x8b\xc6"); c.branch(b"\xe8",info["basic_day_range"])
    absolute(b"\x8b\x15",info["weather_slots"][2]); c.emit(b"\x89\x02\x8b\xd8")
    c.emit(b"\x8b\xc6"); c.branch(b"\xe8",info["basic_night_range"])
    absolute(b"\x8b\x15",info["weather_slots"][3]); c.emit(b"\x89\x02")
    c.emit(b"\x01\xd8\xd1\xf8")  # Twilight is the native day/night average.
    absolute(b"\x8b\x15",info["weather_slots"][4]); c.emit(b"\x89\x02")
    c.branch(b"\xe9","refresh")
    c.mark("off"); absolute(b"\x83\x3d",state+CAPTURED); c.emit(b"\x00"); c.branch(b"\x0f\x84","finish")
    restore()
    c.mark("refresh")
    # Same native label/colour updates as the weather-change handler, without
    # its sound/message side effects or extra random visibility rolls.
    c.emit(b"\x8b\x86\x98\x04\x00\x00\x85\xc0"); c.branch(b"\x0f\x84","finish")
    absolute(b"\x8b\x15",info["weather_slots"][1]); c.emit(b"\x0f\xb6\x12")
    c.branch(b"\xe8",info["weather_colour"])
    c.emit(b"\x8b\x86\x98\x04\x00\x00\x8b\x90\x3d\x03\x00\x00\x8b\x86\x80\x05\x00\x00")
    c.branch(b"\xe8",info["set_colour"])
    c.emit(b"\x8b\xc6"); c.branch(b"\xe8",info["weather_description"])
    c.branch(b"\xe9","finish")
    c.mark("inactive"); absolute(b"\x83\x3d",state+CAPTURED); c.emit(b"\x00"); c.branch(b"\x0f\x84","finish")
    restore()
    c.mark("finish"); absolute(b"\xc7\x05",state+BUSY); c.u32(0)
    c.mark("done"); c.emit(b"\x61\x9d\xc3")
    return c.finish()


def gate_thunk(address, state, sync, info, name):
    site = info["sites"][name]; c = Code(address)
    def absolute(op, target): c.emit(op); c.u32(target)
    c.emit(b"\x9c\x52")
    if name in ("show","hide"):
        if name=="show":
            absolute(b"\xa3",state+ACTIVE)
        else:
            absolute(b"\x3b\x05",state+ACTIVE); c.branch(b"\x0f\x85","native")
            absolute(b"\xc7\x05",state+ACTIVE); c.u32(0)
            # Sync preserves all registers, including the FormHide receiver.
            c.branch(b"\xe8",sync)
    else:
        absolute(b"\x83\x3d",state+FLAGS["force_daytime" if name=="day" else "clear_weather"])
        c.emit(b"\x01"); c.branch(b"\x0f\x85","native")
        absolute(b"\x8b\x15",state+ACTIVE); c.emit(b"\x85\xd2"); c.branch(b"\x0f\x84","native")
        absolute(b"\x3b\x15",info["form_slot"]); c.branch(b"\x0f\x85","native")
        if name=="day":
            for caller in info["air_forecast_returns"]:
                c.emit(b"\x81\x7c\x24\x08");c.u32(caller);c.branch(b"\x0f\x84","daylight")
            # Other future queries stay natural, including sunrise searches.
            absolute(b"\x8b\x15",info["clock_slot"])
            c.emit(b"\x8b\x12\x3b\x54\x24\x0c"); c.branch(b"\x0f\x85","native")
            absolute(b"\x8b\x15",info["clock_slot"])
            c.emit(b"\x8b\x52\x04\x3b\x54\x24\x10"); c.branch(b"\x0f\x85","native")
            c.mark("daylight");c.emit(b"\x5a\x9d\xb8\x01\x00\x00\x00\xc2\x08\x00")
        else:
            c.emit(b"\x5a\x9d\xc3")  # Suspend only the native weather change.
    c.mark("native"); c.emit(b"\x5a\x9d"+bytes.fromhex(site["original"]))
    c.branch(b"\xe9",site["address"]+len(bytes.fromhex(site["original"])))
    return c.finish()


def shadow_thunk(address,state,info):
    # RenderDIBShadow has already calculated its output solar vector here.
    # Skip only its pixel shading loop, only for the native battle-map caller.
    # Its normal epilogue still returns that vector and cleans up all 16 bytes.
    site=info["sites"]["shadow"];c=Code(address);c.emit(b"\x9c\x50")
    c.emit(b"\x83\x3d");c.u32(state);c.emit(b"\x01");c.branch(b"\x0f\x85","native")
    c.emit(b"\xa1");c.u32(state+ACTIVE);c.emit(b"\x85\xc0");c.branch(b"\x0f\x84","native")
    c.emit(b"\x3b\x05");c.u32(info["form_slot"]);c.branch(b"\x0f\x85","native")
    c.emit(b"\x81\x7d\x04");c.u32(info["shadow_battle_return"]);c.branch(b"\x0f\x85","native")
    c.emit(b"\x58\x9d");c.branch(b"\xe9",info["shadow_exit"])
    c.mark("native");c.emit(b"\x58\x9d"+bytes.fromhex(site["original"]))
    c.branch(b"\xe9",site["address"]+5);return c.finish()


def plan(allocation, mailbox, info):
    state, sync = mailbox+0x800, allocation+0x800
    blocks = [(sync,sync_thunk(sync,state,info),0x300)]
    changes = []
    for i,name in enumerate(("day","weather","show","hide")):
        target=allocation+0xc00+i*0x100
        blocks.append((target,gate_thunk(target,state,sync,info,name),0x100))
        site=info["sites"][name]; original=bytes.fromhex(site["original"])
        changes.append(patch("Battle environment: "+name,site["address"],original,
                             b"\xe9"+struct.pack("<i",target-site["address"]-5)+b"\x90"*(len(original)-5)))
    target=allocation+0xb00;site=info["sites"]["shadow"]
    blocks.append((target,shadow_thunk(target,state,info),0x100))
    changes.append(patch("Battle environment: map daylight",site["address"],bytes.fromhex(site["original"]),
                         b"\xe9"+struct.pack("<i",target-site["address"]-5)))
    for _,code,size in blocks:
        if len(code)>size: raise ValueError("Battle environment code exceeds its reserved space.")
    return dict(version=2,state=state,sync=sync,details=info,patches=changes),blocks
