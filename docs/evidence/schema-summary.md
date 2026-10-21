# Schema summary

Every table's columns, types and constraints, read from the PostgreSQL system
catalog (`information_schema`, `pg_constraint`, `pg_indexes`, `pg_trigger`) of the
running database, so this always matches what `db/schema.sql` actually created.

_Generated 2026-10-21 20:06 by `docs/evidence/scripts/build_sql_evidence.py` against the live `placement_db` (freshly seeded). Output blocks are unedited psql output._

## All tables at a glance

Row counts after seeding, and how many columns each table has.

```text
SELECT t.table_name,
       (SELECT COUNT(*) FROM information_schema.columns c
         WHERE c.table_schema = 'public' AND c.table_name = t.table_name) AS columns,
       (xpath('/row/n/text()', query_to_xml(format('SELECT COUNT(*) AS n FROM %I', t.table_name), false, true, '')))[1]::text::int AS rows
  FROM information_schema.tables t
 WHERE t.table_schema = 'public' AND t.table_type = 'BASE TABLE'
 ORDER BY t.table_name;
         table_name         | columns | rows 
----------------------------+---------+------
 application                |       5 |  517
 application_status_history |       5 | 1177
 company                    |       5 |   18
 coordinator                |       6 |    2
 department                 |       3 |    6
 drive                      |      11 |   25
 drive_eligible_dept        |       2 |   40
 interview_round            |       7 |  842
 offer                      |       6 |  177
 offer_history              |       5 |  329
 skill                      |       2 |   28
 student                    |      12 |  180
 student_skill              |       2 |  589
(13 rows)
```

## `department`

Columns (type, nullability, default), then every constraint on `department`: PRIMARY KEY, FOREIGN KEY (with its ON DELETE rule), UNIQUE and CHECK.

```text
SELECT column_name, data_type || COALESCE('(' || character_maximum_length || ')', '')
       || COALESCE(CASE WHEN data_type = 'numeric' THEN '(' || numeric_precision || ',' || numeric_scale || ')' END, '') AS type,
       is_nullable AS nullable,
       COALESCE(column_default, CASE WHEN is_identity = 'YES' THEN 'identity' END) AS "default"
  FROM information_schema.columns
 WHERE table_schema = 'public' AND table_name = 'department'
 ORDER BY ordinal_position;
 column_name |          type          | nullable | default  
-------------+------------------------+----------+----------
 dept_id     | integer                | NO       | identity
 dept_name   | character varying(100) | NO       | (null)
 dept_code   | character varying(10)  | NO       | (null)
(3 rows)

SELECT conname AS constraint_name,
       CASE contype WHEN 'p' THEN 'PRIMARY KEY' WHEN 'f' THEN 'FOREIGN KEY' WHEN 'u' THEN 'UNIQUE' WHEN 'c' THEN 'CHECK' END AS kind,
       pg_get_constraintdef(oid) AS definition
  FROM pg_constraint
 WHERE conrelid = 'public.department'::regclass
 ORDER BY contype, conname;
     constraint_name      |    kind     |      definition       
--------------------------+-------------+-----------------------
 department_pkey          | PRIMARY KEY | PRIMARY KEY (dept_id)
 department_dept_code_key | UNIQUE      | UNIQUE (dept_code)
 department_dept_name_key | UNIQUE      | UNIQUE (dept_name)
(3 rows)
```

## `coordinator`

Columns (type, nullability, default), then every constraint on `coordinator`: PRIMARY KEY, FOREIGN KEY (with its ON DELETE rule), UNIQUE and CHECK.

```text
SELECT column_name, data_type || COALESCE('(' || character_maximum_length || ')', '')
       || COALESCE(CASE WHEN data_type = 'numeric' THEN '(' || numeric_precision || ',' || numeric_scale || ')' END, '') AS type,
       is_nullable AS nullable,
       COALESCE(column_default, CASE WHEN is_identity = 'YES' THEN 'identity' END) AS "default"
  FROM information_schema.columns
 WHERE table_schema = 'public' AND table_name = 'coordinator'
 ORDER BY ordinal_position;
  column_name   |            type             | nullable |             default              
----------------+-----------------------------+----------+----------------------------------
 coordinator_id | integer                     | NO       | identity
 name           | character varying(100)      | NO       | (null)
 email          | character varying(120)      | NO       | (null)
 password_hash  | character varying(255)      | NO       | (null)
 role           | character varying(20)       | NO       | 'Coordinator'::character varying
 created_at     | timestamp without time zone | NO       | CURRENT_TIMESTAMP
(6 rows)

SELECT conname AS constraint_name,
       CASE contype WHEN 'p' THEN 'PRIMARY KEY' WHEN 'f' THEN 'FOREIGN KEY' WHEN 'u' THEN 'UNIQUE' WHEN 'c' THEN 'CHECK' END AS kind,
       pg_get_constraintdef(oid) AS definition
  FROM pg_constraint
 WHERE conrelid = 'public.coordinator'::regclass
 ORDER BY contype, conname;
    constraint_name     |    kind     |                                                 definition                                                 
------------------------+-------------+------------------------------------------------------------------------------------------------------------
 coordinator_role_check | CHECK       | CHECK (((role)::text = ANY ((ARRAY['TPO'::character varying, 'Coordinator'::character varying])::text[])))
 coordinator_pkey       | PRIMARY KEY | PRIMARY KEY (coordinator_id)
 coordinator_email_key  | UNIQUE      | UNIQUE (email)
(3 rows)
```

