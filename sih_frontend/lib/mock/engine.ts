import { originById, portByName, VESSEL_CLASSES } from "@/lib/mock/catalog";
import type {
  Alternative,
  Confidence,
  Feasibility,
  ForecastPoint,
  Recommendation,
  RecommendRequest,
  RiskLevel,
  VesselOption,
} from "@/lib/types";

export const DEMO_ID = "rec-demo-aus-paradip";

function isoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function addDays(base: Date, days: number): Date {
  const next = new Date(base);
  next.setDate(next.getDate() + days);
  return next;
}

function buildForecast(base: number): ForecastPoint[] {
  const today = new Date();
  const points: ForecastPoint[] = [];
  for (let i = -11; i <= 12; i += 1) {
    const date = addDays(today, i * 7);
    const cycle = Math.sin((i + 4) / 3.2);
    const dip = i >= 1 && i <= 4 ? -1.35 : 0;
    const trend = i * 0.04;
    const p50 = Number((base + cycle * 0.85 + dip + trend).toFixed(2));
    const width = 1.55 + Math.abs(i) * 0.06;
    const p10 = Number((p50 - width).toFixed(2));
    const p90 = Number((p50 + width * 1.15).toFixed(2));
    const isForecast = i > 0;
    points.push({
      date: isoDate(date),
      p10,
      p50,
      p90,
      actual: isForecast ? undefined : Number((p50 + (i === 0 ? 0 : cycle * 0.15)).toFixed(2)),
      isForecast,
    });
  }
  return points;
}

function laneBase(origin: RecommendRequest["origin"]): number {
  switch (origin) {
    case "Australia":
      return 18.4;
    case "Indonesia":
      return 14.8;
    case "Mozambique":
      return 21.1;
    case "US":
      return 32.6;
    case "Russia":
      return 24.2;
    default:
      return 18.4;
  }
}

function assessVessel(quantityMt: number, portMax: ReturnType<typeof portByName>): VesselOption[] {
  return VESSEL_CLASSES.map((v) => {
    const reasons: string[] = [];
    let feasibility: Feasibility = "feasible";
    if (v.typicalDwt < quantityMt) {
      feasibility = "infeasible";
      reasons.push(`DWT ${v.typicalDwt.toLocaleString()} < cargo ${quantityMt.toLocaleString()} MT`);
    }
    if (v.designDraftM > portMax.maxDraftM) {
      feasibility = "infeasible";
      reasons.push(`Draft ${v.designDraftM} m exceeds port max ${portMax.maxDraftM} m`);
    }
    if (v.loaM > portMax.maxLoaM) {
      feasibility = "infeasible";
      reasons.push(`LOA ${v.loaM} m exceeds port max ${portMax.maxLoaM} m`);
    }
    if (v.beamM > portMax.maxBeamM) {
      feasibility = "infeasible";
      reasons.push(`Beam ${v.beamM} m exceeds port max ${portMax.maxBeamM} m`);
    }
    if (feasibility === "feasible" && v.typicalDwt > quantityMt * 1.6) {
      feasibility = "marginal";
      reasons.push("Oversized for parcel; ballast/idle cost risk");
    }
    if (feasibility === "feasible" && v.designDraftM > portMax.maxDraftM - 0.4) {
      feasibility = "marginal";
      reasons.push("Tight under-keel margin versus advertised max draft");
    }
    return {
      vesselClassId: v.id,
      vesselClassName: v.name,
      feasibility,
      reason: reasons[0] ?? "Clears destination draft, LOA, beam and cargo size",
    };
  });
}

function pickVessel(options: VesselOption[], quantityMt: number): VesselOption {
  const feasible = options.filter((o) => o.feasibility === "feasible");
  const panamax = feasible.find((o) => o.vesselClassId === "panamax");
  if (quantityMt >= 65000 && quantityMt <= 85000 && panamax) return panamax;
  return feasible[0] ?? options.find((o) => o.feasibility === "marginal") ?? options[1];
}

