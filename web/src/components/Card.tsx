import type { ReactNode } from "react";

interface Props {
  title?: ReactNode;
  aside?: ReactNode;
  children: ReactNode;
  as?: "section" | "div";
}

export function Card({ title, aside, children, as: Tag = "section" }: Props) {
  return (
    <Tag className="card">
      {(title || aside) && (
        <div className="card__head">
          {title && <h2>{title}</h2>}
          {aside}
        </div>
      )}
      {children}
    </Tag>
  );
}
