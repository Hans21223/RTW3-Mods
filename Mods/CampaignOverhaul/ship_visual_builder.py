"""Package high-detail ship artwork as native-compatible EQS graphics.

Filled simple polygons are tessellated into triangles. Line paths are split
into overlapping native-sized runs. Two polygons are packed into each EQS
asset, and the generated design places each asset as a saved Equipment graphic.
"""
import argparse
import json
import math
from pathlib import Path
import re

MAX_POINTS = 100
MAX_EQUIPMENT = 100
NATIVE_POINTS = 25
ANGLE_UNITS_PER_DEGREE = 2_700_000
EPSILON = 1e-8


def _xy(points):
    result = []
    for point in points:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise ValueError("Each point must be an [x, y] pair.")
        x, y = point
        if type(x) not in (int, float) or type(y) not in (int, float):
            raise ValueError("Point coordinates must be numbers.")
        if not math.isfinite(x) or not math.isfinite(y) or abs(x) > 200_000 or abs(y) > 200_000:
            raise ValueError("Point coordinates must be finite and within +/-200,000.")
        result.append((float(x), float(y)))
    if not 2 <= len(result) <= MAX_POINTS:
        raise ValueError(f"A logical graphic must contain 2-{MAX_POINTS} points.")
    return result


def _cross(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def _on_segment(a, b, p):
    return (min(a[0], b[0])-EPSILON <= p[0] <= max(a[0], b[0])+EPSILON and
            min(a[1], b[1])-EPSILON <= p[1] <= max(a[1], b[1])+EPSILON)


def _segments_intersect(a, b, c, d):
    ab_c, ab_d = _cross(a, b, c), _cross(a, b, d)
    cd_a, cd_b = _cross(c, d, a), _cross(c, d, b)
    if ((ab_c > EPSILON and ab_d < -EPSILON or ab_c < -EPSILON and ab_d > EPSILON) and
            (cd_a > EPSILON and cd_b < -EPSILON or cd_a < -EPSILON and cd_b > EPSILON)):
        return True
    return (abs(ab_c) <= EPSILON and _on_segment(a, b, c) or
            abs(ab_d) <= EPSILON and _on_segment(a, b, d) or
            abs(cd_a) <= EPSILON and _on_segment(c, d, a) or
            abs(cd_b) <= EPSILON and _on_segment(c, d, b))


def _clean_polygon(points):
    polygon = list(points)
    if len(polygon) > 1 and math.dist(polygon[0], polygon[-1]) <= EPSILON:
        polygon.pop()
    compact = []
    for point in polygon:
        if not compact or math.dist(point, compact[-1]) > EPSILON:
            compact.append(point)
    if len(compact) > 1 and math.dist(compact[0], compact[-1]) <= EPSILON:
        compact.pop()
    changed = True
    while changed and len(compact) > 3:
        changed = False
        for i in range(len(compact)):
            a, b, c = compact[i-1], compact[i], compact[(i+1) % len(compact)]
            if abs(_cross(a, b, c)) <= EPSILON and _on_segment(a, c, b):
                compact.pop(i)
                changed = True
                break
    if len(compact) < 3:
        raise ValueError("A filled layer needs at least three distinct, non-collinear points.")
    return compact


def triangulate(points):
    """Ear-clip a simple polygon into non-overlapping triangles."""
    polygon = _clean_polygon(_xy(points))
    count = len(polygon)
    for i in range(count):
        a, b = polygon[i], polygon[(i+1) % count]
        for j in range(i+1, count):
            if j in (i, (i+1) % count) or (j+1) % count in (i, (i+1) % count):
                continue
            if _segments_intersect(a, b, polygon[j], polygon[(j+1) % count]):
                raise ValueError("Filled layers must be simple polygons without self-intersections.")
    area2 = sum(polygon[i][0]*polygon[(i+1) % count][1] -
                polygon[(i+1) % count][0]*polygon[i][1] for i in range(count))
    if abs(area2) <= EPSILON:
        raise ValueError("A filled layer must have non-zero area.")
    orientation = 1 if area2 > 0 else -1
    remaining = list(range(count))
    triangles = []
    while len(remaining) > 3:
        clipped = False
        for at, current in enumerate(remaining):
            previous, following = remaining[at-1], remaining[(at+1) % len(remaining)]
            a, b, c = polygon[previous], polygon[current], polygon[following]
            if orientation*_cross(a, b, c) <= EPSILON:
                continue
            contains = False
            for candidate in remaining:
                if candidate in (previous, current, following):
                    continue
                p = polygon[candidate]
                signs = (orientation*_cross(a, b, p), orientation*_cross(b, c, p),
                         orientation*_cross(c, a, p))
                if min(signs) > EPSILON:
                    contains = True
                    break
            if contains:
                continue
            triangles.append((a, b, c))
            remaining.pop(at)
            clipped = True
            break
        if not clipped:
            raise ValueError("Could not safely tessellate this filled layer; simplify its outline and retry.")
    triangles.append(tuple(polygon[i] for i in remaining))
    return triangles


def line_runs(points, closed=False):
    points = _xy(points)
    if closed and math.dist(points[0], points[-1]) > EPSILON:
        points.append(points[0])
    if len(points) < 2:
        raise ValueError("A line graphic needs at least two distinct points.")
    runs, start = [], 0
    while start < len(points)-1:
        run = points[start:start+NATIVE_POINTS]
        if len(run) < 2:
            break
        runs.append(tuple(run))
        start += len(run)-1
    return runs


def _color(value):
    if not isinstance(value, str):
        raise ValueError("Layer color must be an 8-digit game color such as $00C8C8C8.")
    raw = value[1:] if value.startswith("$") else value
    if not re.fullmatch(r"[0-9a-fA-F]{8}", raw):
        raise ValueError("Layer color must contain exactly eight hexadecimal digits.")
    return "$" + raw.upper()


def _polar(point):
    x, y = point
    angle = round(math.degrees(math.atan2(x, y))*ANGLE_UNITS_PER_DEGREE)
    distance = round(math.hypot(x, y))
    return angle, distance


def _polygon_section(number, points, color, is_line):
    values = [_polar(point) for point in points]
    if len(values) > NATIVE_POINTS:
        raise ValueError("Generated native polygon exceeds 25 points.")
    values += [(0, 0)] * (NATIVE_POINTS-len(values))
    lines = [f"[Polygon{number}]"]
    for i, (angle, distance) in enumerate(values):
        lines.extend((f"Point{i}Angle={angle}", f"Point{i}Distance={distance}"))
    lines.extend((f"IsLine={1 if is_line else 0}", f"Color={color}"))
    return "\r\n".join(lines)


def _equipment_file(shapes):
    (first, first_line, color1), (second, second_line, color2) = shapes
    return (_polygon_section(4, first, color1, first_line) + "\r\n" +
            _polygon_section(5, second, color2, second_line) + "\r\n")


def _safe_slug(text):
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if not slug:
        raise ValueError("The output name must contain letters or numbers.")
    return slug[:48].rstrip("-")


def _decode_design(path):
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig"), "utf-8-sig"
    try:
        return raw.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        return raw.decode("cp1252"), "cp1252"


def build_package(spec, design_path, output_dir):
    """Create a separate native design + graphics mod; never edits the source."""
    design_path, output_dir = Path(design_path), Path(output_dir)
    if not design_path.is_file() or design_path.suffix.lower() != ".sdf":
        raise ValueError("Choose an existing .sdf ship design.")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("Choose a new or empty output folder so existing files stay untouched.")
    if not isinstance(spec, dict) or not isinstance(spec.get("layers"), list) or not spec["layers"]:
        raise ValueError("The graphic spec needs a non-empty layers list.")
    output_name = spec.get("design_name", design_path.stem + " Extended")
    if not isinstance(output_name, str) or not output_name.strip() or len(output_name) > 48 or any(c in output_name for c in "[]\r\n"):
        raise ValueError("design_name must be 1-48 characters and cannot contain brackets or new lines.")
    slug = _safe_slug(output_name)
    design_text, encoding = _decode_design(design_path)
    equipment_ids = [int(value) for value in re.findall(r"^\[Equipment(\d+)\]\s*$", design_text, re.M)]
    if len(equipment_ids) != len(set(equipment_ids)):
        raise ValueError("The source design repeats an Equipment section.")
    equipment_count = len(set(equipment_ids))
    if sorted(set(equipment_ids)) != list(range(equipment_count)):
        raise ValueError("The source design's Equipment sections are not consecutive from Equipment0.")
    additions = []
    for layer_number, layer in enumerate(spec["layers"], 1):
        if not isinstance(layer, dict):
            raise ValueError("Each layer must be an object.")
        mode = layer.get("mode", "fill")
        points = _xy(layer.get("points", []))
        color = _color(layer.get("color", "$00C8C8C8"))
        if mode == "fill":
            shapes = [(triangle, False, color) for triangle in triangulate(points)]
        elif mode == "line":
            shapes = [(run, True, color) for run in line_runs(points, bool(layer.get("closed", False)))]
        else:
            raise ValueError("Layer mode must be 'fill' or 'line'.")
        for first in range(0, len(shapes), 2):
            pair = shapes[first:first+2]
            if len(pair) == 1:
                pair.append(((), pair[0][1], pair[0][2]))
            additions.append((layer_number, len(additions)+1, _equipment_file(pair)))
    if equipment_count + len(additions) > MAX_EQUIPMENT:
        raise ValueError(f"This design needs {equipment_count + len(additions)} graphics; the enabled limit is {MAX_EQUIPMENT}.")
    equipment_sections = []
    assets = []
    for number, (layer_number, _, content) in enumerate(additions, equipment_count):
        filename = f"{slug}-layer{layer_number:02d}-graphic{number-equipment_count+1:03d}.eqs"
        assets.append((filename, content))
        equipment_sections.append("\r\n".join((f"[Equipment{number}]", "Tubes=0", "Pos= ", "MT=10",
            "Reloads=0", "LocationAngle=0", "LocationDistance=0", "Nominal=0",
            f"EquipmentFile={filename}", "Sponsoned=0", "")))
    hull_header = re.search(r"^\[HullPoints\]\s*$", design_text, re.M)
    if hull_header is None:
        raise ValueError("The source design has no [HullPoints] section.")
    data_header = re.search(r"^\[Data\]\s*$", design_text, re.M)
    if data_header is None:
        raise ValueError("The source design has no [Data] section.")
    data_end = re.search(r"^\[[^\]]+\]\s*$", design_text[data_header.end():], re.M)
    data_stop = data_header.end() + data_end.start() if data_end else len(design_text)
    data_block = design_text[data_header.start():data_stop]
    name_match = re.search(r"^Name=.*$", data_block, re.M)
    if name_match is None:
        raise ValueError("The source design's [Data] section has no Name field.")
    data_block = data_block[:name_match.start()] + "Name=" + output_name + data_block[name_match.end():]
    design_text = design_text[:data_header.start()] + data_block + design_text[data_stop:]
    hull_header = re.search(r"^\[HullPoints\]\s*$", design_text, re.M)
    newline = "\r\n" if "\r\n" in design_text else "\n"
    insertion = "".join(section.replace("\r\n", newline) + newline for section in equipment_sections)
    design_text = design_text[:hull_header.start()] + insertion + design_text[hull_header.start():]

    output_dir.mkdir(parents=True, exist_ok=True)
    graphics_dir = output_dir / "Data" / "Graphics"
    designs_dir = output_dir / "Designs"
    graphics_dir.mkdir(parents=True)
    designs_dir.mkdir(parents=True)
    design_out = designs_dir / f"{slug}.sdf"
    design_out.write_bytes(design_text.encode(encoding))
    manifest_files = [{"source": f"Designs/{design_out.name}", "target": f"Designs/{design_out.name}"}]
    for filename, content in assets:
        (graphics_dir / filename).write_text(content, encoding="ascii", newline="")
        manifest_files.append({"source": f"Data/Graphics/{filename}", "target": f"Data/Graphics/{filename}"})
    manifest = {"schema": 1, "id": "ship-graphics-" + slug[:48].rstrip("-"),
        "name": output_name + " extended ship graphics", "version": "1.0.0",
        "author": "RTW3 Ship Graphic Builder",
        "description": f"Adds {len(additions)} native-compatible ship graphics to {output_name}. Requires the 100-visual submod.",
        "kind": "data", "experimental": True,
        "requires": ["large-hulls", "extended-ship-graphics"], "conflicts": [],
        "files": manifest_files}
    (output_dir / "mod.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {"design": str(design_out), "graphics": len(assets), "visuals_used": equipment_count + len(additions),
            "visual_limit": MAX_EQUIPMENT, "native_points_per_piece": NATIVE_POINTS,
            "manifest": str(output_dir / "mod.json")}


def main():
    parser = argparse.ArgumentParser(description="Build extended superstructure layers from native-compatible ship graphics.")
    parser.add_argument("spec", type=Path, help="JSON file with design_name and layer point lists")
    parser.add_argument("design", type=Path, help="Source ship .sdf; the source is never changed")
    parser.add_argument("output", type=Path, help="New or empty output folder for the importable mod")
    args = parser.parse_args()
    result = build_package(json.loads(args.spec.read_text(encoding="utf-8-sig")), args.design, args.output)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
