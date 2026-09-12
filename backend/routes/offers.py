from flask import Blueprint, g, jsonify

from db import get_cursor
from services import offer_service
from utils.auth_middleware import require_auth

offers_bp = Blueprint("offers", __name__, url_prefix="/api/offers")


@offers_bp.get("/<int:offer_id>")
@require_auth()
def get_offer(offer_id):
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT o.offer_id, o.offered_package_lpa, o.offer_date, o.status, o.joining_date,
                   a.application_id, a.student_id, dr.job_role, c.company_name
            FROM offer o
            JOIN application a ON a.application_id = o.application_id
            JOIN drive dr ON dr.drive_id = a.drive_id
            JOIN company c ON c.company_id = dr.company_id
            WHERE o.offer_id = %s
            """,
            (offer_id,),
        )
        offer = cur.fetchone()

    if offer is None:
        return jsonify({"error": "Offer not found"}), 404

    user = g.current_user
    if user["role"] == "student" and int(user["sub"]) != offer["student_id"]:
        return jsonify({"error": "Forbidden"}), 403

    return jsonify(offer)


@offers_bp.post("/<int:offer_id>/accept")
@require_auth()
def accept_offer(offer_id):
    return _run_transition(offer_service.accept_offer, offer_id)


@offers_bp.post("/<int:offer_id>/decline")
@require_auth()
def decline_offer(offer_id):
    return _run_transition(offer_service.decline_offer, offer_id)


def _run_transition(service_fn, offer_id):
    try:
        result = service_fn(offer_id, g.current_user)
    except offer_service.OfferNotFound as e:
        return jsonify({"error": str(e)}), 404
    except offer_service.NotOfferOwner as e:
        return jsonify({"error": str(e)}), 403
    except offer_service.OfferNotActionable as e:
        return jsonify({"error": str(e)}), 409
    return jsonify(result)
