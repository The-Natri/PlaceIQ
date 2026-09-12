# College Placement Management System

DBMS academic project: Flask + PostgreSQL + React, with a small Flask ML
microservice for a placement-probability widget. The database design
(schema, triggers, procedures, views) is the primary deliverable — see
`docs/er-diagram.md` and `docs/normalization.md`.

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

### Seeded login credentials
- TPO/admin: `tpo@campus.edu` / `Admin@123`
- Coordinator/admin: `coordinator@campus.edu` / `Admin@123`
- All seeded students: password `Student@123` (see `student` table for emails/reg_nos)

## Status

- [x] Schema (DDL, constraints, indexes, trigger, functions, views) — `db/schema.sql`
- [x] Synthetic dataset generator — `db/seed.py`
- [x] Backend read CRUD (departments/students/companies/drives) — `backend/`
- [ ] Auth (JWT, bcrypt, student/admin roles)
- [ ] Admin drive management + shortlisting + offers
- [ ] Explicit multi-table offer-acceptance transaction
- [ ] Analytics endpoints
- [ ] ML microservice
- [ ] Frontend (React/Vite, minimal)
