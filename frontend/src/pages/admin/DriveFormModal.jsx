import { useEffect, useState } from "react";
import { Save } from "lucide-react";
import { api } from "../../api";
import { Alert } from "../../components/ui/Alert";
import { Field } from "../../components/ui/Field";
import { Modal } from "../../components/ui/Modal";
import { DRIVE_TYPES } from "../../utils/status";
import { toNumber } from "../../utils/format";

const EMPTY = {
  company_id: "", job_role: "", drive_date: "", application_deadline: "", package_lpa: "",
  min_cgpa: "", max_backlogs: "0", drive_type: "Full-Time", status: "Upcoming",
  eligible_dept_ids: [],
};

// Completed is deliberately not offered: completing a drive must go through
// "Close drive" (the sp_close_drive procedure), which also rejects every
// applicant still pending. Setting the status by hand would strand them.
const EDITABLE_STATUSES = ["Upcoming", "Ongoing", "Cancelled"];

function validate(form, isEdit) {
  const e = {};
  if (!isEdit && !form.company_id) e.company_id = "Choose the company.";
  if (!form.job_role.trim()) e.job_role = "Job role is required.";
  if (!form.drive_date) e.drive_date = "Pick the drive date.";
  // Mirrors the CHECK (application_deadline <= drive_date) on the table, so
  // the mistake is caught before the request instead of as a 400.
  if (form.application_deadline && form.drive_date && form.application_deadline > form.drive_date)
    e.application_deadline = "The deadline must be on or before the drive date.";
  const pkg = Number(form.package_lpa);
  if (form.package_lpa === "" || !(pkg > 0)) e.package_lpa = "Package must be greater than 0.";
  const cgpa = Number(form.min_cgpa);
  if (form.min_cgpa === "" || cgpa < 0 || cgpa > 10 || Number.isNaN(cgpa)) e.min_cgpa = "Minimum CGPA must be 0–10.";
  const backlogs = Number(form.max_backlogs);
  if (!Number.isInteger(backlogs) || backlogs < 0) e.max_backlogs = "Must be a whole number, 0 or more.";
  return e;
}

/**
 * Create a drive (drive = null) or edit one (drive = the GET /drives/:id
 * object). Calls onSaved(driveId) after a successful save.
 */
