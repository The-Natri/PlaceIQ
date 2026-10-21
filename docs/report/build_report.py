"""
Builds docs/PlaceIQ_DA3_Report.docx.

Every number in the Results chapter is copied from docs/evidence/ (each
paragraph names the evidence file it comes from). The code listings in the
Appendix are read from the source files at build time, so they always match
the code. Figures are the PNGs in docs/evidence/.

Needs python-docx (pip install python-docx==1.1.2). Run from the repo root:
    python docs/report/build_report.py
Then open the .docx in Word and update fields (or run render_pdf.ps1), which
fills in the table of contents and page numbers.
"""
import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[2]
EVID = ROOT / "docs" / "evidence"
SHOTS = EVID / "screenshots"
# An output path can be given as an argument (e.g. while the report is open in Word).
OUT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "docs" / "PlaceIQ_DA3_Report.docx"

doc = Document()
fig_no = 0
tab_no = 0

# --------------------------------------------------------------------------
# Page setup and styles
# --------------------------------------------------------------------------
sec = doc.sections[0]
sec.page_height, sec.page_width = Cm(29.7), Cm(21.0)
sec.left_margin = sec.right_margin = Cm(2.54)
sec.top_margin = sec.bottom_margin = Cm(2.54)
TEXT_WIDTH = Cm(21.0 - 2 * 2.54)

normal = doc.styles["Normal"]
normal.font.name = "Times New Roman"
normal.font.size = Pt(12)
normal.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
normal.paragraph_format.line_spacing = 1.15
normal.paragraph_format.space_after = Pt(6)

for level, size in ((1, 16), (2, 13), (3, 12)):
    st = doc.styles[f"Heading {level}"]
    st.font.name = "Times New Roman"
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    st.font.size = Pt(size)
    st.font.bold = True
    st.font.color.rgb = RGBColor(0, 0, 0)
    # The default template sets theme fonts (Calibri) that override the font
    # name above; remove them so Times New Roman applies.
    rfonts = st.element.rPr.rFonts
    for attr in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
        rfonts.attrib.pop(qn(attr), None)
    rfonts.set(qn("w:ascii"), "Times New Roman")
    rfonts.set(qn("w:hAnsi"), "Times New Roman")
    # Chapters start on a new page through the style, not an explicit break:
    # an explicit break after a chapter that ends at the foot of a page
    # leaves a blank page.
    st.paragraph_format.page_break_before = level == 1
    st.paragraph_format.space_before = Pt(18 if level == 1 else 12)
    st.paragraph_format.space_after = Pt(6)
    st.paragraph_format.keep_with_next = True

cap = doc.styles["Caption"]
cap.font.name = "Times New Roman"
cap.font.size = Pt(10)
cap.font.italic = False
cap.font.bold = True
cap.font.color.rgb = RGBColor(0, 0, 0)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def runs(par, text):
    """Adds text with **bold** and `code` spans."""
    for part in re.split(r"(\*\*[^*]+\*\*|`[^`]+`)", text):
        if not part:
            continue
        if part.startswith("**"):
            par.add_run(part[2:-2]).bold = True
        elif part.startswith("`"):
            r = par.add_run(part[1:-1])
            r.font.name = "Consolas"
            r.font.size = Pt(10.5)
        else:
            par.add_run(part)
    return par


def P(text, align=WD_ALIGN_PARAGRAPH.JUSTIFY):
    par = doc.add_paragraph()
    par.alignment = align
    return runs(par, text)


def bullets(items, style="List Bullet"):
    for it in items:
        par = doc.add_paragraph(style=style)
        par.paragraph_format.space_after = Pt(3)
        runs(par, it)


def H(text, level=1):
    return doc.add_heading(text, level=level)


def caption(text):
    par = doc.add_paragraph(style="Caption")
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    par.add_run(text)
    return par


def figure(path, title, width=TEXT_WIDTH):
    global fig_no
    fig_no += 1
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    par.paragraph_format.keep_with_next = True
    par.add_run().add_picture(str(path), width=width)
    caption(f"Figure {fig_no}: {title}")
    return fig_no


def shade(cell, hex_fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tcPr.append(shd)


def table(title, header, rows, widths=None, size=10):
    global tab_no
    tab_no += 1
    c = caption(f"Table {tab_no}: {title}")
    c.paragraph_format.keep_with_next = True
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(header):
        cell = t.rows[0].cells[i]
        cell.text = ""
        r = cell.paragraphs[0].add_run(h)
        r.bold = True
        r.font.size = Pt(size)
        shade(cell, "D9E2F3")
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            runs(cells[i].paragraphs[0], str(v))
            for r in cells[i].paragraphs[0].runs:
                r.font.size = Pt(size)
    for row in t.rows:
        for cell in row.cells:
            cell.paragraphs[0].paragraph_format.space_after = Pt(0)
            cell.paragraphs[0].paragraph_format.line_spacing = 1.0
            cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.LEFT
    # Repeat the header row on every page the table spans.
    trPr = t.rows[0]._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    trPr.append(el)
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Cm(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return tab_no


def code(text, size=7.5):
    lines = text.rstrip("\n").split("\n")
    for n, line in enumerate(lines):
        par = doc.add_paragraph()
        # Keep a listing in one piece (Word still splits one longer than a page).
        par.paragraph_format.keep_with_next = n < len(lines) - 1
        par.paragraph_format.space_after = Pt(0)
        par.paragraph_format.line_spacing = 1.0
        r = par.add_run(line.replace("\t", "    ") or " ")
        r.font.name = "Consolas"
        r.font.size = Pt(size)
        pPr = par._p.get_or_add_pPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), "F2F2F2")
        pPr.append(shd)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def field(par, instr):
    """Inserts a Word field (TOC, PAGE); Word fills it in when fields are updated."""
    r = par.add_run()
    for tag, text in (("begin", None), ("instr", instr), ("separate", None), ("text", "(updated when the document is opened in Word)"), ("end", None)):
        if tag == "instr":
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = text
            r._r.append(el)
        elif tag == "text":
            t = OxmlElement("w:t")
            t.text = text
            r._r.append(t)
        else:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), tag)
            r._r.append(el)


