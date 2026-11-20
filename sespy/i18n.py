"""Internationalisation — Python port of the R app's `shiny.i18n` system.

Compatible with the R app's translation JSON files (see
`SESToolbox/MarineSABRES_SES_Shiny/translations/common/buttons.json` for
shape). Each file is `{"languages": [...], "translation": {key: {lang: text}}}`.
The same file can feed both apps once the R-side path is shared.

This is the library side: it imports no shiny. The language is a plain
attribute. The reactive layer (a `reactive.Value` notification channel and
per-session translators) lives in the app-layer `sespy.ui_i18n`, which
plugs into the process-wide default below through `set_resolver`.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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
    """Stateful translator with a plain `_lang` attribute.

    `_lang` is the source of truth — it always reflects the current language
    synchronously, so unit tests and non-reactive code work without a Shiny
    session. The app's `sespy.ui_i18n.Translator` subclass adds the reactive
    `language` channel on top.
    """

    translations: dict[str, dict[str, str]]
    languages: tuple[str, ...] = SUPPORTED_LANGUAGES
    fallback: str = DEFAULT_FALLBACK
    _lang: str = field(default=DEFAULT_FALLBACK)

    def t(self, key: str, **fmt: Any) -> str:
        """Look up a translation key. Falls back to the fallback language,
        then to the key itself if missing entirely. Supports `str.format`-
        style keyword interpolation for templates like `"Found {n} loops"`.
        """
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
        """Switch language; unsupported codes are ignored."""
        if lang not in self.languages:
            return
        self._lang = lang


# --------------------------------------------------------------------------
# Module-level singleton: library code may `from sespy.i18n import t`; app/UI
# code imports it from `sespy.ui_i18n` instead. Either way it can call
# `t("key")` without explicitly receiving the Translator instance.
# The app calls `set_default(T)` after creating its Translator.
#
# One injection point: a resolver. When set, `get_default()` returns
# `_resolver(_default_translator)` instead of the process default. The app
# layer (`sespy.ui_i18n`) installs one on import that returns the current
# Shiny session's translator, which keeps each user's language isolated.
# `_default_translator` keeps its name: MosaicSES writes it directly.
# --------------------------------------------------------------------------

Resolver = Callable[[Translator | None], Translator | None]

_default_translator: Translator | None = None
_resolver: Resolver | None = None


def set_default(translator: Translator) -> None:
    global _default_translator
    _default_translator = translator


def set_resolver(fn: Resolver | None) -> None:
    """Install (or, with None, remove) the hook `get_default()` consults."""
    global _resolver
    _resolver = fn


def get_default() -> Translator | None:
    if _resolver is not None:
        return _resolver(_default_translator)
    return _default_translator


def t(key: str, **fmt) -> str:
    """Translate via the default translator. Returns the key itself if no
    default has been registered yet (e.g. during early imports)."""
    default = get_default()
    if default is None:
        return key
    return default.t(key, **fmt)


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
