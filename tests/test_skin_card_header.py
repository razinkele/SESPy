"""Card headers are white on the skin's dark-blue gradient.

The skin's `.card-header { color: #fff }` has the same specificity as
Bootstrap's `.card-header { color: var(--bs-card-cap-color) }`, and
Bootstrap's stylesheet loads after the skin, so the header text came out in
the body colour, dark on dark (MosaicSES tester report, 23 Oct 2026).
Setting the variable makes Bootstrap's own rule resolve to white whatever
the load order."""
import re
from pathlib import Path

import sespy

SKIN = Path(sespy.__file__).parent / "www" / "sespy-skin.css"


def test_card_header_sets_bootstrap_cap_color():
    css = SKIN.read_text(encoding="utf-8")
    block = re.search(r"(?m)^\.card-header\s*\{([^}]*)\}", css)
    assert block, "no top-level .card-header rule in sespy-skin.css"
    assert re.search(r"--bs-card-cap-color\s*:\s*#fff", block.group(1)), block.group(1)
