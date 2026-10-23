-- =============================================================================
-- Small synthetic dataset for the Oracle port (run as PLACEIQ, after
-- schema_oracle.sql):   @db/seed_oracle_demo.sql
--
-- Deliberately tiny (9 students, 4 drives) so every row in the SQL*Plus demo
-- can be read and explained live. Each student and drive is there to set up
-- one demo case — see the comments. All names are fictional and all data is
-- synthetic; password_hash is a placeholder, not a real hash.
--
-- Foreign keys are looked up by natural keys (reg_no, company_name, ...)
-- instead of hard-coded ids, so the script doesn't depend on sequence values.
-- Application statuses are stepped one legal move at a time, because
-- trg_app_status_transition (schema Section 6) refuses jumps.
-- =============================================================================
SET FEEDBACK OFF
SET DEFINE OFF

INSERT INTO department (dept_name, dept_code) VALUES ('Computer Science Engineering', 'CSE');
INSERT INTO department (dept_name, dept_code) VALUES ('Information Science Engineering', 'ISE');
INSERT INTO department (dept_name, dept_code) VALUES ('Mechanical Engineering', 'MECH');

INSERT INTO coordinator (name, email, password_hash, role)
VALUES ('Placement Officer', 'tpo@campus.edu', 'placeholder-not-a-real-hash', 'TPO');

INSERT INTO skill (skill_name) VALUES ('Python');
INSERT INTO skill (skill_name) VALUES ('Java');
INSERT INTO skill (skill_name) VALUES ('SQL');
INSERT INTO skill (skill_name) VALUES ('AutoCAD');

INSERT INTO company (company_name, industry_sector) VALUES ('Nimbus Cloud Systems', 'Software / Cloud');
INSERT INTO company (company_name, industry_sector) VALUES ('Coral Bay Solutions', 'Software / IT Services');
INSERT INTO company (company_name, industry_sector) VALUES ('Granite Motors', 'Core / Automotive');

-- Students. The ones the demo relies on:
--   Aisha  (CSE, 9.10) - accepted an offer; used for the second-offer rule
--   Kavya  (ISE, 8.40) - holds a Pending offer; used for the transaction demo
--   Arjun  (ISE, 6.10, 3 backlogs) - fails the CGPA/backlog cutoffs
--   Meera  (MECH, 7.80) - good CGPA but wrong branch for the CSE/ISE-only drive;
--                         used for the placement-trigger demo
--   Sneha  (CSE, 8.70) - rejected application; used for the offer-on-rejected rule
INSERT INTO student (reg_no, name, email, password_hash, dept_id, cgpa, backlogs, batch_year)
SELECT 'CSE2024001', 'Aisha Rao', 'aisha@campus.edu', 'placeholder-not-a-real-hash', dept_id, 9.10, 0, 2024
  FROM department WHERE dept_code = 'CSE';
INSERT INTO student (reg_no, name, email, password_hash, dept_id, cgpa, backlogs, batch_year)
SELECT 'CSE2024002', 'Rohan Mehta', 'rohan@campus.edu', 'placeholder-not-a-real-hash', dept_id, 7.20, 1, 2024
  FROM department WHERE dept_code = 'CSE';
INSERT INTO student (reg_no, name, email, password_hash, dept_id, cgpa, backlogs, batch_year)
SELECT 'ISE2024003', 'Kavya Nair', 'kavya@campus.edu', 'placeholder-not-a-real-hash', dept_id, 8.40, 0, 2024
  FROM department WHERE dept_code = 'ISE';
INSERT INTO student (reg_no, name, email, password_hash, dept_id, cgpa, backlogs, batch_year)
SELECT 'ISE2024004', 'Arjun Iyer', 'arjun@campus.edu', 'placeholder-not-a-real-hash', dept_id, 6.10, 3, 2024
  FROM department WHERE dept_code = 'ISE';
