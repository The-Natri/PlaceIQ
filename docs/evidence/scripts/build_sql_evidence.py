"""
Builds docs/evidence/{schema-summary,queries,triggers,transaction-sql}.md.

Every SQL block is sent to a real psql session against the live database
(via `docker exec placement_db psql`), and psql's output is pasted in
unedited. psql echoes each statement (-e) above its result. The prose
around each block is written by hand; the output never is.

Anything that changes data runs inside BEGIN ... ROLLBACK, so building the
evidence leaves the database exactly as it was. ON_ERROR_ROLLBACK lets a
transaction carry on after a rule-violation error (psql wraps each
statement in a savepoint), and LAST_ERROR_SQLSTATE prints the error's code.

Run from the repo root:  python docs/evidence/scripts/build_sql_evidence.py
"""
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs" / "evidence"

# stdbuf -o0 turns off psql's output buffering and 2>&1 merges errors in, both
# inside the container: otherwise result rows and ERROR lines arrive on two
# separately buffered streams and end up out of order.
PSQL = ["docker", "exec", "-i", "placement_db", "sh", "-c",
        "stdbuf -o0 -e0 psql -U placement_admin -d placement_db -X -e -v ON_ERROR_STOP=0 2>&1"]
PREAMBLE = "\\pset pager off\n\\pset null '(null)'\n\\set ON_ERROR_ROLLBACK on\n"


def run_sql(sql: str) -> str:
    # One merged stream (stderr into stdout) so each ERROR lands directly under
    # the statement that caused it, as it would in an interactive session.
    result = subprocess.run(PSQL, input=PREAMBLE + sql, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, encoding="utf-8")
    out = result.stdout.replace("\r\n", "\n")
    # Drop psql's confirmation lines for the \pset/\set preamble only.
    lines = [l for l in out.split("\n") if l not in ("Pager usage is off.", 'Null display is "(null)".')]
    return "\n".join(lines).strip("\n")


def section(title, explanation, sql):
    return f"## {title}\n\n{explanation.strip()}\n\n```text\n{run_sql(sql.strip())}\n```\n"


def write(name, title, intro, sections):
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    body = (f"# {title}\n\n{intro.strip()}\n\n"
            f"_Generated {stamp} by `docs/evidence/scripts/build_sql_evidence.py` against the live "
            f"`placement_db` (freshly seeded). Output blocks are unedited psql output._\n\n")
    body += "\n".join(sections)
    (OUT / name).write_text(body, encoding="utf-8")
    print(f"wrote {name}")


# ---------------------------------------------------------------------------
# schema-summary.md
# ---------------------------------------------------------------------------
TABLES = ["department", "coordinator", "student", "skill", "student_skill", "company", "drive",
          "drive_eligible_dept", "application", "interview_round", "offer", "offer_history",
          "application_status_history"]

schema_sections = [section(
    "All tables at a glance",
    "Row counts after seeding, and how many columns each table has.",
    """
SELECT t.table_name,
       (SELECT COUNT(*) FROM information_schema.columns c
         WHERE c.table_schema = 'public' AND c.table_name = t.table_name) AS columns,
       (xpath('/row/n/text()', query_to_xml(format('SELECT COUNT(*) AS n FROM %I', t.table_name), false, true, '')))[1]::text::int AS rows
  FROM information_schema.tables t
 WHERE t.table_schema = 'public' AND t.table_type = 'BASE TABLE'
 ORDER BY t.table_name;
""")]
for t in TABLES:
    schema_sections.append(section(
        f"`{t}`",
        f"Columns (type, nullability, default), then every constraint on `{t}`: "
        "PRIMARY KEY, FOREIGN KEY (with its ON DELETE rule), UNIQUE and CHECK.",
        f"""
SELECT column_name, data_type || COALESCE('(' || character_maximum_length || ')', '')
       || COALESCE(CASE WHEN data_type = 'numeric' THEN '(' || numeric_precision || ',' || numeric_scale || ')' END, '') AS type,
       is_nullable AS nullable,
       COALESCE(column_default, CASE WHEN is_identity = 'YES' THEN 'identity' END) AS "default"
  FROM information_schema.columns
 WHERE table_schema = 'public' AND table_name = '{t}'
 ORDER BY ordinal_position;

SELECT conname AS constraint_name,
       CASE contype WHEN 'p' THEN 'PRIMARY KEY' WHEN 'f' THEN 'FOREIGN KEY' WHEN 'u' THEN 'UNIQUE' WHEN 'c' THEN 'CHECK' END AS kind,
       pg_get_constraintdef(oid) AS definition
  FROM pg_constraint
 WHERE conrelid = 'public.{t}'::regclass
 ORDER BY contype, conname;
"""))

