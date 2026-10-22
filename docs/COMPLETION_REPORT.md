# PlaceIQ: completion report (final round)

Covers the final round (release Phases 1–6), 22 Oct 2026, on the branch
**`release`**. `release` was created from `frontend-polish` with `main` merged in.
There were no conflicts, and nothing was rewritten or force-pushed.
Everything below is based on real command output kept in `docs/evidence/`.
The earlier rounds are summarised at the end.

## How to run it

| Way | Command | Address |
|---|---|---|
| One command (Docker) | `docker compose up -d --build` · stop: `docker compose down` | http://localhost:8080 |
| Desktop app (Windows) | double-click `desktop/dist/PlaceIQ-1.0.0-portable.exe` (build it with `npm install` then `npm run dist` in `desktop/`) | opens its own window |
| Local virtualenvs | `.\start.ps1` / `.\stop.ps1` (or `./start.sh` / `./stop.sh`) | http://localhost:8080 |
| Temporary public link | `.\scripts\share.ps1` · stop: `.\scripts\share.ps1 -Stop` | prints `https://<words>.trycloudflare.com` |

Demo logins (local only; replaced in public mode):
- admin: `tpo@campus.edu` / `Admin@123`;
- students: any seeded e-mail / `Student@123`.

## What changed, phase by phase

| Phase | Commit | What changed | Verified by |
|---|---|---|---|
| 1. Date integrity | `e554a58` | `drive.application_deadline` (CHECK ≤ drive date). The guard trigger refuses applications after the deadline or dated in the future (PL008 → 409; Oracle −20008). `fn_get_eligible_drives` hides closed drives. The seed builds every timeline relative to the database's date, in order; date jitter uses a separate random generator, so outcomes are unchanged. The database time zone is Asia/Kolkata (a smoke-test failure exposed the UTC/IST deadline gap). UI: deadline field, "Applications close", "Apply by". | 10 date rules, **0 violations**. Smoke **47/47**. Oracle: **82 objects VALID**, 7 intended errors only. Retrained model **identical** (ROC-AUC 0.774). |
| 2. Single link | `132e30a` | waitress serves the built UI and the API on **one port (8080)**, with SPA fallback; the frontend calls relative `/api`; CORS is off; debug is off. The backend refuses to start without a JWT secret. `docker-compose.yml` has db, app and ml, and **only app publishes a port (127.0.0.1:8080)**; the first run applies the schema, seeds and trains. `start/stop.ps1` and `start/stop.sh` cover the venv path; they check Docker and rebuild a stale UI. | Clean-state `docker compose up -d --build`: **235 s**. Browser checks **12/12** (Docker) and **12/12** (venv); no other origin contacted. Smoke **48/48** on waitress. Host listens only on 127.0.0.1:8080. No leftovers after stop. |
| 3. Desktop app | `e3dd086` | `desktop/`: an Electron launcher that checks Docker (message + Retry), runs `compose up`, shows a loading screen until `/api/health` answers, opens the app and runs `compose down` on quit. Packaged as `desktop/dist/PlaceIQ-1.0.0-portable.exe` (electron-builder, free, unsigned). | Packaged app **8/8**: stack up in 16 s, student and admin signed in, **no containers or processes left** after quit. Portable .exe: healthy in 25 s, clean on close. A JWT secret was generated into the volume (mode 600). |
| 4. Public link | `0c911a2` | `scripts/share.ps1`/`.sh`: public mode plus a Cloudflare quick tunnel (cloudflared from the official GitHub release, after a prompt; the binary is checked to run). In public mode, secrets and passwords come from the git-ignored `.env.public` (generated, never printed), demo passwords are replaced, and login/signup are rate-limited (10 per 5 min per visitor). `DEPLOY_FREE.md`: Render + Neon steps with their limits (not run). | Through the public link: demo password **refused (401)**; browser check **12/12**; 8th rapid wrong login → **429**; after `-Stop` the link gives **530** and nothing is left. |
| 5. Docs and report | (this commit) | Screenshots retaken from real runs. README (three ways to run, share, deploy), `docs/API.md`, ER diagram + PNG, normalization, Oracle differences, viva cheat sheet and evidence index updated. Report: PL008, a date-integrity result, a new **2.9 Deployment** subsection, the date limitation removed, 4 new references (all URLs checked). | API contract **161/161**. Transaction evidence: 4/4 scenarios. Report PDF: 34 pages inspected; every figure/table reference matches its caption; no stale text. |
| 6. Push | (filled in after pushing) | | |

### Found and fixed along the way

