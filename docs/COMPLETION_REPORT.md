# PlaceIQ: completion report

Covers the "complete everything remaining" request (Phases 1–7), 21–22 Oct 2026.
It is based on `docs/PROJECT_STATUS.md` (the audit before this work) and on real
output only. **Nothing has been pushed.** All commits are local.

## Where things are

| Branch | Commits not on GitHub | Contents |
|---|---|---|
| `main` | 7 (`a0b612c` … `e02f11d`) | Database, backend, ML, Oracle port, docs, evidence, report |
| `frontend-polish` | 1 more on top of `7ec0239` (`e706f18`) | The rebuilt UI (Phase 5) |

`git merge-tree` shows `frontend-polish` merges into `main` **with no
conflicts**. Phase 5 touched only `frontend/`, `tests/ui_walkthrough.js` and
`docs/evidence/raw/ui-walkthrough.txt`.

## What was done, phase by phase

| Phase | Commit | What changed | Verified by |
|---|---|---|---|
| 1. Bugs and hygiene | `da7b676` | Two new rule triggers (PL006: offer only for a Selected application; PL007: forward-only status changes). The seed was rewritten to move applications through legal steps. JWT secret regenerated into `.env` only (never printed or committed). `.env.example` has a placeholder. Debug mode off by default. CORS limited to configured origins. Autocommit bug fixed in `db.py`. | Smoke test 41/41 |
| 2. Clean data and ML | `cc1bb50` | Live DB rebuilt and reseeded (517 applications, 177 offers, 95 placed). Model retrained (ROC-AUC 0.774, accuracy 0.750 on 36 test students). Stale 0.878/0.820/0.975 figures replaced, with caveats. `.gitattributes` keeps `*.sh` LF. | `/health`, `/predict`, probability endpoint |
| 3. Oracle port | `499e5fb` | Sections 6–10 ported (rule triggers, COMPOUND trigger for PL003, audit, procedure, window views, MV). Also `oracle_setup.sql`, demo data, SQL*Plus demo, one-command full run. | SQL*Plus transcript: 82 objects VALID, 6 intended errors only |
| 4. API docs | `7ec0239` | `docs/API.md` documents all 36 endpoints. `tests/api_contract_check.py` checks the doc against the running backend. | 161/161, and the checker failed on a deliberately tampered doc |
| 5. Frontend polish | `e706f18` (branch `frontend-polish`) | ERP-style rebuild: design tokens, layout shell, reusable UI pieces, SVG charts each with a table view, UI for every endpoint (close drive, rounds, offers, status history, rankings, timeline, MV matrix, student list). | Build + lint clean; Playwright walkthrough 28/28 |
| 6. Evidence | `7337fc6` | `docs/evidence/`: ER PNG, schema summary, queries, triggers, transactions (API + SQL), index benchmark with EXPLAIN ANALYZE, ML results, 14 screenshots, smoke test, INDEX.md. ER diagram, normalization and viva cheat sheet updated to 13 tables. | All outputs real and regenerable. Live DB unchanged afterwards (517/177/95/1177). |
| 7. Report | `e02f11d` | `docs/PlaceIQ_DA3_Report.docx` (+ PDF), 31 pages, 15 figures, 10 tables, 16 references. Built by `docs/report/build_report.py`. | PDF inspected page by page. Every table and figure reference matches its caption, and the TOC page numbers are correct. |

### Found and fixed along the way

- **`placement_timeline_view` skipped empty months** (found while
  capturing screenshots in Phase 6). With no offers in January 2026, `LAG()`
  compared February with December and reported −98. The view now generates
  every month (`generate_series`; `ADD_MONTHS … CONNECT BY` in Oracle), so January
  is 0 and February is +16. Re-verified on PostgreSQL (smoke test 41/41) and
  Oracle (82 objects VALID; new demo step 6e shows the 0 row).
- **The ER diagram's Mermaid source didn't render** (`FK UK` and `PK_FK` aren't
  valid syntax), so it was broken on GitHub too. Fixed.
- **Concurrent acceptance is now proven** on PostgreSQL, not just claimed.
  Two real connections accept two offers of one student. The second waits on
  the row lock, then gets PL003 (`docs/evidence/transaction.md`, scenario 4).

## Final verification

| Check | Result | Where |
|---|---|---|
| Smoke test (API + direct SQL), final schema | 41 / 41 | `docs/evidence/smoke-test.md` |
| API contract check (36 endpoints) | 161 / 161 (re-run 22 Oct, after the last doc change) | `docs/evidence/raw/api-contract-check.txt` |
| Transaction evidence (accept, decline, rollback, concurrency) | 4 / 4 scenarios as designed | `docs/evidence/transaction.md` |
| UI walkthrough (Playwright) | 28 / 28 | `docs/evidence/raw/ui-walkthrough.txt` (on `frontend-polish`) |
| Oracle 21c XE full run | 82 objects VALID, `user_errors` empty, 6 intended ORA-200xx | `docs/evidence/sqlplus-transcript.txt` |
| Index benchmark (250k applications) | 1.8× – 81.2× | `docs/evidence/index-benchmark.md` |

## What failed, was skipped, or is still open

- **Docker Desktop stopped by itself** near the end (likely under memory
  pressure: about 2–3 GB free most of the session). I restarted it. `placement_db`
  came back healthy with its data intact, and I restarted the backend (:5000)
  and ML service (:6000). Earlier in the work Docker also crashed twice during the
  index benchmark, which is why the benchmark uses 250k applications, not 1M.
