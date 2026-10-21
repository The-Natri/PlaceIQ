# PlaceIQ API Reference

Everything the frontend can call. Every endpoint here was exercised against
the running backend, including each listed error code:
`tests/api_contract_check.py` reads **this file** and checks it against the
real backend, so if the doc and the code drift apart that check fails. Run it
with:

```bash
bash tests/run_smoke_test.sh tests/api_contract_check.py
```

## Basics

| | |
|---|---|
| Base URL | `http://127.0.0.1:5000/api` (dev). The frontend reads it from `VITE_API_URL` in `frontend/.env`. |
| Format | JSON in, JSON out. Send `Content-Type: application/json` with a body. |
| Auth | `Authorization: Bearer <token>`. Get a token from one of the login endpoints; it expires after 12 hours. |
| Errors | Always `{"error": "human-readable message"}` with the status code below. |
| CORS | Only origins listed in `FRONTEND_ORIGINS` (root `.env`) may call the API from a browser. |

**Roles** used in the "Auth" lines:
- **Public**: no token needed.
- **Any logged-in user**: any valid token.
- **Student**: only student tokens.
- **Admin**: only coordinator/TPO tokens.
- **Self or admin**: a student may only access their *own* record; an admin may access any.

**Status codes used everywhere:**

| Code | Meaning |
|---|---|
| `401` | No token, a malformed token, or an expired token |
| `403` | Wrong role, or a student touching someone else's record, or a database rule refusing an action (not eligible) |
| `404` | The id in the URL doesn't exist |
| `409` | A database rule or uniqueness constraint refused the change (closed drive, duplicate, illegal status move, …) |

**Value types to watch for:**
- Database `NUMERIC` values come back as **strings**, to keep them exact: `cgpa`, `min_cgpa`, `package_lpa`, `offered_package_lpa`, `avg_package_lpa`, `max_package_lpa`, `min_package_lpa`, `placement_percentage`, `cgpa_percentile_in_dept`, `cumulative_offers`. Convert them with `Number(x)` before doing maths.
- Dates are ISO 8601: `"2026-02-13"` for dates, `"2026-10-21T12:00:48.226639"` for timestamps.
- Empty optional values are `null`.

**Getting tokens for the curl examples below** (seeded accounts):

```bash
API=http://127.0.0.1:5000/api
ADMIN_TOKEN=$(curl -s -X POST $API/auth/admin/login -H "Content-Type: application/json" \
  -d '{"email":"tpo@campus.edu","password":"Admin@123"}' | python -c "import sys,json;print(json.load(sys.stdin)['token'])")
STUDENT_TOKEN=$(curl -s -X POST $API/auth/student/login -H "Content-Type: application/json" \
  -d '{"email":"aarav.chatterjee15cse@campus.edu","password":"Student@123"}' | python -c "import sys,json;print(json.load(sys.stdin)['token'])")
```

That student's `student_id` is `15`. Ids in the examples are illustrative; use real ones from your data.

---

## Health

### `GET /api/health`
Checks the API is up and can reach the database.
- **Auth:** Public
- **Request:** none
- **Success:** `200`
- **Response fields:** `status`
- **Errors:** none
- **Example:**
  ```bash
  curl -s $API/health
  ```

---

## Auth

### `POST /api/auth/student/signup`
Creates a student account (password hashed with bcrypt) and logs it in.
- **Auth:** Public
- **Request:** `reg_no`, `name`, `email`, `password` (min 6 chars), `dept_id`, `cgpa` (0–10), `backlogs` (≥ 0), `batch_year` (2000–2100); optional `phone`
- **Success:** `201`
- **Response fields:** `token`, `user`
- **Nested:** `user` has student_id, reg_no, name, email, dept_id, cgpa, backlogs, batch_year, placement_status
- **Errors:** `400` missing field, short password, unknown dept_id or out-of-range value; `409` reg_no or email already registered
- **Example:**
  ```bash
  curl -s -X POST $API/auth/student/signup -H "Content-Type: application/json" -d '{"reg_no":"CSE2025999","name":"Test Student","email":"test.student@campus.edu","password":"Secret123","dept_id":1,"cgpa":8.2,"backlogs":0,"batch_year":2025}'
  ```

