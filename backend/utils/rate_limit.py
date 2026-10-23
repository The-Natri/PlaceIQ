"""
A small in-memory rate limiter for the login and signup endpoints, so a
shared (public) instance can't be brute-forced: each client gets at most
LIMIT attempts per WINDOW_S seconds, after which it gets 429 and a
Retry-After header.

In memory, per process, with no extra dependency: PlaceIQ runs as one waitress
process, so a dict guarded by a lock is enough. (Several processes or servers
would need a shared store such as Redis.)

Who is "the client": normally the TCP peer address. In PUBLIC_MODE the app
sits behind a Cloudflare tunnel, so every request arrives from the local
tunnel process and the real visitor is in the CF-Connecting-IP header. That
header is only trusted in PUBLIC_MODE, where the app's port is bound to
127.0.0.1 and the only way in from outside is the tunnel. Anywhere else a
client could set the header itself to dodge the limit.
"""
import threading
import time
from collections import defaultdict, deque
from functools import wraps

from flask import jsonify, request

from config import Config

import os

LIMIT = 10
WINDOW_S = 300
# On for a public instance. A local instance (tests log in dozens of times
# from 127.0.0.1) leaves it off unless RATE_LIMIT=1 asks for it.
ENABLED = Config.PUBLIC_MODE or os.environ.get("RATE_LIMIT") == "1"

_attempts = defaultdict(deque)  # (client, bucket) -> timestamps of recent attempts
_lock = threading.Lock()


# Which header holds the visitor's address when PUBLIC_MODE is on. The
# Cloudflare tunnel sets CF-Connecting-IP. Behind another proxy (for example a
# hosting platform, see DEPLOY_FREE.md) set RATE_LIMIT_IP_HEADER to the header
# that proxy sets; the first address in a comma-separated list is used.
IP_HEADER = os.environ.get("RATE_LIMIT_IP_HEADER", "CF-Connecting-IP")


def client_id() -> str:
    if Config.PUBLIC_MODE and request.headers.get(IP_HEADER):
        return request.headers[IP_HEADER].split(",")[0].strip()
    return request.remote_addr or "unknown"


def rate_limited(bucket: str):
    """Decorator: allow LIMIT calls per WINDOW_S seconds per client for this bucket."""
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if not ENABLED:
                return view(*args, **kwargs)
            now = time.monotonic()
            key = (client_id(), bucket)
            with _lock:
                recent = _attempts[key]
                while recent and now - recent[0] > WINDOW_S:
                    recent.popleft()
                if len(recent) >= LIMIT:
                    retry_after = int(WINDOW_S - (now - recent[0])) + 1
                    response = jsonify({"error": f"Too many attempts. Try again in {retry_after} seconds."})
                    response.headers["Retry-After"] = str(retry_after)
                    return response, 429
                recent.append(now)
                if len(_attempts) > 10000:  # keep memory bounded: drop idle clients
                    for k in [k for k, q in _attempts.items() if not q or now - q[-1] > WINDOW_S]:
                        del _attempts[k]
            return view(*args, **kwargs)
        return wrapper
    return decorator
