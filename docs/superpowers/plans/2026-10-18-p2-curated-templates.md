# P2 — Curated R templates in the SESPy gallery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship SESPy v1.14.0: R's 7 curated MarineSABRES templates as a second gallery group ("MarineSABRES templates", with category / complexity / version / regional-sea badges) beside SESPy's 4 examples, pre-converted by P1a's mapper through a sync script with a drift guard, and R re-pinned to v1.31.0 (`4b53b7d`) with R's changes since v1.29.0 triaged.

**Architecture:** `sespy/r_template_catalogue.py` (Shiny-free, no clock, no logging) holds the category port, the catalogue builder and `sync()`, which reads R inputs with `git show` (or the pinned fixtures), converts them in memory, and only then writes the shipped projects `sespy/templates/marinesabres/<stem>.json`, the generated `catalogue.json`, the fixtures, `tests/parity/r_sync.json` and the generated block of `docs/parity/R_SYNC.md`. `scripts/sync_r_templates.py` is a thin CLI run as `python -m scripts.sync_r_templates` from the repo root. The gallery reads `catalogue.json` only (`list_catalogue()`); loading is the unchanged `load_project` path. No runtime conversion, no schema bump.

**Tech Stack:** Python 3.11+ (env Python 3.13), Shiny for Python 1.7+ (`shiny.testserver.test_server` for in-memory module tests), stdlib `subprocess` + git CLI, pytest, Playwright (async standalone e2e scripts).

**Spec:** docs/superpowers/specs/2026-10-18-p2-curated-templates-design.md

## Global Constraints