def page_break():
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def extract(path, start, end_pattern, include_end=True):
    """Lines of a source file from the line containing `start` to the first later
    line matching `end_pattern`, with the file's real line numbers."""
    lines = (ROOT / path).read_text(encoding="utf-8").split("\n")
    i = next(n for n, l in enumerate(lines) if start in l)
    j = next(n for n in range(i + 1, len(lines)) if re.search(end_pattern, lines[n]))
    if not include_end:
        j -= 1
        while not lines[j].strip():
            j -= 1
    width = len(str(j + 1))
    body = "\n".join(f"{n + 1:>{width}}  {lines[n]}" for n in range(i, j + 1))
    return body, i + 1, j + 1


# --------------------------------------------------------------------------
# Title page
# --------------------------------------------------------------------------
for _ in range(3):
    doc.add_paragraph()
t = doc.add_paragraph(); t.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = t.add_run("PlaceIQ"); r.bold = True; r.font.size = Pt(28)
t = doc.add_paragraph(); t.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = t.add_run("A College Placement Management System"); r.bold = True; r.font.size = Pt(18)
t = doc.add_paragraph(); t.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = t.add_run("with database-enforced placement rules, analytics and a placement-probability model")
r.italic = True; r.font.size = Pt(13)
for _ in range(2):
    doc.add_paragraph()
t = doc.add_paragraph(); t.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = t.add_run("Database Management Systems: Digital Assignment 3 (Project Report)"); r.font.size = Pt(13)
t = doc.add_paragraph(); t.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = t.add_run("[Course Code] – [Course Name]"); r.font.size = Pt(13)
for _ in range(2):
    doc.add_paragraph()
t = doc.add_paragraph(); t.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = t.add_run("Submitted by"); r.bold = True
tt = doc.add_table(rows=3, cols=2)
tt.alignment = WD_TABLE_ALIGNMENT.CENTER
for i, (a, b) in enumerate((("Name", "Register Number"), ("[Student Name 1]", "[Register Number 1]"), ("[Student Name 2]", "[Register Number 2]"))):
    for j, v in enumerate((a, b)):
        cell = tt.rows[i].cells[j]
        cell.text = ""
        cell.width = Cm(6)
        rr = cell.paragraphs[0].add_run(v)
        rr.bold = i == 0
        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
doc.add_paragraph()
t = doc.add_paragraph(); t.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = t.add_run("Under the guidance of"); r.bold = True
t = doc.add_paragraph(); t.alignment = WD_ALIGN_PARAGRAPH.CENTER
t.add_run("[Faculty Name]\n[Designation, School / Department]")
for _ in range(2):
    doc.add_paragraph()
t = doc.add_paragraph(); t.alignment = WD_ALIGN_PARAGRAPH.CENTER
t.add_run("[Institution Name]\n[Date of Submission]")

# Everything after the title page is a new section, so the title page can
# carry no page number while the rest are numbered from 1.
body = doc.add_section(WD_SECTION.NEW_PAGE)
body.footer.is_linked_to_previous = False
fp = body.footer.paragraphs[0]
fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
field(fp, "PAGE")
pgNumType = OxmlElement("w:pgNumType")
pgNumType.set(qn("w:start"), "1")
body._sectPr.append(pgNumType)

# --------------------------------------------------------------------------
# Abstract
# --------------------------------------------------------------------------
H("Abstract", 1)
P("Campus placement in most colleges is still coordinated through spreadsheets, forms and e-mail, so "
  "the rules that matter most (who is eligible for a drive, whether a student may hold two accepted "
  "offers, which status changes are legal) live in people's heads or in scattered application code. "
  "This project, PlaceIQ, is a placement management system whose central design decision is to "
  "enforce those rules **inside the database**. A PostgreSQL 16 schema of 13 tables in third normal form "
  "carries six triggers, two stored functions, one stored procedure, six views (three of them built on "
  "window functions) and a materialized view. Invalid writes are refused by the database itself with "
  "custom error codes (PL001–PL007), whether they come from the web application or from a raw SQL "
  "session. A Flask backend written with plain SQL (psycopg2, no ORM) exposes 36 REST endpoints, runs offer "
  "acceptance as an explicit transaction, and serves a React front end with a student portal, an admin "
  "console and an analytics dashboard. A logistic-regression model estimates each student's placement "
  "probability. The schema was also ported to Oracle 21c and run end to end in SQL*Plus.")
P("On a synthetic dataset of 180 students, 25 drives and 517 applications, an end-to-end smoke test "
  "passed 41 of 41 checks, an automated check of the API documentation passed 161 of 161, and a browser "
  "walkthrough of the user interface passed 28 of 28. Every business rule was shown to be refused at the "
  "database level, including two simultaneous offer acceptances, which the trigger's row lock serialized. "
  "On a 250,000-application benchmark database the indexes cut query time by between 1.8× and 81×. The "
  "placement model reached a test accuracy of 0.750 and a ROC-AUC of 0.774, but on a test set of only 36 "
  "synthetic students, so it demonstrates the pipeline rather than real predictive power.")
P("**Keywords:** relational database, triggers, stored procedures, transactions, window functions, "
  "materialized views, indexing, placement management, logistic regression.")
page_break()  # the TOC title is not a heading, so it needs its own break

# --------------------------------------------------------------------------
# Table of contents
# --------------------------------------------------------------------------
t = doc.add_paragraph(); r = t.add_run("Table of Contents"); r.bold = True; r.font.size = Pt(16)
field(doc.add_paragraph(), 'TOC \\o "1-2" \\h \\z \\u')

# --------------------------------------------------------------------------
# 1 Introduction
# --------------------------------------------------------------------------
H("1  Introduction", 1)
P("Every placement season a college's training and placement office (TPO) runs dozens of recruitment "
  "drives. Each drive has its own eligibility rules (a minimum CGPA, a maximum number of active backlogs, "
  "the branches it is open to), and each applicant moves through a pipeline of shortlisting, interview "
  "rounds and offers. The office has to answer two kinds of question at once: operational ones (\"who "
  "is eligible for this drive?\", \"which applicants are still pending?\") and analytical ones "
  "(\"what share of each department has been placed?\", \"which recruiters made the most offers?\").")
P("PlaceIQ is a web-based system for this workflow, built for the DA-3 project of the Database Management "
  "Systems course. Its emphasis is the database: the schema, the rules it enforces, the queries behind "
  "the analytics, and the transactions that keep related tables consistent.")

