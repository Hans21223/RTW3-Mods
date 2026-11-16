"""Audited coastal steering, report-only contact memory and auto-battle air ops.

Session-only hooks for the managed build. No save, disk executable, spotting or
weapon-effect changes. Install at the title screen, never during a battle.
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
import missile_range

REPORT = Path(__file__).with_name("battle_ai_report.json")
EMPTY_GUN = 5   # a missile ship with empty launchers and no main gun over this calibre disengages
DEFAULTS = dict(contact_memory_minutes=20, memory_radius_yards=45000,
                capital_max_advance_yards=6000, capital_gun_range_percent=75,
                stance_commit_minutes=10, withdraw_dead_zone=10, missile_standoff_percent=75,
                catapult_strikes=1)
# Complete audited native bodies where practical; small windows cross-check
# report ownership/time, the Sunk save/load field and final firing arguments.
WINDOWS = (
    (0x925ca0,382,"b7461db0ab2e5d08342ac58542183a0de79681e33b3ad3b6e59037a7a8ceff0c"),
    (0x8cda98,950,"24624136d58fb65ba56904b065cfdafd86dcb1d98cc7c54cd518e8a2569db7d5"),
    (0x8cd880,540,"6f7a313d30a3a3f1d4a4dca1351c7528b636a5619a528b1b95e520185dfd2830"),
    (0x8d2824,479,"68acc6f6471ff9a0edcc175fc438e0263c788c2f91d89a09ba1b24e7bd5fd155"),
    (0x89108c,314,"fc033d6c906d17fe524b729f8c180d81eb3fdc42f4172bc9bd3190cf8063d122"),
    (0x865c63,22,"8824f888b0622300d8e9c7977a7a87db2090de6d40003cfb7001c1dbf46acd5b"),
    (0x87c0dd,20,"fb3f88d4c748325ecc2e8f30e86e662c517ee6b08ab9a50893b1756d326180c9"),
    (0x898c18,10,"44eaf4b863e07ccb48dc58e707080dc9d245e4430f1667f503b356dbdb0e7aae"),
    (0x8986d5,12,"aae5b345ea44d841392c4fb9188ba68ac5be362f4d7f54bd4a5c71f527c09039"),
    (0x8cb915,102,"2fdadca241a15cfd45bd6722551183e2d95d9cd13aee4f066ca98c9b75d7d545"),
    (0x8a4bd1,15,"6ee97458d5f530c5005d0b37aea7232bc272acb6875eb88e95a1ddea583fa68d"),
    (0x8aae2d,24,"a1544bddc48c1ef4220f5242be90e0b1567681caa27c46d3d4cfd9584c3fd6b4"),
    (0x878eb7,30,"08c51fcad2b4644eedd6793b5a435b0eb860cc5bde36d2463843ed5b4f72633c"),
    (0x921468,32,"cf2b430a1f21a0775f1792d09fb29e48d3478dd99bd6a4ec3d121b24b2ba05d2"),
    (0x90804b,57,"3d9ff03e61208b34095ec0943db23f81196f6fa47bbb3bf4d3538517b1b2fff9"),
    (0x877e84,34,"f822128f96d3d1ce691c1f3a73bae27c3c0d7fbf1dbd254836c4d861edcb704b"),
    (0x8d4a67,30,"1dd21500f48c667ff9d30d5e1d7d5a5a7319879af9b65bc911e374bc50be983f"),
    (0x929c39,80,"8d29eb740741732cf882098bd2f5628f42322f7a1caea4c32fb5f376b6a95ea5"),
    (0x899035,42,"876b413ec39ee40ce7a05814a93ad57a352a50260ef9d5658acf42bf1a2ec077"),
    (0x8cd5be,22,"05d5ea2395382b66519ba0da0259814fca0dfec04efd0da48a2df394abaf9ea0"),
    (0x8cb96a,13,"127231642895a0b7b00e6c625936948637a2841cc331212d5679c17272d73bb3"),
    # Native stance dispatch, class/role definitions, main-gun range and
    # formation consumers. Capital protection uses only current known contacts.
    (0x86a709,54,"61ab0d3c4654a0305f2a3582d0e01c591ce6bbea33d3e0a95e7dc85f8194c478"),
    (0x90b5b0,13,"7a23abfd9a9593f46542b602306df648316ec69c78d50e57c5ad038cf291e123"),
    (0x888485,927,"911d4b6b61bfc17a4dbf3715aff8bec9ab0679f140f3b998783fe91d8665e0f0"),
    (0x910c6c,114,"f73995b25e942fd6195fe0613f7e56e0cdae378103159b96191082967b7bd191"),
    (0x921488,88,"8d80eeace1060b004516bd7b5829212dc563fdfd592bf5c432f344902ac26f23"),
    (0x90ab88,388,"d57862349ea01a7f3d5cf6769b6d6c0138d404052e5fb9014d79d7fbd38d94a3"),
    (0x924a4c,176,"b3e8f860ca077f5c81a909ea5f32e727ed7d6bdec9e9b8407c5ef9aa91f0a964"),
    (0x8669bd,10,"de62faa6fa76a2d7145431fb8259837353c36d77440611add810665f8f9a89f9"),
    # Native detach thresholds (can't keep up, fuel <15%, damage >90%) and the
    # per-tick reattach routine whose proximity-only test re-joins those ships.
    (0x87c5cd,610,"fc89eb0f7009dcdc2492ae91586142bbd0b8e6b9dc02b204ffae888596d10fcb"),
    (0x897020,374,"28389874fce5d91e3c1f9f90b2cb564b11c024c5a75e6feacd1d4497c973643c"),
    # Rescue-abort stance call, SetNewCourse validation, big-ship "enemy fire
    # uncomfortable" test and the force-withdrawal score/escalation roll.
    (0x881120,0x48,"53ad76776b5ec550972993f7213677e05a34a8578d85d840c159623c4820c4bf"),
    (0x9217dc,0x6e,"8f21ffbd3d405d24ead29543676552acb160f790dd31c574cc3362e59e0e944b"),
    (0x888a39,0x194,"60432db7d324b8144b951451fdd9fc299ff21a0626df6c0d9b8ea35e1f2ce4ff"),
    (0x87ef7e,0x114,"edb0fd2c6e18d2d070b9c30d46933014229d1d7ac80f8c36cc1aa85bbe6b789e"),
    # Destroyer and light-cruiser "CLOSE on frustrated hold" branches.
    (0x88e48c,194,"81edb98d4e8986ccf62669de86cc1b30b2465da82ca3173165eee86d201fafa0"),
    (0x88be99,229,"4935d5b30b617b5a2c74bc9850f5efca9db4620488548f50ba686fc71fa66189"),
    # Carrier launch (CheckStatus2): the enemy-presence wind check, then the two launch-state choices
    # (state 4 catapult launch without turning for CAP and search, else state 1 turn into the wind).
    (0x9648c2,0x48,"e3670c8c9d07f27e2a640b38e71b3eb1dd852d05efa510aae08335f6fa00eab7"),
    (0x964a2a,0x58,"ead8415118ebcf84c0ad9b098c4b6029ea12f73eae4b2e8e773c6bb82e295b16"),
    (0x964d6b,0x58,"37d941556d2edcc4e8a09e8172f94d422f5ba737ce3acda230b0c61ca5364a3b"),
)


def discover(blob, base, settings=None):
    values = dict(DEFAULTS, **(settings or {}))
    bounds = dict(contact_memory_minutes=(1,60), memory_radius_yards=(5000,100000),
                  capital_max_advance_yards=(2000,20000), capital_gun_range_percent=(50,90),
                  stance_commit_minutes=(0,60), withdraw_dead_zone=(0,50), missile_standoff_percent=(50,85),
                  catapult_strikes=(0,1))
    if values.keys() != DEFAULTS.keys() or any(type(v) is not int or not bounds[k][0] <= v <= bounds[k][1] for k,v in values.items()):
        raise ValueError("Unsupported battle AI settings.")
    normal = audit.normalize(blob, base); delta = base-0x301000
    for address,size,digest in WINDOWS:
        start = address-0x301000
        if hashlib.sha256(normal[start:start+size]).hexdigest() != digest:
            raise ValueError("Battle AI refuses changed native code at "+hex(address)+".")
    def actual(address): return address+delta
    def raw(address,size): return blob[address-0x301000:address-0x301000+size]
    plans = []
    # The two half-distance samples used the original heading, not the
    # candidate heading. The port branch also accepted a blocked far sample.
    for address,old,new,label in (
        (0x925d61,"8b16","8bd7","Starboard midpoint follows candidate course"),
        (0x925dc9,"8b16","8bd7","Port midpoint follows candidate course"),
        (0x925de2,"7416","7516","Reject blocked port course, like starboard")):
        if raw(address,len(bytes.fromhex(old))).hex() != old: raise ValueError("Unknown coastal steering instruction.")
        plans.append(patch(label,actual(address),bytes.fromhex(old),bytes.fromhex(new)))
    air = []
    for address,size,allow,label in (
        (0x8cdb33,13,0x8cdb50,"Auto-battle carrier strike selection"),
        (0x8cd929,13,0x8cd950,"Auto-battle ready carrier strikes"),
        (0x8cdbe1,6,0x8cdbe7,"Auto-battle squadron strike permission"),
        (0x8cd8ff,6,0x8cd905,"Auto-battle ready squadron permission")):
        old = raw(address,size)
        prefix = old[:-2] if size==13 else b""
        opcode = old[-2] if size==13 else old[1]
        if opcode not in (0x74,0x84,0x75,0x85): raise ValueError("Unknown carrier permission branch.")
        target = actual(address+size+(struct.unpack("<b",old[-1:])[0] if size==13 else struct.unpack("<i",old[2:])[0]))
        air.append(dict(address=actual(address), original=old.hex(), prefix=prefix.hex(),
                        jcc=0x84 if opcode in (0x74,0x84) else 0x85,
                        target=target, continuation=actual(address+size), allow=actual(allow), label=label))
    dead = []
    for name,address,size,source,cleanup,stack_offset in (
        ("IsNiceTarget",0x90adcc,7,"edx",0,0),
        ("IsAcceptableTarget",0x90af58,6,"edx",0,0),
        ("FireMount",0x878cc4,9,"stack",20,20),
        ("FireGuns",0x907fe4,9,"ecx",20,0),
        ("FireMissileMount",0x8d4718,9,"stack",16,16)):
        if rt.method_address(blob,base,name) != actual(address): raise ValueError("Unexpected weapon target method.")
        expected = {"IsNiceTarget":"53565751880c24", "IsAcceptableTarget":"535657558bfa", "FireMount":"558bec51b907000000",
                    "FireGuns":"558bec51b94c000000", "FireMissileMount":"558bec51b90a000000"}[name]
        if raw(address,size).hex() != expected: raise ValueError("Weapon target entry is already modified.")
        dead.append(dict(name=name,address=actual(address),original=raw(address,size).hex(),source=source,cleanup=cleanup,stack_offset=stack_offset))
    if rt.method_address(blob,base,"sbAutoRunBattleClick") != actual(0x8d2824): raise ValueError("Unknown auto-battle controller.")
    if raw(0x89717d,10).hex() != "8b45fc83b8d200000000": raise ValueError("Unknown reattach rescue check.")
    def callee(site): return actual(site+5+struct.unpack("<i",raw(site+1,4))[0])
    # Every stance decision goes through these three calls to the per-type
    # chooser dispatcher; wrapping them is one choke point for commitment.
    stance_calls=[actual(a) for a in (0x865c68,0x87c0e2,0x88115d)]
    if any(raw(a-delta,1)!=b"\xe8" or callee(a-delta)!=actual(0x89108c) for a in stance_calls): raise ValueError("Unknown stance dispatcher call.")
    if raw(0x921844,6).hex()!="807b2f077513" or raw(0x87f06f,13).hex()!="8b4b75418b45cc99f7f98945cc" or raw(0x888b4c,9).hex()!="8bc703c03b45f87e78":
        raise ValueError("Unknown course, withdrawal or fire-comfort code.")
    # (site, native "not frustrated" continuation, frustrated CLOSE) for DD and CL.
    frustrated=[]
    for site,skip,go in ((0x88e51c,0x88e54e,0x88e525),(0x88bf1c,0x88bf4b,0x88bf25)):
        if raw(site,9).hex()!="8b435780781c0274"+bytes([skip-site-9]).hex(): raise ValueError("Unknown frustrated-hold branch.")
        frustrated.append(dict(site=actual(site),original=raw(site,9).hex(),skip=actual(skip),go=actual(go)))
    # Carriers with deck catapults launch strikes in the catapult state as CAP and search flights already
    # do (no turn into the wind; recovery still turns), and enemy presence no longer delays their launch.
    wind=None
    if values["catapult_strikes"]:
        for address in (0x964a41,0x964d82):   # jae: not CAP or search -> turn into the wind
            if raw(address,2)!=b"\x73\x1f":raise ValueError("Unknown carrier launch branch.")
            plans.append(patch("Catapult carriers launch strikes without turning into the wind",actual(address),b"\x73\x1f",b"\x90\x90"))
        if raw(0x9648f8,1)!=b"\xe8" or callee(0x9648f8)!=actual(0x918f14):raise ValueError("Unknown carrier wind check.")
        wind=dict(site=actual(0x9648f8),original=raw(0x9648f8,5).hex(),check=actual(0x918f14),catapults=actual(0x94f7fc))
    # "Enemy fire getting uncomfortable" turned big ships away when the enemy
    # was merely half as strong (2*enemy > own); require enemy > own instead.
    plans.append(patch("Big ships: uncomfortable-fire turn-away only when outgunned",actual(0x888b4e),b"\x03\xc0",b"\x8b\xc0"))
    # Full names and field-consumer windows above independently establish these
    # reference addresses. Normalize/relocate, never write reference addresses.
    return dict(settings=values,static_patches=plans,air_gates=air,dead_gates=dead,
                course_calls=[actual(0x865c72),actual(0x87c0ec)], course=actual(0x8668e4),
                flagship=actual(0x921468),
                damage=actual(0x921284),distance=actual(0x90f18c),bearing=actual(0x90de5c),
                clear_course=actual(0x925ca0),set_course=rt.method_address(blob,base,"SetNewCourse"),
                reports_slot=actual(0x9f6e34),minute_slot=actual(0x9f71b8),
                battle_form_slot=actual(0xa23274),auto_run_field=0x7e9,sunk_field=0xa9f,
                search=rt.method_address(blob,base,"SetAIAirSearchPlan"),
                start=actual(0x8d294f),start_original=raw(0x8d294f,9).hex(),
                capital_site=actual(0x86a709), capital_original=raw(0x86a709,6).hex(),
                capital_exit=actual(0x87293d), ship_distance=actual(0x8ecd20),
                trailing_ship=rt.method_address(blob,base,"GetTrailingShip"), main_gun_range=actual(0x90ab88),
                reattach_site=actual(0x89717d), reattach_original=raw(0x89717d,10).hex(),
                reattach_continue=actual(0x897187), reattach_refuse=actual(0x897189),
                max_speed=callee(0x87c5f0), fuel=callee(0x87c72a), ship_damage=callee(0x87c821),
                stance_calls=stance_calls, dispatcher=actual(0x89108c), closest_enemy=actual(0x910c6c),
                true_bearing_ship=rt.method_address(blob,base,"GetTrueBearingToShip"),
                course_site=actual(0x921844), course_hold=actual(0x92184a), course_other=actual(0x92185d),
                withdraw_site=actual(0x87f06f), withdraw_original=raw(0x87f06f,13).hex(), withdraw_exit=actual(0x87f07c),
                frustrated=frustrated, missile=missile_range.discover(blob,base), wind=wind,
                capital_blind_memory_pursuit=False,
                hidden_enemy_positions_read=False,spotting_changed=False,weapon_effects_changed=False,
                dormant_global_path_planner_enabled=False)


def air_thunk(address, state, info, gate):
    c=Code(address); c.emit(bytes.fromhex(gate["prefix"])+b"\x9c\x50\xa1"); c.u32(info["battle_form_slot"])
    c.emit(b"\x85\xc0"); c.branch(b"\x0f\x84","normal")
    c.emit(b"\x80\xb8"); c.u32(info["auto_run_field"]); c.emit(b"\x01"); c.branch(b"\x0f\x85","normal")
    c.emit(b"\xff\x05");c.u32(state+4);c.emit(b"\x58\x9d");c.branch(b"\xe9",gate["allow"])
    c.mark("normal"); c.emit(b"\x58\x9d");c.branch(bytes([0x0f,gate["jcc"]]),gate["target"])
    c.branch(b"\xe9",gate["continuation"]);return c.finish()


def wind_thunk(address, wind):
    """Replaces the launch's wind check call (EAX carrier): a carrier with deck catapults need not turn."""
    c=Code(address);c.emit(b"\x50");c.branch(b"\xe8",wind["catapults"]);c.emit(b"\x85\xc0\x58")
    c.branch(b"\x0f\x8e",wind["check"]);c.emit(b"\xb0\x01\xc3");return c.finish()


