# Queries and their real output

Every view, the materialized view, both stored functions and the stored procedure,
run against the seeded database. These are the queries behind the analytics page
and the student dashboard.

_Generated 2026-10-22 05:28 by `docs/evidence/scripts/build_sql_evidence.py` against the live `placement_db` (freshly seeded). Output blocks are unedited psql output._

## Placement % per department (`department_stats_view`)

LEFT JOIN from `department`, so a department with no students would still appear.

```text
SELECT * FROM department_stats_view ORDER BY placement_percentage DESC;
 dept_id |            dept_name            | total_students | placed_students | placement_percentage 
---------+---------------------------------+----------------+-----------------+----------------------
       4 | Electrical & Electronics        |             30 |              18 |                60.00
       6 | Artificial Intelligence & ML    |             30 |              17 |                56.67
       2 | Information Science Engineering |             30 |              16 |                53.33
       3 | Electronics & Communication     |             30 |              16 |                53.33
       5 | Mechanical Engineering          |             30 |              15 |                50.00
       1 | Computer Science Engineering    |             30 |              13 |                43.33
(6 rows)
```

## Package statistics per company (`company_wise_stats_view`)

Offers made and average / highest / lowest package for each recruiter.

```text
SELECT * FROM company_wise_stats_view ORDER BY company_name;
 company_id |     company_name     | offers_count | avg_package_lpa | max_package_lpa | min_package_lpa 
------------+----------------------+--------------+-----------------+-----------------+-----------------
          6 | Bluepeak Software    |            8 |           14.62 |           15.62 |           13.87
         14 | Coral Bay Solutions  |           80 |            6.89 |            8.84 |            4.92
         16 | Everstone Infra      |           41 |            7.14 |            8.08 |            6.14
         15 | Granite Motors       |            6 |            8.01 |            8.48 |            7.28
         12 | Meridian Consulting  |            8 |           10.14 |           10.88 |            9.10
          3 | Orbital Fintech      |            3 |           20.51 |           21.83 |           18.59
         18 | Solstice Retail Tech |           24 |            5.51 |            6.37 |            4.57
          2 | Vertex Analytics     |            4 |           22.83 |           23.93 |           22.03
         11 | Voltedge Power       |            3 |           10.95 |           11.63 |           10.43
(9 rows)
```

## Top recruiters by number of offers

The same view, sorted by offers and cut to the top 5.

```text
SELECT company_name, offers_count, avg_package_lpa
  FROM company_wise_stats_view
 ORDER BY offers_count DESC, company_name
 LIMIT 5;
     company_name     | offers_count | avg_package_lpa 
----------------------+--------------+-----------------
 Coral Bay Solutions  |           80 |            6.89
 Everstone Infra      |           41 |            7.14
 Solstice Retail Tech |           24 |            5.51
 Bluepeak Software    |            8 |           14.62
 Meridian Consulting  |            8 |           10.14
(5 rows)
```

## Placed students (`placed_students_view`)

One row per offer with the student, department and company joined in. The first 10 rows, then the totals by offer status.

```text
SELECT * FROM placed_students_view ORDER BY offered_package_lpa DESC LIMIT 10;
 student_id |   reg_no    |       name       |            dept_name            |   company_name    | offered_package_lpa | offer_date | offer_status 
------------+-------------+------------------+---------------------------------+-------------------+---------------------+------------+--------------
         37 | ISE2024007  | Arjun Joshi      | Information Science Engineering | Vertex Analytics  |               23.93 | 2026-06-25 | Declined
         44 | ISE2023014  | Aditya Pillai    | Information Science Engineering | Vertex Analytics  |               23.25 | 2026-06-25 | Accepted
         69 | ECE2024009  | Varun Joshi      | Electronics & Communication     | Vertex Analytics  |               22.10 | 2026-06-25 | Pending
         52 | ISE2024022  | Tanvi Chatterjee | Information Science Engineering | Vertex Analytics  |               22.03 | 2026-06-25 | Pending
         51 | ISE2023021  | Naveen Menon     | Information Science Engineering | Orbital Fintech   |               21.83 | 2026-06-29 | Accepted
         37 | ISE2024007  | Arjun Joshi      | Information Science Engineering | Orbital Fintech   |               21.10 | 2026-06-29 | Accepted
         52 | ISE2024022  | Tanvi Chatterjee | Information Science Engineering | Orbital Fintech   |               18.59 | 2026-07-08 | Pending
         15 | CSE2023015  | Aarav Chatterjee | Computer Science Engineering    | Bluepeak Software |               15.62 | 2026-09-10 | Declined
         14 | CSE2022014  | Rohan Mishra     | Computer Science Engineering    | Bluepeak Software |               15.58 | 2026-09-10 | Pending
        152 | AIML2023002 | Sneha Krishnan   | Artificial Intelligence & ML    | Bluepeak Software |               14.88 | 2026-09-21 | Pending
(10 rows)

SELECT offer_status, COUNT(*) AS offers FROM placed_students_view GROUP BY offer_status ORDER BY offer_status;
 offer_status | offers 
--------------+--------
 Accepted     |     85
 Declined     |     67
 Pending      |     25
(3 rows)
```

