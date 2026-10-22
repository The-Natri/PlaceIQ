"""
Checks docs/API.md against the real, running backend.

It parses every endpoint section in docs/API.md (method, path, success
status, response fields, error codes), sends a real request for each one,
and fails if:
  - a backend route is missing from the doc, or the doc lists a route that
    doesn't exist;
  - the success status or the set of response fields differs from the doc;
  - a documented error code can't be reproduced.

`--discover` instead prints what every endpoint actually returns (used to
write the doc in the first place, so the doc starts from real output).

It writes data, so run it against a throwaway database:
    bash tests/run_smoke_test.sh tests/api_contract_check.py
"""
import os
import re
import sys
import time
from pathlib import Path

import psycopg2
import psycopg2.extras
import requests

API = os.environ.get("API_URL", "http://127.0.0.1:5001/api")
DB = os.environ["DATABASE_URL"]
ROOT = Path(__file__).resolve().parents[1]
DOC = Path(os.environ.get("API_DOC", ROOT / "docs" / "API.md"))  # override to test the checker itself
MISSING = 999999


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
def q(sql, *args):
    with psycopg2.connect(DB) as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, args)
        return cur.fetchall() if cur.description else None


def login(kind, email, password):
    r = requests.post(f"{API}/auth/{kind}/login", json={"email": email, "password": password})
    r.raise_for_status()
    body = r.json()
    return {"Authorization": f"Bearer {body['token']}"}, body["user"]


def call(method, path, token=None, body=None):
    return requests.request(method, f"{API}{path}", headers=token or {}, json=body)


ADMIN, _ = login("admin", "tpo@campus.edu", "Admin@123")

_used_students = set()


def fresh():
    """
    A new (logged-in student, open drive) pair the student is eligible for and
    hasn't applied to yet — each call picks a student no other fixture has
    used, so fixtures never collide (e.g. a duplicate application).
    """
    row = q("""
        SELECT s.student_id, s.email, d.drive_id
        FROM student s CROSS JOIN drive d
        WHERE s.placement_status = 'Not Placed' AND d.status IN ('Upcoming', 'Ongoing') AND d.application_deadline >= CURRENT_DATE
          AND fn_check_eligibility(s.student_id, d.drive_id)
          AND NOT EXISTS (SELECT 1 FROM application a WHERE a.student_id = s.student_id AND a.drive_id = d.drive_id)
          AND s.student_id <> ALL(%s)
        ORDER BY s.student_id, d.drive_id LIMIT 1""", list(_used_students) or [0])[0]
    _used_students.add(row["student_id"])
    tok, _ = login("student", row["email"], "Student@123")
    return {"token": tok, "id": row["student_id"], "drive": row["drive_id"], "email": row["email"]}


def make_application(stu, *statuses):
    r = call("POST", "/applications", stu["token"], {"drive_id": stu["drive"]})
    r.raise_for_status()
    app_id = r.json()["application_id"]
    for s in statuses:
        call("PUT", f"/applications/{app_id}/status", ADMIN, {"status": s}).raise_for_status()
    return app_id


def make_offer(stu):
    app_id = make_application(stu, "Shortlisted", "Selected")
    r = call("POST", f"/applications/{app_id}/offer", ADMIN, {"offered_package_lpa": 9.0})
    r.raise_for_status()
    return r.json()["offer_id"]


# S1 owns an application + an offer it accepts; S2 owns one it declines;
# S3 applies through the POST /applications fixture; S4 is the "other
# student" used for ownership (403) checks.
S1, S2, S3, S4 = fresh(), fresh(), fresh(), fresh()


def ongoing_drive():
    return q("SELECT drive_id FROM drive WHERE status = 'Ongoing' ORDER BY drive_id DESC LIMIT 1")[0]["drive_id"]


def completed_drive():
    return q("SELECT drive_id FROM drive WHERE status = 'Completed' LIMIT 1")[0]["drive_id"]


def ineligible_open_drive(stu):
    return q("""SELECT drive_id FROM drive WHERE status IN ('Upcoming','Ongoing') AND application_deadline >= CURRENT_DATE
                AND NOT fn_check_eligibility(%s, drive_id) LIMIT 1""", stu["id"])[0]["drive_id"]


def any_id(table, col):
    return q(f"SELECT {col} FROM {table} ORDER BY {col} LIMIT 1")[0][col]


