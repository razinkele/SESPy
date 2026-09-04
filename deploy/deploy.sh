#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Deploy SESPy to a Shiny Server app directory via scp.
#
# Ships ONLY the runtime files — app.py, sespy/, data/, www/, environment.yml,
# pyproject.toml, README/CHANGELOG, docs/MANUAL.md + docs/screenshots/ — to $APP_DIR on $SERVER, excluding caches/tests/docs/build,
# then touches restart.txt so Shiny Server reloads the app on the next request.
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
#
# Usage (run from anywhere; the script resolves the repo root):
#   deploy/deploy.sh
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
[ -f "$SCRIPT_DIR/config.env" ] && source "$SCRIPT_DIR/config.env"

SERVER="${DEPLOY_SERVER:?set DEPLOY_SERVER (in deploy/config.env or the env), e.g. user@host}"
APP_DIR="${DEPLOY_DIR:?set DEPLOY_DIR (in deploy/config.env or the env), e.g. /srv/shiny-server/SESPy}"

REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

# Runtime files to ship. Anything not listed (tests/, docs/, build/, dist/,
# .git/, sespy.egg-info/, LITERATURE/, .superpowers/) is intentionally excluded.
# README.md + CHANGELOG.md are runtime docs: the About modal renders them via
# read_project_doc(), so they must ship with the app (not just dev metadata).
RUNTIME=(app.py sespy data www environment.yml pyproject.toml README.md CHANGELOG.md)

VERSION="$(git describe --tags --always 2>/dev/null || echo unknown)"
echo "==> Deploying SESPy ${VERSION} to ${SERVER}:${APP_DIR}"

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
# server's copy is preserved across the package wipe in step 2/4 below.
rm -rf "$STAGE/sespy/logs"

# 2. Ensure the target exists; clear the managed package dir + any stale
#    top-level bytecode so a module deleted upstream does not linger and the
#    new app.py is not shadowed by an old .pyc (scp overwrites but never
#    deletes). Only sespy/ and __pycache__ are removed — the rest of $APP_DIR
#    (incl. .git) is untouched. The server-owned sespy/logs/ (feedback.db) is
#    stashed aside first and restored in step 4 so a deploy never destroys it.
ssh "$SERVER" "
  mkdir -p '$APP_DIR' &&
  if [ -d '$APP_DIR/sespy/logs' ]; then
    rm -rf '$APP_DIR/.deploy-keep' &&
    mkdir -p '$APP_DIR/.deploy-keep' &&
    mv '$APP_DIR/sespy/logs' '$APP_DIR/.deploy-keep/logs';
  fi &&
  rm -rf '$APP_DIR/sespy' '$APP_DIR/__pycache__' '$APP_DIR/docs/screenshots'
"

# 3. Copy the staged runtime tree (scp merges sespy/ into the dir left behind).
scp -rq "$STAGE"/* "$SERVER:$APP_DIR/"

# 4. Restore the preserved feedback DB / logs, then reload: Shiny Server
#    restarts an app's workers when restart.txt changes.
ssh "$SERVER" "
  if [ -d '$APP_DIR/.deploy-keep/logs' ]; then
    rm -rf '$APP_DIR/sespy/logs' &&
    mkdir -p '$APP_DIR/sespy' &&
    mv '$APP_DIR/.deploy-keep/logs' '$APP_DIR/sespy/logs';
  fi &&
  rm -rf '$APP_DIR/.deploy-keep' &&
  touch '$APP_DIR/restart.txt'
"

echo "==> Done. ${APP_DIR} updated to ${VERSION}; Shiny Server reloads on next request."