## `student`

Columns (type, nullability, default), then every constraint on `student`: PRIMARY KEY, FOREIGN KEY (with its ON DELETE rule), UNIQUE and CHECK.

```text
SELECT column_name, data_type || COALESCE('(' || character_maximum_length || ')', '')
       || COALESCE(CASE WHEN data_type = 'numeric' THEN '(' || numeric_precision || ',' || numeric_scale || ')' END, '') AS type,
       is_nullable AS nullable,
       COALESCE(column_default, CASE WHEN is_identity = 'YES' THEN 'identity' END) AS "default"
  FROM information_schema.columns
 WHERE table_schema = 'public' AND table_name = 'student'
 ORDER BY ordinal_position;
   column_name    |            type             | nullable |             default             
------------------+-----------------------------+----------+---------------------------------
 student_id       | integer                     | NO       | identity
 reg_no           | character varying(20)       | NO       | (null)
 name             | character varying(100)      | NO       | (null)
 email            | character varying(120)      | NO       | (null)
 password_hash    | character varying(255)      | NO       | (null)
 dept_id          | integer                     | NO       | (null)
 cgpa             | numeric(4,2)                | NO       | (null)
 backlogs         | integer                     | NO       | 0
 batch_year       | integer                     | NO       | (null)
 phone            | character varying(15)       | YES      | (null)
 placement_status | character varying(20)       | NO       | 'Not Placed'::character varying
 created_at       | timestamp without time zone | NO       | CURRENT_TIMESTAMP
(12 rows)

SELECT conname AS constraint_name,
       CASE contype WHEN 'p' THEN 'PRIMARY KEY' WHEN 'f' THEN 'FOREIGN KEY' WHEN 'u' THEN 'UNIQUE' WHEN 'c' THEN 'CHECK' END AS kind,
       pg_get_constraintdef(oid) AS definition
  FROM pg_constraint
 WHERE conrelid = 'public.student'::regclass
 ORDER BY contype, conname;
        constraint_name         |    kind     |                                                        definition                                                        
--------------------------------+-------------+--------------------------------------------------------------------------------------------------------------------------
 student_backlogs_check         | CHECK       | CHECK ((backlogs >= 0))
 student_batch_year_check       | CHECK       | CHECK (((batch_year >= 2000) AND (batch_year <= 2100)))
 student_cgpa_check             | CHECK       | CHECK (((cgpa >= (0)::numeric) AND (cgpa <= (10)::numeric)))
 student_placement_status_check | CHECK       | CHECK (((placement_status)::text = ANY ((ARRAY['Not Placed'::character varying, 'Placed'::character varying])::text[])))
 student_dept_id_fkey           | FOREIGN KEY | FOREIGN KEY (dept_id) REFERENCES department(dept_id)
 student_pkey                   | PRIMARY KEY | PRIMARY KEY (student_id)
 student_email_key              | UNIQUE      | UNIQUE (email)
 student_reg_no_key             | UNIQUE      | UNIQUE (reg_no)
(8 rows)
```

## `skill`

Columns (type, nullability, default), then every constraint on `skill`: PRIMARY KEY, FOREIGN KEY (with its ON DELETE rule), UNIQUE and CHECK.

```text
SELECT column_name, data_type || COALESCE('(' || character_maximum_length || ')', '')
       || COALESCE(CASE WHEN data_type = 'numeric' THEN '(' || numeric_precision || ',' || numeric_scale || ')' END, '') AS type,
       is_nullable AS nullable,
       COALESCE(column_default, CASE WHEN is_identity = 'YES' THEN 'identity' END) AS "default"
  FROM information_schema.columns
 WHERE table_schema = 'public' AND table_name = 'skill'
 ORDER BY ordinal_position;
 column_name |         type          | nullable | default  
-------------+-----------------------+----------+----------
 skill_id    | integer               | NO       | identity
 skill_name  | character varying(60) | NO       | (null)
(2 rows)

SELECT conname AS constraint_name,
       CASE contype WHEN 'p' THEN 'PRIMARY KEY' WHEN 'f' THEN 'FOREIGN KEY' WHEN 'u' THEN 'UNIQUE' WHEN 'c' THEN 'CHECK' END AS kind,
       pg_get_constraintdef(oid) AS definition
  FROM pg_constraint
 WHERE conrelid = 'public.skill'::regclass
 ORDER BY contype, conname;
   constraint_name    |    kind     |       definition       
----------------------+-------------+------------------------
 skill_pkey           | PRIMARY KEY | PRIMARY KEY (skill_id)
 skill_skill_name_key | UNIQUE      | UNIQUE (skill_name)
(2 rows)
```

