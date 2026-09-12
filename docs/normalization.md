# Normalization — Functional Dependencies and 3NF Justification

This document exists so you can defend the schema's normal form in a viva
without re-deriving it live. Every table is analyzed for its functional
dependencies (FDs) and shown to satisfy 3NF, with one documented, deliberate
exception.

## What 1NF / 2NF / 3NF require (quick recap for the viva)

- **1NF**: every attribute is atomic — no repeating groups, no comma-separated
  lists in a single column.
- **2NF**: 1NF + every non-key attribute depends on the **whole** primary key,
  not just part of it (only relevant for tables with a composite PK).
- **3NF**: 2NF + no **transitive** dependencies — a non-key attribute must
  depend directly on the key, not on another non-key attribute.

---

## department
**Key:** `dept_id`
**FDs:** `dept_id → dept_name, dept_code`
All attributes depend only on `dept_id`. Trivially 3NF. This table exists at
all specifically to avoid repeating `dept_name` as a string on every student
row (which would violate 3NF by making `dept_name` transitively dependent on
`student_id` through `dept_id`).

## coordinator
**Key:** `coordinator_id`
**FDs:** `coordinator_id → name, email, password_hash, role, created_at`
Also `email → coordinator_id` (email is a candidate key, enforced via
UNIQUE). No transitive dependencies. 3NF.

## student
**Key:** `student_id`
**FDs:** `student_id → reg_no, name, email, password_hash, dept_id, cgpa,
backlogs, batch_year, phone, placement_status, created_at`
Also `reg_no → student_id` and `email → student_id` (both candidate keys,
enforced via UNIQUE).
`dept_id` is a foreign key, not the department's other attributes
(`dept_name`, `dept_code`) — those are NOT duplicated here, which is exactly
what avoids the transitive dependency `student_id → dept_id → dept_name`
that would otherwise violate 3NF.

**Documented exception — `placement_status`:** this attribute is technically
derivable (`EXISTS (offer joined through this student's applications)`), so a
purist 3NF schema would compute it rather than store it. It is stored anyway
because (a) the assignment spec requires a **trigger** that writes it on
Offer insert, and (b) it makes `department_stats_view` and the student
dashboard read-path avoid a 4-table join for one of the most common queries
in the app. This is a controlled, single-attribute denormalization with a
trigger guaranteeing it never drifts out of sync with the offer data — not an
oversight. Be ready to name it as such if asked "isn't this redundant?"

## skill
**Key:** `skill_id`
**FDs:** `skill_id → skill_name`. Trivially 3NF.

## student_skill (junction)
**Key:** composite `(student_id, skill_id)`
**FDs:** none beyond the key itself — this table carries no non-key
attributes, so 2NF's "no partial dependency" and 3NF's "no transitive
dependency" clauses are vacuously satisfied. This is the standard resolution
of the Student↔Skill M:N relationship: a flat `student.skills` text column
would violate 1NF (a repeating group / multi-valued attribute in one cell),
and would make "count of skills per student" — needed as an ML feature — an
unreliable string-parsing operation instead of `COUNT(*) ... GROUP BY`.

## company
**Key:** `company_id`
**FDs:** `company_id → company_name, industry_sector, website, hr_email`
3NF. Kept separate from `drive` so that `industry_sector`/`website` are
stored once per company, not once per drive — storing them on `drive` would
create `drive_id → company_id → industry_sector`, a transitive dependency,
and an update anomaly (fixing a company's website would require updating
every past drive row).

## drive
**Key:** `drive_id`
**FDs:** `drive_id → company_id, coordinator_id, job_role, drive_date,
package_lpa, min_cgpa, max_backlogs, drive_type, status, created_at`
All attributes are facts about *this specific posting* (package, cutoffs,
date) — none of them are actually facts about the company or coordinator, so
there's no transitive dependency hiding here. 3NF.

## drive_eligible_dept (junction)
**Key:** composite `(drive_id, dept_id)`
**FDs:** none beyond the key — pure resolver table for the Drive↔Department
M:N branch-restriction relationship, same justification pattern as
`student_skill`. Storing eligible branches as `drive.allowed_branches =
'CSE,ISE,ECE'` would violate 1NF and make an indexed "find all drives open to
my department" query impossible without string parsing.

## application (central junction table)
**Key:** `application_id`
**FDs:** `application_id → student_id, drive_id, applied_at, status`
Also a candidate key `(student_id, drive_id) → application_id` (enforced via
UNIQUE, and semantically the constraint "a student applies to a given drive
at most once").
`status` describes the application's own progression (Applied → Shortlisted
→ ... → Selected/Rejected) — it is not a fact about the student or the drive
independently, so it belongs here and only here. 3NF.

## interview_round
**Key:** `round_id`
**FDs:** `round_id → application_id, round_number, round_type, round_date,
result, remarks`
Also `(application_id, round_number) → round_id` (candidate key, enforced via
UNIQUE). One row per round rather than `round1_result, round2_result, ...`
columns on `application` — the latter would violate 1NF (repeating group)
and hard-cap the number of rounds a drive could have. 3NF.

## offer
**Key:** `offer_id`
**FDs:** `offer_id → application_id, offered_package_lpa, offer_date,
status, joining_date`
Also `application_id → offer_id` (candidate key via UNIQUE — this is what
enforces the 1:0..1 Application↔Offer cardinality). 3NF.

## offer_history (append-only audit log)
**Key:** `history_id`
**FDs:** `history_id → offer_id, action, action_timestamp, notes`
Deliberately NOT modeled as an update to a single `offer.last_action`
column — that would destroy history on every write. One row per
state-change event is the correct normalized shape for an audit trail
(each row is an independent fact about "this event happened", not a
repeating group). 3NF.

---

## Summary

Every table's non-key attributes depend on the whole key and nothing but the
key, with one intentional, trigger-guaranteed exception
(`student.placement_status`) that is called out explicitly rather than
hidden. No table stores a value that is fully determined by a non-key
attribute of another table (the classic 3NF violation this schema was
specifically designed to avoid — see the `company`/`drive` and
`department`/`student` discussions above).
