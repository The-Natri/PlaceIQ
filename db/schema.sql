-- =============================================================================
-- College Placement Management System — Database Schema (DDL)
-- Target: PostgreSQL 13+
--
-- PORTABILITY NOTE (read this first if adapting to Oracle SQL*Plus):
--   1. `GENERATED ALWAYS AS IDENTITY` for surrogate keys works UNCHANGED in
--      Oracle 12c+. This was chosen specifically for that reason (instead of
--      Postgres-only SERIAL), so Section 1 (tables) below is close to
--      copy-paste portable to Oracle.
--   2. VARCHAR(n) / NUMERIC(p,s) / DATE / TIMESTAMP are ANSI types supported
--      by both engines. TEXT and BOOLEAN (Postgres-only for table columns)
--      are deliberately NOT used anywhere in this schema.
--   3. Sections 3-5 (trigger function, eligibility function, views) use
--      PL/pgSQL (`LANGUAGE plpgsql`, `$$ ... $$` bodies, `NEW.col`), which is
--      Postgres-specific. Oracle's equivalent is PL/SQL:
--        - `CREATE OR REPLACE FUNCTION ... RETURN <type> IS ... BEGIN ... END;`
--          (no `LANGUAGE plpgsql`, no `$$` delimiters)
--        - Trigger row reference is `:NEW.col` / `:OLD.col`, not `NEW.col`
--        - `RETURN TRUE/FALSE` from SQL context is invalid pre-Oracle 23c —
--          a SQL-callable boolean function must return NUMBER(1) or
--          VARCHAR2('Y'/'N') instead, since Oracle SQL (unlike PL/SQL) had no
--          native BOOLEAN type before 23c.
--        - `RETURNS SETOF drive ... LANGUAGE sql` (fn_get_eligible_drives) is
--          a Postgres inline table function; Oracle needs a pipelined
--          function (`RETURN drive_tab PIPELINED`) or a REF CURSOR out param.
--      These sections are marked inline with "-- ORACLE:" comments explaining
--      the equivalent construct.
-- =============================================================================


-- =============================================================================
-- SECTION 1: TABLES
-- Order follows FK dependency (parents before children) so this script can
-- be run top-to-bottom with no forward references.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- department: lookup/reference entity. Kept separate (not a VARCHAR column on
-- student) so department name changes happen in one place and student.dept_id
-- is a stable FK — this is the textbook 2NF/3NF justification for splitting
-- out a reference table instead of repeating dept_name on every student row.
-- ---------------------------------------------------------------------------
CREATE TABLE department (
    dept_id     INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dept_name   VARCHAR(100) NOT NULL UNIQUE,
    dept_code   VARCHAR(10)  NOT NULL UNIQUE   -- e.g. 'CSE', 'ISE', 'ECE'
);

