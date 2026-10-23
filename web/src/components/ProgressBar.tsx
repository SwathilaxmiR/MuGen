interface Props {
  value: number | null; // null = indeterminate
  label: string;
}

export function ProgressBar({ value, label }: Props) {
  return (
    <div
      className="progress"
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={value ?? undefined}
    >
      <div
        className={`progress__bar ${value === null ? "progress__bar--indeterminate" : ""}`}
        style={{ width: `${Math.max(3, value ?? 30)}%` }}
      />
    </div>
  );
}
