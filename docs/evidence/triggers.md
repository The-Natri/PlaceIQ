# Triggers and database rules in action

Each trigger and rule is fired with real statements against the seeded database. Rows are
picked by the queries themselves (see each `\gset`). Rule violations show psql's
`ERROR` line, followed by the SQLSTATE code the backend maps to an HTTP status
(`backend/utils/db_errors.py`). Anything that changes data is rolled back.

_Generated 2026-10-21 20:06 by `docs/evidence/scripts/build_sql_evidence.py` against the live `placement_db` (freshly seeded). Output blocks are unedited psql output._

## 1. Placement-status trigger (`trg_offer_after_insert`, AFTER INSERT on `offer`)

An unplaced student's Interview_Scheduled application is moved to Selected, then an offer is
inserted. Nothing in the statements touches `student`, but `placement_status` changes from
`Not Placed` to `Placed`: the trigger did it. Rolled back afterwards.

```text
SELECT a.application_id AS app, s.student_id AS sid, s.name
  FROM application a JOIN student s ON s.student_id = a.student_id
 WHERE a.status = 'Interview_Scheduled' AND s.placement_status = 'Not Placed'
 ORDER BY a.application_id LIMIT 1 
BEGIN;
BEGIN
SELECT name, placement_status FROM student WHERE student_id = 10;
     name      | placement_status 
---------------+------------------
 Priya Agarwal | Not Placed
(1 row)

UPDATE application SET status = 'Selected' WHERE application_id = 62;
UPDATE 1
INSERT INTO offer (application_id, offered_package_lpa) VALUES (62, 9.50) RETURNING offer_id, status;
 offer_id | status  
----------+---------
      186 | Pending
(1 row)

INSERT 0 1
SELECT name, placement_status FROM student WHERE student_id = 10;
     name      | placement_status 
---------------+------------------
 Priya Agarwal | Placed
(1 row)

ROLLBACK;
ROLLBACK
```

## 2. Application guard (`trg_application_before_insert`): not eligible → PL001

A student applies to an open drive whose CGPA cutoff they don't meet. The INSERT is refused.

```text
SELECT s.student_id AS sid, d.drive_id AS did, s.cgpa, d.min_cgpa
  FROM student s CROSS JOIN drive d
 WHERE d.status IN ('Upcoming', 'Ongoing') AND s.cgpa < d.min_cgpa
 ORDER BY s.cgpa, d.drive_id LIMIT 1 
SELECT 8 AS student_id, 4.50 AS cgpa, 1 AS drive_id, 8.25 AS drive_min_cgpa;
 student_id | cgpa | drive_id | drive_min_cgpa 
------------+------+----------+----------------
          8 | 4.50 |        1 |           8.25
(1 row)

INSERT INTO application (student_id, drive_id) VALUES (8, 1);
ERROR:  Student 8 is not eligible for drive 1
CONTEXT:  PL/pgSQL function trg_fn_application_guard() line 20 at RAISE
>>> SQLSTATE of the error above: PL001
```

## 3. Application guard: drive closed → PL002

An otherwise-eligible student applies to a Completed drive.

```text
SELECT s.student_id AS sid, d.drive_id AS did
  FROM student s CROSS JOIN drive d
 WHERE d.status = 'Completed'
   AND s.cgpa >= d.min_cgpa AND s.backlogs <= d.max_backlogs
   AND NOT EXISTS (SELECT 1 FROM application a WHERE a.student_id = s.student_id AND a.drive_id = d.drive_id)
 ORDER BY d.drive_id, s.student_id LIMIT 1 
SELECT drive_id, status FROM drive WHERE drive_id = 2;
 drive_id |  status   
----------+-----------
        2 | Completed
(1 row)

INSERT INTO application (student_id, drive_id) VALUES (12, 2);
ERROR:  Drive 2 is Completed and no longer accepts applications
CONTEXT:  PL/pgSQL function trg_fn_application_guard() line 14 at RAISE
>>> SQLSTATE of the error above: PL002
```

## 4. Second-offer guard (`trg_offer_before_accept`): one accepted offer per student → PL003

A student who has already accepted one offer tries to accept a second, Pending offer. The UPDATE
is refused and the second offer stays Pending.

```text
SELECT po.offer_id AS pending_offer, s.student_id AS sid, s.name
  FROM student s
  JOIN application a1 ON a1.student_id = s.student_id JOIN offer ao ON ao.application_id = a1.application_id AND ao.status = 'Accepted'
  JOIN application a2 ON a2.student_id = s.student_id JOIN offer po ON po.application_id = a2.application_id AND po.status = 'Pending'
 ORDER BY s.student_id LIMIT 1 
SELECT o.offer_id, o.status FROM offer o JOIN application a ON a.application_id = o.application_id
 WHERE a.student_id = 18 ORDER BY o.offer_id;
 offer_id |  status  
----------+----------
       70 | Pending
      115 | Accepted
(2 rows)

UPDATE offer SET status = 'Accepted' WHERE offer_id = 70;
ERROR:  Student 18 has already accepted another offer
CONTEXT:  PL/pgSQL function trg_fn_offer_single_acceptance() line 22 at RAISE
>>> SQLSTATE of the error above: PL003
SELECT o.offer_id, o.status FROM offer o JOIN application a ON a.application_id = o.application_id
 WHERE a.student_id = 18 ORDER BY o.offer_id;
 offer_id |  status  
----------+----------
       70 | Pending
      115 | Accepted
(2 rows)
```