- **The Vite dev server is not running.** The working tree is on `main`, which
  still has the old UI. To demo the new UI: `git checkout frontend-polish`,
  then `cd frontend && npm run dev` (or merge first, see below).
- **The Oracle port covers the database layer only.** The backend runs only
  on PostgreSQL. Concurrent acceptance on Oracle is unverified (the demo is
  one SQL*Plus session). `REFRESH … CONCURRENTLY` has no Oracle equivalent.
  Details in `docs/oracle-differences.md`.
- **Seed timestamps.** `applied_at` and the status-history times are the
  moment the seed ran, so an application can appear to be dated after its drive
  (visible in screenshot 06). This is cosmetic and listed as a limitation in the report. It is not fixed,
  because that would mean reseeding and redoing the evidence.
- **One reference left out.** A 2022 IEEE paper (Shahane) appeared in search
  results, but its page couldn't be opened to verify the details, so it isn't cited.
  Two IJERT papers have DOIs that are not registered (doi.org returns 404), so they
  are cited by URL, which was opened and checked.
- **The report has placeholders** to fill in: names, register numbers,
  course code/name, faculty, institution, date (title page). After editing,
  update the table of contents in Word (right-click → Update Field), or rerun
  `docs/report/render_pdf.ps1`.
- **`docs/PROJECT_STATUS.md` is the before-picture.** It was not rewritten, so
  several of its "open" items are now done. A note at its top points here.
- **Possible conflict with your teammate.** `frontend-polish` deletes and
  replaces the old page files (`frontend/src/pages/*.jsx`, `Navbar`, their CSS).
  Their fork (`firetruckss/PlaceIQ`) had nothing unmerged when checked. But if
  they change those old files before this is merged, their change will
  conflict. Agree with them before merging, and point them to
  `frontend/README.md`.

## Read these before the viva

1. `docs/viva-cheatsheet.md`: one line per feature, plus likely questions.
2. `docs/PlaceIQ_DA3_Report.pdf`: what you are submitting.
3. `db/schema.sql`: all of it, section by section (the Section headers are at lines 32, 227, 258, 303, 389, 446, 626, 663, 716 and 791).
4. `docs/normalization.md`: FDs and the one deliberate denormalization.
5. `docs/evidence/INDEX.md`, then `triggers.md`, `transaction.md` and `index-benchmark.md`.
6. `docs/oracle-differences.md`: if the lab expects Oracle.
7. `backend/services/offer_service.py` and `backend/db.py`: the transaction code.
8. `docs/evidence/ml-results.md`: so you can explain the model's limits yourself.

## The 5 things to know line by line

| # | What | Where | Be ready to explain |
|---|---|---|---|
| 1 | PL003 trigger: one accepted offer per student | `db/schema.sql:513-546` | Why `PERFORM 1 FROM student … FOR UPDATE` (line 525) comes before the count. Why `IS DISTINCT FROM NEW.offer_id`. Why BEFORE and not AFTER. |
| 2 | PL007 status state machine | `db/schema.sql:595-622` | Why a CHECK constraint can't do this (it has no `OLD`). The `WHEN (OLD.status IS DISTINCT FROM NEW.status)` clause. Which states are final. |
| 3 | Eligibility function and the guard trigger that uses it | `db/schema.sql:316-370` and `468-500` | Single source of truth. What "no rows in `drive_eligible_dept`" means. PL001 vs PL002. |
| 4 | `sp_close_drive` procedure | `db/schema.sql:682-712` | PROCEDURE vs FUNCTION. `INOUT` and `CALL`. `FOR UPDATE` on the drive row. `GET DIAGNOSTICS … ROW_COUNT`. PL004/PL005. |
| 5 | Offer accept/decline transaction | `backend/services/offer_service.py:65-115` (accept) and `118-172` (decline) | The three statements, `commit()`/`rollback()`, why `AND status = 'Pending' RETURNING` is an atomic guard, why decline re-checks for other live offers. |

Also worth a look: `backend/db.py:42` (`get_cursor`, including the autocommit
case needed for `REFRESH MATERIALIZED VIEW CONCURRENTLY`),
`backend/utils/db_errors.py:23` (SQLSTATE → HTTP mapping), `db/schema.sql:756`
(the timeline view and its month-gap fix) and `db/schema.sql:277`
(the placement-status trigger).

## Git commands (run these yourself)

**1. Push `main`** (7 commits):

```bash
cd "C:/Users/Naveen M N/college-placement-system"
git checkout main
git log --oneline origin/main..main     # check: the 7 commits listed above
git push origin main
```

**2. Get `frontend-polish` into `main`.** Pick one option.

*Option A (recommended): push the branch and open a PR, so your teammate can review the UI rewrite first:*

```bash
git push -u origin frontend-polish
gh pr create --base main --head frontend-polish --title "Frontend polish: ERP-style UI with screens for every endpoint" --body "Phase 5. See frontend/README.md for structure and conventions."
# after review: merge on GitHub, then locally
git checkout main && git pull origin main
```

*Option B: merge locally and push:*

```bash
git checkout main
git merge --no-ff frontend-polish -m "Merge frontend-polish: rebuilt UI"
git push origin main
```

After either option, run the UI with `cd frontend && npm install && npm run dev`.
