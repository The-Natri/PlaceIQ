import { useEffect, useState } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import {
  Briefcase,
  ChartColumn,
  ClipboardList,
  LayoutDashboard,
  LogOut,
  Menu,
  Sparkles,
  Users,
} from "lucide-react";
import { useAuth } from "../../auth/AuthContext";
import { homeRouteFor } from "../../auth/homeRoute";
import { initials } from "../../utils/format";

// Sidebar entries per role. Student "pages" are tabs of one dashboard,
// linked with ?tab= so each can be bookmarked.
const NAV = {
  student: [
    { to: "/student?tab=overview", label: "Overview", icon: LayoutDashboard, tab: "overview" },
    { to: "/student?tab=drives", label: "Eligible Drives", icon: Briefcase, tab: "drives" },
    { to: "/student?tab=applications", label: "My Applications", icon: ClipboardList, tab: "applications" },
  ],
  admin: [
    { to: "/admin/drives", label: "Placement Drives", icon: Briefcase },
    { to: "/admin/students", label: "Students", icon: Users },
    { to: "/admin/analytics", label: "Analytics", icon: ChartColumn },
  ],
};

export function AppLayout() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [navOpen, setNavOpen] = useState(false);

  // Close the mobile drawer whenever the page changes.
  useEffect(() => setNavOpen(false), [location.pathname, location.search]);

  const items = NAV[user.role] || [];
  const currentTab = new URLSearchParams(location.search).get("tab") || "overview";

  function isActive(item) {
    if (item.tab) return location.pathname === "/student" && currentTab === item.tab;
    return location.pathname.startsWith(item.to) || (item.to === "/admin/drives" && location.pathname === "/admin");
  }

  return (
    <div className={`app-shell ${navOpen ? "nav-open" : ""}`}>
      <aside className="sidebar" aria-label="Main navigation">
        <Link to={homeRouteFor(user.role)} className="sidebar-brand">
          <span className="brand-mark">PI</span>
          <span>
            <div className="brand-name">PlaceIQ</div>
            <div className="brand-sub">Placement Management</div>
          </span>
        </Link>

        <div className="sidebar-section">{user.role === "student" ? "Student" : "Placement Cell"}</div>
        <ul className="nav-list">
          {items.map((item) => {
            const Icon = item.icon;
            const active = isActive(item);
            return (
              <li key={item.to}>
                {/* Plain Link, not NavLink: NavLink marks every item whose path
                    matches as active, and the student items all share /student. */}
                <Link
                  to={item.to}
                  className={`nav-item ${active ? "active" : ""}`}
                  aria-current={active ? "page" : undefined}
                >
                  <Icon size={18} aria-hidden="true" />
                  {item.label}
                </Link>
              </li>
            );
          })}
        </ul>

        <div className="sidebar-footer">
          <Sparkles size={13} aria-hidden="true" /> All data in this system is synthetic.
        </div>
      </aside>
      <div className="sidebar-scrim" onClick={() => setNavOpen(false)} aria-hidden="true" />

      <div className="main-col">
        <header className="topbar">
          <button
            type="button"
            className="btn btn-ghost btn-icon menu-toggle"
            onClick={() => setNavOpen(true)}
            aria-label="Open navigation"
          >
            <Menu size={20} />
          </button>
          <span className="topbar-title">
            {user.role === "student" ? "Student Portal" : "Placement Cell Console"}
          </span>
          <span className="topbar-spacer" />
          <div className="user-chip">
            <span className="user-avatar" aria-hidden="true">{initials(user.profile.name)}</span>
            <span className="user-meta">
              <span className="user-name">{user.profile.name}</span>
              <span className="user-role">
                {user.role === "student" ? user.profile.reg_no : user.profile.role}
              </span>
            </span>
          </div>
          <button type="button" className="btn btn-secondary btn-sm" onClick={logout}>
            <LogOut size={15} aria-hidden="true" /> Logout
          </button>
        </header>

        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
