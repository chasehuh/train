#!/usr/bin/env bash
# Build (or refresh) the worker checkpoint: a Railway sandbox with this checkout
# pip-installed, captured as a named checkpoint. The control plane boots every
# job from it (WORKER_TEMPLATE=<name>).
#
# Usage: scripts/checkpoint.sh [-p PROJECT_ID] [-e ENVIRONMENT] [NAME]
# Default NAME is train-<short sha> of HEAD. Requires the railway CLI, logged in.
set -euo pipefail

PROJECT="${RAILWAY_PROJECT_ID:-}"
ENVIRONMENT="${RAILWAY_ENVIRONMENT:-production}"
while getopts "p:e:" opt; do
  case $opt in
    p) PROJECT=$OPTARG ;;
    e) ENVIRONMENT=$OPTARG ;;
    *) exit 2 ;;
  esac
done
shift $((OPTIND - 1))

ROOT=$(cd "$(dirname "$0")/.." && pwd)
NAME="${1:-train-$(git -C "$ROOT" rev-parse --short HEAD)}"
RW=(railway)
[[ -n $PROJECT ]] && RW+=(-p "$PROJECT")
RW+=(-e "$ENVIRONMENT")

quiet() { grep -v "Railway sandboxes are experimental\|newer Railway CLI\|railway upgrade" || true; }

echo "==> creating build sandbox"
ID=$("${RW[@]}" sandbox create --idle-timeout-minutes 10 --json 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
trap '"${RW[@]}" sandbox destroy "$ID" 2>&1 | quiet' EXIT

echo "==> installing checkout into $ID"
tar -C "$ROOT" -czf - --exclude=.git --exclude=.venv --exclude='__pycache__' --exclude='*.egg-info' train korail2 pyproject.toml README.md \
  | "${RW[@]}" sandbox exec --id "$ID" --timeout 600 -- bash -lc \
    'set -e; mkdir -p /app && tar -C /app -xzf - 2>/dev/null; cd /app && pip install -q --disable-pip-version-check --root-user-action=ignore . && python3 -m train --help >/dev/null && echo install-ok' 2>&1 | quiet

echo "==> capturing checkpoint $NAME"
"${RW[@]}" sandbox checkpoint create --id "$ID" "$NAME" 2>&1 | quiet
echo "WORKER_TEMPLATE=$NAME"
