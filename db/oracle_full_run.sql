-- =============================================================================
-- One complete SQL*Plus session: clean schema -> DDL -> demo data -> demo.
-- Run from the repo root (so the @db/... paths resolve):
--     sqlplus /nolog @db/oracle_full_run.sql
--
-- Connection strings assume a local Oracle XE (gvenzl/oracle-xe image) with
-- the PDB XEPDB1 on port 1521; the passwords are local-dev placeholders —
-- edit them for your lab machine. docs/evidence/sqlplus-transcript.txt is the
-- unedited output of this file.
-- =============================================================================
SET ECHO ON
CONNECT system/OraclePass123@//localhost:1521/XEPDB1
@db/oracle_setup.sql

CONNECT placeiq/PlaceIQ_dev_2026@//localhost:1521/XEPDB1
@db/schema_oracle.sql

-- Every object should be VALID, and USER_ERRORS should return no rows.
SET ECHO ON
COLUMN object_type FORMAT A20
SELECT object_type, status, COUNT(*) AS objects
  FROM user_objects
 WHERE object_type IN ('TABLE', 'VIEW', 'MATERIALIZED VIEW', 'TRIGGER',
                       'FUNCTION', 'PROCEDURE', 'SEQUENCE', 'INDEX')
 GROUP BY object_type, status
 ORDER BY object_type;
SELECT name, type, line, text FROM user_errors;

@db/seed_oracle_demo.sql
@db/sqlplus_demo.sql

EXIT
