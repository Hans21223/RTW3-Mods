"""Historical decolonization's guards, run against stand-in game routines: the rebellion entry refuses protected
possessions, and ChangePossessionOwner refuses the game's own transfers of a home region to Neutral."""
from pathlib import Path
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE/"vendor"), str(HERE.parent/"CampaignOverhaul")]
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EDX, UC_X86_REG_ESP, UC_X86_REG_EIP
import decolonization as feature

GUARD, STUBS, STACK = 0x10000000, 0x200000, 0x400000
PROCESSOR = GUARD+0x4000                       # the dated release processor's code range
NATIVE, BLOCKED, CAMPAIGN, NATION = STUBS+0x100, 0x500000, 0x777, 0x4444
GET_POSSESSION = STUBS
NAMES = sorted(feature.PROTECTED_POSSESSIONS) + ["Hawaii"]
POSSESSION = {name: 0x6000+0x10*i for i, name in enumerate(NAMES)}       # name -> possession object
LITERAL = {("guard", name): 0x8000+0x10*i for i, name in enumerate(NAMES)}


class DecolonizationGuardTests(unittest.TestCase):
    def call(self, target, *, owner=0, caller=BLOCKED, owner_guard=True):
        """Calls the guard as the game would; True when it went on to the native routine."""
        code = feature.protected_possession_guard(
            GUARD, NATIVE, dict(get_possession=GET_POSSESSION), LITERAL, owner_guard=owner_guard,
            processor_start=PROCESSOR, processor_end=PROCESSOR+0x100)
        self.assertLess(len(code), PROCESSOR-GUARD)
        vm = Uc(UC_ARCH_X86, UC_MODE_32)
        for base in (GUARD, STUBS, STACK, BLOCKED):
            vm.mem_map(base, 0x10000)
        vm.mem_write(GUARD, code)
        by_literal = {LITERAL[("guard", name)]: POSSESSION[name] for name in NAMES}

        def stand_in(uc, address, size, data):
            if address != GET_POSSESSION:
                return
            self.assertEqual(uc.reg_read(UC_X86_REG_EAX), CAMPAIGN)
            uc.reg_write(UC_X86_REG_EAX, by_literal.get(uc.reg_read(UC_X86_REG_EDX), 0))
            sp = uc.reg_read(UC_X86_REG_ESP)
            uc.reg_write(UC_X86_REG_ESP, sp+4)
            uc.reg_write(UC_X86_REG_EIP, struct.unpack("<I", uc.mem_read(sp, 4))[0])

        def stop(uc, address, size, data):   # the native routine or back at the caller: the guard is done
            if address in (NATIVE, caller):
                uc.emu_stop()
        vm.hook_add(UC_HOOK_CODE, stand_in, begin=STUBS, end=STUBS+0x10)
        vm.hook_add(UC_HOOK_CODE, stop)
        sp = STACK+0xF000
        vm.mem_write(sp, struct.pack("<II", caller, 0))     # return address, the routine's stack argument
        for reg, value in ((UC_X86_REG_EAX, CAMPAIGN), (UC_X86_REG_EDX, POSSESSION[target]),
                           (UC_X86_REG_ECX, owner), (UC_X86_REG_ESP, sp)):
            vm.reg_write(reg, value)
        vm.emu_start(GUARD, 0, count=200000)
        reached = vm.reg_read(UC_X86_REG_EIP)
        if reached == NATIVE:   # passed through with everything as the caller left it
            self.assertEqual([vm.reg_read(r) for r in (UC_X86_REG_EAX, UC_X86_REG_EDX, UC_X86_REG_ECX, UC_X86_REG_ESP)],
                             [CAMPAIGN, POSSESSION[target], owner, sp])
            return True
        self.assertEqual(reached, caller)
        self.assertEqual(vm.reg_read(UC_X86_REG_ESP), sp+(8 if owner_guard else 4))   # RET 4 / RET
        return False

    def test_the_games_transfer_of_a_home_region_to_neutral_is_refused(self):
        self.assertFalse(self.call("Western USA"))

    def test_colonies_still_go_neutral_after_wars_and_for_concessions(self):
        self.assertTrue(self.call("Egypt"))
        self.assertTrue(self.call("Hawaii"))

    def test_a_home_region_may_change_hands_between_nations(self):
        self.assertTrue(self.call("Western USA", owner=NATION))

    def test_the_dated_release_processor_passes(self):
        self.assertTrue(self.call("Western USA", caller=PROCESSOR+0x40))

    def test_new_rebellions_are_refused_in_every_protected_possession(self):
        self.assertFalse(self.call("Egypt", owner_guard=False))
        self.assertFalse(self.call("Western USA", owner_guard=False))
        self.assertTrue(self.call("Hawaii", owner_guard=False))


