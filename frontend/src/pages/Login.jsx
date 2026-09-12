import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export function Login() {
  const [mode, setMode] = useState("student"); // "student" | "admin"
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const { loginStudent, loginAdmin } = useAuth();
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    try {
      const me = mode === "student"
        ? await loginStudent(email, password)
        : await loginAdmin(email, password);
      navigate(me.role === "student" ? "/student" : "/admin");
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="page-narrow">
      <h1>Login</h1>

      <div className="tab-row">
        <button
          className={mode === "student" ? "tab active" : "tab"}
          onClick={() => setMode("student")}
          type="button"
        >
          Student
        </button>
        <button
          className={mode === "admin" ? "tab active" : "tab"}
          onClick={() => setMode("admin")}
          type="button"
        >
          Admin / TPO
        </button>
      </div>

      <form onSubmit={handleSubmit}>
        <label>
          Email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </label>
        <label>
          Password
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </label>
        {error && <p className="error">{error}</p>}
        <button type="submit">Login</button>
      </form>

      {mode === "student" && (
        <p>
          No account? <Link to="/signup">Sign up</Link>
        </p>
      )}
    </div>
  );
}
