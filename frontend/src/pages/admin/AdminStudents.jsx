import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { useApi } from "../../hooks/useApi";
import { ApplicationDetailModal } from "../../components/ApplicationDetailModal";
import { Alert } from "../../components/ui/Alert";
import { DataTable } from "../../components/ui/DataTable";
import { Loading } from "../../components/ui/Feedback";
import { Card, PageHeader } from "../../components/ui/Layout";
import { Modal } from "../../components/ui/Modal";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { formatCgpa, formatDate, formatPercent } from "../../utils/format";

export function AdminStudents() {
  const departments = useApi("/departments");
  const [dept, setDept] = useState("");
  const [minCgpa, setMinCgpa] = useState("");
  const [placement, setPlacement] = useState("");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState(null);

  // Department, CGPA and placement filters run in the database (indexed
  // columns, see schema.sql Section 2); the name search is client-side.
  const query = new URLSearchParams();
  if (dept) query.set("dept_id", dept);
  if (minCgpa !== "" && !Number.isNaN(Number(minCgpa))) query.set("min_cgpa", minCgpa);
  if (placement) query.set("placement_status", placement);
  const students = useApi(`/students${query.toString() ? `?${query}` : ""}`);

  const rows = useMemo(() => {
    const term = search.trim().toLowerCase();
    return (students.data || []).filter(
      (s) => !term || s.name.toLowerCase().includes(term) || s.reg_no.toLowerCase().includes(term)
    );
  }, [students.data, search]);

  const placed = rows.filter((s) => s.placement_status === "Placed").length;

  return (
    <>
      <PageHeader
        eyebrow="Placement cell"
        title="Students"
        subtitle="Every registered student, with their eligibility details and placement status."
      />

      <Card
        title="Student register"
        subtitle={students.data ? `${rows.length} students shown · ${placed} placed` : undefined}
        flush
      >
        <div className="toolbar">
          <label className="search-box">
            <span className="sr-only">Search students</span>
            <Search size={16} aria-hidden="true" />
            <input className="input" placeholder="Search name or reg. no." value={search} onChange={(e) => setSearch(e.target.value)} />
          </label>
          <label>
            <span className="sr-only">Department</span>
            <select className="input" value={dept} onChange={(e) => setDept(e.target.value)}>
              <option value="">All departments</option>
              {(departments.data || []).map((d) => <option key={d.dept_id} value={d.dept_id}>{d.dept_code}</option>)}
            </select>
          </label>
          <label>
            <span className="sr-only">Minimum CGPA</span>
            <input className="input" style={{ width: 130 }} type="number" step="0.5" min="0" max="10" placeholder="Min CGPA" value={minCgpa} onChange={(e) => setMinCgpa(e.target.value)} />
          </label>
          <label>
            <span className="sr-only">Placement status</span>
            <select className="input" value={placement} onChange={(e) => setPlacement(e.target.value)}>
              <option value="">Placed and not placed</option>
              <option value="Placed">Placed</option>
              <option value="Not Placed">Not placed</option>
            </select>
          </label>
        </div>
        <DataTable
          caption="Students"
          loading={students.loading}
          error={students.error}
          rows={students.data ? rows : null}
          rowKey={(s) => s.student_id}
          onRowClick={(s) => setSelected(s.student_id)}
          emptyTitle="No students match these filters"
          columns={[
            { key: "name", header: "Student", render: (s) => (<><div>{s.name}</div><div className="cell-sub">{s.reg_no}</div></>) },
            { key: "dept", header: "Dept", render: (s) => s.dept_code },
            { key: "batch", header: "Batch", className: "num", render: (s) => s.batch_year },
            { key: "cgpa", header: "CGPA", className: "num", render: (s) => formatCgpa(s.cgpa) },
            { key: "backlogs", header: "Backlogs", className: "num", render: (s) => s.backlogs },
            { key: "status", header: "Placement", render: (s) => <StatusBadge status={s.placement_status} /> },
          ]}
        />
      </Card>

      <StudentProfileModal studentId={selected} onClose={() => setSelected(null)} />
    </>
  );
}

function StudentProfileModal({ studentId, onClose }) {
  const open = studentId !== null;
  const profile = useApi(open ? `/students/${studentId}` : null);
  const applications = useApi(open ? `/students/${studentId}/applications` : null);
  const prediction = useApi(open ? `/students/${studentId}/placement-probability` : null);
  const [openApp, setOpenApp] = useState(null);
  const p = profile.data;

  return (
    <>
      <Modal open={open && openApp === null} onClose={onClose} wide title={p ? p.name : "Student"} subtitle={p ? `${p.reg_no} · ${p.dept_name}` : undefined}>
        {profile.error && <Alert variant="error">{profile.error}</Alert>}
        {!p && !profile.error && <Loading />}
        {p && (
          <>
            <dl className="kv">
              <div><dt>CGPA</dt><dd>{formatCgpa(p.cgpa)}</dd></div>
              <div><dt>Backlogs</dt><dd>{p.backlogs}</dd></div>
              <div><dt>Placement</dt><dd><StatusBadge status={p.placement_status} /></dd></div>
              <div>
                <dt>CGPA rank in dept</dt>
                <dd>{p.cgpa_standing ? `${p.cgpa_standing.cgpa_rank_in_dept} of ${p.cgpa_standing.dept_size}` : "—"}</dd>
              </div>
              <div><dt>CGPA percentile</dt><dd>{p.cgpa_standing ? formatPercent(p.cgpa_standing.cgpa_percentile_in_dept) : "—"}</dd></div>
              <div>
                <dt>Predicted placement chance</dt>
                <dd>{prediction.data ? `${Math.round(prediction.data.placement_probability * 100)}%` : prediction.error ? "Unavailable" : "…"}</dd>
              </div>
              <div><dt>Email</dt><dd style={{ wordBreak: "break-all" }}>{p.email}</dd></div>
              <div><dt>Skills</dt><dd>{p.skills.map((s) => s.skill_name).join(", ") || "—"}</dd></div>
            </dl>

            <section>
              <h3 className="section-title">Applications ({applications.data?.length ?? 0})</h3>
              <div className="card">
                <DataTable
                  caption="Applications"
                  loading={applications.loading}
                  error={applications.error}
                  rows={applications.data}
                  rowKey={(a) => a.application_id}
                  onRowClick={(a) => setOpenApp(a.application_id)}
                  emptyTitle="No applications yet"
                  columns={[
                    { key: "c", header: "Company", render: (a) => (<><div>{a.company_name}</div><div className="cell-sub">{a.job_role}</div></>) },
                    { key: "d", header: "Applied", render: (a) => <span className="nowrap">{formatDate(a.applied_at)}</span> },
                    { key: "s", header: "Status", render: (a) => <StatusBadge status={a.status} /> },
                  ]}
                />
              </div>
            </section>
          </>
        )}
      </Modal>
      <ApplicationDetailModal open={openApp !== null} applicationId={openApp} onClose={() => setOpenApp(null)} />
    </>
  );
}