H("1.1  Literature Review", 2)
P("**The relational model and normalization.** Codd's relational model [1] proposed representing data as "
  "relations and introduced a normal form for them, separating how data is logically organized from how it "
  "is stored. Normalization to third normal form, as presented in standard texts such as Silberschatz, "
  "Korth and Sudarshan [3], removes partial and transitive dependencies so that each fact is stored once. "
  "PlaceIQ's schema follows this: department and company details are kept in their own tables instead of "
  "being copied onto every student and drive row.")
P("**Transactions.** Härder and Reuter [2] set out the terminology of transaction-oriented recovery and "
  "the properties now known as ACID: atomicity, consistency, isolation and durability. Accepting an offer "
  "in PlaceIQ updates three tables, and atomicity is what guarantees they never disagree. PostgreSQL's "
  "documentation describes how its transactions [10] and row-level locks [11] provide these guarantees in "
  "practice, and how trigger functions [8] can enforce rules on every write.")
P("**Existing placement management systems.** Santhosh Kumar and Srividhya [7] describe a web application "
  "that automates registration, record updates, searching and notifications for an engineering college's "
  "training and placement unit. Systems of this kind digitize the office's records, but the rules are "
  "typically checked in application code, which a direct database edit or a second client can bypass.")
P("**Predicting placement.** Several studies predict whether a student will be placed from academic "
  "records. Shukla et al. [5] built a logistic-regression model that estimates a student's placement "
  "probability from historical data with known outcomes. Kumar et al. [6] compared several machine-learning "
  "methods on students' academic performance and found Random Forest the most effective. PlaceIQ uses "
  "logistic regression, implemented with scikit-learn [4], because its coefficients can be read directly "
  "and explained to a student. The prediction is a supporting feature here, not the focus.")
P("**Gap addressed.** The reviewed placement systems treat the database mainly as storage. PlaceIQ moves "
  "the placement rules into the database (triggers and stored routines), adds analytics computed with window "
  "functions and a materialized view, and measures the effect of its indexes instead of assuming it.")

H("1.2  Problem Statement", 2)
P("Design and implement a placement management system in which the placement office's rules are "
  "guaranteed by the database, so that no client (the web application, an admin's SQL session or a "
  "future integration) can create an inconsistent state. Examples of such states are an ineligible "
  "application, two accepted offers for one student, an offer for a rejected applicant, or an application "
  "moving backwards in the pipeline. The system must also give students and the placement office the "
  "operational and analytical views they need, and its design choices (normalization, indexing, "
  "transactions) must be justified with measured evidence.")

H("1.3  Objectives", 2)
bullets([
    "Design a normalized (3NF) relational schema for students, departments, skills, companies, drives, "
    "applications, interview rounds and offers, with an audit trail of status changes.",
    "Enforce the placement rules in the database with triggers, a stored function for eligibility and a "
    "stored procedure for closing a drive, each failing with a distinct error code.",
    "Implement offer acceptance and decline as explicit transactions, and show that they are atomic and "
    "safe under concurrent requests.",
    "Provide analytics through views, window functions and a materialized view, and present them in a "
    "web dashboard.",
    "Measure the effect of the indexes with EXPLAIN ANALYZE on a realistically sized dataset.",
    "Integrate a small, explainable placement-probability model and report its accuracy honestly.",
    "Port the database layer to Oracle and run it end to end in SQL*Plus.",
])

H("1.4  Scope", 2)
P("**In scope:**")
bullets([
    "Two roles: a student (register, view eligible drives, apply, track applications, accept or decline "
    "offers) and the placement officer (manage drives, move applicants through the pipeline, record interview "
    "rounds and offers, close drives, view analytics).",
    "The PostgreSQL schema, the Flask REST API, the React user interface, the ML service, and the Oracle "
    "port of the schema.",
])
P("**Out of scope:**")
bullets([
    "Real student data and any connection to an institution's academic systems. All data is synthetic, and "
    "CGPA is entered by the student at sign-up.",
    "E-mail or SMS notifications, document uploads (resumes, offer letters) and recruiter logins.",
    "Running the backend against Oracle: the Oracle port covers the database layer only.",
])

# --------------------------------------------------------------------------
# 2 Modules
# --------------------------------------------------------------------------
H("2  Modules (Implementation and Experimental Setup)", 1)

H("2.1  System Architecture", 2)
P("PlaceIQ is a three-tier web application with a separate prediction service (Table 1). The browser "
  "talks only to the backend. The backend talks to PostgreSQL with plain SQL through a connection pool "
  "and calls the ML service over HTTP when a student asks for their placement probability.")
table("Components and technologies", ["Tier", "Technology", "Responsibility"], [
    ["Presentation", "React 19, React Router 7, Vite 8", "Student portal, placement-office console, analytics dashboard (charts drawn as SVG)"],
    ["Application", "Python, Flask 3.0, psycopg2 (no ORM), PyJWT, bcrypt", "36 REST endpoints, authentication, role checks, offer transactions"],
    ["Data", "PostgreSQL 16 (Docker)", "13 tables, 6 triggers, 2 functions, 1 procedure, 6 views, 1 materialized view"],
    ["Prediction", "Flask, scikit-learn, pandas", "Trains the model from the database and serves POST /predict"],
    ["Oracle port", "Oracle Database 21c XE, SQL*Plus", "The same schema and rules in PL/SQL"],
], widths=[3, 5.5, 7.5])
P("The backend deliberately uses raw SQL rather than an object-relational mapper. Every query the system "
  "runs is visible in the source, which matters for a database course. It also means the transaction "
  "boundaries are explicit `commit()` and `rollback()` calls rather than behaviour hidden inside a framework.")

H("2.2  Database Design", 2)
P("Figure 1 shows the entity–relationship diagram of the 13 tables, rendered from the Mermaid source in "
  "`docs/er-diagram.md`. The central entity is `application`, which resolves the many-to-many relationship "
  "between students and drives and carries its own attributes (status and application time). Two further "
  "junction tables resolve students↔skills and drives↔eligible departments. A drive with no rows in "
  "`drive_eligible_dept` is open to every department.")
