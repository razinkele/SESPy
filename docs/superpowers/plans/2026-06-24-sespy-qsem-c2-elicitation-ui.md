# QSEM-C2 Elicitation UI (Rate Connections) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Rate Connections" module where a stakeholder records their own rating of a connection; each save upserts one rating per `(rater, connection)`, recomputes the consensus, and writes through `project_data` so every analysis updates.

**Architecture:** Two pure helpers in `network.py` (`upsert_rating`/`remove_rating`, built on the shipped `recompute_consensus`) do the data mutation; a new thin Shiny module `rate_connections.py` provides the UI (rater picker from the PIMS Stakeholders register, connections table, pre-filled rating editor, save/remove) and persists via the established `current.replace(isa_data=…)` + `emit_isa_change`/`emit_cld_update` pattern; `app.py` wires the nav item.

**Tech Stack:** Python 3.11, Shiny for Python, pandas (DataGrid), pytest, Playwright.

## Global Constraints

- **Implementation order:** `network.py` helpers + tests (Task 1) MUST be done before the module (Task 3) — the module imports them.
- Persistence is via `current = project_data.get(); project_data.set(current.replace(isa_data=IsaData(elements=…, connections=…))); event_bus.emit_isa_change(); event_bus.emit_cld_update()` (the exact `isa_data_entry._replace` pattern).
- `recompute_consensus` stays the sole writer of the consensus scalars; `upsert_rating`/`remove_rating` call it and never set scalars directly.
- Selection persistence: cache the selected connection index in a `reactive.Value` (`sel_idx`); a `@reactive.effect` sets it only when a row is selected (never overwrites with empty), so it survives the save-triggered table re-render. Reset to `None` on rater change.
- Bounds guard: treat `idx >= len(connections)` as "no selection" (empty-project stub row is selectable).
- `project_data` is a `reactive.Value[Project]` — always `.get()` before `.stakeholders`/`.isa_data`.
- All user-facing strings via `t()`; new keys ×9 languages (`en,es,fr,de,lt,pt,it,no,el`), enforced by `tests/test_i18n.py::test_loader_handles_all_supported_languages`.
- Run python/pytest via micromamba `shiny` env. Windows: never multi-line `python -c`. Commit trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

### Task 1: `network.upsert_rating` + `network.remove_rating`

**Files:**
- Modify: `sespy/network.py` (add after `connection_disagreement`, ~line 380)
- Test: `tests/test_network.py`

**Interfaces:**
- Consumes: `recompute_consensus` (shipped), `dataclasses.replace` (already imported), `Connection`/`Rating` from `sespy.data_structure`.
- Produces:
  - `upsert_rating(connection: Connection, rating: Rating) -> Connection`
  - `remove_rating(connection: Connection, rater_id: str) -> Connection`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_network.py` (import `Rating` if not already in the `from sespy.data_structure import …` line):

```python
def test_upsert_rating_adds_and_recomputes():
    from sespy.data_structure import Connection, Rating
    c = Connection(source="A", target="B")  # ratings=[]
    out = network.upsert_rating(c, Rating(rater_id="s1", strength="strong", confidence=5, polarity="+", delay="short"))
    assert len(out.ratings) == 1
    assert out.strength == "strong" and out.confidence == 5 and out.delay == "short"
    assert c.ratings == []  # input unmutated (pure)


def test_upsert_rating_replaces_same_rater():
    from sespy.data_structure import Connection, Rating
    c = network.upsert_rating(Connection(source="A", target="B"),
                              Rating(rater_id="s1", strength="weak", confidence=2, polarity="+"))
    out = network.upsert_rating(c, Rating(rater_id="s1", strength="strong", confidence=5, polarity="+"))
    assert len(out.ratings) == 1            # replaced, not duplicated
    assert out.ratings[0].strength == "strong"
    assert out.strength == "strong" and out.confidence == 5


