"""Native prompt stack contracts and AI procurement gates, no game writes."""
from pathlib import Path
import struct
import sys
import unittest

HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE/"vendor"),str(HERE.parent/"CampaignOverhaul")]
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import *
import campaign_qol as qol
import modern_research as audit


class QoLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blob=(HERE/"native-designer-inspection.text.bin").read_bytes()
        cls.info=qol.discover(cls.blob,0x301000)

    def vm(self):
        m=Uc(UC_ARCH_X86,UC_MODE_32)
        m.mem_map(0x300000,0x800000);m.mem_map(0x1200000,0x20000);m.mem_map(0x1300000,0x100000);m.mem_map(0x1500000,0x10000)
        return m

    def begin(self,m,day=10000,player=False):
        main,nation,owner=0x1301000,0x1306000,0x130a000
        m.mem_write(main+self.info["player_field"],struct.pack("<I",owner))
        m.mem_write(self.info["clock"],struct.pack("<d",day))
        for reg,value in ((UC_X86_REG_EAX,main),(UC_X86_REG_EDX,owner if player else nation),
                          (UC_X86_REG_ECX,3),(UC_X86_REG_ESP,0x1508000),(UC_X86_REG_EBP,0x1509000),
                          (UC_X86_REG_EFLAGS,0x247)):
            m.reg_write(reg,value)
        m.mem_write(0x1508000,struct.pack("<II",0x120f000,0))
        return main,nation,owner

    def execute(self,m,code,*ends):
        hook=m.hook_add(UC_HOOK_CODE,lambda vm,address,size,_:vm.emu_stop() if address in ends else None)
        try:m.emu_start(code,0,count=200000)
        finally:m.hook_del(hook)
        self.assertIn(m.reg_read(UC_X86_REG_EIP),ends)
        return m.reg_read(UC_X86_REG_EIP)

    def test_procurement_not_four_times_per_month_and_player_unaffected(self):
        m=self.vm();state=0x1300000
        m.mem_write(0x1200000,qol.monthly_thunk(0x1200000,state,self.info))
        for day,allowed in ((10000,True),(10007,False),(10014,False),(10021,False),(10028,True),(9990,True)):
            self.begin(m,day)
            end=self.execute(m,0x1200000,self.info["monthly"]+8,0x120f000)
            self.assertEqual(end==self.info["monthly"]+8,allowed)
        self.begin(m,10001,True)
        self.assertEqual(self.execute(m,0x1200000,self.info["monthly"]+8,0x120f000),self.info["monthly"]+8)

    def test_fleet_project_and_debt_caps_without_deleting_or_limiting_player(self):
        for active,projects,funds,player,initial,blocked in ((399,23,1000,False,False,False),(400,0,1000,False,False,True),
                (100,24,1000,False,False,True),(2,0,-1,False,False,True),(401,25,-1,True,False,False),
                (401,25,-1,False,True,False)):
            m=self.vm();main,nation,owner=self.begin(m,player=player);f=self.info["ship"]
            chosen=owner if player else nation
            if initial: m.mem_write(0x1508000,struct.pack("<I",self.info["initial"]+100))
            m.mem_write(chosen+self.info["funds"],struct.pack("<i",funds))
            m.mem_write(self.info["year_slot"],struct.pack("<I",0x1300500));m.mem_write(0x1300500,struct.pack("<I",1935))
            m.mem_write(chosen+self.info["ship_list"],struct.pack("<I",0x130c000))
            m.mem_write(0x130c004,struct.pack("<II",0x130d000,active+10))
            for i in range(active+10):
                pointer=0x1310000+i*0x200
                m.mem_write(0x130d000+i*4,struct.pack("<I",pointer))
                for key,value in dict(RepairTime=100 if i>=active else 0,Cost=1000,BuildProgress=100 if i<projects else 1000,
                                      MonthlyCost=100,YearBuilt=1936 if i<projects else 1934).items():
                    m.mem_write(pointer+f[key],struct.pack("<I",value))
            before=bytes(m.mem_read(0x1306000,0x90000))
            m.mem_write(0x1200000,qol.build_thunk(0x1200000,0x1300000,self.info))
            end=self.execute(m,0x1200000,self.info["build"]+5,0x120f000)
            self.assertEqual(end==0x120f000,blocked)
            self.assertEqual(bytes(m.mem_read(0x1306000,0x90000)),before)
            if blocked:
                self.assertEqual(m.reg_read(UC_X86_REG_EAX),0)
                self.assertEqual(m.reg_read(UC_X86_REG_ESP),0x1508008)

    def test_name_fallback_assigns_the_native_default_and_cleans_argument(self):
        m=self.vm();self.begin(m)
        m.mem_write(self.info["string_assign"],bytes.fromhex("8910c3"))
        m.mem_write(0x1200000,qol.name_thunk(0x1200000,self.info))
        m.mem_write(0x1508000,struct.pack("<II",0x120f000,0x1300100))
        m.reg_write(UC_X86_REG_ECX,0x1300200)
        self.execute(m,0x1200000,0x120f000)
        self.assertEqual(int.from_bytes(m.mem_read(0x1300100,4),"little"),0x1300200)
        self.assertEqual(m.reg_read(UC_X86_REG_ESP),0x1508008)

    def test_docks_can_be_built_up_to_the_new_limit(self):
        plan=next(p for p in self.info["static_patches"] if "Docks" in p["label"])
        self.assertEqual((plan["address"],plan["original"]),(0x72b26e,"81be1d010000905f0100"))
        self.assertEqual(plan["replacement"],"81be1d010000"+struct.pack("<I",200000).hex())

    def test_only_specific_strike_confirmation_uses_no_and_cleans_help_argument(self):
        m=self.vm();self.begin(m)
        plan=self.info["static_patches"][0];at=plan["address"]
        m.mem_write(at,bytes.fromhex(plan["replacement"]));m.mem_write(0x1508000,struct.pack("<I",0))
        self.execute(m,at,at+8)
        self.assertEqual(m.reg_read(UC_X86_REG_EAX),7)
        self.assertEqual(m.reg_read(UC_X86_REG_ESP),0x1508004)
        self.assertFalse(m.reg_read(UC_X86_REG_EFLAGS)&0x40)

    def test_designer_wheel_steps_the_box_under_the_pointer(self):
        i=self.info;handler,stop=0x1200000,0x120f000
        form,box,child,plain,handled,sp,point=0x1301000,0x1302000,0x1302400,0x1303000,0x1304000,0x1508000,0x1306000
        combo,other,items,button,inner,stub=0x1307000,0x1307400,0x1307800,0x1308000,0x1308400,0x1309000
        def run(control,delta,shift=0,value=100,increment=5,index=3,count=6,owner=form):
            m=self.vm();m.mem_write(handler,qol.wheel_handler(handler,i))
            m.mem_write(box,struct.pack("<I",i["spin_vmt"]));m.mem_write(box+i["increment"],struct.pack("<i",increment))
            child_vmt,plain_vmt,combo_vmt,items_vmt=0x1305100,0x1305200,0x1305400,0x1305800   # a TSpinEdit subclass; others
            m.mem_write(child,struct.pack("<I",child_vmt));m.mem_write(child+i["increment"],struct.pack("<i",increment))
            m.mem_write(child_vmt-0x30,struct.pack("<I",0x1305300));m.mem_write(0x1305300,struct.pack("<I",i["spin_vmt"]))
            m.mem_write(plain,struct.pack("<I",plain_vmt));m.mem_write(plain_vmt-0x30,struct.pack("<I",0))
            for armour,change in ((combo,i["armour_change"]),(other,0x5555)):          # an armour list; the type list
                m.mem_write(armour,struct.pack("<I",i["combo_vmt"]));m.mem_write(armour+i["combo_items"],struct.pack("<I",items))
                m.mem_write(armour+i["combo_change"],struct.pack("<II",change,form))
            m.mem_write(i["combo_vmt"]+i["get_index"],struct.pack("<I",stub));m.mem_write(i["combo_vmt"]+i["set_index"],struct.pack("<I",stub+0x10))
            m.mem_write(items,struct.pack("<I",items_vmt));m.mem_write(items_vmt+i["count_slot"],struct.pack("<I",stub+0x20))
            for b in (button,inner):m.mem_write(b,struct.pack("<I",i["button_vmt"]))
            m.mem_write(button+i["up_click"],struct.pack("<II",stub+0x30,form));m.mem_write(button+i["down_click"],struct.pack("<II",stub+0x40,form))
            m.mem_write(inner+i["up_click"],struct.pack("<II",0,0))
            for c in (box,child,plain,combo,other,button,inner):m.mem_write(c+i["owner"],struct.pack("<I",owner))
            m.mem_write(form+i["owner"],struct.pack("<I",0x1301800));m.mem_write(0x1301800+i["owner"],struct.pack("<I",0))
            calls=[]
            def native(vm,address,size,_):
                eax,edx=vm.reg_read(UC_X86_REG_EAX),vm.reg_read(UC_X86_REG_EDX)
                results={i["find_window"]:control,i["get_value"]:value,stub:index,stub+0x20:count}
                if address==i["find_window"]:calls.append(("find",eax))
                elif address==i["set_value"]:calls.append(("value",eax,edx))
                elif address==stub+0x10:calls.append(("index",eax,edx))
                elif address==i["armour_change"]:calls.append(("change",eax,edx))
                elif address in (stub+0x30,stub+0x40):calls.append(("up" if address==stub+0x30 else "down",eax,edx))
                elif address not in results:return
                top=vm.reg_read(UC_X86_REG_ESP);vm.reg_write(UC_X86_REG_EAX,results.get(address,0))
                for reg in (UC_X86_REG_ECX,UC_X86_REG_EDX):vm.reg_write(reg,0xdead)        # callers keep nothing there
                vm.reg_write(UC_X86_REG_EIP,struct.unpack("<I",vm.mem_read(top,4))[0]);vm.reg_write(UC_X86_REG_ESP,top+4)
            m.hook_add(UC_HOOK_CODE,native)
            m.mem_write(sp,struct.pack("<IIII",stop,handled,point,delta&0xffffffff));m.mem_write(handled,b"\0")
            for reg,v in ((UC_X86_REG_EAX,form),(UC_X86_REG_EDX,form),(UC_X86_REG_ECX,shift),(UC_X86_REG_ESP,sp),
                          (UC_X86_REG_EBX,0x77),(UC_X86_REG_ESI,0x88),(UC_X86_REG_EDI,0x99),(UC_X86_REG_EBP,0xaa)):m.reg_write(reg,v)
            m.emu_start(handler,stop,count=2000)
            self.assertEqual([m.reg_read(r) for r in (UC_X86_REG_ESP,UC_X86_REG_EBX,UC_X86_REG_ESI,UC_X86_REG_EDI,UC_X86_REG_EBP)],
                             [sp+16,0x77,0x88,0x99,0xaa])
            self.assertEqual(calls[:1],[("find",point)])
            return calls[1:],m.mem_read(handled,1)[0]
        self.assertEqual(run(box,120),([("value",box,105)],1))
        self.assertEqual(run(box,-120),([("value",box,95)],1))
        self.assertEqual(run(box,-120,shift=1),([("value",box,50)],1))        # Shift: ten steps
        self.assertEqual(run(child,120,increment=100),([("value",child,200)],1))
        self.assertEqual(run(combo,120),([("index",combo,4),("change",form,combo)],1))   # armour: one item thicker
        self.assertEqual(run(combo,-120,shift=1),([("index",combo,0),("change",form,combo)],1))   # clamped at the top
        self.assertEqual(run(combo,120,index=5),([],1))                 # already the last item: nothing changes
        self.assertEqual(run(combo,120,count=0),([],0))
        self.assertEqual(run(other,120),([],0))                         # other lists (ship type, nation): native
        self.assertEqual(run(button,120),([("up",form,button)],1))      # spin buttons click themselves
        self.assertEqual(run(button,-120,shift=1),([("down",form,button)]*10,1))
        self.assertEqual(run(inner,120),([],0))                         # no click handler
        self.assertEqual(run(plain,120),([],0))                         # other controls: not handled
        self.assertEqual(run(0,120),([],0))                             # nothing under the pointer
        self.assertEqual(run(box,120,owner=0x1301400),([],0))           # another form's box
        self.assertEqual(run(box,120,owner=0x1301800),([],0))           # owned by something the form does not own

    def test_designer_form_show_installs_the_wheel_once_and_keeps_another_handler(self):
        i=self.info;hook,handler,form=0x1200e00,0x1200c00,0x1301000
        for existing,expected in ((0,handler),(handler,handler),(0x4444,0x4444)):
            m=self.vm();m.mem_write(hook,qol.wheel_hook(hook,handler,i));globe=0x1302800
            m.mem_write(form+i["on_mouse_wheel"],struct.pack("<II",existing,0x5555));m.mem_write(form+0xe67,b"\x01")
            m.mem_write(form+i["picture"],struct.pack("<I",globe if existing!=handler else 0))
            m.reg_write(UC_X86_REG_EBX,form)
            m.emu_start(hook,i["form_show"]+7,count=100)
            code,data=struct.unpack("<II",m.mem_read(form+i["on_mouse_wheel"],8))
            self.assertEqual((code,data),(expected,form if expected==handler else 0x5555))
            self.assertEqual(m.mem_read(form+0xe67,1)[0],0)             # FormShow's own store still runs
            self.assertEqual(m.mem_read(globe+i["rotate_button"],1)[0],2 if existing!=handler else 0)   # middle-drag pans

    def test_invasions_close_only_main_home_regions(self):
        i=self.info;thunk=0x1200000
        def literal(m,address,value):
            m.mem_write(address,struct.pack("<HHiI",1200,2,-1,len(value))+value.encode("utf-16-le")+b"\0\0")
            return address+12
        for value,name,home in ((5,"Ceylon",False),(200,"Southern France",False),(200,"Germany",True),(200,"Eastern USA",True),
                                (100,"Germany",False),(200,"Java",True)):   # superstates: one home area a bloc
            for item in i["invasions"]:
                m=self.vm();m.mem_write(0x301000,self.blob);cursor=0x1301000;names=[]
                for homeland in qol.HOMELANDS: names.append(literal(m,cursor,homeland));cursor+=0x80
                text=literal(m,cursor,qol.HOMELAND_TEXT);possession=0x1302000
                m.mem_write(possession+0x58,struct.pack("<i",value));m.mem_write(possession+0x54,struct.pack("<I",literal(m,0x1303000,name)))
                m.mem_write(thunk,qol.invasion_thunk(thunk,item,names,text,i));shown=[]
                def native(vm,address,size,_):
                    if address==i["message"]:
                        shown.append(vm.reg_read(UC_X86_REG_EAX));top=vm.reg_read(UC_X86_REG_ESP)
                        vm.reg_write(UC_X86_REG_EIP,struct.unpack("<I",vm.mem_read(top,4))[0]);vm.reg_write(UC_X86_REG_ESP,top+4)
                m.hook_add(UC_HOOK_CODE,native)
                m.reg_write(UC_X86_REG_EAX,possession);m.reg_write(UC_X86_REG_ESP,0x1508000)
                end=self.execute(m,thunk,item["ok"],item["end"])
                self.assertEqual((end,shown),(item["end"],[text]) if home else (item["ok"],[]),(value,name))
                self.assertEqual(m.reg_read(UC_X86_REG_ESP),0x1508000)

    def test_invasion_range_opens_big_possessions_to_the_player_buttons_only(self):
        i=self.info;thunk=0x1200000;item=i["invasion_range"];frame=0x1509000
        def literal(m,address,value):
            m.mem_write(address,struct.pack("<HHiI",1200,2,-1,len(value))+value.encode("utf-16-le")+b"\0\0")
            return address+12
        for value,name,caller,opened in ((5,"Ceylon",0x7c9381,True),(200,"Southern France",item["players"][0],True),
                                         (200,"Southern France",0x7c937b,False),(200,"Germany",item["players"][1],False)):
            m=self.vm();m.mem_write(0x301000,self.blob);cursor=0x1301000;names=[]
            for homeland in qol.HOMELANDS: names.append(literal(m,cursor,homeland));cursor+=0x80
            possession=0x1302000
            m.mem_write(possession+0x58,struct.pack("<i",value));m.mem_write(possession+0x54,struct.pack("<I",literal(m,0x1303000,name)))
            m.mem_write(frame-0xc,struct.pack("<I",possession));m.mem_write(frame+4,struct.pack("<I",caller))
            m.mem_write(thunk,qol.range_thunk(thunk,item,names,i))
            m.reg_write(UC_X86_REG_EBP,frame);m.reg_write(UC_X86_REG_ESP,0x1508000)
            end=self.execute(m,thunk,item["ok"],item["zero"])
            self.assertEqual(end,item["ok"] if opened else item["zero"],(value,name,hex(caller)))
            self.assertEqual(m.reg_read(UC_X86_REG_ESP),0x1508000)

    def homelands(self,m):
        names=[];cursor=0x1301000
        for homeland in qol.HOMELANDS: names.append(self.literal(m,cursor,homeland));cursor+=0x80
        return names

    def literal(self,m,address,value):
        m.mem_write(address,struct.pack("<HHiI",1200,2,-1,len(value))+value.encode("utf-16-le")+b"\0\0")
        return address+12

    def test_neutral_and_big_possessions_get_the_invasion_target_button(self):
        i=self.info;thunk=0x1200000;item=i["colony"]
        for owner,relation,value,name,enabled in ((0,0,10,"Finland",1),(1,50,10,"Ceylon",1),(1,50,200,"Southern France",1),
                                                  (1,50,200,"Germany",0),(1,30,5,"Ceylon",0)):
            m=self.vm();m.mem_write(0x301000,self.blob);names=self.homelands(m);possession,nation=0x1302000,0x1304000
            m.mem_write(possession+0x61,struct.pack("<I",nation if owner else 0));m.mem_write(nation+0x256,struct.pack("<i",relation))
            m.mem_write(possession+0x58,struct.pack("<i",value));m.mem_write(possession+0x54,struct.pack("<I",self.literal(m,0x1303000,name)))
            m.mem_write(thunk,qol.target_button_thunk(thunk,item,names,i))
            m.reg_write(UC_X86_REG_EBX,possession);m.reg_write(UC_X86_REG_ESP,0x1508000)
            self.execute(m,thunk,item["ui_set"])
            self.assertEqual(m.reg_read(UC_X86_REG_EDX)&0xff,enabled,(owner,relation,value,name))
            self.assertEqual(m.reg_read(UC_X86_REG_ESP),0x1508000)

    def test_turn_time_invasion_keeps_big_targets_and_lands_on_neutral_ones(self):
        i=self.info;thunk=0x1200000;main,player,nation,possession,slot,frame=0x1305000,0x1306000,0x1304000,0x1302000,0x1307000,0x1509000
        stubs=dict(weather=0x1210000,blockade=0x1210100,strength=0x1210200);item=dict(i["colony"],**stubs)
        target=lambda m:struct.unpack("<I",m.mem_read(main+0x4a8c,4))[0]
        for owner,relation,value,name,weather,blockaded,port,strength,enemy,end in (
                (1,30,5,"Ceylon",1,0,1,50,0,"skip"),(1,50,10,"Ceylon",1,0,1,50,0,"proceed"),
                (1,50,200,"Southern France",1,0,1,50,0,"proceed"),(1,50,200,"Germany",1,0,1,50,0,"skip"),
                (0,0,3,"Finland",0,0,1,50,0,"weather_delay"),(0,0,3,"Finland",1,1,0,50,0,"blockade_delay"),
                (0,0,3,"Finland",1,1,1,50,0,"landed"),(0,0,3,"Finland",1,0,1,7,0,"force_delay"),
                (0,0,3,"Finland",1,0,1,50,50,"force_delay"),(0,0,3,"Finland",1,0,1,50,49,"landed")):
            m=self.vm();m.mem_write(0x301000,self.blob);names=self.homelands(m)
            for key,result in (("weather",weather),("blockade",port),("strength",strength)):
                m.mem_write(stubs[key],b"\xb8"+struct.pack("<I",result)+b"\xc3")
            m.mem_write(item["minimum"],struct.pack("<i",3))   # minimum force 3: more than 7 needed
            m.mem_write(main+0x3204,struct.pack("<I",player));m.mem_write(player+0x1c5,bytes([blockaded]))
            m.mem_write(main+0x4a8c,struct.pack("<I",possession));m.mem_write(slot,struct.pack("<I",possession))
            m.mem_write(possession+0x61,struct.pack("<I",nation if owner else 0));m.mem_write(nation+0x256,struct.pack("<i",relation))
            m.mem_write(possession+0x58,struct.pack("<i",value));m.mem_write(possession+0x54,struct.pack("<I",self.literal(m,0x1303000,name)))
            m.mem_write(frame-0x1c,struct.pack("<i",enemy))
            m.mem_write(thunk,qol.turn_thunk(thunk,item,names,i))
            for reg,v in ((UC_X86_REG_EBX,main),(UC_X86_REG_ESI,slot),(UC_X86_REG_EBP,frame),(UC_X86_REG_ESP,0x1508000)): m.reg_write(reg,v)
            ends=[item[k] for k in ("skip","proceed","weather_delay","blockade_delay","force_delay","landed")]
            self.assertEqual(self.execute(m,thunk,*ends),item[end],(owner,relation,value,name,end))
            self.assertEqual(target(m),0 if name=="Germany" else possession)
            self.assertEqual((m.reg_read(UC_X86_REG_ESP),m.reg_read(UC_X86_REG_EBX),m.reg_read(UC_X86_REG_ESI),m.reg_read(UC_X86_REG_EBP)),
                             (0x1508000,main,slot,frame))

    def test_landing_on_a_neutral_possession_makes_it_the_players(self):
        i=self.info;thunk=0x1200000;item=i["colony"];main,player,slot,possession=0x1305000,0x1306000,0x1307000,0x1302000
        assign=0x1210000;info=dict(i,string_assign=assign)
        for owner,expected,end in ((0,player,item["success_done"]),(0x1308000,0x1308000,item["success_native"])):
            m=self.vm();m.mem_write(assign,b"\x89\x10\xc3")   # stub: [EAX] := EDX
            name=self.literal(m,0x1303000,"Japan");m.mem_write(player+4,struct.pack("<I",name))
            m.mem_write(possession+0x61,struct.pack("<I",owner));m.mem_write(possession+0x75,struct.pack("<i",-1))
            m.mem_write(main+0x3204,struct.pack("<I",player));m.mem_write(slot,struct.pack("<I",possession))
            m.mem_write(thunk,qol.colony_thunk(thunk,item,info))
            m.reg_write(UC_X86_REG_EBX,main);m.reg_write(UC_X86_REG_ESI,slot);m.reg_write(UC_X86_REG_ESP,0x1508000)
            self.assertEqual(self.execute(m,thunk,item["success_native"],item["success_done"]),end)
            owner_now,invaded,saved=struct.unpack("<IiI",m.mem_read(possession+0x61,4)+m.mem_read(possession+0x75,4)+m.mem_read(possession+0x65,4))
            self.assertEqual((owner_now,invaded,saved),(player,-1,name) if not owner else (expected,0,0))

    def test_invasion_code_fits_its_reserved_space(self):
        i=self.info;names=[0x1300000+k*0x40 for k in range(len(qol.HOMELANDS))];text=0x1301000
        layout=qol.INVASION_CODE
        sizes=dict(ui=len(qol.target_button_thunk(0x1200000,i["colony"],names,i)),
                   turn=len(qol.turn_thunk(0x1200000,i["colony"],names,i)),
                   success=len(qol.colony_thunk(0x1200000,i["colony"],i)),
                   range=len(qol.range_thunk(0x1200000,i["invasion_range"],names,i)),
                   literals=sum((12+2*len(v)+2+15)&~15 for v in qol.HOMELANDS+(qol.HOMELAND_TEXT,)))
        for key,size in sizes.items(): self.assertLessEqual(size,layout[key][1],key)
        for (offset,room),item in zip(layout["invasions"],i["invasions"]):
            self.assertLessEqual(len(qol.invasion_thunk(0x1200000,item,names,text,i)),room)
        spans=sorted([layout[k] for k in ("ui","turn","success","range","literals")]+list(layout["invasions"]))
        self.assertGreaterEqual(spans[0][0],0x1148)                 # after the procurement state block
        for (a,ra),(b,_) in zip(spans,spans[1:]): self.assertLessEqual(a+ra,b)
        self.assertLessEqual(spans[-1][0]+spans[-1][1],0x3000)       # inside the allocation

    def test_relocated_discovery_and_unknown_patch_fail_closed(self):
        delta=0x510000;moved=bytearray(self.blob)
        for off in audit.text_relocations():struct.pack_into("<I",moved,off,(struct.unpack_from("<I",moved,off)[0]+delta)&0xffffffff)
        found=qol.discover(bytes(moved),0x301000+delta)
        self.assertEqual(found["clock"],self.info["clock"]+delta)
        self.assertEqual(found["build"],self.info["build"]+delta)
        self.assertEqual((found["form_show"],found["spin_vmt"]),(self.info["form_show"]+delta,self.info["spin_vmt"]+delta))
        self.assertEqual((found["find_window"],found["armour_change"]),(self.info["find_window"]+delta,self.info["armour_change"]+delta))
        self.assertEqual({k:v-delta for k,v in found["colony"].items()},self.info["colony"])
        changed=bytearray(self.blob);changed[0x97ba3c-0x301000]^=1
        with self.assertRaises(ValueError):qol.discover(bytes(changed),0x301000)


if __name__=="__main__":unittest.main(verbosity=2)
