from flask import Blueprint, jsonify, request

from db import get_cursor
from utils.auth_middleware import require_auth

drives_bp = Blueprint("drives", __name__, url_prefix="/api/drives")


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
