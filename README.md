# PlaceIQ: College Placement Management System

DBMS academic project: PostgreSQL + Flask (raw psycopg2) + React, with a small
ML service for a placement-probability widget. The database design (schema,
triggers, procedures, views) is the main deliverable: see `docs/er-diagram.md`
and `docs/normalization.md`. An Oracle/SQL*Plus port of the schema is in
`db/schema_oracle.sql`, verified on Oracle 21c (`docs/oracle-differences.md`).
`docs/viva-cheatsheet.md` is a one-page pre-viva reference, and
`docs/PlaceIQ_DA3_Report.pdf` is the project report.

**Everything runs at one address: http://localhost:8080** (the UI and the API
on one port; the ML service and the database are not exposed).

## Run it

Pick one. All three use the same data.

### 1. One command (Docker)

Needs only **Docker Desktop** (free for personal and education use).

```bash
docker compose up -d --build     # then open http://localhost:8080
docker compose down              # stop (data is kept)
```

The first start builds the images, creates the tables, loads the synthetic
data and trains the model (about 4 minutes). Later starts take seconds. A JWT
secret is generated into a Docker volume the first time, or taken from `.env`
if you have one.

### 2. Desktop app (Windows)

`desktop/dist/PlaceIQ-1.0.0-portable.exe`: double-click it. It checks that
Docker Desktop is running (and offers **Retry** if not), starts the same stack,
shows PlaceIQ in its own window, and stops the stack when you close it.
It needs Docker Desktop installed; see `desktop/README.md` for what it does
and doesn't bundle, and how to build it (`npm run dist` in `desktop/`).

### 3. Without Docker for the app (local virtualenvs)

Postgres still runs in Docker; the app and the ML service run from Python
virtualenvs on this machine.

| Windows (PowerShell) | macOS / Linux / Git Bash |
|---|---|
| `.\start.ps1` | `./start.sh` |
| `.\stop.ps1` | `./stop.sh` |

The start scripts check Docker (and say clearly if it isn't running),
generate a JWT secret into your git-ignored `.env`, create the tables and load
the data if needed, rebuild the UI when its source changed, start everything
and open http://localhost:8080. One-time setup of the virtualenvs:

| Windows (PowerShell) | macOS / Linux |
|---|---|
| `python -m venv .venv-db; .venv-db\Scripts\python -m pip install -r db/requirements.txt`<br>`python -m venv .venv-backend; .venv-backend\Scripts\python -m pip install -r backend/requirements.txt`<br>`python -m venv .venv-ml; .venv-ml\Scripts\python -m pip install -r ml-service/requirements.txt -c ml-service/constraints.txt` | `python3 -m venv .venv-db && .venv-db/bin/python -m pip install -r db/requirements.txt`<br>`python3 -m venv .venv-backend && .venv-backend/bin/python -m pip install -r backend/requirements.txt`<br>`python3 -m venv .venv-ml && .venv-ml/bin/python -m pip install -r ml-service/requirements.txt -c ml-service/constraints.txt` |

Node.js is needed only to build the UI (`npm run build` in `frontend/`); for
live UI editing see `frontend/README.md`.

## Share it

**Temporary public link (free, no account):** `.\scripts\share.ps1`
(`./scripts/share.sh`) starts PlaceIQ in public mode and prints an
`https://<random-words>.trycloudflare.com` link through a Cloudflare quick
tunnel. It asks before downloading `cloudflared` from Cloudflare's official
release page. In public mode the demo passwords are replaced by random ones
kept in the git-ignored `.env.public`, the JWT secret comes from there too, and
logins are rate-limited. Stop with `.\scripts\share.ps1 -Stop` (restores the
demo passwords).

**Permanent free hosting:** follow `DEPLOY_FREE.md` (Render + Neon, steps you
run yourself, with their limits).

## Repo layout

```
db/            schema.sql (DDL), seed.py (synthetic data), Oracle port, demos
backend/       Flask API (raw psycopg2, no ORM), serve.py = production server
frontend/      React (Vite) UI, built into frontend/dist and served by the backend
ml-service/    placement model: train.py + app.py (internal service)
docker/        first-run database setup, entrypoint, password tool
desktop/       Windows desktop app (Electron)
scripts/       share.ps1 / share.sh (public link)
tests/         smoke test, API contract check, browser checks
docs/          report, ER diagram, normalization, API, evidence
docker-compose.yml       db + app + ml (only app publishes a port)
docker-compose.dev.yml   also publishes Postgres on 127.0.0.1 (for local tools)
```

### Seeded login credentials
- TPO/admin: `tpo@campus.edu` / `Admin@123`
- Coordinator/admin: `coordinator@campus.edu` / `Admin@123`
- All seeded students: password `Student@123` (see `student` table for emails/reg_nos)

## What's in it

- **Database** (`db/schema.sql`): 13 tables with PK/FK/UNIQUE/CHECK constraints,
  5 purpose-built indexes, 6 triggers (placement status, audit log, and four
  that make the database refuse invalid writes), stored functions, the
  `sp_close_drive` procedure, analytics views, window-function views and a
  materialized view. An Oracle/SQL*Plus port is in `db/schema_oracle.sql`.
- **Synthetic data** (`db/seed.py`): 180 students, 18 companies, 25 drives,
  517 applications, 177 offers, with placement outcomes correlated with CGPA.
- **Backend** (`backend/`): Flask with raw psycopg2 (no ORM), JWT auth with
  student and admin roles, and an explicit multi-statement offer transaction
  (`backend/services/offer_service.py`).
- **ML service** (`ml-service/`): placement-probability model (below).
- **Frontend** (`frontend/`): React + Vite, built and served by the backend
  from the same origin (no CORS).
- **Dates**: every drive has an application deadline; the database refuses
  applications after it or dated in the future (trigger, PL008), and the
  synthetic timelines are always in order (`docs/evidence/date-integrity.md`).
- **Tests** (`tests/`): an end-to-end smoke test on a throwaway database
  (`bash tests/run_smoke_test.sh`, needs the database and the ML service, as
  started by `start.ps1`), the API contract check
  (`bash tests/run_smoke_test.sh tests/api_contract_check.py`), and browser
  checks for the single URL and the desktop app.

## ML model: what the numbers mean

A logistic-regression model predicts each student's chance of being placed
from CGPA, backlogs, department and number of skills. Measured on the current
seed data (`ml-service/train.py` prints these; raw output in
`docs/evidence/raw/ml-training-output.txt`):

| Metric | Value |
|---|---|
| Test ROC-AUC | 0.774 |
| Test accuracy | 0.750 (27 of 36 correct) |
| Test set | 36 students (19 placed, 17 not placed); 144 used for training |
| Strongest features | CGPA (+1.50), backlogs (−1.14), skill count (+0.82), in log-odds per standard deviation |

Two caveats to state whenever these numbers are quoted:

- **The test set is small.** With 36 students, one prediction changing moves
  accuracy by about 3 points, so treat the score as a rough indication.
- **The data is synthetic.** `db/seed.py` builds the CGPA/backlog/skill
  relationship in on purpose, so the model is recovering a pattern we
  designed. It shows the pipeline works end to end, not that it would
  predict real placements.

## API

All 36 endpoints are documented in [`docs/API.md`](docs/API.md): role,
request body, response fields, error codes and a curl example for each.
The doc is checked against the running backend by
`bash tests/run_smoke_test.sh tests/api_contract_check.py`, which fails if
they ever disagree.