def new_signup_body():
    n = int(time.time() * 1000) % 10**9
    return {"reg_no": f"T{n}", "name": "Contract Check", "email": f"contract{n}@campus.edu",
            "password": "Student@123", "dept_id": 1, "cgpa": 8.0, "backlogs": 0, "batch_year": 2025}


# ----------------------------------------------------------------------------
# One successful request per endpoint. Each returns (path, token, body).
# Order matters for a few (e.g. close runs on a drive no other step uses).
# ----------------------------------------------------------------------------
SUCCESS = {
    ("GET", "/api/health"): lambda: ("/health", None, None),
    ("POST", "/api/auth/student/signup"): lambda: ("/auth/student/signup", None, new_signup_body()),
    ("POST", "/api/auth/student/login"): lambda: ("/auth/student/login", None,
                                                  {"email": S4["email"], "password": "Student@123"}),
    ("POST", "/api/auth/admin/login"): lambda: ("/auth/admin/login", None,
                                                {"email": "tpo@campus.edu", "password": "Admin@123"}),
    ("GET", "/api/auth/me"): lambda: ("/auth/me", S1["token"], None),
    ("GET", "/api/departments"): lambda: ("/departments", None, None),
    ("GET", "/api/students"): lambda: ("/students?dept_id=1&min_cgpa=8", ADMIN, None),
    ("GET", "/api/students/:id"): lambda: (f"/students/{S1['id']}", S1["token"], None),
    ("GET", "/api/students/:id/eligible-drives"): lambda: (f"/students/{S1['id']}/eligible-drives", S1["token"], None),
    ("GET", "/api/students/:id/applications"): lambda: (f"/students/{S1['id']}/applications", S1["token"], None),
    ("GET", "/api/students/:id/placement-probability"):
        lambda: (f"/students/{S1['id']}/placement-probability", S1["token"], None),
    ("GET", "/api/companies"): lambda: ("/companies", S1["token"], None),
    ("GET", "/api/companies/:id"): lambda: (f"/companies/{any_id('company', 'company_id')}", S1["token"], None),
    ("GET", "/api/drives"): lambda: ("/drives?status=Ongoing", S1["token"], None),
    ("GET", "/api/drives/:id"): lambda: (f"/drives/{S1['drive']}", S1["token"], None),
    ("POST", "/api/drives"): lambda: ("/drives", ADMIN, {
        "company_id": 1, "job_role": "Contract Check Role", "drive_date": "2026-03-01", "package_lpa": 10,
        "min_cgpa": 7.0, "max_backlogs": 1, "drive_type": "Full-Time", "eligible_dept_ids": [1, 2]}),
    ("PUT", "/api/drives/:id"): lambda: (f"/drives/{S1['drive']}", ADMIN, {"package_lpa": 11.5}),
    ("POST", "/api/drives/:id/close"): lambda: (f"/drives/{ongoing_drive()}/close", ADMIN, None),
    ("GET", "/api/drives/:id/applicants"): lambda: (f"/drives/{S1['drive']}/applicants", ADMIN, None),
    ("POST", "/api/applications"): lambda: ("/applications", S3["token"], {"drive_id": S3["drive"]}),
    ("GET", "/api/applications/:id"): lambda: (f"/applications/{S1_APP}", S1["token"], None),
    ("PUT", "/api/applications/:id/status"):
        lambda: (f"/applications/{make_application(fresh())}/status", ADMIN, {"status": "Shortlisted"}),
    ("POST", "/api/applications/:id/interview-rounds"):
        lambda: (f"/applications/{app_for_rounds()}/interview-rounds", ADMIN,
                 {"round_number": 1, "round_type": "Technical", "round_date": "2026-03-02", "result": "Pass"}),
    ("POST", "/api/applications/:id/offer"):
        lambda: (f"/applications/{selected_app()}/offer", ADMIN, {"offered_package_lpa": 9.0}),
    ("GET", "/api/offers/:id"): lambda: (f"/offers/{OFFER1}", S1["token"], None),
    ("POST", "/api/offers/:id/accept"): lambda: (f"/offers/{OFFER1}/accept", S1["token"], None),
    ("POST", "/api/offers/:id/decline"): lambda: (f"/offers/{OFFER2}/decline", S2["token"], None),
    ("GET", "/api/analytics/overview"): lambda: ("/analytics/overview", ADMIN, None),
    ("GET", "/api/analytics/department-stats"): lambda: ("/analytics/department-stats", ADMIN, None),
    ("GET", "/api/analytics/company-stats"): lambda: ("/analytics/company-stats?top=5", ADMIN, None),
    ("GET", "/api/analytics/package-by-branch"): lambda: ("/analytics/package-by-branch", ADMIN, None),
    ("GET", "/api/analytics/cgpa-vs-outcome"): lambda: ("/analytics/cgpa-vs-outcome", ADMIN, None),
    ("GET", "/api/analytics/top-offers-per-dept"): lambda: ("/analytics/top-offers-per-dept?n=3", ADMIN, None),
    ("GET", "/api/analytics/placement-timeline"): lambda: ("/analytics/placement-timeline", ADMIN, None),
    ("GET", "/api/analytics/company-dept-matrix"): lambda: ("/analytics/company-dept-matrix", ADMIN, None),
    ("POST", "/api/analytics/refresh-matrix"): lambda: ("/analytics/refresh-matrix", ADMIN, None),
}

