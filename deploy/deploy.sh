#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Deploy SESPy to a Shiny Server app directory via scp.
#
# Ships ONLY the runtime files — app.py, sespy/, data/, www/, environment.yml,
# pyproject.toml, README/CHANGELOG, docs/MANUAL.md + docs/screenshots/ — to $APP_DIR on $SERVER, excluding caches/tests/docs/build,
# then touches restart.txt so Shiny Server reloads the app on the next request.
#
# Before uploading, a live reference-data pre-flight (K1 spec 4.8) reads the
# server's $APP_DIR/server_settings.env, fetches the live R data files it
# points at into the stage and runs tests/parity/check_live.py on them. A
# structural problem aborts the deploy before anything on the server changes.
# The sespy/ package is uploaded as sespy.incoming and swapped in with two
# renames, so a worker never sees a half-copied package (K1 spec 4.10); between
# the renames sespy/ is briefly absent. A rerun recovers an interrupted swap in
# step 3, after the step-2 pre-flight (skip it with SESPY_SKIP_LIVE_CHECK if it
# is what blocks the rerun).
#
# Prerequisites:
#   * passwordless (key-based) SSH to $SERVER for the deploy user
#   * $APP_DIR writable by that user (here: razinka & shiny both have write)
#   * the server already has a Python env with the SESPy deps and shiny-server
#     configured to run this app's app.py (this script ships code, not the env;
#     rebuild the env from the shipped environment.yml if it changed)
#
# Config: set DEPLOY_SERVER and DEPLOY_DIR in a gitignored deploy/config.env
# (copy deploy/config.env.example), or pass them as env vars. The real host/path
# are intentionally NOT hard-coded here so this script is safe in a public repo.
# NOTE: deploy/config.env is sourced AFTER the environment, so its values win
# over env vars of the same name.
#
# Optional settings (config.env or env):
#   DEPLOY_MOSAIC_DIR  MosaicSES app dir on the same server; its restart.txt is
#                      touched too, so MosaicSES reloads the swapped sespy/.
#   DEPLOY_REPO_ROOT   deploy this checkout instead of the script's own repo
#                      (rollback: deploy a worktree of an old tag with the
#                      CURRENT script). Use an ABSOLUTE path: a relative one
#                      resolves against the caller's current directory, not
#                      the repo. Pass it per run; never leave it set in
#                      config.env, or every normal deploy ships that tree.
#   DEPLOY_SUDO_TEST   1 = check live-file readability with `sudo -n -u shiny`
#                      (a denied sudo can raise auth alerts; default is stat).
#   SESPY_PY           python command for check_live.py
#                      (default: micromamba run -n shiny python).
#
# Environment only (read before config.env is sourced; setting it there does
# nothing):
#   SESPY_SKIP_LIVE_CHECK="<reason>"  skip the live pre-flight entirely. The
#                      reason must be non-empty: set-but-empty counts as unset
#                      and the pre-flight runs.
#
# Usage (run from anywhere; the script resolves the repo root):
#   deploy/deploy.sh               # normal deploy, gated by check_live.py
#   deploy/deploy.sh --rollback    # never gated: check_live.py --warn-only
#
# Rollback to an older tag (the old tag's script has no atomic swap):
#   git worktree add /abs/path/sespy-rollback v1.15.1
#   DEPLOY_REPO_ROOT=/abs/path/sespy-rollback deploy/deploy.sh --rollback
# ---------------------------------------------------------------------------

# --- settings-file parse rule ------------------------------------------------
# Mirrors sespy/r_kb.py::parse_settings_text + override_dir_from (with no env
# override) exactly; tests/test_deploy_script.py checks both over one case table.
DEFAULT_R_DATA_DIR="/srv/shiny-server/marinesabres/data"

