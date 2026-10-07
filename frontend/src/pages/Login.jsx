import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { homeRouteFor } from "../auth/homeRoute";
import "./Login.css";

export function Login() {
  const [mode, setMode] = useState("student");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");

  const { loginStudent, loginAdmin } = useAuth();
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");

    try {
      const me =
        mode === "student"
          ? await loginStudent(email, password)
          : await loginAdmin(email, password);

      navigate(homeRouteFor(me.role));
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="login-page">
      <div className="login-container">

        <div className="login-brand">
          <div className="brand-logo">PI</div>

          <h1>PlaceIQ</h1>

          <h2>
            Your Placement Journey
            <br />
            Starts Here.
          </h2>

          <p className="brand-description">
            Discover opportunities, track applications and take the next
            step towards your career.
          </p>

          <div className="brand-features">
            <span>✓ Explore placement drives</span>
            <span>✓ Track your applications</span>
            <span>✓ Manage offers easily</span>
          </div>
        </div>

        <div className="login-section">
          <div className="login-card">

            <div className="login-heading">
              <span className="welcome-text">WELCOME BACK</span>
              <h2>Sign in to PlaceIQ</h2>
              <p>Enter your credentials to access your account.</p>
            </div>

            <div className="login-tabs">
              <button
                type="button"
                className={mode === "student" ? "login-tab active" : "login-tab"}
                onClick={() => {
                  setMode("student");
                  setError("");
                }}
              >
                Student
              </button>

              <button
                type="button"
                className={mode === "admin" ? "login-tab active" : "login-tab"}
                onClick={() => {
                  setMode("admin");
                  setError("");
                }}
              >
                Admin / TPO
              </button>
            </div>

            <form onSubmit={handleSubmit} className="login-form">

              <div className="input-group">
                <label htmlFor="email">Email address</label>

                <div className="input-wrapper">
                  <span className="input-icon">✉</span>

                  <input
                    id="email"
                    type="email"
                    placeholder={
                      mode === "student"
                        ? "student@college.edu"
                        : "admin@college.edu"
                    }
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                  />
                </div>
              </div>

              <div className="input-group">
                <label htmlFor="password">Password</label>

                <div className="input-wrapper">
                  <span className="input-icon">🔒</span>

                  <input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    placeholder="Enter your password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />

                  <button
                    type="button"
                    className="password-toggle"
                    onClick={() => setShowPassword(!showPassword)}
                  >
                    {showPassword ? "Hide" : "Show"}
                  </button>
                </div>
              </div>

              {error && <div className="login-error">{error}</div>}

              <button className="login-button" type="submit">
                Sign In
              </button>

            </form>

            {mode === "student" && (
              <p className="signup-text">
                Don't have an account?{" "}
                <Link to="/signup">Create account</Link>
              </p>
            )}

            <p className="login-footer">
              Secure Placement Management Portal
            </p>

          </div>
        </div>
      </div>
    </div>
  );
}