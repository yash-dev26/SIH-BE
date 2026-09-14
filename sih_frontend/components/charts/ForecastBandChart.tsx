"use client";

import type { FreightForecast } from "@/lib/types";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

function fmt(iso: string) {
  return new Date(`${iso}T00:00:00`).toLocaleDateString("en-GB", { day: "2-digit", month: "short" });
}

export function ForecastBandChart({ forecast }: { forecast: FreightForecast }) {
  const historical = forecast.points.filter((p) => !p.isForecast);
  const forward = forecast.points.filter((p) => p.isForecast);
  const today = historical.at(-1)?.date ?? forecast.asOf;
  const entry = forward.reduce((lowest, point) => (point.p50 < lowest.p50 ? point : lowest), forward[0]);
  const entryIndex = forward.findIndex((point) => point.date === entry.date);
  const entryEnd = forward[Math.min(entryIndex + 1, forward.length - 1)];
  const data = forecast.points.map((p) => ({
    ...p,
    label: fmt(p.date),
    band: Number((p.p90 - p.p10).toFixed(2)),
  }));

  return (
    <div className="h-[260px] w-full px-2 pb-2 pt-2 sm:h-[280px]">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="#d5dee5" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="label" tick={{ fill: "#5B6B79", fontSize: 11 }} axisLine={{ stroke: "#d5dee5" }} />
          <YAxis
            tick={{ fill: "#5B6B79", fontSize: 11 }}
            axisLine={{ stroke: "#d5dee5" }}
            tickFormatter={(v: number) => `$${v}`}
            domain={["dataMin - 1", "dataMax + 1"]}
            width={48}
          />
          <Tooltip
            contentStyle={{ border: "1px solid #d5dee5", fontSize: 12, background: "#FBFBFA" }}
            formatter={(value, name) => [`$${Number(value ?? 0).toFixed(2)}/MT`, String(name)]}
          />
          <ReferenceArea
            x1={fmt(entry.date)}
            x2={fmt(entryEnd.date)}
            fill="#E8A33D"
            fillOpacity={0.12}
            strokeOpacity={0}
            label={{ value: "Entry window", fill: "#A66B15", fontSize: 10, position: "insideTop" }}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Area
            type="monotone"
            dataKey="p10"
            stackId="band"
            stroke="none"
            fill="transparent"
            name="p10 floor"
            legendType="none"
          />
          <Area
            type="monotone"
            dataKey="band"
            stackId="band"
            stroke="none"
            fill="#1C7293"
            fillOpacity={0.18}
            name="p10–p90 band"
          />
          <Line type="monotone" dataKey="p10" stroke="#1C7293" strokeDasharray="3 3" dot={false} strokeWidth={1} name="p10" />
          <Line type="monotone" dataKey="p50" stroke="#065A82" dot={false} strokeWidth={2} name="p50" />
          <Line type="monotone" dataKey="p90" stroke="#21295C" strokeDasharray="3 3" dot={false} strokeWidth={1} name="p90" />
          <Line
            type="monotone"
            dataKey="actual"
            stroke="#0F1B24"
            strokeWidth={1.5}
            dot={{ r: 2, fill: "#0F1B24" }}
            connectNulls={false}
            name="Historical / current"
          />
          <ReferenceLine
            x={fmt(today)}
            stroke="#E8A33D"
            strokeWidth={1.5}
            label={{ value: "Today", fill: "#E8A33D", fontSize: 11, position: "top" }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
