"""campaign-qol's MapData.dat: the vanilla map plus complete neutral possessions on South America's Pacific coast."""
from pathlib import Path
import re
import unittest

HERE = Path(__file__).resolve().parent
PACKAGED = HERE.parent/"Library"/"campaign-qol"/"Files"/"Data"/"MapData.dat"
BASELINE = HERE/"baseline"/"Data"/"MapData.dat"   # the loader's copy of the vanilla file, once installed
ZERO = "00000E 00000N"


def lines(path):
    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf") and b"\n" not in raw.replace(b"\r\n", b"")
    return raw[3:].decode("utf-8").split("\r\n")


def degrees(point):
    """'713730W 330200S' -> (-71.625, -33.0333): DDDMMSS longitude, DDMMSS latitude."""
    lon, lat = point.split()
    value = lambda text: int(text[:-5])+int(text[-5:-3])/60+int(text[-3:-1])/3600
    return (-1 if lon[-1] == "W" else 1)*value(lon), (-1 if lat[-1] == "S" else 1)*value(lat)


class PossessionDataTests(unittest.TestCase):
    def setUp(self):
        self.lines = lines(PACKAGED)
        self.values = dict(line.split("=", 1) for line in self.lines if "=" in line)

    def test_new_possessions_are_complete_and_inside_their_area(self):
        v = self.values
        self.assertEqual(v["MapArea10PossessionCount"], "2")
        template = [l.split("=")[0][len("MapArea9Possession1"):] for l in self.lines if l.startswith("MapArea9Possession1")]
        (west, north), (east, south) = degrees(v["MapArea10UL"]), degrees(v["MapArea10LR"])
        names = [v2 for k, v2 in v.items() if re.fullmatch(r"MapArea\d+Possession\d+Name", k)]
        for index, name in enumerate(("Chile", "Peru")):
            prefix = f"MapArea10Possession{index}"
            keys = [l.split("=")[0][len(prefix):] for l in self.lines if l.startswith(prefix)]
            self.assertEqual(keys, template, name)
            self.assertEqual((v[prefix+"Name"], v[prefix+"Owner"], names.count(name)), (name, "Neutral", 1))
            points = [v[prefix+k] for k in template if re.fullmatch(
                r"Location|BaseLocs\d|BaseENP\d|CAPositions\d|WM0(CenterPoint|StartPoints\d)", k) and v[prefix+k] != ZERO]
            self.assertGreater(len(points), 6)
            for point in points:
                lon, lat = degrees(point)
                self.assertTrue(west <= lon <= east and south <= lat <= north, (name, point))
            bases = [v[prefix+f"BaseNames{b}"] for b in range(6) if v[prefix+f"BaseSizes{b}"] != "0"]
            self.assertTrue(bases and all(v[prefix+f"BaseENP{b}"] != ZERO for b in range(len(bases))), name)
            self.assertEqual((v[prefix+"WM0Title"], v[prefix+"WM1Title"]), ("X", ""))

    def test_only_the_west_coast_possessions_and_new_ports_change(self):
        if not BASELINE.is_file(): self.skipTest("the vanilla MapData.dat is not baselined yet")
        import sys
        sys.path.insert(0, str(HERE.parent/"CampaignOverhaul"))
        import map_ports
        west = [l for l in self.lines if re.match(r"MapArea10Possession\d", l)]       # Chile and Peru, as packaged
        vanilla = [l.replace("MapArea10PossessionCount=0", "MapArea10PossessionCount=2") for l in lines(BASELINE)]
        at = vanilla.index("MapArea10PossessionCount=2")+1
        self.assertEqual(self.lines, map_ports.add("\r\n".join(vanilla[:at]+west+vanilla[at:])).split("\r\n"))
        ports = [port for group in map_ports.PORTS.values() for port, *_ in group]
        self.assertEqual(sum(self.lines.count(f"{k}={v}") for k, v in self.values.items() if "BaseNames" in k and v in ports), len(ports))


    def test_the_black_sea_is_a_seventeenth_area_next_to_the_mediterranean(self):
        v, area = self.values, "MapArea16"
        self.assertEqual((v["MapAreaCount"], v[area+"Name"], v[area+"AdjacentAreaNames0"]), ("17", "Black Sea", "The Mediterranean"))
        self.assertIn("Black Sea", [v[f"MapArea1AdjacentAreaNames{s}"] for s in range(5)])
        self.assertEqual((v["MapArea1UL"], v["MapArea1LR"]), ("75608W 421921N", "335803E 283820N"))   # the native box again
        (west, north), (east, south) = degrees(v[area+"UL"]), degrees(v[area+"LR"])
        owners = {"Southern Russia": "Russia", "Romania": "Neutral", "Bulgaria": "Neutral", "Northern Anatolia": "Neutral",
                  "Odessa": "Russia", "Kuban": "Russia", "Georgia": "Russia", "Donbass": "Russia", "Rostov": "Russia"}
        self.assertEqual([v[f"{area}Possession{p}Name"] for p in range(int(v[area+"PossessionCount"]))], list(owners))
        for p, (name, owner) in enumerate(owners.items()):
            key = f"{area}Possession{p}"
            self.assertEqual(v[key+"Owner"], owner)
            points = [v[key+f] for f in ("Location", "BaseLocs0", "BaseENP0", "WM0CenterPoint", "WM0StartPoints0", "WM0StartPoints1")]
            for lon, lat in map(degrees, points):
                self.assertTrue(west <= lon <= east and south <= lat <= north, (name, lon, lat))
        self.assertEqual(v[area+"Possession3BaseNames0"], "Sinop")
        year = (PACKAGED.parent/"MapData1920.dat").read_text(encoding="utf-8-sig")
        self.assertIn("Owner=Soviet Union\nMapArea16Possession0Name=Southern Russia", year)
        self.assertIn("Owner=Soviet Union\nMapArea16Possession8Name=Rostov", year)

    def test_new_regions_have_their_ports_and_no_port_is_on_the_map_twice(self):
        import sys
        sys.path.insert(0, str(HERE.parent/"CampaignOverhaul"))
        import map_ports
        v = self.values
        key = {n: k[:-4] for k, n in v.items() if re.fullmatch(r"MapArea\d+Possession\d+Name", k)}
        for area, name, owner, _, _, _, _, _, _, ports in map_ports.REGIONS:
            self.assertEqual((v[key[name].split("Possession")[0]+"Name"], v[key[name]+"Owner"]), (area, owner), name)
            self.assertEqual([v[f"{key[name]}BaseNames{s}"] for s in range(len(ports))], [p[0] for p in ports], name)
        for possession, gone in map_ports.MOVED.items():          # moved out, and the slots close up
            names = [v[f"{key[possession]}BaseNames{s}"] for s in range(6)]
            self.assertFalse(set(gone) & set(names), possession)
            self.assertEqual(names, sorted(names, key=lambda n: n == "Error"), possession)
        ports = [p for k, p in v.items() if re.fullmatch(r"MapArea\d+Possession\d+BaseNames\d", k) and p != "Error"]
        self.assertEqual(sorted({p for p in ports if ports.count(p) > 1}), [])


if __name__ == "__main__":
    unittest.main()
