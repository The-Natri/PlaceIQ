# Date integrity

Applications, interview rounds, offers and status changes follow each other in time, and nothing
is dated in the future. `db/seed.py` builds every timeline relative to the day it runs. The
database refuses the one rule a client could break: applying after a drive's deadline
(`trg_application_before_insert`, PL008), plus the deadline <= drive date CHECK.

_Generated 2026-10-22 05:28 by `docs/evidence/scripts/build_sql_evidence.py` against the live `placement_db` (freshly seeded). Output blocks are unedited psql output._

## Every date rule, counted

Each row counts the rows that break one rule; every count should be 0.
- **A** applied on or before the drive's deadline;
- **B** no application dated in the future;
- **C** deadline on or before the drive date;
- **D** every interview round on or after the application date;
- **E** rounds that already have a result are not in the future;
- **F** each offer after the application's final round;
- **G** no offer dated in the future;
- **H** status changes after the application date and not in the future;
- **I** status changes in the same order as they were logged;
- **J** offer events after the application date.

```text
SELECT 'A applied after the drive deadline' AS rule, COUNT(*) AS violations
  FROM application a JOIN drive d ON d.drive_id = a.drive_id WHERE a.applied_at::DATE > d.application_deadline
UNION ALL
SELECT 'B application dated in the future', COUNT(*) FROM application WHERE applied_at > now()
UNION ALL
SELECT 'C deadline after the drive date', COUNT(*) FROM drive WHERE application_deadline > drive_date
UNION ALL
SELECT 'D round before the application date', COUNT(*)
  FROM interview_round r JOIN application a ON a.application_id = r.application_id WHERE r.round_date < a.applied_at::DATE
UNION ALL
SELECT 'E finished round dated in the future', COUNT(*) FROM interview_round WHERE result <> 'Pending' AND round_date > CURRENT_DATE
UNION ALL
SELECT 'F offer not after the final round', COUNT(*)
  FROM offer o WHERE o.offer_date <= (SELECT MAX(r.round_date) FROM interview_round r WHERE r.application_id = o.application_id)
UNION ALL
SELECT 'G offer dated in the future', COUNT(*) FROM offer WHERE offer_date > CURRENT_DATE
UNION ALL
SELECT 'H status change before applying or in the future', COUNT(*)
  FROM application_status_history h JOIN application a ON a.application_id = h.application_id
 WHERE h.changed_at < a.applied_at OR h.changed_at > now()
UNION ALL
SELECT 'I status changes out of order', COUNT(*)
  FROM (SELECT changed_at, LAG(changed_at) OVER (PARTITION BY application_id ORDER BY history_id) AS prev
          FROM application_status_history) x WHERE changed_at < prev
UNION ALL
SELECT 'J offer event before the application date', COUNT(*)
  FROM offer_history oh JOIN offer o ON o.offer_id = oh.offer_id JOIN application a ON a.application_id = o.application_id
 WHERE oh.action_timestamp < a.applied_at;
                       rule                       | violations 
--------------------------------------------------+------------
 A applied after the drive deadline               |          0
 B application dated in the future                |          0
 C deadline after the drive date                  |          0
 D round before the application date              |          0
 E finished round dated in the future             |          0
 F offer not after the final round                |          0
 G offer dated in the future                      |          0
 H status change before applying or in the future |          0
 I status changes out of order                    |          0
 J offer event before the application date        |          0
(10 rows)
```

## What the timeline looks like

Drives by status, with their date ranges relative to the day the data was seeded, and how many rows each kind of event has.

```text
SELECT CURRENT_DATE AS today;
   today    
------------
 2026-10-22
(1 row)

SELECT status, COUNT(*) AS drives, MIN(application_deadline) AS earliest_deadline,
       MAX(application_deadline) AS latest_deadline, MIN(drive_date) AS earliest_drive, MAX(drive_date) AS latest_drive
  FROM drive GROUP BY status ORDER BY status;
  status   | drives | earliest_deadline | latest_deadline | earliest_drive | latest_drive 
-----------+--------+-------------------+-----------------+----------------+--------------
 Completed |     14 | 2026-04-26        | 2026-09-14      | 2026-04-29     | 2026-09-18
 Ongoing   |      8 | 2026-10-25        | 2026-10-31      | 2026-10-27     | 2026-11-05
 Upcoming  |      3 | 2026-11-02        | 2026-11-12      | 2026-11-05     | 2026-11-19
(3 rows)

SELECT 'applications' AS what, COUNT(*), MIN(applied_at)::DATE AS first, MAX(applied_at)::DATE AS last FROM application
UNION ALL SELECT 'interview rounds', COUNT(*), MIN(round_date), MAX(round_date) FROM interview_round
UNION ALL SELECT 'offers', COUNT(*), MIN(offer_date), MAX(offer_date) FROM offer
UNION ALL SELECT 'status changes', COUNT(*), MIN(changed_at)::DATE, MAX(changed_at)::DATE FROM application_status_history;
       what       | count |   first    |    last    
------------------+-------+------------+------------
 applications     |   517 | 2026-04-06 | 2026-10-20
 interview rounds |   806 | 2026-04-29 | 2026-11-05
 offers           |   177 | 2026-05-03 | 2026-09-21
 status changes   |  1177 | 2026-04-27 | 2026-10-21
(4 rows)
```

