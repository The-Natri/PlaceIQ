"""
Route-protection decorator. A single `require_auth(roles=...)` factory
(rather than separate `token_required` / `admin_required` decorators stacked
on top of each other) so the token is decoded exactly once per request and
the role check happens in the same place the token is validated.
"""
from functools import wraps

import jwt
from flask import g, jsonify, request

from utils.security import decode_token


def require_auth(roles: list[str] | None = None):
    """
    roles=None      -> any valid, non-expired token (student or admin) may call this.
    roles=["admin"] -> only coordinator/TPO tokens.
    roles=["student"] -> only student tokens.

    On success, g.current_user is set to the decoded JWT payload
    ({"sub": id, "role": ..., "email": ..., "name": ...}) for the route to use.
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return jsonify({"error": "Missing or malformed Authorization header"}), 401

            token = auth_header.split(" ", 1)[1]
            try:
                payload = decode_token(token)
            except jwt.ExpiredSignatureError:
                return jsonify({"error": "Token expired, please log in again"}), 401
            except jwt.InvalidTokenError:
                return jsonify({"error": "Invalid token"}), 401

            if roles is not None and payload.get("role") not in roles:
                return jsonify({"error": "Forbidden: insufficient role"}), 403

            g.current_user = payload
            return f(*args, **kwargs)
        return wrapped
    return decorator
