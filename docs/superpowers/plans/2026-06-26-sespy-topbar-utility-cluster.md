# Topbar Utility Cluster Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Feedback / About / Options / Help button cluster to the left of the topbar (each opens a modal), mimicking the BowTie app — SQLite feedback, About Overview+Changelog tabs, Options theme(2)+language+autosave.

**Architecture:** New `sespy/feedback_store.py` (SQLite, ported from BowTie) + new `sespy/modules/topbar_actions.py` (plain functions: a button group for `header_actions` + four `ui.modal_show` handlers). Two session `reactive.Value`s in `app.py` (`current_theme`, `autosave_enabled`) back the Options modal state and gate `project_io`'s autosave effect. A `data-theme` JS handler + `www/themes.css` provide the two themes.

**Tech Stack:** Shiny for Python, sqlite3 (stdlib), pytest/Playwright.

## Global Constraints

- `topbar_actions` is **plain functions** wired at root (NOT a Shiny module) — input ids are global: `tb_feedback/tb_about/tb_options/tb_help`, `fb_message/fb_rating/fb_category/fb_submit`, `theme_select`, `autosave_enabled/autosave_clear`. e2e selectors use `#tb_feedback` etc. (no module prefix).
- `header_actions=topbar_actions_ui(T)` replaces `language_switcher(T)` in `app.py`; the language switcher relocates into the Options modal.
- **Shared state:** `current_theme = reactive.value("light-marine")` and `autosave_enabled = reactive.value(True)` are created in `app.py`'s `server()` and passed to `topbar_actions_server` (modal reads them for initial input values, so reopening reflects the real state) and `autosave_enabled` also to `quick_actions_server` (its `_autosave_on_change` early-returns when disabled).
- **Theme JS** registers inside `$(document).on('shiny:connected', …)` (mirroring `dashboard.py`'s `bookmark_js` — `Shiny` is undefined at parse time). `www/themes.css` is injected AFTER `sespy-skin.css` in `dashboard.py`'s page CSS links.
- **feedback_store**: `_connect` does `path.parent.mkdir(parents=True, exist_ok=True)`; DB path = arg > `SESPY_FEEDBACK_DB` env > `sespy/logs/feedback.db`. Add `sespy/logs/` to `.gitignore`.
- **i18n**: ~26 new keys, EACH with all 9 languages (en es fr de lt pt it no el); `test_loader_handles_all_supported_languages` hard-fails on any missing. Named presence test per group.
- Run pytest/e2e via micromamba `shiny`; e2e needs a live server on :8000. Windows: never multi-line `python -c`. Commit trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

### Task 1: `sespy/feedback_store.py` — SQLite store (ported from BowTie)

**Files:**
- Create: `sespy/feedback_store.py`
- Modify: `.gitignore`
- Test: `tests/test_feedback_store.py`

**Interfaces:**
- Produces: `feedback_store.add(message, rating, category, *, db_path=None) -> int`; `list_entries(status=None, limit=500, *, db_path=None) -> list[dict]`; `get(entry_id, *, db_path=None) -> dict | None`; `db_path(db=None) -> Path`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_feedback_store.py`:
```python
from sespy import feedback_store


def test_add_and_get(tmp_path):
    db = tmp_path / "fb.db"
    fid = feedback_store.add("It froze on export", 2, "bug", db_path=db)
    assert isinstance(fid, int) and fid >= 1
    row = feedback_store.get(fid, db_path=db)
    assert row["message"] == "It froze on export"
    assert row["rating"] == 2
    assert row["category"] == "bug"
    assert row["status"] == "open"
    assert row["created_at"]  # ISO timestamp present


def test_list_entries_newest_first(tmp_path):
    db = tmp_path / "fb.db"
    feedback_store.add("first", 3, "general", db_path=db)
    feedback_store.add("second", 5, "suggestion", db_path=db)
    rows = feedback_store.list_entries(db_path=db)
    assert [r["message"] for r in rows] == ["second", "first"]


def test_db_path_honors_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SESPY_FEEDBACK_DB", str(tmp_path / "envfb.db"))
    assert feedback_store.db_path() == tmp_path / "envfb.db"


def test_connect_creates_missing_dir(tmp_path):
    nested = tmp_path / "logs" / "feedback.db"   # parent does not exist yet
    fid = feedback_store.add("x", 1, "bug", db_path=nested)
    assert nested.exists() and fid >= 1
```

- [ ] **Step 2: Run to verify failure**

Run: `micromamba run -n shiny python -m pytest tests/test_feedback_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sespy.feedback_store'`.

- [ ] **Step 3: Implement `sespy/feedback_store.py`**

```python
"""SQLite feedback store — pure data layer (no Shiny). Ported from the BowTie app."""
import logging
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# sespy/logs/feedback.db (package-internal; logs/ is gitignored).
_DEFAULT_DB = Path(__file__).resolve().parent / "logs" / "feedback.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    category TEXT,
    message TEXT,
    rating INTEGER,
    status TEXT NOT NULL DEFAULT 'open',
    resolved_at TEXT,
    resolved_note TEXT,
    commit_sha TEXT
)
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db_path(db_path=None) -> Path:
    """Resolution precedence: explicit arg > SESPY_FEEDBACK_DB env > default."""
    if db_path is not None:
        return Path(db_path)
    env = os.environ.get("SESPY_FEEDBACK_DB")
    return Path(env) if env else _DEFAULT_DB


def db_path(db=None) -> Path:
    """Public wrapper — stable API for callers."""
    return _db_path(db)


def _connect(db_path=None) -> sqlite3.Connection:
    """Short-lived connection; ensures the dir + schema (idempotent). WAL + 5s
    timeout so concurrent Shiny sessions don't surface 'database is locked'."""
    path = _db_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(_SCHEMA)
    return conn


def add(message, rating, category, *, db_path=None) -> int:
    with closing(_connect(db_path)) as conn, conn:
        cur = conn.execute(
            "INSERT INTO feedback (created_at, category, message, rating, status) "
            "VALUES (?, ?, ?, ?, 'open')",
            (_now_iso(), category, message, rating),
        )
        return int(cur.lastrowid)


def list_entries(status=None, limit=500, *, db_path=None) -> list[dict]:
    with closing(_connect(db_path)) as conn:
        if status is None:
            rows = conn.execute(
                "SELECT * FROM feedback ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM feedback WHERE status = ? ORDER BY id DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        return [dict(r) for r in rows]


def get(entry_id, *, db_path=None) -> dict | None:
    with closing(_connect(db_path)) as conn:
        row = conn.execute(
            "SELECT * FROM feedback WHERE id = ?", (entry_id,)
        ).fetchone()
        return dict(row) if row else None
```

- [ ] **Step 4: Add `sespy/logs/` to `.gitignore`**

Append to `.gitignore`:
```
# Feedback SQLite store (runtime state)
sespy/logs/
```

- [ ] **Step 5: Run tests + commit**

Run: `micromamba run -n shiny python -m pytest tests/test_feedback_store.py -v` → 4 pass.
```bash
git add sespy/feedback_store.py tests/test_feedback_store.py .gitignore
git commit -m "feat(feedback): SQLite feedback store ported from BowTie"
```

---

### Task 2: `topbar_actions.py` button group + Feedback modal + app.py wiring

**Files:**
- Create: `sespy/modules/topbar_actions.py`
- Modify: `app.py` (header_actions + shared reactives + server wiring), `sespy/translations/core.json`
- Test: `tests/test_i18n.py`; `tests/test_topbar_e2e.py` (new)

**Interfaces:**
- Consumes: `feedback_store.add` (Task 1).
- Produces: `topbar_actions_ui(t) -> Tag`; `topbar_actions_server(input, output, session, *, project_data, translator, current_theme, autosave_enabled)`. The four button ids `tb_feedback/tb_about/tb_options/tb_help`. Modal builders `_feedback_modal/_about_modal/_options_modal/_help_modal` (only `_feedback_modal` implemented here; `_about_modal`/`_options_modal`/`_help_modal` added in Tasks 3-5 and their `tb_*` handlers wired then).

- [ ] **Step 1: Write the failing i18n presence test**

In `tests/test_i18n.py` add:
```python
def test_topbar_and_feedback_keys_present(translations):
    for k in ("topbar.feedback", "topbar.about", "topbar.options", "topbar.help",
              "feedback.title", "feedback.message", "feedback.rating", "feedback.category",
              "feedback.submit", "feedback.sent", "feedback.empty",
              "feedback.cat_bug", "feedback.cat_suggestion", "feedback.cat_question",
              "feedback.cat_other"):
        assert k in translations, k
```
Run it → FAIL (keys absent).

- [ ] **Step 2: Add the i18n keys (topbar.* + feedback.*, all 9 languages)**

In `sespy/translations/core.json` add (UTF-8, mind commas):
```json
    "topbar.feedback": {"en":"Feedback","es":"Comentarios","fr":"Retour","de":"Feedback","lt":"Atsiliepimai","pt":"Comentários","it":"Feedback","no":"Tilbakemelding","el":"Σχόλια"},
    "topbar.about": {"en":"About","es":"Acerca de","fr":"À propos","de":"Über","lt":"Apie","pt":"Sobre","it":"Informazioni","no":"Om","el":"Σχετικά"},
    "topbar.options": {"en":"Options","es":"Opciones","fr":"Options","de":"Optionen","lt":"Parinktys","pt":"Opções","it":"Opzioni","no":"Innstillinger","el":"Επιλογές"},
    "topbar.help": {"en":"Help","es":"Ayuda","fr":"Aide","de":"Hilfe","lt":"Pagalba","pt":"Ajuda","it":"Aiuto","no":"Hjelp","el":"Βοήθεια"},
    "feedback.title": {"en":"Send feedback","es":"Enviar comentarios","fr":"Envoyer un retour","de":"Feedback senden","lt":"Siųsti atsiliepimą","pt":"Enviar comentários","it":"Invia feedback","no":"Send tilbakemelding","el":"Αποστολή σχολίων"},
    "feedback.message": {"en":"Your feedback","es":"Tus comentarios","fr":"Votre retour","de":"Ihr Feedback","lt":"Jūsų atsiliepimas","pt":"O seu comentário","it":"Il tuo feedback","no":"Din tilbakemelding","el":"Τα σχόλιά σας"},
    "feedback.rating": {"en":"Rating","es":"Valoración","fr":"Évaluation","de":"Bewertung","lt":"Įvertinimas","pt":"Avaliação","it":"Valutazione","no":"Vurdering","el":"Βαθμολογία"},
    "feedback.category": {"en":"Category","es":"Categoría","fr":"Catégorie","de":"Kategorie","lt":"Kategorija","pt":"Categoria","it":"Categoria","no":"Kategori","el":"Κατηγορία"},
    "feedback.submit": {"en":"Submit","es":"Enviar","fr":"Envoyer","de":"Absenden","lt":"Pateikti","pt":"Enviar","it":"Invia","no":"Send inn","el":"Υποβολή"},
    "feedback.sent": {"en":"Thanks — your feedback was recorded.","es":"Gracias — tu comentario fue registrado.","fr":"Merci — votre retour a été enregistré.","de":"Danke — Ihr Feedback wurde gespeichert.","lt":"Ačiū — jūsų atsiliepimas įrašytas.","pt":"Obrigado — o seu comentário foi registado.","it":"Grazie — il tuo feedback è stato registrato.","no":"Takk — tilbakemeldingen din er lagret.","el":"Ευχαριστούμε — τα σχόλιά σας καταγράφηκαν."},
    "feedback.empty": {"en":"Please enter a message.","es":"Introduce un mensaje.","fr":"Veuillez saisir un message.","de":"Bitte geben Sie eine Nachricht ein.","lt":"Įveskite žinutę.","pt":"Introduza uma mensagem.","it":"Inserisci un messaggio.","no":"Skriv inn en melding.","el":"Εισαγάγετε ένα μήνυμα."},
    "feedback.cat_bug": {"en":"Bug","es":"Error","fr":"Bogue","de":"Fehler","lt":"Klaida","pt":"Erro","it":"Bug","no":"Feil","el":"Σφάλμα"},
    "feedback.cat_suggestion": {"en":"Suggestion","es":"Sugerencia","fr":"Suggestion","de":"Vorschlag","lt":"Pasiūlymas","pt":"Sugestão","it":"Suggerimento","no":"Forslag","el":"Πρόταση"},
    "feedback.cat_question": {"en":"Question","es":"Pregunta","fr":"Question","de":"Frage","lt":"Klausimas","pt":"Pergunta","it":"Domanda","no":"Spørsmål","el":"Ερώτηση"},
    "feedback.cat_other": {"en":"Other","es":"Otro","fr":"Autre","de":"Sonstiges","lt":"Kita","pt":"Outro","it":"Altro","no":"Annet","el":"Άλλο"}
```
Smoke-check JSON: `micromamba run -n shiny python -c "import json; json.load(open('sespy/translations/core.json', encoding='utf-8')); print('json ok')"`; then `micromamba run -n shiny python -m pytest tests/test_i18n.py -v` → pass.

- [ ] **Step 3: Create `sespy/modules/topbar_actions.py`**

```python
"""Topbar utility cluster — Feedback / About / Options / Help buttons that open
modals. Plain functions wired at root (NOT a Shiny module), so input ids are
global. Mimics the BowTie app's feedback (SQLite) + About/Options/Help."""
from __future__ import annotations

from shiny import reactive, ui

from ..i18n import Translator
from .. import feedback_store

_CATEGORY_KEYS = ("bug", "suggestion", "question", "other")


def _t(translator: Translator | None, key: str, fallback: str) -> str:
    return translator.t(key) if translator else fallback


def topbar_actions_ui(translator: Translator | None = None) -> ui.Tag:
    """The left-of-topbar button group (Feedback / About / Options / Help)."""
    def btn(bid: str, icon: str, key: str, default: str) -> ui.Tag:
        return ui.input_action_button(
            bid, ui.tags.span(ui.tags.i(class_=f"fa fa-{icon}"), " ",
                              _t(translator, key, default)),
            class_="btn btn-sm sespy-topbar-btn",
        )
    return ui.div(
        btn("tb_feedback", "comment", "topbar.feedback", "Feedback"),
        btn("tb_about", "circle-info", "topbar.about", "About"),
        btn("tb_options", "gear", "topbar.options", "Options"),
        btn("tb_help", "circle-question", "topbar.help", "Help"),
        class_="sespy-topbar-actions",
    )


def _feedback_modal(translator: Translator | None) -> ui.Tag:
    cats = {c: _t(translator, f"feedback.cat_{c}", c.title()) for c in _CATEGORY_KEYS}
    return ui.modal(
        ui.input_text_area("fb_message", _t(translator, "feedback.message", "Your feedback"),
                           rows=4, width="100%"),
        ui.input_slider("fb_rating", _t(translator, "feedback.rating", "Rating"),
                        min=1, max=5, value=3, step=1),
        ui.input_select("fb_category", _t(translator, "feedback.category", "Category"),
                        choices=cats),
        title=_t(translator, "feedback.title", "Send feedback"),
        footer=ui.TagList(
            ui.input_action_button("fb_submit", _t(translator, "feedback.submit", "Submit"),
                                   class_="btn-primary"),
            ui.modal_button("Close"),
        ),
        easy_close=True,
    )


def topbar_actions_server(input, output, session, *, project_data, translator=None,
                          current_theme=None, autosave_enabled=None) -> None:
    """Wires the four topbar buttons to their modals. current_theme /
    autosave_enabled are the shared reactive.Values (used by the Options modal)."""

    @reactive.effect
    @reactive.event(input.tb_feedback)
    def _open_feedback():
        ui.modal_show(_feedback_modal(translator))

    @reactive.effect
    @reactive.event(input.fb_submit)
    def _submit_feedback():
        msg = (input.fb_message() or "").strip()
        if not msg:
            ui.notification_show(_t(translator, "feedback.empty", "Please enter a message."),
                                 type="warning", duration=3)
            return
        try:
            feedback_store.add(msg, int(input.fb_rating() or 3), input.fb_category() or "other")
        except Exception:
            ui.notification_show("Could not record feedback.", type="error", duration=4)
            return
        ui.modal_remove()
        ui.notification_show(_t(translator, "feedback.sent",
                                "Thanks — your feedback was recorded."),
                             type="message", duration=4)
```

- [ ] **Step 4: Wire into `app.py`**

a) Imports: add `from sespy.modules.topbar_actions import topbar_actions_ui, topbar_actions_server`.

