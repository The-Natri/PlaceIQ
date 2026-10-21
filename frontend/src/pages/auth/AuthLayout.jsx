export function AuthLayout({ wide, children }) {
  return (
    <div className="auth-page">
      <div className={`auth-card ${wide ? "wide" : ""}`}>
        <div className="auth-brand">
          <span className="brand-mark">PI</span>
          <span>
            <div className="brand-name">PlaceIQ</div>
            <div className="brand-sub">College Placement Management System</div>
          </span>
        </div>
        {children}
      </div>
    </div>
  );
}