figure(EVID / "er-diagram.png", "Entity–relationship diagram (13 tables)")
table("Tables", ["Table", "Purpose", "Key constraints"], [
    ["department", "The six branches", "UNIQUE name and code"],
    ["coordinator", "Placement-office users (TPO / coordinator)", "UNIQUE e-mail; CHECK role"],
    ["student", "Profile, CGPA, backlogs, placement status", "UNIQUE reg. no. and e-mail; CHECK 0 ≤ CGPA ≤ 10; FK department"],
    ["skill, student_skill", "Skills and who holds them (M:N)", "Composite PK (student, skill)"],
    ["company", "Recruiters", "UNIQUE name"],
    ["drive", "One recruitment posting with its cutoffs", "FK company, coordinator; CHECK status, type"],
    ["drive_eligible_dept", "Branches a drive is open to (M:N)", "Composite PK (drive, department)"],
    ["application", "A student's application to a drive", "UNIQUE (student, drive); CHECK status"],
    ["interview_round", "Rounds of one application", "UNIQUE (application, round no.)"],
    ["offer", "At most one offer per application", "UNIQUE application; CHECK status"],
    ["offer_history", "Audit log of offer events", "CHECK action"],
    ["application_status_history", "Audit log of status changes (written by a trigger)", "FK application"],
], widths=[4, 6.5, 5.5])
P("All 13 tables are in third normal form: every non-key attribute depends on the whole key and on "
  "nothing else. The one deliberate exception is `student.placement_status`, which could be derived from the "
  "offers. It is stored because it is read on almost every page, and a trigger keeps it in step with the "
  "offer table, so it cannot drift. The full functional-dependency analysis is in `docs/normalization.md`, "
  "and every column and constraint, read from the system catalog, is in `docs/evidence/schema-summary.md`.")

H("2.3  Database Logic: Triggers, Routines and Views", 2)
P("The placement rules are implemented as BEFORE triggers that inspect the row being written and raise an "
  "error with a custom SQLSTATE code if it breaks a rule (Table 3). Because the check runs inside the "
  "database, it applies to every client. The backend translates each code into an HTTP status "
  "(`backend/utils/db_errors.py`), so the user sees a meaningful message rather than a generic failure.")
table("Database-enforced rules", ["Code", "Trigger / routine", "Rule", "HTTP"], [
    ["PL001", "trg_application_before_insert", "A student may apply only if eligible (CGPA, backlogs, branch)", "403"],
    ["PL002", "trg_application_before_insert", "Applications are accepted only while a drive is Upcoming or Ongoing", "409"],
    ["PL003", "trg_offer_before_accept", "A student may hold at most one Accepted offer", "409"],
    ["PL004", "sp_close_drive", "The drive to close must exist", "404"],
    ["PL005", "sp_close_drive", "A drive can be closed only once", "409"],
    ["PL006", "trg_offer_requires_selected", "An offer can be recorded only for a Selected application", "409"],
    ["PL007", "trg_application_status_transition", "Applications move only forward through the pipeline", "409"],
], widths=[1.6, 5.4, 7.4, 1.6])
P("The legal status transitions form a small state machine: Applied → Shortlisted / Interview_Scheduled / "
  "Rejected; Shortlisted → Interview_Scheduled / Selected / Rejected; Interview_Scheduled → Selected / "
  "Rejected; Selected → Offer_Made / Rejected. Offer_Made and Rejected are final. A CHECK constraint cannot "
  "express this rule because it sees only the new value. The trigger compares `OLD.status` with `NEW.status`.")
P("Two AFTER triggers maintain derived data. `trg_offer_after_insert` marks a student Placed when an offer "
  "is recorded. `trg_application_status_audit` writes one `application_status_history` row for every status "
  "change, so no code path can change a status without leaving a record.")
P("**Rule PL003 and concurrency.** If two requests accept two different offers of the same student at the "
  "same moment, neither can see the other's uncommitted change, and a naive count of Accepted offers "
  "would let both through. The trigger therefore first locks the student's row with `SELECT ... FOR UPDATE`, "
  "so the second request waits until the first commits and then sees its result (Section 3.3).")
P("**Stored routines.** `fn_check_eligibility(student, drive)` returns whether a student meets a drive's "
  "rules. It is the single definition of eligibility, used by the application trigger and by "
  "`fn_get_eligible_drives(student)`, which returns every open drive a student qualifies for. The procedure "
  "`sp_close_drive(drive, INOUT rejected_count)` rejects every still-pending applicant and marks the drive "
  "Completed as one unit of work.")
P("**Views.** Three views serve the dashboards (`placed_students_view`, `company_wise_stats_view`, "
  "`department_stats_view`). Three more use window functions: `dept_offer_ranking_view` ranks offers within "
  "each department with `RANK()`; `placement_timeline_view` computes a running total with `SUM(...) OVER` "
  "and the month-on-month change with `LAG()`; `student_cgpa_standing_view` uses `DENSE_RANK()` and "
  "`PERCENT_RANK()` for each student's position within their department [9]. The materialized view "
  "`mv_company_dept_placements` stores offers per company and department. It is refreshed on demand with "
  "`REFRESH MATERIALIZED VIEW CONCURRENTLY`, which needs a unique index and lets readers continue during "
  "the refresh [12], and the dashboard shows when it was last refreshed.")
P("**Indexes.** Besides the indexes created by primary-key and unique constraints, five indexes support "
  "the frequent lookups: `student(dept_id)`, `student(cgpa)`, `application(status)`, `application(drive_id)` "
  "and `drive(company_id)` [13]. Their effect is measured in Section 3.5.")

H("2.4  Backend API Module", 2)
P("The Flask backend is organized in blueprints (authentication, students, drives, applications, offers, "
  "analytics) and exposes 36 endpoints, each documented in `docs/API.md`. Users authenticate with e-mail and a "
  "bcrypt-hashed password and receive a JSON Web Token [14] that carries their role. Every endpoint checks the "
  "role, and students can read and change only their own records. Database access goes through a psycopg2 "
  "connection pool [15], with parameterized queries throughout.")
P("**The offer transaction.** Accepting an offer must update three things together: the offer becomes "
  "Accepted with a joining date, the student is marked Placed, and an Accepted row is appended to "
  "`offer_history`. `offer_service.accept_offer` runs the three statements on one connection inside "
  "`try`, calls `commit()` only after all three succeed, and calls `rollback()` if any statement fails, "
  "including when a trigger refuses it. Declining works the same way, and it also sets the student back to Not "
  "Placed if no other live offer remains. The full function is listed in Appendix A.")

