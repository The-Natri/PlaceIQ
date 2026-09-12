"""
Synthetic dataset generator for the College Placement Management System.

WHY THIS EXISTS (read before touching the numbers below):
The ML placement-probability widget is only meaningful if the training data
has real signal — i.e. placement outcome must actually correlate with CGPA,
backlogs, and skill count, not be assigned uniformly at random. This script
builds that correlation explicitly:

  1. Each company is assigned a "tier" (1 = hardest/highest package, 3 =
     easiest/lowest package), which sets that company's drives' min_cgpa /
     max_backlogs cutoffs and package range.
  2. Eligibility to even APPLY to a drive is checked by calling the
     database's own `fn_check_eligibility()` SQL function (db/schema.sql,
     Section 4) rather than re-implementing the rule in Python — this both
     saves duplicate logic AND is a live end-to-end test that the function
     works correctly against real rows.
  3. Whether an eligible applicant is actually SELECTED is a logistic
     function of (cgpa margin above the drive's cutoff, backlogs, skill
     count, company tier) — see `selection_probability()`. Interview rounds
     and final Offer rows are generated consistent with that outcome, and
     Offer inserts go through the real `offer` table, so the placement_status
     trigger (schema.sql Section 3) fires exactly as it would in production
     use, not via a Python shortcut.

Run with:  python db/seed.py   (after `docker compose up -d db` and
           `psql ... -f db/schema.sql`, or let this script run both — see
           bottom of file / README).

All data is entirely fictional/synthetic — company names, student names, and
credentials below are not real people, institutions, or organizations.
"""

import math
import os
import random
from datetime import date, timedelta

import bcrypt
import psycopg2
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Reproducibility: fixed seed so re-running produces the identical dataset
# (useful for grading/demo consistency and for debugging the ML model on a
# stable dataset instead of chasing a moving target).
# ---------------------------------------------------------------------------
random.seed(42)

load_dotenv()
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://placement_admin:placement_dev_password@localhost:5432/placement_db",
)

# Default password for every seeded student account — documented here so you
# can actually log in and demo the app. Real signup would hash a user-chosen
# password the same way (see backend/utils/security.py).
DEFAULT_STUDENT_PASSWORD = "Student@123"
DEFAULT_ADMIN_PASSWORD = "Admin@123"


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


# =============================================================================
# Reference data
# =============================================================================

DEPARTMENTS = [
    ("Computer Science Engineering", "CSE"),
    ("Information Science Engineering", "ISE"),
    ("Electronics & Communication", "ECE"),
    ("Electrical & Electronics", "EEE"),
    ("Mechanical Engineering", "MECH"),
    ("Artificial Intelligence & ML", "AIML"),
]

SKILLS = [
    "Python", "Java", "C++", "JavaScript", "SQL", "React", "Node.js",
    "Machine Learning", "Data Structures", "Algorithms", "Django", "Flask",
    "AWS", "Docker", "Git", "Spring Boot", "REST APIs", "MongoDB",
    "PostgreSQL", "Linux", "TensorFlow", "Pandas", "Excel", "AutoCAD",
    "Embedded C", "Power Systems", "MATLAB", "CAD/CAM",
]

FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Krishna",
    "Ishaan", "Rohan", "Ananya", "Diya", "Saanvi", "Aadhya", "Myra", "Anika",
    "Ira", "Pari", "Riya", "Kavya", "Aryan", "Kabir", "Dhruv", "Rudra",
    "Advait", "Nikhil", "Varun", "Siddharth", "Meera", "Sneha", "Pooja",
    "Neha", "Divya", "Shreya", "Tanvi", "Aisha", "Manya", "Prisha", "Zara",
    "Yash", "Karan", "Rahul", "Amit", "Sanjay", "Deepak", "Vikram", "Naveen",
    "Harish", "Lakshmi", "Priya",
]
LAST_NAMES = [
    "Sharma", "Verma", "Gupta", "Reddy", "Rao", "Nair", "Iyer", "Kumar",
    "Singh", "Patel", "Menon", "Pillai", "Shetty", "Bhat", "Hegde", "Gowda",
    "Krishnan", "Joshi", "Desai", "Kulkarni", "Mishra", "Chatterjee", "Das",
    "Banerjee", "Agarwal",
]

