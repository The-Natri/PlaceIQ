import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import { homeRouteFor } from "./auth/homeRoute";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { AppLayout } from "./components/layout/AppLayout";
import { Loading } from "./components/ui/Feedback";
import { Login } from "./pages/auth/Login";
import { Signup } from "./pages/auth/Signup";
import { StudentDashboard } from "./pages/student/StudentDashboard";
import { AdminDrives } from "./pages/admin/AdminDrives";
import { AdminDriveDetail } from "./pages/admin/AdminDriveDetail";
import { AdminStudents } from "./pages/admin/AdminStudents";
import { AdminAnalytics } from "./pages/admin/AdminAnalytics";

function Home() {
  const { user, loading } = useAuth();
  if (loading) return <Loading label="Checking your session…" />;
  return <Navigate to={user ? homeRouteFor(user.role) : "/login"} replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />

      {/* Student area: one layout, guarded once for every page inside it */}
      <Route element={<ProtectedRoute role="student"><AppLayout /></ProtectedRoute>}>
        <Route path="/student" element={<StudentDashboard />} />
      </Route>

      {/* Admin / placement-cell area */}
      <Route element={<ProtectedRoute role="admin"><AppLayout /></ProtectedRoute>}>
        <Route path="/admin" element={<AdminDrives />} />
        <Route path="/admin/drives" element={<AdminDrives />} />
        <Route path="/admin/drives/:driveId" element={<AdminDriveDetail />} />
        <Route path="/admin/students" element={<AdminStudents />} />
        <Route path="/admin/analytics" element={<AdminAnalytics />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