H("2.5  User Interface Module", 2)
P("The React front end has three areas. Students see an overview (profile, CGPA standing in their "
  "department, placement probability), their eligible drives, and their applications. The application "
  "detail shows interview rounds, the offer and the status history written by the audit trigger "
  "(Figure 2). The placement office manages drives and applicants (Figure 3) and sees an analytics "
  "dashboard (Section 3.4). Every chart also has a table view, so no value is available only by hovering.")
figure(SHOTS / "06-application-detail.png", "Application detail: offer, interview rounds and the status history recorded by the audit trigger", width=Cm(13))
figure(SHOTS / "08-drive-detail-applicants.png", "Placement office: a drive's details and its applicants", width=Cm(15.5))

H("2.6  Placement-Probability Module", 2)
P("A separate service trains a scikit-learn [4] pipeline: standardized numeric features, a one-hot encoded "
  "department, and a logistic-regression classifier. The features are CGPA, number of active backlogs, "
  "number of skills (counted with a join on `student_skill`) and department. The label is "
  "`placement_status`, which the database trigger sets. The data is split 80/20, stratified by label, with a "
  "fixed random seed. The trained model is saved to disk and served by `POST /predict`. The backend calls "
  "it for the logged-in student and returns HTTP 503 if the service is unavailable.")

H("2.7  Oracle Port", 2)
P("The schema was ported to Oracle Database 21c Express Edition (`db/schema_oracle.sql`) and run end to end "
  "in a single SQL*Plus session (`db/oracle_full_run.sql`). The main differences are:")
bullets([
    "Identity columns are implemented with sequences and BEFORE INSERT triggers.",
    "Rule violations are raised with `RAISE_APPLICATION_ERROR` (−20001 to −20007) instead of custom SQLSTATEs.",
    "The materialized view is built `REFRESH COMPLETE ON DEMAND`.",
    "Identifiers are shortened to Oracle's 30-character limit.",
    "Rule PL003 is a COMPOUND trigger [16]. A row-level trigger on `offer` cannot query `offer` itself "
    "(ORA-04091, \"table is mutating\"), so the compound trigger collects the affected rows and checks them "
    "after the statement.",
])
P("The differences are documented line by line in `docs/oracle-differences.md`.")

H("2.8  Experimental Setup", 2)
table("Environment", ["Item", "Value"], [
    ["Machine", "12th Gen Intel Core i7-12700H, 15.6 GB RAM, Windows 11"],
    ["Database", "PostgreSQL 16.15 in Docker (postgres:16 image)"],
    ["Oracle", "Oracle Database 21c XE (gvenzl/oracle-xe:21-slim) with SQL*Plus 21.3"],
    ["Backend / ML", "Python 3.14, Flask 3.0.3, psycopg2 2.9, scikit-learn 1.5+"],
    ["Front end", "React 19, Vite 8, tested in headless Chromium (Playwright)"],
], widths=[3.5, 12.5])
P("**Dataset.** No real student data was used. `db/seed.py` generates a deterministic synthetic dataset: "
  "180 students (30 in each of six departments), 18 companies, 25 drives, 517 applications and 177 offers, "
  "after which 95 students (52.8%) are Placed. The seed moves every application through legal status steps, "
  "so the audit trigger logged 1,177 status changes. Offers are made with a probability that rises with "
  "CGPA margin and skill count and falls with backlogs, so the dataset has a learnable signal.")
P("**Tests and measurements.**")
bullets([
    "**Smoke test** (`tests/smoke_test.py`): 41 checks through the API and directly against the "
    "database. It runs on a throwaway copy of the database, built and dropped by `tests/run_smoke_test.sh`.",
    "**API contract check** (`tests/api_contract_check.py`): parses `docs/API.md` and calls every "
    "documented endpoint, comparing status codes and response fields.",
    "**UI walkthrough** (`tests/ui_walkthrough.js`): Playwright drives the real interface through each flow.",
    "**Index benchmark** (`db/demos/index_benchmark.py`): a separate database of 50,000 students, 2,000 drives "
    "and 250,000 applications. Each query's median time over 7 warm runs is measured with and without the indexes.",
    "**SQL evidence**: every query, trigger and transaction was run in psql. Anything that changed data ran "
    "inside a transaction that was rolled back. The unedited output is in `docs/evidence/`.",
])

# --------------------------------------------------------------------------
# 3 Results and Discussion
# --------------------------------------------------------------------------
H("3  Results and Discussion", 1)
P("All figures in this chapter are copied from the evidence files in `docs/evidence/` (listed in "
  "`docs/evidence/INDEX.md`). Each file holds the unedited output of the run it describes.")

H("3.1  Functional Verification", 2)
table("Verification results", ["Check", "Result", "Evidence"], [
    ["End-to-end smoke test (API and database)", "41 / 41 passed", "smoke-test.md"],
    ["API documentation vs. running backend (36 endpoints)", "161 / 161 passed", "raw/api-contract-check.txt"],
    ["Browser walkthrough of the UI", "28 / 28 passed", "raw/ui-walkthrough.txt"],
    ["Oracle schema in SQL*Plus", "82 objects, all VALID; no compilation errors", "sqlplus-transcript.txt"],
    ["Oracle rule triggers", "All 6 intended ORA-200xx errors raised, no others", "sqlplus-transcript.txt"],
], widths=[7, 5, 4])

H("3.2  Rules Enforced by the Database", 2)
P("Each rule was tested by sending a violating statement straight to PostgreSQL, bypassing the backend "
  "(`triggers.md`). Table 6 lists what was run and what the database answered. Each refused write left no "
  "row behind. For example, after the PL006 attempt, application 1 still had 0 offers.")
