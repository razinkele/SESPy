"""Module-level pins for the SES Subsystem Modules block (#24).

Source-text assertions pin the FEATURE, not just call names — the lesson
from #23, where grep-for-the-function tests passed with the column absent.
"""


def test_metrics_module_wires_hypermodules():
    from sespy.modules import analysis_metrics

    text = open(analysis_metrics.__file__, encoding="utf-8").read()
    assert "net_analysis.hypermodules(" in text, "must call the library fn"
    assert '"run_hypermodules"' in text, "the run button"
    assert 'ui.output_ui("hypermodules_summary")' in text, "the UI slot"
    assert "_hypermodules_result" in text, "the reactive result value"
    # The reset-on-isa-change effect must cover the new result value.
    assert text.count("_hypermodules_result.set(None)") == 1


def test_hypermodules_translation_keys_resolve():
    """Through the PRODUCTION loader, per the repo convention."""
    from pathlib import Path
    from sespy.i18n import load_translations

    tr = load_translations(
        Path(__file__).resolve().parents[1] / "sespy" / "translations")
    langs = {"en", "es", "fr", "de", "lt", "pt", "it", "no", "el"}
    for key in ("metrics.hypermodules", "metrics.hypermodules_run",
                "metrics.hypermodules_hint", "metrics.hypermodules_score",
                "metrics.hypermodules_no_coupling",
                "metrics.hypermodules_single_projection",
                "metrics.hypermodules_no_congruence",
                "metrics.hypermodules_caption"):
        assert key in tr, f"{key} does not resolve"
        assert langs.issubset(set(tr[key])), f"{key} missing languages"
        assert all(tr[key][l].strip() for l in langs), f"{key} empty value"
