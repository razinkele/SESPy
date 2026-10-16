"""Per-browser token — port of R 1.20.1 N7.

Each browser keeps a random id in localStorage and reports it to the server
as a root-level input once Shiny connects. Server-side per-user files
(autosave, recent projects) are keyed by a hash of it, so on a shared Shiny
Server — where every session runs as the same OS user — one visitor never
sees another's work. It identifies a browser, not a person: it is not an
authentication mechanism.
"""

from __future__ import annotations

from shiny import ui

from .autosave import valid_token

BROWSER_TOKEN_INPUT = "sespy_browser_token"

_SCRIPT = """
(function () {
  var KEY = "sespy_browser_token";
  function token() {
    var t = null;
    try { t = window.localStorage.getItem(KEY); } catch (e) { return null; }
    if (!t) {
      t = (window.crypto && window.crypto.randomUUID) ? window.crypto.randomUUID() : null;
      if (!t) { return null; }
      try { window.localStorage.setItem(KEY, t); } catch (e) { return null; }
    }
    return t;
  }
  // Wait for session init: the socket-open event fires before the client's
  // init message, and an input update sent then makes the server drop the
  // session ("Invalid method for the current session state").
  $(document).on("shiny:sessioninitialized", function () {
    var t = token();
    if (t) { Shiny.setInputValue("%s", t, {priority: "event"}); }
  });
})();
""" % BROWSER_TOKEN_INPUT


def browser_token_script() -> ui.Tag:
    """Script tag to include once per page."""
    return ui.tags.script(_SCRIPT)


def read_browser_token(input) -> str | None:
    """The validated token, or None before the browser has sent one (or
    with storage/JS blocked). Reading it inside a reactive context takes a
    dependency on the input."""
    try:
        value = getattr(input, BROWSER_TOKEN_INPUT)()
    except Exception:
        return None
    return value if valid_token(value) else None
