#!/usr/bin/env bash
# Stops what start.sh started: the app, the ML service and the database
# container. Data is kept (it lives in a Docker volume).
#   ./stop.sh            stop everything
#   ./stop.sh --keep-db  leave the database container running
set -uo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
RUN="$ROOT/.run"
cd "$ROOT"

for name in app ml; do
  [ -s "$RUN/$name.pid" ] || continue
  pid="$(cat "$RUN/$name.pid")"   # written by the server itself
  case "$(uname -s)" in
    # Windows: the id is the real Python server; /T also ends anything it started.
    MINGW*|MSYS*|CYGWIN*) taskkill //PID "$pid" //T //F >/dev/null 2>&1 ;;
    *) kill "$pid" 2>/dev/null ;;
  esac
  rm -f "$RUN/$name.pid"
  echo "Stopped $name"
done

if [ "${1:-}" != "--keep-db" ] && command -v docker >/dev/null; then
  if docker info >/dev/null 2>&1; then
    docker compose -f docker-compose.yml -f docker-compose.dev.yml stop db >/dev/null 2>&1 && echo "Stopped the database container (data kept)"
  else
    echo "Docker is not running, so the database container is already stopped."
  fi
fi
echo "PlaceIQ stopped."
