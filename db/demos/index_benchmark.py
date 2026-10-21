"""
Index benchmark: proves (or disproves) that the five indexes in schema.sql
Section 2 actually speed up the queries they were added for.

The real dataset (180 students) is far too small for any index to matter —
Postgres reads a few pages either way — so this builds a separate,
throwaway database (placement_bench) at a realistic scale, runs each query
with EXPLAIN ANALYZE, drops the indexes, runs them again, and prints a
markdown table of the results. The live placement_db is never touched.

Run:  .venv-db/Scripts/python db/demos/index_benchmark.py
"""
import os
import statistics
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
LIVE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://placement_admin:placement_dev_password@localhost:5432/placement_db",
)
ADMIN_URL = LIVE_URL.rsplit("/", 1)[0] + "/postgres"
BENCH_DB = "placement_bench"
BENCH_URL = LIVE_URL.rsplit("/", 1)[0] + "/" + BENCH_DB

# Sized for a laptop running Postgres inside Docker Desktop: at 200k
# students / 1M applications (and again at 100k / 500k followed by a
# database-wide VACUUM) Docker's Linux VM ran out of headroom and crashed.
# 250k applications is still far past the point where indexes matter.
N_STUDENTS = 50_000
N_DRIVES = 2_000
N_COMPANIES = 50
APPS_PER_STUDENT = 5          # -> 250,000 applications
BATCH = 10_000                # students loaded (and committed) per batch
RUNS = 7                      # timed runs per query; the median is reported

INDEXES = {
    "idx_student_dept": "CREATE INDEX idx_student_dept ON student(dept_id)",
    "idx_student_cgpa": "CREATE INDEX idx_student_cgpa ON student(cgpa)",
    "idx_application_status": "CREATE INDEX idx_application_status ON application(status)",
    "idx_application_drive": "CREATE INDEX idx_application_drive ON application(drive_id)",
    "idx_drive_company": "CREATE INDEX idx_drive_company ON drive(company_id)",
}

# Each benchmark query is one of the app's real hot paths.
QUERIES = [
    ("Applicants for one drive (admin 'view applicants')",
     "idx_application_drive",
     "SELECT application_id, student_id, status FROM application WHERE drive_id = 1234"),
    ("Top-CGPA students in one department (admin student filter)",
     "idx_student_cgpa / idx_student_dept",
     "SELECT student_id, name, cgpa FROM student WHERE dept_id = 3 AND cgpa >= 9.7"),
    ("Students in one department (department filter)",
     "idx_student_dept",
     "SELECT COUNT(*) FROM student WHERE dept_id = 3"),
    ("Applications in one status (admin status triage)",
     "idx_application_status",
     "SELECT COUNT(*) FROM application WHERE status = 'Selected'"),
    ("Drives for one company",
     "idx_drive_company",
     "SELECT drive_id, job_role FROM drive WHERE company_id = 7"),
]


