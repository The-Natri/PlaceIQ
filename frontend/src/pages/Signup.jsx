import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth/AuthContext";

const initialForm = {
  reg_no: "", name: "", email: "", password: "",
  dept_id: "", cgpa: "", backlogs: "0", batch_year: new Date().getFullYear(),
  phone: "",
};

export function Signup() {
  const [departments, setDepartments] = useState([]);
  const [form, setForm] = useState(initialForm);
  const [error, setError] = useState("");
  const { signupStudent } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    api.get("/departments").then(setDepartments).catch(() => {});
  }, []);

  function update(field) {
    return (e) => setForm({ ...form, [field]: e.target.value });
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    try {
      await signupStudent({
        ...form,
        dept_id: Number(form.dept_id),
        cgpa: Number(form.cgpa),
        backlogs: Number(form.backlogs),
        batch_year: Number(form.batch_year),
      });
      navigate("/student");
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="page-narrow">
      <h1>Student Signup</h1>
      <form onSubmit={handleSubmit}>
        <label>Registration No.
          <input value={form.reg_no} onChange={update("reg_no")} required />
        </label>
        <label>Name
          <input value={form.name} onChange={update("name")} required />
        </label>
        <label>Email
          <input type="email" value={form.email} onChange={update("email")} required />
        </label>
        <label>Password
          <input type="password" value={form.password} onChange={update("password")} required minLength={6} />
        </label>
        <label>Department
          <select value={form.dept_id} onChange={update("dept_id")} required>
            <option value="">Select...</option>
            {departments.map((d) => (
              <option key={d.dept_id} value={d.dept_id}>{d.dept_name}</option>
            ))}
          </select>
        </label>
        <label>CGPA
          <input type="number" step="0.01" min="0" max="10" value={form.cgpa} onChange={update("cgpa")} required />
        </label>
        <label>Backlogs
          <input type="number" min="0" value={form.backlogs} onChange={update("backlogs")} required />
        </label>
        <label>Batch Year
          <input type="number" value={form.batch_year} onChange={update("batch_year")} required />
        </label>
        <label>Phone (optional)
          <input value={form.phone} onChange={update("phone")} />
        </label>
        {error && <p className="error">{error}</p>}
        <button type="submit">Sign up</button>
      </form>
    </div>
  );
}
