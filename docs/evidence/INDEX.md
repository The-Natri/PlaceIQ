# Evidence index

Everything in this folder is **real output** from the running system: psql,
SQL*Plus, the backend's HTTP responses, the training script, the benchmark and
browser screenshots. The prose around each output block was written by hand.
The outputs themselves were pasted unedited, and every one can be regenerated
with the script named beside it.

Collected on 21 Oct 2026 against the final code (`main` + the `frontend-polish`
UI) and a freshly seeded database (180 students, 25 drives, 517 applications,
177 offers, 95 placed).

Report sections: **§2 Modules** (Implementation and Experimental Setup),
**§3 Results and Discussion**, **Appendix**.

## Files

| File | What it shows | Report section | Regenerate with |
|---|---|---|---|
| `er-diagram.png` | ER diagram of all 13 tables, rendered from the Mermaid source in `docs/er-diagram.md` | §2 (schema design) | `scripts/render_er.js` |
| `schema-summary.md` | Every table's columns, types, nullability, defaults and constraints (PK, FK with ON DELETE, UNIQUE, CHECK); every index, trigger, function, procedure and view, read from the system catalog | §2; Appendix | `scripts/build_sql_evidence.py` |
| `queries.md` | All 6 views and the materialized view (with a refresh), `fn_check_eligibility` (one eligible case and three ineligible ones), `fn_get_eligible_drives`, placement % per department, package stats per company and per branch, top recruiters, `sp_close_drive` before/after | §3 | `scripts/build_sql_evidence.py` |
| `triggers.md` | Each trigger fired by a real statement: placement-status trigger; application guard (PL001 not eligible, PL002 drive closed); second-offer guard (PL003); offer-on-rejected guard (PL006); status-transition guard (PL007); status audit trigger; the seed's full audit trail | §3 | `scripts/build_sql_evidence.py` |
| `transaction.md` | The offer accept and decline transactions run through the real backend, with `placement_status` and history before and after; a refused acceptance rolled back; two simultaneous acceptances serialized by the row lock | §3 | `bash tests/run_smoke_test.sh tests/transaction_evidence.py` |
| `transaction-sql.md` | The same accept transaction statement by statement in psql: all three writes undone by `ROLLBACK`, then a forced CHECK failure that aborts the whole transaction | §3 | `scripts/build_sql_evidence.py` |
| `index-benchmark.md` | Median timings with and without the 5 indexes on 250,000 applications, with full `EXPLAIN (ANALYZE, BUFFERS)` plans | §3 | `python db/demos/index_benchmark.py` |
| `ml-results.md` | Training output (accuracy, ROC-AUC, confusion matrix, coefficients), derived precision/recall, honest caveats, sample `/predict` requests and responses | §3 | `python ml-service/train.py` |
| `smoke-test.md` | Final end-to-end run: 41/41 checks through the API and directly against the database | §3 | `bash tests/run_smoke_test.sh` |
| `sqlplus-transcript.txt` | One complete Oracle 21c XE SQL*Plus session: schema (82 objects, all VALID, no errors), demo data, every rule trigger raising its ORA-200xx error, views, procedure, transaction, MV | §2 (Oracle port); Appendix | `sqlplus /nolog @db/oracle_full_run.sql` |
| `screenshots/01-login.png` | Login page | §2 (UI); Appendix | `scripts/capture_screenshots.js` |
| `screenshots/02-student-dashboard.png` | Student dashboard: profile, CGPA standing (window function), probability | §2; §3 | ″ |
| `screenshots/03-probability-widget.png` | Placement-probability card with its explanation | §3 (ML) | ″ |
| `screenshots/04-eligible-drives.png` | Drives from `fn_get_eligible_drives` | §2 | ″ |
| `screenshots/05-application-tracker.png` | A student's applications in five different states | §2 | ″ |
| `screenshots/06-application-detail.png` | One application: offer, interview rounds, status history written by the audit trigger | §2; §3 | ″ |
| `screenshots/07-admin-dashboard.png` | Admin drive list | §2 | ″ |
| `screenshots/08-drive-detail-applicants.png` | Drive detail with applicants, status moves, close-drive button | §2 | ″ |
| `screenshots/09-admin-students.png` | Admin student list | Appendix | ″ |
| `screenshots/10-analytics-overview.png` | Placement % by department, CGPA vs outcome scatter | §3 | ″ |
| `screenshots/11-analytics-recruiters.png` | Recruiters and packages | §3 | ″ |
| `screenshots/12-analytics-rankings.png` | Top offers per department (`RANK()`) | §3 | ″ |
| `screenshots/13-analytics-timeline.png` | Offers per month and running total (`SUM OVER`, `LAG`) | §3 | ″ |
| `screenshots/14-analytics-matrix.png` | Company × department heatmap from the materialized view | §3 | ″ |

## Raw output (`raw/`)

| File | What it is |
|---|---|
| `raw/ml-training-output.txt` | stdout of `ml-service/train.py` |
| `raw/ml-predict-samples.txt` | curl calls to the ML service and the backend's probability endpoint |
| `raw/index-benchmark-output.txt` | stdout of `db/demos/index_benchmark.py` |
| `raw/smoke-test-output.txt` | stdout of `tests/run_smoke_test.sh` |
| `raw/transaction-evidence-output.txt` | stdout of `tests/run_smoke_test.sh tests/transaction_evidence.py` |
| `raw/api-contract-check.txt` | `tests/api_contract_check.py`: every one of the 36 endpoints in `docs/API.md` checked against the running backend (161/161) |
| `raw/api-503-check.txt` | The probability endpoint returning 503 while the ML service is stopped |
| `raw/oracle-extra-checks.txt` | Extra Oracle checks: −20004 (no such drive), `student_cgpa_standing_view`, a legal skip transition |
| `raw/ui-walkthrough.txt` | Playwright walkthrough of every UI flow, 28/28 (it writes data, so it ran on its own students; on the `frontend-polish` branch) |

## Scripts (`scripts/`)

| File | Produces |
|---|---|
| `scripts/build_sql_evidence.py` | `schema-summary.md`, `queries.md`, `triggers.md`, `transaction-sql.md`. Every block runs in psql, and anything that writes is rolled back. |
| `scripts/render_er.js` | `er-diagram.png` |
| `scripts/capture_screenshots.js` | `screenshots/*.png` (read-only: clicks nothing that changes data) |
