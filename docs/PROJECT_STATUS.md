# PlaceIQ — Project Status Audit

**Audited:** 21 Oct 2026, against the repo at commit `a0b612c` (branch `main`).
**Method:** everything below was read from the repo or run during this audit. Nothing is taken from memory of earlier sessions. Where something couldn't be verified it says so. No code was changed during the audit.

**Bottom line:** everything in the original brief works end to end, and every check run during this audit passed. It is **not ready to hand off as-is**. One commit isn't pushed, one file isn't committed, and the docs, the Oracle port and the ML accuracy figure have all fallen behind the code. Most of the frontend doesn't use the newest database features yet. Details in §4.

---

## 1. What's done (verified)

### 1.1 Files

**`db/`**
| File | Contents |
|---|---|
| `schema.sql` | PostgreSQL DDL, 10 sections: tables, indexes, placement trigger, eligibility functions, analytics views, business-rule triggers, audit trigger, `sp_close_drive` procedure, window-function views, materialized view. Every design choice is commented. |
| `schema_oracle.sql` | Oracle/SQL*Plus port of `schema.sql` **Sections 1–5 only** (see §4). Sequences + BEFORE INSERT triggers for auto-increment, PL/SQL trigger and functions. |
| `seed.py` | Deterministic (`random.seed(42)`) synthetic data generator. Placement outcome is a logistic function of CGPA margin, backlogs and skill count. Eligibility goes through the DB's own `fn_check_eligibility()`. |
| `requirements.txt` | psycopg2-binary, bcrypt, python-dotenv. |
| `demos/index_benchmark.py` | **Untracked (not committed).** Builds a throwaway 50k-student / 250k-application database and times 5 queries with and without the indexes. |

**`backend/`**
| File | Contents |
|---|---|
| `app.py` | Flask app factory: registers 8 blueprints, CORS, `/api/health`, ISO-8601 JSON date provider. |
| `config.py` | Reads `.env` (DB URL, JWT secret/expiry, ML service URL, debug flag). |
| `db.py` | psycopg2 connection pool; `get_cursor()` (commit/rollback, optional autocommit) and `get_connection()` (raw, for explicit transactions). |
| `routes/auth.py` | Student signup/login, admin login, `/me`. |
| `routes/departments.py`, `companies.py` | Reference data. |
| `routes/students.py` | Student list/profile, eligible drives, applications, ML probability. |
| `routes/drives.py` | Drive CRUD, close-drive procedure, applicants per drive. |
| `routes/applications.py` | Apply, application detail + audit history, status changes, interview rounds, record offer. |
| `routes/offers.py` | Offer detail, accept, decline. |
| `routes/analytics.py` | 9 admin analytics endpoints. |
| `services/offer_service.py` | Explicit multi-statement accept/decline transactions. |
| `utils/auth_middleware.py` | `require_auth(roles=…)` JWT decorator. |
| `utils/security.py` | bcrypt hashing, JWT encode/decode. |
| `utils/db_errors.py` | Maps DB rule codes PL001–PL005 to HTTP 403/404/409. |
| `requirements.txt` | Flask, flask-cors, psycopg2-binary, python-dotenv, bcrypt, PyJWT, requests. |

**`ml-service/`**
| File | Contents |
|---|---|
| `train.py` | Pulls features from Postgres, fits the pipeline, prints accuracy/ROC-AUC, saves `model/model.joblib`. |
| `app.py` | Flask service: `GET /health`, `POST /predict`. Auto-trains on first start if no model file. |
| `requirements.txt` | Flask, scikit-learn, pandas, joblib, psycopg2-binary, python-dotenv. |