b) In the shell construction, change `header_actions=language_switcher(T),` to
`header_actions=topbar_actions_ui(T),`.

c) In `server()`, after `event_bus = create_event_bus()`, add the shared reactives:
```python
    current_theme = reactive.value("light-marine")
    autosave_enabled = reactive.value(True)
```
d) Pass `autosave_enabled=autosave_enabled` to the existing `quick_actions_server(...)` call.
e) Wire the new server (e.g. after `quick_actions_server(...)`):
```python
    topbar_actions_server(
        input, output, session,
        project_data=project_data,
        translator=T,
        current_theme=current_theme,
        autosave_enabled=autosave_enabled,
    )
```
(`language_switcher` import may now be unused in app.py — leave the import in `dashboard.py`; remove the app.py import only if it becomes unused.)

- [ ] **Step 5: Verify app builds + write the topbar e2e**

`micromamba run -n shiny python -c "import app; print('ok')"` → ok.
Create `tests/test_topbar_e2e.py` (standalone asyncio script following the repo e2e pattern; reuse a sibling e2e's header/launch boilerplate):
```python
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await (await b.new_context()).new_page()
        await pg.goto("http://127.0.0.1:8000", wait_until="networkidle")
        await pg.wait_for_timeout(1500)
        # all four topbar buttons present (root-scoped ids, no module prefix)
        for bid in ("tb_feedback", "tb_about", "tb_options", "tb_help"):
            await pg.wait_for_selector(f"#{bid}", timeout=30000)
        # Feedback opens + submit records + notification
        await pg.click("#tb_feedback")
        await pg.wait_for_selector(".modal #fb_message", timeout=10000)
        await pg.fill("#fb_message", "e2e feedback check")
        await pg.click("#fb_submit")
        await pg.wait_for_selector(".shiny-notification", timeout=10000)
        print("topbar feedback: OK")
        await b.close()

asyncio.run(main())
```
Run it against a live server (free port 8000; `PYTHONPATH="$PWD" micromamba run -n shiny shiny run --port 8000 app.py` in background; wait for 200; `micromamba run -n shiny python tests/test_topbar_e2e.py` → prints OK; stop server).

- [ ] **Step 6: Commit**
```bash
git add sespy/modules/topbar_actions.py app.py sespy/translations/core.json tests/test_i18n.py tests/test_topbar_e2e.py
git commit -m "feat(topbar): button cluster + Feedback modal (SQLite) + wiring (#topbar)"
```

---

### Task 3: About modal — Overview + Changelog tabs

**Files:**
- Create: `CHANGELOG.md` (repo root)
- Modify: `sespy/modules/topbar_actions.py` (`read_project_doc`, `_about_modal`, `tb_about` handler), `sespy/translations/core.json`
- Test: `tests/test_i18n.py`; `tests/test_topbar_e2e.py`

**Interfaces:**
- Consumes: the topbar server scaffold (Task 2).
- Produces: `_about_modal(translator)`; `read_project_doc(name)`.

- [ ] **Step 1: i18n presence test (about.*)**

In `tests/test_i18n.py`:
```python
def test_about_keys_present(translations):
    for k in ("about.overview", "about.changelog"):
        assert k in translations, k
```
Run → FAIL.

- [ ] **Step 2: Add about.* keys (9 langs)**
```json
    "about.overview": {"en":"Overview","es":"Resumen","fr":"Aperçu","de":"Übersicht","lt":"Apžvalga","pt":"Visão geral","it":"Panoramica","no":"Oversikt","el":"Επισκόπηση"},
    "about.changelog": {"en":"Changelog","es":"Registro de cambios","fr":"Journal des modifications","de":"Änderungsprotokoll","lt":"Pakeitimų žurnalas","pt":"Registo de alterações","it":"Registro modifiche","no":"Endringslogg","el":"Αρχείο αλλαγών"}
```
JSON smoke + `pytest tests/test_i18n.py` → pass.

- [ ] **Step 3: Create `CHANGELOG.md`** (keep-a-changelog style, from the release notes)
```markdown
# Changelog

All notable changes to SESPy.

## [1.2.0] — 2026-06-26
- Disagreement-aware loops: a loop whose classification hinges on a rater-contested edge shows ⚠.
- Contested-edge styling on the CLD graph (heavier width + ⚠ marker).
- Blind rating mode in Rate Connections (hide peers' ratings until you submit).
- Off-thread uncertainty Monte Carlo (no UI freeze; "computing…" indicator).

## [1.1.0] — 2026-06-25
- Direct `.qsem` import (QSEM web-app JSON node/link graph).

## [1.0.0] — 2026-06-25
- First stable release: 17-module create→edit→analyze→export workflow, QSEM multi-rater
  elicitation, D2D Monte-Carlo uncertainty, social-ecological fit, FCM import, factor
  quadrant, delay-aware loops, Meadows leverage typology.
```

- [ ] **Step 4: Add `read_project_doc` + `_about_modal` + the `tb_about` handler to `topbar_actions.py`**

Add imports at top: `from pathlib import Path`, and the version source
`from importlib.metadata import version as _pkg_version` (fallback to a literal if not installed).
```python
_REPO_ROOT = Path(__file__).resolve().parents[2]   # sespy/modules/ -> repo root


def read_project_doc(name: str) -> str:
    """Best-effort read of a repo-root doc; short fallback if missing."""
    try:
        return (_REPO_ROOT / name).read_text(encoding="utf-8")
    except OSError:
        return f"_{name} not available._"


def _app_version() -> str:
    try:
        return _pkg_version("sespy")
    except Exception:
        return "1.2.0"


def _about_modal(translator) -> ui.Tag:
    header = ui.markdown(
        f"### MarineSABRES SES Toolbox — Python\n\n"
        f"**Version {_app_version()}** — developed within the "
        f"[MarineSABRES](https://marinesabres.eu) Horizon Europe project. "
        f"[Source](https://github.com/razinkele/SESPy). MIT licensed."
    )
    return ui.modal(
        ui.navset_tab(
            ui.nav_panel(_t(translator, "about.overview", "Overview"),
                         ui.div(header, class_="mb-3"),
                         ui.markdown(read_project_doc("README.md"))),
            ui.nav_panel(_t(translator, "about.changelog", "Changelog"),
                         ui.markdown(read_project_doc("CHANGELOG.md"))),
        ),
        title="About",
        footer=ui.modal_button("Close"),
        size="l", easy_close=True,
    )
```
In `topbar_actions_server`, add:
```python
    @reactive.effect
    @reactive.event(input.tb_about)
    def _open_about():
        ui.modal_show(_about_modal(translator))
```

- [ ] **Step 5: Verify + extend e2e**

`import app` → ok. Append to `tests/test_topbar_e2e.py` `main()` (before close): click `#tb_about`, wait for `.modal`, assert the text "Overview" and "Changelog" tab labels are present:
```python
        await pg.click("#tb_about")
        await pg.wait_for_selector(".modal", timeout=10000)
        body = await pg.text_content(".modal") or ""
        assert "Overview" in body and "Changelog" in body, body[:120]
        await pg.click(".modal .btn-default, .modal button:has-text('Close')")
        print("topbar about: OK")
```
Run the e2e (live server) → OK.

- [ ] **Step 6: Commit**
```bash
git add CHANGELOG.md sespy/modules/topbar_actions.py sespy/translations/core.json tests/test_i18n.py tests/test_topbar_e2e.py
git commit -m "feat(topbar): About modal (Overview + Changelog tabs) + CHANGELOG.md"
```

---

### Task 4: Options modal — theme(2) + relocated language + autosave (the big one)

**Files:**
- Create: `www/themes.css`
- Modify: `sespy/modules/topbar_actions.py` (`_options_modal`, theme + autosave effects, `tb_options` handler), `sespy/dashboard.py` (themes.css link + set_theme JS), `sespy/modules/project_io.py` (gate `_autosave_on_change`), `sespy/translations/core.json`
- Test: `tests/test_i18n.py`; `tests/test_i18n_e2e.py` (UPDATE — language moved into modal); `tests/test_topbar_e2e.py`

**Interfaces:**
- Consumes: `current_theme`, `autosave_enabled` (Task 2 shared reactives), `language_switcher` (dashboard.py), `clear_autosave`/`autosave_age_seconds` (autosave.py).
- Produces: `_options_modal(translator, current_theme, autosave_enabled)`.

- [ ] **Step 1: i18n presence test (options.*)**

In `tests/test_i18n.py`:
```python
def test_options_keys_present(translations):
    for k in ("options.title", "options.appearance", "options.theme", "options.language",
              "options.autosave", "options.autosave_enable", "options.autosave_clear",
              "options.autosave_status"):
        assert k in translations, k
```
Run → FAIL.

- [ ] **Step 2: Add options.* keys (9 langs)**
```json
    "options.title": {"en":"Options","es":"Opciones","fr":"Options","de":"Optionen","lt":"Parinktys","pt":"Opções","it":"Opzioni","no":"Innstillinger","el":"Επιλογές"},
    "options.appearance": {"en":"Appearance","es":"Apariencia","fr":"Apparence","de":"Darstellung","lt":"Išvaizda","pt":"Aparência","it":"Aspetto","no":"Utseende","el":"Εμφάνιση"},
    "options.theme": {"en":"Theme","es":"Tema","fr":"Thème","de":"Design","lt":"Tema","pt":"Tema","it":"Tema","no":"Tema","el":"Θέμα"},
    "options.language": {"en":"Language","es":"Idioma","fr":"Langue","de":"Sprache","lt":"Kalba","pt":"Idioma","it":"Lingua","no":"Språk","el":"Γλώσσα"},
    "options.autosave": {"en":"Autosave","es":"Autoguardado","fr":"Sauvegarde auto","de":"Automatisch speichern","lt":"Automatinis įrašymas","pt":"Gravação automática","it":"Salvataggio automatico","no":"Autolagring","el":"Αυτόματη αποθήκευση"},
    "options.autosave_enable": {"en":"Enable autosave","es":"Activar autoguardado","fr":"Activer la sauvegarde auto","de":"Automatisch speichern aktivieren","lt":"Įjungti automatinį įrašymą","pt":"Ativar gravação automática","it":"Attiva salvataggio automatico","no":"Slå på autolagring","el":"Ενεργοποίηση αυτόματης αποθήκευσης"},
    "options.autosave_clear": {"en":"Clear autosaved data","es":"Borrar datos autoguardados","fr":"Effacer les données auto-sauvegardées","de":"Automatisch gespeicherte Daten löschen","lt":"Išvalyti automatiškai įrašytus duomenis","pt":"Limpar dados gravados automaticamente","it":"Cancella i dati salvati automaticamente","no":"Tøm autolagrede data","el":"Εκκαθάριση αυτόματα αποθηκευμένων δεδομένων"},
    "options.autosave_status": {"en":"Last autosave","es":"Último autoguardado","fr":"Dernière sauvegarde","de":"Letzte Speicherung","lt":"Paskutinis įrašymas","pt":"Última gravação","it":"Ultimo salvataggio","no":"Siste autolagring","el":"Τελευταία αποθήκευση"}
```
JSON smoke + `pytest tests/test_i18n.py` → pass.

- [ ] **Step 3: Create `www/themes.css`** (deep-ocean overrides; loaded after the skin)
```css
/* Light-marine is the default skin (sespy-skin.css). Deep-ocean overrides key
   colours when <html data-theme="deep-ocean"> is set by the theme switcher. */
html[data-theme="deep-ocean"] body,
html[data-theme="deep-ocean"] {
    background: #0b1f33;
    color: #d6e6f5;
}
html[data-theme="deep-ocean"] .card,
html[data-theme="deep-ocean"] .sespy-card,
html[data-theme="deep-ocean"] .modal-content,
html[data-theme="deep-ocean"] .sidebar,
html[data-theme="deep-ocean"] .sespy-topbar {
    background: #12314d;
    color: #d6e6f5;
    border-color: #1e4a72;
}
html[data-theme="deep-ocean"] a { color: #6fb8ff; }
html[data-theme="deep-ocean"] .text-muted { color: #8fb0cc !important; }
html[data-theme="deep-ocean"] .btn-default,
html[data-theme="deep-ocean"] .sespy-topbar-btn {
    background: #1b3e60; color: #d6e6f5; border-color: #2b5d8a;
}
/* pyvis graph canvases keep their in-code white bgcolor (framed cards) — v1. */
```

- [ ] **Step 4: Inject themes.css + the set_theme JS in `sespy/dashboard.py`**

a) In the page-level CSS link block (after `ui.tags.link(rel="stylesheet", href="sespy-skin.css")` and `cld.css`), add:
```python
            ui.tags.link(rel="stylesheet", href="themes.css"),
```
b) Add a `ui.tags.script` next to the existing `bookmark_js` (same `shiny:connected` idiom):
```python
    theme_js = ui.tags.script("""
      $(document).on('shiny:connected', function () {
        Shiny.addCustomMessageHandler('set_theme', function (t) {
          document.documentElement.setAttribute('data-theme', t);
        });
      });
    """)
```
and include `theme_js` in the shell's children alongside `burger_js`/`bookmark_js`.