def air_start_thunk(address, info):
    c=Code(address);c.emit(bytes.fromhex("9c608b45fcb201"));c.branch(b"\xe8",info["search"])
    c.emit(b"\x61\x9d"+bytes.fromhex(info["start_original"]));c.branch(b"\xe9",info["start"]+9);return c.finish()


def dead_thunk(address, state, info, gate):
    c=Code(address);c.emit(b"\x9c\x50")
    c.emit(bytes([0x8b,0x44,0x24,gate["stack_offset"]+8]) if gate["source"]=="stack" else bytes.fromhex("8bc1" if gate["source"]=="ecx" else "8bc2"))
    c.emit(b"\x85\xc0");c.branch(b"\x0f\x84","native")
    c.emit(b"\x80\xb8");c.u32(info["sunk_field"]);c.emit(b"\x00");c.branch(b"\x0f\x84","native")
    c.emit(b"\xff\x05");c.u32(state+8);c.emit(b"\x58\x9d\x31\xc0")
    c.emit(b"\xc2"+struct.pack("<H",gate["cleanup"]) if gate["cleanup"] else b"\xc3")
    c.mark("native");c.emit(b"\x58\x9d"+bytes.fromhex(gate["original"]));c.branch(b"\xe9",gate["address"]+len(bytes.fromhex(gate["original"])));return c.finish()