## `student_skill`

Columns (type, nullability, default), then every constraint on `student_skill`: PRIMARY KEY, FOREIGN KEY (with its ON DELETE rule), UNIQUE and CHECK.

```text
SELECT column_name, data_type || COALESCE('(' || character_maximum_length || ')', '')
       || COALESCE(CASE WHEN data_type = 'numeric' THEN '(' || numeric_precision || ',' || numeric_scale || ')' END, '') AS type,
       is_nullable AS nullable,
       COALESCE(column_default, CASE WHEN is_identity = 'YES' THEN 'identity' END) AS "default"
  FROM information_schema.columns
 WHERE table_schema = 'public' AND table_name = 'student_skill'
 ORDER BY ordinal_position;
 column_name |  type   | nullable | default 
-------------+---------+----------+---------
 student_id  | integer | NO       | (null)
 skill_id    | integer | NO       | (null)
(2 rows)

SELECT conname AS constraint_name,
       CASE contype WHEN 'p' THEN 'PRIMARY KEY' WHEN 'f' THEN 'FOREIGN KEY' WHEN 'u' THEN 'UNIQUE' WHEN 'c' THEN 'CHECK' END AS kind,
       pg_get_constraintdef(oid) AS definition
  FROM pg_constraint
 WHERE conrelid = 'public.student_skill'::regclass
 ORDER BY contype, conname;
        constraint_name        |    kind     |                                definition                                 
-------------------------------+-------------+---------------------------------------------------------------------------
 student_skill_skill_id_fkey   | FOREIGN KEY | FOREIGN KEY (skill_id) REFERENCES skill(skill_id) ON DELETE CASCADE
 student_skill_student_id_fkey | FOREIGN KEY | FOREIGN KEY (student_id) REFERENCES student(student_id) ON DELETE CASCADE
 student_skill_pkey            | PRIMARY KEY | PRIMARY KEY (student_id, skill_id)
(3 rows)
```

## `company`

Columns (type, nullability, default), then every constraint on `company`: PRIMARY KEY, FOREIGN KEY (with its ON DELETE rule), UNIQUE and CHECK.

```text
SELECT column_name, data_type || COALESCE('(' || character_maximum_length || ')', '')
       || COALESCE(CASE WHEN data_type = 'numeric' THEN '(' || numeric_precision || ',' || numeric_scale || ')' END, '') AS type,
       is_nullable AS nullable,
       COALESCE(column_default, CASE WHEN is_identity = 'YES' THEN 'identity' END) AS "default"
  FROM information_schema.columns
 WHERE table_schema = 'public' AND table_name = 'company'
 ORDER BY ordinal_position;
   column_name   |          type          | nullable | default  
-----------------+------------------------+----------+----------
 company_id      | integer                | NO       | identity
 company_name    | character varying(150) | NO       | (null)
 industry_sector | character varying(80)  | YES      | (null)
 website         | character varying(200) | YES      | (null)
 hr_email        | character varying(120) | YES      | (null)
(5 rows)

SELECT conname AS constraint_name,
       CASE contype WHEN 'p' THEN 'PRIMARY KEY' WHEN 'f' THEN 'FOREIGN KEY' WHEN 'u' THEN 'UNIQUE' WHEN 'c' THEN 'CHECK' END AS kind,
       pg_get_constraintdef(oid) AS definition
  FROM pg_constraint
 WHERE conrelid = 'public.company'::regclass
 ORDER BY contype, conname;
     constraint_name      |    kind     |        definition        
--------------------------+-------------+--------------------------
 company_pkey             | PRIMARY KEY | PRIMARY KEY (company_id)
 company_company_name_key | UNIQUE      | UNIQUE (company_name)
(2 rows)
```

## `drive`

Columns (type, nullability, default), then every constraint on `drive`: PRIMARY KEY, FOREIGN KEY (with its ON DELETE rule), UNIQUE and CHECK.

