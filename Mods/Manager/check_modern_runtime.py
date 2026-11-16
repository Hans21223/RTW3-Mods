"""Read-only installed/runtime validation. Never loads or advances a campaign."""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/"CampaignOverhaul"))
import modern_research as modern
import live_cheats as live


def check():
    saved = json.loads(modern.REPORT.read_text(encoding="utf-8"))
    live.memory.configure()
    if dict(live.rt.process_candidates()).get(saved["pid"]) != live.rt.GAME/"RTW3.exe":
        raise ValueError("The validated modern-research session has ended.")
    if live.rt.module_info(saved["pid"])[0] != saved["base"]:
        raise ValueError("The modern-research session changed.")
    handle = live.rt.K.OpenProcess(0x410, False, saved["pid"])
    if not handle: raise live.rt.win_error("Cannot inspect the running research package")
    try:
        modern.verify(handle, saved["patches"], "replacement")
        payload_hash = modern.check_payload()
        details = saved["details"]
        for index, site in enumerate(details["getters"]):
            code = modern.effect_thunk(site)
            if live.rt.read(handle, saved["allocation"]+index*0x1000, len(code)) != code:
                raise ValueError("A research effect buffer changed.")
        nodes = modern.tree.render()[1]
        matched = dict(ids=0, names=0, years=0, prerequisites=0, costs=0)
        for node in nodes:
            at = details["table_id_base"]+node["area"]*details["table_stride"]+node["slot"]*details["record_stride"]
            matched["ids"] += live.integer(handle, at) == node["id"]
            matched["names"] += live.text_value(handle, at-21, "") == node["name"]
            matched["years"] += live.integer(handle, at-13) == node["year"]
            matched["prerequisites"] += live.integer(handle, at+4) == node["prerequisite"]
            matched["costs"] += live.integer(handle, at-4) == node["cost_units"]*20000
        if any(value != len(nodes) for value in matched.values()):
            raise ValueError("The loaded research table is not the unmodified title-screen package: "+str(matched))
        dispatcher, read_handle = live.session(saved["pid"])
        try:
            main = live.integer(read_handle, dispatcher["layout"]["main_slot"])
            loaded = bool(main and live.integer(read_handle, main+dispatcher["layout"]["player_field"]))
            reveal = dispatcher.get("battle_reveal", {}).get("details", {})
            if not reveal.get("known_ship_rendering_preserved"):
                raise ValueError("The optimized battle-map reveal hooks are not installed.")
        finally: live.rt.K.CloseHandle(read_handle)
        return {"ok": True, "pid": saved["pid"], "module_base": saved["base"],
                "research_sha256": payload_hash, "effect_hooks": len(saved["patches"]),
                "new_technologies": len(nodes), "loaded_table_matches": matched,
                "optimized_reveal_attached": True, "campaign_loaded": loaded,
                "personal_saves_modified": False, "turns_advanced": 0,
                "battle_frame_timing_measured": False, "long_campaign_gameplay_verified": False}
    finally: live.rt.K.CloseHandle(handle)


if __name__ == "__main__":
    result = check()
    (HERE/"modern-research-validation.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result))