function strategyFor(req: RecommendRequest): {
  contractType: string;
  marketEntryWindow: string;
  confidence: Confidence;
  risk: RiskLevel;
} {
  if (req.contractPreference !== "let_system_decide") {
    const labels: Record<RecommendRequest["contractPreference"], string> = {
      let_system_decide: "Short-term / multiple-voyage",
      spot: "Spot voyage",
      short_term: "Short-term / multiple-voyage",
      coa: "Contract of affreightment (COA)",
      period: "Period time-charter",
    };
    const risk: RiskLevel =
      req.riskTolerance === "aggressive" ? "High" : req.riskTolerance === "conservative" ? "Low" : "Moderate";
    return {
      contractType: labels[req.contractPreference],
      marketEntryWindow: req.riskTolerance === "aggressive" ? "Next 5–10 days" : "Next 2–3 weeks",
      confidence: req.riskTolerance === "aggressive" ? "Medium" : "High",
      risk,
    };
  }

  if (req.riskTolerance === "conservative") {
    return {
      contractType: "COA / short-period cover",
      marketEntryWindow: "Weeks 3–5, after the near-term dip confirms",
      confidence: "High",
      risk: "Low",
    };
  }
  if (req.riskTolerance === "aggressive") {
    return {
      contractType: "Spot voyage",
      marketEntryWindow: "Immediate / next 7 days",
      confidence: "Medium",
      risk: "High",
    };
  }
  return {
    contractType: "Short-term / multiple-voyage",
    marketEntryWindow: "Next 2–3 weeks",
    confidence: "High",
    risk: "Moderate",
  };
}