INSERT INTO student (reg_no, name, email, password_hash, dept_id, cgpa, backlogs, batch_year)
SELECT 'MEC2024005', 'Meera Shetty', 'meera@campus.edu', 'placeholder-not-a-real-hash', dept_id, 7.80, 0, 2024
  FROM department WHERE dept_code = 'MECH';
INSERT INTO student (reg_no, name, email, password_hash, dept_id, cgpa, backlogs, batch_year)
SELECT 'MEC2024006', 'Vikram Das', 'vikram@campus.edu', 'placeholder-not-a-real-hash', dept_id, 6.50, 2, 2024
  FROM department WHERE dept_code = 'MECH';
INSERT INTO student (reg_no, name, email, password_hash, dept_id, cgpa, backlogs, batch_year)
SELECT 'CSE2024007', 'Sneha Pillai', 'sneha@campus.edu', 'placeholder-not-a-real-hash', dept_id, 8.70, 0, 2024
  FROM department WHERE dept_code = 'CSE';
INSERT INTO student (reg_no, name, email, password_hash, dept_id, cgpa, backlogs, batch_year)
SELECT 'ISE2024008', 'Dev Kulkarni', 'dev@campus.edu', 'placeholder-not-a-real-hash', dept_id, 7.00, 0, 2024
  FROM department WHERE dept_code = 'ISE';
INSERT INTO student (reg_no, name, email, password_hash, dept_id, cgpa, backlogs, batch_year)
SELECT 'MEC2024009', 'Nikhil Bhat', 'nikhil@campus.edu', 'placeholder-not-a-real-hash', dept_id, 7.40, 1, 2024
  FROM department WHERE dept_code = 'MECH';

INSERT INTO student_skill (student_id, skill_id)
SELECT s.student_id, k.skill_id FROM student s, skill k
 WHERE (s.reg_no IN ('CSE2024001', 'CSE2024007', 'ISE2024003') AND k.skill_name IN ('Python', 'Java', 'SQL'))
    OR (s.reg_no IN ('CSE2024002', 'ISE2024008', 'ISE2024004') AND k.skill_name IN ('Java', 'SQL'))
    OR (s.reg_no LIKE 'MEC%' AND k.skill_name IN ('AutoCAD', 'Python'));

-- Drives. All start Ongoing so applications can be inserted; Data Analyst
-- is completed at the end (trg_application_before_insert refuses
-- applications to a Completed drive).
--   Software Engineer         - strict (8.00 CGPA, 0 backlogs), CSE/ISE only
--   Associate Engineer        - easy (6.50 CGPA, 1 backlog), open to all branches
--   Graduate Engineer Trainee - MECH only; closed by sp_close_drive in the demo
--   Data Analyst              - finished earlier in the season
-- Dates are relative to today (TRUNC(SYSDATE)), like db/seed.py, so the
-- demo always satisfies the date rules: open drives still take
-- applications, and the finished drive's whole timeline is in the past.
-- Deadline <= drive date is a CHECK; applying after the deadline is -20008.
INSERT INTO drive (company_id, coordinator_id, job_role, drive_date, application_deadline, package_lpa, min_cgpa, max_backlogs, drive_type, status)
SELECT company_id, 1, 'Software Engineer', TRUNC(SYSDATE) + 14, TRUNC(SYSDATE) + 10, 18.00, 8.00, 0, 'Full-Time', 'Ongoing'
  FROM company WHERE company_name = 'Nimbus Cloud Systems';
INSERT INTO drive (company_id, coordinator_id, job_role, drive_date, application_deadline, package_lpa, min_cgpa, max_backlogs, drive_type, status)
SELECT company_id, 1, 'Associate Engineer', TRUNC(SYSDATE) + 21, TRUNC(SYSDATE) + 15, 6.50, 6.50, 1, 'Full-Time', 'Ongoing'
  FROM company WHERE company_name = 'Coral Bay Solutions';