## Package statistics per branch

Average, highest and lowest offered package per department (the query behind `GET /api/analytics/package-by-branch`).

```text
SELECT d.dept_name,
       COUNT(o.offer_id) AS offers_count,
       ROUND(AVG(o.offered_package_lpa), 2) AS avg_package_lpa,
       MAX(o.offered_package_lpa) AS max_package_lpa,
       MIN(o.offered_package_lpa) AS min_package_lpa
  FROM offer o
  JOIN application a ON a.application_id = o.application_id
  JOIN student s ON s.student_id = a.student_id
  JOIN department d ON d.dept_id = s.dept_id
 GROUP BY d.dept_name
 ORDER BY avg_package_lpa DESC;
            dept_name            | offers_count | avg_package_lpa | max_package_lpa | min_package_lpa 
---------------------------------+--------------+-----------------+-----------------+-----------------
 Information Science Engineering |           39 |            9.66 |           23.93 |            4.57
 Electronics & Communication     |           30 |            8.33 |           22.10 |            5.07
 Computer Science Engineering    |           24 |            7.59 |           15.62 |            4.91
 Artificial Intelligence & ML    |           27 |            7.35 |           14.88 |            4.58
 Electrical & Electronics        |           32 |            7.11 |            8.73 |            4.95
 Mechanical Engineering          |           25 |            6.92 |            8.84 |            4.95
(6 rows)
```

## Top 3 offers in each department (`dept_offer_ranking_view`, `RANK()`)

`RANK() OVER (PARTITION BY dept ORDER BY package DESC)`; ties share a rank.

```text
SELECT dept_name, rank_in_dept, name, company_name, offered_package_lpa
  FROM dept_offer_ranking_view
 WHERE rank_in_dept <= 3
 ORDER BY dept_name, rank_in_dept, name;
            dept_name            | rank_in_dept |       name       |    company_name     | offered_package_lpa 
---------------------------------+--------------+------------------+---------------------+---------------------
 Artificial Intelligence & ML    |            1 | Sneha Krishnan   | Bluepeak Software   |               14.88
 Artificial Intelligence & ML    |            2 | Siddharth Reddy  | Coral Bay Solutions |                8.59
 Artificial Intelligence & ML    |            3 | Sneha Agarwal    | Coral Bay Solutions |                8.56
 Computer Science Engineering    |            1 | Rohan Mishra     | Bluepeak Software   |               15.58
 Computer Science Engineering    |            2 | Aadhya Shetty    | Meridian Consulting |               10.88
 Computer Science Engineering    |            3 | Reyansh Reddy    | Meridian Consulting |                9.10
 Electrical & Electronics        |            1 | Lakshmi Gowda    | Coral Bay Solutions |                8.73
 Electrical & Electronics        |            2 | Diya Gowda       | Coral Bay Solutions |                8.63
 Electrical & Electronics        |            3 | Tanvi Shetty     | Coral Bay Solutions |                8.25
 Electronics & Communication     |            1 | Varun Joshi      | Vertex Analytics    |               22.10
 Electronics & Communication     |            2 | Varun Joshi      | Bluepeak Software   |               14.33
 Electronics & Communication     |            3 | Sneha Rao        | Voltedge Power      |               11.63
 Information Science Engineering |            1 | Aditya Pillai    | Vertex Analytics    |               23.25
 Information Science Engineering |            2 | Tanvi Chatterjee | Vertex Analytics    |               22.03
 Information Science Engineering |            3 | Naveen Menon     | Orbital Fintech     |               21.83
 Mechanical Engineering          |            1 | Myra Kulkarni    | Coral Bay Solutions |                8.38
 Mechanical Engineering          |            2 | Priya Rao        | Coral Bay Solutions |                8.17
 Mechanical Engineering          |            3 | Advait Desai     | Coral Bay Solutions |                8.03
(18 rows)
```