```text
SELECT column_name, data_type || COALESCE('(' || character_maximum_length || ')', '')
       || COALESCE(CASE WHEN data_type = 'numeric' THEN '(' || numeric_precision || ',' || numeric_scale || ')' END, '') AS type,
       is_nullable AS nullable,
       COALESCE(column_default, CASE WHEN is_identity = 'YES' THEN 'identity' END) AS "default"
  FROM information_schema.columns
 WHERE table_schema = 'public' AND table_name = 'drive'
 ORDER BY ordinal_position;
  column_name   |            type             | nullable |            default             
----------------+-----------------------------+----------+--------------------------------
 drive_id       | integer                     | NO       | identity
 company_id     | integer                     | NO       | (null)
 coordinator_id | integer                     | YES      | (null)
 job_role       | character varying(100)      | NO       | (null)
 drive_date     | date                        | NO       | (null)
 package_lpa    | numeric(6,2)                | NO       | (null)
 min_cgpa       | numeric(4,2)                | NO       | 0
 max_backlogs   | integer                     | NO       | 0
 drive_type     | character varying(20)       | NO       | 'Full-Time'::character varying
 status         | character varying(20)       | NO       | 'Upcoming'::character varying
 created_at     | timestamp without time zone | NO       | CURRENT_TIMESTAMP
(11 rows)

SELECT conname AS constraint_name,
       CASE contype WHEN 'p' THEN 'PRIMARY KEY' WHEN 'f' THEN 'FOREIGN KEY' WHEN 'u' THEN 'UNIQUE' WHEN 'c' THEN 'CHECK' END AS kind,
       pg_get_constraintdef(oid) AS definition
  FROM pg_constraint
 WHERE conrelid = 'public.drive'::regclass
 ORDER BY contype, conname;
      constraint_name      |    kind     |                                                                                  definition                                                                                   
---------------------------+-------------+-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
 drive_drive_type_check    | CHECK       | CHECK (((drive_type)::text = ANY ((ARRAY['Full-Time'::character varying, 'Internship'::character varying])::text[])))
 drive_max_backlogs_check  | CHECK       | CHECK ((max_backlogs >= 0))
 drive_min_cgpa_check      | CHECK       | CHECK (((min_cgpa >= (0)::numeric) AND (min_cgpa <= (10)::numeric)))
 drive_package_lpa_check   | CHECK       | CHECK ((package_lpa > (0)::numeric))
 drive_status_check        | CHECK       | CHECK (((status)::text = ANY ((ARRAY['Upcoming'::character varying, 'Ongoing'::character varying, 'Completed'::character varying, 'Cancelled'::character varying])::text[])))
 drive_company_id_fkey     | FOREIGN KEY | FOREIGN KEY (company_id) REFERENCES company(company_id)
 drive_coordinator_id_fkey | FOREIGN KEY | FOREIGN KEY (coordinator_id) REFERENCES coordinator(coordinator_id)
 drive_pkey                | PRIMARY KEY | PRIMARY KEY (drive_id)
(8 rows)
```

## `drive_eligible_dept`

Columns (type, nullability, default), then every constraint on `drive_eligible_dept`: PRIMARY KEY, FOREIGN KEY (with its ON DELETE rule), UNIQUE and CHECK.

```text
SELECT column_name, data_type || COALESCE('(' || character_maximum_length || ')', '')
       || COALESCE(CASE WHEN data_type = 'numeric' THEN '(' || numeric_precision || ',' || numeric_scale || ')' END, '') AS type,
       is_nullable AS nullable,
       COALESCE(column_default, CASE WHEN is_identity = 'YES' THEN 'identity' END) AS "default"
  FROM information_schema.columns
 WHERE table_schema = 'public' AND table_name = 'drive_eligible_dept'
 ORDER BY ordinal_position;
 column_name |  type   | nullable | default 
-------------+---------+----------+---------
 drive_id    | integer | NO       | (null)
 dept_id     | integer | NO       | (null)
(2 rows)

SELECT conname AS constraint_name,
       CASE contype WHEN 'p' THEN 'PRIMARY KEY' WHEN 'f' THEN 'FOREIGN KEY' WHEN 'u' THEN 'UNIQUE' WHEN 'c' THEN 'CHECK' END AS kind,
       pg_get_constraintdef(oid) AS definition
  FROM pg_constraint
 WHERE conrelid = 'public.drive_eligible_dept'::regclass
 ORDER BY contype, conname;
          constraint_name          |    kind     |                               definition                               
-----------------------------------+-------------+------------------------------------------------------------------------
 drive_eligible_dept_dept_id_fkey  | FOREIGN KEY | FOREIGN KEY (dept_id) REFERENCES department(dept_id) ON DELETE CASCADE
 drive_eligible_dept_drive_id_fkey | FOREIGN KEY | FOREIGN KEY (drive_id) REFERENCES drive(drive_id) ON DELETE CASCADE
 drive_eligible_dept_pkey          | PRIMARY KEY | PRIMARY KEY (drive_id, dept_id)
(3 rows)
```

## `application`

Columns (type, nullability, default), then every constraint on `application`: PRIMARY KEY, FOREIGN KEY (with its ON DELETE rule), UNIQUE and CHECK.