schema_sections.append(section(
    "Indexes",
    "Every index, including the ones PRIMARY KEY and UNIQUE constraints create. The five "
    "purpose-built ones are `idx_student_dept`, `idx_student_cgpa`, `idx_application_status`, "
    "`idx_application_drive` and `idx_drive_company` (reasons in `db/schema.sql` Section 2; "
    "measured effect in `index-benchmark.md`).",
    """
SELECT tablename, indexname, indexdef
  FROM pg_indexes WHERE schemaname = 'public'
 ORDER BY tablename, indexname;
"""))
schema_sections.append(section(
    "Triggers, functions, procedure and views",
    "Every trigger with its timing and event, then every routine and view in the schema.",
    """
SELECT tgrelid::regclass AS on_table, tgname AS trigger_name,
       CASE WHEN tgtype & 2 = 2 THEN 'BEFORE' ELSE 'AFTER' END AS timing,
       concat_ws(' OR ', CASE WHEN tgtype & 4 = 4 THEN 'INSERT' END, CASE WHEN tgtype & 16 = 16 THEN 'UPDATE' END) AS event,
       p.proname AS calls_function
  FROM pg_trigger tg JOIN pg_proc p ON p.oid = tg.tgfoid
 WHERE NOT tgisinternal ORDER BY 1, 2;

SELECT p.proname AS name,
       CASE p.prokind WHEN 'f' THEN 'FUNCTION' WHEN 'p' THEN 'PROCEDURE' END AS kind,
       pg_get_function_identity_arguments(p.oid) AS arguments,
       CASE WHEN p.prokind = 'f' THEN pg_get_function_result(p.oid) END AS returns
  FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
 WHERE n.nspname = 'public' ORDER BY kind, name;

SELECT table_name AS view_name, 'VIEW' AS kind FROM information_schema.views WHERE table_schema = 'public'
UNION ALL
SELECT matviewname, 'MATERIALIZED VIEW' FROM pg_matviews WHERE schemaname = 'public'
ORDER BY kind, view_name;
"""))

write("schema-summary.md", "Schema summary",
      """
Every table's columns, types and constraints, read from the PostgreSQL system
catalog (`information_schema`, `pg_constraint`, `pg_indexes`, `pg_trigger`) of the
running database, so this always matches what `db/schema.sql` actually created.
""", schema_sections)


