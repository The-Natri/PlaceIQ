import { Inbox, LoaderCircle } from "lucide-react";

export function Loading({ label = "Loading…" }) {
  return (
    <div className="loading" role="status">
      <LoaderCircle size={20} className="spin" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

export function EmptyState({ icon: Icon = Inbox, title, message, action }) {
  return (
    <div className="empty-state">
      <div className="empty-icon"><Icon size={22} aria-hidden="true" /></div>
      <h3>{title}</h3>
      {message && <p>{message}</p>}
      {action}
    </div>
  );
}
