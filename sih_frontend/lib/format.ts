export function formatMt(value: number): string {
  return `${new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 }).format(value)} MT`;
}

export function formatUsdPerMt(value: number): string {
  return `$${value.toFixed(2)}/MT`;
}

export function formatUsd(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatDate(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export function formatLaycan(start: string, end: string): string {
  return `${formatDate(start)} – ${formatDate(end)}`;
}

export function titleCase(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