# ---------------------------------------------------------------------------
# queries.md
# ---------------------------------------------------------------------------
query_sections = [
    section("Placement % per department (`department_stats_view`)",
            "LEFT JOIN from `department`, so a department with no students would still appear.",
            "SELECT * FROM department_stats_view ORDER BY placement_percentage DESC;"),
    section("Package statistics per company (`company_wise_stats_view`)",
            "Offers made and average / highest / lowest package for each recruiter.",
            "SELECT * FROM company_wise_stats_view ORDER BY company_name;"),
    section("Top recruiters by number of offers",
            "The same view, sorted by offers and cut to the top 5.",
            """
SELECT company_name, offers_count, avg_package_lpa
  FROM company_wise_stats_view
 ORDER BY offers_count DESC, company_name
 LIMIT 5;
"""),
    section("Placed students (`placed_students_view`)",
            "One row per offer with the student, department and company joined in. "
            "The first 10 rows, then the totals by offer status.",
            """
SELECT * FROM placed_students_view ORDER BY offered_package_lpa DESC LIMIT 10;
SELECT offer_status, COUNT(*) AS offers FROM placed_students_view GROUP BY offer_status ORDER BY offer_status;
"""),
    section("Package statistics per branch",
            "Average, highest and lowest offered package per department (the query behind "
            "`GET /api/analytics/package-by-branch`).",
            """
SELECT d.dept_name,
       COUNT(o.offer_id) AS offers_count,
       ROUND(AVG(o.offered_package_lpa), 2) AS avg_package_lpa,
       MAX(o.offered_package_lpa) AS max_package_lpa,
       MIN(o.offered_package_lpa) AS min_package_lpa
  FROM offer o
  JOIN application a ON a.application_id = o.application_id
  JOIN student s ON s.student_id = a.student_id
  JOIN department d ON d.dept_id = s.dept_id
 GROUP BY d.dept_name
 ORDER BY avg_package_lpa DESC;
"""),
    section("Top 3 offers in each department (`dept_offer_ranking_view`, `RANK()`)",
            "`RANK() OVER (PARTITION BY dept ORDER BY package DESC)`; ties share a rank.",
            """
SELECT dept_name, rank_in_dept, name, company_name, offered_package_lpa
  FROM dept_offer_ranking_view
 WHERE rank_in_dept <= 3
 ORDER BY dept_name, rank_in_dept, name;
"""),
    section("Offers per month with running total (`placement_timeline_view`)",
            "`SUM(...) OVER (ORDER BY month)` is the running total and `LAG(...)` the "
            "previous month's count. Every month from the first offer to the last is generated "
            "(`generate_series`), so a month with no offers (January 2026 here) is a 0 row and "
            "February's change is measured against January, not December.",
            "SELECT * FROM placement_timeline_view ORDER BY month;"),
    section("CGPA standing within department (`student_cgpa_standing_view`)",
            "`DENSE_RANK()` and `PERCENT_RANK()` over each department; the top 2 students per department.",
            """
SELECT d.dept_code, s.name, v.cgpa, v.cgpa_rank_in_dept, v.dept_size, v.cgpa_percentile_in_dept
  FROM student_cgpa_standing_view v
  JOIN student s ON s.student_id = v.student_id
  JOIN department d ON d.dept_id = v.dept_id
 WHERE v.cgpa_rank_in_dept <= 2
 ORDER BY d.dept_code, v.cgpa_rank_in_dept;
"""),
    section("Materialized view `mv_company_dept_placements`",
            "A stored snapshot: `refreshed_at` is fixed at the last `REFRESH`. The 10 busiest "
            "company × department cells, then a refresh, which moves `refreshed_at` forward.",
            """
SELECT company_name, dept_name, offers_count, avg_package_lpa
  FROM mv_company_dept_placements ORDER BY offers_count DESC, company_name, dept_name LIMIT 10;
SELECT MAX(refreshed_at) AS refreshed_at FROM mv_company_dept_placements;
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_company_dept_placements;
SELECT MAX(refreshed_at) AS refreshed_at FROM mv_company_dept_placements;
"""),
    section("`fn_check_eligibility(student, drive)`: eligible and ineligible cases",
            """
One real student/drive pair for each outcome, chosen by the query itself:
- a student who meets every rule (expect `t`);
- one below the CGPA cutoff;
- one with too many backlogs;
- one from a department the drive is not open to.

The `reason` column is computed independently, so the function's answer can be checked against it.
""",
            """
WITH pairs AS (
  SELECT s.student_id, s.name, s.cgpa, s.backlogs, dep.dept_code,
         d.drive_id, d.job_role, d.min_cgpa, d.max_backlogs,
         (SELECT string_agg(x.dept_code, ',' ORDER BY x.dept_code) FROM drive_eligible_dept e
            JOIN department x ON x.dept_id = e.dept_id WHERE e.drive_id = d.drive_id) AS open_to,
         CASE
           WHEN s.cgpa < d.min_cgpa THEN 'CGPA below cutoff'
           WHEN s.backlogs > d.max_backlogs THEN 'too many backlogs'
           WHEN EXISTS (SELECT 1 FROM drive_eligible_dept e WHERE e.drive_id = d.drive_id)
            AND NOT EXISTS (SELECT 1 FROM drive_eligible_dept e WHERE e.drive_id = d.drive_id AND e.dept_id = s.dept_id)
             THEN 'department not allowed'
           ELSE 'meets every rule'
         END AS reason
    FROM student s JOIN department dep ON dep.dept_id = s.dept_id CROSS JOIN drive d
)
SELECT DISTINCT ON (reason) name, dept_code, cgpa, backlogs, job_role, min_cgpa, max_backlogs,
       COALESCE(open_to, 'ALL') AS open_to, reason,
       fn_check_eligibility(student_id, drive_id) AS eligible
  FROM pairs
 ORDER BY reason, student_id, drive_id;
"""),
    section("`fn_get_eligible_drives(student)`",
            "The open (Upcoming/Ongoing) drives one student qualifies for: the function the student "
            "dashboard calls. The student is the highest-CGPA unplaced student.",
            """
SELECT student_id AS sid, name, cgpa, backlogs
  FROM student WHERE placement_status = 'Not Placed' ORDER BY cgpa DESC LIMIT 1 \\gset
SELECT :sid AS student_id, :'name' AS name, :cgpa AS cgpa, :backlogs AS backlogs;
SELECT e.drive_id, c.company_name, e.job_role, e.min_cgpa, e.max_backlogs, e.status
  FROM fn_get_eligible_drives(:sid) e JOIN company c ON c.company_id = e.company_id
 ORDER BY e.drive_date;
"""),
    section("`sp_close_drive`: before and after (rolled back)",
            """
Picks the Ongoing drive with the most pending applicants and shows its application statuses.
Then it calls the procedure inside a transaction, shows the drive and its applications again
(pending moved to Rejected, the drive Completed, and the audit rows the trigger wrote), and
finally `ROLLBACK`s, so the live data is unchanged.
""",
            """
SELECT d.drive_id AS did, c.company_name || ' - ' || d.job_role AS drive_name
  FROM drive d JOIN company c ON c.company_id = d.company_id
  JOIN application a ON a.drive_id = d.drive_id
 WHERE d.status = 'Ongoing' AND a.status IN ('Applied', 'Shortlisted', 'Interview_Scheduled')
 GROUP BY d.drive_id, c.company_name, d.job_role ORDER BY COUNT(*) DESC LIMIT 1 \\gset
SELECT :did AS drive_id, :'drive_name' AS drive;
BEGIN;
SELECT status FROM drive WHERE drive_id = :did;
SELECT status, COUNT(*) FROM application WHERE drive_id = :did GROUP BY status ORDER BY status;
CALL sp_close_drive(:did, NULL);
SELECT status FROM drive WHERE drive_id = :did;
SELECT status, COUNT(*) FROM application WHERE drive_id = :did GROUP BY status ORDER BY status;
SELECT h.old_status, h.new_status, COUNT(*) AS logged_by_audit_trigger
  FROM application_status_history h JOIN application a ON a.application_id = h.application_id
 WHERE a.drive_id = :did AND h.new_status = 'Rejected' AND h.changed_at >= now() - interval '1 minute'
 GROUP BY 1, 2;
ROLLBACK;
SELECT status FROM drive WHERE drive_id = :did;
"""),
]
write("queries.md", "Queries and their real output", """
Every view, the materialized view, both stored functions and the stored procedure,
run against the seeded database. These are the queries behind the analytics page
and the student dashboard.
""", query_sections)


