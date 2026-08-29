# SESPy — Loop Dominance Over Time (#22) Design

**Status:** Draft, pending review. Implements [#22](https://github.com/razinkele/SESPy/issues/22) as corrected on 2026-08-29 (see the issue's correction comment — the original description named a function and a host module that do not exist, and proposed a metric that is provably constant).

**Prerequisite, already shipped:** `97a1e65` fixed `simulate_dynamics` propagating influence *backwards* along every edge. This design depends on trajectories flowing the direction the edges point; without that fix a dominance ranking would be computed from states that never moved.

## 1. Purpose

Feedback-loop analysis currently reports a flat, time-invariant inventory: which loops exist and whether each is Reinforcing or Balancing. It cannot answer *which loop is governing behaviour right now*.

The motivating literature reports exactly that as its central finding — Nguyen et al. (2026, [10.1002/sres.70145](https://doi.org/10.1002/sres.70145)) find a balancing loop dominating an early transition phase before reinforcing loops take over; Imtihan et al. (2026, [10.25105/urbanenvirotech.v9i2.22457](https://doi.org/10.25105/urbanenvirotech.v9i2.22457)) report a balancing loop acting as the operative barrier.

**The deliverable is the shift, not the raw series.** A user should be able to read "B1 governs until step 41, then R3 takes over" and act on it. Per-timestep gains are computed internally but are not the headline output.

## 2. Scope

In scope: a pure `loop_dominance()` over an existing trajectory; a pure `dominance_shifts()` detector; an optional overlay on the existing simulation trajectory plot.

Out of scope:
- **ALC (Adjusted Loop Centrality).** #22 folds it in, but it is a *node* metric, not a time series, and #23's correction shows the node-side depth/leverage surface needs reconciling with the already-shipped `leverage_realm()` first. Deferred so two independent decisions do not become coupled.
- Changing loop enumeration, the simulation itself, or `leverage_scores()`.
- Any new time-series simulation. This annotates the trajectory the user already ran.

## 3. Why gain must be state-scaled — and normalised

The bare product of signed edge weights around a cycle is **time-invariant** under `x_{t+1} = A @ x_t` with constant `A`. Emitting it per timestep would produce an identical number at every step: a constant column presented as a dominance ranking. #22's acceptance criterion would be unsatisfiable.

Structure does not change over time; **which loops carry activity** does. So:

```
structural_L  = |Π M[n_i, n_i+1]|                 # constant, the loop's strength
activity_L(t) = mean( |x_t[n]| for n in L )       # how live its nodes are at t
gain_L(t)     = structural_L × activity_L(t)
share_L(t)    = gain_L(t) / Σ_L' gain_L'(t)       # dominance share, sums to 1
```

`structural_L` uses `isa_to_numeric_matrix`'s orientation (`M[i,j]` = edge i→j), computed once. `activity_L(t)` is a **mean**, deliberately: an intensive quantity, independent of loop length.

### Normalisation is load-bearing, not cosmetic

Measured on `data/sample_ses.json`: spectral radius **2.998**, so states grow like 3ᵗ. Per-step normalisation makes `share` scale-free and bounded in [0,1], readable as "L3 accounts for 41% of loop activity at step 40".

### The rejected alternative, and why

A per-edge state-weighted product `Π (M[n_i,n_i+1] · x_t[n_i])` is the more literal reading of "state-scaled". It was tested and rejected on evidence. On the sample model at t=30:

| loop length | median \|gain\| |
|---|---|
| 5 | 2.4 × 10⁷⁰ |
| 6 | 1.0 × 10⁸⁵ |

**Fifteen orders of magnitude from one additional node.** The ranking would report loop length rather than influence, and the magnitudes are already leaving the range where floating point is meaningful. Rescaling cannot rescue a quantity that has overflowed. Eigenmode attribution — theoretically the "right" answer — is research-grade with no clean result for non-normal matrices, and belongs with the deferred Chunk-3-style work, not here.

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

- `trajectory` is `(n_steps, n)` as returned by `simulate_dynamics`; `node_ids` is the matching order from `isa_to_dynamics_matrix`. **The trajectory is passed in, never simulated here** — the function stays pure and testable without `dynamics`, and the caller guarantees the ranking describes the run actually on screen.
- `cycles` defaults to `feedback_loops(isa)` (note: `feedback_loops`, **not** `find_loops`, which does not exist). The UI passes its already-enumerated set so loops are not re-enumerated per render.
- Returns a `TypedDict` with `rows` (one per loop: `loop_id`, `nodes`, `polarity`, `structural_gain`, `shares` as a list over timesteps, `peak_share`, `peak_step`), plus `n_steps`, `active` (bool) and `note` (a human-readable reason when `active` is False).

Polarity comes from the existing `loop_polarity()`; no new polarity logic.

## 5. Component ② — `dominance_shifts`

**File:** `sespy/network.py`.

```python
def dominance_shifts(
    result: DominanceResult, *, margin: float = 0.05, dwell: int = 5
) -> list[Shift]:
```

A shift is recorded only when a new leader's share exceeds the incumbent's by a **relative margin** AND holds the lead for `dwell` consecutive steps. Near-ties never register as shifts; they are reported as contested.

Each `Shift` carries `step`, `from_loop`, `to_loop`, `from_polarity`, `to_polarity`, `margin_pct`, `held_steps`, and `polarity_changed`.

**`polarity_changed` is a separate field on purpose.** Measured on the sample model, dominance moves from loop L0 to L3 at ≈ step 20 while *both* are Balancing. The motivating literature is about polarity regime change; a change of governing loop within the same polarity is a different, weaker event. Conflating them would report a "B→R shift" that never happened.

## 6. Component ③ — the overlay

**File:** `sespy/modules/analysis_simulation.py`.

An **optional, default-off** checkbox on the existing trajectory plot at `analysis_simulation.py:129` — the matrix-trajectory plot, **not** `analysis_bot.py` (empirical, never calls `simulate_dynamics`) and **not** `analysis_loops.py` (no plot). When enabled it shades the plot background by the governing loop and lists the detected shifts beneath it.

It reuses the trajectory and `node_ids` the panel already computed. No second simulation.

## 7. Degenerate cases — never raise

| Condition | Behaviour |
|---|---|
| `initial_state="zeros"` (the panel default) → identically-zero trajectory | `active=False`, note: "no loop activity — the trajectory is identically zero; choose a non-zero initial state" |
| No cycles found | `active=False`, note naming that |
| All structural gains zero | `active=False` |
| Fewer than 2 loops | Dominance is trivially the single loop; no shifts |
| `trajectory` shape inconsistent with `node_ids` | `ValueError` — a caller bug, not user input |

The empty shape is returned, never an exception, for every condition arising from user data.

## 8. Testing

**Unit — `tests/test_network.py`:**
- **A purpose-built B→R fixture.** `data/sample_ses.json` cannot serve: all five of its loops are Balancing, so it exhibits no polarity regime change. The fixture must be constructed so a balancing loop dominates early and a reinforcing loop later, and it is what proves #22's acceptance criterion.
- **A constant-metric guard.** Assert shares genuinely vary across timesteps (`max |share(0) − share(end)|` above a threshold). This is the regression test for the whole design: if someone later "simplifies" gain back to the bare edge-weight product, this fails loudly instead of silently emitting constants.
- Length-comparability: two loops of different lengths with equal structural gain and equal activity get equal shares.
- Shift detection: a near-tie below `margin` produces no shift; a clear lead held for `dwell` produces exactly one; a lead held for fewer than `dwell` steps produces none.
- `polarity_changed` is True only for a genuine B↔R transition.
- Every degenerate case in §7.

**E2e:** the checkbox renders and toggles, using namespaced ids and `wait_for_nav`. Deliberately **not** asserting overlay pixel content — that logic is covered by the pure-function tests above. A declared coverage limit, consistent with how this codebase tests its analysis surfaces.

## 9. Cross-repo gate

MosaicSES imports `sespy` through an editable install pinned to this working tree and embeds `analysis_loops` / `analysis_leverage` UI directly. Any change to `sespy/network.py` or `sespy/modules/*` must pass **both** repos' full unnarrowed suites before pushing — SESPy unit + `tests/run_e2e.py`, and MosaicSES `pytest tests/`. Never `-k "not e2e"`. Do not run the two concurrently: the shared editable tree makes concurrent runs non-reproducible.

## 10. Risks

- **Loop count.** `feedback_loops` caps at `max_loops=50`; the shares are normalised over the loops actually enumerated, so the metric is relative to that capped set. The note must say so — a share is "of the loops we found", not "of all loops".
- **Unstable systems.** With ρ > 1 the trajectory grows without bound and float overflow eventually reaches `activity_L`. Normalisation delays but does not remove this; if `Σ gain` is non-finite, return `active=False` rather than emitting NaNs.
- **Interpretation.** A dominance share is a heuristic attribution, not a proof that a loop *causes* the observed behaviour. The UI copy must not claim causation — consistent with the existing disclaimer language on the simulation panel.
