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
    -- An offer that is already Declined when inserted (only possible from
    -- bulk loads like db/seed.py — the app always inserts Pending) must not
    -- mark the student Placed.
    IF NEW.status = 'Declined' THEN
        RETURN NEW;
    END IF;

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


-- =============================================================================
-- SECTION 6: BUSINESS-RULE TRIGGERS (BEFORE triggers that REJECT bad writes)
-- Section 3's trigger REACTS to a write (sets placement_status after an
-- offer is inserted). These triggers instead GUARD a write: they fire
-- BEFORE the row is stored and raise an exception to abort it. That makes
-- the database itself the last line of defence — the rules hold even for a
-- DBA running raw SQL, a seed script, or a buggy future endpoint, not just
-- for requests that go through the Flask app's checks.
--
-- Each rule raises its own custom SQLSTATE so the backend can map it to the
-- right HTTP status without parsing error text (backend/utils/db_errors.py):
--   PL001  student not eligible for the drive      -> 403
--   PL002  drive is closed to applications          -> 409
--   PL003  student has already accepted an offer    -> 409
--   PL004  drive does not exist (sp_close_drive)    -> 404
--   PL005  drive is already closed (sp_close_drive) -> 409
--   PL006  offer on an application not Selected     -> 409
--   PL007  illegal application status transition    -> 409
-- =============================================================================

-- Rule: you can only apply to an open drive you are eligible for.
-- Eligibility reuses fn_check_eligibility() (Section 4) rather than
-- restating the CGPA/backlog/department rule a second time.
CREATE OR REPLACE FUNCTION trg_fn_application_guard()
RETURNS TRIGGER AS $$
DECLARE
    v_drive_status drive.status%TYPE;
BEGIN
    SELECT status INTO v_drive_status FROM drive WHERE drive_id = NEW.drive_id;

    -- Nonexistent drive: let the drive_id foreign key reject it with its own
    -- error rather than misreporting it as "not eligible".
    IF NOT FOUND THEN
        RETURN NEW;
    END IF;

    IF v_drive_status IN ('Completed', 'Cancelled') THEN
        RAISE EXCEPTION 'Drive % is % and no longer accepts applications',
            NEW.drive_id, v_drive_status
            USING ERRCODE = 'PL002';
    END IF;

    IF NOT fn_check_eligibility(NEW.student_id, NEW.drive_id) THEN
        RAISE EXCEPTION 'Student % is not eligible for drive %',
            NEW.student_id, NEW.drive_id
            USING ERRCODE = 'PL001';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_application_before_insert
BEFORE INSERT ON application
FOR EACH ROW
EXECUTE FUNCTION trg_fn_application_guard();

-- Rule: a student can hold at most ONE accepted offer.
-- This can't be a UNIQUE constraint because offer has no student_id column
-- (the student is reached through application), so it's enforced here.
--
-- The SELECT ... FOR UPDATE on the student row is what makes this rule hold
-- under concurrency: without it, two transactions accepting two DIFFERENT
-- offers for the same student at the same instant could each check, each
-- see "no accepted offer yet", and both commit. Locking the student row
-- forces the second transaction to wait until the first commits, and then
-- its check sees the first acceptance. (db/demos/concurrency_demo.py runs
-- exactly this race.)
CREATE OR REPLACE FUNCTION trg_fn_offer_single_acceptance()
RETURNS TRIGGER AS $$
DECLARE
    v_student_id student.student_id%TYPE;
BEGIN
    IF NEW.status <> 'Accepted' THEN
        RETURN NEW;
    END IF;

    SELECT student_id INTO v_student_id
      FROM application WHERE application_id = NEW.application_id;

    PERFORM 1 FROM student WHERE student_id = v_student_id FOR UPDATE;

    IF EXISTS (
        SELECT 1
          FROM offer o
          JOIN application a ON a.application_id = o.application_id
         WHERE a.student_id = v_student_id
           AND o.status = 'Accepted'
           AND o.offer_id IS DISTINCT FROM NEW.offer_id
    ) THEN
        RAISE EXCEPTION 'Student % has already accepted another offer', v_student_id
            USING ERRCODE = 'PL003';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_offer_before_accept
BEFORE INSERT OR UPDATE OF status ON offer
FOR EACH ROW
EXECUTE FUNCTION trg_fn_offer_single_acceptance();

-- Rule: an offer can only be recorded for an application that is Selected
-- (the student cleared every round). Without this, an admin could record an
-- offer on a Rejected application — and the backend would then flip it to
-- Offer_Made, rewriting a rejection into a hire.
CREATE OR REPLACE FUNCTION trg_fn_offer_requires_selected()
RETURNS TRIGGER AS $$
DECLARE
    v_app_status application.status%TYPE;
BEGIN
    SELECT status INTO v_app_status
      FROM application WHERE application_id = NEW.application_id;

    -- Nonexistent application: let the application_id foreign key report it.
    IF NOT FOUND THEN
        RETURN NEW;
    END IF;

    IF v_app_status <> 'Selected' THEN
        RAISE EXCEPTION 'Application % is %; an offer can only be recorded for a Selected application',
            NEW.application_id, v_app_status
            USING ERRCODE = 'PL006';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_offer_requires_selected
