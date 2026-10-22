# Final smoke test

`tests/smoke_test.py` drives the real backend through every main flow and
every database-enforced rule. Where a rule lives in a trigger, it also sends
the bad write straight to PostgreSQL (no backend), to prove the database
refuses it on its own.

It writes data, so `tests/run_smoke_test.sh` runs it against a throwaway copy:
- builds `placement_smoke` from `db/schema.sql` and `db/seed.py`;
- starts a second backend on port 5001;
- runs the checks;
- drops the database.

The live `placement_db` is not touched.

This run used the final schema, including the corrected
`placement_timeline_view` and the date-integrity rule (PL008). **Result: 47 / 47 passed.**

Unedited output of `bash tests/run_smoke_test.sh` (also in
`raw/smoke-test-output.txt`):

```text
== Building placement_smoke (schema + seed) ==
NOTICE:  database "placement_smoke" does not exist, skipping
Students marked 'Placed' by the trigger: 95 / 180
Seeding complete.
== Starting backend on :5001 against placement_smoke ==
== Running smoke_test.py ==
PASS | Admin login                                                                              | HTTP 200
PASS | Admin login with wrong password rejected                                                 | HTTP 401
PASS | Student login                                                                            | HTTP 200
PASS | Eligible drives (fn_get_eligible_drives)                                                 | HTTP 200, 1 drives
PASS | Student cannot read another student's record                                             | HTTP 403
PASS | Apply to drive                                                                           | HTTP 201
PASS | Duplicate application rejected                                                           | HTTP 409
PASS | Admin shortlists (Applied -> Shortlisted)                                                | HTTP 200
PASS | Student cannot change status (admin-only)                                                | HTTP 403
PASS | Admin records interview round                                                            | HTTP 201
PASS | NEW: offer on a Shortlisted (not yet Selected) application refused                       | HTTP 409: Application is Shortlisted; mark it Selected before recording an offer
PASS | Admin selects (Shortlisted -> Selected)                                                  | HTTP 200
PASS | Record offer -> trigger flips placement_status                                           | HTTP 201; Not Placed -> Placed
PASS | Accept offer (transaction)                                                               | HTTP 200; offer_history=['Created', 'Accepted']
PASS | Accepting the same offer twice refused                                                   | HTTP 409
PASS | Decline only offer -> placement_status reverts                                           | HTTP 200; Placed -> Not Placed
PASS | Student cannot act on someone else's offer                                               | HTTP 403
PASS | Placement-probability endpoint (backend -> ML service)                                   | HTTP 200, p=0.059
PASS | Rule PL002: apply to a closed drive refused                                              | HTTP 409
PASS | (found an ineligible open drive for the PL001 test)                                      | 
PASS | Rule PL001: apply while ineligible refused                                               | HTTP 403
PASS | Rule PL003: second accepted offer refused                                                | HTTP 409
PASS | Admin rejects (Applied -> Rejected)                                                      | HTTP 200
PASS | NEW: offer on a Rejected application refused (API)                                       | HTTP 409: Application is Rejected; mark it Selected before recording an offer
PASS | NEW: offer on a Rejected application refused by the trigger itself (raw SQL, no backend) | SQLSTATE PL006
PASS | ...and the Rejected application has no offer row                                         | 
PASS | NEW: Rejected -> Applied refused (API)                                                   | HTTP 409: Application 523 cannot move from Rejected to Applied
PASS | NEW: Rejected -> Applied refused by the trigger itself (raw SQL)                         | SQLSTATE PL007
PASS | NEW: Offer_Made -> Shortlisted (backwards) refused                                       | SQLSTATE PL007
PASS | ...application statuses unchanged after the refused moves                                | 
PASS | Admin moves a drive's application deadline to yesterday                                  | HTTP 200
PASS | NEW: apply after the deadline refused (API)                                              | HTTP 409: Applications for drive 24 closed on 2026-10-21
PASS | NEW: apply after the deadline refused by the trigger itself (raw SQL)                    | SQLSTATE PL008
PASS | NEW: application dated in the future refused (raw SQL)                                   | SQLSTATE PL008
PASS | NEW: deadline after the drive date refused (CHECK constraint)                            | HTTP 400
PASS | ...the student has no application to that drive after the refused attempts               | 
PASS | Procedure sp_close_drive via API                                                         | HTTP 200, rejected 37 of 37 pending
PASS | GET /analytics/overview                                                                  | HTTP 200
PASS | GET /analytics/department-stats                                                          | HTTP 200
PASS | GET /analytics/company-stats?top=5                                                       | HTTP 200
PASS | GET /analytics/package-by-branch                                                         | HTTP 200
PASS | GET /analytics/cgpa-vs-outcome                                                           | HTTP 200
PASS | GET /analytics/top-offers-per-dept                                                       | HTTP 200
PASS | GET /analytics/placement-timeline                                                        | HTTP 200
PASS | GET /analytics/company-dept-matrix                                                       | HTTP 200
PASS | CORS: frontend origin http://localhost:5173 allowed                                      | Access-Control-Allow-Origin=http://localhost:5173
PASS | CORS: unknown origin http://evil.example not allowed                                     | Access-Control-Allow-Origin=None

TOTAL: 47/47 passed
```
