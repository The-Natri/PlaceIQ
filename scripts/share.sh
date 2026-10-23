#!/usr/bin/env bash
# Shares PlaceIQ on a temporary public https link (Cloudflare quick tunnel,
# free, no account), with private passwords instead of the demo ones.
# Same steps as scripts/share.ps1 (read its header for details).
#
#   ./scripts/share.sh          start sharing, print the https://...trycloudflare.com link
#   ./scripts/share.sh --yes    same, without asking before downloading cloudflared
#   ./scripts/share.sh --stop   end the tunnel, restore demo passwords, stop the stack
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUN="$ROOT/.run"; TOOLS="$ROOT/tools"; ENV_PUBLIC="$ROOT/.env.public"
HEALTH="http://127.0.0.1:8080/api/health"
step() { printf '\033[36m==> %s\033[0m\n' "$1"; }
fail() { printf '\n\033[31mSharing did not start: %s\033[0m\n' "$1"; exit 1; }
up() { curl -fs -o /dev/null --max-time 3 "$HEALTH"; }
cd "$ROOT"; mkdir -p "$RUN"
COMPOSE=(docker compose --env-file "$ENV_PUBLIC")
case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) WIN=1 ;; *) WIN=0 ;; esac

if [ "${1:-}" = "--stop" ]; then
  if [ -s "$RUN/cloudflared.pid" ]; then
    if [ "$WIN" = 1 ]; then taskkill //PID "$(cat "$RUN/cloudflared.pid")" //T //F >/dev/null 2>&1
    else kill "$(cat "$RUN/cloudflared.pid")" 2>/dev/null; fi
    rm -f "$RUN/cloudflared.pid"; echo "Stopped the tunnel. The public link no longer works."
  fi
  if docker info >/dev/null 2>&1; then
    up && docker exec placeiq_app python /app/docker/set_passwords.py --demo
    "${COMPOSE[@]}" down >/dev/null 2>&1
    echo "Stopped PlaceIQ. Next local start uses the demo passwords again."
  fi
  exit 0
fi

step "Checking Docker"
command -v docker >/dev/null || fail "Docker is not installed. Install Docker Desktop (free for personal and education use) and run this again."
docker info >/dev/null 2>&1 || fail "Docker is not running. Start it, wait until it is ready, then run this again."

if [ ! -f "$ENV_PUBLIC" ]; then
  step "Creating .env.public with a random JWT secret and passwords (git-ignored)"
  rnd() { head -c "$1" /dev/urandom | base64 | tr '+/' '-_' | tr -d '=\n'; }
  umask 077
  {
    echo "# Secrets for the PUBLIC instance (scripts/share.sh). Git-ignored: never commit it."
    echo "# Log in on the public link with these. Delete this file to get new ones."
    echo "PUBLIC_MODE=1"
    echo "JWT_SECRET_KEY=$(rnd 48)"
    echo "ADMIN_PASSWORD=$(rnd 12)"
    echo "STUDENT_PASSWORD=$(rnd 12)"
  } > "$ENV_PUBLIC"
fi

step "Starting PlaceIQ in public mode"
"${COMPOSE[@]}" up -d --build >/dev/null 2>&1 || fail "docker compose could not start the stack (is port 8080 used by start.sh? stop it with ./stop.sh)."
for _ in $(seq 1 300); do up && break; sleep 3; done
up || fail "PlaceIQ did not become ready (docker logs placeiq_app)."

case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) ASSET="cloudflared-windows-amd64.exe"; BIN="$TOOLS/cloudflared.exe" ;;
  Linux) ASSET="cloudflared-linux-amd64"; BIN="$TOOLS/cloudflared" ;;
  *) ASSET=""; BIN="" ;;
esac
CLOUDFLARED="$(command -v cloudflared || true)"
if [ -z "$CLOUDFLARED" ]; then
  [ -n "$ASSET" ] || fail "cloudflared is not installed. On macOS: brew install cloudflared"
  CLOUDFLARED="$BIN"
  if [ ! -x "$CLOUDFLARED" ]; then
    URL_DL="https://github.com/cloudflare/cloudflared/releases/latest/download/$ASSET"
    echo; echo "cloudflared (Cloudflare's free tunnel client, no account needed) is not installed."
    echo "It will be downloaded from Cloudflare's official GitHub release page:"
    echo "  $URL_DL"; echo "into $TOOLS (git-ignored)."
    if [ "${1:-}" != "--yes" ]; then
      read -r -p "Download it now? [y/N] " answer
      [[ "$answer" =~ ^[Yy]([Ee][Ss])?$ ]] || fail "cloudflared is needed for the public link."
    fi
    mkdir -p "$TOOLS" && curl -fL --progress-bar -o "$CLOUDFLARED" "$URL_DL" && chmod +x "$CLOUDFLARED" || fail "the download failed."
  fi
fi

step "Opening the tunnel"
rm -f "$RUN/cloudflared.log"
nohup "$CLOUDFLARED" tunnel --no-autoupdate --url http://localhost:8080 > "$RUN/cloudflared.log" 2>&1 &
pid=$!
# Git Bash: record the Windows process id (needed by taskkill). Read it after a
# moment, once the background job has become cloudflared itself.
[ "$WIN" = 1 ] && { sleep 2; pid="$(ps -p "$pid" | awk 'NR==2 {print $4}')"; }
echo "$pid" > "$RUN/cloudflared.pid"

url=""
for _ in $(seq 1 60); do
  # The link is https://<random-words>.trycloudflare.com; api.trycloudflare.com is Cloudflare's API, not it.
  url="$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$RUN/cloudflared.log" | grep -v '://api\.' | head -n 1)"
  [ -n "$url" ] && break
  grep -q "failed to request quick Tunnel" "$RUN/cloudflared.log" && break
  sleep 1
done
[ -n "$url" ] || fail "Cloudflare did not create a tunnel (see .run/cloudflared.log; often a network or firewall block on api.trycloudflare.com). Try again in a minute. Stop with ./scripts/share.sh --stop."
echo "$url" > "$RUN/share-url.txt"
printf '\n\033[32mPlaceIQ is public at:  %s\033[0m\n' "$url"
echo "Log in with the passwords in .env.public (demo passwords are disabled)."
echo "Stop sharing with:  ./scripts/share.sh --stop"