def memory_thunk(address, state, info):
    # EAX = battle form, EDX = division. This replaces only two AI course
    # call sites, not manual orders or the visibility/weapon-selection paths.
    c=Code(address);c.emit(bytes.fromhex("9c6083ec208bda8bf8"))
    c.emit(b"\x85\xdb");c.branch(b"\x0f\x84","native")
    for field,value in ((0x30,1),(0x2f,7),(0x3a,0),(0x4d,0)):
        c.emit(bytes([0x80,0x7b,field,value]));c.branch(b"\x0f\x85","native")
    c.emit(bytes.fromhex("837b3c00"));c.branch(b"\x0f\x85","native")
    c.emit(bytes.fromhex("8b435785c0"));c.branch(b"\x0f\x84","native")
    c.emit(bytes.fromhex("80781c02"));c.branch(b"\x0f\x84","native")
    c.emit(bytes.fromhex("8b430d85c0"));c.branch(b"\x0f\x84","native")
    c.emit(bytes.fromhex("83780800"));c.branch(b"\x0f\x8e","native")
    c.emit(b"\x8b\xc3");c.branch(b"\xe8",info["damage"]);c.emit(b"\x83\xf8\x1e");c.branch(b"\x0f\x8d","native")
    c.emit(b"\x8b\xc3");c.branch(b"\xe8",info["flagship"]);c.emit(b"\x8b\xe8\x85\xed");c.branch(b"\x0f\x84","native")
    c.emit(bytes.fromhex("8b85d90a000085c0"));c.branch(b"\x0f\x84","native")
    c.emit(bytes.fromhex("83780800"));c.branch(b"\x0f\x85","native")
    # Surface combatants only; carriers/airfields, auxiliaries and transports
    # keep their own native navigation even if no enemies are currently seen.
    c.emit(bytes.fromhex("0fb685d3090000"))
    # B/BB/BC retain native force/objective navigation. A remembered contact
    # alone must not override their formation with a direct 45,000-yard chase.
    c.emit(b"\x83\xf8\x02");c.branch(b"\x0f\x86","native")
    c.emit(b"\x83\xf8\x04");c.branch(b"\x0f\x86","surface")
    c.emit(b"\x83\xf8\x09");c.branch(b"\x0f\x84","surface")
    c.emit(b"\x83\xf8\x0a");c.branch(b"\x0f\x85","native")
    c.mark("surface");c.emit(b"\xa1");c.u32(info["reports_slot"]);c.emit(b"\x85\xc0");c.branch(b"\x0f\x84","native")
    c.emit(b"\x8b\x00\x85\xc0");c.branch(b"\x0f\x84","native")
    c.emit(bytes.fromhex("8b480885c9"));c.branch(b"\x0f\x8e","native")
    c.emit(b"\x81\xf9");c.u32(4096);c.branch(b"\x0f\x87","native")
    c.emit(bytes.fromhex("894c24188b400489442410c744240400000000c7442408ffffff7fc744240cffffff7f"))
    c.emit(b"\xa1");c.u32(info["minute_slot"]);c.emit(bytes.fromhex("8b0089442414"))
    c.mark("loop");c.emit(bytes.fromhex("8b4424108b3085f6"));c.branch(b"\x0f\x84","next")
    # +7c is the report RECIPIENT side, not the reported ship's side. The
    # native air selector asks for the opposite side then excludes that side's
    # reports. Select our own reports directly; never use the opponent's intel.
    c.emit(bytes.fromhex("8b467c3b85550a0000"));c.branch(b"\x0f\x85","next")
    c.emit(bytes.fromhex("83f801"));c.branch(b"\x0f\x87","next")
    c.emit(bytes.fromhex("8b4424142b4678"));c.branch(b"\x0f\x88","next")
    c.emit(b"\x3d");c.u32(info["settings"]["contact_memory_minutes"]);c.branch(b"\x0f\x87","next")
    c.emit(bytes.fromhex("3b442408"));c.branch(b"\x0f\x87","next")
    c.emit(bytes.fromhex("8944241c"))
    # Require an actual surface-ship composition report, not a submarine or
    # aircraft-only contact. Never dereference its associated true-object +64.
    for field in range(0x88,0xa4,4):
        c.emit(b"\x83\xbe");c.u32(field);c.emit(b"\x00");c.branch(b"\x0f\x8f","ship_report")
    c.branch(b"\xe9","next")
    c.mark("ship_report");c.emit(bytes.fromhex("8d56548bc5"));c.branch(b"\xe8",info["distance"])
    c.emit(b"\x3d");c.u32(2000);c.branch(b"\x0f\x8c","next")
    c.emit(b"\x3d");c.u32(info["settings"]["memory_radius_yards"]);c.branch(b"\x0f\x87","next")
    c.emit(bytes.fromhex("8b54241c3b542408"));c.branch(b"\x0f\x82","choose")
    c.emit(bytes.fromhex("3b44240c"));c.branch(b"\x0f\x83","next")
    c.mark("choose");c.emit(bytes.fromhex("89742404895424088944240c"))
    c.mark("next");c.emit(bytes.fromhex("8344241004ff4c2418"));c.branch(b"\x0f\x85","loop")
    c.emit(bytes.fromhex("8b74240485f6"));c.branch(b"\x0f\x84","native")
    c.emit(bytes.fromhex("8d56548bc5"));c.branch(b"\xe8",info["bearing"]);c.emit(b"\x89\x04\x24")
    c.emit(bytes.fromhex("8d0424508bc5badc050000b9a0000000"));c.branch(b"\xe8",info["clear_course"])
    c.emit(b"\x84\xc0");c.branch(b"\x0f\x84","native")
    c.emit(bytes.fromhex("8bd48bc3"));c.branch(b"\xe8",info["set_course"])
    c.emit(b"\xff\x05");c.u32(state);c.emit(bytes.fromhex("83c420619dc3"))
    c.mark("native");c.emit(bytes.fromhex("83c420619d"));c.branch(b"\xe9",info["course"]);return c.finish()


