/**
 * Label + control + hint/error, correctly wired together:
 * the label's htmlFor points at the control's id, and the error is linked
 * with aria-describedby so screen readers announce it.
 *
 *   <Field id="cgpa" label="CGPA" error={errors.cgpa} required>
 *     <input id="cgpa" ... />
 *   </Field>
 */
import { Children, cloneElement, isValidElement } from "react";

export function Field({ id, label, error, hint, required, className = "", children }) {
  const describedBy = error ? `${id}-error` : hint ? `${id}-hint` : undefined;
  const control = Children.only(children);
  const wired = isValidElement(control)
    ? cloneElement(control, {
        id,
        "aria-invalid": error ? "true" : undefined,
        "aria-describedby": describedBy,
      })
    : control;

  return (
    <div className={`field ${error ? "has-error" : ""} ${className}`}>
      <label htmlFor={id}>
        {label}
        {required && <span className="required" aria-hidden="true"> *</span>}
      </label>
      {wired}
      {error ? (
        <span id={`${id}-error`} className="field-error">{error}</span>
      ) : hint ? (
        <span id={`${id}-hint`} className="field-hint">{hint}</span>
      ) : null}
    </div>
  );
}