```text
SELECT column_name, data_type || COALESCE('(' || character_maximum_length || ')', '')
       || COALESCE(CASE WHEN data_type = 'numeric' THEN '(' || numeric_precision || ',' || numeric_scale || ')' END, '') AS type,
       is_nullable AS nullable,
       COALESCE(column_default, CASE WHEN is_identity = 'YES' THEN 'identity' END) AS "default"
  FROM information_schema.columns
 WHERE table_schema = 'public' AND table_name = 'application'
 ORDER BY ordinal_position;
  column_name   |            type             | nullable |           default            
----------------+-----------------------------+----------+------------------------------
 application_id | integer                     | NO       | identity
 student_id     | integer                     | NO       | (null)
 drive_id       | integer                     | NO       | (null)
 applied_at     | timestamp without time zone | NO       | CURRENT_TIMESTAMP
 status         | character varying(30)       | NO       | 'Applied'::character varying
(5 rows)

SELECT conname AS constraint_name,
       CASE contype WHEN 'p' THEN 'PRIMARY KEY' WHEN 'f' THEN 'FOREIGN KEY' WHEN 'u' THEN 'UNIQUE' WHEN 'c' THEN 'CHECK' END AS kind,
       pg_get_constraintdef(oid) AS definition
  FROM pg_constraint
 WHERE conrelid = 'public.application'::regclass
 ORDER BY contype, conname;
           constraint_name           |    kind     |                                                                                                                        definition                                                                                                                         
-------------------------------------+-------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
 application_status_check            | CHECK       | CHECK (((status)::text = ANY ((ARRAY['Applied'::character varying, 'Shortlisted'::character varying, 'Interview_Scheduled'::character varying, 'Rejected'::character varying, 'Selected'::character varying, 'Offer_Made'::character varying])::text[])))
 application_drive_id_fkey           | FOREIGN KEY | FOREIGN KEY (drive_id) REFERENCES drive(drive_id)
 application_student_id_fkey         | FOREIGN KEY | FOREIGN KEY (student_id) REFERENCES student(student_id)
 application_pkey                    | PRIMARY KEY | PRIMARY KEY (application_id)
 application_student_id_drive_id_key | UNIQUE      | UNIQUE (student_id, drive_id)
(5 rows)
```

## `interview_round`

Columns (type, nullability, default), then every constraint on `interview_round`: PRIMARY KEY, FOREIGN KEY (with its ON DELETE rule), UNIQUE and CHECK.

```text
SELECT column_name, data_type || COALESCE('(' || character_maximum_length || ')', '')
       || COALESCE(CASE WHEN data_type = 'numeric' THEN '(' || numeric_precision || ',' || numeric_scale || ')' END, '') AS type,
       is_nullable AS nullable,
       COALESCE(column_default, CASE WHEN is_identity = 'YES' THEN 'identity' END) AS "default"
  FROM information_schema.columns
 WHERE table_schema = 'public' AND table_name = 'interview_round'
 ORDER BY ordinal_position;
  column_name   |          type          | nullable |           default            
----------------+------------------------+----------+------------------------------
 round_id       | integer                | NO       | identity
 application_id | integer                | NO       | (null)
 round_number   | integer                | NO       | (null)
 round_type     | character varying(30)  | NO       | (null)
 round_date     | date                   | YES      | (null)
 result         | character varying(20)  | NO       | 'Pending'::character varying
 remarks        | character varying(500) | YES      | (null)
(7 rows)

SELECT conname AS constraint_name,
       CASE contype WHEN 'p' THEN 'PRIMARY KEY' WHEN 'f' THEN 'FOREIGN KEY' WHEN 'u' THEN 'UNIQUE' WHEN 'c' THEN 'CHECK' END AS kind,
       pg_get_constraintdef(oid) AS definition
  FROM pg_constraint
 WHERE conrelid = 'public.interview_round'::regclass
 ORDER BY contype, conname;
                 constraint_name                 |    kind     |                                                                                                      definition                                                                                                       
-------------------------------------------------+-------------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
 interview_round_result_check                    | CHECK       | CHECK (((result)::text = ANY ((ARRAY['Pass'::character varying, 'Fail'::character varying, 'Pending'::character varying])::text[])))
 interview_round_round_number_check              | CHECK       | CHECK ((round_number > 0))
 interview_round_round_type_check                | CHECK       | CHECK (((round_type)::text = ANY ((ARRAY['Aptitude'::character varying, 'Technical'::character varying, 'HR'::character varying, 'Group_Discussion'::character varying, 'Coding_Test'::character varying])::text[])))
 interview_round_application_id_fkey             | FOREIGN KEY | FOREIGN KEY (application_id) REFERENCES application(application_id) ON DELETE CASCADE
 interview_round_pkey                            | PRIMARY KEY | PRIMARY KEY (round_id)
 interview_round_application_id_round_number_key | UNIQUE      | UNIQUE (application_id, round_number)
(6 rows)
```

## `offer`

Columns (type, nullability, default), then every constraint on `offer`: PRIMARY KEY, FOREIGN KEY (with its ON DELETE rule), UNIQUE and CHECK.

