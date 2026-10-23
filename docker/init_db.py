"""
Prepares the database on first start, and does nothing on later starts:

  1. waits until Postgres accepts connections;
  2. applies db/schema.sql if the tables don't exist yet;
  3. runs db/seed.py if the synthetic dataset isn't fully loaded.

Used by the Docker app container's entrypoint and by start.ps1 / start.sh,
so both ways of running PlaceIQ set the database up the same way.

"Fully loaded" means the materialized view has rows: the seed refreshes it
as its very last step, so an interrupted seed is simply run again (the seed
truncates every table before it starts). SKIP_SEED=1 skips seeding.
"""
import os
import subprocess
import sys
import time

import psycopg2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# On this machine (start.ps1 / start.sh) settings come from the repo's .env;
# in the container there is no .env and they come from the environment.
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))
except ImportError:
    pass
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://placement_admin:placement_dev_password@localhost:5432/placement_db",
)


def connect_when_ready(timeout_s=120):
    deadline = time.time() + timeout_s
    while True:
        try:
            return psycopg2.connect(DATABASE_URL)
        except psycopg2.OperationalError as e:
            if time.time() > deadline:
                sys.exit(f"init_db: the database did not become reachable within {timeout_s}s: {e}")
            print("init_db: waiting for the database...", flush=True)
            time.sleep(2)


def main():
    conn = connect_when_ready()
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('public.student') IS NOT NULL")
        if not cur.fetchone()[0]:
            print("init_db: no tables yet, applying db/schema.sql", flush=True)
            with open(os.path.join(ROOT, "db", "schema.sql"), encoding="utf-8") as f:
                cur.execute(f.read())
        cur.execute("SELECT (SELECT COUNT(*) FROM student) > 0 AND (SELECT COUNT(*) FROM mv_company_dept_placements) > 0")
        seeded = cur.fetchone()[0]
    conn.close()

    if seeded:
        print("init_db: schema and data already present", flush=True)
    elif os.environ.get("SKIP_SEED") == "1":
        print("init_db: SKIP_SEED=1, leaving the database empty", flush=True)
    else:
        print("init_db: loading the synthetic dataset (db/seed.py, about 1-3 minutes)...", flush=True)
        subprocess.run([sys.executable, os.path.join(ROOT, "db", "seed.py")], check=True)


if __name__ == "__main__":
    main()