def test_remove_rating_drops_and_recomputes():
    from sespy.data_structure import Connection, Rating
    c = Connection(source="A", target="B", ratings=[
        Rating(rater_id="s1", strength="weak", confidence=1, polarity="-"),
        Rating(rater_id="s2", strength="strong", confidence=5, polarity="+"),
    ])
    c = network.recompute_consensus(c)
    out = network.remove_rating(c, "s1")
    assert [r.rater_id for r in out.ratings] == ["s2"]
    assert out.strength == "strong" and out.polarity == "+"
    assert len(c.ratings) == 2  # input unmutated


def test_remove_last_rating_freezes_consensus():
    from sespy.data_structure import Connection, Rating
    c = network.upsert_rating(Connection(source="A", target="B"),
                              Rating(rater_id="s1", strength="strong", confidence=5, polarity="-", delay="long"))
    out = network.remove_rating(c, "s1")
    assert out.ratings == []
    # no-op recompute on empty ratings: scalars stay at last consensus
    assert (out.strength, out.confidence, out.polarity, out.delay) == ("strong", 5, "-", "long")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py -k "upsert_rating or remove_rating or remove_last" -v`
Expected: FAIL — `module 'sespy.network' has no attribute 'upsert_rating'`.

- [ ] **Step 3: Implement the helpers**

Add to `sespy/network.py` after `connection_disagreement` (`replace` is already imported):

```python
def upsert_rating(connection, rating):
    """Return a copy of `connection` with `rating` replacing any existing entry
    by the same rater_id (else appended), consensus recomputed. Pure."""
    kept = [r for r in connection.ratings if r.rater_id != rating.rater_id]
    return recompute_consensus(replace(connection, ratings=[*kept, rating]))


def remove_rating(connection, rater_id: str):
    """Return a copy of `connection` with `rater_id`'s rating dropped, consensus
    recomputed (no-op when no ratings remain). Pure."""
    kept = [r for r in connection.ratings if r.rater_id != rater_id]
    return recompute_consensus(replace(connection, ratings=kept))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `micromamba run -n shiny python -m pytest tests/test_network.py -k "upsert_rating or remove_rating or remove_last" -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add sespy/network.py tests/test_network.py
git commit -m "feat(network): upsert_rating + remove_rating (rating mutation helpers)"
```

---

### Task 2: i18n keys (Rate Connections + strength labels)

**Files:**
- Modify: `sespy/translations/core.json`
- Test: `tests/test_i18n.py`

**Interfaces:**
- Produces translation keys consumed by Task 3: `nav.rate`, `rate.title`, `rate.rating_as`, `rate.no_stakeholders`, `rate.your_rating`, `rate.polarity`, `rate.strength`, `rate.confidence`, `rate.delay`, `rate.save`, `rate.remove`, `rate.current_ratings`, `rate.select_connection`, `rate.saved`, `rate.removed`, `rate.nothing_to_remove`, and `strength.weak`, `strength.medium`, `strength.strong`.

(Connection-table column headers stay raw English, matching the existing `isa_data_entry`/`loops` tables — no i18n keys for them.)

- [ ] **Step 1: Add the keys**

Insert these 19 entries into the `"translation"` object in `sespy/translations/core.json` (valid JSON, non-ASCII kept as-is, UTF-8):

