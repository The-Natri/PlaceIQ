import { Alert } from "./Alert";
import { EmptyState, Loading } from "./Feedback";

/**
 * Table with built-in loading, error and empty states.
 *   columns = [{ key, header, render?: (row) => node, className?: "num" }]
 *   rowKey  = (row) => unique key
 */
export function DataTable({
  columns,
  rows,
  rowKey,
  loading,
  error,
  emptyTitle = "Nothing here yet",
  emptyMessage,
  onRowClick,
  caption,
}) {
  if (error) {
    return <div className="card-body"><Alert variant="error">{error}</Alert></div>;
  }
  if (loading && !rows) return <Loading />;
  if (!rows || rows.length === 0) {
    return <EmptyState title={emptyTitle} message={emptyMessage} />;
  }

  return (
    <div className="table-wrap" style={{ opacity: loading ? 0.6 : 1 }}>
      <table className="table">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key} scope="col" className={col.className}>{col.header}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={rowKey(row)}
              className={onRowClick ? "clickable" : undefined}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
            >
              {columns.map((col) => (
                <td key={col.key} className={col.className}>
                  {col.render ? col.render(row) : row[col.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
