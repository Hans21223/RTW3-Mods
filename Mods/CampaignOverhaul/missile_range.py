"""Missile regression fix: native launches and actual AI course control.

Version 0.5's custom firing replacement is deliberately not installed. Native
current-contact launch decisions, including researched SAM surface fire, remain.
The native fallback that searches the global ship list (targets the shooter's side
has spotted, behind the nation's missile research and the native identification
check) runs again: skipping it (0.5.1 to 2026-11-22) left ships under Fire at will
silent at enemies their own sensors did not hold. Only its one-in-500 pick of a
friendly ship as the target is removed.

Missile blind fire: a ship that launches missiles (FireSSM) gives its position away
for BLIND_MINUTES battle minutes. The global search may then pick it although no one
has sighted it, so ships under Fire at will (and the computer's) answer launches from
beyond their sensors. Range, arcs, research and the rest of the native search stand.
A new battle (its clock below the last minute seen) forgets the last battle's launches.
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
BLIND_MINUTES,BLIND_SLOTS=10,64   # how long a launch gives a ship away; launches remembered (a power of two)
LAUNCH=(0x876374,"558bec83c4e8")  # FireSSM (EDX side, ECX launch position: a ship's +A1Ch): PUSH EBP / MOV EBP,ESP / ADD ESP,-18h


def discover(blob,base):
    # Reuse the original launch/geometry audits, not the custom selector.
    info=legacy.discover(blob,base)
    normal=audit.normalize(blob,base);delta=base-BASE
    for address,size,digest in WINDOWS:
        if hashlib.sha256(normal[address-BASE:address-BASE+size]).hexdigest()!=digest:
            raise ValueError("Missile range correction refuses changed code at "+hex(address))
    # The fallback's same-side candidate: MOV EAX,500 / CALL Random / DEC EAX / JNZ next (one in 500 goes on).
    info.update(friendly_site=0x8773C1+delta,friendly_next=0x8775B4+delta,
                friendly_original=blob[0x8773C1-BASE:0x8773C1-BASE+5].hex())
    # Its sighting check: MOV EAX,[EBP-4] / CMP [EAX+0D55h],1 / JG sighted, else the identification helper.
    launch=LAUNCH[0]+delta
    if blob[launch-base:launch-base+6].hex()!=LAUNCH[1]:raise ValueError("Missile blind fire refuses changed FireSSM.")
    info.update(launch=launch,launch_original=LAUNCH[1],blind_site=0x8773D2+delta,blind_helper=0x8773DE+delta,
                blind_sighted=0x8773ED+delta,blind_original=blob[0x8773D2-BASE:0x8773D2-BASE+10].hex())
    return info


def fresh(c,table):
    """EDX the battle minute: when it is below the last one seen, a new battle has begun and the launches (the
    table, then the ring index after it) are wiped, as its ships may reuse the last battle's addresses. Uses ECX, ESI."""
    last=table+8*BLIND_SLOTS+4
    c.emit(b"\x3b\x15");c.u32(last);c.emit(b"\x89\x15");c.u32(last);c.branch(b"\x0f\x83","same_battle")
    c.emit(b"\xbe");c.u32(table);c.emit(b"\xb9");c.u32(BLIND_SLOTS*2+1)
    c.mark("wipe");c.emit(b"\xc7\x06\x00\x00\x00\x00\x83\xc6\x04\x49");c.branch(b"\x0f\x85","wipe")
    c.mark("same_battle")


def record_thunk(address,info,table,ring):
    """FireSSM's entry: the launcher (ECX-A1Ch) and the battle minute go into a ring of BLIND_SLOTS. Launches by
    submarines and aircraft (ECX their +14h) leave entries that match no ship."""
    c=Code(address);c.emit(b"\x50\x51\x52\x56\x8d\x81"+struct.pack("<i",-0xA1C))   # EAX the launcher
    c.emit(b"\x8b\x15");c.u32(info["minute_slot"]);c.emit(b"\x8b\x12");fresh(c,table)
    c.emit(b"\x8b\x0d");c.u32(ring);c.emit(b"\x89\x04\xcd");c.u32(table);c.emit(b"\x89\x14\xcd");c.u32(table+4)
    c.emit(b"\x41\x83\xe1"+bytes([BLIND_SLOTS-1])+b"\x89\x0d");c.u32(ring)
    c.emit(b"\x5e\x5a\x59\x58"+bytes.fromhex(info["launch_original"]));c.branch(b"\xe9",info["launch"]+6)
    return c.finish()