export function DriveFormModal({ open, onClose, drive, companies, departments, onSaved }) {
  const isEdit = Boolean(drive);
  const [form, setForm] = useState(EMPTY);
  const [errors, setErrors] = useState({});
  const [serverError, setServerError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setErrors({});
    setServerError("");
    setForm(
      drive
        ? {
            company_id: String(drive.company_id),
            job_role: drive.job_role,
            drive_date: drive.drive_date?.slice(0, 10) || "",
            application_deadline: drive.application_deadline?.slice(0, 10) || "",
            package_lpa: String(toNumber(drive.package_lpa) ?? ""),
            min_cgpa: String(toNumber(drive.min_cgpa) ?? ""),
            max_backlogs: String(drive.max_backlogs),
            drive_type: drive.drive_type,
            status: drive.status,
            eligible_dept_ids: (drive.eligible_departments || []).map((d) => d.dept_id),
          }
        : EMPTY
    );
  }, [open, drive]);

  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value });
  const toggleDept = (id) =>
    setForm((f) => ({
      ...f,
      eligible_dept_ids: f.eligible_dept_ids.includes(id)
        ? f.eligible_dept_ids.filter((x) => x !== id)
        : [...f.eligible_dept_ids, id],
    }));

  async function save() {
    setServerError("");
    const found = validate(form, isEdit);
    setErrors(found);
    if (Object.keys(found).length) return;
    setSaving(true);
    const payload = {
      job_role: form.job_role.trim(),
      drive_date: form.drive_date,
      // Left empty on a new drive, the backend closes applications on the drive date.
      application_deadline: form.application_deadline || (isEdit ? form.drive_date : undefined),
      package_lpa: Number(form.package_lpa),
      min_cgpa: Number(form.min_cgpa),
      max_backlogs: Number(form.max_backlogs),
      drive_type: form.drive_type,
      status: form.status,
      eligible_dept_ids: form.eligible_dept_ids,
    };
    try {
      if (isEdit) {
        await api.put(`/drives/${drive.drive_id}`, payload);
        onSaved(drive.drive_id);
      } else {
        const created = await api.post("/drives", { ...payload, company_id: Number(form.company_id) });
        onSaved(created.drive_id);
      }
    } catch (err) {
      setServerError(err.message);
    } finally {
      setSaving(false);
    }
  }

  const statusOptions = isEdit && !EDITABLE_STATUSES.includes(form.status)
    ? [form.status, ...EDITABLE_STATUSES]
    : EDITABLE_STATUSES;

  return (
    <Modal
      open={open}
      onClose={onClose}
      wide
      title={isEdit ? "Edit drive" : "New placement drive"}
      subtitle={isEdit ? `${drive.company_name} · ${drive.job_role}` : "Company, role and the eligibility rules students must meet"}
      footer={
        <>
          <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button type="button" className="btn btn-primary" onClick={save} disabled={saving}>
            <Save size={16} aria-hidden="true" /> {saving ? "Saving…" : isEdit ? "Save changes" : "Create drive"}
          </button>
        </>
      }
    >
      <div className="form-grid">
        {!isEdit && (
          <Field id="drive-company" label="Company" error={errors.company_id} required className="span-2">
            <select value={form.company_id} onChange={set("company_id")}>
              <option value="">Select company</option>
              {companies.map((c) => <option key={c.company_id} value={c.company_id}>{c.company_name}</option>)}
            </select>
          </Field>
        )}
        <Field id="drive-role" label="Job role" error={errors.job_role} required>
          <input value={form.job_role} onChange={set("job_role")} placeholder="e.g. Software Engineer" />
        </Field>
        <Field id="drive-date" label="Drive date" error={errors.drive_date} required>
          <input type="date" value={form.drive_date} onChange={set("drive_date")} />
        </Field>
        <Field id="drive-deadline" label="Application deadline" error={errors.application_deadline}
          hint="Last day to apply. Leave empty to close applications on the drive date.">
          <input type="date" value={form.application_deadline} max={form.drive_date || undefined} onChange={set("application_deadline")} />
        </Field>
        <Field id="drive-package" label="Package (LPA)" error={errors.package_lpa} required>
          <input type="number" step="0.01" min="0" value={form.package_lpa} onChange={set("package_lpa")} />
        </Field>
        <Field id="drive-type" label="Drive type">
          <select value={form.drive_type} onChange={set("drive_type")}>
            {DRIVE_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </Field>
        <Field id="drive-cgpa" label="Minimum CGPA" error={errors.min_cgpa} required>
          <input type="number" step="0.01" min="0" max="10" value={form.min_cgpa} onChange={set("min_cgpa")} />
        </Field>
        <Field id="drive-backlogs" label="Maximum backlogs" error={errors.max_backlogs} required>
          <input type="number" min="0" step="1" value={form.max_backlogs} onChange={set("max_backlogs")} />
        </Field>
        <Field id="drive-status" label="Status" hint="To complete a drive, use Close drive on its page." className="span-2">
          <select value={form.status} onChange={set("status")}>
            {statusOptions.map((s) => <option key={s} value={s} disabled={!EDITABLE_STATUSES.includes(s)}>{s}</option>)}
          </select>
        </Field>
        <fieldset className="span-2" style={{ border: 0, padding: 0, margin: 0 }}>
          <legend className="section-title">Eligible departments <span className="muted">(none selected = open to all)</span></legend>
          <div className="checkbox-group">
            {departments.map((d) => (
              <label key={d.dept_id} className="checkbox-pill">
                <input
                  type="checkbox"
                  checked={form.eligible_dept_ids.includes(d.dept_id)}
                  onChange={() => toggleDept(d.dept_id)}
                />
                {d.dept_code}
              </label>
            ))}
          </div>
        </fieldset>
      </div>
      <Alert variant="error">{serverError}</Alert>
    </Modal>
  );
}
