"""
Offer acceptance / decline — the explicit multi-table transaction demo
called for in the assignment spec: "offer acceptance should be an explicit
multi-table transaction (update Offer status, update Student status, log to
Offer_History) with rollback on failure, implemented visibly, not hidden
behind an ORM's auto transaction."

This is deliberately written as raw psycopg2 with a manual
try / conn.commit() / except / conn.rollback() block (see db.get_connection)
rather than reusing the generic get_cursor(commit=True) helper, so the
transaction boundary is unmistakable to someone reading this file cold.

WHY "update Student status" is meaningful on BOTH paths, not just accept:
- ACCEPT: student.placement_status is already 'Placed' by this point (the
  AFTER INSERT trigger on `offer` set it the moment the offer was created —
  see schema.sql Section 3). This function re-asserts it anyway, both to
  satisfy the transaction demo's own 3-step shape and as a harmless,
  idempotent safety net.
- DECLINE: this is where "update Student status" earns its place for real.
  If the student has no OTHER Pending/Accepted offer once this one is
  declined, they should revert to 'Not Placed' — the trigger only ever
  turns placement_status ON, it never turns it back off, so a decline with
  no remaining active offer would otherwise leave the student stuck showing
  'Placed' with zero live offers. That's exactly the kind of check-then-act
  logic ("count remaining active offers, THEN decide") that needs to run
  inside a single atomic transaction rather than as two separate requests.
"""
import psycopg2.extras

import db


class OfferNotFound(Exception):
    pass


class OfferNotActionable(Exception):
    """Offer exists but is not in 'Pending' state (already Accepted/Declined)."""
    pass


class NotOfferOwner(Exception):
    """A student attempted to act on an offer that isn't theirs."""
    pass


def _load_offer_owner(cur, offer_id: int):
    cur.execute(
        """
        SELECT o.offer_id, o.status, a.student_id
        FROM offer o
        JOIN application a ON a.application_id = o.application_id
        WHERE o.offer_id = %s
        """,
        (offer_id,),
    )
    return cur.fetchone()


def _authorize(requesting_user: dict, owner_student_id: int):
    if requesting_user["role"] == "student" and int(requesting_user["sub"]) != owner_student_id:
        raise NotOfferOwner("This offer does not belong to the requesting student")


def accept_offer(offer_id: int, requesting_user: dict) -> dict:
    with db.get_connection() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            offer_row = _load_offer_owner(cur, offer_id)
            if offer_row is None:
                raise OfferNotFound(f"Offer {offer_id} does not exist")
            _authorize(requesting_user, offer_row["student_id"])
            student_id = offer_row["student_id"]

            # --- Statement 1: flip the Offer itself -----------------------
            # WHERE status='Pending' + RETURNING doubles as an atomic guard:
            # if two requests race to accept/decline the same offer, only
            # the first UPDATE finds a matching row — the second gets back
            # no row and this function raises instead of silently
            # double-processing the offer.
            cur.execute(
                """
                UPDATE offer
                SET status = 'Accepted',
                    joining_date = COALESCE(joining_date, offer_date + INTERVAL '60 days')
                WHERE offer_id = %s AND status = 'Pending'
                RETURNING offer_id
                """,
                (offer_id,),
            )
            if cur.fetchone() is None:
                raise OfferNotActionable(
                    f"Offer {offer_id} is not Pending (already actioned or invalid)"
                )

            # --- Statement 2: update Student status ------------------------
            cur.execute(
                "UPDATE student SET placement_status = 'Placed' WHERE student_id = %s",
                (student_id,),
            )

            # --- Statement 3: append to the audit trail ---------------------
            cur.execute(
                "INSERT INTO offer_history (offer_id, action, notes) VALUES (%s, 'Accepted', %s)",
                (offer_id, "Offer accepted by student"),
            )

            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()

    return {"offer_id": offer_id, "status": "Accepted"}


def decline_offer(offer_id: int, requesting_user: dict) -> dict:
    with db.get_connection() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            offer_row = _load_offer_owner(cur, offer_id)
            if offer_row is None:
                raise OfferNotFound(f"Offer {offer_id} does not exist")
            _authorize(requesting_user, offer_row["student_id"])
            student_id = offer_row["student_id"]

            # --- Statement 1: flip the Offer itself -----------------------
            cur.execute(
                "UPDATE offer SET status = 'Declined' WHERE offer_id = %s AND status = 'Pending' "
                "RETURNING offer_id",
                (offer_id,),
            )
            if cur.fetchone() is None:
                raise OfferNotActionable(
                    f"Offer {offer_id} is not Pending (already actioned or invalid)"
                )

            # --- Statement 2: update Student status, conditionally ---------
            # Only revert to 'Not Placed' if this was the student's last
            # remaining active offer — they may still hold another
            # Pending/Accepted offer from a different drive.
            cur.execute(
                """
                SELECT COUNT(*) AS active_offers
                FROM offer o
                JOIN application a ON a.application_id = o.application_id
                WHERE a.student_id = %s AND o.status IN ('Pending', 'Accepted')
                """,
                (student_id,),
            )
            remaining_active = cur.fetchone()["active_offers"]
            if remaining_active == 0:
                cur.execute(
                    "UPDATE student SET placement_status = 'Not Placed' WHERE student_id = %s",
                    (student_id,),
                )

            # --- Statement 3: append to the audit trail ---------------------
            cur.execute(
                "INSERT INTO offer_history (offer_id, action, notes) VALUES (%s, 'Declined', %s)",
                (offer_id, "Offer declined by student"),
            )

            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()

    return {"offer_id": offer_id, "status": "Declined"}