```text
SELECT column_name, data_type || COALESCE('(' || character_maximum_length || ')', '')
       || COALESCE(CASE WHEN data_type = 'numeric' THEN '(' || numeric_precision || ',' || numeric_scale || ')' END, '') AS type,
       is_nullable AS nullable,
       COALESCE(column_default, CASE WHEN is_identity = 'YES' THEN 'identity' END) AS "default"
  FROM information_schema.columns
 WHERE table_schema = 'public' AND table_name = 'offer'
 ORDER BY ordinal_position;
     column_name     |         type          | nullable |           default            
---------------------+-----------------------+----------+------------------------------
 offer_id            | integer               | NO       | identity
 application_id      | integer               | NO       | (null)
 offered_package_lpa | numeric(6,2)          | NO       | (null)
 offer_date          | date                  | NO       | CURRENT_DATE
 status              | character varying(20) | NO       | 'Pending'::character varying
 joining_date        | date                  | YES      | (null)
(6 rows)

SELECT conname AS constraint_name,
       CASE contype WHEN 'p' THEN 'PRIMARY KEY' WHEN 'f' THEN 'FOREIGN KEY' WHEN 'u' THEN 'UNIQUE' WHEN 'c' THEN 'CHECK' END AS kind,
       pg_get_constraintdef(oid) AS definition
  FROM pg_constraint
 WHERE conrelid = 'public.offer'::regclass
 ORDER BY contype, conname;
         constraint_name         |    kind     |                                                                  definition                                                                  
---------------------------------+-------------+----------------------------------------------------------------------------------------------------------------------------------------------
 offer_offered_package_lpa_check | CHECK       | CHECK ((offered_package_lpa > (0)::numeric))
 offer_status_check              | CHECK       | CHECK (((status)::text = ANY ((ARRAY['Pending'::character varying, 'Accepted'::character varying, 'Declined'::character varying])::text[])))
 offer_application_id_fkey       | FOREIGN KEY | FOREIGN KEY (application_id) REFERENCES application(application_id)
 offer_pkey                      | PRIMARY KEY | PRIMARY KEY (offer_id)
 offer_application_id_key        | UNIQUE      | UNIQUE (application_id)
(5 rows)
```

## `offer_history`

Columns (type, nullability, default), then every constraint on `offer_history`: PRIMARY KEY, FOREIGN KEY (with its ON DELETE rule), UNIQUE and CHECK.

```text
SELECT column_name, data_type || COALESCE('(' || character_maximum_length || ')', '')
       || COALESCE(CASE WHEN data_type = 'numeric' THEN '(' || numeric_precision || ',' || numeric_scale || ')' END, '') AS type,
       is_nullable AS nullable,
       COALESCE(column_default, CASE WHEN is_identity = 'YES' THEN 'identity' END) AS "default"
  FROM information_schema.columns
 WHERE table_schema = 'public' AND table_name = 'offer_history'
 ORDER BY ordinal_position;
   column_name    |            type             | nullable |      default      
------------------+-----------------------------+----------+-------------------
 history_id       | integer                     | NO       | identity
 offer_id         | integer                     | NO       | (null)
 action           | character varying(30)       | NO       | (null)
 action_timestamp | timestamp without time zone | NO       | CURRENT_TIMESTAMP
 notes            | character varying(500)      | YES      | (null)
(5 rows)

SELECT conname AS constraint_name,
       CASE contype WHEN 'p' THEN 'PRIMARY KEY' WHEN 'f' THEN 'FOREIGN KEY' WHEN 'u' THEN 'UNIQUE' WHEN 'c' THEN 'CHECK' END AS kind,
       pg_get_constraintdef(oid) AS definition
  FROM pg_constraint
 WHERE conrelid = 'public.offer_history'::regclass
 ORDER BY contype, conname;
       constraint_name       |    kind     |                                                                  definition                                                                  
-----------------------------+-------------+----------------------------------------------------------------------------------------------------------------------------------------------
 offer_history_action_check  | CHECK       | CHECK (((action)::text = ANY ((ARRAY['Created'::character varying, 'Accepted'::character varying, 'Declined'::character varying])::text[])))
 offer_history_offer_id_fkey | FOREIGN KEY | FOREIGN KEY (offer_id) REFERENCES offer(offer_id) ON DELETE CASCADE
 offer_history_pkey          | PRIMARY KEY | PRIMARY KEY (history_id)
(3 rows)
```

## `application_status_history`

Columns (type, nullability, default), then every constraint on `application_status_history`: PRIMARY KEY, FOREIGN KEY (with its ON DELETE rule), UNIQUE and CHECK.

