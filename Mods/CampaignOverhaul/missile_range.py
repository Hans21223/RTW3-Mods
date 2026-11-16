"""Missile regression fix: native launches and actual AI course control.

Version 0.5's custom firing replacement is deliberately not installed. Native
current-contact launch decisions, including researched SAM surface fire, remain.
Only the native fallback that searches the global ship list is bypassed.
"""
import hashlib
import struct

import missile_ai as legacy
import modern_research as audit
from campaign_security import Code
from hull_rules import patch

BASE=0x301000
WINDOWS=(
    (0x87730A,10,"1694b06105ea2ccea6377aa88817d64f7622797d5c43559c04e882a2bcd69def"),
    (0x9217DC,272,"ea98bc26aaa885cfed79f88f342cbfd150d8558b30cf333698bc66dfe6142727"),
    (0x91AC14,184,"30d0ee44def55e0cdf8065011f6631d30690de73c5dc38654842c4b57f581bbe"),
    (0x9253B4,1308,"50f4f870b031b6c825dd4d972098443a9cfc6717f682931e6fd89377d8bf80af"),
)


def discover(blob,base):
    # Reuse the original launch/geometry audits, not the custom selector.
    info=legacy.discover(blob,base)
    normal=audit.normalize(blob,base);delta=base-BASE
    for address,size,digest in WINDOWS:
        if hashlib.sha256(normal[address-BASE:address-BASE+size]).hexdigest()!=digest:
            raise ValueError("Missile range correction refuses changed code at "+hex(address))
    info.update(world_site=0x87730A+delta,world_exit=0x8775C6+delta,
                world_original=blob[0x87730A-BASE:0x87730A-BASE+10].hex())
    return info


