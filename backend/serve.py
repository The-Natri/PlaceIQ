"""
Production entry point: the waitress WSGI server, serving the API and the
built frontend on one port (default http://127.0.0.1:8080).

Why waitress: Flask's built-in server is for development only (single
process, debugger risk, not hardened). waitress is a production-grade,
pure-Python server that runs on Windows as well as Linux, unlike gunicorn.

Run:  python serve.py        (from backend/, after npm run build in frontend/)
"""
import os

from waitress import serve

from app import create_app
from config import Config


def write_pidfile():
    """
    When PLACEIQ_PIDFILE is set (start.sh does this), records this server's
    own process id there, so the stop script can end exactly this process.
    The server writes it itself because on Windows the id a shell sees for a
    background job is not the Python process (a venv's python.exe is a
    launcher that starts the real interpreter as a child).
    """
    path = os.environ.get("PLACEIQ_PIDFILE")
    if path:
        with open(path, "w") as f:
            f.write(str(os.getpid()))


def main():
    write_pidfile()
    app = create_app()
    print(f"PlaceIQ is serving on http://{'localhost' if Config.HOST in ('127.0.0.1', '0.0.0.0') else Config.HOST}:{Config.PORT}", flush=True)
    # threads: concurrent requests. The DB pool (db.py, maxconn 10) is larger,
    # so a request never waits for a connection.
    serve(app, host=Config.HOST, port=Config.PORT, threads=8)


if __name__ == "__main__":
    main()