INSERT INTO drive (company_id, coordinator_id, job_role, drive_date, application_deadline, package_lpa, min_cgpa, max_backlogs, drive_type, status)
SELECT company_id, 1, 'Graduate Engineer Trainee', TRUNC(SYSDATE) + 28, TRUNC(SYSDATE) + 20, 7.20, 7.00, 1, 'Full-Time', 'Ongoing'
  FROM company WHERE company_name = 'Granite Motors';
INSERT INTO drive (company_id, coordinator_id, job_role, drive_date, application_deadline, package_lpa, min_cgpa, max_backlogs, drive_type, status)
SELECT company_id, 1, 'Data Analyst', TRUNC(SYSDATE) - 60, TRUNC(SYSDATE) - 65, 14.00, 7.50, 0, 'Full-Time', 'Ongoing'
  FROM company WHERE company_name = 'Nimbus Cloud Systems';

INSERT INTO drive_eligible_dept (drive_id, dept_id)
SELECT d.drive_id, dp.dept_id FROM drive d, department dp
 WHERE d.job_role = 'Software Engineer' AND dp.dept_code IN ('CSE', 'ISE');
INSERT INTO drive_eligible_dept (drive_id, dept_id)
SELECT d.drive_id, dp.dept_id FROM drive d, department dp
 WHERE d.job_role = 'Graduate Engineer Trainee' AND dp.dept_code = 'MECH';

-- Applications (student reg_no -> drive job_role). Each is dated a few days
-- before its drive's deadline, or two days ago for the open drives; never
-- after the deadline and never in the future (-20008).
INSERT INTO application (student_id, drive_id, applied_at)
SELECT s.student_id, d.drive_id,
       CAST(LEAST(d.application_deadline - 5, TRUNC(SYSDATE) - 2) AS TIMESTAMP) + INTERVAL '10' HOUR
  FROM student s, drive d
 WHERE (s.reg_no, d.job_role) IN (
        ('CSE2024001', 'Data Analyst'), ('ISE2024003', 'Data Analyst'), ('CSE2024007', 'Data Analyst'),
        ('CSE2024001', 'Software Engineer'), ('CSE2024007', 'Software Engineer'), ('ISE2024003', 'Software Engineer'),
        ('CSE2024002', 'Associate Engineer'), ('ISE2024008', 'Associate Engineer'), ('MEC2024005', 'Associate Engineer'),
        ('MEC2024005', 'Graduate Engineer Trainee'), ('MEC2024009', 'Graduate Engineer Trainee'));

-- Walk applications through the pipeline, one legal step per UPDATE.
-- (Each step is also recorded by trg_application_status_audit.)
UPDATE application SET status = 'Shortlisted'
 WHERE drive_id = (SELECT drive_id FROM drive WHERE job_role = 'Data Analyst');
UPDATE application SET status = 'Interview_Scheduled'
 WHERE drive_id = (SELECT drive_id FROM drive WHERE job_role = 'Data Analyst');
UPDATE application SET status = 'Selected'
 WHERE drive_id = (SELECT drive_id FROM drive WHERE job_role = 'Data Analyst')
   AND student_id IN (SELECT student_id FROM student WHERE reg_no IN ('CSE2024001', 'ISE2024003'));
UPDATE application SET status = 'Rejected'
 WHERE drive_id = (SELECT drive_id FROM drive WHERE job_role = 'Data Analyst')
   AND student_id = (SELECT student_id FROM student WHERE reg_no = 'CSE2024007');

UPDATE application SET status = 'Shortlisted'
 WHERE drive_id = (SELECT drive_id FROM drive WHERE job_role = 'Software Engineer')
   AND student_id IN (SELECT student_id FROM student WHERE reg_no IN ('CSE2024007', 'ISE2024003'));
UPDATE application SET status = 'Shortlisted'
 WHERE drive_id = (SELECT drive_id FROM drive WHERE job_role = 'Associate Engineer')
   AND student_id IN (SELECT student_id FROM student WHERE reg_no IN ('ISE2024008', 'MEC2024005'));
