import type { ReactNode } from "react";

export function Notice({ title, children, tone }: { title: ReactNode; children?: ReactNode; tone?: "warn" | "danger" }) {
  return (
    <div className={`notice ${tone ? `notice--${tone}` : ""}`} role={tone === "danger" ? "alert" : undefined}>
      <strong>{title}</strong>
      {children && <span>{children}</span>}
    </div>
  );
}
