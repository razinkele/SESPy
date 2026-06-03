"""Boot the app in-process and trigger a session, capturing any error."""
import asyncio
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app  # noqa: E402

from shiny._app import App  # noqa: E402

# Fake an HTTP request through the ASGI app
async def main():
    from shiny._connection import StarletteConnection  # type: ignore

    print("App constructed successfully:", type(app.app).__name__)
    print("Number of nav items:", len(app.NAV))
    print("Number of panels:", len(app.PANELS))


asyncio.run(main())
