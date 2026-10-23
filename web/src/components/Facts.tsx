import type { ReactNode } from "react";

export function Facts({ items }: { items: [label: string, value: ReactNode][] }) {
  return (
    <dl className="facts">
      {items.map(([label, value]) => (
        <div className="fact" key={label}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}
