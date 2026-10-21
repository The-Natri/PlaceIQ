/**
 * Horizontal bars in plain HTML (so long labels wrap and it reflows on a
 * phone). One series, so one colour for every bar; each value is printed
 * at the bar end, so there is nothing to hover for.
 *   rows = [{ key, label, value (number), display (string) }]
 */
export function BarList({ rows, max, label }) {
  const top = max ?? Math.max(1, ...rows.map((r) => r.value));
  return (
    <div className="bar-list" role="list" aria-label={label}>
      {rows.map((r) => (
        <div key={r.key} className="bar-row" role="listitem">
          <span className="bar-label" title={r.label}>{r.label}</span>
          <span className="bar-track" aria-hidden="true">
            <span className="bar-fill" style={{ width: `${Math.max(0, (r.value / top) * 100)}%` }} />
          </span>
          <span className="bar-value">{r.display}</span>
        </div>
      ))}
    </div>
  );
}
