# CLD edge styling for contested edges — design

**Date:** 2026-06-25
**Status:** approved (brainstorm)
**Tracks:** GitHub issue #8 (#5a, split from #5). Follow-up to QSEM-C3 (`d262a67`,
the table-only contested view); see memory `sespy-qsem-multirater`.

## Problem / goal

The Rate Connections table flags contested edges (`⚠`), but the **CLD graph** doesn't —
disagreement is invisible where the system is actually read. Surface
`polarity_contested` (sign disagreement among raters) on the CLD edges.

**The honest constraint (why deferred):** the CLD edge channels are nearly all spoken
for — `color` = polarity, `label` = polarity text, `dashes` = delay, `title` =
`"polarity · delay"` (the shared `network.delay_edge_kwargs`). The one fully-free channel
is **`width`** (fixed at 2). And `polarity_contested` is a boolean *about the edge's own
colour*, so it cannot be shown by re-colouring.

## Decisions (from brainstorm)

- **Encode contestedness on `width` + a `⚠` label marker** (both at-a-glance, redundant
  for clarity), extend the hover `title`, and add a legend line. **Not** a colour
  override — colour carries the consensus polarity, which stays primary.
- **Boolean `polarity_contested` drives it** — sign disagreement is the strong signal.
  `strength_spread`/`confidence_spread` (magnitude disagreement) are deferred (could later
  *scale* the width; YAGNI for v1).
- **CLD only.** Per-edge `network.connection_disagreement(c)` in the build loop — pure and
  cheap; `polarity_contested` is `False` for any edge with <2 ratings, so single-author
  and imported models render **exactly as today** (purely additive, self-gating).

## Architecture

All in `sespy/modules/cld_visualization.py` (and two i18n keys). **Import fix
(REQUIRED):** the module currently imports only `from ..network import delay_edge_kwargs`
(line 41) — `connection_disagreement` is NOT in scope. Extend that line to:
```python
from ..network import connection_disagreement, delay_edge_kwargs
```
(`delay_edge_kwargs` is an existing pure function; `connection_disagreement` is the pure
helper from `network.py`.)

**Edge loop** (`_build_pyvis_network`, currently lines 231-240):
```python
    for c in isa.connections:
        kwargs = delay_edge_kwargs(c)          # fresh dict per call {"title": .., "dashes": ..}
        label = c.polarity
        width = 2
        if connection_disagreement(c)["polarity_contested"]:
            label = f"{c.polarity} ⚠"
            width = 6
            kwargs["title"] = f'{kwargs["title"]} · ⚠ {t("cld.contested_sign")}'
        net.add_edge(
            c.source,
            c.target,
            label=label,
            color=EDGE_COLORS["reinforcing" if c.polarity == "+" else "opposing"],
            arrows="to",
            width=width,
            **kwargs,
        )
```
- `width=6` for contested vs `2` default (heavy edge = disagreement).
- `label` appends `⚠` to the polarity glyph (`"+"` → `"+ ⚠"`).
- `title` (hover) appends `· ⚠ <contested_sign text>`; `kwargs["title"]` already exists
  from `delay_edge_kwargs`, so we extend it (no key collision: `title`/`dashes` come only
  from `kwargs`; `width`/`label`/`color` are passed explicitly).

**Legend.** Next to the existing delay legend
(`ui.tags.small(t("cld.delay_legend"), ...)`, ~line 135), add:
```python
            ui.tags.small(t("cld.contested_legend"), class_="text-muted"),
```

**i18n** — two new keys joining the `cld.*` namespace, **each with all 9 languages**
(en es fr de lt pt it no el — `test_loader_handles_all_supported_languages` hard-fails on
any missing language). Supply verbatim:

`cld.contested_legend`:
| lang | value |
|---|---|
| en | ⚠ / thick edge = raters disagree on the sign |
| es | ⚠ / arista gruesa = los evaluadores discrepan en el signo |
| fr | ⚠ / arête épaisse = les évaluateurs sont en désaccord sur le signe |
| de | ⚠ / dicke Kante = Bewerter sind sich beim Vorzeichen uneinig |
| lt | ⚠ / stora briauna = vertintojai nesutaria dėl ženklo |
| pt | ⚠ / aresta grossa = os avaliadores discordam no sinal |
| it | ⚠ / arco spesso = i valutatori non concordano sul segno |
| no | ⚠ / tykk kant = vurdererne er uenige om fortegnet |
| el | ⚠ / παχιά ακμή = οι αξιολογητές διαφωνούν ως προς το πρόσημο |

`cld.contested_sign` (used in the hover title):
| lang | value |
|---|---|
| en | contested sign |
| es | signo en disputa |
| fr | signe contesté |
| de | umstrittenes Vorzeichen |
| lt | ginčijamas ženklas |
| pt | sinal contestado |
| it | segno conteso |
| no | omstridt fortegn |
| el | αμφισβητούμενο πρόσημο |

## Error handling / edge cases

- **<2 ratings** (single-author, imported, or one rater) → `polarity_contested` is
  `False` → default styling, identical to today.
- **Unanimous ratings** → `polarity_contested` False → default styling.
- **A node filtered out** of the view → its edges aren't added (existing
  `filter_elements` behaviour, unchanged) — contested styling only applies to rendered
  edges.
- Performance: `connection_disagreement` is O(ratings) per edge; negligible for typical
  graphs (the module already rebuilds the whole Network on every reactive change).

## Testing

- **Unit** — extend the **existing `tests/test_cld.py`** (it already imports
  `_build_pyvis_network`, has a `_fixture()` helper, and reads edges via
  `net.get_network_data()` — do NOT create a new file). Add a test that builds an
  `IsaData` with two elements and one connection carrying **two sign-disagreeing
  ratings** (`Rating(..., polarity="+")` and `Rating(..., polarity="-")`), calls
  `_build_pyvis_network` (same kwargs the file's other tests use — e.g.
  `layout_kind="hierarchical", direction="UD", level_sep=90, node_sp=120,
  size_scale=1.0, font_scale=1.0`), and inspects the edges (`net.edges` or
  `net.get_network_data()[1]`, same list object): assert the contested edge has
  `edge["width"] > 2` and `"⚠" in edge["label"]`; and a control connection with **<2
  ratings** has `edge["width"] == 2` and no `⚠`. (Verified live: pyvis edge dicts carry
  int `width` and the `⚠` glyph survives in `label`.)
- **i18n** presence test for `cld.contested_legend` + `cld.contested_sign`.
- The existing CLD e2e (`test_cld_e2e.py`) must stay green (default rendering unchanged
  for non-contested models); no new browser test needed — the build-function unit test
  fully covers the styling logic without a browser.

## Out of scope (YAGNI)

- Scaling width/marker by `strength_spread` / `confidence_spread` (boolean only for v1).
- Styling contested edges in the *other* pyvis views (loops, leverage, intervention) —
  CLD is the primary system map; the others can follow as separate work.
- A colour/legend redesign; an interactive "show only contested" CLD filter.
- The #5b analytical half (flagging loops/quadrant/leverage that hinge on contested
  edges) — tracked separately as #9.
