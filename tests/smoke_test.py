"""
End-to-end smoke test: drives the real API (and checks the database
directly) through every main flow and every database-enforced rule.

It WRITES data (applications, offers, a closed drive), so point it at a
throwaway database — tests/run_smoke_test.sh builds one, seeds it, starts a
second backend on port 5001 against it, runs this file, and cleans up.

Environment variables:
  API_URL       backend base URL           (default http://127.0.0.1:5001/api)
  DATABASE_URL  the SAME database that backend uses
Exit code is 0 only if every check passes.
"""
import os
import sys

import psycopg2
import psycopg2.extras
import requests

API = os.environ.get("API_URL", "http://127.0.0.1:5001/api")
DB = os.environ["DATABASE_URL"]
results = []


def check(step, ok, detail=""):
    results.append((bool(ok), step, detail))
    return ok


def q(sql, *args):
    with psycopg2.connect(DB) as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, args)
        return cur.fetchall() if cur.description else None


def sql_error_code(sql, *args):
    """Runs a write directly against the DB (bypassing the backend) and returns the SQLSTATE it raised, or None."""
    conn = psycopg2.connect(DB)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
        return None
    except psycopg2.Error as e:
        return e.pgcode
    finally:
        conn.rollback()
        conn.close()


def status_of(student_id):
    return q("SELECT placement_status FROM student WHERE student_id=%s", student_id)[0]["placement_status"]


def login(kind, email, password):
    r = requests.post(f"{API}/auth/{kind}/login", json={"email": email, "password": password})
    return r, ({"Authorization": f"Bearer {r.json()['token']}"} if r.ok else None)


def set_status(app_id, status, headers):
    return requests.put(f"{API}/applications/{app_id}/status", json={"status": status}, headers=headers)


def open_eligible_pairs(n):
    """n never-placed students, each with an open drive they're eligible for and haven't applied to."""
    return q("""
        SELECT DISTINCT ON (s.student_id) s.student_id, s.email, d.drive_id
        FROM student s CROSS JOIN drive d
        WHERE s.placement_status = 'Not Placed' AND d.status IN ('Upcoming', 'Ongoing') AND d.application_deadline >= CURRENT_DATE
          AND fn_check_eligibility(s.student_id, d.drive_id)
          AND NOT EXISTS (SELECT 1 FROM application a WHERE a.student_id = s.student_id AND a.drive_id = d.drive_id)
        ORDER BY s.student_id, d.drive_id
        LIMIT %s""", n)


# --- Authentication -------------------------------------------------------
r, admin = login("admin", "tpo@campus.edu", "Admin@123")
check("Admin login", r.status_code == 200, f"HTTP {r.status_code}")
r, _ = login("admin", "tpo@campus.edu", "wrong-password")
check("Admin login with wrong password rejected", r.status_code == 401, f"HTTP {r.status_code}")

A, B, C, D = open_eligible_pairs(4)
r, stu_a = login("student", A["email"], "Student@123")
check("Student login", r.status_code == 200, f"HTTP {r.status_code}")

# --- Student flow -----------------------------------------------------------
r = requests.get(f"{API}/students/{A['student_id']}/eligible-drives", headers=stu_a)
ids = [d["drive_id"] for d in r.json()] if r.ok else []
check("Eligible drives (fn_get_eligible_drives)", r.ok and A["drive_id"] in ids, f"HTTP {r.status_code}, {len(ids)} drives")
r = requests.get(f"{API}/students/{A['student_id'] + 1}", headers=stu_a)
check("Student cannot read another student's record", r.status_code == 403, f"HTTP {r.status_code}")

r = requests.post(f"{API}/applications", json={"drive_id": A["drive_id"]}, headers=stu_a)
app_a = r.json().get("application_id")
check("Apply to drive", r.status_code == 201, f"HTTP {r.status_code}")
r = requests.post(f"{API}/applications", json={"drive_id": A["drive_id"]}, headers=stu_a)
check("Duplicate application rejected", r.status_code == 409, f"HTTP {r.status_code}")

