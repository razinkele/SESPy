"""App-layer i18n: the reactive Translator and per-session translators.

The library's `sespy.i18n` is plain (no shiny). This module adds:

Reactive integration:
- `Translator.language` is a `reactive.value(str)`. UI rendered inside an
  `@render.ui` context that calls `t(...)` automatically re-renders when
  the language changes — no full-page reload needed for those.
- Static UI built at app construction time captures the language at the
  moment of construction. To re-render those, the language switcher
  triggers a page reload (same fallback pattern as the R app at app.R:838).

Multi-user safety: importing this module installs `_session_resolver` as the
library's resolver hook, so inside a Shiny session `get_default()` / `t()`
return a session-specific clone of the process default, isolating each
user's language. The clone lives on the root session: inside a module server
the current session is a SessionProxy, and every module scope must see the
translator app.py configured, not a fresh clone at the process default.

App code imports everything i18n from here; the re-exported names are the
library's own objects, so monkeypatching `sespy.i18n` still takes effect.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from shiny import reactive
from shiny.session import get_current_session

from . import i18n as _lib
from .i18n import (
    DEFAULT_FALLBACK,
    SUPPORTED_LANGUAGES,
    detect_initial_language,
    get_default,
    load_translations,
    set_default,
    t,
)

__all__ = [
    "DEFAULT_FALLBACK",
    "SUPPORTED_LANGUAGES",
    "Translator",
    "detect_initial_language",
    "get_default",
    "load_translations",
    "set_default",
    "t",
]


@dataclass
class Translator(_lib.Translator):
    """Reactive translator. One instance per app (created in app.py), plus
    one clone per session (see `_session_resolver`).

    The `language` `reactive.Value` is a *notification channel*: any UI
    rendered inside an `@render.ui` that calls `t(...)` subscribes via
    `language.get()` and re-renders when `set_language` is called. Outside
    a reactive flush, the reactive value may lag the plain attribute by one
    flush cycle — that's fine, the read in `t()` prefers the plain attr.
    """

    language: reactive.Value[str] = field(default=None)  # type: ignore

    def __post_init__(self) -> None:
        if self.language is None:
            self.language = reactive.value(self._lang)

    def t(self, key: str, **fmt: Any) -> str:
        # Touch the reactive value so this call subscribes when called
        # inside a reactive context. The actual lang choice comes from the
        # plain attribute (works synchronously in tests too).
        try:
            self.language.get()
        except Exception:
            pass
        return super().t(key, **fmt)

    def set_language(self, lang: str) -> None:
        super().set_language(lang)
        try:
            with reactive.isolate():
                # Unsupported codes leave _lang unchanged, and setting a
                # reactive value to its current value is a no-op.
                self.language.set(self._lang)
        except Exception:
            # Outside a Shiny session (e.g. in unit tests) the reactive
            # write is a no-op — the plain attribute is what matters.
            pass


def _session_resolver(default: _lib.Translator | None) -> _lib.Translator | None:
    """The library resolver hook: the root session's translator, created on
    first use as a reactive clone of the process default. Outside a session
    it returns `default`; in a session with no default, None."""
    session = get_current_session()
    if session is None:
        return default
    session = session.root_scope()
    if not hasattr(session, "_translator"):
        if default is None:
            return None
        # A session-isolated clone sharing the same translations reference.
        # Always the reactive class, even when the default is a plain one.
        sess_t = Translator(
            translations=default.translations,
            languages=default.languages,
            fallback=default.fallback,
            _lang=default._lang,
        )
        setattr(session, "_translator", sess_t)
    return getattr(session, "_translator")


_lib.set_resolver(_session_resolver)
