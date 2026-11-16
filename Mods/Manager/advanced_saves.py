"""Searchable save fields with a conservative editable schema and slot backups."""
import datetime
import math
import re
import save_cheats as saves

GENERAL = {
    "Year": (1850, 2100), "Month": (1, 12), "Day": (1, 31), "ResearchSpeed": (1, 1000),
    "ResearchVariation": (0, 2), "FleetSize": (0, 8), "GameMaxAirbaseSize": (10, 1000),
    "Treaties": (0, 1), "TreatyCalibreLimit": (0, 2147483647), "TreatyDisplacementLimit": (0, 2147483647),
    "TreatyTimeRemaining": (0, 1200), "TreatyTonnageBasePercentage": (0, 1000),
    "SubBanPoss": (0, 1), "SubBanTime": (0, 1200), "HardPeaceDeals": (0, 1), "AiAdvantage": (0, 1),
    "AutoBuildSubs": (0, 1), "AutoBuildSubType": (0, 5)
}
NATION = {saved: (low, high) for saved, low, high in saves.FIELDS.values() if saved != "ResearchSpeed"}
NATION.update({"FleetMorale": (-10, 10), "IntelEffort": (0, 100), "ResearchPct": (0, 100),
               "PilotTraining": (0, 100), "AvailableRadarSets": (0, 100000), "VP": (0, 1000000000),
               "BuildConstraintTime": (0, 1200), "PendingTrainingTime": (0, 1200),
               "GunneryTraining": (0, 1), "NightFighting": (0, 1), "TorpedoWarfare": (0, 1), "DamageControl": (0, 1),
               "PendingGunneryTraining": (0, 1), "PendingNightFighting": (0, 1),
               "PendingTorpedoWarfare": (0, 1), "PendingDamageControl": (0, 1)})
SHIP = {"CrewQuality": (0, 3), "TimeToRefit": (0, 1200), "RepairTime": (0, 1200),
        "Cost": (1, 1000000000), "BuildProgress": (0, 1000000000), "MonthlyCost": (0, 1000000000),
        "Maintenance": (0, 1000000000), "Halted": (0, 1), "Hurry": (0, 1),
        "YearBuilt": (1850, 2100), "EngineYear": (1850, 2100), "BattleStars": (0, 100000),
        "ObsoleteDate": (0, 2100), "Mines": (0, 10000)}


def rule(section, key, current):
    bounds = None
    if section == "General": bounds = GENERAL.get(key)
    elif re.fullmatch(r"Nation\d+", section):
        bounds = NATION.get(key)
        match = re.fullmatch(r"Research\d+(ResearchPoints|Prio|Advantage)", key)
        if match:
            bounds = {"ResearchPoints": (0, 1000000000), "Prio": (1, 3), "Advantage": (-100, 100)}[match.group(1)]
        if key in {"AdmiralName", "AdmiralRank", "Leader", "ParliamentName"}:
            return {"editable": True, "type": "text", "max_length": 120, "note": "Display text; original byte encoding only."}
    elif re.fullmatch(r"Nation\d+Ships", section):
        match = re.fullmatch(r"Ship\d+(.+)", key)
        if match:
            field = match.group(1)
            bounds = SHIP.get(field)
            if field in {"Name", "Description", "Fate"}:
                return {"editable": True, "type": "text", "max_length": 500 if field != "Name" else 120,
                        "note": "Text only; ship IDs and design references stay unchanged."}
    if bounds and re.fullmatch(r"-?\d+", current) and bounds[0] <= int(current) <= bounds[1]:
        return {"editable": True, "type": "integer", "minimum": bounds[0], "maximum": bounds[1],
                "note": "Native save value. Allowed editor range: "+str(bounds[0])+" to "+str(bounds[1])+"."}
    return {"editable": False, "type": "protected", "note": "Read-only: structural, design-linked, unsupported or outside the editor's validated range."}


