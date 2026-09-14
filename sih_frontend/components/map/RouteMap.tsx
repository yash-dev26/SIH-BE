"use client";

import type { Recommendation } from "@/lib/types";
import dynamic from "next/dynamic";

const Inner = dynamic(() => import("./RouteMapInner").then((m) => m.RouteMapInner), {
  ssr: false,
  loading: () => <div className="flex h-[320px] items-center justify-center bg-ice text-sm text-muted">Loading chart of the sea…</div>,
});

const tone: Record<string, string> = {
  feasible: "text-risk-low",
  marginal: "text-risk-med",
  infeasible: "text-risk-high",
};

export function RouteMap({ rec }: { rec: Recommendation }) {
  const port = rec.destinationPort;
  return (
    <div>
      <Inner rec={rec} />
      <div className="grid grid-cols-2 gap-px border-t border-line bg-line sm:grid-cols-4">
        {[
          ["Max draft", `${port.maxDraftM} m`],
          ["Max LOA", `${port.maxLoaM} m`],
          ["Max beam", `${port.maxBeamM} m`],
          ["Handling", `${port.handlingRateMtpd.toLocaleString()} MT/d`],
        ].map(([k, v]) => (
          <div key={k} className="bg-paper px-3 py-2">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted">{k}</p>
            <p className="text-sm font-semibold text-ink">{v}</p>
          </div>
        ))}
      </div>
      <ul className="divide-y divide-line">
        {rec.vesselOptions.map((v) => (
          <li key={v.vesselClassId} className="grid grid-cols-[7.5rem_5.5rem_1fr] items-center gap-3 px-3 py-2 text-sm">
            <span className="font-medium text-ink">
              {v.vesselClassName}
              {v.vesselClassId === rec.summary.vesselClassId ? (
                <span className="ml-1.5 text-[10px] font-semibold uppercase tracking-wider text-gold">Rec</span>
              ) : null}
            </span>
            <span className={`text-[11px] font-semibold uppercase tracking-wider ${tone[v.feasibility]}`}>
              {v.feasibility}
            </span>
            <span className="truncate text-xs text-muted">{v.reason}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
