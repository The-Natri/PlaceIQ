"""
Sets the login passwords of every account, for sharing PlaceIQ publicly and
for going back to the demo afterwards.

  python set_passwords.py            ADMIN_PASSWORD -> every coordinator/TPO,
                                     STUDENT_PASSWORD -> every student (from the
                                     environment, i.e. the git-ignored .env.public)
  python set_passwords.py --demo     back to the documented demo passwords
                                     (Admin@123 / Student@123) for local use

Why: the demo passwords are printed in the README. On a public link anyone could
log in with them, so a shared instance must use passwords only you know.
Each password is hashed once with bcrypt and that hash is stored for every
account of that kind. Hashing per account would take a minute for 180
students and gives no benefit when the plaintext is the same.
Nothing is printed except counts.
"""
import os
import sys

import bcrypt
import psycopg2

DEMO = {"ADMIN_PASSWORD": "Admin@123", "STUDENT_PASSWORD": "Student@123"}


def strong(pw: str) -> bool:
    return len(pw) >= 12 and pw not in DEMO.values()


def main():
    demo = "--demo" in sys.argv
    passwords = DEMO if demo else {k: os.environ.get(k, "") for k in DEMO}
    if not demo:
        weak = [k for k, v in passwords.items() if not strong(v)]
        if weak:
            sys.exit(f"set_passwords: {', '.join(weak)} missing or too weak (12+ characters, not a demo password).")

    hashes = {k: bcrypt.hashpw(v.encode(), bcrypt.gensalt()).decode() for k, v in passwords.items()}
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    with conn, conn.cursor() as cur:
        cur.execute("UPDATE coordinator SET password_hash = %s", (hashes["ADMIN_PASSWORD"],))
        admins = cur.rowcount
        cur.execute("UPDATE student SET password_hash = %s", (hashes["STUDENT_PASSWORD"],))
        students = cur.rowcount
    conn.close()
    kind = "demo" if demo else "private (from .env.public)"
    print(f"set_passwords: {kind} passwords set for {admins} admin and {students} student accounts.")


if __name__ == "__main__":
    main()
