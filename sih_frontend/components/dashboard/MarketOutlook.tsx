import { Activity, ArrowDownRight, ArrowRight, ArrowUpRight, CalendarRange, Target } from "lucide-react";
import type { FreightForecast } from "@/lib/types";

function formatDate(iso: string) {
  return new Date(`${iso}T00:00:00`).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

export function MarketOutlook({ forecast }: { forecast: FreightForecast }) {
  const historical = forecast.points.filter((point) => !point.isForecast);
  const forward = forecast.points.filter((point) => point.isForecast);
  const current = historical.at(-1)?.actual ?? forecast.currentP50;
  const entry = forward.reduce((lowest, point) => (point.p50 < lowest.p50 ? point : lowest), forward[0]);
  const entryIndex = forward.findIndex((point) => point.date === entry.date);
  const entryEnd = forward[Math.min(entryIndex + 1, forward.length - 1)];
  const move = entry.p50 - current;
  const magnitude = Math.abs(move);
  const percent = current ? (magnitude / current) * 100 : 0;
  const isFalling = move < -0.15;
  const isRising = move > 0.15;
  const direction = isFalling ? "Rates easing" : isRising ? "Rates firming" : "Rates stable";
  const outlookTitle = isFalling ? "Freight rates expected to ease" : isRising ? "Freight rates expected to firm" : "Freight rates expected to hold steady";
  const DirectionIcon = isFalling ? ArrowDownRight : isRising ? ArrowUpRight : ArrowRight;
  const signal = ((entry.p90 - entry.p10) / entry.p50) * 100;
  const confidence = signal <= 18 ? "High" : signal <= 28 ? "Medium" : "Low";
  const action = isFalling
    ? "Wait for the forecasted softening, then secure the charter during this window."
    : isRising
      ? "Secure charter coverage before the modelled freight firming accelerates."
      : "Hold for the defined entry window; the model indicates limited timing value outside it.";

  return (
    <section className="border-b border-line bg-[#f7fafb] px-4 py-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-teal">Market outlook</p>
          <h2 className="mt-1 font-serif text-xl text-ink">{outlookTitle}</h2>
        </div>
        <span className="inline-flex w-fit items-center gap-1.5 border border-teal/25 bg-paper px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.13em] text-teal">
          <Activity className="h-3.5 w-3.5" /> {confidence} signal confidence
        </span>
      </div>

      <div className="mt-4 grid gap-px overflow-hidden border border-line bg-line sm:grid-cols-4">
        <div className="bg-paper px-3 py-3">
          <p className="text-[9px] font-bold uppercase tracking-[0.14em] text-muted">Expected direction</p>
          <div className="mt-2 flex items-center gap-1.5 text-sm font-semibold text-ink">
            <DirectionIcon className={`h-4 w-4 ${isFalling ? "text-risk-low" : isRising ? "text-risk-high" : "text-teal"}`} />
            {direction}
          </div>
          <p className="mt-1 text-xs text-muted">{magnitude.toFixed(2)} USD/MT · {percent.toFixed(1)}%</p>
        </div>
        <div className="bg-paper px-3 py-3">
          <p className="text-[9px] font-bold uppercase tracking-[0.14em] text-muted">Current freight</p>
          <p className="mt-2 text-sm font-semibold text-ink">${current.toFixed(2)} <span className="font-normal text-muted">/ MT</span></p>
          <p className="mt-1 text-xs text-muted">As of {formatDate(forecast.asOf)}</p>
        </div>
        <div className="bg-paper px-3 py-3">
          <p className="text-[9px] font-bold uppercase tracking-[0.14em] text-muted">Expected freight</p>
          <p className="mt-2 text-sm font-semibold text-ink">${entry.p50.toFixed(2)} <span className="font-normal text-muted">/ MT</span></p>
          <p className="mt-1 text-xs text-muted">Forecast p50 at projected low</p>
        </div>
        <div className="bg-[#e8f5ef] px-3 py-3 text-ink">
          <p className="text-[9px] font-bold uppercase tracking-[0.14em] text-risk-low">Optimal entry window</p>
          <p className="mt-2 flex items-center gap-1.5 text-sm font-semibold"><CalendarRange className="h-3.5 w-3.5 text-risk-low" /> {formatDate(entry.date)}–{formatDate(entryEnd.date)}</p>
          <p className="mt-1 text-xs text-muted">Projected lowest p50 window</p>
        </div>
      </div>
      <p className="mt-3 flex items-center gap-2 border border-risk-low/20 bg-[#e8f5ef] px-3 py-2 text-sm font-medium leading-5 text-ink"><Target className="h-4 w-4 shrink-0 text-risk-low" />{action}</p>
    </section>
  );
}
