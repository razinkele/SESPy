# Blind Rating Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in "blind mode" to Rate Connections that hides the per-rater `current_ratings` list until the current rater submits their own rating for the selected connection (anti-anchoring).

**Architecture:** A display gate on the `current_ratings` output in `rate_connections.py` plus a sidebar checkbox; two i18n keys. No schema/consensus/`network.py` change.

**Tech Stack:** Shiny for Python, pytest/Playwright.

## Global Constraints

- Sidebar toggle `ui.input_checkbox("blind_mode", t("rate.blind_mode"), value=False)` added directly after the existing `contested_only` checkbox.
- `current_ratings` gate (after the existing `if conn is None or not conn.ratings: return "—"` early-return): get `rater` via try/except; `rater_has_rated = bool(rater) and any(r.rater_id == rater for r in conn.ratings)`; `if input.blind_mode() and not rater_has_rated: return ui.tags.p(t("rate.blind_hidden"), class_="text-muted")` — placed BEFORE building the peer `<ul>`. Read `input.blind_mode()` directly (static checkbox, no try/except, like `contested_only`); it is the LEFT operand of the `and`, so the reactive dependency always registers whenever ratings exist.
- i18n: `rate.blind_mode` + `rate.blind_hidden`, **each with all 9 languages** (en, es, fr, de, lt, pt, it, no, el) — `test_loader_handles_all_supported_languages` hard-fails on any missing language.
- The e2e hidden state is only reachable with a peer rating present AND a different current rater who hasn't rated (blank project → `conn.ratings` empty → `"—"` early-return, blind branch never hit). Use the existing two-rater flow.
- No schema/consensus/`network.py` change. Run pytest/e2e via micromamba `shiny` env; e2e needs a live server on :8000. Windows: never multi-line `python -c`. Commit trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

### Task 1: Blind mode toggle + gate + i18n + e2e

**Files:**
- Modify: `sespy/translations/core.json` (2 keys × 9 languages)
- Modify: `sespy/modules/rate_connections.py` (sidebar checkbox ~line 31; `current_ratings` render ~175-187)
- Test: `tests/test_i18n.py` (presence test); `tests/test_rate_connections_e2e.py` (two-rater blind block)

**Interfaces:**
- Produces: the `blind_mode` input + gated `current_ratings`; i18n keys `rate.blind_mode`, `rate.blind_hidden`.

- [ ] **Step 1: Write the failing i18n presence test**

In `tests/test_i18n.py` add (the module-scoped `translations` fixture is the param):

```python
def test_blind_rating_keys_present(translations):
    assert "rate.blind_mode" in translations
    assert "rate.blind_hidden" in translations
```

- [ ] **Step 2: Run it to verify it fails**

Run: `micromamba run -n shiny python -m pytest tests/test_i18n.py::test_blind_rating_keys_present -v`
Expected: FAIL — keys not present.

- [ ] **Step 3: Add the i18n keys (all 9 languages)**

In `sespy/translations/core.json`, inside the `"translation"` object (next to the other `rate.*` keys), add (valid JSON — mind commas; UTF-8, keep accents/Greek exactly):

```json
    "rate.blind_mode": {
      "en": "Blind mode (hide others' ratings)",
      "es": "Modo ciego (ocultar valoraciones ajenas)",
      "fr": "Mode aveugle (masquer les évaluations des autres)",
      "de": "Blindmodus (Bewertungen anderer ausblenden)",
      "lt": "Aklasis režimas (slėpti kitų vertinimus)",
      "pt": "Modo cego (ocultar avaliações de outros)",
      "it": "Modalità cieca (nascondi le valutazioni altrui)",
      "no": "Blindmodus (skjul andres vurderinger)",
      "el": "Τυφλή λειτουργία (απόκρυψη αξιολογήσεων άλλων)"
    },
    "rate.blind_hidden": {
      "en": "Hidden until you submit your own rating (blind mode).",
      "es": "Oculto hasta que envíes tu propia valoración (modo ciego).",
      "fr": "Masqué jusqu'à ce que vous soumettiez votre évaluation (mode aveugle).",
      "de": "Ausgeblendet, bis Sie Ihre eigene Bewertung abgeben (Blindmodus).",
      "lt": "Paslėpta, kol pateiksite savo vertinimą (aklasis režimas).",
      "pt": "Oculto até enviares a tua avaliação (modo cego).",
      "it": "Nascosto finché non invii la tua valutazione (modalità cieca).",
      "no": "Skjult til du sender inn din egen vurdering (blindmodus).",
      "el": "Κρυμμένο μέχρι να υποβάλετε τη δική σας αξιολόγηση (τυφλή λειτουργία)."
    }
```

- [ ] **Step 4: Smoke-check JSON, then run i18n tests**

`micromamba run -n shiny python -c "import json; json.load(open('sespy/translations/core.json', encoding='utf-8')); print('json ok')"` → `json ok`.
Then `micromamba run -n shiny python -m pytest tests/test_i18n.py -v` → PASS (presence + the per-language completeness test).

- [ ] **Step 5: Add the sidebar toggle**