# stdin: the settings file text. Prints the raw value of the LAST line that
# starts with "SESPY_R_DATA_DIR=" (no leading whitespace), with surrounding
# whitespace stripped; returns 1 when no line matches. Never sources the file.
# Python's str.splitlines() also breaks lines on CR, VT, FF and FS/GS/RS, and
# the app reads the file as utf-8-sig (a leading BOM is dropped).
settings_raw_value() {
  local LC_ALL=C line value="" found=1 first=1
  while IFS= read -r line || [ -n "$line" ]; do
    if [ "$first" = 1 ]; then
      line="${line#$'\xef\xbb\xbf'}"
      first=0
    fi
    case "$line" in
      SESPY_R_DATA_DIR=*) value="${line#SESPY_R_DATA_DIR=}"; found=0 ;;
    esac
  done < <(tr '\r\013\014\034\035\036' '\n\n\n\n\n\n')
  [ "$found" -eq 0 ] || return 1
  # Python's str.strip() whitespace, ASCII part: space, TAB, LF, VT, FF, CR and
  # FS/GS/RS/US (0x1c-0x1f; the first three already split lines above).
  # Known difference: non-ASCII whitespace that Python also strips or splits on
  # (U+0085, U+00A0, U+1680, U+2000-U+200A, U+2028, U+2029, U+202F, U+205F,
  # U+3000) is kept here as bytes. Such a value fails DIR validation, so the
  # deploy fails closed (missing.txt) rather than checking a different dir.
  local ws=$' \t\n\v\f\r\034\035\036\037'
  while [ -n "$value" ] && [[ "$ws" == *"${value:0:1}"* ]]; do value="${value:1}"; done
  while [ -n "$value" ] && [[ "$ws" == *"${value: -1}"* ]]; do value="${value:0:${#value}-1}"; done
  printf '%s' "$value"
}

# $1 = "absent" (no settings file) or "present" (text on stdin).
# Prints the override directory, or nothing when the override is off.
resolve_override_dir() {
  local raw
  if [ "$1" = absent ]; then
    printf '%s' "$DEFAULT_R_DATA_DIR"
    return 0
  fi
  if ! raw="$(settings_raw_value)"; then
    printf '%s' "$DEFAULT_R_DATA_DIR"
    return 0
  fi
  case "${raw,,}" in
    "" | off) return 0 ;;
  esac
  printf '%s' "$raw"
}

# Same rule as check_live.py: absolute, and only [A-Za-z0-9._/@+-] (scp may
# hand the remote path to a shell, so never fetch an odd path).
is_safe_remote_dir() {
  local LC_ALL=C re='^/[A-Za-z0-9._/@+-]+$'
  [[ "$1" =~ $re ]]
}

# Sourced (by the parity test) for the functions above only.
if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
  return 0
fi
# -----------------------------------------------------------------------------

set -euo pipefail

ROLLBACK=0
for arg in "$@"; do
  case "$arg" in
    --rollback) ROLLBACK=1 ;;
    *) echo "usage: deploy/deploy.sh [--rollback]" >&2; exit 2 ;;
  esac
done
SKIP_LIVE=0
if [ -n "${SESPY_SKIP_LIVE_CHECK:-}" ]; then
  SKIP_LIVE=1
  echo "==> skipping live check: ${SESPY_SKIP_LIVE_CHECK}"
elif [ -n "${SESPY_SKIP_LIVE_CHECK+x}" ]; then
  echo "    ! SESPY_SKIP_LIVE_CHECK is set but empty; a reason is required, so the live check runs" >&2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
[ -f "$SCRIPT_DIR/config.env" ] && source "$SCRIPT_DIR/config.env"

SERVER="${DEPLOY_SERVER:?set DEPLOY_SERVER (in deploy/config.env or the env), e.g. user@host}"
APP_DIR="${DEPLOY_DIR:?set DEPLOY_DIR (in deploy/config.env or the env), e.g. /srv/shiny-server/SESPy}"

REPO_ROOT="$(cd "${DEPLOY_REPO_ROOT:-$SCRIPT_DIR/..}" && pwd)"
cd "$REPO_ROOT"

# Native Windows python (micromamba.exe) does not understand MSYS /tmp/... paths.
native_path() {
  if command -v cygpath >/dev/null 2>&1; then cygpath -w "$1"; else printf '%s' "$1"; fi
}
CHECK_LIVE="$REPO_ROOT/tests/parity/check_live.py"
run_check_live() {
  # SESPY_PY is word-split on purpose (default is a multi-word command).
  # shellcheck disable=SC2086
  PYTHONPATH="$(native_path "$REPO_ROOT")" ${SESPY_PY:-micromamba run -n shiny python} \
    "$(native_path "$CHECK_LIVE")" "$@"
}

# Runtime files to ship. Anything not listed (tests/, docs/, build/, dist/,
# .git/, sespy.egg-info/, LITERATURE/, .superpowers/) is intentionally excluded.
# README.md + CHANGELOG.md are runtime docs: the About modal renders them via
# read_project_doc(), so they must ship with the app (not just dev metadata).
RUNTIME=(app.py sespy data www environment.yml pyproject.toml README.md CHANGELOG.md)

