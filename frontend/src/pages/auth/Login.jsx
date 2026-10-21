import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { LogIn } from "lucide-react";
import { useAuth } from "../../auth/AuthContext";
import { homeRouteFor } from "../../auth/homeRoute";
import { Alert } from "../../components/ui/Alert";
import { Field } from "../../components/ui/Field";
import { AuthLayout } from "./AuthLayout";

export function Login() {
  const { user, loginStudent, loginAdmin } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState("student");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState({});
  const [serverError, setServerError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (user) return <Navigate to={homeRouteFor(user.role)} replace />;

  function validate() {
    const next = {};
    if (!email.trim()) next.email = "Enter your email address.";
    else if (!/^\S+@\S+\.\S+$/.test(email)) next.email = "That doesn't look like an email address.";
    if (!password) next.password = "Enter your password.";
    setErrors(next);
    return Object.keys(next).length === 0;
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setServerError("");
    if (!validate()) return;
    setSubmitting(true);
    try {
      const me = mode === "student" ? await loginStudent(email, password) : await loginAdmin(email, password);
      navigate(homeRouteFor(me.role));
    } catch (err) {
      setServerError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout>
      <div>
        <h1>Sign in</h1>
        <p className="page-subtitle">Use your campus email and password.</p>
      </div>

      <div className="segmented" role="group" aria-label="Account type">
        {[["student", "Student"], ["admin", "Admin / TPO"]].map(([value, label]) => (
          <button
            key={value}
            type="button"
            aria-pressed={mode === value}
            onClick={() => { setMode(value); setServerError(""); }}
          >
            {label}
          </button>
        ))}
      </div>

      <form onSubmit={handleSubmit} noValidate className="form-grid" style={{ gridTemplateColumns: "1fr" }}>
        <Field id="login-email" label="Email address" error={errors.email} required>
          <input
            type="email"
            autoComplete="username"
            placeholder={mode === "student" ? "you@campus.edu" : "tpo@campus.edu"}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </Field>

        <Field id="login-password" label="Password" error={errors.password} required>
          <PasswordInput
            value={password}
            onChange={setPassword}
            show={showPassword}
            onToggle={() => setShowPassword(!showPassword)}
            autoComplete="current-password"
          />
        </Field>

        <Alert variant="error">{serverError}</Alert>

        <button type="submit" className="btn btn-primary" disabled={submitting}>
          <LogIn size={16} aria-hidden="true" /> {submitting ? "Signing in…" : "Sign in"}
        </button>
      </form>

      {mode === "student" && (
        <p className="auth-footer">
          New student? <Link to="/signup">Create an account</Link>
        </p>
      )}
    </AuthLayout>
  );
}

// The id/aria props from <Field> land on the wrapper's <input>.
export function PasswordInput({ value, onChange, show, onToggle, autoComplete, ...rest }) {
  return (
    <div className="password-wrap">
      <input
        {...rest}
        type={show ? "text" : "password"}
        autoComplete={autoComplete}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
      <button
        type="button"
        className="password-toggle"
        onClick={onToggle}
        aria-label={show ? "Hide password" : "Show password"}
      >
        {show ? "Hide" : "Show"}
      </button>
    </div>
  );
}