- [ ] **Step 5: Add `_options_modal` + effects + the `tb_options` handler to `topbar_actions.py`**

Import the language switcher + autosave helpers at top:
```python
from ..dashboard import language_switcher
from ..autosave import clear_autosave, autosave_age_seconds

_THEME_CHOICES = {"light-marine": "Light Marine", "deep-ocean": "Deep Ocean (Dark)"}
```
```python
def _options_modal(translator, current_theme, autosave_enabled) -> ui.Tag:
    age = autosave_age_seconds()
    status = (f"{int(age)}s ago" if age is not None else "—")
    return ui.modal(
        ui.h5(_t(translator, "options.appearance", "Appearance")),
        ui.input_radio_buttons("theme_select", _t(translator, "options.theme", "Theme"),
                               choices=_THEME_CHOICES, selected=current_theme.get()),
        language_switcher(translator),   # the relocated language selector
        ui.tags.hr(),
        ui.h5(_t(translator, "options.autosave", "Autosave")),
        ui.input_switch("autosave_enabled", _t(translator, "options.autosave_enable",
                        "Enable autosave"), value=autosave_enabled.get()),
        ui.p(f"{_t(translator, 'options.autosave_status', 'Last autosave')}: {status}",
             class_="text-muted"),
        ui.input_action_button("autosave_clear",
                               _t(translator, "options.autosave_clear", "Clear autosaved data"),
                               class_="btn-outline-danger btn-sm"),
        title=_t(translator, "options.title", "Options"),
        footer=ui.modal_button("Close"), easy_close=True,
    )
```
In `topbar_actions_server`:
```python
    @reactive.effect
    @reactive.event(input.tb_options)
    def _open_options():
        ui.modal_show(_options_modal(translator, current_theme, autosave_enabled))

    @reactive.effect
    @reactive.event(input.theme_select)
    async def _apply_theme():
        theme = input.theme_select()
        if theme in _THEME_CHOICES:
            current_theme.set(theme)
            await session.send_custom_message("set_theme", theme)

    @reactive.effect
    @reactive.event(input.autosave_enabled)
    def _apply_autosave_pref():
        if autosave_enabled is not None:
            autosave_enabled.set(bool(input.autosave_enabled()))

    @reactive.effect
    @reactive.event(input.autosave_clear)
    def _clear_autosave():
        clear_autosave()
        ui.notification_show("Autosaved data cleared.", type="message", duration=3)
```

