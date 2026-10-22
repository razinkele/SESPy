"""P1b — content parity of the response-register code lists with R
constants.R (v1.33.0 fixture, tests/parity/r_source/constants.R).

A hash pin alone would let a hand-copy error pass, so a small R-literal
parser reads each ported vector and data.frame and compares it, order
included, with the Python constants. The parser knows only what these
constants use (string literals, numbers, TRUE/FALSE, `c()`, `list()`,
`rep()`, `paste0()`, `data.frame()`, `name = value` pairs, `#` comments)
and raises on anything else, so an R change of shape surfaces at re-pin.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from sespy import response_register as RR
from sespy.constants import POLICY_TARGET_CODES
from sespy.data_structure import INDICATOR_FIELDS
from sespy.stakeholders import STAKEHOLDER_ROLES

ROOT = Path(__file__).resolve().parents[2]
R_SOURCE = ROOT / "tests" / "parity" / "r_source"


def _read(name: str) -> str:
    return (R_SOURCE / name).read_bytes().decode("utf-8").replace("\r\n", "\n")


# ---- a minimal R-literal parser ----------------------------------------------

_TOKEN = re.compile(r"""
    (?P<ws>\s+)
  | (?P<comment>\#[^\n]*)
  | (?P<str>"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')
  | (?P<num>\d+(?:\.\d+)?(?:[eE][+-]?\d+)?L?)
  | (?P<ident>[A-Za-z.][A-Za-z0-9._]*)
  | (?P<op>[(),=])
""", re.X)


def _next(src: str, pos: int) -> tuple[str, str, int]:
    """The token at `pos` (whitespace and comments skipped) and the position
    after it. Lazy, so the rest of the R file is never tokenised."""
    while pos < len(src):
        m = _TOKEN.match(src, pos)
        if not m:
            raise ValueError(f"unexpected R text at {pos}: {src[pos:pos + 30]!r}")
        if m.lastgroup not in ("ws", "comment"):
            return m.lastgroup, m.group(), m.end()
        pos = m.end()
    return "eof", "", pos


def _unescape(lit: str) -> str:
    body = lit[1:-1]
    return re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t"}.get(m.group(1), m.group(1)), body)


class _Parser:
    def __init__(self, src: str):
        self.src, self.pos = src, 0

    def peek(self, k: int = 1) -> tuple[str, str]:
        pos, tok = self.pos, ("eof", "")
        for _ in range(k):
            kind, text, pos = _next(self.src, pos)
            tok = (kind, text)
        return tok

    def take(self, value: str | None = None) -> tuple[str, str]:
        kind, text, self.pos = _next(self.src, self.pos)
        if value is not None and text != value:
            raise ValueError(f"expected {value!r}, got {(kind, text)!r}")
        return kind, text

    def expr(self) -> Any:
        kind, text = self.take()
        if kind == "str":
            return _unescape(text)
        if kind == "num":
            return float(text.rstrip("L")) if "." in text or "e" in text.lower() else int(text.rstrip("L"))
        if kind == "ident" and text in ("TRUE", "FALSE"):
            return text == "TRUE"
        if kind == "ident" and self.peek()[1] == "(":
            return self.call(text)
        raise ValueError(f"unsupported R expression {text!r}")

    def args(self) -> list[tuple[str | None, Any]]:
        self.take("(")
        out: list[tuple[str | None, Any]] = []
        while self.peek()[1] != ")":
            name = None
            if self.peek()[0] in ("ident", "str") and self.peek(2)[1] == "=":
                kind, text = self.take()
                name = _unescape(text) if kind == "str" else text
                self.take("=")
            out.append((name, self.expr()))
            if self.peek()[1] == ",":
                self.take(",")
        self.take(")")
        return out

    def call(self, fn: str) -> Any:
        args = self.args()
        named = [n is not None for n, _ in args]
        if fn in ("c", "list"):
            if args and all(named):
                return {n: v for n, v in args}
            if any(named):
                raise ValueError(f"{fn}() mixes named and unnamed arguments")
            flat: list[Any] = []
            for _, v in args:
                flat.extend(v if isinstance(v, list) else [v])
            return flat
        if fn == "rep":
            (_, x), (_, n) = args
            return [x] * int(n)
        if fn == "paste0":
            (_, prefix), (_, vec) = args
            return [f"{prefix}{v}" for v in vec]
        if fn == "data.frame":
            return {n: v for n, v in args if n != "stringsAsFactors"}
        raise ValueError(f"unsupported R function {fn}()")


def r_constant(text: str, name: str) -> Any:
    m = re.search(rf"^{re.escape(name)} <- ", text, re.M)
    assert m, f"{name} not found"
    return _Parser(text[m.end():]).expr()


@pytest.fixture(scope="module")
def constants_r() -> str:
    return _read("constants.R")


def test_parser_reads_the_shapes_it_needs(constants_r):
    assert r_constant('X <- c(a = "1", b = "2") # tail\n', "X") == {"a": "1", "b": "2"}
    assert r_constant('X <- c("a", rep("b", 2), paste0("p", c("x", "y")))\n', "X") == [
        "a", "b", "b", "px", "py"]
    with pytest.raises(ValueError):
        r_constant("X <- setdiff(Y, 1)\n", "X")
    assert r_constant(constants_r, "ELEMENT_ID_PREFIX")["measures"] == "RM"    # trailing comments


# ---- the register code lists (constants.R:780-846, v1.33.0) -------------------

@pytest.mark.parametrize("r_name,py", [
    ("RM_TYPE_CODES", RR.RM_TYPE_CODES),
    ("RM_TARGET_CODES", RR.RM_TARGET_CODES),
    ("RM_STATUS_CODES", RR.RM_STATUS_CODES),
])
def test_named_code_vectors(constants_r, r_name, py):
    assert list(r_constant(constants_r, r_name).items()) == list(py.items())


@pytest.mark.parametrize("r_name,py", [
    ("GOVERNANCE_LEVELS", RR.GOVERNANCE_LEVELS),
    ("TENET_LEVELS", RR.TENET_LEVELS),
    ("PESTLE_CODES", RR.PESTLE_CODES),
    ("RM_REGISTER_COLUMNS", RR.RM_REGISTER_COLUMNS),
    ("RM_DISPLAY_COLUMNS", RR.RM_DISPLAY_COLUMNS),
])
def test_vectors(constants_r, r_name, py):
    assert tuple(r_constant(constants_r, r_name)) == py


def test_ebm_tables(constants_r):
    assert tuple(r_constant(constants_r, "EBM_TENETS")["code"]) == RR.TENET_CODES
    inst = r_constant(constants_r, "EBM_POLICY_INSTRUMENTS")
    assert tuple(zip(inst["code"], inst["level"])) == RR.EBM_POLICY_INSTRUMENTS
    meas = r_constant(constants_r, "EBM_MANAGEMENT_MEASURES")
    assert tuple(zip(meas["code"], meas["category"], meas["dapsiwrm_target"])) \
        == RR.EBM_MANAGEMENT_MEASURES


def test_cross_module_constants(constants_r):
    assert tuple(r_constant(constants_r, "STAKEHOLDER_TYPES")) == STAKEHOLDER_ROLES
    assert tuple(r_constant(constants_r, "WP5_POLICY_TARGETS")) == POLICY_TARGET_CODES
    assert tuple(c.lower() for c in r_constant(constants_r, "ISA_INDICATOR_COLUMNS")) \
        == INDICATOR_FIELDS
    assert r_constant(constants_r, "ELEMENT_ID_PREFIX")["measures"] == "RM"
    assert r_constant(constants_r, "PIMS_ID_PREFIX")["stakeholder"] == "SH"


def test_r_normalisers_still_have_the_ported_rules():
    # By string presence: an R change here surfaces at re-pin.
    rm = _read("response_measures_schema.R")
    assert '"intermediate"' in rm and "setdiff(TENET_LEVELS" in rm
    sh = _read("stakeholder_schema.R")
    assert "STAKEHOLDER_TYPES[STAKEHOLDER_TYPES %in% t]" in sh
