"""Remove predictive torpedo turnaways, preserving native late detection.

This does not implement a new wake-spotting model. Mines retain their native
side-specific knowledge queries and proximity/detection/hit resolution.
"""
import re
import struct
import weekly_runtime as rt
from hull_rules import patch, unique
from ai_rules import calls_to, target_at


PREDICTIVE_MESSAGES = (
    " selects AVOID TORPEDO ATTACK 11 ",
    " selects AVOID TORPEDO ATTACK ",
    " CL selects AVOID TORPEDO ATTACK ",
)
FOLLOW_MESSAGE = "on lead is avoiding torpedoes!"
MINE_ERROR = "Debug: Error in IsInMinefield procedure!"


def string_pointers(blob, base, text, count):
    encoded = text.encode("utf-16-le") + b"\0\0"
    hits = [m.start() for m in re.finditer(re.escape(encoded), blob)
            if m.start() >= 4 and struct.unpack_from("<I", blob, m.start()-4)[0] == len(text)]
    if len(hits) != count:
        raise ValueError("Unsupported hazard message layout: " + text)
    for at in hits:
        if at < 4 or struct.unpack_from("<I", blob, at-4)[0] != len(text):
            raise ValueError("Invalid native hazard string header.")
    return [base + at for at in hits]


def pointer_refs(blob, pointer):
    return [m.start() for m in re.finditer(re.escape(struct.pack("<I", pointer)), blob)]


def audit_mine_knowledge(blob, base):
    error, = string_pointers(blob, base, MINE_ERROR, 1)
    ref, = pointer_refs(blob, error)
    if blob[ref-1] != 0xb8:
        raise ValueError("Unsupported mine-query error handler.")
    prologue = b"\x55\x8b\xec\x83\xc4\xe8\x53\x56\x57\x33\xc9"
    window = max(0, ref-0x200)
    start = window + unique(blob[window:ref], prologue, "side-specific mine query")
    body = blob[start:ref]
    # With a ship, native code branches past the two-layer editor/no-ship path.
    # It constructs MineLayer{ship.Side}; the AI must supply a ship, not nil.
    test = unique(body, b"\x85\xdb\x75", "mine-query ship guard")
    branch = start + test + 4 + struct.unpack("<b", body[test+3:test+4])[0]
    side_load = b"\x8d\x55\xe8\x8b\x83\x55\x0a\x00\x00\xe8"
    if blob[branch:branch+len(side_load)] != side_load:
        raise ValueError("Mine query no longer selects the supplied ship's side.")
    # The operand is a Delphi string constant. Check its actual bytes, not the
    # number of other 'MineLayer' strings in unrelated game/editor routines.
    at = branch + 0x14
    if blob[at:at+1] != b"\xba":
        raise ValueError("Cannot verify the mine knowledge layer prefix.")
    pointer, = struct.unpack_from("<I", blob, at+1)
    if blob[pointer-base:pointer-base+20] != "MineLayer".encode("utf-16-le") + b"\0\0":
        raise ValueError("Unexpected mine knowledge layer.")
    query = base + start
    callers = calls_to(blob, base, query)
    explicit_ship = []
    for call in callers:
        off = call-base
        # Native AI movement checks: point + actual ship, or division flagship.
        if blob[off-2:off] == b"\x8b\x13":
            explicit_ship.append(call)
        elif blob[off-3:off] == b"\x8b\xd0\x58" and blob[off-10:off-8] == b"\x8b\x03":
            explicit_ship.append(call)
    if len(explicit_ship) != 3:
        raise ValueError("The audited AI mine-routing arguments changed.")
    return {"query": query, "ship_guard": base+start+test,
            "ship_layer_branch": base+branch,
            "explicit_ship_ai_query_calls": explicit_ship,
            "mine_avoidance_changed": False, "mine_detection_and_damage_changed": False,
            "scope": "three explicit-ship tactical routing calls; not a complete strategic mine audit"}


def discover(blob, base):
    plans, logger_targets, covered = [], set(), []
    for text, expected_strings, expected_refs in (
        (PREDICTIVE_MESSAGES[0], 1, 1),
        (PREDICTIVE_MESSAGES[1], 3, 4),
        (PREDICTIVE_MESSAGES[2], 1, 1),
    ):
        refs = [ref for ptr in string_pointers(blob, base, text, expected_strings)
                for ref in pointer_refs(blob, ptr)]
        if len(refs) != expected_refs:
            raise ValueError("Unexpected predictive torpedo decision references.")
        for ref in refs:
            start = ref-8
            original = b"\xc6\x43\x2f\x06\xff\x73\x15"
            if blob[start:start+7] != original or blob[ref-1] != 0x68:
                raise ValueError("Unsupported predictive torpedo stance assignment.")
            # Skip assignment, log construction and threat-pointer write as one
            # unit. Earlier native stance decisions are retained, not guessed.
            tail = list(re.finditer(rb"\x8b\xd3\xe8(.{4})\x89\x73\x2b",
                                    blob[ref+4:ref+0x90], re.DOTALL))
            if len(tail) != 1:
                raise ValueError("Cannot verify the complete predictive torpedo decision block.")
            end = ref+4+tail[0].end()
            logger_targets.add(target_at(blob, base, base+ref+4+tail[0].start()+2))
            changed = b"\xe9"+struct.pack("<i", end-start-5)+b"\x90\x90"
            plans.append(patch("No predictive torpedo turnaway " + str(len(plans)+1),
                               base+start, original, changed))
            covered.append(base+start)
    if len(logger_targets) != 1:
        raise ValueError("Predictive torpedo branches do not share the native AI logger.")
    assignments = [base+m.start() for m in re.finditer(re.escape(b"\xc6\x43\x2f\x06"), blob)]
    if sorted(assignments) != sorted(covered):
        raise ValueError("Unreviewed predictive torpedo assignments exist.")
    # Followers must not inherit a leader's predictive turnaway/course either.
    follow, = string_pointers(blob, base, FOLLOW_MESSAGE, 1)
    ref, = pointer_refs(blob, follow)
    lo = max(0, ref-0x90)
    pattern = b"\x8b\x03\x8b\x40\x3c\x80\x78\x2f\x06\x75"
    at = lo + unique(blob[lo:ref], pattern, "predictive lead-division turnaway")
    branch = at+len(pattern)-1
    end = branch+2+struct.unpack("<b", blob[branch+1:branch+2])[0]
    if not ref < end < ref+0x90 or b"\xc6\x40\x2f\x06" not in blob[branch:end]:
        raise ValueError("Unsupported inherited torpedo turnaway boundary.")
    plans.append(patch("Do not inherit predictive torpedo turns", base+branch,
                       b"\x75", b"\xeb"))
    return plans, {"predictive_decision_blocks_skipped": 6, "predictive_following_disabled": True,
                   "applies_to": "automatically controlled divisions on both sides",
                   "native_last_minute_torpedo_evasion_preserved": True,
                   "projectile_spotting_model_added": False,
                   "new_battles_required": True,
                   "mine_knowledge_audit": audit_mine_knowledge(blob, base),
                   "full_ai_information_access_audited": False}
