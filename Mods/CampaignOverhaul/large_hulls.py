"""Historical/paper hull limits, DD fuel capacity and guarded designer visuals."""
import argparse
import json
from pathlib import Path
import re
import struct
import time
import weekly_runtime as rt
import week_display as memory
import hull_rules
import designer_visuals
import destroyer_fuel
import destroyer_torpedoes

REPORT = Path(__file__).with_name("large_hulls_report.json")
LIMIT = hull_rules.LIMITS["overall"]
# mod.json setting -> hull_rules.LIMITS key
SETTINGS = {"max_tons": "overall", "dd_tons": "DD", "cl_tons": "CL", "ca_tons": "CA", "ke_tons": "KE",
            "cvl_tons": "CVL", "cv_tons": "CV", "cvl_aircraft": "CVL_aircraft"}


def hull_limits(settings):
    unknown = set(settings) - set(SETTINGS)
    if unknown:
        raise ValueError("Unknown large-hulls settings: " + ", ".join(sorted(unknown)))
    limits = {**hull_rules.LIMITS, **{SETTINGS[key]: value for key, value in settings.items()}}
    # Aircraft limits are signed-byte compares, and the extended machinery table
    # must end before the hook's message strings at allocation+0x8000.
    if not 34 <= limits["CVL_aircraft"] <= 127 or not 90000 <= limits["overall"] <= 280000:
        raise ValueError("CVL aircraft must be 34-127 and max_tons 90000-280000.")
    return limits


def discover(blob, text_base):
    method = rt.method_address(blob, text_base, "seDisplacementChange")
    start = method - text_base
    original = blob[start:start+5]
    if original != b"\x53\x56\x57\x8b\xd8":
        raise ValueError("Designer displacement handler differs from the supported build.")
    fields = list(re.finditer(rb"\x8b\x83(.{4})\xe8(.{4})(?:\x3d\xc8\x00\x00\x00|\x81\xf8\xc8\x00\x00\x00)", blob[start:start+0x70], re.DOTALL))
    if len(fields) != 1:
        raise ValueError("Cannot identify the displacement input control.")
    match = fields[0]
    field, = struct.unpack("<I", match.group(1))
    getter = method + match.start() + 11 + struct.unpack("<i", match.group(2))[0]
    # The getter's nearby range-check routine exposes its MinValue/MaxValue
    # fields. Require the paired comparison instead of assuming VCL offsets.
    checks = list(re.finditer(rb"\x8b\xb0(.{4})\x8b\xb8(.{4})\x3b\xf7", blob[getter-text_base:getter-text_base+0x180], re.DOTALL))
    if len(checks) != 1:
        raise ValueError("Cannot verify the spin control's range fields.")
    minimum, maximum = [struct.unpack("<I", value)[0] for value in checks[0].groups()]
    if maximum != minimum + 4 or not 0x100 <= minimum < 0x1000:
        raise ValueError("Unexpected designer range layout.")
    return method, field, maximum, original


def build_thunk(address, method, field, maximum, original, limit=LIMIT):
    code = bytearray(b"\x52\x8b\x90" + struct.pack("<I", field) + b"\x85\xd2\x74\x0a")
    code += b"\xc7\x82" + struct.pack("<II", maximum, limit)
    code += b"\x5a" + original + b"\xe9"
    code += struct.pack("<i", method + len(original) - (address + len(code) + 4))
    return bytes(code)


