# Oracle Port: Every Difference from `db/schema.sql`, and Why

`db/schema_oracle.sql` is the Oracle/SQL*Plus version of `db/schema.sql`
(PostgreSQL). This document explains, in plain language, every place the two
files differ, so you can answer "why does the Oracle version look different
here?". It also says, for each item, whether it was actually run on Oracle or
only reasoned through.

`db/schema.sql` stays the PostgreSQL file the live app runs on. The Oracle
port is a separate deliverable for the report and the SQL*Plus demo.

## Files

| File | Run as | Purpose |
|---|---|---|
| `db/oracle_setup.sql` | SYSTEM | Drops and recreates the `PLACEIQ` user, so every run starts from an empty schema |
| `db/schema_oracle.sql` | PLACEIQ | All DDL: 13 tables, 11 sequences, 17 triggers, 2 functions, 1 procedure, 6 views, 1 materialized view |
| `db/seed_oracle_demo.sql` | PLACEIQ | Small synthetic dataset (9 students, 4 drives) chosen so each demo case is readable |
| `db/sqlplus_demo.sql` | PLACEIQ | The live viva demo; rolls itself back, so it can be re-run |
| `db/oracle_full_run.sql` | (connects itself) | All four in one session: `sqlplus /nolog @db/oracle_full_run.sql` |

## Verification summary

Everything was run on **Oracle Database 21c Express Edition** (Docker image
`gvenzl/oracle-xe:21-slim`) through SQL*Plus. The unedited session output is
in [`docs/evidence/sqlplus-transcript.txt`](evidence/sqlplus-transcript.txt),
plus a short follow-up session in
[`docs/evidence/raw/oracle-extra-checks.txt`](evidence/raw/oracle-extra-checks.txt).

- All **82 objects in `USER_OBJECTS`** have **status VALID** (2 functions, 30 indexes, 1 materialized view, 1 procedure, 11 sequences, 14 tables, 17 triggers, 6 views), and `USER_ERRORS` returned no rows. There are 14 tables because the materialized view stores its data in a table of the same name, and 30 indexes because PK and UNIQUE constraints create their own.
- The demo dataset loaded without errors: 9 students, 4 drives, 11 applications, 2 offers, and 17 status changes logged by the audit trigger.
- The demo produced **exactly six errors, all intended**: `-20001`, `-20002`, `-20006`, `-20007`, `-20003`, `-20005`. There were no `SP2-` or unexpected `ORA-` errors.

| Status | Meaning |
|---|---|
| ✅ Verified | Executed on Oracle 21c and the output checked |
| 🟡 Unverified | Written to Oracle's documented behaviour but not demonstrated (reason given) |

---

## 1. Data types (Section 1)

| Postgres | Oracle | Why | |
|---|---|---|---|
| `INTEGER GENERATED ALWAYS AS IDENTITY` | `NUMBER` + `SEQUENCE` + `BEFORE INSERT` trigger | IDENTITY columns only exist from Oracle 12c; the sequence-plus-trigger pattern works on every version, so it doesn't gamble on the lab's Oracle version. The trigger's `WHEN (NEW.id IS NULL)` only fills the id if the caller didn't supply one. | ✅ |
| `VARCHAR(n)` | `VARCHAR2(n)` | Oracle reserves plain `VARCHAR` for possible future redefinition and tells you to use `VARCHAR2`. | ✅ |
| `NUMERIC(p,s)`, `INTEGER` | `NUMBER(p,s)`, `NUMBER` | `NUMBER` is Oracle's native numeric type (it accepts the ANSI names as synonyms, but `NUMBER` is idiomatic). | ✅ |
| `TIMESTAMP` | `TIMESTAMP` | Same in both. | ✅ |
| `DATE` | `DATE` | Same keyword, **different meaning**: an Oracle `DATE` always carries a time of day (it is really date + time). Every `DATE` column here stores midnight. Nothing in this schema compares times of day, so behaviour is unchanged, but it's a real difference worth naming. | ✅ |
| `TEXT`, `BOOLEAN` columns | not used | Neither appears in `schema.sql`: free text uses bounded `VARCHAR`, and true/false states use `VARCHAR` + `CHECK (... IN (...))`. That was chosen so the port wouldn't need to change them (Oracle has no `BOOLEAN` column type before 23c). | ✅ |

## 2. Indexes (Section 2)

Identical syntax and identical reasoning. ✅

## 3. Placement-status trigger (Section 3)

| Postgres | Oracle | |
|---|---|---|
| A trigger **function** plus a `CREATE TRIGGER ... EXECUTE FUNCTION` that calls it (two objects) | One self-contained `CREATE OR REPLACE TRIGGER ... BEGIN ... END;` | ✅ |
| Row values are `NEW.col` | `:NEW.col` in the body (but `NEW.col`, no colon, in a `WHEN` clause) | ✅ |
| Skips offers inserted as Declined with `IF NEW.status = 'Declined' THEN RETURN NEW` | The same guard as a `WHEN (NEW.status <> 'Declined')` clause, so the body doesn't even run | ✅ |
| `$$ ... $$ LANGUAGE plpgsql` | No delimiters; SQL*Plus needs a `/` on its own line after every PL/SQL block | ✅ |

