import type { HTMLAttributes } from "react";

export function Panel({ className = "", ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <section
      className={`border border-line bg-paper ${className}`}
      {...props}
    />
  );
}

export function PanelHeader({ title, kicker }: { title: string; kicker?: string }) {
  return (
    <header className="flex items-baseline justify-between gap-3 border-b border-line px-4 py-2.5">
      {kicker ? (
        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">{kicker}</p>
      ) : null}
      <h2 className="font-serif text-lg leading-none text-ink">{title}</h2>
    </header>
  );
}
