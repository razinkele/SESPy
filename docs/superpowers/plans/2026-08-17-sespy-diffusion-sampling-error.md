# Sampling-Error-Aware Token Diffusion (issue #19) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `token_diffusion()` report its own sampling error — a 95 % margin per element, a rank in which statistically tied elements share a number, and a contested (`~`) rule based on a t-test rather than an arbitrary 5 % band.

**Architecture:** Batch means. Tokens are i.i.d., so accumulating per-batch arrival counts and signed sums alongside the existing totals yields an honest standard error at O(B × elements) memory, with the RNG stream untouched (only bookkeeping changes) so every shipped count/first-arrival golden stays valid. Spec: `docs/superpowers/specs/2026-08-17-diffusion-sampling-error-design.md`.

**Tech Stack:** Python, numpy, scipy (already a hard dependency; lazily imported), Shiny for Python, pytest, Playwright e2e.

## Global Constraints

- Python ONLY via `micromamba run -n shiny python …` (no global python, no pip/venv).
- Unit suite (CI parity): `micromamba run -n shiny python -m pytest tests -q --ignore-glob='*e2e*' --ignore=tests/test_burger.py --ignore=tests/test_stepper.py --ignore=tests/test_stepper_click.py` (525 green on main, 5 pre-existing warnings).
- e2e: ALWAYS the full suite; the controller runs it detached LAST on an IDLE machine; implementers must NOT attempt it.
- Every i18n key needs all 9 languages (en es fr de lt pt it no el), one line per key.
- `sespy/dynamics.py` stays pandas-free; scipy is imported lazily INSIDE the function (repo pattern), never at module top.
- **Do not change the RNG draw order** — one `rng.random(live.size)` per step over live tokens. The goldens depend on it.
- Playwright selectors scoped to ids, never bare `text=`.
- Commit style: conventional. Branch `feat/diffusion-sampling-error` off `main`.

**Golden values** (computed against the real repo with a reference implementation of the exact algorithm below, 2026-08-17):

- **Sample** (`sample_ses.json`, D001, seed 0, defaults, `n_batches=20`) — counts/signs/steps unchanged from what ships today; rank and margin are new:
  `(1, P001, 2000, 0, "+", 2)`, `(1, MPF1, 2000, 0, "-", 3)`, `(3, GB01, 1501, 32, "-", 5)`, `(3, A001, 1499, 32, "+", 1)`, `(5, ES03, 1002, 44, "-", 4)`, `(5, ES01, 998, 44, "-", 4)`, `(7, R002, 501, 32, "-", 6)`.