```text
SELECT column_name, data_type || COALESCE('(' || character_maximum_length || ')', '')
       || COALESCE(CASE WHEN data_type = 'numeric' THEN '(' || numeric_precision || ',' || numeric_scale || ')' END, '') AS type,
       is_nullable AS nullable,
       COALESCE(column_default, CASE WHEN is_identity = 'YES' THEN 'identity' END) AS "default"
  FROM information_schema.columns
 WHERE table_schema = 'public' AND table_name = 'application_status_history'
 ORDER BY ordinal_position;
  column_name   |            type             | nullable |      default      
----------------+-----------------------------+----------+-------------------
 history_id     | integer                     | NO       | identity
 application_id | integer                     | NO       | (null)
 old_status     | character varying(30)       | NO       | (null)
 new_status     | character varying(30)       | NO       | (null)
 changed_at     | timestamp without time zone | NO       | CURRENT_TIMESTAMP
(5 rows)

SELECT conname AS constraint_name,
       CASE contype WHEN 'p' THEN 'PRIMARY KEY' WHEN 'f' THEN 'FOREIGN KEY' WHEN 'u' THEN 'UNIQUE' WHEN 'c' THEN 'CHECK' END AS kind,
       pg_get_constraintdef(oid) AS definition
  FROM pg_constraint
 WHERE conrelid = 'public.application_status_history'::regclass
 ORDER BY contype, conname;
                constraint_name                 |    kind     |                                      definition                                       
------------------------------------------------+-------------+---------------------------------------------------------------------------------------
 application_status_history_application_id_fkey | FOREIGN KEY | FOREIGN KEY (application_id) REFERENCES application(application_id) ON DELETE CASCADE
 application_status_history_pkey                | PRIMARY KEY | PRIMARY KEY (history_id)
(2 rows)
```

## Indexes

Every index, including the ones PRIMARY KEY and UNIQUE constraints create. The five purpose-built ones are `idx_student_dept`, `idx_student_cgpa`, `idx_application_status`, `idx_application_drive` and `idx_drive_company` (reasons in `db/schema.sql` Section 2; measured effect in `index-benchmark.md`).

```text
SELECT tablename, indexname, indexdef
  FROM pg_indexes WHERE schemaname = 'public'
 ORDER BY tablename, indexname;
         tablename          |                    indexname                    |                                                                 indexdef                                                                 
----------------------------+-------------------------------------------------+------------------------------------------------------------------------------------------------------------------------------------------
 application                | application_pkey                                | CREATE UNIQUE INDEX application_pkey ON public.application USING btree (application_id)
 application                | application_student_id_drive_id_key             | CREATE UNIQUE INDEX application_student_id_drive_id_key ON public.application USING btree (student_id, drive_id)
 application                | idx_application_drive                           | CREATE INDEX idx_application_drive ON public.application USING btree (drive_id)
 application                | idx_application_status                          | CREATE INDEX idx_application_status ON public.application USING btree (status)
 application_status_history | application_status_history_pkey                 | CREATE UNIQUE INDEX application_status_history_pkey ON public.application_status_history USING btree (history_id)
 application_status_history | idx_status_history_application                  | CREATE INDEX idx_status_history_application ON public.application_status_history USING btree (application_id)
 company                    | company_company_name_key                        | CREATE UNIQUE INDEX company_company_name_key ON public.company USING btree (company_name)
 company                    | company_pkey                                    | CREATE UNIQUE INDEX company_pkey ON public.company USING btree (company_id)
 coordinator                | coordinator_email_key                           | CREATE UNIQUE INDEX coordinator_email_key ON public.coordinator USING btree (email)
 coordinator                | coordinator_pkey                                | CREATE UNIQUE INDEX coordinator_pkey ON public.coordinator USING btree (coordinator_id)
 department                 | department_dept_code_key                        | CREATE UNIQUE INDEX department_dept_code_key ON public.department USING btree (dept_code)
 department                 | department_dept_name_key                        | CREATE UNIQUE INDEX department_dept_name_key ON public.department USING btree (dept_name)
 department                 | department_pkey                                 | CREATE UNIQUE INDEX department_pkey ON public.department USING btree (dept_id)
 drive                      | drive_pkey                                      | CREATE UNIQUE INDEX drive_pkey ON public.drive USING btree (drive_id)
 drive                      | idx_drive_company                               | CREATE INDEX idx_drive_company ON public.drive USING btree (company_id)
 drive_eligible_dept        | drive_eligible_dept_pkey                        | CREATE UNIQUE INDEX drive_eligible_dept_pkey ON public.drive_eligible_dept USING btree (drive_id, dept_id)
 interview_round            | interview_round_application_id_round_number_key | CREATE UNIQUE INDEX interview_round_application_id_round_number_key ON public.interview_round USING btree (application_id, round_number)
 interview_round            | interview_round_pkey                            | CREATE UNIQUE INDEX interview_round_pkey ON public.interview_round USING btree (round_id)
 mv_company_dept_placements | idx_mv_company_dept                             | CREATE UNIQUE INDEX idx_mv_company_dept ON public.mv_company_dept_placements USING btree (company_id, dept_id)
 offer                      | offer_application_id_key                        | CREATE UNIQUE INDEX offer_application_id_key ON public.offer USING btree (application_id)
 offer                      | offer_pkey                                      | CREATE UNIQUE INDEX offer_pkey ON public.offer USING btree (offer_id)
 offer_history              | offer_history_pkey                              | CREATE UNIQUE INDEX offer_history_pkey ON public.offer_history USING btree (history_id)
 skill                      | skill_pkey                                      | CREATE UNIQUE INDEX skill_pkey ON public.skill USING btree (skill_id)
 skill                      | skill_skill_name_key                            | CREATE UNIQUE INDEX skill_skill_name_key ON public.skill USING btree (skill_name)
 student                    | idx_student_cgpa                                | CREATE INDEX idx_student_cgpa ON public.student USING btree (cgpa)
 student                    | idx_student_dept                                | CREATE INDEX idx_student_dept ON public.student USING btree (dept_id)
 student                    | student_email_key                               | CREATE UNIQUE INDEX student_email_key ON public.student USING btree (email)
 student                    | student_pkey                                    | CREATE UNIQUE INDEX student_pkey ON public.student USING btree (student_id)
 student                    | student_reg_no_key                              | CREATE UNIQUE INDEX student_reg_no_key ON public.student USING btree (reg_no)
 student_skill              | student_skill_pkey                              | CREATE UNIQUE INDEX student_skill_pkey ON public.student_skill USING btree (student_id, skill_id)
(30 rows)
```

