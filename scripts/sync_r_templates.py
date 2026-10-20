"""Sync SESPy's MarineSABRES gallery with R's curated templates (P2).

Run from the SESPy repo root (so `-m` imports this checkout's `sespy`):

    micromamba run -n shiny python -m scripts.sync_r_templates --r-root <R app dir>
        [--rev vX.Y.Z] [--check] [--accept-warnings]
    micromamba run -n shiny python -m scripts.sync_r_templates --from-fixtures [--check]

<R app dir> is .../SESToolbox/MarineSABRES_SES_Shiny. The R repo is only read
with `git show`; it is never checked out, switched or stashed. All logic
lives in sespy.r_template_catalogue.sync(); this is a thin wrapper.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sespy.r_template_catalogue import sync

REPO_ROOT = Path(__file__).resolve().parents[1]   # the directory holding scripts/


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m scripts.sync_r_templates",
                                 description=__doc__.splitlines()[0])
    ap.add_argument("--r-root", type=Path, help="the R app directory (MarineSABRES_SES_Shiny)")
    ap.add_argument("--rev", help="R release tag (default: the pinned tag)")
    ap.add_argument("--from-fixtures", action="store_true",
                    help="read the 7 templates from tests/parity/ (offline, tests)")
    ap.add_argument("--check", action="store_true", help="report drift, write nothing")
    ap.add_argument("--accept-warnings", action="store_true",
                    help="accept off-rule links / type mismatches (recorded in the pin)")
    a = ap.parse_args(argv)
    result = sync(repo_root=REPO_ROOT, r_root=a.r_root, rev=a.rev,
                  from_fixtures=a.from_fixtures, check=a.check,
                  accept_warnings=a.accept_warnings)
    for line in result.lines:
        print(line)
    return result.code


if __name__ == "__main__":
    sys.exit(main())
