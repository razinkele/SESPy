def test_leverage_rows_carry_realm_and_alc():
    """ranked() must expose both new fields, and the realm must be the
    loop-aware one.

    The last two assertions pin the FEATURE, not just the call names: an
    earlier draft of these tests passed with the ALC column stripped out
    entirely, because it only checked that the functions were called.
    """
    from sespy.modules import analysis_leverage
    src = analysis_leverage.__file__
    text = open(src, encoding="utf-8").read()
    assert "leverage_realms(" in text, "must use the loop-aware realms"
    assert "adjusted_loop_centrality(" in text
    assert "alc_is_truncated(" in text
    assert "leverage_realm(" not in text.replace("leverage_realms(", ""), (
        "the per-row type-only call must be gone")
    # The column must actually reach the row and the header.
    assert 'row["alc"]' in text, "ranked() must put alc on the row"
    assert 'base_cols.insert(5, "alc")' in text, "alc must reach base_cols"


def test_leverage_enumerates_loops_once():
    """Every consumer must share ONE enumeration. feedback_loops is bounded
    but not free, and an earlier draft ran it twice per render because the
    truncation reactive re-enumerated."""
    from sespy.modules import analysis_leverage
    text = open(analysis_leverage.__file__, encoding="utf-8").read()
    assert text.count("feedback_loops(") == 1, "one enumeration, shared"
    assert text.count("cycles=") == 3, (
        "leverage_realms, adjusted_loop_centrality and alc_is_truncated must "
        "each receive the shared list")


def test_alc_translation_keys_exist_in_every_language():
    """Resolve through the PRODUCTION loader, the way tests/test_i18n.py does.
    A hand-rolled recursive search over core.json would find a key sitting at
    the wrong nesting level and pass, while t() at runtime would not resolve
    it."""
    from pathlib import Path
    from sespy.i18n import load_translations

    root = Path(__file__).resolve().parents[1]
    tr = load_translations(root / "sespy" / "translations")

    langs = {"en", "es", "fr", "de", "lt", "pt", "it", "no", "el"}
    for key in ("leverage.caption", "leverage.alc_truncated"):
        assert key in tr, f"{key} does not resolve through load_translations"
        assert langs.issubset(set(tr[key])), f"{key} is missing languages"
        assert all(tr[key][l].strip() for l in langs), f"{key} has an empty value"


def test_promotion_actually_fires_on_the_sample_project():
    """The structural rule must be pinned on real data, not only on a 2-node
    synthetic fixture. An Activity inside a detected loop must resolve to
    'feedbacks' where the type-only mapping would have said 'design'."""
    from pathlib import Path
    from sespy.data_structure import load_sample
    from sespy.network import leverage_realms, leverage_realm

    isa = load_sample(
        Path(__file__).resolve().parents[1] / "data" / "sample_ses.json")
    realms = leverage_realms(isa)
    by_id = {el.id: el for el in isa.elements}

    activities = [nid for nid, el in by_id.items() if el.type == "Activities"]
    assert activities, "sample must contain Activities or this pins nothing"

    promoted = [nid for nid in activities if realms[nid] == "feedbacks"]
    assert promoted, (
        "no Activity was promoted on the sample project — the structural rule "
        "is not firing on real data")
    # Every promoted node is one the type-only mapping would have called
    # 'design', which is exactly what promotion means.
    for nid in promoted:
        assert leverage_realm(by_id[nid].type) == "design"
    # And an unpromoted Activity still falls back to the type mapping.
    for nid in set(activities) - set(promoted):
        assert realms[nid] == "design"
