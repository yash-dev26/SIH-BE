"use client";

import { ForecastBandChart } from "@/components/charts/ForecastBandChart";
import { SamundraSetuLogo } from "@/components/brand/SamundraSetuLogo";
import { MarketOutlook } from "@/components/dashboard/MarketOutlook";
import { RouteMap } from "@/components/map/RouteMap";
import { AlternativesPanel, RationalePanel, RisksPanel } from "@/components/recommendation/RationalePanel";
import { RecommendationCard } from "@/components/recommendation/RecommendationCard";
import { Panel } from "@/components/ui/Panel";
import { formatLaycan, formatMt, titleCase } from "@/lib/format";
import type { Recommendation } from "@/lib/types";
import Link from "next/link";

export function DashboardView({ rec }: { rec: Recommendation }) {
  const { request } = rec;
  return (
    <div className="min-h-screen bg-ice">
      <header className="border-b border-midnight bg-ink text-paper">
        <div className="mx-auto flex max-w-[1440px] flex-wrap items-center justify-between gap-4 px-5 py-3">
          <Link href="/" className="flex items-center gap-2.5">
            <SamundraSetuLogo className="w-9" />
            <span className="font-serif text-lg tracking-tight text-paper">Samundra Setu</span>
            <span className="hidden h-4 w-px bg-white/20 sm:block" />
            <span className="hidden text-[9px] uppercase tracking-[0.16em] text-ice/55 sm:inline">Maritime intelligence system</span>
          </Link>
        </div>
        <div className="mx-auto grid max-w-[1440px] grid-cols-2 gap-px border-t border-white/10 bg-white/10 sm:grid-cols-3 lg:grid-cols-6">
          {[
            ["Route", `${request.origin} → ${request.destination}`],
            ["Commodity", request.commodity],
            ["Quantity", formatMt(request.quantityMt)],
            ["Laycan", formatLaycan(request.laycanStart, request.laycanEnd)],
            ["Risk tolerance", titleCase(request.riskTolerance)],
            ["ID", rec.id],
          ].map(([k, v]) => (
            <div key={k} className="bg-ink px-4 py-3">
              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted">{k}</p>
              <p className="mt-1 text-sm text-paper">{v}</p>
            </div>
          ))}
        </div>
      </header>

      <main className="mx-auto grid max-w-[1440px] gap-4 px-5 py-4">
        <RecommendationCard rec={rec} />
        <Panel>
          <MarketOutlook forecast={rec.forecast} />
          <ForecastBandChart forecast={rec.forecast} />
        </Panel>
        <RationalePanel rec={rec} />
        <Panel>
          <div className="border-b border-line px-4 py-2.5">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted">Route & port feasibility</p>
            <h2 className="font-serif text-lg text-ink">Can the recommended vessel execute this movement?</h2>
          </div>
          <RouteMap rec={rec} />
        </Panel>
        <div className="grid gap-4 xl:grid-cols-2">
          <RisksPanel rec={rec} />
          <AlternativesPanel rec={rec} />
        </div>
      </main>
    </div>
  );
}
