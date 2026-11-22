# SESPy: DAPSI(W)R(M) social-ecological system library

[![CI](https://github.com/razinkele/SESPy/actions/workflows/ci.yml/badge.svg)](https://github.com/razinkele/SESPy/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)

SESPy is a pure-Python library for DAPSI(W)R(M) social-ecological system
(SES) modelling and analysis, with parity to the R MarineSABRES SES Toolbox
(Horizon Europe Marine-SABRES). It has no web-framework dependency: nothing
in the package imports Shiny, htmltools or pyvis.

Since 1.18.0 SESPy is only the library. The Shiny research UI that used to live
in this repository moved to [razinkele/sespy-app](https://github.com/razinkele/sespy-app)
(version 1.0.0), which depends on this library.

## Install

```bash
pip install "sespy @ git+https://github.com/razinkele/SESPy@v1.20.0"
```

Optional extras: `sespy[pdf]` (WeasyPrint PDF report export; needs native
cairo/pango libraries), `sespy[bayes]` (pgmpy belief networks), `sespy[prod]`
(python-igraph), `sespy[test]`, `sespy[lint]`.

## Module map

| Module | Purpose |
|---|---|
| `data_structure`, `persistent_storage`, `autosave`, `recent_projects`, `bookmark` | ISA project model, JSON project I/O, per-browser autosave, recent projects, view bookmarks |
| `excel_import`, `qsem_import`, `claude_session_import` | Excel, `.qsem` and Claude session-transcript importers |
| `network`, `dynamics`, `bayes` | Graph metrics and loops, Boolean/simulation dynamics, path-set Bayesian networks |
| `link_rules`, `connection_scorer`, `r_connection_kb`, `wizard`, `claude_backend` | DAPSI(W)R(M) link rules, rule-based connection scoring (R parity), AI-ISA wizard flow and Claude suggestions |
| `r_kb`, `kb_suggestions`, `kb_report`, `regional_seas`, `r_sync` | R knowledge-base snapshots, context suggestions, regional report content, pinned R-sourced files |
| `r_template_mapper`, `r_template_catalogue` | R `*_SES_Template.json` conversion and the template gallery |
| `response_register`, `response_reports`, `stakeholders`, `stakeholder_reports` | Response register, stakeholder register and their exports |
| `report` | HTML, PDF and Word project reports |
| `i18n`, `constants`, `utils`, `input_utils` | Translation catalogue (plain language state), DAPSI(W)R(M) constants, shared helpers |

## Consumers

- [razinkele/sespy-app](https://github.com/razinkele/sespy-app): the Shiny research UI.
- MosaicSES: an optional app extra built on SESPy.
- Nid4Ocean imports a pinned set of library names; `tests/test_public_api.py` fails if one of them disappears.

## Development

```bash
pip install -e ".[test,lint]"
pytest tests -q
python scripts/run_library_tests.py   # same suite with shiny/htmltools/pyvis blocked
ruff check sespy tests scripts
```

R-parity fixtures and the R sources they pin live under `tests/parity/`.
See `CHANGELOG.md` for release history.

## License

MIT, see [LICENSE](LICENSE).