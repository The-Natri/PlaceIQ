# Transactions at the SQL level

The offer-acceptance transaction run by hand in psql, showing what atomicity means
in practice. For the same transaction run through the real backend code (accept,
decline, and a rule-triggered rollback), see `transaction.md`.

_Generated 2026-10-22 05:28 by `docs/evidence/scripts/build_sql_evidence.py` against the live `placement_db` (freshly seeded). Output blocks are unedited psql output._

## A. The accept transaction, statement by statement (COMMIT replaced by ROLLBACK)

These are the three statements `backend/services/offer_service.accept_offer` runs, in the same
order, inside one transaction:
1. accept the Pending offer;
2. make sure the student is Placed;
3. log the acceptance in the history.

All three are visible inside the transaction. `ROLLBACK` then undoes all of them together.

```text
SELECT o.offer_id AS oid, a.student_id AS sid FROM offer o JOIN application a ON a.application_id = o.application_id
 WHERE o.status = 'Pending'
   AND NOT EXISTS (SELECT 1 FROM offer o2 JOIN application a2 ON a2.application_id = o2.application_id
                    WHERE a2.student_id = a.student_id AND o2.status = 'Accepted')
 ORDER BY o.offer_id LIMIT 1 
SELECT o.offer_id, o.status, o.joining_date, s.placement_status,
       (SELECT COUNT(*) FROM offer_history h WHERE h.offer_id = o.offer_id) AS history_rows
  FROM offer o JOIN application a ON a.application_id = o.application_id JOIN student s ON s.student_id = a.student_id
 WHERE o.offer_id = 3;
 offer_id | status  | joining_date | placement_status | history_rows 
----------+---------+--------------+------------------+--------------
        3 | Pending | (null)       | Placed           |            1
(1 row)

BEGIN;
BEGIN
UPDATE offer SET status = 'Accepted', joining_date = COALESCE(joining_date, offer_date + INTERVAL '60 days')
 WHERE offer_id = 3 AND status = 'Pending' RETURNING offer_id;
 offer_id 
----------
        3
(1 row)

UPDATE 1
UPDATE student SET placement_status = 'Placed' WHERE student_id = 52;
UPDATE 1
INSERT INTO offer_history (offer_id, action, notes) VALUES (3, 'Accepted', 'Offer accepted by student');
INSERT 0 1
SELECT o.offer_id, o.status, o.joining_date, s.placement_status,
       (SELECT COUNT(*) FROM offer_history h WHERE h.offer_id = o.offer_id) AS history_rows
  FROM offer o JOIN application a ON a.application_id = o.application_id JOIN student s ON s.student_id = a.student_id
 WHERE o.offer_id = 3;
 offer_id |  status  | joining_date | placement_status | history_rows 
----------+----------+--------------+------------------+--------------
        3 | Accepted | 2026-08-24   | Placed           |            2
(1 row)

ROLLBACK;
ROLLBACK
SELECT o.offer_id, o.status, o.joining_date, s.placement_status,
       (SELECT COUNT(*) FROM offer_history h WHERE h.offer_id = o.offer_id) AS history_rows
  FROM offer o JOIN application a ON a.application_id = o.application_id JOIN student s ON s.student_id = a.student_id
 WHERE o.offer_id = 3;
 offer_id | status  | joining_date | placement_status | history_rows 
----------+---------+--------------+------------------+--------------
        3 | Pending | (null)       | Placed           |            1
(1 row)
```

## B. Forced failure: one bad statement aborts the whole transaction

Same three statements, then a fourth that violates a CHECK constraint (an `offer_history.action`
value that isn't allowed). This block does **not** use ON_ERROR_ROLLBACK, so the failure aborts
the transaction:
- PostgreSQL refuses every later statement;
- `COMMIT` turns into a rollback;
- the offer is still Pending with the original history count.

The first two statements were undone too. This is atomicity.

```text
SELECT o.offer_id AS oid, a.student_id AS sid FROM offer o JOIN application a ON a.application_id = o.application_id
 WHERE o.status = 'Pending'
   AND NOT EXISTS (SELECT 1 FROM offer o2 JOIN application a2 ON a2.application_id = o2.application_id
                    WHERE a2.student_id = a.student_id AND o2.status = 'Accepted')
 ORDER BY o.offer_id LIMIT 1 
SELECT offer_id, status, (SELECT COUNT(*) FROM offer_history h WHERE h.offer_id = 3) AS history_rows FROM offer WHERE offer_id = 3;
 offer_id | status  | history_rows 
----------+---------+--------------
        3 | Pending |            1
(1 row)

BEGIN;
BEGIN
UPDATE offer SET status = 'Accepted' WHERE offer_id = 3 AND status = 'Pending' RETURNING offer_id, status;
 offer_id |  status  
----------+----------
        3 | Accepted
(1 row)

UPDATE 1
UPDATE student SET placement_status = 'Placed' WHERE student_id = 52;
UPDATE 1
INSERT INTO offer_history (offer_id, action, notes) VALUES (3, 'Bogus', 'not an allowed action');
ERROR:  new row for relation "offer_history" violates check constraint "offer_history_action_check"
DETAIL:  Failing row contains (331, 3, Bogus, 2026-10-22 05:28:31.307385, not an allowed action).
SELECT offer_id, status FROM offer WHERE offer_id = 3;
ERROR:  current transaction is aborted, commands ignored until end of transaction block
COMMIT;
ROLLBACK
SELECT offer_id, status, (SELECT COUNT(*) FROM offer_history h WHERE h.offer_id = 3) AS history_rows FROM offer WHERE offer_id = 3;
 offer_id | status  | history_rows 
----------+---------+--------------
        3 | Pending |            1
(1 row)
```