VERSION="$(git describe --tags --always 2>/dev/null || echo unknown)"
echo "==> Deploying SESPy ${VERSION} to ${SERVER}:${APP_DIR}$([ "$ROLLBACK" = 1 ] && echo ' (rollback)')"

# 1. Stage a clean copy locally so no __pycache__/*.pyc (stale bytecode) ships.
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
for item in "${RUNTIME[@]}"; do
  if [ -e "$item" ]; then
    cp -R "$item" "$STAGE/"
  else
    echo "    ! missing '$item' — skipping" >&2
  fi
done
# The About modal's Manual tab renders docs/MANUAL.md and serves
# docs/screenshots/ as static assets; ship exactly those two, not docs/.
mkdir -p "$STAGE/docs"
cp docs/MANUAL.md "$STAGE/docs/"
cp -R docs/screenshots "$STAGE/docs/"
find "$STAGE" -name __pycache__ -type d -prune -exec rm -rf {} +
find "$STAGE" -name '*.pyc' -delete
# Never ship the runtime feedback DB / logs. The server OWNS its own
# sespy/logs/ (feedback.db, surfaced in the Feedback modal); shipping the
# local copy would clobber production feedback with dev/test entries. The
# server's copy is moved into the incoming package before the swap (step 4).
rm -rf "$STAGE/sespy/logs"

# 2. Live reference-data pre-flight (K1 spec 4.8). Nothing on the server has
#    changed yet, so an abort here leaves production untouched.
SETTINGS="$APP_DIR/server_settings.env"
if [ "$SKIP_LIVE" = 1 ]; then
  :
elif [ ! -f "$CHECK_LIVE" ]; then
  echo "==> tests/parity/check_live.py is absent from this checkout (pre-K1 tag); skipping the live fetch and check"