def course_thunk(address,info,ready_range,engageable,counter):
    """EBX division, ESI validated course pointer inside native SetNewCourse.

    Guard runs at course commitment for screen divisions as well as main-line
    stance decisions. Proposed courses still pass native land/turn checks.
    """
    c=Code(address);c.emit(bytes.fromhex("9c6083ec208bec8b5d308b752485db"));c.branch(b"\x0f\x84","out")
    c.emit(b"\x85\xf6");c.branch(b"\x0f\x84","out")
    c.emit(b"\x80\x7b\x30\x01");c.branch(b"\x0f\x85","out")
    c.emit(b"\x80\x7b\x3a\x04");c.branch(b"\x0f\x87","out")
    c.emit(b"\x80\x7b\x4d\x00");c.branch(b"\x0f\x85","out")
    c.emit(bytes.fromhex("0fb6432f85c0"));c.branch(b"\x0f\x84","out")
    c.emit(b"\x83\xf8\x07");c.branch(b"\x0f\x87","out")
    for stance in (5,6):
        c.emit(b"\x83\xf8"+bytes([stance]));c.branch(b"\x0f\x84","out")
    c.emit(bytes.fromhex("8b435785c0"));c.branch(b"\x0f\x84","out")
    c.emit(b"\x80\x78\x1c\x02");c.branch(b"\x0f\x84","out")
    c.emit(b"\x8b\xc3");c.branch(b"\xe8",info["flagship"])
    c.emit(b"\x8b\xf8\x85\xff");c.branch(b"\x0f\x84","out")
    c.emit(bytes.fromhex("80bf9f0a000000"));c.branch(b"\x0f\x85","out")
    c.emit(bytes.fromhex("0fb687d309000083f804"));c.branch(b"\x0f\x86","surface")
    c.emit(b"\x83\xf8\x09");c.branch(b"\x0f\x84","surface")
    c.emit(b"\x83\xf8\x0d");c.branch(b"\x0f\x85","out")
    c.mark("surface");c.emit(bytes.fromhex("8b87550a000083f801"));c.branch(b"\x0f\x87","out")
    c.emit(b"\x8b\xc7");c.branch(b"\xe8",ready_range)
    c.emit(b"\x85\xc0");c.branch(b"\x0f\x8e","out")
    # Physical gun maximum does not disqualify missile stand-off. A 1946 ship
    # can have a large theoretical gun range and still need missile separation.
    c.emit(b"\x89\x45\x1c\x69\xc0");c.u32(info["settings"]["missile_standoff_percent"])
    c.emit(bytes.fromhex("33d2b964000000f7f18945008b451c69c05a00000033d2b964000000f7f1894504"))
    c.emit(bytes.fromhex("8b87d90a000085c0"));c.branch(b"\x0f\x84","out")
    c.emit(bytes.fromhex("8b480885c9"));c.branch(b"\x0f\x8e","out")
    c.emit(b"\x81\xf9");c.u32(4096);c.branch(b"\x0f\x87","out")
    c.emit(bytes.fromhex("894d108b400485c0"));c.branch(b"\x0f\x84","out")
    c.emit(bytes.fromhex("894514c74508ffffff7fc7450c00000000"))
    c.mark("contact");c.emit(bytes.fromhex("8b45148b1085d2"));c.branch(b"\x0f\x84","next")
    c.emit(bytes.fromhex("8b82550a000083f801"));c.branch(b"\x0f\x87","next")
    c.emit(bytes.fromhex("3b87550a0000"));c.branch(b"\x0f\x84","next")
    c.emit(bytes.fromhex("80ba9f0a000000"));c.branch(b"\x0f\x85","next")
    c.emit(bytes.fromhex("89551c8bc7"));c.branch(b"\xe8",info["ship_distance"])
    c.emit(b"\x85\xc0");c.branch(b"\x0f\x8e","next")
    c.emit(b"\x3b\x45\x04");c.branch(b"\x0f\x83","next")
    c.emit(b"\x3b\x45\x08");c.branch(b"\x0f\x83","next")
    c.emit(bytes.fromhex("8945088b451c89450c"))
    c.mark("next");c.emit(bytes.fromhex("83451404ff4d10"));c.branch(b"\x0f\x85","contact")
    c.emit(bytes.fromhex("8b550c85d2"));c.branch(b"\x0f\x84","out")
    c.emit(b"\x8b\xc7");c.branch(b"\xe8",info["true_bearing"])
    c.emit(b"\x3d");c.u32(360);c.branch(b"\x0f\x87","out")
    c.emit(bytes.fromhex("8b4d083b4d00"));c.branch(b"\x0f\x8d","beam")
    c.emit(b"\x05");c.u32(180);c.emit(bytes.fromhex("c7451801000000"));c.branch(b"\xe9","wrap")
    c.mark("beam");c.emit(bytes.fromhex("8b97280a00002bd081fa"));c.u32(180)
    c.branch(b"\x0f\x8c","low");c.emit(b"\x81\xea");c.u32(360)
    c.mark("low");c.emit(b"\x81\xfa");c.u32((-180)&0xFFFFFFFF)
    c.branch(b"\x0f\x8d","side");c.emit(b"\x81\xc2");c.u32(360)
    c.mark("side");c.emit(bytes.fromhex("c745180200000085d2"));c.branch(b"\x0f\x88","left")
    c.emit(bytes.fromhex("c745100e01000083c05a"));c.branch(b"\xe9","wrap")  # relative target bearing 270
    c.mark("left");c.emit(bytes.fromhex("c745105a00000083e85a"))  # relative target bearing 90
    c.mark("wrap");c.emit(b"\x85\xc0");c.branch(b"\x0f\x8d","high")
    c.emit(b"\x05");c.u32(360)
    c.mark("high");c.emit(b"\x3d");c.u32(360);c.branch(b"\x0f\x8c","arc")
    c.emit(b"\x2d");c.u32(360)
    # Pick the beam that can actually expose a loaded launcher. Native wing
    # arcs can allow relative 270 but prohibit 90 (or the reverse).
    c.mark("arc");c.emit(bytes.fromhex("837d1802"));c.branch(b"\x0f\x85","apply")
    c.emit(bytes.fromhex("89451c6a008b55108b4d088bc7"));c.branch(b"\xe8",engageable)
    c.emit(b"\x84\xc0");c.branch(b"\x0f\x85","keep_beam")
    c.emit(b"\x6a\x00\xba");c.u32(360)
    c.emit(bytes.fromhex("2b55108b4d088bc7"));c.branch(b"\xe8",engageable)
    c.emit(b"\x84\xc0");c.branch(b"\x0f\x84","keep_beam")
    c.emit(b"\x8b\x45\x1c\x05");c.u32(180)
    c.emit(b"\x3d");c.u32(360);c.branch(b"\x0f\x8c","apply")
    c.emit(b"\x2d");c.u32(360);c.branch(b"\xe9","apply")
    c.mark("keep_beam");c.emit(b"\x8b\x45\x1c")
    c.mark("apply");c.emit(bytes.fromhex("8b551888532f3906"));c.branch(b"\x0f\x84","out")
    c.emit(b"\x89\x06\xff\x05");c.u32(counter)
    c.mark("out");c.emit(bytes.fromhex("83c420619dc3"));return c.finish()


def build(allocation,info,state):
    positions=dict(ready=allocation+0x10000,course=allocation+0x10400,engageable=allocation+0x10800)
    routines=dict(ready=legacy.ready_range_thunk(positions["ready"],info),
                  course=course_thunk(positions["course"],info,positions["ready"],positions["engageable"],state+48),
                  engageable=legacy.engageable_thunk(positions["engageable"],info))
    blocks=[]
    for name,code in routines.items():
        if len(code)>0x400:raise ValueError("Missile range correction exceeds its reservation")
        blocks.append(dict(name="missile_"+name,address=positions[name],bytes=code.hex()))
    replacement=b"\xe9"+struct.pack("<i",info["world_exit"]-info["world_site"]-5)+b"\x90"*5
    changes=[patch("Automatic missiles: current contacts only, native launch decisions",info["world_site"],
                   bytes.fromhex(info["world_original"]),replacement)]
    return dict(blocks=blocks,patches=changes,positions=positions,allocation_size=0x20000,
                native_missile_selector_preserved=True,native_sam_surface_fire_preserved=True,
                custom_firing_selector_installed=False,custom_salvo_throttles_installed=False,
                screen_role_supported=True,course_control=True,launcher_arc_beam_selection=True,gun_range_disqualifier=False,
                missile_standoff_percent=info["settings"]["missile_standoff_percent"],
                battlefield_records_rewritten=False,battle_gameplay_verified=False)
