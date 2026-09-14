import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Plus,
  X,
  Building2,
  BriefcaseBusiness,
  CalendarDays,
  IndianRupee,
  GraduationCap,
  Users,
  ArrowRight,
} from "lucide-react";
import { api } from "../api";
import "./AdminDashboard.css";

const initialForm = {
  company_id: "",
  job_role: "",
  drive_date: "",
  package_lpa: "",
  min_cgpa: "",
  max_backlogs: "0",
  drive_type: "Full-Time",
  status: "Upcoming",
  eligible_dept_ids: [],
};

export function AdminDashboard() {
  const [drives, setDrives] = useState([]);
  const [companies, setCompanies] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [form, setForm] = useState(initialForm);
  const [message, setMessage] = useState("");
  const [showForm, setShowForm] = useState(false);

  function loadDrives() {
    api.get("/drives").then(setDrives);
  }

  useEffect(() => {
    loadDrives();
    api.get("/companies").then(setCompanies);
    api.get("/departments").then(setDepartments);
  }, []);

  function update(field) {
    return (e) => setForm({ ...form, [field]: e.target.value });
  }

  function toggleDept(deptId) {
    setForm((f) => ({
      ...f,
      eligible_dept_ids: f.eligible_dept_ids.includes(deptId)
        ? f.eligible_dept_ids.filter((id) => id !== deptId)
        : [...f.eligible_dept_ids, deptId],
    }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setMessage("");

    try {
      await api.post("/drives", {
        ...form,
        company_id: Number(form.company_id),
        package_lpa: Number(form.package_lpa),
        min_cgpa: Number(form.min_cgpa),
        max_backlogs: Number(form.max_backlogs),
      });

      setMessage("Drive created.");
      setForm(initialForm);
      setShowForm(false);
      loadDrives();
    } catch (err) {
      setMessage(err.message);
    }
  }

  return (
    <main className="admin-dashboard">
      <section className="admin-hero">
        <div>
          <p className="admin-eyebrow">PLACEMENT MANAGEMENT</p>
          <h1>Placement Drives</h1>
          <p className="admin-subtitle">
            Create, review and manage placement drives from one place.
          </p>
        </div>

        <button
          className={`new-drive-button ${showForm ? "cancel" : ""}`}
          onClick={() => setShowForm(!showForm)}
        >
          {showForm ? <X size={18} /> : <Plus size={18} />}
          {showForm ? "Cancel" : "New Drive"}
        </button>
      </section>

      <section className="admin-stats">
        <AdminStatCard
          icon={<BriefcaseBusiness size={20} />}
          label="Total Drives"
          value={drives.length}
        />

        <AdminStatCard
          icon={<Building2 size={20} />}
          label="Companies"
          value={companies.length}
        />

        <AdminStatCard
          icon={<GraduationCap size={20} />}
          label="Departments"
          value={departments.length}
        />

        <AdminStatCard
          icon={<Users size={20} />}
          label="Upcoming"
          value={drives.filter((d) => d.status === "Upcoming").length}
        />
      </section>

      {showForm && (
        <section className="admin-card create-drive-card">
          <div className="admin-card-header">
            <div>
              <p className="section-label">NEW DRIVE</p>
              <h2>Create Placement Drive</h2>
              <p>
                Enter the company, role and eligibility requirements.
              </p>
            </div>
          </div>

          <form className="admin-form" onSubmit={handleSubmit}>
            <div className="admin-form-grid">
              <div className="admin-field">
                <label>Company</label>

                <select
                  value={form.company_id}
                  onChange={update("company_id")}
                  required
                >
                  <option value="">Select company</option>

                  {companies.map((c) => (
                    <option
                      key={c.company_id}
                      value={c.company_id}
                    >
                      {c.company_name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="admin-field">
                <label>Job Role</label>

                <input
                  value={form.job_role}
                  onChange={update("job_role")}
                  placeholder="e.g. Software Engineer"
                  required
                />
              </div>

              <div className="admin-field">
                <label>Drive Date</label>

                <input
                  type="date"
                  value={form.drive_date}
                  onChange={update("drive_date")}
                  required
                />
              </div>

              <div className="admin-field">
                <label>Package (LPA)</label>

                <input
                  type="number"
                  step="0.01"
                  value={form.package_lpa}
                  onChange={update("package_lpa")}
                  placeholder="e.g. 12.5"
                  required
                />
              </div>

              <div className="admin-field">
                <label>Minimum CGPA</label>

                <input
                  type="number"
                  step="0.01"
                  min="0"
                  max="10"
                  value={form.min_cgpa}
                  onChange={update("min_cgpa")}
                  placeholder="e.g. 7.5"
                  required
                />
              </div>

              <div className="admin-field">
                <label>Maximum Backlogs</label>

                <input
                  type="number"
                  min="0"
                  value={form.max_backlogs}
                  onChange={update("max_backlogs")}
                  required
                />
              </div>

              <div className="admin-field">
                <label>Drive Type</label>

                <select
                  value={form.drive_type}
                  onChange={update("drive_type")}
                >
                  <option value="Full-Time">Full-Time</option>
                  <option value="Internship">Internship</option>
                </select>
              </div>
            </div>

            <fieldset className="department-fieldset">
              <legend>
                Eligible Departments
                <span>None selected = open to all</span>
              </legend>

              <div className="department-options">
                {departments.map((d) => (
                  <label
                    key={d.dept_id}
                    className={`department-option ${
                      form.eligible_dept_ids.includes(d.dept_id)
                        ? "selected"
                        : ""
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={form.eligible_dept_ids.includes(
                        d.dept_id
                      )}
                      onChange={() => toggleDept(d.dept_id)}
                    />

                    <span>{d.dept_name}</span>
                  </label>
                ))}
              </div>
            </fieldset>

            <div className="form-actions">
              <button
                type="submit"
                className="create-drive-button"
              >
                Create Drive
              </button>
            </div>
          </form>
        </section>
      )}

      {message && (
        <div className="admin-notice">
          {message}
        </div>
      )}

      <section className="admin-card drives-table-card">
        <div className="admin-card-header">
          <div>
            <p className="section-label">DRIVE DIRECTORY</p>
            <h2>All Placement Drives</h2>
            <p>
              Review company drives and open individual drive management.
            </p>
          </div>

          <span className="drive-count-pill">
            {drives.length} Drives
          </span>
        </div>

        {drives.length === 0 ? (
          <div className="admin-empty-state">
            <div className="admin-empty-icon">
              <BriefcaseBusiness size={24} />
            </div>

            <h3>No placement drives yet</h3>
            <p>Create your first drive using the button above.</p>
          </div>
        ) : (
          <div className="admin-table-wrapper">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Company</th>
                  <th>Role</th>
                  <th>Date</th>
                  <th>Package</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>

              <tbody>
                {drives.map((d) => (
                  <tr key={d.drive_id}>
                    <td>
                      <div className="company-cell">
                        <div className="company-logo">
                          {d.company_name?.charAt(0)}
                        </div>

                        <span>{d.company_name}</span>
                      </div>
                    </td>

                    <td>{d.job_role}</td>

                    <td>
                      <div className="table-meta">
                        <CalendarDays size={15} />
                        {d.drive_date?.slice(0, 10)}
                      </div>
                    </td>

                    <td>
                      <div className="table-meta">
                        <IndianRupee size={15} />
                        {d.package_lpa} LPA
                      </div>
                    </td>

                    <td>
                      <span
                        className={`drive-status drive-status-${d.status}`}
                      >
                        {d.status}
                      </span>
                    </td>

                    <td>
                      <Link
                        className="manage-drive-link"
                        to={`/admin/drives/${d.drive_id}`}
                      >
                        Manage
                        <ArrowRight size={15} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}

function AdminStatCard({ icon, label, value }) {
  return (
    <div className="admin-stat-card">
      <div className="admin-stat-icon">
        {icon}
      </div>

      <div>
        <span>{label}</span>
        <strong>{value}</strong>
      </div>
    </div>
  );
}