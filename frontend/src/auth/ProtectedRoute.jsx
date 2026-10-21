import { Navigate } from "react-router-dom";
import { useAuth } from "./AuthContext";
import { Loading } from "../components/ui/Feedback";

// role=undefined -> any logged-in user; role="student"|"admin" -> that role only.
export function ProtectedRoute({ role, children }) {
  const { user, loading } = useAuth();

  if (loading) return <Loading label="Checking your session…" />;
  if (!user) return <Navigate to="/login" replace />;
  if (role && user.role !== role) return <Navigate to="/" replace />;

  return children;
}
