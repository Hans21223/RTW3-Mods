"""Offline native-hook and guarded transaction checks; never opens RTW3."""
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE/"vendor"),str(HERE.parent/"CampaignOverhaul")]
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import *
import battle_environment as env
import modern_research as audit
import live_cheats as live

CODE,DATA,STACK,STATE=0x1200000,0x1300000,0x1500000,0x1330000
STOP=CODE+0xf000


class EnvironmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blob=(HERE/"native-designer-inspection.text.bin").read_bytes()
        cls.info=env.discover(cls.blob,0x301000)

    def put(self,m,a,v,width=4): m.mem_write(a,(v&((1<<(width*8))-1)).to_bytes(width,"little"))
    def get(self,m,a,width=4): return int.from_bytes(m.mem_read(a,width),"little")

    def vm(self):
        m=Uc(UC_ARCH_X86,UC_MODE_32)
        for a,n in ((0x300000,0x800000),(CODE,0x10000),(DATA,0x40000),(STACK,0x10000)): m.mem_map(a,n)
        for r,v in ((UC_X86_REG_EAX,DATA),(UC_X86_REG_EDX,0x1234),(UC_X86_REG_ECX,0x2345),
                    (UC_X86_REG_EBX,0x3456),(UC_X86_REG_ESI,0x4567),(UC_X86_REG_EDI,0x5678),
                    (UC_X86_REG_EBP,STACK+0x9000),(UC_X86_REG_ESP,STACK+0x8000),(UC_X86_REG_EFLAGS,0x246)):
            m.reg_write(r,v)
        self.put(m,STACK+0x8000,STOP)
        self.put(m,self.info["form_slot"],DATA)
        self.put(m,STATE+env.ACTIVE,DATA)
        self.put(m,self.info["clock_slot"],DATA+0x1000)
        m.mem_write(DATA+0x1000,struct.pack("<d",45000.75))
        m.mem_write(STACK+0x8004,struct.pack("<d",45000.75))
        for i,(slot,width,v) in enumerate(zip(self.info["weather_slots"],self.info["widths"],(8,8,3000,4000,3500))):
            target=DATA+0x2000+i*8
            self.put(m,slot,target);m.mem_write(target,b"\xaa"*8);self.put(m,target,v,width)
        self.put(m,DATA+0x498,DATA+0x3000)
        self.put(m,DATA+0x3000+0x33d,0x123456)
        self.put(m,DATA+0x580,DATA+0x4000)
        m.mem_write(CODE,env.sync_thunk(CODE,STATE,self.info))
        start=self.info["basic_day_range"]
        m.mem_write(start,self.blob[start-0x301000:start-0x301000+234])
        start=self.info["basic_night_range"]
        m.mem_write(start,self.blob[start-0x301000:start-0x301000+260])
        return m

    def execute(self,m,start,*ends,callback=None):
        def hook(vm,a,size,_):
            if a in ends: vm.emu_stop()
            elif callback: callback(vm,a)
        h=m.hook_add(UC_HOOK_CODE,hook)
        try: m.emu_start(start,0,count=10000)
        finally: m.hook_del(h)
        self.assertIn(m.reg_read(UC_X86_REG_EIP),ends)
        return m.reg_read(UC_X86_REG_EIP)

    def ret(self,m,value=None):
        if value is not None: m.reg_write(UC_X86_REG_EAX,value)
        sp=m.reg_read(UC_X86_REG_ESP);target=self.get(m,sp)
        m.reg_write(UC_X86_REG_ESP,sp+4);m.reg_write(UC_X86_REG_EIP,target)

    def sync(self,m):
        m.reg_write(UC_X86_REG_ESP,STACK+0x8000);self.put(m,STACK+0x8000,STOP)
        calls=[]
        def native(vm,a):
            if a in [self.info[k] for k in ("basic_day_range","basic_night_range","weather_colour","set_colour","weather_description")]:
                calls.append(a)
                # Real basic range helper, with audited clear-sky branch.
                if a in (self.info["basic_day_range"],self.info["basic_night_range"]): self.assertEqual(self.get(vm,DATA+0x2008,1),2)
                else:self.ret(vm,123)
        self.execute(m,CODE,STOP,callback=native)
        return calls

    def weather(self,m):
        return [self.get(m,DATA+0x2000+i*8,width) for i,width in enumerate(self.info["widths"])]

    def gate(self,m,name):
        a=CODE+0x1000
        m.mem_write(a,env.gate_thunk(a,STATE,CODE,self.info,name))
        site=self.info["sites"][name]
        return self.execute(m,a,STOP,self.get(m,STACK+0x8000),site["address"]+len(bytes.fromhex(site["original"])))

    def test_day_forces_native_day_phase_without_clock_or_register_changes(self):
        m=self.vm();self.put(m,STATE,1)
        before={r:m.reg_read(r) for r in (UC_X86_REG_EDX,UC_X86_REG_EBX,UC_X86_REG_ESI,UC_X86_REG_EFLAGS)}
        self.assertEqual(self.gate(m,"day"),STOP)
        self.assertEqual(m.reg_read(UC_X86_REG_EAX),1)
        self.assertEqual(m.reg_read(UC_X86_REG_ESP),STACK+0x800c)
        self.assertEqual(bytes(m.mem_read(DATA+0x1000,8)),struct.pack("<d",45000.75))
        for r,v in before.items(): self.assertEqual(m.reg_read(r),v)

    def test_day_off_outside_battle_and_forecasts_replay_native_prologue(self):
        for mode in ("off","inactive","different-form","forecast-low","forecast-high"):
            m=self.vm();self.put(m,STATE,1)
            if mode=="off": self.put(m,STATE,0)
            if mode=="inactive": self.put(m,STATE+env.ACTIVE,0)
            if mode=="different-form": self.put(m,self.info["form_slot"],DATA+1)
            if mode=="forecast-low": self.put(m,STACK+0x8004,1)
            if mode=="forecast-high": self.put(m,STACK+0x8008,1)
            site=self.info["sites"]["day"]
            self.assertEqual(self.gate(m,"day"),site["address"]+9,mode)
            self.assertEqual(m.reg_read(UC_X86_REG_EAX),DATA)
            self.assertEqual(m.reg_read(UC_X86_REG_EDX),0x1234)
            self.assertEqual(m.reg_read(UC_X86_REG_EBP),STACK+0x7ffc)
            self.assertEqual(m.reg_read(UC_X86_REG_ESP),STACK+0x7f64)

    def test_clear_applies_real_calm_sea_enum_and_visibility_once(self):
        m=self.vm();self.put(m,STATE+4,1)
        before={r:m.reg_read(r) for r in (UC_X86_REG_EAX,UC_X86_REG_EDX,UC_X86_REG_ECX,UC_X86_REG_EBX,UC_X86_REG_ESI,UC_X86_REG_EDI,UC_X86_REG_EBP,UC_X86_REG_EFLAGS)}
        self.assertEqual(len(self.sync(m)),5)
        self.assertEqual(self.weather(m),[0,2,27000,5000,16000])
        self.assertEqual(self.get(m,STATE+env.CAPTURED),1)
        self.assertEqual(bytes(m.mem_read(DATA+0x2009,3)),b"\xaa"*3)
        self.assertEqual(self.sync(m),[])
        for r,v in before.items():self.assertEqual(m.reg_read(r),v)
        self.assertEqual(bytes(m.mem_read(DATA+0x1000,8)),struct.pack("<d",45000.75))

    def test_clear_off_restores_all_captured_conditions_and_refreshes_native_ui(self):
        m=self.vm();self.put(m,STATE+4,1);self.sync(m)
        self.put(m,STATE+4,0)
        self.assertEqual(len(self.sync(m)),3)
        self.assertEqual(self.weather(m),[8,8,3000,4000,3500])
        self.assertEqual(self.get(m,STATE+env.CAPTURED),0)
        self.assertEqual(self.sync(m),[])

    def test_real_native_flying_weather_and_visibility_use_forced_conditions(self):
        results=[]
        for clear in (False,True):
            m=self.vm();self.put(m,0x9f7a0c,DATA+0x5000)
            if clear:self.put(m,STATE+4,1);self.sync(m)
            row=[]
            for address,size in ((0x87e23c,234),(0x8b1d7c,114)):
                m.mem_write(address,self.blob[address-0x301000:address-0x301000+size])
                m.reg_write(UC_X86_REG_ESP,STACK+0x8000);self.put(m,STACK+0x8000,STOP)
                m.reg_write(UC_X86_REG_EAX,DATA);m.reg_write(UC_X86_REG_ECX,0);m.reg_write(UC_X86_REG_EDX,1)
                self.execute(m,address,STOP)
                row.append(m.reg_read(UC_X86_REG_EAX)&(0xff if size==114 else 0xffffffff))
            results.append(row)
        self.assertEqual(results,[[3500,0],[27000,1]])

    def test_clear_does_nothing_outside_battle_and_repeated_toggle_recaptures(self):
        m=self.vm();self.put(m,STATE+4,1);self.put(m,STATE+env.ACTIVE,0)
        self.assertEqual(self.sync(m),[]);self.assertEqual(self.weather(m),[8,8,3000,4000,3500])
        self.put(m,STATE+env.ACTIVE,DATA);self.sync(m)
        self.put(m,STATE+4,0);self.sync(m);self.put(m,DATA+0x2000,6)
        self.put(m,STATE+4,1);self.sync(m);self.put(m,STATE+4,0);self.sync(m)
        self.assertEqual(self.weather(m)[0],6)

    def test_native_weather_changes_are_suspended_only_when_enabled_and_active(self):
        for enabled,active in ((0,1),(1,0),(1,1)):
            m=self.vm();self.put(m,STATE+4,enabled);self.put(m,STATE+env.ACTIVE,DATA if active else 0)
            end=self.gate(m,"weather")
            self.assertEqual(end,STOP if enabled and active else self.info["sites"]["weather"]["address"]+6)
            self.assertEqual(m.reg_read(UC_X86_REG_EAX),DATA)
            self.assertEqual(m.reg_read(UC_X86_REG_EDX),0x1234)

    def test_hide_restores_conditions_before_next_battle_and_ignores_other_forms(self):
        m=self.vm();self.put(m,STATE,1);self.put(m,STATE+4,1);self.sync(m)
        self.gate(m,"hide")
        self.assertEqual(self.weather(m),[8,8,3000,4000,3500])
        self.assertEqual(self.get(m,STATE+env.ACTIVE),0)
        self.assertEqual(self.get(m,STATE),1);self.assertEqual(self.get(m,STATE+4),1)
        # New FormShow does not reuse captured conditions from the old battle.
        m.reg_write(UC_X86_REG_ESP,STACK+0x8000);m.reg_write(UC_X86_REG_EAX,DATA)
        self.gate(m,"show");self.assertEqual(self.get(m,STATE+env.ACTIVE),DATA)
        self.assertEqual(self.get(m,STATE+env.CAPTURED),0)
        m.reg_write(UC_X86_REG_EAX,DATA+0x5000);m.reg_write(UC_X86_REG_ESP,STACK+0x8000)
        self.gate(m,"hide");self.assertEqual(self.get(m,STATE+env.ACTIVE),DATA)

    def test_idle_work_is_reentrant_safe_and_default_off_is_inert(self):
        m=self.vm();self.assertEqual(self.sync(m),[])
        self.put(m,STATE+4,1);self.put(m,STATE+env.BUSY,1)
        self.assertEqual(self.sync(m),[]);self.assertEqual(self.weather(m),[8,8,3000,4000,3500])

    def test_audit_rejects_changed_code_and_relocates_all_native_addresses(self):
        for a,n,_ in env.WINDOWS:
            b=bytearray(self.blob);b[a-0x301000+n-1]^=1
            with self.assertRaises(ValueError):env.discover(bytes(b),0x301000)
        delta=0x120000;b=bytearray(self.blob)
        for offset in audit.text_relocations():
            if offset+4<=len(b):struct.pack_into("<I",b,offset,(struct.unpack_from("<I",b,offset)[0]+delta)&0xffffffff)
        moved=env.discover(bytes(b),0x301000+delta)
        for key in ("clock_slot","form_slot","basic_day_range","weather_colour"):
            self.assertEqual(moved[key],self.info[key]+delta)
        report,blocks=env.plan(CODE,CODE+0x1000,moved)
        self.assertEqual(len(report["patches"]),5)
        for address,code,limit in blocks:self.assertLessEqual(len(code),limit)
        for change in report["patches"]:
            self.assertTrue(bytes.fromhex(change["replacement"]).startswith(b"\xe9"))

    def test_all_reviewed_aircraft_forecasts_get_daylight_including_after_midnight(self):
        for caller in self.info["air_forecast_returns"]:
            for date in (45000.9,45001.1):
                m=self.vm();self.put(m,STATE,1);self.put(m,STACK+0x8000,caller)
                m.mem_write(STACK+0x8004,struct.pack("<d",date))
                self.assertEqual(self.gate(m,"day"),caller)
                self.assertEqual(m.reg_read(UC_X86_REG_EAX),1)
                self.assertEqual(m.reg_read(UC_X86_REG_ESP),STACK+0x800c)
                self.assertEqual(bytes(m.mem_read(DATA+0x1000,8)),struct.pack("<d",45000.75))

    def test_aircraft_future_override_still_requires_enabled_active_battle(self):
        for mode in ("off","hidden","other-form"):
            m=self.vm();self.put(m,STATE,1);self.put(m,STACK+0x8000,self.info["air_forecast_returns"][0])
            m.mem_write(STACK+0x8004,struct.pack("<d",45001.1))
            if mode=="off":self.put(m,STATE,0)
            elif mode=="hidden":self.put(m,STATE+env.ACTIVE,0)
            else:self.put(m,self.info["form_slot"],DATA+1)
            self.assertEqual(self.gate(m,"day"),self.info["sites"]["day"]["address"]+9)

    def test_sunrise_and_battle_setup_searches_keep_natural_future_values(self):
        for caller in (0x8b51e5,0x8b547c,0x6af1ac):
            m=self.vm();self.put(m,STATE,1);self.put(m,STACK+0x8000,caller)
            m.mem_write(STACK+0x8004,struct.pack("<d",45001.1))
            self.assertEqual(self.gate(m,"day"),self.info["sites"]["day"]["address"]+9)

    def aircraft_vm(self,enabled):
        m=self.vm();self.put(m,STATE,int(enabled))
        # Native ship readiness reads the direct clock storage; aircraft
        # formations use its imported pointer. Both alias the same native time.
        self.put(m,self.info["clock_slot"],0xa7cab8)
        m.mem_write(0xa7cab8,struct.pack("<d",45000.75))
        site=self.info["sites"]["day"];target=CODE+0x1000
        m.mem_write(target,env.gate_thunk(target,STATE,CODE,self.info,"day"))
        m.mem_write(site["address"],b"\xe9"+struct.pack("<i",target-site["address"]-5))
        # Real EncodeTime ABI: return an x87 interval, consuming milliseconds.
        m.mem_write(DATA+0x7000,struct.pack("<d",3/24))
        m.mem_write(0x32c94c,b"\xdd\x05"+struct.pack("<I",DATA+0x7000)+b"\xc2\x04\x00")
        for a,n in ((0x918ac8,294),(0x978118,432)):
            m.mem_write(a,self.blob[a-0x301000:a-0x301000+n])
        def natural(vm,address):
            if address==0x919518:
                self.ret(vm,0)  # This fixture has no night-capable scout aircraft.
            elif address==site["address"]+9:
                frame=vm.reg_read(UC_X86_REG_EBP)
                date=struct.unpack("<d",vm.mem_read(frame+8,8))[0]
                destination=self.get(vm,frame+4);old_frame=self.get(vm,frame)
                vm.reg_write(UC_X86_REG_EAX,1 if date==45000.75 else 2)
                vm.reg_write(UC_X86_REG_ESP,frame+16);vm.reg_write(UC_X86_REG_EBP,old_frame)
                vm.reg_write(UC_X86_REG_EIP,destination)
        return m,natural

    def test_native_launch_readiness_no_longer_rejects_future_night_when_forced(self):
        for enabled in (False,True):
            m,natural=self.aircraft_vm(enabled)
            self.execute(m,0x918ac8,STOP,callback=natural)
            self.assertEqual(m.reg_read(UC_X86_REG_EAX)&0xff,int(enabled))
            self.assertEqual(m.reg_read(UC_X86_REG_ESP),STACK+0x8004)

    def test_native_aircraft_return_warning_uses_forced_day_at_arrival(self):
        for enabled in (False,True):
            m,natural=self.aircraft_vm(enabled)
            formation=DATA+0x6000;self.put(m,formation+0x4d,DATA)
            m.reg_write(UC_X86_REG_EBX,formation)
            self.put(m,STACK+0x9000-0xc,3);self.put(m,STACK+0x9000-8,0)
            # Execute the actual current/arrival daylight warning decision,
            # after the native distance calculation has supplied a 3h flight.
            self.execute(m,0x9781d3,0x97822a,callback=natural)
            self.assertEqual(m.reg_read(UC_X86_REG_EAX)&0xff,0 if enabled else 1)

    def test_map_daylight_skips_only_shading_after_native_solar_output(self):
        for mode in ("forced","off","inactive","campaign-map"):
            m=self.vm();self.put(m,STATE,int(mode!="off"))
            if mode=="inactive":self.put(m,STATE+env.ACTIVE,0)
            frame=STACK+0x8000;sp=frame-0xc8
            m.reg_write(UC_X86_REG_EBP,frame);m.reg_write(UC_X86_REG_ESP,sp)
            for i,v in enumerate((0x5678,0x4567,0x3456)):self.put(m,sp+i*4,v)
            self.put(m,frame,STACK+0x9000)
            caller=self.info["shadow_battle_return"] if mode!="campaign-map" else 0x63ba52
            self.put(m,frame+4,caller);self.put(m,frame+8,DATA+0x6100)
            vector=struct.pack("<3i",123,-456,789);m.mem_write(DATA+0x6100,vector)
            site=self.info["sites"]["shadow"];a=CODE+0x2000
            m.mem_write(a,env.shadow_thunk(a,STATE,self.info))
            m.mem_write(self.info["shadow_exit"],self.blob[0x567097-0x301000:0x5670a0-0x301000])
            end=self.execute(m,a,caller,site["address"]+5)
            self.assertEqual(end,caller if mode=="forced" else site["address"]+5)
            self.assertEqual(bytes(m.mem_read(DATA+0x6100,12)),vector)
            if mode=="forced":
                self.assertEqual(m.reg_read(UC_X86_REG_ESP),frame+24)
                self.assertEqual(m.reg_read(UC_X86_REG_EBP),STACK+0x9000)
                for r,v in ((UC_X86_REG_EDI,0x5678),(UC_X86_REG_ESI,0x4567),(UC_X86_REG_EBX,0x3456)):self.assertEqual(m.reg_read(r),v)
            else:self.assertEqual(m.reg_read(UC_X86_REG_EDX),1)


