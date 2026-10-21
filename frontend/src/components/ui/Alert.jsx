import { CircleCheck, CircleX, Info, TriangleAlert, X } from "lucide-react";

const ICONS = { error: CircleX, success: CircleCheck, info: Info, warning: TriangleAlert };

/** Inline message box. `variant`: error | success | info | warning. */
export function Alert({ variant = "info", children, onClose }) {
  if (!children) return null;
  const Icon = ICONS[variant];
  return (
    <div className={`alert alert-${variant}`} role={variant === "error" ? "alert" : "status"}>
      <Icon size={18} aria-hidden="true" />
      <div className="alert-body">{children}</div>
      {onClose && (
        <button type="button" className="alert-close" onClick={onClose} aria-label="Dismiss message">
          <X size={16} />
        </button>
      )}
    </div>
  );
}
