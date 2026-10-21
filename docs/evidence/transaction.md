# Transactions: offer accept and decline

Accepting or declining an offer changes three things that must stay
consistent: the offer's status, the student's `placement_status` and the
`offer_history` log. `backend/services/offer_service.py` does all three
inside one explicit transaction:
- `try` runs the statements;
- `conn.commit()` makes them permanent together;
- any error goes to `except` and `conn.rollback()`.

So either every change happens or none does.

The output below is from the real backend. Each `>`/`<` pair is an HTTP
request and the backend's response. Each `[before]`/`[after]` line is a fresh
SELECT straight from the database. It ran on a throwaway copy of the database
(`placement_smoke`, built from the same schema and seed):

```
bash tests/run_smoke_test.sh tests/transaction_evidence.py
```

The script exits non-zero if any result differs from what the design
promises. It exited 0.

What each scenario shows:
1. **Accept.** One request produces all three changes: the offer becomes
   Accepted with a joining date, the student stays Placed, and one Accepted
   history row is added.
2. **Decline** of the student's only offer. The offer becomes Declined, and
   `placement_status` goes back from Placed to Not Placed, in the same
   transaction as the history row. (The insert trigger only ever turns
   Placed *on*. Turning it off needs the "does the student still have
   another live offer?" check, which `decline_offer` makes inside the
   transaction.)
3. **Rollback.** The database refuses a second acceptance (trigger PL003),
   the backend rolls back and answers 409, and the `[before]` and `[after]`
   lines are identical.
4. **Concurrency.** Two connections accept two different offers of the
   same student at the same moment. The trigger locks the student's row
   (`SELECT ... FOR UPDATE`), so B waits until A commits, then sees A's
   acceptance and is refused. Without the lock, neither would see the
   other's uncommitted row and both would succeed.

For the same transaction typed statement by statement in psql, including a
forced failure that aborts it half-way, see `transaction-sql.md`.

## Output

Unedited (also in `raw/transaction-evidence-output.txt`):

### 1. Accept: one transaction, three writes, one COMMIT

```text
Setup: Ira Verma (student 5) applied to drive 24; the admin moved application 518 to Selected and recorded offer 178 (Pending, 9.5 LPA).

  [before] offer.status=Pending, offer.joining_date=None, student.placement_status=Placed, offer_history=['Created']
> POST /api/offers/178/accept
< HTTP 200 {"offer_id": 178, "status": "Accepted"}
  [after ] offer.status=Accepted, offer.joining_date=2026-12-20, student.placement_status=Placed, offer_history=['Created', 'Accepted']
```

### 2. Decline: the student's only offer, so placement_status goes back

```text
Setup: Rudra Desai (student 6) applied to drive 24; the admin moved application 519 to Selected and recorded offer 179 (Pending, 7.0 LPA).

  [before] offer.status=Pending, offer.joining_date=None, student.placement_status=Placed, offer_history=['Created']
> POST /api/offers/179/decline
< HTTP 200 {"offer_id": 179, "status": "Declined"}
  [after ] offer.status=Declined, offer.joining_date=None, student.placement_status=Not Placed, offer_history=['Created', 'Declined']
```

### 3. Refused mid-transaction: a second acceptance (PL003) is rolled back

```text
Setup: Shreya Sharma (student 18) has already accepted one offer; offer 70 is a second, Pending offer.

  [before] offer.status=Pending, offer.joining_date=None, student.placement_status=Placed, offer_history=['Created']
> POST /api/offers/70/accept
< HTTP 409 {"error": "Student 18 has already accepted another offer"}
  [after ] offer.status=Pending, offer.joining_date=None, student.placement_status=Placed, offer_history=['Created']
```

### 4. Two acceptances at the same moment: the row lock serializes them

```text
Setup: Priya Agarwal (student 10) applied to drive 15; the admin moved application 520 to Selected and recorded offer 180 (Pending, 10.0 LPA).

Setup: the same student now also has offer 181 (Pending). Two connections will each accept one.

  t= 0.06s  A: UPDATE offer 180 -> Accepted done (trigger took the student-row lock); A has NOT committed
  t= 0.06s  B: UPDATE offer 181 -> Accepted sent
  t= 1.56s  (B still waiting after 1.5 s: True)
  t= 1.56s  A: COMMIT
  t= 1.57s  B: refused, SQLSTATE PL003: Student 10 has already accepted another offer
  [after] offer 180: Accepted, offer 181: Pending
```