## 5. Offer-on-rejected guard (`trg_offer_requires_selected`) → PL006

An offer is inserted for a Rejected application, bypassing the backend entirely. The database itself refuses it.

```text
SELECT application_id AS app FROM application WHERE status = 'Rejected' ORDER BY application_id LIMIT 1 
SELECT application_id, status FROM application WHERE application_id = 1;
 application_id |  status  
----------------+----------
              1 | Rejected
(1 row)

INSERT INTO offer (application_id, offered_package_lpa) VALUES (1, 8.00);
ERROR:  Application 1 is Rejected; an offer can only be recorded for a Selected application
CONTEXT:  PL/pgSQL function trg_fn_offer_requires_selected() line 14 at RAISE
>>> SQLSTATE of the error above: PL006
SELECT COUNT(*) AS offers_for_this_application FROM offer WHERE application_id = 1;
 offers_for_this_application 
-----------------------------
                           0
(1 row)
```

## 6. Status-transition guard (`trg_application_status_transition`) → PL007

- A Rejected application can't go back to Applied.
- An application that already has an offer can't go backwards to Shortlisted.
- A legal forward move (Applied → Shortlisted) still works.

Rolled back.

```text
SELECT application_id AS rejected_app FROM application WHERE status = 'Rejected' ORDER BY application_id LIMIT 1 
SELECT application_id AS offer_app FROM application WHERE status = 'Offer_Made' ORDER BY application_id LIMIT 1 
SELECT application_id AS applied_app FROM application WHERE status = 'Applied' ORDER BY application_id LIMIT 1 
BEGIN;
BEGIN
UPDATE application SET status = 'Applied' WHERE application_id = 1;
ERROR:  Application 1 cannot move from Rejected to Applied
CONTEXT:  PL/pgSQL function trg_fn_application_status_transition() line 14 at RAISE
>>> SQLSTATE of the error above: PL007
UPDATE application SET status = 'Shortlisted' WHERE application_id = 2;
ERROR:  Application 2 cannot move from Offer_Made to Shortlisted
CONTEXT:  PL/pgSQL function trg_fn_application_status_transition() line 14 at RAISE
>>> SQLSTATE of the error above: PL007
UPDATE application SET status = 'Shortlisted' WHERE application_id = 8 RETURNING application_id, status;
 application_id |   status    
----------------+-------------
              8 | Shortlisted
(1 row)

UPDATE 1
ROLLBACK;
ROLLBACK
```

## 7. Audit trigger (`trg_application_status_audit`, AFTER UPDATE OF status)

A status change is logged with its old and new value automatically. An UPDATE that doesn't change
the status is skipped by the trigger's `WHEN` clause, so it adds no row. Rolled back.

```text
SELECT application_id AS app FROM application WHERE status = 'Applied' ORDER BY application_id LIMIT 1 
BEGIN;
BEGIN
SELECT COUNT(*) AS history_rows_before FROM application_status_history WHERE application_id = 8;
 history_rows_before 
---------------------
                   0
(1 row)

UPDATE application SET status = 'Shortlisted' WHERE application_id = 8;
UPDATE 1
UPDATE application SET status = 'Shortlisted' WHERE application_id = 8;
UPDATE 1
SELECT old_status, new_status, changed_at FROM application_status_history WHERE application_id = 8 ORDER BY history_id;
 old_status | new_status  |         changed_at         
------------+-------------+----------------------------
 Applied    | Shortlisted | 2026-10-21 14:36:24.113767
(1 row)

ROLLBACK;
ROLLBACK
```

## 8. The audit trail the seed left behind

Every status change made while seeding went through the same trigger. This is how many transitions of each kind were logged.

```text
SELECT old_status, new_status, COUNT(*) AS times
  FROM application_status_history GROUP BY 1, 2 ORDER BY 1, 2;
     old_status      |     new_status      | times 
---------------------+---------------------+-------
 Applied             | Interview_Scheduled |    41
 Applied             | Rejected            |    71
 Applied             | Shortlisted         |   320
 Interview_Scheduled | Rejected            |   107
 Interview_Scheduled | Selected            |   177
 Selected            | Offer_Made          |   177
 Shortlisted         | Interview_Scheduled |   284
(7 rows)
```