- **Chain** A→B→C(−)→D, `n_steps=5, n_tokens=100, seed=0`: all three rows `tokens_received=100`, `margin=0`, `rank=1`, signs `+`, `-`, `-`, steps 1, 2, 3.
- **Balanced** A→X(+)→T, A→Y(−)→T, `n_steps=3, n_tokens=1000`: T is `"~"` at **both** seed 0 and seed 1 (the old rule wrongly said `"-"` at seed 0 — this is the regression test for the whole issue), `tokens_received=1000`, `margin=0`, rank 1. At seed 0, Y 527 ±32 `"-"` and X 473 ±32 `"+"`, both rank 2; at seed 1, X 507 ±20 `"+"` and Y 493 ±20 `"-"`, both rank 2.
- **Sink** A→B→T, `n_steps=6, n_tokens=50, seed=0`: B and T both 50 ±5, rank 1, `"+"`, steps 1 and 2.
- **Small n**: chain with `n_tokens=5` → `n_batches=5`, margins 0.
- **P002** from the sample still reaches 13 of 17 (the e2e's second-source assertion is unaffected).

---

### Task 0: Branch

- [ ] **Step 1:**

```bash
git checkout -b feat/diffusion-sampling-error
```

---

### Task 1: batch-means estimator in `sespy/dynamics.py`

**Files:**
- Modify: `sespy/dynamics.py` — `token_diffusion()` only (currently lines ~509-604)
- Test: `tests/test_dynamics.py` — update two existing tests, add three

**Interfaces:**
- Produces: `token_diffusion(...)` returning `{"rows": [{"id", "label", "tokens_received", "margin", "net_sign", "first_arrival_step", "rank"}], "source", "n_tokens", "n_steps", "n_reached", "n_batches"}`. Task 3's renderer consumes `rank`, `margin`, `tokens_received`, `net_sign`, `first_arrival_step`.

- [ ] **Step 1: Update the two whole-dict tests and add the new ones** in `tests/test_dynamics.py`.

(a) In `test_token_diffusion_matches_manual_trace`, replace the `assert r["rows"] == [...]` block with:

```python
    assert r["n_batches"] == 20
    assert r["rows"] == [
        {"id": "B", "label": "b", "tokens_received": 100, "margin": 0,
         "net_sign": "+", "first_arrival_step": 1, "rank": 1},
        {"id": "C", "label": "c", "tokens_received": 100, "margin": 0,
         "net_sign": "-", "first_arrival_step": 2, "rank": 1},
        {"id": "D", "label": "d", "tokens_received": 100, "margin": 0,
         "net_sign": "-", "first_arrival_step": 3, "rank": 1},
    ]
```

(b) In `test_token_diffusion_degenerate_shapes`, the final sink-source assertion gains the new key:

```python
    assert r == {"rows": [], "source": "A", "n_tokens": 10,
                 "n_steps": 5, "n_reached": 0, "n_batches": 0}
```

(c) Replace the body of `test_token_diffusion_sample_golden`'s row assertion with the rank/margin-bearing form:

```python
    assert [(x["rank"], x["id"], x["tokens_received"], x["margin"],
             x["net_sign"], x["first_arrival_step"]) for x in r["rows"]] == [
        (1, "P001", 2000, 0, "+", 2),
        (1, "MPF1", 2000, 0, "-", 3),
        (3, "GB01", 1501, 32, "-", 5),
        (3, "A001", 1499, 32, "+", 1),
        (5, "ES03", 1002, 44, "-", 4),
        (5, "ES01", 998, 44, "-", 4),
        (7, "R002", 501, 32, "-", 6),
    ]
```

(d) Append three new tests:

```python
def test_token_diffusion_balanced_node_is_contested_at_both_seeds():
    # THE regression test for issue #19: the old fixed 5% margin called
    # this structurally balanced node "-" at seed 0 (a 473/527 split is
    # well inside sampling error at n=1000). The t-test must say "~" at
    # both seeds.
    els = [Element(id=i, label=i.lower(), type="Drivers")
           for i in ("A", "X", "Y", "T")]
    conns = [Connection(source="A", target="X", polarity="+"),
             Connection(source="A", target="Y", polarity="-"),
             Connection(source="X", target="T", polarity="+"),
             Connection(source="Y", target="T", polarity="+")]
    isa = _isa(els, conns)
    for seed in (0, 1):
        r = dynamics.token_diffusion(isa, "A", n_steps=3, n_tokens=1000,
                                     seed=seed)
        t_row = next(x for x in r["rows"] if x["id"] == "T")
        assert t_row["net_sign"] == "~", f"seed {seed} misread a tie as signed"
        assert t_row["tokens_received"] == 1000 and t_row["margin"] == 0
        # X and Y are genuinely signed and tie with each other on count.
        x_row = next(x for x in r["rows"] if x["id"] == "X")
        y_row = next(x for x in r["rows"] if x["id"] == "Y")
        assert x_row["net_sign"] == "+" and y_row["net_sign"] == "-"
        assert x_row["rank"] == y_row["rank"]


def test_token_diffusion_ties_share_a_rank():
    # GB01 1501 +/-32 and A001 1499 +/-32 overlap almost entirely: the
    # review measured that ordering flipping in 20 of 50 seeds, so they
    # must not be presented as distinct ranks.
    from pathlib import Path

    from sespy.data_structure import load_sample

    root = Path(__file__).resolve().parents[1]
    r = dynamics.token_diffusion(load_sample(root / "data" / "sample_ses.json"),
                                 "D001", seed=0)
    by_id = {x["id"]: x for x in r["rows"]}
    assert by_id["GB01"]["rank"] == by_id["A001"]["rank"] == 3
    assert by_id["ES03"]["rank"] == by_id["ES01"]["rank"] == 5
    assert by_id["R002"]["rank"] == 7  # clear of the pair above it
    # A margin must never be negative, and a deterministic count has none.
    assert all(x["margin"] >= 0 for x in r["rows"])
    assert by_id["P001"]["margin"] == 0


def test_token_diffusion_batches_adapt_to_small_token_counts():
    r = dynamics.token_diffusion(_chain_isa(), "A", n_steps=3, n_tokens=5,
                                 seed=0)
    assert r["n_batches"] == 5           # fewer tokens than the 20 default
    assert all(x["margin"] == 0 for x in r["rows"])
```

- [ ] **Step 2: Run to verify failure**

Run: `micromamba run -n shiny python -m pytest tests/test_dynamics.py -q -k token_diffusion`
Expected: failures — `KeyError: 'n_batches'` / missing `margin`/`rank` keys.

- [ ] **Step 3: Implement.** Four edits to `token_diffusion()` in `sespy/dynamics.py`.

(a) The `empty` literal gains `n_batches`:

```python
    empty = {"rows": [], "source": source, "n_tokens": n_tokens,
             "n_steps": n_steps, "n_reached": 0, "n_batches": 0}
```

(b) Replace the simulation setup and loop (currently from `rng = np.random.default_rng(seed)` through `first[arrived[first[arrived] < 0]] = step`) with:

```python
    # Batch means: tokens are i.i.d., so B independent batches give an
    # honest standard error with no distributional assumption and
    # O(B x elements) memory. The RNG draw order is unchanged.
    n_batches = min(_DIFFUSION_BATCHES, n_tokens)
    batch_of = (np.arange(n_tokens) * n_batches) // n_tokens

    rng = np.random.default_rng(seed)
    pos = np.full(n_tokens, order[source], dtype=np.int64)
    sign = np.ones(n_tokens, dtype=np.int8)
    arrivals = np.zeros((n_batches, n), dtype=np.int64)
    signed = np.zeros((n_batches, n), dtype=np.int64)
    first = np.full(n, -1, dtype=np.int64)

    for step in range(1, n_steps + 1):
        live = np.nonzero(outdeg[pos] > 0)[0]
        if live.size == 0:
            break
        here = pos[live]
        slot = indptr[here] + (rng.random(live.size) * outdeg[here]).astype(np.int64)
        pos[live] = indices[slot]
        sign[live] = sign[live] * np.where(flips[slot], -1, 1).astype(np.int8)
        landed, landed_sign = pos[live], sign[live]
        np.add.at(arrivals, (batch_of[live], landed), 1)
        np.add.at(signed, (batch_of[live], landed), landed_sign.astype(np.int64))
        arrived = np.unique(landed)
        first[arrived[first[arrived] < 0]] = step
```

(c) Replace the row-building block (from `rows: list[dict] = []` to the final `return`) with:

```python
    if n_batches > 1:
        from scipy import stats  # lazy: scipy is a hard dep but a heavy import

        crit = float(stats.t.ppf(0.975, n_batches - 1))
        se_total = np.sqrt(n_batches * arrivals.var(axis=0, ddof=1))
        se_net = np.sqrt(n_batches * signed.var(axis=0, ddof=1))
    else:
        crit = 0.0
        se_total = np.zeros(n)
        se_net = np.zeros(n)
    total = arrivals.sum(axis=0)
    net = signed.sum(axis=0)

    rows: list[dict] = []
    src_index = order[source]
    for el in isa.elements:
        i = order[el.id]
        if i == src_index or total[i] == 0:
            continue
        if net[i] == 0 or abs(net[i]) <= crit * se_net[i]:
            net_sign = "~"
        else:
            net_sign = "+" if net[i] > 0 else "-"
        rows.append({"id": el.id, "label": el.label,
                     "tokens_received": int(total[i]),
                     "margin": int(round(crit * se_total[i])),
                     "net_sign": net_sign,
                     "first_arrival_step": int(first[i])})
    rows.sort(key=lambda r: -r["tokens_received"])
    for idx, row in enumerate(rows):
        if idx == 0:
            row["rank"] = 1
            continue
        prev = rows[idx - 1]
        overlaps = (row["tokens_received"] + row["margin"]
                    >= prev["tokens_received"] - prev["margin"])
        row["rank"] = prev["rank"] if overlaps else idx + 1
    return {"rows": rows, "source": source, "n_tokens": n_tokens,
            "n_steps": n_steps, "n_reached": len(rows),
            "n_batches": n_batches}
```

(d) Add the module-level constant directly above `def token_diffusion(`:

```python
# Batch count for token_diffusion's standard errors. 20 gives 19 degrees of
# freedom (t = 2.093 at 95%) while keeping batches large enough for the CLT.
_DIFFUSION_BATCHES = 20
```

(e) Extend the docstring: after the existing "net_sign is ..." sentence, replace that sentence and add the new paragraph:

```
    net_sign is "+"/"-" only when the polarity imbalance is distinguishable
    from zero at 95% (Student's t over the batch means); otherwise "~".
    This replaces a fixed 5% band, which mislabelled structurally balanced
    nodes in ~12% of seeds because 5% of n_tokens is comparable to the
    sampling error itself (issue #19).

    Counts are one Monte-Carlo sample, so each row carries `margin`, the
    95% half-width on tokens_received from a batch-means estimate (tokens
    are i.i.d., so Var(total) = B * Var(batch totals)), and `rank`, in
    which a row shares the rank above it when their intervals overlap —
    ties chain down the list, matching how the column is read. A
    deterministic count has margin 0.
```

- [ ] **Step 4: Run the new tests, then the full unit suite** — expect 9 token_diffusion tests passing, then 528 passed / 5 pre-existing warnings.

- [ ] **Step 5: Commit**

```bash
git add sespy/dynamics.py tests/test_dynamics.py
git commit -m "feat(dynamics): batch-means margins, tied ranks and a calibrated contested rule (#19)"
```

---

### Task 2: caption rewrite (9 languages)

**Files:**
- Modify: `sespy/translations/core.json` — replace the single `"diffusion.caption"` line.

**Interfaces:**
- Consumes/produces: the existing key `diffusion.caption`; no new keys, so `tests/test_i18n.py` needs no change (its presence test and the 9-language drift test both already cover this key).

- [ ] **Step 1: Replace the whole `"diffusion.caption"` line VERBATIM:**

```json
    "diffusion.caption": {"en": "tokens follow random outgoing links; negative links flip a token's sign. Counts are one random sample: ± is the 95% margin, and elements whose margins overlap share a rank — equal ranks mean too close to call. A net sign of ~ means the split is within sampling error. The simulation always uses the full model, ignoring any elements removed above.", "es": "las fichas siguen enlaces salientes al azar; los enlaces negativos invierten su signo. Los recuentos son una muestra aleatoria: ± es el margen del 95 % y los elementos cuyos márgenes se solapan comparten rango; un rango igual significa que no se pueden distinguir. Un signo neto ~ indica que la diferencia está dentro del error de muestreo. La simulación siempre usa el modelo completo, ignorando los elementos eliminados arriba.", "fr": "les jetons suivent des liens sortants au hasard ; les liens négatifs inversent leur signe. Les comptes sont un échantillon aléatoire : ± est la marge à 95 % et les éléments dont les marges se chevauchent partagent un rang — un rang identique signifie qu'on ne peut pas les départager. Un signe net ~ indique un écart inférieur à l'erreur d'échantillonnage. La simulation utilise toujours le modèle complet, en ignorant les éléments supprimés ci-dessus.", "de": "Marken folgen zufälligen ausgehenden Verbindungen; negative Verbindungen kehren ihr Vorzeichen um. Die Zählungen sind eine Zufallsstichprobe: ± ist die 95-%-Spanne, und Elemente mit überlappenden Spannen teilen sich einen Rang — gleicher Rang heißt nicht unterscheidbar. Ein Netto-Vorzeichen ~ bedeutet, dass der Unterschied innerhalb des Stichprobenfehlers liegt. Die Simulation verwendet immer das vollständige Modell und ignoriert die oben entfernten Elemente.", "lt": "žetonai eina atsitiktiniais išeinančiais ryšiais; neigiami ryšiai apverčia jų ženklą. Skaičiai yra viena atsitiktinė imtis: ± yra 95 % paklaida, o elementai, kurių paklaidos persidengia, dalijasi ta pačia vieta — vienoda vieta reiškia, kad atskirti neįmanoma. Grynasis ženklas ~ reiškia, kad skirtumas neviršija imties paklaidos. Modeliavimas visada naudoja visą modelį, nepaisant aukščiau pašalintų elementų.", "pt": "as fichas seguem ligações de saída aleatórias; ligações negativas invertem o seu sinal. As contagens são uma amostra aleatória: ± é a margem de 95 % e os elementos cujas margens se sobrepõem partilham a mesma posição — posições iguais significam que não é possível distingui-los. Um sinal líquido ~ indica que a diferença está dentro do erro de amostragem. A simulação usa sempre o modelo completo, ignorando os elementos removidos acima.", "it": "i gettoni seguono collegamenti in uscita casuali; i collegamenti negativi ne invertono il segno. I conteggi sono un campione casuale: ± è il margine al 95 % e gli elementi i cui margini si sovrappongono condividono la stessa posizione — posizioni uguali significano che non sono distinguibili. Un segno netto ~ indica che la differenza rientra nell'errore di campionamento. La simulazione usa sempre il modello completo, ignorando gli elementi rimossi sopra.", "no": "brikker følger tilfeldige utgående koblinger; negative koblinger snur fortegnet. Tallene er én tilfeldig stikkprøve: ± er 95 %-marginen, og elementer med overlappende marginer deler plassering — lik plassering betyr at de ikke kan skilles. Et nettofortegn ~ betyr at forskjellen ligger innenfor utvalgsfeilen. Simuleringen bruker alltid hele modellen og ignorerer elementene som er fjernet ovenfor.", "el": "οι μονάδες ακολουθούν τυχαίους εξερχόμενους δεσμούς· οι αρνητικοί δεσμοί αντιστρέφουν το πρόσημο. Οι μετρήσεις είναι ένα τυχαίο δείγμα: το ± είναι το περιθώριο 95 % και τα στοιχεία με επικαλυπτόμενα περιθώρια μοιράζονται την ίδια θέση — ίδια θέση σημαίνει ότι δεν ξεχωρίζουν. Καθαρό πρόσημο ~ σημαίνει ότι η διαφορά είναι εντός του σφάλματος δειγματοληψίας. Η προσομοίωση χρησιμοποιεί πάντα το πλήρες μοντέλο, αγνοώντας τα στοιχεία που αφαιρέθηκαν παραπάνω."},
```

- [ ] **Step 2: Verify JSON and run the i18n suite**

Run: `micromamba run -n shiny python -c "import json;json.load(open('sespy/translations/core.json',encoding='utf-8'))"` → no output.
Run: `micromamba run -n shiny python -m pytest tests/test_i18n.py -q` → all pass (drift test covers the 9 languages).

- [ ] **Step 3: Commit**

```bash
git add sespy/translations/core.json
git commit -m "i18n(diffusion): caption explains the margin, tied ranks and the contested rule (#19)"
```

---

### Task 3: rank + margin in the UI, and e2e

**Files:**
- Modify: `sespy/modules/analysis_intervention.py` — the `diffusion_summary` table only (currently the header at ~line 342 and the row cells at ~line 348).
- Modify: `tests/test_intervention_e2e.py` — extend the existing diffusion assertions.

**Interfaces:**
- Consumes: `rank`, `margin` (Task 1), the rewritten caption (Task 2).

- [ ] **Step 1: Table header** — replace the existing header row with:

```python
        header = ui.tags.tr(
            ui.tags.th("rank"), ui.tags.th(""), ui.tags.th("arrivals"),
            ui.tags.th("net sign"), ui.tags.th("first step"),
        )
```

- [ ] **Step 2: Row cells** — replace the existing body comprehension with:

```python
        body = [
            ui.tags.tr(
                ui.tags.td(str(row["rank"])),
                ui.tags.td(f"{row['id']} · {row['label']}"),
                ui.tags.td(f"{row['tokens_received']} ±{row['margin']}"),
                ui.tags.td(ui.tags.strong(row["net_sign"])),
                ui.tags.td(str(row["first_arrival_step"])),
            )
            for row in r["rows"]
        ]
```

- [ ] **Step 3: e2e** — in `tests/test_intervention_e2e.py`, immediately after the existing `assert "Anchor damage" in diff_text and "2000" in diff_text, ...` assertion, add:

```python
        # Sampling error is now visible: GB01 and A001 differ by 2 arrivals
        # with a +/-32 margin, so they must share a rank rather than being
        # ranked 3 and 4 (issue #19).
        assert "±32" in diff_text, f"expected a 95% margin column, got: {diff_text!r}"
        assert "1501 ±32" in diff_text and "1499 ±32" in diff_text, \
            f"expected margins on the near-tied pair, got: {diff_text!r}"
```

- [ ] **Step 4: Sanity-import and run the unit suite**

Run: `micromamba run -n shiny python -c "import sespy.modules.analysis_intervention"` → clean.
Run the full CI-parity unit suite → 528 passed. Do NOT run the e2e suite.

- [ ] **Step 5: Commit**

```bash
git add sespy/modules/analysis_intervention.py tests/test_intervention_e2e.py
git commit -m "feat(intervention): show tied ranks and the 95% margin in the diffusion table (#19)"
```

---

### Task 4: Changelog, merge, close issue #19

- [ ] **Step 1: Changelog** — first bullet under `## [Unreleased]`:

```markdown
- Intervention simulation now reports its own sampling error (#19): each
  element carries a 95% margin (`1501 ±32`) and a rank that statistically
  tied elements share, so a near-tie is no longer displayed as a firm
  ranking, and a net sign of `~` now means "within sampling error" rather
  than "inside an arbitrary 5% band" — the old rule mislabelled balanced
  elements in about 12% of runs.
```

```bash
git add CHANGELOG.md
git commit -m "docs(changelog): sampling-error-aware diffusion under Unreleased (#19)"
```

- [ ] **Step 2: Merge and push** (after the final review is clean AND the detached full e2e is green):

```bash
git checkout main
git merge --no-ff feat/diffusion-sampling-error -m "feat: sampling-error-aware token diffusion (#19)"
git push
```

- [ ] **Step 3: Close issue #19** with the measured before/after: the flagged GB01/A001 pair now shares rank 3; the balanced-node mislabel rate falls from 6/50 seeds to 3/50, where ~5 % is the nominal false-positive rate of a 95 % test (a known, controllable error rate replacing an arbitrary band); counts, signs and first-arrival steps are unchanged because the RNG stream was untouched.

---

## Self-review notes

- Spec coverage: batch-means estimator + `n_batches` (Task 1), `margin` (Task 1), tied `rank` (Task 1), calibrated `~` rule (Task 1 + the both-seeds regression test), two whole-dict tests updated (Task 1 Step 1a/1b), caption rewrite (Task 2), rank + `±` display (Task 3), e2e proof that the flagged pair shares a rank (Task 3), changelog + issue close with measurements (Task 4).
- Type consistency: row keys identical across Tasks 1 and 3; `_DIFFUSION_BATCHES` referenced only inside `token_diffusion`.
- Golden values computed against the real repo on 2026-08-17 with a reference implementation of exactly the Task 1 Step 3 code (sample, chain, balanced ×2 seeds, sink, small-n and P002 fixtures all verified).
