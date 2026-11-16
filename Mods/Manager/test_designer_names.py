"""Designer captions follow the research that replaces a module, executed in the emulator."""
import unittest
from test_modern_sensors import World, CODE, DATA, NATION
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_EDX
import designer_names as names
import modern_tree as tree

FORM, DESIGN = DATA+0xC000, DATA+0x1000
CONTROLS = dict(cbAluminium=DATA+0xD000, cbHangar=DATA+0xD400, GroupBox8=DATA+0xD800)


class NameTests(unittest.TestCase):
    def captions(self, owned, design_year, build_year):
        world = World(owned); shown = {}
        sync = CODE+len(world_details(world))*0x1000+0xD400
        world.vm.mem_write(DESIGN, bytes(0xC00))
        world.put(FORM+names.FORM["nation"], NATION); world.put(FORM+names.FORM["design"], DESIGN)
        world.put(DESIGN+names.DESIGN_YEAR, design_year); world.put(DESIGN+names.BUILD_YEAR, build_year)
        for name, address in CONTROLS.items(): world.put(FORM+names.FORM[name], address)
        where = {address: name for name, address in CONTROLS.items()}
        where.update({address+names.HINT: name+" hint" for name, address in CONTROLS.items()})
        record = lambda: shown.update({where[world.vm.reg_read(UC_X86_REG_EAX)]: world.text_at(world.vm.reg_read(UC_X86_REG_EDX))}) or 0
        world.stubs.update({0x451CA0: record, 0x30BCCC: record})
        world.call(sync, FORM)
        return shown

    def test_names_change_only_with_the_research_on_new_enough_designs(self):
        every = {tree.COMPOSITE[0], tree.UAVS, tree.EMALS[0]}
        native = {"cbAluminium": "Aluminium superstructure", "cbAluminium hint": "Saves weight but increases fire hazard",
                  "cbHangar": "Seaplane/helicopter hangar", "GroupBox8": "Catapults"}
        self.assertEqual(self.captions(set(), 2020, 2020), native)
        self.assertEqual(self.captions(every, 2020, 2020),
                         {"cbAluminium": "Composite superstructure",
                          "cbAluminium hint": "Composite: saves more weight, costs more, no fire hazard",
                          "cbHangar": "UAV/helicopter hangar", "GroupBox8": "EMALS catapults"})
        self.assertEqual(self.captions(every, tree.COMPOSITE[1]-1, tree.EMALS[1]-1), {**native, "cbHangar": "UAV/helicopter hangar"})


def world_details(world):
    import modern_research as modern
    from test_modern_sensors import BLOB
    return modern.discover(BLOB, 0x301000)["getters"]


if __name__ == "__main__": unittest.main(verbosity=2)
