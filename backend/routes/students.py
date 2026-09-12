from flask import Blueprint, jsonify, request

from db import get_cursor

students_bp = Blueprint("students", __name__, url_prefix="/api/students")


@students_bp.get("")
def list_students():
    """
    Admin-facing student listing with optional filters. Filters are appended
    as parameterized conditions (never string-interpolated) to avoid SQL
    injection, and only touch columns that are indexed (dept_id, cgpa — see
    schema.sql Section 2) so this stays fast as the table grows.
    """
    dept_id = request.args.get("dept_id", type=int)
    min_cgpa = request.args.get("min_cgpa", type=float)
    placement_status = request.args.get("placement_status")

    conditions = []
    params = []
    if dept_id is not None:
        conditions.append("s.dept_id = %s")
        params.append(dept_id)
    if min_cgpa is not None:
        conditions.append("s.cgpa >= %s")
        params.append(min_cgpa)
    if placement_status is not None:
        conditions.append("s.placement_status = %s")
        params.append(placement_status)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    query = f"""
        SELECT s.student_id, s.reg_no, s.name, s.email, s.cgpa, s.backlogs,
               s.batch_year, s.placement_status, d.dept_name, d.dept_code
        FROM student s
        JOIN department d ON d.dept_id = s.dept_id
        {where_clause}
        ORDER BY s.name
    """
    with get_cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()
    return jsonify(rows)


@students_bp.get("/<int:student_id>")
def get_student(student_id):
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT s.student_id, s.reg_no, s.name, s.email, s.cgpa, s.backlogs,
                   s.batch_year, s.phone, s.placement_status, s.created_at,
                   d.dept_id, d.dept_name, d.dept_code
            FROM student s
            JOIN department d ON d.dept_id = s.dept_id
            WHERE s.student_id = %s
            """,
            (student_id,),
        )
        student = cur.fetchone()
        if student is None:
            return jsonify({"error": "Student not found"}), 404

        cur.execute(
            """
            SELECT sk.skill_id, sk.skill_name
            FROM student_skill ss
            JOIN skill sk ON sk.skill_id = ss.skill_id
            WHERE ss.student_id = %s
            ORDER BY sk.skill_name
            """,
            (student_id,),
        )
        student["skills"] = cur.fetchall()

    return jsonify(student)


@students_bp.get("/<int:student_id>/eligible-drives")
def eligible_drives(student_id):
    """
    Delegates entirely to the DB's fn_get_eligible_drives() stored function
    (schema.sql Section 4) instead of re-implementing the CGPA/backlog/
    department eligibility rule here — this is the "eligibility check as a
    stored procedure, called from the backend" requirement in practice.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT d.drive_id, d.job_role, d.drive_date, d.package_lpa,
                   d.min_cgpa, d.max_backlogs, d.drive_type, d.status,
                   c.company_name
            FROM fn_get_eligible_drives(%s) d
            JOIN company c ON c.company_id = d.company_id
            ORDER BY d.drive_date
            """,
            (student_id,),
        )
        rows = cur.fetchall()
    return jsonify(rows)
