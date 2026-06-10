# MosaicSES Phase-2 — 10-Tenets Evaluation Framework — Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use `- [ ]` checkboxes. TDD: write the failing test, see red, implement, see green, commit.

**Goal:** Implement the 10-tenets evaluative overlay per the design spec: a `TENETS` vocabulary, `Channel.tenet_scores` (governance) + `Compartment.response_tenet_scores` (overlay, SESPy `Element` untouched), `MULTISES_SCHEMA_VERSION` 1→2, a `tenet_gap_analysis(ms)` function, a read-only "Tenet readiness" Comparative card, and demonstrative Curonian seed scores.

**Spec (source of truth):** `SESPy/docs/superpowers/specs/2026-06-09-mosaicses-phase2-tenets-design.md`. Section refs ("design §3.2") point there.

**Repo:** `C:/Users/arturas.baziukas/OneDrive - ku.lt/HORIZON_EUROPE/Marine-SABRES/MosaicSES` (work on local `main`, per chunk-4x precedent). The spec + this plan live in the SESPy repo.

**Environment:** all commands via `micromamba run -n shiny ...`. Run pytest with `micromamba run -n shiny pytest tests/ -q`.

**Baseline (verified 2026-06-09):** `main` at `e1625f4`; `MULTISES_SCHEMA_VERSION = 1` (`multises/data_structure.py:20`); `Channel` phase-2-reserved fields at `:231-235`; `ErrorCode` has `M205` (last hard) + `W303_TRANSBOUNDARY_CCI_MISSING`/`W400` (so `M206` and `W304` are the next free codes); `comparative_ui` has 5 `comparative-card`s; full unit suite 293 passed.

**Commit hygiene:** path-scoped `git add` with explicit paths only — never `git add -A`/`.`. Leave the user-managed `.gitignore`/`.superpowers/` untouched.

---

## Task 1: Data model — TENETS vocab, fields, validation, schema bump, round-trip

**Files:**
- Modify: `multises/data_structure.py`
- Modify: `multises/__init__.py` (re-exports)
- Test: `tests/test_tenets.py` (new)

- [ ] **Step 1: Write the failing data-model tests** — create `tests/test_tenets.py`. Use the real construction idiom (`seed_compartment(archetype, label=, id=)` builds a `Compartment` *with a project*; `MultiSESMetadata()` takes `name=`, not id/label; channels via `multises.channels.make_channel`):

```python
import math
import pytest
from multises import data_structure as ds
from multises.archetypes import seed_compartment
from multises.channels import make_channel
from multises.data_structure import (
    Channel, Compartment, MultiSES, MultiSESMetadata,
    TENETS, TENET_SLUGS, TENET_SCORE_MIN, TENET_SCORE_MAX,
    MULTISES_SCHEMA_VERSION, ErrorCode,
)


def _two_compartment_ms(channels):
    a = seed_compartment("lagoon", label="A", id="a")
    b = seed_compartment("coastal_sea", label="B", id="b")
    return MultiSES(metadata=MultiSESMetadata(), compartments=[a, b], channels=channels)


def _gov_channel(**kw):
    return make_channel(id="a_to_b_gov", source="a", target="b",
                        channel_type="governance", governance_regime="WFD", **kw)


def test_tenets_vocab_shape():
    assert len(TENETS) == 10
    assert len(TENET_SLUGS) == 10
    assert len(set(TENET_SLUGS)) == 10                 # unique
    assert TENET_SLUGS[0] == "ecological"              # canonical order is load-bearing
    assert TENET_SLUGS[-1] == "communicable"
    assert (TENET_SCORE_MIN, TENET_SCORE_MAX) == (1, 5)


def test_channel_tenet_scores_valid_and_partial():
    ch = _gov_channel(tenet_scores={"ecological": 5, "legal": 4})  # partial allowed
    assert ch.tenet_scores == {"ecological": 5, "legal": 4}


@pytest.mark.parametrize("bad", [
    {"not_a_tenet": 3}, {"ecological": 0}, {"ecological": 6},
    {"ecological": True}, {"ecological": 3.0},
])
def test_channel_tenet_scores_invalid_raise_m206(bad):
    with pytest.raises(ds._ChannelValidationError) as e:
        _gov_channel(tenet_scores=bad)
    assert e.value.code == ErrorCode.M206_INVALID_TENET_SCORES


def test_channel_tenet_scores_round_trip():
    ms = _two_compartment_ms([_gov_channel(tenet_scores={"ecological": 5, "political": 2})])
    res = MultiSES.from_json(ms.to_json())
    assert res.multises.channels[0].tenet_scores == {"ecological": 5, "political": 2}


def test_compartment_response_tenet_scores_round_trip_and_validation():
    a = seed_compartment("lagoon", label="A", id="a")
    a.response_tenet_scores = {"resp1": {"ecological": 4}}   # set post-build for the round-trip
    ms = MultiSES(metadata=MultiSESMetadata(), compartments=[a], channels=[])
    res = MultiSES.from_json(ms.to_json())
    assert res.multises.compartments[0].response_tenet_scores == {"resp1": {"ecological": 4}}
    with pytest.raises(ds._ChannelValidationError):
        seed_compartment("lagoon", label="A", id="a",
                         response_tenet_scores={"resp1": {"ecological": 9}})


def test_schema_version_unchanged():
    assert MULTISES_SCHEMA_VERSION == 1     # additive fields; no bump (design §3.4)
```