**`frontend/`** (React 19 + Vite, redesigned by teammate, merged in PR #1)
| File | Contents |
|---|---|
| `src/api.js` | fetch wrapper; adds the JWT; base URL from `VITE_API_URL`. |
| `src/auth/AuthContext.jsx`, `ProtectedRoute.jsx`, `homeRoute.js` | Login state, role-guarded routes, role → home route. |
| `src/components/Navbar.jsx/.css` | Top bar, role-specific links. |
| `src/pages/*.jsx/.css` | Login, Signup, StudentDashboard, AdminDashboard, AdminDriveDetail, AdminAnalytics, with one CSS file per page. |
| `.env.example`, `vite.config.js`, `package.json` | Config; depends on `react-router-dom`, `lucide-react`. |

**`docs/`**: `er-diagram.md`, `normalization.md`, `oracle-differences.md`, `viva-cheatsheet.md`, and this file. Completeness is covered in §1.7.

**Root:** `README.md`, `docker-compose.yml` (Postgres 16 only), `.env.example`, `.gitignore`.

### 1.2 Database

Exact counts below come from the system catalog after applying `schema.sql` to an empty database.

**Tables (13):**
| Table | Purpose |
|---|---|
| `department` | Branches (CSE, ISE, …) |
| `coordinator` | TPO/admin accounts |
| `student` | Students; `placement_status` is a deliberate, trigger-maintained denormalization |
| `skill`, `student_skill` | Skills and the student↔skill M:N junction |
| `company` | Recruiters |
| `drive` | Job postings with eligibility cutoffs |
| `drive_eligible_dept` | Drive↔department M:N restriction (no rows = open to all) |
| `application` | Student↔drive M:N junction with status |
| `interview_round` | One row per round per application |
| `offer` | 0..1 per application (UNIQUE `application_id`) |
| `offer_history` | Offer audit log, written by the backend transaction |
| `application_status_history` | Application status audit log, written by a trigger |

**Constraints:** 13 PRIMARY KEY, 13 FOREIGN KEY (7 with `ON DELETE CASCADE`), 10 UNIQUE, 17 CHECK, 62 NOT NULL columns.

**Indexes:** 5 purpose-built (`idx_student_dept`, `idx_student_cgpa`, `idx_application_status`, `idx_application_drive`, `idx_drive_company`), plus `idx_status_history_application` and the materialized view's unique index. That's 30 in total once PK/UNIQUE indexes are counted.

**Triggers (4):**
| Trigger | Timing | What it does |
|---|---|---|
| `trg_offer_after_insert` | AFTER INSERT on offer | Sets student to Placed (skips offers inserted as Declined) |
| `trg_application_before_insert` | BEFORE INSERT on application | Refuses closed drives (PL002) and ineligible students (PL001) |
| `trg_offer_before_accept` | BEFORE INSERT/UPDATE on offer | Refuses a second accepted offer (PL003); locks the student row |
| `trg_application_status_audit` | AFTER UPDATE OF status, `WHEN` changed | Logs old → new status |

**Functions and procedure:**
- `fn_check_eligibility(student, drive) → boolean`
- `fn_get_eligible_drives(student) → SETOF drive`
- the 4 trigger functions above
- `sp_close_drive(drive, INOUT rejected_count)`, a PROCEDURE called with `CALL`

**Views (6 + 1 materialized):**
- `placed_students_view`, `company_wise_stats_view`, `department_stats_view`
- `dept_offer_ranking_view` (RANK), `placement_timeline_view` (running SUM, LAG), `student_cgpa_standing_view` (DENSE_RANK, PERCENT_RANK)
- Materialized: `mv_company_dept_placements` (refreshable CONCURRENTLY)

**Postgres vs Oracle:**
| Object group | `schema.sql` | `schema_oracle.sql` |
|---|---|---|
| 12 original tables, constraints, 5 indexes | ✅ | ✅ |
| `trg_offer_after_insert` | ✅ (with Declined guard) | ✅ (without the Declined guard) |
| `fn_check_eligibility`, `fn_get_eligible_drives` | ✅ | ✅ (NUMBER return, SYS_REFCURSOR) |
| 3 analytics views | ✅ | ✅ |
| `application_status_history` table + audit trigger | ✅ | ❌ missing |
| Business-rule triggers (PL001–PL003) | ✅ | ❌ missing |
| `sp_close_drive` procedure | ✅ | ❌ missing |
| 3 window-function views | ✅ | ❌ missing |
| Materialized view | ✅ | ❌ missing |

### 1.3 Backend API (36 endpoints)

Auth column: *public* = no token; *any* = any valid JWT; *self/admin* = a student may only access their own record, admins may access any.

| Method | Path | Auth | What it does |
|---|---|---|---|
| GET | `/api/health` | public | Liveness + DB connectivity |
| POST | `/api/auth/student/signup` | public | Create student (bcrypt), return JWT |
| POST | `/api/auth/student/login` | public | Student login → JWT |
| POST | `/api/auth/admin/login` | public | Coordinator/TPO login → JWT |
| GET | `/api/auth/me` | any | Current user's profile |
| GET | `/api/departments` | public | Department list (signup form) |
| GET | `/api/students` | admin | Student list; filters `dept_id`, `min_cgpa`, `placement_status` |
| GET | `/api/students/:id` | self/admin | Profile + skills + CGPA rank/percentile in dept |
| GET | `/api/students/:id/eligible-drives` | self/admin | Calls `fn_get_eligible_drives()` |
| GET | `/api/students/:id/applications` | self/admin | Application tracker |
| GET | `/api/students/:id/placement-probability` | self/admin | Sends features to ML `/predict` (503 if ML down) |
| GET | `/api/companies` | any | Company list |
| GET | `/api/companies/:id` | any | Company + its drives |
| GET | `/api/drives` | any | Drive list (`?status=`) |
| GET | `/api/drives/:id` | any | Drive + eligible departments |
| POST | `/api/drives` | admin | Create drive + department restrictions in one transaction |
| PUT | `/api/drives/:id` | admin | Edit drive / replace restrictions |
| POST | `/api/drives/:id/close` | admin | `CALL sp_close_drive` → rejected count |
| GET | `/api/drives/:id/applicants` | admin | Applicants for a drive |
| POST | `/api/applications` | student | Apply; the DB trigger enforces eligibility and an open drive |
| GET | `/api/applications/:id` | self/admin | Detail + interview rounds + offer + status history |
| PUT | `/api/applications/:id/status` | admin | Set Applied/Shortlisted/Interview_Scheduled/Rejected/Selected |
| POST | `/api/applications/:id/interview-rounds` | admin | Record a round |
| POST | `/api/applications/:id/offer` | admin | Insert offer (fires placement trigger) + offer_history + Offer_Made |
| GET | `/api/offers/:id` | self/admin | Offer detail |
| POST | `/api/offers/:id/accept` | self/admin | Accept transaction (below) |
| POST | `/api/offers/:id/decline` | self/admin | Decline transaction (below) |
| GET | `/api/analytics/overview` | admin | Totals + overall placement % |
| GET | `/api/analytics/department-stats` | admin | From `department_stats_view` |
| GET | `/api/analytics/company-stats?top=N` | admin | From `company_wise_stats_view` |
| GET | `/api/analytics/package-by-branch` | admin | Avg/max/min package per department |
| GET | `/api/analytics/cgpa-vs-outcome` | admin | Raw (cgpa, backlogs, status) points |
| GET | `/api/analytics/top-offers-per-dept?n=N` | admin | From `dept_offer_ranking_view` |
| GET | `/api/analytics/placement-timeline` | admin | From `placement_timeline_view` |
| GET | `/api/analytics/company-dept-matrix` | admin | Reads the materialized view + `refreshed_at` |
| POST | `/api/analytics/refresh-matrix` | admin | `REFRESH MATERIALIZED VIEW CONCURRENTLY` |

**Offer transaction (`backend/services/offer_service.py`).** Raw psycopg2, with explicit `conn.commit()` / `conn.rollback()`.

- **Accept:**
  1. `UPDATE offer SET status='Accepted' … WHERE status='Pending' RETURNING`. This acts as a guard against double-accept.
  2. `UPDATE student SET placement_status='Placed'`.
  3. `INSERT INTO offer_history 'Accepted'`.
- **Decline:**
  1. Flip the offer to Declined, with the same guard.
  2. If the student has no other Pending/Accepted offer, set them back to `'Not Placed'`.
  3. Write the history row.
- Any failure rolls back all three statements. That includes the PL003 trigger refusing a second acceptance; this audit confirmed no history row leaks.

### 1.4 ML service

| Item | Value |
|---|---|
| Model | scikit-learn Pipeline: `StandardScaler` (cgpa, backlogs, skill_count) + `OneHotEncoder` (dept_id) → `LogisticRegression(max_iter=1000)` |
| Features | `cgpa`, `backlogs`, `dept_id`, `skill_count` (counted from `student_skill`) |
| Label | `placement_status = 'Placed'` |
| Training | `python ml-service/train.py` reads straight from Postgres, 80/20 stratified split (`random_state=42`), saves `ml-service/model/model.joblib`. `app.py` auto-trains if the file is missing. |
| Backend call | `GET /api/students/:id/placement-probability` fetches the student's features → `POST {ML_SERVICE_URL}/predict` (5 s timeout) → returns the probability; 503 if the ML service is unreachable. |
| **Current ROC-AUC** | **0.774** for a fresh retrain on today's data (measured, not saved). The saved model scores 0.820, but it was trained on 12 Sep, before the seed changed, and probably saw some of today's test rows, so 0.820 is optimistic. The test set is only 36 students, so expect ±0.05 swings. The README's "0.878" is **out of date**. *Update (Phase 2, same day): the model was retrained and saved on freshly reseeded data, giving test ROC-AUC 0.774 and accuracy 0.750 on 36 test students. The 0.820 and 0.878 figures no longer apply anywhere; see the README's "ML model" section.* |
| Coefficients (fresh model) | cgpa +1.50, backlogs −1.14, skill_count +0.82 (standardized), so CGPA dominates, as designed. |

### 1.5 Frontend

| Page / component | API endpoints used |
|---|---|
| `AuthContext` | `POST /auth/student/login`, `/auth/admin/login`, `/auth/student/signup`, `GET /auth/me` |
| `Login` | via AuthContext |
| `Signup` | `GET /departments` (+ signup via AuthContext) |
| `StudentDashboard` | `GET /students/:id`, `/students/:id/eligible-drives`, `/students/:id/applications`, `/students/:id/placement-probability`, `/applications/:id`; `POST /applications`, `/offers/:id/accept`, `/offers/:id/decline` |
| `AdminDashboard` | `GET /drives`, `/companies`, `/departments`; `POST /drives` |
| `AdminDriveDetail` | `GET /drives/:id`, `/drives/:id/applicants`; `PUT /applications/:id/status`; `POST /applications/:id/interview-rounds`, `/applications/:id/offer` |
| `AdminAnalytics` | `GET /analytics/overview`, `/department-stats`, `/company-stats?top=8`, `/package-by-branch`, `/cgpa-vs-outcome` |
| `Navbar`, `ProtectedRoute` | none |

**Backend endpoints the frontend never calls:**
- `GET /students` (admin list), `GET /companies/:id`, `PUT /drives/:id` (edit), `POST /drives/:id/close`, `GET /offers/:id`
- analytics `top-offers-per-dept`, `placement-timeline`, `company-dept-matrix`, `refresh-matrix`
- the `status_history` and `cgpa_standing` fields returned by existing calls are never displayed

### 1.6 Seed data (live `placement_db`, counted during this audit)

| Table | Rows |
|---|---|
| department | 6 |
| coordinator | 2 |
| student | 180 (95 Placed) |
| skill | 28 |
| student_skill | 589 |
| company | 18 |
| drive | 25 (15 Completed, 7 Ongoing, 3 Upcoming) |
| drive_eligible_dept | 40 |
| application | 518 |
| interview_round | 842 |
| offer | 177 |
| offer_history | 329 |
| application_status_history | 646 |
| mv_company_dept_placements | 28 |

⚠️ This is **not a clean seed**. An earlier feature test left one extra application (a fresh seed gives 517) and closed drive 24, rejecting 37 applicants. Reseeding a fresh database during this audit gave the clean figures: 517 applications, 177 offers, 95 Placed.

### 1.7 Docs

| Doc | Exists | Complete? |
|---|---|---|
| `README.md` | ✅ | ❌ Out of date: calls the frontend "minimal/unstyled", quotes ROC-AUC 0.878, and its status list and API summary don't include any of the newest features (procedure, rules, audit, window functions, materialized view). *(Setup, feature list and ML figures fixed in Phases 1–2.)* |
| `docs/er-diagram.md` | ✅ | ❌ No `application_status_history` table. Mermaid only, no image. |
| `docs/normalization.md` | ✅ | ❌ Doesn't cover `application_status_history`. |
| `docs/oracle-differences.md` | ✅ | ⚠️ Accurate for what the Oracle port contains, but the port itself is missing Sections 6–10 (§1.2). |
| `docs/viva-cheatsheet.md` | ✅ | ❌ Doesn't cover the procedure, the rule/audit triggers, window functions, the materialized view or the index benchmark. |
| API contract doc for teammate | ❌ | Doesn't exist. The only reference is the README's partial "API summary". |

---

## 2. Verification (run during this audit)

| Check | Result | Evidence |
|---|---|---|
| Postgres starts | ✅ PASS | Cold start from Docker Desktop off: container healthy after 28 s |
| Backend starts | ✅ PASS | `/api/health` → 200; no errors in startup log |
| ML service starts | ✅ PASS | `/health` → 200, `model_loaded: true` |
| Frontend starts | ✅ PASS | Vite dev server → 200; `npm run build` succeeds (307 kB JS) |
| `schema.sql` on a fresh DB | ✅ PASS | New empty database, `ON_ERROR_STOP=1`, exit 0. Output: 13 tables, 4 triggers, 6 functions, 1 procedure, 6 views, 7 indexes, materialized view. No errors or warnings. |
| `seed.py` on that fresh DB | ✅ PASS | Exit 0; 180 students, 25 drives, 517 applications, 177 offers, 95 Placed |
| `schema_oracle.sql` on Oracle | ✅ PASS (for what it contains) | Oracle 21c XE in Docker, SQL*Plus. 12 tables, 10 sequences, 11 triggers, 5 indexes, 2 functions, 3 views created, with zero ORA-/SP2-/PLS- errors. Behaviour check: auto-increment IDs populated; `fn_check_eligibility` returned 1 / 0 / 0 (eligible / ineligible / nonexistent); trigger flipped Not Placed → Placed; view returned the row; REF CURSOR returned the drive. **Sections 6–10 can't be tested on Oracle because they haven't been ported.** |
| End-to-end smoke test | ✅ **28/28 PASS** | Run against a throwaway copy (fresh schema + seed) through a second backend on :5001, so the live DB was untouched. Details below. |

Smoke test steps (all PASS):
1. Admin login (200); wrong password rejected (401).
2. Student login; eligible drives returned via `fn_get_eligible_drives`.
3. A student reading another student's record is refused (403).
4. Apply (201); duplicate apply refused (409).
5. Admin shortlists (200); a student trying to change status is refused (403).
6. Admin records an interview round (201).
7. Record offer: the trigger flips the student **Not Placed → Placed**.
8. Accept: offer becomes Accepted, `offer_history` = [Created, Accepted], student stays Placed. Accepting again is refused (409).
9. Decline a student's only offer: **Placed → Not Placed**. Acting on someone else's offer is refused (403).
10. Placement-probability: 200, p = 0.083 (backend → ML service).
11. Database rules: closed drive refused (PL002, 409), ineligible refused (PL001, 403), second accepted offer refused (PL003, 409).
12. `sp_close_drive` via the API rejected exactly the 37 pending applicants.
13. All 8 analytics GET endpoints → 200.

The throwaway database and the second backend were removed afterwards. The main backend, ML service, frontend and Postgres were left running.

---

## 3. Git / handoff state

- **Branch:** `main`
- **Last 10 commits:**
  ```
  a0b612c Add rule-enforcing triggers, audit log, close-drive procedure, window-function views and a materialized view
  1b22556 Merge pull request #1 from firetruckss/main
  e5175ab Fix review findings on the frontend redesign
  49fca3e Redesign PlaceIQ frontend UI UX
  c43ffcd Point README at the Oracle port and viva cheat sheet
  3ebce03 Add Oracle SQL*Plus schema port, difference doc, and viva cheat sheet
  2b371c7 Add minimal React/Vite frontend and fix a real date-serialization bug
  fae24d2 Add ML microservice for placement probability + backend integration
  85033fc Add admin analytics endpoints and update README API summary
  ccdae18 Add admin drive/application workflow and offer acceptance transaction demo
  ```
- **Uncommitted:** `db/demos/index_benchmark.py` (untracked), plus this file.
- **Remote:** `origin` → `https://github.com/The-Natri/PlaceIQ` (public). Local `main` is **1 commit ahead** of GitHub: `a0b612c` is not pushed.
- **Collaborators:** only `The-Natri` (admin). Teammate `firetruckss` is **not** a collaborator and has no pending invite. They contribute via their fork + pull requests, which worked for PR #1.
- **`.gitignore`:** present. Correctly ignores `.env`, `frontend/.env`, `ml-service/model/*.joblib`, `db/backups/`, `frontend/dist`, `node_modules`. ⚠️ The venv folders (`.venv-backend`, `.venv-db`, `.venv-ml`) are **not** matched by the root `.gitignore` (it only lists `.venv/` and `venv/`). They're currently ignored only because Python 3.13+ writes a `.gitignore` inside each venv; with an older Python they'd show up as committable.
- **Secrets:**
  - No `.env` file has ever been committed (checked full history).
  - No API keys, tokens or private keys appear in any commit.
  - **Committed, by design:** dev-only placeholder credentials. That's `POSTGRES_PASSWORD: placement_dev_password` in `docker-compose.yml`, `JWT_SECRET_KEY=change_this_secret_in_production` in `.env.example`, and the seed logins `Admin@123` / `Student@123` in `seed.py`.
  - ⚠️ The local `.env` still uses the **same JWT secret and DB URL as the public `.env.example`**. Anyone who reads the repo can forge a valid admin JWT for this running instance. Fine for a local demo; not for anything exposed to a network.

---

## 4. What's pending

### 4.1 Incomplete or known issues in the code
1. **Unpushed and uncommitted work.** Commit `a0b612c` isn't on GitHub, and `db/demos/index_benchmark.py` isn't committed. That script also prints an em-dash that shows up as `�` in the Windows console.
2. **The Oracle port is behind the Postgres schema.** It's missing the audit table and trigger, the 3 rule triggers, `sp_close_drive`, the 3 window-function views and the materialized view. Its `trg_offer_after_insert` also lacks the "skip Declined offers" guard added to the Postgres version. `oracle-differences.md` doesn't mention any of this.
3. **Offers can be recorded on applications in any state.** `record_offer` doesn't check the application's status, so an admin can record an offer on a **Rejected** application, and that silently changes it to Offer_Made. A DB rule or an API check should require Selected (or at least not Rejected).
4. **Admin status changes allow any transition.** `PUT /applications/:id/status`, for example, allows Rejected → Applied. There's no state machine.
5. **Students set their own CGPA and backlogs at signup**, and those numbers drive eligibility, the DB rules and the ML score. Nothing marks them as verified by the placement cell.
6. **The live DB has leftover test data** (§1.6). Reseed before any demo.
7. **The saved ML model is stale.** It was trained 12 Sep on the old seed. Retrain it (`python ml-service/train.py`) and update the figure quoted in the README.
8. **No automated tests.** Everything was verified with scripts run by hand, which are not in the repo.
9. **Debug mode is on** (`FLASK_ENV=development`) and **CORS allows any origin**. Fine locally, but both should change before anything is exposed.
10. No TODO/FIXME markers were found anywhere in the code.

### 4.2 Missing report deliverables
| Deliverable | Status |
|---|---|
| ER diagram as an image | ❌ Mermaid text only; needs exporting to PNG/SVG (e.g. mermaid.live), and the diagram itself is missing `application_status_history` |
| Query output screenshots / sample outputs | ❌ None in the repo. The index benchmark produced real timings (with indexes: 0.45 ms vs 38.9 ms for applicants-per-drive, about 86×), but they were never saved to a doc. |
| SQL*Plus demo script | ❌ Only the DDL (`schema_oracle.sql`) exists. There's no script that runs the demo queries, calls the functions and shows the trigger firing for the report. |
| Viva cheat sheet | ⚠️ Exists but doesn't cover the newest database features |

### 4.3 Gaps in the frontend handoff
- **No API contract doc.** The README summary lacks request/response shapes, error codes and the newer endpoints. Your teammate would have to read the Flask routes.
- **Nine backend endpoints have no UI** (§1.5): close drive, edit drive, ranking/timeline/matrix analytics, status history, CGPA percentile, admin student list.
- **No CGPA-vs-outcome chart.** The original brief asked for a chart; the page shows a banded table.
- **Setup steps for the teammate.** The README's quick start works, but it assumes Windows paths (`.venv-*/Scripts/`) and doesn't mention that `npm install` is needed after pulling (for `lucide-react`) or how to point the frontend at a different backend (`frontend/.env`, `VITE_API_URL`).
- **CORS/env:** CORS is wide open, so a frontend on any port works. `VITE_API_URL` defaults to `http://localhost:5000/api`.

### 4.4 What I'd fix or add before submission (in priority order)
1. Commit `index_benchmark.py`, save its results to a doc, then push.
2. Reseed the live DB and retrain the ML model; update the AUC figure in the README.
3. Bring the docs up to date: README, ER diagram + exported image, normalization (new table), viva cheat sheet.
4. Port Sections 6–10 to `schema_oracle.sql` and re-run it on Oracle, if the professor will grade the SQL*Plus version.
5. Add a SQL*Plus demo script with saved sample output for the report.
6. Write `docs/API.md` for the teammate.
7. Block offers on Rejected applications (DB rule, PL006).
8. Fix the `.gitignore` venv pattern (`.venv*/`).
9. Add the UI for close drive, status history and the CGPA chart (teammate's call on design).

---

## 5. Viva readiness: know these line by line

| # | What | Where | Why it matters |
|---|---|---|---|
| 1 | Placement trigger and the two rule triggers | `db/schema.sql`: `trg_fn_offer_insert_update_placement` (line 277), `trg_fn_application_guard` (466), `trg_fn_offer_single_acceptance` (511) | Row-level AFTER vs BEFORE triggers, `NEW`/`OLD`, `RAISE … USING ERRCODE`, and why the `FOR UPDATE` lock is needed under concurrency |
| 2 | Eligibility function | `db/schema.sql`: `fn_check_eligibility` (line 316), `fn_get_eligible_drives` (379) | Stored function, `SELECT INTO` + `FOUND`, "no rows = open to all departments"; the Oracle version's `NO_DATA_FOUND` difference |
| 3 | Offer accept/decline transaction | `backend/services/offer_service.py`: `accept_offer` (line 65), `decline_offer` (118) | ACID, explicit commit/rollback, the conditional `UPDATE … WHERE status='Pending' RETURNING` guard, and why decline must check remaining offers inside the same transaction |
| 4 | Close-drive procedure | `db/schema.sql`: `sp_close_drive` (line 604) | PROCEDURE vs FUNCTION, `CALL`, `INOUT`, `GET DIAGNOSTICS ROW_COUNT`, and how the audit trigger fires for every row it updates |
| 5 | Core tables and normalization | `db/schema.sql` Section 1 (from line 32): `application`, `offer`, `drive_eligible_dept`; `docs/normalization.md` | M:N resolution, 1:0..1 via UNIQUE FK, CHECK constraints, and the one deliberate denormalization (`placement_status`) |

Backups worth reading once: `backend/db.py` `get_cursor` (line 42), `db/seed.py` `selection_probability` (line 144), and the window-function views in `db/schema.sql` Section 9 (line 638).
