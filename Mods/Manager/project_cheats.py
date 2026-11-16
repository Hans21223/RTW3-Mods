"""Shared selected/bulk yard cheats. No process or save writes here."""

SHIP_WIDTHS = {"Cost": 4, "BuildProgress": 4, "MonthlyCost": 4, "YearBuilt": 4,
               "Halted": 1, "Hurry": 1, "Rebuild": 1, "RepairTime": 4,
               "TimeToRefit": 4, "Sunk": 1}


def select(ships, ship_index=None, all_projects=None):
    if ship_index is not None and all_projects is not None:
        raise ValueError("Choose a selected ship or an all-ships option, not both.")
    if all_projects is not None:
        if all_projects not in ("build", "refit"):
            raise ValueError("Unknown all-ships option.")
        kinds = ("build",) if all_projects == "build" else ("refit", "rebuild")
        return [ship for ship in ships if ship["kind"] in kinds]
    if ship_index is None:
        return []
    if isinstance(ship_index, bool) or not isinstance(ship_index, int):
        raise ValueError("Choose a valid ship project.")
    selected = [ship for ship in ships if ship["index"] == ship_index]
    if len(selected) != 1:
        raise ValueError("The selected ship no longer has an active yard project.")
    return selected


def fleet_visible(row):
    # Strategic RTW3 ships encode losses in RepairTime, not a Sunk Boolean.
    # Preserve support for explicit Sunk fields in older imported fixtures.
    return not row.get("Sunk", 0) and row.get("RepairTime", 0) < 100


def describe(row, year):
    if not fleet_visible(row):
        return None
    cost, spent, monthly = (row.get(key, 0) for key in ("Cost", "BuildProgress", "MonthlyCost"))
    if cost > spent >= 0 and monthly > 0 and (
            spent > 0 or row.get("YearBuilt", 0) > year or row.get("Rebuild", 0)):
        return {"kind": "rebuild" if row.get("Rebuild", 0) else "build",
                "remaining_turns": max(1, (cost-spent+monthly-1)//monthly),
                "cost": cost, "spent": spent, "per_turn": monthly}
    repair = row.get("RepairTime", 0)
    # 100+ are native status sentinels, not 100-turn yard jobs. The engine
    # shares the small countdown between routine refits and damage repairs.
    if not row.get("Rebuild", 0) and 0 < repair < 100:
        return {"kind": "refit", "remaining_turns": repair,
                "cost": cost, "spent": spent, "per_turn": monthly}
    return None


def changes(project, turns):
    if isinstance(turns, bool) or not isinstance(turns, int) or not 1 <= turns <= 1200:
        raise ValueError("Choose 1-1200 remaining project turns.")
    if project["kind"] == "refit":
        if turns >= 100:
            raise ValueError("Refit / repair countdowns must be between 1 and 99 turns.")
        # Never change TimeToRefit: that is when maintenance is due, not the
        # remaining duration of the current yard visit.
        return {"RepairTime": turns}
    if project["kind"] not in ("build", "rebuild"):
        raise ValueError("Unsupported yard project.")
    remaining = project["cost"]-project["spent"]
    if remaining <= 0:
        raise ValueError("This construction project has already finished.")
    monthly = (remaining+turns-1)//turns
    if monthly > 2_000_000_000:
        raise ValueError("Requested construction spending is too large.")
    return {"MonthlyCost": monthly, "Halted": 0, "Hurry": 0}
