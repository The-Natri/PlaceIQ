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
frontend/      React (Vite) — minimal/unstyled, teammate restyles this
ml-service/    Flask microservice, trains + serves the placement model
docs/          er-diagram.md, normalization.md
docker-compose.yml   Postgres 16 for local dev
```

## Quick start (verified working on this machine)

1. **Start Postgres:**
   ```
   docker compose up -d db
   ```
2. **Copy env file:**
   ```
   cp .env.example .env
   ```
3. **Load the schema:**
   ```
   docker exec -i placement_db psql -U placement_admin -d placement_db < db/schema.sql
   ```
4. **Seed synthetic data** (~180 students, 18 companies, 25 drives, correlated
   outcomes — see the big comment at the top of `db/seed.py` for the
   correlation logic):
   ```
   python -m venv .venv-db
   .venv-db/Scripts/pip install -r db/requirements.txt      # Windows
   .venv-db/Scripts/python db/seed.py
   ```
5. **Run the backend:**
   ```
   python -m venv .venv-backend
   .venv-backend/Scripts/pip install -r backend/requirements.txt
   cd backend
   ../.venv-backend/Scripts/python app.py
   ```
   Then check `http://127.0.0.1:5000/api/health`.
6. **Run the ML microservice** (trains a model from the live DB on first run):
   ```
   python -m venv .venv-ml
   .venv-ml/Scripts/pip install -r ml-service/requirements.txt
   cd ml-service
   ../.venv-ml/Scripts/python train.py     # optional — app.py auto-trains if model/model.joblib is missing
   ../.venv-ml/Scripts/python app.py
   ```
   Then check `http://127.0.0.1:6000/health`. Re-run `train.py` after re-seeding.
7. **Run the frontend:**
   ```
   cd frontend
   npm install
   cp .env.example .env
   npm run dev
   ```
   Then open `http://localhost:5173`.

### Seeded login credentials
- TPO/admin: `tpo@campus.edu` / `Admin@123`
- Coordinator/admin: `coordinator@campus.edu` / `Admin@123`
- All seeded students: password `Student@123` (see `student` table for emails/reg_nos)

## Status

- [x] Schema (DDL, constraints, indexes, trigger, functions, views) — `db/schema.sql`
- [x] Synthetic dataset generator — `db/seed.py`
- [x] Backend read CRUD (departments/students/companies/drives) — `backend/`
- [x] Auth (JWT, bcrypt, student/admin roles) — `backend/routes/auth.py`
- [x] Admin drive management + shortlisting + offers — `backend/routes/drives.py`, `applications.py`
- [x] Explicit multi-table offer-acceptance transaction — `backend/services/offer_service.py`
- [x] Analytics endpoints (views + package/branch + cgpa-vs-outcome) — `backend/routes/analytics.py`
- [x] ML microservice (logistic regression, trained off the live DB) — `ml-service/`
- [x] Frontend (React/Vite, minimal, unstyled) — `frontend/` — full flow verified in a real browser: student signup/login/apply/accept-offer, admin login/create-drive/shortlist/record-offer, analytics page

## Everything verified end-to-end, not just written

Every piece above was actually run against a live Postgres container, not
just authored: schema applied cleanly, seed script produces a real
CGPA-placement correlation (100% placed at CGPA 8.5+, 6.8% below 6.5), the
placement_status trigger was confirmed firing through the real API path, the
offer accept/decline transaction was confirmed both committing correctly and
correctly reverting `placement_status` when a student's only offer is
declined, the ML model trained to test ROC-AUC 0.878, and the full frontend
flow (student dashboard incl. ML widget, admin drive management, analytics)
was driven headlessly in a real browser with screenshots checked by eye.

## API summary (once auth is added, everything below api/departments requires `Authorization: Bearer <token>`)

- `POST /api/auth/student/signup`, `/student/login`, `/admin/login`, `GET /me`
- `GET /api/departments`
- `GET /api/students` (admin), `GET /api/students/:id` (self/admin), `GET /api/students/:id/eligible-drives`, `GET /api/students/:id/applications`
- `GET /api/companies`, `GET /api/companies/:id`
- `GET/POST /api/drives`, `PUT /api/drives/:id` (admin write), `GET /api/drives/:id/applicants` (admin)
- `POST /api/applications` (student applies), `GET /api/applications/:id`, `PUT /api/applications/:id/status` (admin), `POST /api/applications/:id/interview-rounds` (admin), `POST /api/applications/:id/offer` (admin — fires the placement_status trigger)
- `GET /api/offers/:id`, `POST /api/offers/:id/accept`, `POST /api/offers/:id/decline` (the explicit transaction demo)
- `GET /api/analytics/overview`, `/department-stats`, `/company-stats?top=N`, `/package-by-branch`, `/cgpa-vs-outcome` (all admin-only)
