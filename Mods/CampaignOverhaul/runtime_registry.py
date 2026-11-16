"""Reviewed adapter API v2. Package manifests select adapters, never Python paths.

Keep schemas, launch flags, invocation styles and ordering in this one registry.
The native signatures and per-adapter title-screen guards remain authoritative.
"""
from dataclasses import dataclass, field
import importlib

API_VERSION = 2


@dataclass(frozen=True)
class Adapter:
    id: str
    module: str
    style: str = "plain"
    bounds: dict = field(default_factory=dict)
    after: tuple = ()
    requires: tuple = ()
    flag: str = ""

    @property
    def cli_flag(self):
        return self.flag or "--" + self.id


_ADAPTERS = (
    Adapter("calendar-days", "weekly_runtime", "kwargs", {"days": (1, 28)}, flag="--weekly"),
    Adapter("torpedo-initiative", "ai_runtime", "mode", {"roll": (1, 255)}),
    Adapter("fair-ai", "ai_runtime", "mode"),
    Adapter("detection-only-evasion", "ai_runtime", "mode"),
    Adapter("week-display", "week_display"),
    Adapter("large-hulls", "large_hulls", "kwargs", {
        "max_tons": (90000, 280000), "dd_tons": (3800, 280000), "cl_tons": (14000, 280000),
        "ke_tons": (2500, 280000), "cvl_tons": (16000, 280000),
        "cv_tons": (16000, 280000), "cvl_aircraft": (34, 127)}),
    Adapter("legacy-fleet", "legacy_fleet"),
    Adapter("timeline-2030", "timeline_2030", "kwargs", {"end_year": (1890, 9998), "cutoff_year": (1891, 9999)}),
    Adapter("campaign-security", "campaign_security", requires=("live-cheats",)),
    Adapter("campaign-qol", "campaign_qol", "settings", {
        "max_active_ships": (50, 10000), "max_building_ships": (1, 1000), "min_procurement_days": (1, 90),
        "invade_possessions": (0, 1)},
        after=("campaign-security",)),
    Adapter("battle-ai", "battle_ai", "settings", {
        "contact_memory_minutes": (1, 60), "memory_radius_yards": (5000, 100000),
        "capital_max_advance_yards": (2000, 20000), "capital_gun_range_percent": (50, 90),
        "stance_commit_minutes": (0, 60), "withdraw_dead_zone": (0, 50),
        "missile_standoff_percent": (50, 85), "catapult_strikes": (0, 1)}, after=("campaign-qol",)),
    Adapter("research-traits", "research_traits", "settings", {
        "research_advantage_bonus_percent": (0, 300), "technical_excellence_bonus_percent": (0, 200)},
        after=("battle-ai",)),
    # Traits hashes the native cap window, so it must attach before budget patches it.
    Adapter("research-budget", "research_budget", "settings", {
        "overflow_percent": (0, 100), "max_turn_progress_percent": (20, 100)}, after=("research-traits",)),
    Adapter("aircraft-improvements", "aircraft_improvements", after=("research-traits",)),
    # Traits hashes a window over the Research<N> key calls this adapter retargets.
    Adapter("modern-research", "modern_research", requires=("timeline-2030",), after=("research-traits", "aircraft-improvements")),
    # Requires means present, not necessarily installed first: security and QoL
    # extend the idle dispatcher which live-cheats discovers later.
    Adapter("live-cheats", "live_cheats", after=("campaign-security", "campaign-qol", "battle-ai", "research-traits", "aircraft-improvements")),
    Adapter("in-game-submarines", "in_game_submarines", "pid", requires=("live-cheats",), after=("live-cheats",)),
    # Missile AI audits native arc/firing windows; VLS extends them afterwards.
    Adapter("vls-cells", "vls_cells", after=("battle-ai", "live-cheats", "in-game-submarines"),
            requires=("modern-research",)),
    # Big guns rewrites gun-level and calibre code that these adapters audit (their audits read it back as
    # native through modern_research.normalize); attaching last keeps their checks on untouched code anyway.
    Adapter("big-guns", "big_guns", after=("campaign-security", "campaign-qol", "research-traits", "research-budget",
                                           "modern-research", "live-cheats", "vls-cells")),
    # The frigate type reroutes 1,600 native reads; attaching last lets it skip the reads others already hook.
    Adapter("frigate-type", "frigate_type", requires=("modern-research",), after=(
        "calendar-days", "torpedo-initiative", "fair-ai", "detection-only-evasion", "week-display", "large-hulls",
        "legacy-fleet", "timeline-2030", "campaign-security", "campaign-qol", "battle-ai", "research-traits",
        "research-budget", "aircraft-improvements", "modern-research", "live-cheats", "in-game-submarines",
        "vls-cells", "big-guns")),
)
REGISTRY = {adapter.id: adapter for adapter in _ADAPTERS}
SCHEMAS = {ident: adapter.bounds for ident, adapter in REGISTRY.items()}


def validate_settings(ident, values, registry=None):
    registry = REGISTRY if registry is None else registry
    if ident not in registry:
        raise ValueError("Unknown reviewed runtime adapter: " + str(ident))
    if not isinstance(values, dict):
        raise ValueError(ident + " settings must be an object.")
    bounds = registry[ident].bounds
    for name, value in values.items():
        if name not in bounds:
            raise ValueError(ident + ": unknown setting " + str(name))
        low, high = bounds[name]
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f"{ident}: {name} must be a whole number from {low} to {high}.")
    if ident == "timeline-2030" and values.get("cutoff_year", values.get("end_year", 2030)+1) <= values.get("end_year", 2030):
        raise ValueError("The timeline cutoff must follow its end year.")
    return dict(values)


def plan(selected, settings=None, registry=None):
    """Stable dependency order, independent of checkbox/manifest order."""
    registry = REGISTRY if registry is None else registry
    selected = list(selected)
    if len(selected) != len(set(selected)):
        raise ValueError("A runtime adapter was selected twice.")
    settings = {} if settings is None else settings
    if not isinstance(settings, dict) or set(settings) - set(selected):
        raise ValueError("Runtime settings must belong to selected adapters.")
    wanted = set(selected)
    for ident in selected:
        validate_settings(ident, settings.get(ident, {}), registry)
        missing = set(registry[ident].requires) - wanted
        if missing:
            raise ValueError(ident + " requires adapters: " + ", ".join(sorted(missing)))
    pending = [ident for ident in registry if ident in wanted]
    ordered = []
    while pending:
        ready = next((ident for ident in pending if not (set(registry[ident].after) & set(pending))), None)
        if ready is None:
            raise ValueError("Runtime adapter ordering cycle: " + ", ".join(pending))
        pending.remove(ready)
        ordered.append(ready)
    return [{"adapter": ident, "settings": dict(settings.get(ident, {})),
             "module": registry[ident].module, "flag": registry[ident].cli_flag,
             "after": list(registry[ident].after), "requires": list(registry[ident].requires)} for ident in ordered]


def invoke(ident, settings, pid):
    """Only this trusted registry chooses an import or callable."""
    values = validate_settings(ident, settings)
    spec = REGISTRY[ident]
    attach = importlib.import_module(spec.module).attach
    if spec.style == "mode":
        return attach(ident, settings=values)
    if spec.style == "settings":
        return attach(settings=values)
    if spec.style == "kwargs":
        return attach(**values)
    if spec.style == "pid":
        return attach(pid=pid)
    return attach()
