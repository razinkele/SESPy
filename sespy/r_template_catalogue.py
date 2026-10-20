"""Build SESPy's MarineSABRES template gallery from R's curated templates (P2).

`sync()` reads the 7 R `*_SES_Template.json` files (from an R git checkout
with `git show`, or from the pinned fixtures under tests/parity/), converts
them with P1a's mapper, and produces the shipped projects and
`catalogue.json` under sespy/templates/marinesabres/. When it reads from R it
also produces the fixtures, the pin (tests/parity/r_sync.json) and the
generated block of docs/parity/R_SYNC.md. Everything is built in memory
first: any failure writes nothing.

Every SESPy data file is read and written under `repo_root`, so tests point
it at a tmp_path copy; code and constants (the mapper, regional_seas.json)
come from the imported package. Shiny-free, no clock, no logging: the caller
prints `SyncResult.lines`.

R reference: functions/template_loader.R:359-371 (v1.31.0) for the category
rule (ported in `determine_category`, guarded by
tests/parity/test_r_category_parity.py).
"""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .r_sync import sha256_norm, sha256_text_norm
from .r_template_mapper import ConversionReport, convert_r_template
from .regional_seas import get_regional_seas

STEMS = ("Aquaculture", "Caribbean", "ClimateChange", "Fisheries",
         "OffshoreWind", "Pollution", "Tourism")
TEMPLATE_FILES = tuple(f"{s}_SES_Template.json" for s in STEMS)
SUFFIX = " (MarineSABRES)"
OUT_DIR = "sespy/templates/marinesabres"
CATALOGUE_PATH = f"{OUT_DIR}/catalogue.json"
PIN_PATH = "tests/parity/r_sync.json"
MD_PATH = "docs/parity/R_SYNC.md"
BEGIN, END = "<!-- r-sync:begin -->", "<!-- r-sync:end -->"
TAG_RE = re.compile(r"^v\d+\.\d+\.\d+$")

# R app path -> fixture path under repo_root (spec §3.2, §3.3 step 6). A
# template added or removed in R is a deliberate change to this list.
INPUTS: dict[str, str] = {
    **{f"data/{f}": f"tests/parity/r_templates/{f}" for f in TEMPLATE_FILES},
    "functions/dapsiwrm_connection_rules.R": "tests/parity/r_rules/dapsiwrm_connection_rules.R",
    "functions/template_loader.R": "tests/parity/r_source/template_loader.R",
}

# Port of R's .determine_template_category, in R's order (first match wins).
CATEGORY_NULL = "General"          # main_issues is NULL
CATEGORY_MULTI = "Multi-Stressor"  # more than one issue
CATEGORY_FALLBACK = "General"      # no rule matched
CATEGORY_RULES: tuple[tuple[str, str], ...] = (
    ("fish", "Extraction"),
    ("touris", "Recreation"),
    ("aqua|farm", "Production"),
    ("pollut|contamin", "Pollution"),
    ("climat|warm|sea level", "Climate"),
    ("wind|energy", "Energy"),
)
DEFAULT_COMPLEXITY = "simple"      # R's stated default

CATALOGUE_KEYS = ("file", "name", "description", "category", "complexity",
                  "version", "regional_sea_label", "source", "usage_notes",
                  "element_count", "connection_count")
ALWAYS_NON_EMPTY = ("file", "name", "description", "category", "complexity",
                    "version")
_WARNING_SORT_FIELDS = ("template", "kind", "from", "to", "text")


@dataclass(frozen=True)
class SyncResult:
    code: int
    lines: list[str] = field(default_factory=list)


# ---- catalogue fields (spec §4) -------------------------------------------

def determine_category(raw: dict) -> str:
    """R `.determine_template_category`: NULL main_issues -> General; more
    than one issue -> Multi-Stressor; else the first matching rule
    (unanchored, case-insensitive); else General. A scalar counts as one
    issue; an empty list falls through to General."""
    rc = raw.get("regional_context")
    issues = rc.get("main_issues") if isinstance(rc, dict) else None
    if issues is None:
        return CATEGORY_NULL
    if not isinstance(issues, list):
        issues = [issues]
    if len(issues) > 1:
        return CATEGORY_MULTI
    for pattern, category in CATEGORY_RULES:
        if any(re.search(pattern, str(i), re.IGNORECASE) for i in issues):
            return category
    return CATEGORY_FALLBACK


