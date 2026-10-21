"""
Produces the API-level part of docs/evidence/transaction.md: the offer
accept and decline transactions (backend/services/offer_service.py) run
through the real backend, with the database state read directly before and
after each call, plus a request that the database refuses mid-transaction.

Like smoke_test.py it WRITES data, so run it through the throwaway-database
runner, which also prints this script's output:

    bash tests/run_smoke_test.sh tests/transaction_evidence.py

Everything printed is real: each request with the HTTP status and JSON body
the backend returned, and each "state" line is a fresh SELECT. Exit code is
non-zero if anything comes out different from what the transaction design
promises, so the evidence can't silently show a failure.
"""
import json
import os
import sys
import threading
import time

import psycopg2
import psycopg2.extras
import requests

API = os.environ.get("API_URL", "http://127.0.0.1:5001/api")
DB = os.environ["DATABASE_URL"]
problems = []


def q(sql, *args):
    with psycopg2.connect(DB) as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, args)
        return cur.fetchall() if cur.description else None


def call(method, path, headers=None, body=None, show=True):
    r = requests.request(method, f"{API}{path}", json=body, headers=headers)
    if show:
        sent = f" {json.dumps(body)}" if body else ""
        print(f"> {method} /api{path}{sent}")
        print(f"< HTTP {r.status_code} {json.dumps(r.json(), default=str)}")
    return r


def state(offer_id, student_id, label):
    """The three things the offer transactions change, read straight from the DB."""
    o = q("SELECT status, joining_date FROM offer WHERE offer_id = %s", offer_id)[0]
    s = q("SELECT placement_status FROM student WHERE student_id = %s", student_id)[0]
    h = [r["action"] for r in q("SELECT action FROM offer_history WHERE offer_id = %s ORDER BY history_id", offer_id)]
    print(f"  [{label}] offer.status={o['status']}, offer.joining_date={o['joining_date']}, "
          f"student.placement_status={s['placement_status']}, offer_history={h}")
    return o["status"], s["placement_status"], h


def expect(ok, what):
    if not ok:
        problems.append(what)
        print(f"  !! UNEXPECTED: {what}")


def login(kind, email, password):
    r = requests.post(f"{API}/auth/{kind}/login", json={"email": email, "password": password})
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['token']}"}


def fresh_offer(admin, package):
    """A never-placed student applies to an open drive they're eligible for, the
    admin moves the application to Selected and records an offer. Setup only:
    these calls aren't printed; the transaction calls below are."""
    s = q("""
        SELECT DISTINCT ON (s.student_id) s.student_id, s.name, s.email, d.drive_id
          FROM student s CROSS JOIN drive d
         WHERE s.placement_status = 'Not Placed' AND d.status IN ('Upcoming', 'Ongoing')
           AND fn_check_eligibility(s.student_id, d.drive_id)
           AND NOT EXISTS (SELECT 1 FROM application a WHERE a.student_id = s.student_id AND a.drive_id = d.drive_id)
         ORDER BY s.student_id, d.drive_id LIMIT 1""")[0]
    student = login("student", s["email"], "Student@123")
    app_id = call("POST", "/applications", student, {"drive_id": s["drive_id"]}, show=False).json()["application_id"]
    for status in ("Shortlisted", "Selected"):
        call("PUT", f"/applications/{app_id}/status", admin, {"status": status}, show=False)
    offer_id = call("POST", f"/applications/{app_id}/offer", admin, {"offered_package_lpa": package},
                    show=False).json()["offer_id"]
    print(f"Setup: {s['name']} (student {s['student_id']}) applied to drive {s['drive_id']}; the admin moved "
          f"application {app_id} to Selected and recorded offer {offer_id} (Pending, {package} LPA).\n")
    return s["student_id"], student, offer_id


admin = login("admin", "tpo@campus.edu", "Admin@123")

print("### 1. Accept: one transaction, three writes, one COMMIT\n")
print("```text")
sid, stu, oid = fresh_offer(admin, 9.5)
before = state(oid, sid, "before")
r = call("POST", f"/offers/{oid}/accept", stu)
after = state(oid, sid, "after ")
expect(r.status_code == 200, "accept should return 200")
expect(after[0] == "Accepted" and after[1] == "Placed" and after[2] == before[2] + ["Accepted"],
       "accept should set Accepted, keep Placed and add one 'Accepted' history row")
print("```\n")

print("### 2. Decline: the student's only offer, so placement_status goes back\n")
print("```text")
sid, stu, oid = fresh_offer(admin, 7.0)
before = state(oid, sid, "before")
r = call("POST", f"/offers/{oid}/decline", stu)
after = state(oid, sid, "after ")
expect(r.status_code == 200, "decline should return 200")
expect(before[1] == "Placed" and after[0] == "Declined" and after[1] == "Not Placed"
       and after[2] == before[2] + ["Declined"],
       "decline of the only offer should set Declined, revert to Not Placed and add one 'Declined' history row")
