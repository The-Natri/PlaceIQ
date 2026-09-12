-- =============================================================================
-- College Placement Management System — Database Schema (DDL)
-- Target: Oracle Database, run via SQL*Plus (@schema_oracle.sql)
-- Ported from db/schema.sql (PostgreSQL). Full rationale for every change
-- below is in docs/oracle-differences.md — read that before a viva on this
-- file, since several changes are not just syntax swaps but real semantic
-- differences (see NO_DATA_FOUND handling in Section 4, for one).
--
-- COMPATIBILITY TARGET: written to run on Oracle 9i and later (so it works
-- whether the lab machine has 11g, 12c, 19c, or 21c) — this is why auto-
-- increment PKs use the classic SEQUENCE + BEFORE INSERT TRIGGER pattern
-- instead of `GENERATED ALWAYS AS IDENTITY`, which only exists from Oracle
-- 12c onward. If your Oracle is confirmed 12c+, IDENTITY is a valid, simpler
-- alternative — see docs/oracle-differences.md for that version.
--
-- SQL*PLUS MECHANICS: every PL/SQL block below (CREATE ... TRIGGER, CREATE
-- ... FUNCTION) ends with a `/` on its own line. That is not a typo or an
-- extra semicolon — SQL*Plus needs it to know where a PL/SQL block ends,
-- since the block's own body is full of ordinary semicolons. Plain DDL
-- (CREATE TABLE, CREATE INDEX, CREATE VIEW, CREATE SEQUENCE) needs no `/`,
-- a trailing `;` is enough, same as in the Postgres version.
-- =============================================================================


-- =============================================================================
-- SECTION 1: TABLES (with their surrogate-key SEQUENCE + BEFORE INSERT
-- TRIGGER pairs, and FK-dependency ordering — parents before children, same
-- order as db/schema.sql, so this script runs top-to-bottom with no forward
-- references)
--
-- Every surrogate PK below follows the same three-part pattern:
--   1. CREATE SEQUENCE  <table>_seq  — the counter
--   2. CREATE TABLE     <table>      — the id column is just NUMBER, no
--                                       IDENTITY keyword
--   3. CREATE TRIGGER   trg_<table>_bi  — BEFORE INSERT, fills the id from
--                                          the sequence only if the caller
--                                          didn't already supply one (the
--                                          `WHEN (NEW.col IS NULL)` guard)
-- This is the traditional Oracle idiom for auto-increment and predates
-- IDENTITY columns by two decades, so it is the safest choice when the
-- exact Oracle version available isn't known in advance.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- department: lookup/reference entity. Kept separate (not a VARCHAR2 column
-- on student) so department name changes happen in one place and
-- student.dept_id is a stable FK — this is the textbook 2NF/3NF
-- justification for splitting out a reference table instead of repeating
-- dept_name on every student row.
-- ---------------------------------------------------------------------------
CREATE SEQUENCE department_seq START WITH 1 INCREMENT BY 1;

CREATE TABLE department (
    dept_id     NUMBER PRIMARY KEY,
    dept_name   VARCHAR2(100) NOT NULL UNIQUE,
    dept_code   VARCHAR2(10)  NOT NULL UNIQUE   -- e.g. 'CSE', 'ISE', 'ECE'
);

CREATE OR REPLACE TRIGGER trg_department_bi
BEFORE INSERT ON department
FOR EACH ROW
WHEN (NEW.dept_id IS NULL)
BEGIN
    SELECT department_seq.NEXTVAL INTO :NEW.dept_id FROM dual;
END;
/

-- ---------------------------------------------------------------------------
-- coordinator: TPO / placement-cell admin accounts. Separate table (not a
-- role flag on student) because coordinators are a structurally different
-- principal — different auth claims, no cgpa/dept, and we never want a
-- student row to accidentally gain admin capability via a bad UPDATE.
-- ---------------------------------------------------------------------------
CREATE SEQUENCE coordinator_seq START WITH 1 INCREMENT BY 1;