## Offers per month with running total (`placement_timeline_view`)

`SUM(...) OVER (ORDER BY month)` is the running total and `LAG(...)` the previous month's count. Every month from the first offer to the last is generated (`generate_series`), so a month with no offers (January 2026 here) is a 0 row and February's change is measured against January, not December.

```text
SELECT * FROM placement_timeline_view ORDER BY month;
   month    | offers_in_month | cumulative_offers | change_from_prev_month 
------------+-----------------+-------------------+------------------------
 2026-05-01 |             114 |               114 |                 (null)
 2026-06-01 |              36 |               150 |                    -78
 2026-07-01 |               1 |               151 |                    -35
 2026-08-01 |               7 |               158 |                      6
 2026-09-01 |              19 |               177 |                     12
(5 rows)
```

## CGPA standing within department (`student_cgpa_standing_view`)

`DENSE_RANK()` and `PERCENT_RANK()` over each department; the top 2 students per department.

```text
SELECT d.dept_code, s.name, v.cgpa, v.cgpa_rank_in_dept, v.dept_size, v.cgpa_percentile_in_dept
  FROM student_cgpa_standing_view v
  JOIN student s ON s.student_id = v.student_id
  JOIN department d ON d.dept_id = v.dept_id
 WHERE v.cgpa_rank_in_dept <= 2
 ORDER BY d.dept_code, v.cgpa_rank_in_dept;
 dept_code |        name        | cgpa | cgpa_rank_in_dept | dept_size | cgpa_percentile_in_dept 
-----------+--------------------+------+-------------------+-----------+-------------------------
 AIML      | Sneha Agarwal      | 8.48 |                 1 |        30 |                   100.0
 AIML      | Sneha Krishnan     | 8.20 |                 2 |        30 |                    96.6
 CSE       | Aarav Chatterjee   | 9.15 |                 1 |        30 |                   100.0
 CSE       | Reyansh Reddy      | 8.33 |                 2 |        30 |                    96.6
 ECE       | Sneha Rao          | 8.97 |                 1 |        30 |                   100.0
 ECE       | Varun Joshi        | 8.70 |                 2 |        30 |                    96.6
 EEE       | Anika Hegde        | 8.62 |                 1 |        30 |                   100.0
 EEE       | Krishna Agarwal    | 8.55 |                 2 |        30 |                    96.6
 ISE       | Arjun Joshi        | 9.90 |                 1 |        30 |                   100.0
 ISE       | Tanvi Chatterjee   | 9.48 |                 2 |        30 |                    96.6
 MECH      | Reyansh Chatterjee | 9.07 |                 1 |        30 |                   100.0
 MECH      | Vivaan Kulkarni    | 8.42 |                 2 |        30 |                    96.6
(12 rows)
```

## Materialized view `mv_company_dept_placements`

A stored snapshot: `refreshed_at` is fixed at the last `REFRESH`. The 10 busiest company × department cells, then a refresh, which moves `refreshed_at` forward.