def inspect(value, section="General", query="", offset=0, limit=250):
    import mod_loader
    path = saves.resolve_save(value)
    raw = path.read_bytes()
    _, sections, _ = saves.parse(raw)
    if section != "*" and section not in sections: raise ValueError("Select an existing save section.")
    if not 0 <= offset <= 1000000 or not 1 <= limit <= 500: raise ValueError("Invalid field page.")
    rows, total_editable = [], 0
    for owner, data in sections.items():
        if section != "*" and owner != section: continue
        for key, current in data.items():
            if query.lower() not in (owner+" "+key+" "+current).lower(): continue
            spec = rule(owner, key, current)
            total_editable += int(spec["editable"])
            rows.append({"section": owner, "key": key, "value": current, **spec})
    return {"ok": True, "path": str(path), "sha256": saves.hashlib.sha256(raw).hexdigest(),
            "sections": list(sections), "section": section, "offset": offset, "limit": limit,
            "total": len(rows), "editable": total_editable, "fields": rows[offset:offset+limit],
            "game_running": bool(mod_loader.running_games())}


def edit(value, edits, expected_hash):
    import mod_loader
    if mod_loader.running_games(): raise ValueError("Close RTW3 before applying saved-campaign edits.")
    path = saves.resolve_save(value)
    raw = path.read_bytes()
    if not expected_hash or saves.hashlib.sha256(raw).hexdigest() != expected_hash: raise ValueError("The save changed. Reload fields before applying.")
    lines, sections, positions = saves.parse(raw)
    if not isinstance(edits, list) or len(edits) > 1000: raise ValueError("Choose at most 1000 existing fields per edit.")
    changed, seen = {}, set()
    for item in edits:
        section, key = item.get("section"), item.get("key")
        pair = (section, key)
        if pair in seen: raise ValueError("Duplicate field in save edit.")
        seen.add(pair)
        if pair not in positions: raise ValueError("Save fields cannot be added or renamed.")
        current = sections[section][key]
        if item.get("expected") != current: raise ValueError("A field changed. Reload before applying.")
        spec = rule(section, key, current)
        if not spec["editable"]: raise ValueError("Protected save field: "+section+"/"+key)
        value = item.get("value")
        if not isinstance(value, str) or any(c in value for c in "\r\n\0"): raise ValueError("Enter a single-line field value.")
        if spec["type"] == "integer":
            if not re.fullmatch(r"-?\d+", value) or not spec["minimum"] <= int(value) <= spec["maximum"]: raise ValueError("Value outside the allowed range for "+key)
            value = str(int(value))
        else:
            if len(value) > spec["max_length"]: raise ValueError("Text is too long for "+key)
            try: value.encode("latin-1")
            except UnicodeEncodeError: raise ValueError("Text must use characters supported by the original save encoding.")
        if value != current: changed[pair] = value
    for (section, key), value in changed.items():
        sections[section][key] = value
    try:
        general = sections["General"]
        datetime.date(int(general["Year"]), int(general["Month"]), int(general["Day"]))
    except (ValueError, KeyError): raise ValueError("The proposed campaign date is not a valid calendar date.")
    touched_ships = {(section, re.match(r"Ship\d+", key).group()) for section, key in changed
                     if re.fullmatch(r"Nation\d+Ships", section) and re.fullmatch(r"Ship\d+(Cost|BuildProgress|MonthlyCost)", key)}
    for section, prefix in touched_ships:
        data = sections[section]
        cost, spent = int(data.get(prefix+"Cost", 0)), int(data.get(prefix+"BuildProgress", 0))
        if cost < 0 or spent < 0 or spent > cost: raise ValueError("Ship build progress must be between zero and its total cost.")
    if not changed: return {"ok": True, "message": "No fields changed."}
    for pair, value in changed.items():
        index = positions[pair]
        old_line = lines[index]
        ending = old_line[len(old_line.rstrip("\r\n")):]
        lines[index] = pair[1]+"="+value+ending
    output = "".join(lines).encode("latin-1")
    _, check, _ = saves.parse(output)
    if any(check[s][k] != value for (s, k), value in changed.items()): raise ValueError("Proposed save did not validate.")
    backup = saves.commit(path, output, expected_hash, [{"section": s, "key": k, "value": v} for (s, k), v in changed.items()])
    return {"ok": True, "message": f"Applied {len(changed)} saved fields. Reload this campaign in RTW3.", "backup": str(backup)}
