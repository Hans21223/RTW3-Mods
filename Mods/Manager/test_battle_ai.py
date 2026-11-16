"""Execute battle AI rules in isolation, with no real game or campaign writes."""
from pathlib import Path
import struct
import sys
import unittest

HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE/"vendor"),str(HERE.parent/"CampaignOverhaul")]
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import *
import battle_ai as ai
import modern_research as audit

CODE,DATA,STACK,STATE=0x1200000,0x1300000,0x1500000,0x1330000
STOP=CODE+0xf000


class BattleAITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blob=(HERE/"native-designer-inspection.text.bin").read_bytes()
        cls.info=ai.discover(cls.blob,0x301000)

    def vm(self):
        m=Uc(UC_ARCH_X86,UC_MODE_32)
        for a,n in ((0x300000,0x800000),(CODE,0x10000),(DATA,0x40000),(STACK,0x10000)):m.mem_map(a,n)
        for reg,value in ((UC_X86_REG_EAX,DATA),(UC_X86_REG_EDX,DATA+0x1000),(UC_X86_REG_ECX,0x1234),
                (UC_X86_REG_EBX,0x2345),(UC_X86_REG_ESI,0x3456),(UC_X86_REG_EDI,0x4567),
                (UC_X86_REG_EBP,STACK+0x9000),(UC_X86_REG_ESP,STACK+0x8000),(UC_X86_REG_EFLAGS,0x246)):
            m.reg_write(reg,value)
        self.put(m,STACK+0x8000,STOP)
        return m

    def put(self,m,address,value,width=4):m.mem_write(address,(value&((1<<(width*8))-1)).to_bytes(width,"little"))
    def get(self,m,address):return int.from_bytes(m.mem_read(address,4),"little")

    def execute(self,m,start,*ends,callback=None):
        def hook(vm,address,size,_):
            if address in ends:vm.emu_stop()
            elif callback:callback(vm,address)
        token=m.hook_add(UC_HOOK_CODE,hook)
        try:m.emu_start(start,0,count=300000)
        finally:m.hook_del(token)
        self.assertIn(m.reg_read(UC_X86_REG_EIP),ends)
        return m.reg_read(UC_X86_REG_EIP)

    def ret(self,m,value=None,cleanup=0):
        if value is not None:m.reg_write(UC_X86_REG_EAX,value)
        sp=m.reg_read(UC_X86_REG_ESP);dest=self.get(m,sp)
        m.reg_write(UC_X86_REG_ESP,sp+4+cleanup);m.reg_write(UC_X86_REG_EIP,dest)

    def test_native_navigation_port_far_point_is_rejected_not_selected(self):
        # Original selects 80 despite its far point being blocked. Correct
        # steering must keep searching and select the clear 70-degree course.
        def blocked(course,distance):return course!=70 and not (course in (80,90) and distance==500)
        self.assertEqual(self.navigation(blocked,patched=False), (1,80))
        self.assertEqual(self.navigation(blocked), (1,70))

    def test_native_navigation_midpoints_use_the_candidate_in_both_directions(self):
        for desired in (100,80):
            def blocked(course,distance):return course!=desired
            self.assertEqual(self.navigation(blocked), (1,desired))
        self.assertEqual(self.navigation(lambda c,d:True), (0,90))
        self.assertEqual(self.navigation(lambda c,d:False), (1,90))

    def navigation(self,blocked,patched=True):
        m=self.vm();a=0x925ca0;m.mem_write(a,self.blob[a-0x301000:a-0x301000+0x17e])
        if patched:
            for p in self.info["static_patches"]:m.mem_write(p["address"],bytes.fromhex(p["replacement"]))
        self.put(m,STACK+0x8004,DATA+0x3000);self.put(m,DATA+0x3000,90)
        m.reg_write(UC_X86_REG_EAX,DATA);m.reg_write(UC_X86_REG_EDX,1000);m.reg_write(UC_X86_REG_ECX,40)
        def native(vm,address):
            if address==0x8ec340:
                x=vm.reg_read(UC_X86_REG_EAX);y=vm.reg_read(UC_X86_REG_EDX);y=y if y<0x80000000 else y-0x100000000
                self.ret(vm,(x+y)%360)
            elif address==0x9261d4:
                p=self.get(vm,vm.reg_read(UC_X86_REG_ESP)+4)
                vm.mem_write(p,struct.pack("<III",vm.reg_read(UC_X86_REG_EDX),vm.reg_read(UC_X86_REG_ECX),0));self.ret(vm,cleanup=4)
            elif address==0x9269cc:
                p=vm.reg_read(UC_X86_REG_EAX);self.ret(vm,int(blocked(self.get(vm,p),self.get(vm,p+4))))
        self.execute(m,a,STOP,callback=native)
        self.assertEqual(m.reg_read(UC_X86_REG_ESP),STACK+0x8008)
        return m.reg_read(UC_X86_REG_EAX)&0xff,self.get(m,DATA+0x3000)

    def test_air_permissions_preserve_manual_mode_and_allow_autobattle(self):
        for gate in self.info["air_gates"]:
            for automatic in (0,1):
                for native_allowed in (False,True):
                    m=self.vm();form=DATA+0x100;group=DATA+0x1000
                    self.put(m,self.info["battle_form_slot"],form);self.put(m,form+self.info["auto_run_field"],automatic,1)
                    self.put(m,0x9f7008,DATA+0x200);self.put(m,DATA+0x200,0)
                    self.put(m,group+0x38,int(native_allowed));m.reg_write(UC_X86_REG_EBX,group)
                    # For the squadron JE gates, zero means native rejection.
                    m.reg_write(UC_X86_REG_EFLAGS,0x202 if native_allowed else 0x242)
                    m.mem_write(CODE,ai.air_thunk(CODE,STATE,self.info,gate))
                    end=self.execute(m,CODE,gate["target"],gate["continuation"],gate["allow"])
                    expected=gate["allow"] if automatic or native_allowed else (gate["continuation"] if gate["prefix"] else gate["target"])
                    self.assertEqual(end,expected,(gate["label"],automatic,native_allowed))
                    self.assertEqual(m.reg_read(UC_X86_REG_ESP),STACK+0x8000)
                    self.assertEqual(self.get(m,STATE+4),automatic)
                    self.assertEqual(m.reg_read(UC_X86_REG_ECX),0x1234)
                    self.assertEqual(m.reg_read(UC_X86_REG_EBX),group)

    def test_air_search_plan_is_initialized_once_on_autobattle_start(self):
        m=self.vm();form=DATA+0x100;self.put(m,STACK+0x9000-4,form)
        self.put(m,form+0x4d4,DATA+0x200)
        m.mem_write(CODE,ai.air_start_thunk(CODE,self.info));calls=[]
        def native(vm,address):
            if address==self.info["search"]:
                calls.append((vm.reg_read(UC_X86_REG_EAX),vm.reg_read(UC_X86_REG_EDX)&0xff));self.ret(vm)
        self.execute(m,CODE,self.info["start"]+9,callback=native)
        self.assertEqual(calls,[(form,1)])
        self.assertEqual(m.reg_read(UC_X86_REG_EAX),DATA+0x200)
        self.assertEqual(m.reg_read(UC_X86_REG_ECX),0x1234)

    def memory_fixture(self,reports,side=0):
        m=self.vm();d=DATA+0x1000;ship=DATA+0x2000;force=DATA+0x4000
        self.put(m,d+0x30,1,1);self.put(m,d+0x2f,7,1);self.put(m,d+0x57,force)
        self.put(m,d+0xd,DATA+0x5000);self.put(m,DATA+0x5008,1)
        self.put(m,ship+0x9d3,3,1);self.put(m,ship+0xa55,side)
        self.put(m,ship+0xad9,DATA+0x7000)
        self.put(m,self.info["minute_slot"],DATA+0x800);self.put(m,DATA+0x800,100)
        self.put(m,self.info["reports_slot"],DATA+0x8000);self.put(m,DATA+0x8000,DATA+0x9000)
        self.put(m,DATA+0x9004,DATA+0xa000);self.put(m,DATA+0x9008,len(reports))
        for i,r in enumerate(reports):
            p=DATA+0x10000+i*0x200;self.put(m,DATA+0xa000+i*4,p)
            self.put(m,p+0x7c,r.get("recipient",side));self.put(m,p+0x78,100-r.get("age",5))
            self.put(m,p+0x88,r.get("ships",1));self.put(m,p+0x64,0xdeadc000) # Never readable true object.
            m.mem_write(p+0x54,struct.pack("<III",r.get("distance",10000),r.get("course",120),0))
        m.mem_write(CODE,ai.memory_thunk(CODE,STATE,self.info));calls=[]
        def native(vm,address):
            eax=vm.reg_read(UC_X86_REG_EAX);edx=vm.reg_read(UC_X86_REG_EDX)
            if address==self.info["damage"]:self.ret(vm,self.get(vm,DATA+0x900))
            elif address==self.info["flagship"]:self.ret(vm,ship)
            elif address==self.info["distance"]:self.ret(vm,self.get(vm,edx))
            elif address==self.info["bearing"]:self.ret(vm,self.get(vm,edx+4))
            elif address==self.info["clear_course"]:self.ret(vm,0 if self.get(vm,DATA+0x904) else 1,4)
            elif address==self.info["set_course"]:
                course=self.get(vm,edx);calls.append(course);self.put(vm,eax+4,course);self.ret(vm)
        return m,calls,native

    def memory(self,reports,side=0,change=None):
        m,calls,native=self.memory_fixture(reports,side)
        if change:change(m)
        end=self.execute(m,CODE,STOP,self.info["course"],callback=native)
        self.assertEqual(m.reg_read(UC_X86_REG_EDX),DATA+0x1000)
        self.assertEqual(m.reg_read(UC_X86_REG_ECX),0x1234)
        self.assertEqual(m.reg_read(UC_X86_REG_EBX),0x2345)
        self.assertEqual(m.reg_read(UC_X86_REG_ESI),0x3456)
        self.assertEqual(m.reg_read(UC_X86_REG_EDI),0x4567)
        self.assertEqual(m.reg_read(UC_X86_REG_EBP),STACK+0x9000)
        self.assertEqual(m.reg_read(UC_X86_REG_ESP),STACK+0x8004 if calls else STACK+0x8000)
        return end,calls

    def test_memory_uses_only_report_coordinates_symmetrically(self):
        for side in (0,1):
            self.assertEqual(self.memory([dict(age=4,course=123)],side), (STOP,[123]))
        # Freshest report wins, distance breaks ties; foreign and stale
        # reports cannot override it. No true-object pointer is ever read.
        records=[dict(age=19,course=30),dict(age=3,distance=20000,course=80),dict(age=3,distance=12000,course=90),
                 dict(age=1,recipient=1,course=10),dict(age=21,course=20)]
        self.assertEqual(self.memory(records),(STOP,[90]))

    def test_memory_rejects_expired_future_foreign_air_only_and_far_reports(self):
        for records in ([],[dict(age=21)],[dict(age=-1)],[dict(recipient=1)],[dict(ships=0)],
                        [dict(distance=45001)],[dict(distance=1500)]):
            self.assertEqual(self.memory(records),(self.info["course"],[]))

    def test_capitals_do_not_get_the_blind_report_chase_override(self):
        for kind in (0,1,2):
            for side in (0,1):
                self.assertEqual(self.memory([dict(distance=15000,course=90)],side,
                    change=lambda m:self.put(m,DATA+0x29d3,kind,1)),(self.info["course"],[]))

    def test_memory_respects_manual_retreat_escort_visible_and_damaged_conditions(self):
        for address,value,width in ((DATA+0x1030,0,1),(DATA+0x102f,2,1),(DATA+0x103a,1,1),
                (DATA+0x104d,1,1),(DATA+0x103c,1,4),(DATA+0x401c,2,1),
                (DATA+0x7008,1,4),(DATA+0x29d3,5,1),(DATA+0x900,35,4),(DATA+0x904,1,4)):
            with self.subTest(address=hex(address)):
                self.assertEqual(self.memory([{}],change=lambda m:self.put(m,address,value,width)),(self.info["course"],[]))

    def test_sunk_target_selection_and_final_fire_guard_with_stack_cleanup(self):
        for gate in self.info["dead_gates"]:
            for sunk in (0,1):
                m=self.vm();target=DATA+0x1000;self.put(m,target+self.info["sunk_field"],sunk,1)
                # Heavy damage is not a kill; no other target field may matter.
                self.put(m,target+0xb35,999)
                if gate["source"]=="stack":self.put(m,STACK+0x8000+gate["stack_offset"],target)
                else:m.reg_write(UC_X86_REG_ECX if gate["source"]=="ecx" else UC_X86_REG_EDX,target)
                m.mem_write(CODE,ai.dead_thunk(CODE,STATE,self.info,gate))
                native=gate["address"]+len(bytes.fromhex(gate["original"]))
                self.assertEqual(self.execute(m,CODE,STOP,native),STOP if sunk else native)
                self.assertEqual(self.get(m,STATE+8),sunk)
                if sunk:
                    self.assertEqual(m.reg_read(UC_X86_REG_ESP),STACK+0x8004+gate["cleanup"])
                    self.assertEqual(m.reg_read(UC_X86_REG_EAX),0)

    def test_catapult_carriers_launch_strikes_without_turning_into_the_wind(self):
        wind=self.info["wind"];labels=[p["label"] for p in self.info["static_patches"]]
        self.assertEqual(labels.count("Catapult carriers launch strikes without turning into the wind"),2)
        native=ai.discover(self.blob,0x301000,{"catapult_strikes":0})
        self.assertIsNone(native["wind"])
        self.assertFalse([p for p in native["static_patches"] if "Catapult" in p["label"]])
        for site in (0x964a41,0x964d82):                  # the strike branch now falls through to the catapult test
            item=next(p for p in self.info["static_patches"] if p["address"]==site)
            self.assertEqual((item["original"],item["replacement"]),("731f","9090"))
        for catapults,expected in ((2,"launch"),(0,"native check")):
            m=self.vm();m.mem_write(CODE,ai.wind_thunk(CODE,wind))
            def native(vm,address):
                if address==wind["catapults"]:
                    self.assertEqual(vm.reg_read(UC_X86_REG_EAX),DATA);self.ret(vm,catapults)
            end=self.execute(m,CODE,STOP,wind["check"],callback=native)
            self.assertEqual("launch" if end==STOP else "native check",expected)
            self.assertEqual(m.reg_read(UC_X86_REG_EAX)&0xff if end==STOP else m.reg_read(UC_X86_REG_EAX),1 if end==STOP else DATA)

    def test_discovery_relocates_and_refuses_unknown_code_or_settings(self):
        delta=0x510000;moved=bytearray(self.blob)
        for off in audit.text_relocations():struct.pack_into("<I",moved,off,(struct.unpack_from("<I",moved,off)[0]+delta)&0xffffffff)
        found=ai.discover(bytes(moved),0x301000+delta)
        self.assertEqual(found["reports_slot"],self.info["reports_slot"]+delta)
        self.assertEqual(found["air_gates"][0]["target"],self.info["air_gates"][0]["target"]+delta)
        self.assertEqual(found["capital_site"],self.info["capital_site"]+delta)
        for address in (0x925d61,0x8cdb33,0x878cc4,0x86a709,0x90ab88):
            changed=bytearray(self.blob);changed[address-0x301000]^=1
            with self.assertRaises(ValueError):ai.discover(bytes(changed),0x301000)
        for settings in ({"contact_memory_minutes":0},{"memory_radius_yards":True},{"cheat":1},{"catapult_strikes":2},
                         {"capital_max_advance_yards":1999},{"capital_gun_range_percent":91}):
            with self.assertRaises(ValueError):ai.discover(self.blob,0x301000,settings)

    def capital(self, stance=3, kind=1, side=0, role=0, ai_control=1, enemy_distance=7000,
                gun_range=10000, lead_distance=7000, lead_enemy_distance=20000,
                contact=True, known=True, blocked=False, foreign_lead=False, dead_lead=False):
        m=self.vm();d=DATA+0x1000;ship=DATA+0x2000;enemy=DATA+0x4000
        lead=DATA+0x5000;tail=DATA+0x6000;seen=DATA+0x7000;items=DATA+0x8000;ref=DATA+0x9000
        self.put(m,ref,d);m.reg_write(UC_X86_REG_EBX,ref)
        m.reg_write(UC_X86_REG_ESI,enemy if known else 0xdeadc000)
        self.put(m,STACK+0x9000-0x24,ship);self.put(m,STACK+0x9000-8,DATA+0x200)
        self.put(m,d+0x30,ai_control,1);self.put(m,d+0x2f,stance,1);self.put(m,d+0x3a,role,1)
        self.put(m,ship+0x9d3,kind,1);self.put(m,ship+0xa55,side)
        self.put(m,enemy+0xa55,1-side);self.put(m,ship+0xad9,seen)
        self.put(m,seen+4,items);self.put(m,seen+8,int(contact));self.put(m,items,enemy)
        self.put(m,d+0x3c,lead);self.put(m,lead+0xd,DATA+0xa000);self.put(m,DATA+0xa008,1)
        self.put(m,tail+0xa55,1-side if foreign_lead else side);self.put(m,tail+0x9d3,1,1)
        self.put(m,tail+0xa9f,int(dead_lead),1)
        m.mem_write(CODE,ai.capital_thunk(CODE,STATE,self.info));courses=[];distances=[]
        def native(vm,address):
            eax=vm.reg_read(UC_X86_REG_EAX);edx=vm.reg_read(UC_X86_REG_EDX)
            if address==self.info["ship_distance"]:
                distances.append((eax,edx))
                values={(ship,enemy):enemy_distance,(ship,tail):lead_distance,(tail,enemy):lead_enemy_distance}
                self.assertIn((eax,edx),values);self.ret(vm,values[(eax,edx)])
            elif address==self.info["trailing_ship"]:
                self.assertEqual(eax,lead);self.ret(vm,tail)
            elif address==self.info["main_gun_range"]:
                self.assertEqual((eax,edx),(ship,1));self.ret(vm,gun_range)
            elif address==self.info["bearing"]:
                self.assertEqual((eax,edx),(ship,tail+0xa1c));self.ret(vm,270)
            elif address==self.info["clear_course"]:self.ret(vm,int(not blocked),4)
            elif address==self.info["set_course"]:
                courses.append(self.get(vm,edx));self.assertEqual(eax,d);self.put(vm,d+4,courses[-1]);self.ret(vm)
        dispatch=self.info["capital_site"]+6
        end=self.execute(m,CODE,dispatch,self.info["capital_exit"],callback=native)
        for register,value in ((UC_X86_REG_EBX,ref),(UC_X86_REG_ESI,enemy if known else 0xdeadc000),
                (UC_X86_REG_EDX,DATA+0x1000),(UC_X86_REG_ECX,0x1234),(UC_X86_REG_EDI,0x4567),
                (UC_X86_REG_EBP,STACK+0x9000),(UC_X86_REG_ESP,STACK+0x8000),(UC_X86_REG_EFLAGS,0x246)):
            self.assertEqual(m.reg_read(register),value,register)
        return dict(stance=self.get(m,d+0x2f)&255,end=end,courses=courses,
                    holds=self.get(m,STATE+12),regroups=self.get(m,STATE+16),distances=distances)

    def test_capital_close_and_rapid_stances_hold_at_main_battery_distance_for_both_sides(self):
        for stance in (3,4):
            for kind in (0,1,2):
                for side in (0,1):
                    result=self.capital(stance=stance,kind=kind,side=side)
                    self.assertEqual(result["stance"],2);self.assertEqual(result["holds"],1)
                    self.assertEqual(result["courses"],[])
        self.assertEqual(self.capital(enemy_distance=7500)["stance"],2)
        self.assertEqual(self.capital(enemy_distance=7501)["stance"],3)

    def test_capitals_can_still_close_when_out_of_gun_range(self):
        result=self.capital(enemy_distance=16000)
        self.assertEqual(result["stance"],3);self.assertEqual(result["holds"],0)
        for gun_range in (0,1999,200001):self.assertEqual(self.capital(gun_range=gun_range)["stance"],3)

    def test_capital_formation_regroups_when_far_ahead_toward_known_enemy(self):
        for side in (0,1):
            for role in (1,2):
                result=self.capital(role=role,side=side,enemy_distance=12000)
                self.assertEqual(result["courses"],[270]);self.assertEqual(result["regroups"],1)
                self.assertEqual(result["end"],self.info["capital_exit"])
        result=self.capital(role=1,enemy_distance=12000,blocked=True)
        self.assertEqual(result["stance"],2);self.assertEqual(result["courses"],[])

    def test_formation_does_not_pull_back_ships_catching_up_from_behind(self):
        for values in (dict(lead_distance=6000),dict(lead_enemy_distance=10000),
                       dict(lead_enemy_distance=13500),dict(foreign_lead=True),dict(dead_lead=True)):
            result=self.capital(role=1,enemy_distance=12000,**values)
            self.assertEqual(result["stance"],3);self.assertEqual(result["regroups"],0)

    def test_capital_guard_preserves_manual_emergency_noncapital_and_special_role_orders(self):
        for values in (dict(ai_control=0),dict(kind=3),dict(kind=4),dict(kind=9),dict(role=3),dict(role=4),dict(role=5)):
            result=self.capital(**values)
            self.assertEqual(result["stance"],3);self.assertEqual(result["holds"],0)
        for stance in (0,1,2,5,6,7):self.assertEqual(self.capital(stance=stance)["stance"],stance)

    def test_capital_guard_does_not_read_hidden_or_unreported_enemy_objects(self):
        for values in (dict(contact=False),dict(known=False)):
            result=self.capital(**values)
            self.assertEqual(result["stance"],3);self.assertEqual(result["distances"],[])

    def test_capital_hook_fits_reserved_space_and_native_dispatch_ordinals(self):
        code=ai.capital_thunk(CODE,STATE,self.info)
        self.assertLessEqual(len(code),0x400)
        table=struct.unpack_from('<8I',self.blob,0x86a71f-0x301000)
        self.assertEqual(table[2],0x86da35)  # Native HOLD branch.
        self.assertEqual(table[3],0x8701f5)  # Native CLOSE branch.

    def test_original_dispatch_continues_close_but_guard_changes_in_range_order_to_hold(self):
        m=self.vm();ref=DATA+0x9000;d=DATA+0x1000
        self.put(m,ref,d);self.put(m,d+0x2f,3,1);m.reg_write(UC_X86_REG_EBX,ref)
        site=self.info["capital_site"];m.mem_write(site,self.blob[site-0x301000:site-0x301000+54])
        table=struct.unpack_from('<8I',self.blob,0x86a71f-0x301000)
        self.assertEqual(self.execute(m,site,*table),table[3])
        self.assertEqual(self.capital(enemy_distance=3500)["stance"],2)

    def test_capital_guard_accepts_the_enabled_fair_ai_torpedo_and_detection_patches(self):
        import ai_rules
        combined=bytearray(self.blob)
        for mode in ("torpedo-initiative","fair-ai","detection-only-evasion"):
            plans,_=ai_rules.discover(self.blob,0x301000,mode)
            for item in plans:
                start=item["address"]-0x301000
                combined[start:start+len(bytes.fromhex(item["original"]))]=bytes.fromhex(item["replacement"])
        found=ai.discover(bytes(combined),0x301000)
        self.assertEqual(found["capital_original"],self.info["capital_original"])
        self.assertFalse(found["hidden_enemy_positions_read"])

    def reattach(self,fuel=50,damage=10,speed=24,division_speed=20,rescuing=0):
        m=self.vm();div=DATA+0x1000;flag=DATA+0x2000;orig=DATA+0x3000;frame=m.reg_read(UC_X86_REG_EBP)
        self.put(m,frame-4,div);self.put(m,flag+0xb1d,orig);self.put(m,orig+9,division_speed);self.put(m,div+0xd2,rescuing)
        m.mem_write(CODE,ai.reattach_thunk(CODE,STATE,self.info))
        values={self.info["flagship"]:(div,flag),self.info["fuel"]:(flag,fuel),
                self.info["ship_damage"]:(flag,damage),self.info["max_speed"]:(flag,speed)}
        def native(vm,address):
            if address in values:
                self.assertEqual(vm.reg_read(UC_X86_REG_EAX),values[address][0]);self.ret(vm,values[address][1])
        before={r:m.reg_read(r) for r in (UC_X86_REG_EBX,UC_X86_REG_ECX,UC_X86_REG_ESI,UC_X86_REG_EDI,UC_X86_REG_EBP,UC_X86_REG_ESP)}
        end=self.execute(m,CODE,self.info["reattach_continue"],self.info["reattach_refuse"],callback=native)
        for r,v in before.items():self.assertEqual(m.reg_read(r),v)
        return end==self.info["reattach_continue"],m

    def test_detached_ships_rejoin_only_if_native_checks_would_keep_them(self):
        for kwargs,joins in (({},True),(dict(fuel=15),True),(dict(fuel=14),False),(dict(damage=90),True),
                             (dict(damage=91),False),(dict(speed=18),True),(dict(speed=17),False)):
            joins_now,m=self.reattach(**kwargs)
            self.assertEqual(joins_now,joins,kwargs)
            self.assertEqual(self.get(m,STATE+20),0 if joins else 1)
            if joins:self.assertEqual(m.reg_read(UC_X86_REG_EAX),DATA+0x1000)
            else:self.assertEqual(m.reg_read(UC_X86_REG_EAX),DATA)
        # The replayed native rescue check still decides: ZF=1 rejoins, a rescuer stays detached.
        for rescuing,zero in ((0,True),(1,False)):
            _,m=self.reattach(rescuing=rescuing)
            self.assertEqual(bool(m.reg_read(UC_X86_REG_EFLAGS)&0x40),zero)
        self.assertLessEqual(len(ai.reattach_thunk(CODE,STATE,self.info)),0x400)

    def test_an_ai_missile_ship_with_empty_launchers_disengages(self):
        # mounts: (kind, loaded, reloads); kind 0 is a torpedo mount, 1-6 SAM and SSM launchers
        for mounts,gun,control,stance in ((((2,0,0),(5,0,0),(0,4,0)),5,1,0),(((2,0,0),(5,1,0)),5,1,3),(((2,0,0),(5,0,2)),5,1,3),
                                          (((2,0,0),),8,1,3),(((0,4,0),),5,1,3),((),5,1,3),(((2,0,0),),5,0,3)):
            self.assertEqual(self.commit(2,3,control=control,mounts=mounts,gun=gun)[0],stance,(mounts,gun,control))

    def commit(self,prev,new,recorded=None,minute=100,control=1,damage=0,enemy=20000,settings=None,mounts=None,gun=5):
        info=self.info if settings is None else ai.discover(self.blob,0x301000,settings)
        m=self.vm();div=DATA+0x1000;table=DATA+0x20000;clock=DATA+0x3f000;entry=table+((div>>4)&1023)*12
        self.put(m,info["minute_slot"],clock);self.put(m,clock,minute)
        self.put(m,div+0x2f,prev,1);self.put(m,div+0x30,control,1)
        if recorded:self.put(m,entry,div);self.put(m,entry+4,recorded[0]);self.put(m,entry+8,recorded[1])
        if mounts is not None:   # the flagship's missile mounts
            ship,lst,items=DATA+0x2000,DATA+0x2800,DATA+0x2900
            self.put(m,ship+0x6d,gun);self.put(m,ship+0x9e,lst);self.put(m,lst+4,items);self.put(m,lst+8,len(mounts))
            for i,(kind,loaded,reloads) in enumerate(mounts):
                mount=DATA+0x2a00+i*0x100;self.put(m,items+4*i,mount);self.put(m,mount+0xe,kind,1)
                self.put(m,mount+0xf1,loaded);self.put(m,mount+0xf,reloads)
        m.mem_write(CODE,ai.commit_thunk(CODE,STATE,info,table));m.reg_write(UC_X86_REG_EDX,div)
        values={info["damage"]:damage,info["closest_enemy"]:enemy,info["flagship"]:DATA+0x2000}
        def native(vm,address):
            if address==info["dispatcher"]:self.put(vm,div+0x2f,new,1);self.ret(vm)
            elif address in values:self.ret(vm,values[address])
        before={r:m.reg_read(r) for r in (UC_X86_REG_EBX,UC_X86_REG_ESI,UC_X86_REG_EDI,UC_X86_REG_EBP)}
        self.execute(m,CODE,STOP,callback=native)
        for r,v in before.items():self.assertEqual(m.reg_read(r),v)
        return m.mem_read(div+0x2f,1)[0],tuple(self.get(m,entry+i) for i in (4,8)),self.get(m,STATE+24)

    def test_stance_commitment_blocks_only_quick_hold_increase_close_reversals(self):
        recent=lambda prev:(95,prev)
        for prev,new in ((2,1),(1,2),(1,3),(2,3)):
            self.assertEqual(self.commit(prev,new,recent(prev)),(prev,(95,prev),1),(prev,new))
            self.assertEqual(self.commit(prev,new,(85,prev))[:2],(new,(100,new)),(prev,new))
        # Emergencies, closing faster, and leaving CLOSE always pass and are recorded.
        for prev,new in ((2,0),(1,0),(2,5),(1,6),(3,1),(4,2),(3,4),(1,4),(2,7),(0,2),(6,2)):
            self.assertEqual(self.commit(prev,new,recent(prev))[:2],(new,(100,new)),(prev,new))

    def test_stance_commitment_exemptions_and_stale_records(self):
        self.assertEqual(self.commit(2,1,(95,2),damage=30)[0],1)
        self.assertEqual(self.commit(2,1,(95,2),damage=29)[0],2)
        self.assertEqual(self.commit(2,1,(95,2),enemy=4999)[0],1)
        self.assertEqual(self.commit(2,1,(95,2),enemy=5000)[0],2)
        self.assertEqual(self.commit(2,1,(95,3))[0],1)       # stance changed elsewhere since the record
        self.assertEqual(self.commit(2,1,(500,2))[0],1)      # record from a previous battle's clock
        self.assertEqual(self.commit(2,1)[:2],(1,(100,1)))   # first decision is recorded
        self.assertEqual(self.commit(2,1,(95,2),control=0)[:2],(1,(95,2)))
        self.assertEqual(self.commit(2,1,(95,2),settings={"stance_commit_minutes":0})[0],1)
        self.assertEqual(self.commit(2,2,(95,2))[1:],((95,2),0))

    def bow(self,course=90,bearing=100,stance=2,kind=1,control=1,enemy_kind=1,side=1,sunk=0,distance=10000,gun=30000):
        m=self.vm();div=DATA+0x1000;flag=DATA+0x2000;enemy=DATA+0x4000;contacts=DATA+0x5000;items=DATA+0x5100;cp=DATA+0x6000
        self.put(m,div+0x30,control,1);self.put(m,div+0x2f,stance,1)
        self.put(m,flag+0x9d3,kind,1);self.put(m,flag+0xa55,0);self.put(m,flag+0xad9,contacts)
        self.put(m,contacts+8,1);self.put(m,contacts+4,items);self.put(m,items,enemy)
        self.put(m,enemy+0xa55,side);self.put(m,enemy+0xa9f,sunk,1);self.put(m,enemy+0x9d3,enemy_kind,1);self.put(m,cp,course)
        m.reg_write(UC_X86_REG_EBX,div);m.reg_write(UC_X86_REG_ESI,cp);m.mem_write(CODE,ai.bow_thunk(CODE,STATE,self.info))
        values={self.info["flagship"]:flag,self.info["main_gun_range"]:gun,
                self.info["ship_distance"]:distance,self.info["true_bearing_ship"]:bearing}
        def native(vm,address):
            if address in values:self.ret(vm,values[address])
        end=self.execute(m,CODE,self.info["course_hold"],self.info["course_other"],callback=native)
        self.assertEqual(m.reg_read(UC_X86_REG_ESI),cp)
        return self.get(m,cp),end==self.info["course_hold"]

    def test_capitals_turn_bow_on_courses_away_from_nearby_enemy_heavy_ships(self):
        for course,bearing,expected in ((90,100,40),(110,100,160),(10,350,50),(340,10,310),(100,100,160)):
            self.assertEqual(self.bow(course,bearing)[0],expected,(course,bearing))
        for stance in (0,1,2):self.assertEqual(self.bow(stance=stance)[0],40)
        self.assertEqual(self.bow(distance=22499)[0],40)   # inside 75% of 30,000 yards

    def test_bow_guard_leaves_closing_evasion_other_classes_and_far_or_friendly_ships(self):
        for kwargs in (dict(course=150),dict(course=50),dict(stance=3),dict(stance=4),dict(stance=5),dict(stance=6),
                       dict(kind=3),dict(control=0),dict(enemy_kind=4),dict(side=0),dict(sunk=1),dict(distance=22500),dict(gun=1999)):
            self.assertEqual(self.bow(**kwargs)[0],kwargs.get("course",90),kwargs)
        self.assertEqual(self.bow(stance=7,course=150),(150,True))   # native NOENEMYSIGHTED check is replayed
        self.assertEqual(self.bow()[1],False)

    def withdraw(self,score,level,patched=True,settings=None):
        info=self.info if settings is None else ai.discover(self.blob,0x301000,settings)
        m=self.vm();force=DATA+0x1000;frame=m.reg_read(UC_X86_REG_EBP)
        self.put(m,frame-0x34,score);self.put(m,force+0x75,level);m.reg_write(UC_X86_REG_EBX,force)
        site=info["withdraw_site"];m.mem_write(site,self.blob[site-0x301000:site-0x301000+13])
        if patched:m.mem_write(CODE,ai.withdraw_thunk(CODE,info));start=CODE
        else:start=site
        self.execute(m,start,info["withdraw_exit"])
        value=self.get(m,frame-0x34);return value-(1<<32) if value>=1<<31 else value

    def test_force_withdrawal_ignores_the_first_points_of_score(self):
        for score,level in ((25,0),(25,2),(10,0),(5,1),(-20,0),(60,3)):
            self.assertEqual(self.withdraw(score,level,settings={"withdraw_dead_zone":0}),self.withdraw(score,level,False))
            self.assertEqual(self.withdraw(score,level),int((score-10)/(level+1)))

    def test_uncomfortable_fire_turnaway_now_requires_being_outgunned(self):
        site=0x888b4c;item=next(p for p in self.info["static_patches"] if p["address"]==0x888b4e)
        for enemy,own,native,patched in ((60,100,True,False),(120,100,True,True),(50,100,False,False)):
            for use_patch,expected in ((False,native),(True,patched)):
                m=self.vm();m.mem_write(site,self.blob[site-0x301000:site-0x301000+9])
                if use_patch:m.mem_write(item["address"],bytes.fromhex(item["replacement"]))
                m.reg_write(UC_X86_REG_EDI,enemy);self.put(m,m.reg_read(UC_X86_REG_EBP)-8,own)
                self.assertEqual(self.execute(m,site,0x888b55,0x888bcd)==0x888b55,expected,(enemy,own,use_patch))

    def frustrated(self,gate,light=1,kind=1,damage=0,mission=0):
        m=self.vm();div=DATA+0x1000;force=DATA+0x1800;flag=DATA+0x2000;target=DATA+0x4000
        self.put(m,div+0x57,force);self.put(m,force+0x1c,mission,1);self.put(m,flag+0xb02,light);self.put(m,target+0x9d3,kind,1)
        m.reg_write(UC_X86_REG_EBX,div);m.reg_write(UC_X86_REG_EDI,flag);m.reg_write(UC_X86_REG_ESI,target)
        m.mem_write(CODE,ai.frustrated_thunk(CODE,STATE,self.info,gate))
        def native(vm,address):
            if address==self.info["ship_damage"]:self.assertEqual(vm.reg_read(UC_X86_REG_EAX),target);self.ret(vm,damage)
        return self.execute(m,CODE,gate["skip"],gate["go"],callback=native)==gate["go"]

    def test_light_ships_no_daylight_boredom_charge_at_intact_heavy_ships(self):
        self.assertEqual([hex(g["site"]) for g in self.info["frustrated"]],["0x88e51c","0x88bf1c"])
        for gate in self.info["frustrated"]:
            self.assertFalse(self.frustrated(gate))                    # daylight, intact BB: stays out
            for kind in (0,2,3):self.assertFalse(self.frustrated(gate,kind=kind))
            self.assertTrue(self.frustrated(gate,light=2))             # night: native charge
            self.assertTrue(self.frustrated(gate,kind=4))              # light cruiser target
            self.assertTrue(self.frustrated(gate,damage=60))           # crippled heavy ship
            self.assertFalse(self.frustrated(gate,mission=2,light=2))  # native mission-2 exit replayed

    def test_new_hooks_fit_their_reserved_space(self):
        for code in (ai.commit_thunk(CODE,STATE,self.info,DATA),ai.bow_thunk(CODE,STATE,self.info),ai.withdraw_thunk(CODE,self.info)):
            self.assertLessEqual(len(code),0x400)


if __name__=="__main__":unittest.main(verbosity=2)