# --- Admin pipeline ----------------------------------------------------------
r = set_status(app_a, "Shortlisted", admin)
check("Admin shortlists (Applied -> Shortlisted)", r.ok, f"HTTP {r.status_code}")
r = set_status(app_a, "Selected", stu_a)
check("Student cannot change status (admin-only)", r.status_code == 403, f"HTTP {r.status_code}")
r = requests.post(f"{API}/applications/{app_a}/interview-rounds",
                  json={"round_number": 1, "round_type": "Technical", "result": "Pass"}, headers=admin)
check("Admin records interview round", r.status_code == 201, f"HTTP {r.status_code}")
r = requests.post(f"{API}/applications/{app_a}/offer", json={"offered_package_lpa": 9.5}, headers=admin)
check("NEW: offer on a Shortlisted (not yet Selected) application refused", r.status_code == 409,
      f"HTTP {r.status_code}: {r.json().get('error')}")
r = set_status(app_a, "Selected", admin)
check("Admin selects (Shortlisted -> Selected)", r.ok, f"HTTP {r.status_code}")

before = status_of(A["student_id"])
r = requests.post(f"{API}/applications/{app_a}/offer", json={"offered_package_lpa": 9.5}, headers=admin)
offer_a = r.json().get("offer_id")
after = status_of(A["student_id"])
check("Record offer -> trigger flips placement_status", r.status_code == 201 and (before, after) == ("Not Placed", "Placed"),
      f"HTTP {r.status_code}; {before} -> {after}")

# --- Offer transaction (accept) ---------------------------------------------
r = requests.post(f"{API}/offers/{offer_a}/accept", headers=stu_a)
hist = [h["action"] for h in q("SELECT action FROM offer_history WHERE offer_id=%s ORDER BY history_id", offer_a)]
check("Accept offer (transaction)", r.ok and status_of(A["student_id"]) == "Placed" and hist == ["Created", "Accepted"],
      f"HTTP {r.status_code}; offer_history={hist}")
r = requests.post(f"{API}/offers/{offer_a}/accept", headers=stu_a)
check("Accepting the same offer twice refused", r.status_code == 409, f"HTTP {r.status_code}")

# --- Offer transaction (decline) --------------------------------------------
_, stu_b = login("student", B["email"], "Student@123")
app_b = requests.post(f"{API}/applications", json={"drive_id": B["drive_id"]}, headers=stu_b).json()["application_id"]
set_status(app_b, "Shortlisted", admin)
set_status(app_b, "Selected", admin)
offer_b = requests.post(f"{API}/applications/{app_b}/offer", json={"offered_package_lpa": 7.0}, headers=admin).json()["offer_id"]
mid = status_of(B["student_id"])
r = requests.post(f"{API}/offers/{offer_b}/decline", headers=stu_b)
end = status_of(B["student_id"])
check("Decline only offer -> placement_status reverts", r.ok and (mid, end) == ("Placed", "Not Placed"),
      f"HTTP {r.status_code}; {mid} -> {end}")
r = requests.post(f"{API}/offers/{offer_b}/accept", headers=stu_a)
check("Student cannot act on someone else's offer", r.status_code == 403, f"HTTP {r.status_code}")

# --- ML ------------------------------------------------------------------------
r = requests.get(f"{API}/students/{A['student_id']}/placement-probability", headers=stu_a)
p = r.json().get("placement_probability") if r.ok else None
check("Placement-probability endpoint (backend -> ML service)", r.ok and isinstance(p, float) and 0 <= p <= 1,
      f"HTTP {r.status_code}, p={p}")