def attach(wait=30, **settings):
    limits = hull_limits(settings)
    memory.configure()
    deadline = time.monotonic() + wait
    while True:
        games = [(pid, path) for pid, path in rt.process_candidates() if path == rt.GAME / "RTW3.exe"]
        if len(games) == 1:
            break
        if time.monotonic() >= deadline:
            raise ValueError("Open the local game first.")
        time.sleep(0.5)
    pid, path = games[0]
    handle = rt.K.OpenProcess(0x438, False, pid)
    try:
        if REPORT.exists():
            prior = json.loads(REPORT.read_text(encoding="utf-8"))
            base_now, _ = rt.module_info(pid)
            if prior.get("pid") == pid and prior.get("base") == base_now and prior.get("attached") and rt.report_is_current(REPORT, pid):
                if rt.read(handle, prior["method"], 5).hex() == prior["replacement"]:
                    if prior.get("adapter_version") != 10:
                        raise ValueError("Close and reopen the game to upgrade the older large-hulls attachment.")
                    for item in prior["patches"]:
                        if rt.read(handle, item["address"], len(bytes.fromhex(item["replacement"]))).hex() != item["replacement"]:
                            raise ValueError("The existing hull-rules attachment has unexpected changes.")
                    return prior
                raise ValueError("The existing designer attachment has unexpected changes.")
        while True:
            try:
                base, size = rt.module_info(pid)
                text_base, blob = rt.text_section(handle, base)
                method, field, maximum, original = discover(blob, text_base)
                visuals_info = designer_visuals.discover(blob, text_base)
                fuel_plans, fuel_info = destroyer_fuel.discover(blob, text_base, limits["DD"])
                torpedo_info = destroyer_torpedoes.discover(blob, text_base, limits["DD"])
                _, native_table, _, _, _ = hull_rules.machinery_patches(blob, text_base, 0x10000000, limits)
                hull_rules.extended_table(rt.read(handle, native_table+100, 9000), limits["overall"])
                break
            except (OSError, ValueError):
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.5)
        # Auto superstructure: the player's own AI design templates, packed once and cached until they change.
        templates = designer_visuals.superstructure_templates(rt.GAME/"Data"/"IDes",
                                                               REPORT.with_name("superstructure_templates.bin"))
        allocation = rt.K.VirtualAllocEx(handle, None, 65536, 0x3000, 0x40)
        if not allocation:
            raise rt.win_error("Cannot allocate the designer hook")
        extra = rt.K.VirtualAllocEx(handle, None, 0x1000+len(templates[0]), 0x3000, 0x40)
        if not extra:
            rt.K.VirtualFreeEx(handle, allocation, 0, 0x8000)
            raise rt.win_error("Cannot allocate the superstructure templates")
        published, applied = False, []
        try:
            import ai_runtime
            import live_cheats
            ai_runtime.require_title_screen(handle, live_cheats.discover(blob, text_base))
            class_plans, strings = hull_rules.class_patches(blob, text_base, allocation, limits)
            suggestion_plan, suggestion_code = hull_rules.classification_patch(blob, text_base, allocation, limits)
            engine_plans, native_table, new_table, interpolation, engine = hull_rules.machinery_patches(blob, text_base, allocation, limits)
            table = hull_rules.extended_table(rt.read(handle, native_table+100, 9000), limits["overall"])
            visuals = designer_visuals.build(allocation, visuals_info, extra, templates)
            fuel = destroyer_fuel.build(allocation, fuel_info)
            torpedoes = destroyer_torpedoes.build(allocation, torpedo_info)
            code = build_thunk(allocation, method, field, maximum, original, limits["overall"])
            memory.write(handle, allocation, code)
            memory.write(handle, allocation+0x100, interpolation)
            memory.write(handle, allocation+hull_rules.SUGGESTION_OFFSET, suggestion_code)
            memory.write(handle, new_table, table)
            memory.write(handle, allocation+0x8000, strings)
            for block in visuals["blocks"] + fuel["blocks"] + torpedoes["blocks"]:
                memory.write(handle, block["address"], bytes.fromhex(block["bytes"]))
            memory.write(handle, visuals["locations"]["templates"], templates[0])
            rt.K.FlushInstructionCache(handle, allocation, 65536)
            rt.K.FlushInstructionCache(handle, extra, 0x1000)
            replacement = b"\xe9" + struct.pack("<i", allocation-method-5)
            plans = engine_plans + class_plans + [suggestion_plan] + visuals["patches"] + fuel_plans + fuel["patches"] + torpedoes["patches"] + [hull_rules.patch("Designer input", method, original, replacement)]
            for item in plans:
                expected = bytes.fromhex(item["original"])
                if rt.read(handle, item["address"], len(expected)) != expected:
                    raise ValueError("Game changed during hull-rule preparation. Nothing applied.")
            for item in plans:
                # Keep the allocation alive if any code has ever referenced it.
                published = True
                rt.write_code(handle, item["address"], bytes.fromhex(item["original"]), bytes.fromhex(item["replacement"]))
                applied.append(item)
                if rt.read(handle, item["address"], len(bytes.fromhex(item["replacement"]))).hex() != item["replacement"]:
                    raise ValueError("Hull-rule patch did not verify.")
            saved = {"pid": pid, "base": base, "method": method, "control_field": field, "maximum_field": maximum,
                 "allocation": allocation, "original": original.hex(), "replacement": replacement.hex(),
                 "adapter_version": 10, "patches": plans, "class_limits": limits, "superstructure_allocation": extra,
                 "destroyer_fuel": fuel_info,
                 "destroyer_torpedoes": {key: value for key, value in torpedoes.items() if key not in ("blocks", "patches")},
                 "designer_visuals": {key: value for key, value in visuals.items() if key not in ("blocks", "patches")},
                 "limit_tons": limits["overall"], "attached": True, "component_weights_changed": False,
                 "machinery_table": {"native": native_table, "extended": new_table, "engine": engine,
                                     "native_rows_preserved": 90, "extension": "HP90 * (D/90000)^(2/3)",
                                     "unsupported_speeds_preserved": True},
                 "limits_preserved": ["dock size", "treaties", "weapon and hull technology", "minimum speed and armament", "component weights"]}
            REPORT.write_text(json.dumps(saved, indent=2)+"\n", encoding="utf-8")
            return saved
        except Exception:
            for item in reversed(applied):
                rt.write_code(handle, item["address"], bytes.fromhex(item["replacement"]), bytes.fromhex(item["original"]))
            if not published:
                rt.K.VirtualFreeEx(handle, allocation, 0, 0x8000)
                rt.K.VirtualFreeEx(handle, extra, 0, 0x8000)
            raise
    finally:
        rt.K.CloseHandle(handle)