In `sespy/modules/rate_connections.py`, in `rate_connections_ui`, immediately after the `contested_only` checkbox line:
```python
                ui.input_checkbox("contested_only", t("rate.contested_only"), value=False),
```
add:
```python
                ui.input_checkbox("blind_mode", t("rate.blind_mode"), value=False),
```

- [ ] **Step 6: Gate the `current_ratings` render**

Replace the body of `current_ratings` (currently):
```python
    @output
    @render.ui
    def current_ratings():
        event_bus.isa_change.get()
        _, conn = _selected()
        if conn is None or not conn.ratings:
            return ui.tags.p("—", class_="text-muted")
        name_by_id = {s.id: s.name for s in project_data.get().stakeholders}
        return ui.tags.ul(*[
            ui.tags.li(f"{name_by_id.get(r.rater_id, r.rater_id)}: "
                       f"{r.polarity}/{r.strength}/{r.confidence}/{r.delay}")
            for r in conn.ratings
        ])
```
with:
```python
    @output
    @render.ui
    def current_ratings():
        event_bus.isa_change.get()
        _, conn = _selected()
        if conn is None or not conn.ratings:
            return ui.tags.p("—", class_="text-muted")
        try:
            rater = input.rater()
        except Exception:
            rater = None
        rater_has_rated = bool(rater) and any(r.rater_id == rater for r in conn.ratings)
        if input.blind_mode() and not rater_has_rated:
            return ui.tags.p(t("rate.blind_hidden"), class_="text-muted")
        name_by_id = {s.id: s.name for s in project_data.get().stakeholders}
        return ui.tags.ul(*[
            ui.tags.li(f"{name_by_id.get(r.rater_id, r.rater_id)}: "
                       f"{r.polarity}/{r.strength}/{r.confidence}/{r.delay}")
            for r in conn.ratings
        ])
```

- [ ] **Step 7: Verify the app builds**

`micromamba run -n shiny python -c "import app; print('ok')"` → `ok`.

- [ ] **Step 8: Extend the e2e with the two-rater blind block**

In `tests/test_rate_connections_e2e.py`, the existing flow rates with rater 1, switches to rater 2, re-clicks the row (the `await page.click(RATE_ROW)` / `wait_for_selector("#rate-save_rating")` at ~lines 94-95) and then rates "-" + saves. Insert the **hidden** check right AFTER that re-click/editor-render (before the `await page.click("#rate-ed_polarity input[value='-']")` line ~99):

```python
        # Blind mode: rater 2 has NOT rated this connection yet, but rater 1 has.
        # Enabling blind hides the peer value from rater 2 until they submit.
        await page.check("#rate-blind_mode")
        await page.wait_for_timeout(500)
        blind_txt = (await page.text_content("#rate-current_ratings")) or ""
        assert "blind mode" in blind_txt.lower(), f"blind placeholder not shown: {blind_txt!r}"
        assert "/" not in blind_txt, f"peer rating value leaked under blind mode: {blind_txt!r}"
```

Then insert the **reveal** check right AFTER the existing `assert saved2, ...` line (~line 114, where rater 2's save is confirmed with #ratings==2):

```python
        # Reveal: rater 2 has now submitted, so blind mode reveals the full peer list.
        reveal = False
        rtxt = ""
        for _ in range(20):
            await page.wait_for_timeout(500)
            rtxt = (await page.text_content("#rate-current_ratings")) or ""
            if "blind mode" not in rtxt.lower() and "/" in rtxt:
                reveal = True
                break
        assert reveal, f"blind mode did not reveal after submit: {rtxt!r}"
```

(Both assertions are name-independent: the blind placeholder has no `/`, the revealed peer-list items contain `polarity/strength/confidence/delay`.)

- [ ] **Step 9: Run the e2e**

Free port 8000 (kill the listener), start the app in the background
(`PYTHONPATH="$PWD" micromamba run -n shiny shiny run --port 8000 app.py`), wait for
`http://127.0.0.1:8000/` → 200, then:
`micromamba run -n shiny python tests/test_rate_connections_e2e.py`
Expected: PASS — prints "rate connections contested view: OK" AND the new blind hidden/reveal asserts pass. Stop the server after.

- [ ] **Step 10: Commit**

```bash
git add sespy/translations/core.json sespy/modules/rate_connections.py tests/test_i18n.py tests/test_rate_connections_e2e.py
git commit -m "feat(rate): anchoring-independent blind rating mode (#6)"
```

---

## Definition of Done

- [ ] Full unit + i18n suite green:
  `micromamba run -n shiny python -m pytest tests/ --ignore-glob='*e2e*' --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py -q`
  (incl. the new presence test + per-language completeness test).
- [ ] `import app` builds cleanly.
- [ ] Full e2e: `micromamba run -n shiny python tests/run_e2e.py` → green except the pre-existing WeasyPrint `test_report_e2e.py`. `test_rate_connections_e2e.py` must pass (contested view + blind hidden/reveal).
- [ ] Manual sanity (optional): with two stakeholders, enable blind mode as a rater who hasn't rated the selected connection → peer ratings hidden; save your rating → they reveal.