def capital_thunk(address, state, info):
    """Filter only CLOSE/RAPID orders at the native tactical stance dispatch.

    Native frame: [EBX]=division, [EBP-24]=own flagship, ESI=current enemy.
    All original registers/flags survive. Escorts/objectives and emergency
    avoidance already handled before this dispatch retain their native paths.
    """
    c=Code(address);c.emit(bytes.fromhex("9c6083ec108b3b8b5ddc85ff"))
    c.branch(b"\x0f\x84","native")
    c.emit(bytes.fromhex("807f3001"));c.branch(b"\x0f\x85","native")
    c.emit(bytes.fromhex("807f3a02"));c.branch(b"\x0f\x87","native")  # independent/core/support
    c.emit(bytes.fromhex("0fb6472f83e80383f801"));c.branch(b"\x0f\x87","native")
    c.emit(bytes.fromhex("85db"));c.branch(b"\x0f\x84","native")
    c.emit(bytes.fromhex("80bbd309000002"));c.branch(b"\x0f\x87","native")
    c.emit(bytes.fromhex("80bb9f0a000000"));c.branch(b"\x0f\x85","native")
    c.emit(bytes.fromhex("85f6"));c.branch(b"\x0f\x84","native")
    # Prove membership BEFORE reading the enemy object. No world-list scan,
    # last-report live pointer or unspotted enemy position is consulted.
    c.emit(bytes.fromhex("8b83d90a000085c0"));c.branch(b"\x0f\x84","native")
    c.emit(bytes.fromhex("8b480885c9"));c.branch(b"\x0f\x8e","native")
    c.emit(b"\x81\xf9");c.u32(4096);c.branch(b"\x0f\x87","native")
    c.emit(bytes.fromhex("8b400485c0"));c.branch(b"\x0f\x84","native")
    c.mark("scan");c.emit(bytes.fromhex("3b30"));c.branch(b"\x0f\x84","known")
    c.emit(bytes.fromhex("83c00449"));c.branch(b"\x0f\x85","scan");c.branch(b"\xe9","native")
    c.mark("known");c.emit(bytes.fromhex("8b83550a000083f801"));c.branch(b"\x0f\x87","native")
    c.emit(bytes.fromhex("3b86550a0000"));c.branch(b"\x0f\x84","native")
    c.emit(bytes.fromhex("83be550a000001"));c.branch(b"\x0f\x87","native")
    c.emit(bytes.fromhex("80be9f0a000000"));c.branch(b"\x0f\x85","native")
    c.emit(bytes.fromhex("8bc38bd6"));c.branch(b"\xe8",info["ship_distance"])
    c.emit(bytes.fromhex("85c0"));c.branch(b"\x0f\x88","native");c.emit(bytes.fromhex("89442404"))
    # An assigned core/support division that has run >6,000 yards ahead of its
    # lead's trailing capital ship must regroup instead of charging alone.
    c.emit(bytes.fromhex("807f3a00"));c.branch(b"\x0f\x84","range")
    c.emit(bytes.fromhex("8b473c85c0"));c.branch(b"\x0f\x84","range")
    c.emit(bytes.fromhex("3bc7"));c.branch(b"\x0f\x84","range")
    c.emit(bytes.fromhex("8b500d85d2"));c.branch(b"\x0f\x84","range")
    c.emit(bytes.fromhex("837a0800"));c.branch(b"\x0f\x8e","range")
    c.branch(b"\xe8",info["trailing_ship"]);c.emit(b"\x85\xc0");c.branch(b"\x0f\x84","range")
    c.emit(bytes.fromhex("3bc3"));c.branch(b"\x0f\x84","range")
    c.emit(bytes.fromhex("80b8d309000002"));c.branch(b"\x0f\x87","range")
    c.emit(bytes.fromhex("80b89f0a000000"));c.branch(b"\x0f\x85","range")
    c.emit(bytes.fromhex("8b93550a00003990550a0000"));c.branch(b"\x0f\x85","range")
    c.emit(bytes.fromhex("894424088bd08bc3"));c.branch(b"\xe8",info["ship_distance"])
    c.emit(b"\x3d");c.u32(info["settings"]["capital_max_advance_yards"]);c.branch(b"\x0f\x8e","range")
    c.emit(bytes.fromhex("8b4424088bd6"));c.branch(b"\xe8",info["ship_distance"])
    c.emit(bytes.fromhex("2b4424043ddc050000"));c.branch(b"\x0f\x8e","range")
    c.emit(bytes.fromhex("8b54240881c21c0a00008bc3"));c.branch(b"\xe8",info["bearing"])
    c.emit(b"\x3d");c.u32(360);c.branch(b"\x0f\x87","hold")
    c.emit(bytes.fromhex("8944240c8d44240c508bc3badc050000b9a0000000"));c.branch(b"\xe8",info["clear_course"])
    c.emit(b"\x84\xc0");c.branch(b"\x0f\x84","hold")
    c.emit(bytes.fromhex("c6472f028d54240c8bc7"));c.branch(b"\xe8",info["set_course"])
    c.emit(b"\xff\x05");c.u32(state+16)
    c.emit(bytes.fromhex("83c410619d"));c.branch(b"\xe9",info["capital_exit"])
    # Hold once inside 75% of this ship's native main-gun range, rather than
    # force another charge. Short-range/unknown guns retain native decisions.
    c.mark("range");c.emit(bytes.fromhex("8bc3ba01000000"));c.branch(b"\xe8",info["main_gun_range"])
    c.emit(b"\x3d");c.u32(2000);c.branch(b"\x0f\x8c","native")
    c.emit(b"\x3d");c.u32(200000);c.branch(b"\x0f\x8f","native")
    c.emit(bytes.fromhex("69c0"));c.u32(info["settings"]["capital_gun_range_percent"])
    c.emit(bytes.fromhex("31d2b964000000f7f139442404"));c.branch(b"\x0f\x87","native")
    c.mark("hold");c.emit(bytes.fromhex("c6472f02ff05"));c.u32(state+12)
    c.mark("native");c.emit(bytes.fromhex("83c410619d")+bytes.fromhex(info["capital_original"]))
    c.branch(b"\xe9",info["capital_site"]+len(bytes.fromhex(info["capital_original"])));return c.finish()


