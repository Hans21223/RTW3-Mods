"""The research dates against real ships: what a ship carried must be researchable by the year it was laid down, and
not long before. Only research that unlocks a design choice is listed (propulsion, launchers, radar classes, hull
and deck features); quality and range research applies whenever it is done."""
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent/"CampaignOverhaul")]
import modern_tree as tree

NUCLEAR, AEGIS = tree.NUCLEAR_PROPULSION, tree.PHASED_ARRAY
VLS8, VLS16, VLS32, VLS64 = (tree.VLS_CELLS[n] for n in (8, 16, 32, 64))
PERIPHERAL_VLS, SHAPING, LOW_OBSERVABLE = 2209, tree.STEALTH[0][0], tree.STEALTH[1][0]
AESA, POWER, EMALS, SKI_JUMP, COMPOSITE = tree.AESA[0], tree.INTEGRATED_POWER[0], tree.EMALS[0], tree.SKI_JUMP[0], tree.COMPOSITE[0]
ANGLED_DECK, STEAM_CATAPULTS, HEAVY_SAM, MEDIUM_SAM, CIWS, CRUISE_MISSILES = 1808, 1823, 1908, 1905, 2106, 1917
# ship, year laid down, research its design needs
SHIPS = (
    ("USS Nautilus (SSN)", 1952, (tree.SSN,)),
    ("USS George Washington (SSBN)", 1957, (tree.SSBN,)),
    ("USS Long Beach", 1957, (NUCLEAR, HEAVY_SAM, MEDIUM_SAM)),
    ("USS Enterprise", 1958, (NUCLEAR, ANGLED_DECK, STEAM_CATAPULTS)),
    ("USS Nimitz", 1968, (NUCLEAR, ANGLED_DECK, STEAM_CATAPULTS)),
    ("Kirov", 1974, (NUCLEAR, VLS8, HEAVY_SAM, CRUISE_MISSILES)),
    ("Slava", 1976, (VLS8, HEAVY_SAM, CRUISE_MISSILES)),
    ("HMS Invincible", 1973, (SKI_JUMP,)),
    ("USS Ticonderoga", 1980, (AEGIS, HEAVY_SAM, CIWS)),
    ("Admiral Kuznetsov", 1982, (SKI_JUMP, VLS8, CRUISE_MISSILES)),
    ("USS Bunker Hill", 1984, (AEGIS, VLS64)),
    ("USS Arleigh Burke", 1988, (AEGIS, VLS64, SHAPING, CIWS)),
    ("La Fayette", 1990, (SHAPING,)),
    ("Kongo", 1990, (AEGIS, VLS64)),
    ("Visby", 1995, (COMPOSITE, SHAPING)),
    ("De Zeven Provincien", 1998, (AESA, VLS32)),
    ("HMS Daring", 2003, (AESA, VLS32, POWER, SHAPING)),
    ("Sejong the Great", 2004, (AEGIS, VLS64)),
    ("Admiral Gorshkov", 2006, (AESA, VLS32, SHAPING)),
    ("USS Gerald R. Ford", 2009, (NUCLEAR, EMALS, ANGLED_DECK)),
    ("HMS Queen Elizabeth", 2009, (SKI_JUMP,)),
    ("Akizuki", 2009, (AESA, VLS32)),
    ("USS Zumwalt", 2011, (LOW_OBSERVABLE, POWER, COMPOSITE, PERIPHERAL_VLS, VLS64)),
    ("Nanchang (Type 055)", 2014, (AESA, VLS64, SHAPING)),
)
# Nuclear propulsion follows the game's own last machinery row (1960): the first nuclear surface ships come when
# they were completed (1961), not when they were laid down.
# HMS Invincible (laid down 1973) got her ski-jump while building; the research is 1974 (any hull may fit one).
LATE = {("USS Long Beach", NUCLEAR), ("USS Enterprise", NUCLEAR), ("HMS Invincible", SKI_JUMP)}
EARLY_YEARS = 8                      # research may lead its first ship by this much (Aegis at sea 1973, CG-47 laid down 1980)
# A laid-down or design year the code asks for besides the research
GATES = {AESA: tree.AESA[1], EMALS: tree.EMALS[1], COMPOSITE: tree.COMPOSITE[1],
         SHAPING: tree.STEALTH[0][1], LOW_OBSERVABLE: tree.STEALTH[1][1]}


class RealShipTests(unittest.TestCase):
    def setUp(self):
        raw, nodes = tree.render()
        self.year = {n["id"]: n["year"] for n in nodes}
        for area in tree.parse(raw):
            for row in area["rows"]: self.year.setdefault(row["id"], row["year"])
        self.nodes = nodes

    def test_every_ship_s_design_research_is_dated_by_its_keel_laying(self):
        for ship, laid, needs in SHIPS:
            for ident in needs:
                if (ship, ident) in LATE: continue
                self.assertLessEqual(self.year[ident], laid, (ship, ident))
                self.assertLessEqual(GATES.get(ident, 0), laid, (ship, ident, "year gate"))

    def test_research_does_not_lead_its_first_ship_by_long(self):
        first = {}
        for ship, laid, needs in SHIPS:
            for ident in needs:
                if (ident > 2200 or ident in (NUCLEAR, AEGIS)) and ident not in (VLS16, VLS32):   # sizes between first and full
                    first[ident] = min(first.get(ident, 9999), laid)
        for ident, laid in first.items():
            self.assertLessEqual(laid-self.year[ident], EARLY_YEARS, (ident, self.year[ident], laid))

    def test_prerequisites_are_dated_before_what_needs_them_and_branches_run_in_year_order(self):
        for node in self.nodes:
            before = node["prerequisite"]
            if before in self.year and node["id"] != NUCLEAR: self.assertLessEqual(self.year[before], node["year"], node["name"])
        for area in (22, 23):
            years = [n["year"] for n in self.nodes if n["area"] == area]
            self.assertEqual(years, sorted(years))


if __name__ == "__main__": unittest.main(verbosity=2)
