"""
Database access layer.

DELIBERATE CHOICE: raw psycopg2 (a connection pool + parameterized SQL),
NOT an ORM like SQLAlchemy. The whole point of this project is the SQL
design (schema, triggers, procedures, views) — an ORM would auto-generate
queries and quietly hide exactly the SQL we need to be able to point at and
explain in the viva. Every query in routes/ and services/ is therefore
plain, visible SQL passed through here.

A connection pool (not one connection per request opened/closed by hand) is
used because Flask handles requests on multiple threads in dev/prod, and
opening a fresh TCP+auth handshake to Postgres per request would be wasteful
and, under concurrent requests, is exactly the kind of behaviour worth
avoiding via a pool.
"""
import contextlib

import psycopg2
import psycopg2.extras
from psycopg2.pool import SimpleConnectionPool

from config import Config

_pool: SimpleConnectionPool | None = None


def init_pool(minconn: int = 1, maxconn: int = 10) -> None:
    global _pool
    if _pool is None:
        _pool = SimpleConnectionPool(minconn, maxconn, dsn=Config.DATABASE_URL)


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None


@contextlib.contextmanager
def get_cursor(commit: bool = False):
    """
    Yields a RealDictCursor (rows come back as dict-like objects, so routes
    can do `row["cgpa"]` instead of tracking positional column order) bound
    to a pooled connection.

    commit=True: caller intends to write; the transaction is committed on
    clean exit and explicitly rolled back if an exception propagates — this
    is the same explicit commit/rollback pattern used, at larger scale, by
    the offer-acceptance transaction in services/offer_service.py.
    """
    if _pool is None:
        init_pool()
    conn = _pool.getconn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            yield cur
            if commit:
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
    finally:
        _pool.putconn(conn)
