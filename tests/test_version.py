import tomllib
from pathlib import Path
import sespy

def test_pyproject_version_matches_dunder():
    data = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["version"] == sespy.__version__
