import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";

const initialForm = {
  company_id: "", job_role: "", drive_date: "", package_lpa: "",
  min_cgpa: "", max_backlogs: "0", drive_type: "Full-Time", status: "Upcoming",
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
    <div className="page">
      <h1>Drives</h1>

      <button onClick={() => setShowForm(!showForm)}>
        {showForm ? "Cancel" : "+ New Drive"}
      </button>

      {showForm && (
        <form className="card" onSubmit={handleSubmit}>
          <label>Company
            <select value={form.company_id} onChange={update("company_id")} required>
              <option value="">Select...</option>
              {companies.map((c) => (
                <option key={c.company_id} value={c.company_id}>{c.company_name}</option>
              ))}
            </select>
          </label>
          <label>Job Role
            <input value={form.job_role} onChange={update("job_role")} required />
          </label>
          <label>Drive Date
            <input type="date" value={form.drive_date} onChange={update("drive_date")} required />
          </label>
          <label>Package (LPA)
            <input type="number" step="0.01" value={form.package_lpa} onChange={update("package_lpa")} required />
          </label>
          <label>Min CGPA
            <input type="number" step="0.01" min="0" max="10" value={form.min_cgpa} onChange={update("min_cgpa")} required />
          </label>
          <label>Max Backlogs
            <input type="number" min="0" value={form.max_backlogs} onChange={update("max_backlogs")} required />
          </label>
          <label>Drive Type
            <select value={form.drive_type} onChange={update("drive_type")}>
              <option value="Full-Time">Full-Time</option>
              <option value="Internship">Internship</option>
            </select>
          </label>
          <fieldset>
            <legend>Eligible Departments (none selected = open to all)</legend>
            {departments.map((d) => (
              <label key={d.dept_id} className="checkbox-label">
                <input
                  type="checkbox"
                  checked={form.eligible_dept_ids.includes(d.dept_id)}
                  onChange={() => toggleDept(d.dept_id)}
                />
                {d.dept_name}
              </label>
            ))}
          </fieldset>
          <button type="submit">Create Drive</button>
        </form>
      )}

      {message && <p className="notice">{message}</p>}

      <table>
        <thead>
          <tr><th>Company</th><th>Role</th><th>Date</th><th>Package</th><th>Status</th><th></th></tr>
        </thead>
        <tbody>
          {drives.map((d) => (
            <tr key={d.drive_id}>
              <td>{d.company_name}</td>
              <td>{d.job_role}</td>
              <td>{d.drive_date?.slice(0, 10)}</td>
              <td>{d.package_lpa}</td>
              <td>{d.status}</td>
              <td><Link to={`/admin/drives/${d.drive_id}`}>Manage</Link></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