DATA = 0x600000                                # the year global (pointing at DATA+0x10), the campaign, possessions
CAMPAIGN_OBJECT, GET_NATION, CHANGE_OWNER = DATA+0x1000, STUBS+0x10, STUBS+0x20


class ReleaseProcessorTests(unittest.TestCase):
    """Each dated release happens once: in its year, or in the first year of a campaign that starts later."""
    def released(self, year, start, held):
        """Runs the release processor with possessions held as {name: owner}; the names it hands to Neutral."""
        literals, text = {}, {}
        for _, possession, owners in feature.RELEASES:
            for key in [(possession, None), *[(possession, owner) for owner in owners]]:
                literals[key] = 0x9000+0x10*len(literals)
                text[literals[key]] = key[1] or key[0]
        nations = {name: 0x7000+0x10*i for i, name in enumerate(sorted(set(held.values())))}
        possessions = {name: DATA+0x8000+0x100*i for i, name in enumerate(held)}
        info = dict(year_pointer=DATA, get_possession=GET_POSSESSION, get_nation=GET_NATION, change_owner=CHANGE_OWNER)
        code = feature.release_processor(GUARD, 0, literals, info)
        self.assertLess(len(code), 0x2000)                          # the processor's reserved code area
        vm = Uc(UC_ARCH_X86, UC_MODE_32)
        for base in (GUARD, STUBS, STACK, BLOCKED, DATA):
            vm.mem_map(base, 0x10000)
        vm.mem_write(GUARD, code)
        vm.mem_write(DATA, struct.pack("<I", DATA+0x10))
        vm.mem_write(DATA+0x10, struct.pack("<I", year))
        vm.mem_write(CAMPAIGN_OBJECT+feature.START_YEAR, struct.pack("<I", start))
        for name, owner in held.items():
            vm.mem_write(possessions[name]+0x61, struct.pack("<I", nations[owner]))
        released = []

        def stand_in(uc, address, size, data):   # GetPossessionWithName, GetBNationWithName, ChangePossessionOwner
            eax, ecx, edx, sp = (uc.reg_read(r) for r in (UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EDX, UC_X86_REG_ESP))
            self.assertEqual(eax, CAMPAIGN_OBJECT)
            if address == GET_POSSESSION:
                eax = possessions.get(text[edx], 0)
            elif address == GET_NATION:
                eax = nations.get(text[edx], 0)
            else:
                self.assertEqual(ecx, 0)                             # to Neutral
                released.append(next(name for name, p in possessions.items() if p == edx))
            uc.reg_write(UC_X86_REG_EAX, eax)
            uc.reg_write(UC_X86_REG_ESP, sp+(8 if address == CHANGE_OWNER else 4))   # RET 4 / RET
            uc.reg_write(UC_X86_REG_EIP, struct.unpack("<I", uc.mem_read(sp, 4))[0])

        def stop(uc, address, size, data):
            if address == BLOCKED:
                uc.emu_stop()
        vm.hook_add(UC_HOOK_CODE, stand_in, begin=STUBS, end=CHANGE_OWNER)
        vm.hook_add(UC_HOOK_CODE, stop)
        sp = STACK+0xF000
        vm.mem_write(sp, struct.pack("<I", BLOCKED))
        vm.reg_write(UC_X86_REG_EAX, CAMPAIGN_OBJECT)
        vm.reg_write(UC_X86_REG_ESP, sp)
        vm.emu_start(GUARD, 0, count=500000)
        self.assertEqual((vm.reg_read(UC_X86_REG_EIP), vm.reg_read(UC_X86_REG_ESP)), (BLOCKED, sp+4))
        return sorted(released)

    def test_released_in_its_year(self):
        self.assertEqual(self.released(1922, 1890, {"Ireland": "Great Britain"}), ["Ireland"])

    def test_a_territory_taken_back_later_stays_taken(self):   # a tester's Ireland went Neutral after every takeover
        self.assertEqual(self.released(1923, 1890, {"Ireland": "Great Britain"}), [])
        self.assertEqual(self.released(1950, 1920, {"Ireland": "Great Britain"}), [])

    def test_a_later_start_releases_in_its_first_year_only(self):
        held = {"Nova Scotia": "Great Britain", "Western Australia": "European NATO", "India": "European NATO"}
        self.assertEqual(self.released(1935, 1935, {"Nova Scotia": "Great Britain"}), ["Nova Scotia"])
        self.assertEqual(self.released(1947, 1947, held), ["India", "Nova Scotia", "Western Australia"])
        self.assertEqual(self.released(1948, 1947, held), [])

    def test_not_before_its_year_nor_from_another_power(self):
        self.assertEqual(self.released(1921, 1890, {"Ireland": "Great Britain"}), [])
        self.assertEqual(self.released(1922, 1890, {"Ireland": "Germany"}), [])


if __name__ == "__main__":
    unittest.main()