# --- Database-enforced rules (existing) ---------------------------------------
closed = q("SELECT drive_id FROM drive WHERE status='Completed' LIMIT 1")[0]["drive_id"]
r = requests.post(f"{API}/applications", json={"drive_id": closed}, headers=stu_b)
check("Rule PL002: apply to a closed drive refused", r.status_code == 409, f"HTTP {r.status_code}")
row = q("""SELECT drive_id FROM drive WHERE status IN ('Upcoming','Ongoing') AND application_deadline >= CURRENT_DATE
           AND NOT fn_check_eligibility(%s, drive_id) LIMIT 1""", B["student_id"])
if check("(found an ineligible open drive for the PL001 test)", bool(row)):
    r = requests.post(f"{API}/applications", json={"drive_id": row[0]["drive_id"]}, headers=stu_b)
    check("Rule PL001: apply while ineligible refused", r.status_code == 403, f"HTTP {r.status_code}")
row = q("""SELECT s.email, po.offer_id FROM student s
           JOIN application a1 ON a1.student_id=s.student_id JOIN offer ao ON ao.application_id=a1.application_id AND ao.status='Accepted'
           JOIN application a2 ON a2.student_id=s.student_id JOIN offer po ON po.application_id=a2.application_id AND po.status='Pending'
           LIMIT 1""")[0]
_, stu_x = login("student", row["email"], "Student@123")
r = requests.post(f"{API}/offers/{row['offer_id']}/accept", headers=stu_x)
check("Rule PL003: second accepted offer refused", r.status_code == 409, f"HTTP {r.status_code}")

# --- NEW Phase 1 rules: offer-on-rejected (PL006), status transitions (PL007) --
_, stu_c = login("student", C["email"], "Student@123")
app_c = requests.post(f"{API}/applications", json={"drive_id": C["drive_id"]}, headers=stu_c).json()["application_id"]
r = set_status(app_c, "Rejected", admin)
check("Admin rejects (Applied -> Rejected)", r.ok, f"HTTP {r.status_code}")
r = requests.post(f"{API}/applications/{app_c}/offer", json={"offered_package_lpa": 8.0}, headers=admin)
check("NEW: offer on a Rejected application refused (API)", r.status_code == 409,
      f"HTTP {r.status_code}: {r.json().get('error')}")
code = sql_error_code("INSERT INTO offer (application_id, offered_package_lpa) VALUES (%s, 8.0)", app_c)
check("NEW: offer on a Rejected application refused by the trigger itself (raw SQL, no backend)", code == "PL006",
      f"SQLSTATE {code}")
check("...and the Rejected application has no offer row", not q("SELECT 1 FROM offer WHERE application_id=%s", app_c), "")
r = set_status(app_c, "Applied", admin)
check("NEW: Rejected -> Applied refused (API)", r.status_code == 409, f"HTTP {r.status_code}: {r.json().get('error')}")
code = sql_error_code("UPDATE application SET status='Applied' WHERE application_id=%s", app_c)
check("NEW: Rejected -> Applied refused by the trigger itself (raw SQL)", code == "PL007", f"SQLSTATE {code}")
code = sql_error_code("UPDATE application SET status='Shortlisted' WHERE application_id=%s", app_a)
check("NEW: Offer_Made -> Shortlisted (backwards) refused", code == "PL007", f"SQLSTATE {code}")
check("...application statuses unchanged after the refused moves",
      q("SELECT status FROM application WHERE application_id=%s", app_c)[0]["status"] == "Rejected"
      and q("SELECT status FROM application WHERE application_id=%s", app_a)[0]["status"] == "Offer_Made", "")

# --- Date integrity (PL008) ------------------------------------------------------
# The admin moves an open drive's deadline to yesterday: a student who is
# otherwise eligible must now be refused, both through the API and when the
# row is written straight into the database.
_, stu_d = login("student", D["email"], "Student@123")
old_deadline = q("SELECT application_deadline FROM drive WHERE drive_id=%s", D["drive_id"])[0]["application_deadline"]
r = requests.put(f"{API}/drives/{D['drive_id']}", headers=admin,
                 # "Yesterday" by the database's clock: that is the clock the rule uses.
                 json={"application_deadline": q("SELECT CURRENT_DATE - 1 AS d")[0]["d"].isoformat()})
