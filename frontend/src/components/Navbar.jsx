import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export function Navbar() {
  const { user, logout } = useAuth();

  return (
    <nav className="navbar">
      <span className="navbar-brand">Placement Cell</span>
      {user?.role === "student" && (
        <Link to="/student">Dashboard</Link>
      )}
      {user?.role === "admin" && (
        <>
          <Link to="/admin">Drives</Link>
          <Link to="/admin/analytics">Analytics</Link>
        </>
      )}
      <span className="navbar-spacer" />
      {user && (
        <>
          <span>{user.profile.name} ({user.role})</span>
          <button onClick={logout}>Logout</button>
        </>
      )}
    </nav>
  );
}
