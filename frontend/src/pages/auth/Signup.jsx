import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { UserRound } from "lucide-react";
import { api } from "../../api";
import { useAuth } from "../../auth/AuthContext";
import { Alert } from "../../components/ui/Alert";
import { Field } from "../../components/ui/Field";
import { AuthLayout } from "./AuthLayout";
import { PasswordInput } from "./Login";

const EMPTY = {
  reg_no: "", name: "", email: "", password: "", dept_id: "",
  cgpa: "", backlogs: "0", batch_year: String(new Date().getFullYear()), phone: "",
};

// Same limits as the CHECK constraints in db/schema.sql, so most mistakes are
// caught here with a clear message instead of a round trip to the server.
function validate(form) {
  const e = {};
  if (!form.reg_no.trim()) e.reg_no = "Registration number is required.";
  if (!form.name.trim()) e.name = "Full name is required.";
  if (!/^\S+@\S+\.\S+$/.test(form.email)) e.email = "Enter a valid email address.";
  if (form.password.length < 6) e.password = "Use at least 6 characters.";
  if (!form.dept_id) e.dept_id = "Choose your department.";
  const cgpa = Number(form.cgpa);
  if (form.cgpa === "" || Number.isNaN(cgpa) || cgpa < 0 || cgpa > 10) e.cgpa = "CGPA must be between 0 and 10.";
  const backlogs = Number(form.backlogs);
  if (!Number.isInteger(backlogs) || backlogs < 0) e.backlogs = "Backlogs must be a whole number, 0 or more.";
  const year = Number(form.batch_year);
  if (!Number.isInteger(year) || year < 2000 || year > 2100) e.batch_year = "Enter a year between 2000 and 2100.";
  if (form.phone && !/^\d{10,15}$/.test(form.phone)) e.phone = "Phone should be 10–15 digits.";
  return e;
}

export function Signup() {
  const { signupStudent } = useAuth();
  const navigate = useNavigate();
  const [departments, setDepartments] = useState([]);
  const [form, setForm] = useState(EMPTY);
  const [errors, setErrors] = useState({});
  const [serverError, setServerError] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api.get("/departments").then(setDepartments).catch(() => setServerError("Couldn't load departments."));
  }, []);

  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  async function handleSubmit(e) {
    e.preventDefault();
    setServerError("");
    const found = validate(form);
    setErrors(found);
    if (Object.keys(found).length) return;
    setSubmitting(true);
    try {
      await signupStudent({
        ...form,
        dept_id: Number(form.dept_id),
        cgpa: Number(form.cgpa),
        backlogs: Number(form.backlogs),
        batch_year: Number(form.batch_year),
        phone: form.phone || undefined,
      });
      navigate("/student");
    } catch (err) {
      setServerError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout wide>
      <div>
        <h1>Create your student account</h1>
        <p className="page-subtitle">Your CGPA and backlogs decide which drives you are eligible for.</p>
      </div>

      <form onSubmit={handleSubmit} noValidate className="form-grid">
        <Field id="su-reg" label="Registration No." error={errors.reg_no} required>
          <input value={form.reg_no} onChange={set("reg_no")} placeholder="e.g. CSE2024015" />
        </Field>
        <Field id="su-name" label="Full name" error={errors.name} required>
          <input value={form.name} onChange={set("name")} autoComplete="name" />
        </Field>
        <Field id="su-email" label="Email address" error={errors.email} required className="span-2">
          <input type="email" value={form.email} onChange={set("email")} autoComplete="email" placeholder="you@campus.edu" />
        </Field>
        <Field id="su-password" label="Password" error={errors.password} hint="At least 6 characters." required className="span-2">
          <PasswordInput
            value={form.password}
            onChange={(v) => setForm({ ...form, password: v })}
            show={showPassword}
            onToggle={() => setShowPassword(!showPassword)}
            autoComplete="new-password"
          />
        </Field>
        <Field id="su-dept" label="Department" error={errors.dept_id} required className="span-2">
          <select value={form.dept_id} onChange={set("dept_id")}>
            <option value="">Select your department</option>
            {departments.map((d) => (
              <option key={d.dept_id} value={d.dept_id}>{d.dept_name}</option>
            ))}
          </select>
        </Field>
        <Field id="su-cgpa" label="CGPA" error={errors.cgpa} required>
          <input type="number" step="0.01" min="0" max="10" value={form.cgpa} onChange={set("cgpa")} placeholder="0.00 – 10.00" />
        </Field>
        <Field id="su-backlogs" label="Active backlogs" error={errors.backlogs} required>
          <input type="number" min="0" step="1" value={form.backlogs} onChange={set("backlogs")} />
        </Field>
        <Field id="su-batch" label="Batch (graduation year)" error={errors.batch_year} required>
          <input type="number" value={form.batch_year} onChange={set("batch_year")} />
        </Field>
        <Field id="su-phone" label="Phone" error={errors.phone} hint="Optional">
          <input type="tel" value={form.phone} onChange={set("phone")} autoComplete="tel" />
        </Field>

        <div className="span-2"><Alert variant="error">{serverError}</Alert></div>

        <div className="span-2 form-actions">
          <Link to="/login" className="btn btn-ghost">Back to sign in</Link>
          <button type="submit" className="btn btn-primary" disabled={submitting}>
            <UserRound size={16} aria-hidden="true" /> {submitting ? "Creating account…" : "Create account"}
          </button>
        </div>
      </form>
    </AuthLayout>
  );
}
