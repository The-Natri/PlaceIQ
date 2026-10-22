#!/usr/bin/env bash
# Starts PlaceIQ from this machine's Python virtualenvs and opens
# http://localhost:8080 (the fallback to "docker compose up").
#
# Postgres still runs in Docker (published on 127.0.0.1:5432 only, via
# docker-compose.dev.yml); the ML service (127.0.0.1:6000, internal) and the
# app (API + built UI) run from the .venv-* virtualenvs. Stop with ./stop.sh.
# Works in Git Bash on Windows, and on macOS and Linux.
#
#   ./start.sh              start and open the browser
#   ./start.sh --no-browser start only
set -uo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
RUN="$ROOT/.run"
URL="http://localhost:8080"
HEALTH="http://127.0.0.1:8080/api/health"
OPEN_BROWSER=1
[ "${1:-}" = "--no-browser" ] && OPEN_BROWSER=0

step() { printf '\033[36m==> %s\033[0m\n' "$1"; }
fail() { printf '\n\033[31mPlaceIQ did not start: %s\033[0m\n' "$1"; exit 1; }
up() { curl -fs -o /dev/null --max-time 3 "$1"; }
venv_python() {  # Windows venvs keep python in Scripts/, macOS/Linux in bin/
  if [ -f "$ROOT/$1/Scripts/python.exe" ]; then echo "$ROOT/$1/Scripts/python.exe"; else echo "$ROOT/$1/bin/python"; fi
}
open_url() {
  case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*) start "" "$1" ;;
    Darwin) open "$1" ;;
    *) xdg-open "$1" >/dev/null 2>&1 || true ;;
  esac
}

cd "$ROOT"
mkdir -p "$RUN"

# --- 1. Docker (Postgres runs in it) ---------------------------------------------
step "Checking Docker"
command -v docker >/dev/null || fail "Docker is not installed. Install Docker Desktop (free for personal and education use) from https://www.docker.com/products/docker-desktop/ and run this again."
docker info >/dev/null 2>&1 || fail "Docker is not running. Start Docker Desktop (or the Docker daemon), wait until it is ready, then run ./start.sh again."

# --- 2. Already running? Port free? -------------------------------------------------
if up "$HEALTH"; then
  printf '\033[32mPlaceIQ is already running at %s\033[0m\n' "$URL"
  [ "$OPEN_BROWSER" = 1 ] && open_url "$URL"
  exit 0
fi
if curl -s -o /dev/null --max-time 2 "http://127.0.0.1:8080/"; then
  fail "port 8080 is used by another program. If it is the Docker version of PlaceIQ, stop it with 'docker compose down' first."
fi

# --- 3. Virtualenvs ------------------------------------------------------------------
PY_DB="$(venv_python .venv-db)"; PY_BACKEND="$(venv_python .venv-backend)"; PY_ML="$(venv_python .venv-ml)"
for py in "$PY_DB" "$PY_BACKEND" "$PY_ML"; do
  [ -e "$py" ] || fail "missing virtualenv ($py). Create it as described in README.md (Setup without Docker), or use 'docker compose up -d --build' instead."
done

# --- 4. JWT secret in the git-ignored .env (generated, never printed) ----------------
[ -f .env ] || cp .env.example .env
if ! grep -Eq '^JWT_SECRET_KEY=.+' .env || grep -q '^JWT_SECRET_KEY=replace_with_a_long_random_secret' .env; then
  step "Generating a JWT secret into .env (git-ignored)"
  secret="$("$PY_BACKEND" -c 'import secrets; print(secrets.token_urlsafe(64))')"
  grep -v '^JWT_SECRET_KEY=' .env > "$RUN/env.tmp" || true
  printf 'JWT_SECRET_KEY=%s\n' "$secret" >> "$RUN/env.tmp"
  mv "$RUN/env.tmp" .env
  unset secret
fi

# --- 5. Database -------------------------------------------------------------------
step "Starting the database container"
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d db >/dev/null 2>&1 || fail "could not start the database container."
for _ in $(seq 1 45); do
  [ "$(docker inspect -f '{{.State.Health.Status}}' placement_db 2>/dev/null)" = "healthy" ] && break
  sleep 2
done
[ "$(docker inspect -f '{{.State.Health.Status}}' placement_db 2>/dev/null)" = "healthy" ] || fail "the database container did not become healthy within 90 seconds."
"$PY_DB" docker/init_db.py || fail "preparing the database failed (see the messages above)."

# --- 6. Built UI -----------------------------------------------------------------------
# Built when missing, and rebuilt when any frontend source is newer than the
# build: serving a stale build after a UI change would show old code (or, as
# happened once, call an API address that no longer exists).
need_build=0
if [ ! -f frontend/dist/index.html ]; then
  need_build=1
elif [ -n "$(find frontend/src frontend/public frontend/index.html frontend/package.json frontend/vite.config.js frontend/.env \
               -newer frontend/dist/index.html -type f 2>/dev/null | head -n 1)" ]; then
  need_build=1
fi
if [ "$need_build" = 1 ]; then
  step "Building the UI (first run, or the UI changed since the last build)"
  command -v npm >/dev/null || fail "frontend/dist is missing and Node.js is not installed to build it. Install Node.js LTS from https://nodejs.org/ or use 'docker compose up -d --build'."
  (cd frontend && npm ci --no-audit --no-fund >/dev/null 2>&1 && npm run build >/dev/null 2>&1) || fail "the UI build failed. Run 'npm run build' in frontend/ to see why."
fi

# --- 7. ML service and app -------------------------------------------------------------
# Each server writes its own process id to .run/<name>.pid (PLACEIQ_PIDFILE),
# which stop.sh uses. A shell's $! is not reliable here: on Windows it is not
# the Python process (a venv's python.exe starts the real interpreter as a child).
start_bg() {  # name, directory, python, script
  pidfile="$RUN/$1.pid"
  # Native Windows Python needs a Windows path (C:\...), not Git Bash's /c/...
  case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) pidfile="$(cygpath -w "$pidfile")" ;; esac
  rm -f "$RUN/$1.pid"
  (cd "$2" && PLACEIQ_PIDFILE="$pidfile" nohup "$3" "$4" > "$RUN/$1.log" 2>&1 &)
}
step "Starting the ML service (127.0.0.1:6000, internal)"
start_bg ml ml-service "$PY_ML" app.py
step "Starting the app on $URL"
start_bg app backend "$PY_BACKEND" serve.py

for _ in $(seq 1 60); do
  up "$HEALTH" && break
  sleep 1
done
if ! up "$HEALTH"; then
  tail -n 15 "$RUN/app.log"
  fail "the app did not answer on $HEALTH (log above, full logs in .run/). Stop leftovers with ./stop.sh."
fi

printf '\n\033[32mPlaceIQ is running at %s\033[0m\n' "$URL"
echo "Stop it with ./stop.sh   (logs: .run/)"
[ "$OPEN_BROWSER" = 1 ] && open_url "$URL"
exit 0
