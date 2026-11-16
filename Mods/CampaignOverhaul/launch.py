"""Launch the updated local RTW3 copy through the installed Steam client."""
from __future__ import annotations

import argparse
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import winreg

import campaign_mod
import weekly_runtime
import runtime_registry
import runtime_host


def show_error(message):
    ctypes.windll.user32.MessageBoxW(None, message, "RTW3 Campaign Overhaul", 0x10)


def steam_path():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            return Path(winreg.QueryValueEx(key, "SteamExe")[0])
    except OSError:
        return Path(r"C:\Program Files (x86)\Steam\steam.exe")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for ident, adapter in runtime_registry.REGISTRY.items():
        parser.add_argument(adapter.cli_flag, dest=ident, action="store_true")
    parser.add_argument("--no-dialog", action="store_true", help="For automated launch checks")
    parser.add_argument("--settings", default="{}", help="JSON settings for each runtime adapter, validated by the mod loader")
    args = parser.parse_args()
    try:
        settings = json.loads(args.settings)
        selected = [ident for ident in runtime_registry.REGISTRY if vars(args)[ident]]
        # Validate even direct launcher use before starting Steam or the game.
        runtime_registry.plan(selected, settings)
        weekly = "calendar-days" in selected
        current = campaign_mod.state()
        if current.get("upgrade"):   # the local Steam copy; a release install was checked by mod_loader's verify
            if not current["upgrade"].get("complete"):
                raise ValueError("The Steam-copy update has not completed.")
            if campaign_mod.digest(campaign_mod.GAME / "RTW3.exe") != current["upgrade"]["steam_exe_sha256"]:
                raise ValueError("RTW3.exe differs from the copied Steam executable. Run Verify installation.cmd.")
        weekly_runtime.configure_api()
        running = weekly_runtime.process_candidates()
        if running:
            raise ValueError("RTW3 is already running. Close it before choosing another campaign mode.")
        if weekly and not args.no_dialog:
            choice = ctypes.windll.user32.MessageBoxW(None,
                "Experimental weekly calendar\n\n"
                f"Each campaign turn advances {settings.get('calendar-days', {}).get('days', 7)} days. Budgets, research, construction, AI and some timers still process once per turn. "
                "They are not yet balanced for weekly turns.\n\n"
                "Use a separate test campaign. The patch affects only this running session and resets when the game closes.\n\n"
                "Start the experimental mode?", "RTW3 - Experimental Weekly Calendar", 0x34)
            if choice != 6:
                return 0
        steam = steam_path()
        if not steam.is_file():
            raise ValueError("Steam was not found. Open Steam and sign in before launching this copy.")
        # Normal Steam app environment; the official executable and Steam client
        # still perform their ordinary license checks. No replacement DLLs.
        subprocess.Popen([str(steam), "-silent"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        env = os.environ.copy()
        env.update(SteamAppId="2008100", SteamGameId="2008100")
        visible = subprocess.STARTUPINFO()
        visible.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        visible.wShowWindow = 1
        game = subprocess.Popen([str(campaign_mod.GAME / "RTW3.exe")], cwd=campaign_mod.GAME, env=env, startupinfo=visible,
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not weekly:
            time.sleep(4)
            if game.poll() is not None:
                raise ValueError("The local game exited during startup. Check that Steam is signed in and owns RTW3.")
        runtime_host.wait_session(game.pid)
        result = runtime_host.run(selected, settings, game.pid)
        if not result["ok"]:
            raise ValueError("Runtime startup stopped: " + result.get("error", "See diagnostics.") +
                             " Close RTW3 when safe and retry before loading a campaign. Details: Mods/CampaignOverhaul/runtime_host_report.json")
        print(json.dumps({"framework_api": runtime_registry.API_VERSION, "pid": game.pid,
                          "runtime_ms": result["elapsed_ms"], "hooks_verified": result["hooks_verified"],
                          "adapters": result["adapters"]}))
        if "live-cheats" in selected:
            subprocess.Popen([str(campaign_mod.GAME / "RTW3 Mod Manager.exe"), "--game-tools", "--pid", str(game.pid)],
                             cwd=campaign_mod.GAME, startupinfo=visible,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return 0
    except (OSError, ValueError) as error:
        print(f"Launch stopped: {error}", file=sys.stderr)
        if not args.no_dialog:
            show_error(str(error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