# State shared by fixtures (created lazily, once).
_cache = {}


def app_for_rounds():
    if "rounds_app" not in _cache:
        _cache["rounds_app"] = make_application(fresh(), "Shortlisted")
    return _cache["rounds_app"]


def selected_app():
    return make_application(fresh(), "Shortlisted", "Selected")


OFFER1 = make_offer(S1)   # accepted by S1
S1_APP = q("SELECT application_id FROM offer WHERE offer_id = %s", OFFER1)[0]["application_id"]
OFFER2 = make_offer(S2)   # declined by S2

# ----------------------------------------------------------------------------
# One request per documented error: (method, path, status) -> (path, token, body).
# 401 (no token) and 403 (student calling an admin route) are generated
# automatically for every protected endpoint; only the rest are listed here.
# ----------------------------------------------------------------------------
ERRORS = {
    ("POST", "/api/auth/student/signup", 400): lambda: ("/auth/student/signup", None, {"name": "x"}),
    ("POST", "/api/auth/student/signup", 409): lambda: ("/auth/student/signup", None,
                                                        {**new_signup_body(), "email": S4["email"]}),
    ("POST", "/api/auth/student/login", 400): lambda: ("/auth/student/login", None, {"email": "a@b.c"}),
    ("POST", "/api/auth/student/login", 401): lambda: ("/auth/student/login", None,
                                                       {"email": S4["email"], "password": "wrong"}),
    ("POST", "/api/auth/admin/login", 400): lambda: ("/auth/admin/login", None, {}),
    ("POST", "/api/auth/admin/login", 401): lambda: ("/auth/admin/login", None,
                                                     {"email": "tpo@campus.edu", "password": "wrong"}),
    ("GET", "/api/students/:id", 403): lambda: (f"/students/{S2['id']}", S1["token"], None),
    ("GET", "/api/students/:id", 404): lambda: (f"/students/{MISSING}", ADMIN, None),
    ("GET", "/api/students/:id/eligible-drives", 403): lambda: (f"/students/{S2['id']}/eligible-drives", S1["token"], None),
    ("GET", "/api/students/:id/applications", 403): lambda: (f"/students/{S2['id']}/applications", S1["token"], None),
    ("GET", "/api/students/:id/placement-probability", 403):
        lambda: (f"/students/{S2['id']}/placement-probability", S1["token"], None),
    ("GET", "/api/students/:id/placement-probability", 404):
        lambda: (f"/students/{MISSING}/placement-probability", ADMIN, None),
    ("GET", "/api/companies/:id", 404): lambda: (f"/companies/{MISSING}", ADMIN, None),
    ("GET", "/api/drives/:id", 404): lambda: (f"/drives/{MISSING}", ADMIN, None),
    ("POST", "/api/drives", 400): lambda: ("/drives", ADMIN, {"job_role": "x"}),
    ("PUT", "/api/drives/:id", 400): lambda: (f"/drives/{S1['drive']}", ADMIN, {"unknown": 1}),
    ("PUT", "/api/drives/:id", 404): lambda: (f"/drives/{MISSING}", ADMIN, {"package_lpa": 5}),
    ("POST", "/api/drives/:id/close", 404): lambda: (f"/drives/{MISSING}/close", ADMIN, None),
    ("POST", "/api/drives/:id/close", 409): lambda: (f"/drives/{completed_drive()}/close", ADMIN, None),
    ("POST", "/api/applications", 400): lambda: ("/applications", S3["token"], {}),
    ("POST", "/api/applications", 403): lambda: ("/applications", S3["token"], {"drive_id": ineligible_open_drive(S3)}),
    ("POST", "/api/applications", 409): lambda: ("/applications", S3["token"], {"drive_id": completed_drive()}),
    ("GET", "/api/applications/:id", 403): lambda: (f"/applications/{app_for_rounds()}", S1["token"], None),
    ("GET", "/api/applications/:id", 404): lambda: (f"/applications/{MISSING}", ADMIN, None),
    ("PUT", "/api/applications/:id/status", 400): lambda: (f"/applications/{app_for_rounds()}/status", ADMIN, {"status": "Hired"}),
    ("PUT", "/api/applications/:id/status", 404): lambda: (f"/applications/{MISSING}/status", ADMIN, {"status": "Rejected"}),
    ("PUT", "/api/applications/:id/status", 409): lambda: (f"/applications/{app_for_rounds()}/status", ADMIN, {"status": "Applied"}),
    ("POST", "/api/applications/:id/interview-rounds", 400):
        lambda: (f"/applications/{app_for_rounds()}/interview-rounds", ADMIN, {"round_number": 2, "round_type": "Dance"}),
    ("POST", "/api/applications/:id/interview-rounds", 409):
        lambda: (f"/applications/{app_for_rounds()}/interview-rounds", ADMIN, {"round_number": 1, "round_type": "HR"}),
    ("POST", "/api/applications/:id/offer", 400): lambda: (f"/applications/{app_for_rounds()}/offer", ADMIN, {}),
    ("POST", "/api/applications/:id/offer", 404): lambda: (f"/applications/{MISSING}/offer", ADMIN, {"offered_package_lpa": 5}),
    ("POST", "/api/applications/:id/offer", 409): lambda: (f"/applications/{app_for_rounds()}/offer", ADMIN, {"offered_package_lpa": 5}),
    ("GET", "/api/offers/:id", 403): lambda: (f"/offers/{OFFER2}", S1["token"], None),
    ("GET", "/api/offers/:id", 404): lambda: (f"/offers/{MISSING}", ADMIN, None),
    ("POST", "/api/offers/:id/accept", 403): lambda: (f"/offers/{OFFER2}/accept", S1["token"], None),
    ("POST", "/api/offers/:id/accept", 404): lambda: (f"/offers/{MISSING}/accept", ADMIN, None),
    ("POST", "/api/offers/:id/accept", 409): lambda: (f"/offers/{OFFER1}/accept", S1["token"], None),
    ("POST", "/api/offers/:id/decline", 403): lambda: (f"/offers/{OFFER1}/decline", S2["token"], None),
    ("POST", "/api/offers/:id/decline", 404): lambda: (f"/offers/{MISSING}/decline", ADMIN, None),
    ("POST", "/api/offers/:id/decline", 409): lambda: (f"/offers/{OFFER2}/decline", S2["token"], None),
}

