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


@analytics_bp.get("/top-offers-per-dept")
@require_auth(roles=["admin"])
def top_offers_per_dept():
    """
    Top N offers in each department, from dept_offer_ranking_view (schema.sql
    Section 9). The RANK() window function is computed in the view; "top N"
    is a plain filter on its result — a window function's output can't be
    filtered in the same SELECT that computes it, which is why the ranking
    lives in a view and the filter lives here.
    """
    n = request.args.get("n", default=3, type=int)
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT dept_name, rank_in_dept, name, reg_no, company_name, offered_package_lpa
            FROM dept_offer_ranking_view
            WHERE rank_in_dept <= %s
            ORDER BY dept_name, rank_in_dept, name
            """,
            (n,),
        )
        rows = cur.fetchall()
    return jsonify(rows)


@analytics_bp.get("/placement-timeline")
@require_auth(roles=["admin"])
def placement_timeline():
    """Monthly offers with running total and month-over-month change (placement_timeline_view)."""
    with get_cursor() as cur:
        cur.execute("SELECT * FROM placement_timeline_view ORDER BY month")
        rows = cur.fetchall()
    return jsonify(rows)


@analytics_bp.get("/company-dept-matrix")
@require_auth(roles=["admin"])
def company_dept_matrix():
    """
    Reads the materialized view (schema.sql Section 10). This is a stored
    snapshot, not live data — refreshed_at says how old it is, and
    POST /refresh-matrix brings it up to date.
    """
    with get_cursor() as cur:
        cur.execute(
            "SELECT company_name, dept_name, offers_count, avg_package_lpa, refreshed_at "
            "FROM mv_company_dept_placements ORDER BY company_name, dept_name"
        )
        rows = cur.fetchall()
    refreshed_at = rows[0]["refreshed_at"] if rows else None
    for row in rows:
        del row["refreshed_at"]
    return jsonify({"refreshed_at": refreshed_at, "cells": rows})


@analytics_bp.post("/refresh-matrix")
@require_auth(roles=["admin"])
def refresh_matrix():
    """
    REFRESH ... CONCURRENTLY rebuilds the snapshot without locking out
    readers of the old one while it runs (possible because the view has a
    UNIQUE index). It can't run inside a transaction block, hence autocommit.
    """
    with get_cursor(autocommit=True) as cur:
        cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_company_dept_placements")
        cur.execute("SELECT MAX(refreshed_at) AS refreshed_at FROM mv_company_dept_placements")
        refreshed_at = cur.fetchone()["refreshed_at"]
    return jsonify({"refreshed_at": refreshed_at})


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
