import { Navigate, Route, Routes } from "react-router-dom";
import { Navbar } from "./components/Navbar";
import { useAuth } from "./auth/AuthContext";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { Login } from "./pages/Login";
import { Signup } from "./pages/Signup";
import { StudentDashboard } from "./pages/StudentDashboard";
import { AdminDashboard } from "./pages/AdminDashboard";
import { AdminDriveDetail } from "./pages/AdminDriveDetail";
import { AdminAnalytics } from "./pages/AdminAnalytics";

function Home() {
  const { user, loading } = useAuth();
  if (loading) return <p>Loading...</p>;
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to={user.role === "student" ? "/student" : "/admin"} replace />;
}

export default function App() {
  return (
    <>
      <Navbar />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route
          path="/student"
          element={<ProtectedRoute role="student"><StudentDashboard /></ProtectedRoute>}
        />
        <Route
          path="/admin"
          element={<ProtectedRoute role="admin"><AdminDashboard /></ProtectedRoute>}
        />
        <Route
          path="/admin/drives/:driveId"
          element={<ProtectedRoute role="admin"><AdminDriveDetail /></ProtectedRoute>}
        />
        <Route
          path="/admin/analytics"
          element={<ProtectedRoute role="admin"><AdminAnalytics /></ProtectedRoute>}
        />
      </Routes>
    </>
  );
}
