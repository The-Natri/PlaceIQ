"""
Auth endpoints. Students and coordinators/TPOs are deliberately separate
login flows (not one "users" table with a role flag) because they were
already modeled as separate entities in the schema (see docs/normalization.md)
— a student can never accidentally end up with admin claims just because a
shared table's role column got mis-set.
"""
import psycopg2.errors
from flask import Blueprint, g, jsonify, request

from db import get_cursor
from utils.auth_middleware import require_auth
from utils.security import generate_token, hash_password, verify_password

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

REQUIRED_SIGNUP_FIELDS = ["reg_no", "name", "email", "password", "dept_id", "cgpa", "backlogs", "batch_year"]


@auth_bp.post("/student/signup")
def student_signup():
    body = request.get_json(silent=True) or {}
    missing = [f for f in REQUIRED_SIGNUP_FIELDS if body.get(f) in (None, "")]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    if len(body["password"]) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    password_hash = hash_password(body["password"])

    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO student
                    (reg_no, name, email, password_hash, dept_id, cgpa, backlogs, batch_year, phone)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING student_id, reg_no, name, email, dept_id, cgpa, backlogs, batch_year, placement_status
                """,
                (body["reg_no"], body["name"], body["email"], password_hash, body["dept_id"],
                 body["cgpa"], body["backlogs"], body["batch_year"], body.get("phone")),
            )
            student = cur.fetchone()
    except psycopg2.errors.UniqueViolation:
        return jsonify({"error": "A student with this reg_no or email already exists"}), 409
    except psycopg2.errors.ForeignKeyViolation:
        return jsonify({"error": "Invalid dept_id"}), 400
    except psycopg2.errors.CheckViolation as e:
        return jsonify({"error": f"Invalid field value: {e.diag.constraint_name}"}), 400

    token = generate_token(
        sub=student["student_id"], role="student", email=student["email"], name=student["name"]
    )
    return jsonify({"token": token, "user": student}), 201


@auth_bp.post("/student/login")
def student_login():
    body = request.get_json(silent=True) or {}
    email, password = body.get("email"), body.get("password")
    if not email or not password:
        return jsonify({"error": "email and password are required"}), 400

    with get_cursor() as cur:
        cur.execute(
            "SELECT student_id, name, email, password_hash, placement_status "
            "FROM student WHERE email = %s",
            (email,),
        )
        student = cur.fetchone()

    # Same generic error whether the email doesn't exist or the password is
    # wrong — avoids leaking which registered emails exist in the system.
    if student is None or not verify_password(password, student["password_hash"]):
        return jsonify({"error": "Invalid email or password"}), 401

    token = generate_token(sub=student["student_id"], role="student", email=student["email"], name=student["name"])
    return jsonify({
        "token": token,
        "user": {
            "student_id": student["student_id"],
            "name": student["name"],
            "email": student["email"],
            "placement_status": student["placement_status"],
        },
    })


@auth_bp.post("/admin/login")
def admin_login():
    body = request.get_json(silent=True) or {}
    email, password = body.get("email"), body.get("password")
    if not email or not password:
        return jsonify({"error": "email and password are required"}), 400

    with get_cursor() as cur:
        cur.execute(
            "SELECT coordinator_id, name, email, password_hash, role "
            "FROM coordinator WHERE email = %s",
            (email,),
        )
        coordinator = cur.fetchone()

    if coordinator is None or not verify_password(password, coordinator["password_hash"]):
        return jsonify({"error": "Invalid email or password"}), 401

    token = generate_token(
        sub=coordinator["coordinator_id"], role="admin", email=coordinator["email"],
        name=coordinator["name"], extra={"admin_role": coordinator["role"]},
    )
    return jsonify({
        "token": token,
        "user": {
            "coordinator_id": coordinator["coordinator_id"],
            "name": coordinator["name"],
            "email": coordinator["email"],
            "role": coordinator["role"],
        },
    })


@auth_bp.get("/me")
@require_auth()
def me():
    """
    Lets the frontend bootstrap the logged-in user's own dashboard from just
    the token, without having to separately remember/decode the id itself.
    """
    user = g.current_user
    with get_cursor() as cur:
        if user["role"] == "student":
            cur.execute(
                """
                SELECT s.student_id, s.reg_no, s.name, s.email, s.cgpa, s.backlogs,
                       s.batch_year, s.phone, s.placement_status, d.dept_name, d.dept_code
                FROM student s JOIN department d ON d.dept_id = s.dept_id
                WHERE s.student_id = %s
                """,
                (user["sub"],),
            )
        else:
            cur.execute(
                "SELECT coordinator_id, name, email, role FROM coordinator WHERE coordinator_id = %s",
                (user["sub"],),
            )
        profile = cur.fetchone()

    if profile is None:
        return jsonify({"error": "User not found"}), 404

    return jsonify({"role": user["role"], "profile": profile})
