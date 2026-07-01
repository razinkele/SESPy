"""Tests for the CLD element-type keep-set.

Regression guard: QSEM / food-web imports use their own node themes (or none),
so their Elements get type="" or a custom theme. The DAPSIWRM-only type filter
must not silently drop them, or an imported model renders as an empty diagram.
"""
from sespy.constants import DAPSIWRM_ELEMENTS
from sespy.data_structure import Element, IsaData
from sespy.modules.cld_visualization import cld_keep_types


def _isa(*types: str) -> IsaData:
    els = [Element(id=f"N{i}", label=str(i), type=t) for i, t in enumerate(types)]
    return IsaData(elements=els, connections=[])


def test_untyped_and_custom_themes_are_always_kept():
    isa = _isa("", "OWFs", "Drivers")
    keep = cld_keep_types(isa, list(DAPSIWRM_ELEMENTS))
    assert "" in keep          # untyped (non-DAPSIWRM) kept
    assert "OWFs" in keep      # custom QSEM theme kept
    assert "Drivers" in keep   # selected DAPSIWRM kept


def test_custom_kept_even_when_nothing_selected():
    isa = _isa("OWFs", "")
    keep = cld_keep_types(isa, [])
    assert "OWFs" in keep and "" in keep  # filter doesn't offer these -> never hidden


def test_deselected_dapsiwrm_type_is_hidden():
    isa = _isa("Drivers", "Responses")
    keep = cld_keep_types(isa, ["Responses"])   # user unchecked "Drivers"
    assert "Drivers" not in keep                 # DAPSIWRM type the filter offers can hide
    assert "Responses" in keep