def blind_thunk(address,info,table):
    """The global search's sighting check ([EBP-4] the candidate): sighted (native), or it launched in the last
    BLIND_MINUTES battle minutes (blind fire), else the native identification helper."""
    c=Code(address);c.emit(bytes.fromhex(info["blind_original"]));c.branch(b"\x0f\x8f",info["blind_sighted"])
    c.emit(b"\x51\x52\x56\x57\x8b\x15");c.u32(info["minute_slot"]);c.emit(b"\x8b\x12");fresh(c,table)
    c.emit(b"\x8b\xfa\xbe");c.u32(table);c.emit(b"\xb9");c.u32(BLIND_SLOTS)
    c.mark("loop");c.emit(b"\x39\x06");c.branch(b"\x0f\x85","next")
    c.emit(b"\x8b\xd7\x2b\x56\x04\x83\xfa"+bytes([BLIND_MINUTES]));c.branch(b"\x0f\x86","found")   # now-then <= N
    c.mark("next");c.emit(b"\x83\xc6\x08\x49");c.branch(b"\x0f\x85","loop")
    c.emit(b"\x5f\x5e\x5a\x59");c.branch(b"\xe9",info["blind_helper"])
    c.mark("found");c.emit(b"\x5f\x5e\x5a\x59");c.branch(b"\xe9",info["blind_sighted"])
    return c.finish()


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
    positions=dict(ready=allocation+0x10000,course=allocation+0x10400,engageable=allocation+0x10800,
                   record=allocation+0x10C00,blind=allocation+0x11000,
                   launches=allocation+0x11400,ring=allocation+0x11400+8*BLIND_SLOTS)   # zeroed by VirtualAllocEx
    routines=dict(ready=legacy.ready_range_thunk(positions["ready"],info),
                  course=course_thunk(positions["course"],info,positions["ready"],positions["engageable"],state+48),
                  engageable=legacy.engageable_thunk(positions["engageable"],info),
                  record=record_thunk(positions["record"],info,positions["launches"],positions["ring"]),
                  blind=blind_thunk(positions["blind"],info,positions["launches"]))
    blocks=[]
    for name,code in routines.items():
        if len(code)>0x400:raise ValueError("Missile range correction exceeds its reservation")
        blocks.append(dict(name="missile_"+name,address=positions[name],bytes=code.hex()))
    replacement=b"\xe9"+struct.pack("<i",info["friendly_next"]-info["friendly_site"]-5)   # same side: next ship
    changes=[patch("Automatic missiles: spotted targets, never a friendly ship",info["friendly_site"],
                   bytes.fromhex(info["friendly_original"]),replacement),
             patch("Missile blind fire: a launch gives the ship away",info["launch"],bytes.fromhex(info["launch_original"]),
                   b"\xe9"+struct.pack("<i",positions["record"]-info["launch"]-5)+b"\x90"),
             patch("Missile blind fire: launchers are targets",info["blind_site"],bytes.fromhex(info["blind_original"]),
                   b"\xe9"+struct.pack("<i",positions["blind"]-info["blind_site"]-5)+b"\x90"*5)]
    return dict(blocks=blocks,patches=changes,positions=positions,allocation_size=0x20000,
                blind_fire_minutes=BLIND_MINUTES,
                native_missile_selector_preserved=True,native_sam_surface_fire_preserved=True,
                custom_firing_selector_installed=False,custom_salvo_throttles_installed=False,
                screen_role_supported=True,course_control=True,launcher_arc_beam_selection=True,gun_range_disqualifier=False,
                missile_standoff_percent=info["settings"]["missile_standoff_percent"],
                battlefield_records_rewritten=False,battle_gameplay_verified=False)
