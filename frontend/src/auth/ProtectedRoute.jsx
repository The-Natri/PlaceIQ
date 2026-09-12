import { Navigate } from "react-router-dom";
import { useAuth } from "./AuthContext";

// role=undefined -> any logged-in user; role="student"|"admin" -> that role only.
export function ProtectedRoute({ role, children }) {
  const { user, loading } = useAuth();

  if (loading) return <p>Loading...</p>;
  if (!user) return <Navigate to="/login" replace />;
  if (role && user.role !== role) return <Navigate to="/" replace />;

  return children;
}