else
  LIVE="$STAGE/.live"
  CHECK_ARGS=(--stage "$(native_path "$STAGE")")
  [ "$ROLLBACK" = 1 ] && CHECK_ARGS+=(--warn-only)

  # 2a. Read the settings file without sourcing it: exit 3 = absent,
  #     4 = present but unreadable (same split as check_live.py --fetch).
  settings_rc=0
  settings_text="$(ssh "$SERVER" "if [ -e '$SETTINGS' ]; then cat '$SETTINGS' || exit 4; else exit 3; fi")" \
    || settings_rc=$?
  LIVE_DIR=""
  case "$settings_rc" in
    0) LIVE_DIR="$(printf '%s' "$settings_text" | resolve_override_dir present)" ;;
    3) LIVE_DIR="$(resolve_override_dir absent)" ;;
    4)
      if [ "$ROLLBACK" = 1 ]; then
        echo "    ! WARNING: $SETTINGS exists but cannot be read; live checks skipped (--rollback)" >&2
      else
        echo "!! $SETTINGS exists but cannot be read; the live override setting is unknown. Aborting before upload." >&2
        exit 2
      fi
      ;;
    *)
      if [ "$ROLLBACK" = 1 ]; then
        echo "    ! WARNING: could not read $SETTINGS over ssh (exit $settings_rc); live checks skipped (--rollback)" >&2
      else
        echo "!! could not read $SETTINGS over ssh (exit $settings_rc). Aborting before upload." >&2
        exit 2
      fi
      ;;
  esac

  if [ "$settings_rc" -ne 0 ] && [ "$settings_rc" -ne 3 ]; then
    :  # unreadable settings under --rollback: shipped-copy check only
  elif [ -z "$LIVE_DIR" ]; then
    echo "==> live override is off on the server; fetching nothing"
  else
    # 2b. Fetch each override file (names from check_live, the one allow-list)
    #     plus the optional VERSION_INFO.json one level up.
    if ! names_out="$(run_check_live --print-override-names)"; then
      if [ "$ROLLBACK" = 1 ]; then
        echo "    ! WARNING: check_live.py --print-override-names failed; live checks skipped (--rollback)" >&2
        names_out=""
      else
        echo "!! check_live.py --print-override-names failed. Aborting before upload." >&2
        exit 2
      fi
    fi
    NAMES=()
    while IFS= read -r n; do
      [ -n "$n" ] && NAMES+=("$n")
    done < <(printf '%s\n' "$names_out" | tr -d '\r')
    if [ "${#NAMES[@]}" -eq 0 ]; then
      if [ "$ROLLBACK" = 1 ]; then
        echo "    ! WARNING: check_live.py --print-override-names gave no names; live checks skipped (--rollback)" >&2
      else
        echo "!! check_live.py --print-override-names gave no names, so nothing could be checked. Aborting before upload." >&2
        exit 2
      fi
    fi

    if [ "${#NAMES[@]}" -gt 0 ]; then
      mkdir -p "$LIVE"
      while [ "${#LIVE_DIR}" -gt 1 ] && [ "${LIVE_DIR%/}" != "$LIVE_DIR" ]; do
        LIVE_DIR="${LIVE_DIR%/}"
      done
      if ! is_safe_remote_dir "$LIVE_DIR"; then
        echo "    ! SESPY_R_DATA_DIR '$LIVE_DIR' is not an absolute path of [A-Za-z0-9._/@+-]; not fetching" >&2
        printf '%s\n' "${NAMES[@]}" > "$LIVE/missing.txt"
        : > "$LIVE/perms.txt"
      else
        echo "==> fetching live reference data from ${SERVER}:${LIVE_DIR}"
        for n in "${NAMES[@]}"; do
          scp -q "$SERVER:$LIVE_DIR/$n" "$LIVE/" || echo "$n" >> "$LIVE/missing.txt"
        done
        scp -q "$SERVER:$(dirname "$LIVE_DIR")/VERSION_INFO.json" "$LIVE/" 2>/dev/null || true

        # 2c. Can user shiny read each file and traverse every parent dir?
        STAT_PATHS=()
        add_path() {
          local p
          for p in "${STAT_PATHS[@]}"; do [ "$p" = "$1" ] && return 0; done
          STAT_PATHS+=("$1")
        }
        FILES=()
        for n in "${NAMES[@]}"; do
          f="$LIVE_DIR/$n"
          FILES+=("'$f'")
          add_path "$f"
          d="$(dirname "$f")"
          while [ "$d" != "/" ]; do
            add_path "$d"
            d="$(dirname "$d")"
          done
          add_path "/"
        done
        quoted_paths="$(printf "'%s' " "${STAT_PATHS[@]}")"
        stat_cmd="stat -c 'stat %a %U %G %n' $quoted_paths"
        if [ "${DEPLOY_SUDO_TEST:-}" = 1 ]; then
          remote="if sudo -n -u shiny true 2>/dev/null; then
            for f in ${FILES[*]}; do
              if sudo -n -u shiny test -r \"\$f\"; then echo \"sudo-test \$f ok\"; else echo \"sudo-test \$f denied\"; fi
            done
          else $stat_cmd; fi"
        else
          remote="$stat_cmd"
        fi
        ssh "$SERVER" "$remote" > "$LIVE/perms.txt" 2>/dev/null || true
      fi
      CHECK_ARGS+=(--live "$(native_path "$LIVE")" --perms "$(native_path "$LIVE/perms.txt")")
    fi
  fi

  # 2d. Check. Structural problems abort (exit 2); --rollback never gates.
  echo "==> running check_live.py"
  check_rc=0
  run_check_live "${CHECK_ARGS[@]}" || check_rc=$?
  if [ "$check_rc" -ne 0 ]; then
    if [ "$ROLLBACK" = 1 ]; then
      echo "    ! WARNING: check_live.py exited $check_rc; continuing (--rollback)" >&2
    else
      echo "!! check_live.py exited $check_rc. Aborting before upload (set SESPY_SKIP_LIVE_CHECK=\"<reason>\" to override)." >&2
      exit "$check_rc"
    fi
  fi
fi
rm -rf "$STAGE/.live"

