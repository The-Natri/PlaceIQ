"""
Admin analytics dashboard. Wherever a view already covers the query
(department_stats_view, company_wise_stats_view — schema.sql Section 5),
these routes select straight from it instead of re-deriving the same joins
in Python — that's the whole point of having defined the views in the
database rather than in application code.
"""
from flask import Blueprint, jsonify, request

from db import get_cursor
from utils.auth_middleware import require_auth

analytics_bp = Blueprint("analytics", __name__, url_prefix="/api/analytics")


@analytics_bp.get("/overview")
@require_auth(roles=["admin"])
def overview():
    """Single-request summary for the top of the analytics page."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM student) AS total_students,
                (SELECT COUNT(*) FROM student WHERE placement_status = 'Placed') AS placed_students,
                (SELECT COUNT(*) FROM company) AS total_companies,
                (SELECT COUNT(*) FROM drive) AS total_drives,
                (SELECT COUNT(*) FROM offer) AS total_offers,
                (SELECT COUNT(*) FROM offer WHERE status = 'Accepted') AS accepted_offers
            """
        )
        row = cur.fetchone()
    total = row["total_students"] or 1  # guard divide-by-zero on an empty dataset
    row["overall_placement_pct"] = round(100.0 * row["placed_students"] / total, 2)
    return jsonify(row)


@analytics_bp.get("/department-stats")
@require_auth(roles=["admin"])
def department_stats():
    """Placement % per department — straight from department_stats_view."""
    with get_cursor() as cur:
        cur.execute("SELECT * FROM department_stats_view ORDER BY placement_percentage DESC")
        rows = cur.fetchall()
    return jsonify(rows)


@analytics_bp.get("/company-stats")
@require_auth(roles=["admin"])
def company_stats():
    """
    Offers made + package stats per company — straight from
    company_wise_stats_view. ?top=N also serves the "top recruiters by
    offer count" requirement by sorting on the same view instead of a
    separate query.
    """
    top = request.args.get("top", type=int)
    query = "SELECT * FROM company_wise_stats_view ORDER BY offers_count DESC"
    if top:
        query += " LIMIT %s"
    with get_cursor() as cur:
        cur.execute(query, (top,) if top else None)
        rows = cur.fetchall()
    return jsonify(rows)


@analytics_bp.get("/package-by-branch")
@require_auth(roles=["admin"])
def package_by_branch():
    """
    Avg/highest/lowest offered package per department. Not covered by an
    existing view (company_wise_stats_view groups by company, not
    department), so this is its own query — grouping offers through
    application -> student -> department.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT d.dept_name,
                   COUNT(o.offer_id) AS offers_count,
                   ROUND(AVG(o.offered_package_lpa), 2) AS avg_package_lpa,
                   MAX(o.offered_package_lpa) AS max_package_lpa,
                   MIN(o.offered_package_lpa) AS min_package_lpa
            FROM offer o
            JOIN application a ON a.application_id = o.application_id
            JOIN student s ON s.student_id = a.student_id
            JOIN department d ON d.dept_id = s.dept_id
            GROUP BY d.dept_name
            ORDER BY avg_package_lpa DESC
            """
        )
        rows = cur.fetchall()
    return jsonify(rows)


@analytics_bp.get("/cgpa-vs-outcome")
@require_auth(roles=["admin"])
def cgpa_vs_outcome():
    """
    Raw per-student (cgpa, backlogs, placement_status) points for the
    frontend to render as a scatter plot — deliberately unaggregated since
    a scatter chart needs individual points, not a GROUP BY summary.
    """
    with get_cursor() as cur:
        cur.execute(
            "SELECT student_id, cgpa, backlogs, placement_status, dept_id FROM student ORDER BY cgpa"
        )
        rows = cur.fetchall()
    return jsonify(rows)