table("Rule violations sent directly to the database", ["Statement (summary)", "Database response", "Code"], [
    ["Student 8 (CGPA below cutoff) applies to drive 1", "Student 8 is not eligible for drive 1", "PL001"],
    ["A student applies to drive 2, which is Completed", "Drive 2 is Completed and no longer accepts applications", "PL002"],
    ["Student 18, who already accepted an offer, accepts offer 70", "Student 18 has already accepted another offer", "PL003"],
    ["Insert an offer for application 1 (Rejected)", "Application 1 is Rejected; an offer can only be recorded for a Selected application", "PL006"],
    ["Move application 1 from Rejected to Applied", "Application 1 cannot move from Rejected to Applied", "PL007"],
    ["Move application 2 from Offer_Made to Shortlisted", "Application 2 cannot move from Offer_Made to Shortlisted", "PL007"],
], widths=[6.5, 7.5, 2])
P("The function `fn_check_eligibility` was checked against an independently computed reason for four real "
  "student–drive pairs (`queries.md`). It returned true for the pair meeting every rule. It returned false "
  "for a CGPA of 7.99 against a cutoff of 8.25, for 2 backlogs against a maximum of 1, and for a CSE student "
  "applying to a drive open only to AIML and ECE. Calling `sp_close_drive` on drive 24 (Brightwave BPO, Full "
  "Stack Developer) rejected its 37 pending applicants (27 Applied, 5 Shortlisted, 5 Interview_Scheduled) and "
  "marked it Completed, and the audit trigger logged all 37 changes. The demonstration was then rolled back, "
  "and the drive was again Ongoing.")

H("3.3  Transactions and Concurrency", 2)
P("The offer transactions were run through the real backend with the database state read before and after "
  "each call (`transaction.md`):")
bullets([
    "**Accept**: offer 178 went from Pending to Accepted with a joining date of 2026-12-20, and the history "
    "went from [Created] to [Created, Accepted] in one request.",
    "**Decline** of a student's only offer: the offer became Declined and `placement_status` returned from "
    "Placed to Not Placed, together with the history row.",
    "**Refused acceptance** (PL003): the backend answered HTTP 409, and the before and after states were "
    "identical. The transaction left nothing behind.",
    "**Two simultaneous acceptances** from two database connections: connection B was still blocked on the "
    "student-row lock 1.5 s later. When A committed, B was immediately refused with PL003. Offer 180 ended "
    "Accepted and offer 181 stayed Pending, exactly one acceptance.",
])
P("At the SQL level (`transaction-sql.md`), the same three statements were run by hand and then rolled back, "
  "and all three changes disappeared together. In a second run a CHECK-constraint violation in the third "
  "statement aborted the transaction: PostgreSQL refused every following statement, the final COMMIT became "
  "a rollback, and the first two updates were undone. This is atomicity in practice [2], [10].")

H("3.4  Placement Analytics", 2)
P("Table 7 is the output of `department_stats_view` on the seeded data. Electrical & Electronics has the "
  "highest placement rate (60.0%) and Computer Science the lowest (43.3%). Because the data is synthetic, "
  "these figures describe the generator's choices, not any real college.")
table("Placement by department (department_stats_view)", ["Department", "Students", "Placed", "Placed %"], [
    ["Electrical & Electronics", "30", "18", "60.00"],
    ["Artificial Intelligence & ML", "30", "17", "56.67"],
    ["Information Science Engineering", "30", "16", "53.33"],
    ["Electronics & Communication", "30", "16", "53.33"],
    ["Mechanical Engineering", "30", "15", "50.00"],
    ["Computer Science Engineering", "30", "13", "43.33"],
], widths=[7, 3, 3, 3])
table("Top recruiters by offers (company_wise_stats_view)", ["Company", "Offers", "Average package (LPA)"], [
    ["Coral Bay Solutions", "80", "6.89"],
    ["Everstone Infra", "41", "7.14"],
    ["Solstice Retail Tech", "24", "5.51"],
    ["Bluepeak Software", "8", "14.62"],
    ["Meridian Consulting", "8", "10.14"],
], widths=[7, 3, 6])
P("Offers per month (from `placement_timeline_view`) were 3, 7, 1, 36, 114, 0 and 16 for August 2025 to "
  "February 2026, a running total of 177 (Figure 5). Capturing this screen exposed a defect. The first "
  "version of the view only had rows for months with offers, so `LAG()` compared February with December, "
  "because January had no offers, and reported a fall of 98. The view now generates every month between "
  "the first and last offer (`generate_series` in PostgreSQL, `ADD_MONTHS` with `CONNECT BY LEVEL` in Oracle) "
  "and left-joins the counts, so January appears as 0 and February's change is +16. The fix was re-verified "
  "on both databases. It shows a general pitfall of `LAG()`: it reads the previous row, not the previous "
  "calendar period.")
figure(SHOTS / "10-analytics-overview.png", "Analytics: placement % by department and CGPA against placement outcome", width=Cm(15.5))
figure(SHOTS / "13-analytics-timeline.png", "Offers per month and running total, from the window-function view", width=Cm(15.5))
figure(SHOTS / "14-analytics-matrix.png", "Offers by company and department, read from the materialized view", width=Cm(15.5))

H("3.5  Effect of the Indexes", 2)
P("Table 9 gives the median execution time of five of the application's lookups on the 250,000-application "
  "benchmark database, with and without the indexes (`index-benchmark.md`, which also contains every query "
  "plan).")
table("Index benchmark (median of 7 warm runs)", ["Query", "Index used", "With", "Without", "Speed-up"], [
    ["Applicants for one drive", "idx_application_drive", "0.13 ms", "10.31 ms", "81.2×"],
    ["CSE students with CGPA ≥ 9.7", "idx_student_cgpa + idx_student_dept", "0.62 ms", "6.15 ms", "9.9×"],
    ["Count of students in one department", "idx_student_dept", "2.08 ms", "7.20 ms", "3.5×"],
    ["Count of applications in one status", "idx_application_status", "4.56 ms", "13.23 ms", "2.9×"],
    ["Drives of one company", "idx_drive_company", "0.07 ms", "0.12 ms", "1.8×"],
], widths=[4.6, 4.6, 2.1, 2.3, 2.4])
P("The gain depends on selectivity. Listing one drive's applicants touches 125 of 250,000 rows. Through the "
  "index PostgreSQL read 127 buffer pages instead of scanning all 1,966, an 81× speed-up. For the CGPA and "
  "department query the planner combined two indexes with a `BitmapAnd` before reading the table. A filter "
  "that matches a sixth of the students (one department) or 3% of the applications (one status) still has to "
  "visit most pages, so the gain is smaller. The `drive.company_id` index barely helps (0.07 vs 0.12 ms) "
  "because the whole `drive` table is 27 pages. It is kept for the drive-to-company join, but the "
  "measurement does not justify it on speed alone. On the real 180-student dataset none of the indexes "
  "matters, which is why the benchmark uses a separate, larger database.")

