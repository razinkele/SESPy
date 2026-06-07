"""Pure list-mutation helpers for the stakeholder register.

No Shiny imports — every function takes a list and returns a NEW list, so the
reactive module layer stays a thin wrapper and these stay trivially testable.
The caller injects `today` (keeps these pure / no datetime.now inside) and is
responsible for name+type validation before calling add/update.
"""

from __future__ import annotations

from dataclasses import replace

from sespy.data_structure import Communication, Engagement, Stakeholder
from sespy.utils import next_id


def add_stakeholder(
    items: list[Stakeholder], fields_: dict, *, today: str
) -> list[Stakeholder]:
    # INVARIANT: `fields_` contains only valid Stakeholder field names and
    # NEVER `id` or `created_at` (those are assigned here). The module layer
    # builds it from exactly the form inputs, so this holds.
    sid = next_id([s.id for s in items], "SH")
    return [*items, Stakeholder(id=sid, created_at=today, **fields_)]


def update_stakeholder(
    items: list[Stakeholder], sid: str, fields_: dict
) -> list[Stakeholder]:
    return [replace(s, **fields_) if s.id == sid else s for s in items]


def remove_stakeholder(items: list[Stakeholder], sid: str) -> list[Stakeholder]:
    return [s for s in items if s.id != sid]


# --- SH2: Power-Interest grid classification (pure) -------------------------
_LEVEL_NUM = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
QUADRANTS = ("key_players", "keep_satisfied", "keep_informed", "monitor")


def level_num(level: str) -> int | None:
    """Map a power/interest code to its 1-3 axis position, or None if blank/unknown."""
    return _LEVEL_NUM.get(level)


def classify_quadrant(power: str, interest: str) -> str | None:
    """Mendelow quadrant for a (power, interest) pair, or None if either is unset.

    Binning: a value is "high" iff it is MEDIUM or HIGH (>= 2 on the 1-3 axis),
    matching the plot's colored regions. This classifies MEDIUM stakeholders
    (R dropped them from its summary entirely).
    """
    p, i = level_num(power), level_num(interest)
    if p is None or i is None:
        return None
    high_p, high_i = p >= 2, i >= 2
    if high_p and high_i:
        return "key_players"
    if high_p and not high_i:
        return "keep_satisfied"
    if not high_p and high_i:
        return "keep_informed"
    return "monitor"


def summarize_quadrants(items: list[Stakeholder]) -> dict[str, list[str]]:
    """Return {quadrant_key: [names]} for the 4 quadrants plus "unplotted"
    (stakeholders missing power or interest). All 5 keys always present."""
    out: dict[str, list[str]] = {q: [] for q in QUADRANTS}
    out["unplotted"] = []
    for s in items:
        q = classify_quadrant(s.power, s.interest)
        out[q if q is not None else "unplotted"].append(s.name)
    return out


# --- SH3: engagement activity log (pure) -----------------------------------
ENGAGEMENT_METHODS = ("workshop", "interview", "survey", "focus_group",
                      "public_meeting", "advisory_committee", "email_newsletter",
                      "one_on_one", "site_visit", "other")
ENGAGEMENT_STATUSES = ("planned", "completed", "cancelled", "ongoing")


def add_engagement(
    items: list[Engagement], fields_: dict, *, today: str
) -> list[Engagement]:
    # INVARIANT: `fields_` contains only valid Engagement field names and NEVER
    # `id` or `created_at` (those are assigned here).
    eid = next_id([e.id for e in items], "ENG")
    return [*items, Engagement(id=eid, created_at=today, **fields_)]


def remove_engagement(items: list[Engagement], eid: str) -> list[Engagement]:
    return [e for e in items if e.id != eid]


def _label(code: str, known: tuple[str, ...], translate, prefix: str) -> str:
    # Translate only KNOWN codes (Translator.t() returns the key on a miss);
    # an unknown or blank code is passed through verbatim.
    if code and code in known:
        return translate(f"{prefix}.{code}")
    return code


def engagement_rows(
    engagements: list[Engagement], stakeholders: list[Stakeholder], *, translate
) -> list[dict]:
    """Display rows for the engagement log table: resolve stakeholder_id -> name
    (dangling id -> ""), map method/status codes -> labels (known codes only),
    in input order."""
    names = {s.id: s.name for s in stakeholders}
    return [
        {
            "stakeholder": names.get(e.stakeholder_id, ""),
            "method": _label(e.method, ENGAGEMENT_METHODS, translate,
                             "stakeholders.activity.method"),
            "date": e.date,
            "objectives": e.objectives,
            "outcomes": e.outcomes,
            "status": _label(e.status, ENGAGEMENT_STATUSES, translate,
                             "stakeholders.activity.status"),
            "facilitator": e.facilitator,
        }
        for e in engagements
    ]


# --- SH4: communication plan (pure) ----------------------------------------
COMMUNICATION_AUDIENCES = ("all_stakeholders", "key_players", "government",
                           "industry", "ngos", "local_communities",
                           "scientific_community", "specific_stakeholder")
COMMUNICATION_TYPES = ("report", "newsletter", "presentation", "website_update",
                       "press_release", "social_media", "email", "meeting_notes",
                       "other")
COMMUNICATION_FREQUENCIES = ("one_time", "weekly", "monthly", "quarterly",
                             "annual", "as_needed")


def add_communication(
    items: list[Communication], fields_: dict, *, today: str
) -> list[Communication]:
    cid = next_id([c.id for c in items], "COMM")
    return [*items, Communication(id=cid, created_at=today, **fields_)]


def remove_communication(
    items: list[Communication], cid: str
) -> list[Communication]:
    return [c for c in items if c.id != cid]


def communication_rows(
    communications: list[Communication], *, translate
) -> list[dict]:
    """Display rows for the communication log: map audience/type/frequency codes
    -> labels (known codes only), in input order."""
    return [
        {
            "audience": _label(c.audience, COMMUNICATION_AUDIENCES, translate,
                               "stakeholders.comm.audience"),
            "type": _label(c.comm_type, COMMUNICATION_TYPES, translate,
                           "stakeholders.comm.type"),
            "date": c.date,
            "frequency": _label(c.frequency, COMMUNICATION_FREQUENCIES, translate,
                                "stakeholders.comm.frequency"),
            "message": c.message,
            "responsible": c.responsible,
        }
        for c in communications
    ]


# --- SH5: analysis summary (pure) ------------------------------------------
def stakeholder_stats(stakeholders, engagements, communications) -> dict:
    return {
        "total": len(stakeholders),
        "types": len({s.stakeholder_type for s in stakeholders if s.stakeholder_type}),
        "sectors": len({s.sector for s in stakeholders if s.sector}),
        "high_power": sum(1 for s in stakeholders if s.power == "HIGH"),
        "high_interest": sum(1 for s in stakeholders if s.interest == "HIGH"),
        "engagements": len(engagements),
        "communications": len(communications),
    }


def engagement_coverage(stakeholders, engagements) -> float:
    if not stakeholders:
        return 0.0
    engaged = {e.stakeholder_id for e in engagements}
    covered = sum(1 for s in stakeholders if s.id in engaged)
    return covered / len(stakeholders) * 100


def count_by(stakeholders, field: str) -> dict:
    counts: dict = {}
    for s in stakeholders:
        key = getattr(s, field)
        counts[key] = counts.get(key, 0) + 1
    return counts