```text
SELECT company_name, dept_name, offers_count, avg_package_lpa
  FROM mv_company_dept_placements ORDER BY offers_count DESC, company_name, dept_name LIMIT 10;
     company_name     |            dept_name            | offers_count | avg_package_lpa 
----------------------+---------------------------------+--------------+-----------------
 Coral Bay Solutions  | Mechanical Engineering          |           14 |            6.70
 Coral Bay Solutions  | Electrical & Electronics        |           11 |            6.33
 Coral Bay Solutions  | Artificial Intelligence & ML    |            9 |            7.12
 Coral Bay Solutions  | Computer Science Engineering    |            9 |            6.92
 Coral Bay Solutions  | Electronics & Communication     |            9 |            6.90
 Everstone Infra      | Electrical & Electronics        |            7 |            7.29
 Coral Bay Solutions  | Information Science Engineering |            6 |            6.51
 Solstice Retail Tech | Artificial Intelligence & ML    |            5 |            5.02
 Everstone Infra      | Artificial Intelligence & ML    |            4 |            7.37
 Everstone Infra      | Electronics & Communication     |            3 |            7.44
(10 rows)

SELECT MAX(refreshed_at) AS refreshed_at FROM mv_company_dept_placements;
          refreshed_at           
---------------------------------
 2026-10-22 05:28:14.83657+05:30
(1 row)

REFRESH MATERIALIZED VIEW CONCURRENTLY mv_company_dept_placements;
REFRESH MATERIALIZED VIEW
SELECT MAX(refreshed_at) AS refreshed_at FROM mv_company_dept_placements;
          refreshed_at           
---------------------------------
 2026-10-22 05:28:28.16347+05:30
(1 row)
```

## `fn_check_eligibility(student, drive)`: eligible and ineligible cases

One real student/drive pair for each outcome, chosen by the query itself:
- a student who meets every rule (expect `t`);
- one below the CGPA cutoff;
- one with too many backlogs;
- one from a department the drive is not open to.

The `reason` column is computed independently, so the function's answer can be checked against it.

```text
WITH pairs AS (
  SELECT s.student_id, s.name, s.cgpa, s.backlogs, dep.dept_code,
         d.drive_id, d.job_role, d.min_cgpa, d.max_backlogs,
         (SELECT string_agg(x.dept_code, ',' ORDER BY x.dept_code) FROM drive_eligible_dept e
            JOIN department x ON x.dept_id = e.dept_id WHERE e.drive_id = d.drive_id) AS open_to,
         CASE
           WHEN s.cgpa < d.min_cgpa THEN 'CGPA below cutoff'
           WHEN s.backlogs > d.max_backlogs THEN 'too many backlogs'
           WHEN EXISTS (SELECT 1 FROM drive_eligible_dept e WHERE e.drive_id = d.drive_id)
            AND NOT EXISTS (SELECT 1 FROM drive_eligible_dept e WHERE e.drive_id = d.drive_id AND e.dept_id = s.dept_id)
             THEN 'department not allowed'
           ELSE 'meets every rule'
         END AS reason
    FROM student s JOIN department dep ON dep.dept_id = s.dept_id CROSS JOIN drive d
)
SELECT DISTINCT ON (reason) name, dept_code, cgpa, backlogs, job_role, min_cgpa, max_backlogs,
       COALESCE(open_to, 'ALL') AS open_to, reason,
       fn_check_eligibility(student_id, drive_id) AS eligible
  FROM pairs
 ORDER BY reason, student_id, drive_id;
     name     | dept_code | cgpa | backlogs |     job_role      | min_cgpa | max_backlogs |   open_to   |         reason         | eligible 
--------------+-----------+------+----------+-------------------+----------+--------------+-------------+------------------------+----------
 Myra Rao     | CSE       | 7.99 |        0 | Backend Developer |     8.25 |            0 | CSE,ECE     | CGPA below cutoff      | f
 Myra Rao     | CSE       | 7.99 |        0 | QA Engineer       |     7.42 |            1 | AIML,ECE    | department not allowed | f
 Myra Rao     | CSE       | 7.99 |        0 | Software Engineer |     7.42 |            1 | CSE,ISE     | meets every rule       | t
 Vikram Menon | ISE       | 7.01 |        2 | Data Analyst      |     7.01 |            1 | CSE,ECE,ISE | too many backlogs      | f
(4 rows)
```

## `fn_get_eligible_drives(student)`

The open (Upcoming/Ongoing) drives one student qualifies for: the function the student dashboard calls. The student is the highest-CGPA unplaced student.

