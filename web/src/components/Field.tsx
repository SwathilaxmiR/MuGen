import { cloneElement, isValidElement, useId, type ReactElement, type ReactNode } from "react";

interface Props {
  label: ReactNode;
  hint?: ReactNode;
  error?: string | null;
  optional?: boolean;
  /** A single input/select/textarea; it receives id, aria-describedby and aria-invalid. */
  children: ReactElement;
}

/** Label + control + hint + error, wired for screen readers. */
export function Field({ label, hint, error, optional, children }: Props) {
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  const errId = error ? `${id}-err` : undefined;
  const control = isValidElement(children)
    ? cloneElement(children as ReactElement<Record<string, unknown>>, {
        id,
        "aria-describedby": [hintId, errId].filter(Boolean).join(" ") || undefined,
        "aria-invalid": error ? true : undefined,
      })
    : children;
  return (
    <div className="field">
      <label className="field__label" htmlFor={id}>
        {label} {optional && <span className="optional">(optional)</span>}
      </label>
      {control}
      {hint && (
        <p className="field__hint" id={hintId}>
          {hint}
        </p>
      )}
      {error && (
        <p className="field__error" id={errId} role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
