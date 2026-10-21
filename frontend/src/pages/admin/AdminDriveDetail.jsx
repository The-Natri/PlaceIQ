import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { Award, ClipboardList, Eye, Lock, Pencil, Search } from "lucide-react";
import { api } from "../../api";
import { useApi } from "../../hooks/useApi";
import { ApplicationDetailModal } from "../../components/ApplicationDetailModal";
import { Alert } from "../../components/ui/Alert";
import { DataTable } from "../../components/ui/DataTable";
import { Field } from "../../components/ui/Field";
import { Loading } from "../../components/ui/Feedback";
import { Card, PageHeader } from "../../components/ui/Layout";
import { Modal } from "../../components/ui/Modal";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { formatCgpa, formatDate, formatLpa, toNumber } from "../../utils/format";
import { NEXT_STATUSES, ROUND_TYPES, statusLabel } from "../../utils/status";
import { DriveFormModal } from "./DriveFormModal";

const PENDING = ["Applied", "Shortlisted", "Interview_Scheduled"];
const APPLICATION_STATUSES = ["Applied", "Shortlisted", "Interview_Scheduled", "Selected", "Offer_Made", "Rejected"];

export function AdminDriveDetail() {
  const { driveId } = useParams();
  const drive = useApi(`/drives/${driveId}`);
  const applicants = useApi(`/drives/${driveId}/applicants`);
  const companies = useApi("/companies");
  const departments = useApi("/departments");

  const [notice, setNotice] = useState({ variant: "", text: "" });
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");
  const [editOpen, setEditOpen] = useState(false);
  const [closeOpen, setCloseOpen] = useState(false);
  const [roundFor, setRoundFor] = useState(null);
  const [offerFor, setOfferFor] = useState(null);
  const [detailFor, setDetailFor] = useState(null);

  const d = drive.data;
  const isClosed = d && (d.status === "Completed" || d.status === "Cancelled");
  const pendingCount = (applicants.data || []).filter((a) => PENDING.includes(a.status)).length;

  const rows = useMemo(() => {
    const term = search.trim().toLowerCase();
    return (applicants.data || []).filter(
      (a) =>
        (!statusFilter || a.status === statusFilter) &&
        (!term || a.name.toLowerCase().includes(term) || a.reg_no.toLowerCase().includes(term))
    );
  }, [applicants.data, search, statusFilter]);

  const statusCounts = useMemo(() => {
    const c = {};
    (applicants.data || []).forEach((a) => { c[a.status] = (c[a.status] || 0) + 1; });
    return c;
  }, [applicants.data]);

  function say(variant, text) {
    setNotice({ variant, text });
  }

  async function changeStatus(app, status) {
    try {
      await api.put(`/applications/${app.application_id}/status`, { status });
      say("success", `${app.name}: ${statusLabel(app.status)} → ${statusLabel(status)}.`);
      applicants.reload();
    } catch (err) {
      say("error", err.message);
    }
  }

  if (drive.error) return <Alert variant="error">{drive.error}</Alert>;
  if (!d) return <Loading />;

  return (
    <>
      <PageHeader
        backTo="/admin/drives"
        backLabel="All drives"
        eyebrow={d.company_name}
        title={d.job_role}
        subtitle={`${d.drive_type} · ${formatDate(d.drive_date)} · ${formatLpa(d.package_lpa)}`}
        actions={
          <>
            <button type="button" className="btn btn-secondary" onClick={() => setEditOpen(true)}>
              <Pencil size={16} aria-hidden="true" /> Edit drive
            </button>
            <button
              type="button"
              className="btn btn-danger"
              disabled={isClosed}
              onClick={() => setCloseOpen(true)}
              title={isClosed ? `This drive is already ${d.status}` : undefined}
            >
              <Lock size={16} aria-hidden="true" /> Close drive
            </button>
          </>
        }
      />

      <Alert variant={notice.variant || "info"} onClose={() => setNotice({ variant: "", text: "" })}>{notice.text}</Alert>

      <Card title="Drive details">
        <dl className="kv">
          <div><dt>Status</dt><dd><StatusBadge status={d.status} /></dd></div>
          <div><dt>Industry</dt><dd>{d.industry_sector || "—"}</dd></div>
          <div><dt>Minimum CGPA</dt><dd>{formatCgpa(d.min_cgpa)}</dd></div>
          <div><dt>Maximum backlogs</dt><dd>{d.max_backlogs}</dd></div>
          <div>
            <dt>Open to</dt>
            <dd>{d.eligible_departments.length ? d.eligible_departments.map((x) => x.dept_code).join(", ") : "All departments"}</dd>
          </div>
          <div><dt>Applicants</dt><dd>{applicants.data?.length ?? "—"} ({pendingCount} still pending)</dd></div>
        </dl>
      </Card>

      <Card title="Applicants" subtitle="Move each applicant through the pipeline, record rounds and offers" flush>
        <div className="toolbar">
          <label className="search-box">
            <span className="sr-only">Search applicants</span>
            <Search size={16} aria-hidden="true" />
            <input className="input" placeholder="Search name or reg. no." value={search} onChange={(e) => setSearch(e.target.value)} />
          </label>
          <label>
            <span className="sr-only">Filter by status</span>
            <select className="input" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value="">All statuses ({applicants.data?.length ?? 0})</option>
              {APPLICATION_STATUSES.map((s) => (
                <option key={s} value={s}>{statusLabel(s)} ({statusCounts[s] || 0})</option>
              ))}
            </select>
          </label>
        </div>
        <DataTable
          caption={`Applicants for ${d.job_role}`}
          loading={applicants.loading}
          error={applicants.error}
          rows={applicants.data ? rows : null}
          rowKey={(a) => a.application_id}
          emptyTitle={applicants.data?.length ? "No applicants match these filters" : "No applicants yet"}
          emptyMessage={applicants.data?.length ? undefined : "Students who apply to this drive will appear here."}
          columns={[
            { key: "student", header: "Student", render: (a) => (<><div>{a.name}</div><div className="cell-sub">{a.reg_no} · {a.dept_name}</div></>) },
            { key: "cgpa", header: "CGPA", className: "num", render: (a) => formatCgpa(a.cgpa) },
            { key: "backlogs", header: "Backlogs", className: "num", render: (a) => a.backlogs },
            { key: "status", header: "Status", render: (a) => <StatusBadge status={a.status} /> },
            {
              key: "move",
              header: "Move to",
              render: (a) =>
                NEXT_STATUSES[a.status]?.length ? (
                  <select
                    className="input"
                    style={{ minHeight: 30, padding: "2px 8px", width: 170 }}
                    value=""
                    aria-label={`Move ${a.name} to`}
                    onChange={(e) => e.target.value && changeStatus(a, e.target.value)}
                  >
                    <option value="">Choose…</option>
                    {NEXT_STATUSES[a.status].map((s) => <option key={s} value={s}>{statusLabel(s)}</option>)}
                  </select>
                ) : (
                  <span className="cell-sub">Final</span>
                ),
            },
            {
              key: "actions",
              header: <span className="sr-only">Actions</span>,
              render: (a) => (
                <div className="inline-actions">
                  {!["Offer_Made", "Rejected"].includes(a.status) && (
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => setRoundFor(a)}>
                      <ClipboardList size={14} aria-hidden="true" /> Round
                    </button>
                  )}
                  {a.status === "Selected" && (
                    <button type="button" className="btn btn-success btn-sm" onClick={() => setOfferFor(a)}>
                      <Award size={14} aria-hidden="true" /> Offer
                    </button>
                  )}
                  <button type="button" className="btn btn-secondary btn-sm" onClick={() => setDetailFor(a.application_id)} aria-label={`View ${a.name}'s application`}>
                    <Eye size={14} aria-hidden="true" /> View
                  </button>
                </div>
              ),
            },
          ]}
        />
      </Card>

      <DriveFormModal
        open={editOpen}
        onClose={() => setEditOpen(false)}
        drive={d}
        companies={companies.data || []}
        departments={departments.data || []}
        onSaved={() => { setEditOpen(false); drive.reload(); say("success", "Drive updated."); }}
      />

      <CloseDriveModal
        open={closeOpen}
        drive={d}
        pendingCount={pendingCount}
        onClose={() => setCloseOpen(false)}
        onClosed={(result) => {
          setCloseOpen(false);
          drive.reload();
          applicants.reload();
          say("success", `Drive closed. ${result.rejected_count} pending applicant${result.rejected_count === 1 ? " was" : "s were"} rejected by the sp_close_drive procedure.`);
        }}
      />

      <RoundModal
        applicant={roundFor}
        onClose={() => setRoundFor(null)}
        onSaved={(a) => { setRoundFor(null); say("success", `Round recorded for ${a.name}.`); }}
      />

      <OfferModal
        applicant={offerFor}
        defaultPackage={toNumber(d.package_lpa)}
        onClose={() => setOfferFor(null)}
        onSaved={(a) => { setOfferFor(null); applicants.reload(); say("success", `Offer recorded for ${a.name}. The database trigger has marked them Placed.`); }}
      />

      <ApplicationDetailModal open={detailFor !== null} applicationId={detailFor} onClose={() => setDetailFor(null)} />
    </>
  );
}

