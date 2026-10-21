-- =============================================================================
-- Creates a clean, dedicated Oracle schema (user PLACEIQ) for the project.
-- Run as SYSTEM in SQL*Plus:   @db/oracle_setup.sql
--
-- In Oracle a "schema" is a user: dropping and recreating PLACEIQ gives a
-- completely empty schema every time, so schema_oracle.sql always runs
-- against a clean slate and never collides with SYSTEM's own objects.
--
-- The password is a local-development placeholder for a lab/XE instance;
-- change it on any shared database.
-- =============================================================================

-- Drop the user if it already exists (ORA-01918 = "user does not exist").
BEGIN
    EXECUTE IMMEDIATE 'DROP USER placeiq CASCADE';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -1918 THEN
            RAISE;
        END IF;
END;
/

CREATE USER placeiq IDENTIFIED BY "PlaceIQ_dev_2026";

-- Only the privileges the schema actually needs (least privilege): no DBA,
-- no ANY-privileges, just the right to create its own objects.
GRANT CREATE SESSION,
      CREATE TABLE,
      CREATE VIEW,
      CREATE SEQUENCE,
      CREATE TRIGGER,
      CREATE PROCEDURE,
      CREATE MATERIALIZED VIEW
   TO placeiq;

ALTER USER placeiq QUOTA UNLIMITED ON users;
