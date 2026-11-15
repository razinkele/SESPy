"""Port of R's connection knowledge-base scoring (R v1.35.6, ML off).

Mirrors ``lookup_knowledge_base``, ``.synonym_match``, ``.keyword_idf_weight``
and ``calculate_enhanced_relevance`` from ``ses_connection_knowledge_base.R``
(see ``docs/parity/k1b/R_SCORER_NOTES.md`` section 2). Pure functions; the
knowledge base is passed in as ``Snapshot.connection_db()``.

Every R match is a regex, so every match here is ``re.search`` (unanchored),
with ``re.ASCII`` when a pattern contains ``\\b`` (R's PCRE ``\\b`` is
ASCII-only). Floating-point operation order follows R exactly.

The no-match keyword lists below are the *live* ones from the KB file
(KB:1257-1291); R's dead `.calculate_basic_relevance` lists were dropped with
the old `connection_keywords.json` (K1b Task 6).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal


@dataclass(frozen=True)
class KBMatch:
    polarity: str
    strength: str
    probability: float
    match_quality: Literal["exact", "synonym"]


_BASE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "drivers_activities": ("fish", "food", "econom", "livelihood", "subsistence",
                           "commerc", "industr", "recreat", "tourism", "develop",
                           "demand", "need", "cultural", "spiritual", "energy",
                           "transport", "trade"),
    "activities_pressures": ("fish", "extract", "harvest", "develop", "construct",
                             "pollut", "discharge", "emission", "waste", "noise",
                             "disturb", "remov", "introduc", "invasive", "dredg",
                             "trawl", "aquacult", "farm"),
    "pressures_states": ("pollut", "nutrient", "contamin", "extract", "remov",
                         "habitat", "species", "abundance", "diversity", "structure",
                         "function", "ecosystem", "chemical", "physical", "biological",
                         "acidif", "warm", "noise", "litter"),
    "states_impacts": ("decline", "loss", "degrad", "change", "abundance",
                       "diversity", "habitat", "ecosystem", "service", "provision",
                       "regulat", "cultural", "support", "carbon", "protect"),
    "impacts_welfare": ("food", "protein", "nutrition", "income", "livelihood",
                        "employ", "health", "wellbeing", "recreation", "cultural",
                        "spiritual", "aesthetic", "economic", "social", "safety",
                        "property", "displace"),
    "responses_pressures": ("regulat", "protect", "conserv", "restor", "manag",
                            "monitor", "enforc", "limit", "restrict", "ban",
                            "quota", "closure", "zone", "designation", "treat",
                            "remov", "clean"),
    "welfare_responses": ("concern", "awareness", "demand", "advocacy", "pressure",
                          "policy", "legislation", "management", "action",
                          "intervention", "compens", "support"),
    "responses_drivers": ("policy", "awareness", "education", "incentiv", "subsid",
                          "tax", "regulation", "enforcement", "behavior", "demand"),
    "responses_activities": ("limit", "restrict", "ban", "regulat", "control",
                             "manage", "permit", "license", "quota", "closure",
                             "zone", "gear.*restrict"),
    "welfare_drivers": ("food", "econom", "livelihood", "income", "need",
                        "demand", "subsist", "employ", "security", "poverty"),
}

_COMMON_WORDS = ("chang", "increas", "decreas", "loss", "impact",
                 "effect", "manag", "develop", "system", "environ",
                 "marine", "coast", "ocean", "sea", "water")
_RARE_WORDS = ("eutrophic", "hypox", "acidif", "bleach", "trawl",
               "bycatch", "bioaccumul", "calcif", "permafrost",
               "denitrif", "anox", "pteropod", "sargassum",
               "ballast", "anti.?foul", "discarding", "ghost.*net")

_TERM_SPLIT = re.compile(r"\||\.\*|\.|\?|\*|\+|\(|\)")


@lru_cache(maxsize=None)
def _rx(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.ASCII if "\\b" in pattern else 0)


def _search(pattern: str, text: str) -> bool:
    return _rx(pattern).search(text) is not None


@lru_cache(maxsize=None)
def _pattern_terms(pattern: str) -> tuple[str, ...]:
    terms = (t.strip() for t in _TERM_SPLIT.split(pattern))
    return tuple(t for t in terms if len(t) >= 3)


def _synonym_match(text: str, pattern: str, synonym_db: dict) -> bool:
    terms = _pattern_terms(pattern)
    if not terms:
        return False
    for synonyms in synonym_db.values():
        if not any(_search(s, text) for s in synonyms):
            continue
        for pt in terms:
            for s in synonyms:
                if _search(pt, s) or _search(s, pt):
                    return True
    return False


@lru_cache(maxsize=None)
def _keyword_idf_weight(keyword: str) -> float:
    kw = keyword.lower()
    if any(_search(rw, kw) for rw in _RARE_WORDS):
        return 2.0
    if any(_search(cw, kw) for cw in _COMMON_WORDS):
        return 0.6
    return 1.0


_ENTRIES: dict[tuple[int, str, str], tuple] = {}
_SIDE_HITS: dict[tuple, tuple[bool, ...]] = {}
_SYN_CACHE: dict[tuple[int, str, str], bool] = {}


def _typed_entries(db: dict, from_type: str, to_type: str) -> tuple:
    """DB entries of one type pair, in DB order (cached per db object, which
    is kept alive so its id cannot be reused)."""
    key = (id(db), from_type, to_type)
    entries = _ENTRIES.get(key)
    if entries is None:
        _SYN_KEEPALIVE[id(db)] = db
        entries = tuple(e for e in db["connection_db"]
                        if e["from_type"] == from_type and e["to_type"] == to_type)
        _ENTRIES[key] = entries
    return entries


def _side_hits(db: dict, from_type: str, to_type: str, side: str,
               lowered: str, entries: tuple) -> tuple[bool, ...]:
    """Per-entry pattern hits for one name (a name meets many partners)."""
    key = (id(db), from_type, to_type, side, lowered)
    hits = _SIDE_HITS.get(key)
    if hits is None:
        pat = side + "_pattern"
        hits = tuple(_search(e[pat], lowered) for e in entries)
        _SIDE_HITS[key] = hits
    return hits


def _synonym_cached(db: dict, text: str, pattern: str) -> bool:
    key = (id(db), text, pattern)
    hit = _SYN_CACHE.get(key)
    if hit is None:
        hit = _synonym_match(text, pattern, db["synonym_db"])
        _SYN_CACHE[key] = hit
    return hit


def lookup_knowledge_base(from_name: str, from_type: str, to_name: str,
                          to_type: str, db: dict) -> KBMatch | None:
    from_lower = from_name.lower()
    to_lower = to_name.lower()
    entries = _typed_entries(db, from_type, to_type)
    from_hits = _side_hits(db, from_type, to_type, "from", from_lower, entries)
    to_hits = _side_hits(db, from_type, to_type, "to", to_lower, entries)
    best: KBMatch | None = None
    best_score = 0.0
    for entry, from_match, to_match in zip(entries, from_hits, to_hits):
        p = entry["probability"]
        if from_match and to_match:
            score = p * 1.0
            if score > best_score:
                best_score = score
                best = KBMatch(entry["polarity"], entry["strength"], p, "exact")
        elif from_match or to_match:
            if from_match:
                expanded = _synonym_cached(db, to_lower, entry["to_pattern"])
            else:
                expanded = _synonym_cached(db, from_lower, entry["from_pattern"])
            if expanded:
                score = p * 0.8
                if score > best_score:
                    best_score = score
                    best = KBMatch(entry["polarity"], entry["strength"],
                                   p * 0.9, "synonym")
    return best


def _words(lowered: str) -> list[str]:
    stripped = re.sub(r"[^a-z ]", "", lowered)
    if stripped == "":
        return []
    return re.split(r"\s+", stripped)


@lru_cache(maxsize=1 << 16)
def _keyword_hits(keywords: tuple[str, ...], lowered: str) -> tuple[bool, ...]:
    """Per-name keyword hits (a name is scored against many partners)."""
    return tuple(_search(kw, lowered) for kw in keywords)


_SYN_KEEPALIVE: dict[int, dict] = {}
_SYN_GROUPS: dict[tuple[int, str], frozenset] = {}


def _synonym_groups_hit(synonym_db: dict, lowered: str) -> frozenset:
    """Indices of the synonym groups with a member matching a word of the
    name. Depends on one name only, so it is cached per (db, name); the db
    is kept alive so its id cannot be reused."""
    key = (id(synonym_db), lowered)
    hit = _SYN_GROUPS.get(key)
    if hit is None:
        _SYN_KEEPALIVE[id(synonym_db)] = synonym_db
        words = _words(lowered)
        hit = frozenset(
            idx for idx, synonyms in enumerate(synonym_db.values())
            if any(_search(s, w) for s in synonyms for w in words))
        _SYN_GROUPS[key] = hit
    return hit


_UNSET = object()


def calculate_enhanced_relevance(from_name: str, to_name: str, from_type: str,
                                 to_type: str, db: dict, kb=_UNSET) -> float:
    """``kb`` may carry the caller's already-computed lookup (or None for no
    match) so a scorer does one lookup per candidate; R repeats it, but the
    lookup is deterministic."""
    if kb is _UNSET:
        kb = lookup_knowledge_base(from_name, from_type, to_name, to_type, db)
    if kb is not None:
        kb_score = kb.probability if kb.match_quality == "exact" else kb.probability * 0.9
        return min(1.0, kb_score)

    from_lower = from_name.lower()
    to_lower = to_name.lower()
    keywords = _BASE_KEYWORDS.get(f"{from_type}_{to_type}")
    if keywords is None:
        return 0.5

    total_weight = 0.0
    matched_weight = 0.0
    from_hits = _keyword_hits(keywords, from_lower)
    to_hits = _keyword_hits(keywords, to_lower)
    for kw, from_hit, to_hit in zip(keywords, from_hits, to_hits):
        weight = _keyword_idf_weight(kw)
        total_weight = total_weight + weight
        if from_hit and to_hit:
            matched_weight = matched_weight + weight * 1.5
        elif from_hit or to_hit:
            matched_weight = matched_weight + weight

    bonus = 0.0
    shared = (_synonym_groups_hit(db["synonym_db"], from_lower)
              & _synonym_groups_hit(db["synonym_db"], to_lower))
    for _ in shared:
        bonus = bonus + 0.1
    bonus = min(bonus, 0.3)

    if total_weight == 0:
        return 0.3
    keyword_score = matched_weight / total_weight
    relevance = 0.2 + 0.75 * min(1.0, keyword_score + bonus)
    return min(1.0, relevance)
