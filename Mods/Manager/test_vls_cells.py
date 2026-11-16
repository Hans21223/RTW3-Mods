"""Native VLS arc/ammunition execution and designer event-contract checks."""
from pathlib import Path
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE/"vendor"), str(HERE.parent/"CampaignOverhaul")]
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import *
from test_missile_range import NativeWorld
from test_missile_ai import BASE, CODE, DATA, STACK, FORM, SHIP, STOP
import vls_cells as vls
import modern_tree as tree
import modern_research as audit
import runtime_registry as registry

VLS = CODE+0x20000


class VLSWorld(NativeWorld):
    def __init__(self, blob):
        super().__init__(blob)
        self.vm.mem_map(VLS, 0x10000)
        self.vls_info = vls.discover(blob, BASE)
        self.vls = vls.build(VLS, self.vls_info)
        for block in self.vls["blocks"]:
            self.vm.mem_write(block["address"], bytes.fromhex(block["bytes"]))
        for plan in self.vls["patches"]:
            self.vm.mem_write(plan["address"], bytes.fromhex(plan["replacement"]))
        self.stubs = {}
        self.vm.hook_add(UC_HOOK_CODE, self.boundary)

    def boundary(self, vm, address, size, data):
        if address in self.stubs:
            result, cleanup = self.stubs[address]()
            self.ret(result, cleanup)

    def extra(self, kind, cells, position='P'):
        """Another mount on the designer ship (its list has room for four more)."""
        mount = self.allocate(); self.put(mount+0xE, kind, 1); self.put(mount+4, cells); self.put(mount+8, ord(position), 2)
        items = self.get(SHIP+0x9E); count = self.get(items+8)
        self.put(self.get(items+4)+4*count, mount); self.put(items+8, count+1)

    def topside(self, mount):
        """Run the native nested per-mount topside routine with its parent frame."""
        parent, sp = STACK+0xA000, STACK+0x8000
        for offset, value in ((-0x1C, 0), (-0x14, mount), (-0x10, 0), (-0xC, 5), (-8, 0), (-4, SHIP)):
            self.put(parent+offset, value)
        self.vm.mem_write(sp, struct.pack("<II", STOP, parent))
        self.vm.reg_write(UC_X86_REG_ESP, sp); self.vm.reg_write(UC_X86_REG_EBP, STACK+0x9000)
        self.vm.emu_start(0x94A23C, STOP, count=100000)
        assert self.vm.reg_read(UC_X86_REG_ESP) == sp+4
        return self.get(parent-8), self.get(parent-0xC)-5

    def bank(self, kind=5, cells=32, loaded=None, side=0, position='P'):
        mount = self.ship(SHIP, side, ((kind, cells if loaded is None else loaded, cells, 0),))[0]
        self.put(mount+8, ord(position), 2)
        return mount

    def designer(self, kind=5, cells=4, position='P'):
        mount = self.bank(kind, cells, position=position)
        self.put(mount, self.vls_info["mount_vmt"])
        self.put(FORM+0xE67, 1, 1); self.put(FORM+0xE6C, SHIP)
        self.put(FORM+0x9B4, DATA+0x8000); self.put(DATA+0x8100+0x28, mount)
        self.put(FORM+0xC63, DATA+0xA000); self.put(SHIP+0x2C, 10000); self.put(SHIP+0xE4, 1970)   # BuildYear
        self.stubs[self.vls_info["selected"]] = lambda: (DATA+0x8100, 0)
        # Run actual MissileTypeOK, supplying only the nation's tech ownership.
        self.known = True; self.missing = set(); self.research_queries = []
        def research():
            self.research_queries.append(self.vm.reg_read(UC_X86_REG_EDX))
            return int(self.known and self.research_queries[-1] not in self.missing), 0
        self.stubs[0x729FA4] = research
        return mount


class VLSTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blob = (HERE/"native-designer-inspection.text.bin").read_bytes()
        cls.info = vls.discover(cls.blob, BASE)

    def world(self): return VLSWorld(self.blob)

    def test_vls_all_round_arcs_for_all_native_missile_types(self):
        w = self.world()
        for kind in range(1, 7):
            for cells in vls.CELLS:
                mount = w.bank(kind, cells)
                for bearing in (0, 1, 45, 90, 180, 270, 359):
                    self.assertTrue(w.call(w.info["arc"], mount, bearing) & 0xFF)

    def test_torpedoes_catapults_wing_mounts_and_conventional_arcs_unchanged(self):
        original = NativeWorld(self.blob); patched = self.world()
        for kind in range(8):
            for cells, position in ((4,'P'), (4,'J'), (6,'P'), (5,'J')):
                a = original.ship(SHIP, mounts=((kind,cells,cells,0),))[0]
                original.put(a+8, ord(position), 2)
                b = patched.bank(kind,cells,position=position)
                for bearing in (0,90,180,270):
                    self.assertEqual(patched.call(patched.info['arc'],b,bearing)&0xFF,
                                     original.call(original.info['arc'],a,bearing)&0xFF)

    def test_real_native_launch_never_exceeds_remaining_cells(self):
        for side in (0,1):
            # Native light SAMs are air-defence only (surface range is zero).
            for kind in (1,2,4,5,6):
                w = self.world(); mount = w.bank(kind,64,loaded=3,side=side)
                target = w.target(side=1-side); w.see(SHIP,[target],15000)
                if kind == 6: w.geometry_distance = 5500
                count = w.call(w.info['fire'], FORM, mount, SHIP,
                               args=(64,0,target+0xA1C,target))
                self.assertEqual(count,3,(kind,side))
                self.assertEqual(len(w.native_launches),3)
                self.assertEqual(w.get(mount+0xF1),0)
                self.assertEqual(w.get(mount+0xF),0)
                again = w.call(w.info['fire'],FORM,mount,SHIP,
                               args=(64,180,target+0xA1C,target))
                self.assertEqual(again,0)
                self.assertEqual(len(w.native_launches),3)

    def test_light_sam_keeps_native_air_defence_only_role(self):
        w=self.world(); mount=w.bank(3,32);target=w.target()
        self.assertEqual(w.call(w.info['range'],0,3),0)
        self.assertEqual(w.call(w.info['fire'],FORM,mount,SHIP,args=(8,0,target+0xA1C,target)),0)
        self.assertEqual(w.get(mount+0xF1),32)

    def test_real_native_air_defence_spends_only_available_cells(self):
        for kind in (1,2,3):
            for available in (1,2,3,8,64):
                for single in (0,1):
                    w=self.world(); mount=w.bank(kind,64,loaded=available)
                    count=w.call(0x917F54,SHIP,kind,single)
                    expected=min(available,1 if single else 2)
                    self.assertEqual(count,expected)
                    self.assertEqual(w.get(mount+0xF1),available-expected)
                    self.assertEqual(w.get(mount+0xF),0)
                    if available==expected:
                        self.assertEqual(w.call(0x917F54,SHIP,kind,single),0)

    def test_native_range_and_damaged_mount_gates_still_block_fire(self):
        for mode in ('far','near','damaged'):
            w = self.world(); mount = w.bank(); target = w.target(); w.see(SHIP,[target],15000)
            if mode=='far': w.geometry_distance=100000
            if mode=='near': w.geometry_distance=1
            if mode=='damaged': w.put(mount+0xF0,1,1)
            self.assertEqual(w.call(w.info['fire'],FORM,mount,SHIP,args=(8,0,target+0xA1C,target)),0)
            self.assertEqual(w.get(mount+0xF1),32)
            self.assertEqual(w.native_launches,[])

    def test_native_automatic_contact_selector_fires_vls(self):
        w = self.world(); mount = w.bank(5,32); target = w.target(); w.see(SHIP,[target],15000)
        w.call(w.info['selector'])
        self.assertGreater(len(w.native_launches),0)
        self.assertEqual(w.get(mount+0xF1)+len(w.native_launches),32)
        self.assertLessEqual(len(w.native_launches),32)

    def test_native_initial_loaded_rounds_equal_cell_count_and_no_reserve_reload(self):
        w = self.world()
        for count in vls.CELLS:
            mount = w.bank(5,count,loaded=0)
            w.vm.reg_write(UC_X86_REG_EDI,mount)
            w.vm.emu_start(0x6CB940,0x6CB949,count=10)
            self.assertEqual(w.get(mount+0xF1),count)
            self.assertEqual(w.get(mount+0xF),0)
            self.assertFalse(w.call(0x9258CC,mount)&0xFF)
            w.put(mount+0xF1,0)
            self.assertFalse(w.call(0x9258CC,mount)&0xFF)
            self.assertEqual(w.get(mount+0xF1),0)

    def test_vls_quantity_is_accepted_without_changing_conventional_nation_limits(self):
        w=self.world();w.stubs[0x72D444]=lambda:(4,0)
        for kind,cells,position,expected in ((5,64,'P',1),(1,8,'P',1),
                                            (5,4,'P',1),(5,5,'P',0),
                                            (5,8,'J',1),(5,5,'J',0),(0,8,'P',0)):
            mount=w.bank(kind,cells,position=position)
            self.assertEqual(w.call(0x7297D8,DATA+0xA000,9,mount,args=(DATA+0xB000,))&0xFF,expected)

    def test_complete_native_mount_validator_accepts_vls_on_oversized_dd_and_cruiser(self):
        from test_destroyer_torpedoes import DestroyerTorpedoTests
        helper=DestroyerTorpedoTests();helper.blob=self.blob
        vm,_,_=helper.machine()
        for kind,tons in ((9,10000),(4,20000),(3,50000)):
            for missile in range(1,7):
                for count in vls.CELLS:
                    self.assertTrue(helper.validate(vm,tons,kind,quantity=count,mount_type=missile))

    def test_conversion_changes_only_cells_and_reloads_and_refreshes_native_design(self):
        w = self.world(); mount = w.designer(); w.put(mount+0xF,20)
        calls=[]
        for name in ('recalculate','refresh','refresh_design','sync_preview'):
            w.stubs[w.vls_info[name]] = lambda name=name: (calls.append(name) or 0,0)
        for count, handler in zip(vls.CELLS,w.vls['handlers']):
            before=bytes(w.vm.mem_read(mount,0x100))
            w.call(handler,FORM)
            self.assertEqual(w.get(mount+4),count); self.assertEqual(w.get(mount+0xF),0)
            after=bytes(w.vm.mem_read(mount,0x100))
            self.assertEqual(before[:4],after[:4]); self.assertEqual(before[8:0xF],after[8:0xF])
            self.assertEqual(before[0x13:],after[0x13:])
        self.assertEqual(calls,['recalculate','refresh','refresh_design','sync_preview']*4)
        self.assertTrue(w.research_queries)
        self.assertEqual(set(w.research_queries),{1903}|{i for i,_ in tree.VLS_DENSE}|set(tree.VLS_CELLS.values()))

    def test_each_size_needs_its_research_and_hull_room_for_all_banks(self):
        handlers=self.world().vls['handlers']
        for count,handler in zip(vls.CELLS,handlers):
            gate=tree.VLS_CELLS[count]
            for tons,missing,converted in ((count*80,{2206,2209},True),(count*80-1,{2206,2209},False),
                                           (count*64,{2209},True),(count*64-1,{2209},False),
                                           (count*51,set(),True),(count*51-1,set(),False),(10**6,{gate},False)):
                w=self.world();mount=w.designer();w.put(SHIP+0x2C,tons);w.missing=missing
                for name in ('recalculate','refresh','refresh_design','sync_preview'):w.stubs[w.vls_info[name]]=lambda:(0,0)
                messages=[];w.stubs[w.vls_info['message']]=lambda:(messages.append(1) or 0,0)
                w.call(handler,FORM)
                self.assertEqual((w.get(mount+4),len(messages)),(count,0) if converted else (4,1),(count,tons,missing))
        # Hulls laid down before 1960 cannot take VLS even with research and room.
        for year, converted in ((1959, False), (1960, True)):
            w=self.world();mount=w.designer();w.put(SHIP+0xE4,year)
            for name in ('recalculate','refresh','refresh_design','sync_preview'):w.stubs[w.vls_info[name]]=lambda:(0,0)
            messages=[];w.stubs[w.vls_info['message']]=lambda:(messages.append(1) or 0,0)
            w.call(handlers[0],FORM)
            self.assertEqual((w.get(mount+4),len(messages)),(8,0) if converted else (4,1),year)
        # Other VLS banks count, side banks too; conventional launchers do not.
        for tons,converted in ((56*51,True),(56*51-1,False)):
            w=self.world();mount=w.designer();w.put(SHIP+0x2C,tons)
            w.extra(2,32);w.extra(5,4);w.extra(5,16,'J')
            for name in ('recalculate','refresh','refresh_design','sync_preview'):w.stubs[w.vls_info[name]]=lambda:(0,0)
            w.stubs[w.vls_info['message']]=lambda:(0,0)
            w.call(handlers[0],FORM)
            self.assertEqual(w.get(mount+4),8 if converted else 4)

    def test_vls_weighs_its_loaded_cells_and_launchers_keep_native_weight_but_medium_ssms_half(self):
        lighter=[i for i,_ in tree.VLS_LIGHT]
        for owned,percent in ((0,100),(1,80),(2,70),(3,60)):
            w=self.world()
            for kind in range(1,7):
                mount=w.designer(kind=kind,cells=8);w.missing=set(lighter[owned:])
                for cells in vls.CELLS:
                    w.put(mount+4,cells);w.put(mount+0xF,0)
                    w.call(0x9511BC,mount,0,0)
                    quad=vls.QUAD_WEIGHT if kind==3 and tree.QUAD_PACK in lighter[:owned] else 1   # four light SAMs a cell
                    self.assertEqual(w.get(mount+0xA),-(-cells*vls.CELL_TENTHS[kind-1]*quad*percent//1000),(kind,cells,percent))
        native=NativeWorld(self.blob);patched=self.world()
        native.stubs={};native.vm.hook_add(UC_HOOK_CODE,VLSWorld.boundary.__get__(native))
        for world in (native,patched):world.stubs[0x729FA4]=lambda:(1,0)
        for kind,cells,reloads,position in ((5,4,8,'P'),(2,2,20,'P'),(4,4,0,'J'),(0,4,0,'P'),(0,8,0,'J')):
            weights=[]
            for world in (native,patched):
                mount=VLSWorld.bank(world,kind,cells,position=position);world.put(mount+0xF,reloads)
                world.call(0x9511BC,mount,21,4);weights.append(world.get(mount+0xA))
            lighter=4*(cells+reloads) if kind==5 else 0     # medium SSM launchers: 4 t a missile and reload, not 8
            self.assertEqual(weights[0]-lighter,weights[1],(kind,cells,position))

    def test_vls_topside_is_one_point_per_8_cells_and_launchers_unchanged(self):
        w=self.world();w.stubs[0x729FA4]=lambda:(1,0)
        for kind in range(1,7):
            for cells in vls.CELLS:
                self.assertEqual(w.topside(w.bank(kind,cells)),(cells//8,cells//8))
        native=NativeWorld(self.blob);native.stubs={0x729FA4:lambda:(1,0)}
        native.vm.hook_add(UC_HOOK_CODE,VLSWorld.boundary.__get__(native))
        for kind,cells,position in ((5,4,'P'),(2,2,'P'),(4,4,'J'),(1,1,'P')):
            a=native.ship(SHIP,0,((kind,cells,cells,0),))[0];native.put(a+8,ord(position),2)
            b=w.bank(kind,cells,position=position)
            self.assertEqual(w.topside(b),VLSWorld.topside(native,a),(kind,cells))

    def draw(self, world, kind, cells, heading=90, train=45, position='P'):
        """Run the native mount drawing; record polar points and polygon calls."""
        mount = VLSWorld.bank(world, kind, cells, position=position)
        world.put(mount, self.info['mount_vmt']); world.put(mount+0x1B, train); world.put(SHIP+0xA28, heading)
        drawer, table, canvas, poly = DATA+0x9000, DATA+0x9800, DATA+0x9400, DATA+0xF000
        world.put(drawer, table); world.put(table+0x1C4, poly); world.put(drawer+0x2E4, canvas)
        world.put(canvas+0x44, DATA+0x9500); world.put(canvas+0x48, DATA+0x9600)
        points, polygons = [], []
        def vertex():
            frame = world.get(world.vm.reg_read(UC_X86_REG_ESP)+4)
            points.append((world.get(frame-0x10) - (1 << 32) * (world.get(frame-0x10) >> 31),
                           world.get(frame-0x18), world.get(frame-0x14)))
            return 0, 0
        world.stubs.update({0x41F760: lambda: (0, 0), 0x41F798: lambda: (0, 0), 0x41FA20: lambda: (0, 0),
                            0x41F63C: lambda: (0, 0), 0x309DB0: lambda: (0, 0), 0x928A50: lambda: (0, 0),
                            0x83E530: vertex, poly: lambda: (polygons.append(world.vm.reg_read(UC_X86_REG_ECX)) or 0, 0)})
        world.call(0x83E5D0, DATA+0x9F00, mount, drawer, args=(SHIP,))
        return points, polygons

    def test_vls_banks_draw_as_cell_grids_aligned_with_the_ship(self):
        table = vls.shapes()
        for offset, position in ((0, 'P'), (4, 'J')):   # side banks use the long layouts
            for size, cells in enumerate(vls.CELLS):
                points, polygons = self.draw(self.world(), 2, cells, position=position)
                expected = [struct.unpack_from('<iI', table, (((offset+size)*2+p)*25+i)*8) for p in (0, 1) for i in range(25)]
                self.assertEqual(points, [(a, d, 90) for a, d in expected if d], (position, cells))   # train ignored
                self.assertEqual(polygons, [24, 24])
        # Side banks are long and narrow: their outline spans further along the hull than across it.
        for cells in (16, 32, 64):
            across, along = vls.SIDE_MODULES[cells]
            self.assertGreater(along*340, across*260, cells)
        # Conventional launchers keep their native shapes and bearing.
        native = NativeWorld(self.blob); native.stubs = {}
        native.vm.hook_add(UC_HOOK_CODE, VLSWorld.boundary.__get__(native))
        self.assertEqual(self.draw(native, 2, 2), self.draw(self.world(), 2, 2))

    def test_cell_label_wrapper_preserves_native_arguments_and_stack(self):
        for cells,expected in ((32,' VLS cells ('),(4,' (')):
            w=self.world();mount=w.bank(5,cells);sp=STACK+0x8000
            registers={UC_X86_REG_EAX:123,UC_X86_REG_EBX:mount,UC_X86_REG_ECX:234,
                       UC_X86_REG_EDX:345,UC_X86_REG_ESI:456,UC_X86_REG_EDI:567,
                       UC_X86_REG_EBP:STACK+0x9000,UC_X86_REG_ESP:sp,UC_X86_REG_EFLAGS:0x246}
            for reg,value in registers.items():w.vm.reg_write(reg,value)
            w.vm.emu_start(0x5EE87B,0x5EE880,count=1000)
            self.assertEqual(w.vm.reg_read(UC_X86_REG_EIP),0x5EE880)
            self.assertEqual(w.vm.reg_read(UC_X86_REG_ESP),sp-4)
            ptr=w.get(sp-4);size=w.get(ptr-4)
            self.assertEqual(bytes(w.vm.mem_read(ptr,size*2)).decode('utf-16-le'),expected)
            for reg,value in registers.items():
                if reg!=UC_X86_REG_ESP:self.assertEqual(w.vm.reg_read(reg),value)

    def test_read_only_no_selection_wing_torpedo_and_unresearched_conversions_refused(self):
        for mode in ('read_only','selection','wing','torpedo','research'):
            w=self.world(); mount=w.designer(position='J' if mode=='wing' else 'P',kind=0 if mode=='torpedo' else 5)
            if mode=='wing':w.put(SHIP+0x2C,vls.SIDE_VLS_TONS-1)   # side banks need a big hull
            if mode=='read_only':w.put(FORM+0xE67,0,1)
            if mode=='selection':w.stubs[w.vls_info['selected']]=lambda:(0,0)
            if mode=='research':w.known=False
            messages=[]; w.stubs[w.vls_info['message']]=lambda:(messages.append('blocked') or 0,0)
            before=bytes(w.vm.mem_read(mount,0x100));w.call(w.vls['handlers'][0],FORM)
            self.assertEqual(bytes(w.vm.mem_read(mount,0x100)),before)
            self.assertEqual(messages,['blocked'])

    def test_side_vls_banks_pass_the_side_torpedo_tube_limit(self):
        # Design report, per mount (EDI): non-centreline mounts over 4 tubes error at 0x5D6A08.
        for kind,cells,position,allowed in ((5,64,'J',True),(2,8,'J',True),(0,5,'J',False),(5,5,'J',False),(0,5,'P',True)):
            w=self.world();mount=w.bank(kind,cells,position=position);reached=[]
            w.vm.hook_add(UC_HOOK_CODE,lambda vm,a,s,d:(reached.append(a),vm.emu_stop()) if a in (0x5D6A08,0x5D6A48) else None)
            w.vm.reg_write(UC_X86_REG_EDI,mount);w.vm.reg_write(UC_X86_REG_ESP,STACK+0x8000)
            w.vm.emu_start(0x5D69F5,0,count=10000)
            self.assertEqual(reached,[0x5D6A48 if allowed else 0x5D6A08],(kind,cells,position))

    def test_side_medium_and_heavy_sams_need_a_carrier_or_vls_research(self):
        # bnAddMissileClick, ESI form: after the centreline and SAM-type tests, AL decides the side mount.
        for kind,known,allowed,asked in ((4,True,True,True),(4,False,False,True),(5,False,True,False),(6,False,True,False)):
            w=self.world();w.designer();w.known=known;w.put(SHIP+0x9D3,kind,1)
            w.vm.reg_write(UC_X86_REG_ESI,FORM);w.vm.reg_write(UC_X86_REG_ESP,STACK+0x8000)
            w.vm.emu_start(0x5EEB44,0x5EEB4F,count=1000)
            self.assertEqual((bool(w.vm.reg_read(UC_X86_REG_EAX)&0xFF),w.vm.reg_read(UC_X86_REG_ESP)),(allowed,STACK+0x8000),kind)
            self.assertEqual(w.research_queries,[tree.VLS_CELLS[8]] if asked else [])

    def test_side_mounts_convert_on_big_hulls(self):
        for tons,converted in ((vls.SIDE_VLS_TONS,True),(vls.SIDE_VLS_TONS-1,False)):
            w=self.world();mount=w.designer(position='J');w.put(SHIP+0x2C,tons)
            for name in ('recalculate','refresh','refresh_design','sync_preview'):w.stubs[w.vls_info[name]]=lambda:(0,0)
            messages=[];w.stubs[w.vls_info['message']]=lambda:(messages.append(1) or 0,0)
            w.call(w.vls['handlers'][0],FORM)
            self.assertEqual((w.get(mount+4),len(messages)),(8,0) if converted else (4,1),tons)

    def test_native_menu_has_one_parent_four_cell_choices_and_native_owner(self):
        w=self.world(); popup=DATA+0xC000; root=DATA+0xC100
        w.put(FORM+0xA3C,popup); w.put(popup+0x44,root)
        made=[]; captions=[]; added=[]
        def create():
            self.assertEqual(w.vm.reg_read(UC_X86_REG_ECX),FORM)
            self.assertEqual(w.vm.reg_read(UC_X86_REG_EAX),w.vls_info['menu_vmt'])
            made.append(DATA+0xD000+len(made)*0x100);return made[-1],0
        def caption():
            ptr=w.vm.reg_read(UC_X86_REG_EDX);n=w.get(ptr-4)
            captions.append(bytes(w.vm.mem_read(ptr,n*2)).decode('utf-16-le'));return 0,0
        def add():
            added.append((w.vm.reg_read(UC_X86_REG_EAX),w.vm.reg_read(UC_X86_REG_EDX)));return 0,0
        w.stubs.update({w.vls_info['menu_create']:create,w.vls_info['menu_caption']:caption,w.vls_info['menu_add']:add})
        w.call(w.vls['locations']['ensure'],FORM);w.call(w.vls['locations']['ensure'],FORM)
        self.assertEqual(captions,['VLS cells (no reloads)','8 cells','16 cells','32 cells','64 cells'])
        self.assertEqual(added,[(made[0],child) for child in made[1:]]+[(root,made[0])])
        for child,handler in zip(made[1:],w.vls['handlers']):
            self.assertEqual(w.get(child+0x98),handler);self.assertEqual(w.get(child+0x9C),FORM)

    def test_vls_reload_edits_refused_by_both_native_commands(self):
        for method in (0x5EF2D4,0x5F6834):
            w=self.world();mount=w.designer(cells=32);messages=[]
            w.stubs[w.vls_info['message']]=lambda:(messages.append('no reloads') or 0,0)
            w.call(method,FORM)
            self.assertEqual(messages,['no reloads']);self.assertEqual(w.get(mount+0xF),0)
            w.known=False
            w.call(method,FORM)
            self.assertEqual(messages,['no reloads','no reloads'])

    def test_code_or_field_tampering_refused(self):
        for address,_,_ in vls.WINDOWS:
            b=bytearray(self.blob);b[address-BASE]^=1
            with self.assertRaisesRegex(ValueError,'refuses changed'):vls.discover(bytes(b),BASE)
        b=bytearray(self.blob);b[0x9339F4-BASE]^=1
        with self.assertRaises(ValueError):vls.discover(bytes(b),BASE)

    def test_aslr_and_allocation_reservations(self):
        delta=0x400000;b=bytearray(self.blob)
        for offset in audit.text_relocations():
            value=struct.unpack_from('<I',b,offset)[0];struct.pack_into('<I',b,offset,(value+delta)&0xFFFFFFFF)
        info=vls.discover(bytes(b),BASE+delta)
        self.assertEqual(info['centreline'],self.info['centreline']+delta)
        built=vls.build(VLS,info)
        ranges=sorted((x['address'],x['address']+len(bytes.fromhex(x['bytes']))) for x in built['blocks'])
        self.assertTrue(all(a[1]<=b[0] for a,b in zip(ranges,ranges[1:])))
        self.assertLess(ranges[-1][1],built['state'])
        self.assertTrue(all(VLS<=a<z<=VLS+0x10000 for a,z in ranges))
        order=[x['adapter'] for x in registry.plan(list(reversed(registry.REGISTRY)))]
        self.assertGreater(order.index('vls-cells'),order.index('battle-ai'))
        self.assertGreater(order.index('vls-cells'),order.index('live-cheats'))


if __name__=='__main__':unittest.main(verbosity=2)