def build_bench_db():
    admin = psycopg2.connect(ADMIN_URL)
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute(f"DROP DATABASE IF EXISTS {BENCH_DB}")
        cur.execute(f"CREATE DATABASE {BENCH_DB}")
    admin.close()

    conn = psycopg2.connect(BENCH_URL)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute((ROOT / "db" / "schema.sql").read_text(encoding="utf-8"))

    # Standard bulk-load practice: drop secondary indexes, load, then build
    # them once at the end — far cheaper than updating them on every row.
    for idx in INDEXES:
        cur.execute(f"DROP INDEX {idx}")

    # session_replication_role = replica switches off triggers, including
    # the FK-check triggers and the application guard trigger — the
    # generated data is consistent by construction, and running the
    # eligibility check half a million times would only slow the load down.
    cur.execute("SET session_replication_role = replica")
    cur.execute("SELECT setseed(0.42)")
    cur.execute("""
        INSERT INTO department (dept_name, dept_code)
        VALUES ('CSE','CSE'),('ISE','ISE'),('ECE','ECE'),('EEE','EEE'),('MECH','MECH'),('AIML','AIML')
    """)
    cur.execute(f"""
        INSERT INTO company (company_name)
        SELECT 'Company ' || g FROM generate_series(1, {N_COMPANIES}) g
    """)
    cur.execute(f"""
        INSERT INTO drive (company_id, job_role, drive_date, package_lpa, min_cgpa, max_backlogs, status)
        SELECT (g % {N_COMPANIES}) + 1, 'Role ' || g, DATE '2025-08-01' + (g % 200),
               5 + (g % 25), 6 + (g % 3) * 0.5, g % 3, 'Ongoing'
        FROM generate_series(1, {N_DRIVES}) g
    """)
    # Loaded in batches (each its own autocommitted statement) so no single
    # statement has to hold hundreds of thousands of rows of work in memory.
    # A single huge INSERT ... SELECT crashed Docker's Postgres the first
    # time this was run.
    for start in range(1, N_STUDENTS + 1, BATCH):
        end = min(start + BATCH - 1, N_STUDENTS)
        cur.execute(f"""
            INSERT INTO student (reg_no, name, email, password_hash, dept_id, cgpa, backlogs, batch_year)
            SELECT 'B' || g, 'Student ' || g, 's' || g || '@bench.edu', 'x',
                   (g % 6) + 1, ROUND((4.5 + random() * 5.4)::NUMERIC, 2),
                   FLOOR(random() * 3)::INT, 2024
            FROM generate_series({start}, {end}) g
        """)
        # (student + k*397) % N_DRIVES gives each student 5 distinct drives,
        # so UNIQUE(student_id, drive_id) holds. Status mix mirrors a busy
        # placement season.
        cur.execute(f"""
            INSERT INTO application (student_id, drive_id, status)
            SELECT s, ((s + k * 397) % {N_DRIVES}) + 1,
                   CASE WHEN r < 0.60 THEN 'Applied'
                        WHEN r < 0.70 THEN 'Shortlisted'
                        WHEN r < 0.80 THEN 'Interview_Scheduled'
                        WHEN r < 0.97 THEN 'Rejected'
                        ELSE 'Selected' END
            FROM (SELECT s, k, random() AS r
                  FROM generate_series({start}, {end}) s,
                       generate_series(0, {APPS_PER_STUDENT - 1}) k) x
        """)
        print(f"  loaded students {start:,}-{end:,}", flush=True)

    cur.execute("SET session_replication_role = origin")
    for ddl in INDEXES.values():
        cur.execute(ddl)
    # ANALYZE (statistics for the planner, from a sample of rows), not
    # VACUUM ANALYZE — VACUUM rewrites every page and is what tipped Docker
    # over on the larger runs; the planner only needs the statistics.
    for table in ("department", "company", "drive", "student", "application"):
        cur.execute(f"ANALYZE {table}")
    return conn


def time_query(cur, sql):
    """Median execution time (ms) over RUNS runs, plus the plan's top scan node."""
    cur.execute(sql)  # warm-up: pulls the pages into cache so we compare plans, not disk
    cur.fetchall()
    times, node = [], None
    for _ in range(RUNS):
        cur.execute("EXPLAIN (ANALYZE, FORMAT JSON) " + sql)
        plan = cur.fetchone()[0][0]
        times.append(plan["Execution Time"])
        node = scan_node(plan["Plan"])
    return statistics.median(times), node


def scan_node(plan):
    """The first node that actually reads a table (Seq Scan / Index Scan / Bitmap ...)."""
    if "Scan" in plan["Node Type"]:
        name = plan["Node Type"]
        if plan.get("Index Name"):
            name += f" using {plan['Index Name']}"
        return name
    for child in plan.get("Plans", []):
        found = scan_node(child)
        if found:
            return found
    return plan["Node Type"]


def main():
    print(f"Building {BENCH_DB}: {N_STUDENTS:,} students, {N_DRIVES:,} drives, "
          f"{N_STUDENTS * APPS_PER_STUDENT:,} applications ...")
    conn = build_bench_db()
    cur = conn.cursor()

    with_idx = {name: time_query(cur, sql) for name, _, sql in QUERIES}

    for idx in INDEXES:
        cur.execute(f"DROP INDEX {idx}")
    without_idx = {name: time_query(cur, sql) for name, _, sql in QUERIES}
    conn.close()

    admin = psycopg2.connect(ADMIN_URL)
    admin.autocommit = True
    with admin.cursor() as c:
        c.execute(f"DROP DATABASE {BENCH_DB}")
    admin.close()

    print("\n| Query | Index | With indexes | Without indexes | Speed-up |")
    print("|---|---|---|---|---|")
    for name, idx, _ in QUERIES:
        t_with, node_with = with_idx[name]
        t_without, node_without = without_idx[name]
        print(f"| {name} | `{idx}` | {t_with:.2f} ms ({node_with}) | "
              f"{t_without:.2f} ms ({node_without}) | {t_without / t_with:.1f}x |")

    print(f"\n(median of {RUNS} warm runs each; {BENCH_DB} was dropped afterwards)")


if __name__ == "__main__":
    main()
