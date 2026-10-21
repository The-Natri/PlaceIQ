import psycopg2.errors
from flask import Blueprint, g, jsonify, request

from db import get_cursor
from utils.auth_middleware import require_auth
from utils.db_errors import business_rule_response

applications_bp = Blueprint("applications", __name__, url_prefix="/api/applications")

# Statuses an admin may set directly through PUT .../status. 'Offer_Made' is
# deliberately excluded — it is only ever set as a side effect of recording
# an actual Offer row (see record_offer below), so the application's status
# can never claim an offer exists when the offer table says otherwise.
ADMIN_SETTABLE_STATUSES = {"Applied", "Shortlisted", "Interview_Scheduled", "Rejected", "Selected"}

INTERVIEW_ROUND_TYPES = {"Aptitude", "Technical", "HR", "Group_Discussion", "Coding_Test"}


@applications_bp.post("")
@require_auth(roles=["student"])
def apply_to_drive():
    """
    A student applies to a drive. There is deliberately no eligibility check
    here: trg_application_before_insert (schema.sql Section 6) rejects the
    INSERT itself if the student isn't eligible or the drive is closed, so
    the rule can't be bypassed by any client — this route just reports the
    database's answer.
    """
    body = request.get_json(silent=True) or {}
    drive_id = body.get("drive_id")
    if not drive_id:
        return jsonify({"error": "drive_id is required"}), 400

    student_id = g.current_user["sub"]

    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "INSERT INTO application (student_id, drive_id) VALUES (%s, %s) "
                "RETURNING application_id, status, applied_at",
                (student_id, drive_id),
            )
            application = cur.fetchone()
    except psycopg2.errors.UniqueViolation:
        return jsonify({"error": "You have already applied to this drive"}), 409
    except psycopg2.errors.ForeignKeyViolation:
        return jsonify({"error": "Invalid drive_id"}), 400
    except psycopg2.Error as e:
        rule_violation = business_rule_response(e)
        if rule_violation:
            return rule_violation
        raise

    return jsonify(application), 201


def _load_application_owner(cur, application_id):
    cur.execute("SELECT student_id FROM application WHERE application_id = %s", (application_id,))
    return cur.fetchone()


@applications_bp.get("/<int:application_id>")
@require_auth()
def get_application(application_id):
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT a.application_id, a.status, a.applied_at, a.student_id,
                   dr.drive_id, dr.job_role, dr.package_lpa, dr.drive_date,
                   c.company_name
            FROM application a
            JOIN drive dr ON dr.drive_id = a.drive_id
            JOIN company c ON c.company_id = dr.company_id
            WHERE a.application_id = %s
            """,
            (application_id,),
        )
        application = cur.fetchone()
        if application is None:
            return jsonify({"error": "Application not found"}), 404

        user = g.current_user
        if user["role"] == "student" and int(user["sub"]) != application["student_id"]:
            return jsonify({"error": "Forbidden"}), 403

        cur.execute(
            "SELECT round_id, round_number, round_type, round_date, result, remarks "
            "FROM interview_round WHERE application_id = %s ORDER BY round_number",
            (application_id,),
        )
        application["interview_rounds"] = cur.fetchall()

        cur.execute(
            "SELECT offer_id, offered_package_lpa, offer_date, status, joining_date "
            "FROM offer WHERE application_id = %s",
            (application_id,),
        )
        application["offer"] = cur.fetchone()  # None if no offer yet

        # Written by trg_application_status_audit (schema.sql Section 7),
        # never by this app — every status change appears here regardless of
        # which code path or SQL client made it.
        cur.execute(
            "SELECT old_status, new_status, changed_at "
            "FROM application_status_history WHERE application_id = %s ORDER BY changed_at, history_id",
            (application_id,),
        )
        application["status_history"] = cur.fetchall()

    return jsonify(application)


@applications_bp.put("/<int:application_id>/status")
@require_auth(roles=["admin"])
def update_application_status(application_id):
    body = request.get_json(silent=True) or {}
    new_status = body.get("status")
    if new_status not in ADMIN_SETTABLE_STATUSES:
        return jsonify({"error": f"status must be one of {sorted(ADMIN_SETTABLE_STATUSES)}"}), 400

    # Which transitions are legal is decided by trg_application_status_transition
    # (schema.sql Section 6), not here — an illegal one (e.g. Rejected ->
    # Applied) comes back as PL007 and is reported as a 409.
    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "UPDATE application SET status = %s WHERE application_id = %s RETURNING application_id",
                (new_status, application_id),
            )
            if cur.fetchone() is None:
                return jsonify({"error": "Application not found"}), 404
    except psycopg2.Error as e:
        rule_violation = business_rule_response(e)
        if rule_violation:
            return rule_violation
        raise

    return jsonify({"application_id": application_id, "status": new_status})


@applications_bp.post("/<int:application_id>/interview-rounds")
@require_auth(roles=["admin"])
def record_interview_round(application_id):
    body = request.get_json(silent=True) or {}
    round_number = body.get("round_number")
    round_type = body.get("round_type")
    result = body.get("result", "Pending")

    if not round_number or round_type not in INTERVIEW_ROUND_TYPES:
        return jsonify({"error": f"round_number is required and round_type must be one of {sorted(INTERVIEW_ROUND_TYPES)}"}), 400

    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO interview_round (application_id, round_number, round_type, round_date, result, remarks)
                VALUES (%s,%s,%s,%s,%s,%s)
                RETURNING round_id
                """,
                (application_id, round_number, round_type, body.get("round_date"),
                 result, body.get("remarks")),
            )
            round_row = cur.fetchone()
    except psycopg2.errors.UniqueViolation:
        return jsonify({"error": "This round_number already exists for this application"}), 409
    except psycopg2.errors.ForeignKeyViolation:
        return jsonify({"error": "Invalid application_id"}), 400

    return jsonify(round_row), 201