```json
"nav.rate": {"en": "Rate Connections", "es": "Valorar conexiones", "fr": "Évaluer les liens", "de": "Verbindungen bewerten", "lt": "Vertinti ryšius", "pt": "Avaliar conexões", "it": "Valuta connessioni", "no": "Vurder koblinger", "el": "Αξιολόγηση συνδέσεων"},
"rate.title": {"en": "Rate Connections", "es": "Valorar conexiones", "fr": "Évaluer les liens", "de": "Verbindungen bewerten", "lt": "Vertinti ryšius", "pt": "Avaliar conexões", "it": "Valuta connessioni", "no": "Vurder koblinger", "el": "Αξιολόγηση συνδέσεων"},
"rate.rating_as": {"en": "Rating as", "es": "Valorando como", "fr": "Évaluer en tant que", "de": "Bewerten als", "lt": "Vertina", "pt": "Avaliando como", "it": "Valuti come", "no": "Vurderer som", "el": "Αξιολόγηση ως"},
"rate.no_stakeholders": {"en": "Add stakeholders first.", "es": "Añade partes interesadas primero.", "fr": "Ajoutez d'abord des parties prenantes.", "de": "Zuerst Akteure hinzufügen.", "lt": "Pirma pridėkite suinteresuotąsias šalis.", "pt": "Adicione partes interessadas primeiro.", "it": "Aggiungi prima i portatori d'interesse.", "no": "Legg til interessenter først.", "el": "Προσθέστε πρώτα ενδιαφερόμενους."},
"rate.your_rating": {"en": "Your rating", "es": "Tu valoración", "fr": "Votre évaluation", "de": "Ihre Bewertung", "lt": "Jūsų vertinimas", "pt": "A sua avaliação", "it": "La tua valutazione", "no": "Din vurdering", "el": "Η αξιολόγησή σας"},
"rate.polarity": {"en": "Polarity", "es": "Polaridad", "fr": "Polarité", "de": "Polarität", "lt": "Poliškumas", "pt": "Polaridade", "it": "Polarità", "no": "Polaritet", "el": "Πολικότητα"},
"rate.strength": {"en": "Strength", "es": "Fuerza", "fr": "Force", "de": "Stärke", "lt": "Stiprumas", "pt": "Força", "it": "Forza", "no": "Styrke", "el": "Ισχύς"},
"rate.confidence": {"en": "Confidence", "es": "Confianza", "fr": "Confiance", "de": "Konfidenz", "lt": "Pasitikėjimas", "pt": "Confiança", "it": "Confidenza", "no": "Tillit", "el": "Βεβαιότητα"},
"rate.delay": {"en": "Delay", "es": "Retraso", "fr": "Délai", "de": "Verzögerung", "lt": "Vėlavimas", "pt": "Atraso", "it": "Ritardo", "no": "Forsinkelse", "el": "Καθυστέρηση"},
"rate.save": {"en": "Save my rating", "es": "Guardar mi valoración", "fr": "Enregistrer mon évaluation", "de": "Meine Bewertung speichern", "lt": "Išsaugoti mano vertinimą", "pt": "Guardar a minha avaliação", "it": "Salva la mia valutazione", "no": "Lagre min vurdering", "el": "Αποθήκευση αξιολόγησης"},
"rate.remove": {"en": "Remove mine", "es": "Eliminar la mía", "fr": "Supprimer la mienne", "de": "Meine entfernen", "lt": "Pašalinti mano", "pt": "Remover a minha", "it": "Rimuovi la mia", "no": "Fjern min", "el": "Αφαίρεση της δικής μου"},
"rate.current_ratings": {"en": "Current ratings", "es": "Valoraciones actuales", "fr": "Évaluations actuelles", "de": "Aktuelle Bewertungen", "lt": "Dabartiniai vertinimai", "pt": "Avaliações atuais", "it": "Valutazioni attuali", "no": "Gjeldende vurderinger", "el": "Τρέχουσες αξιολογήσεις"},
"rate.select_connection": {"en": "Select a connection to rate.", "es": "Selecciona una conexión para valorar.", "fr": "Sélectionnez un lien à évaluer.", "de": "Wählen Sie eine zu bewertende Verbindung.", "lt": "Pasirinkite vertinamą ryšį.", "pt": "Selecione uma conexão para avaliar.", "it": "Seleziona una connessione da valutare.", "no": "Velg en kobling å vurdere.", "el": "Επιλέξτε σύνδεση για αξιολόγηση."},
"rate.saved": {"en": "Rating saved.", "es": "Valoración guardada.", "fr": "Évaluation enregistrée.", "de": "Bewertung gespeichert.", "lt": "Vertinimas išsaugotas.", "pt": "Avaliação guardada.", "it": "Valutazione salvata.", "no": "Vurdering lagret.", "el": "Η αξιολόγηση αποθηκεύτηκε."},
"rate.removed": {"en": "Rating removed.", "es": "Valoración eliminada.", "fr": "Évaluation supprimée.", "de": "Bewertung entfernt.", "lt": "Vertinimas pašalintas.", "pt": "Avaliação removida.", "it": "Valutazione rimossa.", "no": "Vurdering fjernet.", "el": "Η αξιολόγηση αφαιρέθηκε."},
"rate.nothing_to_remove": {"en": "You have no rating on this connection.", "es": "No tienes valoración en esta conexión.", "fr": "Vous n'avez pas d'évaluation sur ce lien.", "de": "Sie haben keine Bewertung für diese Verbindung.", "lt": "Neturite šio ryšio vertinimo.", "pt": "Não tem avaliação nesta conexão.", "it": "Non hai una valutazione su questa connessione.", "no": "Du har ingen vurdering på denne koblingen.", "el": "Δεν έχετε αξιολόγηση σε αυτή τη σύνδεση."},
"strength.weak": {"en": "Weak", "es": "Débil", "fr": "Faible", "de": "Schwach", "lt": "Silpnas", "pt": "Fraco", "it": "Debole", "no": "Svak", "el": "Ασθενής"},
"strength.medium": {"en": "Medium", "es": "Medio", "fr": "Moyen", "de": "Mittel", "lt": "Vidutinis", "pt": "Médio", "it": "Medio", "no": "Middels", "el": "Μέτριος"},
"strength.strong": {"en": "Strong", "es": "Fuerte", "fr": "Fort", "de": "Stark", "lt": "Stiprus", "pt": "Forte", "it": "Forte", "no": "Sterk", "el": "Ισχυρός"}
```

