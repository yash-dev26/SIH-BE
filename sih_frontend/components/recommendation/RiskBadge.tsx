import type { RiskLevel } from "@/lib/types";

const styles: Record<RiskLevel, string> = {
  Low: "bg-risk-low text-paper",
  Moderate: "bg-risk-med text-ink",
  High: "bg-risk-high text-paper",
};

export function RiskBadge({ risk }: { risk: RiskLevel }) {
  return (
    <span className={`inline-flex px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wider ${styles[risk]}`}>
      {risk} risk
    </span>
  );
}
