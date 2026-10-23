#!/bin/sh
# Entrypoint of the app container: secret, database, then the server.
set -e

# A public (shared) instance never falls back to generated or demo values:
# everything must come from the git-ignored .env.public (scripts/share.ps1).
if [ "$PUBLIC_MODE" = "1" ]; then
  if [ ${#JWT_SECRET_KEY} -lt 32 ] || [ ${#ADMIN_PASSWORD} -lt 12 ] || [ ${#STUDENT_PASSWORD} -lt 12 ]; then
    echo "PUBLIC_MODE=1 needs JWT_SECRET_KEY (32+), ADMIN_PASSWORD and STUDENT_PASSWORD (12+) from .env.public." >&2
    exit 1
  fi
fi

# The JWT secret signs login tokens. If none was provided (JWT_SECRET_KEY),
# one is generated the first time and kept in the app_data volume, so it is
# never in the image or the repository, and logins survive a restart.
if [ -z "$JWT_SECRET_KEY" ]; then
  SECRET_FILE=/data/jwt_secret
  if [ ! -s "$SECRET_FILE" ]; then
    umask 077
    python -c "import secrets; print(secrets.token_urlsafe(64))" > "$SECRET_FILE"
    echo "Generated a new JWT secret (kept in the app_data volume)."
  fi
  JWT_SECRET_KEY="$(cat "$SECRET_FILE")"
  export JWT_SECRET_KEY
fi

python /app/docker/init_db.py

# Shared publicly: replace the documented demo passwords with private ones.
if [ "$PUBLIC_MODE" = "1" ]; then
  python /app/docker/set_passwords.py
fi

cd /app/backend
exec python serve.py