- [ ] **Step 2: Verify JSON + key coverage**

Run: `micromamba run -n shiny python -m pytest tests/test_i18n.py -v`
Expected: PASS (esp. `test_loader_handles_all_supported_languages` — all 9 languages present for every new key).

- [ ] **Step 3: Commit**

```bash
git add sespy/translations/core.json
git commit -m "i18n(rate): Rate Connections + strength labels (19 keys, 9 languages)"
```

---

### Task 3: `rate_connections` module + `app.py` wiring + e2e

**Files:**
- Create: `sespy/modules/rate_connections.py`
- Modify: `app.py` (NAV, NAV_TO_STEP, PANELS, import, server call)
- Test: `tests/test_rate_connections_e2e.py`

**Interfaces:**
- Consumes: `network.upsert_rating`/`remove_rating` (Task 1), the i18n keys (Task 2), `Rating`/`IsaData` from `data_structure`, `CONNECTION_POLARITY_LABELS`/`DELAY_LEVELS` from `constants`, `Translator`/`t` from `i18n`, `EventBus`.
- Produces: `rate_connections_ui()` and `rate_connections_server(input, output, session, *, project_data, event_bus, translator=None)`; module namespace `rate` (selectors `#rate-…`).

- [ ] **Step 1: Create the module**

Create `sespy/modules/rate_connections.py`:

