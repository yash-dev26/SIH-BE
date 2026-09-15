import { Panel } from "@/components/ui/Panel";
import { formatUsd, formatUsdPerMt } from "@/lib/format";
import type { Recommendation, RiskLevel } from "@/lib/types";
import { AlertTriangle, GitFork, ShieldCheck, Info } from "lucide-react";

function headline(text: string) {
  // Extract just the first sentence for a cleaner headline
  const first = text.split(/[;\n]/)[0].trim();
  // Remove emoji prefixes and dashes if the backend sent the full human_readable_summary
  return first.replace(/^[-─]+\s*/, "").replace(/^[🚢🏆💰📈📅⚠️]+\s*/, "").trim();
}

export function RationalePanel({ rec }: { rec: Recommendation }) {
  const points = rec.rationale.points.slice(0, 5);
  return (
    <Panel>
      <div className="border-b border-line px-5 py-3">
        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Why this recommendation?</p>
        <h2 className="mt-1 font-serif text-xl leading-snug text-ink">{headline(rec.rationale.headline)}</h2>
      </div>

      {/* Key decision points */}
      <ol className="space-y-3 px-5 py-4">
        {points.map((p, i) => (
          <li key={`point-${i}`} className="flex gap-3 text-sm leading-relaxed text-ink">
            <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-gold/15 font-serif text-xs font-bold text-gold">
              {i + 1}
            </span>
            <span>{p}</span>
          </li>
        ))}
      </ol>

      {/* Binding constraints */}
      {rec.rationale.bindingConstraints.length > 0 && (
        <div className="border-t border-line px-5 py-3">
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">Binding constraints</p>
          <ul className="space-y-1">
            {rec.rationale.bindingConstraints.map((c, i) => (
              <li key={`constraint-${i}`} className="flex items-start gap-2 text-xs text-muted">
                <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-teal" />
                <span>{c}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Model provenance */}
      {rec.rationale.forecastUsed.length > 0 && (
        <div className="border-t border-dashed border-line px-5 py-3">
          <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">Forecast model</p>
          <div className="flex flex-wrap gap-x-5 gap-y-1">
            {rec.rationale.forecastUsed.map((f, i) => (
              <span key={`forecast-${i}`} className="font-mono text-[11px] text-muted">{f}</span>
            ))}
          </div>
        </div>
      )}
    </Panel>
  );
}

export function AlternativesPanel({ rec }: { rec: Recommendation }) {
  if (!rec.alternatives || rec.alternatives.length === 0) return null;

  return (
    <Panel>
      <div className="flex items-center justify-between border-b border-line bg-[#f7fafb] px-5 py-3">
        <div className="flex items-center gap-2.5">
          <GitFork className="h-4 w-4 text-teal" />
          <h2 className="font-serif text-xl text-ink">Alternative strategies</h2>
        </div>
        <span className="text-[10px] font-medium uppercase tracking-[0.12em] text-muted">Considered, not recommended</span>
      </div>
      <ul className="divide-y divide-line">
        {rec.alternatives.map((alt) => {
          return (
          <li key={alt.id} className="px-5 py-4">
            <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start">
              <div>
                <p className="text-[17px] font-semibold leading-none text-ink">{alt.title}</p>
                <p className="mt-2 font-mono text-xs text-muted">
                  {alt.vesselClass} <span className="mx-1.5 text-line">·</span> {alt.contractType}
                </p>
              </div>
            </div>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-muted">
              <span className="font-medium text-ink">Trade-off: </span>
              {alt.tradeoff}
            </p>
          </li>
          );
        })}
      </ul>
    </Panel>
  );
}

export function RisksPanel({ rec }: { rec: Recommendation }) {
  const risks = rec.rationale.importantRisks;
  const mitigations = rec.rationale.riskMitigations || [];

  if (!risks || risks.length === 0) return null;

  return (
    <Panel>
      <div className="flex items-center gap-2.5 border-b border-line bg-[#f7fafb] px-5 py-3">
        <AlertTriangle className="h-5 w-5 text-teal" />
        <h2 className="font-serif text-xl text-ink">Key Risks &amp; Mitigation</h2>
      </div>
      <ul className="divide-y divide-line">
        {risks.map((item, i) => {
          const mitigation = mitigations[i] || "";
          return (
            <li key={`risk-${i}`} className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-start sm:justify-between">
              <div className="max-w-4xl space-y-2">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-risk-med" />
                  <p className="text-[15px] font-semibold leading-snug text-ink">{item}</p>
                </div>
                {mitigation && (
                  <div className="ml-6 flex items-start gap-2 rounded-md bg-[#f0faf5] px-3 py-2">
                    <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-risk-low" />
                    <p className="text-sm leading-relaxed text-muted">{mitigation}</p>
                  </div>
                )}
              </div>
              <SeverityBadge risk={rec.summary.risk} />
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}

function SeverityBadge({ risk }: { risk: RiskLevel }) {
  const styles: Record<RiskLevel, string> = {
    Low: "border-risk-low/60 bg-[#e8f5ef] text-risk-low",
    Moderate: "border-risk-med/60 bg-[#fff8e9] text-risk-med",
    High: "border-risk-high/50 bg-[#fff0ee] text-risk-high",
  };

  return (
    <span className={`inline-flex shrink-0 items-center gap-2 border px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.13em] ${styles[risk]}`}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" /> {risk}
    </span>
  );
}
