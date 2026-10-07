import { Link, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { homeRouteFor } from "../auth/homeRoute";
import "./Navbar.css";

export function Navbar() {
  const { user, logout } = useAuth();
  const location = useLocation();

  function isActive(path) {
    return location.pathname === path;
  }

  return (
    <header className="app-navbar">
      <div className="navbar-inner">
        <div className="navbar-left">
          {/* "/" (Home) waits for auth to finish loading before redirecting,
              so the logo can't send a not-yet-loaded user to /admin. */}
          <Link
            to={user ? homeRouteFor(user.role) : "/"}
            className="navbar-brand"
          >
            <div className="brand-mark">PI</div>

            <div className="brand-text">
              <span className="brand-name">PlaceIQ</span>
              <span className="brand-subtitle">Placement Portal</span>
            </div>
          </Link>

          <nav className="navbar-links">
            {user?.role === "student" && (
              <Link
                to="/student"
                className={
                  isActive("/student")
                    ? "nav-link active"
                    : "nav-link"
                }
              >
                Dashboard
              </Link>
            )}

            {user?.role === "admin" && (
              <>
                <Link
                  to="/admin"
                  className={
                    isActive("/admin")
                      ? "nav-link active"
                      : "nav-link"
                  }
                >
                  Drives
                </Link>

                <Link
                  to="/admin/analytics"
                  className={
                    isActive("/admin/analytics")
                      ? "nav-link active"
                      : "nav-link"
                  }
                >
                  Analytics
                </Link>
              </>
            )}
          </nav>
        </div>

        {user && (
          <div className="navbar-right">
            <div className="user-info">
              <div className="user-avatar">
                {user.profile.name?.charAt(0)?.toUpperCase()}
              </div>

              <div className="user-details">
                <span className="user-name">{user.profile.name}</span>
                <span className="user-role">
                  {user.role === "student" ? "Student" : "Admin"}
                </span>
              </div>
            </div>

            <button className="logout-button" onClick={logout}>
              Logout
            </button>
          </div>
        )}
      </div>
    </header>
  );
}