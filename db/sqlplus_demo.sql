-- =============================================================================
-- PlaceIQ — live SQL*Plus demo (Oracle)
--
-- Run as PLACEIQ after oracle_setup.sql, schema_oracle.sql and
-- seed_oracle_demo.sql:
--     sqlplus placeiq/PlaceIQ_dev_2026@//localhost:1521/XEPDB1
--     SQL> @db/sqlplus_demo.sql
--
-- What it shows, in order:
--   1. Stored function   fn_check_eligibility (eligible / ineligible / missing)
--   2. Set-returning fn  fn_get_eligible_drives (REF CURSOR)
--   3. Triggers firing   placement status on offer insert + audit log
--   4. Rule triggers     five invalid writes, each refused with its own error
--   5. Procedure         sp_close_drive (OUT parameter)
--   6. Views             analytics, window functions, materialized view
--   7. Transaction       the offer-accept statements, undone with ROLLBACK
--   8. Undo the demo     ROLLBACK everything, then refresh the MV
--
-- REPEATABLE: nothing is committed until the very end (section 8 rolls the
-- whole demo back first), so the script can be run again and again.
-- Errors in section 4 are EXPECTED — each one is a rule doing its job.
-- =============================================================================

SET ECHO OFF
-- The id lookups below rely on &substitution variables; make sure they are
-- enabled even if an earlier script in this session ran SET DEFINE OFF.
SET DEFINE ON
SET LINESIZE 200
SET PAGESIZE 100
SET TAB OFF
SET TRIMOUT ON
SET VERIFY OFF
SET FEEDBACK ON
SET SERVEROUTPUT ON
WHENEVER SQLERROR CONTINUE

COLUMN name               FORMAT A13
COLUMN reg_no             FORMAT A11
COLUMN dept               FORMAT A5
COLUMN dept_name          FORMAT A32
COLUMN company_name       FORMAT A21
COLUMN job_role           FORMAT A26
COLUMN status             FORMAT A20
COLUMN app_status         FORMAT A20
COLUMN placement_status   FORMAT A12
COLUMN old_status         FORMAT A20
COLUMN new_status         FORMAT A20
COLUMN action             FORMAT A9
COLUMN eligible           FORMAT 9
COLUMN drive_type         FORMAT A10
COLUMN created_at         FORMAT A28
COLUMN refreshed_at       FORMAT A35
COLUMN month              FORMAT A10
COLUMN open_to            FORMAT A8

-- Look up the ids the demo needs (by natural key, so nothing depends on
-- sequence values). NEW_VALUE stores each result in a substitution variable.
SET TERMOUT OFF
COLUMN v NEW_VALUE swe_id NOPRINT
SELECT drive_id v FROM drive WHERE job_role = 'Software Engineer';
COLUMN v NEW_VALUE da_id NOPRINT
SELECT drive_id v FROM drive WHERE job_role = 'Data Analyst';
COLUMN v NEW_VALUE get_id NOPRINT
SELECT drive_id v FROM drive WHERE job_role = 'Graduate Engineer Trainee';
COLUMN v NEW_VALUE aisha_id NOPRINT
SELECT student_id v FROM student WHERE reg_no = 'CSE2024001';
COLUMN v NEW_VALUE kavya_id NOPRINT
SELECT student_id v FROM student WHERE reg_no = 'ISE2024003';
COLUMN v NEW_VALUE arjun_id NOPRINT
SELECT student_id v FROM student WHERE reg_no = 'ISE2024004';
COLUMN v NEW_VALUE meera_id NOPRINT
SELECT student_id v FROM student WHERE reg_no = 'MEC2024005';
COLUMN v NEW_VALUE dev_id NOPRINT
SELECT student_id v FROM student WHERE reg_no = 'ISE2024008';
COLUMN v NEW_VALUE meera_ae_app NOPRINT
SELECT a.application_id v FROM application a JOIN drive d ON d.drive_id = a.drive_id
 WHERE a.student_id = (SELECT student_id FROM student WHERE reg_no = 'MEC2024005') AND d.job_role = 'Associate Engineer';
