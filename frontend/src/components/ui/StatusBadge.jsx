import { statusLabel, statusVariant } from "../../utils/status";

// Colour + text together, so status is never conveyed by colour alone.
export function StatusBadge({ status }) {
  const variant = statusVariant(status);
  return (
    <span className={variant === "neutral" ? "badge" : `badge badge-${variant}`}>
      {statusLabel(status)}
    </span>
  );
}