@applications_bp.post("/<int:application_id>/offer")
@require_auth(roles=["admin"])
def record_offer(application_id):
    """
    Admin records that a company has extended an offer. Inserting into
    `offer` is what fires the placement_status trigger (schema.sql Section
    3) — nothing in this route sets placement_status itself, which is the
    whole point of demonstrating the trigger instead of duplicating its
    logic in application code.
    """
    body = request.get_json(silent=True) or {}
    offered_package_lpa = body.get("offered_package_lpa")
    if not offered_package_lpa:
        return jsonify({"error": "offered_package_lpa is required"}), 400

    try:
        with get_cursor(commit=True) as cur:
            # Friendly early answer for the UI. The real guarantee is
            # trg_offer_requires_selected (schema.sql Section 6), which rejects
            # the INSERT below even if this check were removed or raced.
            cur.execute("SELECT status FROM application WHERE application_id = %s", (application_id,))
            app_row = cur.fetchone()
            if app_row is None:
                return jsonify({"error": "Application not found"}), 404
            if app_row["status"] != "Selected":
                return jsonify({
                    "error": f"Application is {app_row['status']}; mark it Selected before recording an offer"
                }), 409

            cur.execute(
                """
                INSERT INTO offer (application_id, offered_package_lpa, offer_date)
                VALUES (%s, %s, COALESCE(%s, CURRENT_DATE))
                RETURNING offer_id, application_id, offered_package_lpa, offer_date, status
                """,
                (application_id, offered_package_lpa, body.get("offer_date")),
            )
            offer = cur.fetchone()

            cur.execute(
                "INSERT INTO offer_history (offer_id, action, notes) VALUES (%s, 'Created', %s)",
                (offer["offer_id"], "Offer recorded by placement cell"),
            )

            cur.execute(
                "UPDATE application SET status = 'Offer_Made' WHERE application_id = %s",
                (application_id,),
            )
    except psycopg2.errors.UniqueViolation:
        return jsonify({"error": "This application already has an offer"}), 409
    except psycopg2.errors.ForeignKeyViolation:
        return jsonify({"error": "Invalid application_id"}), 400
    except psycopg2.Error as e:
        rule_violation = business_rule_response(e)
        if rule_violation:
            return rule_violation
        raise

    return jsonify(offer), 201