print("```\n")

print("### 3. Refused mid-transaction: a second acceptance (PL003) is rolled back\n")
print("```text")
row = q("""
    SELECT s.student_id, s.name, s.email, po.offer_id
      FROM student s
      JOIN application a1 ON a1.student_id = s.student_id
      JOIN offer ao ON ao.application_id = a1.application_id AND ao.status = 'Accepted'
      JOIN application a2 ON a2.student_id = s.student_id
      JOIN offer po ON po.application_id = a2.application_id AND po.status = 'Pending'
     ORDER BY s.student_id LIMIT 1""")[0]
print(f"Setup: {row['name']} (student {row['student_id']}) has already accepted one offer; "
      f"offer {row['offer_id']} is a second, Pending offer.\n")
stu = login("student", row["email"], "Student@123")
before = state(row["offer_id"], row["student_id"], "before")
r = call("POST", f"/offers/{row['offer_id']}/accept", stu)
after = state(row["offer_id"], row["student_id"], "after ")
expect(r.status_code == 409, "a second acceptance should return 409")
expect(after == before, "the refused acceptance should leave the database exactly as it was")
print("```\n")

# --- 4. Two acceptances at the same moment ------------------------------------
# Two separate connections (two "requests") each try to accept a different
# Pending offer of the same student. Without the FOR UPDATE lock in
# trg_fn_offer_single_acceptance, both would count 0 Accepted offers (neither
# can see the other's uncommitted row) and both would succeed. With it, the
# second waits on the student-row lock until the first commits, then counts 1
# and is refused. Timestamps show the wait.
print("### 4. Two acceptances at the same moment: the row lock serializes them\n")
print("```text")
sid, stu, offer_1 = fresh_offer(admin, 10.0)
app_2 = q("""
    SELECT d.drive_id FROM drive d
     WHERE d.status IN ('Upcoming', 'Ongoing') AND fn_check_eligibility(%s, d.drive_id)
       AND NOT EXISTS (SELECT 1 FROM application a WHERE a.student_id = %s AND a.drive_id = d.drive_id)
     ORDER BY d.drive_id LIMIT 1""", sid, sid)[0]["drive_id"]
app_2 = call("POST", "/applications", stu, {"drive_id": app_2}, show=False).json()["application_id"]
for status in ("Shortlisted", "Selected"):
    call("PUT", f"/applications/{app_2}/status", admin, {"status": status}, show=False)
offer_2 = call("POST", f"/applications/{app_2}/offer", admin, {"offered_package_lpa": 11.0}, show=False).json()["offer_id"]
print(f"Setup: the same student now also has offer {offer_2} (Pending). Two connections will each accept one.\n")

t0 = time.monotonic()
log = []
def stamp(msg):
    log.append((time.monotonic() - t0, msg))

conn_a, conn_b = psycopg2.connect(DB), psycopg2.connect(DB)
cur_a, cur_b = conn_a.cursor(), conn_b.cursor()
cur_a.execute("UPDATE offer SET status = 'Accepted' WHERE offer_id = %s", (offer_1,))
stamp(f"A: UPDATE offer {offer_1} -> Accepted done (trigger took the student-row lock); A has NOT committed")

outcome_b = {}
def session_b():
    stamp(f"B: UPDATE offer {offer_2} -> Accepted sent")
    try:
        cur_b.execute("UPDATE offer SET status = 'Accepted' WHERE offer_id = %s", (offer_2,))
        conn_b.commit()
        outcome_b["result"] = "committed"
        stamp("B: UPDATE succeeded and committed")
    except psycopg2.Error as e:
        conn_b.rollback()
        outcome_b["result"] = e.pgcode
        stamp(f"B: refused, SQLSTATE {e.pgcode}: {e.diag.message_primary}")

worker = threading.Thread(target=session_b)
worker.start()
time.sleep(1.5)  # B is now blocked on the lock A holds
stamp(f"(B still waiting after 1.5 s: {worker.is_alive()})")
blocked = worker.is_alive()
conn_a.commit()
stamp("A: COMMIT")
worker.join(10)
conn_a.close(); conn_b.close()
for t, msg in sorted(log):
    print(f"  t={t:5.2f}s  {msg}")
final = {r["offer_id"]: r["status"] for r in q("SELECT offer_id, status FROM offer WHERE offer_id IN (%s, %s)", offer_1, offer_2)}
print(f"  [after] offer {offer_1}: {final[offer_1]}, offer {offer_2}: {final[offer_2]}")
expect(blocked, "B should still be waiting while A holds the lock")
expect(outcome_b.get("result") == "PL003", "B should be refused with PL003 once A commits")
expect(final == {offer_1: "Accepted", offer_2: "Pending"}, "exactly one offer should end up Accepted")
print("```")

if problems:
    print(f"\n{len(problems)} unexpected result(s)", file=sys.stderr)
    sys.exit(1)
