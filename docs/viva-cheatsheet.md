# Viva Cheat Sheet

One line per row, short enough to say out loud in one breath. Skim this right
before you walk in.

| Feature | Where in code | DBMS concept it proves | Why I built it this way |
|---|---|---|---|
| `placement_status` auto-updates on offer insert | `db/schema.sql` §3, `trg_offer_after_insert` | Row-level AFTER INSERT trigger | So a student's placement status can never drift out of sync with reality — it's set by the database itself the instant an offer exists, not by whichever app code happened to remember to update it. |
| `fn_check_eligibility(student_id, drive_id)` | `db/schema.sql` §4 | Stored function, single source of truth for business logic | Eligibility has to mean the same thing everywhere it's checked, so I put the rule in the database once instead of reimplementing it in Python and risking the two falling out of sync. |
| `fn_get_eligible_drives(student_id)` | `db/schema.sql` §4 | Stored function returning a set, reused by the backend | Lets the backend get a student's whole eligible-drives list in one query instead of looping `fn_check_eligibility()` per drive in application code. |
| `placed_students_view`, `company_wise_stats_view`, `department_stats_view` | `db/schema.sql` §5 | Views for abstraction and reuse | Every analytics/dashboard query that needs these joins hits the view instead of re-deriving the same multi-table join in every route file. |
| Offer accept/decline transaction | `backend/services/offer_service.py` | Explicit multi-statement transaction with commit/rollback (ACID) | The spec wanted a *visible* transaction, not one hidden behind an ORM's autocommit, so I wrote raw psycopg2 with an explicit `try / conn.commit() / except / conn.rollback()` block updating Offer, Student, and Offer_History together. |
| 5 indexes on `dept_id`, `cgpa`, `application.status`, `application.drive_id`, `drive.company_id` | `db/schema.sql` §2 | Query optimization on high-traffic filter columns | Each one maps to a specific hot-path query (eligibility checks, admin filtering by drive/status) — I indexed what's actually queried, not everything "just in case." |
| `Application` junction table | `db/schema.sql` §1 | Relational resolution of an M:N relationship | A student applies to many drives and a drive gets many applicants, so the relationship needed its own table with its own attributes (`status`, `applied_at`) rather than trying to force it into either side. |
| Normalization (3NF) | `docs/normalization.md` | Elimination of transitive/partial functional dependencies | Split out `department` and `company` as their own tables so facts like `dept_name` and `industry_sector` live in exactly one row each, instead of being copied onto every student/drive row and risking update anomalies. |
| Raw psycopg2, no ORM | `backend/db.py` | Deliberate SQL visibility over convenience | An ORM would auto-generate the queries — the whole point of this project is the SQL itself, so every query needed to be plain, visible, and something I can point at and explain, not hidden behind an abstraction layer. |

## Backup one-liners (if asked to go deeper)

- **Why is `placement_status` on `student` even though it's derivable from `offer`?** Deliberate, documented denormalization — required by the trigger, and it saves a 4-table join on the dashboard's most common read. See `docs/normalization.md`.
- **Why does declining an offer sometimes flip `placement_status` back to `'Not Placed'`?** The trigger only ever turns it ON (on offer insert); `offer_service.decline_offer()` is what turns it back OFF, but only if the student has no other Pending/Accepted offer — a check-then-act that has to happen inside the same transaction.
- **Why junction tables for `student_skill` and `drive_eligible_dept` too?** Same M:N reasoning as `Application` — a comma-separated column would violate 1NF and make `COUNT(*)`-style queries (skill count for the ML model, eligible-department lookups) unreliable string parsing instead of real SQL.
- **Why generate the dataset instead of using real placement data?** No real student data exists for this course, and the ML model needs a *correlated* dataset, not a random one — `db/seed.py` deliberately makes CGPA/backlogs predictive of outcome so the model has real signal (see the big comment at the top of that file).
