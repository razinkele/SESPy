"""Shared fixtures for the causal path diagnostics tests."""
from __future__ import annotations

from sespy.data_structure import Connection, Element, IsaData


def worked_example_isa() -> IsaData:
    """The intervention worked example as a 10-node, 12-edge model.

    Development note 2026-11-21, §1.2–1.3; synthetic values. The note is not
    in git, so it is transcribed here. Its weights are snapped to levels
    (w < 0.45 weak, w < 0.70 medium, else strong), its delay steps to levels
    (1 immediate, 2 short, 3 long), and every confidence is 3 because the
    note gives none.
    """
    nodes = [
        ("I", "Eco-moorings + anchoring exclusion", "Responses"),
        ("C", "Compliance", "Responses"),
        ("D", "Direct seabed disturbance", "Pressures"),
        ("S", "Seagrass condition", "Marine Processes & Functioning"),
        ("N", "Nursery habitat function", "Marine Processes & Functioning"),
        ("F", "Fish biomass", "Ecosystem Services"),
        ("W", "Water clarity", "Marine Processes & Functioning"),
        ("R", "Recreation value", "Goods & Benefits"),
        ("A", "Local acceptance", "Drivers"),
        ("X", "Displaced anchoring pressure", "Pressures"),
    ]
    # Note weights (w) and delay steps, for the record:
    # I>C .80/1, C>D .85/1, D>S .90/2, S>N .80/2, N>F .65/3, S>W .55/2,
    # W>R .50/2, S>R .45/3, R>A .40/2, A>C .55/1, I>X .45/1, X>S .35/2.
    edges = [
        ("I", "C", "+", "strong", "immediate"),
        ("C", "D", "-", "strong", "immediate"),
        ("D", "S", "-", "strong", "short"),
        ("S", "N", "+", "strong", "short"),
        ("N", "F", "+", "medium", "long"),
        ("S", "W", "+", "medium", "short"),
        ("W", "R", "+", "medium", "short"),
        ("S", "R", "+", "medium", "long"),
        ("R", "A", "+", "weak", "short"),
        ("A", "C", "+", "medium", "immediate"),
        ("I", "X", "+", "medium", "immediate"),
        ("X", "S", "-", "weak", "short"),
    ]
    return IsaData(
        elements=[Element(id=i, label=lab, type=t) for i, lab, t in nodes],
        connections=[Connection(source=s, target=t, polarity=p, strength=w,
                                confidence=3, delay=d)
                     for s, t, p, w, d in edges],
    )