COLUMN v NEW_VALUE sneha_da_app NOPRINT
SELECT a.application_id v FROM application a JOIN drive d ON d.drive_id = a.drive_id
 WHERE a.student_id = (SELECT student_id FROM student WHERE reg_no = 'CSE2024007') AND d.job_role = 'Data Analyst';
COLUMN v NEW_VALUE aisha_swe_app NOPRINT
SELECT a.application_id v FROM application a JOIN drive d ON d.drive_id = a.drive_id
 WHERE a.student_id = (SELECT student_id FROM student WHERE reg_no = 'CSE2024001') AND d.job_role = 'Software Engineer';
COLUMN v NEW_VALUE kavya_offer NOPRINT
SELECT o.offer_id v FROM offer o JOIN application a ON a.application_id = o.application_id
 WHERE a.student_id = (SELECT student_id FROM student WHERE reg_no = 'ISE2024003');
SET TERMOUT ON
SET ECHO ON

-- -----------------------------------------------------------------------------
PROMPT
PROMPT ====================================================================
PROMPT  0. The data: students and drives
PROMPT ====================================================================
SELECT s.reg_no, s.name, d.dept_code AS dept, s.cgpa, s.backlogs, s.placement_status
  FROM student s JOIN department d ON d.dept_id = s.dept_id
 ORDER BY s.reg_no;

SELECT dr.drive_id, c.company_name, dr.job_role, dr.min_cgpa, dr.max_backlogs, dr.status,
       NVL((SELECT LISTAGG(dp.dept_code, ',') WITHIN GROUP (ORDER BY dp.dept_code)
              FROM drive_eligible_dept e JOIN department dp ON dp.dept_id = e.dept_id
             WHERE e.drive_id = dr.drive_id), 'ALL') AS open_to
  FROM drive dr JOIN company c ON c.company_id = dr.company_id
 ORDER BY dr.drive_id;

-- -----------------------------------------------------------------------------
PROMPT
PROMPT ====================================================================
PROMPT  1. Stored function fn_check_eligibility(student, drive)
PROMPT     Software Engineer needs CGPA >= 8.00, 0 backlogs, CSE/ISE only.
PROMPT     Expect: Aisha 1 (eligible), Arjun 0 (CGPA/backlogs), Meera 0 (branch)
PROMPT ====================================================================
SELECT s.name, d.dept_code AS dept, s.cgpa, s.backlogs,
       fn_check_eligibility(s.student_id, &swe_id) AS eligible
  FROM student s JOIN department d ON d.dept_id = s.dept_id
 WHERE s.reg_no IN ('CSE2024001', 'ISE2024004', 'MEC2024005')
 ORDER BY s.name;

PROMPT  A student id that doesn't exist: NO_DATA_FOUND is caught inside the function -> 0
SELECT fn_check_eligibility(99999, &swe_id) AS eligible FROM dual;

-- -----------------------------------------------------------------------------
PROMPT
PROMPT ====================================================================
PROMPT  2. fn_get_eligible_drives(student) returns a REF CURSOR
PROMPT     Meera (MECH, 7.80): the MECH drive and the open-to-all drive,
PROMPT     not the CSE/ISE-only one.
PROMPT ====================================================================
VARIABLE rc REFCURSOR
EXEC :rc := fn_get_eligible_drives(&meera_id)
COLUMN drive_id FORMAT 99
COLUMN company_id FORMAT 99
COLUMN coordinator_id FORMAT 99
PRINT rc

-- -----------------------------------------------------------------------------
PROMPT
PROMPT ====================================================================
PROMPT  3. Triggers firing: Meera is selected and gets an offer
PROMPT     trg_offer_after_insert sets placement_status;
PROMPT     trg_application_status_audit logs every status change.
PROMPT ====================================================================
SELECT name, placement_status FROM student WHERE student_id = &meera_id;

UPDATE application SET status = 'Selected' WHERE application_id = &meera_ae_app;

INSERT INTO offer (application_id, offered_package_lpa) VALUES (&meera_ae_app, 6.80);

