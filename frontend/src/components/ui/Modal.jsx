import { useEffect, useRef } from "react";
import { X } from "lucide-react";

/**
 * Dialog box. Closes on Escape or a click on the backdrop, moves focus into
 * the dialog when it opens and back to where it was when it closes.
 */
export function Modal({ open, title, subtitle, onClose, footer, wide, children }) {
  const dialogRef = useRef(null);
  // Kept in a ref so the effect below runs only when the dialog opens —
  // parents usually pass a new onClose function on every render, and
  // re-running the effect would yank focus back to the first field while
  // the user is typing.
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!open) return undefined;
    const previouslyFocused = document.activeElement;
    const focusable = dialogRef.current?.querySelector(
      "input, select, textarea, button:not(.modal-close)"
    );
    (focusable || dialogRef.current)?.focus();

    function onKey(e) {
      if (e.key === "Escape") onCloseRef.current();
    }
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      previouslyFocused?.focus?.();
    };
  }, [open]);

  if (!open) return null;

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div
        ref={dialogRef}
        className={`modal ${wide ? "wide" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        tabIndex={-1}
      >
        <div className="modal-header">
          <div>
            <h2 id="modal-title">{title}</h2>
            {subtitle && <p>{subtitle}</p>}
          </div>
          <button type="button" className="btn btn-ghost btn-icon modal-close" onClick={onClose} aria-label="Close dialog">
            <X size={18} />
          </button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-footer">{footer}</div>}
      </div>
    </div>
  );
}
