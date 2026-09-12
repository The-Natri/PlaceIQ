import psycopg2.errors
from flask import Blueprint, g, jsonify, request

from db import get_cursor
from utils.auth_middleware import require_auth

drives_bp = Blueprint("drives", __name__, url_prefix="/api/drives")

DRIVE_EDITABLE_FIELDS = [
    "job_role", "drive_date", "package_lpa", "min_cgpa", "max_backlogs",
    "drive_type", "status",
]


@drives_bp.post("")
@require_auth(roles=["admin"])
def create_drive():
    """
    Admin creates a drive with its eligibility rule (min_cgpa, max_backlogs)
    and, optionally, a list of restricted department ids. Both the drive row
    and its eligible_dept_ids rows are written in ONE commit (get_cursor's
    single connection + single commit) so a drive can never end up
    half-created — e.g. saved with cutoffs but missing its branch
    restriction because a second request failed partway through.
    """
    body = request.get_json(silent=True) or {}
    required = ["company_id", "job_role", "drive_date", "package_lpa", "min_cgpa", "max_backlogs"]
    missing = [f for f in required if body.get(f) in (None, "")]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    eligible_dept_ids = body.get("eligible_dept_ids") or []  # [] => open to all departments

    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO drive
                    (company_id, coordinator_id, job_role, drive_date, package_lpa,
                     min_cgpa, max_backlogs, drive_type, status)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING drive_id
                """,
                (body["company_id"], g.current_user["sub"], body["job_role"], body["drive_date"],
                 body["package_lpa"], body["min_cgpa"], body["max_backlogs"],
                 body.get("drive_type", "Full-Time"), body.get("status", "Upcoming")),
            )
            drive_id = cur.fetchone()["drive_id"]

            for dept_id in eligible_dept_ids:
                cur.execute(
                    "INSERT INTO drive_eligible_dept (drive_id, dept_id) VALUES (%s,%s)",
                    (drive_id, dept_id),
                )
    except psycopg2.errors.ForeignKeyViolation:
        return jsonify({"error": "Invalid company_id or dept_id"}), 400
    except psycopg2.errors.CheckViolation as e:
        return jsonify({"error": f"Invalid field value: {e.diag.constraint_name}"}), 400

    return jsonify({"drive_id": drive_id}), 201


@drives_bp.put("/<int:drive_id>")
@require_auth(roles=["admin"])
def update_drive(drive_id):
    body = request.get_json(silent=True) or {}
    updates = {k: v for k, v in body.items() if k in DRIVE_EDITABLE_FIELDS}
    eligible_dept_ids = body.get("eligible_dept_ids")  # None => leave restrictions unchanged

    if not updates and eligible_dept_ids is None:
        return jsonify({"error": "No editable fields provided"}), 400

    try:
        with get_cursor(commit=True) as cur:
            if updates:
                set_clause = ", ".join(f"{col} = %s" for col in updates)
                cur.execute(
                    f"UPDATE drive SET {set_clause} WHERE drive_id = %s RETURNING drive_id",
                    [*updates.values(), drive_id],
                )
                if cur.fetchone() is None:
                    return jsonify({"error": "Drive not found"}), 404

            if eligible_dept_ids is not None:
                cur.execute("DELETE FROM drive_eligible_dept WHERE drive_id = %s", (drive_id,))
                for dept_id in eligible_dept_ids:
                    cur.execute(
                        "INSERT INTO drive_eligible_dept (drive_id, dept_id) VALUES (%s,%s)",
                        (drive_id, dept_id),
                    )
    except psycopg2.errors.CheckViolation as e:
        return jsonify({"error": f"Invalid field value: {e.diag.constraint_name}"}), 400
    except psycopg2.errors.ForeignKeyViolation:
        return jsonify({"error": "Invalid dept_id in eligible_dept_ids"}), 400

    return jsonify({"drive_id": drive_id, "updated": True})


@drives_bp.get("")
@require_auth()
def list_drives():
    status = request.args.get("status")
    conditions = []
    params = []
    if status is not None:
        conditions.append("dr.status = %s")
        params.append(status)
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    query = f"""
        SELECT dr.drive_id, dr.job_role, dr.drive_date, dr.package_lpa,
               dr.min_cgpa, dr.max_backlogs, dr.drive_type, dr.status,
               c.company_id, c.company_name
        FROM drive dr
        JOIN company c ON c.company_id = dr.company_id
        {where_clause}
        ORDER BY dr.drive_date DESC
    """
    with get_cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()
    return jsonify(rows)


@drives_bp.get("/<int:drive_id>")
@require_auth()
def get_drive(drive_id):
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT dr.drive_id, dr.job_role, dr.drive_date, dr.package_lpa,
                   dr.min_cgpa, dr.max_backlogs, dr.drive_type, dr.status,
                   dr.created_at, c.company_id, c.company_name, c.industry_sector
            FROM drive dr
            JOIN company c ON c.company_id = dr.company_id
            WHERE dr.drive_id = %s
            """,
            (drive_id,),
        )
        drive = cur.fetchone()
        if drive is None:
            return jsonify({"error": "Drive not found"}), 404

        cur.execute(
            """
            SELECT d.dept_id, d.dept_name, d.dept_code
            FROM drive_eligible_dept ded
            JOIN department d ON d.dept_id = ded.dept_id
            WHERE ded.drive_id = %s
            ORDER BY d.dept_name
            """,
            (drive_id,),
        )
        eligible = cur.fetchall()
        drive["eligible_departments"] = eligible  # empty list => open to all depts

    return jsonify(drive)


@drives_bp.get("/<int:drive_id>/applicants")
@require_auth(roles=["admin"])
def drive_applicants(drive_id):
    """Admin view: everyone who applied to this drive, for shortlisting."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT a.application_id, a.status, a.applied_at,
                   s.student_id, s.reg_no, s.name, s.cgpa, s.backlogs,
                   d.dept_name
            FROM application a
            JOIN student s ON s.student_id = a.student_id
            JOIN department d ON d.dept_id = s.dept_id
            WHERE a.drive_id = %s
            ORDER BY a.applied_at
            """,
            (drive_id,),
        )
        rows = cur.fetchall()
    return jsonify(rows)
