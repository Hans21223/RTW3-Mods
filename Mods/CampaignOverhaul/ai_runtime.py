"""Opt-in, reversible native AI rule changes; no personal save editing."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import ai_rules
import live_cheats as live
import weekly_runtime as rt


MODES = ("torpedo-initiative", "fair-ai", "detection-only-evasion")


def report_path(mode):
    if mode not in MODES:
        raise ValueError("Unknown AI adapter.")
    return Path(__file__).with_name(mode.replace("-", "_") + "_report.json")


def verify(handle, plans, key):
    for item in plans:
        expected = bytes.fromhex(item[key])
        if rt.read(handle, item["address"], len(expected)) != expected:
            raise ValueError("AI rules changed: " + item["label"] + ". Operation refused.")


def apply_plans(handle, plans):
    verify(handle, plans, "original")
    applied = []
    try:
        for item in plans:
            rt.write_code(handle, item["address"], bytes.fromhex(item["original"]),
                          bytes.fromhex(item["replacement"]))
            applied.append(item)
        verify(handle, plans, "replacement")
    except Exception:
        for item in reversed(applied):
            rt.write_code(handle, item["address"], bytes.fromhex(item["replacement"]),
                          bytes.fromhex(item["original"]))
        raise


def checked_game():
    expected = json.loads((rt.GAME/"Mods/Manager/state.json").read_text(encoding="utf-8"))["game_sha256"]
    if hashlib.sha256((rt.GAME/"RTW3.exe").read_bytes()).hexdigest() != expected:
        raise ValueError("The game executable differs from the managed Steam build.")


def require_title_screen(handle, layout):
    main = live.integer(handle, layout["main_slot"]) & 0xffffffff
    if not main or live.integer(handle, main + layout["player_field"]):
        raise ValueError("Restart through Play with mods before loading a campaign; no live AI rule swap is allowed.")


def attach(mode, wait=30, settings=None):
    report = report_path(mode)
    checked_game()
    rt.configure_api()
    deadline = time.monotonic() + wait
    while True:
        games = [g for g in rt.process_candidates() if g[1].resolve() == (rt.GAME/"RTW3.exe").resolve()]
        if len(games) == 1:
            break
        if time.monotonic() >= deadline:
            raise ValueError("Open this local RTW3 copy first.")
        time.sleep(0.5)
    pid, _ = games[0]
    handle = rt.K.OpenProcess(0x438, False, pid)
    if not handle:
        raise rt.win_error("Cannot open the local game")
    try:
        module, _ = rt.module_info(pid)
        if report.exists():
            prior = json.loads(report.read_text(encoding="utf-8"))
            if prior.get("attached") and prior.get("pid") == pid and prior.get("base") == module and rt.report_is_current(report, pid):
                verify(handle, prior["patches"], "replacement")
                return prior
        while True:
            try:
                base, blob = rt.text_section(handle, module)
                plans, details = ai_rules.discover(blob, base, mode, settings)
                layout = live.discover(blob, base)
                break
            except (OSError, ValueError):
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.5)
        require_title_screen(handle, layout)
        apply_plans(handle, plans)
        saved = {"adapter": mode, "version": 1, "attached": True, "pid": pid, "base": module,
                 "patches": plans, "details": details, "personal_saves_modified": False,
                 "campaign_guard": {k: layout[k] for k in ("main_slot", "player_field")},
                 "battle_gameplay_verified": False, "strategic_ai_rewritten": False}
        try:
            report.write_text(json.dumps(saved, indent=2)+"\n", encoding="utf-8")
        except Exception:
            for item in reversed(plans):
                rt.write_code(handle, item["address"], bytes.fromhex(item["replacement"]),
                              bytes.fromhex(item["original"]))
            raise
        return saved
    finally:
        rt.K.CloseHandle(handle)


def detach(mode):
    report = report_path(mode)
    saved = json.loads(report.read_text(encoding="utf-8"))
    if not saved.get("attached"):
        return saved
    rt.configure_api()
    if dict(rt.process_candidates()).get(saved["pid"]) != rt.GAME/"RTW3.exe":
        raise ValueError("The attached game session has ended.")
    handle = rt.K.OpenProcess(0x438, False, saved["pid"])
    if not handle:
        raise rt.win_error("Cannot open the local game")
    try:
        if rt.module_info(saved["pid"])[0] != saved["base"]:
            raise ValueError("The game session changed.")
        require_title_screen(handle, saved["campaign_guard"])
        reverse = [{**p, "original": p["replacement"], "replacement": p["original"]}
                   for p in reversed(saved["patches"])]
        apply_plans(handle, reverse)
        saved["attached"] = False
        report.write_text(json.dumps(saved, indent=2)+"\n", encoding="utf-8")
        return saved
    finally:
        rt.K.CloseHandle(handle)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("attach", "detach"))
    parser.add_argument("--mode", required=True, choices=MODES)
    parser.add_argument("--settings", default="{}", help='JSON mod.json settings, for example {"roll": 50}')
    args = parser.parse_args()
    try:
        print(json.dumps(attach(args.mode, settings=json.loads(args.settings)) if args.command == "attach" else detach(args.mode)))
    except (OSError, ValueError, TypeError) as error:
        print(json.dumps({"ok": False, "message": str(error)}))
        raise SystemExit(1)