# tier -> (min_cgpa range, max_backlogs, package_lpa range, difficulty factor)
COMPANY_TIERS = {
    1: {"min_cgpa": (8.0, 8.5), "max_backlogs": 0, "package": (15.0, 32.0), "difficulty": 1.4},
    2: {"min_cgpa": (7.0, 7.5), "max_backlogs": 1, "package": (8.0, 15.0), "difficulty": 0.7},
    3: {"min_cgpa": (6.0, 6.5), "max_backlogs": 2, "package": (3.5, 7.5), "difficulty": 0.0},
}

# (company_name, industry_sector, tier, software_focused)
# software_focused companies restrict drives to CSE/ISE/AIML/ECE;
# core companies restrict to MECH/EEE/ECE. Names are fictional.
COMPANIES = [
    ("Nimbus Cloud Systems", "Software / Cloud", 1, True),
    ("Vertex Analytics", "Software / Data", 1, True),
    ("Orbital Fintech", "Fintech", 1, True),
    ("Quantara Labs", "Software / AI", 1, True),
    ("Helios Semiconductors", "Semiconductors", 1, False),
    ("Bluepeak Software", "Software / IT Services", 2, True),
    ("Crestline Systems", "Software / IT Services", 2, True),
    ("Aster Technologies", "Software / IT Services", 2, True),
    ("Pinnacle Networks", "Telecom / Networking", 2, False),
    ("Ironclad Manufacturing", "Core / Manufacturing", 2, False),
    ("Voltedge Power", "Core / Power Systems", 2, False),
    ("Meridian Consulting", "IT Consulting", 2, True),
    ("Silverline Info Systems", "Software / IT Services", 3, True),
    ("Coral Bay Solutions", "Software / IT Services", 3, True),
    ("Granite Motors", "Core / Automotive", 3, False),
    ("Everstone Infra", "Core / Infrastructure", 3, False),
    ("Brightwave BPO", "ITES / BPO", 3, True),
    ("Solstice Retail Tech", "Software / Retail", 3, True),
]


def build_reg_no(dept_code: str, batch_year: int, seq: int) -> str:
    return f"{dept_code}{batch_year}{seq:03d}"


def selection_probability(cgpa, backlogs, skill_count, drive):
    """
    Core "not random" signal-generation logic. Higher CGPA margin above the
    drive's own cutoff, fewer backlogs, and more skills all push probability
    up; a harder (tier-1) company pulls it back down. This is deliberately a
    logistic function (not a hard threshold) so outcomes have realistic
    noise around the boundary instead of a suspiciously clean cliff — while
    still being strongly correlated with the inputs, which is what gives the
    logistic-regression ML model real signal to learn from later.
    """
    margin = cgpa - float(drive["min_cgpa"])
    score = (
        -1.5
        + 1.3 * margin
        - 1.2 * backlogs
        + 0.10 * skill_count
        - 0.9 * drive["difficulty"]
    )
    p = sigmoid(score)
    return min(max(p, 0.03), 0.92)