## One completed application, end to end

The full timeline of one application that reached an offer, in date order.

```text
SELECT a.application_id AS app FROM application a JOIN offer o ON o.application_id = a.application_id
 ORDER BY a.application_id LIMIT 1 
SELECT event, at FROM (
  SELECT 'drive: applications close' AS event, d.application_deadline::TIMESTAMP AS at
    FROM application a JOIN drive d ON d.drive_id = a.drive_id WHERE a.application_id = 2
  UNION ALL SELECT 'drive: drive day', d.drive_date::TIMESTAMP
    FROM application a JOIN drive d ON d.drive_id = a.drive_id WHERE a.application_id = 2
  UNION ALL SELECT 'applied', applied_at FROM application WHERE application_id = 2
  UNION ALL SELECT 'status: ' || old_status || ' -> ' || new_status, changed_at
    FROM application_status_history WHERE application_id = 2
  UNION ALL SELECT 'round ' || round_number || ' (' || round_type || '): ' || result, round_date::TIMESTAMP
    FROM interview_round WHERE application_id = 2
  UNION ALL SELECT 'offer: ' || action, oh.action_timestamp
    FROM offer_history oh JOIN offer o ON o.offer_id = oh.offer_id WHERE o.application_id = 2
) t ORDER BY at, event;
                   event                    |         at          
--------------------------------------------+---------------------
 applied                                    | 2026-06-13 18:03:00
 drive: applications close                  | 2026-06-15 00:00:00
 status: Applied -> Shortlisted             | 2026-06-16 10:31:00
 status: Shortlisted -> Interview_Scheduled | 2026-06-16 12:31:00
 drive: drive day                           | 2026-06-21 00:00:00
 round 1 (Aptitude): Pass                   | 2026-06-21 00:00:00
 round 2 (Technical): Pass                  | 2026-06-22 00:00:00
 round 3 (HR): Pass                         | 2026-06-23 00:00:00
 status: Interview_Scheduled -> Selected    | 2026-06-24 17:27:00
 offer: Created                             | 2026-06-25 11:29:00
 status: Selected -> Offer_Made             | 2026-06-25 11:29:00
 offer: Declined                            | 2026-06-28 18:59:00
(12 rows)
```

## The database refuses a late application (PL008)

The rule is enforced by `trg_application_before_insert`, not only by the seed. Inside one transaction:
1. an eligible student applies to an open drive, which is accepted;
2. the drive's deadline is moved to yesterday and another eligible student applies, which is refused;
3. an application dated in the future is refused.

Rolled back.

```text
SELECT d.drive_id AS did, MIN(s.student_id) AS sid1, MAX(s.student_id) AS sid2
  FROM student s CROSS JOIN drive d
 WHERE d.status IN ('Upcoming', 'Ongoing') AND d.application_deadline >= CURRENT_DATE
   AND fn_check_eligibility(s.student_id, d.drive_id)
   AND NOT EXISTS (SELECT 1 FROM application a WHERE a.student_id = s.student_id AND a.drive_id = d.drive_id)
 GROUP BY d.drive_id HAVING COUNT(*) >= 2 ORDER BY d.drive_id LIMIT 1 
BEGIN;
BEGIN
SELECT drive_id, status, application_deadline, drive_date FROM drive WHERE drive_id = 1;
 drive_id |  status  | application_deadline | drive_date 
----------+----------+----------------------+------------
        1 | Upcoming | 2026-11-11           | 2026-11-15
(1 row)

INSERT INTO application (student_id, drive_id) VALUES (12, 1) RETURNING application_id, applied_at::DATE;
 application_id | applied_at 
----------------+------------
            520 | 2026-10-22
(1 row)

INSERT 0 1
UPDATE drive SET application_deadline = CURRENT_DATE - 1 WHERE drive_id = 1 RETURNING application_deadline;
 application_deadline 
----------------------
 2026-10-21
(1 row)

UPDATE 1
INSERT INTO application (student_id, drive_id) VALUES (69, 1);
ERROR:  Applications for drive 1 closed on 2026-10-21
CONTEXT:  PL/pgSQL function trg_fn_application_guard() line 33 at RAISE
>>> SQLSTATE of the error above: PL008
INSERT INTO application (student_id, drive_id, applied_at) VALUES (69, 1, now() + INTERVAL '1 hour');
ERROR:  Application date 2026-10-22 06:28:30.982637 is in the future
CONTEXT:  PL/pgSQL function trg_fn_application_guard() line 28 at RAISE
>>> SQLSTATE of the error above: PL008
UPDATE drive SET application_deadline = drive_date + 1 WHERE drive_id = 1;
ERROR:  new row for relation "drive" violates check constraint "drive_check"
DETAIL:  Failing row contains (1, 1, 1, Backend Developer, 2026-11-15, 2026-11-16, 31.28, 8.25, 0, Full-Time, Upcoming, 2026-10-22 05:28:09.468802).
>>> SQLSTATE of the error above: 23514
ROLLBACK;
ROLLBACK
```