BEFORE INSERT ON offer
FOR EACH ROW
EXECUTE FUNCTION trg_fn_offer_requires_selected();

-- Rule: application status can only move forward through the hiring
-- pipeline. Allowed transitions (anything else raises PL007):
--
--   FROM                 ALLOWED TO
--   Applied              Shortlisted, Interview_Scheduled, Rejected
--   Shortlisted          Interview_Scheduled, Selected, Rejected
--   Interview_Scheduled  Selected, Rejected
--   Selected             Offer_Made, Rejected
--   Offer_Made           (final — set only when an offer row exists)
--   Rejected             (final — a rejection can't be undone)
--
-- Skipping forward (Applied -> Interview_Scheduled) is allowed because some
-- drives have no separate shortlisting step; going backwards is never
-- allowed. The WHEN clause means an UPDATE that doesn't change the status
-- never reaches the check.
CREATE OR REPLACE FUNCTION trg_fn_application_status_transition()
RETURNS TRIGGER AS $$
DECLARE
    v_allowed BOOLEAN;
BEGIN
    v_allowed := CASE OLD.status
        WHEN 'Applied'             THEN NEW.status IN ('Shortlisted', 'Interview_Scheduled', 'Rejected')
        WHEN 'Shortlisted'         THEN NEW.status IN ('Interview_Scheduled', 'Selected', 'Rejected')
        WHEN 'Interview_Scheduled' THEN NEW.status IN ('Selected', 'Rejected')
        WHEN 'Selected'            THEN NEW.status IN ('Offer_Made', 'Rejected')
        ELSE FALSE   -- Offer_Made and Rejected are final
    END;

    IF NOT v_allowed THEN
        RAISE EXCEPTION 'Application % cannot move from % to %',
            NEW.application_id, OLD.status, NEW.status
            USING ERRCODE = 'PL007';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_application_status_transition
BEFORE UPDATE OF status ON application
FOR EACH ROW
WHEN (OLD.status IS DISTINCT FROM NEW.status)
EXECUTE FUNCTION trg_fn_application_status_transition();


-- =============================================================================
-- SECTION 7: AUDIT TRIGGER — application status history (OLD vs NEW)
-- Every change to application.status is recorded with its before and after
-- value. Unlike offer_history (written explicitly by the backend's
-- transaction), this log is written by the database itself, so no status
-- change can skip it — including bulk changes made by sp_close_drive().
--
-- The WHEN clause skips UPDATEs that touch the row but don't actually
-- change the status, so the log never fills with no-op entries.
-- =============================================================================

CREATE TABLE application_status_history (
    history_id      INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    application_id  INTEGER NOT NULL REFERENCES application(application_id) ON DELETE CASCADE,
    old_status      VARCHAR(30) NOT NULL,
    new_status      VARCHAR(30) NOT NULL,
    changed_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_status_history_application ON application_status_history(application_id);

CREATE OR REPLACE FUNCTION trg_fn_application_status_audit()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO application_status_history (application_id, old_status, new_status)
    VALUES (NEW.application_id, OLD.status, NEW.status);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_application_status_audit
AFTER UPDATE OF status ON application
FOR EACH ROW
WHEN (OLD.status IS DISTINCT FROM NEW.status)
EXECUTE FUNCTION trg_fn_application_status_audit();


-- =============================================================================
-- SECTION 8: STORED PROCEDURE — close a drive
-- A PROCEDURE, not a FUNCTION, on purpose. The difference to explain:
--   - A FUNCTION returns a value and is used inside a query
--     (SELECT fn_check_eligibility(...)). It's for computing something.
--   - A PROCEDURE is invoked on its own with CALL and performs an action.
--     It can't appear inside a SELECT, and (unlike a function) it is allowed
--     to COMMIT/ROLLBACK internally when called outside a transaction block.
-- Closing a drive is an action with several writes, so it's a procedure.
--
-- What it does, atomically: marks the drive Completed and rejects every
-- applicant still waiting on it (Applied / Shortlisted / Interview_Scheduled).
-- Selected and Offer_Made applications are left alone. Each rejection is
-- logged automatically by the Section 7 audit trigger.
--
-- p_rejected_count is INOUT because a procedure has no RETURN value — this
-- is how it hands the number of rejected applications back to the caller:
--   CALL sp_close_drive(5, NULL);   -- returns one row: p_rejected_count
-- =============================================================================

CREATE OR REPLACE PROCEDURE sp_close_drive(
    p_drive_id        INTEGER,
    INOUT p_rejected_count INTEGER DEFAULT NULL
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_status drive.status%TYPE;
BEGIN
    -- Lock the drive row so two admins closing the same drive at once can't
    -- both pass the "already closed?" check below.
    SELECT status INTO v_status FROM drive WHERE drive_id = p_drive_id FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Drive % does not exist', p_drive_id USING ERRCODE = 'PL004';
    END IF;

    IF v_status IN ('Completed', 'Cancelled') THEN
        RAISE EXCEPTION 'Drive % is already %', p_drive_id, v_status USING ERRCODE = 'PL005';
    END IF;

    UPDATE application
       SET status = 'Rejected'
     WHERE drive_id = p_drive_id
       AND status IN ('Applied', 'Shortlisted', 'Interview_Scheduled');

    GET DIAGNOSTICS p_rejected_count = ROW_COUNT;

    UPDATE drive SET status = 'Completed' WHERE drive_id = p_drive_id;
END;
$$;


-- =============================================================================
-- SECTION 9: WINDOW-FUNCTION VIEWS
-- A window function computes a value across a set of related rows WITHOUT
-- collapsing them into one row the way GROUP BY does. Each view below keeps
-- every row and adds a ranking / running total next to it.
-- =============================================================================

-- Every non-declined offer, ranked within its department by package.
-- RANK() gives ties the same rank and then skips (1, 1, 3); "top N per
-- department" is just WHERE rank_in_dept <= N on top of this view.
CREATE VIEW dept_offer_ranking_view AS
SELECT
    d.dept_id,
    d.dept_name,
    s.student_id,
    s.reg_no,
    s.name,
    c.company_name,
    o.offered_package_lpa,
    RANK() OVER (
        PARTITION BY d.dept_id
        ORDER BY o.offered_package_lpa DESC
    ) AS rank_in_dept
FROM offer o
JOIN application a ON a.application_id = o.application_id
JOIN student s      ON s.student_id = a.student_id
JOIN department d   ON d.dept_id = s.dept_id
JOIN drive dr       ON dr.drive_id = a.drive_id
JOIN company c      ON c.company_id = dr.company_id
WHERE o.status <> 'Declined';

-- Offers per month, with a running (cumulative) total and the change from
-- the previous month. The window functions run AFTER the GROUP BY, over
-- the monthly rows: SUM(...) OVER (ORDER BY month) is a running total,
-- LAG(...) reads the previous month's value.
CREATE VIEW placement_timeline_view AS
SELECT
    date_trunc('month', o.offer_date)::DATE AS month,
    COUNT(*) AS offers_in_month,
    SUM(COUNT(*)) OVER (ORDER BY date_trunc('month', o.offer_date)) AS cumulative_offers,
    COUNT(*) - LAG(COUNT(*)) OVER (ORDER BY date_trunc('month', o.offer_date)) AS change_from_prev_month
FROM offer o
GROUP BY date_trunc('month', o.offer_date);

-- Where each student's CGPA stands within their own department.
-- PERCENT_RANK() is 0 for the lowest CGPA and 1 for the highest;
-- DENSE_RANK() is the plain 1st/2nd/3rd position with no gaps after ties.
CREATE VIEW student_cgpa_standing_view AS
SELECT
    s.student_id,
    s.dept_id,
    s.cgpa,
    DENSE_RANK() OVER (PARTITION BY s.dept_id ORDER BY s.cgpa DESC) AS cgpa_rank_in_dept,
    COUNT(*)     OVER (PARTITION BY s.dept_id) AS dept_size,
    ROUND((PERCENT_RANK() OVER (PARTITION BY s.dept_id ORDER BY s.cgpa) * 100)::NUMERIC, 1)
        AS cgpa_percentile_in_dept
FROM student s;


-- =============================================================================
-- SECTION 10: MATERIALIZED VIEW — company x department placement matrix
-- A normal view (Section 5) is just a saved query: it re-runs its joins on
-- every read, so it's always current. A MATERIALIZED view runs the query
-- once and STORES the result like a table. Reads are fast, but the data is
-- only as fresh as the last REFRESH — that staleness is the trade-off.
--
-- This one powers the analytics page's company-by-department matrix, which
-- joins five tables and doesn't need to be up to the second. refreshed_at
-- is evaluated at refresh time, so the page can show how old the data is.
--
-- The UNIQUE index is required for REFRESH MATERIALIZED VIEW CONCURRENTLY,
-- which rebuilds the data without blocking readers while it runs.
-- =============================================================================

CREATE MATERIALIZED VIEW mv_company_dept_placements AS
SELECT
    c.company_id,
    c.company_name,
    d.dept_id,
    d.dept_name,
    COUNT(o.offer_id)                    AS offers_count,
    ROUND(AVG(o.offered_package_lpa), 2) AS avg_package_lpa,
    CURRENT_TIMESTAMP                    AS refreshed_at
FROM offer o
JOIN application a ON a.application_id = o.application_id
JOIN student s      ON s.student_id = a.student_id
JOIN department d   ON d.dept_id = s.dept_id
JOIN drive dr       ON dr.drive_id = a.drive_id
JOIN company c      ON c.company_id = dr.company_id
WHERE o.status <> 'Declined'
GROUP BY c.company_id, c.company_name, d.dept_id, d.dept_name;

CREATE UNIQUE INDEX idx_mv_company_dept ON mv_company_dept_placements(company_id, dept_id);
