from flask import Blueprint, jsonify

from db import get_cursor

departments_bp = Blueprint("departments", __name__, url_prefix="/api/departments")


@departments_bp.get("")
def list_departments():
    """Reference data for dropdowns (student signup form, drive creation form)."""
    with get_cursor() as cur:
        cur.execute("SELECT dept_id, dept_name, dept_code FROM department ORDER BY dept_name")
        rows = cur.fetchall()
    return jsonify(rows)