PROMPT  After the INSERT - no UPDATE on student was run by us:
SELECT name, placement_status FROM student WHERE student_id = &meera_id;

PROMPT  The audit trail for her application (written by the trigger, not by us):
SELECT old_status, new_status FROM application_status_history
 WHERE application_id = &meera_ae_app ORDER BY history_id;

-- -----------------------------------------------------------------------------
PROMPT
PROMPT ====================================================================
PROMPT  4. Rule triggers refusing invalid writes (each ORA- error is expected)
PROMPT ====================================================================
PROMPT  4a. Arjun applies to Software Engineer (not eligible)  -> ORA-20001
INSERT INTO application (student_id, drive_id) VALUES (&arjun_id, &swe_id);

PROMPT  4b. Dev applies to the Completed Data Analyst drive    -> ORA-20002
INSERT INTO application (student_id, drive_id) VALUES (&dev_id, &da_id);

PROMPT  4c. An offer on Sneha's Rejected application            -> ORA-20006
INSERT INTO offer (application_id, offered_package_lpa) VALUES (&sneha_da_app, 14.00);

PROMPT  4d. Moving Sneha's application from Rejected back to Applied -> ORA-20007
UPDATE application SET status = 'Applied' WHERE application_id = &sneha_da_app;

PROMPT  4e. Aisha already ACCEPTED a Data Analyst offer. She is selected for
PROMPT      Software Engineer too and gets a second offer (allowed - it is Pending)...
UPDATE application SET status = 'Shortlisted' WHERE application_id = &aisha_swe_app;
UPDATE application SET status = 'Selected'    WHERE application_id = &aisha_swe_app;
INSERT INTO offer (application_id, offered_package_lpa) VALUES (&aisha_swe_app, 18.00);

PROMPT  ...but accepting it is refused by the COMPOUND trigger    -> ORA-20003
UPDATE offer SET status = 'Accepted' WHERE application_id = &aisha_swe_app;

PROMPT  Oracle rolled back only the failed statement - the offer is still Pending,
PROMPT  and our transaction (all the work above) is still open:
SELECT o.offer_id, o.status, o.offered_package_lpa FROM offer o WHERE o.application_id = &aisha_swe_app;

-- -----------------------------------------------------------------------------
PROMPT
PROMPT ====================================================================
PROMPT  5. Stored procedure sp_close_drive(drive, OUT rejected_count)
PROMPT     Graduate Engineer Trainee has two applicants still pending.
PROMPT ====================================================================
SELECT s.name, a.status AS app_status
  FROM application a JOIN student s ON s.student_id = a.student_id
 WHERE a.drive_id = &get_id ORDER BY s.name;

VARIABLE rejected NUMBER
EXEC sp_close_drive(&get_id, :rejected)
PRINT rejected

SELECT status FROM drive WHERE drive_id = &get_id;
SELECT s.name, a.status AS app_status
  FROM application a JOIN student s ON s.student_id = a.student_id
 WHERE a.drive_id = &get_id ORDER BY s.name;

PROMPT  Closing it a second time                                -> ORA-20005
EXEC sp_close_drive(&get_id, :rejected)

-- -----------------------------------------------------------------------------
PROMPT
PROMPT ====================================================================
PROMPT  6. Views
PROMPT ====================================================================
PROMPT  6a. department_stats_view - placement % per department
COLUMN placement_percentage FORMAT 990.99
SELECT dept_name, total_students, placed_students, placement_percentage
  FROM department_stats_view ORDER BY dept_name;

PROMPT  6b. company_wise_stats_view - offers and packages per company
SELECT company_name, offers_count, avg_package_lpa, max_package_lpa, min_package_lpa
  FROM company_wise_stats_view ORDER BY offers_count DESC, company_name;

PROMPT  6c. dept_offer_ranking_view - RANK() of offers within each department
SELECT dept_name, rank_in_dept, name, company_name, offered_package_lpa
  FROM dept_offer_ranking_view ORDER BY dept_name, rank_in_dept;