function CloseDriveModal({ open, drive, pendingCount, onClose, onClosed }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function confirm() {
    setBusy(true);
    setError("");
    try {
      onClosed(await api.post(`/drives/${drive.drive_id}/close`));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Close this drive?"
      subtitle={`${drive.company_name} · ${drive.job_role}`}
      footer={
        <>
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button type="button" className="btn btn-danger" onClick={confirm} disabled={busy}>
            <Lock size={16} aria-hidden="true" /> {busy ? "Closing…" : "Close drive"}
          </button>
        </>
      }
    >
      <p>
        The drive will be marked <strong>Completed</strong> and{" "}
        <strong>{pendingCount} applicant{pendingCount === 1 ? "" : "s"}</strong> still at Applied,
        Shortlisted or Interview Scheduled will be <strong>rejected</strong>. Selected students and
        those with offers are not affected.
      </p>
      <p className="muted">This can't be undone. It runs as one transaction in the database (stored procedure sp_close_drive).</p>
      <Alert variant="error">{error}</Alert>
    </Modal>
  );
}

function RoundModal({ applicant, onClose, onSaved }) {
  const [form, setForm] = useState({ round_number: "1", round_type: "Aptitude", round_date: "", result: "Pending", remarks: "" });
  const [errors, setErrors] = useState({});
  const [serverError, setServerError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (f) => (e) => setForm({ ...form, [f]: e.target.value });

  async function save() {
    setServerError("");
    const e = {};
    const n = Number(form.round_number);
    if (!Number.isInteger(n) || n < 1) e.round_number = "Round number must be 1 or more.";
    setErrors(e);
    if (Object.keys(e).length) return;
    setBusy(true);
    try {
      await api.post(`/applications/${applicant.application_id}/interview-rounds`, {
        round_number: n,
        round_type: form.round_type,
        round_date: form.round_date || null,
        result: form.result,
        remarks: form.remarks || null,
      });
      onSaved(applicant);
      setForm({ round_number: String(n + 1), round_type: "Aptitude", round_date: "", result: "Pending", remarks: "" });
    } catch (err) {
      setServerError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={Boolean(applicant)}
      onClose={onClose}
      title="Record interview round"
      subtitle={applicant ? `${applicant.name} (${applicant.reg_no})` : undefined}
      footer={
        <>
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button type="button" className="btn btn-primary" onClick={save} disabled={busy}>{busy ? "Saving…" : "Save round"}</button>
        </>
      }
    >
      <div className="form-grid">
        <Field id="round-number" label="Round number" error={errors.round_number} required>
          <input type="number" min="1" step="1" value={form.round_number} onChange={set("round_number")} />
        </Field>
        <Field id="round-type" label="Round type" required>
          <select value={form.round_type} onChange={set("round_type")}>
            {ROUND_TYPES.map((t) => <option key={t} value={t}>{statusLabel(t)}</option>)}
          </select>
        </Field>
        <Field id="round-date" label="Date">
          <input type="date" value={form.round_date} onChange={set("round_date")} />
        </Field>
        <Field id="round-result" label="Result">
          <select value={form.result} onChange={set("result")}>
            <option value="Pending">Pending</option>
            <option value="Pass">Pass</option>
            <option value="Fail">Fail</option>
          </select>
        </Field>
        <Field id="round-remarks" label="Remarks" className="span-2">
          <textarea rows={2} maxLength={500} value={form.remarks} onChange={set("remarks")} />
        </Field>
      </div>
      <Alert variant="error">{serverError}</Alert>
    </Modal>
  );
}

function OfferModal({ applicant, defaultPackage, onClose, onSaved }) {
  const [pkg, setPkg] = useState("");
  const [date, setDate] = useState("");
  const [error, setError] = useState("");
  const [serverError, setServerError] = useState("");
  const [busy, setBusy] = useState(false);

  // Prefill with the drive's advertised package each time the dialog opens.
  useEffect(() => {
    if (!applicant) return;
    setPkg(defaultPackage ? String(defaultPackage) : "");
    setDate("");
    setError("");
    setServerError("");
  }, [applicant, defaultPackage]);

  async function save() {
    setServerError("");
    const value = Number(pkg);
    if (!(value > 0)) { setError("Package must be greater than 0."); return; }
    setError("");
    setBusy(true);
    try {
      await api.post(`/applications/${applicant.application_id}/offer`, {
        offered_package_lpa: value,
        offer_date: date || undefined,
      });
      onSaved(applicant);
    } catch (err) {
      setServerError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={Boolean(applicant)}
      onClose={onClose}
      title="Record offer"
      subtitle={applicant ? `${applicant.name} (${applicant.reg_no})` : undefined}
      footer={
        <>
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button type="button" className="btn btn-success" onClick={save} disabled={busy}>{busy ? "Saving…" : "Record offer"}</button>
        </>
      }
    >
      <div className="form-grid">
        <Field id="offer-package" label="Package offered (LPA)" error={error} required>
          <input type="number" step="0.01" min="0" value={pkg} onChange={(e) => setPkg(e.target.value)} />
        </Field>
        <Field id="offer-date" label="Offer date" hint="Defaults to today">
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </Field>
      </div>
      <p className="muted">
        The offer starts as Pending until the student accepts or declines it. Recording it marks the
        student Placed (database trigger) and moves this application to Offer Made.
      </p>
      <Alert variant="error">{serverError}</Alert>
    </Modal>
  );
}
