import { Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";

export function PageHeader({ eyebrow, title, subtitle, actions, backTo, backLabel }) {
  return (
    <div className="page-header">
      <div>
        {backTo && (
          <Link to={backTo} className="back-link">
            <ArrowLeft size={15} aria-hidden="true" /> {backLabel || "Back"}
          </Link>
        )}
        {eyebrow && <div className="page-eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
        {subtitle && <p className="page-subtitle">{subtitle}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  );
}

export function Card({ title, subtitle, actions, flush, children, className = "" }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <div className="card-header">
          <div>
            {title && <h2>{title}</h2>}
            {subtitle && <p>{subtitle}</p>}
          </div>
          {actions && <div className="inline-actions">{actions}</div>}
        </div>
      )}
      <div className={`card-body ${flush ? "flush" : ""}`}>{children}</div>
    </section>
  );
}

export function StatCard({ icon: Icon, label, value, hint }) {
  return (
    <div className="stat">
      {Icon && <div className="stat-icon"><Icon size={20} aria-hidden="true" /></div>}
      <div>
        <div className="stat-label">{label}</div>
        <div className="stat-value">{value}</div>
        {hint && <div className="stat-hint">{hint}</div>}
      </div>
    </div>
  );
}

export function CompanyCell({ name, sub }) {
  return (
    <div className="company-cell">
      <div className="company-logo" aria-hidden="true">{name?.charAt(0)}</div>
      <div>
        <div>{name}</div>
        {sub && <div className="cell-sub">{sub}</div>}
      </div>
    </div>
  );
}