- [ ] **Step 6: Gate `project_io._autosave_on_change`**

a) Add `autosave_enabled=None` to `quick_actions_server(...)`'s signature.
b) In `_autosave_on_change` (project_io.py), gate after the isa_change subscribe:
```python
    @reactive.effect
    def _autosave_on_change():
        event_bus.isa_change.get()
        if autosave_enabled is not None and not autosave_enabled.get():
            return
        try:
            write_autosave(project_data.get())
            from datetime import datetime as _dt
            autosave_time.set(_dt.now().strftime("%H:%M:%S"))
        except Exception:
            pass
```

- [ ] **Step 7: UPDATE `tests/test_i18n_e2e.py`** (language now in the Options modal)

Replace the `document.getElementById('__sespy_language__')` block with: open the Options modal, wait for the in-modal select, then select 'es':
```python
        await page.click("#tb_options")
        await page.wait_for_selector(".modal #__sespy_language__", timeout=10000)
        await page.select_option(".modal #__sespy_language__", "es")
        await page.wait_for_timeout(1500)
```
(Keep the existing assertions that the nav labels switch to Spanish.)

- [ ] **Step 8: Verify + extend topbar e2e**

`import app` → ok. Append to `tests/test_topbar_e2e.py`:
```python
        await pg.click("#tb_options")
        await pg.wait_for_selector(".modal #theme_select", timeout=10000)
        # pick Deep Ocean → data-theme applied
        await pg.click(".modal input[value='deep-ocean']")
        ok = False
        for _ in range(20):
            await pg.wait_for_timeout(300)
            dt = await pg.get_attribute("html", "data-theme")
            if dt == "deep-ocean":
                ok = True; break
        assert ok, "data-theme not applied"
        print("topbar options/theme: OK")
```
Run the topbar e2e AND `tests/test_i18n_e2e.py` (live server) → both pass.

