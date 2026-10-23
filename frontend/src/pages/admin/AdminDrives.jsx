import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Briefcase, CalendarDays, Clock, Pencil, Plus, Search, CircleCheck } from "lucide-react";
import { api } from "../../api";
import { useApi } from "../../hooks/useApi";
import { Alert } from "../../components/ui/Alert";
import { DataTable } from "../../components/ui/DataTable";
import { Card, CompanyCell, PageHeader, StatCard } from "../../components/ui/Layout";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { formatCgpa, formatDate, formatLpa } from "../../utils/format";
import { DRIVE_STATUSES } from "../../utils/status";
import { DriveFormModal } from "./DriveFormModal";

export function AdminDrives() {
  const navigate = useNavigate();
  const drives = useApi("/drives");
  const companies = useApi("/companies");
  const departments = useApi("/departments");

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null); // full drive object for edit
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const rows = useMemo(() => {
    const term = search.trim().toLowerCase();
    return (drives.data || []).filter(
      (d) =>
        (!statusFilter || d.status === statusFilter) &&
        (!term || d.company_name.toLowerCase().includes(term) || d.job_role.toLowerCase().includes(term))
    );
  }, [drives.data, search, statusFilter]);

  const counts = useMemo(() => {
    const c = { Upcoming: 0, Ongoing: 0, Completed: 0, Cancelled: 0 };
    (drives.data || []).forEach((d) => { c[d.status] = (c[d.status] || 0) + 1; });
    return c;
  }, [drives.data]);

  async function openEdit(drive) {
    setError("");
    try {
      // The list row lacks the department restrictions; fetch the full drive.
      setEditing(await api.get(`/drives/${drive.drive_id}`));
      setFormOpen(true);
    } catch (err) {
      setError(err.message);
    }
  }

  function onSaved(driveId) {
    const wasEdit = Boolean(editing);
    setFormOpen(false);
    setEditing(null);
    drives.reload();
    if (wasEdit) setNotice("Drive updated.");
    else navigate(`/admin/drives/${driveId}`);
  }

  return (
    <>
      <PageHeader
        eyebrow="Placement cell"
        title="Placement drives"
        subtitle="Create drives, set their eligibility rules, and manage applicants."
        actions={
          <button type="button" className="btn btn-primary" onClick={() => { setEditing(null); setFormOpen(true); }}>
            <Plus size={16} aria-hidden="true" /> New drive
          </button>
        }
      />

      <div className="stat-grid">
        <StatCard icon={Briefcase} label="All drives" value={drives.data?.length ?? "—"} />
        <StatCard icon={CalendarDays} label="Upcoming" value={drives.data ? counts.Upcoming : "—"} />
        <StatCard icon={Clock} label="Ongoing" value={drives.data ? counts.Ongoing : "—"} />
        <StatCard icon={CircleCheck} label="Completed" value={drives.data ? counts.Completed : "—"} />
      </div>

      <Alert variant="success" onClose={() => setNotice("")}>{notice}</Alert>
      <Alert variant="error" onClose={() => setError("")}>{error}</Alert>

      <Card title="Drive directory" subtitle={`${rows.length} of ${drives.data?.length ?? 0} drives shown`} flush>
        <div className="toolbar">
          <label className="search-box">
            <span className="sr-only">Search drives</span>
            <Search size={16} aria-hidden="true" />
            <input className="input" placeholder="Search company or role" value={search} onChange={(e) => setSearch(e.target.value)} />
          </label>
          <label>
            <span className="sr-only">Filter by status</span>
            <select className="input" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value="">All statuses</option>
              {DRIVE_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
        </div>
        <DataTable
          caption="Placement drives"
          loading={drives.loading}
          error={drives.error}
          rows={drives.data ? rows : null}
          rowKey={(d) => d.drive_id}
          emptyTitle={drives.data?.length ? "No drives match these filters" : "No drives yet"}
          emptyMessage={drives.data?.length ? "Clear the search or status filter." : "Create the first drive with New drive."}
          columns={[
            { key: "company", header: "Company / role", render: (d) => <CompanyCell name={d.company_name} sub={d.job_role} /> },
            { key: "date", header: "Date", render: (d) => <span className="nowrap">{formatDate(d.drive_date)}</span> },
            { key: "package", header: "Package", className: "num", render: (d) => formatLpa(d.package_lpa) },
            { key: "criteria", header: "Criteria", render: (d) => <span className="cell-sub">CGPA ≥ {formatCgpa(d.min_cgpa)} · ≤ {d.max_backlogs} backlogs</span> },
            { key: "type", header: "Type", render: (d) => d.drive_type },
            { key: "status", header: "Status", render: (d) => <StatusBadge status={d.status} /> },
            {
              key: "actions",
              header: <span className="sr-only">Actions</span>,
              render: (d) => (
                <div className="inline-actions">
                  <Link className="btn btn-secondary btn-sm" to={`/admin/drives/${d.drive_id}`}>Manage</Link>
                  <button type="button" className="btn btn-ghost btn-sm" onClick={() => openEdit(d)} aria-label={`Edit ${d.company_name} ${d.job_role}`}>
                    <Pencil size={14} aria-hidden="true" /> Edit
                  </button>
                </div>
              ),
            },
          ]}
        />
      </Card>

      <DriveFormModal
        open={formOpen}
        onClose={() => { setFormOpen(false); setEditing(null); }}
        drive={editing}
        companies={companies.data || []}
        departments={departments.data || []}
        onSaved={onSaved}
      />
    </>
  );
}
