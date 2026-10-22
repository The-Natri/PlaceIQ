#!/bin/sh
# Entrypoint of the app container: secret, database, then the server.
set -e

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

cd /app/backend
exec python serve.py
