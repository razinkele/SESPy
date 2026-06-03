"""Internationalisation — Python port of the R app's `shiny.i18n` system.

Compatible with the R app's translation JSON files (see
`SESToolbox/MarineSABRES_SES_Shiny/translations/common/buttons.json` for
shape). Each file is `{"languages": [...], "translation": {key: {lang: text}}}`.
The same file can feed both apps once the R-side path is shared.

Reactive integration:
- `Translator.language` is a `reactive.value(str)`. UI rendered inside an
  `@render.ui` context that calls `t(...)` automatically re-renders when
  the language changes — no full-page reload needed for those.
- Static UI built at app construction time captures the language at the
  moment of construction. To re-render those, the language switcher
  triggers a page reload (same fallback pattern as the R app at app.R:838).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from shiny import reactive

DEFAULT_FALLBACK = "en"
SUPPORTED_LANGUAGES = (
    "en", "es", "fr", "de", "lt", "pt", "it", "no", "el",
)


def _load_one(path: Path) -> dict[str, dict[str, str]]:
    """Load a single R-format translation file → flat {key: {lang: text}}."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw.get("translation", {})


def load_translations(directory: Path | str) -> dict[str, dict[str, str]]:
    """Walk `directory` recursively, merging every *.json file's `translation`
    block into one flat dict. Mirrors how `shiny.i18n::Translator` consumes
    R's `translations/common/`, `translations/modules/`, etc.
    """
    root = Path(directory)
    out: dict[str, dict[str, str]] = {}
    for path in sorted(root.rglob("*.json")):
        # Skip the merged-output file the R build script emits — it's a
        # cache, not a source.
        if path.name.startswith("_"):
            continue
        try:
            out.update(_load_one(path))
        except (json.JSONDecodeError, OSError):
            # Bad JSON in one file shouldn't kill startup; log and skip.
            continue
    return out


@dataclass
class Translator:
    """Stateful translator. One instance per app (created in app.py).

    The plain `_lang` attribute is the source of truth — it always reflects
    the current language synchronously, so unit tests and non-reactive code
    work without a Shiny session.

    The `language` `reactive.Value` is a *notification channel*: any UI
    rendered inside an `@render.ui` that calls `t(...)` subscribes via
    `language.get()` and re-renders when `set_language` is called. Outside
    a reactive flush, the reactive value may lag the plain attribute by one
    flush cycle — that's fine, the read in `t()` prefers the plain attr.
    """

    translations: dict[str, dict[str, str]]
    languages: tuple[str, ...] = SUPPORTED_LANGUAGES
    fallback: str = DEFAULT_FALLBACK
    _lang: str = field(default=DEFAULT_FALLBACK)
    language: reactive.Value[str] = field(default=None)  # type: ignore

    def __post_init__(self) -> None:
        if self.language is None:
            self.language = reactive.value(self._lang)

    def t(self, key: str, **fmt: Any) -> str:
        """Look up a translation key. Falls back to the fallback language,
        then to the key itself if missing entirely. Supports `str.format`-
        style keyword interpolation for templates like `"Found {n} loops"`.
        """
        # Touch the reactive value so this call subscribes when called
        # inside a reactive context. The actual lang choice comes from the
        # plain attribute (works synchronously in tests too).
        try:
            self.language.get()
        except Exception:
            pass
        lang = self._lang
        entry = self.translations.get(key)
        if entry is None:
            text = key  # show the key itself when missing — flag for translation
        else:
            text = entry.get(lang) or entry.get(self.fallback) or key
        if fmt:
            try:
                return text.format(**fmt)
            except (KeyError, IndexError, ValueError):
                return text
        return text

    def set_language(self, lang: str) -> None:
        if lang not in self.languages:
            return
        self._lang = lang
        try:
            with reactive.isolate():
                self.language.set(lang)
        except Exception:
            # Outside a Shiny session (e.g. in unit tests) the reactive
            # write is a no-op — the plain attribute is what matters.
            pass


# --------------------------------------------------------------------------
# Module-level singleton — any module can `from sespy.i18n import t` and
# call `t("key")` without explicitly receiving the Translator instance.
# `app.py` calls `set_default(T)` after creating its Translator. Modules
# that import `t` get whatever is set at the time their UI is constructed
# (i.e. the language picked from the URL query, plus any subsequent
# `T.set_language` calls — which won't re-render statically-built UIs).
# --------------------------------------------------------------------------

_default_translator: Translator | None = None


def set_default(translator: Translator) -> None:
    global _default_translator
    _default_translator = translator


def get_default() -> Translator | None:
    return _default_translator


def t(key: str, **fmt) -> str:
    """Translate via the default translator. Returns the key itself if no
    default has been registered yet (e.g. during early imports)."""
    if _default_translator is None:
        return key
    return _default_translator.t(key, **fmt)


def detect_initial_language(
    query_string: str | None,
    *,
    default: str = DEFAULT_FALLBACK,
    supported: tuple[str, ...] = SUPPORTED_LANGUAGES,
) -> str:
    """Parse a `?lang=es` URL query param. Returns `default` if missing or
    invalid. Used at session start to honour the language URL param the way
    the R app does at app.R:818.
    """
    if not query_string:
        return default
    from urllib.parse import parse_qs

    qs = parse_qs(query_string.lstrip("?"))
    lang_values = qs.get("lang") or qs.get("language") or []
    if lang_values and lang_values[0] in supported:
        return lang_values[0]
    return default