PUBLIC = {("GET", "/api/health"), ("POST", "/api/auth/student/signup"), ("POST", "/api/auth/student/login"),
          ("POST", "/api/auth/admin/login"), ("GET", "/api/departments")}


def shape(body):
    """Field names of a response: top-level keys, or the keys of a list's first item."""
    if isinstance(body, list):
        return ("list", sorted(body[0].keys()) if body else [])
    return ("object", sorted(body.keys()))


def nested(body):
    """Keys of nested objects / lists inside an object response (for the doc)."""
    out = {}
    if isinstance(body, dict):
        for k, v in body.items():
            if isinstance(v, dict):
                out[k] = sorted(v.keys())
            elif isinstance(v, list) and v and isinstance(v[0], dict):
                out[k] = sorted(v[0].keys())
    return out


# ----------------------------------------------------------------------------
# discover mode
# ----------------------------------------------------------------------------
def run_order(keys):
    """Accept/decline after everything that reads the offers; closing a drive last,
    since it changes which drives are open for later fixtures."""
    keys = list(keys)
    late = [k for k in keys if k[1].endswith(("/accept", "/decline"))]
    last = [k for k in keys if k[1].endswith("/close")]
    return [k for k in keys if k not in late and k not in last] + late + last


def discover():
    for (method, path) in run_order(SUCCESS):
        p, tok, body = SUCCESS[(method, path)]()
        r = call(method, p, tok, body)
        data = r.json()
        kind, fields = shape(data)
        print(f"{method} {path}  -> {r.status_code} {kind} {fields}  nested={nested(data)}")
        print(f"    request: {method} {p} body={body}")
        print(f"    sample:  {str(data)[:300]}")
    for (method, path, code), fx in ERRORS.items():
        p, tok, body = fx()
        r = call(method, p, tok, body)
        print(f"ERR {method} {path} expect {code} -> {r.status_code} {r.text.strip()[:140]}")