-- ---------------------------------------------------------------------------
-- coordinator: TPO / placement-cell admin accounts. Separate table (not a
-- role flag on student) because coordinators are a structurally different
-- principal — different auth claims, no cgpa/dept, and we never want a
-- student row to accidentally gain admin capability via a bad UPDATE.
-- ---------------------------------------------------------------------------
CREATE TABLE coordinator (
    coordinator_id  INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    email           VARCHAR(120) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,      -- bcrypt hash, never plaintext
    role            VARCHAR(20)  NOT NULL DEFAULT 'Coordinator'
                        CHECK (role IN ('TPO', 'Coordinator')),
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------------
-- student: core entity. placement_status is a DELIBERATE DENORMALIZATION —
-- it is derivable by checking whether an Accepted-or-Created offer exists
-- through this student's applications, but the spec requires a trigger to
-- maintain it directly (see Section 3), and it lets department_stats_view
-- and the dashboard avoid a multi-table join for a very common read. This
-- tradeoff is documented in detail in docs/normalization.md.
-- ---------------------------------------------------------------------------
CREATE TABLE student (
    student_id          INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    reg_no              VARCHAR(20)  NOT NULL UNIQUE,
    name                VARCHAR(100) NOT NULL,
    email               VARCHAR(120) NOT NULL UNIQUE,
    password_hash       VARCHAR(255) NOT NULL,
    dept_id             INTEGER NOT NULL REFERENCES department(dept_id),
    cgpa                NUMERIC(4,2) NOT NULL CHECK (cgpa BETWEEN 0 AND 10),
    backlogs            INTEGER NOT NULL DEFAULT 0 CHECK (backlogs >= 0),
    batch_year          INTEGER NOT NULL CHECK (batch_year BETWEEN 2000 AND 2100),
    phone               VARCHAR(15),
    placement_status    VARCHAR(20) NOT NULL DEFAULT 'Not Placed'
                            CHECK (placement_status IN ('Not Placed', 'Placed')),
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------------
-- skill / student_skill: a student can have many skills and a skill belongs
-- to many students — classic M:N, so it MUST be a junction table rather than
-- a comma-separated "skills" column on student (which would violate 1NF and
-- make "count of skills" for the ML feature impossible to query cleanly).
-- ---------------------------------------------------------------------------
CREATE TABLE skill (
    skill_id    INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    skill_name  VARCHAR(60) NOT NULL UNIQUE
);

CREATE TABLE student_skill (
    student_id  INTEGER NOT NULL REFERENCES student(student_id) ON DELETE CASCADE,
    skill_id    INTEGER NOT NULL REFERENCES skill(skill_id) ON DELETE CASCADE,
    PRIMARY KEY (student_id, skill_id)
);

-- ---------------------------------------------------------------------------
-- company: recruiter organizations. One company can run many drives across
-- years, so company attributes (industry, website) live here ONCE, not
-- copied onto every drive row — avoids the update-anomaly a flat table would
-- have (e.g. fixing a typo'd website on every past drive individually).
-- ---------------------------------------------------------------------------
CREATE TABLE company (
    company_id       INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_name     VARCHAR(150) NOT NULL UNIQUE,
    industry_sector  VARCHAR(80),
    website          VARCHAR(200),
    hr_email         VARCHAR(120)
);

-- ---------------------------------------------------------------------------
-- drive: a single job posting/visit by a company. Eligibility cutoffs
-- (min_cgpa, max_backlogs) live on the drive, not hardcoded in application
-- code, specifically so fn_check_eligibility() (Section 4) can read them
-- generically for ANY drive without a code change per drive.
-- ---------------------------------------------------------------------------
CREATE TABLE drive (
    drive_id        INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id      INTEGER NOT NULL REFERENCES company(company_id),
    coordinator_id  INTEGER REFERENCES coordinator(coordinator_id),
    job_role        VARCHAR(100) NOT NULL,
    drive_date      DATE NOT NULL,
    package_lpa     NUMERIC(6,2) NOT NULL CHECK (package_lpa > 0),
    min_cgpa        NUMERIC(4,2) NOT NULL DEFAULT 0 CHECK (min_cgpa BETWEEN 0 AND 10),
    max_backlogs    INTEGER NOT NULL DEFAULT 0 CHECK (max_backlogs >= 0),
    drive_type      VARCHAR(20) NOT NULL DEFAULT 'Full-Time'
                        CHECK (drive_type IN ('Full-Time', 'Internship')),
    status          VARCHAR(20) NOT NULL DEFAULT 'Upcoming'
                        CHECK (status IN ('Upcoming', 'Ongoing', 'Completed', 'Cancelled')),
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------------
-- drive_eligible_dept: which departments a drive is restricted to. A junction
-- table (not a single dept_id column on drive) because a drive is often open
-- to MULTIPLE branches (e.g. "CSE, ISE, AIML"). A drive with NO rows here is
-- treated as open to ALL departments — enforced in fn_check_eligibility(),
-- not with a magic sentinel value like dept_id = -1.
-- ---------------------------------------------------------------------------
CREATE TABLE drive_eligible_dept (
    drive_id  INTEGER NOT NULL REFERENCES drive(drive_id) ON DELETE CASCADE,
    dept_id   INTEGER NOT NULL REFERENCES department(dept_id) ON DELETE CASCADE,
    PRIMARY KEY (drive_id, dept_id)
);

-- ---------------------------------------------------------------------------
-- application: THE central junction table resolving Student M:N Drive (and
-- transitively Student M:N Company, since drive -> company). A student may
-- apply to the same drive only once, enforced by the UNIQUE constraint below
-- rather than trusted to application-layer logic.
-- ---------------------------------------------------------------------------
CREATE TABLE application (
    application_id  INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    student_id      INTEGER NOT NULL REFERENCES student(student_id),
    drive_id        INTEGER NOT NULL REFERENCES drive(drive_id),
    applied_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status          VARCHAR(30) NOT NULL DEFAULT 'Applied'
                        CHECK (status IN ('Applied', 'Shortlisted', 'Interview_Scheduled',
                                           'Rejected', 'Selected', 'Offer_Made')),
    UNIQUE (student_id, drive_id)
);

-- ---------------------------------------------------------------------------
-- interview_round: an application can go through several rounds (aptitude,
-- technical, HR...). One row per round rather than round1_result/round2_result
-- columns on application — a flat "N columns per round" design would cap the
-- number of rounds and violate 1NF (repeating group of the same fact).
-- ---------------------------------------------------------------------------
CREATE TABLE interview_round (
    round_id        INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    application_id  INTEGER NOT NULL REFERENCES application(application_id) ON DELETE CASCADE,
    round_number    INTEGER NOT NULL CHECK (round_number > 0),
    round_type      VARCHAR(30) NOT NULL
                        CHECK (round_type IN ('Aptitude', 'Technical', 'HR',
                                               'Group_Discussion', 'Coding_Test')),
    round_date      DATE,
    result          VARCHAR(20) NOT NULL DEFAULT 'Pending'
                        CHECK (result IN ('Pass', 'Fail', 'Pending')),
    remarks         VARCHAR(500),
    UNIQUE (application_id, round_number)
);

-- ---------------------------------------------------------------------------
-- offer: at most one offer per application, enforced by UNIQUE on
-- application_id (a 1:0..1 relationship, not 1:N) — a drive/application
-- either has one offer or none, never two competing offers for the same
-- application.
-- ---------------------------------------------------------------------------
CREATE TABLE offer (
    offer_id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    application_id        INTEGER NOT NULL UNIQUE REFERENCES application(application_id),
    offered_package_lpa   NUMERIC(6,2) NOT NULL CHECK (offered_package_lpa > 0),
    offer_date            DATE NOT NULL DEFAULT CURRENT_DATE,
    status                VARCHAR(20) NOT NULL DEFAULT 'Pending'
                              CHECK (status IN ('Pending', 'Accepted', 'Declined')),
    joining_date          DATE
);

-- ---------------------------------------------------------------------------
-- offer_history: append-only audit log. Written explicitly by the BACKEND
-- transaction that handles offer acceptance (see backend/services/offer_service.py),
-- not by a trigger — this is intentional: the spec wants ONE trigger
-- (placement_status on offer insert, Section 3) and a SEPARATE, visibly-coded
-- multi-statement transaction for acceptance, so the two DB techniques stay
-- distinguishable for the viva instead of blurring into "everything is a trigger".
-- ---------------------------------------------------------------------------
CREATE TABLE offer_history (
    history_id        INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    offer_id          INTEGER NOT NULL REFERENCES offer(offer_id) ON DELETE CASCADE,
    action            VARCHAR(30) NOT NULL
                          CHECK (action IN ('Created', 'Accepted', 'Declined')),
    action_timestamp  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes             VARCHAR(500)
);


-- =============================================================================
-- SECTION 2: INDEXES
-- Each index targets a column that is filtered/joined on a hot path in the
-- app (dashboard queries, eligibility checks, admin filters) — indexing
-- everything "just in case" bloats writes for no benefit, so each one below
-- is tied to a specific query pattern.
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

-- Company-wise stats view groups/join drives by company_id.
CREATE INDEX idx_drive_company ON drive(company_id);


-- =============================================================================
-- SECTION 3: TRIGGER — auto-update placement_status on Offer insert
-- Fires the moment an offer row is created (i.e. the company has selected
-- the student), independent of whether the student later accepts/declines it.
-- This is a deliberate reading of "record offers -> student is Placed": the
-- offer_acceptance transaction (in the backend) governs Offer.status
-- (Pending/Accepted/Declined), while this trigger governs the coarser
-- Student.placement_status (Not Placed/Placed).
--
-- ORACLE: same logic, but written as
--   CREATE OR REPLACE TRIGGER trg_offer_after_insert
--   AFTER INSERT ON offer FOR EACH ROW
--   BEGIN
--     UPDATE student SET placement_status = 'Placed'
--     WHERE student_id = (SELECT student_id FROM application WHERE application_id = :NEW.application_id);
--   END;
-- (no separate trigger FUNCTION object — Oracle triggers are self-contained
-- PL/SQL blocks, they don't reference a standalone function like Postgres does)
-- =============================================================================

CREATE OR REPLACE FUNCTION trg_fn_offer_insert_update_placement()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE student
    SET placement_status = 'Placed'
    WHERE student_id = (
        SELECT student_id FROM application WHERE application_id = NEW.application_id
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_offer_after_insert
AFTER INSERT ON offer
FOR EACH ROW
EXECUTE FUNCTION trg_fn_offer_insert_update_placement();


-- =============================================================================
-- SECTION 4: STORED FUNCTIONS — eligibility check
-- Implemented in the DATABASE (not reimplemented as Python if/else) so the
-- eligibility rule is enforced identically no matter which client calls it
-- (Flask backend today, a future script, or a DBA running ad-hoc SQL) and so
-- it lives in exactly one place to change.
--
-- ORACLE: `RETURN BOOLEAN` is a PL/SQL-only type — it cannot be called from
-- plain SQL (e.g. `SELECT fn_check_eligibility(...)`) before Oracle 23c.
-- A SQL-callable Oracle port would change the return type to
-- `RETURN NUMBER` (1/0) or `RETURN VARCHAR2` ('Y'/'N') instead, and drop the
-- `LANGUAGE plpgsql` / `$$` wrapper for plain `IS ... BEGIN ... END;`.
-- =============================================================================

CREATE OR REPLACE FUNCTION fn_check_eligibility(p_student_id INTEGER, p_drive_id INTEGER)
RETURNS BOOLEAN AS $$
DECLARE
    v_cgpa              NUMERIC(4,2);
    v_backlogs          INTEGER;
    v_dept_id           INTEGER;
    v_min_cgpa          NUMERIC(4,2);
    v_max_backlogs      INTEGER;
    v_restricted_count  INTEGER;
    v_dept_match_count  INTEGER;
BEGIN
    SELECT cgpa, backlogs, dept_id
      INTO v_cgpa, v_backlogs, v_dept_id
      FROM student
     WHERE student_id = p_student_id;

    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    SELECT min_cgpa, max_backlogs
      INTO v_min_cgpa, v_max_backlogs
      FROM drive
     WHERE drive_id = p_drive_id;

    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    IF v_cgpa < v_min_cgpa THEN
        RETURN FALSE;
    END IF;

    IF v_backlogs > v_max_backlogs THEN
        RETURN FALSE;
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
            RETURN FALSE;
        END IF;
    END IF;

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql STABLE;

-- Convenience wrapper used by the student dashboard's "eligible drives" list
-- so the backend issues one query instead of looping fn_check_eligibility()
-- per drive in Python.
--
-- ORACLE: `RETURNS SETOF drive ... LANGUAGE sql` (an inline SQL table
-- function) has no direct Oracle equivalent; port as a pipelined function
-- (`RETURN drive_tab PIPELINED`) or a function returning a REF CURSOR.
CREATE OR REPLACE FUNCTION fn_get_eligible_drives(p_student_id INTEGER)
RETURNS SETOF drive AS $$
    SELECT d.*
      FROM drive d
     WHERE d.status IN ('Upcoming', 'Ongoing')
       AND fn_check_eligibility(p_student_id, d.drive_id) = TRUE;
$$ LANGUAGE sql STABLE;


-- =============================================================================
-- SECTION 5: VIEWS — used directly by admin analytics + student dashboard
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