```python
"""Rate Connections — QSEM-C2 multi-rater elicitation UI.

Stakeholders (raters) record their own rating (polarity/strength/confidence/
delay) of an existing connection. Each save upserts one Rating per
(rater, connection) and recomputes the consensus via network.upsert_rating,
then writes through project_data so every analysis sees the new consensus.
Reuses the PIMS Stakeholders register as the rater list. No structural
editing here (that lives in Edit Data).
"""
from __future__ import annotations

from shiny import Inputs, Outputs, Session, module, reactive, render, ui

from ..constants import CONNECTION_POLARITY_LABELS, DELAY_LEVELS
from ..data_structure import IsaData, Rating
from ..event_bus import EventBus
from ..i18n import Translator, t
from .. import network

_STRENGTHS = ("weak", "medium", "strong")


@module.ui
def rate_connections_ui() -> ui.Tag:
    return ui.card(
        ui.card_header(t("rate.title")),
        ui.layout_sidebar(
            ui.sidebar(ui.output_ui("rater_picker"), width=260),
            ui.div(
                ui.output_data_frame("connections_table"),
                ui.tags.hr(),
                ui.output_ui("rating_editor"),
                ui.tags.hr(),
                ui.h5(t("rate.current_ratings")),
                ui.output_ui("current_ratings"),
            ),
        ),
        class_="sespy-card sespy-card-canvas",
        full_screen=True,
    )


@module.server
def rate_connections_server(
    input: Inputs,
    output: Outputs,
    session: Session,
    *,
    project_data,
    event_bus: EventBus,
    translator: Translator | None = None,
) -> None:
    sel_idx: reactive.Value = reactive.value(None)

    @output
    @render.ui
    def rater_picker():
        shs = project_data.get().stakeholders
        if not shs:
            return ui.tags.p(t("rate.no_stakeholders"), class_="text-muted")
        return ui.input_select("rater", t("rate.rating_as"), {s.id: s.name for s in shs})

    @output
    @render.data_frame
    def connections_table():
        import pandas as pd
        event_bus.isa_change.get()
        isa = project_data.get().isa_data
        try:
            rater = input.rater()
        except Exception:
            rater = None
        by_id = {el.id: el.label for el in isa.elements}
        cols = ["source", "target", "polarity", "strength", "confidence", "delay", "#ratings", "mine"]
        rows = [{
            "source": f"{c.source} · {by_id.get(c.source, '?')}",
            "target": f"{c.target} · {by_id.get(c.target, '?')}",
            "polarity": c.polarity,
            "strength": c.strength,
            "confidence": c.confidence,
            "delay": c.delay,
            "#ratings": len(c.ratings),
            "mine": "✓" if rater and any(r.rater_id == rater for r in c.ratings) else "—",
        } for c in isa.connections]
        return render.DataGrid(
            pd.DataFrame(rows or [{k: "" for k in cols}]),
            selection_mode="row", height="260px",
        )

    @reactive.effect
    def _track_selection():
        sel = connections_table.cell_selection()
        if sel and sel.get("rows"):
            sel_idx.set(sel["rows"][0])

    @reactive.effect
    @reactive.event(input.rater)
    def _reset_selection_on_rater():
        sel_idx.set(None)

    def _selected():
        """(index, connection) for the cached selection, or (None, None).
        Bounds-guards the empty-project stub row."""
        idx = sel_idx.get()
        if idx is None:
            return None, None
        conns = project_data.get().isa_data.connections
        if idx >= len(conns):
            return None, None
        return idx, conns[idx]

    @output
    @render.ui
    def rating_editor():
        event_bus.isa_change.get()
        try:
            rater = input.rater()
        except Exception:
            rater = None
        _, conn = _selected()
        if not rater or conn is None:
            return ui.tags.p(t("rate.select_connection"), class_="text-muted")
        ex = next((r for r in conn.ratings if r.rater_id == rater), None)
        return ui.div(
            ui.h5(t("rate.your_rating")),
            ui.input_radio_buttons("ed_polarity", t("rate.polarity"),
                                   CONNECTION_POLARITY_LABELS,
                                   selected=ex.polarity if ex else "+", inline=True),
            ui.input_select("ed_strength", t("rate.strength"),
                            {s: t(f"strength.{s}") for s in _STRENGTHS},
                            selected=ex.strength if ex else "medium"),
            ui.input_slider("ed_confidence", t("rate.confidence"), min=1, max=5,
                            value=ex.confidence if ex else 3, step=1),
            ui.input_select("ed_delay", t("rate.delay"),
                            {lvl: t(f"delay.{lvl}") for lvl in DELAY_LEVELS},
                            selected=ex.delay if ex else "immediate"),
            ui.input_action_button("save_rating", t("rate.save"), class_="btn btn-primary"),
            ui.input_action_button("remove_rating", t("rate.remove"),
                                   class_="btn btn-outline-danger", style="margin-left:8px;"),
        )

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

    def _persist(new_conns):
        current = project_data.get()
        project_data.set(current.replace(isa_data=IsaData(
            elements=current.isa_data.elements, connections=new_conns)))
        event_bus.emit_isa_change()
        event_bus.emit_cld_update()

    def _rater_or_warn():
        try:
            rater = input.rater()
        except Exception:
            rater = None
        if not rater:
            ui.notification_show(t("rate.no_stakeholders"), type="warning", duration=3)
        return rater

    @reactive.effect
    @reactive.event(input.save_rating)
    def _save():
        rater = _rater_or_warn()
        if not rater:
            return
        idx, conn = _selected()
        if conn is None:
            ui.notification_show(t("rate.select_connection"), type="warning", duration=3)
            return
        rating = Rating(rater_id=rater,
                        strength=input.ed_strength() or "medium",
                        confidence=int(input.ed_confidence() or 3),
                        polarity=input.ed_polarity() or "+",
                        delay=input.ed_delay() or "immediate")
        conns = list(project_data.get().isa_data.connections)
        conns[idx] = network.upsert_rating(conn, rating)
        _persist(conns)
        ui.notification_show(t("rate.saved"), type="message", duration=2)

    @reactive.effect
    @reactive.event(input.remove_rating)
    def _remove():
        rater = _rater_or_warn()
        if not rater:
            return
        idx, conn = _selected()
        if conn is None:
            ui.notification_show(t("rate.select_connection"), type="warning", duration=3)
            return
        if not any(r.rater_id == rater for r in conn.ratings):
            ui.notification_show(t("rate.nothing_to_remove"), type="warning", duration=3)
            return
        conns = list(project_data.get().isa_data.connections)
        conns[idx] = network.remove_rating(conn, rater)
        _persist(conns)
        ui.notification_show(t("rate.removed"), type="message", duration=2)
```

