"use client";

import React, { useState } from "react";
import type { VoyageWeather, DailyWaypoint } from "@/lib/types";
import {
  Waves,
  Wind,
  ShieldCheck,
  AlertTriangle,
  Compass,
  Clock,
  Fuel,
  CloudSun,
  Navigation,
  ChevronRight,
  Info,
} from "lucide-react";

interface VoyageWeatherTrackerProps {
  weather?: VoyageWeather;
}

export function VoyageWeatherTracker({ weather }: VoyageWeatherTrackerProps) {
  const [selectedDay, setSelectedDay] = useState<number>(0);

  if (!weather || !weather.daily_waypoints || weather.daily_waypoints.length === 0) {
    return (
      <div className="border border-midnight/50 bg-ink/50 p-5 rounded-lg text-muted text-sm flex items-center gap-2">
        <CloudSun className="w-5 h-5 text-gold animate-pulse" />
        <span>Live ocean weather dataset loading or unavailable for this route.</span>
      </div>
    );
  }

  const activeWaypoint: DailyWaypoint =
    weather.daily_waypoints.find((wp) => wp.day === selectedDay) || weather.daily_waypoints[0];

  const getStatusColorClass = (color: string) => {
    switch (color) {
      case "GREEN":
        return "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
      case "YELLOW":
        return "bg-amber-500/10 text-amber-400 border-amber-500/30";
      case "RED":
        return "bg-rose-500/10 text-rose-400 border-rose-500/30";
      default:
        return "bg-blue-500/10 text-blue-400 border-blue-500/30";
    }
  };

  return (
    <section className="border border-midnight bg-ink text-paper shadow-xl rounded-none overflow-hidden my-6">
      {/* Header Banner */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-white/10 px-5 py-4 md:px-6 bg-paper/5">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-gold/10 border border-gold/30 rounded-lg text-gold">
            <Waves className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-gold">
                Live Maritime Weather & Oceanic Intelligence
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-white/10 text-ice/80">
                {weather.transit_days} Days Voyage
              </span>
            </div>
            <h3 className="mt-0.5 font-serif text-xl font-medium text-paper">
              {weather.origin_port_name} → {weather.destination_port_name} ({weather.sea_distance_nm.toLocaleString()} NM)
            </h3>
          </div>
        </div>

        {/* Overall Status Badge */}
        <div className="flex items-center gap-3">
          <div
            className={`flex items-center gap-2 px-3 py-1.5 border rounded-full text-xs font-semibold uppercase tracking-wider ${getStatusColorClass(
              weather.status_color
            )}`}
          >
            {weather.status_color === "RED" ? (
              <AlertTriangle className="w-4 h-4 text-rose-400" />
            ) : (
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
            )}
            <span>{weather.overall_status}</span>
          </div>

          <div className="text-right">
            <div className="text-[10px] uppercase tracking-wider text-muted font-semibold">
              Safety Score
            </div>
            <div className="font-serif text-2xl font-bold text-gold">
              {weather.safety_score}
              <span className="text-xs text-muted font-sans font-normal">/100</span>
            </div>
          </div>
        </div>
      </div>

      {/* Summary KPI Strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 border-b border-white/10 bg-midnight/40 divide-x divide-white/5">
        <div className="p-4 flex items-center gap-3">
          <Waves className="w-5 h-5 text-cyan-400 shrink-0" />
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted">Peak Wave Height</p>
            <p className="text-lg font-serif font-medium text-paper">
              {weather.max_wave_height_m} m
            </p>
          </div>
        </div>

        <div className="p-4 flex items-center gap-3">
          <Wind className="w-5 h-5 text-sky-400 shrink-0" />
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted">Max Wind Speed</p>
            <p className="text-lg font-serif font-medium text-paper">
              {weather.max_wind_speed_kts} knots
            </p>
          </div>
        </div>

        <div className="p-4 flex items-center gap-3">
          <Clock className="w-5 h-5 text-amber-400 shrink-0" />
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted">Estimated Delay</p>
            <p className="text-lg font-serif font-medium text-paper">
              {weather.estimated_delay_hours > 0 ? `+${weather.estimated_delay_hours} hrs` : "On Schedule"}
            </p>
          </div>
        </div>

        <div className="p-4 flex items-center gap-3">
          <Fuel className="w-5 h-5 text-rose-400 shrink-0" />
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted">Bunker Surcharge</p>
            <p className="text-lg font-serif font-medium text-paper">
              {weather.estimated_fuel_surcharge_pct > 0 ? `+${weather.estimated_fuel_surcharge_pct}%` : "Baseline"}
            </p>
          </div>
        </div>
      </div>

      {/* Weather Alerts if any */}
      {weather.weather_alerts && weather.weather_alerts.length > 0 && (
        <div className="bg-amber-500/10 border-b border-amber-500/20 px-5 py-3 flex items-start gap-2.5 text-xs text-amber-200">
          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold uppercase tracking-wider mr-1">Route Advisories:</span>
            {weather.weather_alerts.join(" • ")}
          </div>
        </div>
      )}

      {/* 7-Day Voyage Timeline Selector */}
      <div className="p-5 md:p-6 space-y-5">
        <div>
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-xs font-semibold uppercase tracking-[0.16em] text-gold flex items-center gap-1.5">
              <Navigation className="w-3.5 h-3.5 text-gold" />
              Day-By-Day Voyage Weather Timeline
            </h4>
            <span className="text-[11px] text-ice/60 italic">
              Click a day to view detailed sea conditions & waypoints
            </span>
          </div>

          <div className="grid grid-cols-4 sm:grid-cols-8 gap-2">
            {weather.daily_waypoints.map((wp) => {
              const isSelected = wp.day === selectedDay;
              const hasAlert = Boolean(wp.alert);

              return (
                <button
                  key={wp.day}
                  onClick={() => setSelectedDay(wp.day)}
                  className={`p-3 border text-left transition-all duration-150 relative ${
                    isSelected
                      ? "border-gold bg-gold/15 text-paper shadow-md"
                      : "border-white/10 bg-midnight/30 hover:border-gold/50 text-ice/80 hover:bg-midnight/60"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-muted">
                      Day {wp.day}
                    </span>
                    {hasAlert && <span className="w-2 h-2 rounded-full bg-rose-400 animate-pulse" />}
                  </div>
                  <div className="mt-1 text-sm font-serif font-medium truncate">
                    {wp.day === 0 ? "Origin" : wp.day === weather.transit_days ? "Dest." : `${wp.wave_height_m}m`}
                  </div>
                  <div className="mt-0.5 text-[10px] text-ice/60 truncate">
                    {wp.sea_state.split(" ")[0]}
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Selected Waypoint Detailed Card */}
        {activeWaypoint && (
          <div className="border border-gold/30 bg-paper/5 p-4 md:p-5 rounded-none space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/10 pb-3">
              <div>
                <span className="text-[10px] font-semibold uppercase tracking-widest text-gold">
                  Waypoint Detail · Day {activeWaypoint.day} ({activeWaypoint.date})
                </span>
                <h5 className="font-serif text-lg text-paper flex items-center gap-2">
                  <Compass className="w-4 h-4 text-cyan-400" />
                  {activeWaypoint.location_name}
                </h5>
              </div>

              <div className="flex items-center gap-2">
                <span className="px-2.5 py-1 text-xs font-semibold bg-white/10 border border-white/15 text-ice/90">
                  {activeWaypoint.sea_state}
                </span>
                <span className="text-[10px] font-mono px-2 py-1 bg-midnight border border-white/10 text-muted">
                  {activeWaypoint.data_source}
                </span>
              </div>
            </div>

            {/* Metrics Breakdown Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="bg-midnight/40 p-3 border border-white/5">
                <span className="text-[10px] uppercase font-semibold text-muted tracking-wider block">
                  Wave Height & Swell
                </span>
                <span className="font-serif text-xl font-medium text-paper">
                  {activeWaypoint.wave_height_m} m
                </span>
                <span className="text-[11px] text-ice/60 block mt-0.5">
                  Heading: {activeWaypoint.wave_direction_deg}°
                </span>
              </div>

              <div className="bg-midnight/40 p-3 border border-white/5">
                <span className="text-[10px] uppercase font-semibold text-muted tracking-wider block">
                  Wind Velocity
                </span>
                <span className="font-serif text-xl font-medium text-paper">
                  {activeWaypoint.wind_speed_kts} kts
                </span>
                <span className="text-[11px] text-ice/60 block mt-0.5">
                  Direction: {activeWaypoint.wind_direction}
                </span>
              </div>

              <div className="bg-midnight/40 p-3 border border-white/5">
                <span className="text-[10px] uppercase font-semibold text-muted tracking-wider block">
                  Speed Slowdown
                </span>
                <span
                  className={`font-serif text-xl font-medium ${
                    activeWaypoint.speed_penalty_pct < 0 ? "text-rose-400" : "text-emerald-400"
                  }`}
                >
                  {activeWaypoint.speed_penalty_pct < 0 ? `${activeWaypoint.speed_penalty_pct}%` : "Nominal"}
                </span>
                <span className="text-[11px] text-ice/60 block mt-0.5">
                  Transit Speed Impact
                </span>
              </div>

              <div className="bg-midnight/40 p-3 border border-white/5">
                <span className="text-[10px] uppercase font-semibold text-muted tracking-wider block">
                  Fuel Burn Impact
                </span>
                <span
                  className={`font-serif text-xl font-medium ${
                    activeWaypoint.fuel_penalty_pct > 0 ? "text-amber-400" : "text-emerald-400"
                  }`}
                >
                  {activeWaypoint.fuel_penalty_pct > 0 ? `+${activeWaypoint.fuel_penalty_pct}%` : "Baseline"}
                </span>
                <span className="text-[11px] text-ice/60 block mt-0.5">
                  Bunker Consumption
                </span>
              </div>
            </div>

            {/* Waypoint Specific Alert */}
            {activeWaypoint.alert && (
              <div className="flex items-center gap-2 p-3 bg-rose-500/10 border border-rose-500/30 text-xs text-rose-300">
                <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
                <span>{activeWaypoint.alert}</span>
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