# 3. Recovery prologue: repair what an interrupted earlier deploy left behind,
#    then clear any half-uploaded incoming package.
#    - sespy/ gone but sespy.old/ there: the swap died between its two mv's.
#    - sespy.old/logs or sespy.incoming/logs: the swap died after moving the
#      logs. A sespy.old or sespy.incoming that still holds logs/ is NEVER
#      deleted with them: the logs go back to sespy/logs, or, when a worker
#      has already recreated sespy/logs (feedback_store mkdirs it on every
#      call), aside to $APP_DIR/logs.rescued-<timestamp> with a warning.
#    - .deploy-keep/logs: the pre-K1 script died between stash and restore
#      (left in place if sespy/logs already exists).
# Remote helper, defined in every ssh that may delete sespy.old/sespy.incoming.
REMOTE_RESCUE='rescue_logs() {
  [ -e "$1/logs" ] || return 0
  if [ ! -e sespy/logs ]; then
    mkdir -p sespy && mv -T "$1/logs" sespy/logs
  else
    r="logs.rescued-$(date +%Y%m%d%H%M%S)"
    [ -e "$r" ] && r="$r-$1"
    mv -T "$1/logs" "$r" &&
      echo "!! WARNING: $1/logs was stranded and sespy/logs already exists; kept it as $PWD/$r - merge it by hand" >&2
  fi
}'
ssh "$SERVER" "$REMOTE_RESCUE
  mkdir -p '$APP_DIR' &&
  cd '$APP_DIR' &&
  if [ ! -e sespy ] && [ -d sespy.old ]; then mv -T sespy.old sespy; fi &&
  rescue_logs sespy.old &&
  rescue_logs sespy.incoming &&
  if [ ! -e sespy/logs ] && [ -d .deploy-keep/logs ]; then
    mkdir -p sespy && mv -T .deploy-keep/logs sespy/logs;
  fi &&
  if [ -d .deploy-keep ] && [ ! -e .deploy-keep/logs ]; then rm -rf .deploy-keep; fi &&
  rm -rf sespy.old sespy.incoming
"

# 4. Upload the package beside the live one, then swap. sespy/ goes first: a
#    new app.py against the old sespy/ would crash on new imports, while the
#    old app.py runs fine against the new sespy/ (new kwargs are optional).
#    The server-owned sespy/logs/ (feedback.db) moves into the incoming
#    package, so it is never overwritten; the whole sequence is one && chain.
#    mv -T fails (instead of nesting the package) if a worker recreated
#    sespy/ in the instant between the two renames.
scp -rq "$STAGE/sespy" "$SERVER:$APP_DIR/sespy.incoming"
ssh "$SERVER" "$REMOTE_RESCUE
  cd '$APP_DIR' &&
  if [ -d sespy/logs ]; then mv -T sespy/logs sespy.incoming/logs; fi &&
  if [ -e sespy ]; then mv -T sespy sespy.old; fi &&
  mv -T sespy.incoming sespy &&
  rescue_logs sespy.old &&
  rm -rf sespy.old &&
  rm -rf '$APP_DIR/__pycache__' '$APP_DIR/docs/screenshots'
"

# 5. The other runtime items (stale top-level bytecode and screenshots were
#    cleared above, since scp overwrites but never deletes).
OTHERS=()
for p in "$STAGE"/*; do
  [ "$(basename "$p")" = sespy ] || OTHERS+=("$p")
done
if [ "${#OTHERS[@]}" -gt 0 ]; then
  scp -rq "${OTHERS[@]}" "$SERVER:$APP_DIR/"
fi

# 6. Create the server settings file if absent (an existing one keeps its
#    content), chmod 0644 either way so user shiny can read what the
#    pre-flight read; then reload: Shiny Server restarts an app's workers when
#    restart.txt changes. A settings failure only warns: it must not skip the
#    reload of the code that is already swapped in.
ssh "$SERVER" "
  if [ ! -e '$SETTINGS' ]; then
    ( umask 022 && printf 'SESPY_R_DATA_DIR=%s\n' '$DEFAULT_R_DATA_DIR' > '$SETTINGS' ) ||
      echo '!! WARNING: could not create $SETTINGS' >&2
  fi
  if [ -e '$SETTINGS' ]; then
    chmod 0644 '$SETTINGS' || echo '!! WARNING: could not chmod 0644 $SETTINGS' >&2
  fi
  touch '$APP_DIR/restart.txt'
"
echo "==> Done. ${APP_DIR} updated to ${VERSION}; Shiny Server reloads on next request."

# 7. MosaicSES symlinks this sespy/; restart it too. The SESPy deploy has
#    already succeeded, so a failure here only warns.
if [ -n "${DEPLOY_MOSAIC_DIR:-}" ]; then
  if ssh "$SERVER" "touch '$DEPLOY_MOSAIC_DIR/restart.txt'"; then
    echo "==> MosaicSES at ${DEPLOY_MOSAIC_DIR} restarted; run its deploy/verify_live.py."
  else
    echo "!! WARNING: could not touch ${DEPLOY_MOSAIC_DIR}/restart.txt; restart MosaicSES by hand." >&2
  fi
fi
exit 0