- [ ] **Step 2: Wire it into `app.py`**

Four edits in `app.py`:

(a) Import (near the other module imports, e.g. after the `isa_data_entry` import line):
```python
from sespy.modules.rate_connections import rate_connections_server, rate_connections_ui
```

(b) Add to the `NAV` list immediately after the `entry` item:
```python
    NavItem(id="rate",     icon="user-pen",        label="Rate Connections",  label_key="nav.rate"),
```

(c) Add to `NAV_TO_STEP` (alongside `"entry": "create"`):
```python
    "rate": "create",
```

(d) Add to the `PANELS` tuple immediately after the `Edit Data` panel:
```python
    ui.nav_panel("Rate Connections", rate_connections_ui("rate"), value="rate"),
```

(e) Add the server call immediately after `isa_data_entry_server(...)`:
```python
    rate_connections_server(
        "rate",
        project_data=project_data,
        event_bus=event_bus,
        translator=T,
    )
```

- [ ] **Step 3: Smoke-test imports + app construction**

Run: `micromamba run -n shiny python -c "import app; print('ok')"`
Expected: prints `ok` (module imports and the app object builds with the new panel/nav wired).

- [ ] **Step 4: Write the e2e**

Create `tests/test_rate_connections_e2e.py`. Mirror the launch boilerplate and the add-stakeholder steps from `tests/test_stakeholders_e2e.py` (read it for the exact stakeholder add-form selectors and submit button). The flow:

