import { createContext, useContext, useEffect, useState } from "react";
import { api } from "../api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  // user shape: { role: "student"|"admin", profile: {...} }
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      setLoading(false);
      return;
    }
    api
      .get("/auth/me")
      .then(setUser)
      .catch(() => localStorage.removeItem("token"))
      .finally(() => setLoading(false));
  }, []);

  async function afterLogin(loginResponsePromise) {
    const data = await loginResponsePromise;
    localStorage.setItem("token", data.token);
    const me = await api.get("/auth/me");
    setUser(me);
    return me;
  }

  const loginStudent = (email, password) =>
    afterLogin(api.post("/auth/student/login", { email, password }));

  const loginAdmin = (email, password) =>
    afterLogin(api.post("/auth/admin/login", { email, password }));

  const signupStudent = (payload) =>
    afterLogin(api.post("/auth/student/signup", payload));

  function logout() {
    localStorage.removeItem("token");
    setUser(null);
  }

  return (
    <AuthContext.Provider
      value={{ user, loading, loginStudent, loginAdmin, signupStudent, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
