"""Regression tests using real native range, arc and missile launch routines."""
from pathlib import Path
import struct
import sys
import unittest

HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE/"vendor"),str(HERE.parent/"CampaignOverhaul")]
from unicorn import UC_HOOK_MEM_READ
from unicorn.x86_const import *
from test_missile_ai import World,BASE,CODE,DATA,STACK,FORM,DIV,SHIP,STOP,STATE
import battle_ai
import missile_range
import modern_research as audit


class NativeWorld(World):
    def __init__(self,blob):
        super().__init__(blob)
        self.vm.mem_map(0,0x1000)  # isolated Delphi SEH chain, not an OS surface
        self.corrected=missile_range.build(CODE,self.info,STATE)
        for block in self.corrected["blocks"]:
            self.vm.mem_write(block["address"],bytes.fromhex(block["bytes"]))
        for plan in self.corrected["patches"]:
            self.vm.mem_write(plan["address"],bytes.fromhex(plan["replacement"]))
        self.put(0x9F7328,DATA+0xA00);self.put(DATA+0xA00,1946)
        self.put(0x9F7008,DATA+0xA10);self.put(DATA+0xA10,2)
        self.put(0x9F7A0C,0xA7CB4E)
        for nation in (0,1):
            self.put(0xA7CBFC+nation*334,0)
            self.put(0xA7CC11+nation*334,0,1)
            self.put(0xA7CB4E+nation*334+0x8C,1,1)  # native SAM-vs-surface research
        self.native_launches=[]
        self.native_primitive_calls=set()
        self.geometry_distance=15000
        self.bearing=90
        self.put(SHIP+0xA28,90)
        self.put(SHIP+0xD49,DATA+0xD00);self.put(DATA+0xD00,CODE+0x1E000)
        self.put(FORM+0x7F8,DATA+0xD00)
        self.put(CODE+0x1E000+0x3C,CODE+0x1F000)
        self.put(CODE+0x1E000+0x40,CODE+0x1F000)
        self.vm.mem_write(CODE+0x1F000,b"\xc3")

    def native(self,m,a,size,unused):
        # Execute these critical routines from the retained native image.
        if a in (self.info["range"],self.info["arc"],self.info["minimum_range"],
                 self.info["fire"],self.info["selector"]):
            if hasattr(self,"native_primitive_calls"):self.native_primitive_calls.add(a)
            return
        eax=m.reg_read(UC_X86_REG_EAX);edx=m.reg_read(UC_X86_REG_EDX)
        ecx=m.reg_read(UC_X86_REG_ECX);sp=m.reg_read(UC_X86_REG_ESP)
        if a==0x876374:  # projectile allocation/flight boundary only
            self.native_launches.append(dict(side=edx,target=self.get(sp+24)))
            self.ret(0,28)
        elif a==0x307834:self.ret(0)  # deterministic native assessment roll
        elif a==0x90F18C:self.ret(self.geometry_distance)
        elif a==0x8D354C:self.ret(900)  # flight speed, not an eligibility decision
        elif a==self.info["true_bearing"]:
            self.active_target=edx;self.ret(self.bearing)
        elif a==0x90DE5C:self.ret(90)
        elif a==0x87F5E0:self.ret(0)
        elif a in (0x9045A8,0x9043D4,0x951E70):
            self.put(edx,0);self.ret()
        elif a in (0x30B8DC,0x30B93C,0x30BCCC,0x30BD14):
            self.put(eax,0);self.ret()
        elif a==0x30B9D0:self.ret(eax)
        elif a==0x30C71C:
            self.put(eax,0);self.ret(0,edx*4)
        elif a==0x32E008:
            self.put(ecx,0);self.ret(0,8)
        else:super().native(m,a,size,unused)

    def call(self,address,eax=FORM,edx=SHIP,ecx=0,ebx=0x2345,esi=DIV,args=()):
        sp=STACK+0x8000
        regs={UC_X86_REG_EAX:eax,UC_X86_REG_EDX:edx,UC_X86_REG_ECX:ecx,
              UC_X86_REG_EBX:ebx,UC_X86_REG_ESI:esi,UC_X86_REG_EDI:0x4567,
              UC_X86_REG_EBP:STACK+0x9000,UC_X86_REG_ESP:sp,UC_X86_REG_EFLAGS:0x246}
        for r,v in regs.items():self.vm.reg_write(r,v)
        self.vm.mem_write(sp,struct.pack('<'+'I'*(len(args)+1),STOP,*args))
        self.vm.emu_start(address,STOP,count=100000)
        assert self.vm.reg_read(UC_X86_REG_EIP)==STOP
        assert self.vm.reg_read(UC_X86_REG_ESP)==sp+4+4*len(args)
        for r in (UC_X86_REG_EBX,UC_X86_REG_ESI,UC_X86_REG_EDI,UC_X86_REG_EBP):
            assert self.vm.reg_read(r)==regs[r]
        return self.vm.reg_read(UC_X86_REG_EAX)

    def course(self,proposed=90):
        ptr=DATA+0xE00;self.put(ptr,proposed)
        self.call(self.corrected["positions"]["course"],ebx=DIV,esi=ptr)
        return self.get(ptr)


class MissileRangeRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.blob=(HERE/"native-designer-inspection.text.bin").read_bytes()
    def world(self):return NativeWorld(self.blob)

    def test_native_1946_ranges_are_used_instead_of_mocked_50000_yards(self):
        w=self.world()
        for mode,expected in ((4,25000),(5,20000),(6,6000)):
            mounts=w.ship(SHIP,mounts=((mode,8,4,0),))
            w.put(mounts[0]+8,ord('P'),2)
            self.assertEqual(w.call(w.corrected['positions']['ready'],SHIP),expected)

    def test_screen_role_four_gets_real_away_course_despite_long_gun_range(self):
        w=self.world();w.ship(SHIP,mounts=((5,8,4,0),));w.guns=45000
        target=w.target();w.see(SHIP,[target],10000);w.put(DIV+0x3A,4,1)
        self.assertEqual(w.course(90),270)
        self.assertEqual(w.get(DIV+0x2F,1),1)

    def test_near_enemy_is_opened_from_instead_of_ignored_below_5000(self):
        w=self.world();w.see(SHIP,[w.target()],3000)
        self.assertEqual(w.course(90),270)

    def test_in_range_uses_beam_course_and_outside_range_remains_native(self):
        w=self.world();w.ship(SHIP,mounts=((5,8,4,0),));w.put(SHIP+0xA28,0)
        w.see(SHIP,[w.target()],16000);self.assertEqual(w.course(90),0)
        self.assertEqual(w.get(DIV+0x2F,1),2)
        w=self.world();w.ship(SHIP,mounts=((5,8,4,0),));w.see(SHIP,[w.target()],19000)
        self.assertEqual(w.course(90),90)

    def test_rapid_close_and_no_enemy_labels_cannot_override_current_contacts(self):
        for stance in (4,7):
            w=self.world();w.put(DIV+0x2F,stance,1);w.see(SHIP,[w.target()],10000)
            self.assertEqual(w.course(90),270)

    def test_manual_retreat_threat_torpedo_orders_and_empty_ammo_unchanged(self):
        for field,value in ((0x30,0),(0x2F,0),(0x2F,5),(0x2F,6),(0x4D,1),(0x3A,5)):
            w=self.world();w.put(DIV+field,value,1);w.see(SHIP,[w.target()],10000)
            self.assertEqual(w.course(90),90,(field,value))
        w=self.world();w.ship(SHIP,mounts=((5,0,4,0),));w.see(SHIP,[w.target()],10000)
        self.assertEqual(w.course(90),90)

    def test_known_membership_and_both_sides_respected(self):
        for side in (0,1):
            w=self.world();w.ship(SHIP,side);w.see(SHIP,[w.target(side=1-side)],10000)
            self.assertEqual(w.course(90),270)
        w=self.world();w.target();w.see(SHIP,[]);self.assertEqual(w.course(),90)
        w=self.world();w.see(SHIP,[w.target(side=0)],10000);self.assertEqual(w.course(),90)

    def test_firing_replacement_and_salvo_throttles_are_not_installed(self):
        w=self.world();self.assertFalse(w.corrected['custom_firing_selector_installed'])
        self.assertFalse(w.corrected['custom_salvo_throttles_installed'])
        self.assertNotIn(0x87945A,[p['address'] for p in w.corrected['patches']])
        self.assertTrue(w.corrected['native_sam_surface_fire_preserved'])
        self.assertEqual(bytes(w.vm.mem_read(0x87945A,5)),self.blob[0x87945A-BASE:0x87945A-BASE+5])

    def test_native_selector_without_missile_research_does_not_scan_the_ship_list(self):
        w=self.world();w.see(SHIP,[])
        # The global world list remains an unreadable pointer: the fallback needs the nation's research first.
        w.call(w.info['selector'])

    def test_the_global_search_runs_again_but_never_picks_a_friendly_ship(self):
        from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
        w=self.world()
        self.assertEqual(bytes(w.vm.mem_read(0x87730A,10)),self.blob[0x87730A-BASE:0x87730A-BASE+10])   # not skipped
        patched=bytearray(self.blob)
        for p in w.corrected['patches']:
            new=bytes.fromhex(p['replacement']);patched[p['address']-BASE:p['address']-BASE+len(new)]=new
        def landing(code,side):   # from the candidate's side check: 0x8775B4 next ship, 0x8773D2 goes on as a target
            vm=Uc(UC_ARCH_X86,UC_MODE_32);vm.mem_map(0x300000,0x800000);vm.mem_map(STACK,0x10000);vm.mem_map(DATA,0x40000)
            vm.mem_write(0x301000,bytes(code))
            shooter,candidate,frame=DATA+0x1000,DATA+0x2000,STACK+0x9000
            vm.mem_write(shooter+0xA55,struct.pack('<I',0));vm.mem_write(candidate+0xA55,struct.pack('<I',side))
            vm.mem_write(frame-8,struct.pack('<II',shooter,candidate))
            vm.reg_write(UC_X86_REG_EBP,frame);vm.reg_write(UC_X86_REG_ESP,STACK+0x8000)
            stops=[]
            def hook(m,a,size,_):
                if a==0x307834:   # Random(500) gives 1: the native one-in-500 friendly target
                    sp=m.reg_read(UC_X86_REG_ESP);m.reg_write(UC_X86_REG_EAX,1)
                    m.reg_write(UC_X86_REG_EIP,int.from_bytes(m.mem_read(sp,4),'little'));m.reg_write(UC_X86_REG_ESP,sp+4)
                elif a in (0x8775B4,0x8773D2):stops.append(a);m.emu_stop()
            vm.hook_add(UC_HOOK_CODE,hook);vm.emu_start(0x8773AD,0,count=20)
            return stops[0]
        self.assertEqual([landing(self.blob,side) for side in (0,1)],[0x8773D2,0x8773D2])
        self.assertEqual([landing(patched,side) for side in (0,1)],[0x8775B4,0x8773D2])

    def test_missile_blind_fire_answers_a_launch_for_ten_minutes(self):
        from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
        w=self.world();built=w.corrected
        vm=Uc(UC_ARCH_X86,UC_MODE_32)
        for a,n in ((0x300000,0x800000),(CODE,0x20000),(DATA,0x40000),(STACK,0x10000)):vm.mem_map(a,n)
        vm.mem_write(0x301000,self.blob)
        for b in built['blocks']:vm.mem_write(b['address'],bytes.fromhex(b['bytes']))
        for p in built['patches']:vm.mem_write(p['address'],bytes.fromhex(p['replacement']))
        clock,launcher,other,frame=DATA+0x800,DATA+0x10000,DATA+0x20000,STACK+0x9000
        vm.mem_write(w.info['minute_slot'],struct.pack('<I',clock))
        def put(a,v):vm.mem_write(a,struct.pack('<I',v))
        def run(start,stops,**regs):
            for r,v in regs.items():vm.reg_write(globals()['UC_X86_REG_'+r],v)
            vm.reg_write(UC_X86_REG_ESP,STACK+0x8000);hit=[]
            def hook(m,a,size,_):
                if a in stops:hit.append(a);m.emu_stop()
            h=vm.hook_add(UC_HOOK_CODE,hook);vm.emu_start(start,0,count=1000);vm.hook_del(h)
            return hit[0]
        put(clock,100)
        self.assertEqual(run(0x876374,(0x87637A,),ECX=launcher+0xA1C),0x87637A)   # FireSSM: recorded, native body next
        sighted,helper=0x8773ED,0x8773DE                                               # the search's two ways on
        for now,seen,landing in ((100,0,sighted),(110,0,sighted),(111,0,helper),(99,0,helper),(130,2,sighted)):
            put(clock,now);put(launcher+0xD55,seen);put(frame-4,launcher)
            self.assertEqual(run(0x8773D2,(helper,sighted),EBP=frame),landing,(now,seen))
        put(clock,100);put(other+0xD55,0);put(frame-4,other)
        self.assertEqual(run(0x8773D2,(helper,sighted),EBP=frame),helper)              # never launched: native check
        # A new battle (its clock starts again) forgets the last one's launches: its ships may reuse their addresses.
        run(0x876374,(0x87637A,),ECX=launcher+0xA1C)
        self.assertEqual(vm.reg_read(UC_X86_REG_ECX),launcher+0xA1C)                  # FireSSM keeps its ECX
        put(clock,0);self.assertEqual(run(0x8773D2,(helper,sighted),EBP=frame),helper)
        put(clock,104);put(launcher+0xD55,0);put(frame-4,launcher)
        self.assertEqual(run(0x8773D2,(helper,sighted),EBP=frame),helper)              # minute 100 was the last battle's
        run(0x876374,(0x87637A,),ECX=launcher+0xA1C);put(clock,106)
        self.assertEqual(run(0x8773D2,(helper,sighted),EBP=frame),sighted)             # this battle's launch counts

    def test_real_native_missile_launch_and_ammo_consumption(self):
        for mode in (4,5):
            w=self.world();mount=w.ship(SHIP,mounts=((mode,20,4,0),))[0]
            w.put(mount+8,ord('P'),2);target=w.target();w.see(SHIP,[target],15000)
            w.call(0x877CCC,ecx=target,args=(1,))
            self.assertGreater(len(w.native_launches),0)
            self.assertLess(w.get(mount+0xF1),20)
            self.assertIn(w.info['range'],w.native_primitive_calls)
            self.assertIn(w.info['arc'],w.native_primitive_calls)

    def test_complete_native_automatic_contact_selector_reaches_real_firing(self):
        w=self.world();mount=w.ship(SHIP,mounts=((5,40,4,0),))[0]
        w.put(mount+8,ord('P'),2);target=w.target(kind=5);w.see(SHIP,[target],15000)
        w.call(w.info['selector'])
        self.assertGreater(len(w.native_launches),0)
        self.assertLess(w.get(mount+0xF1),40)
        self.assertIn(w.info['fire'],w.native_primitive_calls)

    def test_native_minimum_range_prevents_impossible_close_missile_shots(self):
        w=self.world();mount=w.ship(SHIP,mounts=((5,20,4,0),))[0]
        w.put(mount+8,ord('P'),2);target=w.target();w.see(SHIP,[target],5000)
        w.geometry_distance=5000;w.call(0x877CCC,ecx=target,args=(1,))
        self.assertEqual(w.native_launches,[])
        self.assertEqual(w.get(mount+0xF1),20)

    def test_reserve_sam_surface_fire_is_left_to_native_research_rules(self):
        w=self.world();mount=w.ship(SHIP,mounts=((1,30,2,0),))[0]
        w.put(mount+8,ord('P'),2);target=w.target();w.see(SHIP,[target],15000)
        w.call(0x877CCC,ecx=target,args=(1,))
        self.assertGreater(len(w.native_launches),0)
        self.assertLess(w.get(mount+0xF1),30)

    def test_course_hook_is_on_real_course_path_and_preserves_native_continuation(self):
        w=self.world();info=dict(w.info,missile_course=w.corrected['positions']['course'])
        wrapper=CODE+0x4400;w.vm.mem_write(wrapper,battle_ai.bow_thunk(wrapper,STATE,info))
        w.see(SHIP,[w.target()],10000);ptr=DATA+0xE00;w.put(ptr,90)
        # Stop at native continuation, before its unchanged terrain checks.
        def stop(m,a,size,u):
            if a in (info['course_hold'],info['course_other']):m.emu_stop()
        from unicorn import UC_HOOK_CODE
        token=w.vm.hook_add(UC_HOOK_CODE,stop)
        w.vm.reg_write(UC_X86_REG_EBX,DIV);w.vm.reg_write(UC_X86_REG_ESI,ptr)
        w.vm.reg_write(UC_X86_REG_ESP,STACK+0x8000)
        w.vm.emu_start(wrapper,0,count=10000);w.vm.hook_del(token)
        self.assertEqual(w.get(ptr),270)
        self.assertEqual(w.vm.reg_read(UC_X86_REG_EIP),info['course_other'])

    def test_course_wraps_correctly_around_north(self):
        for bearing,heading,expected in ((359,359,89),(10,5,280)):
            w=self.world();w.bearing=bearing;w.ship(SHIP,mounts=((5,8,4,0),))
            w.put(SHIP+0xA28,heading);w.see(SHIP,[w.target()],16000)
            self.assertEqual(w.course(90),expected)

    def test_real_native_wing_arc_selects_the_other_beam_to_allow_firing(self):
        w=self.world();mount=w.ship(SHIP,mounts=((5,8,4,0),))[0]
        w.put(mount+8,ord('J'),2);w.put(SHIP+0xA28,0)
        self.assertEqual(w.call(w.info['arc'],mount,90),0)
        self.assertEqual(w.call(w.info['arc'],mount,270),1)
        w.see(SHIP,[w.target()],16000)
        self.assertEqual(w.course(90),180)

    def test_relocated_image_and_changed_native_windows(self):
        delta=0x400000;blob=bytearray(self.blob)
        for offset in audit.text_relocations():
            value=struct.unpack_from('<I',blob,offset)[0]
            struct.pack_into('<I',blob,offset,(value+delta)&0xFFFFFFFF)
        info=missile_range.discover(bytes(blob),BASE+delta)
        self.assertEqual(info['friendly_site'],0x8773C1+delta)
        for address,_,_ in missile_range.WINDOWS:
            changed=bytearray(self.blob);changed[address-BASE]^=1
            with self.assertRaises(ValueError):missile_range.discover(bytes(changed),BASE)


if __name__=='__main__':unittest.main()