# ---------------------------------------------------------------------------
# triggers.md
# ---------------------------------------------------------------------------
ERR = "\\echo '>>> SQLSTATE of the error above:' :LAST_ERROR_SQLSTATE"
trigger_sections = [
    section("1. Placement-status trigger (`trg_offer_after_insert`, AFTER INSERT on `offer`)",
            """
An unplaced student's Interview_Scheduled application is moved to Selected, then an offer is
inserted. Nothing in the statements touches `student`, but `placement_status` changes from
`Not Placed` to `Placed`: the trigger did it. Rolled back afterwards.
""",
            """
SELECT a.application_id AS app, s.student_id AS sid, s.name
  FROM application a JOIN student s ON s.student_id = a.student_id
 WHERE a.status = 'Interview_Scheduled' AND s.placement_status = 'Not Placed'
 ORDER BY a.application_id LIMIT 1 \\gset
BEGIN;
SELECT name, placement_status FROM student WHERE student_id = :sid;
UPDATE application SET status = 'Selected' WHERE application_id = :app;
INSERT INTO offer (application_id, offered_package_lpa) VALUES (:app, 9.50) RETURNING offer_id, status;
SELECT name, placement_status FROM student WHERE student_id = :sid;
ROLLBACK;
"""),
    section("2. Application guard (`trg_application_before_insert`): not eligible → PL001",
            "A student applies to an open drive whose CGPA cutoff they don't meet. The INSERT is refused.",
            f"""
SELECT s.student_id AS sid, d.drive_id AS did, s.cgpa, d.min_cgpa
  FROM student s CROSS JOIN drive d
 WHERE d.status IN ('Upcoming', 'Ongoing') AND d.application_deadline >= CURRENT_DATE AND s.cgpa < d.min_cgpa
 ORDER BY s.cgpa, d.drive_id LIMIT 1 \\gset
SELECT :sid AS student_id, :cgpa AS cgpa, :did AS drive_id, :min_cgpa AS drive_min_cgpa;
INSERT INTO application (student_id, drive_id) VALUES (:sid, :did);
{ERR}
"""),
    section("3. Application guard: drive closed → PL002",
            "An otherwise-eligible student applies to a Completed drive.",
            f"""
SELECT s.student_id AS sid, d.drive_id AS did
  FROM student s CROSS JOIN drive d
 WHERE d.status = 'Completed'
   AND s.cgpa >= d.min_cgpa AND s.backlogs <= d.max_backlogs
   AND NOT EXISTS (SELECT 1 FROM application a WHERE a.student_id = s.student_id AND a.drive_id = d.drive_id)
 ORDER BY d.drive_id, s.student_id LIMIT 1 \\gset
SELECT drive_id, status FROM drive WHERE drive_id = :did;
INSERT INTO application (student_id, drive_id) VALUES (:sid, :did);
{ERR}
"""),
    section("4. Second-offer guard (`trg_offer_before_accept`): one accepted offer per student → PL003",
            """
A student who has already accepted one offer tries to accept a second, Pending offer. The UPDATE
is refused and the second offer stays Pending.
""",
            f"""
SELECT po.offer_id AS pending_offer, s.student_id AS sid, s.name
  FROM student s
  JOIN application a1 ON a1.student_id = s.student_id JOIN offer ao ON ao.application_id = a1.application_id AND ao.status = 'Accepted'
  JOIN application a2 ON a2.student_id = s.student_id JOIN offer po ON po.application_id = a2.application_id AND po.status = 'Pending'
 ORDER BY s.student_id LIMIT 1 \\gset
SELECT o.offer_id, o.status FROM offer o JOIN application a ON a.application_id = o.application_id
 WHERE a.student_id = :sid ORDER BY o.offer_id;
UPDATE offer SET status = 'Accepted' WHERE offer_id = :pending_offer;
{ERR}
SELECT o.offer_id, o.status FROM offer o JOIN application a ON a.application_id = o.application_id
 WHERE a.student_id = :sid ORDER BY o.offer_id;
"""),
    section("5. Offer-on-rejected guard (`trg_offer_requires_selected`) → PL006",
            "An offer is inserted for a Rejected application, bypassing the backend entirely. "
            "The database itself refuses it.",
            f"""
SELECT application_id AS app FROM application WHERE status = 'Rejected' ORDER BY application_id LIMIT 1 \\gset
SELECT application_id, status FROM application WHERE application_id = :app;
INSERT INTO offer (application_id, offered_package_lpa) VALUES (:app, 8.00);
{ERR}
SELECT COUNT(*) AS offers_for_this_application FROM offer WHERE application_id = :app;
"""),
    section("6. Status-transition guard (`trg_application_status_transition`) → PL007",
            """
- A Rejected application can't go back to Applied.
- An application that already has an offer can't go backwards to Shortlisted.
- A legal forward move (Applied → Shortlisted) still works.

Rolled back.
""",
            f"""
SELECT application_id AS rejected_app FROM application WHERE status = 'Rejected' ORDER BY application_id LIMIT 1 \\gset
SELECT application_id AS offer_app FROM application WHERE status = 'Offer_Made' ORDER BY application_id LIMIT 1 \\gset
SELECT application_id AS applied_app FROM application WHERE status = 'Applied' ORDER BY application_id LIMIT 1 \\gset
BEGIN;
UPDATE application SET status = 'Applied' WHERE application_id = :rejected_app;
{ERR}
UPDATE application SET status = 'Shortlisted' WHERE application_id = :offer_app;
{ERR}
UPDATE application SET status = 'Shortlisted' WHERE application_id = :applied_app RETURNING application_id, status;
ROLLBACK;
"""),
    section("7. Audit trigger (`trg_application_status_audit`, AFTER UPDATE OF status)",
            """
A status change is logged with its old and new value automatically. An UPDATE that doesn't change
the status is skipped by the trigger's `WHEN` clause, so it adds no row. Rolled back.
""",
            """
SELECT application_id AS app FROM application WHERE status = 'Applied' ORDER BY application_id LIMIT 1 \\gset
BEGIN;
SELECT COUNT(*) AS history_rows_before FROM application_status_history WHERE application_id = :app;
UPDATE application SET status = 'Shortlisted' WHERE application_id = :app;
UPDATE application SET status = 'Shortlisted' WHERE application_id = :app;
SELECT old_status, new_status, changed_at FROM application_status_history WHERE application_id = :app ORDER BY history_id;
ROLLBACK;
"""),
    section("8. The audit trail the seed left behind",
            "Every status change made while seeding went through the same trigger. This is how many "
            "transitions of each kind were logged.",
            """
SELECT old_status, new_status, COUNT(*) AS times
  FROM application_status_history GROUP BY 1, 2 ORDER BY 1, 2;
"""),
]
write("triggers.md", "Triggers and database rules in action", """
Each trigger and rule is fired with real statements against the seeded database. Rows are
picked by the queries themselves (see each `\\gset`). Rule violations show psql's
`ERROR` line, followed by the SQLSTATE code the backend maps to an HTTP status
(`backend/utils/db_errors.py`). Anything that changes data is rolled back.
""", trigger_sections)


