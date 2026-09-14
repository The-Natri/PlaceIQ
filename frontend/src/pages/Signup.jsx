import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth/AuthContext";
import "./Signup.css";

const initialForm = {
  reg_no: "",
  name: "",
  email: "",
  password: "",
  dept_id: "",
  cgpa: "",
  backlogs: "0",
  batch_year: new Date().getFullYear(),
  phone: "",
};

export function Signup() {
  const [departments, setDepartments] = useState([]);
  const [form, setForm] = useState(initialForm);
  const [error, setError] = useState("");
  const [showPassword, setShowPassword] = useState(false);

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
    <div className="signup-page">
      <div className="signup-container">

        <div className="signup-brand">
          <div className="signup-logo">PI</div>

          <h1>PlaceIQ</h1>

          <h2>Create your student profile.</h2>

          <p>
            Register once and manage your entire placement journey from
            one place.
          </p>

          <div className="signup-features">
            <span>✓ Discover eligible drives</span>
            <span>✓ Apply to companies</span>
            <span>✓ Track interview progress</span>
            <span>✓ Manage placement offers</span>
          </div>
        </div>

        <div className="signup-section">
          <div className="signup-card">

            <div className="signup-heading">
              <span className="signup-eyebrow">STUDENT REGISTRATION</span>
              <h2>Create your account</h2>
              <p>Enter your academic and contact details.</p>
            </div>

            <form onSubmit={handleSubmit} className="signup-form">

              <div className="signup-grid">
                <div className="signup-field">
                  <label>Registration No.</label>
                  <input
                    value={form.reg_no}
                    onChange={update("reg_no")}
                    placeholder="24BLCXXXX"
                    required
                  />
                </div>

                <div className="signup-field">
                  <label>Full Name</label>
                  <input
                    value={form.name}
                    onChange={update("name")}
                    placeholder="Your name"
                    required
                  />
                </div>

                <div className="signup-field signup-full">
                  <label>Email address</label>
                  <input
                    type="email"
                    value={form.email}
                    onChange={update("email")}
                    placeholder="student@college.edu"
                    required
                  />
                </div>

                <div className="signup-field signup-full">
                  <label>Password</label>

                  <div className="signup-password-wrapper">
                    <input
                      type={showPassword ? "text" : "password"}
                      value={form.password}
                      onChange={update("password")}
                      placeholder="Minimum 6 characters"
                      required
                      minLength={6}
                    />

                    <button
                      type="button"
                      className="signup-password-toggle"
                      onClick={() => setShowPassword(!showPassword)}
                    >
                      {showPassword ? "Hide" : "Show"}
                    </button>
                  </div>
                </div>

                <div className="signup-field signup-full">
                  <label>Department</label>

                  <select
                    value={form.dept_id}
                    onChange={update("dept_id")}
                    required
                  >
                    <option value="">Select department</option>

                    {departments.map((d) => (
                      <option key={d.dept_id} value={d.dept_id}>
                        {d.dept_name}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="signup-field">
                  <label>CGPA</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    max="10"
                    value={form.cgpa}
                    onChange={update("cgpa")}
                    placeholder="8.50"
                    required
                  />
                </div>

                <div className="signup-field">
                  <label>Backlogs</label>
                  <input
                    type="number"
                    min="0"
                    value={form.backlogs}
                    onChange={update("backlogs")}
                    required
                  />
                </div>

                <div className="signup-field">
                  <label>Batch Year</label>
                  <input
                    type="number"
                    value={form.batch_year}
                    onChange={update("batch_year")}
                    required
                  />
                </div>

                <div className="signup-field">
                  <label>Phone</label>
                  <input
                    type="tel"
                    value={form.phone}
                    onChange={update("phone")}
                    placeholder="Optional"
                  />
                </div>
              </div>

              {error && <div className="signup-error">{error}</div>}

              <button type="submit" className="signup-button">
                Create Account
              </button>
            </form>

            <p className="signup-login-text">
              Already have an account?{" "}
              <Link to="/login">Sign in</Link>
            </p>

          </div>
        </div>
      </div>
    </div>
  );
}