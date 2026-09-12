from flask import Blueprint, jsonify

from db import get_cursor
from utils.auth_middleware import require_auth

companies_bp = Blueprint("companies", __name__, url_prefix="/api/companies")


@companies_bp.get("")
@require_auth()
def list_companies():
    with get_cursor() as cur:
        cur.execute(
            "SELECT company_id, company_name, industry_sector, website, hr_email "
            "FROM company ORDER BY company_name"
        )
        rows = cur.fetchall()
    return jsonify(rows)


@companies_bp.get("/<int:company_id>")
@require_auth()
def get_company(company_id):
    with get_cursor() as cur:
        cur.execute(
            "SELECT company_id, company_name, industry_sector, website, hr_email "
            "FROM company WHERE company_id = %s",
            (company_id,),
        )
        company = cur.fetchone()
        if company is None:
            return jsonify({"error": "Company not found"}), 404

        cur.execute(
            """
            SELECT drive_id, job_role, drive_date, package_lpa, status, drive_type
            FROM drive WHERE company_id = %s ORDER BY drive_date DESC
            """,
            (company_id,),
        )
        company["drives"] = cur.fetchall()

    return jsonify(company)
