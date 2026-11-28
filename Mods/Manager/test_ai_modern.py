"""AI designs and the modern options: the pass run by the generated code against stand-in game functions."""
from pathlib import Path
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE/"vendor"), str(HERE.parent/"CampaignOverhaul")]
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_EDI, UC_X86_REG_ESI, UC_X86_REG_ESP
import ai_modern as ai
import modern_tree as tree

PAGE, STUBS, DESIGN, NATION, EXT, BACK, STACK = 0x100000, 0x200000, 0x300000, 0x310000, 0x320000, 0x330000, 0x34F000
ALL = (tree.NUCLEAR_PROPULSION, tree.RAILGUN, tree.SUPER_HEAVY, tree.HYPERSONIC, tree.LASERS)


def stubs(budget, balance, research, heavy, ssm, spare, rail_need, light=0, style=0, load=0, capacity=100):
    """Stand-ins: name -> code. Power needs one MW per laser plus rail_need for a railgun battery. style: what Pos
    answers for every nation-name part (non-zero: a gun-missile nation); load, capacity: topside points."""
    known = b"".join(b"\x81\xfa"+struct.pack("<I", r)+b"\x74"+bytes([8*(len(research)-1-i)+3]) for i, r in enumerate(research))
    return dict(
        recompute=b"\xc3", get_nation=b"\xb8"+struct.pack("<I", NATION)+b"\xc3",
        has_research=known+b"\x33\xc0\xc3\xb8\x01\x00\x00\x00\xc3",
        monthly_balance=b"\xb8"+struct.pack("<i", balance)+b"\xc3", modified_budget=b"\xb8"+struct.pack("<i", budget)+b"\xc3",
        random=b"\x33\xc0\xc3",
        count_missiles=b"\x80\xfa\x04\x74\x0d\x80\xfa\x0e\x74\x0e\x80\xfa\x03\x74\x0f\x33\xc0\xc3"   # heavy SSM, any SSM, light SAM
                       + b"\xb8"+struct.pack("<I", heavy)+b"\xc3"+b"\xb8"+struct.pack("<I", ssm)+b"\xc3"
                       + b"\xb8"+struct.pack("<I", light)+b"\xc3",
        pos=b"\xb8"+struct.pack("<I", style)+b"\xc3", topside_load=b"\xb8"+struct.pack("<I", load)+b"\xc3",
        topside_points=b"\xb8"+struct.pack("<I", capacity)+b"\xc3",
        ext=b"\xb8"+struct.pack("<I", EXT)+b"\xc3",
        power=b"\x0f\xb6\x05"+struct.pack("<I", EXT)+b"\x80\x3d"+struct.pack("<I", DESIGN+ai.ELEVATION)+b"\x02\x75\x05"
              + b"\x05"+struct.pack("<I", rail_need)+b"\xba"+struct.pack("<I", spare)+b"\xc3")