- [ ] **Step 9: Commit**
```bash
git add www/themes.css sespy/dashboard.py sespy/modules/topbar_actions.py sespy/modules/project_io.py sespy/translations/core.json tests/test_i18n.py tests/test_i18n_e2e.py tests/test_topbar_e2e.py
git commit -m "feat(topbar): Options modal — theme(2) + relocated language + autosave"
```

---

### Task 5: Help modal + final sweep

**Files:**
- Modify: `sespy/modules/topbar_actions.py` (`_help_modal`, `tb_help` handler), `sespy/translations/core.json`
- Test: `tests/test_i18n.py`; `tests/test_topbar_e2e.py`

**Interfaces:**
- Produces: `_help_modal(translator)`.

- [ ] **Step 1: i18n presence test (help.*)**
```python
def test_help_keys_present(translations):
    for k in ("help.title", "help.body"):
        assert k in translations, k
```
Run → FAIL.

- [ ] **Step 2: Add help.* keys (9 langs)**
```json
    "help.title": {"en":"Help","es":"Ayuda","fr":"Aide","de":"Hilfe","lt":"Pagalba","pt":"Ajuda","it":"Aiuto","no":"Hjelp","el":"Βοήθεια"},
    "help.body": {"en":"SESPy follows a create → edit → analyze → export workflow. Use the left stepper to set up a project (PIMS / Templates / Wizard), edit elements and connections, run the analyses (CLD, Loops, Metrics, Leverage, Quadrant, Simulation), then export a report. See the README for details.","es":"SESPy sigue un flujo crear → editar → analizar → exportar. Usa el paso lateral para crear un proyecto, editar elementos y conexiones, ejecutar los análisis y exportar un informe. Consulta el README.","fr":"SESPy suit un flux créer → éditer → analyser → exporter. Utilisez le panneau latéral pour créer un projet, modifier les éléments et connexions, lancer les analyses et exporter un rapport. Voir le README.","de":"SESPy folgt einem Erstellen → Bearbeiten → Analysieren → Exportieren-Ablauf. Nutzen Sie die Seitenleiste, um ein Projekt anzulegen, Elemente und Verbindungen zu bearbeiten, die Analysen auszuführen und einen Bericht zu exportieren. Siehe README.","lt":"SESPy veikia pagal kūrimo → redagavimo → analizės → eksporto eigą. Naudokite šoninę juostą projektui sukurti, elementams ir ryšiams redaguoti, analizėms vykdyti ir ataskaitai eksportuoti. Žr. README.","pt":"O SESPy segue um fluxo criar → editar → analisar → exportar. Use a barra lateral para criar um projeto, editar elementos e ligações, executar as análises e exportar um relatório. Consulte o README.","it":"SESPy segue un flusso crea → modifica → analizza → esporta. Usa la barra laterale per creare un progetto, modificare elementi e connessioni, eseguire le analisi ed esportare un report. Vedi il README.","no":"SESPy følger en opprett → rediger → analyser → eksporter-flyt. Bruk sidefeltet for å sette opp et prosjekt, redigere elementer og koblinger, kjøre analysene og eksportere en rapport. Se README.","el":"Το SESPy ακολουθεί ροή δημιουργία → επεξεργασία → ανάλυση → εξαγωγή. Χρησιμοποιήστε την πλαϊνή μπάρα για να δημιουργήσετε έργο, να επεξεργαστείτε στοιχεία και συνδέσεις, να εκτελέσετε τις αναλύσεις και να εξαγάγετε αναφορά. Δείτε το README."}
```
JSON smoke + `pytest tests/test_i18n.py` → pass.