def main():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor()

    print("Clearing existing data (TRUNCATE ... RESTART IDENTITY CASCADE)...")
    cur.execute(
        """
        TRUNCATE TABLE offer_history, offer, interview_round, application,
                       drive_eligible_dept, drive, student_skill, skill,
                       company, student, coordinator, department
        RESTART IDENTITY CASCADE
        """
    )
    conn.commit()

    # -------------------------------------------------------------------
    # Departments
    # -------------------------------------------------------------------
    dept_ids = {}
    for name, code in DEPARTMENTS:
        cur.execute(
            "INSERT INTO department (dept_name, dept_code) VALUES (%s, %s) RETURNING dept_id",
            (name, code),
        )
        dept_ids[code] = cur.fetchone()[0]
    conn.commit()
    print(f"Inserted {len(dept_ids)} departments.")

    # -------------------------------------------------------------------
    # Coordinators (admin/TPO logins)
    # -------------------------------------------------------------------
    cur.execute(
        "INSERT INTO coordinator (name, email, password_hash, role) VALUES (%s,%s,%s,%s)",
        ("Placement Officer", "tpo@campus.edu", hash_password(DEFAULT_ADMIN_PASSWORD), "TPO"),
    )
    cur.execute(
        "INSERT INTO coordinator (name, email, password_hash, role) VALUES (%s,%s,%s,%s) RETURNING coordinator_id",
        ("Placement Coordinator", "coordinator@campus.edu", hash_password(DEFAULT_ADMIN_PASSWORD), "Coordinator"),
    )
    coordinator_ids = [1, cur.fetchone()[0]]
    conn.commit()
    print("Inserted 2 coordinator/TPO accounts "
          "(tpo@campus.edu / coordinator@campus.edu, password: Admin@123).")

    # -------------------------------------------------------------------
    # Skills
    # -------------------------------------------------------------------
    skill_ids = []
    for s in SKILLS:
        cur.execute("INSERT INTO skill (skill_name) VALUES (%s) RETURNING skill_id", (s,))
        skill_ids.append(cur.fetchone()[0])
    conn.commit()
    print(f"Inserted {len(skill_ids)} skills.")

    # -------------------------------------------------------------------
    # Companies
    # -------------------------------------------------------------------
    company_rows = []  # (company_id, tier, software_focused)
    for name, sector, tier, sw in COMPANIES:
        cur.execute(
            "INSERT INTO company (company_name, industry_sector, website, hr_email) "
            "VALUES (%s,%s,%s,%s) RETURNING company_id",
            (name, sector, f"https://www.{name.lower().replace(' ', '')}.example.com",
             f"hr@{name.lower().replace(' ', '')}.example.com"),
        )
        company_rows.append((cur.fetchone()[0], tier, sw))
    conn.commit()
    print(f"Inserted {len(company_rows)} companies.")

    # -------------------------------------------------------------------
    # Students (~180), CGPA/backlogs/skills deliberately correlated so the
    # downstream selection simulation (and therefore the ML label) has
    # real signal — see selection_probability().
    # -------------------------------------------------------------------
    students = []  # dicts with id, cgpa, backlogs, dept_code, skill_count
    used_emails = set()
    seq_by_dept = {code: 0 for _, code in DEPARTMENTS}
    STUDENTS_PER_DEPT = 30

    for _, dept_code in DEPARTMENTS:
        for _ in range(STUDENTS_PER_DEPT):
            seq_by_dept[dept_code] += 1
            batch_year = random.choice([2022, 2023, 2023, 2024, 2024])
            reg_no = build_reg_no(dept_code, batch_year, seq_by_dept[dept_code])

            cgpa = round(min(max(random.gauss(7.2, 1.0), 4.5), 9.9), 2)
            # Backlogs anti-correlated with CGPA: weaker students are more
            # likely to be carrying backlogs, but it's still probabilistic,
            # not deterministic, to keep the dataset realistic.
            backlog_lambda = max(0.0, (7.5 - cgpa) * 0.9)
            backlogs = min(int(random.gauss(backlog_lambda, 1.0) + 0.5) if backlog_lambda > 0 else 0, 6)
            backlogs = max(backlogs, 0)

            first = random.choice(FIRST_NAMES)
            last = random.choice(LAST_NAMES)
            name = f"{first} {last}"
            email_base = f"{first.lower()}.{last.lower()}{seq_by_dept[dept_code]}{dept_code.lower()}"
            email = f"{email_base}@campus.edu"
            while email in used_emails:
                email = f"{email_base}{random.randint(1,999)}@campus.edu"
            used_emails.add(email)

            phone = f"9{random.randint(100000000, 999999999)}"

            cur.execute(
                """
                INSERT INTO student
                    (reg_no, name, email, password_hash, dept_id, cgpa, backlogs, batch_year, phone)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING student_id
                """,
                (reg_no, name, email, hash_password(DEFAULT_STUDENT_PASSWORD),
                 dept_ids[dept_code], cgpa, backlogs, batch_year, phone),
            )
            student_id = cur.fetchone()[0]

            # Skill count mildly correlated with CGPA (stronger students
            # tend to have picked up a few more skills), plus noise.
            base_skills = 2 + int((cgpa - 5.0) * 0.8)
            n_skills = min(max(base_skills + random.randint(-2, 2), 1), 9)
            chosen_skills = random.sample(skill_ids, n_skills)
            for sk_id in chosen_skills:
                cur.execute(
                    "INSERT INTO student_skill (student_id, skill_id) VALUES (%s,%s)",
                    (student_id, sk_id),
                )

            students.append({
                "id": student_id, "cgpa": cgpa, "backlogs": backlogs,
                "dept_code": dept_code, "dept_id": dept_ids[dept_code],
                "skill_count": n_skills,
            })

    conn.commit()
    print(f"Inserted {len(students)} students (with skills).")

    # -------------------------------------------------------------------
    # Drives
    # -------------------------------------------------------------------
    SOFTWARE_DEPTS = ["CSE", "ISE", "AIML", "ECE"]
    CORE_DEPTS = ["MECH", "EEE", "ECE"]
    ROLES_SOFTWARE = ["Software Engineer", "Data Analyst", "SDE Intern", "Backend Developer",
                      "Full Stack Developer", "ML Engineer", "QA Engineer"]
    ROLES_CORE = ["Graduate Engineer Trainee", "Design Engineer", "Field Engineer", "Core Engineer"]

    season_start = date(2025, 8, 1)
    drives = []  # dicts: id, company_id, tier, min_cgpa, max_backlogs, package, status, restricted_depts
    coord_cycle = 0

    for company_id, tier, sw in company_rows:
        n_drives = random.choice([1, 1, 2])
        for _ in range(n_drives):
            tier_cfg = COMPANY_TIERS[tier]
            min_cgpa = round(random.uniform(*tier_cfg["min_cgpa"]), 2)
            max_backlogs = tier_cfg["max_backlogs"]
            package = round(random.uniform(*tier_cfg["package"]), 2)
            role = random.choice(ROLES_SOFTWARE if sw else ROLES_CORE)
            drive_type = random.choices(["Full-Time", "Internship"], weights=[80, 20])[0]
            drive_date = season_start + timedelta(days=random.randint(0, 210))
            status = random.choices(
                ["Completed", "Ongoing", "Upcoming"], weights=[65, 25, 10]
            )[0]
            coordinator_id = coordinator_ids[coord_cycle % len(coordinator_ids)]
            coord_cycle += 1

            cur.execute(
                """
                INSERT INTO drive
                    (company_id, coordinator_id, job_role, drive_date, package_lpa,
                     min_cgpa, max_backlogs, drive_type, status)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING drive_id
                """,
                (company_id, coordinator_id, role, drive_date, package,
                 min_cgpa, max_backlogs, drive_type, status),
            )
            drive_id = cur.fetchone()[0]

            # ~60% of drives are department-restricted; the rest are open to
            # all departments (no rows in drive_eligible_dept at all).
            restricted = []
            if random.random() < 0.6:
                pool = SOFTWARE_DEPTS if sw else CORE_DEPTS
                k = random.randint(1, len(pool))
                restricted = random.sample(pool, k)
                for dc in restricted:
                    cur.execute(
                        "INSERT INTO drive_eligible_dept (drive_id, dept_id) VALUES (%s,%s)",
                        (drive_id, dept_ids[dc]),
                    )

            drives.append({
                "id": drive_id, "min_cgpa": min_cgpa, "max_backlogs": max_backlogs,
                "package": package, "status": status, "difficulty": tier_cfg["difficulty"],
                "drive_type": drive_type, "drive_date": drive_date,
            })

    conn.commit()
    print(f"Inserted {len(drives)} drives.")

    # -------------------------------------------------------------------
    # Applications, interview rounds, offers.
    # Eligibility is checked by calling the DB's own fn_check_eligibility()
    # (not reimplemented here) so the seed data is guaranteed consistent
    # with the same rule the backend uses at request time.
    # -------------------------------------------------------------------
    APPLY_PROB = 0.45
    n_applications = 0
    n_offers = 0

    for drive in drives:
        if drive["status"] == "Upcoming":
            continue  # nothing has happened yet for a not-yet-run drive

        eligible_students = []
        for s in students:
            cur.execute(
                "SELECT fn_check_eligibility(%s, %s)", (s["id"], drive["id"])
            )
            if cur.fetchone()[0]:
                eligible_students.append(s)

        applicants = [s for s in eligible_students if random.random() < APPLY_PROB]

        for s in applicants:
            cur.execute(
                "INSERT INTO application (student_id, drive_id, status) "
                "VALUES (%s,%s,%s) RETURNING application_id",
                (s["id"], drive["id"], "Applied"),
            )
            application_id = cur.fetchone()[0]
            n_applications += 1

            if drive["status"] == "Ongoing":
                # Snapshot mid-process: leave in an intermediate state, no
                # final outcome yet (this is what makes the demo account's
                # "in progress" applications look realistic).
                partial_status = random.choices(
                    ["Applied", "Shortlisted", "Interview_Scheduled"],
                    weights=[55, 25, 20],
                )[0]
                if partial_status != "Applied":
                    cur.execute(
                        "UPDATE application SET status=%s WHERE application_id=%s",
                        (partial_status, application_id),
                    )
                    cur.execute(
                        "INSERT INTO interview_round "
                        "(application_id, round_number, round_type, round_date, result) "
                        "VALUES (%s,1,%s,%s,'Pass')",
                        (application_id, "Aptitude", drive["drive_date"]),
                    )
                continue

            # drive["status"] == "Completed": run the full simulation.
            n_rounds = 2 if drive["drive_type"] == "Internship" else 3
            round_types = (["Aptitude", "Technical"] if n_rounds == 2
                            else ["Aptitude", "Technical", "HR"])

            p_select = selection_probability(s["cgpa"], s["backlogs"], s["skill_count"], drive)
            selected = random.random() < p_select

            if selected:
                for i, rtype in enumerate(round_types, start=1):
                    cur.execute(
                        "INSERT INTO interview_round "
                        "(application_id, round_number, round_type, round_date, result) "
                        "VALUES (%s,%s,%s,%s,'Pass')",
                        (application_id, i, rtype, drive["drive_date"] + timedelta(days=i)),
                    )
                cur.execute(
                    "UPDATE application SET status='Selected' WHERE application_id=%s",
                    (application_id,),
                )

                offered_package = round(max(drive["package"] + random.uniform(-0.5, 1.5), 1.0), 2)
                offer_date = drive["drive_date"] + timedelta(days=n_rounds + 2)
                offer_status = random.choices(
                    ["Accepted", "Pending", "Declined"], weights=[70, 18, 12]
                )[0]
                joining_date = offer_date + timedelta(days=60) if offer_status == "Accepted" else None

                cur.execute(
                    """
                    INSERT INTO offer
                        (application_id, offered_package_lpa, offer_date, status, joining_date)
                    VALUES (%s,%s,%s,%s,%s)
                    RETURNING offer_id
                    """,
                    (application_id, offered_package, offer_date, offer_status, joining_date),
                )
                offer_id = cur.fetchone()[0]
                n_offers += 1

                cur.execute(
                    "INSERT INTO offer_history (offer_id, action, action_timestamp, notes) "
                    "VALUES (%s,'Created',%s,'Offer generated by seed script')",
                    (offer_id, offer_date),
                )
                if offer_status in ("Accepted", "Declined"):
                    cur.execute(
                        "INSERT INTO offer_history (offer_id, action, action_timestamp, notes) "
                        "VALUES (%s,%s,%s,%s)",
                        (offer_id, offer_status, offer_date + timedelta(days=3),
                         f"Candidate {offer_status.lower()} the offer"),
                    )

                cur.execute(
                    "UPDATE application SET status='Offer_Made' WHERE application_id=%s",
                    (application_id,),
                )
            else:
                fail_at = random.randint(1, n_rounds)
                for i, rtype in enumerate(round_types, start=1):
                    if i < fail_at:
                        result = "Pass"
                    elif i == fail_at:
                        result = "Fail"
                    else:
                        break
                    cur.execute(
                        "INSERT INTO interview_round "
                        "(application_id, round_number, round_type, round_date, result) "
                        "VALUES (%s,%s,%s,%s,%s)",
                        (application_id, i, rtype, drive["drive_date"] + timedelta(days=i), result),
                    )
                cur.execute(
                    "UPDATE application SET status='Rejected' WHERE application_id=%s",
                    (application_id,),
                )

        conn.commit()

    print(f"Inserted {n_applications} applications and {n_offers} offers "
          f"(placement_status trigger fired on each offer insert).")

    cur.execute("SELECT COUNT(*) FROM student WHERE placement_status = 'Placed'")
    placed_count = cur.fetchone()[0]
    print(f"Students marked 'Placed' by the trigger: {placed_count} / {len(students)}")

    cur.close()
    conn.close()
    print("Seeding complete.")


if __name__ == "__main__":
    main()