### `POST /api/auth/student/login`
- **Auth:** Public
- **Request:** `email`, `password`
- **Success:** `200`
- **Response fields:** `token`, `user`
- **Nested:** `user` has student_id, name, email, placement_status
- **Errors:** `400` email or password missing; `401` wrong email or password (same message for both, so it doesn't reveal which emails exist)
- **Example:**
  ```bash
  curl -s -X POST $API/auth/student/login -H "Content-Type: application/json" -d '{"email":"aarav.chatterjee15cse@campus.edu","password":"Student@123"}'
  ```

### `POST /api/auth/admin/login`
- **Auth:** Public
- **Request:** `email`, `password`
- **Success:** `200`
- **Response fields:** `token`, `user`
- **Nested:** `user` has coordinator_id, name, email, role (`TPO` or `Coordinator`)
- **Errors:** `400` email or password missing; `401` wrong email or password
- **Example:**
  ```bash
  curl -s -X POST $API/auth/admin/login -H "Content-Type: application/json" -d '{"email":"tpo@campus.edu","password":"Admin@123"}'
  ```

### `GET /api/auth/me`
Who the token belongs to; the frontend uses this to restore a session on page load.
- **Auth:** Any logged-in user
- **Request:** none
- **Success:** `200`
- **Response fields:** `profile`, `role`
- **Nested:** `role` is `student` or `admin`. For a student, `profile` has student_id, reg_no, name, email, cgpa, backlogs, batch_year, phone, placement_status, dept_name, dept_code; for an admin, coordinator_id, name, email, role.
- **Errors:** `401` missing or invalid token
- **Example:**
  ```bash
  curl -s $API/auth/me -H "Authorization: Bearer $STUDENT_TOKEN"
  ```

---

## Reference data

### `GET /api/departments`
All departments, for dropdowns (public so the signup form can use it).
- **Auth:** Public
- **Request:** none
- **Success:** `200` (a list)
- **Response fields:** `dept_code`, `dept_id`, `dept_name`
- **Errors:** none
- **Example:**
  ```bash
  curl -s $API/departments
  ```

### `GET /api/companies`
- **Auth:** Any logged-in user
- **Request:** none
- **Success:** `200` (a list)
- **Response fields:** `company_id`, `company_name`, `hr_email`, `industry_sector`, `website`
- **Errors:** `401` missing or invalid token
- **Example:**
  ```bash
  curl -s $API/companies -H "Authorization: Bearer $STUDENT_TOKEN"
  ```

### `GET /api/companies/:id`
One company and all its drives (newest first).
- **Auth:** Any logged-in user
- **Request:** none
- **Success:** `200`
- **Response fields:** `company_id`, `company_name`, `drives`, `hr_email`, `industry_sector`, `website`
- **Nested:** each item in `drives` has drive_id, job_role, drive_date, package_lpa, status, drive_type
- **Errors:** `401` missing or invalid token; `404` no such company
- **Example:**
  ```bash
  curl -s $API/companies/1 -H "Authorization: Bearer $STUDENT_TOKEN"
  ```

---

## Students

### `GET /api/students`
All students, optionally filtered.
- **Auth:** Admin
- **Request:** optional query parameters `dept_id`, `min_cgpa`, `placement_status` (`Placed` / `Not Placed`)
- **Success:** `200` (a list)
- **Response fields:** `backlogs`, `batch_year`, `cgpa`, `dept_code`, `dept_name`, `email`, `name`, `placement_status`, `reg_no`, `student_id`
- **Errors:** `401` missing or invalid token; `403` not an admin
- **Example:**
  ```bash
  curl -s "$API/students?dept_id=1&min_cgpa=8" -H "Authorization: Bearer $ADMIN_TOKEN"
  ```

### `GET /api/students/:id`
Full profile, skills, and where the student's CGPA stands in their department (from the window-function view `student_cgpa_standing_view`).
- **Auth:** Self or admin
- **Request:** none
- **Success:** `200`
- **Response fields:** `backlogs`, `batch_year`, `cgpa`, `cgpa_standing`, `created_at`, `dept_code`, `dept_id`, `dept_name`, `email`, `name`, `phone`, `placement_status`, `reg_no`, `skills`, `student_id`
- **Nested:** `skills` items have skill_id, skill_name. `cgpa_standing` has cgpa_rank_in_dept (1 = highest), dept_size, cgpa_percentile_in_dept (0 = lowest in dept, 100 = highest).
- **Errors:** `401` missing or invalid token; `403` another student's record; `404` no such student
- **Example:**
  ```bash
  curl -s $API/students/15 -H "Authorization: Bearer $STUDENT_TOKEN"
  ```

### `GET /api/students/:id/eligible-drives`
Open drives (Upcoming or Ongoing) this student is eligible for, computed by the database function `fn_get_eligible_drives`.
- **Auth:** Self or admin
- **Request:** none
- **Success:** `200` (a list)
- **Response fields:** `company_name`, `drive_date`, `drive_id`, `drive_type`, `job_role`, `max_backlogs`, `min_cgpa`, `package_lpa`, `status`
- **Errors:** `401` missing or invalid token; `403` another student's record
- **Example:**
  ```bash
  curl -s $API/students/15/eligible-drives -H "Authorization: Bearer $STUDENT_TOKEN"
  ```

### `GET /api/students/:id/applications`
The student's application tracker (newest first).
- **Auth:** Self or admin
- **Request:** none
- **Success:** `200` (a list)
- **Response fields:** `application_id`, `applied_at`, `company_name`, `drive_date`, `drive_id`, `job_role`, `package_lpa`, `status`
- **Errors:** `401` missing or invalid token; `403` another student's record
- **Example:**
  ```bash
  curl -s $API/students/15/applications -H "Authorization: Bearer $STUDENT_TOKEN"
  ```

### `GET /api/students/:id/placement-probability`
The ML model's estimate (0 to 1) that this student gets placed, based on CGPA, backlogs, department and skill count. The backend reads the student's data and asks the ML service.
- **Auth:** Self or admin
- **Request:** none
- **Success:** `200`
- **Response fields:** `placement_probability`
- **Errors:** `401` missing or invalid token; `403` another student's record; `404` no such student
- **Also:** `503` with `{"error": "ML service is currently unavailable"}` when the ML service can't be reached. The checker can't reproduce that, so it was verified separately with the ML service stopped (`docs/evidence/raw/api-503-check.txt`).
- **Example:**
  ```bash
  curl -s $API/students/15/placement-probability -H "Authorization: Bearer $STUDENT_TOKEN"
  ```

---

## Drives

### `GET /api/drives`
All drives, newest first.
- **Auth:** Any logged-in user
- **Request:** optional query parameter `status` (`Upcoming`, `Ongoing`, `Completed`, `Cancelled`)
- **Success:** `200` (a list)
- **Response fields:** `company_id`, `company_name`, `drive_date`, `drive_id`, `drive_type`, `job_role`, `max_backlogs`, `min_cgpa`, `package_lpa`, `status`
- **Errors:** `401` missing or invalid token
- **Example:**
  ```bash
  curl -s "$API/drives?status=Ongoing" -H "Authorization: Bearer $STUDENT_TOKEN"
  ```

### `GET /api/drives/:id`
One drive with the departments it is restricted to.
- **Auth:** Any logged-in user
- **Request:** none
- **Success:** `200`
- **Response fields:** `company_id`, `company_name`, `created_at`, `drive_date`, `drive_id`, `drive_type`, `eligible_departments`, `industry_sector`, `job_role`, `max_backlogs`, `min_cgpa`, `package_lpa`, `status`
- **Nested:** `eligible_departments` items have dept_id, dept_name, dept_code. **An empty list means the drive is open to all departments.**
- **Errors:** `401` missing or invalid token; `404` no such drive
- **Example:**
  ```bash
  curl -s $API/drives/8 -H "Authorization: Bearer $STUDENT_TOKEN"
  ```

### `POST /api/drives`
Creates a drive and its department restrictions in one transaction.
- **Auth:** Admin
- **Request:** required `company_id`, `job_role`, `drive_date` (YYYY-MM-DD), `package_lpa`, `min_cgpa`, `max_backlogs`; optional `drive_type` (`Full-Time` default, or `Internship`), `status` (`Upcoming` default), `eligible_dept_ids` (list; empty or omitted = open to all)
- **Success:** `201`
- **Response fields:** `drive_id`
- **Errors:** `400` missing field, unknown company or department, or out-of-range value; `401` missing or invalid token; `403` not an admin
- **Example:**
  ```bash
  curl -s -X POST $API/drives -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" -d '{"company_id":1,"job_role":"Backend Developer","drive_date":"2026-03-01","package_lpa":12.5,"min_cgpa":7.5,"max_backlogs":0,"eligible_dept_ids":[1,2]}'
  ```

### `PUT /api/drives/:id`
Edits a drive. Send only what changes. Sending `eligible_dept_ids` replaces the whole restriction list (`[]` = open to all).
- **Auth:** Admin
- **Request:** any of `job_role`, `drive_date`, `package_lpa`, `min_cgpa`, `max_backlogs`, `drive_type`, `status`, `eligible_dept_ids`
- **Success:** `200`
- **Response fields:** `drive_id`, `updated`
- **Errors:** `400` no editable field sent, or an invalid value or department; `401` missing or invalid token; `403` not an admin; `404` no such drive
- **Example:**
  ```bash
  curl -s -X PUT $API/drives/8 -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" -d '{"package_lpa":15.0,"status":"Ongoing"}'
  ```

### `POST /api/drives/:id/close`
Closes a drive by calling the stored procedure `sp_close_drive`. It marks the drive Completed and rejects every applicant still at Applied, Shortlisted or Interview_Scheduled, in one transaction. Selected and Offer_Made applicants are left alone.
- **Auth:** Admin
- **Request:** none
- **Success:** `200`
- **Response fields:** `drive_id`, `rejected_count`, `status`
- **Errors:** `401` missing or invalid token; `403` not an admin; `404` no such drive; `409` drive already Completed or Cancelled
- **Example:**
  ```bash
  curl -s -X POST $API/drives/8/close -H "Authorization: Bearer $ADMIN_TOKEN"
  ```

### `GET /api/drives/:id/applicants`
Everyone who applied to a drive, for shortlisting.
- **Auth:** Admin
- **Request:** none
- **Success:** `200` (a list)
- **Response fields:** `application_id`, `applied_at`, `backlogs`, `cgpa`, `dept_name`, `name`, `reg_no`, `status`, `student_id`
- **Errors:** `401` missing or invalid token; `403` not an admin
- **Example:**
  ```bash
  curl -s $API/drives/8/applicants -H "Authorization: Bearer $ADMIN_TOKEN"
  ```

---

## Applications

Status moves only forward (enforced by a database trigger; an illegal move returns `409`):

| From | Allowed to |
|---|---|
| Applied | Shortlisted, Interview_Scheduled, Rejected |
| Shortlisted | Interview_Scheduled, Selected, Rejected |
| Interview_Scheduled | Selected, Rejected |
| Selected | Offer_Made (set automatically by recording an offer), Rejected |
| Offer_Made, Rejected | final |

### `POST /api/applications`
The logged-in student applies to a drive. The database checks eligibility and that the drive is open.
- **Auth:** Student
- **Request:** `drive_id`
- **Success:** `201`
- **Response fields:** `application_id`, `applied_at`, `status`
- **Errors:** `400` drive_id missing or unknown; `401` missing or invalid token; `403` not eligible for this drive (or not a student token); `409` already applied, or the drive is Completed or Cancelled
- **Example:**
  ```bash
  curl -s -X POST $API/applications -H "Authorization: Bearer $STUDENT_TOKEN" -H "Content-Type: application/json" -d '{"drive_id":24}'
  ```

### `GET /api/applications/:id`
One application with its interview rounds, offer (or `null`), and full status history (written by the database's audit trigger).
- **Auth:** Self or admin
- **Request:** none
- **Success:** `200`
- **Response fields:** `application_id`, `applied_at`, `company_name`, `drive_date`, `drive_id`, `interview_rounds`, `job_role`, `offer`, `package_lpa`, `status`, `status_history`, `student_id`
- **Nested:**
  - `interview_rounds` items have round_id, round_number, round_type, round_date, result, remarks.
  - `offer` is `null` or has offer_id, offered_package_lpa, offer_date, status, joining_date.
  - `status_history` items have old_status, new_status, changed_at (oldest first).
- **Errors:** `401` missing or invalid token; `403` another student's application; `404` no such application
- **Example:**
  ```bash
  curl -s $API/applications/120 -H "Authorization: Bearer $STUDENT_TOKEN"
  ```

### `PUT /api/applications/:id/status`
Moves an application along the pipeline (see the table above).
- **Auth:** Admin
- **Request:** `status`, one of `Applied`, `Shortlisted`, `Interview_Scheduled`, `Selected`, `Rejected` (`Offer_Made` is set only by recording an offer)
- **Success:** `200`
- **Response fields:** `application_id`, `status`
- **Errors:** `400` status not in that list; `401` missing or invalid token; `403` not an admin; `404` no such application; `409` illegal move (e.g. Rejected → Applied)
- **Example:**
  ```bash
  curl -s -X PUT $API/applications/120/status -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" -d '{"status":"Shortlisted"}'
  ```

### `POST /api/applications/:id/interview-rounds`
Records one interview round.
- **Auth:** Admin
- **Request:** required `round_number`, `round_type` (`Aptitude`, `Technical`, `HR`, `Group_Discussion`, `Coding_Test`); optional `round_date`, `result` (`Pass`, `Fail`, `Pending` default), `remarks`
- **Success:** `201`
- **Response fields:** `round_id`
- **Errors:** `400` missing round_number, invalid round_type, or unknown application; `401` missing or invalid token; `403` not an admin; `409` that round_number already exists for this application
- **Example:**
  ```bash
  curl -s -X POST $API/applications/120/interview-rounds -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" -d '{"round_number":1,"round_type":"Technical","result":"Pass"}'
  ```

### `POST /api/applications/:id/offer`
Records an offer for a **Selected** application. Recording it:
- inserts the offer as Pending;
- logs it in the offer history;
- moves the application to Offer_Made;
- fires the database trigger that marks the student Placed.
- **Auth:** Admin
- **Request:** required `offered_package_lpa`; optional `offer_date` (defaults to today)
- **Success:** `201`
- **Response fields:** `application_id`, `offer_date`, `offer_id`, `offered_package_lpa`, `status`
- **Errors:** `400` offered_package_lpa missing; `401` missing or invalid token; `403` not an admin; `404` no such application; `409` the application isn't Selected, or it already has an offer
- **Example:**
  ```bash
  curl -s -X POST $API/applications/120/offer -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" -d '{"offered_package_lpa":9.5}'
  ```

---

## Offers

### `GET /api/offers/:id`
- **Auth:** Self or admin
- **Request:** none
- **Success:** `200`
- **Response fields:** `application_id`, `company_name`, `job_role`, `joining_date`, `offer_date`, `offer_id`, `offered_package_lpa`, `status`, `student_id`
- **Errors:** `401` missing or invalid token; `403` another student's offer; `404` no such offer
- **Example:**
  ```bash
  curl -s $API/offers/178 -H "Authorization: Bearer $STUDENT_TOKEN"
  ```

### `POST /api/offers/:id/accept`
Accepts a Pending offer in one explicit database transaction (`backend/services/offer_service.py`). It:
- marks the offer Accepted and sets a joining date;
- makes sure the student is Placed;
- logs the acceptance in the offer history.

All three happen together or not at all.
- **Auth:** Self or admin
- **Request:** none
- **Success:** `200`
- **Response fields:** `offer_id`, `status`
- **Errors:** `401` missing or invalid token; `403` another student's offer; `404` no such offer; `409` the offer isn't Pending, or the student has already accepted a different offer
- **Example:**
  ```bash
  curl -s -X POST $API/offers/178/accept -H "Authorization: Bearer $STUDENT_TOKEN"
  ```

### `POST /api/offers/:id/decline`
Declines a Pending offer in one transaction. If it was the student's last Pending or Accepted offer, the student goes back to Not Placed.
- **Auth:** Self or admin
- **Request:** none
- **Success:** `200`
- **Response fields:** `offer_id`, `status`
- **Errors:** `401` missing or invalid token; `403` another student's offer; `404` no such offer; `409` the offer isn't Pending
- **Example:**
  ```bash
  curl -s -X POST $API/offers/178/decline -H "Authorization: Bearer $STUDENT_TOKEN"
  ```

---

## Analytics (admin only)

### `GET /api/analytics/overview`
Headline numbers for the analytics page.
- **Auth:** Admin
- **Request:** none
- **Success:** `200`
- **Response fields:** `accepted_offers`, `overall_placement_pct`, `placed_students`, `total_companies`, `total_drives`, `total_offers`, `total_students`
- **Errors:** `401` missing or invalid token; `403` not an admin
- **Example:**
  ```bash
  curl -s $API/analytics/overview -H "Authorization: Bearer $ADMIN_TOKEN"
  ```

### `GET /api/analytics/department-stats`
Placement % per department (from `department_stats_view`).
- **Auth:** Admin
- **Request:** none
- **Success:** `200` (a list)
- **Response fields:** `dept_id`, `dept_name`, `placed_students`, `placement_percentage`, `total_students`
- **Errors:** `401` missing or invalid token; `403` not an admin
- **Example:**
  ```bash
  curl -s $API/analytics/department-stats -H "Authorization: Bearer $ADMIN_TOKEN"
  ```

### `GET /api/analytics/company-stats`
Offers and package range per company (from `company_wise_stats_view`), most offers first.
- **Auth:** Admin
- **Request:** optional query parameter `top` (only the first N companies)
- **Success:** `200` (a list)
- **Response fields:** `avg_package_lpa`, `company_id`, `company_name`, `max_package_lpa`, `min_package_lpa`, `offers_count`
- **Errors:** `401` missing or invalid token; `403` not an admin
- **Example:**
  ```bash
  curl -s "$API/analytics/company-stats?top=5" -H "Authorization: Bearer $ADMIN_TOKEN"
  ```

### `GET /api/analytics/package-by-branch`
Average, highest and lowest offered package per department.
- **Auth:** Admin
- **Request:** none
- **Success:** `200` (a list)
- **Response fields:** `avg_package_lpa`, `dept_name`, `max_package_lpa`, `min_package_lpa`, `offers_count`
- **Errors:** `401` missing or invalid token; `403` not an admin
- **Example:**
  ```bash
  curl -s $API/analytics/package-by-branch -H "Authorization: Bearer $ADMIN_TOKEN"
  ```

### `GET /api/analytics/cgpa-vs-outcome`
One point per student, for the CGPA-vs-placement chart.
- **Auth:** Admin
- **Request:** none
- **Success:** `200` (a list)
- **Response fields:** `backlogs`, `cgpa`, `dept_id`, `placement_status`, `student_id`
- **Errors:** `401` missing or invalid token; `403` not an admin
- **Example:**
  ```bash
  curl -s $API/analytics/cgpa-vs-outcome -H "Authorization: Bearer $ADMIN_TOKEN"
  ```

### `GET /api/analytics/top-offers-per-dept`
The best offers in each department, ranked with `RANK()` (ties share a rank).
- **Auth:** Admin
- **Request:** optional query parameter `n` (top N per department, default 3)
- **Success:** `200` (a list)
- **Response fields:** `company_name`, `dept_name`, `name`, `offered_package_lpa`, `rank_in_dept`, `reg_no`
- **Errors:** `401` missing or invalid token; `403` not an admin
- **Example:**
  ```bash
  curl -s "$API/analytics/top-offers-per-dept?n=3" -H "Authorization: Bearer $ADMIN_TOKEN"
  ```

### `GET /api/analytics/placement-timeline`
Offers per month with a running total, from window functions. Every month from the first offer to the last is listed, and a month with no offers has `offers_in_month` 0, so `change_from_prev_month` always compares consecutive calendar months. It is `null` for the first month.
- **Auth:** Admin
- **Request:** none
- **Success:** `200` (a list)
- **Response fields:** `change_from_prev_month`, `cumulative_offers`, `month`, `offers_in_month`
- **Errors:** `401` missing or invalid token; `403` not an admin
- **Example:**
  ```bash
  curl -s $API/analytics/placement-timeline -H "Authorization: Bearer $ADMIN_TOKEN"
  ```

### `GET /api/analytics/company-dept-matrix`
Offers per company × department, read from a **materialized view**. It's a stored snapshot, so it doesn't change until refreshed; `refreshed_at` says how old it is.
- **Auth:** Admin
- **Request:** none
- **Success:** `200`
- **Response fields:** `cells`, `refreshed_at`
- **Nested:** `cells` items have company_name, dept_name, offers_count, avg_package_lpa
- **Errors:** `401` missing or invalid token; `403` not an admin
- **Example:**
  ```bash
  curl -s $API/analytics/company-dept-matrix -H "Authorization: Bearer $ADMIN_TOKEN"
  ```

### `POST /api/analytics/refresh-matrix`
Rebuilds the matrix snapshot (`REFRESH MATERIALIZED VIEW CONCURRENTLY`, so readers aren't blocked while it runs).
- **Auth:** Admin
- **Request:** none
- **Success:** `200`
- **Response fields:** `refreshed_at`
- **Errors:** `401` missing or invalid token; `403` not an admin
- **Example:**
  ```bash
  curl -s -X POST $API/analytics/refresh-matrix -H "Authorization: Bearer $ADMIN_TOKEN"
  ```