check("Admin moves a drive's application deadline to yesterday", r.ok, f"HTTP {r.status_code}")
r = requests.post(f"{API}/applications", json={"drive_id": D["drive_id"]}, headers=stu_d)
check("NEW: apply after the deadline refused (API)", r.status_code == 409,
      f"HTTP {r.status_code}: {r.json().get('error')}")
code = sql_error_code("INSERT INTO application (student_id, drive_id) VALUES (%s, %s)", D["student_id"], D["drive_id"])
check("NEW: apply after the deadline refused by the trigger itself (raw SQL)", code == "PL008", f"SQLSTATE {code}")
requests.put(f"{API}/drives/{D['drive_id']}", headers=admin, json={"application_deadline": old_deadline.isoformat()})
code = sql_error_code("INSERT INTO application (student_id, drive_id, applied_at) VALUES (%s, %s, now() + interval '1 day')",
                      D["student_id"], D["drive_id"])
check("NEW: application dated in the future refused (raw SQL)", code == "PL008", f"SQLSTATE {code}")
r = requests.put(f"{API}/drives/{D['drive_id']}", headers=admin,
                 json={"application_deadline": "2999-01-01"})
check("NEW: deadline after the drive date refused (CHECK constraint)", r.status_code == 400, f"HTTP {r.status_code}")
check("...the student has no application to that drive after the refused attempts",
      not q("SELECT 1 FROM application WHERE student_id=%s AND drive_id=%s", D["student_id"], D["drive_id"]), "")

# --- Procedure + analytics ------------------------------------------------------
drv = q("""SELECT d.drive_id, COUNT(a.*) AS pending FROM drive d LEFT JOIN application a ON a.drive_id = d.drive_id
           AND a.status IN ('Applied','Shortlisted','Interview_Scheduled') WHERE d.status = 'Ongoing'
           GROUP BY d.drive_id ORDER BY 2 DESC LIMIT 1""")[0]
r = requests.post(f"{API}/drives/{drv['drive_id']}/close", headers=admin)
check("Procedure sp_close_drive via API", r.ok and r.json()["rejected_count"] == drv["pending"],
      f"HTTP {r.status_code}, rejected {r.json().get('rejected_count')} of {drv['pending']} pending")

for path in ["/analytics/overview", "/analytics/department-stats", "/analytics/company-stats?top=5",
             "/analytics/package-by-branch", "/analytics/cgpa-vs-outcome", "/analytics/top-offers-per-dept",
             "/analytics/placement-timeline", "/analytics/company-dept-matrix"]:
    r = requests.get(f"{API}{path}", headers=admin)
    check(f"GET {path}", r.ok, f"HTTP {r.status_code}")

# --- CORS: only the configured frontend origin may call the API --------------------
r = requests.get(f"{API}/health", headers={"Origin": "http://localhost:5173"})
check("CORS: frontend origin http://localhost:5173 allowed",
      r.headers.get("Access-Control-Allow-Origin") == "http://localhost:5173",
      f"Access-Control-Allow-Origin={r.headers.get('Access-Control-Allow-Origin')}")
r = requests.get(f"{API}/health", headers={"Origin": "http://evil.example"})
check("CORS: unknown origin http://evil.example not allowed",
      "Access-Control-Allow-Origin" not in r.headers,
      f"Access-Control-Allow-Origin={r.headers.get('Access-Control-Allow-Origin')}")

# --- Report -----------------------------------------------------------------------
width = max(len(step) for _, step, _ in results)
for ok, step, detail in results:
    print(f"{'PASS' if ok else 'FAIL'} | {step.ljust(width)} | {detail}")
passed = sum(ok for ok, _, _ in results)
print(f"\nTOTAL: {passed}/{len(results)} passed")
sys.exit(0 if passed == len(results) else 1)
