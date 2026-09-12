# Oracle Port — Every Difference from db/schema.sql, and Why

`db/schema_oracle.sql` is a full port of `db/schema.sql` (PostgreSQL) to
Oracle/SQL*Plus. This document is the plain-language explanation of every
place the two files diverge, so you can explain any of it if your professor
asks "why does the Oracle version look different here?" — and so you know
exactly which parts are tested-and-confirmed versus reasoned-through-but-
not-run-on-real-Oracle.

**Do not edit `db/schema.sql`** — it stays PostgreSQL-only and is what the
live app actually runs against. `schema_oracle.sql` is a separate,
standalone deliverable for the report/demo.

---

## Verification status (read this first)

| Status | What it means |
|---|---|
| ✅ Verified | Actually run against a real Oracle instance in this session (Docker, `gvenzl/oracle-xe:21-slim`, Oracle Database 21c XE) — see the note at the bottom of this file for the exact outcome. |
| 🟡 Best-effort / unverified | Written to Oracle's documented syntax and semantics, reasoned through carefully, but not executed against a real Oracle database. Check these manually if you hit an issue. |

**Bottom line up front: `schema_oracle.sql` was run start-to-finish against a real Oracle 21c instance in this session — every object (12 tables, 10 sequences, 11 triggers, 2 functions, 3 views, 5 indexes) created with zero errors — and every piece of custom logic (auto-increment, the placement_status trigger, both eligibility functions) was then smoke-tested with real data and confirmed to behave correctly. Full transcript summarized in the last section of this file. Only two minor items (below) remain unverified because they don't affect correctness either way.**

---

## 1. Data types

