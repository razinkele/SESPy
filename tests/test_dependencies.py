import re
import tomllib
from pathlib import Path

BANNED = {"shiny", "htmltools", "pyvis-optimized", "pytest-playwright"}


def _name(req: str) -> str:
    return re.split(r"[\s<>=!~;\[(]", req.strip(), maxsplit=1)[0].lower().replace("_", "-")


def test_dependencies_exclude_ui():
    data = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8"))
    reqs = list(data["project"]["dependencies"])
    for extra in data["project"].get("optional-dependencies", {}).values():
        reqs.extend(extra)
    found = sorted({_name(r) for r in reqs} & BANNED)
    assert found == [], f"UI dependencies still declared: {found}"