def regional_sea_label(slug: str, raw: dict) -> str:
    """Display label for a card: the regional-seas name for a known slug, an
    unknown slug title-cased, else R's `regional_context.region` text."""
    if slug:
        seas = get_regional_seas()
        if slug in seas:
            return seas[slug]["name"]
        return slug.replace("_", " ").title()
    rc = raw.get("regional_context")
    region = rc.get("region") if isinstance(rc, dict) else None
    return region if isinstance(region, str) and region.strip() else ""


def complexity_of(raw: dict) -> str:
    """R `complexity`; absent, null or "" -> "simple"."""
    value = raw.get("complexity")
    return DEFAULT_COMPLEXITY if value is None or value == "" else str(value)


def _text(value: Any) -> str:
    return "" if value is None else str(value)


# ---- warnings ---------------------------------------------------------------

def warning_entries(stem: str, report: ConversionReport) -> list[dict[str, str]]:
    """One entry per off-rule link / type mismatch, scoped to the template
    (ids like D001 repeat across templates)."""
    out = [{"template": stem, "kind": "off_rule_link", "from": a, "to": b}
           for a, b in report.off_rule_links]
    out += [{"template": stem, "kind": "type_mismatch", "text": m}
            for m in report.type_mismatches]
    return out


def warning_sort_key(entry: dict) -> tuple[str, ...]:
    return tuple(str(entry.get(k, "")) for k in _WARNING_SORT_FIELDS)


def format_warning(entry: dict) -> str:
    if entry.get("kind") == "off_rule_link":
        return f"{entry['template']}: off_rule_link {entry['from']} -> {entry['to']}"
    return f"{entry.get('template')}: {entry.get('kind')} {entry.get('text', '')}"


# ---- build (pure) -----------------------------------------------------------