H("3.6  Placement-Probability Model", 2)
table("Model results on the held-out test set", ["Measure", "Value"], [
    ["Training / test rows", "144 / 36 (test: 19 placed, 17 not placed)"],
    ["Training accuracy", "0.875"],
    ["Test accuracy", "0.750 (27 of 36 correct)"],
    ["Test ROC-AUC", "0.774"],
    ["Precision / recall for 'placed'", "0.750 (15 of 20) / 0.789 (15 of 19)"],
    ["Confusion matrix (actual rows × predicted)", "Not placed: 12 correct, 5 wrong; Placed: 15 correct, 4 wrong"],
], widths=[6.5, 9.5])
P("The coefficients point the expected way. CGPA has the largest positive weight (+1.496 log-odds per "
  "standard deviation), backlogs the largest negative (−1.136), and the skill count is positive (+0.819). "
  "Department effects are smaller. Figure 7 shows the estimate as a student sees it.")
P("These results must be read with care. The test set has only 36 students, so one prediction changes "
  "accuracy by about 2.8 percentage points, and another random split could easily give 0.70 or 0.80. The data "
  "is synthetic, and the generator itself makes CGPA, backlogs and skills predictive, so the model largely "
  "recovers rules that were built in. The result shows that the pipeline works end to end (database, "
  "features, model, API, interface). It does not show that the model would predict real placements. "
  "For comparison, Kumar et al. [6] report Random Forest as the most effective of the methods they "
  "compared on real student records. Choosing a model on real data would need a comparison of that kind.")
figure(SHOTS / "03-probability-widget.png", "The placement-probability card on the student dashboard", width=Cm(10))

# --------------------------------------------------------------------------
# 4 Conclusion and Future Work
# --------------------------------------------------------------------------
H("4  Conclusion and Future Work", 1)
P("PlaceIQ shows that a placement office's rules can live in the database rather than in application "
  "code. Eligibility, the one-accepted-offer rule, offers only for selected applicants and forward-only "
  "status changes are all enforced by triggers, and each was shown to refuse a violating write sent "
  "directly to PostgreSQL. The offer transactions are atomic and remain correct under concurrent requests "
  "because the trigger locks the student's row. Window functions and a materialized view supply the "
  "analytics. The indexes were measured rather than assumed: up to 81× faster for selective lookups, "
  "and negligible on a tiny table. The same design runs on Oracle 21c with all 82 objects valid.")
H("Limitations", 3)
bullets([
    "**Synthetic data.** All students, companies and outcomes are generated. The analytics describe the "
    "generator, not a real college.",
    "**Self-reported CGPA.** Students enter their own CGPA and backlogs at sign-up, and eligibility depends on "
    "them. A real deployment would need these values verified against the institution's records through an "
    "official integration, not entered by the student.",
    "**Small ML evaluation.** The model was tested on 36 synthetic students with a single split. Its accuracy "
    "is a rough figure, and its strength largely reflects how the data was generated.",
    "**Oracle port covers the database layer only.** The backend runs only against PostgreSQL. Mapping "
    "Oracle's −20001 to −20007 errors in the backend and the Oracle date arithmetic in the offer service were "
    "not built. On Oracle, the concurrent-acceptance behaviour rests on documented locking and was not "
    "demonstrated, because the demo is a single SQL*Plus session. Oracle has no `CONCURRENTLY` refresh option.",
    "**Seeded timestamps.** The seed leaves application and status-history timestamps at the time it ran, so "
    "in the demo data an application can appear to be dated after its drive.",
    "**Placement policy.** A placed student may keep applying to other drives. Many colleges restrict this, "
    "and the rule would be one more trigger.",
])
H("Future Work", 3)
bullets([
    "Verify academic records through an official institutional data feed instead of self-reported values.",
    "Evaluate the model on real, consented and anonymized placement records with cross-validation, and "
    "compare it with other classifiers such as Random Forest [6].",
    "Add recruiter accounts, e-mail notifications and document uploads (resumes, offer letters).",
    "Make the placement policy configurable (for example, how many offers a placed student may hold) and "
    "enforce it with a trigger.",
    "Complete an Oracle-backed deployment of the backend and demonstrate concurrent acceptance there.",
    "Schedule the materialized-view refresh, or refresh it when offers change, instead of on demand only.",
])