PROMPT  6d. placement_timeline_view - running total (SUM OVER) and LAG
SELECT TO_CHAR(month, 'YYYY-MM') AS month, offers_in_month, cumulative_offers, change_from_prev_month
  FROM placement_timeline_view ORDER BY 1;

PROMPT  6e. Materialized view - a stored snapshot. It still shows the data as of
PROMPT      its last refresh: Meera's and Aisha's new offers from this session
PROMPT      are in OFFER but NOT in the snapshot yet.
SELECT company_name, dept_name, offers_count, avg_package_lpa
  FROM mv_company_dept_placements ORDER BY company_name, dept_name;

-- -----------------------------------------------------------------------------
PROMPT
PROMPT ====================================================================
PROMPT  7. Transaction: the three statements offer_service.accept_offer runs
PROMPT     (update offer, update student, write history), then ROLLBACK
PROMPT     Kavya is already Placed - trg_offer_after_insert set that when her
PROMPT     offer was created - so the student UPDATE re-asserts it, exactly as
PROMPT     the backend does. Watch STATUS and HISTORY_ROWS change and revert.
PROMPT ====================================================================
PROMPT  Before:
SELECT o.offer_id, o.status, s.name, s.placement_status,
       (SELECT COUNT(*) FROM offer_history h WHERE h.offer_id = o.offer_id) AS history_rows
  FROM offer o JOIN application a ON a.application_id = o.application_id
  JOIN student s ON s.student_id = a.student_id
 WHERE o.offer_id = &kavya_offer;

SAVEPOINT before_accept;

UPDATE offer SET status = 'Accepted', joining_date = offer_date + 60
 WHERE offer_id = &kavya_offer AND status = 'Pending';
UPDATE student SET placement_status = 'Placed' WHERE student_id = &kavya_id;
INSERT INTO offer_history (offer_id, action, notes)
VALUES (&kavya_offer, 'Accepted', 'Offer accepted by student');

PROMPT  Inside the transaction, all three changes are visible:
SELECT o.offer_id, o.status, s.name, s.placement_status,
       (SELECT COUNT(*) FROM offer_history h WHERE h.offer_id = o.offer_id) AS history_rows
  FROM offer o JOIN application a ON a.application_id = o.application_id
  JOIN student s ON s.student_id = a.student_id
 WHERE o.offer_id = &kavya_offer;

ROLLBACK TO SAVEPOINT before_accept;

PROMPT  After ROLLBACK: all three are undone together (atomicity):
SELECT o.offer_id, o.status, s.name, s.placement_status,
       (SELECT COUNT(*) FROM offer_history h WHERE h.offer_id = o.offer_id) AS history_rows
  FROM offer o JOIN application a ON a.application_id = o.application_id
  JOIN student s ON s.student_id = a.student_id
 WHERE o.offer_id = &kavya_offer;

-- -----------------------------------------------------------------------------
PROMPT
PROMPT ====================================================================
PROMPT  8. Undo the whole demo, then refresh the materialized view
PROMPT ====================================================================
ROLLBACK;

PROMPT  Back to the seeded state (Meera Not Placed, Graduate Engineer Trainee Ongoing):
SELECT name, placement_status FROM student WHERE student_id = &meera_id;
SELECT job_role, status FROM drive WHERE drive_id = &get_id;

PROMPT  DBMS_MVIEW.REFRESH rebuilds the snapshot. (It COMMITs, which is why it
PROMPT  runs only after the ROLLBACK above - there is nothing left to commit.)
SELECT TO_CHAR(MAX(refreshed_at), 'YYYY-MM-DD HH24:MI:SS') AS refreshed_at FROM mv_company_dept_placements;
EXEC DBMS_MVIEW.REFRESH('MV_COMPANY_DEPT_PLACEMENTS', 'C')
SELECT TO_CHAR(MAX(refreshed_at), 'YYYY-MM-DD HH24:MI:SS') AS refreshed_at FROM mv_company_dept_placements;

SET ECHO OFF
PROMPT
PROMPT Demo complete. Nothing from sections 3-7 was committed.
