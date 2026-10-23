/**
 * Accessible tab bar. Controlled: the parent owns `active` (often synced to
 * the URL so a tab can be linked to or refreshed).
 *   tabs = [{ id: "drives", label: "Eligible Drives", count: 8 }, ...]
 * Arrow keys move between tabs, as the ARIA tabs pattern expects.
 */
export function Tabs({ tabs, active, onChange, label }) {
  function onKeyDown(event) {
    const index = tabs.findIndex((t) => t.id === active);
    const step = { ArrowRight: 1, ArrowLeft: -1 }[event.key];
    if (!step) return;
    event.preventDefault();
    const next = tabs[(index + step + tabs.length) % tabs.length];
    onChange(next.id);
    document.getElementById(`tab-${next.id}`)?.focus();
  }

  return (
    <div className="tabs" role="tablist" aria-label={label} onKeyDown={onKeyDown}>
      {tabs.map((tab) => (
        <button
          key={tab.id}
          id={`tab-${tab.id}`}
          type="button"
          role="tab"
          className="tab"
          aria-selected={tab.id === active}
          aria-controls={`panel-${tab.id}`}
          tabIndex={tab.id === active ? 0 : -1}
          onClick={() => onChange(tab.id)}
        >
          {tab.label}
          {tab.count !== undefined && tab.count !== null && <span className="tab-count">{tab.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function TabPanel({ id, active, children }) {
  if (id !== active) return null;
  return (
    <div id={`panel-${id}`} role="tabpanel" aria-labelledby={`tab-${id}`}>
      {children}
    </div>
  );
}
