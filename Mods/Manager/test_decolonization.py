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


if __name__ == "__main__":
    unittest.main()