**Verified:** in demo section 3, Meera went from Not Placed to Placed with no `UPDATE` on `student` by us.

> "In Postgres a trigger calls a named function; in Oracle the trigger body *is* the code. Same rule, one object instead of two."

## 4. Stored functions (Section 4)

**`fn_check_eligibility`** ✅. The demo returns Aisha 1, Arjun 0 (CGPA/backlogs), Meera 0 (branch), and 0 for a missing id.
- **Return type:** Postgres returns `BOOLEAN` and is called from SQL. Oracle SQL can't use a `BOOLEAN` before 23c, so the Oracle version returns `NUMBER` (1 = eligible, 0 = not).
- **"Row not found":** PL/pgSQL's `SELECT INTO` on zero rows sets a `FOUND` flag you check afterwards. Oracle's `SELECT INTO` **raises `NO_DATA_FOUND`** instead, so the Oracle function has an `EXCEPTION WHEN NO_DATA_FOUND THEN RETURN 0` handler. This is a genuine control-flow difference, not a syntax one.
- **`%TYPE`:** parameters and variables are declared as e.g. `student.cgpa%TYPE`, so they always match the column's type.

**`fn_get_eligible_drives`** ✅. The demo returns exactly Meera's 2 eligible drives.
- Postgres returns `SETOF drive`, a function you can `SELECT * FROM` like a table. Oracle has no direct equivalent without declaring object types and a `PIPELINED` function, so it returns a **`SYS_REFCURSOR`**.
- That's a different calling convention: in SQL*Plus it's `VARIABLE rc REFCURSOR`, then `EXEC :rc := fn_get_eligible_drives(id)`, then `PRINT rc`.
- **Gotcha:** you can't pass an inline subquery as the argument in that `EXEC`. That fails with `PLS-00103`, so look the id up first; the demo uses SQL*Plus `NEW_VALUE` variables for this.

## 5. Views (Section 5)

Copied unchanged. They use only ANSI SQL (`JOIN`, `GROUP BY`, `COUNT`, `AVG`, `MAX`, `MIN`, `ROUND`, `NULLIF`, `CASE`), with no Postgres-only functions such as `NOW()` or `ILIKE`. (`||` concatenation is the same in both anyway.) ✅ The demo queries `department_stats_view` and `company_wise_stats_view`.

## 6. Business-rule triggers (Section 6)

