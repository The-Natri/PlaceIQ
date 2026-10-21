# College Placement Management System

DBMS academic project: Flask + PostgreSQL + React, with a small Flask ML
microservice for a placement-probability widget. The database design
(schema, triggers, procedures, views) is the primary deliverable — see
`docs/er-diagram.md` and `docs/normalization.md`. An Oracle/SQL*Plus port
of the schema (for professors who specifically want SQL*Plus) lives at
`db/schema_oracle.sql`, with every divergence explained in
`docs/oracle-differences.md` — verified against a real Oracle 21c instance,
not just written. `docs/viva-cheatsheet.md` is a one-page pre-viva reference.

## Repo layout

```
db/            schema.sql (DDL), seed.py (synthetic dataset generator)
backend/       Flask API (raw psycopg2, no ORM — see backend/db.py for why)
frontend/      React (Vite) UI — owned by the frontend teammate
ml-service/    Flask microservice, trains + serves the placement model
docs/          er-diagram.md, normalization.md
docker-compose.yml   Postgres 16 for local dev
```

## Quick start

**Prerequisites:** Docker Desktop, Python 3.10+, Node.js 18+.

The only difference between platforms is where a virtual environment keeps
its Python: `.venv-x\Scripts\python` on Windows, `.venv-x/bin/python` on
macOS/Linux. Every command below calls that Python directly, so nothing needs
"activating". Run all commands from the repo root unless a step says `cd`.

1. **Start Postgres** (same everywhere):
   ```
   docker compose up -d db
   ```

2. **Create your `.env`** and give it a real JWT secret (anyone who knows the
   secret can forge an admin login, so never reuse the placeholder):

   | Windows (PowerShell) | macOS / Linux |
   |---|---|
   | `Copy-Item .env.example .env` | `cp .env.example .env` |

   Generate a secret with
   `python -c "import secrets; print(secrets.token_urlsafe(64))"` and paste it
   as the `JWT_SECRET_KEY` value in `.env`.

3. **Load the schema** (PowerShell has no `<` redirection, hence the pipe):

   | Windows (PowerShell) | macOS / Linux |
   |---|---|
   | `Get-Content db/schema.sql \| docker exec -i placement_db psql -U placement_admin -d placement_db` | `docker exec -i placement_db psql -U placement_admin -d placement_db < db/schema.sql` |

4. **Seed synthetic data** (180 students, 18 companies, 25 drives, outcomes
   correlated with CGPA; see the comment at the top of `db/seed.py`). Takes
   about 2-3 minutes.

   | Windows (PowerShell) | macOS / Linux |
   |---|---|
   | `python -m venv .venv-db`<br>`.venv-db\Scripts\python -m pip install -r db/requirements.txt`<br>`.venv-db\Scripts\python db/seed.py` | `python3 -m venv .venv-db`<br>`.venv-db/bin/python -m pip install -r db/requirements.txt`<br>`.venv-db/bin/python db/seed.py` |

5. **Run the backend** (port 5000):

   | Windows (PowerShell) | macOS / Linux |
   |---|---|
   | `python -m venv .venv-backend`<br>`.venv-backend\Scripts\python -m pip install -r backend/requirements.txt`<br>`cd backend; ..\.venv-backend\Scripts\python app.py` | `python3 -m venv .venv-backend`<br>`.venv-backend/bin/python -m pip install -r backend/requirements.txt`<br>`cd backend && ../.venv-backend/bin/python app.py` |

   Check `http://127.0.0.1:5000/api/health`. Debug mode is off by default;
   set `FLASK_DEBUG=1` in `.env` for auto-reload while developing.

6. **Run the ML service** (port 6000; trains a model from the database on first start):

   | Windows (PowerShell) | macOS / Linux |
   |---|---|
   | `python -m venv .venv-ml`<br>`.venv-ml\Scripts\python -m pip install -r ml-service/requirements.txt`<br>`cd ml-service; ..\.venv-ml\Scripts\python app.py` | `python3 -m venv .venv-ml`<br>`.venv-ml/bin/python -m pip install -r ml-service/requirements.txt`<br>`cd ml-service && ../.venv-ml/bin/python app.py` |

   Check `http://127.0.0.1:6000/health`. Re-run `train.py` in `ml-service/`
   after re-seeding so the model matches the data.

7. **Run the frontend** (port 5173). **Run `npm install` again every time you
   pull**, since teammates may add packages (e.g. `lucide-react`):

   | Windows (PowerShell) | macOS / Linux |
   |---|---|
   | `cd frontend`<br>`npm install`<br>`Copy-Item .env.example .env`<br>`npm run dev` | `cd frontend`<br>`npm install`<br>`cp .env.example .env`<br>`npm run dev` |

   Open `http://localhost:5173`. `frontend/.env` holds `VITE_API_URL` (the
   backend address). If the frontend runs on a different address, add it to
   `FRONTEND_ORIGINS` in the root `.env`, or the browser will block its API
   calls (CORS).

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
- **Frontend** (`frontend/`): React + Vite.
- **Tests** (`tests/`): an end-to-end smoke test that runs against a
  throwaway database. Run it with `bash tests/run_smoke_test.sh`
  (needs Postgres and the ML service running).

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

## API summary (once auth is added, everything below api/departments requires `Authorization: Bearer <token>`)

- `POST /api/auth/student/signup`, `/student/login`, `/admin/login`, `GET /me`
- `GET /api/departments`
- `GET /api/students` (admin), `GET /api/students/:id` (self/admin), `GET /api/students/:id/eligible-drives`, `GET /api/students/:id/applications`
- `GET /api/companies`, `GET /api/companies/:id`
- `GET/POST /api/drives`, `PUT /api/drives/:id` (admin write), `GET /api/drives/:id/applicants` (admin)
- `POST /api/applications` (student applies), `GET /api/applications/:id`, `PUT /api/applications/:id/status` (admin), `POST /api/applications/:id/interview-rounds` (admin), `POST /api/applications/:id/offer` (admin — fires the placement_status trigger)
- `GET /api/offers/:id`, `POST /api/offers/:id/accept`, `POST /api/offers/:id/decline` (the explicit transaction demo)
- `GET /api/analytics/overview`, `/department-stats`, `/company-stats?top=N`, `/package-by-branch`, `/cgpa-vs-outcome` (all admin-only)