def detach():
    memory.configure()
    saved = json.loads(REPORT.read_text(encoding="utf-8"))
    candidates = dict(rt.process_candidates())
    if candidates.get(saved["pid"]) != rt.GAME / "RTW3.exe":
        raise ValueError("The hooked game session has ended.")
    handle = rt.K.OpenProcess(0x438, False, saved["pid"])
    try:
        base, _ = rt.module_info(saved["pid"])
        if base != saved["base"]:
            raise ValueError("Game session changed.")
        plans = saved.get("patches", [hull_rules.patch("Designer input", saved["method"], bytes.fromhex(saved["original"]), bytes.fromhex(saved["replacement"]))])
        for item in plans:
            expected = bytes.fromhex(item["replacement"])
            if rt.read(handle, item["address"], len(expected)) != expected:
                raise ValueError("Hull rules changed; no partial detach performed.")
        for item in reversed(plans):
            rt.write_code(handle, item["address"], bytes.fromhex(item["replacement"]), bytes.fromhex(item["original"]))
        # Retain the allocation until process exit in case a native call is in flight.
        saved["attached"] = False
        REPORT.write_text(json.dumps(saved, indent=2)+"\n", encoding="utf-8")
        return saved
    finally:
        rt.K.CloseHandle(handle)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("attach", "detach"))
    parser.add_argument("--settings", default="{}", help='JSON mod.json settings, for example {"max_tons": 250000}')
    args = parser.parse_args()
    try:
        print(json.dumps(attach(**json.loads(args.settings)) if args.command == "attach" else detach()))
    except (OSError, ValueError) as error:
        print(json.dumps({"ok": False, "message": str(error)}))
        raise SystemExit(1)