| Rule | Postgres | Oracle | |
|---|---|---|---|
| How a rule aborts the write | `RAISE EXCEPTION ... USING ERRCODE = 'PL00x'` (custom SQLSTATE) | `RAISE_APPLICATION_ERROR(-2000x, 'message')` (Oracle's user-defined range is −20000 to −20999). The last digit matches: PL001 ↔ −20001, and so on. | ✅ |
| Not eligible / drive closed (`trg_application_before_insert`) | Row trigger; `IF NOT FOUND` for a missing drive | Row trigger; `EXCEPTION WHEN NO_DATA_FOUND THEN NULL` for a missing drive | ✅ −20001 and −20002 in the demo |
| One accepted offer per student (`trg_offer_before_accept`) | Plain row trigger reading `offer` | **COMPOUND trigger** (explained below) | ✅ −20003 in the demo |
| Offer only on a Selected application (`trg_offer_requires_selected`) | Row trigger | Row trigger (it reads `application`, not `offer`, so it's fine) | ✅ −20006 in the demo |
| Status only moves forward (`trg_application_status_transition`) | Row trigger with a `CASE` | Same `CASE` (PL/SQL has `BOOLEAN` even though Oracle SQL doesn't). **Renamed `trg_app_status_transition`**, since Oracle 11g caps names at 30 characters. | ✅ −20007 in the demo; legal moves verified by the seed and the extra checks |

**Why a compound trigger, the biggest structural difference in the port.** The one-accepted-offer rule has to *count Accepted rows in `offer`*, but it fires *on `offer`*.

- **Oracle:** a normal row-level trigger that reads its own table during an `UPDATE` fails with **ORA-04091 "table is mutating"**, because the table is half-way through changing. A compound trigger splits the work:
  - its `AFTER EACH ROW` part only records which accepted rows the statement touched;
  - its `AFTER STATEMENT` part runs once the statement has finished and the table is consistent. That's where it locks the student row and counts.
- **Postgres:** has no such restriction, so its version stays a simple row trigger.
- **Behaviour on failure:** when the rule fails, Oracle rolls back that one statement but keeps the transaction open. The demo shows this: the offer is still Pending afterwards, and earlier work in the same transaction survives.
- **Version:** compound triggers need **Oracle 11g or later**, so the port's minimum version is 11g, not 9i as the older version of this doc said.

> "Oracle won't let a row trigger read the table it's changing, so the check moves to the end of the statement using a compound trigger."

🟡 **Unverified on Oracle: concurrent accepts.** Both versions lock the student row (`SELECT ... FOR UPDATE`) so that two *simultaneous* accepts for the same student are serialized. On **PostgreSQL this is verified**: `docs/evidence/transaction.md` scenario 4 runs two real connections, and the second one waits on the lock, then is refused with PL003. The Oracle demo runs in one SQL*Plus session, so it cannot show two transactions racing; on Oracle the claim rests on its documented locking behaviour.

## 7. Audit trigger (Section 7)

Same design: `application_status_history` plus an `AFTER UPDATE OF status` row trigger with `WHEN (OLD.status <> NEW.status)`. Oracle adds a sequence and a `BEFORE INSERT` id trigger, named `trg_app_status_history_bi` to stay under 30 characters. ✅ The demo prints Meera's three-step history, and every status move in the seed was logged (17 rows).

## 8. Stored procedure `sp_close_drive` (Section 8)

| Postgres | Oracle | |
|---|---|---|
| `INOUT p_rejected_count`, called with `CALL sp_close_drive(5, NULL)` | `OUT p_rejected_count`, called with `VARIABLE n NUMBER`, then `EXEC sp_close_drive(5, :n)`, then `PRINT n` | ✅ demo printed `2` |
| `GET DIAGNOSTICS ... = ROW_COUNT` | `SQL%ROWCOUNT` | ✅ |
| Drive not found: `IF NOT FOUND` → PL004 | `EXCEPTION WHEN NO_DATA_FOUND` → −20004 | ✅ (extra-checks session) |
| Already closed → PL005 | −20005 | ✅ demo |

Neither version COMMITs inside the procedure, so the caller can roll the close back; the demo relies on this.

## 9. Window-function views (Section 9)

`RANK`, `DENSE_RANK`, `PERCENT_RANK`, `LAG` and `SUM(...) OVER` behave the same. Two changes, both in `placement_timeline_view`. The month bucket: Postgres `date_trunc('month', offer_date)::DATE` becomes Oracle `TRUNC(offer_date, 'MM')`. The list of every month between the first and last offer (so an empty month is a 0 row and `LAG` compares consecutive months): Postgres `generate_series(first, last, INTERVAL '1 month')` becomes Oracle `ADD_MONTHS(first, LEVEL - 1) ... CONNECT BY LEVEL <= MONTHS_BETWEEN(last, first) + 1`. Demo step 6e moves one offer to February inside a savepoint and shows January as a 0 row. ✅ The demo queries `dept_offer_ranking_view` and `placement_timeline_view`; `student_cgpa_standing_view` was checked in the extra session (each department's percentiles come out 100 / 50 / 0).

## 10. Materialized view (Section 10)

| Postgres | Oracle | |
|---|---|---|
| `CREATE MATERIALIZED VIEW ... AS` (filled at creation) | `BUILD IMMEDIATE REFRESH COMPLETE ON DEMAND` states the policy in the definition | ✅ |
| `REFRESH MATERIALIZED VIEW CONCURRENTLY mv` | `EXEC DBMS_MVIEW.REFRESH('MV_COMPANY_DEPT_PLACEMENTS', 'C')` | ✅ demo |
| `CURRENT_TIMESTAMP AS refreshed_at` | `SYSTIMESTAMP AS refreshed_at` | ✅ the timestamp advanced on refresh |

**Not ported:** the `CONCURRENTLY` keyword itself.
- **Postgres:** `CONCURRENTLY` exists so readers aren't locked out during a refresh.
- **Oracle:** its complete refresh is atomic by default, so readers keep seeing the old rows until the refresh commits. The goal is met without a keyword.
- **Side effect to remember:** `DBMS_MVIEW.REFRESH` **commits**. That's why the demo refreshes only after rolling everything else back.

## 11. Things that don't port, or were changed on purpose

| Item | What happened |
|---|---|
| `CONCURRENTLY` refresh | No Oracle keyword; atomic refresh gives the equivalent reader behaviour (§10) |
| Two object names | `trg_application_status_transition` → `trg_app_status_transition`, and the history-id trigger → `trg_app_status_history_bi` (30-character limit in 11g) |
| Minimum version | 11g (compound trigger), was 9i |
| Backend error mapping | `backend/utils/db_errors.py` maps the **Postgres** codes PL001–PL007. An Oracle-backed backend would map −20001 to −20007 instead; not built, since the app runs on Postgres |
| Python seed (`db/seed.py`) | Postgres-only (psycopg2). Oracle gets the small hand-written `seed_oracle_demo.sql` instead |

Out of scope, but worth knowing if the whole app were ever moved to Oracle:
- `backend/services/offer_service.py` uses Postgres's `offer_date + INTERVAL '60 days'`. Oracle's equivalent is `offer_date + 60`.
- The backend talks to the database through psycopg2. Oracle would need `python-oracledb`.