| Postgres | Oracle | Why |
|---|---|---|
| `INTEGER GENERATED ALWAYS AS IDENTITY` | `NUMBER` + `SEQUENCE` + `BEFORE INSERT TRIGGER` | `GENERATED ALWAYS AS IDENTITY` only exists from Oracle 12c onward. The sequence+trigger pattern works on every Oracle version back to the 1990s, so it was chosen to not gamble on which Oracle version the lab machine actually has. **If you know for certain your Oracle is 12c+**, you can simplify any table to `dept_id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY` and delete that table's sequence + trigger — behaviorally identical, less code. |
| `VARCHAR(n)` | `VARCHAR2(n)` | Oracle's plain `VARCHAR` is a reserved-but-deprecated type Oracle explicitly says not to use (it's reserved for a possible future redefinition with different semantics). `VARCHAR2` is the type Oracle actually wants you to use, and is what every Oracle textbook/course uses. |
| `NUMERIC(p,s)` | `NUMBER(p,s)` | Both engines' native precision/scale numeric type. Postgres calls it `NUMERIC`; Oracle calls it `NUMBER`. (Oracle does accept `NUMERIC` as an ANSI-compatibility synonym for `NUMBER`, but `NUMBER` is the idiomatic spelling everyone expects in an Oracle script.) |
| plain `INTEGER` (backlogs, batch_year, round_number, ...) | `NUMBER` | Same reasoning — `NUMBER` (no precision/scale) is Oracle's native general-purpose numeric type; `INTEGER` is only an ANSI synonym Oracle maps onto `NUMBER(38)` internally, so using `NUMBER` directly is more idiomatic. |
| `TIMESTAMP` | `TIMESTAMP` | No change — identical ANSI type in both engines. |
| `DATE` | `DATE` (🟡 semantic note) | Same keyword, but **not quite the same type**: Postgres's `DATE` is genuinely date-only (no time component at all). Oracle's `DATE` always includes a time-of-day down to the second — it's really a date+time type that Oracle happens to call `DATE`. Every `DATE` column here (`drive_date`, `offer_date`, `joining_date`, `round_date`) will silently store `00:00:00` as the time portion when inserted from a date literal. This changes nothing functionally in this schema (nothing compares time-of-day), but it's a genuine engine difference worth being able to name if asked. |
| `TEXT`, `BOOLEAN` | *(not used)* | Neither appears anywhere in `db/schema.sql` in the first place — both are Postgres-only for table columns (Oracle's `BOOLEAN` only became usable in table columns in Oracle 23c), so there was nothing to convert here. Every free-text column (`remarks`, `notes`) already used a bounded `VARCHAR(500)`/`VARCHAR2(500)` instead of `TEXT`, and every true/false fact (`placement_status`, offer/application statuses) was already modeled as a `VARCHAR` + `CHECK (... IN (...))` "enum" instead of `BOOLEAN` — specifically so this port wouldn't need to touch them. |

## 2. The `placement_status` trigger (Section 3)

✅ Verified — see bottom of file.

| Postgres | Oracle |
|---|---|
| A standalone `CREATE FUNCTION trg_fn_offer_insert_update_placement() RETURNS TRIGGER AS $$ ... $$ LANGUAGE plpgsql;`, then `CREATE TRIGGER ... EXECUTE FUNCTION trg_fn_offer_insert_update_placement();` — **two objects**, the trigger just points at the function. | `CREATE OR REPLACE TRIGGER trg_offer_after_insert AFTER INSERT ON offer FOR EACH ROW BEGIN ... END;` — **one object**. Oracle triggers are self-contained PL/SQL blocks; there's no separate reusable "trigger function" concept like Postgres has. |
| Row values referenced as bare `NEW.application_id`. | Row values referenced as `:NEW.application_id` — the leading colon is required in the trigger body (note: **not** in a trigger's `WHEN` clause, where it's written without the colon — see the `WHEN (NEW.dept_id IS NULL)` guards on the auto-increment triggers in Section 1 for that contrast). |
| Body wrapped in `$$ ... $$` with `LANGUAGE plpgsql` declared. | No `$$`, no `LANGUAGE` clause — just `BEGIN ... END;`, followed by a `/` on its own line so SQL*Plus knows the block is finished. |

**What I'd say out loud:** "In Postgres a trigger just calls a named function; in Oracle the trigger body *is* the function, written inline — so the Oracle version is actually simpler, one object instead of two, just with `:NEW` instead of `NEW`."

## 3. `fn_check_eligibility()` (Section 4)

✅ Verified — including the NO_DATA_FOUND branch specifically. See bottom of file for the actual test data and results.

This is the biggest real rewrite in the whole port — not just syntax, but different control flow:

- **Return type**: Postgres returns `BOOLEAN` and is called straight from SQL (`SELECT fn_check_eligibility(%s, %s)` — see `backend/routes/applications.py` and `db/seed.py`). Oracle's `BOOLEAN` type cannot appear in a SQL statement (only inside PL/SQL) before Oracle 23c — you cannot write `SELECT fn_check_eligibility(...)` against a function that returns `BOOLEAN` in older Oracle. So the Oracle version returns `NUMBER` instead: `1` = eligible, `0` = not eligible. This is the standard workaround every Oracle course teaches for "I need a boolean-ish function I can call from SQL."
- **"Row not found" handling — this is the real semantic difference**: PL/pgSQL's `SELECT ... INTO` on zero matching rows just leaves the target variables `NULL` and sets an implicit `FOUND` flag to false, which the Postgres version checks explicitly (`IF NOT FOUND THEN RETURN FALSE; END IF;`, twice — once after the student lookup, once after the drive lookup). **Oracle's `SELECT ... INTO` does something completely different on zero rows: it raises the `NO_DATA_FOUND` exception immediately**, unwinding execution to the nearest `EXCEPTION` handler. There is no flag to check — the failure interrupts control flow instead. So the Oracle version has one `EXCEPTION WHEN NO_DATA_FOUND THEN RETURN 0;` block at the end instead of two inline `IF NOT FOUND` checks — whichever `SELECT INTO` fails first (student lookup or drive lookup), control jumps straight there and the function returns 0, which is the same end result as the Postgres version's two separate checks, just reached via exception propagation instead of a polled flag.
- **`%TYPE` anchoring**: parameters and local variables are declared as e.g. `student.cgpa%TYPE` instead of a hardcoded `NUMERIC(4,2)`/`NUMBER(4,2)`. This is idiomatic Oracle PL/SQL with no real Postgres equivalent used in this schema — if `student.cgpa`'s precision ever changed, this function's variable would automatically follow it instead of silently becoming out of sync.

**What I'd say out loud:** "The logic is identical, but Oracle's `SELECT INTO` throws an exception instead of Postgres's silent not-found flag, so I had to wrap the lookups in an exception handler instead of checking a flag after each one."

## 4. `fn_get_eligible_drives()` (Section 4)

✅ Verified — including the exact `SYS_REFCURSOR` invocation shown below. See bottom of file for the real transcript.

Postgres's version is `RETURNS SETOF drive ... LANGUAGE sql` — an *inline table function* you can query exactly like a table: `SELECT * FROM fn_get_eligible_drives(1)`. Oracle has no direct equivalent for "call a function and treat its result like a table" without extra ceremony:

- **The "correct" heavyweight Oracle way**: define a SQL object type matching every `drive` column (`CREATE TYPE drive_obj AS OBJECT (...)`), a table-of-that-type type (`CREATE TYPE drive_tab AS TABLE OF drive_obj`), and a `PIPELINED` function that `PIPE ROW`s results — genuinely queryable with `SELECT * FROM TABLE(fn_get_eligible_drives(1))`, but roughly triples the code for one function.
- **What's actually in `schema_oracle.sql`**: a function that `RETURN`s a `SYS_REFCURSOR` — the standard, much simpler Oracle idiom for "a function that hands back a set of rows," and what most Oracle/PL-SQL courses teach first. The tradeoff: it's a genuinely different **calling convention**, not just different syntax — you can't `FROM` it like a table. Confirmed working in SQL*Plus like this:
  ```sql
  VARIABLE rc REFCURSOR
  DECLARE
    v_student_id NUMBER;
  BEGIN
    SELECT student_id INTO v_student_id FROM student WHERE reg_no = 'CSE001';
    :rc := fn_get_eligible_drives(v_student_id);
  END;
  /
  PRINT rc
  ```
  **One genuine gotcha found while testing this**: you cannot pass a bare subquery directly as the function's argument in a one-line `EXEC` (`:rc := fn_get_eligible_drives((SELECT student_id FROM student WHERE reg_no = 'CSE001'));` fails with `PLS-00103` — PL/SQL's procedural statement syntax doesn't allow an inline scalar subquery as a plain expression the way a SQL statement would). The fix is what's shown above: `SELECT ... INTO` a local variable first, then pass the variable. This is a PL/SQL calling-convention quirk on the caller's side, not a bug in the function itself.

  From PL/SQL you'd `OPEN`/`FETCH`/`CLOSE` it, or pass it back out through another `SYS_REFCURSOR` out-parameter. (If this were ever wired into the live Python backend against Oracle instead of Postgres, `python-oracledb` fetches a `SYS_REFCURSOR` result via `cursor.callfunc(...)` returning a cursor object you iterate — a real code change on the backend side, not just the DB side, if the whole app were ever ported rather than just this schema file.)

**What I'd say out loud:** "Postgres let me treat a function like a table; Oracle doesn't do that without defining matching object types, so I used a REF CURSOR instead — the standard, simpler Oracle pattern for a function that returns a result set, at the cost of a different calling convention."

## 5. Views (Section 5)

✅ No changes at all — copied verbatim from `db/schema.sql`.

Checked every one of the three views (`placed_students_view`, `company_wise_stats_view`, `department_stats_view`) line by line for Postgres-only functions — specifically looked for `NOW()`, `ILIKE`, `||` string concatenation, and anything Postgres-flavored. Found none. Everything used — `JOIN`, `LEFT JOIN`, `GROUP BY`, `COUNT`, `COUNT(DISTINCT ...)`, `AVG`, `MAX`, `MIN`, `ROUND`, `NULLIF`, `CASE WHEN ... THEN ... END` — is ANSI SQL and behaves identically in Oracle. This is the one section of the whole port with zero risk.

(Note: `||` for string concatenation and `NOW()`/`CURRENT_TIMESTAMP` don't happen to appear in `db/schema.sql` at all, so there was nothing to convert even if they had shown up — but if you're asked "what about `||`?" in a viva: Oracle uses the exact same `||` operator Postgres does, so that one specifically would have needed no change either way.)

## 6. Sequences / auto-increment

Covered in detail in Section 1 of the table above. Summary: every surrogate-key table (all of them except the two pure junction tables, `student_skill` and `drive_eligible_dept`, which use composite primary keys and need no surrogate key at all) gets its own `CREATE SEQUENCE <table>_seq` plus a `BEFORE INSERT ... FOR EACH ROW WHEN (NEW.<col> IS NULL)` trigger that pulls `<table>_seq.NEXTVAL` into the new row's id column only if the caller didn't already supply one.

## 7. Reserved words / identifier length

✅ Verified — `CREATE TABLE coordinator (... role VARCHAR2(20) ...)` and `CREATE TABLE offer_history (... action VARCHAR2(30) ...)` both ran with zero errors against real Oracle 21c, confirming neither `role` nor `action` needed quoting. Identifier lengths were also fine in practice (expected — see reasoning below, all well under even the old 30-byte limit).

- **Identifier lengths**: every table, column, index, sequence, and trigger name in this schema is well under Oracle's identifier length limit (30 bytes on Oracle 11g and earlier, 128 bytes from 12.2 onward) — the longest names here (`idx_application_status`, `department_stats_view`, `trg_interview_round_bi`) are all in the low 20s.
- **`role` (coordinator.role) and `action` (offer_history.action)** as column names: confirmed unreserved by the live test run above.

## 8. What's out of scope here

This document covers `db/schema.sql` only, as asked. Two things worth knowing if the *whole app* (not just the schema) were ever pointed at Oracle instead of Postgres, though neither affects this deliverable:

- `backend/services/offer_service.py` uses Postgres's `INTERVAL '60 days'` syntax in one `UPDATE` statement (`offer_date + INTERVAL '60 days'`) — Oracle's equivalent is `offer_date + 60` (Oracle lets you add a plain number of days directly to a `DATE`) or `offer_date + INTERVAL '60' DAY`.
- `backend/db.py` and `db/seed.py` connect via `psycopg2` (Postgres-only driver) — an Oracle-backed version of the app would need `python-oracledb` instead, with different connection-string and cursor-handling code. Not attempted here since only the schema was asked for.

---

## What was actually verified in this session

Pulled `gvenzl/oracle-xe:21-slim` (a free, widely-used community Docker image for Oracle Database 21c Express Edition) and ran everything below against it via `sqlplus` — this was a genuine SQL*Plus session against real Oracle, not a syntax-only check.

**1. Full script execution — `db/schema_oracle.sql` run top-to-bottom, zero errors:**
```
docker run -d --name oracle_test -e ORACLE_PASSWORD=OraclePass123 -p 1522:1521 gvenzl/oracle-xe:21-slim
docker cp db/schema_oracle.sql oracle_test:/tmp/schema_oracle.sql
docker exec -i oracle_test sqlplus -s system/OraclePass123@//localhost:1521/XEPDB1 @/tmp/schema_oracle.sql
```
Result: **10 sequences created, 12 tables created, 11 triggers created, 5 indexes created, 2 functions created, 3 views created — no `ORA-` or `SP2-` errors anywhere in the output.**

**2. Behavioral smoke test — real data, real triggers, real function calls:**

| Check | What was run | Result |
|---|---|---|
| Auto-increment triggers | Inserted a department, coordinator, 2 students, a company, and a drive *without specifying any id column* | All 4 surrogate keys came back as `1` — every `trg_<table>_bi` trigger correctly pulled from its sequence |
| `fn_check_eligibility` — eligible case | `fn_check_eligibility(<8.50 CGPA, 0 backlogs student>, <7.5 min_cgpa, 1 max_backlogs drive>)` | Returned `1` ✅ |
| `fn_check_eligibility` — ineligible case | Same call for a 6.00 CGPA / 3-backlog student against the same drive | Returned `0` ✅ |
| `fn_check_eligibility` — NO_DATA_FOUND path | Called with a nonexistent `student_id` (999999) | Returned `0` cleanly — confirmed the `EXCEPTION WHEN NO_DATA_FOUND` block actually catches the exception rather than raising an unhandled `ORA-01403` up to the caller |
| `trg_offer_after_insert` | Checked `student.placement_status` immediately before and after inserting the matching `offer` row | `Not Placed` → `Placed`, exactly as designed |
| `fn_get_eligible_drives` | Called via `SYS_REFCURSOR`/`PRINT rc` for the eligible student | Returned exactly the 1 expected drive row, all columns populated correctly |

**Net result: every piece of custom logic in this port — not just the DDL shape, but the actual trigger and function *behavior* — is now confirmed correct against real Oracle, not just reasoned through.** The only things left at 🟡 best-effort are the two noted above (the Oracle `DATE`-includes-time semantic footnote in §1, which changes no behavior in this schema; and the general note that `GENERATED ALWAYS AS IDENTITY` is a valid 12c+ alternative I didn't separately test since the sequence+trigger version already works everywhere). Container was removed after testing (`docker rm -f oracle_test`) — nothing Oracle-related was left running or committed to the repo besides `schema_oracle.sql` itself.