def reattach_thunk(address, state, info):
    """Rejoin a detached ship only if the native detach checks would keep it.

    Native rejoins on proximity alone, so a low-fuel, crippled or slow ship is
    re-attached and detached again every check, turning back and forth all
    battle. [EBP-4] = detached division; its flagship +B1D = original division.
    """
    c=Code(address);c.emit(b"\x9c\x60\x8b\x45\xfc");c.branch(b"\xe8",info["flagship"])
    c.emit(b"\x8b\xd8\x8b\xb3");c.u32(0xb1d)
    c.emit(b"\x8b\xc3");c.branch(b"\xe8",info["fuel"]);c.emit(b"\x83\xf8\x0f");c.branch(b"\x0f\x8c","refuse")
    c.emit(b"\x8b\xc3");c.branch(b"\xe8",info["ship_damage"]);c.emit(b"\x83\xf8\x5a");c.branch(b"\x0f\x8f","refuse")
    c.emit(b"\x8b\xc3");c.branch(b"\xe8",info["max_speed"]);c.emit(b"\x8b\x56\x09\x83\xea\x02\x3b\xc2");c.branch(b"\x0f\x8c","refuse")
    c.emit(b"\x61\x9d"+bytes.fromhex(info["reattach_original"]));c.branch(b"\xe9",info["reattach_continue"])
    c.mark("refuse");c.emit(b"\xff\x05");c.u32(state+20);c.emit(b"\x61\x9d");c.branch(b"\xe9",info["reattach_refuse"])
    return c.finish()


