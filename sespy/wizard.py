"""Pure-data definition of the AI-ISA wizard flow.

This module has NO Shiny imports — it's a flat data file plus the
suggest_connections() stub. The Shiny module at
`sespy/modules/ai_isa_wizard.py` imports from here; SP3 and SP4 will
later replace `suggest_connections` with real scoring backends.

The 12 steps mirror R's `ai_isa_assistant_module.R` question_flow.R
1:1 by step index and target. The 6 distinct R step types collapse to
4 widget archetypes (choice_one, choice_many, freeform_multiple,
connection_review).

Element-type mapping for steps 4-10 (the freeform_multiple steps that
write Element objects to project_data.isa_data.elements):
- impacts → Ecosystem Services (the impact ON ecosystem services)
- welfare → Goods & Benefits (welfare derived from goods & benefits)
This matches `constants.ELEMENT_ID_PREFIX` (impacts→ES, welfare→GB).
"""
from __future__ import annotations

from typing import Any

from .data_structure import WizardState, ConnectionSuggestion, ELEMENT_TYPE_MAP
from .connection_scorer import suggest_connections as _suggest_impl
from .regional_seas import get_regional_seas


# ---------------------------------------------------------------------------
# Wizard step flow — 12 steps as a list of dicts. Each dict has:
#   step:       int (0-11)
#   title_key:  str — i18n key suffix (resolved as wizard.step_<key>_title)
#   archetype:  str — one of choice_one, choice_many, freeform_multiple, connection_review
#   target:     str — key in wizard_answers + element-type mapping (for steps 4-10)
# ---------------------------------------------------------------------------

WIZARD_STEPS: list[dict[str, Any]] = [
    {"step": 0,  "title_key": "regional_sea",       "archetype": "choice_one",         "target": "regional_sea"},
    {"step": 1,  "title_key": "ecosystem",          "archetype": "choice_one",         "target": "ecosystem_type"},
    {"step": 2,  "title_key": "countries",          "archetype": "choice_many",        "target": "countries"},
    {"step": 3,  "title_key": "main_issue",         "archetype": "choice_many",        "target": "main_issue"},
    {"step": 4,  "title_key": "drivers",            "archetype": "freeform_multiple",  "target": "drivers"},
    {"step": 5,  "title_key": "activities",         "archetype": "freeform_multiple",  "target": "activities"},
    {"step": 6,  "title_key": "pressures",          "archetype": "freeform_multiple",  "target": "pressures"},
    {"step": 7,  "title_key": "states",             "archetype": "freeform_multiple",  "target": "states"},
    {"step": 8,  "title_key": "impacts",            "archetype": "freeform_multiple",  "target": "impacts"},
    {"step": 9,  "title_key": "welfare",            "archetype": "freeform_multiple",  "target": "welfare"},
    {"step": 10, "title_key": "responses",          "archetype": "freeform_multiple",  "target": "responses"},
    {"step": 11, "title_key": "connection_review",  "archetype": "connection_review",  "target": "connections"},
]


# ---------------------------------------------------------------------------
# Regional-seas knowledge base — sourced from sespy/regional_seas.json
# (loaded once at module import via sespy/regional_seas.py).
#
# SP2 (2026-05-02) replaced SP1's inline 5-sea mock with the real
# 11-sea KB. Originally exported as `REGIONAL_SEAS_PLACEHOLDER` for
# back-compat with SP1's import; renamed to `REGIONAL_SEAS` on the
# same day (post-SP2 cleanup, ahead of SP3).
# ---------------------------------------------------------------------------

REGIONAL_SEAS: dict[str, dict[str, Any]] = get_regional_seas()


# ---------------------------------------------------------------------------
# suggest_connections — SP1 stub.
#
# SP3 (TF-IDF + rules) and SP4 (Claude API) replace this with real
# implementations. The signature is the contract: a WizardState in,
# a list of ConnectionSuggestion out. SP1 always returns [].
# ---------------------------------------------------------------------------

def suggest_connections(state: WizardState) -> list[ConnectionSuggestion]:
    """SP3 contract: rule-based scoring across all 10 connection types.
    Delegates to sespy.connection_scorer.suggest_connections (imported
    as _suggest_impl at module top).

    SP4 (Claude API) will replace the implementation behind a settings
    switch; the signature is the contract.
    """
    return _suggest_impl(state)