- Python: always `micromamba run -n shiny python ...`. Never `pip install`, never a venv, never `python - <<EOF` or a bare `python -` (both leave spinning stdin orphans), never a multi-line `python -c "..."` on Windows (it splits per line and creates stray files) — use a `.py` file in the scratchpad.
- Branch: cut `feat/p2-curated-templates` from the current HEAD of `docs/p2-design` (commit `b5c903a`, which carries the spec, this plan and the v1.13.0 code). Local `main` may be behind `origin/main`; do not use it.
- Never `git commit -a` / `git add -A` / `git add .`: the user's `LITERATURE/proposed-issues.md` is modified and `LITERATURE/*.md` are untracked; they are **never staged**. Stage explicit paths only.
- Every commit message ends with exactly this trailer line (the model name may be the implementer's own):
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
- Commit messages are multi-line: use the **PowerShell tool** with a single-quoted here-string (`git commit -m @'...'@` with `'@` at column 0). Never a PowerShell here-string in the Bash tool (it leaks a literal `@`).
- CI unit command (every task must end green on it): `micromamba run -n shiny python -m pytest tests/ --ignore-glob='*e2e*' --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py -q` (≈6 min; baseline measured while planning on `1e3b49e`: **1052 passed, 1 skipped**; ≈**1224 passed, 1 skipped** at the end (`tests/test_no_deprecations.py` walks `sespy` and gains one case per new module) — `tests/test_r_template_catalogue.py` alone is ≈60 s because it builds real git repos).
- **Shell state does not persist between tool calls**: every PowerShell / Bash call starts in the repo root with no variables. Each code block below is meant as **one** call and defines every variable it uses (`$R`, `$W`, `$log`, …); never rely on a `cd` or a variable from an earlier block. `<scratchpad>` means the session scratchpad's absolute path (substitute it literally).
- Lint (CI runs `ruff check sespy tests app.py`): the local ruff 0.15.4 already reports **54 errors on the untouched tree** (50 I001, 2 E741, 1 E501, 1 F821; measured on `d6b280c`) — do not fix those. The P2 lint gate, at every commit, is: (a) the P2 files are clean — `micromamba run -n shiny python -m ruff check sespy/r_template_catalogue.py sespy/templates/__init__.py sespy/modules/templates.py sespy/r_template_mapper.py scripts tests/test_r_template_catalogue.py tests/test_templates.py tests/test_templates_module.py tests/parity` → `All checks passed!` (only files that exist yet); and (b) no new errors elsewhere — `micromamba run -n shiny python -m ruff check sespy tests app.py --statistics` still totals 54.
- Edits are placed by **quoted anchor**, never by line number (the working copy is CRLF under `core.autocrlf=true`; the Edit tool handles that).
- Version: **1.14.0** in `sespy/__init__.py`, `pyproject.toml`, `docs/MANUAL.md` line 3 — first commit. **No schema bump**: `PROJECT_SCHEMA_VERSION` stays 7; the shipped projects carry `min_sespy_version` `1.13.0` (the schema floor that `Project.to_json()` stamps), never the running version.
- R reference: MarineSABRES_SES_Shiny **v1.31.0, commit `4b53b7d`** (2026-10-18), app directory `C:\Users\arturas.baziukas\OneDrive - ku.lt\HORIZON_EUROPE\Marine-SABRES\SESToolbox\MarineSABRES_SES_Shiny` (written `<R>` below; its git prefix is `MarineSABRES_SES_Shiny/`). The R repo is **read-only**: only `git show`, `git rev-parse`, `git diff`, `git log`; never checkout, switch, stash, commit, or touch its working tree (it is on `main` with the user's own uncommitted files). The 9 pinned files are identical at v1.29.0 and v1.31.0 (`git diff --quiet e33faea v1.31.0 -- <9 paths>` exits 0).
- Exact values from the spec: name suffix `" (MarineSABRES)"`; shipped files `sespy/templates/marinesabres/{Aquaculture,Caribbean,ClimateChange,Fisheries,OffshoreWind,Pollution,Tourism}_SES_Template.json` + `sespy/templates/marinesabres/catalogue.json`; new fixture `tests/parity/r_source/template_loader.R` (sha256_text_norm `3ebe6c83a737ead8e91936f9f11ca5cfa4244d56d52f1644fc7df2af131d02d3`, computed by a real sync while planning); R_SYNC.md markers `<!-- r-sync:begin -->` / `<!-- r-sync:end -->`; catalogue keys, in order, `file, name, description, category, complexity, version, regional_sea_label, source, usage_notes, element_count, connection_count`; new i18n keys `templates.group_marinesabres`, `templates.group_sespy`, `templates.about`, `templates.complexity_simple`, `templates.complexity_complex`, `templates.category_{multi_stressor,extraction,recreation,production,pollution,climate,energy,general}`; module ids `templates-group_marinesabres`, `templates-group_sespy`.
- Writes from the sync use `Path.write_bytes(text.encode("utf-8"))` (LF). Never `write_text` (CRLF on Windows), never `persistent_storage.project_to_bytes` / `save_project_atomic` (they stamp `modified_at` with the clock).
- `python -m scripts.sync_r_templates` is always run **from the repo root**: `-m` then imports this checkout's `sespy` (the editable install points at the main checkout), and the new regular package `scripts/` wins over the stray namespace package the env has at `site-packages/win32/scripts`. Tests never `from tests.x import ...` (a stray site-packages `tests` package shadows it); `tests/parity/` has no `__init__.py`.
- `git -c core.longpaths=true` for every worktree or fake repo under a long temp path (the test helper already passes it).
- Nothing heavy runs alongside the e2e gate; port 8000 must be free before any e2e run (`Get-NetTCPConnection -LocalPort 8000 -State Listen` prints nothing); after any big run, sweep orphan `python` processes by creation date.
- Release steps (Task 13) and the roadmap push need the user's explicit go-ahead, each step separately.

## Review Focus

1. **Line endings** — the sync writes LF only (`write_bytes`), and `--check` / the parity extraction tolerate a CRLF working copy (JSON compared parsed, text CRLF → LF). Owning tasks: **Task 4** (`test_build_is_deterministic_lf_and_newline_terminated`, `test_check_passes_on_a_crlf_copy`, `test_check_in_git_mode_passes_on_a_crlf_copy`, `test_real_run_writes_everything_then_checks_clean`) and **Task 5** (`test_committed_tree_has_no_drift`, `test_committed_tree_has_no_drift_as_crlf`, `test_r_category_parity.py`: `test_null_branch`, `test_multi_issue_branch`, `test_regex_table_and_order`, `test_fallback`, `test_no_unparsed_branch`, all reading R through the CRLF-normalising `_function_body`).
2. **Nothing written on any failure** — mapper `ValueError`, an empty always-non-empty field, missing/duplicated markers, a bad `--rev`, an unknown tag, a path missing at the rev, an unaccepted warning, argument errors: exit 1 and a byte-identical tree. Owning task: **Task 4** (`test_value_error_writes_nothing`, `test_empty_always_non_empty_field_writes_nothing`, `test_markers_missing_or_duplicated_write_nothing`, `test_rev_must_be_a_release_tag`, `test_unknown_tag_and_missing_path_write_nothing`, `test_argument_errors_write_nothing`, `test_malformed_pin_exits_1_and_writes_nothing`, `test_non_object_template_exits_1_and_writes_nothing`, all via `_snap`).
3. **Accepted-warning semantics** — exact-field match, scoped per template, persisted only by a git-mode run, dropped when it no longer occurs, sorted by `(template, kind, from, to, text)`, fixture mode cannot accept. Owning task: **Task 4** (`test_off_rule_link_needs_accept_warnings_and_is_persisted`, `test_accepted_warning_matches_only_on_every_field`, `test_accepted_warning_that_no_longer_occurs_is_dropped`, `test_type_mismatch_entries_and_sort_order`, `test_persisted_warnings_are_sorted_not_in_production_order`, `test_warning_sort_key_literal_order`, `test_off_rule_link_in_fixture_mode_fails_and_cannot_be_accepted`).
4. **`list_catalogue` robustness** — escaping / absolute / dangling / empty `file`, bool / str / zero counts, a wrong-typed may-be-empty field, an unparsable catalogue, a relative and an 8.3-short directory. Owning task: **Task 6** (`test_bad_entry_is_skipped_with_a_warning` (12 cases), `test_unparsable_catalogue_gives_empty_and_warns`, `test_relative_directory_still_lists_all_seven`, `test_short_8dot3_directory_still_lists_all_seven`).
5. **Category precedence and the untranslated fallback** — R's first-match order ("wind farm" → Production, "fish farm" → Extraction, scalar / empty / NULL issues), content parity with R's source, and a category or complexity without a key rendering the raw R value, never a key string. Owning tasks: **Task 4** (`test_category_synthetic`), **Task 5** (`test_regex_table_and_order`, `test_no_unparsed_branch`), **Task 8** (`test_untranslated_category_and_complexity_show_the_raw_value`, `test_tr_value_on_a_key_miss_returns_the_value`).

---

## File Structure

**Created**
| Path | Responsibility |
|---|---|
| `sespy/r_template_catalogue.py` | `SyncResult`, `determine_category`, `regional_sea_label`, `complexity_of`, warning entries, `build_outputs`, `render_block`, `splice_block`, `sync()`. Shiny-free, no clock, no logging. |
| `scripts/__init__.py` | Makes `scripts` a regular package (beats the env's stray namespace `scripts`). |
| `scripts/sync_r_templates.py` | Thin argparse CLI over `sync()`; `repo_root` from `__file__`. |
| `sespy/templates/marinesabres/{7 stems}_SES_Template.json` | Shipped SESPy projects converted from R v1.31.0 (generated). |
| `sespy/templates/marinesabres/catalogue.json` | Generated gallery catalogue (§4). |
| `tests/parity/r_source/template_loader.R` | R v1.31.0 `functions/template_loader.R` fixture (generated by the sync). |
| `tests/parity/test_r_category_parity.py` | R `.determine_template_category` vs the Python port. |
| `tests/test_r_template_catalogue.py` | Sync, catalogue, category port, accepted warnings, CLI; drift guard and raw-R check on the shipped tree. |
| `tests/test_templates_module.py` | `test_server` tests of the Templates panel. |
| `tests/test_r_templates_e2e.py` | Playwright e2e for the MarineSABRES group. |

**Modified**
| Path | Change |
|---|---|
| `sespy/__init__.py`, `pyproject.toml` (version), `docs/MANUAL.md` (line 3) | Version 1.14.0 (Task 1). |
| `sespy/r_template_mapper.py`, `tests/test_r_template_mapper.py` | §5 hardening + its tests (Task 2). |
| `docs/parity/R_SYNC.md` | Markers, prose, 42-row triage (Task 3); generated block (Task 5). |
| `tests/parity/r_sync.json`, `tests/parity/test_r_sync.py` | Re-pin to v1.31.0, 9 files, `accepted_warnings` (Task 5). |
| `sespy/templates/__init__.py`, `pyproject.toml` (package-data), `tests/test_templates.py` | `TemplateInfo` fields, `list_catalogue()`, packaging (Task 6). |
| `sespy/translations/core.json`, `tests/test_i18n.py` | 13 new `templates.*` keys (Task 7). |
| `sespy/modules/templates.py` | Groups, badges, About, combined index (Task 8). |
| `tests/test_templates_e2e.py` | Exact-name card lookup, CLD count (Task 9). |
| `docs/MANUAL.md` §7, `README.md`, `CHANGELOG.md`, `docs/screenshots/templates.png` | Release docs (Task 10); README e2e count (Task 12). |
| `docs/superpowers/specs/2026-10-16-r-parity-roadmap-design.md` on branch `docs/r-parity-roadmap` | Roadmap edits (Task 11). |

Commit order (spec §9): **C1** = Task 1; **C2** = Task 2; **C3** = Task 3; **C4** = Task 4; **C5** = Task 5 (the first real sync + the tests that need it, one commit); then gallery (Tasks 6–8), e2e (Task 9), docs (Task 10); roadmap = Task 11 (other branch); gates = Task 12; release = Task 13.

Catalogue facts every later task relies on (from the real sync while planning):

| Catalogue order | Name | Elements / links | Category | Complexity | Version | Regional-sea label |
|---|---|---|---|---|---|---|
| 0 | Caribbean Island - Comprehensive SES Template (MarineSABRES) | 78 / 140 | Multi-Stressor | complex | 1.1 | Caribbean Sea |
| 1 | Climate Change (MarineSABRES) | 25 / 28 | Climate | simple | 2.2 | Arctic Ocean |
| 2 | Coastal Lagoon (MarineSABRES) (R's Aquaculture file) | 28 / 30 | Production | simple | 2.1 | Baltic Sea |
| 3 | Fisheries (MarineSABRES) | 26 / 33 | Extraction | simple | 2.3 | Baltic Sea |
| 4 | Offshore Wind Energy (MarineSABRES) | 23 / 27 | Energy | complex | 2.2 | North Sea |
| 5 | Pollution (MarineSABRES) | 28 / 29 | Pollution | simple | 2.3 | Baltic Sea |
| 6 | Tourism (MarineSABRES) | 26 / 33 | Recreation | simple | 2.2 | Mediterranean Sea |

Gallery indices: 0–6 above, then SESPy's examples 7–10 (`list_templates()` order: Coastal Tourism SES, Minimal Demo, Offshore Wind Farm SES, Small-scale Coastal Fisheries SES). 320 links in total; 0 off-rule links and 0 type mismatches today.

---

### Task 0: Branch and baseline

**Files:** none.

- [ ] **Step 1: Create the implementation branch from the spec branch**

```powershell
git switch docs/p2-design
git log --oneline -1          # expect b5c903a docs(p2): implementation plan (or a later docs(p2) plan-review commit)
git switch -c feat/p2-curated-templates
git status --short            # expect only LITERATURE/ entries (user's, never staged)
```

- [ ] **Step 2: Record the R repo state** (the user works in R concurrently, so its branch and status may change during P2 on their own; what must hold is that **the sync adds nothing** — it only runs `git show` / `rev-parse`, which write neither the reflog nor the working tree)

```powershell
$R = 'C:\Users\arturas.baziukas\OneDrive - ku.lt\HORIZON_EUROPE\Marine-SABRES\SESToolbox\MarineSABRES_SES_Shiny'
git -C $R rev-parse --short=7 'v1.31.0^{commit}'         # 4b53b7d
git -C $R reflog -n 1 --date=iso --format='%gd %gs'   # note this newest entry; %gd prints HEAD@{<entry time>}
Get-Date -Format o                                         # note T0
```

- [ ] **Step 3: Confirm the baseline is green**

Run the CI unit command. Expected: `1052 passed, 1 skipped` (a few more or fewer is fine; zero failures).

---

### Task 1 (C1): Version bump to 1.14.0

**Files:**
- Modify: `sespy/__init__.py`, `pyproject.toml`, `docs/MANUAL.md`
- Test: `tests/test_manual.py::test_manual_version_line_matches_package` (existing)

**Interfaces:** Produces `sespy.__version__ == "1.14.0"`. (No stamping depends on it: schema 7's floor stays `1.13.0`.)

- [ ] **Step 1: Edit the three version lines (by anchor)**

`sespy/__init__.py`: `__version__ = "1.13.0"` → `__version__ = "1.14.0"`
`pyproject.toml`: `version = "1.13.0"` → `version = "1.14.0"`
`docs/MANUAL.md`: `**Version 1.13.0 · October 2026**` → `**Version 1.14.0 · October 2026**`

- [ ] **Step 2: Run the manual test**

`micromamba run -n shiny python -m pytest tests/test_manual.py -q` → `7 passed`.

- [ ] **Step 3: Run the CI unit command** → all green.

- [ ] **Step 4: Commit**

```powershell
git add sespy/__init__.py pyproject.toml docs/MANUAL.md
git commit -m @'
chore(release): bump version to 1.14.0 (P2)

First P2 commit (spec §9). No schema bump: P2 writes only schema-7 fields.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
'@
```

---

### Task 2 (C2): Mapper hardening (spec §5)

**Files:**
- Modify: `sespy/r_template_mapper.py` (`convert_r_template`: docstring, the element id check, the connections loop)
- Test: `tests/test_r_template_mapper.py` (append)

**Interfaces:** `convert_r_template(raw, *, key)` keeps its signature. New `ValueError` messages: `"{key}: connections must be a list"`, `"{key}: connections[{i}] is not an object"`. Connection endpoints are `str()`-coerced when not `None`; an element id `0` is accepted (`id` missing / `None` / `""` still raises `"{key}: {cat}[{i}] has no id or name"`).

- [ ] **Step 1: Append the failing tests to `tests/test_r_template_mapper.py`** (after `test_mapper_imports_without_shiny`; `_tiny()` is the file's existing helper)

```python
# ---- P2 §5: mapper hardening ---------------------------------------------

@pytest.mark.parametrize("how", ["absent", "null"])
def test_absent_or_null_connections_give_no_links(how):
    # Guard (green before and after): R's `%||% list()`. The type check added
    # in P2 must not turn these two into errors.
    t = _tiny()
    if how == "absent":
        del t["connections"]
    else:
        t["connections"] = None
    project, report = convert_r_template(t, key="Tiny")
    assert project.isa_data.connections == [] and report.link_count == 0


@pytest.mark.parametrize("bad", [{}, "", 0, {"from_id": "P1"}, "P1->S1", 7])
def test_non_list_connections_raise(bad):
    # Today `{}`, `""` and `0` are swallowed by `or []` (silently no links),
    # a dict or string iterates into AttributeError, and 7 is a TypeError.
    t = _tiny()
    t["connections"] = bad
    with pytest.raises(ValueError, match=r"Tiny: connections must be a list"):
        convert_r_template(t, key="Tiny")


@pytest.mark.parametrize("bad", ["P1->S1", ["P1", "S1"], None, 3])
def test_non_dict_connection_raises(bad):
    # Today: AttributeError ('str' object has no attribute 'get').
    t = _tiny()
    t["connections"].append(bad)
    with pytest.raises(ValueError, match=r"Tiny: connections\[1\] is not an object"):
        convert_r_template(t, key="Tiny")


def test_integer_ids_on_both_sides_match():
    # Element ids are str()-coerced; endpoints were not, so 1 != "1".
    t = {
        "template_name": "Ints", "metadata": {"version": "1.0"},
        "dapsiwrm_framework": {
            "pressures": [{"id": 1, "name": "p"}],
            "marine_processes": [{"id": 2, "name": "s"}],
        },
        "connections": [{"from_id": 1, "to_id": 2, "polarity": "-"}],
    }
    project, report = convert_r_template(t, key="Ints")
    c = project.isa_data.connections[0]
    assert (c.source, c.target, c.polarity) == ("1", "2", "-")
    assert [e.id for e in project.isa_data.elements] == ["1", "2"]
    assert report.off_rule_links == ()


def test_missing_endpoint_still_reports_none():
    # Guard: coercion applies only when the endpoint is not None.
    t = _tiny()
    del t["connections"][0]["to_id"]
    with pytest.raises(ValueError, match=r"Tiny.*unknown element id None"):
        convert_r_template(t, key="Tiny")


def test_element_id_zero_is_accepted():
    # Today `not item.get("id")` rejects 0.
    t = _tiny()
    t["dapsiwrm_framework"]["drivers"] = [{"id": 0, "name": "d0"}]
    project, _ = convert_r_template(t, key="Tiny")
    assert "0" in {e.id for e in project.isa_data.elements}


@pytest.mark.parametrize("bad_id", ["missing", None, ""])
def test_element_without_usable_id_still_raises(bad_id):
    t = _tiny()
    item = {"name": "d"}
    if bad_id != "missing":
        item["id"] = bad_id
    t["dapsiwrm_framework"]["drivers"] = [item]
    with pytest.raises(ValueError, match=r"Tiny: drivers\[0\] has no id or name"):
        convert_r_template(t, key="Tiny")
```

- [ ] **Step 2: Run them — RED**

`micromamba run -n shiny python -m pytest tests/test_r_template_mapper.py -q` → `12 failed, 55 passed`:
- `test_non_list_connections_raise` ×6: `{}`, `""`, `0` → `DID NOT RAISE` (swallowed by `or []`); `{"from_id": "P1"}`, `"P1->S1"` → `AttributeError: 'str' object has no attribute 'get'`; `7` → `TypeError: 'int' object is not iterable`.
- `test_non_dict_connection_raises` ×4: `AttributeError` (`'str'` / `'list'` / `'NoneType'` / `'int'` object has no attribute `'get'`).
- `test_integer_ids_on_both_sides_match`: `ValueError: Ints: connections[0] 1->2: unknown element id 1`.
- `test_element_id_zero_is_accepted`: `ValueError: Tiny: drivers[0] has no id or name`.
The six guards (`test_absent_or_null_connections_give_no_links` ×2, `test_missing_endpoint_still_reports_none`, `test_element_without_usable_id_still_raises` ×3) pass before and after: they pin the behaviour the fix must keep.

- [ ] **Step 3: Implement — three anchored edits in `sespy/r_template_mapper.py`**

Docstring — replace
```python
    (from_id, to_id) pair, or a present-but-invalid polarity, strength,
    confidence or description."""
```
with
```python
    (from_id, to_id) pair, `connections` present but not a list, a
    connection that is not an object, or a present-but-invalid polarity,
    strength, confidence or description. Element ids and connection
    endpoints are compared as strings, so integer ids (including 0) match."""
```

Element id check — replace
```python
            if not isinstance(item, dict) or not item.get("id") or not item.get("name"):
```
with
```python
            if (not isinstance(item, dict) or item.get("id") in (None, "")
                    or not item.get("name")):
```

Connections loop — replace
```python
    for i, c in enumerate(raw.get("connections") or []):
        src, tgt = c.get("from_id"), c.get("to_id")
```
with
```python
    raw_connections = raw.get("connections")
    if raw_connections is None:                 # absent or null: R's %||% list()
        raw_connections = []
    elif not isinstance(raw_connections, list):
        raise ValueError(f"{key}: connections must be a list")
    for i, c in enumerate(raw_connections):
        if not isinstance(c, dict):
            raise ValueError(f"{key}: connections[{i}] is not an object")
        src, tgt = c.get("from_id"), c.get("to_id")
        src = None if src is None else str(src)     # integer ids match str() ids
        tgt = None if tgt is None else str(tgt)
```
(The type is checked before any fallback; the coerced `src`/`tgt` flow into `where`, the endpoint check, `seen`, `classify` and `Connection(source=..., target=...)` unchanged.)

- [ ] **Step 4: Run — GREEN**

`micromamba run -n shiny python -m pytest tests/test_r_template_mapper.py tests/parity -q` → `83 passed` (67 mapper + 16 parity). The 7 real fixtures convert exactly as before (their ids are strings).

- [ ] **Step 5: Run the CI unit command** → green.

- [ ] **Step 6: Commit**

```powershell
git add sespy/r_template_mapper.py tests/test_r_template_mapper.py
git commit -m @'
fix(mapper): reject non-list connections and non-object links; int ids (P2 §5)

connections absent or null still gives no links (R's %||% list()); any other
non-list now raises instead of being swallowed by `or []` or crashing with
AttributeError. A connection that is not an object raises ValueError.
Endpoints are str()-coerced like element ids, so integer ids match, and an
element id of 0 is accepted.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
'@
```

---

### Task 3 (C3): `docs/parity/R_SYNC.md` hand edits — markers, prose, R triage

**Files:** Modify `docs/parity/R_SYNC.md` (whole file rewritten below). Tests: `tests/parity/test_r_sync.py` (existing, unchanged here) must stay green.

**Interfaces:** Produces the markers `<!-- r-sync:begin -->` / `<!-- r-sync:end -->` that Task 4's `splice_block` requires. The block between them is already in the exact generated format (`| File | Hash |`, rows sorted by path, `**Accepted sync warnings:** none.`) for the **current** v1.29.0 pin, so Task 5's sync diff is just the pin line and one new row. The prose says "Adopted in SESPy 1.14.0" / "baseline v1.31.0" while the block still reads v1.29.0: **intended** (spec §9 puts all hand edits in this commit); Task 5 makes the block agree. Do not "fix" it here.

The triage table is `git -C <R> diff --name-status e33faea v1.31.0` (42 paths; use `--name-status`, `--stat` truncates paths), each with an owner. Verify the count before writing: `git -C '<R>' diff --name-status e33faea v1.31.0 | Measure-Object -Line` → `42` (`<R>` = the literal R app path from Global Constraints).

- [ ] **Step 1: Replace the whole file with**

````markdown
# R sync record

SESPy reads a few files from the R MarineSABRES SES Toolbox. The copies under
`tests/parity/` are **test fixtures**: they never ship to the server. Since
SESPy 1.14.0 the 7 R templates also ship, as SESPy projects converted from
those fixtures (`sespy/templates/marinesabres/`). This page is the human
record of which R release they come from. The machine-readable pin is
[`tests/parity/r_sync.json`](../../tests/parity/r_sync.json), which
`tests/parity/test_r_sync.py` checks; it also checks that this page lists
exactly the same hashes. The sync script
(`python -m scripts.sync_r_templates`) updates the pin, the hashes and the
generated block below together; never edit the block by hand.

## Current pin

<!-- r-sync:begin -->
- **R release:** MarineSABRES_SES_Shiny **v1.29.0**, commit `e33faea`.

| File | Hash |
|---|---|
| `tests/parity/r_rules/dapsiwrm_connection_rules.R` | `ca4294f10974af34adf7dad9fe029318955c1c498356224b656a3e69525422a5` |
| `tests/parity/r_templates/Aquaculture_SES_Template.json` | `d24154498ce843d0f10e2b724340ca63878002e63486132d933ef777d844c946` |
| `tests/parity/r_templates/Caribbean_SES_Template.json` | `7c38efa11232215eea9754c2831e8beaec31eb8d7a90618a16d3834af9bd5961` |
| `tests/parity/r_templates/ClimateChange_SES_Template.json` | `ab8cbaca91842fdc8cf87e46d0b0d20e14d298f38c21379dcaf27c8650f92ae3` |
| `tests/parity/r_templates/Fisheries_SES_Template.json` | `f04c3673afad34f2424e3ebaf3944f9e117dda87efb537960e4c14ef16c04da6` |
| `tests/parity/r_templates/OffshoreWind_SES_Template.json` | `a7657b88a1046d0590e4dcfdea39852cf2a4cdfa7629a2f14564753079c6debf` |
| `tests/parity/r_templates/Pollution_SES_Template.json` | `d3da39cf77605a35c7d3accbdd4b37830753443230f88d22c59e971c60332e56` |
| `tests/parity/r_templates/Tourism_SES_Template.json` | `1c0af86d3737cdb306ccc8eb0107fbe1ac75b41c4fede2dd56dc265c9983662e` |

**Accepted sync warnings:** none.
<!-- r-sync:end -->

- **Adopted in:** SESPy 1.14.0 (P2: curated R templates in the gallery);
  laguna verification of the new pin follows the 1.14.0 deploy. The
  previous pin, v1.29.0 (`e33faea`), was adopted in SESPy 1.13.0 (P1a).
- **Roadmap baseline:** moved from v1.29.0 (`e33faea`) to v1.31.0
  (`4b53b7d`). The pinned files are unchanged between the two tags
  (`git diff --quiet e33faea v1.31.0 -- <the 9 paths>` exits 0).

The JSON templates are hashed with `sespy.r_sync.sha256_norm` (the parsed
JSON, so key order, CRLF and a BOM do not matter). The `.R` files are hashed
with `sespy.r_sync.sha256_text_norm` (text with CRLF normalised to LF).
`Caribbean_SES_Template_backup.json` is not a fixture.

## Laguna verification (2026-10-17)

The R app deployed on laguna (`/srv/shiny-server/marinesabres`) was
v1.29.0 on 2026-10-17. Its 7 templates and its
`functions/dapsiwrm_connection_rules.R` have the same hashes as the local
checkout, so the pin above matches what users run. This check covered the 8
files P1a pinned; `functions/template_loader.R` (pinned since SESPy 1.14.0)
is pinned from git only and was not checked on laguna. The 9 pinned files
are identical at v1.29.0 and v1.31.0, so a laguna R still at v1.29.0 does
not affect them.

## Adopting a new R release

1. From the SESPy repo root run
   `micromamba run -n shiny python -m scripts.sync_r_templates --r-root <R app dir> --rev vX.Y.Z`
   (`<R app dir>` is `.../SESToolbox/MarineSABRES_SES_Shiny`). It reads the
   inputs with `git show` (it never checks out, switches or stashes in the R
   repo), converts the 7 templates, and rewrites the fixtures,
   `tests/parity/r_sync.json`, the shipped `sespy/templates/marinesabres/`
   files and the generated block above in one go. Off-rule links or type
   mismatches make it fail; after reviewing them, rerun with
   `--accept-warnings` and they are listed in the block.
2. Review the diff (`git diff --stat`, and the `hash ...: old -> new` lines
   the script prints), then triage R's changes since the previous pin into a
   table like the one below: one row per path of
   `git -C <R app dir> diff --name-status <old tag> <new tag>`, each with an
   owner sub-project or "not relevant".
3. Run the gates: `tests/parity/`, `tests/test_r_template_mapper.py`,
   `tests/test_r_template_catalogue.py`, `tests/test_templates.py`, then the
   CI unit command and the full e2e gate. A red `test_r_rules_parity.py`
   means R's rule table changed (`sespy/constants.py::DAPSIWRM_ADJACENCY_RULES`
   must follow); a red `test_r_category_parity.py` means R's
   `.determine_template_category` changed (`sespy/r_template_catalogue.py`
   must follow). Finally `python -m scripts.sync_r_templates --r-root <R app dir> --check`
   must report no drift.

Live drift against laguna (`tests/parity/check_live.py`) is owned by **K1**
in the R-parity roadmap; P1a and P2 read R only through these fixtures and
the sync script.

## R changes v1.29.0 → v1.31.0 (triaged 2026-10-18)

`git -C <R app dir> diff --name-status e33faea v1.31.0`: 42 paths, all
under `MarineSABRES_SES_Shiny/` (prefix omitted). None of them is a pinned
file. R 1.30.0 = WP5 governance profiles (WS-9a), R 1.31.0 = WP5
governance-readiness check (WS-9b).

| # | Status | Path | Change | Owner |
|---|---|---|---|---|
| 1 | M | `.gitattributes` | `text eol=lf` for the two new WP5 data files | not relevant |
| 2 | M | `CHANGELOG.md` | 1.30.0 and 1.31.0 entries (source of this triage) | not relevant |
| 3 | M | `DESCRIPTION` | version 1.31.0 | not relevant |
| 4 | M | `VERSION` | version 1.31.0 | not relevant |
| 5 | M | `VERSION_INFO.json` | version metadata | not relevant |
| 6 | M | `app.R` | registers the readiness page and the governance-context sub-module | P4 |
| 7 | M | `constants.R` | `Policy_Target` in `ISA_INDICATOR_COLUMNS`; stakeholder columns `NERoles`, `SourceId` (P1b); `WP5_GOV_*`, `WP5_POLICY_TARGETS`, readiness constants and min-app versions (P4) | P1b, P4 |
| 8 | M | `data/country_governance_db.json` | 97 → 99 countries (Greenland, Faroe Islands), 8 → 15 regional conventions/bodies | K1 |
| 9 | A | `data/wp5_governance_profiles.json` | D5.4 governance profiles (curated data) | P4 (§3 allow-list) |
| 10 | A | `data/wp5_readiness_items.json` | D5.4 readiness item bank | P4 (§3 allow-list) |
| 11 | A | `docs/superpowers/plans/2026-10-17-wp5-ws9a-governance-profiles.md` | R plan (reference reading) | not relevant |
| 12 | A | `docs/superpowers/plans/2026-10-17-wp5-ws9b-readiness-check.md` | R plan (reference reading) | not relevant |
| 13 | A | `docs/superpowers/specs/2026-10-17-wp5-ws9a-governance-profiles-design.md` | R spec (reference for P1b/P4) | not relevant |
| 14 | A | `docs/superpowers/specs/2026-10-17-wp5-ws9b-readiness-check-design.md` | R spec (reference for P4) | not relevant |
| 15 | M | `functions/data_structure.R` | stakeholder register gains `NERoles`/`SourceId`; `next_element_id`/`safe_counter` (duplicate-row fix `33ddd96`) (P1b); empty `pims$readiness` block and its load normalisation (P4) | P1b, P4 |
| 16 | M | `functions/indicator_snapshot.R` | `Policy_Target` input id; `project_has_policy_target()` | P1b |
| 17 | M | `functions/isa_form_builders.R` | `Policy_Target` field in the indicator row; free-text select | P1b |
| 18 | A | `functions/stakeholder_schema.R` | stakeholder schema and D5.4 roles (Newton & Elliott typology) | P1b |
| 19 | M | `functions/ui_sidebar.R` | "Governance readiness (D5.4)" menu item | P4 |
| 20 | A | `functions/wp5_governance.R` | D5.4 governance-profile helpers | P4 |
| 21 | A | `functions/wp5_readiness.R` | readiness scoring, storage, import/export | P4 |
| 22 | M | `global.R` | sources the three new function files | P1b, P4 |
| 23 | M | `modules/isa_data_entry_module.R` | stamps min app version when an element has a `Policy_Target` | P1b |
| 24 | M | `modules/pims_stakeholder_module.R` | D5.4 roles column, "Load DA actor list"; duplicate-row fix `33ddd96` | P1b |
| 25 | M | `modules/response_module.R` | "Governance context (D5.4)" tab, register add API; duplicate-row fix `33ddd96` | P4 |
| 26 | A | `modules/wp5_governance_context_module.R` | governance-context tab with "Add to register" | P4 |
| 27 | A | `modules/wp5_readiness_module.R` | WS-9b readiness page in PIMS | P4 |
| 28 | A | `scripts/tests/test_wp5_governance_profiles.py` | R's data-file tests | P4 |
| 29 | A | `scripts/tests/test_wp5_readiness_items.py` | R's data-file tests | P4 |
| 30 | M | `tests/testthat/test-indicator-snapshot.R` | `Policy_Target` tests | P1b |
| 31 | M | `tests/testthat/test-pims-stakeholder-module.R` | roles, actor list, duplicate-row tests | P1b |
| 32 | M | `tests/testthat/test-response-module.R` | register add / duplicate-row tests | P4 |
| 33 | A | `tests/testthat/test-wp5-governance-context-module.R` | governance tab tests | P4 |
| 34 | A | `tests/testthat/test-wp5-governance-profiles.R` | profile data tests | P4 |
| 35 | A | `tests/testthat/test-wp5-governance.R` | governance helper tests | P4 |
| 36 | A | `tests/testthat/test-wp5-readiness-items.R` | item bank tests | P4 |
| 37 | A | `tests/testthat/test-wp5-readiness-module.R` | readiness page tests | P4 |
| 38 | A | `tests/testthat/test-wp5-readiness.R` | readiness scoring tests | P4 |
| 39 | M | `translations/modules/indicator_registry.json` | `Policy_Target` strings | P1b |
| 40 | A | `translations/modules/wp5_governance.json` | governance strings (9 languages) | P4 |
| 41 | A | `translations/modules/wp5_readiness.json` | readiness strings (9 languages) | P4 |
| 42 | M | `translations/ui/sidebar.json` | `ui.sidebar.governance_readiness` | P4 |

**Check item (SESPy stakeholders page):** R commit `33ddd96` ("adding a
second stakeholder or measure no longer creates duplicate rows") fixed
`generate_element_id(prefix, n)` returning every id 1..n at the stakeholder,
engagement, communication and response-measure add sites. Check that
SESPy's stakeholders page (`sespy/modules/pims_stakeholders.py`) adds exactly
one row per click and allocates ids safely for loaded projects. Owners: P1b
(stakeholder schema), P4 (response register).
````

- [ ] **Step 2: Check the 42 rows against git**

Every path of `git -C '<R>' diff --name-status e33faea v1.31.0` (prefix `MarineSABRES_SES_Shiny/` stripped) appears exactly once in the table, with the same status letter. The 8 hashes in the block are unchanged (`test_r_sync_md_lists_exactly_the_pinned_hashes`).

- [ ] **Step 3: Run** `micromamba run -n shiny python -m pytest tests/parity tests/test_manual.py -q` → `23 passed`; then the CI unit command → green.

- [ ] **Step 4: Commit**

```powershell
git add docs/parity/R_SYNC.md
git commit -m @'
docs(parity): R_SYNC.md generated-block markers and R v1.29.0 -> v1.31.0 triage (P2)

Wraps the pin line and hash table in r-sync markers (already in the
generated format), moves the Adopted-in / baseline bullets outside the
block, scopes the laguna verification to the 8 P1a files, rewrites
"Adopting a new R release" around scripts/sync_r_templates, and triages
all 42 paths of git diff --name-status e33faea v1.31.0 with owners
(K1, P1b, P4, not relevant) plus the 33ddd96 stakeholder check item.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
'@
```

---

### Task 4 (C4): `sespy/r_template_catalogue.py`, the CLI, and the tmp_path tests

**Files:**
- Create: `sespy/r_template_catalogue.py`, `scripts/__init__.py`, `scripts/sync_r_templates.py`, `tests/test_r_template_catalogue.py`

**Interfaces:**
- Consumes: `sespy.r_template_mapper.convert_r_template`, `ConversionReport` (Task 2); `sespy.r_sync.sha256_norm`, `sha256_text_norm`; `sespy.regional_seas.get_regional_seas`; the markers (Task 3).
- Produces (used by Tasks 5–8):
  - constants `STEMS`, `TEMPLATE_FILES`, `SUFFIX`, `OUT_DIR = "sespy/templates/marinesabres"`, `CATALOGUE_PATH`, `PIN_PATH`, `MD_PATH`, `BEGIN`, `END`, `TAG_RE`, `INPUTS` (R path → fixture path, 9 entries), `CATEGORY_NULL`, `CATEGORY_MULTI`, `CATEGORY_FALLBACK`, `CATEGORY_RULES`, `DEFAULT_COMPLEXITY`, `CATALOGUE_KEYS`, `ALWAYS_NON_EMPTY`
  - `SyncResult(code: int, lines: list[str])` (frozen)
  - `determine_category(raw: dict) -> str`; `regional_sea_label(slug: str, raw: dict) -> str`; `complexity_of(raw: dict) -> str`
  - `warning_entries(stem, report) -> list[dict[str, str]]`; `warning_sort_key(entry) -> tuple[str, ...]`; `format_warning(entry) -> str`
  - `build_outputs(raw_by_file, *, r_tag, r_commit) -> (dict[str, bytes], list[dict], list[str])`
  - `render_block(r_tag, r_commit, files, accepted) -> str`; `splice_block(md, block) -> str`
  - `sync(*, repo_root, r_root=None, rev=None, from_fixtures=False, check=False, accept_warnings=False) -> SyncResult`
- Settled where the spec was silent: fixture mode refuses `--r-root` / `--rev` (exit 1); warning lines print as `warning (accepted|unaccepted): <format_warning>`; `format_warning` gives `<template>: off_rule_link <from> -> <to>` / `<template>: type_mismatch <text>`; `complexity_of` `str()`-coerces a non-string R value; hash-change lines read `hash <path>: <old or (none)> -> <new>`.

- [ ] **Step 1: Write the failing test file `tests/test_r_template_catalogue.py`**

```python
"""P2 — sespy.r_template_catalogue: the R template sync (spec §3, §4, §8).

Every sync() here runs against a tmp_path copy of the repo files it reads
(tests/parity/ and docs/parity/R_SYNC.md); the R side is a real git repo
built in tmp_path. Nothing touches the working tree.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from sespy import r_template_catalogue as C
from sespy.r_template_mapper import load_r_template
from sespy.regional_seas import get_regional_seas

ROOT = Path(__file__).resolve().parents[1]
PARITY = ROOT / "tests" / "parity"
FIX = PARITY / "r_templates"
RAW = {f: load_r_template(FIX / f) for f in C.TEMPLATE_FILES}
MS = Path(C.OUT_DIR)
LOADER_STUB = b"# stand-in for functions/template_loader.R in the fake R repo\n"
EXPECTED_CATEGORY = {
    "Aquaculture": "Production", "Caribbean": "Multi-Stressor",
    "ClimateChange": "Climate", "Fisheries": "Extraction",
    "OffshoreWind": "Energy", "Pollution": "Pollution", "Tourism": "Recreation",
}
CARIBBEAN = "Caribbean Island - Comprehensive SES Template (MarineSABRES)"


# ---- helpers ------------------------------------------------------------------

def _tree(tmp_path: Path) -> Path:
    """A repo_root holding only what sync() reads: tests/parity/ and R_SYNC.md."""
    root = tmp_path / "repo"
    shutil.copytree(PARITY, root / "tests" / "parity",
                    ignore=shutil.ignore_patterns("__pycache__", "*.py"))
    (root / "docs" / "parity").mkdir(parents=True)
    shutil.copy(ROOT / "docs" / "parity" / "R_SYNC.md", root / "docs" / "parity" / "R_SYNC.md")
    return root


def _snap(root: Path) -> dict[Path, bytes]:
    return {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "core.longpaths=true", "-c", "core.autocrlf=false",
         "-c", "user.name=p2", "-c", "user.email=p2@example.invalid",
         "-c", "commit.gpgsign=false", "-C", str(cwd), *args],
        check=True, capture_output=True, text=True).stdout


def _fake_r(tmp_path: Path, tag: str = "v1.31.0") -> Path:
    """A real git repo whose app lives in a subdirectory (non-empty prefix),
    holding the pinned inputs, committed and tagged. Returns the app dir."""
    outer = tmp_path / "Rrepo"
    app = outer / "MarineSABRES_SES_Shiny"
    (app / "data").mkdir(parents=True)
    (app / "functions").mkdir()
    for f in C.TEMPLATE_FILES:
        (app / "data" / f).write_bytes((FIX / f).read_bytes().replace(b"\r\n", b"\n"))
    rules = PARITY / "r_rules" / "dapsiwrm_connection_rules.R"
    (app / "functions" / "dapsiwrm_connection_rules.R").write_bytes(
        rules.read_bytes().replace(b"\r\n", b"\n"))
    (app / "functions" / "template_loader.R").write_bytes(LOADER_STUB)
    subprocess.run(["git", "-c", "core.longpaths=true", "init", "-q", "--template=", str(outer)],
                   check=True, capture_output=True)
    _git(outer, "add", "-A")
    _git(outer, "commit", "-qm", "r")
    _git(outer, "tag", tag)
    return app


@pytest.fixture(scope="module")
def r_app(tmp_path_factory) -> Path:
    """One untouched fake R repo (tag v1.31.0) shared by the read-only tests;
    tests that add an R release build their own with _fake_r(tmp_path)."""
    return _fake_r(tmp_path_factory.mktemp("r"))


def _r_release(app: Path, tag: str, edit) -> None:
    """Edit one R template in the fake repo and tag the result."""
    edit(app)
    _git(app.parent, "commit", "-qam", tag)
    _git(app.parent, "tag", tag)


def _edit_json(path: Path, change) -> None:
    d = json.loads(path.read_bytes().decode("utf-8-sig"))
    change(d)
    path.write_bytes(json.dumps(d, indent=2, ensure_ascii=False).encode("utf-8"))


def _add_off_rule(d: dict) -> None:
    fw = d["dapsiwrm_framework"]       # Goods & Benefits -> Activities is off-rule
    d["connections"].append({"from_id": fw["goods_benefits"][0]["id"],
                             "to_id": fw["activities"][0]["id"], "polarity": "+"})


def _md_block(root: Path) -> str:
    md = (root / C.MD_PATH).read_bytes().decode("utf-8").replace("\r\n", "\n")
    return md.split(C.BEGIN)[1].split(C.END)[0]


def _md_prose(root: Path) -> tuple[str, str]:
    md = (root / C.MD_PATH).read_bytes().decode("utf-8").replace("\r\n", "\n")
    return md.split(C.BEGIN)[0], md.split(C.END)[1]


def _pin(root: Path) -> dict:
    return json.loads((root / C.PIN_PATH).read_bytes().decode("utf-8"))


# ---- category port (§4) -------------------------------------------------------

@pytest.mark.parametrize("stem", C.STEMS)
def test_category_of_the_seven(stem):
    assert C.determine_category(RAW[f"{stem}_SES_Template.json"]) == EXPECTED_CATEGORY[stem]


@pytest.mark.parametrize("regional_context,want", [
    (None, "General"),                                   # no regional_context
    ({}, "General"),                                     # main_issues absent (NULL)
    ({"main_issues": None}, "General"),
    ({"main_issues": []}, "General"),                    # empty list falls through
    ({"main_issues": "Fisheries decline"}, "Extraction"),  # scalar = one issue
    ({"main_issues": ["a", "b"]}, "Multi-Stressor"),
    ({"main_issues": ["fish stocks"]}, "Extraction"),
    ({"main_issues": ["Coastal TOURISM"]}, "Recreation"),
    ({"main_issues": ["aquaculture"]}, "Production"),
    ({"main_issues": ["pollution"]}, "Pollution"),
    ({"main_issues": ["contamination"]}, "Pollution"),
    ({"main_issues": ["climate"]}, "Climate"),
    ({"main_issues": ["warming"]}, "Climate"),
    ({"main_issues": ["Sea Level rise"]}, "Climate"),
    ({"main_issues": ["wind"]}, "Energy"),
    ({"main_issues": ["energy"]}, "Energy"),
    ({"main_issues": ["wind farm"]}, "Production"),      # R's order: farm before wind
    ({"main_issues": ["fish farm"]}, "Extraction"),      # fish before farm
    ({"main_issues": ["xyz"]}, "General"),
])
def test_category_synthetic(regional_context, want):
    raw = {} if regional_context is None else {"regional_context": regional_context}
    assert C.determine_category(raw) == want


# ---- regional-sea label, complexity (§4) --------------------------------------

def test_regional_sea_label():
    assert C.regional_sea_label("north_sea", {}) == get_regional_seas()["north_sea"]["name"]
    assert C.regional_sea_label("north_sea", {}) == "North Sea"
    assert C.regional_sea_label("kelp_coast", {}) == "Kelp Coast"          # unknown slug
    assert C.regional_sea_label("", {"regional_context": {"region": "Caribbean Sea"}}) \
        == "Caribbean Sea"
    assert C.regional_sea_label("", {"regional_context": {"region": "  "}}) == ""
    assert C.regional_sea_label("", {"regional_context": {"region": ["x"]}}) == ""
    assert C.regional_sea_label("", {}) == ""


@pytest.mark.parametrize("raw,want", [
    ({}, "simple"), ({"complexity": None}, "simple"), ({"complexity": ""}, "simple"),
    ({"complexity": "complex"}, "complex"), ({"complexity": "moderate"}, "moderate"),
])
def test_complexity(raw, want):
    assert C.complexity_of(raw) == want


# ---- build (§3.3 steps 2-5) ---------------------------------------------------

def _build() -> dict[str, bytes]:
    return C.build_outputs(RAW, r_tag="v1.31.0", r_commit="4b53b7d")[0]


def test_build_is_deterministic_lf_and_newline_terminated():
    a, b = _build(), _build()
    assert a == b
    assert set(a) == {f"{C.OUT_DIR}/{f}" for f in C.TEMPLATE_FILES} | {C.CATALOGUE_PATH}
    for data in a.values():
        assert data.endswith(b"}\n") and b"\r" not in data
    cat = a[C.CATALOGUE_PATH]          # spec §3.3 step 5: indent=2, ensure_ascii=False
    assert cat == (json.dumps(json.loads(cat), indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    # The 7 real names are pure ASCII, so only a non-ASCII name can tell the two settings apart.
    raw = {f: json.loads(json.dumps(r)) for f, r in RAW.items()}
    raw["Aquaculture_SES_Template.json"]["template_name"] = "Ålands skärgård"
    cat = C.build_outputs(raw, r_tag="v1.31.0", r_commit="4b53b7d")[0][C.CATALOGUE_PATH]
    assert "Ålands skärgård (MarineSABRES)".encode("utf-8") in cat and b"\\u00c5" not in cat


@pytest.mark.parametrize("fname", C.TEMPLATE_FILES)
def test_shipped_project_metadata(fname):
    md = json.loads(_build()[f"{C.OUT_DIR}/{fname}"])["metadata"]
    raw = RAW[fname]
    assert md["name"] == raw["template_name"] + " (MarineSABRES)"
    assert md["modified_at"] == md["created_at"] == raw["metadata"]["created_date"]
    assert md["min_sespy_version"] == "1.13.0"        # schema floor, not the running version
    assert md["origin"] == "r_template"
    assert md["ecosystem_type"] == ""
    assert md["regional_sea"] == ((raw.get("regional_context") or {}).get("regional_sea") or "")


def test_catalogue_shape():
    cat = json.loads(_build()[C.CATALOGUE_PATH])
    assert (cat["r_tag"], cat["r_commit"]) == ("v1.31.0", "4b53b7d")
    rows = cat["templates"]
    assert [r["name"] for r in rows] == sorted((r["name"] for r in rows), key=str.casefold)
    assert rows[0]["name"] == CARIBBEAN and rows[0]["element_count"] == 78
    for r in rows:
        assert tuple(r) == C.CATALOGUE_KEYS
        for k in C.ALWAYS_NON_EMPTY:
            assert isinstance(r[k], str) and r[k], (r["file"], k)
        assert r["element_count"] > 0 and r["connection_count"] > 0
    by_stem = {r["file"][: -len("_SES_Template.json")]: r for r in rows}
    for s, r in by_stem.items():                                  # §4: straight from R
        raw = RAW[f"{s}_SES_Template.json"]
        assert r["description"] == raw["template_description"], s
        assert r["version"] == str(raw["metadata"]["version"]), s
        assert r["source"] == str(raw["metadata"].get("source") or ""), s
    assert {s: r["category"] for s, r in by_stem.items()} == EXPECTED_CATEGORY
    assert by_stem["Caribbean"]["regional_sea_label"] == "Caribbean Sea"
    assert by_stem["OffshoreWind"]["regional_sea_label"] == "North Sea"
    assert by_stem["OffshoreWind"]["complexity"] == "complex"
    assert [s for s, r in by_stem.items() if r["usage_notes"]] == ["Caribbean"]
    assert [s for s, r in by_stem.items() if r["element_count"] == 23] == ["OffshoreWind"]
    assert by_stem["Aquaculture"]["name"] == "Coastal Lagoon (MarineSABRES)"
    assert sum(r["connection_count"] for r in rows) == 320


def test_catalogue_sort_is_case_insensitive():
    raw = {f: json.loads(json.dumps(r)) for f, r in RAW.items()}
    raw["Aquaculture_SES_Template.json"]["template_name"] = "coastal lagoon"
    cat = json.loads(C.build_outputs(raw, r_tag="v1.31.0", r_commit="4b53b7d")[0][C.CATALOGUE_PATH])
    # A case-sensitive sort would put "coastal" after "Tourism".
    assert [r["name"] for r in cat["templates"]][2] == "coastal lagoon (MarineSABRES)"


def test_render_block_golden():
    files = {"tests/parity/r_templates/b.json": "2" * 64, "tests/parity/r_rules/a.R": "1" * 64}
    assert C.render_block("v1.31.0", "4b53b7d", files, []) == (
        "- **R release:** MarineSABRES_SES_Shiny **v1.31.0**, commit `4b53b7d`.\n"
        "\n"
        "| File | Hash |\n"
        "|---|---|\n"
        f"| `tests/parity/r_rules/a.R` | `{'1' * 64}` |\n"
        f"| `tests/parity/r_templates/b.json` | `{'2' * 64}` |\n"
        "\n"
        "**Accepted sync warnings:** none.")
    accepted = [{"template": "Tourism_SES_Template", "kind": "off_rule_link",
                 "from": "GB001", "to": "A001"},
                {"template": "Tourism_SES_Template", "kind": "type_mismatch",
                 "text": "connections[0] x"}]
    assert C.render_block("v1.31.0", "4b53b7d", files, accepted).endswith(
        "\n\n**Accepted sync warnings:**\n"
        "- Tourism_SES_Template: off_rule_link GB001 -> A001\n"
        "- Tourism_SES_Template: type_mismatch connections[0] x")


def test_warning_sort_key_literal_order():
    a = {"template": "A", "kind": "type_mismatch", "text": "z"}
    b = {"template": "B", "kind": "off_rule_link", "from": "X", "to": "Y"}
    c = {"template": "B", "kind": "off_rule_link"}                 # missing from/to sort as ""
    d = {"template": "B", "kind": "off_rule_link", "from": "X", "to": "W"}
    e = {"template": "B", "kind": "type_mismatch", "text": "a"}
    assert sorted([e, b, d, c, a], key=C.warning_sort_key) == [a, c, d, b, e]


# ---- fixture mode (§3.1, §3.3 step 7) -----------------------------------------

def test_fixture_mode_writes_projects_and_catalogue_only(tmp_path):
    root = _tree(tmp_path)
    before = _snap(root)
    res = C.sync(repo_root=root, from_fixtures=True)
    assert res.code == 0, res.lines
    changed = {p.relative_to(root).as_posix() for p, b in _snap(root).items()
               if before.get(p) != b}
    assert changed == {f"{C.OUT_DIR}/{f}" for f in C.TEMPLATE_FILES} | {C.CATALOGUE_PATH}
    pin = _pin(root)
    cat = json.loads((root / C.CATALOGUE_PATH).read_bytes())
    assert (cat["r_tag"], cat["r_commit"]) == (pin["r_tag"], pin["r_commit"])
    for p in (root / MS).glob("*.json"):
        assert b"\r\n" not in p.read_bytes()                  # LF on disk
    assert sum(line.startswith("wrote ") for line in res.lines) == 8


def test_check_passes_on_a_crlf_copy(tmp_path):
    root = _tree(tmp_path)
    assert C.sync(repo_root=root, from_fixtures=True).code == 0
    for p in (root / MS).glob("*.json"):
        p.write_bytes(p.read_bytes().replace(b"\n", b"\r\n"))
    res = C.sync(repo_root=root, from_fixtures=True, check=True)
    assert res.code == 0, res.lines


def test_check_reports_drift_and_writes_nothing(tmp_path):
    root = _tree(tmp_path)
    assert C.sync(repo_root=root, from_fixtures=True).code == 0
    _edit_json(root / MS / "Tourism_SES_Template.json",
               lambda d: d["metadata"].update(name="edited"))
    before = _snap(root)
    res = C.sync(repo_root=root, from_fixtures=True, check=True)
    assert res.code == 1
    assert res.lines == [f"differs: {C.OUT_DIR}/Tourism_SES_Template.json"]
    assert _snap(root) == before


def test_check_reports_missing_outputs(tmp_path):
    res = C.sync(repo_root=_tree(tmp_path), from_fixtures=True, check=True)
    assert res.code == 1 and len(res.lines) == 8          # 7 projects + catalogue


def test_value_error_writes_nothing(tmp_path):
    root = _tree(tmp_path)
    _edit_json(root / "tests/parity/r_templates/Tourism_SES_Template.json",
               lambda d: d["dapsiwrm_framework"]["drivers"].append(
                   dict(d["dapsiwrm_framework"]["drivers"][0])))     # duplicate id
    before = _snap(root)
    res = C.sync(repo_root=root, from_fixtures=True)
    assert res.code == 1 and _snap(root) == before
    assert "Tourism_SES_Template" in res.lines[-1] and "duplicate element id" in res.lines[-1]


@pytest.mark.parametrize("change,line", [
    (lambda d: d["metadata"].update(version=""), "Fisheries_SES_Template.json: empty version"),
    (lambda d: d.update(template_description=""), "Fisheries_SES_Template.json: empty description"),
    (lambda d: d.update(connections=[]), "Fisheries_SES_Template.json: connection_count is 0"),
])
def test_empty_always_non_empty_field_writes_nothing(tmp_path, change, line):
    root = _tree(tmp_path)
    _edit_json(root / "tests/parity/r_templates/Fisheries_SES_Template.json", change)
    before = _snap(root)
    res = C.sync(repo_root=root, from_fixtures=True)
    assert res.code == 1 and line in res.lines and _snap(root) == before


def test_off_rule_link_in_fixture_mode_fails_and_cannot_be_accepted(tmp_path):
    root = _tree(tmp_path)
    _edit_json(root / "tests/parity/r_templates/Tourism_SES_Template.json", _add_off_rule)
    before = _snap(root)
    res = C.sync(repo_root=root, from_fixtures=True)
    assert res.code == 1 and _snap(root) == before
    assert any(line.startswith("warning (unaccepted): Tourism_SES_Template: off_rule_link ")
               for line in res.lines)
    res = C.sync(repo_root=root, from_fixtures=True, accept_warnings=True)
    assert res.code == 1 and _snap(root) == before


@pytest.mark.parametrize("pin", [
    {"files": {}}, {"r_tag": "", "r_commit": "x"}, [],
    {"r_tag": "v1.31.0", "r_commit": "4b53b7d", "files": []},
    {"r_tag": "v1.31.0", "r_commit": "4b53b7d", "files": {}, "accepted_warnings": "x"},
])
def test_malformed_pin_exits_1_and_writes_nothing(tmp_path, pin):
    root = _tree(tmp_path)
    (root / C.PIN_PATH).write_bytes(json.dumps(pin).encode("utf-8"))
    before = _snap(root)
    res = C.sync(repo_root=root, from_fixtures=True)
    assert res.code == 1 and "r_tag and r_commit" in res.lines[0] and _snap(root) == before


def test_non_object_template_exits_1_and_writes_nothing(tmp_path):
    root = _tree(tmp_path)
    (root / "tests/parity/r_templates/Tourism_SES_Template.json").write_bytes(b"[1, 2]")
    before = _snap(root)
    res = C.sync(repo_root=root, from_fixtures=True)
    assert res.code == 1 and res.lines[-1].startswith("conversion failed: ") and _snap(root) == before


@pytest.mark.parametrize("kwargs", [
    {},                                                    # neither r_root nor fixtures
    {"from_fixtures": True, "accept_warnings": True},
    {"from_fixtures": True, "rev": "v1.31.0"},
])
def test_argument_errors_write_nothing(tmp_path, kwargs):
    root = _tree(tmp_path)
    before = _snap(root)
    assert C.sync(repo_root=root, **kwargs).code == 1
    assert _snap(root) == before


# ---- git mode against a fake R repo (§3.1, §3.3, §8) --------------------------

def test_real_run_writes_everything_then_checks_clean(tmp_path, r_app):
    root, app = _tree(tmp_path), r_app
    prose_before = _md_prose(root)
    res = C.sync(repo_root=root, r_root=app, rev="v1.31.0")
    assert res.code == 0, res.lines
    pin = _pin(root)
    commit = _git(app, "rev-parse", "--short=7", "v1.31.0^{commit}").strip()
    assert (pin["r_tag"], pin["r_commit"]) == ("v1.31.0", commit)
    assert sorted(pin["files"]) == sorted(C.INPUTS.values()) and len(pin["files"]) == 9
    assert pin["accepted_warnings"] == []
    assert any(line.startswith("hash tests/parity/r_source/template_loader.R: ")
               for line in res.lines)
    assert (root / "tests/parity/r_source/template_loader.R").read_bytes() == LOADER_STUB
    # The block is exactly the generated text; the prose around it is untouched.
    assert _md_block(root) == "\n" + C.render_block("v1.31.0", commit, pin["files"], []) + "\n"
    assert _md_prose(root) == prose_before
    md = (root / C.MD_PATH).read_text(encoding="utf-8")
    assert set(re.findall(r"\b[0-9a-f]{64}\b", md)) == set(pin["files"].values())
    assert "**Accepted sync warnings:** none." in _md_block(root)
    for rel in [C.PIN_PATH, C.MD_PATH, *C.INPUTS.values()]:
        assert b"\r\n" not in (root / rel).read_bytes(), rel
    # Clean afterwards: explicit rev, rev from the new pin, and fixture mode.
    assert C.sync(repo_root=root, r_root=app, rev="v1.31.0", check=True).code == 0
    assert C.sync(repo_root=root, r_root=app, check=True).code == 0
    assert C.sync(repo_root=root, from_fixtures=True, check=True).code == 0


def test_check_in_git_mode_passes_on_a_crlf_copy(tmp_path, r_app):
    root, app = _tree(tmp_path), r_app
    assert C.sync(repo_root=root, r_root=app, rev="v1.31.0").code == 0
    for p in root.rglob("*"):
        if p.is_file():
            p.write_bytes(p.read_bytes().replace(b"\n", b"\r\n"))
    res = C.sync(repo_root=root, r_root=app, rev="v1.31.0", check=True)
    assert res.code == 0, res.lines


@pytest.mark.parametrize("rev", ["main", "HEAD", "v1.31", "1.31.0", "v1.31.0-rc1", "v1.31.0\n"])
def test_rev_must_be_a_release_tag(tmp_path, r_app, rev):
    root, app = _tree(tmp_path), r_app
    before = _snap(root)
    res = C.sync(repo_root=root, r_root=app, rev=rev)
    assert res.code == 1 and "release tag" in res.lines[0] and _snap(root) == before


def test_unknown_tag_and_missing_path_write_nothing(tmp_path):
    root, app = _tree(tmp_path), _fake_r(tmp_path)
    before = _snap(root)
    assert C.sync(repo_root=root, r_root=app, rev="v9.9.9").code == 1
    _git(app.parent, "rm", "-q", "MarineSABRES_SES_Shiny/data/Tourism_SES_Template.json")
    _git(app.parent, "commit", "-qm", "drop Tourism")
    _git(app.parent, "tag", "v1.32.0")
    res = C.sync(repo_root=root, r_root=app, rev="v1.32.0")
    assert res.code == 1 and "data/Tourism_SES_Template.json" in res.lines[0]
    assert _snap(root) == before


@pytest.mark.parametrize("md", [
    "no markers\n",
    f"{C.BEGIN}\n{C.BEGIN}\n{C.END}\n",
    f"{C.BEGIN}\n{C.END}\n{C.END}\n",
    f"{C.END}\n{C.BEGIN}\n",
    None,                                               # R_SYNC.md missing
])
def test_markers_missing_or_duplicated_write_nothing(tmp_path, r_app, md):
    root, app = _tree(tmp_path), r_app
    if md is None:
        (root / C.MD_PATH).unlink()
    else:
        (root / C.MD_PATH).write_bytes(md.encode("utf-8"))
    before = _snap(root)
    res = C.sync(repo_root=root, r_root=app, rev="v1.31.0")
    assert res.code == 1 and _snap(root) == before


def test_off_rule_link_needs_accept_warnings_and_is_persisted(tmp_path):
    root, app = _tree(tmp_path), _fake_r(tmp_path)
    tourism = app / "data" / "Tourism_SES_Template.json"
    _r_release(app, "v1.32.0", lambda a: _edit_json(tourism, _add_off_rule))
    fw = json.loads(tourism.read_bytes())["dapsiwrm_framework"]
    gb, act = fw["goods_benefits"][0]["id"], fw["activities"][0]["id"]
    entry = {"template": "Tourism_SES_Template", "kind": "off_rule_link", "from": gb, "to": act}

    before = _snap(root)
    res = C.sync(repo_root=root, r_root=app, rev="v1.32.0")
    assert res.code == 1 and _snap(root) == before
    assert f"warning (unaccepted): Tourism_SES_Template: off_rule_link {gb} -> {act}" in res.lines

    fixture = "tests/parity/r_templates/Tourism_SES_Template.json"
    old_hash = _pin(root)["files"][fixture]
    res = C.sync(repo_root=root, r_root=app, rev="v1.32.0", accept_warnings=True)
    assert res.code == 0, res.lines
    assert _pin(root)["accepted_warnings"] == [entry]
    new_hash = _pin(root)["files"][fixture]
    assert old_hash != new_hash
    assert f"hash {fixture}: {old_hash} -> {new_hash}" in res.lines      # §3.1 old -> new
    assert _md_block(root).endswith(
        f"**Accepted sync warnings:**\n- Tourism_SES_Template: off_rule_link {gb} -> {act}\n")
    # Accepted from now on, without the flag, in both modes.
    assert C.sync(repo_root=root, r_root=app, check=True).code == 0
    assert C.sync(repo_root=root, from_fixtures=True, check=True).code == 0
    assert C.sync(repo_root=root, r_root=app, rev="v1.32.0").code == 0


def test_type_mismatch_entries_and_sort_order(tmp_path):
    root, app = _tree(tmp_path), _fake_r(tmp_path)
    fisheries = app / "data" / "Fisheries_SES_Template.json"
    tourism = app / "data" / "Tourism_SES_Template.json"

    def edit(a):
        _edit_json(tourism, _add_off_rule)
        _edit_json(fisheries, lambda d: d["connections"][0].update(to_type="welfare"))
    _r_release(app, "v1.32.0", edit)
    res = C.sync(repo_root=root, r_root=app, rev="v1.32.0", accept_warnings=True)
    assert res.code == 0, res.lines
    acc = _pin(root)["accepted_warnings"]
    assert [(w["template"], w["kind"]) for w in acc] == [
        ("Fisheries_SES_Template", "type_mismatch"),
        ("Tourism_SES_Template", "off_rule_link")]
    assert set(acc[0]) == {"template", "kind", "text"}
    assert acc[0]["text"].startswith("connections[0] ") and "to_type 'welfare'" in acc[0]["text"]


def test_persisted_warnings_are_sorted_not_in_production_order(tmp_path):
    # The mapper reports in connection order: GB002 first, then GB001, then
    # the type mismatch on connections[0]. The pin must hold the
    # (template, kind, from, to, text) order instead.
    root, app = _tree(tmp_path), _fake_r(tmp_path)
    tourism = app / "data" / "Tourism_SES_Template.json"

    def edit_tourism(d):
        fw = d["dapsiwrm_framework"]
        for gb in (fw["goods_benefits"][1], fw["goods_benefits"][0]):
            d["connections"].append({"from_id": gb["id"], "to_id": fw["activities"][0]["id"],
                                     "polarity": "+"})
        d["connections"][0]["to_type"] = "welfare"
    _r_release(app, "v1.32.0", lambda a: _edit_json(tourism, edit_tourism))
    fw = json.loads(tourism.read_bytes())["dapsiwrm_framework"]
    gb1, gb2 = fw["goods_benefits"][0]["id"], fw["goods_benefits"][1]["id"]
    act = fw["activities"][0]["id"]
    assert gb1 < gb2
    res = C.sync(repo_root=root, r_root=app, rev="v1.32.0", accept_warnings=True)
    assert res.code == 0, res.lines
    acc = _pin(root)["accepted_warnings"]
    assert [(w["kind"], w.get("from"), w.get("to")) for w in acc] == [
        ("off_rule_link", gb1, act), ("off_rule_link", gb2, act), ("type_mismatch", None, None)]


@pytest.mark.parametrize("variant", ["other_template", "other_to", "extra_key"])
def test_accepted_warning_matches_only_on_every_field(tmp_path, variant):
    root, app = _tree(tmp_path), _fake_r(tmp_path)
    tourism = app / "data" / "Tourism_SES_Template.json"
    _r_release(app, "v1.32.0", lambda a: _edit_json(tourism, _add_off_rule))
    fw = json.loads(tourism.read_bytes())["dapsiwrm_framework"]
    entry = {"template": "Tourism_SES_Template", "kind": "off_rule_link",
             "from": fw["goods_benefits"][0]["id"], "to": fw["activities"][0]["id"]}
    if variant == "other_template":
        entry["template"] = "Fisheries_SES_Template"       # ids like A001 repeat across templates
    elif variant == "other_to":
        entry["to"] = fw["activities"][1]["id"]
    else:
        entry["note"] = "x"
    pin = _pin(root)
    pin["accepted_warnings"] = [entry]
    (root / C.PIN_PATH).write_bytes(json.dumps(pin, indent=2).encode("utf-8"))
    before = _snap(root)
    res = C.sync(repo_root=root, r_root=app, rev="v1.32.0")
    assert res.code == 1 and _snap(root) == before


def test_accepted_warning_that_no_longer_occurs_is_dropped(tmp_path, r_app):
    root, app = _tree(tmp_path), r_app
    assert C.sync(repo_root=root, r_root=app, rev="v1.31.0").code == 0     # clean baseline
    pin = _pin(root)
    pin["accepted_warnings"] = [{"template": "Tourism_SES_Template", "kind": "off_rule_link",
                                 "from": "GB01", "to": "A01"}]
    (root / C.PIN_PATH).write_bytes(json.dumps(pin, indent=2).encode("utf-8"))
    res = C.sync(repo_root=root, r_root=app, rev="v1.31.0", check=True)
    assert res.code == 1 and res.lines == [f"differs: {C.PIN_PATH}"]      # only the stale entry
    res = C.sync(repo_root=root, r_root=app, rev="v1.31.0")
    assert res.code == 0, res.lines
    assert _pin(root)["accepted_warnings"] == []
    assert "**Accepted sync warnings:** none." in _md_block(root)


# ---- CLI wrapper (§3.1) --------------------------------------------------------

def test_cli_passes_arguments_and_the_repo_root(monkeypatch, capsys):
    from scripts import sync_r_templates as cli
    seen = {}

    def fake_sync(**kw):
        seen.update(kw)
        return C.SyncResult(3, ["line one", "line two"])
    monkeypatch.setattr(cli, "sync", fake_sync)
    code = cli.main(["--r-root", "R", "--rev", "v1.31.0", "--check", "--accept-warnings"])
    assert code == 3 and capsys.readouterr().out == "line one\nline two\n"
    assert seen == {"repo_root": ROOT, "r_root": Path("R"), "rev": "v1.31.0",
                    "from_fixtures": False, "check": True, "accept_warnings": True}


def test_cli_runs_as_a_module_from_the_repo_root():
    # Refused before any read or write; --check as a second guard, so even a
    # broken refusal can never write into the real tree.
    r = subprocess.run([sys.executable, "-m", "scripts.sync_r_templates",
                        "--from-fixtures", "--accept-warnings", "--check"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 1 and "--accept-warnings needs --r-root" in r.stdout


def test_catalogue_module_imports_without_shiny():
    code = "import sys, sespy.r_template_catalogue; sys.exit(1 if 'shiny' in sys.modules else 0)"
    assert subprocess.run([sys.executable, "-c", code], cwd=ROOT).returncode == 0
```

(The fake R repo's `template_loader.R` is a stub: the sync only copies and hashes it; the real file and its content-parity test arrive in Task 5. `_tree` copies whatever `tests/parity/` holds, so these tests pass both before and after Task 5's re-pin.)

- [ ] **Step 2: Run — RED**

`micromamba run -n shiny python -m pytest tests/test_r_template_catalogue.py -q` → collection error `ImportError: cannot import name 'r_template_catalogue' from 'sespy'` (the test imports `from sespy import r_template_catalogue as C`).

- [ ] **Step 3: Create `sespy/r_template_catalogue.py`**

```python
"""Build SESPy's MarineSABRES template gallery from R's curated templates (P2).

`sync()` reads the 7 R `*_SES_Template.json` files (from an R git checkout
with `git show`, or from the pinned fixtures under tests/parity/), converts
them with P1a's mapper, and produces the shipped projects and
`catalogue.json` under sespy/templates/marinesabres/. When it reads from R it
also produces the fixtures, the pin (tests/parity/r_sync.json) and the
generated block of docs/parity/R_SYNC.md. Everything is built in memory
first: any failure writes nothing.

Every SESPy data file is read and written under `repo_root`, so tests point
it at a tmp_path copy; code and constants (the mapper, regional_seas.json)
come from the imported package. Shiny-free, no clock, no logging: the caller
prints `SyncResult.lines`.

R reference: functions/template_loader.R:359-371 (v1.31.0) for the category
rule (ported in `determine_category`, guarded by
tests/parity/test_r_category_parity.py).
"""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .r_sync import sha256_norm, sha256_text_norm
from .r_template_mapper import ConversionReport, convert_r_template
from .regional_seas import get_regional_seas

STEMS = ("Aquaculture", "Caribbean", "ClimateChange", "Fisheries",
         "OffshoreWind", "Pollution", "Tourism")
TEMPLATE_FILES = tuple(f"{s}_SES_Template.json" for s in STEMS)
SUFFIX = " (MarineSABRES)"
OUT_DIR = "sespy/templates/marinesabres"
CATALOGUE_PATH = f"{OUT_DIR}/catalogue.json"
PIN_PATH = "tests/parity/r_sync.json"
MD_PATH = "docs/parity/R_SYNC.md"
BEGIN, END = "<!-- r-sync:begin -->", "<!-- r-sync:end -->"
TAG_RE = re.compile(r"^v\d+\.\d+\.\d+$")

# R app path -> fixture path under repo_root (spec §3.2, §3.3 step 6). A
# template added or removed in R is a deliberate change to this list.
INPUTS: dict[str, str] = {
    **{f"data/{f}": f"tests/parity/r_templates/{f}" for f in TEMPLATE_FILES},
    "functions/dapsiwrm_connection_rules.R": "tests/parity/r_rules/dapsiwrm_connection_rules.R",
    "functions/template_loader.R": "tests/parity/r_source/template_loader.R",
}

# Port of R's .determine_template_category, in R's order (first match wins).
CATEGORY_NULL = "General"          # main_issues is NULL
CATEGORY_MULTI = "Multi-Stressor"  # more than one issue
CATEGORY_FALLBACK = "General"      # no rule matched
CATEGORY_RULES: tuple[tuple[str, str], ...] = (
    ("fish", "Extraction"),
    ("touris", "Recreation"),
    ("aqua|farm", "Production"),
    ("pollut|contamin", "Pollution"),
    ("climat|warm|sea level", "Climate"),
    ("wind|energy", "Energy"),
)
DEFAULT_COMPLEXITY = "simple"      # R's stated default

CATALOGUE_KEYS = ("file", "name", "description", "category", "complexity",
                  "version", "regional_sea_label", "source", "usage_notes",
                  "element_count", "connection_count")
ALWAYS_NON_EMPTY = ("file", "name", "description", "category", "complexity",
                    "version")
_WARNING_SORT_FIELDS = ("template", "kind", "from", "to", "text")


@dataclass(frozen=True)
class SyncResult:
    code: int
    lines: list[str] = field(default_factory=list)


# ---- catalogue fields (spec §4) -------------------------------------------

def determine_category(raw: dict) -> str:
    """R `.determine_template_category`: NULL main_issues -> General; more
    than one issue -> Multi-Stressor; else the first matching rule
    (unanchored, case-insensitive); else General. A scalar counts as one
    issue; an empty list falls through to General."""
    rc = raw.get("regional_context")
    issues = rc.get("main_issues") if isinstance(rc, dict) else None
    if issues is None:
        return CATEGORY_NULL
    if not isinstance(issues, list):
        issues = [issues]
    if len(issues) > 1:
        return CATEGORY_MULTI
    for pattern, category in CATEGORY_RULES:
        if any(re.search(pattern, str(i), re.IGNORECASE) for i in issues):
            return category
    return CATEGORY_FALLBACK


def regional_sea_label(slug: str, raw: dict) -> str:
    """Display label for a card: the regional-seas name for a known slug, an
    unknown slug title-cased, else R's `regional_context.region` text."""
    if slug:
        seas = get_regional_seas()
        if slug in seas:
            return seas[slug]["name"]
        return slug.replace("_", " ").title()
    rc = raw.get("regional_context")
    region = rc.get("region") if isinstance(rc, dict) else None
    return region if isinstance(region, str) and region.strip() else ""


def complexity_of(raw: dict) -> str:
    """R `complexity`; absent, null or "" -> "simple"."""
    value = raw.get("complexity")
    return DEFAULT_COMPLEXITY if value is None or value == "" else str(value)


def _text(value: Any) -> str:
    return "" if value is None else str(value)


# ---- warnings ---------------------------------------------------------------

def warning_entries(stem: str, report: ConversionReport) -> list[dict[str, str]]:
    """One entry per off-rule link / type mismatch, scoped to the template
    (ids like D001 repeat across templates)."""
    out = [{"template": stem, "kind": "off_rule_link", "from": a, "to": b}
           for a, b in report.off_rule_links]
    out += [{"template": stem, "kind": "type_mismatch", "text": m}
            for m in report.type_mismatches]
    return out


def warning_sort_key(entry: dict) -> tuple[str, ...]:
    return tuple(str(entry.get(k, "")) for k in _WARNING_SORT_FIELDS)


def format_warning(entry: dict) -> str:
    if entry.get("kind") == "off_rule_link":
        return f"{entry['template']}: off_rule_link {entry['from']} -> {entry['to']}"
    return f"{entry.get('template')}: {entry.get('kind')} {entry.get('text', '')}"


# ---- build (pure) -----------------------------------------------------------

def build_outputs(raw_by_file: dict[str, dict], *, r_tag: str, r_commit: str
                  ) -> tuple[dict[str, bytes], list[dict[str, str]], list[str]]:
    """Convert the 7 templates and build the catalogue, in memory.

    Returns (outputs {repo-relative path: bytes}, warning entries, errors).
    A mapper ValueError propagates; errors lists empty always-non-empty
    catalogue fields."""
    outputs: dict[str, bytes] = {}
    warnings: list[dict[str, str]] = []
    entries: list[dict[str, Any]] = []
    for fname in TEMPLATE_FILES:
        raw = raw_by_file[fname]
        stem = fname[: -len(".json")]
        project, report = convert_r_template(raw, key=stem)
        warnings += warning_entries(stem, report)
        md = project.metadata
        md.name = md.name + SUFFIX      # the mapper already applied R's fallbacks
        # to_json, never project_to_bytes/save_project_atomic: those stamp
        # modified_at with the clock. LF only; write_bytes, never write_text.
        outputs[f"{OUT_DIR}/{fname}"] = (project.to_json() + "\n").encode("utf-8")
        meta = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
        entries.append({
            "file": fname,
            "name": md.name,
            "description": md.description,
            "category": determine_category(raw),
            "complexity": complexity_of(raw),
            "version": md.r_template_version,
            "regional_sea_label": regional_sea_label(md.regional_sea, raw),
            "source": _text(meta.get("source")),
            "usage_notes": _text(raw.get("usage_notes")),
            "element_count": project.isa_data.element_count(),
            "connection_count": project.isa_data.connection_count(),
        })
    errors: list[str] = []
    for e in entries:
        errors += [f"{e['file']}: empty {k}" for k in ALWAYS_NON_EMPTY if not e[k]]
        errors += [f"{e['file']}: {k} is 0" for k in ("element_count", "connection_count")
                   if e[k] <= 0]
    entries.sort(key=lambda e: e["name"].casefold())
    catalogue = {"r_tag": r_tag, "r_commit": r_commit, "templates": entries}
    outputs[CATALOGUE_PATH] = (
        json.dumps(catalogue, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    return outputs, warnings, errors


def render_block(r_tag: str, r_commit: str, files: dict[str, str],
                 accepted: list[dict]) -> str:
    """The generated R_SYNC.md block (without the surrounding newlines)."""
    rows = "\n".join(f"| `{p}` | `{h}` |" for p, h in sorted(files.items()))
    if accepted:
        tail = "**Accepted sync warnings:**\n" + "\n".join(
            f"- {format_warning(w)}" for w in accepted)
    else:
        tail = "**Accepted sync warnings:** none."
    return (f"- **R release:** MarineSABRES_SES_Shiny **{r_tag}**, commit `{r_commit}`.\n"
            f"\n| File | Hash |\n|---|---|\n{rows}\n\n{tail}")


def splice_block(md: str, block: str) -> str:
    """Replace everything between the markers with "\\n" + block + "\\n".
    Raises ValueError unless there is exactly one BEGIN before one END."""
    md = md.replace("\r\n", "\n")
    if md.count(BEGIN) != 1 or md.count(END) != 1 or md.index(BEGIN) > md.index(END):
        raise ValueError(f"{MD_PATH}: needs exactly one {BEGIN} before one {END}")
    start = md.index(BEGIN) + len(BEGIN)
    return md[:start] + "\n" + block + "\n" + md[md.index(END):]


# ---- I/O ----------------------------------------------------------------------

def _git(r_root: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-c", "core.longpaths=true", "-C", str(r_root), *args],
        check=True, capture_output=True).stdout


def _hash(rel: str, data: bytes) -> str:
    text = data.decode("utf-8-sig")
    return sha256_norm(json.loads(text)) if rel.endswith(".json") else sha256_text_norm(text)


def _same(path: Path, data: bytes) -> bool:
    """--check comparison: JSON parsed, text with CRLF -> LF."""
    if not path.is_file():
        return False
    disk = path.read_bytes().decode("utf-8-sig")
    new = data.decode("utf-8-sig")
    if path.suffix == ".json":
        try:
            return json.loads(disk) == json.loads(new)
        except ValueError:
            return False
    return disk.replace("\r\n", "\n") == new.replace("\r\n", "\n")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_bytes().decode("utf-8-sig"))


def sync(*, repo_root: Path, r_root: Path | None = None, rev: str | None = None,
         from_fixtures: bool = False, check: bool = False,
         accept_warnings: bool = False) -> SyncResult:
    """Spec §3.3. Exit code 0 = written (or, with check, no drift)."""
    repo_root = Path(repo_root)
    if from_fixtures and accept_warnings:
        return SyncResult(1, ["--accept-warnings needs --r-root: fixture mode never "
                              "writes tests/parity/r_sync.json, so the acceptance would be lost"])
    if from_fixtures and (r_root is not None or rev is not None):
        return SyncResult(1, ["--from-fixtures takes neither --r-root nor --rev"])
    if not from_fixtures and r_root is None:
        return SyncResult(1, ["--r-root is required unless --from-fixtures"])
    try:
        pin_old = _read_json(repo_root / PIN_PATH)
    except (OSError, ValueError) as e:
        return SyncResult(1, [f"cannot read {PIN_PATH}: {e}"])
    if not (isinstance(pin_old, dict)
            and all(isinstance(pin_old.get(k), str) and pin_old[k] for k in ("r_tag", "r_commit"))
            and isinstance(pin_old.get("files", {}), dict)
            and isinstance(pin_old.get("accepted_warnings", []), list)
            and all(isinstance(w, dict) for w in pin_old.get("accepted_warnings", []))):
        return SyncResult(1, [f"{PIN_PATH}: needs non-empty string r_tag and r_commit, "
                              "a files object and an accepted_warnings list of objects"])
    accepted_old = list(pin_old.get("accepted_warnings", []))

    raw_bytes: dict[str, bytes] = {}
    if from_fixtures:
        r_tag, r_commit = pin_old["r_tag"], pin_old["r_commit"]
        for r_path, fixture in INPUTS.items():
            if r_path.startswith("data/"):
                try:
                    raw_bytes[r_path] = (repo_root / fixture).read_bytes()
                except OSError as e:
                    return SyncResult(1, [f"cannot read {fixture}: {e}"])
    else:
        r_tag = rev or pin_old["r_tag"]
        if not TAG_RE.fullmatch(r_tag):        # fullmatch: "$" alone accepts a trailing "\n"
            return SyncResult(1, [f"--rev must be a release tag like v1.31.0, got {r_tag!r}"])
        try:
            prefix = _git(r_root, "rev-parse", "--show-prefix").decode().strip()
            r_commit = _git(r_root, "rev-parse", "--short=7", f"{r_tag}^{{commit}}").decode().strip()
        except (subprocess.CalledProcessError, OSError) as e:
            detail = e.stderr.decode(errors="replace").strip() if isinstance(
                e, subprocess.CalledProcessError) else str(e)
            return SyncResult(1, [f"git failed for {r_tag}: {detail}"])
        for r_path in INPUTS:
            try:
                raw_bytes[r_path] = _git(r_root, "show", f"{r_tag}:{prefix}{r_path}")
            except subprocess.CalledProcessError as e:
                return SyncResult(1, [f"git show {r_tag}:{prefix}{r_path} failed: "
                                      f"{e.stderr.decode(errors='replace').strip()}"])

    try:
        raw_by_file = {f: json.loads(raw_bytes[f"data/{f}"].decode("utf-8-sig"))
                       for f in TEMPLATE_FILES}
        outputs, warnings, errors = build_outputs(raw_by_file, r_tag=r_tag, r_commit=r_commit)
    except (ValueError, KeyError, TypeError, AttributeError) as e:
        # JSON or mapper error, or a template that is not the expected shape
        # (e.g. not an object): exit 1, never a traceback.
        return SyncResult(1, [f"conversion failed: {type(e).__name__}: {e}"])

    lines: list[str] = []
    unaccepted = [w for w in warnings if w not in accepted_old]
    for w in warnings:
        state = "unaccepted" if w in unaccepted and not accept_warnings else "accepted"
        lines.append(f"warning ({state}): {format_warning(w)}")
    if unaccepted and not accept_warnings:
        errors.append(f"{len(unaccepted)} unaccepted warning(s); review them, "
                      "then rerun with --accept-warnings")
    if errors:
        return SyncResult(1, lines + errors)

    if not from_fixtures:
        files: dict[str, str] = {}
        for r_path, fixture in INPUTS.items():
            outputs[fixture] = raw_bytes[r_path]            # raw bytes as read
            files[fixture] = _hash(fixture, raw_bytes[r_path])
            old = pin_old.get("files", {}).get(fixture)
            if old != files[fixture]:
                lines.append(f"hash {fixture}: {old or '(none)'} -> {files[fixture]}")
        accepted_new: list[dict] = []
        for w in sorted(warnings, key=warning_sort_key):
            if w not in accepted_new:
                accepted_new.append(w)
        pin_new = {"r_tag": r_tag, "r_commit": r_commit,
                   "files": dict(sorted(files.items())),
                   "accepted_warnings": accepted_new}
        outputs[PIN_PATH] = (json.dumps(pin_new, indent=2, ensure_ascii=False)
                             + "\n").encode("utf-8")
        try:
            md_old = (repo_root / MD_PATH).read_bytes().decode("utf-8-sig")
            md_new = splice_block(md_old, render_block(r_tag, r_commit, files, accepted_new))
        except (OSError, ValueError) as e:
            return SyncResult(1, lines + [str(e)])
        outputs[MD_PATH] = md_new.encode("utf-8")

    if check:
        differing = [p for p, data in outputs.items() if not _same(repo_root / p, data)]
        lines += [f"differs: {p}" for p in differing]
        return SyncResult(1 if differing else 0, lines)
    for p, data in outputs.items():
        dst = repo_root / p
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(data)
        lines.append(f"wrote {p}")
    return SyncResult(0, lines)
```

- [ ] **Step 4: Create `scripts/__init__.py`**

```python
"""Developer scripts, run from the repo root as `python -m scripts.<name>`."""
```

- [ ] **Step 5: Create `scripts/sync_r_templates.py`**

```python
"""Sync SESPy's MarineSABRES gallery with R's curated templates (P2).

Run from the SESPy repo root (so `-m` imports this checkout's `sespy`):

    micromamba run -n shiny python -m scripts.sync_r_templates --r-root <R app dir>
        [--rev vX.Y.Z] [--check] [--accept-warnings]
    micromamba run -n shiny python -m scripts.sync_r_templates --from-fixtures [--check]

<R app dir> is .../SESToolbox/MarineSABRES_SES_Shiny. The R repo is only read
with `git show`; it is never checked out, switched or stashed. All logic
lives in sespy.r_template_catalogue.sync(); this is a thin wrapper.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sespy.r_template_catalogue import sync

REPO_ROOT = Path(__file__).resolve().parents[1]   # the directory holding scripts/


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m scripts.sync_r_templates",
                                 description=__doc__.splitlines()[0])
    ap.add_argument("--r-root", type=Path, help="the R app directory (MarineSABRES_SES_Shiny)")
    ap.add_argument("--rev", help="R release tag (default: the pinned tag)")
    ap.add_argument("--from-fixtures", action="store_true",
                    help="read the 7 templates from tests/parity/ (offline, tests)")
    ap.add_argument("--check", action="store_true", help="report drift, write nothing")
    ap.add_argument("--accept-warnings", action="store_true",
                    help="accept off-rule links / type mismatches (recorded in the pin)")
    a = ap.parse_args(argv)
    result = sync(repo_root=REPO_ROOT, r_root=a.r_root, rev=a.rev,
                  from_fixtures=a.from_fixtures, check=a.check,
                  accept_warnings=a.accept_warnings)
    for line in result.lines:
        print(line)
    return result.code


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: Run — GREEN**

`micromamba run -n shiny python -m pytest tests/test_r_template_catalogue.py -q` → `86 passed` (≈60 s: about 15 real git repos and ~40 syncs).

- [ ] **Step 7: Run the CI unit command** → green. (`--from-fixtures --check` on the real tree would still exit 1 here — nothing is shipped yet; no test asserts it before Task 5.)

- [ ] **Step 8: Commit**

```powershell
git add sespy/r_template_catalogue.py scripts/__init__.py scripts/sync_r_templates.py tests/test_r_template_catalogue.py
git commit -m @'
feat(sync): R template catalogue builder and sync script (P2 §3, §4)

sespy.r_template_catalogue.sync() reads R's 7 templates with git show (or
the pinned fixtures), converts them with the P1a mapper, builds the
catalogue and - from R - the fixtures, the pin and the R_SYNC.md block, all
in memory; any failure writes nothing. Off-rule links and type mismatches
fail unless accepted (persisted in r_sync.json). --check compares parsed
JSON / LF-normalised text. scripts/sync_r_templates.py is a thin CLI run
with python -m from the repo root. Tests run against tmp_path copies and a
real fake R git repo.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
'@
```

---

### Task 5 (C5, one commit): First real sync — re-pin to v1.31.0, shipped templates, and the tests that need them

**Files:**
- Create: `tests/parity/test_r_category_parity.py`
- Modify: `tests/parity/test_r_sync.py`, `tests/test_r_template_catalogue.py` (append)
- Generated by the sync: `sespy/templates/marinesabres/*.json` (8), `tests/parity/r_source/template_loader.R`, `tests/parity/r_sync.json`, `docs/parity/R_SYNC.md` (block only); the 7 template fixtures and the rules fixture are rewritten byte-identically in content.

**Interfaces:** Consumes `sync()` and the category constants (Task 4). Produces the shipped tree Tasks 6–10 read and the pin `{"r_tag": "v1.31.0", "r_commit": "4b53b7d", "files": {9}, "accepted_warnings": []}`.

- [ ] **Step 1: Create `tests/parity/test_r_category_parity.py`**

```python
"""P2 — content parity of the gallery category rule with R (spec §8).

tests/parity/r_source/template_loader.R is R's file at the pin (hash-checked
by test_r_sync.py, rewritten by the sync script). A hash alone would be
silently re-pinned, so this test reads R's `.determine_template_category`
and asserts that its branches, regex table and order equal the Python port
in sespy.r_template_catalogue. A red here means R changed the rule: port the
change, never edit the fixture.
"""
from __future__ import annotations

import re
from pathlib import Path

from sespy import r_template_catalogue as C

ROOT = Path(__file__).resolve().parents[2]
R_SOURCE = ROOT / "tests" / "parity" / "r_source" / "template_loader.R"


def _function_body() -> str:
    # The working copy is CRLF under core.autocrlf=true: normalise first.
    src = R_SOURCE.read_text(encoding="utf-8").replace("\r\n", "\n")
    m = re.search(r"^\.determine_template_category <- function\(json_data\) \{\n(.*?)\n\}\n",
                  src, re.S | re.M)
    assert m, "R's .determine_template_category not found in template_loader.R"
    return m.group(1)


def test_null_branch():
    m = re.search(r'if \(is\.null\(json_data\$regional_context\$main_issues\)\) return\("([^"]+)"\)',
                  _function_body())
    assert m and m.group(1) == C.CATEGORY_NULL


def test_multi_issue_branch():
    body = _function_body()
    assert "issues <- json_data$regional_context$main_issues" in body
    m = re.search(r'if \(length\(issues\) > 1\) return\("([^"]+)"\)', body)
    assert m and m.group(1) == C.CATEGORY_MULTI


def test_regex_table_and_order():
    rules = re.findall(
        r'if \(any\(grepl\("([^"]+)", issues, ignore\.case = TRUE\)\)\) return\("([^"]+)"\)',
        _function_body())
    assert tuple(rules) == C.CATEGORY_RULES


def test_fallback():
    m = re.search(r'\n\s*"([^"]+)"\s*$', _function_body())
    assert m and m.group(1) == C.CATEGORY_FALLBACK


def test_no_unparsed_branch():
    # NULL + length + one `if (` per regex rule: any new branch in R turns this red.
    assert _function_body().count("if (") == 2 + len(C.CATEGORY_RULES)
```

- [ ] **Step 2: Edit `tests/parity/test_r_sync.py`** (the pin is no longer a literal)

Replace the module docstring
```python
"""P1a — the R fixtures are pinned to MarineSABRES v1.29.0 (e33faea).

tests/parity/r_sync.json is the machine-readable pin; docs/parity/R_SYNC.md
is the human record and must list the same hashes. A new R release is
adopted by re-copying the fixtures and updating both in one commit.
"""
```
with
```python
"""P1a/P2 — the R fixtures are pinned to one MarineSABRES release.

tests/parity/r_sync.json is the machine-readable pin; docs/parity/R_SYNC.md
is the human record and must list the same hashes and the same release in
its generated block. A new R release is adopted with
`python -m scripts.sync_r_templates`, which rewrites the fixtures, the pin
and the block together, so the release is not a literal here.
"""
```
and replace `test_pin_shape`
```python
def test_pin_shape():
    assert PIN["r_tag"] == "v1.29.0" and PIN["r_commit"] == "e33faea"
    paths = sorted(PIN["files"])
    assert len(paths) == 8
    assert "tests/parity/r_rules/dapsiwrm_connection_rules.R" in paths
    assert sum(p.startswith("tests/parity/r_templates/") for p in paths) == 7
    assert not any("backup" in p for p in paths)
```
with
```python
def test_pin_shape():
    assert re.fullmatch(r"v\d+\.\d+\.\d+", PIN["r_tag"]), PIN["r_tag"]
    assert re.fullmatch(r"[0-9a-f]{7}", PIN["r_commit"]), PIN["r_commit"]
    paths = sorted(PIN["files"])
    assert len(paths) == 9
    assert "tests/parity/r_rules/dapsiwrm_connection_rules.R" in paths
    assert "tests/parity/r_source/template_loader.R" in paths
    assert sum(p.startswith("tests/parity/r_templates/") for p in paths) == 7
    assert not any("backup" in p for p in paths)
    assert isinstance(PIN["accepted_warnings"], list)


def test_r_sync_md_pin_line_equals_the_pin():
    md = (ROOT / "docs" / "parity" / "R_SYNC.md").read_text(encoding="utf-8")
    assert md.count("<!-- r-sync:begin -->") == 1 and md.count("<!-- r-sync:end -->") == 1
    block = md.split("<!-- r-sync:begin -->")[1].split("<!-- r-sync:end -->")[0]
    m = re.search(r"\*\*R release:\*\* MarineSABRES_SES_Shiny \*\*(v\d+\.\d+\.\d+)\*\*, "
                  r"commit `([0-9a-f]{7})`\.", block)
    assert m, "no generated pin line between the r-sync markers"
    assert (m.group(1), m.group(2)) == (PIN["r_tag"], PIN["r_commit"])
```

- [ ] **Step 3: Append the shipped-tree tests to `tests/test_r_template_catalogue.py`**

```python
# ---- the shipped tree (spec §1 done-when, §8; needs the first real sync) -------

SHIPPED = ROOT / C.OUT_DIR


@pytest.mark.parametrize("fname", C.TEMPLATE_FILES)
def test_drift_guard_shipped_project_equals_the_conversion(fname):
    from sespy.persistent_storage import load_project
    from sespy.r_template_mapper import convert_r_template
    project, _ = convert_r_template(RAW[fname], key=fname[: -len(".json")])
    raw_shipped = json.loads((SHIPPED / fname).read_bytes().decode("utf-8-sig"))
    assert raw_shipped["isa_data"] == project.to_dict()["isa_data"]
    shipped = load_project(SHIPPED / fname)
    assert shipped.isa_data == project.isa_data
    # Field by field, never Project ==: a round trip stamps min_sespy_version.
    want = project.metadata
    got = shipped.metadata
    assert got.name == want.name + " (MarineSABRES)"
    for f in ("description", "regional_sea", "ecosystem_type", "origin",
              "r_template_version", "created_at"):
        assert getattr(got, f) == getattr(want, f), f


@pytest.mark.parametrize("fname", C.TEMPLATE_FILES)
def test_raw_r_links_and_signs(fname):
    # Independent of the mapper: the shipped links against R's own JSON.
    raw_links = RAW[fname]["connections"]
    want = {(str(c["from_id"]), str(c["to_id"])): c.get("polarity") or "+" for c in raw_links}
    shipped = json.loads((SHIPPED / fname).read_bytes().decode("utf-8-sig"))["isa_data"]
    got = {(c["source"], c["target"]): c["polarity"] for c in shipped["connections"]}
    assert len(shipped["connections"]) == len(raw_links) == len(want)
    assert got == want


def test_shipped_catalogue_equals_a_fresh_build(tmp_path):
    root = _tree(tmp_path)
    assert C.sync(repo_root=root, from_fixtures=True).code == 0
    fresh = json.loads((root / C.CATALOGUE_PATH).read_bytes())
    assert json.loads((ROOT / C.CATALOGUE_PATH).read_bytes().decode("utf-8-sig")) == fresh
    assert (fresh["r_tag"], fresh["r_commit"]) == ("v1.31.0", "4b53b7d")


def test_committed_tree_has_no_drift():
    # --check never writes, so this is safe on the real working tree (which is
    # CRLF on a core.autocrlf=true checkout).
    res = C.sync(repo_root=ROOT, from_fixtures=True, check=True)
    assert res.code == 0, res.lines


def test_committed_tree_has_no_drift_as_crlf(tmp_path):
    root = _tree(tmp_path)
    shutil.copytree(SHIPPED, root / C.OUT_DIR)
    for p in (root / C.OUT_DIR).glob("*.json"):
        p.write_bytes(p.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    res = C.sync(repo_root=root, from_fixtures=True, check=True)
    assert res.code == 0, res.lines

@pytest.mark.parametrize("fname", C.TEMPLATE_FILES)
def test_shipped_project_loads_without_off_rule_warnings(fname, caplog):
    # Spec §7: 0 off-rule links today, so validation logs nothing on sespy.link_rules.
    import logging

    from sespy.persistent_storage import load_project
    with caplog.at_level(logging.WARNING, logger="sespy.link_rules"):
        project = load_project(SHIPPED / fname)
    assert project.newer_build == {}
    assert not [r for r in caplog.records if r.name == "sespy.link_rules"]
```

- [ ] **Step 4: Run — RED**

`micromamba run -n shiny python -m pytest tests/parity tests/test_r_template_catalogue.py -q` → `30 failed, 102 passed`: the 5 `test_r_category_parity.py` tests (`FileNotFoundError` for `tests/parity/r_source/template_loader.R`), `test_pin_shape` (`assert 8 == 9`), and the 24 shipped-tree tests (no `sespy/templates/marinesabres/`). `test_r_sync_md_pin_line_equals_the_pin` already passes (Task 3's block reads v1.29.0 = the current pin).

- [ ] **Step 5: Run the sync against R v1.31.0** (from the repo root)

```powershell
$R = 'C:\Users\arturas.baziukas\OneDrive - ku.lt\HORIZON_EUROPE\Marine-SABRES\SESToolbox\MarineSABRES_SES_Shiny'
micromamba run -n shiny python -m scripts.sync_r_templates --r-root $R --rev v1.31.0
```
Expected exit 0 and exactly these 20 lines (verified while planning):
```
hash tests/parity/r_source/template_loader.R: (none) -> 3ebe6c83a737ead8e91936f9f11ca5cfa4244d56d52f1644fc7df2af131d02d3
wrote sespy/templates/marinesabres/Aquaculture_SES_Template.json
wrote sespy/templates/marinesabres/Caribbean_SES_Template.json
wrote sespy/templates/marinesabres/ClimateChange_SES_Template.json
wrote sespy/templates/marinesabres/Fisheries_SES_Template.json
wrote sespy/templates/marinesabres/OffshoreWind_SES_Template.json
wrote sespy/templates/marinesabres/Pollution_SES_Template.json
wrote sespy/templates/marinesabres/Tourism_SES_Template.json
wrote sespy/templates/marinesabres/catalogue.json
wrote tests/parity/r_templates/Aquaculture_SES_Template.json
wrote tests/parity/r_templates/Caribbean_SES_Template.json
wrote tests/parity/r_templates/ClimateChange_SES_Template.json
wrote tests/parity/r_templates/Fisheries_SES_Template.json
wrote tests/parity/r_templates/OffshoreWind_SES_Template.json
wrote tests/parity/r_templates/Pollution_SES_Template.json
wrote tests/parity/r_templates/Tourism_SES_Template.json
wrote tests/parity/r_rules/dapsiwrm_connection_rules.R
wrote tests/parity/r_source/template_loader.R
wrote tests/parity/r_sync.json
wrote docs/parity/R_SYNC.md
```
No `warning` line (0 off-rule links, 0 type mismatches) and no other `hash` line (the 8 P1a hashes are unchanged).

- [ ] **Step 6: Check, twice, and confirm R is untouched**

```powershell
$R = 'C:\Users\arturas.baziukas\OneDrive - ku.lt\HORIZON_EUROPE\Marine-SABRES\SESToolbox\MarineSABRES_SES_Shiny'
micromamba run -n shiny python -m scripts.sync_r_templates --r-root $R --check     # no output, exit 0
micromamba run -n shiny python -m scripts.sync_r_templates --from-fixtures --check  # no output, exit 0
git -C $R reflog -n 10 --date=iso --format='%gd %gs'   # entries newer than Task 0's (compare the HEAD@{time}) must all be the user's own checkout:/commit: lines
```
The sync never checks out or commits, so it cannot add a reflog entry; a new entry is the user working in R, not P2. Do not compare `HEAD` / `status` counts (they move with the user's work).

- [ ] **Step 7: Review the diff**

`git status --short` (besides `LITERATURE/`) shows only `M docs/parity/R_SYNC.md`, `M tests/parity/r_sync.json`, `M tests/parity/test_r_sync.py`, `M tests/test_r_template_catalogue.py`, `?? sespy/templates/marinesabres/`, `?? tests/parity/r_source/`, `?? tests/parity/test_r_category_parity.py`. The 8 rewritten fixtures are written LF over a CRLF working copy, so on this `core.autocrlf=true` checkout **expect all 8 to show `M`** (dry run): `git diff --ignore-cr-at-eol -- tests/parity/r_templates tests/parity/r_rules` must print nothing, and after `git add` they drop out of the commit (content-equal to their LF blobs). Stage them anyway with the rest, or `git checkout -- tests/parity/r_templates tests/parity/r_rules` first; either way the commit holds no fixture change. `git diff -- docs/parity/R_SYNC.md` (ignoring CR) is exactly: the pin line `**v1.29.0**, commit `e33faea`` → `**v1.31.0**, commit `4b53b7d``, plus one added row ``| `tests/parity/r_source/template_loader.R` | `3ebe6c83…02d3` |``. `tests/parity/r_sync.json` gains `r_tag`/`r_commit` v1.31.0/4b53b7d, the `template_loader.R` entry, files sorted by path, and `"accepted_warnings": []`.

- [ ] **Step 8: Run — GREEN**

`micromamba run -n shiny python -m pytest tests/parity tests/test_r_template_catalogue.py tests/test_r_template_mapper.py -q` → `200 passed`.

- [ ] **Step 9: Run the CI unit command** → green.

- [ ] **Step 10: Commit (one commit: nothing ever ships stamped v1.29.0)**

```powershell
git add sespy/templates/marinesabres tests/parity/r_source tests/parity/r_sync.json tests/parity/r_templates tests/parity/r_rules docs/parity/R_SYNC.md tests/parity/test_r_category_parity.py tests/parity/test_r_sync.py tests/test_r_template_catalogue.py
git status --short    # staged: only the paths above; LITERATURE/ untouched
git commit -m @'
feat(templates): re-pin R to v1.31.0 and ship the 7 MarineSABRES templates (P2)

First real run of python -m scripts.sync_r_templates --r-root <R> --rev
v1.31.0 (4b53b7d): the 7 converted projects and catalogue.json under
sespy/templates/marinesabres/, functions/template_loader.R as a 9th pinned
fixture, r_sync.json (accepted_warnings: []) and the R_SYNC.md block. The
8 P1a fixtures are unchanged. Adds the drift guard, the raw-R link/sign
check, a no-off-rule-warning load check, catalogue equality, the
committed-tree --check, the category content-parity test, and a
non-literal pin test with 9 files.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
'@
```

---

### Task 6: Gallery listing — `TemplateInfo`, `list_catalogue()`, package data (spec §6.1)

**Files:**
- Modify: `sespy/templates/__init__.py` (whole file below), `pyproject.toml` (package-data)
- Test: `tests/test_templates.py` (append)

**Interfaces:**
- Consumes: `CATALOGUE_KEYS`, `ALWAYS_NON_EMPTY` from `sespy.r_template_catalogue` (one definition of the §4 keys); the shipped tree (Task 5).
- Produces: `TemplateInfo(..., group="sespy", category="", complexity="", version="", regional_sea_label="", source="", usage_notes="")` (defaulted; existing keyword callers unchanged); `list_catalogue(directory: Path | None = None) -> list[TemplateInfo]` (catalogue order, `group="marinesabres"`, `da_site=""`, `file` absolute and resolved; bad entry → skipped + WARNING on logger `sespy.templates`; missing/unparsable → `[]` + WARNING). `list_templates()` unchanged (top-level `*.json` only). Settled: the three may-be-empty text fields must also be strings.

- [ ] **Step 1: Append the failing tests to `tests/test_templates.py`**

```python
# ---- P2: the MarineSABRES group (spec §6.1) -------------------------------

import json
import logging
import shutil
import sys
import tomllib

from sespy.r_template_catalogue import ALWAYS_NON_EMPTY, OUT_DIR

ROOT = Path(__file__).resolve().parents[1]
CAT_DIR = ROOT / OUT_DIR
SUFFIX = " (MarineSABRES)"


def test_list_catalogue_has_the_seven_r_templates():
    rows = tpl.list_catalogue()
    assert len(rows) == 7
    assert rows[0].name == "Caribbean Island - Comprehensive SES Template (MarineSABRES)"
    for r in rows:
        assert r.group == "marinesabres" and r.da_site == ""
        assert r.name.endswith(SUFFIX)
        assert r.file.is_absolute() and r.file.parent == CAT_DIR.resolve()
        for k in ALWAYS_NON_EMPTY:
            v = r.file.name if k == "file" else getattr(r, k)
            assert isinstance(v, str) and v, (r.name, k)
        assert r.element_count > 0 and r.connection_count > 0


def test_list_catalogue_parses_no_project(tmp_path):
    # Unparsable project files cannot matter if only catalogue.json is read.
    d = tmp_path / "marinesabres"
    shutil.copytree(CAT_DIR, d)
    for p in d.glob("*_SES_Template.json"):
        p.write_bytes(b"not json")
    rows = tpl.list_catalogue(d)
    assert len(rows) == 7 and rows[0].element_count == 78


def test_every_catalogue_file_loads_with_the_listed_counts():
    for r in tpl.list_catalogue():
        project = load_project(r.file)
        assert project.isa_data.element_count() == r.element_count, r.name
        assert project.isa_data.connection_count() == r.connection_count, r.name
        assert project.metadata.name == r.name
        assert project.metadata.origin == "r_template"


def test_names_unique_across_both_groups_and_fit_the_wired_buttons():
    from sespy.modules.templates import MAX_TEMPLATES
    rows = tpl.list_catalogue() + tpl.list_templates()
    names = [r.name for r in rows]
    assert len(names) == len(set(names)), names
    assert len(rows) == 11 and len(rows) <= MAX_TEMPLATES


def test_list_templates_ignores_the_marinesabres_subdirectory():
    rows = tpl.list_templates()
    assert {r.group for r in rows} == {"sespy"}
    assert all(r.file.parent == Path(tpl._templates_dir()) for r in rows)
    assert not any(r.name.endswith(SUFFIX) for r in rows)


def test_template_info_new_fields_default_for_existing_callers():
    info = tpl.TemplateInfo(file=Path("x.json"), name="n", description="d",
                            da_site="", element_count=1, connection_count=1)
    assert (info.group, info.category, info.complexity, info.version,
            info.regional_sea_label, info.source, info.usage_notes) == ("sespy", "", "", "", "", "", "")


# -- list_catalogue(directory=...) on a tmp copy --------------------------------

def _copy(tmp_path: Path) -> Path:
    d = tmp_path / "marinesabres"
    shutil.copytree(CAT_DIR, d)
    return d


def _edit_catalogue(d: Path, change) -> None:
    cat = json.loads((d / "catalogue.json").read_bytes().decode("utf-8-sig"))
    change(cat)
    (d / "catalogue.json").write_bytes(json.dumps(cat).encode("utf-8"))


def test_missing_catalogue_gives_empty_and_warns(tmp_path, caplog):
    with caplog.at_level(logging.WARNING, logger="sespy.templates"):
        assert tpl.list_catalogue(tmp_path) == []
    assert "catalogue unavailable" in caplog.text


@pytest.mark.parametrize("text", ["{not json", "[]", '{"templates": {}}', '{"r_tag": "v1"}'])
def test_unparsable_catalogue_gives_empty_and_warns(tmp_path, caplog, text):
    (tmp_path / "catalogue.json").write_text(text, encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger="sespy.templates"):
        assert tpl.list_catalogue(tmp_path) == []
    assert "catalogue unavailable" in caplog.text


@pytest.mark.parametrize("change", [
    lambda e: e.pop("usage_notes"),                  # missing key
    lambda e: e.update(name=""),                     # empty always-non-empty field
    lambda e: e.update(category=None),
    lambda e: e.update(source=3),                    # may-be-empty field, wrong type
    lambda e: e.update(element_count=0),
    lambda e: e.update(connection_count="140"),      # non-int
    lambda e: e.update(element_count=True),          # bool is not a count
    lambda e: e.update(file="missing.json"),         # dangling
    lambda e: e.update(file="../catalogue.json"),    # escaping
    lambda e: e.update(file="..\\catalogue.json"),   # Windows escape to the {} target
    lambda e: e.update(file=str(CAT_DIR.parent / "minimal_demo.json")),   # absolute, outside
    lambda e: e.update(file=""),
], ids=["missing-key", "empty-name", "null-category", "int-source", "zero-count",
        "str-count", "bool-count", "dangling", "escape-up", "escape-backslash",
        "absolute", "empty-file"])
def test_bad_entry_is_skipped_with_a_warning(tmp_path, caplog, change):
    d = _copy(tmp_path)
    (tmp_path / "catalogue.json").write_text("{}", encoding="utf-8")      # an escape target
    _edit_catalogue(d, lambda cat: change(cat["templates"][0]))
    with caplog.at_level(logging.WARNING, logger="sespy.templates"):
        rows = tpl.list_catalogue(d)
    assert len(rows) == 6
    assert "entry 0 skipped" in caplog.text


def test_relative_directory_still_lists_all_seven(tmp_path, monkeypatch):
    _copy(tmp_path)
    monkeypatch.chdir(tmp_path)
    rows = tpl.list_catalogue(Path("marinesabres"))
    assert len(rows) == 7 and all(r.file.is_absolute() for r in rows)


@pytest.mark.skipif(sys.platform != "win32", reason="8.3 short paths are a Windows thing")
def test_short_8dot3_directory_still_lists_all_seven(tmp_path):
    import ctypes
    d = _copy(tmp_path)
    buf = ctypes.create_unicode_buffer(1024)
    n = ctypes.windll.kernel32.GetShortPathNameW(str(d), buf, len(buf))
    short = Path(buf.value) if n else d
    if "~" not in str(short):
        pytest.skip("8.3 short names are disabled on this volume")
    assert str(short) != str(d.resolve())
    rows = tpl.list_catalogue(short)
    assert len(rows) == 7


def test_package_data_ships_the_marinesabres_templates():
    with open(ROOT / "pyproject.toml", "rb") as f:
        globs = tomllib.load(f)["tool"]["setuptools"]["package-data"]["sespy"]
    assert "templates/marinesabres/*.json" in globs
    # setuptools expands these with glob semantics: "*" never crosses "/".
    shipped = {p.resolve() for g in globs for p in (ROOT / "sespy").glob(g)}
    wanted = {p.resolve() for p in CAT_DIR.glob("*.json")}
    assert len(wanted) == 8 and wanted <= shipped
```

- [ ] **Step 2: Run — RED**

`micromamba run -n shiny python -m pytest tests/test_templates.py -q` → `26 failed, 6 passed`: `AttributeError: module 'sespy.templates' has no attribute 'list_catalogue'` (list/no-parse/load/names/bad-entry/relative/short-path tests), `AttributeError: 'TemplateInfo' object has no attribute 'group'` (the two field tests), and `test_package_data_ships_the_marinesabres_templates` (`'templates/marinesabres/*.json' in [...]` fails).

- [ ] **Step 3: Replace `sespy/templates/__init__.py` with**

```python
"""Built-in SES templates — domain-specific starting projects.

Two groups, both plain Project envelopes (`{metadata, isa_data}`) loaded with
`load_template()`:

- **SESPy examples**: each top-level `*.json` here, discovered by
  `list_templates()` (which validates every file).
- **MarineSABRES templates** (P2): R's 7 curated templates, pre-converted by
  `python -m scripts.sync_r_templates` into `marinesabres/`, and listed by
  `list_catalogue()` from the generated `marinesabres/catalogue.json` only
  (no project parsing at list time). Never edit those files by hand.

Loading a template into the app replaces `project_data`, fires `isa_change`,
and the analysis modules see the new SES immediately.

To add a SESPy example:
  1. Drop `mydomain.json` here, shaped like one of the existing files
  2. Restart the app — `list_templates()` discovers it automatically
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from ..data_structure import Project
from ..persistent_storage import load_project
from ..r_template_catalogue import ALWAYS_NON_EMPTY, CATALOGUE_KEYS

log = logging.getLogger(__name__)

_COUNT_KEYS = ("element_count", "connection_count")
_TEXT_KEYS = tuple(k for k in CATALOGUE_KEYS if k not in _COUNT_KEYS)


@dataclass(frozen=True)
class TemplateInfo:
    """Lightweight metadata for the picker — full Project loaded on demand."""
    file: Path
    name: str
    description: str
    da_site: str
    element_count: int
    connection_count: int
    group: str = "sespy"                 # "sespy" | "marinesabres"
    category: str = ""                   # the MarineSABRES fields (catalogue.json)
    complexity: str = ""
    version: str = ""
    regional_sea_label: str = ""
    source: str = ""
    usage_notes: str = ""


def _templates_dir() -> Path:
    return Path(__file__).parent


def _catalogue_dir() -> Path:
    return _templates_dir() / "marinesabres"


def _entry_problem(entry: object, base: Path) -> str | None:
    """Why a catalogue entry is unusable, or None when it is fine."""
    if not isinstance(entry, dict):
        return "not an object"
    missing = [k for k in CATALOGUE_KEYS if k not in entry]
    if missing:
        return f"missing {', '.join(missing)}"
    for k in _TEXT_KEYS:
        if not isinstance(entry[k], str):
            return f"{k} is not a string"
    for k in ALWAYS_NON_EMPTY:
        if not entry[k]:
            return f"empty {k}"
    for k in _COUNT_KEYS:
        v = entry[k]
        if isinstance(v, bool) or not isinstance(v, int) or v <= 0:
            return f"{k} is not a positive integer"
    path = (base / entry["file"]).resolve()
    if not path.is_relative_to(base) or not path.is_file():
        return f"file {entry['file']!r} is outside the catalogue directory or missing"
    return None


def list_catalogue(directory: Path | None = None) -> list[TemplateInfo]:
    """The MarineSABRES templates, in catalogue order, from
    `<directory or templates/marinesabres>/catalogue.json` only. A bad entry
    is skipped with a WARNING; a missing or unparsable catalogue gives []."""
    d = Path(directory) if directory is not None else _catalogue_dir()
    try:
        catalogue = json.loads((d / "catalogue.json").read_bytes().decode("utf-8-sig"))
        entries = catalogue["templates"]
        if not isinstance(entries, list):
            raise TypeError("templates is not a list")
    except (OSError, ValueError, KeyError, TypeError) as e:
        log.warning("MarineSABRES template catalogue unavailable in %s: %s", d, e)
        return []
    # Both sides resolved, so an 8.3 short path or a symlinked sespy/ works.
    base = d.resolve()
    out: list[TemplateInfo] = []
    for i, entry in enumerate(entries):
        problem = _entry_problem(entry, base)
        if problem:
            log.warning("MarineSABRES catalogue entry %d skipped: %s", i, problem)
            continue
        out.append(TemplateInfo(
            file=(base / entry["file"]).resolve(),
            name=entry["name"],
            description=entry["description"],
            da_site="",
            element_count=entry["element_count"],
            connection_count=entry["connection_count"],
            group="marinesabres",
            category=entry["category"],
            complexity=entry["complexity"],
            version=entry["version"],
            regional_sea_label=entry["regional_sea_label"],
            source=entry["source"],
            usage_notes=entry["usage_notes"],
        ))
    return out


def list_templates() -> list[TemplateInfo]:
    """Scan the templates directory (top-level `*.json` only, so
    `marinesabres/` is not picked up) and return the SESPy examples,
    name-sorted. Skips files that fail to validate so a broken sample
    doesn't poison the picker."""
    out: list[TemplateInfo] = []
    for path in sorted(_templates_dir().glob("*.json")):
        try:
            project = load_project(path)
        except (ValueError, OSError):
            continue
        out.append(TemplateInfo(
            file=path,
            name=project.metadata.name or path.stem,
            description=project.metadata.description or "",
            da_site=project.metadata.da_site or "",
            element_count=project.isa_data.element_count(),
            connection_count=project.isa_data.connection_count(),
        ))
    return out


def load_template(file: Path | str) -> Project:
    """Reuse the standard project loader (validation + envelope handling)."""
    return load_project(file)
```

- [ ] **Step 4: `pyproject.toml` package data** — replace
```toml
sespy = ["*.json", "translations/*.json", "templates/*.json", "www/*.css"]
```
with
```toml
sespy = ["*.json", "translations/*.json", "templates/*.json", "templates/marinesabres/*.json", "www/*.css"]
```

- [ ] **Step 5: Run — GREEN**

`micromamba run -n shiny python -m pytest tests/test_templates.py -q` → `32 passed` (on Windows with 8.3 names enabled the short-path test runs; elsewhere it skips).

- [ ] **Step 6: Run the CI unit command** → green.

- [ ] **Step 7: Commit**

```powershell
git add sespy/templates/__init__.py pyproject.toml tests/test_templates.py
git commit -m @'
feat(templates): list_catalogue() for the MarineSABRES group; package data (P2 §6.1)

TemplateInfo gains defaulted group/category/complexity/version/
regional_sea_label/source/usage_notes. list_catalogue() reads only
marinesabres/catalogue.json, validates every entry (keys, types, positive
int counts, file inside the directory with both sides resolved) and skips a
bad one with a warning. list_templates() still globs top-level *.json.
pyproject ships templates/marinesabres/*.json.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
'@
```

---

### Task 7: Translations — 13 `templates.*` keys in all 9 languages (spec §6.3)

**Files:**
- Modify: `sespy/translations/core.json`
- Test: `tests/test_i18n.py` (append)

**Interfaces:** Produces the keys Task 8 renders: `templates.group_marinesabres`, `templates.group_sespy`, `templates.about`, `templates.complexity_{simple,complex}`, `templates.category_{multi_stressor,extraction,recreation,production,pollution,climate,energy,general}`. Slug rule: `value.lower().replace("-", "_")`.

- [ ] **Step 1: Append the failing tests to `tests/test_i18n.py`**

```python
def test_templates_gallery_keys_present(translations):
    # P2 §6.3: SESPy-only keys (R shows these values untranslated).
    keys = ["templates.group_marinesabres", "templates.group_sespy", "templates.about",
            "templates.complexity_simple", "templates.complexity_complex"]
    keys += [f"templates.category_{s}" for s in (
        "multi_stressor", "extraction", "recreation", "production",
        "pollution", "climate", "energy", "general")]
    for key in keys:
        assert key in translations, key
        for lang in SUPPORTED_LANGUAGES:
            assert translations[key].get(lang, "").strip(), (key, lang)
    assert translations["templates.group_marinesabres"]["en"] == "MarineSABRES templates"
    assert translations["templates.group_sespy"]["en"] == "SESPy examples"
    assert translations["templates.about"]["en"] == "About this template"


def test_every_category_and_complexity_the_port_emits_has_a_key(translations):
    from sespy import r_template_catalogue as C
    categories = {C.CATEGORY_NULL, C.CATEGORY_MULTI, C.CATEGORY_FALLBACK,
                  *(cat for _, cat in C.CATEGORY_RULES)}
    for value in categories:
        slug = value.lower().replace("-", "_")
        assert f"templates.category_{slug}" in translations, value
        assert translations[f"templates.category_{slug}"]["en"] == value
    for value in (C.DEFAULT_COMPLEXITY, "complex"):
        assert f"templates.complexity_{value}" in translations, value
```

- [ ] **Step 2: Run — RED**

`micromamba run -n shiny python -m pytest tests/test_i18n.py -q` → `2 failed, 33 passed` (`AssertionError: templates.group_marinesabres`; `AssertionError: Multi-Stressor` or the first category checked).

- [ ] **Step 3: Insert the block in `sespy/translations/core.json`**

Anchor: the end of the `"templates.loaded"` entry, i.e. the two lines
```json
      "el": "Το πρότυπο φορτώθηκε."
    },
```
(followed by `"stepper.start": {`). Insert directly after them (same 4-space key indent, every entry ends with `},`):

```json
    "templates.group_marinesabres": {
      "en": "MarineSABRES templates",
      "es": "Plantillas MarineSABRES",
      "fr": "Modèles MarineSABRES",
      "de": "MarineSABRES-Vorlagen",
      "lt": "MarineSABRES šablonai",
      "pt": "Modelos MarineSABRES",
      "it": "Modelli MarineSABRES",
      "no": "MarineSABRES-maler",
      "el": "Πρότυπα MarineSABRES"
    },
    "templates.group_sespy": {
      "en": "SESPy examples",
      "es": "Ejemplos de SESPy",
      "fr": "Exemples SESPy",
      "de": "SESPy-Beispiele",
      "lt": "SESPy pavyzdžiai",
      "pt": "Exemplos do SESPy",
      "it": "Esempi SESPy",
      "no": "SESPy-eksempler",
      "el": "Παραδείγματα SESPy"
    },
    "templates.about": {
      "en": "About this template",
      "es": "Acerca de esta plantilla",
      "fr": "À propos de ce modèle",
      "de": "Über diese Vorlage",
      "lt": "Apie šį šabloną",
      "pt": "Sobre este modelo",
      "it": "Informazioni su questo modello",
      "no": "Om denne malen",
      "el": "Σχετικά με αυτό το πρότυπο"
    },
    "templates.complexity_simple": {
      "en": "Simple",
      "es": "Simple",
      "fr": "Simple",
      "de": "Einfach",
      "lt": "Paprastas",
      "pt": "Simples",
      "it": "Semplice",
      "no": "Enkel",
      "el": "Απλό"
    },
    "templates.complexity_complex": {
      "en": "Complex",
      "es": "Complejo",
      "fr": "Complexe",
      "de": "Komplex",
      "lt": "Sudėtingas",
      "pt": "Complexo",
      "it": "Complesso",
      "no": "Kompleks",
      "el": "Σύνθετο"
    },
    "templates.category_multi_stressor": {
      "en": "Multi-Stressor",
      "es": "Múltiples presiones",
      "fr": "Pressions multiples",
      "de": "Mehrfachbelastung",
      "lt": "Daugybinis poveikis",
      "pt": "Múltiplas pressões",
      "it": "Pressioni multiple",
      "no": "Flere påvirkninger",
      "el": "Πολλαπλές πιέσεις"
    },
    "templates.category_extraction": {
      "en": "Extraction",
      "es": "Extracción",
      "fr": "Extraction",
      "de": "Entnahme",
      "lt": "Išgavimas",
      "pt": "Extração",
      "it": "Estrazione",
      "no": "Uttak",
      "el": "Απόληψη"
    },
    "templates.category_recreation": {
      "en": "Recreation",
      "es": "Recreación",
      "fr": "Loisirs",
      "de": "Erholung",
      "lt": "Rekreacija",
      "pt": "Recreação",
      "it": "Attività ricreative",
      "no": "Rekreasjon",
      "el": "Αναψυχή"
    },
    "templates.category_production": {
      "en": "Production",
      "es": "Producción",
      "fr": "Production",
      "de": "Produktion",
      "lt": "Gamyba",
      "pt": "Produção",
      "it": "Produzione",
      "no": "Produksjon",
      "el": "Παραγωγή"
    },
    "templates.category_pollution": {
      "en": "Pollution",
      "es": "Contaminación",
      "fr": "Pollution",
      "de": "Verschmutzung",
      "lt": "Tarša",
      "pt": "Poluição",
      "it": "Inquinamento",
      "no": "Forurensning",
      "el": "Ρύπανση"
    },
    "templates.category_climate": {
      "en": "Climate",
      "es": "Clima",
      "fr": "Climat",
      "de": "Klima",
      "lt": "Klimatas",
      "pt": "Clima",
      "it": "Clima",
      "no": "Klima",
      "el": "Κλίμα"
    },
    "templates.category_energy": {
      "en": "Energy",
      "es": "Energía",
      "fr": "Énergie",
      "de": "Energie",
      "lt": "Energetika",
      "pt": "Energia",
      "it": "Energia",
      "no": "Energi",
      "el": "Ενέργεια"
    },
    "templates.category_general": {
      "en": "General",
      "es": "General",
      "fr": "Général",
      "de": "Allgemein",
      "lt": "Bendra",
      "pt": "Geral",
      "it": "Generale",
      "no": "Generelt",
      "el": "Γενικό"
    },
```

Then check the file still parses: `micromamba run -n shiny python -m json.tool sespy/translations/core.json > $null` → exit 0.

- [ ] **Step 4: Run — GREEN**

`micromamba run -n shiny python -m pytest tests/test_i18n.py -q` → `35 passed`.

- [ ] **Step 5: Run the CI unit command** → green.

- [ ] **Step 6: Commit**

```powershell
git add sespy/translations/core.json tests/test_i18n.py
git commit -m @'
i18n(templates): group, About, complexity and category labels in 9 languages (P2 §6.3)

SESPy-only keys under templates.* in core.json (R shows these values
untranslated, so there is no R key to adopt). A test derives the expected
keys from the category port, so a new R category needs a key.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
'@
```

---

### Task 8: Templates panel — groups, badges, About, combined index (spec §6.2)

**Files:**
- Modify: `sespy/modules/templates.py` (whole file below)
- Create: `tests/test_templates_module.py`

**Interfaces:**
- Consumes: `list_catalogue`, `list_templates`, `TemplateInfo` (Task 6); the Task 7 keys.
- Produces: calc `templates()` = `list_catalogue() + list_templates()` (index 0–6 MarineSABRES, 7–10 SESPy; `MAX_TEMPLATES` stays 16); output ids `templates-group_marinesabres`, `templates-group_sespy` (`h4`, via `session.ns`, (the same `session.ns(...)` call `cld_visualization.py` uses for its controller id) — a plain `id=` inside `render.ui` is not namespaced); card `h5` = name only (the only `h5`s in the list); `div.sespy-template-badges` of `span.badge` (category, complexity, `v<version>`, regional-sea label when set); `<details>` "About this template" when source or usage notes are set; toast unchanged `t("templates.loaded") + f" ({info.name})"`; `_tr_value(kind, value)` shows the raw value on a key miss. Settled: groups render in `GROUPS = ("marinesabres", "sespy")` order; badge classes `badge bg-secondary me-1`.

- [ ] **Step 1: Write the failing test file `tests/test_templates_module.py`**

```python
"""P2 — the Templates panel in memory with shiny.testserver (spec §6.2, §6.3, §8):
two namespaced group headers, MarineSABRES badges and "About this template",
loading by the combined index, and raw R values without a translation key.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import shiny
from shiny import reactive
from shiny.testserver import test_server

import sespy.modules.templates as mod
from sespy import i18n
from sespy.data_structure import IsaData, Project, ProjectMetadata
from sespy.event_bus import create_event_bus
from sespy.i18n import Translator, load_translations
from sespy.templates import TemplateInfo, list_catalogue

ROOT = Path(__file__).resolve().parents[1]
TR = Translator(translations=load_translations(ROOT / "sespy" / "translations"))
CARIBBEAN = "Caribbean Island - Comprehensive SES Template (MarineSABRES)"


@pytest.fixture
def panel(monkeypatch):
    # The module labels with the module-level t(); give it the real
    # translations for this test only (restored by monkeypatch).
    monkeypatch.setattr(i18n, "_default_translator", TR)
    toasts: list[str] = []
    monkeypatch.setattr(shiny.ui, "notification_show",
                        lambda msg, **kw: toasts.append(str(msg)))
    holder: list[reactive.Value[Project]] = []

    def server(input, output, session):
        pd = reactive.value(Project(ProjectMetadata(name="before"), IsaData()))
        holder.append(pd)
        mod.templates_server("templates", project_data=pd,
                             event_bus=create_event_bus(), translator=TR)

    # A factory, so a test can monkeypatch list_catalogue before the server starts.
    yield (lambda: test_server(server)), toasts, holder


def _html(ts) -> str:
    return ts.make_scope("templates").get_output("templates_list").value["html"]


def test_two_namespaced_group_headers_in_order(panel):
    run, *_ = panel
    with run() as ts:
        html = _html(ts)
    assert re.search(r'<h4 id="templates-group_marinesabres"[^>]*>MarineSABRES templates</h4>', html)
    assert re.search(r'<h4 id="templates-group_sespy"[^>]*>SESPy examples</h4>', html)
    assert html.index("templates-group_marinesabres") < html.index("sespy-template-badges") \
        < html.index("templates-group_sespy")


def test_h5_are_exactly_the_card_names(panel):
    run, *_ = panel
    with run() as ts:
        html = _html(ts)
    names = re.findall(r"<h5[^>]*>(.*?)</h5>", html)
    assert len(names) == 11
    assert names[0] == CARIBBEAN
    assert names[7:] == [r.name for r in mod.list_templates()]


def test_first_card_shows_its_badges_and_about(panel):
    run, *_ = panel
    with run() as ts:
        html = _html(ts)
    first = html[html.index(CARIBBEAN): html.index("templates-load_template_0")]
    badges = re.findall(r'<span class="badge[^"]*">(.*?)</span>', first)
    assert badges == ["Multi-Stressor", "Complex", "v1.1", "Caribbean Sea"]
    assert "78 elements · 140 connections" in first
    assert "<summary>About this template</summary>" in first
    assert html.count("sespy-template-badges") == 7      # MarineSABRES cards only
    assert html.count("<details") == 7                    # all 7 have a source


def test_loading_index_0_loads_the_caribbean_template(panel):
    run, toasts, holder = panel
    with run() as ts:
        scope = ts.make_scope("templates")
        scope.set_inputs(load_template_0=0)
        scope.set_inputs(load_template_0=1)
        with reactive.isolate():
            project = holder[0]()
    assert project.metadata.name == CARIBBEAN
    assert project.isa_data.element_count() == 78
    assert toasts == [f"Template loaded. ({CARIBBEAN})"]


def test_index_7_is_the_first_sespy_example(panel):
    run, toasts, holder = panel
    first_sespy = mod.list_templates()[0].name
    with run() as ts:
        scope = ts.make_scope("templates")
        scope.set_inputs(load_template_7=0)
        scope.set_inputs(load_template_7=1)
        with reactive.isolate():
            assert holder[0]().metadata.name == first_sespy


def test_untranslated_category_and_complexity_show_the_raw_value(panel, monkeypatch):
    real = list_catalogue()[0]
    odd = TemplateInfo(**{**real.__dict__, "category": "Kelp Forests",
                          "complexity": "moderate", "regional_sea_label": ""})
    monkeypatch.setattr(mod, "list_catalogue", lambda: [odd])
    run, *_ = panel
    with run() as ts:
        html = _html(ts)
    badges = re.findall(r'<span class="badge[^"]*">(.*?)</span>', html)
    assert badges == ["Kelp Forests", "moderate", "v1.1"]
    assert "templates.category_" not in html and "templates.complexity_" not in html


def test_empty_catalogue_renders_no_marinesabres_header(panel, monkeypatch):
    monkeypatch.setattr(mod, "list_catalogue", lambda: [])
    run, *_ = panel
    with run() as ts:
        html = _html(ts)
    assert "templates-group_marinesabres" not in html
    assert 'id="templates-group_sespy"' in html


def test_tr_value_on_a_key_miss_returns_the_value(monkeypatch):
    monkeypatch.setattr(i18n, "_default_translator", TR)
    assert i18n.t("templates.complexity_moderate") == "templates.complexity_moderate"
    assert mod._tr_value("complexity", "moderate") == "moderate"
    assert mod._tr_value("category", "Multi-Stressor") == "Multi-Stressor"
    assert mod._tr_value("complexity", "complex") == "Complex"
    TR.set_language("de")
    try:
        assert mod._tr_value("category", "Energy") == "Energie"
    finally:
        TR.set_language("en")
```

- [ ] **Step 2: Run — RED**

`micromamba run -n shiny python -m pytest tests/test_templates_module.py -q` → `8 failed`: `assert 4 == 11` (h5 count), `ValueError: substring not found` (no header / Caribbean card), `'Coastal Tourism SES' == 'Caribbean Is...'` (index 0), `'before' == 'Coastal Tourism SES'` (index 7 not wired to anything), `AttributeError: ... has no attribute 'list_catalogue'` (×2), `... has no attribute '_tr_value'`, and the header regex.

- [ ] **Step 3: Replace `sespy/modules/templates.py` with**

```python
"""Templates panel — pick a domain-specific starting project.

Two groups (P2): "MarineSABRES templates" (R's 7 curated templates,
pre-converted, listed from `templates/marinesabres/catalogue.json`) and
"SESPy examples" (SESPy's own 4). Each card shows the template's name,
badges (MarineSABRES only: category, complexity, version, regional sea),
element/connection counts, the description, an "About this template"
section (source, usage notes) and a Load button. Loading replaces
`project_data` and fires `isa_change` so the analysis modules recompute
against the new SES.

R counterpart: `modules/template_ses_module.R` (~1200 LOC). Slimmed to
the picker + load action; R's complexity filter (P12) and its preview /
"edit before loading" flow (P13) are deferred.
"""

from __future__ import annotations

from shiny import Inputs, Outputs, Session, module, reactive, render, ui

from ..data_structure import Project
from ..event_bus import EventBus
from ..i18n import Translator, t
from ..templates import TemplateInfo, list_catalogue, list_templates, load_template

GROUPS = ("marinesabres", "sespy")      # display order of the two groups


def _tr_value(kind: str, value: str) -> str:
    """Translated category / complexity label. `t()` returns the key itself on
    a miss, so an R value SESPy has no key for (e.g. a future complexity
    "moderate") is shown raw, never as a key string."""
    key = f"templates.{kind}_{value.lower().replace('-', '_')}"
    text = t(key)
    return value if text == key else text


def _badges(info: TemplateInfo) -> ui.Tag:
    labels = [_tr_value("category", info.category) if info.category else "",
              _tr_value("complexity", info.complexity) if info.complexity else "",
              f"v{info.version}" if info.version else "",
              info.regional_sea_label]
    return ui.tags.div(
        *[ui.tags.span(x, class_="badge bg-secondary me-1") for x in labels if x],
        class_="sespy-template-badges",
        style="margin: 0 0 4px 0;",
    )


def _about(info: TemplateInfo) -> ui.Tag | None:
    if not (info.source or info.usage_notes):
        return None
    return ui.tags.details(
        ui.tags.summary(t("templates.about")),
        *[ui.tags.p(x, style="margin: 4px 0 0 0;")
          for x in (info.source, info.usage_notes) if x],
        style="margin: 8px 0 0 0; font-size: 0.85rem;",
    )


def _template_card(idx: int, info: TemplateInfo) -> ui.Tag:
    marinesabres = info.group == "marinesabres"
    return ui.tags.div(
        ui.tags.div(
            ui.tags.h5(info.name, style="margin: 0 0 4px 0;"),
            _badges(info) if marinesabres else None,
            ui.tags.div(
                f"{info.element_count} elements · {info.connection_count} connections"
                + (f" · {info.da_site}" if info.da_site else ""),
                class_="text-muted",
                style="font-size: 0.85rem;",
            ),
            ui.tags.p(
                info.description,
                style="margin: 8px 0 0 0; font-size: 0.9rem;",
            ),
            _about(info) if marinesabres else None,
            style="flex: 1;",
        ),
        ui.tags.div(
            ui.input_action_button(
                f"load_template_{idx}",
                t("templates.load"),
                class_="btn btn-primary",
            ),
            style="display: flex; align-items: center;",
        ),
        style=("display: flex; gap: 16px; align-items: center; "
               "padding: 16px 20px; border: 1px solid var(--mist-light); "
               "border-radius: 8px; background: white; "
               "margin-bottom: 12px;"),
    )


@module.ui
def templates_ui() -> ui.Tag:
    return ui.card(
        ui.card_header(t("nav.templates")),
        ui.div(
            ui.p(
                t("templates.intro"),
                class_="text-muted",
            ),
            ui.output_ui("templates_list"),
            style="padding: 24px;",
        ),
        class_="sespy-card",
        full_screen=False,
    )


# --- Helper to wire each Load button at module init time -------------------

MAX_TEMPLATES = 16


def _wire_load(
    input: Inputs,
    idx: int,
    project_data: reactive.Value[Project],
    event_bus: EventBus,
    templates_calc,
) -> None:
    @reactive.effect
    @reactive.event(input[f"load_template_{idx}"], ignore_init=True)
    def _():
        rows = templates_calc()
        if idx >= len(rows):
            return
        info = rows[idx]
        try:
            project = load_template(info.file)
        except (ValueError, OSError) as e:
            ui.notification_show(
                f"Couldn't load template: {e}",
                type="warning",
                duration=6,
            )
            return
        project_data.set(project)
        event_bus.emit_isa_change()
        event_bus.emit_cld_update()
        event_bus.emit_template_loaded()
        ui.notification_show(
            t("templates.loaded") + f" ({info.name})",
            type="message",
            duration=4,
        )


@module.server
def templates_server(
    input: Inputs,
    output: Outputs,
    session: Session,
    *,
    project_data: reactive.Value[Project],
    event_bus: EventBus,
    translator: Translator | None = None,
) -> None:

    @reactive.calc
    def templates() -> list[TemplateInfo]:
        # One combined index drives the pre-wired load_template_<i> buttons.
        return list_catalogue() + list_templates()

    @output
    @render.ui
    def templates_list():
        rows = templates()
        if not rows:
            return ui.tags.p(
                "No templates installed.",
                class_="text-muted",
            )
        children: list[ui.Tag] = []
        for group in GROUPS:
            cards = [_template_card(i, r) for i, r in enumerate(rows) if r.group == group]
            if not cards:
                continue                    # an empty group renders no header
            # A plain id= inside render.ui is not namespaced: use session.ns.
            children.append(ui.tags.h4(t(f"templates.group_{group}"),
                                       id=session.ns(f"group_{group}"),
                                       style="margin: 8px 0 12px 0;"))
            children += cards
        return ui.tags.div(*children)

    for i in range(MAX_TEMPLATES):
        _wire_load(input, i, project_data, event_bus, templates)
```

- [ ] **Step 4: Run — GREEN**

`micromamba run -n shiny python -m pytest tests/test_templates_module.py tests/test_templates.py -q` → `40 passed` (39 where 8.3 short names are disabled and that test skips).

- [ ] **Step 5: Run the CI unit command** → green.

- [ ] **Step 6: Commit**

```powershell
git add sespy/modules/templates.py tests/test_templates_module.py
git commit -m @'
feat(templates): MarineSABRES and SESPy groups with badges in the gallery (P2 §6.2)

The panel lists list_catalogue() + list_templates() under two h4 headers
with session.ns ids (templates-group_marinesabres / templates-group_sespy);
MarineSABRES cards show category, complexity, version and regional-sea
badges and a collapsed "About this template". One combined index drives the
pre-wired Load buttons. A category or complexity without a translation key
shows R's raw value.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
'@
```

---

### Task 9: e2e — update `test_templates_e2e.py`, add `test_r_templates_e2e.py`

**Files:**
- Modify: `tests/test_templates_e2e.py` (whole file below)
- Create: `tests/test_r_templates_e2e.py` (picked up by `tests/run_e2e.py` via `test_*_e2e.py`; excluded from the CI unit command by `--ignore-glob='*e2e*'`)

**Interfaces:** Consumes `#sespy_nav_templates`, `#templates-templates_list h5`, `#templates-load_template_<i>`, `#templates-group_marinesabres`, `#templates-group_sespy`, `.sespy-template-badges .badge`, `.shiny-notification`, `#sespy_nav_cld`, `window.pyvisNetworks['cld-network'].nodes`. Other e2e scripts (`test_bot_e2e.py`, `test_boolean_happy_e2e.py`, `test_pims_project_e2e.py`, `test_wizard_e2e.py`) already find their card by **exact** `h5` text ("Minimal Demo", "Coastal Tourism SES"), so the new group needs no change there.

**Not run while planning** (servers were out of scope): both scripts were only `py_compile`d.

- [ ] **Step 1: Replace `tests/test_templates_e2e.py` with** (index 0 is now Caribbean; exact names; the stale "≥ 15 elements" claim becomes "exactly 17")

```python
"""E2E for Templates: panel renders, clicking a template loads it,
analysis modules see the new data."""
import asyncio

from playwright.async_api import async_playwright

TARGET = "Coastal Tourism SES"


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 900})
        await page.goto("http://127.0.0.1:8000", wait_until="networkidle")
        await page.wait_for_selector("#sespy_nav_templates", timeout=60000)

        # Click Templates nav
        await page.click("#sespy_nav_templates")
        # templates_list is a suspended @render.ui inside the hidden pane: its
        # first render (list_catalogue() + list_templates()) begins at this nav
        # click, so wait for the cards instead of sleeping. Shiny swaps an
        # output_ui's innerHTML atomically, so once one h5 is present the whole
        # list is present.
        await page.wait_for_selector("#templates-templates_list h5", timeout=60000)

        # Every h5 in the list is a card name (group headers are h4), in the
        # order of the load_template_<i> buttons: the 7 MarineSABRES templates
        # first, then SESPy's 4 examples.
        cards = await page.evaluate(
            "() => Array.from(document.querySelectorAll('#templates-templates_list h5'))"
            ".map(e => e.textContent.trim())"
        )
        print("templates listed:", cards)
        assert len(cards) == 11, f"expected 7 + 4 templates, got {cards}"
        # Exact names: R's "Offshore Wind Energy (MarineSABRES)" also contains
        # "Offshore Wind", so a substring check would prove nothing.
        assert "Offshore Wind Farm SES" in cards, f"Offshore Wind Farm SES missing: {cards}"
        assert TARGET in cards, f"{TARGET} missing: {cards}"

        # Load the Coastal Tourism SES card, found by its exact h5 text (index
        # 0 is now the Caribbean MarineSABRES template).
        idx = cards.index(TARGET)
        # The h5s render before Shiny binds the buttons; an unbound click is lost.
        await page.wait_for_selector(f"#templates-load_template_{idx}.shiny-bound-input", timeout=15000)
        await page.click(f"#templates-load_template_{idx}")
        # The load can only be proven by its own success toast. Coastal
        # Tourism SES (sespy/templates/coastal_tourism.json) is graph-identical
        # to the seeded sample (same 17 element ids/labels, 20 connections),
        # so NO CLD node count can distinguish "loaded" from "never loaded",
        # and .shiny-notification alone is shared with the autosave
        # "Recovered work" banner. Match the interpolated template name in
        # parentheses: templates.py builds t("templates.loaded") + f" ({info.name})"
        # only on the success path (the except branch's message is
        # f"Couldn't load template: {e}" and never carries the name), and
        # matching the name rather than the translated sentence keeps this
        # language-independent.
        await page.wait_for_function(
            """(name) => Array.from(document.querySelectorAll('.shiny-notification'))
              .some(n => (n.textContent || '').includes('(' + name + ')'))""",
            arg=TARGET,
            timeout=30000,
        )

        # Sanity check only (the toast above is the proof): the CLD still
        # shows 17 nodes, as it would for the seeded sample.
        await page.click("#sespy_nav_cld")
        n = None
        for _ in range(30):
            n = await page.evaluate("""() => {
              const s = window.pyvisNetworks && window.pyvisNetworks['cld-network'];
              return s && s.nodes ? s.nodes.length : null;
            }""")
            if n == 17:
                break
            await page.wait_for_timeout(500)
        print(f"CLD nodes after template load: {n}")
        assert n == 17, f"CLD should show 17 nodes after loading Coastal Tourism SES: {n}"

        await page.screenshot(path="tests/screenshots/templates.png")
        print("\ntemplates e2e assertions pass")
        await browser.close()


asyncio.run(main())
```

- [ ] **Step 2: Create `tests/test_r_templates_e2e.py`**

```python
"""E2E for P2: the MarineSABRES template group in the Templates panel.

Both group headers render with namespaced ids, the "Offshore Wind Energy
(MarineSABRES)" card shows its badges, Load shows the success toast with its
name, and the CLD then shows exactly 23 nodes. The seeded sample already has
17, so polling for n > 0 would prove nothing; OffshoreWind is the only
template with 23 elements, and the CLD shows every DAPSI(W)R(M) type by
default. Namespaced ids only, no bare text= selectors.
"""
import asyncio

from playwright.async_api import async_playwright

URL = "http://127.0.0.1:8000"
LIST = "#templates-templates_list"
NAME = "Offshore Wind Energy (MarineSABRES)"
BADGES = ["Energy", "Complex", "v2.2", "North Sea"]


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await (await browser.new_context()).new_page()
        await page.set_viewport_size({"width": 1280, "height": 900})
        await page.goto(URL, wait_until="networkidle")
        # The nav is server-rendered (cold server ~32 s idle; more under load).
        await page.wait_for_selector("#sespy_nav_templates", timeout=60000)
        await page.click("#sespy_nav_templates")
        await page.wait_for_selector(f"{LIST} h5", timeout=60000)

        # ---- both groups, MarineSABRES first ---------------------------------
        await page.wait_for_selector("#templates-group_marinesabres", state="visible", timeout=15000)
        await page.wait_for_selector("#templates-group_sespy", state="visible", timeout=15000)
        order = await page.evaluate(
            """() => {
              const a = document.getElementById('templates-group_marinesabres');
              const b = document.getElementById('templates-group_sespy');
              return !!(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);
            }""")
        assert order, "MarineSABRES group should come before SESPy examples"
        print("group headers: MarineSABRES templates, SESPy examples")

        # ---- the Offshore Wind Energy card and its badges --------------------
        cards = await page.evaluate(
            f"() => Array.from(document.querySelectorAll('{LIST} h5'))"
            ".map(e => e.textContent.trim())")
        assert cards.count(NAME) == 1, cards
        idx = cards.index(NAME)
        badges = await page.evaluate(
            """([list, name]) => {
              const h5 = Array.from(document.querySelectorAll(list + ' h5'))
                .find(e => e.textContent.trim() === name);
              const row = h5 && h5.parentElement.querySelector('.sespy-template-badges');
              return row ? Array.from(row.querySelectorAll('.badge'))
                .map(b => b.textContent.trim()) : null;
            }""", [LIST, NAME])
        assert badges == BADGES, badges
        print(f"card {idx}: {NAME} badges {badges}")

        # ---- Load: toast with the name, then exactly 23 CLD nodes ------------
        # The h5s render before Shiny binds the buttons; an unbound click is lost.
        await page.wait_for_selector(f"#templates-load_template_{idx}.shiny-bound-input", timeout=15000)
        await page.click(f"#templates-load_template_{idx}")
        await page.wait_for_function(
            """(name) => Array.from(document.querySelectorAll('.shiny-notification'))
              .some(n => (n.textContent || '').includes('(' + name + ')'))""",
            arg=NAME, timeout=30000)
        print("toast names the template")

        await page.click("#sespy_nav_cld")
        n = None
        for _ in range(60):
            n = await page.evaluate("""() => {
              const s = window.pyvisNetworks && window.pyvisNetworks['cld-network'];
              return s && s.nodes ? s.nodes.length : null;
            }""")
            if n == 23:
                break
            await page.wait_for_timeout(500)
        assert n == 23, f"CLD should show the template's 23 elements, got {n}"
        print("CLD shows 23 nodes")

        await browser.close()
        print("r-templates e2e: all assertions passed")


asyncio.run(main())
```

- [ ] **Step 3: Compile check** `micromamba run -n shiny python -m py_compile tests/test_templates_e2e.py tests/test_r_templates_e2e.py` → exit 0.

- [ ] **Step 4: Run each solo against a fresh server** (port 8000 must be free; nothing heavy alongside)

Run them the way the gate does (SHINY_TESTMODE, PYTHONPATH, throwaway feedback DB, warm-up session), through `run_e2e.py`'s own functions. `run_e2e.py` has no single-script option, so write `<scratchpad>\e2e_solo.py` (loaded by path: `from tests.run_e2e` would hit the stray site-packages `tests`):
```python
"""Run named e2e scripts solo, exactly as tests/run_e2e.py runs them.
Usage (from the SESPy repo root): python e2e_solo.py tests/test_a_e2e.py [...]"""
import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("run_e2e", Path("tests/run_e2e.py").resolve())
E = importlib.util.module_from_spec(spec)
spec.loader.exec_module(E)
url = "http://127.0.0.1:8000/"
if E.port_busy(url):
    sys.exit("port 8000 is busy: kill it first")
proc = E.start_server(8000, {})
code = 0
try:
    if not E.wait_ready(url):
        sys.exit("server never answered")
    E.warm_session(url)
    for s in sys.argv[1:]:
        r = E.run_script(E.ROOT / s)
        print(f"{'PASS' if r.returncode == 0 else 'FAIL'} {s}\n{r.stdout[-1500:]}{r.stderr[-1500:]}")
        code |= r.returncode != 0
finally:
    E.stop_server(proc)
sys.exit(code)
```
```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue   # must print nothing
micromamba run -n shiny python -I '<scratchpad>\e2e_solo.py' tests/test_r_templates_e2e.py tests/test_templates_e2e.py
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue   # must print nothing again
```
(`-I` is safe here: `run_e2e.py` is loaded by absolute path and the scripts run in child processes with `PYTHONPATH` set.) Expected: `PASS` for both, with last lines `r-templates e2e: all assertions passed` and `templates e2e assertions pass`. If 8000 is still held afterwards, stop it **by port**. (The red step for this behaviour is Task 8's in-memory module test; on pre-Task-8 code `test_r_templates_e2e.py` times out waiting for `#templates-group_marinesabres`.)

- [ ] **Step 5: Run the CI unit command** → green (the e2e files are ignored by it).

- [ ] **Step 6: Commit**

```powershell
git add tests/test_templates_e2e.py tests/test_r_templates_e2e.py
git commit -m @'
test(e2e): MarineSABRES template group; exact-name template selection (P2)

test_templates_e2e.py loads "Coastal Tourism SES" by its exact h5 (index 0
is now Caribbean), checks "Offshore Wind Farm SES" by exact name and the
CLD for exactly 17 nodes. New test_r_templates_e2e.py: both namespaced
group headers, the Offshore Wind Energy (MarineSABRES) badges, the toast,
and exactly 23 CLD nodes after loading it.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
'@
```

---

### Task 10: Release docs — MANUAL §7, README, CHANGELOG, templates screenshot

**Files:** Modify `docs/MANUAL.md` (§7 Templates), `README.md`, `CHANGELOG.md`, `docs/screenshots/templates.png`.

- [ ] **Step 1: Check the version is still 1.14.0 everywhere**

Grep `1\.13\.0|1\.14\.0` in `sespy/__init__.py`, `pyproject.toml`, `docs/MANUAL.md` line 3 → only `1.14.0` in the version lines.

- [ ] **Step 2: MANUAL §7** — replace the two paragraphs
```
**Controls.** One card per template with its name, size, demonstration area and description, and a "Load" button. Loading replaces the current project, so save first if you want to keep your work; the panel says so at the top.

**Shipped templates.** Coastal Tourism SES (17 elements, 20 connections, Tuscan Archipelago), Minimal Demo (5 and 6, a positive three-cycle plus a mutually activating pair, useful for learning the analyses), Offshore Wind Farm SES (19 and 21, Macaronesia), Small-scale Coastal Fisheries SES (18 and 22, Arctic Northeast Atlantic).
```
with
```
**Controls.** 11 templates in two groups: "MarineSABRES templates" (the 7 curated templates of the R MarineSABRES SES Toolbox) and "SESPy examples" (SESPy's own 4). One card per template with its name, size and description, and a "Load" button. A MarineSABRES card also shows badges for its category, its complexity ("Simple" or "Complex"), its template version and its regional sea, and a collapsed "About this template" section with the template's source and usage notes. A SESPy example shows its demonstration area instead. Loading replaces the current project, so save first if you want to keep your work; the panel says so at the top.

**Shipped templates: MarineSABRES.** R's template names with " (MarineSABRES)" appended, so they never clash with SESPy's examples: Caribbean Island - Comprehensive SES Template (78 elements, 140 connections, Caribbean Sea, complex), Climate Change (25 and 28, Arctic Ocean), Coastal Lagoon (28 and 30, Baltic Sea), Fisheries (26 and 33, Baltic Sea), Offshore Wind Energy (23 and 27, North Sea, complex), Pollution (28 and 29, Baltic Sea), Tourism (26 and 33, Mediterranean Sea). "Coastal Lagoon (MarineSABRES)" is R's aquaculture template: R names it "Coastal Lagoon", and SESPy keeps R's name. The templates are converted from R release v1.31.0: R's Measures appear as Responses, every link keeps its sign, strength and description, and its confidence (kept within SESPy's 1–5 scale); R records no delays, so every link starts as "immediate". The Caribbean template is large; analyses with a node limit (Boolean allows at most 12 nodes) say so instead of running.

**Shipped templates: SESPy examples.** Coastal Tourism SES (17 elements, 20 connections, Tuscan Archipelago), Minimal Demo (5 and 6, a positive three-cycle plus a mutually activating pair, useful for learning the analyses), Offshore Wind Farm SES (19 and 21, Macaronesia), Small-scale Coastal Fisheries SES (18 and 22, Arctic Northeast Atlantic).
```
(Keep the words "Shipped templates": `tests/test_help_offcanvas.py::test_section_stops_before_the_next_heading` asserts them in the Templates section — found while planning.)

- [ ] **Step 3: README** — three anchored edits:

Replace `| Picker for built-in starter projects (Offshore Wind, Coastal Tourism, Small-scale Fisheries). |` with
```
| Picker for built-in starter projects in two groups: R's 7 curated MarineSABRES templates (badges for category, complexity, version, regional sea) and SESPy's 4 examples (Offshore Wind, Coastal Tourism, Small-scale Fisheries, Minimal Demo). |
```
Replace ``| `sespy/templates/` | Built-in starter projects: Offshore Wind, Coastal Tourism, Small-scale Fisheries. `list_templates()` discovers `*.json` files. |`` with
```
| `sespy/templates/` | Built-in starter projects: SESPy's examples (Offshore Wind, Coastal Tourism, Small-scale Fisheries, Minimal Demo), discovered by `list_templates()` from the top-level `*.json` files, and in `marinesabres/` R's 7 curated templates, pre-converted by `python -m scripts.sync_r_templates` and listed by `list_catalogue()` from the generated `catalogue.json`. |
```
Replace `- `tests/test_templates.py` — every template loads and validates, distinct names, populated metadata` with
```
- `tests/test_templates.py` — every template loads and validates, distinct names, populated metadata; the MarineSABRES catalogue listing (bad entries skipped, package data)
- `tests/test_templates_module.py` — the Templates panel in memory: group headers, badges, loading by index
- `tests/test_r_template_catalogue.py` — the R template sync (`scripts/sync_r_templates.py`): category port, catalogue, drift guard against the pinned R fixtures, `--check`, accepted warnings
```
(The "N standalone Playwright scripts (M runs" line is updated in Task 12 from `run_e2e.py`'s own summary, not by arithmetic.)

- [ ] **Step 4: CHANGELOG** — replace
```
## [Unreleased]

## [1.13.0] — 2026-10-17
```
with
```
## [Unreleased]

## [1.14.0] — 2026-10-18

Roadmap P2 (curated R templates; R-parity roadmap §2 P2). Ports R
MarineSABRES 1.21.1, 1.22.1 and 1.22.3 (the reviewed curated templates),
against R v1.31.0 (`4b53b7d`).

### Added

- **R's 7 curated templates in the gallery.** The Templates panel now has
  two groups: "MarineSABRES templates" (Caribbean Island, Climate Change,
  Coastal Lagoon, Fisheries, Offshore Wind Energy, Pollution, Tourism — 320
  links in total) and "SESPy examples" (SESPy's own 4). R's names carry the
  suffix " (MarineSABRES)"; "Coastal Lagoon (MarineSABRES)" is R's
  aquaculture template.
- **Badges** on each MarineSABRES card: category (R's rule: Multi-Stressor,
  Extraction, Recreation, Production, Pollution, Climate, Energy or
  General), complexity, template version and regional sea, plus an "About
  this template" section with the source and usage notes. Category and
  complexity labels are translated into all 9 languages.
- **`python -m scripts.sync_r_templates`** re-converts the templates from an
  R git checkout (read with `git show`, never checked out) and rewrites the
  fixtures, the pin and the R_SYNC.md block together; `--check` reports
  drift and a unit test guards it. Off-rule links or type mismatches in a
  future R release fail the sync unless they are explicitly accepted.

### Changed

- R pin moved from v1.29.0 to **v1.31.0** (`4b53b7d`); the pinned files are
  unchanged. R's `functions/template_loader.R` is now pinned too, and a
  parity test checks the category rule against it. R's changes since v1.29.0
  are triaged in `docs/parity/R_SYNC.md`.
- R template mapper hardening: `connections` that is not a list and a
  connection that is not an object raise a clear error; integer element ids
  (including 0) and integer connection endpoints now match.

### Deliberate differences from R

- No complexity filter (R's user levels come with P12) and no preview or
  customise-before-load step (P13); templates load directly.
- Category and complexity labels are translated (R shows the English value).
- Template names, descriptions, sources and usage notes stay in English.

## [1.13.0] — 2026-10-17
```

- [ ] **Step 5: Re-shoot only the templates screenshot**

`tests/make_docs_screenshots.py` has no per-panel option: it shoots every panel into `--out`. Shoot into a scratch dir and copy back only `templates.png`:
```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue   # nothing
$srv = Start-Process micromamba.exe -ArgumentList "run -n shiny python -m shiny run --port 8000 app.py" -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 40
micromamba run -n shiny python tests/make_docs_screenshots.py --port 8000 --out <scratchpad>\shots
Copy-Item <scratchpad>\shots\templates.png docs\screenshots\templates.png
Get-NetTCPConnection -LocalPort 8000 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
Stop-Process -Id $srv.Id -Force -ErrorAction SilentlyContinue
```
Open `docs/screenshots/templates.png` (Read tool): the "MarineSABRES templates" header and the Caribbean card with its badges are visible. Run `attrib +P docs\screenshots\templates.png` (OneDrive: keep it local so the About→Manual image loads).

- [ ] **Step 6: Run** `micromamba run -n shiny python -m pytest tests/test_manual.py tests/test_help_offcanvas.py -q` → `29 passed`; then the CI unit command → green.

- [ ] **Step 7: Commit**

```powershell
git add docs/MANUAL.md README.md CHANGELOG.md docs/screenshots/templates.png
git commit -m @'
docs(release): 1.14.0 changelog, manual templates section, templates screenshot (P2)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
'@
```

---

### Task 11: Roadmap edits on `docs/r-parity-roadmap` (same release cycle)

**Files:** `docs/superpowers/specs/2026-10-16-r-parity-roadmap-design.md` on branch `docs/r-parity-roadmap` (HEAD `481b804`), edited in a scratchpad worktree so the feature branch checkout is never switched.

The 16 edits below were verified while planning: each old string occurs exactly once in the branch's file (`16/16 edits applied`). They cover spec §9: header pin and SESPy version; the P2 section (R source v1.31.0 + `template_loader.R`, `sespy/templates/marinesabres/` + `catalogue.json`, cards read `catalogue.json`, v1.14.0, deferrals); P12 gains R's complexity filter; P13 gains R's preview / customise-before-load flow; the triage owners (K1 country count re-check, P1b `Policy_Target` and stakeholder roles, P4 governance profiles / readiness items / readiness page, §3 allow-list gains the two WP5 files); the §3 i18n note; plus the §3 sync-tracking baseline, the "R files never ship" clarification and the release list.

- [ ] **Step 1: Worktree**

```powershell
git -c core.longpaths=true worktree add <scratchpad>\p2-roadmap docs/r-parity-roadmap
```

- [ ] **Step 2: Write `<scratchpad>\roadmap_edits.py`**

```python
"""Verify (and apply to a copy) the P2 roadmap edits: each old string must
occur exactly once. Usage: python roadmap_edits.py <roadmap_lf.md> <out.md>"""
import sys
from pathlib import Path

EDITS = [
    # E1 header
    ("""Date: 2026-10-16 (revised after review loops 1–3; amended 2026-10-17 after
P0 shipped and the P1a spec converged)
Baseline: MarineSABRES_SES_Shiny **v1.29.0** (`e33faea`; verified identical to
the laguna deployment on 2026-10-17). The original baseline was v1.28.0
(`e3c3b77`) against SESPy v1.12.1. SESPy is now at **v1.12.3** (P0 shipped).""",
     """Date: 2026-10-16 (revised after review loops 1–3; amended 2026-10-17 after
P0 shipped and the P1a spec converged; amended 2026-10-18 by P2)
Baseline: MarineSABRES_SES_Shiny **v1.31.0** (`4b53b7d`, re-pinned by P2 on
2026-10-18). The files pinned so far are identical to v1.29.0 (`e33faea`),
which was verified against the laguna deployment on 2026-10-17. The original
baseline was v1.28.0 (`e3c3b77`) against SESPy v1.12.1. SESPy is now at
**v1.14.0** (P0, P1a and P2 shipped)."""),
    # E2 P1b R source
    ("R source: 1.19.0, 1.23.0 (WS-3a), 1.24.0 (WS-4), 1.29.0 (`PestleTag`).",
     "R source: 1.19.0, 1.23.0 (WS-3a), 1.24.0 (WS-4), 1.29.0 (`PestleTag`),\n"
     "1.30.0 (WS-9a: `Policy_Target`, stakeholder roles; triaged by P2)."),
    # E3 P1b indicator fields + stakeholder bullet
    ("""- Element indicator fields with R's names: `Indicator, Indicator_Unit,
  Data_Source, Registry_Id, Registry_Version`, on **all elements except
  Responses**.""",
     """- Element indicator fields with R's names: `Indicator, Indicator_Unit,
  Data_Source, Registry_Id, Registry_Version` and, since R 1.30.0, the
  optional `Policy_Target` (`constants.R` `ISA_INDICATOR_COLUMNS`,
  `functions/indicator_snapshot.R`), on **all elements except Responses**.
- **Stakeholder roles (R 1.30.0, WS-9a):** the PIMS stakeholder register gains
  `NERoles` (D5.4 actor roles, Newton & Elliott typology) and `SourceId`
  (`functions/stakeholder_schema.R`, `modules/pims_stakeholder_module.R`),
  plus "Load DA actor list". Also check SESPy's stakeholders page against R's
  duplicate-row fix `33ddd96` (one row per add, safe id counter)."""),
    # E4 K1 country db
    ("""- **`country_governance_db.json`**: 97 countries, 11 seas and 8 conventions,
  giving governance context.""",
     """- **`country_governance_db.json`**: 97 countries, 11 seas and 8 conventions
  at v1.29.0, giving governance context. R v1.30.0 added Greenland, the Faroe
  Islands and seven regional bodies (99 countries, 15 conventions/bodies at
  v1.31.0, triaged in R_SYNC.md); re-check the counts at K1's pin."""),
    # E5 P2 R source + spec + release
    ("""R source: 1.21.1, 1.22.1, 1.22.3. Depends on P1a; soft dependency on K1
(R templates say they were rebuilt from KB contexts).""",
     """R source: 1.21.1, 1.22.1, 1.22.3, pinned at v1.31.0 (`4b53b7d`), plus
`functions/template_loader.R` (the category rule). **Detailed spec:**
`docs/superpowers/specs/2026-10-18-p2-curated-templates-design.md`. Shipped
in **SESPy v1.14.0**. Depends on P1a; soft dependency on K1
(R templates say they were rebuilt from KB contexts)."""),
    # E6 P2 ship location
    ("""- Ship them in `sespy/templates/` beside SESPy's 4. Names get an origin""",
     """- Ship them pre-converted in `sespy/templates/marinesabres/` with a
  generated `catalogue.json`, as a second gallery group beside SESPy's 4.
  Names get an origin"""),
    # E7 P2 cards + deferrals
    ("""  `tests/parity/r_sync.json` and `docs/parity/R_SYNC.md`. Gallery cards read
  `ConversionReport.template_meta` (complexity, usage notes, source,
  applicable regions).""",
     """  `tests/parity/r_sync.json` and `docs/parity/R_SYNC.md`. Gallery cards
  read `catalogue.json` (category, complexity, version, regional-sea label;
  source and usage notes under "About this template").
- Deferred: R's complexity filter (P12) and R's template preview /
  customise-before-load flow (P13)."""),
    # E8 P4 R source
    ("R source: 1.19.0, 1.22.0 (N48), 1.23.0, 1.24.0. Depends on P1b; loader from K1.",
     "R source: 1.19.0, 1.22.0 (N48), 1.23.0, 1.24.0, 1.30.0 (WS-9a governance\n"
     "profiles), 1.31.0 (WS-9b readiness check). Depends on P1b; loader from K1."),
    # E9 P4 bullet before done-when
    ("""- **Done when:** loaded asset counts and ids equal the vendored copy, and, when""",
     """- **D5.4 governance (R 1.30.0/1.31.0, triaged by P2):** the "Governance
  context (D5.4)" tab with "Add to register" (`modules/wp5_governance_context_module.R`,
  `functions/wp5_governance.R`, data `wp5_governance_profiles.json`) and the
  PIMS "Governance readiness (D5.4)" page (`modules/wp5_readiness_module.R`,
  `functions/wp5_readiness.R`, data `wp5_readiness_items.json`). Their strings
  (`translations/modules/wp5_governance.json`, `wp5_readiness.json`) live
  outside `data/` and are always vendored.
- **Done when:** loaded asset counts and ids equal the vendored copy, and, when"""),
    # E10 §3 allow-list
    ("""  `wp5_scenarios_ssp.json` and `wp5_worldview_matrix.json` (P8, R 1.29.0),""",
     """  `wp5_scenarios_ssp.json` and `wp5_worldview_matrix.json` (P8, R 1.29.0),
  `wp5_governance_profiles.json` and `wp5_readiness_items.json` (P4, R
  1.30.0/1.31.0; their version keys are named when P4 adds them),"""),
    # E11 §3 fixtures never ship
    ("""  They are never read at runtime and never ship (`deploy.sh` excludes
  `tests/`).""",
     """  They are never read at runtime and never ship (`deploy.sh` excludes
  `tests/`). P2 ships SESPy projects converted from the templates
  (`sespy/templates/marinesabres/`); the R files themselves still never ship."""),
    # E12 §3 sync tracking
    ("""matches (baseline v1.29.0 @ `e33faea`, verified against laguna on 2026-10-17),""",
     """matches (baseline v1.31.0 @ `4b53b7d` since P2; the pinned files are
identical to v1.29.0 @ `e33faea`, verified against laguna on 2026-10-17),"""),
    # E13 §3 i18n note
    ("""older strings are mapped explicitly. e2e selectors stay scoped and namespaced.""",
     """older strings are mapped explicitly. e2e selectors stay scoped and namespaced.
SESPy-only UI keys with no R counterpart may live in `core.json` (P2's
`templates.group_*`, `templates.category_*`, `templates.complexity_*` and
`templates.about`: R shows those values untranslated)."""),
    # E14 §3 releases
    ("- P0 = v1.12.2 (hotfix) + v1.12.3 (P0b); P1a = v1.13.0. Then one minor release",
     "- P0 = v1.12.2 (hotfix) + v1.12.3 (P0b); P1a = v1.13.0; P2 = v1.14.0. Then one minor release"),
    # E15 P12 row
    ("(menus, AI element caps; per-session store, R 1.20.0 N20)",
     "(menus, AI element caps; per-session store, R 1.20.0 N20); R's template "
     "complexity filter (`template_ses_module.R:125-141`, deferred from P2)"),
    # E16 P13 row
    ("`connection_review_tabbed` (observer-leak fix R 1.21.0 N30)",
     "`connection_review_tabbed` (observer-leak fix R 1.21.0 N30); R's template "
     "preview / customise-before-load flow (`template_ses_module.R`, deferred from P2)"),
]

text = Path(sys.argv[1]).read_bytes().decode("utf-8").replace("\r\n", "\n")
bad = 0
for i, (old, new) in enumerate(EDITS, 1):
    n = text.count(old)
    if n != 1:
        print(f"E{i}: old string occurs {n} times")
        bad += 1
        continue
    text = text.replace(old, new)
Path(sys.argv[2]).write_bytes(text.encode("utf-8"))
print(f"{len(EDITS) - bad}/{len(EDITS)} edits applied")
sys.exit(1 if bad else 0)
```

- [ ] **Step 3: Apply in place and review**

```powershell
$f = '<scratchpad>\p2-roadmap\docs\superpowers\specs\2026-10-16-r-parity-roadmap-design.md'
micromamba run -n shiny python -I <scratchpad>\roadmap_edits.py $f $f    # 16/16 edits applied
git -c core.longpaths=true -C <scratchpad>\p2-roadmap diff --ignore-cr-at-eol --stat             # 1 file, ~53 insertions, ~20 deletions
```
(The script normalises to LF; git normalises line endings on add, so the diff is content only.)

- [ ] **Step 4: Commit on the roadmap branch**

```powershell
git -c core.longpaths=true -C <scratchpad>\p2-roadmap add docs/superpowers/specs/2026-10-16-r-parity-roadmap-design.md
git -c core.longpaths=true -C <scratchpad>\p2-roadmap commit -m @'
docs(roadmap): P2 shipped as v1.14.0; re-pin v1.31.0 and triage owners

Header pin/version, the P2 section (marinesabres/ + catalogue.json,
template_loader.R, v1.14.0, deferrals), P12 complexity filter, P13
preview/customise flow, K1 country re-check, P1b Policy_Target and
stakeholder roles, P4 D5.4 governance and readiness, allow-list WP5 files,
i18n note for SESPy-only core.json keys.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
'@
git -c core.longpaths=true worktree remove <scratchpad>\p2-roadmap
```
Pushing `docs/r-parity-roadmap` happens in Task 13 Step 7, with the user's go-ahead.

---

### Task 12: Gates — CI unit, sync check, full e2e, MosaicSES, reviews (README count commit only)

- [ ] **Step 1: CI unit command** on the branch tip → green (≈1224 passed, 1 skipped).

- [ ] **Step 2: Sync check at the pin**

```powershell
$R = 'C:\Users\arturas.baziukas\OneDrive - ku.lt\HORIZON_EUROPE\Marine-SABRES\SESToolbox\MarineSABRES_SES_Shiny'
micromamba run -n shiny python -m scripts.sync_r_templates --r-root $R --check     # exit 0, no output
micromamba run -n shiny python -m scripts.sync_r_templates --from-fixtures --check  # exit 0, no output
micromamba run -n shiny python -m ruff check sespy/r_template_catalogue.py sespy/templates/__init__.py sespy/modules/templates.py sespy/r_template_mapper.py scripts tests/test_r_template_catalogue.py tests/test_templates.py tests/test_templates_module.py tests/parity   # All checks passed!
micromamba run -n shiny python -m ruff check sespy tests app.py --statistics      # Found 54 errors (the pre-P2 baseline, none new)
```

- [ ] **Step 3: Full e2e gate, detached** (the Bash tool kills anything past 10 min even backgrounded). Port 8000 free, nothing heavy running:
```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue   # must print nothing
$log = "<scratchpad>\e2e-p2.log"
Start-Process micromamba.exe -ArgumentList "run -n shiny python -u tests/run_e2e.py" -RedirectStandardOutput $log -RedirectStandardError "$log.err" -WindowStyle Hidden
```
Poll in bounded PowerShell calls (`Start-Sleep -Seconds 240; Get-Content '<scratchpad>\e2e-p2.log' -Tail 15` — literal path, `$log` is gone in a new call) until the summary prints; do not park on a background monitor. Expected: every script PASS, including the new `test_r_templates_e2e.py` and the updated `test_templates_e2e.py` (one more script than the last green run). Any red: rerun that script **solo** (Task 9 Step 4 procedure) before believing it; green solo = load flake, red solo = regression (new i18n labels can collide with another module's selector: scope it). After the run: port 8000 free, `git status --short` shows only the user's `LITERATURE/` entries, and sweep orphans:
```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CreationDate -gt (Get-Date).AddHours(-2) } | Select-Object ProcessId, CreationDate, CommandLine
```

- [ ] **Step 4: README e2e count from the gate's own summary**

Set the `N standalone Playwright scripts (M runs` numbers in README.md (the paragraph after the `make_docs_screenshots.py` block; today it reads `31 ... (32 runs`) **and** the script count in the `# Full Playwright e2e — one command boots the server, runs all 31 browser` comment (README line ≈468) to what `run_e2e.py` reported. If they changed:
```powershell
git add README.md
git commit -m @'
docs(readme): e2e script count after P2's test_r_templates_e2e.py

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
'@
```

- [ ] **Step 5: MosaicSES gate — full suite incl. e2e** (shared env; it imports SESPy from this working tree). MosaicSES's own release gate is `python -m pytest tests -q -p no:cacheprovider` (unit + pytest-playwright e2e, ≈15–20 min), so detach it too, with port 8000 free:
```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue   # must print nothing
$mlog = "<scratchpad>\mosaicses-p2.log"
Start-Process micromamba.exe -ArgumentList "run -n shiny python -m pytest tests -q -p no:cacheprovider" -WorkingDirectory "C:\Users\arturas.baziukas\OneDrive - ku.lt\HORIZON_EUROPE\Marine-SABRES\MosaicSES" -RedirectStandardOutput $mlog -RedirectStandardError "$mlog.err" -WindowStyle Hidden
```
Poll with bounded `Start-Sleep -Seconds 240; Get-Content '<scratchpad>\mosaicses-p2.log' -Tail 5` calls (literal path). Expected: all green. Never gate MosaicSES on `-k "not e2e"`. P2 changes no serialisation and no module MosaicSES reuses (MosaicSES does not import `sespy.templates`), so a red here is environmental until shown otherwise — rerun the failing test solo, then triage.

- [ ] **Step 6: Implementation review loop** — superpowers:requesting-code-review over `docs/p2-design..HEAD` (the implementation commits only, not the spec/plan), repeated until a round finds no Critical or Important issues; each fix is its own commit followed by the CI unit command (and `--check`).

---

### Task 13: Merge, tag v1.14.0, deploy, verify — **each step needs the user's go-ahead**

- [ ] **Step 1 (user go-ahead): Merge onto `origin/main` in a temp worktree** (local `main` may be behind, and the untracked `LITERATURE/` files block a fast-forward in the main checkout):
```powershell
$W = '<scratchpad>\sespy-release'
git fetch origin
git -c core.longpaths=true worktree add $W origin/main
git -c core.longpaths=true -C $W switch -c release/1.14.0
git -c core.longpaths=true -C $W merge --no-ff feat/p2-curated-templates -m @'
Merge v1.14.0 (P2: curated R templates in the gallery) into main

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
'@
```
Conflicts are possible only in `CHANGELOG.md`/`LITERATURE/` (origin/main carries literature-alert commits); keep both sides. Set the `## [1.14.0]` date in `CHANGELOG.md` to the actual release date if it differs (amend nothing: a separate commit in the worktree). Then, in **one** PowerShell call starting with `Set-Location '<scratchpad>\sespy-release'`, run the CI unit command → green, and `micromamba run -n shiny python -m scripts.sync_r_templates --from-fixtures --check` → exit 0.

- [ ] **Step 2 (user go-ahead): Push and tag**
```powershell
$W = '<scratchpad>\sespy-release'
git -c core.longpaths=true -C $W push origin release/1.14.0:main
git -c core.longpaths=true -C $W tag -a v1.14.0 -m "v1.14.0 — P2: curated R templates in the gallery"
git -c core.longpaths=true -C $W push origin v1.14.0
```

- [ ] **Step 3 (user go-ahead): Deploy from the worktree**
```powershell
$W = '<scratchpad>\sespy-release'
Copy-Item "C:\Users\arturas.baziukas\OneDrive - ku.lt\HORIZON_EUROPE\Marine-SABRES\SESPy\deploy\config.env" "$W\deploy\config.env"   # gitignored, not in the worktree
Set-Location $W; bash deploy/deploy.sh
```
Expected: `==> Deploying SESPy v1.14.0 to ...`. `deploy.sh` ships the whole `sespy/` (so `templates/marinesabres/` goes too) and not `scripts/`/`tests/`. The deployed `sespy/` is symlinked into the live MosaicSES, so this deploy changes MosaicSES immediately.

- [ ] **Step 4 (user go-ahead): Verify on laguna with the worker's Python** (user site disabled: `-s`). Write `<scratchpad>\verify_p2.py`:
```python
"""Run on laguna from the SESPy app dir with the worker python:
/opt/micromamba/envs/shiny/bin/python3 -s /tmp/verify_p2.py"""
import sys

sys.path.insert(0, ".")
import sespy  # noqa: E402
from sespy.templates import list_catalogue, list_templates, load_template  # noqa: E402

assert sespy.__version__ == "1.14.0", sespy.__version__
rows = list_catalogue()
assert len(rows) == 7, [r.name for r in rows]
assert rows[0].name == "Caribbean Island - Comprehensive SES Template (MarineSABRES)"
assert len(list_templates()) == 4
wind = next(r for r in rows if r.name == "Offshore Wind Energy (MarineSABRES)")
p = load_template(wind.file)
assert (p.isa_data.element_count(), p.isa_data.connection_count()) == (23, 27)
assert p.metadata.origin == "r_template" and p.metadata.r_template_version == "2.2"
print("P2 gallery OK:", sespy.__file__, wind.file)
```
Then, in **one** Bash tool call (`config.env` is bash syntax; scratchpad path with forward slashes; the `cd` must be in the same command because the cwd resets between calls):
```bash
cd "<scratchpad>/sespy-release" && source deploy/config.env && \
scp "<scratchpad>/verify_p2.py" "$DEPLOY_SERVER:/tmp/verify_p2.py" && \
ssh "$DEPLOY_SERVER" "cd '$DEPLOY_DIR' && /opt/micromamba/envs/shiny/bin/python3 -s /tmp/verify_p2.py; rm -f /tmp/verify_p2.py"
```
Expected: `P2 gallery OK: <DEPLOY_DIR>/sespy/__init__.py <DEPLOY_DIR>/sespy/templates/marinesabres/OffshoreWind_SES_Template.json` (this also proves the new JSONs reached the server). Then open the live SESPy app in a browser → Templates: both group headers show, the Caribbean card shows its badges, and loading "Offshore Wind Energy (MarineSABRES)" gives the toast and a 23-node CLD.

- [ ] **Step 5 (user go-ahead): Laguna R check for R_SYNC.md** — record whether laguna's R is still v1.29.0 (the 9 pinned files are identical at v1.29.0 and v1.31.0, so either is fine). If the user wants it recorded, add one line under "Laguna verification" in `docs/parity/R_SYNC.md` (outside the markers) in a follow-up docs commit.

- [ ] **Step 6: Recheck the live MosaicSES**
```powershell
Set-Location 'C:\Users\arturas.baziukas\OneDrive - ku.lt\HORIZON_EUROPE\Marine-SABRES\MosaicSES'
micromamba run -n shiny python deploy/verify_live.py
```
Expected: all checks pass (HTTP 200, nav renders, scenario authored, sibling apps answer).

- [ ] **Step 7 (user go-ahead): Push the roadmap branch** (Task 11's commit)
```powershell
git push origin docs/r-parity-roadmap
```

- [ ] **Step 8 (user go-ahead: it deletes a branch and moves `main`): Clean up** — from the SESPy repo root (a fresh call starts there; never from inside the worktree being removed)
```powershell
git -c core.longpaths=true worktree remove '<scratchpad>\sespy-release'
git fetch origin
git log --oneline origin/main..feat/p2-curated-templates   # must print nothing (all merged)
git branch -D feat/p2-curated-templates                    # -D: local main never received the merge
git branch -f main origin/main                             # only if main is not checked out
```
Record the release in memory (P2 shipped, v1.14.0, R pin v1.31.0 `4b53b7d`, deploy status; deferred: complexity filter → P12, preview/customise → P13; triage owners K1/P1b/P4).
