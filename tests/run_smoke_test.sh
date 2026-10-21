#!/usr/bin/env bash
# Runs a test script (default: tests/smoke_test.py) against a THROWAWAY copy
# of the database, so the live placement_db is never modified:
#   1. creates placement_smoke, loads db/schema.sql, runs db/seed.py into it
#   2. starts a second backend on port 5001 pointed at placement_smoke
#   3. runs the test script (any extra arguments are passed to it)
#   4. stops that backend and drops placement_smoke
#
# Usage:  bash tests/run_smoke_test.sh                              # smoke test
#         bash tests/run_smoke_test.sh tests/api_contract_check.py  # API doc check
#
# Needs: Postgres running (docker compose up -d db), the ML service on :6000,
# and the .venv-db / .venv-backend virtualenvs from the README.
# Works in Git Bash (Windows), macOS and Linux.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SMOKE_DB=placement_smoke
SMOKE_URL="postgresql://placement_admin:placement_dev_password@localhost:5432/${SMOKE_DB}"
PORT=5001

venv_python() {  # Windows venvs keep python in Scripts/, macOS/Linux in bin/
  if [ -x "$ROOT/$1/Scripts/python" ] || [ -f "$ROOT/$1/Scripts/python.exe" ]; then
    echo "$ROOT/$1/Scripts/python"
  else
    echo "$ROOT/$1/bin/python"
  fi
}
DB_PY="$(venv_python .venv-db)"
BACKEND_PY="$(venv_python .venv-backend)"
psql_admin() { docker exec -i placement_db psql -U placement_admin -v ON_ERROR_STOP=1 "$@"; }

backend_pid=""
cleanup() {
  [ -n "$backend_pid" ] && kill "$backend_pid" 2>/dev/null || true
  psql_admin -d postgres -qc "DROP DATABASE IF EXISTS ${SMOKE_DB};" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "== Building ${SMOKE_DB} (schema + seed) =="
psql_admin -d postgres -qc "DROP DATABASE IF EXISTS ${SMOKE_DB};" -c "CREATE DATABASE ${SMOKE_DB};"
psql_admin -q -d "${SMOKE_DB}" < "$ROOT/db/schema.sql"
DATABASE_URL="$SMOKE_URL" "$DB_PY" "$ROOT/db/seed.py" | tail -2

echo "== Starting backend on :${PORT} against ${SMOKE_DB} =="
cd "$ROOT/backend"
DATABASE_URL="$SMOKE_URL" FLASK_DEBUG=0 "$BACKEND_PY" -m flask --app "app:create_app" run --port "$PORT" \
  > "${TMPDIR:-/tmp}/smoke-backend.log" 2>&1 &
backend_pid=$!
for _ in $(seq 1 30); do
  curl -s -o /dev/null "http://127.0.0.1:${PORT}/api/health" && break
  sleep 1
done

TEST_SCRIPT="${1:-tests/smoke_test.py}"
[ $# -gt 0 ] && shift
case "$TEST_SCRIPT" in
  /*|[A-Za-z]:*) ;;                       # already absolute
  *) TEST_SCRIPT="$ROOT/$TEST_SCRIPT" ;;  # relative to the repo root
esac
echo "== Running $(basename "$TEST_SCRIPT") =="
PYTHONIOENCODING=utf-8 API_URL="http://127.0.0.1:${PORT}/api" DATABASE_URL="$SMOKE_URL" \
  "$BACKEND_PY" "$TEST_SCRIPT" "$@"
