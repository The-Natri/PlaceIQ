"""
Maps the custom SQLSTATE codes raised by the database's business-rule
triggers and procedure (schema.sql Sections 6 and 8) to HTTP responses.

The rules themselves live in the database; the backend only translates
"the database refused this" into the right status code, using the error
code rather than parsing the message text.
"""
import psycopg2
from flask import jsonify

BUSINESS_RULE_HTTP_STATUS = {
    "PL001": 403,  # student not eligible for the drive
    "PL002": 409,  # drive is closed to applications
    "PL003": 409,  # student has already accepted an offer
    "PL004": 404,  # drive does not exist
    "PL005": 409,  # drive is already closed
    "PL006": 409,  # offer on an application that isn't Selected
    "PL007": 409,  # illegal application status transition
    "PL008": 409,  # application after the drive's deadline (or dated in the future)
}


def business_rule_response(err: psycopg2.Error):
    """Returns a (response, status) tuple for a business-rule error, or None for any other error."""
    status = BUSINESS_RULE_HTTP_STATUS.get(err.pgcode)
    if status is None:
        return None
    return jsonify({"error": err.diag.message_primary}), status
