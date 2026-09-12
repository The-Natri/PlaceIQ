"""
Password hashing (bcrypt) and JWT issuing/verification.

Bcrypt (not plain SHA-256 or MD5) is used because it is a deliberately slow,
salted hash designed to resist brute-forcing even if the `password_hash`
column leaks — this matters more than most columns in this schema since
student/coordinator credentials sit behind it.
"""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from config import Config


def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))


def generate_token(*, sub: int, role: str, email: str, name: str, extra: dict | None = None) -> str:
    """
    `sub` is always the row's own PK (student_id or coordinator_id) — `role`
    is what the rest of the app uses to tell which table/permissions apply,
    since the two id spaces overlap (student_id=1 and coordinator_id=1 are
    unrelated people).
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "role": role,
        "email": email,
        "name": name,
        "iat": now,
        "exp": now + timedelta(hours=Config.JWT_EXPIRY_HOURS),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, Config.JWT_SECRET_KEY, algorithm=Config.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Raises jwt.ExpiredSignatureError / jwt.InvalidTokenError on failure — caller handles those."""
    return jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=[Config.JWT_ALGORITHM])