class EnvironmentProtocolTests(unittest.TestCase):
    def test_flags_use_guarded_ui_transaction_and_missing_old_hook_requires_restart(self):
        saved=dict(pid=1,mailbox=1000,layout={},battle_environment=dict(state=2000))
        before=dict(sha256="snapshot",main=100,player=200,ships=[],values=dict(force_daytime=0,clear_weather=0))
        memory={1000:0,2000:0,2004:0}; writes=[]; records=[]
        def write(handle,address,data):
            writes.append((address,data))
            if address==1032:
                records.extend(struct.iter_unpack("<4I",data))
            if address==1000:
                for a,old,new,width in records:
                    self.assertEqual(memory[a],old);memory[a]=new
                memory[1000]=2
        with patch.object(live,"session",return_value=(saved,1)),patch.object(live,"snapshot",return_value=before),\
             patch.object(live,"integer",side_effect=lambda h,a,width=4:memory.get(a,0)),\
             patch.object(live.memory,"write",side_effect=write),patch.object(live,"wake"),patch.object(live.rt.K,"CloseHandle"):
            result=live.edit(1,dict(force_daytime=1,clear_weather=1),"snapshot")
            self.assertTrue(result["ok"]);self.assertEqual(records,[(2000,0,1,4),(2004,0,1,4)])
            for key in env.FLAGS:
                for invalid in (True,-1,2,"1"):
                    with self.assertRaises(ValueError): live.edit(1,{key:invalid},"snapshot")
            del saved["battle_environment"]
            with self.assertRaisesRegex(ValueError,"Restart"): live.edit(1,dict(force_daytime=1),"snapshot")
            self.assertEqual(len(writes),3)


if __name__=="__main__":unittest.main()