class AIModernTests(unittest.TestCase):
    def design(self, *, kind=0, tons=30000, drive=2, calibre=16, weight_left=500, budget=120000, balance=2000,
               funds=50000, research=ALL, heavy=2, ssm=4, spare=30, rail_need=20, trim_pass=0, **point_defence):
        code = stubs(budget, balance, research, heavy, ssm, spare, rail_need, **point_defence)
        at = {name: STUBS+0x100*i for i, name in enumerate(code)}
        info = dict(site=0x7B6B03, original=ai.SITE_BYTES, **{k: at[k] for k in ai.NATIVE})
        blocks, plans = ai.build(PAGE, info, at["ext"], at["power"])
        vm = Uc(UC_ARCH_X86, UC_MODE_32)
        for address in (PAGE, STUBS, DESIGN, NATION, EXT, BACK, STACK & ~0xFFFF): vm.mem_map(address, 0x10000)
        for block in blocks: vm.mem_write(block["address"], bytes.fromhex(block["bytes"]))
        for name, body in code.items(): vm.mem_write(at[name], body)
        vm.mem_write(BACK, b"\xc3")
        for field, size, value in ((0x2C, "i", tons), (0x6D, "i", calibre), (ai.TYPE, "B", kind), (ai.DRIVE, "B", drive),
                                   (ai.ELEVATION, "B", 0), (ai.WEIGHT_LEFT, "i", weight_left)):
            vm.mem_write(DESIGN+field, struct.pack("<"+size, value))
        vm.mem_write(NATION+ai.FUNDS, struct.pack("<i", funds))
        vm.mem_write(STACK, struct.pack("<I", BACK))
        for reg, value in ((UC_X86_REG_EAX, DESIGN), (UC_X86_REG_ESI, trim_pass), (UC_X86_REG_EDI, 0x77), (UC_X86_REG_ESP, STACK)):
            vm.reg_write(reg, value)
        vm.emu_start(PAGE, BACK, count=20000)
        self.assertEqual(plans[0]["replacement"][:2], "e8")
        self.assertEqual((vm.reg_read(UC_X86_REG_ESI), vm.reg_read(UC_X86_REG_EDI)), (trim_pass, 0x77))   # pushad/popad
        drive, elevation = vm.mem_read(DESIGN+ai.DRIVE, 1)[0], vm.mem_read(DESIGN+ai.ELEVATION, 1)[0]
        return drive, elevation, struct.unpack("<I", vm.mem_read(EXT, 4))[0]

    def test_a_rich_nation_fits_everything_its_ship_can_carry(self):
        self.assertEqual(self.design(), (5, 2, 0x300 | 8))                      # nuclear, railgun, super, hyper, 8 lasers

    def test_lasers_stop_at_the_spare_power(self):
        self.assertEqual(self.design(spare=25), (5, 2, 0x300 | 5))              # railgun 20 MW + 5 lasers
        self.assertEqual(self.design(spare=15), (5, 0, 0x300 | 8))              # no railgun: lasers alone fit

    def test_a_modest_economy_gets_only_the_cheap_options(self):
        self.assertEqual(self.design(balance=500, funds=15000), (2, 0, 0x100 | 4))   # hypersonic, half the lasers

    def test_a_struggling_economy_changes_nothing(self):
        for balance, funds in ((-1, 10**6), (5000, 9999)):                     # losing money, or under a month of cash
            self.assertEqual(self.design(balance=balance, funds=funds), (2, 0, 0))

    def test_an_overweight_design_gets_every_option_undone(self):
        self.assertEqual(self.design(weight_left=-1), (2, 0, 0))

    def test_point_defence_follows_the_nations_style_size_and_economy(self):
        import modern_extension as extension
        ram, spare = extension.RAM_BIT, 1 << extension.SPARE_SHIFT
        searam = lambda n: n << extension.SEARAM_SHIFT
        gm = lambda n: n << extension.GUN_MISSILE_SHIFT
        pd = (tree.SEARAM, tree.GUN_MISSILE, tree.RAM)
        for options, expected in ((dict(light=2), ram | searam(2) | spare),             # US style: RAM, two SeaRAM
                                  (dict(light=0, tons=5000), searam(1) | spare),         # no light SAMs: no RAM
                                  (dict(light=2, style=1), gm(6) | spare),              # Russian style: six Kashtan
                                  (dict(style=1, tons=10000), gm(2) | spare),
                                  (dict(style=1, balance=500, funds=15000), gm(6)),     # tier 1: no spares
                                  (dict(light=2, load=150), ram),                       # over the topside: mounts undone
                                  (dict(style=1, weight_left=-1), 0),                   # overweight: undone
                                  (dict(style=1, tons=1000), 0)):                       # too small
            self.assertEqual(self.design(research=pd, **options)[2], expected, options)
        self.assertEqual(self.design(research=(tree.RAM,), light=2)[2], ram)           # RAM without SeaRAM research

    def test_anti_torpedo_launchers_follow_research_size_weight_and_topside(self):
        import modern_extension as extension
        att = lambda n: n << extension.ATT_SHIFT
        both = (tree.SEARAM, tree.ANTI_TORPEDO)
        for research, options, expected in (((tree.ANTI_TORPEDO,), dict(), att(3)),                 # 30000 t
                                            ((tree.ANTI_TORPEDO,), dict(tons=8000), att(2)),
                                            ((tree.ANTI_TORPEDO,), dict(tons=2000, balance=500, funds=15000), att(1)),
                                            ((tree.ANTI_TORPEDO,), dict(load=150), 0),              # over the topside
                                            ((tree.ANTI_TORPEDO,), dict(weight_left=-1), 0),        # overweight
                                            ((tree.ANTI_TORPEDO,), dict(tons=1000), 0),             # too small
                                            ((tree.ANTI_TORPEDO,), dict(style=1), att(3)),          # every style
                                            (both, dict(), att(3) | 2 << extension.SEARAM_SHIFT | 1 << extension.SPARE_SHIFT),
                                            ((tree.SEARAM,), dict(), 2 << extension.SEARAM_SHIFT | 1 << extension.SPARE_SHIFT)):
            self.assertEqual(self.design(research=research, **options)[2], expected, (research, options))

    def test_research_hull_and_drive_rules_hold(self):
        self.assertEqual(self.design(research=()), (2, 0, 0))
        self.assertEqual(self.design(kind=9, tons=5000, heavy=0, ssm=0), (2, 0, 2))        # destroyer: two lasers only
        self.assertEqual(self.design(kind=4, tons=30000, heavy=2), (2, 0, 0x100 | 8))      # CL: not nuclear, no super
        self.assertEqual(self.design(research=(tree.RAILGUN, tree.LASERS)), (2, 0, 8))     # oil drive: no railgun

    def test_the_pass_runs_once_per_design(self):
        self.assertEqual(self.design(trim_pass=1), (2, 0, 0))


if __name__ == "__main__":
    unittest.main()