```python
"""E2E for Rate Connections (QSEM-C2): add a stakeholder, rate a connection,
assert the connection row reflects the new rating (#ratings -> 1, mine -> check)."""
import asyncio
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 900})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        await page.wait_for_timeout(1500)

        # 1. Add one stakeholder (pattern from tests/test_stakeholders_e2e.py:95-97).
        await page.click("#sespy_nav_stakeholders")
        await page.wait_for_selector("#stakeholders-sh_name", timeout=30000)
        await page.fill("#stakeholders-sh_name", "Port Authority")
        await page.click("#stakeholders-save_stakeholder")
        await page.wait_for_timeout(1000)

        # 2. Go to Rate Connections.
        await page.click("#sespy_nav_rate")
        await page.wait_for_selector("#rate-connections_table table tbody tr", timeout=30000)
        await page.wait_for_selector("#rate-rater", timeout=30000)  # picker present (register non-empty)

        # 3. Select the first connection row.
        await page.click("#rate-connections_table table tbody tr:first-child")
        await page.wait_for_selector("#rate-save_rating", timeout=30000)  # editor rendered

        # 4. Set a rating and save.
        await page.evaluate(
            "() => { const s=document.getElementById('rate-ed_strength');"
            " if(s){ s.value='strong'; s.dispatchEvent(new Event('change',{bubbles:true})); } }"
        )
        await page.click("#rate-save_rating")

        # 5. Assert the first row's #ratings cell became 1 (poll the re-render).
        ok = False
        for _ in range(20):
            await page.wait_for_timeout(500)
            cells = await page.evaluate(
                "() => Array.from(document.querySelectorAll("
                "'#rate-connections_table table tbody tr:first-child td')).map(td => td.textContent.trim())"
            )
            if cells and "1" in cells:
                ok = True
                break
        assert ok, f"connection row did not reflect the saved rating: {cells}"
        print("rate connections save: OK")
        await browser.close()


asyncio.run(main())
```

The stakeholder-add step uses the proven `#stakeholders-sh_name` + `#stakeholders-save_stakeholder` selectors (from `tests/test_stakeholders_e2e.py`) so the rater register is non-empty and `#rate-rater` renders. If the row-selection click (`:first-child`) does not register the selection, fall back to the verified `#rate-connections_table tbody tr td:first-child` cell-click idiom that `test_stakeholders_e2e.py` relies on.

- [ ] **Step 5: Run the e2e**

Start the app and run the script directly (the `run_e2e.py` runner has no single-test arg; start a server, then run the file — see how `tests/test_stakeholders_e2e.py` is run):
```
# one terminal: micromamba run -n shiny shiny run --port 8000 app.py
# then:        micromamba run -n shiny python tests/test_rate_connections_e2e.py
```
Expected: prints `rate connections save: OK`. If the environment can't run the e2e for infra reasons (not a code defect), report DONE_WITH_CONCERNS with detail and still commit.

- [ ] **Step 6: Commit**

```bash
git add sespy/modules/rate_connections.py app.py tests/test_rate_connections_e2e.py
git commit -m "feat(rate): Rate Connections elicitation module + nav wiring + e2e"
```

---

## Definition of Done

- [ ] Full unit + i18n suite green:
  `micromamba run -n shiny python -m pytest tests/ --ignore-glob='*e2e*' --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py -q`
  Expected: prior baseline (362 passed, 1 skipped) + 4 new network tests, all passing.
- [ ] `import app` builds cleanly with the new nav page.
- [ ] Full e2e: `micromamba run -n shiny python tests/run_e2e.py` → green except the pre-existing WeasyPrint `test_report_e2e.py`; the new `test_rate_connections_e2e.py` passes; no regression in other modules (the new "Rate Connections (Monte Carlo)"-free label won't collide, but confirm `test_simulation_e2e.py` still passes).
- [ ] `recompute_consensus` remains the sole writer of consensus scalars (the module only calls `upsert_rating`/`remove_rating`).
