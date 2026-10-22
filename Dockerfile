# PlaceIQ app image: the React frontend (built in the first stage) and the
# Flask API, served together by waitress on one port (8080).

# --- Stage 1: build the frontend ---------------------------------------------
FROM node:22-alpine AS frontend
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# --- Stage 2: the Python app ---------------------------------------------------
FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8080 \
    FRONTEND_DIST=/app/frontend/dist
WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/
COPY db/schema.sql db/seed.py db/
COPY docker/init_db.py docker/app-entrypoint.sh docker/
COPY --from=frontend /src/dist frontend/dist

# Run as an unprivileged user; /data holds the generated JWT secret.
RUN useradd --create-home placeiq && mkdir /data && chown placeiq /data
USER placeiq

EXPOSE 8080
ENTRYPOINT ["sh", "/app/docker/app-entrypoint.sh"]