export function buildRecommendation(request: RecommendRequest, id?: string): Recommendation {
  const destinationPort = portByName(request.destination);
  const originHub = originById(request.origin);
  const forecastPoints = buildForecast(laneBase(request.origin));
  const current = forecastPoints.find((p) => !p.isForecast) ?? forecastPoints[11];
  const dip = forecastPoints.filter((p) => p.isForecast).slice(1, 4);
  const expectedFreightUsdPerMt = Number(
    (dip.reduce((s, p) => s + p.p50, 0) / Math.max(dip.length, 1)).toFixed(2),
  );
  const vesselOptions = assessVessel(request.quantityMt, destinationPort);
  const chosen = pickVessel(vesselOptions, request.quantityMt);
  const strat = strategyFor(request);
  const demo =
    request.origin === "Australia" &&
    request.destination === "Paradip" &&
    request.commodity === "Thermal Coal";

  const cape = vesselOptions.find((v) => v.vesselClassId === "capesize");
  const alternatives: Alternative[] = [
    {
      id: "alt-spot",
      title: "Spot now",
      vesselClass: chosen.vesselClassName,
      contractType: "Spot voyage",
      tradeoff: "Captures today’s fixture but misses the modelled 2–3 week softening.",
    },
    {
      id: "alt-cape",
      title: cape?.feasibility === "feasible" ? "Capesize parcel" : "Wait for a Capesize-capable discharge",
      vesselClass: "Capesize",
      contractType: strat.contractType,
      tradeoff:
        cape?.feasibility === "feasible"
          ? "Lower unit freight if the cargo can be combined; higher demurrage if the parcel is only this size."
          : "Blocked by destination draft/LOA/beam in this scenario.",
    },
    {
      id: "alt-coa",
      title: "Cover with COA",
      vesselClass: chosen.vesselClassName,
      contractType: "COA",
      tradeoff: "Stabilises FY rate risk; less able to harvest a short-lived freight dip.",
    },
  ];

  return {
    id: id ?? `rec-${Date.now()}`,
    demo,
    createdAt: new Date().toISOString(),
    request,
    summary: {
      vesselClass: chosen.vesselClassName,
      vesselClassId: chosen.vesselClassId,
      contractType: strat.contractType,
      marketEntryWindow: strat.marketEntryWindow,
      expectedFreightUsdPerMt,
      expectedLogisticsCostUsd: Math.round(expectedFreightUsdPerMt * request.quantityMt),
      overallTceRateUsdDay: Math.round(expectedFreightUsdPerMt * (request.quantityMt / 25)),
      overallVoyageCostUsd: Math.round(expectedFreightUsdPerMt * request.quantityMt),
      confidence: strat.confidence,
      risk: strat.risk,
    },
    forecast: {
      unit: "USD_PER_MT",
      currentP50: current.p50,
      asOf: current.date,
      points: forecastPoints,
    },
    originHub,
    destinationPort,
    vesselOptions,
    rationale: {
      headline: `${originHub.region} → ${destinationPort.name} is a ${chosen.vesselClassName.toLowerCase()} parcel. Timing and contract follow the freight path; origin is a scenario input, not a sourcing recommendation.`,
      points: [
        `The ${originHub.region}–east coast India p50 path eases over the next 2–3 weeks, then drifts higher. That window is the modelled charter entry.`,
        `${chosen.vesselClassName} clears ${destinationPort.name} draft ${destinationPort.maxDraftM} m, LOA ${destinationPort.maxLoaM} m and beam ${destinationPort.maxBeamM} m, and can lift ${request.quantityMt.toLocaleString()} MT.`,
        `Handling at ~${destinationPort.handlingRateMtpd.toLocaleString()} MT/day supports a single-discharge call inside a normal laycan.`,
        `${strat.contractType} matches the ${request.riskTolerance} risk posture: cover the movement without locking an oversized period book.`,
        "Main residual risk is a congestion- or weather-driven spike that lifts the p90 band before the vessel is stemmed.",
      ],
      bindingConstraints: [
        `Cargo size ${request.quantityMt.toLocaleString()} MT vs vessel DWT`,
        `${destinationPort.name} max draft ${destinationPort.maxDraftM} m / LOA ${destinationPort.maxLoaM} m / beam ${destinationPort.maxBeamM} m`,
        `Laycan ${request.laycanStart} → ${request.laycanEnd}`,
      ],
      forecastUsed: [
        `Lane p10/p50/p90 in USD/MT (mock), as-of ${current.date}`,
        `Current p50 ${current.p50.toFixed(2)}; expected freight uses the near-term forecast p50, not a risk-mapped percentile`,
        "Risk tolerance changes contract and timing; p10/p50/p90 stay visible as uncertainty",
      ],
      importantRisks: [
        "Port congestion or monsoon delay at discharge",
        "Bunker and Cape–Panamax spread widening",
        "Laycan slip forcing a fixture outside the forecast dip",
      ],
      riskMitigations: [
        "Build 3-5 day buffer into laycan window. Monitor weather advisories.",
        "Consider bunker fuel hedging or COA to reduce exposure.",
        "Maintain flexibility in fixture timing to capture forecast dip window.",
      ],
    },
    alternatives,
    voyageWeather: {
      origin_port_code: originHub.id,
      origin_port_name: originHub.name,
      destination_port_code: destinationPort.id,
      destination_port_name: destinationPort.name,
      departure_date: request.laycanStart,
      transit_days: 7,
      sea_distance_nm: 3450,
      overall_status: "Optimal Sea Conditions",
      status_color: "GREEN",
      safety_score: 92,
      max_wave_height_m: 2.1,
      max_wind_speed_kts: 18.5,
      estimated_delay_hours: 0,
      estimated_fuel_surcharge_pct: 0,
      weather_alerts: [],
      daily_waypoints: [
        { day: 0, date: request.laycanStart, lat: originHub.lat, lon: originHub.lng, location_name: `Origin: ${originHub.name}`, wave_height_m: 1.2, wave_direction_deg: 140, wind_speed_kts: 12.0, wind_direction: "SE", sea_state: "Calm (Smooth Sea)", weather_condition: "Clear Fair Weather", visibility_km: 10, speed_penalty_pct: 0, fuel_penalty_pct: 0, data_source: "Live Marine Simulator" },
        { day: 1, date: isoDate(addDays(new Date(request.laycanStart), 1)), lat: originHub.lat + 2, lon: originHub.lng + 3, location_name: "Waypoint Day 1 (Oceanic Waypoint)", wave_height_m: 1.5, wave_direction_deg: 155, wind_speed_kts: 14.2, wind_direction: "SE", sea_state: "Slight (Minor Swell)", weather_condition: "Fair Oceanic Weather", visibility_km: 10, speed_penalty_pct: 0, fuel_penalty_pct: 0, data_source: "Live Marine Simulator" },
        { day: 2, date: isoDate(addDays(new Date(request.laycanStart), 2)), lat: originHub.lat + 4, lon: originHub.lng + 6, location_name: "Waypoint Day 2 (Oceanic Waypoint)", wave_height_m: 1.8, wave_direction_deg: 160, wind_speed_kts: 16.5, wind_direction: "E", sea_state: "Slight (Minor Swell)", weather_condition: "Partly Cloudy", visibility_km: 10, speed_penalty_pct: 0, fuel_penalty_pct: 0, data_source: "Live Marine Simulator" },
        { day: 3, date: isoDate(addDays(new Date(request.laycanStart), 3)), lat: originHub.lat + 6, lon: originHub.lng + 9, location_name: "Waypoint Day 3 (Bay of Bengal Entrance)", wave_height_m: 2.1, wave_direction_deg: 175, wind_speed_kts: 18.5, wind_direction: "E", sea_state: "Moderate (Moderate Swell)", weather_condition: "Moderate Tropical Breeze", visibility_km: 9.5, speed_penalty_pct: 0, fuel_penalty_pct: 0, data_source: "Live Marine Simulator" },
        { day: 4, date: isoDate(addDays(new Date(request.laycanStart), 4)), lat: originHub.lat + 8, lon: originHub.lng + 11, location_name: "Waypoint Day 4 (Mid Bay of Bengal)", wave_height_m: 1.9, wave_direction_deg: 180, wind_speed_kts: 15.0, wind_direction: "NE", sea_state: "Slight (Minor Swell)", weather_condition: "Fair Oceanic Weather", visibility_km: 10, speed_penalty_pct: 0, fuel_penalty_pct: 0, data_source: "Live Marine Simulator" },
        { day: 5, date: isoDate(addDays(new Date(request.laycanStart), 5)), lat: originHub.lat + 10, lon: originHub.lng + 13, location_name: "Waypoint Day 5 (Approach Channel)", wave_height_m: 1.4, wave_direction_deg: 190, wind_speed_kts: 13.0, wind_direction: "NE", sea_state: "Calm (Smooth Sea)", weather_condition: "Clear Ocean Sky", visibility_km: 10, speed_penalty_pct: 0, fuel_penalty_pct: 0, data_source: "Live Marine Simulator" },
        { day: 6, date: isoDate(addDays(new Date(request.laycanStart), 6)), lat: destinationPort.lat - 0.5, lon: destinationPort.lng - 0.5, location_name: `Waypoint Day 6 (Outer Anchorage)`, wave_height_m: 1.1, wave_direction_deg: 200, wind_speed_kts: 11.5, wind_direction: "N", sea_state: "Calm (Smooth Sea)", weather_condition: "Fair Berthing Window", visibility_km: 10, speed_penalty_pct: 0, fuel_penalty_pct: 0, data_source: "Live Marine Simulator" },
        { day: 7, date: isoDate(addDays(new Date(request.laycanStart), 7)), lat: destinationPort.lat, lon: destinationPort.lng, location_name: `Destination: ${destinationPort.name}`, wave_height_m: 0.9, wave_direction_deg: 210, wind_speed_kts: 10.0, wind_direction: "N", sea_state: "Calm (Smooth Sea)", weather_condition: "Berth Operations Clear", visibility_km: 10, speed_penalty_pct: 0, fuel_penalty_pct: 0, data_source: "Live Marine Simulator" },
      ]
    }
  };
}

export function demoRequest(): RecommendRequest {
  const start = addDays(new Date(), 21);
  const end = addDays(new Date(), 35);
  return {
    commodity: "Thermal Coal",
    quantityMt: 70000,
    origin: "Australia",
    destination: "Paradip",
    laycanStart: isoDate(start),
    laycanEnd: isoDate(end),
    contractPreference: "let_system_decide",
    riskTolerance: "balanced",
  };
}

export function getDemoRecommendation(): Recommendation {
  return { ...buildRecommendation(demoRequest(), DEMO_ID), demo: true };
}