def commit_thunk(address, state, info, table):
    """Replaces calls to the stance dispatcher: no HOLD/INCREASE/CLOSE flip-flop.

    Native re-rolls stances every few minutes (50/50 HOLD-or-INCREASE dice,
    out-of-range CLOSE vs uncomfortable-fire INCREASE), so divisions weave.
    Within N battle minutes of a recorded change only INCREASE->HOLD/CLOSE and
    HOLD->INCREASE/CLOSE are undone. Disengage, threat/torpedo avoidance,
    CLOSE RAPIDLY, leaving CLOSE, 30%+ damage and enemies inside 5,000 yards pass.
    Table entry (12 bytes): division, minute of change, stance chosen.
    """
    c=Code(address);c.emit(b"\x53\x56\x57\x55\x8b\xda\x0f\xb6\x73\x2f");c.branch(b"\xe8",info["dispatcher"])
    # Out of missiles: an AI division whose flagship has missile launchers, none of them with a missile left
    # (loaded or reload), and no main gun over EMPTY_GUN inches disengages (stance 0), as the native choosers do
    # for ships low on gun ammunition.
    c.emit(b"\x80\x7b\x30\x01");c.branch(b"\x0f\x85","armed")
    c.emit(b"\x8b\xc3");c.branch(b"\xe8",info["flagship"]);c.emit(b"\x85\xc0");c.branch(b"\x0f\x84","armed")
    c.emit(b"\x83\x78\x6d"+bytes([EMPTY_GUN]));c.branch(b"\x0f\x8f","armed")
    c.emit(b"\x8b\x88\x9e\x00\x00\x00\x85\xc9");c.branch(b"\x0f\x84","armed");c.emit(b"\x8b\x51\x08\x8b\x49\x04\x33\xed")
    c.mark("mount");c.emit(b"\x4a");c.branch(b"\x0f\x88","mounts");c.emit(b"\x8b\x04\x91\x0f\xb6\x78\x0e\x4f\x83\xff\x05")
    c.branch(b"\x0f\x87","mount");c.emit(b"\x45\x83\xb8\xf1\x00\x00\x00\x00");c.branch(b"\x0f\x8f","armed")
    c.emit(b"\x83\x78\x0f\x00");c.branch(b"\x0f\x8f","armed");c.branch(b"\xe9","mount")
    c.mark("mounts");c.emit(b"\x85\xed");c.branch(b"\x0f\x84","armed");c.emit(b"\xc6\x43\x2f\x00");c.branch(b"\xe9","done")
    c.mark("armed");c.emit(b"\x0f\xb6\x7b\x2f\x3b\xfe");c.branch(b"\x0f\x84","done")
    c.emit(b"\x80\x7b\x30\x01");c.branch(b"\x0f\x85","done")
    c.emit(b"\x8b\xeb\xc1\xed\x04\x81\xe5");c.u32(1023);c.emit(b"\x6b\xed\x0c\x81\xc5");c.u32(table)
    c.emit(b"\xa1");c.u32(info["minute_slot"]);c.emit(b"\x8b\x00")
    c.emit(b"\x83\xfe\x01");c.branch(b"\x0f\x84","from_increase")
    c.emit(b"\x83\xfe\x02");c.branch(b"\x0f\x85","record")
    c.emit(b"\x83\xff\x01");c.branch(b"\x0f\x84","check")
    c.emit(b"\x83\xff\x03");c.branch(b"\x0f\x84","check");c.branch(b"\xe9","record")
    c.mark("from_increase");c.emit(b"\x83\xff\x02");c.branch(b"\x0f\x84","check")
    c.emit(b"\x83\xff\x03");c.branch(b"\x0f\x85","record")
    # Only a still-current record of this division's last change can block.
    c.mark("check");c.emit(b"\x39\x5d\x00");c.branch(b"\x0f\x85","record")
    c.emit(b"\x39\x75\x08");c.branch(b"\x0f\x85","record")
    c.emit(b"\x8b\xc8\x2b\x4d\x04");c.branch(b"\x0f\x8c","record")
    c.emit(b"\x81\xf9");c.u32(info["settings"]["stance_commit_minutes"]);c.branch(b"\x0f\x8d","record")
    c.emit(b"\x50\x8b\xc3");c.branch(b"\xe8",info["damage"]);c.emit(b"\x83\xf8\x1e");c.branch(b"\x0f\x8d","pop_record")
    c.emit(b"\x8b\xc3");c.branch(b"\xe8",info["flagship"]);c.emit(b"\x85\xc0");c.branch(b"\x0f\x84","pop_record")
    c.emit(b"\x33\xd2");c.branch(b"\xe8",info["closest_enemy"]);c.emit(b"\x3d");c.u32(5000);c.branch(b"\x0f\x8c","pop_record")
    c.emit(b"\x58\x8b\xc6\x88\x43\x2f\xff\x05");c.u32(state+24);c.branch(b"\xe9","done")
    c.mark("pop_record");c.emit(b"\x58")
    c.mark("record");c.emit(b"\x89\x5d\x00\x89\x45\x04\x89\x7d\x08")
    c.mark("done");c.emit(b"\x5d\x5f\x5e\x5b\xc3");return c.finish()


