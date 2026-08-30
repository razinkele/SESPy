# SESPy — Loop Dominance Over Time (#22) Design

**Status:** Revised 2026-08-30 after a multi-agent review (32 findings survived adversarial verification; verdict "safe after these revisions"). Implements [#22](https://github.com/razinkele/SESPy/issues/22) as corrected on 2026-08-29 — the original issue named a function and a host module that do not exist and proposed a metric that is provably constant.

**Prerequisite, already shipped:** `97a1e65` fixed `simulate_dynamics` propagating influence *backwards* along every edge. Without it a dominance ranking would be computed from states that never moved.

> **Rule for this document, learned the hard way:** never name a loop by its enumeration index. `feedback_loops`' output order *and each cycle's rotation* vary across processes (`nx.simple_cycles` iterates sets, so hash seeding changes both). Loops are named here by node tuple, and every measured number records the `initial_state`, `seed` and `n_iter` it was produced under.

## 1. Purpose

Feedback-loop analysis reports a flat, time-invariant inventory: which loops exist and whether each is Reinforcing or Balancing. It cannot answer *which loop is governing behaviour right now*.

The motivating literature reports exactly that — Nguyen et al. (2026, [10.1002/sres.70145](https://doi.org/10.1002/sres.70145)) find a balancing loop dominating an early transition before reinforcing loops take over; Imtihan et al. (2026, [10.25105/urbanenvirotech.v9i2.22457](https://doi.org/10.25105/urbanenvirotech.v9i2.22457)) report a balancing loop as the operative barrier.

**The deliverable is the shift, not the raw series.** A user should read "in this run, the *{A002…D002}* loop governs until step 18, then *{MPF1…P001}* takes over". Per-timestep gains are computed internally and are not the headline output.

**What the shift is, and is not.** See §10: shift *timing* is a property of the run, not a prediction of the model. UI copy says "in this run".

## 2. Scope

In scope: a pure `loop_dominance()` over an existing trajectory; a pure `dominance_shifts()` detector; an optional overlay on the existing simulation trajectory plot.

Out of scope:
- **ALC (Adjusted Loop Centrality).** #22 folds it in, but it is a *node* metric, not a time series, and #23's reconciliation with the already-shipped `leverage_realm()` must settle first. Deferred so two independent decisions do not become coupled.
- Changing loop enumeration, the simulation, or `leverage_scores()`.
- Any new simulation run. This annotates the trajectory the user already produced.

## 3. Why gain must be state-scaled — and normalised

The bare product of signed edge weights around a cycle is **time-invariant** under `x_{t+1} = A @ x_t` with constant `A`. Emitting it per timestep gives an identical number at every step: a constant column presented as a ranking, and #22's acceptance criterion would be unsatisfiable.

Structure does not change; **which loops carry activity** does.

```
structural_L  = |Π M[n_i, n_i+1]|                 # constant, the loop's strength
activity_L(t) = mean( |x_t[n]| for n in L )       # how live its nodes are at t
gain_L(t)     = structural_L × activity_L(t)
share_L(t)    = gain_L(t) / Σ_L' gain_L'(t)       # dominance share, sums to 1
```

`structural_L` uses `isa_to_numeric_matrix`'s orientation (`M[i,j]` = edge i→j), computed once. `activity_L(t)` is a **mean** — an intensive quantity, independent of loop length. **Only cycles of length ≥ 2 participate** (§7).

### Normalisation is load-bearing

Measured on `data/sample_ses.json`: spectral radius **2.998**, so states grow like 3ᵗ. Per-step normalisation makes `share` scale-free, bounded in [0,1], and readable as "this loop accounts for 41% of loop activity at step 40".

### The rejected alternative

A per-edge state-weighted product `Π (M[n_i,n_i+1] · x_t[n_i])` is the more literal reading of "state-scaled". Rejected on measurement. At `initial_state="uniform"`, `t=30`:

| loop length | median \|gain\| |
|---|---|
| 5 | 2.37 × 10⁷⁰ |
| 6 | 1.04 × 10⁸⁵ |

**Fifteen orders of magnitude from one additional node** — the ranking would report loop length, not influence, and the magnitudes are leaving the range where floating point is meaningful. (Absolute values are init-dependent — another run at a different `initial_state` gave 6.3e70 / 5.2e85 — but the length-domination conclusion is unaffected.) Eigenmode attribution, theoretically the "right" answer, is research-grade with no clean result for non-normal matrices and belongs with deferred work.

## 4. Component ① — `loop_dominance`

**File:** `sespy/network.py`.

```python
def loop_dominance(
    isa: IsaData,
    trajectory: np.ndarray,
    node_ids: list[str],
    *,
    cycles: list[list[str]] | None = None,
) -> DominanceResult:
```

- `trajectory` is `(n_steps, n)` as returned by `simulate_dynamics`; `node_ids` is the matching order from `isa_to_dynamics_matrix`. **The trajectory is passed in, never simulated here** — the function stays pure and testable without `dynamics`, and the caller guarantees the ranking describes the run on screen.
- `cycles` defaults to `feedback_loops(isa)` (`feedback_loops`, **not** `find_loops`, which does not exist). The parameter exists for **test injection and for the caller's own snapshot** — it is *not* a hand-off from the Loop Detection panel, whose `detected` set is a module-local reactive inside `analysis_loops_server` (`analysis_loops.py:169`) that `analysis_simulation` cannot read. Enumeration on the sample costs ≈4.75 ms, so the simulation panel enumerating its own set is cheap.
- **Import.** `structural_L` uses a **function-local** `from .dynamics import isa_to_numeric_matrix` (precedent: `network.py:984` does a function-local `import numpy as np`). A module-level import would be circular — `dynamics.py:16` already imports `network`. If a hand-rolled walk over `isa.connections` + `_STRENGTH_RANK` is used instead, it must **sum** parallel edges, matching `isa_to_numeric_matrix`; `loop_polarity`'s lookup is last-wins.

**Loop identity.** `loop_id: str`, formatted `L{idx:03d}` (1-based), matching `classify_loops` (`network.py:1065`) and the Loop Detection table. Because enumeration order and cycle rotation vary across processes, `loop_dominance` **canonicalises before assigning ids**: rotate each cycle to its lexicographically-least starting node, then sort the set, then enumerate. Rows are keyed by `nodes`; consumers must key on `nodes`, not position. Canonicalisation runs on the set *already returned* by `feedback_loops` — do **not** sort before applying `max_loops`, which would require enumerating all eligible cycles and defeat #18's `length_bound` tractability fix (>5 min unbounded vs ~10 ms).

**Returns** a `TypedDict`:

| field | type | meaning |
|---|---|---|
| `rows` | list | per loop: `loop_id`, `nodes` (tuple), `polarity`, `structural_gain`, `shares` (list over kept steps), `peak_share`, `peak_step` |
| `n_steps` | int | number of usable steps (after any truncation) |
| `truncated_at` | int \| None | step where the series was truncated, if any |
| `contested_steps` | list[int] | steps where the top two shares differ by less than `margin` |
| `active` | bool | False when no usable prefix of ≥2 steps exists |
| `note` | str | machine token, never prose (§6 i18n) |

Polarity comes from the existing `loop_polarity()`.

## 5. Component ② — `dominance_shifts`

**File:** `sespy/network.py`.

```python
def dominance_shifts(
    result: DominanceResult, *, margin: float = 0.05, dwell: int = 5
) -> list[Shift]:
```

A shift is recorded only when a new leader's share exceeds the incumbent's by a **relative** `margin` (i.e. `new > old × (1 + margin)`) AND holds the lead for `dwell` consecutive steps. The shift's `step` is the step at which the new leader *first* took the lead, not the step at which dwell completed.

Steps where the top two shares differ by less than `margin` are recorded in `DominanceResult["contested_steps"]` and never produce a `Shift`. **`contested_steps` is populated by `loop_dominance`** (it needs only the shares and the same `margin` default), so `dominance_shifts` stays a pure reader of the result.

Each `Shift` carries `step`, `from_loop`, `to_loop` (ids), `from_nodes`, `to_nodes` (tuples), `from_polarity`, `to_polarity`, `margin_pct`, `held_steps`, `polarity_changed`.

**`polarity_changed` is a separate field on purpose.** Measured on the sample (`initial_state="random"`, seed 42, `n_iter=200`, §3 formula): the Balancing loop `A002→P002→MPF2→ES02→GB02→D002` (structural gain 486) leads until step 17 and is overtaken at step 18 by the Balancing loop `MPF1→ES01→GB01→D001→A001→P001` (gain 216), whose near-tied `ES03` variant sits at 0.404 vs 0.423 at t=200. Both are Balancing, so `polarity_changed` is False. The crossing step is initial-state dependent and the two 6-cycles are near-tied throughout, so the successor's identity is fragile to seed — hence naming by node tuple. The motivating literature is about *polarity* regime change; a change of governing loop within one polarity is a different, weaker event, and conflating them would report a "B→R shift" that never happened.

## 6. Component ③ — the overlay

**File:** `sespy/modules/analysis_simulation.py`.

An optional, **default-off** checkbox on the existing trajectory plot (output declared at `:75`, rendered at `:173`) — the matrix-trajectory plot, **not** `analysis_bot.py` (empirical, never calls `simulate_dynamics`) and **not** `analysis_loops.py` (no plot).

When enabled it shades the plot background using the **dwell/margin-filtered segments implied by `dominance_shifts`** — one band per confirmed governing period, `contested_steps` left unshaded — consistent with §1's "the deliverable is the shift". It does **not** shade the raw per-step `argmax`, which flickers on near-ties.

**Snapshot, don't re-read.** `_run_sim` stores, at Run time alongside `traj`/`node_ids`, everything the overlay consumes: the enumerated `cycles`, their polarities and structural gains (or minimally the ISA actually simulated). The overlay reads only `sim_store` plus the checkbox — **never** the live `project_data`. Today `_run_sim` stores only `{error, traj, node_ids}` and `_stale_warning` merely shows a notification without clearing `sim_store`, so an ISA edit after a run would otherwise pair a new model with an old trajectory. No second simulation, no re-enumeration per render.

**i18n.** The checkbox label, background legend, shift-list header and no-causation disclaimer are new `simulation.dominance*` keys in `sespy/translations/core.json` in **all nine** supported languages (en/es/fr/de/lt/pt/it/no/el) — `tests/test_i18n.py::test_loader_handles_all_supported_languages` fails otherwise. `loop_dominance` returns **no prose**: `note` is a machine token (`"zero_trajectory"`, `"no_cycles"`, `"zero_gain"`, `"truncated_overflow"`, `"truncated_underflow"`), following the existing `_BEHAVIOR_KEY` precedent, and the module maps it to a translated key.

## 7. Degenerate cases — never raise

| Condition | Behaviour |
|---|---|
| User selects `initial_state="zeros"` (**not** the panel default, which is `"random"` with seed 42) → identically-zero trajectory | `active=False`, note `"zero_trajectory"` |
| No cycles found | `active=False`, note `"no_cycles"` |
| All structural gains zero | `active=False`, note `"zero_gain"` |
| `cycles` contains length-1 (self-)loops | **Excluded**: filter `len(cycle) >= 2` before computing shares. A self-loop is not a feedback loop for this metric — `feedback_loops` returns them and `isa_to_numeric_matrix` sums them onto the diagonal, and left in, a self-growing node was measured governing 86% of a test system |
| Fewer than 2 loops after filtering | Dominance is trivially the single loop; no shifts |
| `Σ gain` non-finite at step k>0 (overflow, ρ>1) | Truncate at k; `active=True`, `truncated_at=k`, note `"truncated_overflow"` |
| `Σ gain == 0` at step k>0 (state underflowed to zeros, ρ<1) | Same truncation path, note `"truncated_underflow"` |
| `trajectory` shape inconsistent with `node_ids` | `ValueError` — a caller bug, unreachable through the UI once the overlay reads its ISA snapshot from `sim_store` |

The empty shape is returned, never an exception, for every condition arising from user data.

## 8. Testing

**Unit — `tests/test_network.py`:**

- **A purpose-built B→R fixture.** `data/sample_ses.json` cannot serve — **not** because it lacks Reinforcing loops (it has two: the length-5 cycles through `R002`, `{MPF1,ES01,GB01,R002,P001}` and `{MPF1,ES03,GB01,R002,P001}`, each with two negative edges hence even ⇒ Reinforcing) but because they never attain leadership: their shares peak at ≈0.114 and ≈0.104 and sit at 0.089/0.084 at t=200, while a Balancing loop holds ≈0.42 throughout (`initial_state="random"`, seed 42, `n_iter=200`). The sample's only leadership change is Balancing→Balancing. The reliable construction for a guaranteed B→R shift is **timescale separation** — two components with distinct spectral radii, or a decaying-vs-growing mode pair — so the early leader's share provably decays. A single-SCC graph *can* show a transient shift; it just cannot be relied on to.
- **A constant-metric guard.** Assert shares genuinely vary across timesteps. If someone later "simplifies" gain back to the bare edge-weight product, this fails loudly instead of silently emitting constants.
- **Self-loops excluded**: a self-loop appears in neither `rows` nor the denominator.
- Length-comparability: two loops of different lengths with equal structural gain and equal activity get equal shares.
- Shift detection: a near-tie below `margin` produces no shift **and lands in `contested_steps`**; a clear lead held for `dwell` produces exactly one; a lead held for fewer than `dwell` steps produces none.
- `polarity_changed` is True only for a genuine B↔R transition.
- Truncation: an overflowing run yields `active=True` with `truncated_at` set, not a blanked result.
- Every degenerate case in §7.
- **Determinism:** tests pin `PYTHONHASHSEED` or sort fixture cycles, and assert on `nodes`, never on enumeration position.

**E2e:** extend `tests/test_simulation_e2e.py`, or add a globbed `test_*_e2e.py` asyncio script following that file's pattern (SESPy's e2e are standalone Playwright scripts discovered by `tests/run_e2e.py:51`; **`wait_for_nav` does not exist in this repo** — it is a MosaicSES helper). Flow: `wait_for_selector("#sespy_nav_simulation")` → click → run the sim → toggle the dominance checkbox → `wait_for_selector` on the plot image → assert the toggle state. Namespaced ids only, no bare `text=` selectors. Deliberately not asserting overlay pixel content — a declared coverage limit, consistent with how this codebase tests analysis surfaces.

## 9. Cross-repo gate

MosaicSES imports `sespy` through an editable install (`__editable__.sespy-1.3.0.pth`) pinned to the SESPy working tree, and embeds SESPy analysis UI directly. Any change to `sespy/network.py` or `sespy/modules/*` must pass **both** repos' full unnarrowed suites before pushing — SESPy unit + `tests/run_e2e.py`, and MosaicSES `pytest tests/`. Never `-k "not e2e"`. Do not run the two concurrently: the shared editable tree makes concurrent runs non-reproducible. Because the install is path-pinned, this work must happen on a branch **in the SESPy checkout itself**, not a worktree — a worktree would leave MosaicSES importing unmodified code and the gate would prove nothing.

## 10. Risks and interpretation

- **Shift timing is initial-condition dependent, and late-run dominance is structural.** `share_L(t)` is homogeneous of degree 1 in the state, so global scale cancels and shares depend only on the *direction* of `x_t` — which converges to the dominant eigenvector. Verified: final shares `[0.4227, 0.4044, 0.0000, 0.0892, 0.0837]` versus shares computed directly from the dominant eigenvector `[0.4170, 0.3943, 0.0000, 0.0978, 0.0910]`; shares are within 0.02 of final by t=63. And rescaling the initial state on one loop's nodes by 1/10/100/1e4 moved the sample's only crossing from step 16→36→40→41. **Post-transient dominance is a structural fact requiring no simulation; the step at which a shift occurs is a property of the run.** UI copy must read "in this run, X governs until step N" and must never present N as a model prediction.
- **Unstable and stable extremes.** The guard is **per timestep, not per result**: shares are computed over the finite, positive-Σ prefix and truncated at the first bad step. Measured on the sample at the panel's slider maximum (`n_iter` range is 50–2000, `analysis_simulation.py:27-30`): first non-finite row at step **647** of 2001 with ρ=2.998, while all dominance behaviour happens at t<63. Symmetrically, the same matrix scaled to ρ≈0.60 underflows to exact zeros at step 1459, giving `Σ gain = 0`. A global `active=False` would void an entire run over one late step.
- **Loop set is panel-local.** `feedback_loops` defaults to `max_length=6, max_loops=50`; the Loops panel's UI default for `max_loops` is **200**, so the two panels may enumerate different sets. When the cap binds, the truncated subset — and hence the share denominator — is hash-seed dependent across processes. Ids are canonicalised (§4) but remain panel-local; the note must not invite cross-referencing with the Loops tab.
- **Attribution, not causation.** `activity_L` measures node magnitude, so a loop touching large-magnitude nodes scores highly even when that magnitude was injected from outside the loop. This is a known limit of the attribution and sits beside the existing no-causation disclaimer on the simulation panel. A dominance share is a heuristic attribution, not proof that a loop *causes* the observed behaviour.