CREATE TABLE coordinator (
    coordinator_id  NUMBER PRIMARY KEY,
    name            VARCHAR2(100) NOT NULL,
    email           VARCHAR2(120) NOT NULL UNIQUE,
    password_hash   VARCHAR2(255) NOT NULL,      -- bcrypt hash, never plaintext
    role            VARCHAR2(20)  DEFAULT 'Coordinator' NOT NULL
                        CHECK (role IN ('TPO', 'Coordinator')),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE OR REPLACE TRIGGER trg_coordinator_bi
BEFORE INSERT ON coordinator
FOR EACH ROW
WHEN (NEW.coordinator_id IS NULL)
BEGIN
    SELECT coordinator_seq.NEXTVAL INTO :NEW.coordinator_id FROM dual;
END;
/

-- ---------------------------------------------------------------------------
-- student: core entity. placement_status is a DELIBERATE DENORMALIZATION —
-- it is derivable by checking whether an Accepted-or-Created offer exists
-- through this student's applications, but the spec requires a trigger to
-- maintain it directly (see Section 3), and it lets department_stats_view
-- and the dashboard avoid a multi-table join for a very common read. This
-- tradeoff is documented in detail in docs/normalization.md.
-- ---------------------------------------------------------------------------
CREATE SEQUENCE student_seq START WITH 1 INCREMENT BY 1;

CREATE TABLE student (
    student_id          NUMBER PRIMARY KEY,
    reg_no              VARCHAR2(20)  NOT NULL UNIQUE,
    name                VARCHAR2(100) NOT NULL,
    email               VARCHAR2(120) NOT NULL UNIQUE,
    password_hash       VARCHAR2(255) NOT NULL,
    dept_id             NUMBER NOT NULL REFERENCES department(dept_id),
    cgpa                NUMBER(4,2) NOT NULL CHECK (cgpa BETWEEN 0 AND 10),
    backlogs            NUMBER DEFAULT 0 NOT NULL CHECK (backlogs >= 0),
    batch_year          NUMBER NOT NULL CHECK (batch_year BETWEEN 2000 AND 2100),
    phone               VARCHAR2(15),
    placement_status    VARCHAR2(20) DEFAULT 'Not Placed' NOT NULL
                            CHECK (placement_status IN ('Not Placed', 'Placed')),
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE OR REPLACE TRIGGER trg_student_bi
BEFORE INSERT ON student
FOR EACH ROW
WHEN (NEW.student_id IS NULL)
BEGIN
    SELECT student_seq.NEXTVAL INTO :NEW.student_id FROM dual;
END;
/

-- ---------------------------------------------------------------------------
-- skill / student_skill: a student can have many skills and a skill belongs
-- to many students — classic M:N, so it MUST be a junction table rather than
-- a comma-separated "skills" column on student (which would violate 1NF and
-- make "count of skills" for the ML feature impossible to query cleanly).
-- ---------------------------------------------------------------------------
CREATE SEQUENCE skill_seq START WITH 1 INCREMENT BY 1;

CREATE TABLE skill (
    skill_id    NUMBER PRIMARY KEY,
    skill_name  VARCHAR2(60) NOT NULL UNIQUE
);

CREATE OR REPLACE TRIGGER trg_skill_bi
BEFORE INSERT ON skill
FOR EACH ROW
WHEN (NEW.skill_id IS NULL)
BEGIN
    SELECT skill_seq.NEXTVAL INTO :NEW.skill_id FROM dual;
END;
/

-- student_skill is a pure junction table (composite PK, no surrogate key of
-- its own) — no sequence/trigger needed, same as in the Postgres version.
CREATE TABLE student_skill (
    student_id  NUMBER NOT NULL REFERENCES student(student_id) ON DELETE CASCADE,
    skill_id    NUMBER NOT NULL REFERENCES skill(skill_id) ON DELETE CASCADE,
    PRIMARY KEY (student_id, skill_id)
);

-- ---------------------------------------------------------------------------
-- company: recruiter organizations. One company can run many drives across
-- years, so company attributes (industry, website) live here ONCE, not
-- copied onto every drive row — avoids the update-anomaly a flat table would
-- have (e.g. fixing a typo'd website on every past drive individually).
-- ---------------------------------------------------------------------------
CREATE SEQUENCE company_seq START WITH 1 INCREMENT BY 1;

CREATE TABLE company (
    company_id       NUMBER PRIMARY KEY,
    company_name     VARCHAR2(150) NOT NULL UNIQUE,
    industry_sector  VARCHAR2(80),
    website          VARCHAR2(200),
    hr_email         VARCHAR2(120)
);

CREATE OR REPLACE TRIGGER trg_company_bi
BEFORE INSERT ON company
FOR EACH ROW
WHEN (NEW.company_id IS NULL)
BEGIN
    SELECT company_seq.NEXTVAL INTO :NEW.company_id FROM dual;
END;
/

-- ---------------------------------------------------------------------------
-- drive: a single job posting/visit by a company. Eligibility cutoffs
-- (min_cgpa, max_backlogs) live on the drive, not hardcoded in application
-- code, specifically so fn_check_eligibility() (Section 4) can read them
-- generically for ANY drive without a code change per drive.
--
-- NOTE: Oracle's DATE type carries a time component (down to the second),
-- unlike Postgres's date-only DATE — see docs/oracle-differences.md. It
-- doesn't change any behavior here since nothing in this schema compares
-- time-of-day, but it's worth knowing drive_date will store midnight
-- (00:00:00) rather than being genuinely date-only at the storage level.
-- ---------------------------------------------------------------------------
CREATE SEQUENCE drive_seq START WITH 1 INCREMENT BY 1;

CREATE TABLE drive (
    drive_id        NUMBER PRIMARY KEY,
    company_id      NUMBER NOT NULL REFERENCES company(company_id),
    coordinator_id  NUMBER REFERENCES coordinator(coordinator_id),
    job_role        VARCHAR2(100) NOT NULL,
    drive_date      DATE NOT NULL,
    package_lpa     NUMBER(6,2) NOT NULL CHECK (package_lpa > 0),
    min_cgpa        NUMBER(4,2) DEFAULT 0 NOT NULL CHECK (min_cgpa BETWEEN 0 AND 10),
    max_backlogs    NUMBER DEFAULT 0 NOT NULL CHECK (max_backlogs >= 0),
    drive_type      VARCHAR2(20) DEFAULT 'Full-Time' NOT NULL
                        CHECK (drive_type IN ('Full-Time', 'Internship')),
    status          VARCHAR2(20) DEFAULT 'Upcoming' NOT NULL
                        CHECK (status IN ('Upcoming', 'Ongoing', 'Completed', 'Cancelled')),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE OR REPLACE TRIGGER trg_drive_bi
BEFORE INSERT ON drive
FOR EACH ROW
WHEN (NEW.drive_id IS NULL)
BEGIN
    SELECT drive_seq.NEXTVAL INTO :NEW.drive_id FROM dual;
END;
/

-- ---------------------------------------------------------------------------
-- drive_eligible_dept: which departments a drive is restricted to. A
-- junction table (not a single dept_id column on drive) because a drive is
-- often open to MULTIPLE branches (e.g. "CSE, ISE, AIML"). A drive with NO
-- rows here is treated as open to ALL departments — enforced in
-- fn_check_eligibility(), not with a magic sentinel value like dept_id = -1.
-- ---------------------------------------------------------------------------
CREATE TABLE drive_eligible_dept (
    drive_id  NUMBER NOT NULL REFERENCES drive(drive_id) ON DELETE CASCADE,
    dept_id   NUMBER NOT NULL REFERENCES department(dept_id) ON DELETE CASCADE,
    PRIMARY KEY (drive_id, dept_id)
);

-- ---------------------------------------------------------------------------
-- application: THE central junction table resolving Student M:N Drive (and
-- transitively Student M:N Company, since drive -> company). A student may
-- apply to the same drive only once, enforced by the UNIQUE constraint below
-- rather than trusted to application-layer logic.
-- ---------------------------------------------------------------------------
CREATE SEQUENCE application_seq START WITH 1 INCREMENT BY 1;

CREATE TABLE application (
    application_id  NUMBER PRIMARY KEY,
    student_id      NUMBER NOT NULL REFERENCES student(student_id),
    drive_id        NUMBER NOT NULL REFERENCES drive(drive_id),
    applied_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    status          VARCHAR2(30) DEFAULT 'Applied' NOT NULL
                        CHECK (status IN ('Applied', 'Shortlisted', 'Interview_Scheduled',
                                           'Rejected', 'Selected', 'Offer_Made')),
    UNIQUE (student_id, drive_id)
);

CREATE OR REPLACE TRIGGER trg_application_bi
BEFORE INSERT ON application
FOR EACH ROW
WHEN (NEW.application_id IS NULL)
BEGIN
    SELECT application_seq.NEXTVAL INTO :NEW.application_id FROM dual;
END;
/

-- ---------------------------------------------------------------------------
-- interview_round: an application can go through several rounds (aptitude,
-- technical, HR...). One row per round rather than round1_result/
-- round2_result columns on application — a flat "N columns per round"
-- design would cap the number of rounds and violate 1NF (repeating group of
-- the same fact).
-- ---------------------------------------------------------------------------
CREATE SEQUENCE interview_round_seq START WITH 1 INCREMENT BY 1;

CREATE TABLE interview_round (
    round_id        NUMBER PRIMARY KEY,
    application_id  NUMBER NOT NULL REFERENCES application(application_id) ON DELETE CASCADE,
    round_number    NUMBER NOT NULL CHECK (round_number > 0),
    round_type      VARCHAR2(30) NOT NULL
                        CHECK (round_type IN ('Aptitude', 'Technical', 'HR',
                                               'Group_Discussion', 'Coding_Test')),
    round_date      DATE,
    result          VARCHAR2(20) DEFAULT 'Pending' NOT NULL
                        CHECK (result IN ('Pass', 'Fail', 'Pending')),
    remarks         VARCHAR2(500),
    UNIQUE (application_id, round_number)
);

CREATE OR REPLACE TRIGGER trg_interview_round_bi
BEFORE INSERT ON interview_round
FOR EACH ROW
WHEN (NEW.round_id IS NULL)
BEGIN
    SELECT interview_round_seq.NEXTVAL INTO :NEW.round_id FROM dual;
END;
/

-- ---------------------------------------------------------------------------
-- offer: at most one offer per application, enforced by UNIQUE on
-- application_id (a 1:0..1 relationship, not 1:N) — a drive/application
-- either has one offer or none, never two competing offers for the same
-- application.
-- ---------------------------------------------------------------------------
CREATE SEQUENCE offer_seq START WITH 1 INCREMENT BY 1;

CREATE TABLE offer (
    offer_id              NUMBER PRIMARY KEY,
    application_id        NUMBER NOT NULL UNIQUE REFERENCES application(application_id),
    offered_package_lpa   NUMBER(6,2) NOT NULL CHECK (offered_package_lpa > 0),
    offer_date            DATE DEFAULT CURRENT_DATE NOT NULL,
    status                VARCHAR2(20) DEFAULT 'Pending' NOT NULL
                              CHECK (status IN ('Pending', 'Accepted', 'Declined')),
    joining_date          DATE
);

CREATE OR REPLACE TRIGGER trg_offer_bi
BEFORE INSERT ON offer
FOR EACH ROW
WHEN (NEW.offer_id IS NULL)
BEGIN
    SELECT offer_seq.NEXTVAL INTO :NEW.offer_id FROM dual;
END;
/

-- ---------------------------------------------------------------------------
-- offer_history: append-only audit log. Written explicitly by the BACKEND
-- transaction that handles offer acceptance (see backend/services/
-- offer_service.py), not by a trigger — this is intentional: the spec wants
-- ONE trigger (placement_status on offer insert, Section 3) and a SEPARATE,
-- visibly-coded multi-statement transaction for acceptance, so the two DB
-- techniques stay distinguishable for the viva instead of blurring into
-- "everything is a trigger".
--
-- NOTE: `action` is used here as a plain column name. It is NOT a reserved
-- word in Oracle SQL DDL, so this is expected to be fine as-is — flagged in
-- docs/oracle-differences.md as one of the few things in this file that
-- could not be checked against a live Oracle instance, in case your
-- specific version/edition disagrees.
-- ---------------------------------------------------------------------------
CREATE SEQUENCE offer_history_seq START WITH 1 INCREMENT BY 1;

CREATE TABLE offer_history (
    history_id        NUMBER PRIMARY KEY,
    offer_id          NUMBER NOT NULL REFERENCES offer(offer_id) ON DELETE CASCADE,
    action            VARCHAR2(30) NOT NULL
                          CHECK (action IN ('Created', 'Accepted', 'Declined')),
    action_timestamp  TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    notes             VARCHAR2(500)
);

CREATE OR REPLACE TRIGGER trg_offer_history_bi
BEFORE INSERT ON offer_history
FOR EACH ROW
WHEN (NEW.history_id IS NULL)
BEGIN
    SELECT offer_history_seq.NEXTVAL INTO :NEW.history_id FROM dual;
END;
/


-- =============================================================================
-- SECTION 2: INDEXES
-- Identical syntax and identical reasoning to db/schema.sql — nothing here
-- is Postgres-specific. Each index targets a column that is filtered/joined
-- on a hot path in the app (dashboard queries, eligibility checks, admin
-- filters) — indexing everything "just in case" bloats writes for no
-- benefit, so each one below is tied to a specific query pattern.
-- =============================================================================

-- Student dashboard + eligibility checks constantly filter/join students by
-- department (e.g. department_stats_view, branch-restricted drives).
CREATE INDEX idx_student_dept ON student(dept_id);

-- fn_check_eligibility() and the "eligible drives" list filter students by
-- a cgpa threshold on every single call — this is the single most-run
-- predicate in the whole system.
CREATE INDEX idx_student_cgpa ON student(cgpa);

-- Admin dashboard's "view applicants per drive" filters by status
-- (Applied/Shortlisted/Rejected/...) constantly when triaging a drive.
CREATE INDEX idx_application_status ON application(status);

-- "View applicants per drive" also joins/filters application by drive_id;
-- (student_id, drive_id) is already covered by the UNIQUE constraint's
-- implicit index for the student-side lookup, so only drive_id needs its
-- own index here.
CREATE INDEX idx_application_drive ON application(drive_id);

-- Company-wise stats view groups/joins drives by company_id.
CREATE INDEX idx_drive_company ON drive(company_id);


-- =============================================================================
-- SECTION 3: TRIGGER — auto-update placement_status on Offer insert
-- Fires the moment an offer row is created (i.e. the company has selected
-- the student), independent of whether the student later accepts/declines
-- it. This is a deliberate reading of "record offers -> student is Placed":
-- the offer-acceptance transaction (in the backend) governs Offer.status
-- (Pending/Accepted/Declined), while this trigger governs the coarser
-- Student.placement_status (Not Placed/Placed).
--
-- WHAT CHANGED FROM db/schema.sql:
--   - Postgres needs a standalone trigger FUNCTION plus a CREATE TRIGGER
--     that references it by name. Oracle triggers are self-contained PL/SQL
--     blocks — the logic goes directly in the CREATE TRIGGER body, no
--     separate function object exists.
--   - Row values are referenced as `:NEW.col` (with the leading colon) in
--     the trigger body — Postgres uses bare `NEW.col`.
--   - No `LANGUAGE plpgsql` / `$$` delimiters; Oracle just needs `BEGIN ...
--     END;` followed by a `/` for SQL*Plus.
-- =============================================================================

CREATE OR REPLACE TRIGGER trg_offer_after_insert
AFTER INSERT ON offer
FOR EACH ROW
BEGIN
    UPDATE student
       SET placement_status = 'Placed'
     WHERE student_id = (
        SELECT student_id FROM application WHERE application_id = :NEW.application_id
     );
END;
/


-- =============================================================================
-- SECTION 4: STORED FUNCTIONS — eligibility check
-- Implemented in the DATABASE (not reimplemented as Python if/else) so the
-- eligibility rule is enforced identically no matter which client calls it
-- (Flask backend today, a future script, or a DBA running ad-hoc SQL) and so
-- it lives in exactly one place to change.
--
-- WHAT CHANGED FROM db/schema.sql — this is the biggest semantic rewrite in
-- the whole port, not just a syntax swap:
--   1. RETURN TYPE: Postgres returns BOOLEAN and the backend/seed script
--      calls it straight from SQL (`SELECT fn_check_eligibility(...)`).
--      Oracle's BOOLEAN type cannot be used in a SQL context (only inside
--      PL/SQL) before Oracle 23c, so a SQL-callable Oracle version must
--      return NUMBER instead — 1 means eligible, 0 means not eligible.
--   2. "ROW NOT FOUND" HANDLING: PL/pgSQL's `SELECT ... INTO` on a missing
--      row just leaves the variables NULL and sets a `FOUND` flag you check
--      afterward (`IF NOT FOUND THEN RETURN FALSE; END IF;` in the Postgres
--      version). Oracle's `SELECT ... INTO` on a missing row instead RAISES
--      the NO_DATA_FOUND exception immediately — there's no flag to poll.
--      This function therefore needs an EXCEPTION block, which the Postgres
--      version doesn't. Whether the student lookup or the drive lookup is
--      the one that fails, control jumps straight to WHEN NO_DATA_FOUND and
--      the function returns 0 (not eligible) — the same end result as the
--      two separate `IF NOT FOUND` checks in the Postgres version, just
--      reached through Oracle's exception-based control flow instead of a
--      checked flag.
--   3. `%TYPE` anchors each parameter/variable to its source column's type
--      (e.g. `student.cgpa%TYPE`) so the function can never drift out of
--      sync with the schema if a column's precision changes later — this is
--      idiomatic Oracle PL/SQL with no real Postgres equivalent used here.
-- =============================================================================

CREATE OR REPLACE FUNCTION fn_check_eligibility(
    p_student_id IN student.student_id%TYPE,
    p_drive_id   IN drive.drive_id%TYPE
) RETURN NUMBER
IS
    v_cgpa              student.cgpa%TYPE;
    v_backlogs          student.backlogs%TYPE;
    v_dept_id           student.dept_id%TYPE;
    v_min_cgpa          drive.min_cgpa%TYPE;
    v_max_backlogs      drive.max_backlogs%TYPE;
    v_restricted_count  NUMBER;
    v_dept_match_count  NUMBER;
BEGIN
    SELECT cgpa, backlogs, dept_id
      INTO v_cgpa, v_backlogs, v_dept_id
      FROM student
     WHERE student_id = p_student_id;

    SELECT min_cgpa, max_backlogs
      INTO v_min_cgpa, v_max_backlogs
      FROM drive
     WHERE drive_id = p_drive_id;

    IF v_cgpa < v_min_cgpa THEN
        RETURN 0;
    END IF;

    IF v_backlogs > v_max_backlogs THEN
        RETURN 0;
    END IF;

    -- No rows in drive_eligible_dept for this drive => open to all branches.
    SELECT COUNT(*) INTO v_restricted_count
      FROM drive_eligible_dept
     WHERE drive_id = p_drive_id;

    IF v_restricted_count > 0 THEN
        SELECT COUNT(*) INTO v_dept_match_count
          FROM drive_eligible_dept
         WHERE drive_id = p_drive_id AND dept_id = v_dept_id;

        IF v_dept_match_count = 0 THEN
            RETURN 0;
        END IF;
    END IF;

    RETURN 1;
EXCEPTION
    WHEN NO_DATA_FOUND THEN
        -- p_student_id or p_drive_id doesn't exist — can't be eligible.
        RETURN 0;
END fn_check_eligibility;
/

-- Convenience wrapper used by the student dashboard's "eligible drives"
-- list so the backend issues one query instead of looping
-- fn_check_eligibility() per drive in Python.
--
-- WHAT CHANGED FROM db/schema.sql: Postgres's version is
-- `RETURNS SETOF drive ... LANGUAGE sql` — an inline table function you can
-- query like a table (`SELECT * FROM fn_get_eligible_drives(1)`). Oracle has
-- no direct equivalent for "a function you FROM like a table" without first
-- declaring matching SQL object types (CREATE TYPE ... AS OBJECT / ... AS
-- TABLE OF) and writing a PIPELINED function — much more ceremony for the
-- same result. The standard, simpler Oracle idiom used here instead is a
-- function that RETURNs a SYS_REFCURSOR: the caller OPENs it implicitly by
-- calling the function, then FETCHes rows from the cursor procedurally
-- (from PL/SQL, from SQL*Plus with VARIABLE/EXEC/PRINT, or from the Python
-- backend's oracledb driver). It is genuinely a different calling
-- convention, not just different syntax — see docs/oracle-differences.md
-- for a runnable SQL*Plus example.
CREATE OR REPLACE FUNCTION fn_get_eligible_drives(
    p_student_id IN student.student_id%TYPE
) RETURN SYS_REFCURSOR
IS
    v_cursor SYS_REFCURSOR;
BEGIN
    OPEN v_cursor FOR
        SELECT d.*
          FROM drive d
         WHERE d.status IN ('Upcoming', 'Ongoing')
           AND fn_check_eligibility(p_student_id, d.drive_id) = 1;
    RETURN v_cursor;
END fn_get_eligible_drives;
/


-- =============================================================================
-- SECTION 5: VIEWS — used directly by admin analytics + student dashboard
-- None of these three views use any Postgres-specific function (no NOW(),
-- no ILIKE, no || string concatenation, nothing Postgres-only) — ROUND,
-- COUNT, AVG, MAX, MIN, NULLIF, and CASE WHEN are all ANSI-standard and
-- behave identically in Oracle, so this section is copied over UNCHANGED
-- from db/schema.sql. This is the one section with zero porting risk.
-- =============================================================================

-- placed_students_view: one row per placed student with their offer +
-- company details, joined once here so the backend never repeats this join.
CREATE VIEW placed_students_view AS
SELECT
    s.student_id,
    s.reg_no,
    s.name,
    d.dept_name,
    c.company_name,
    o.offered_package_lpa,
    o.offer_date,
    o.status AS offer_status
FROM student s
JOIN application a  ON a.student_id = s.student_id
JOIN offer o         ON o.application_id = a.application_id
JOIN drive dr         ON dr.drive_id = a.drive_id
JOIN company c        ON c.company_id = dr.company_id
JOIN department d     ON d.dept_id = s.dept_id;

-- company_wise_stats_view: offers made + package stats per recruiter, used
-- for the "top recruiters" and package-range analytics.
CREATE VIEW company_wise_stats_view AS
SELECT
    c.company_id,
    c.company_name,
    COUNT(o.offer_id)                         AS offers_count,
    ROUND(AVG(o.offered_package_lpa), 2)      AS avg_package_lpa,
    MAX(o.offered_package_lpa)                AS max_package_lpa,
    MIN(o.offered_package_lpa)                AS min_package_lpa
FROM company c
JOIN drive dr        ON dr.company_id = c.company_id
JOIN application a   ON a.drive_id = dr.drive_id
JOIN offer o          ON o.application_id = a.application_id
GROUP BY c.company_id, c.company_name;

-- department_stats_view: placement % per department. LEFT JOIN from
-- department (not student) so a department with zero students still shows
-- up with 0/0 instead of vanishing from the report.
CREATE VIEW department_stats_view AS
SELECT
    dep.dept_id,
    dep.dept_name,
    COUNT(DISTINCT s.student_id) AS total_students,
    COUNT(DISTINCT CASE WHEN s.placement_status = 'Placed' THEN s.student_id END) AS placed_students,
    ROUND(
        100.0 * COUNT(DISTINCT CASE WHEN s.placement_status = 'Placed' THEN s.student_id END)
        / NULLIF(COUNT(DISTINCT s.student_id), 0),
    2) AS placement_percentage
FROM department dep
LEFT JOIN student s ON s.dept_id = dep.dept_id
GROUP BY dep.dept_id, dep.dept_name;
