"""Build-checked, symmetric torpedo initiative and limited AI fairness rules.

Discovery works on the authenticated game's unpacked .text, never its DRM or
on-disk executable. This is not a replacement strategic/tactical AI.
"""
import re
import struct
import weekly_runtime as rt
import live_cheats as live
from hull_rules import patch, unique


TORPEDO_ROLL = 75  # Was Random(100); no change to hit probability.


def calls_to(blob, base, target):
    return [base + m.start() for m in re.finditer(rb"\xe8(.{4})", blob, re.DOTALL)
            if base + m.start() + 5 + struct.unpack("<i", m.group(1))[0] == target]


def target_at(blob, base, call):
    off = call - base
    if not 0 <= off <= len(blob) - 5 or blob[off] != 0xe8:
        raise ValueError("Expected a direct native call.")
    target = call + 5 + struct.unpack_from("<i", blob, off + 1)[0]
    if not base <= target < base + len(blob):
        raise ValueError("Native call leaves the verified code image.")
    return target


def torpedo_plans(blob, base, roll=TORPEDO_ROLL):
    # Only the low byte of the native mov eax,100 changes.
    if not 1 <= roll <= 255:
        raise ValueError("The torpedo assessment roll must be 1-255 (native 100).")
    shot = rt.method_address(blob, base, "TorpedoShotPossible")
    fire = rt.method_address(blob, base, "FireMount")
    friendly = rt.method_address(blob, base, "IsFriendlyShipInLineOfFire")
    shots = calls_to(blob, base, shot)
    if len(shots) != 2:
        raise ValueError("Unsupported automatic torpedo firing paths.")
    # The automatic firing routine immediately precedes the named mount-firing
    # routine. Verify its complete boundary and both fast/slow torpedo paths.
    prologue = b"\x53\x56\x57\x55\x83\xc4\xe4\x8b\xd9\x8b\xf2\x89\x04\x24"
    first = min(shots) - base
    window = max(0, first - 0x900)
    automatic = base + window + unique(blob[window:first], prologue, "automatic torpedo routine")
    if not automatic < min(shots) < max(shots) < fire < automatic + 0x1000:
        raise ValueError("Torpedo routine boundaries disagree.")
    body = blob[automatic-base:fire-base]
    if not body.endswith(b"\x83\xc4\x1c\x5d\x5f\x5e\x5b\xc3\x90"):
        raise ValueError("Unsupported torpedo return contract.")
    for name, destination in (("launch", fire), ("friendly-fire", friendly)):
        if len(calls_to(body, automatic, destination)) != 2:
            raise ValueError("Cannot verify both native torpedo " + name + " checks.")
    candidates = calls_to(blob, base, automatic)
    if len(candidates) != 2:
        raise ValueError("Unsupported torpedo assessment paths.")
    plans, randoms = [], set()
    for index, call in enumerate(sorted(candidates)):
        at = call - base - 23
        original = blob[at:at+5]
        expected = b"\x3b\x44\x24\x04\x7d\x0c\x8b\xcb\x8b\xd6\x8b\x04\x24"
        if original != b"\xb8\x64\x00\x00\x00" or blob[at+10:at+23] != expected:
            raise ValueError("Unsupported torpedo opportunity roll.")
        randoms.add(target_at(blob, base, base+at+5))
        plans.append(patch("Torpedo opportunity assessment " + str(index+1), base+at+1,
                           original[1:2], bytes([roll])))
    if len(randoms) != 1:
        raise ValueError("The torpedo paths do not share the native random generator.")
    # Preserve every instruction in the actual firing routine. In particular,
    # uncertainty, range, arcs, loaded mounts and friendly-fire checks remain.
    return plans, {"automatic_fire": automatic, "mount_fire": fire,
                   "assessment_roll_before": 100, "assessment_roll_after": roll,
                   "applies_to": "both sides, automated torpedo decisions",
                   "hit_chances_changed": False, "native_firing_checks_preserved": True}


