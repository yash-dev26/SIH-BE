import { RiskBadge } from "@/components/recommendation/RiskBadge";
import { formatMt, formatUsd, formatUsdPerMt } from "@/lib/format";
import type { Recommendation } from "@/lib/types";
import { ArrowRight } from "lucide-react";

function Stat({ label, value, gold = false }: { label: string; value: string; gold?: boolean }) {
  return (
    <div className="min-w-0">
      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">{label}</p>
      <p className={`mt-1 font-serif text-2xl leading-none ${gold ? "text-gold" : "text-paper"}`}>{value}</p>
    </div>
  );
}

export function RecommendationCard({ rec }: { rec: Recommendation }) {
  const { summary, request } = rec;
  const forecastPoints = rec.forecast.points.filter((point) => point.isForecast);
  const entryPoint = forecastPoints.reduce(
    (lowest, point) => (point.p50 < lowest.p50 ? point : lowest),
    forecastPoints[0],
  );
  const entryIndex = forecastPoints.findIndex((point) => point.date === entryPoint.date);
  const entryEnd = forecastPoints[Math.min(entryIndex + 1, forecastPoints.length - 1)];
  const entryWindow = `${formatEntryDate(entryPoint.date)}–${formatEntryDate(entryEnd.date)}`;
  const expectedFreight = entryPoint.p50;
  const voyageFreightCost = expectedFreight * request.quantityMt;
  return (
    <section className="border border-midnight bg-ink text-paper shadow-[inset_4px_0_0_0_#E8A33D]">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 px-5 py-4 md:px-6">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-gold">What should I do?</p>
          <h2 className="mt-1 font-serif text-3xl leading-tight text-paper md:text-4xl">
            {summary.vesselClass} · {summary.contractType}
          </h2>
          <p className="mt-2 flex items-center gap-1.5 text-sm text-ice/75"><ArrowRight className="h-4 w-4 text-gold" /> Wait for market softening, then enter during {entryWindow}.</p>
        </div>
        <div className="flex items-center gap-2">
          {rec.demo ? (
            <span className="border border-gold/50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-gold">
              Mock / demo data
            </span>
          ) : (
            <span className="border border-white/20 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-ice/80">
              Mock adapter
            </span>
          )}
          <RiskBadge risk={summary.risk} />
        </div>
      </div>
      <div className="grid gap-5 px-5 py-5 sm:grid-cols-2 lg:grid-cols-5 md:px-6">
        <Stat label="Vessel class" value={summary.vesselClass} gold />
        <Stat label="Contract type" value={summary.contractType} />
        <Stat label="Market-entry window" value={entryWindow} gold />
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">Expected freight</p>
          <p className="mt-1 font-serif text-2xl leading-none text-paper">
            {formatUsdPerMt(expectedFreight)}
          </p>
          <p className="mt-1 text-xs text-ice/70">
            {formatUsd(voyageFreightCost)} calculated voyage freight · {formatMt(request.quantityMt)}
          </p>
        </div>
        <Stat label="Confidence" value={summary.confidence} />
      </div>
    </section>
  );
}

function formatEntryDate(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}