```text
SELECT student_id AS sid, name, cgpa, backlogs
  FROM student WHERE placement_status = 'Not Placed' ORDER BY cgpa DESC LIMIT 1 
SELECT 15 AS student_id, 'Aarav Chatterjee' AS name, 9.15 AS cgpa, 0 AS backlogs;
 student_id |       name       | cgpa | backlogs 
------------+------------------+------+----------
         15 | Aarav Chatterjee | 9.15 |        0
(1 row)

SELECT e.drive_id, c.company_name, e.job_role, e.min_cgpa, e.max_backlogs, e.status
  FROM fn_get_eligible_drives(15) e JOIN company c ON c.company_id = e.company_id
 ORDER BY e.drive_date;
 drive_id |      company_name      |       job_role       | min_cgpa | max_backlogs |  status  
----------+------------------------+----------------------+----------+--------------+----------
        3 | Vertex Analytics       | ML Engineer          |     8.03 |            0 | Ongoing
       15 | Meridian Consulting    | Software Engineer    |     7.17 |            1 | Ongoing
       24 | Brightwave BPO         | Full Stack Developer |     6.26 |            2 | Ongoing
       13 | Ironclad Manufacturing | Core Engineer        |     7.45 |            1 | Ongoing
       11 | Aster Technologies     | Backend Developer    |     7.18 |            1 | Ongoing
       10 | Crestline Systems      | Data Analyst         |     7.38 |            1 | Upcoming
        1 | Nimbus Cloud Systems   | Backend Developer    |     8.25 |            0 | Upcoming
        6 | Quantara Labs          | QA Engineer          |     8.41 |            0 | Upcoming
(8 rows)
```

## `sp_close_drive`: before and after (rolled back)

Picks the Ongoing drive with the most pending applicants and shows its application statuses.
Then it calls the procedure inside a transaction, shows the drive and its applications again
(pending moved to Rejected, the drive Completed, and the audit rows the trigger wrote), and
finally `ROLLBACK`s, so the live data is unchanged.

```text
SELECT d.drive_id AS did, c.company_name || ' - ' || d.job_role AS drive_name
  FROM drive d JOIN company c ON c.company_id = d.company_id
  JOIN application a ON a.drive_id = d.drive_id
 WHERE d.status = 'Ongoing' AND a.status IN ('Applied', 'Shortlisted', 'Interview_Scheduled')
 GROUP BY d.drive_id, c.company_name, d.job_role ORDER BY COUNT(*) DESC LIMIT 1 
SELECT 24 AS drive_id, 'Brightwave BPO - Full Stack Developer' AS drive;
 drive_id |                 drive                 
----------+---------------------------------------
       24 | Brightwave BPO - Full Stack Developer
(1 row)

BEGIN;
BEGIN
SELECT status FROM drive WHERE drive_id = 24;
 status  
---------
 Ongoing
(1 row)

SELECT status, COUNT(*) FROM application WHERE drive_id = 24 GROUP BY status ORDER BY status;
       status        | count 
---------------------+-------
 Applied             |    27
 Interview_Scheduled |     5
 Shortlisted         |     5
(3 rows)

CALL sp_close_drive(24, NULL);
 p_rejected_count 
------------------
               37
(1 row)

SELECT status FROM drive WHERE drive_id = 24;
  status   
-----------
 Completed
(1 row)

SELECT status, COUNT(*) FROM application WHERE drive_id = 24 GROUP BY status ORDER BY status;
  status  | count 
----------+-------
 Rejected |    37
(1 row)

SELECT h.old_status, h.new_status, COUNT(*) AS logged_by_audit_trigger
  FROM application_status_history h JOIN application a ON a.application_id = h.application_id
 WHERE a.drive_id = 24 AND h.new_status = 'Rejected' AND h.changed_at >= now() - interval '1 minute'
 GROUP BY 1, 2;
     old_status      | new_status | logged_by_audit_trigger 
---------------------+------------+-------------------------
 Applied             | Rejected   |                      27
 Interview_Scheduled | Rejected   |                       5
 Shortlisted         | Rejected   |                       5
(3 rows)

ROLLBACK;
ROLLBACK
SELECT status FROM drive WHERE drive_id = 24;
 status  
---------
 Ongoing
(1 row)
```