def fairness_plans(blob, base):
    # Cross-check the load/store paths, instead of trusting a remembered offset.
    refs = live.literal_refs(blob, base, "AiAdvantage")
    fields = []
    for ref in refs:
        body = blob[ref+4:ref+0x25]
        for m in re.finditer(rb"\xe8(.{4})\x8b\x55.\x88\x82(.{4})", body, re.DOTALL):
            fields.append(struct.unpack("<I", m.group(2))[0])
    if len(fields) != 1 or not 0x100 < fields[0] < 0x8000:
        raise ValueError("Cannot verify the native AI advantage setting.")
    field = fields[0]
    packed = struct.pack("<I", field)
    # One read is save serialization, six are game decisions. The save flag is
    # intentionally left alone: disabling this mod restores the original setting.
    comparisons = list(re.finditer(rb"\x80([\xb8\xbb\xbe])" + re.escape(packed) + b"\x00", blob))
    arithmetic = list(re.finditer(rb"\x0f\xb6\x97" + re.escape(packed) + rb"\xc1\xe2\x02\x83\xc2\x05", blob))
    serialized = list(re.finditer(rb"\x0f\xb6\x86" + re.escape(packed) + b"\x50\xb9", blob))
    if len(comparisons) != 5 or len(arithmetic) != 1 or len(serialized) != 1:
        raise ValueError("AI advantage consumers differ from the audited build.")
    saved_read = serialized[0].start()
    if saved_read+9 not in refs:
        raise ValueError("AI advantage serialization cross-check failed.")
    plans = [patch("AI advantage decision " + str(i+1), base+m.start(), m.group(),
                   b"\x38\xc0" + b"\x90"*5) for i, m in enumerate(comparisons)]
    at = arithmetic[0].start()
    plans.append(patch("AI advantage diplomatic weighting", base+at, blob[at:at+7],
                       b"\xba\x00\x00\x00\x00\x90\x90"))
    # Verify the emergency grant against the independently discovered Funds
    # field in the nation's save loader, and only in the AI budget method.
    funds, _ = live.load_field(blob, base, "Funds")
    budget = rt.method_address(blob, base, "AINationAdjustBudget")
    body = blob[budget-base:budget-base+0x500]
    grant = b"\x81\x83" + struct.pack("<I", funds) + struct.pack("<I", 2000)
    grant_at = unique(body, grant, "AI emergency funds grant")
    gate = b"\x81\xbb" + struct.pack("<I", funds) + struct.pack("<i", -10000)
    gates = [m.start() for m in re.finditer(re.escape(gate), body[:grant_at])]
    if not gates:
        raise ValueError("Cannot verify AI emergency grant gate.")
    start = gates[-1]
    end = grant_at + len(grant)
    if body[start+10:start+12] != b"\x7d" + bytes([end-start-12]) or end-start != 75:
        raise ValueError("AI emergency grant branch changed.")
    # Skip the entire grant event, including its misleading budget report.
    new = b"\xe9" + struct.pack("<i", end-start-5) + b"\x90"*5
    plans.append(patch("No AI emergency 2000-fund grant", budget+start, gate, new))
    return plans, {"advantage_field": field, "advantage_decision_reads_disabled": 6,
                   "emergency_grant_removed": 2000, "nation_funds_field": funds,
                   "campaign_settings_edited": False, "all_ai_asymmetries_audited": False,
                   "normal_nation_budgets_and_technology_preserved": True}


def discover(blob, base, mode, settings=None):
    if mode == "torpedo-initiative":
        return torpedo_plans(blob, base, **(settings or {}))
    if mode == "fair-ai":
        return fairness_plans(blob, base)
    if mode == "detection-only-evasion":
        import hazard_rules
        return hazard_rules.discover(blob, base)
    raise ValueError("Unknown AI rules adapter.")