- **UTC vs IST deadlines:** the database fix described in Phase 1.
- **Stale UI build:** `start.ps1` served an old build that called the removed port 5000. The browser check caught it, and the start scripts now rebuild when the UI source is newer.
- **Process cleanup on Windows:** `stop.sh` couldn't end servers, because a venv's `python.exe` is a launcher. The servers now write their own PID files.
- **Truncated cloudflared download:** PowerShell 5.1's `Invoke-WebRequest` cut it short; the script now uses `curl.exe` and test-runs the binary.
- **Tunnel URL:** the share script mistook `api.trycloudflare.com` for the tunnel link; the regex now excludes it.
- **2-second ML calls on Windows:** `localhost` tried IPv6 first; the backend now uses `127.0.0.1`.
- **Contract checker:** it counted the JSON-404 catch-all as an undocumented endpoint; it now skips it.
- **Schema comment:** it pointed at a demo file that didn't exist; it now points at the real test.

## Not done, skipped, or still open

- **Index benchmark not re-run.** It was run before `application_deadline` existed. The column is in no benchmarked query or index; the script was updated, not re-run.
- **Full UI walkthrough (28/28) not re-run.** It is from the UI rebuild, against the Vite dev server. The single-address browser checks (12/12 ×3) and the desktop check (8/8) replace it.
- **Lint warnings.** `npx oxlint` reports 2 `set-state-in-effect` warnings in `DriveFormModal.jsx` and `AdminDriveDetail.jsx`. They are in code from before this round (a newer oxlint added the rule) and are left as they are.
- **Permanent hosting not deployed.** It needs your Render and Neon accounts (`DEPLOY_FREE.md`).
- **The .exe is unsigned** (signing costs money), so SmartScreen may warn. The desktop app needs Docker Desktop installed; it is not bundled.
- **Oracle:** the backend isn't ported; concurrent acceptance isn't demonstrated on Oracle (it is on Postgres).

## You need to do

1. Fill in the report's title-page placeholders (names, register numbers, course, faculty, institution, date). Then in Word: right-click the table of contents → Update Field, and re-export the PDF (or run `docs/report/render_pdf.ps1`).
2. Optionally deploy permanently with `DEPLOY_FREE.md` (your free accounts).
3. Your teammate: see "Conflicts" below.

## Read before the viva

1. `docs/viva-cheatsheet.md`
2. `docs/PlaceIQ_DA3_Report.pdf`
3. `db/schema.sql`, section by section
4. `docs/evidence/INDEX.md`, then `date-integrity.md`, `triggers.md` and `transaction.md`
5. `docs/normalization.md`, `docs/oracle-differences.md`
6. `backend/services/offer_service.py`, `backend/app.py`, `docker-compose.yml`

## The 5 things to know line by line

| # | What | Where |
|---|---|---|
| 1 | Application guard: PL002 closed drive, **PL008 deadline / future date**, PL001 eligibility | `db/schema.sql:489-539` (deadline check at 521) |
| 2 | PL003 one accepted offer, with the row lock | `db/schema.sql:552-585` (`FOR UPDATE` at 564) |
| 3 | PL007 status state machine (OLD vs NEW) | `db/schema.sql:634-661` |
| 4 | `sp_close_drive` procedure | `db/schema.sql:721-751` |
| 5 | Offer accept/decline transaction | `backend/services/offer_service.py:65-115` and `118-172` |

Also worth reading:
- `db/schema.sql:334-388`: `fn_check_eligibility`;
- `db/schema.sql:795`: the timeline view;
- `backend/app.py:92`: SPA serving;
- `backend/utils/rate_limit.py:52`: the login limit;
- `db/seed.py:164`: replayed, backdated audit rows.

## Conflicts with your teammate

`release` replaces the old frontend pages (`frontend/src/pages/*.jsx`, `Navbar`, their CSS) with the
rebuilt UI. It also changes `frontend/src/api.js` (relative `/api`) and `vite.config.js` (dev proxy).
If your teammate has local changes to any of those old files, they will conflict when they pull, and
their old pages no longer exist in this version. They should commit or stash first, then read
`frontend/README.md` (the new structure). Their local `frontend/.env` must no longer set
`VITE_API_URL=http://localhost:5000/api`. It would be baked into their build and break the
single-port setup.

## Earlier rounds (for reference)

- **Phases 1–7 of the previous round:** rule triggers PL006/PL007, reseed and retrain, Oracle port, API docs, UI rebuild, evidence pack, report.
- They are on `main` up to `f5d7ed6` and are described in that commit history.
