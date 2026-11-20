"""Missile defence by radar class and doctrine: the two hooks in the native SAM intercept, in the emulator."""
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE/"vendor"), str(HERE.parent/"CampaignOverhaul")]
from unicorn.x86_const import *
from test_modern_combat import World, NATION, MAIN, STACK, SHIP, DATA, FRAME
import struct
import modern_defence as defence
import modern_tree as tree
import modern_research as modern
import shell_doctrine as sd

INFO = modern.discover(open(HERE/"native-designer-inspection.text.bin", "rb").read(), 0x301000)["defence"]


class DefenceTests(unittest.TestCase):
    def ship(self, radar, down=0, handled=0, flags=0):
        self.world = w = World()
        w.vm.mem_write(SHIP, bytes(0xE20)); w.put(SHIP+defence.SHIP["nation"], 3)
        w.put(SHIP+defence.SHIP["radar"], radar); w.put(SHIP+defence.SHIP["radar_down"], down)
        w.put(SHIP+defence.SHIP["handled"], handled); w.put(SHIP+defence.SHIP["busy"], 0x0101, 2)
        w.put(w.doctrine+4, flags)
        return w

    def run_site(self, name, **registers):
        w, site = self.world, INFO["sites"][name]
        for reg, value in dict(dict(EAX=0x11, EBX=2, ECX=0x1234, EDX=0x22, ESI=SHIP, EDI=0x5678, EBP=FRAME, ESP=STACK+0x8000), **registers).items():
            w.vm.reg_write(globals()["UC_X86_REG_"+reg], value)
        w.vm.emu_start(site, site+6, count=5000)
        self.assertEqual((w.reg("ESI"), w.reg("EDI"), w.reg("ESP"), w.reg("EBX")), (SHIP, 0x5678, STACK+0x8000, 2))

    def test_a_phased_array_frees_busy_launchers_and_the_player_may_fire_one_sam(self):
        for radar, down, roll, flags, busy, single in ((5, 0, 0, 0, 0x0101, 0), (6, 0, defence.FREE[6]-1, 0, 0, 0),
                                                       (6, 0, defence.FREE[6], 0, 0x0101, 0), (7, 0, defence.FREE[7]-1, 0, 0, 0),
                                                       (7, 50, 0, 0, 0x0101, 0), (5, 0, 0, sd.CONSERVE, 0x0101, 1),
                                                       (7, 0, 0, sd.CONSERVE, 0, 1)):
            w = self.ship(radar, down, flags=flags)
            w.stubs[INFO["random"]] = lambda: roll
            self.run_site("shots")
            case = (radar, down, roll, flags)
            self.assertEqual(int.from_bytes(w.vm.mem_read(SHIP+defence.SHIP["busy"], 2), "little"), busy, case)
            self.assertEqual((w.reg("ECX"), w.reg("EDX"), w.reg("EAX")), (single, 2, SHIP), case)   # FireSAM(ship, kind, single)

    def mounts(self, *mounts):
        """(kind, tubes, loaded, reloads, destroyed) missile mounts on the ship; returns their addresses."""
        w = self.world
        lst, items = DATA+0x6000, DATA+0x6100
        w.put(SHIP+defence.MOUNTS, lst); w.put(lst+4, items); w.put(lst+8, len(mounts))
        out = []
        for i, (kind, tubes, loaded, reloads, destroyed) in enumerate(mounts):
            mount = DATA+0x6200+i*0x100; out.append(mount); w.put(items+4*i, mount)
            w.vm.mem_write(mount, bytes(0x100)); w.put(mount+defence.MOUNT["kind"], kind, 1); w.put(mount+defence.MOUNT["tubes"], tubes)
            w.put(mount+defence.MOUNT["loaded"], loaded); w.put(mount+defence.MOUNT["reloads"], reloads)
            w.put(mount+defence.MOUNT["destroyed"], destroyed, 1)
        return out

    def test_quad_packed_light_sams_come_back_three_times_in_four(self):
        loaded = defence.MOUNT["loaded"]
        for owned, kind, fired, roll, back in (({tree.QUAD_PACK}, 3, 2, 1, 2), ({tree.QUAD_PACK}, 3, 2, 0, 0), (set(), 3, 2, 1, 0),
                                               ({tree.QUAD_PACK}, 2, 2, 1, 0), ({tree.QUAD_PACK}, 3, 0, 1, 0)):
            w = self.ship(5); w.owned = owned
            w.stubs[INFO["random"]] = lambda: roll
            box, full, bank = self.mounts((3, 2, 0, 4, 0), (3, 16, 16, 0, 0), (3, 16, 6, 0, 0))   # a launcher, a full bank, a used one
            site, stop = INFO["sites"]["fired"], INFO["shot"] if fired else INFO["no_shot"]
            for reg, value in dict(EAX=fired, EBX=kind, ESI=SHIP, EDI=0x5678, ESP=STACK+0x8000).items():
                w.vm.reg_write(globals()["UC_X86_REG_"+reg], value)
            w.vm.emu_start(site, stop, count=5000)
            case = (owned, kind, fired, roll)
            self.assertEqual([w.get(m+loaded) for m in (box, full, bank)], [0, 16, 6+back], case)
            self.assertEqual((w.reg("EAX"), w.reg("EBX"), w.reg("ESI"), w.reg("ESP")), (fired-1 & 0xFFFFFFFF, kind, SHIP, STACK+0x8000), case)

    def test_light_sams_fired_at_aircraft_come_back_too(self):
        # Only the missile-defence FireSAM call had the refund, so against aircraft a cell held one missile (issue #1).
        loaded = defence.MOUNT["loaded"]
        for site in INFO["calls"].values():
            for owned, kind, fired, roll, back in (({tree.QUAD_PACK}, 3, 2, 1, 2), ({tree.QUAD_PACK}, 3, 2, 0, 0),
                                                   (set(), 3, 2, 1, 0), ({tree.QUAD_PACK}, 2, 2, 1, 0)):
                w = self.ship(5); w.owned = owned
                w.stubs[INFO["random"]] = lambda: roll
                w.stubs[INFO["fire_sam"]] = lambda: fired if (w.reg("EAX"), w.reg("EDX")) == (SHIP, kind) else -1
                box, full, bank = self.mounts((3, 2, 0, 4, 0), (3, 16, 16, 0, 0), (3, 16, 6, 0, 0))
                for reg, value in dict(EAX=SHIP, EDX=kind, ECX=0, EBX=0x1111, ESI=0x2222, EDI=0x5678, ESP=STACK+0x8000).items():
                    w.vm.reg_write(globals()["UC_X86_REG_"+reg], value)
                w.vm.emu_start(site, site+5, count=5000)                  # the patched call returns past itself
                case = (hex(site), owned, kind, roll)
                self.assertEqual([w.get(m+loaded) for m in (box, full, bank)], [0, 16, 6+back], case)
                self.assertEqual((w.reg("EAX"), w.reg("EBX"), w.reg("ESI"), w.reg("EDI"), w.reg("ESP")),
                                 (fired, 0x1111, 0x2222, 0x5678, STACK+0x8000), case)

    def test_the_battle_panel_shows_the_missiles_left(self):
        for mounts, shown in ((((1, 2, 2, 6, 0), (3, 16, 9, 0, 0), (4, 8, 3, 0, 0), (2, 8, 8, 0, 1), (0, 4, 4, 4, 0)), "SAM 17, SSM 3"),
                              (((5, 4, 0, 0, 0),), "SAM 0, SSM 0"), (((0, 4, 4, 0, 0),), ""), ((), "")):
            w = self.ship(5); self.mounts(*mounts)
            texts = []
            def set_text():
                pointer = w.reg("EDX")
                texts.append((w.reg("EAX"), bytes(w.vm.mem_read(pointer, 2*w.get(pointer-4))).decode("utf-16-le") if pointer else ""))
                return 0
            w.stubs[INFO["set_text"]] = set_text
            w.put(FRAME-0xC, SHIP)
            site = INFO["sites"]["readout"]
            for reg, value in dict(EAX=0x1ABE1, EBX=0x2345, ESI=0x4567, EDI=0x5678, EBP=FRAME, ESP=STACK+0x8000).items():
                w.vm.reg_write(globals()["UC_X86_REG_"+reg], value)
            w.vm.emu_start(site, site+7, count=20000)
            self.assertEqual(texts, [(0x1ABE1, shown)], mounts)
            self.assertEqual((w.reg("EBX"), w.reg("ESI"), w.reg("EDI"), w.reg("ESP")), (0x2345, 0x4567, 0x5678, STACK+0x8000))

    def test_better_radars_feel_saturation_less(self):
        for radar, down, handled, counted in ((5, 0, 4, 4), (6, 0, 4, 2), (7, 0, 4, 1), (7, 0, 1, 0), (7, 30, 4, 4), (0, 0, 0, 0)):
            self.ship(radar, down, handled)
            self.run_site("handled")
            self.assertEqual(self.world.reg("ECX"), counted, (radar, down, handled))

    def test_electronic_warfare_suites_add_to_the_decoy_chance(self):
        (jam, jam_year, jam_percent), (decoy, decoy_year, decoy_percent) = tree.EW_SUITES
        seeker, less = tree.EW_SEEKER
        for owned, year, percent in ((set(), 2010, 13), ({jam}, jam_year-1, 13), ({jam}, jam_year, 13+jam_percent),
                                     ({jam, decoy}, decoy_year-1, 13+jam_percent), ({jam, decoy}, 2010, 13+jam_percent+decoy_percent),
                                     ({jam, decoy, seeker}, 2010, 13+jam_percent+decoy_percent-less)):
            w = self.ship(5); w.owned = owned; w.put(SHIP+defence.DESIGN_YEAR, year)
            w.stubs[INFO["operational"]] = lambda: 1
            site = INFO["sites"]["decoy"]
            for reg, value in dict(EAX=0x11, EBX=2, ESI=13, EDI=3, EBP=SHIP, ESP=STACK+0x8000).items():
                w.vm.reg_write(globals()["UC_X86_REG_"+reg], value)
            w.vm.emu_start(site, site+7, count=5000)
            self.assertEqual((w.reg("ESI"), w.reg("EAX"), w.reg("EDI"), w.reg("EBP"), w.reg("ESP")),
                             (percent, 1, 3, SHIP, STACK+0x8000), (owned, year))

    def test_sea_skimming_and_manoeuvring_medium_and_light_missiles_are_harder_to_engage(self):
        skim, weave = tree.MISSILE_FLIGHT
        for owned, radar, handled, counted, code in (
                ({skim}, 5, 4, 5, 32), ({skim, weave}, 5, 0, 2, 32), ({skim, weave}, 6, 4, 3, 32), ({skim, weave}, 7, 2, 1, 33),
                ({weave}, 0, 0, 1, 32), (set(), 5, 4, 4, 32), ({skim, weave}, 5, 4, 4, 31), ({skim, weave}, 5, 4, 4, 30)):
            w = self.ship(radar, 0, handled); w.owned = owned; w.put(FRAME-4, 3); w.put(FRAME+8, code)   # nation, code
            self.run_site("handled")
            self.assertEqual((w.reg("ECX"), w.reg("EBP"), w.reg("EAX")), (counted, FRAME, 0x11), (owned, radar, handled))


if __name__ == "__main__": unittest.main(verbosity=2)