# ----------------------------------------------------------------------------
# verify mode: parse docs/API.md and check it against the backend
# ----------------------------------------------------------------------------
def parse_doc():
    text = DOC.read_text(encoding="utf-8")
    sections = re.split(r"^### ", text, flags=re.M)[1:]
    docs = {}
    for sec in sections:
        m = re.match(r"`(GET|POST|PUT|DELETE) (/api/\S+)`", sec)
        if not m:
            continue
        key = (m.group(1), m.group(2))
        auth = re.search(r"\*\*Auth:\*\*\s*(.+)", sec).group(1).strip()
        success = int(re.search(r"\*\*Success:\*\*\s*`(\d{3})`", sec).group(1))
        fields_line = re.search(r"\*\*Response fields:\*\*\s*(.+)", sec).group(1)
        fields = sorted(re.findall(r"`([a-z_]+)`", fields_line))
        errors_line = re.search(r"\*\*Errors:\*\*\s*(.+)", sec).group(1)
        errors = sorted({int(c) for c in re.findall(r"`(\d{3})`", errors_line)})
        docs[key] = {"auth": auth, "success": success, "fields": fields, "errors": errors}
    return docs


def backend_routes():
    sys.path.insert(0, str(ROOT / "backend"))
    from app import create_app  # noqa: E402
    routes = set()
    for rule in create_app().url_map.iter_rules():
        if not rule.rule.startswith("/api"):
            continue
        path = re.sub(r"<(?:int:)?([a-z_]+)>", ":id", rule.rule)
        for m in rule.methods - {"HEAD", "OPTIONS"}:
            routes.add((m, path))
    return routes


def verify():
    docs = parse_doc()
    results = []

    def rec(ok, what, detail=""):
        results.append((bool(ok), what, detail))

    routes = backend_routes()
    for key in sorted(routes - set(docs)):
        rec(False, f"{key[0]} {key[1]}", "backend route is NOT documented")
    for key in sorted(set(docs) - routes):
        rec(False, f"{key[0]} {key[1]}", "documented but NO such backend route")
    rec(routes == set(docs), "Doc covers exactly the backend's routes", f"{len(docs)} documented, {len(routes)} in backend")

    for key in run_order(docs):
        d = docs[key]
        label = f"{key[0]} {key[1]}"
        if key not in SUCCESS:
            rec(False, label, "no request defined in this checker")
            continue
        p, tok, body = SUCCESS[key]()
        r = call(key[0], p, tok, body)
        try:
            kind, fields = shape(r.json())
        except ValueError:
            kind, fields = "non-json", []
        rec(r.status_code == d["success"], f"{label} -> {d['success']}", f"got {r.status_code}")
        rec(fields == d["fields"], f"{label} fields",
            "match" if fields == d["fields"] else f"doc {d['fields']} vs real {fields}")

        for code in d["errors"]:
            if code == 401 and key not in PUBLIC:
                p, _, body = SUCCESS[key]() if key[0] == "GET" else (p, None, body)
                r = call(key[0], p, None, body)
            elif code == 403 and (key[0], key[1], 403) not in ERRORS and "admin" in d["auth"].lower():
                r = call(key[0], p, S1["token"], body)
            elif (key[0], key[1], code) in ERRORS:
                ep, etok, ebody = ERRORS[(key[0], key[1], code)]()
                r = call(key[0], ep, etok, ebody)
            else:
                rec(False, f"{label} -> {code}", "documented error has no reproduction in this checker")
                continue
            rec(r.status_code == code, f"{label} -> {code}", f"got {r.status_code}: {r.text.strip()[:90]}")

    width = max(len(w) for _, w, _ in results)
    for ok, what, detail in results:
        print(f"{'PASS' if ok else 'FAIL'} | {what.ljust(width)} | {detail}")
    passed = sum(ok for ok, _, _ in results)
    print(f"\nTOTAL: {passed}/{len(results)} passed  ({len(docs)} endpoints documented)")
    return passed == len(results)


if __name__ == "__main__":
    if "--discover" in sys.argv:
        discover()
    else:
        sys.exit(0 if verify() else 1)