def bow_thunk(address, state, info):
    """A capital that is not closing never steers bow-on at a nearby enemy heavy ship.

    Native rejoin/objective/home/report courses ignore the enemy, so a BB/BC on
    HOLD/INCREASE/DISENGAGE could sail into the enemy line. Inside the capital
    gun-range fraction, a course within 45 degrees of the nearest current
    contact (B/BB/BC/CA) turns to keep it 60 degrees off the bow, on the same
    side. EBX = division, ESI = course pointer already validated 0-360.
    """
    c=Code(address)
    if info.get("missile_course"):
        c.branch(b"\xe8",info["missile_course"])
    c.emit(b"\x9c\x60\x83\xec\x14\x80\x7b\x30\x01");c.branch(b"\x0f\x85","out")
    c.emit(b"\x8a\x43\x2f")
    for stance in (3,4,5,6):c.emit(b"\x3c"+bytes([stance]));c.branch(b"\x0f\x84","out")
    c.emit(b"\x8b\xc3");c.branch(b"\xe8",info["flagship"]);c.emit(b"\x85\xc0");c.branch(b"\x0f\x84","out")
    c.emit(b"\x8b\xf8\x80\xbf");c.u32(0x9d3);c.emit(b"\x02");c.branch(b"\x0f\x87","out")
    c.emit(b"\x80\xbf");c.u32(0xa9f);c.emit(b"\x00");c.branch(b"\x0f\x85","out")
    c.emit(b"\x8b\xc7\xba\x01\x00\x00\x00");c.branch(b"\xe8",info["main_gun_range"])
    c.emit(b"\x3d");c.u32(2000);c.branch(b"\x0f\x8c","out");c.emit(b"\x3d");c.u32(200000);c.branch(b"\x0f\x8f","out")
    c.emit(b"\x69\xc0");c.u32(info["settings"]["capital_gun_range_percent"])
    c.emit(b"\x33\xd2\xb9\x64\x00\x00\x00\xf7\xf1\x89\x04\x24\xc7\x44\x24\x04\x00\x00\x00\x00")
    # Current contacts only: never a world-list scan or a report's live pointer.
    c.emit(b"\x8b\x87");c.u32(0xad9);c.emit(b"\x85\xc0");c.branch(b"\x0f\x84","out")
    c.emit(b"\x8b\x48\x08\x85\xc9");c.branch(b"\x0f\x8e","out");c.emit(b"\x81\xf9");c.u32(4096);c.branch(b"\x0f\x87","out")
    c.emit(b"\x89\x4c\x24\x08\x8b\x40\x04\x85\xc0");c.branch(b"\x0f\x84","out");c.emit(b"\x89\x44\x24\x0c")
    c.mark("loop");c.emit(b"\x8b\x44\x24\x0c\x8b\x10\x85\xd2");c.branch(b"\x0f\x84","next")
    c.emit(b"\x8b\x82");c.u32(0xa55);c.emit(b"\x3b\x87");c.u32(0xa55);c.branch(b"\x0f\x84","next")
    c.emit(b"\x83\xf8\x01");c.branch(b"\x0f\x87","next")
    c.emit(b"\x80\xba");c.u32(0xa9f);c.emit(b"\x00");c.branch(b"\x0f\x85","next")
    c.emit(b"\x80\xba");c.u32(0x9d3);c.emit(b"\x03");c.branch(b"\x0f\x87","next")
    c.emit(b"\x89\x54\x24\x10\x8b\xc7");c.branch(b"\xe8",info["ship_distance"])
    c.emit(b"\x3b\x04\x24");c.branch(b"\x0f\x8d","next")
    c.emit(b"\x89\x04\x24\x8b\x44\x24\x10\x89\x44\x24\x04")
    c.mark("next");c.emit(b"\x83\x44\x24\x0c\x04\xff\x4c\x24\x08");c.branch(b"\x0f\x85","loop")
    c.emit(b"\x8b\x54\x24\x04\x85\xd2");c.branch(b"\x0f\x84","out")
    c.emit(b"\x8b\xc7");c.branch(b"\xe8",info["true_bearing_ship"])
    # EDX = course - bearing, normalized to -180..179; [ESP+18] = saved ESI.
    c.emit(b"\x8b\x4c\x24\x18\x8b\x11\x2b\xd0\x81\xfa");c.u32(180);c.branch(b"\x0f\x8c","n1");c.emit(b"\x81\xea");c.u32(360)
    c.mark("n1");c.emit(b"\x81\xfa");c.u32(-180&0xffffffff);c.branch(b"\x0f\x8d","n2");c.emit(b"\x81\xc2");c.u32(360)
    c.mark("n2");c.emit(b"\x83\xfa\x2d");c.branch(b"\x0f\x8d","out");c.emit(b"\x83\xfa\xd3");c.branch(b"\x0f\x8e","out")
    c.emit(b"\x85\xd2");c.branch(b"\x0f\x88","left");c.emit(b"\x83\xc0\x3c");c.branch(b"\xe9","wrap")
    c.mark("left");c.emit(b"\x83\xe8\x3c")
    c.mark("wrap");c.emit(b"\x85\xc0");c.branch(b"\x0f\x8d","n3");c.emit(b"\x05");c.u32(360)
    c.mark("n3");c.emit(b"\x3d");c.u32(360);c.branch(b"\x0f\x8c","n4");c.emit(b"\x2d");c.u32(360)
    c.mark("n4");c.emit(b"\x89\x01\xff\x05");c.u32(state+28)
    c.mark("out");c.emit(b"\x83\xc4\x14\x61\x9d\x80\x7b\x2f\x07");c.branch(b"\x0f\x85",info["course_other"])
    c.branch(b"\xe9",info["course_hold"]);return c.finish()


def withdraw_thunk(address, info):
    # Native escalates the force's withdrawal with chance score/(level+1) per
    # tick, so any lasting small disadvantage ends in a retreat. Ignore the
    # first points of score; clear disadvantages still escalate as before.
    c=Code(address);c.emit(b"\x8b\x45\xcc\x2d");c.u32(info["settings"]["withdraw_dead_zone"])
    c.emit(b"\x8b\x4b\x75\x41\x99\xf7\xf9\x89\x45\xcc");c.branch(b"\xe9",info["withdraw_exit"]);return c.finish()


def frustrated_thunk(address, state, info, gate):
    # A light division bored of holding out of range charged whatever it held
    # on, even an intact battleship in daylight, which the native daylight rule
    # then pulls back again. In daylight it no longer starts that charge at an
    # intact (<60% damaged) BB/BC/CA; torpedo attacks keep their own branch.
    c=Code(address);c.emit(b"\x8b\x43\x57\x80\x78\x1c\x02");c.branch(b"\x0f\x84",gate["skip"])
    c.emit(b"\x83\xbf");c.u32(0xb02);c.emit(b"\x01");c.branch(b"\x0f\x85",gate["go"])
    c.emit(b"\x80\xbe");c.u32(0x9d3);c.emit(b"\x04");c.branch(b"\x0f\x83",gate["go"])
    c.emit(b"\x8b\xc6");c.branch(b"\xe8",info["ship_damage"]);c.emit(b"\x83\xf8\x3c");c.branch(b"\x0f\x8d",gate["go"])
    c.emit(b"\xff\x05");c.u32(state+32);c.branch(b"\xe9",gate["skip"]);return c.finish()