(`seed_compartment` must accept/forward `response_tenet_scores`; if it doesn't take arbitrary kwargs, set the attribute on the returned Compartment instead, as `test_compartment_response_tenet_scores_round_trip_and_validation` does for the round-trip case, and test the validation path by constructing `Compartment(...)` directly with a real project from `conftest.empty_project`.)

- [ ] **Step 2: Run → red.** `micromamba run -n shiny pytest tests/test_tenets.py -q` — expect ImportError/AttributeError (`TENETS` etc. absent), then assertion failures.

- [ ] **Step 3: Add the vocab + bounds** near the other module constants in `multises/data_structure.py` (after the `DELAYS`/`CCI` constants):

```python
TENETS: tuple[tuple[str, str], ...] = (
    ("ecological",      "Ecologically sustainable"),
    ("technological",   "Technologically feasible"),
    ("economic",        "Economically viable"),
    ("social",          "Socially desirable"),
    ("legal",           "Legally permissible"),
    ("administrative",  "Administratively achievable"),
    ("political",       "Politically expedient"),
    ("ethical",         "Ethically defensible"),
    ("cultural",        "Culturally inclusive"),
    ("communicable",    "Effectively communicable"),
)
TENET_SLUGS: tuple[str, ...] = tuple(slug for slug, _ in TENETS)
TENET_SCORE_MIN: int = 1
TENET_SCORE_MAX: int = 5
```

- [ ] **Step 4: Add the `M206` + `W304` ErrorCode constants** to the `ErrorCode` class (alongside `M205` and `W303`):

```python
    M206_INVALID_TENET_SCORES = "M206_INVALID_TENET_SCORES"
    W304_TENET_SCORE_UNKNOWN_RESPONSE = "W304_TENET_SCORE_UNKNOWN_RESPONSE"
```

- [ ] **Step 5: Add a shared validator helper** (module-level, reused by Channel + Compartment):

```python
def _validate_tenet_scores(scores: dict, *, where: str) -> None:
    """Raise _ChannelValidationError(M206) unless every key is a TENET slug and
    every value is an int (not bool) in TENET_SCORE_MIN..TENET_SCORE_MAX."""
    for slug, val in scores.items():
        if slug not in TENET_SLUGS:
            raise _ChannelValidationError(
                ErrorCode.M206_INVALID_TENET_SCORES,
                f"{where}: unknown tenet {slug!r}; expected one of {TENET_SLUGS}")
        if not isinstance(val, int) or isinstance(val, bool):
            raise _ChannelValidationError(
                ErrorCode.M206_INVALID_TENET_SCORES,
                f"{where}: tenet {slug!r} score must be int (got {type(val).__name__})")
        if not TENET_SCORE_MIN <= val <= TENET_SCORE_MAX:
            raise _ChannelValidationError(
                ErrorCode.M206_INVALID_TENET_SCORES,
                f"{where}: tenet {slug!r} score {val} out of {TENET_SCORE_MIN}..{TENET_SCORE_MAX}")
```

- [ ] **Step 6: Add `Channel.tenet_scores`** field (after the phase-2 reserved block, before `_unknown_channel_type_original`):

```python
    tenet_scores: dict[str, int] | None = None
```

and at the end of `Channel.__post_init__`:

```python
        if self.tenet_scores is not None:
            _validate_tenet_scores(self.tenet_scores, where=f"Channel {self.id!r}")
```

- [ ] **Step 7: Add `Compartment.response_tenet_scores`** field + `__post_init__` value/key validation:

```python
    response_tenet_scores: dict[str, dict[str, int]] | None = None
```

```python
        if self.response_tenet_scores is not None:
            for eid, scores in self.response_tenet_scores.items():
                _validate_tenet_scores(scores, where=f"Compartment {self.id!r} response {eid!r}")
```

(Place after the existing Compartment validation; if `Compartment` has no `__post_init__` yet, add one. Referential integrity is NOT here — it's the W304 soft check in Task 2.)

- [ ] **Step 8: Round-trip parse (NO schema bump).** Leave `MULTISES_SCHEMA_VERSION = 1` (design §3.4 — additive optional fields, no migration). In `MultiSES.from_dict`, the known-channel-type `Channel(...)` call (`data_structure.py:640-656`) gains `tenet_scores=ch_raw.get("tenet_scores")`; the unknown-channel-type *preserved* branch (`:618-629`) also gains `tenet_scores=ch_raw.get("tenet_scores")` for lossless round-trip. The `Compartment(...)` call (`:571-580`) gains `response_tenet_scores=c_raw.get("response_tenet_scores")`. `to_dict` needs no change (asdict emits the new fields as null — design §3.4).

- [ ] **Step 9: Re-export** in `multises/__init__.py`: add `TENETS`, `TENET_SLUGS`, `TENET_SCORE_MIN`, `TENET_SCORE_MAX` to imports + `__all__`.

- [ ] **Step 10: Run → green.** `micromamba run -n shiny pytest tests/test_tenets.py -q`. No existing schema test changes are needed (version stays 1).

- [ ] **Step 11: Commit**

```bash
git add multises/data_structure.py multises/__init__.py tests/test_tenets.py tests/test_data_structure.py
git commit -m "feat(mosaicses): tenets data model — Channel.tenet_scores + Compartment overlay (phase-2 #19)"
```

---

## Task 2: Referential-integrity soft check (`W304`) in `validate()`

**Files:**
- Modify: `multises/validate.py`
- Test: `tests/test_tenets.py` (append)

- [ ] **Step 1: Append the failing test:**

```python
def test_validate_warns_on_orphan_response_tenet_score():
    from multises.validate import validate
    c = Compartment(id="a", label="A", archetype="lagoon",
                    response_tenet_scores={"ghost_response": {"ecological": 3}})
    ms = MultiSES(metadata=MultiSESMetadata(id="m", label="M"), compartments=[c], channels=[])
    issues = validate(ms)
    codes = {i.code for i in issues}
    assert ErrorCode.W304_TENET_SCORE_UNKNOWN_RESPONSE in codes
```

(Adjust `validate()` import + `ValidationIssue.code` access to the real API — see `_check_governance_regimes` in `validate.py:131` for the pattern.)

- [ ] **Step 2: Run → red.** `pytest tests/test_tenets.py::test_validate_warns_on_orphan_response_tenet_score -q`.

- [ ] **Step 3: Add `_check_tenet_response_refs`** to `multises/validate.py`, mirroring `_check_governance_regimes`. For each compartment with `response_tenet_scores`, resolve element ids against that compartment's project Response elements (`c.project.isa_data.elements`, filter `el.type == "Responses"`); for any key not matching a Response element id, yield a `ValidationIssue(code=ErrorCode.W304_TENET_SCORE_UNKNOWN_RESPONSE, ...)`. Wire it into the top-level `validate()` (the `issues.extend(...)` block at ~:157).

- [ ] **Step 4: Run → green** (test_tenets.py whole file). **Commit:**

```bash
git add multises/validate.py tests/test_tenets.py
git commit -m "feat(mosaicses): W304 soft warning for orphaned response tenet scores"
```

---

## Task 3: `tenet_gap_analysis(ms)` analysis function

**Files:**
- Modify: `multises/comparative.py`
- Modify: `multises/__init__.py` (export)
- Test: `tests/test_tenets.py` (append)

- [ ] **Step 1: Append the failing test** (hand-built MultiSES: one governance channel scored `{ecological:5, political:2}`, one compartment with one Response scored `{ecological:3}`):

```python
def test_tenet_gap_analysis_columns_and_values():
    from multises.comparative import tenet_gap_analysis
    import math
    ch = _gov_channel(tenet_scores={"ecological": 5, "political": 2})
    ms = MultiSES(metadata=MultiSESMetadata(id="m", label="M"),
                  compartments=[Compartment(id="a", label="A", archetype="lagoon"),
                                Compartment(id="b", label="B", archetype="coastal_sea")],
                  channels=[ch])
    df = tenet_gap_analysis(ms)
    row = df[df.subject_kind == "governance_channel"].iloc[0]
    assert row.scored_count == 2 and row.gap_count == 8
    assert row.min_score == 2 and row.weakest_tenet == "political"
    assert math.isclose(row.mean_score, 3.5)
    assert row.source_compartment_id == "a" and row.target_compartment_id == "b"
    # full column set on empty input
    empty = tenet_gap_analysis(MultiSES(metadata=MultiSESMetadata(id="m", label="M"),
                                        compartments=[], channels=[]))
    assert list(empty.columns) == list(df.columns) and len(empty) == 0
```

- [ ] **Step 2: Run → red** (ImportError / no such function).

- [ ] **Step 3: Implement `tenet_gap_analysis`** in `multises/comparative.py` per design §4. Build a fixed `COLUMNS` list (the hero columns + one per `TENET_SLUGS` slug); iterate governance channels with `tenet_scores`, then each compartment's scored Responses (resolve label from `c.project.isa_data.elements`); compute `scored_count`, `gap_count = 10 - scored_count`, `mean_score` (NaN if 0), `min_score`, `weakest_tenet` (min value, ties → canonical `TENET_SLUGS` order). Return `pd.DataFrame(rows, columns=COLUMNS)` (full columns even when empty). Sort by `subject_kind`, `source_compartment_id`, `subject_id`.

- [ ] **Step 4: Export** `tenet_gap_analysis` in `multises/__init__.py`.

- [ ] **Step 5: Run → green.** **Commit:**

```bash
git add multises/comparative.py multises/__init__.py tests/test_tenets.py
git commit -m "feat(mosaicses): tenet_gap_analysis — gap-first tenet readiness frame (phase-2 #19)"
```

---

## Task 4: Curonian seed scores

**Files:**
- Modify: `multises/curonian/curonian_loac.json`
- Test: `tests/test_curonian_seed.py` (append)

- [ ] **Step 1: Append the failing seed test:**

```python
def test_seed_has_tenet_scores():
    from multises import seed_curonian
    from multises.comparative import tenet_gap_analysis
    ms = seed_curonian()
    df = tenet_gap_analysis(ms)
    assert len(df) >= 1
    assert (df.gap_count > 0).any()           # gap-first: at least one partial measure
```

- [ ] **Step 2: Run → red.**

- [ ] **Step 3: Add demonstrative scores** to `curonian_loac.json` (design §6): on 2–3 governance channels add `"tenet_scores": {...}` with high `ecological`/`legal`, lower `political`/`administrative`, omitting `cultural`/`communicable` (the gap); on 1–2 lagoon Responses add a `response_tenet_scores` entry on the owning compartment. Add a short `"_comment"` noting the scores are demonstrative (if the JSON loader tolerates an extra key; the metadata-key filter drops unknown top-level keys, but per-channel/compartment extra keys are ignored by the explicit-kwarg construction — verify it doesn't trip a stricter check). **No `schema_version` change** (the seed JSON carries none; loader defaults it).

- [ ] **Step 4: Run → green** (seed test + `tests/test_curonian_seed.py` whole file; fix any now-expected `W400` warning assertions). **Commit:**

```bash
git add multises/curonian/curonian_loac.json tests/test_curonian_seed.py
git commit -m "feat(mosaicses): demonstrative tenet scores in Curonian seed (phase-2 #19)"
```

---

## Task 5: Comparative "Tenet readiness" card (read-only)

**Files:**
- Modify: `multises_app/modules/comparative.py`
- Test: `tests/test_comparative_module.py` (update card count + new ids)

- [ ] **Step 1: Update the failing module test** — bump the `comparative-card` count 5 → 6 and assert the new output ids:

```python
def test_comparative_ui_has_tenet_card():
    from multises_app.modules.comparative import comparative_ui
    html = str(comparative_ui("test_id"))
    assert html.count("comparative-card") == 6
    assert 'id="test_id-tenet_table"' in html
    assert "Tenet readiness" in html
```

Also update any existing `test_comparative_ui_renders_5_cards` count assertion to 6 (1-for-1).

- [ ] **Step 2: Run → red.**

- [ ] **Step 3: Add the card** in `comparative_ui` after the "Response–Pressure gap" card (design §5):

```python
        ui.card(ui.card_header("Tenet readiness"),
                ui.output_ui("tenet_disclaimer"),
                ui.output_data_frame("tenet_table"),
                class_="comparative-card"),
```

- [ ] **Step 4: Add the server renders** in `comparative_server` (read-only, reactive on `state.active_multises`):

```python
    @render.ui
    def tenet_disclaimer():
        ms = state.active_multises.get()
        df = tenet_gap_analysis(ms)
        if df.empty:
            return ui.em("No tenet scores in this MultiSES yet.")
        return ui.help_text("Scores 1–5; blank = un-scored gap. Mean is over scored "
                            "tenets only and is NOT a readiness score — read it with "
                            "gap count and min.")

    @render.data_frame
    def tenet_table():
        ms = state.active_multises.get()
        df = tenet_gap_analysis(ms)
        return render.DataGrid(df, height="320px")
```

(Import `tenet_gap_analysis` from `multises`. Match the exact `state`/reactive idiom used by the existing `gap_lists`/`heatmap` renders in this module.)

- [ ] **Step 5: Run → green** (`tests/test_comparative_module.py`). **Commit:**

```bash
git add multises_app/modules/comparative.py tests/test_comparative_module.py
git commit -m "feat(mosaicses): Tenet readiness card in Comparative dashboard (phase-2 #19)"
```

---

## Task 6: Full suite + e2e + ship

**Files:**
- Modify: `tests/test_comparative_e2e.py` (card-count sync + panel assertion)

- [ ] **Step 1: Full unit suite (excl. e2e).** `micromamba run -n shiny pytest tests/ -q --ignore=tests/test_cross_view_e2e.py --ignore=tests/test_comparative_e2e.py --ignore=tests/test_project_e2e.py`. Baseline was 293; this adds `test_tenets.py` (~9) + seed (1) + module (1). Expect green; fix any stale `MULTISES_SCHEMA_VERSION == 1` or card-count assertions discovered.

- [ ] **Step 2: e2e card-count sync + panel assertion.** In `tests/test_comparative_e2e.py`, update any `cards.count() == 5` → `== 6`, and add: after loading the seed, the `#comparative-tenet_table` (or namespaced id) is visible with ≥ 1 data row and the disclaimer text is present.

- [ ] **Step 3: Run e2e.** `micromamba run -n shiny pytest tests/test_comparative_e2e.py -q`. Expect pass (~70–120s). If the tenet table selector is wrong, fix the locator only.

- [ ] **Step 4: Commit + push** (user-go-ahead for shared state per repo convention; the change is additive + green):

```bash
git add tests/test_comparative_e2e.py
git commit -m "test(mosaicses): comparative e2e — tenet readiness panel + card count (phase-2 #19)"
git push origin main
```

---

## Definition of done

- [ ] `TENETS` vocab + bounds in the library, re-exported; `M206`/`W304` codes added.
- [ ] `Channel.tenet_scores` + `Compartment.response_tenet_scores` validated, round-tripped; `MULTISES_SCHEMA_VERSION` stays 1 (additive fields, no bump); existing schema tests untouched.
- [ ] `validate(ms)` emits `W304` for orphaned response scores.
- [ ] `tenet_gap_analysis(ms)` returns the design §4 tidy frame (gap-first; full columns when empty; source/target compartment columns).
- [ ] Comparative "Tenet readiness" card renders table + disclaimer; read-only; 6 cards total.
- [ ] Curonian seed carries demonstrative, gap-bearing scores; loads at v2.
- [ ] Full unit suite green + comparative e2e green; pushed to origin.

## Spec-coverage self-check

- Design §3.1 vocab → Task 1 ✓
- Design §3.2 Channel.tenet_scores + M206 → Task 1 ✓
- Design §3.3 Compartment overlay + W304 (validate) → Tasks 1 + 2 ✓
- Design §3.4 schema v2 + round-trip → Task 1 ✓
- Design §4 tenet_gap_analysis (source/target cols, full-column empty) → Task 3 ✓
- Design §5 Comparative card → Task 5 ✓
- Design §6 seed → Task 4 ✓
- Design §7 tests → Tasks 1–6 ✓