# --------------------------------------------------------------------------
# References
# --------------------------------------------------------------------------
H("References", 1)
refs = [
    "E. F. Codd, \"A relational model of data for large shared data banks,\" Communications of the ACM, vol. 13, no. 6, pp. 377–387, 1970, doi: 10.1145/362384.362685.",
    "T. Härder and A. Reuter, \"Principles of transaction-oriented database recovery,\" ACM Computing Surveys, vol. 15, no. 4, pp. 287–317, 1983, doi: 10.1145/289.291.",
    "A. Silberschatz, H. F. Korth, and S. Sudarshan, Database System Concepts, 7th ed. New York: McGraw-Hill, 2019. [Online]. Available: https://www.db-book.com/",
    "F. Pedregosa et al., \"Scikit-learn: Machine learning in Python,\" Journal of Machine Learning Research, vol. 12, pp. 2825–2830, 2011. [Online]. Available: https://jmlr.org/papers/v12/pedregosa11a.html",
    "M. K. Shukla, P. Rambade, J. Torasakar, R. Prabhu, and D. Maste, \"Students placement prediction model using logistic regression,\" International Journal of Engineering Research & Technology (IJERT), ICIATE – 2017, vol. 5, no. 01, 2017. [Online]. Available: https://www.ijert.org/students-placement-prediction-model-using-logistic-regression",
    "M. Kumar, N. Walia, S. Bansal, G. Kumar, and K. Cengiz, \"Predicting college students' placements based on academic performance using machine learning approaches,\" International Journal of Modern Education and Computer Science, vol. 15, no. 6, pp. 1–13, 2023, doi: 10.5815/ijmecs.2023.06.01.",
    "H. Santhosh Kumar and V. R. Srividhya, \"Online training and placement management system,\" International Journal of Engineering Research & Technology (IJERT), ICACT – 2016, vol. 4, no. 22, 2016. [Online]. Available: https://www.ijert.org/online-training-and-placement-management-system",
    "The PostgreSQL Global Development Group, \"Trigger functions,\" PostgreSQL 16 Documentation, §43.10. [Online]. Available: https://www.postgresql.org/docs/16/plpgsql-trigger.html",
    "The PostgreSQL Global Development Group, \"Window functions,\" PostgreSQL 16 Documentation, §3.5. [Online]. Available: https://www.postgresql.org/docs/16/tutorial-window.html",
    "The PostgreSQL Global Development Group, \"Transactions,\" PostgreSQL 16 Documentation, §3.4. [Online]. Available: https://www.postgresql.org/docs/16/tutorial-transactions.html",
    "The PostgreSQL Global Development Group, \"Explicit locking,\" PostgreSQL 16 Documentation, §13.3. [Online]. Available: https://www.postgresql.org/docs/16/explicit-locking.html",
    "The PostgreSQL Global Development Group, \"Materialized views,\" PostgreSQL 16 Documentation, §41.3. [Online]. Available: https://www.postgresql.org/docs/16/rules-materializedviews.html",
    "The PostgreSQL Global Development Group, \"Using EXPLAIN,\" PostgreSQL 16 Documentation, §14.1. [Online]. Available: https://www.postgresql.org/docs/16/using-explain.html",
    "M. Jones, J. Bradley, and N. Sakimura, \"JSON Web Token (JWT),\" RFC 7519, Internet Engineering Task Force, 2015. [Online]. Available: https://www.rfc-editor.org/rfc/rfc7519",
    "Psycopg – PostgreSQL database adapter for Python, documentation. [Online]. Available: https://www.psycopg.org/docs/",
    "Oracle, \"PL/SQL triggers,\" Oracle Database PL/SQL Language Reference, 21c. [Online]. Available: https://docs.oracle.com/en/database/oracle/oracle-database/21/lnpls/plsql-triggers.html",
]
for i, ref in enumerate(refs, 1):
    par = doc.add_paragraph()
    par.paragraph_format.left_indent = Cm(1)
    par.paragraph_format.first_line_indent = Cm(-1)
    par.paragraph_format.space_after = Pt(4)
    par.add_run(f"[{i}]\t{ref}")

# --------------------------------------------------------------------------
# Appendix
# --------------------------------------------------------------------------
H("Appendix A  Code Listings", 1)
P("The listings below are read from the source files when this report is generated, with their real line "
  "numbers, so they match the submitted code exactly.")
listings = [
    ("A.1  Rule PL003: one accepted offer per student, with the row lock", "db/schema.sql",
     "CREATE OR REPLACE FUNCTION trg_fn_offer_single_acceptance", r"EXECUTE FUNCTION trg_fn_offer_single_acceptance", True, 0),
    ("A.2  Rule PL007: the status-transition state machine", "db/schema.sql",
     "CREATE OR REPLACE FUNCTION trg_fn_application_status_transition", r"EXECUTE FUNCTION trg_fn_application_status_transition", True, 0),
    ("A.3  Stored procedure sp_close_drive", "db/schema.sql",
     "CREATE OR REPLACE PROCEDURE sp_close_drive", r"^\$\$;", True, 0),
    ("A.4  Window-function view with the month series (placement_timeline_view)", "db/schema.sql",
     "CREATE VIEW placement_timeline_view", r"^LEFT JOIN monthly x", True, 0),
    ("A.5  The offer-acceptance transaction (backend)", "backend/services/offer_service.py",
     "def accept_offer", r"^def decline_offer", False, 0),
]
for title, path, start, end, inc, extra in listings:
    text, a, b = extract(path, start, end, inc)
    if extra:  # include the lines that finish the CREATE TRIGGER statement
        all_lines = (ROOT / path).read_text(encoding="utf-8").split("\n")
        width = len(str(b + extra))
        text = "\n".join(f"{n + 1:>{width}}  {all_lines[n]}" for n in range(a - 1, b + extra))
        b += extra
    H(title, 3)  # level 3: listed in the text, not in the table of contents
    P(f"`{path}`, lines {a}–{b}.", align=WD_ALIGN_PARAGRAPH.LEFT).paragraph_format.keep_with_next = True
    code(text)

H("Appendix B  Screenshots", 1)
for name, title in [
    ("01-login.png", "Sign-in page (student and placement-office roles)"),
    ("02-student-dashboard.png", "Student dashboard: profile, CGPA standing in the department, placement probability"),
    ("04-eligible-drives.png", "Eligible drives, from fn_get_eligible_drives"),
    ("05-application-tracker.png", "A student's applications at five different stages"),
    ("07-admin-dashboard.png", "Placement office: list of drives"),
    ("09-admin-students.png", "Placement office: student list"),
    ("11-analytics-recruiters.png", "Analytics: recruiters and packages"),
    ("12-analytics-rankings.png", "Analytics: top offers in each department (RANK)"),
]:
    figure(SHOTS / name, title, width=Cm(15.5))

H("Appendix C  Evidence Files", 1)
P("The `docs/evidence/` folder of the repository holds the unedited output behind every result in this "
  "report. Its index (`docs/evidence/INDEX.md`) lists each file, the report section it supports and the "
  "script that regenerates it. Among them are the SQL*Plus transcript of the Oracle run, the full EXPLAIN "
  "ANALYZE plans of the benchmark, and the schema summary read from the PostgreSQL catalog.")

# Mark the file as a current Word document (compatibility mode 15), so Word
# doesn't open it in "Compatibility Mode" for Word 2010.
settings = doc.settings.element
compat = settings.find(qn("w:compat"))
if compat is None:
    compat = OxmlElement("w:compat")
    settings.append(compat)
for old in compat.findall(qn("w:compatSetting")):
    if old.get(qn("w:name")) == "compatibilityMode":
        compat.remove(old)
cs = OxmlElement("w:compatSetting")
cs.set(qn("w:name"), "compatibilityMode")
cs.set(qn("w:uri"), "http://schemas.microsoft.com/office/word")
cs.set(qn("w:val"), "15")
compat.append(cs)

doc.save(OUT)
print(f"wrote {OUT.name}: {fig_no} figures, {tab_no} tables, {len(refs)} references")