UPDATE application SET status = 'Interview_Scheduled'
 WHERE drive_id = (SELECT drive_id FROM drive WHERE job_role = 'Associate Engineer')
   AND student_id = (SELECT student_id FROM student WHERE reg_no = 'MEC2024005');
UPDATE application SET status = 'Shortlisted'
 WHERE drive_id = (SELECT drive_id FROM drive WHERE job_role = 'Graduate Engineer Trainee')
   AND student_id = (SELECT student_id FROM student WHERE reg_no = 'MEC2024005');

INSERT INTO interview_round (application_id, round_number, round_type, round_date, result)
SELECT a.application_id, 1, 'Aptitude', d.drive_date, 'Pass'
  FROM application a JOIN drive d ON d.drive_id = a.drive_id WHERE d.job_role = 'Data Analyst';
INSERT INTO interview_round (application_id, round_number, round_type, round_date, result)
SELECT a.application_id, 2, 'Technical', d.drive_date + 1,
       CASE WHEN s.reg_no = 'CSE2024007' THEN 'Fail' ELSE 'Pass' END
  FROM application a JOIN drive d ON d.drive_id = a.drive_id JOIN student s ON s.student_id = a.student_id
 WHERE d.job_role = 'Data Analyst';

-- Offers for the two Selected Data Analyst applicants (inserted Pending, as
-- the backend does; trg_offer_after_insert marks both students Placed).
INSERT INTO offer (application_id, offered_package_lpa, offer_date)
SELECT a.application_id, 15.00, d.drive_date + 3
  FROM application a JOIN drive d ON d.drive_id = a.drive_id JOIN student s ON s.student_id = a.student_id
 WHERE d.job_role = 'Data Analyst' AND s.reg_no = 'CSE2024001';
INSERT INTO offer (application_id, offered_package_lpa, offer_date)
SELECT a.application_id, 14.50, d.drive_date + 3
  FROM application a JOIN drive d ON d.drive_id = a.drive_id JOIN student s ON s.student_id = a.student_id
 WHERE d.job_role = 'Data Analyst' AND s.reg_no = 'ISE2024003';

INSERT INTO offer_history (offer_id, action, notes)
SELECT offer_id, 'Created', 'Offer recorded by placement cell' FROM offer;

UPDATE application SET status = 'Offer_Made'
 WHERE application_id IN (SELECT application_id FROM offer);

-- Aisha accepts her offer (Kavya's stays Pending for the transaction demo).
UPDATE offer SET status = 'Accepted', joining_date = offer_date + 60
 WHERE application_id = (SELECT a.application_id FROM application a
                           JOIN drive d ON d.drive_id = a.drive_id JOIN student s ON s.student_id = a.student_id
                          WHERE d.job_role = 'Data Analyst' AND s.reg_no = 'CSE2024001');
INSERT INTO offer_history (offer_id, action, notes)
SELECT offer_id, 'Accepted', 'Offer accepted by student' FROM offer WHERE status = 'Accepted';

-- The Data Analyst drive is over.
UPDATE drive SET status = 'Completed' WHERE job_role = 'Data Analyst';

COMMIT;

EXEC DBMS_MVIEW.REFRESH('MV_COMPANY_DEPT_PLACEMENTS', 'C');

-- Restore the defaults this script changed, so a demo run in the same
-- session still has &substitution variables available.
SET DEFINE ON
SET FEEDBACK ON
PROMPT Demo data loaded:
SELECT (SELECT COUNT(*) FROM student) AS students, (SELECT COUNT(*) FROM drive) AS drives,
       (SELECT COUNT(*) FROM application) AS applications, (SELECT COUNT(*) FROM offer) AS offers,
       (SELECT COUNT(*) FROM application_status_history) AS status_changes_logged
  FROM dual;