def attach(wait=30, settings=None):
    import ai_runtime as ai
    import live_cheats as live
    import week_display as memory
    ai.checked_game();memory.configure();deadline=time.monotonic()+wait
    while True:
        games=[g for g in rt.process_candidates() if g[1]==rt.GAME/"RTW3.exe"]
        if len(games)==1:break
        if time.monotonic()>=deadline:raise ValueError("Start the local game with mods first.")
        time.sleep(.5)
    pid,_=games[0];handle=rt.K.OpenProcess(0x438,False,pid)
    if not handle:raise rt.win_error("Cannot open battle AI adapter")
    try:
        module,_=rt.module_info(pid)
        if REPORT.exists():
            old=json.loads(REPORT.read_text())
            if old.get("attached") and old.get("pid")==pid and old.get("base")==module and rt.report_is_current(REPORT,pid):
                if old.get("adapter_version",1)!=7:
                    raise ValueError("Restart through Play with mods to install the updated battle AI. No live battle hooks were changed.")
                ai.verify(handle,old["patches"],"replacement");return old
        base,blob=rt.text_section(handle,module);info=discover(blob,base,settings)
        guard=live.discover(blob,base);ai.require_title_screen(handle,guard)
        allocation=rt.K.VirtualAllocEx(handle,None,0x20000,0x3000,0x40)
        if not allocation:raise rt.win_error("Cannot allocate battle AI rules")
        state=allocation+0xf000;plans=list(info["static_patches"]);blocks=[];applied=[]
        def emit(offset,code):
            if len(code)>(0x1000 if offset==0 else 0x400):raise ValueError("Battle AI code exceeds its reserved area.")
            target=allocation+offset;memory.write(handle,target,code);rt.K.FlushInstructionCache(handle,target,len(code))
            blocks.append(dict(address=target,bytes=code.hex()));return target
        def detour(label,site,old,target,call=False):
            plans.append(patch(label,site,old,bytes([0xe8 if call else 0xe9])+struct.pack("<i",target-site-5)+b"\x90"*(len(old)-5)))
        try:
            missiles=missile_range.build(allocation,{**info,**info["missile"]},state)
            for block in missiles["blocks"]:
                code=bytes.fromhex(block["bytes"])
                memory.write(handle,block["address"],code)
                rt.K.FlushInstructionCache(handle,block["address"],len(code))
                blocks.append(block)
            plans.extend(missiles["patches"])
            info["missile_course"]=missiles["positions"]["course"]
            target=emit(0,memory_thunk(allocation,state,info))
            for site in info["course_calls"]:
                old=blob[site-base:site-base+5]
                if old[0]!=0xe8 or site+5+struct.unpack("<i",old[1:])[0]!=info["course"]:raise ValueError("AI course caller changed.")
                detour("Report-only last-contact navigation",site,old,target,True)
            for i,gate in enumerate(info["air_gates"]):
                offset=0x1000+i*0x400;target=emit(offset,air_thunk(allocation+offset,state,info,gate))
                detour(gate["label"],gate["address"],bytes.fromhex(gate["original"]),target)
            target=emit(0x2000,air_start_thunk(allocation+0x2000,info))
            detour("Native search plan when starting auto-battle",info["start"],bytes.fromhex(info["start_original"]),target)
            for i,gate in enumerate(info["dead_gates"]):
                offset=0x2400+i*0x400;target=emit(offset,dead_thunk(allocation+offset,state,info,gate))
                detour("No sunk targets: "+gate["name"],gate["address"],bytes.fromhex(gate["original"]),target)
            target=emit(0x3800,capital_thunk(allocation+0x3800,state,info))
            detour("Capital ships: gunnery distance and formation discipline",info["capital_site"],bytes.fromhex(info["capital_original"]),target)
            target=emit(0x3c00,reattach_thunk(allocation+0x3c00,state,info))
            detour("Detached ships: no low-fuel or straggler rejoin loop",info["reattach_site"],bytes.fromhex(info["reattach_original"]),target)
            # The stance table at +8000 starts zeroed by VirtualAllocEx: no records.
            target=emit(0x4000,commit_thunk(allocation+0x4000,state,info,allocation+0x8000))
            for site in info["stance_calls"]:
                detour("Stance commitment: no flip-flop within minutes",site,blob[site-base:site-base+5],target,True)
            target=emit(0x4400,bow_thunk(allocation+0x4400,state,info))
            detour("Capitals: no bow-on course at nearby enemy heavy ships",info["course_site"],bytes.fromhex("807b2f077513"),target)
            target=emit(0x4800,withdraw_thunk(allocation+0x4800,info))
            detour("Force withdrawal: ignore minor disadvantages",info["withdraw_site"],bytes.fromhex(info["withdraw_original"]),target)
            for i,gate in enumerate(info["frustrated"]):
                offset=0x4c00+i*0x400;target=emit(offset,frustrated_thunk(allocation+offset,state,info,gate))
                detour("Light ships: no daylight boredom charge at intact heavy ships",gate["site"],bytes.fromhex(gate["original"]),target)
            if info["wind"]:
                target=emit(0x5400,wind_thunk(allocation+0x5400,info["wind"]))
                detour("Catapult carriers: enemy presence does not delay launches",info["wind"]["site"],
                       bytes.fromhex(info["wind"]["original"]),target,True)
            ai.verify(handle,plans,"original")
            for p in plans:
                rt.write_code(handle,p["address"],bytes.fromhex(p["original"]),bytes.fromhex(p["replacement"]));applied.append(p)
            ai.verify(handle,plans,"replacement")
            saved=dict(attached=True,adapter_version=7,pid=pid,base=module,allocation=allocation,state=state,patches=plans,code_blocks=blocks,
                       details=info,missiles={k:v for k,v in missiles.items() if k not in ("blocks","patches")},
                       personal_saves_modified=False,battle_gameplay_verified=False)
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