def build_outputs(raw_by_file: dict[str, dict], *, r_tag: str, r_commit: str
                  ) -> tuple[dict[str, bytes], list[dict[str, str]], list[str]]:
    """Convert the 7 templates and build the catalogue, in memory.

    Returns (outputs {repo-relative path: bytes}, warning entries, errors).
    A mapper ValueError propagates; errors lists empty always-non-empty
    catalogue fields."""
    outputs: dict[str, bytes] = {}
    warnings: list[dict[str, str]] = []
    entries: list[dict[str, Any]] = []
    for fname in TEMPLATE_FILES:
        raw = raw_by_file[fname]
        stem = fname[: -len(".json")]
        project, report = convert_r_template(raw, key=stem)
        warnings += warning_entries(stem, report)
        md = project.metadata
        md.name = md.name + SUFFIX      # the mapper already applied R's fallbacks
        # to_json, never project_to_bytes/save_project_atomic: those stamp
        # modified_at with the clock. LF only; write_bytes, never write_text.
        outputs[f"{OUT_DIR}/{fname}"] = (project.to_json() + "\n").encode("utf-8")
        meta = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
        entries.append({
            "file": fname,
            "name": md.name,
            "description": md.description,
            "category": determine_category(raw),
            "complexity": complexity_of(raw),
            "version": md.r_template_version,
            "regional_sea_label": regional_sea_label(md.regional_sea, raw),
            "source": _text(meta.get("source")),
            "usage_notes": _text(raw.get("usage_notes")),
            "element_count": project.isa_data.element_count(),
            "connection_count": project.isa_data.connection_count(),
        })
    errors: list[str] = []
    for e in entries:
        errors += [f"{e['file']}: empty {k}" for k in ALWAYS_NON_EMPTY if not e[k]]
        errors += [f"{e['file']}: {k} is 0" for k in ("element_count", "connection_count")
                   if e[k] <= 0]
    entries.sort(key=lambda e: e["name"].casefold())
    catalogue = {"r_tag": r_tag, "r_commit": r_commit, "templates": entries}
    outputs[CATALOGUE_PATH] = (
        json.dumps(catalogue, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    return outputs, warnings, errors


def render_block(r_tag: str, r_commit: str, files: dict[str, str],
                 accepted: list[dict]) -> str:
    """The generated R_SYNC.md block (without the surrounding newlines)."""
    rows = "\n".join(f"| `{p}` | `{h}` |" for p, h in sorted(files.items()))
    if accepted:
        tail = "**Accepted sync warnings:**\n" + "\n".join(
            f"- {format_warning(w)}" for w in accepted)
    else:
        tail = "**Accepted sync warnings:** none."
    return (f"- **R release:** MarineSABRES_SES_Shiny **{r_tag}**, commit `{r_commit}`.\n"
            f"\n| File | Hash |\n|---|---|\n{rows}\n\n{tail}")


def splice_block(md: str, block: str) -> str:
    """Replace everything between the markers with "\\n" + block + "\\n".
    Raises ValueError unless there is exactly one BEGIN before one END."""
    md = md.replace("\r\n", "\n")
    if md.count(BEGIN) != 1 or md.count(END) != 1 or md.index(BEGIN) > md.index(END):
        raise ValueError(f"{MD_PATH}: needs exactly one {BEGIN} before one {END}")
    start = md.index(BEGIN) + len(BEGIN)
    return md[:start] + "\n" + block + "\n" + md[md.index(END):]


# ---- I/O ----------------------------------------------------------------------

def _git(r_root: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-c", "core.longpaths=true", "-C", str(r_root), *args],
        check=True, capture_output=True).stdout


def _hash(rel: str, data: bytes) -> str:
    text = data.decode("utf-8-sig")
    return sha256_norm(json.loads(text)) if rel.endswith(".json") else sha256_text_norm(text)


def _same(path: Path, data: bytes) -> bool:
    """--check comparison: JSON parsed, text with CRLF -> LF."""
    if not path.is_file():
        return False
    disk = path.read_bytes().decode("utf-8-sig")
    new = data.decode("utf-8-sig")
    if path.suffix == ".json":
        try:
            return json.loads(disk) == json.loads(new)
        except ValueError:
            return False
    return disk.replace("\r\n", "\n") == new.replace("\r\n", "\n")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_bytes().decode("utf-8-sig"))


def sync(*, repo_root: Path, r_root: Path | None = None, rev: str | None = None,
         from_fixtures: bool = False, check: bool = False,
         accept_warnings: bool = False) -> SyncResult:
    """Spec §3.3. Exit code 0 = written (or, with check, no drift)."""
    repo_root = Path(repo_root)
    if from_fixtures and accept_warnings:
        return SyncResult(1, ["--accept-warnings needs --r-root: fixture mode never "
                              "writes tests/parity/r_sync.json, so the acceptance would be lost"])
    if from_fixtures and (r_root is not None or rev is not None):
        return SyncResult(1, ["--from-fixtures takes neither --r-root nor --rev"])
    if not from_fixtures and r_root is None:
        return SyncResult(1, ["--r-root is required unless --from-fixtures"])
    try:
        pin_old = _read_json(repo_root / PIN_PATH)
    except (OSError, ValueError) as e:
        return SyncResult(1, [f"cannot read {PIN_PATH}: {e}"])
    if not (isinstance(pin_old, dict)
            and all(isinstance(pin_old.get(k), str) and pin_old[k] for k in ("r_tag", "r_commit"))
            and isinstance(pin_old.get("files", {}), dict)
            and isinstance(pin_old.get("accepted_warnings", []), list)
            and all(isinstance(w, dict) for w in pin_old.get("accepted_warnings", []))):
        return SyncResult(1, [f"{PIN_PATH}: needs non-empty string r_tag and r_commit, "
                              "a files object and an accepted_warnings list of objects"])
    accepted_old = list(pin_old.get("accepted_warnings", []))

    raw_bytes: dict[str, bytes] = {}
    if from_fixtures:
        r_tag, r_commit = pin_old["r_tag"], pin_old["r_commit"]
        for r_path, fixture in INPUTS.items():
            if r_path.startswith("data/"):
                try:
                    raw_bytes[r_path] = (repo_root / fixture).read_bytes()
                except OSError as e:
                    return SyncResult(1, [f"cannot read {fixture}: {e}"])
    else:
        r_tag = rev or pin_old["r_tag"]
        if not TAG_RE.fullmatch(r_tag):        # fullmatch: "$" alone accepts a trailing "\n"
            return SyncResult(1, [f"--rev must be a release tag like v1.31.0, got {r_tag!r}"])
        try:
            prefix = _git(r_root, "rev-parse", "--show-prefix").decode().strip()
            r_commit = _git(r_root, "rev-parse", "--short=7", f"{r_tag}^{{commit}}").decode().strip()
        except (subprocess.CalledProcessError, OSError) as e:
            detail = e.stderr.decode(errors="replace").strip() if isinstance(
                e, subprocess.CalledProcessError) else str(e)
            return SyncResult(1, [f"git failed for {r_tag}: {detail}"])
        for r_path in INPUTS:
            try:
                raw_bytes[r_path] = _git(r_root, "show", f"{r_tag}:{prefix}{r_path}")
            except subprocess.CalledProcessError as e:
                return SyncResult(1, [f"git show {r_tag}:{prefix}{r_path} failed: "
                                      f"{e.stderr.decode(errors='replace').strip()}"])

    try:
        raw_by_file = {f: json.loads(raw_bytes[f"data/{f}"].decode("utf-8-sig"))
                       for f in TEMPLATE_FILES}
        outputs, warnings, errors = build_outputs(raw_by_file, r_tag=r_tag, r_commit=r_commit)
    except (ValueError, KeyError, TypeError, AttributeError) as e:
        # JSON or mapper error, or a template that is not the expected shape
        # (e.g. not an object): exit 1, never a traceback.
        return SyncResult(1, [f"conversion failed: {type(e).__name__}: {e}"])

    lines: list[str] = []
    unaccepted = [w for w in warnings if w not in accepted_old]
    for w in warnings:
        state = "unaccepted" if w in unaccepted and not accept_warnings else "accepted"
        lines.append(f"warning ({state}): {format_warning(w)}")
    if unaccepted and not accept_warnings:
        errors.append(f"{len(unaccepted)} unaccepted warning(s); review them, "
                      "then rerun with --accept-warnings")
    if errors:
        return SyncResult(1, lines + errors)

    if not from_fixtures:
        files: dict[str, str] = {}
        for r_path, fixture in INPUTS.items():
            outputs[fixture] = raw_bytes[r_path]            # raw bytes as read
            files[fixture] = _hash(fixture, raw_bytes[r_path])
            old = pin_old.get("files", {}).get(fixture)
            if old != files[fixture]:
                lines.append(f"hash {fixture}: {old or '(none)'} -> {files[fixture]}")
        accepted_new: list[dict] = []
        for w in sorted(warnings, key=warning_sort_key):
            if w not in accepted_new:
                accepted_new.append(w)
        pin_new = {"r_tag": r_tag, "r_commit": r_commit,
                   "files": dict(sorted(files.items())),
                   "accepted_warnings": accepted_new}
        outputs[PIN_PATH] = (json.dumps(pin_new, indent=2, ensure_ascii=False)
                             + "\n").encode("utf-8")
        try:
            md_old = (repo_root / MD_PATH).read_bytes().decode("utf-8-sig")
            md_new = splice_block(md_old, render_block(r_tag, r_commit, files, accepted_new))
        except (OSError, ValueError) as e:
            return SyncResult(1, lines + [str(e)])
        outputs[MD_PATH] = md_new.encode("utf-8")

    if check:
        differing = [p for p, data in outputs.items() if not _same(repo_root / p, data)]
        lines += [f"differs: {p}" for p in differing]
        return SyncResult(1 if differing else 0, lines)
    for p, data in outputs.items():
        dst = repo_root / p
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(data)
        lines.append(f"wrote {p}")
    return SyncResult(0, lines)