- [ ] **Step 3: Add `_help_modal` + `tb_help` handler**
```python
def _help_modal(translator) -> ui.Tag:
    return ui.modal(
        ui.markdown(_t(translator, "help.body", "See the README.")),
        title=_t(translator, "help.title", "Help"),
        footer=ui.modal_button("Close"), size="l", easy_close=True,
    )
```
```python
    @reactive.effect
    @reactive.event(input.tb_help)
    def _open_help():
        ui.modal_show(_help_modal(translator))
```

- [ ] **Step 4: Verify + extend e2e + commit**
`import app` → ok. Append to `tests/test_topbar_e2e.py`: click `#tb_help`, wait `.modal`, assert workflow text present; print "topbar help: OK". Run e2e → OK.
```bash
git add sespy/modules/topbar_actions.py sespy/translations/core.json tests/test_i18n.py tests/test_topbar_e2e.py
git commit -m "feat(topbar): Help modal + i18n"
```

---

## Definition of Done

- [ ] Full unit + i18n suite green:
  `micromamba run -n shiny python -m pytest tests/ --ignore-glob='*e2e*' --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py -q`
  (incl. `test_feedback_store`, the 4 named presence tests, and `test_loader_handles_all_supported_languages`).
- [ ] `import app` builds cleanly.
- [ ] Full e2e: `micromamba run -n shiny python tests/run_e2e.py` → green except the pre-existing WeasyPrint `test_report_e2e.py`. The NEW `test_topbar_e2e.py` passes, and `test_i18n_e2e.py` (updated to drive the in-modal language select) passes.
- [ ] Manual sanity (optional): each topbar button opens its modal; feedback writes a row to `sespy/logs/feedback.db`; theme switches the page to deep-ocean; reopening Options shows the chosen theme/autosave state.