## Triggers, functions, procedure and views

Every trigger with its timing and event, then every routine and view in the schema.

```text
SELECT tgrelid::regclass AS on_table, tgname AS trigger_name,
       CASE WHEN tgtype & 2 = 2 THEN 'BEFORE' ELSE 'AFTER' END AS timing,
       concat_ws(' OR ', CASE WHEN tgtype & 4 = 4 THEN 'INSERT' END, CASE WHEN tgtype & 16 = 16 THEN 'UPDATE' END) AS event,
       p.proname AS calls_function
  FROM pg_trigger tg JOIN pg_proc p ON p.oid = tg.tgfoid
 WHERE NOT tgisinternal ORDER BY 1, 2;
  on_table   |           trigger_name            | timing |      event       |            calls_function            
-------------+-----------------------------------+--------+------------------+--------------------------------------
 application | trg_application_before_insert     | BEFORE | INSERT           | trg_fn_application_guard
 application | trg_application_status_audit      | AFTER  | UPDATE           | trg_fn_application_status_audit
 application | trg_application_status_transition | BEFORE | UPDATE           | trg_fn_application_status_transition
 offer       | trg_offer_after_insert            | AFTER  | INSERT           | trg_fn_offer_insert_update_placement
 offer       | trg_offer_before_accept           | BEFORE | INSERT OR UPDATE | trg_fn_offer_single_acceptance
 offer       | trg_offer_requires_selected       | BEFORE | INSERT           | trg_fn_offer_requires_selected
(6 rows)

SELECT p.proname AS name,
       CASE p.prokind WHEN 'f' THEN 'FUNCTION' WHEN 'p' THEN 'PROCEDURE' END AS kind,
       pg_get_function_identity_arguments(p.oid) AS arguments,
       CASE WHEN p.prokind = 'f' THEN pg_get_function_result(p.oid) END AS returns
  FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
 WHERE n.nspname = 'public' ORDER BY kind, name;
                 name                 |   kind    |                       arguments                       |   returns   
--------------------------------------+-----------+-------------------------------------------------------+-------------
 fn_check_eligibility                 | FUNCTION  | p_student_id integer, p_drive_id integer              | boolean
 fn_get_eligible_drives               | FUNCTION  | p_student_id integer                                  | SETOF drive
 trg_fn_application_guard             | FUNCTION  |                                                       | trigger
 trg_fn_application_status_audit      | FUNCTION  |                                                       | trigger
 trg_fn_application_status_transition | FUNCTION  |                                                       | trigger
 trg_fn_offer_insert_update_placement | FUNCTION  |                                                       | trigger
 trg_fn_offer_requires_selected       | FUNCTION  |                                                       | trigger
 trg_fn_offer_single_acceptance       | FUNCTION  |                                                       | trigger
 sp_close_drive                       | PROCEDURE | IN p_drive_id integer, INOUT p_rejected_count integer | (null)
(9 rows)

SELECT table_name AS view_name, 'VIEW' AS kind FROM information_schema.views WHERE table_schema = 'public'
UNION ALL
SELECT matviewname, 'MATERIALIZED VIEW' FROM pg_matviews WHERE schemaname = 'public'
ORDER BY kind, view_name;
         view_name          |       kind        
----------------------------+-------------------
 mv_company_dept_placements | MATERIALIZED VIEW
 company_wise_stats_view    | VIEW
 department_stats_view      | VIEW
 dept_offer_ranking_view    | VIEW
 placed_students_view       | VIEW
 placement_timeline_view    | VIEW
 student_cgpa_standing_view | VIEW
(7 rows)
```
