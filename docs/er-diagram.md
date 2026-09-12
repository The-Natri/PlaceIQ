# ER Diagram — College Placement Management System

Render this directly on GitHub, in VS Code (Markdown Preview Mermaid Support
extension), or at https://mermaid.live.

```mermaid
erDiagram
    DEPARTMENT ||--o{ STUDENT : "has"
    DEPARTMENT ||--o{ DRIVE_ELIGIBLE_DEPT : "restricts"
    DRIVE ||--o{ DRIVE_ELIGIBLE_DEPT : "restricted_to"
    STUDENT ||--o{ STUDENT_SKILL : "has"
    SKILL ||--o{ STUDENT_SKILL : "held_by"
    COMPANY ||--o{ DRIVE : "posts"
    COORDINATOR ||--o{ DRIVE : "creates"
    STUDENT ||--o{ APPLICATION : "submits"
    DRIVE ||--o{ APPLICATION : "receives"
    APPLICATION ||--o{ INTERVIEW_ROUND : "has"
    APPLICATION ||--o| OFFER : "results_in"
    OFFER ||--o{ OFFER_HISTORY : "logs"

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
        string placement_status "Not Placed / Placed"
        timestamp created_at
    }
    SKILL {
        int skill_id PK
        string skill_name UK
    }
    STUDENT_SKILL {
        int student_id PK_FK
        int skill_id PK_FK
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
        string drive_type "Full-Time / Internship"
        string status "Upcoming/Ongoing/Completed/Cancelled"
    }
    DRIVE_ELIGIBLE_DEPT {
        int drive_id PK_FK
        int dept_id PK_FK
    }
    APPLICATION {
        int application_id PK
        int student_id FK
        int drive_id FK
        timestamp applied_at
        string status "Applied/Shortlisted/.../Offer_Made"
    }
    INTERVIEW_ROUND {
        int round_id PK
        int application_id FK
        int round_number
        string round_type
        date round_date
        string result "Pass/Fail/Pending"
        string remarks
    }
    OFFER {
        int offer_id PK
        int application_id FK UK
        numeric offered_package_lpa
        date offer_date
        string status "Pending/Accepted/Declined"
        date joining_date
    }
    OFFER_HISTORY {
        int history_id PK
        int offer_id FK
        string action "Created/Accepted/Declined"
        timestamp action_timestamp
        string notes
    }
    COORDINATOR {
        int coordinator_id PK
        string name
        string email UK
        string password_hash
        string role "TPO / Coordinator"
    }
```

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

## Why Application resolves Student↔Drive (not Student↔Company directly)

A company runs many drives over time (different roles, different years, different eligibility cutoffs and packages). A student applies to one specific posting, not generically to "Infosys" — so `Application.drive_id` is the correct FK, and the Student↔Company relationship is still fully queryable by joining through Drive → Company. Modeling it as `Application.company_id` directly would lose which specific drive was applied to, or require carrying both FKs redundantly.
