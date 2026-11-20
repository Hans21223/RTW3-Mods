"""Native-format shape splitting and safe output-package checks."""
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "CampaignOverhaul"))
import ship_visual_builder as builder


class ShipVisualBuilderTests(unittest.TestCase):
    def design(self, folder, equipment=1):
        path = Path(folder) / "Source.sdf"
        sections = ["[Data]", "Name=Source", "ShipType=DD"]
        for index in range(equipment):
            sections += [f"[Equipment{index}]", "Tubes=0", "EquipmentFile=Native.eqs"]
        sections += ["[HullPoints]", "HullPoint0Angle=0", "HullPoint0Distance=4000", ""]
        path.write_bytes("\r\n".join(sections).encode("cp1252"))
        return path

    @staticmethod
    def polygon_points(count=100):
        return [[round(1000*math.cos(2*math.pi*i/count), 4),
                 round(1600*math.sin(2*math.pi*i/count), 4)] for i in range(count)]

    def test_100_point_fill_becomes_native_triangles_and_a_separate_importable_design(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            design = self.design(root)
            before = design.read_bytes()
            spec = {"design_name": "Source Extended", "layers": [
                {"mode": "fill", "color": "$00C8C8C8", "points": self.polygon_points()}]}
            result = builder.build_package(spec, design, root / "output")
            self.assertEqual(result["graphics"], 49)  # 98 triangles, two per EQS graphic
            self.assertEqual(result["visuals_used"], 50)  # one existing + 49 generated
            self.assertEqual(design.read_bytes(), before)
            output = Path(result["design"]).read_bytes().decode("cp1252")
            self.assertIn("Name=Source Extended", output)
            self.assertIn("[Equipment49]", output)
            self.assertIn("EquipmentFile=source-extended-layer01-graphic049.eqs", output)
            generated = sorted((root / "output" / "Data" / "Graphics").glob("*.eqs"))
            self.assertEqual(len(generated), 49)
            for path in generated:
                text = path.read_text(encoding="ascii")
                self.assertEqual(text.count("[Polygon"), 2)
                for section in text.split("[Polygon")[1:]:
                    # Every triangle has three nonzero distances; unused slots are zero.
                    distances = [int(line.split("=", 1)[1]) for line in section.splitlines()
                                 if line.startswith("Point") and "Distance=" in line]
                    self.assertEqual(len(distances), 25)
                    self.assertEqual(sum(value != 0 for value in distances), 3)
            manifest = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
            self.assertEqual(manifest["requires"], ["large-hulls", "extended-ship-graphics"])
            self.assertEqual(len(manifest["files"]), 50)

    def test_100_point_line_is_split_with_shared_endpoints(self):
        points = [[i*10, i*i] for i in range(100)]
        runs = builder.line_runs(points)
        self.assertEqual(len(runs), 5)
        self.assertTrue(all(2 <= len(run) <= 25 for run in runs))
        self.assertEqual([runs[i][-1] for i in range(4)], [runs[i+1][0] for i in range(4)])
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            design = self.design(root, equipment=0)
            result = builder.build_package({"layers": [{"mode": "line", "points": points}]},
                                           design, root / "output")
            self.assertEqual(result["graphics"], 3)
            self.assertEqual(result["visuals_used"], 3)

    def test_self_intersection_and_visual_overflow_are_refused(self):
        bow_tie = [[0, 0], [10, 10], [0, 10], [10, 0]]
        with self.assertRaisesRegex(ValueError, "self-intersections"):
            builder.triangulate(bow_tie)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            design = self.design(root, equipment=100)
            triangle = {"layers": [{"mode": "fill", "points": [[0, 0], [10, 0], [0, 10]]}]}
            with self.assertRaisesRegex(ValueError, "needs 101 graphics"):
                builder.build_package(triangle, design, root / "output")

    def test_nonempty_output_folder_and_bad_coordinates_are_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            design = self.design(root)
            output = root / "output"
            output.mkdir()
            (output / "keep.txt").write_text("preserve")
            spec = {"layers": [{"mode": "line", "points": [[0, 0], [1, 1]]}]}
            with self.assertRaisesRegex(ValueError, "new or empty"):
                builder.build_package(spec, design, output)
            with self.assertRaisesRegex(ValueError, "finite"):
                builder.line_runs([[float("nan"), 0], [1, 1]])


if __name__ == "__main__":
    unittest.main()