# ---------------------------------------------------------------------------
# date-integrity.md
# ---------------------------------------------------------------------------
date_sections = [
    section("Every date rule, counted",
            """
Each row counts the rows that break one rule; every count should be 0.
- **A** applied on or before the drive's deadline;
- **B** no application dated in the future;
- **C** deadline on or before the drive date;
- **D** every interview round on or after the application date;
- **E** rounds that already have a result are not in the future;
- **F** each offer after the application's final round;
- **G** no offer dated in the future;
- **H** status changes after the application date and not in the future;
- **I** status changes in the same order as they were logged;
- **J** offer events after the application date.
""",
            """
SELECT 'A applied after the drive deadline' AS rule, COUNT(*) AS violations
  FROM application a JOIN drive d ON d.drive_id = a.drive_id WHERE a.applied_at::DATE > d.application_deadline
UNION ALL
SELECT 'B application dated in the future', COUNT(*) FROM application WHERE applied_at > now()
UNION ALL
SELECT 'C deadline after the drive date', COUNT(*) FROM drive WHERE application_deadline > drive_date
UNION ALL
SELECT 'D round before the application date', COUNT(*)
  FROM interview_round r JOIN application a ON a.application_id = r.application_id WHERE r.round_date < a.applied_at::DATE
UNION ALL
SELECT 'E finished round dated in the future', COUNT(*) FROM interview_round WHERE result <> 'Pending' AND round_date > CURRENT_DATE
UNION ALL
SELECT 'F offer not after the final round', COUNT(*)
  FROM offer o WHERE o.offer_date <= (SELECT MAX(r.round_date) FROM interview_round r WHERE r.application_id = o.application_id)
UNION ALL
SELECT 'G offer dated in the future', COUNT(*) FROM offer WHERE offer_date > CURRENT_DATE
UNION ALL
SELECT 'H status change before applying or in the future', COUNT(*)
  FROM application_status_history h JOIN application a ON a.application_id = h.application_id
 WHERE h.changed_at < a.applied_at OR h.changed_at > now()
UNION ALL
SELECT 'I status changes out of order', COUNT(*)
  FROM (SELECT changed_at, LAG(changed_at) OVER (PARTITION BY application_id ORDER BY history_id) AS prev
          FROM application_status_history) x WHERE changed_at < prev
UNION ALL
SELECT 'J offer event before the application date', COUNT(*)
  FROM offer_history oh JOIN offer o ON o.offer_id = oh.offer_id JOIN application a ON a.application_id = o.application_id
 WHERE oh.action_timestamp < a.applied_at;
"""),
    section("What the timeline looks like",
            "Drives by status, with their date ranges relative to the day the data was seeded, and how "
            "many rows each kind of event has.",
            """
SELECT CURRENT_DATE AS today;
SELECT status, COUNT(*) AS drives, MIN(application_deadline) AS earliest_deadline,
       MAX(application_deadline) AS latest_deadline, MIN(drive_date) AS earliest_drive, MAX(drive_date) AS latest_drive
  FROM drive GROUP BY status ORDER BY status;
SELECT 'applications' AS what, COUNT(*), MIN(applied_at)::DATE AS first, MAX(applied_at)::DATE AS last FROM application
UNION ALL SELECT 'interview rounds', COUNT(*), MIN(round_date), MAX(round_date) FROM interview_round
UNION ALL SELECT 'offers', COUNT(*), MIN(offer_date), MAX(offer_date) FROM offer
UNION ALL SELECT 'status changes', COUNT(*), MIN(changed_at)::DATE, MAX(changed_at)::DATE FROM application_status_history;
"""),
    section("One completed application, end to end",
            "The full timeline of one application that reached an offer, in date order.",
            """
SELECT a.application_id AS app FROM application a JOIN offer o ON o.application_id = a.application_id
 ORDER BY a.application_id LIMIT 1 \\gset
SELECT event, at FROM (
  SELECT 'drive: applications close' AS event, d.application_deadline::TIMESTAMP AS at
    FROM application a JOIN drive d ON d.drive_id = a.drive_id WHERE a.application_id = :app
  UNION ALL SELECT 'drive: drive day', d.drive_date::TIMESTAMP
    FROM application a JOIN drive d ON d.drive_id = a.drive_id WHERE a.application_id = :app
  UNION ALL SELECT 'applied', applied_at FROM application WHERE application_id = :app
  UNION ALL SELECT 'status: ' || old_status || ' -> ' || new_status, changed_at
    FROM application_status_history WHERE application_id = :app
  UNION ALL SELECT 'round ' || round_number || ' (' || round_type || '): ' || result, round_date::TIMESTAMP
    FROM interview_round WHERE application_id = :app
  UNION ALL SELECT 'offer: ' || action, oh.action_timestamp
    FROM offer_history oh JOIN offer o ON o.offer_id = oh.offer_id WHERE o.application_id = :app
) t ORDER BY at, event;
"""),
    section("The database refuses a late application (PL008)",
            """
The rule is enforced by `trg_application_before_insert`, not only by the seed. Inside one transaction:
1. an eligible student applies to an open drive, which is accepted;
2. the drive's deadline is moved to yesterday and another eligible student applies, which is refused;
3. an application dated in the future is refused.

Rolled back.
""",
            f"""
SELECT d.drive_id AS did, MIN(s.student_id) AS sid1, MAX(s.student_id) AS sid2
  FROM student s CROSS JOIN drive d
 WHERE d.status IN ('Upcoming', 'Ongoing') AND d.application_deadline >= CURRENT_DATE
   AND fn_check_eligibility(s.student_id, d.drive_id)
   AND NOT EXISTS (SELECT 1 FROM application a WHERE a.student_id = s.student_id AND a.drive_id = d.drive_id)
 GROUP BY d.drive_id HAVING COUNT(*) >= 2 ORDER BY d.drive_id LIMIT 1 \\gset
BEGIN;
SELECT drive_id, status, application_deadline, drive_date FROM drive WHERE drive_id = :did;
INSERT INTO application (student_id, drive_id) VALUES (:sid1, :did) RETURNING application_id, applied_at::DATE;
UPDATE drive SET application_deadline = CURRENT_DATE - 1 WHERE drive_id = :did RETURNING application_deadline;
INSERT INTO application (student_id, drive_id) VALUES (:sid2, :did);
{ERR}
INSERT INTO application (student_id, drive_id, applied_at) VALUES (:sid2, :did, now() + INTERVAL '1 hour');
{ERR}
UPDATE drive SET application_deadline = drive_date + 1 WHERE drive_id = :did;
{ERR}
ROLLBACK;
"""),
]
write("date-integrity.md", "Date integrity", """
Applications, interview rounds, offers and status changes follow each other in time, and nothing
is dated in the future. `db/seed.py` builds every timeline relative to the day it runs. The
database refuses the one rule a client could break: applying after a drive's deadline
(`trg_application_before_insert`, PL008), plus the deadline <= drive date CHECK.
""", date_sections)


