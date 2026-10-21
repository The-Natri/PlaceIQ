# ER Diagram — College Placement Management System

13 tables, matching `db/schema.sql` (checked against the live database's
`information_schema.columns`; full column/constraint listing in
`docs/evidence/schema-summary.md`). A rendered PNG of this exact diagram is
`docs/evidence/er-diagram.png`.

Render this directly on GitHub, in VS Code (Markdown Preview Mermaid Support
extension), or at https://mermaid.live.

```mermaid
erDiagram
    DEPARTMENT ||--o{ STUDENT : "has"
    SKILL ||--o{ STUDENT_SKILL : "held_by"
    STUDENT ||--o{ STUDENT_SKILL : "has"
    STUDENT ||--o{ APPLICATION : "submits"
    DRIVE ||--o{ APPLICATION : "receives"
    DEPARTMENT ||--o{ DRIVE_ELIGIBLE_DEPT : "restricts"
    DRIVE ||--o{ DRIVE_ELIGIBLE_DEPT : "restricted_to"
    COMPANY ||--o{ DRIVE : "posts"
    COORDINATOR ||--o{ DRIVE : "creates"
    APPLICATION ||--o{ INTERVIEW_ROUND : "has"
    APPLICATION ||--o| OFFER : "results_in"
    OFFER ||--o{ OFFER_HISTORY : "logs"
    APPLICATION ||--o{ APPLICATION_STATUS_HISTORY : "audited_by"

    DEPARTMENT {
        int dept_id PK
        string dept_name UK
        string dept_code UK
    }
    STUDENT {
        int student_id PK
        string reg_no UK
        string name
        string email UK
        string password_hash
        int dept_id FK
        numeric cgpa
        int backlogs
        int batch_year
        string phone
        string placement_status
        timestamp created_at
    }
    SKILL {
        int skill_id PK
        string skill_name UK
    }
    STUDENT_SKILL {
        int student_id PK, FK
        int skill_id PK, FK
    }
    COMPANY {
        int company_id PK
        string company_name UK
        string industry_sector
        string website
        string hr_email
    }
    DRIVE {
        int drive_id PK
        int company_id FK
        int coordinator_id FK
        string job_role
        date drive_date
        numeric package_lpa
        numeric min_cgpa
        int max_backlogs
        string drive_type
        string status
        timestamp created_at
    }
    DRIVE_ELIGIBLE_DEPT {
        int drive_id PK, FK
        int dept_id PK, FK
    }
    APPLICATION {
        int application_id PK
        int student_id FK
        int drive_id FK
        timestamp applied_at
        string status
    }
    INTERVIEW_ROUND {
        int round_id PK
        int application_id FK
        int round_number
        string round_type
        date round_date
        string result
        string remarks
    }
    OFFER {
        int offer_id PK
        int application_id FK, UK
        numeric offered_package_lpa
        date offer_date
        string status
        date joining_date
    }
    OFFER_HISTORY {
        int history_id PK
        int offer_id FK
        string action
        timestamp action_timestamp
        string notes
    }
    COORDINATOR {
        int coordinator_id PK
        string name
        string email UK
        string password_hash
        string role
        timestamp created_at
    }
    APPLICATION_STATUS_HISTORY {
        int history_id PK
        int application_id FK
        string old_status
        string new_status
        timestamp changed_at
    }
```

## Allowed values (CHECK constraints)

Kept out of the diagram so it stays legible on an A4 page. Each list is a
`CHECK (... IN (...))` constraint in `db/schema.sql`.

| Column | Allowed values |
|---|---|
| `student.placement_status` | Not Placed, Placed |
| `coordinator.role` | TPO, Coordinator |
| `drive.drive_type` | Full-Time, Internship |
| `drive.status` | Upcoming, Ongoing, Completed, Cancelled |
| `application.status` | Applied, Shortlisted, Interview_Scheduled, Rejected, Selected, Offer_Made |
| `interview_round.round_type` | Aptitude, Technical, HR, Group_Discussion, Coding_Test |
| `interview_round.result` | Pass, Fail, Pending |
| `offer.status` | Pending, Accepted, Declined |
| `offer_history.action` | Created, Accepted, Declined |

## Entity list with cardinalities (plain-English, for the viva)

| Relationship | Cardinality | Notes |
|---|---|---|
| Department — Student | 1 : N | Every student belongs to exactly one department. |
| Department — Drive (via Drive_Eligible_Dept) | M : N | A drive can be restricted to multiple departments; a department can be targeted by multiple drives. Zero rows for a drive = open to all departments. |
| Student — Skill (via Student_Skill) | M : N | A student has many skills; a skill is held by many students. |
| Company — Drive | 1 : N | A company can run many drives (across years/roles); each drive belongs to one company. |
| Coordinator — Drive | 1 : N | A coordinator/TPO creates many drives; each drive has one creator (nullable — a drive could be system/seed-created). |
| Student — Application | 1 : N | A student can submit many applications (to different drives). |
| Drive — Application | 1 : N | A drive receives many applications (from different students). |
| **Student — Drive (via Application)** | **M : N** | The actual M:N relationship the spec calls out — Application is the resolving junction/associative entity, carrying its own attributes (applied_at, status). |
| Application — Interview_Round | 1 : N | An application goes through zero or more interview rounds. |
| Application — Offer | 1 : 0..1 | An application results in at most one offer (enforced by UNIQUE(application_id) on Offer). |
| Offer — Offer_History | 1 : N | Every state change to an offer (Created/Accepted/Declined) appends one audit row. |
| Application — Application_Status_History | 1 : N | Every status change of an application appends one row. Written only by the trigger `trg_application_status_audit`, never by application code. |

## Which tables the database maintains by itself

Some rows and columns are written by triggers, not by the backend, so they
stay correct even if someone edits the data directly in SQL:

| Written by | What it writes |
|---|---|
| `trg_offer_after_insert` | `student.placement_status` → `Placed` when a (non-Declined) offer is inserted |
| `trg_application_status_audit` | one `application_status_history` row per status change |
| `sp_close_drive` (procedure) | `drive.status` → `Completed`, pending applications → `Rejected` |

And four BEFORE triggers refuse rows that break a rule (error codes PL001–PL007,
evidence in `docs/evidence/triggers.md`): `trg_application_before_insert`,
`trg_offer_before_accept`, `trg_offer_requires_selected`,
`trg_application_status_transition`.

## Why Application resolves Student↔Drive (not Student↔Company directly)

A company runs many drives over time (different roles, different years, different eligibility cutoffs and packages). A student applies to one specific posting, not generically to "Infosys" — so `Application.drive_id` is the correct FK, and the Student↔Company relationship is still fully queryable by joining through Drive → Company. Modeling it as `Application.company_id` directly would lose which specific drive was applied to, or require carrying both FKs redundantly.
