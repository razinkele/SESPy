"""DAPSI(W)R(M) link rules (P1a): classify a (from_type, to_type) pair, seed
its default polarity, and describe off-rule links.

Off-rule links are allowed and warned about, as R does
(`validate_connection(strict = FALSE)`): ISA entry shows a note, and
`persistent_storage.validate_project_payload` logs them through
`log_off_rule_links`. Nothing is ever rejected.

Shiny-free at import: `sespy.i18n` imports `shiny.reactive`, so it is only
imported inside `off_rule_message` when no translator is passed.
`persistent_storage`, the R template mapper and P2's sync script import this
module. tests/test_link_rules.py checks that in a subprocess.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Literal

from .constants import DAPSIWRM_ADJACENCY_RULES, DAPSIWRM_ELEMENTS

if TYPE_CHECKING:
    from .data_structure import Element
    from .i18n import Translator

logger = logging.getLogger(__name__)

LinkClass = Literal["canonical", "extension", "off_rule", "untyped"]

_KNOWN_TYPES = frozenset(DAPSIWRM_ELEMENTS)
_LOG_PAIRS = 5     # how many off-rule pairs one log line names


def _target(from_type: str, to_type: str):
    rule = DAPSIWRM_ADJACENCY_RULES.get(from_type)
    if rule is None:
        return None, None
    for kind, targets in (("canonical", rule.targets),
                          ("extension", rule.extension_targets)):
        for t in targets:
            if t.to_type == to_type:
                return kind, t
    return None, None


def classify(from_type: str, to_type: str) -> LinkClass:
    """"untyped" when either type is "" or not one of the 7
    DAPSIWRM_ELEMENTS (QSEM themes, a legacy "Measures"); untyped pairs are
    never flagged. Otherwise canonical, extension or off_rule."""
    if from_type not in _KNOWN_TYPES or to_type not in _KNOWN_TYPES:
        return "untyped"
    kind, _ = _target(from_type, to_type)
    return kind or "off_rule"


def default_polarity(from_type: str, to_type: str) -> str:
    """The pair's rule polarity, else "+" (what R's
    get_rule_default_polarity returns in practice)."""
    _, t = _target(from_type, to_type)
    return t.polarity if t is not None else "+"


def rule_id(from_type: str, to_type: str) -> str | None:
    _, t = _target(from_type, to_type)
    return t.rule_id if t is not None else None


def seed_polarity(src_el: Element | None, tgt_el: Element | None) -> str | None:
    """Polarity the ISA entry form pre-fills: None while either endpoint is
    missing or both are the same element, else default_polarity()."""
    if src_el is None or tgt_el is None or src_el.id == tgt_el.id:
        return None
    return default_polarity(src_el.type, tgt_el.type)


def off_rule_message(from_label: str, from_type: str, to_label: str,
                     to_type: str, translator: Translator | None) -> str:
    """The `entry.off_rule_link` text. Type placeholders take the raw
    canonical type names (as the entry form's type dropdown shows them)."""
    fmt = dict(source=from_label, target=to_label,
               source_type=from_type, target_type=to_type)
    if translator is not None:
        return translator.t("entry.off_rule_link", **fmt)
    from .i18n import t      # function-local: keeps this module Shiny-free
    return t("entry.off_rule_link", **fmt)


def note_for(src_el: Element | None, tgt_el: Element | None,
             translator: Translator | None) -> str | None:
    """The ISA entry warning for the chosen pair, or None (missing endpoint,
    same element, or a pair that is not off-rule)."""
    if src_el is None or tgt_el is None or src_el.id == tgt_el.id:
        return None
    if classify(src_el.type, tgt_el.type) != "off_rule":
        return None
    return off_rule_message(src_el.label, src_el.type, tgt_el.label,
                            tgt_el.type, translator)


def log_off_rule_links(project_or_isa: Any, *, context: str) -> int:
    """Count the off-rule links of a Project or IsaData. Logs one WARNING on
    `sespy.link_rules` only when the count is above 0 (a clean project logs
    nothing). Returns the count."""
    isa = getattr(project_or_isa, "isa_data", project_or_isa)
    types = {el.id: el.type for el in isa.elements}
    off: list[str] = []
    for c in isa.connections:
        ft, tt = types.get(c.source, ""), types.get(c.target, "")
        if classify(ft, tt) == "off_rule":
            off.append(f"{c.source}->{c.target} ({ft} -> {tt})")
    if off:
        more = f" (+{len(off) - _LOG_PAIRS} more)" if len(off) > _LOG_PAIRS else ""
        logger.warning("%s: %d off-rule link(s): %s%s", context, len(off),
                       "; ".join(off[:_LOG_PAIRS]), more)
    return len(off)