# ---------------------------------------------------------------------------
# transaction-sql.md (the API-level transaction evidence is in transaction.md)
# ---------------------------------------------------------------------------
tx_sections = [
    section("A. The accept transaction, statement by statement (COMMIT replaced by ROLLBACK)",
            """
These are the three statements `backend/services/offer_service.accept_offer` runs, in the same
order, inside one transaction:
1. accept the Pending offer;
2. make sure the student is Placed;
3. log the acceptance in the history.

All three are visible inside the transaction. `ROLLBACK` then undoes all of them together.
""",
            """
SELECT o.offer_id AS oid, a.student_id AS sid FROM offer o JOIN application a ON a.application_id = o.application_id
 WHERE o.status = 'Pending'
   AND NOT EXISTS (SELECT 1 FROM offer o2 JOIN application a2 ON a2.application_id = o2.application_id
                    WHERE a2.student_id = a.student_id AND o2.status = 'Accepted')
 ORDER BY o.offer_id LIMIT 1 \\gset
SELECT o.offer_id, o.status, o.joining_date, s.placement_status,
       (SELECT COUNT(*) FROM offer_history h WHERE h.offer_id = o.offer_id) AS history_rows
  FROM offer o JOIN application a ON a.application_id = o.application_id JOIN student s ON s.student_id = a.student_id
 WHERE o.offer_id = :oid;
BEGIN;
UPDATE offer SET status = 'Accepted', joining_date = COALESCE(joining_date, offer_date + INTERVAL '60 days')
 WHERE offer_id = :oid AND status = 'Pending' RETURNING offer_id;
UPDATE student SET placement_status = 'Placed' WHERE student_id = :sid;
INSERT INTO offer_history (offer_id, action, notes) VALUES (:oid, 'Accepted', 'Offer accepted by student');
SELECT o.offer_id, o.status, o.joining_date, s.placement_status,
       (SELECT COUNT(*) FROM offer_history h WHERE h.offer_id = o.offer_id) AS history_rows
  FROM offer o JOIN application a ON a.application_id = o.application_id JOIN student s ON s.student_id = a.student_id
 WHERE o.offer_id = :oid;
ROLLBACK;
SELECT o.offer_id, o.status, o.joining_date, s.placement_status,
       (SELECT COUNT(*) FROM offer_history h WHERE h.offer_id = o.offer_id) AS history_rows
  FROM offer o JOIN application a ON a.application_id = o.application_id JOIN student s ON s.student_id = a.student_id
 WHERE o.offer_id = :oid;
"""),
    section("B. Forced failure: one bad statement aborts the whole transaction",
            """
Same three statements, then a fourth that violates a CHECK constraint (an `offer_history.action`
value that isn't allowed). This block does **not** use ON_ERROR_ROLLBACK, so the failure aborts
the transaction:
- PostgreSQL refuses every later statement;
- `COMMIT` turns into a rollback;
- the offer is still Pending with the original history count.

The first two statements were undone too. This is atomicity.
""",
            """
\\set ON_ERROR_ROLLBACK off
SELECT o.offer_id AS oid, a.student_id AS sid FROM offer o JOIN application a ON a.application_id = o.application_id
 WHERE o.status = 'Pending'
   AND NOT EXISTS (SELECT 1 FROM offer o2 JOIN application a2 ON a2.application_id = o2.application_id
                    WHERE a2.student_id = a.student_id AND o2.status = 'Accepted')
 ORDER BY o.offer_id LIMIT 1 \\gset
SELECT offer_id, status, (SELECT COUNT(*) FROM offer_history h WHERE h.offer_id = :oid) AS history_rows FROM offer WHERE offer_id = :oid;
BEGIN;
UPDATE offer SET status = 'Accepted' WHERE offer_id = :oid AND status = 'Pending' RETURNING offer_id, status;
UPDATE student SET placement_status = 'Placed' WHERE student_id = :sid;
INSERT INTO offer_history (offer_id, action, notes) VALUES (:oid, 'Bogus', 'not an allowed action');
SELECT offer_id, status FROM offer WHERE offer_id = :oid;
COMMIT;
SELECT offer_id, status, (SELECT COUNT(*) FROM offer_history h WHERE h.offer_id = :oid) AS history_rows FROM offer WHERE offer_id = :oid;
"""),
]
write("transaction-sql.md", "Transactions at the SQL level", """
The offer-acceptance transaction run by hand in psql, showing what atomicity means
in practice. For the same transaction run through the real backend code (accept,
decline, and a rule-triggered rollback), see `transaction.md`.
""", tx_sections)
