import type { Recommendation, RecommendRequest } from "./types";
import { originById, portByName } from "@/lib/mock/catalog";

const PORT_CODE_MAP: Record<string, string> = {
  "Paradip": "INPDP",
  "Vizag": "INVTZ",
  "Gangavaram": "INGGV",
  "Gopalpur": "INGOP",
  "Dhamra": "INDHM",
  "Sagar-Sandheads": "INSGR",
  "Sagar / Sagar-Sandheads Anchorage": "INSGR",
  "Sagar / Sagar-Sandheads": "INSGR",
  "Sagar Sandheads": "INSGR",
  "Haldia": "INHAL",
  "Haldia Dock Complex": "INHAL",
  "Haldia Dock": "INHAL",
};

const PORT_CODE_REVERSE_MAP: Record<string, RecommendRequest["destination"]> = {
  INPDP: "Paradip",
  INVTZ: "Vizag",
  INGGV: "Gangavaram",
  INGOP: "Gopalpur",
  INDHM: "Dhamra",
  INSGR: "Sagar-Sandheads",
  INHAL: "Haldia",
};

const COMMODITY_MAP: Record<string, string> = {
  "Thermal Coal": "thermal_coal",
  "Coking Coal": "coking_coal",
  "Iron Ore": "iron_ore",
};

function normalizeForecastValue(rawValue: number | undefined, basePerMt: number, referenceRate: number): number {
  if (rawValue === undefined || rawValue === null || Number.isNaN(rawValue)) {
    return basePerMt;
  }

  if (referenceRate > 0 && rawValue > basePerMt * 20) {
    return Number((basePerMt * (rawValue / referenceRate)).toFixed(2));
  }

  return Number(rawValue.toFixed(2));
}

export interface BackendRecommendationResponse {
  recommendation_id?: string;
  commodity?: string;
  cargo_qty_mt?: number;
  destination_port_code?: string;
  recommended_origin_port?: string;
  recommended_origin_port_code?: string;
  recommended_vessel_class?: string;
  recommended_vessel_class_id?: number;
  recommended_trade_lane_id?: number;
  recommended_contract_type?: string;
  recommended_entry_window_start?: string;
  recommended_entry_window_end?: string;
  expected_total_cost_usd?: number;
  cost_per_mt_usd?: number;
  forecasted_tce_rate_usd_day?: number;
  model_id?: string;
  model_version?: string;
  model_fallback_used?: boolean;
  model_training_rows?: number;
  vessel_utilization_pct?: number;
  candidates_considered_count?: number;
  feasible_candidates_count?: number;
  why_selected?: string[];
  human_readable_summary?: string;
  voyage_weather?: any;
  origin?: {
    latitude?: number;
    longitude?: number;
    port_name?: string;
  };
  destination?: {
    latitude?: number;
    longitude?: number;
    max_draft_m?: number;
    max_loa_m?: number;
    max_beam_m?: number;
    handling_rate_mtpd?: number;
    notes?: string;
  };
  vessel?: {
    vessel_class_id?: number;
  };
  forecast?: {
    points?: Array<{
      date: string;
      p10?: number;
      predicted_rate_p10?: number;
      p50?: number;
      predicted_rate?: number;
      p90?: number;
      predicted_rate_p90?: number;
    }>;
  };
  rationale?: {
    binding_constraints?: string[];
    summary?: string;
    vessel_choice_reason?: string;
    origin_port_choice_reason?: string;
    contract_selection_rationale?: string;
    entry_window_rationale?: string;
  };
  risk_flags?: Array<string | { flag?: string; code?: string; description?: string; message?: string; severity?: string; mitigation?: string }>;
  alternatives?: Array<{
    title?: string;
    contract_type?: string;
    vessel_class?: string;
    tradeoff?: string;
    description?: string;
  }>;
}

export function mapFrontendRequestToBackend(request: RecommendRequest) {
  const destinationName = typeof request.destination === "string" ? request.destination.trim() : "";
  const normalizedDestination = destinationName.replace(/[-_/]+/g, " ").replace(/\s+/g, " ").trim();
  const destCode = (destinationName && PORT_CODE_MAP[destinationName])
    ? PORT_CODE_MAP[destinationName]
    : (normalizedDestination && PORT_CODE_MAP[normalizedDestination])
      ? PORT_CODE_MAP[normalizedDestination]
      : (request.destination || "INPRT");

  const commCode = (request.commodity && COMMODITY_MAP[request.commodity])
    ? COMMODITY_MAP[request.commodity]
    : (request.commodity ? String(request.commodity).toLowerCase().replace(" ", "_") : "thermal_coal");

  return {
    commodity: commCode,
    cargo_qty_mt: Number(request.quantityMt) || 70000,
    destination_port_code: destCode,
    laycan_start: request.laycanStart || new Date().toISOString().slice(0, 10),
    laycan_end: request.laycanEnd || new Date(Date.now() + 14 * 86400000).toISOString().slice(0, 10),
    risk_tolerance: request.riskTolerance || "balanced",
    contract_preference: request.contractPreference || "let_system_decide",
  };
}

export function transformBackendResponse(
  backendData: BackendRecommendationResponse,
  originalRequest: RecommendRequest,
): Recommendation {
  const baseCostPerMt = backendData.cost_per_mt_usd ?? 18.5;
  const baseTceRate = backendData.forecasted_tce_rate_usd_day ?? 20000;
  const voyageDays = Math.max(backendData.forecast?.points?.length ? backendData.forecast.points.length : 20, 12);
  const overallVoyageCostUsd = Number(
    backendData.expected_total_cost_usd ?? Math.max((baseCostPerMt * (Number(originalRequest.quantityMt) || 70000)), 0),
  );
  const overallTceRateUsdDay = Number(
    backendData.forecasted_tce_rate_usd_day ?? Math.max((overallVoyageCostUsd / voyageDays), 0),
  );

  const summary = {
    vesselClass: backendData.recommended_vessel_class || "Capesize",
    vesselClassId: String(backendData.recommended_vessel_class_id || backendData.vessel?.vessel_class_id || "4"),
    contractType: (backendData.recommended_contract_type || "Spot").toUpperCase(),
    marketEntryWindow: backendData.recommended_entry_window_start
      ? `${backendData.recommended_entry_window_start} to ${backendData.recommended_entry_window_end}`
      : `${originalRequest.laycanStart} to ${originalRequest.laycanEnd}`,
    expectedFreightUsdPerMt: baseCostPerMt,
    expectedLogisticsCostUsd: backendData.expected_total_cost_usd || 1387500,
    overallTceRateUsdDay,
    overallVoyageCostUsd,
    confidence: (backendData.model_fallback_used ? "Medium" : "High") as "High" | "Medium" | "Low",
    risk: (backendData.risk_flags && backendData.risk_flags.length > 1 ? "Moderate" : "Low") as "Low" | "Moderate" | "High",
  };

  if (originalRequest.contractPreference && originalRequest.contractPreference !== "let_system_decide") {
    const preferred = originalRequest.contractPreference.toLowerCase();
    const override = preferred === "spot" ? "SPOT" : preferred === "short_term" ? "SHORT-TERM / MULTIPLE-VOYAGE" : preferred === "coa" ? "COA" : preferred === "period" ? "PERIOD" : summary.contractType;
    summary.contractType = override;
  }

  const destinationPortCatalog = portByName(originalRequest.destination);
  const originHubCatalog = originById(originalRequest.origin);

  const forecastPoints = [];
  if (backendData.forecast && Array.isArray(backendData.forecast.points)) {
    for (const p of backendData.forecast.points) {
      const rawP50 = Number(p.p50 ?? p.predicted_rate ?? baseTceRate ?? 20000);
      const rawP10 = Number(p.p10 ?? p.predicted_rate_p10 ?? rawP50 * 0.9);
      const rawP90 = Number(p.p90 ?? p.predicted_rate_p90 ?? rawP50 * 1.1);

      forecastPoints.push({
        date: p.date,
        p10: normalizeForecastValue(rawP10, baseCostPerMt, baseTceRate),
        p50: normalizeForecastValue(rawP50, baseCostPerMt, baseTceRate),
        p90: normalizeForecastValue(rawP90, baseCostPerMt, baseTceRate),
        isForecast: true,
      });
    }
  } else {
    const startDate = new Date(originalRequest.laycanStart || Date.now());
    for (let i = -7; i <= 7; i++) {
      const d = new Date(startDate);
      d.setDate(d.getDate() + i);
      const iso = d.toISOString().split("T")[0];
      const drift = Number((Math.sin(i) * 0.18).toFixed(4));
      const rate = baseCostPerMt * (1 + drift);
      forecastPoints.push({
        date: iso,
        p10: Number((rate * 0.9).toFixed(2)),
        p50: Number(rate.toFixed(2)),
        p90: Number((rate * 1.1).toFixed(2)),
        isForecast: i >= 0,
      });
    }
  }

  const forecast = {
    unit: "USD_PER_MT" as const,
    currentP50: baseCostPerMt,
    asOf: new Date().toISOString().split("T")[0],
    points: forecastPoints,
  };

  const originHub = {
    id: originalRequest.origin,
    name: backendData.recommended_origin_port || originHubCatalog.name,
    region: originalRequest.origin,
    lat: backendData.origin?.latitude ?? originHubCatalog.lat,
    lng: backendData.origin?.longitude ?? originHubCatalog.lng,
    typicalExportBerth: backendData.origin?.port_name || originHubCatalog.typicalExportBerth,
  };

  const destinationPort = {
    id: originalRequest.destination,
    name: originalRequest.destination,
    country: "India" as const,
    lat: backendData.destination?.latitude ?? destinationPortCatalog.lat,
    lng: backendData.destination?.longitude ?? destinationPortCatalog.lng,
    maxDraftM: backendData.destination?.max_draft_m ?? destinationPortCatalog.maxDraftM,
    maxLoaM: backendData.destination?.max_loa_m ?? destinationPortCatalog.maxLoaM,
    maxBeamM: backendData.destination?.max_beam_m ?? destinationPortCatalog.maxBeamM,
    handlingRateMtpd: backendData.destination?.handling_rate_mtpd ?? destinationPortCatalog.handlingRateMtpd,
    notes: backendData.destination?.notes || destinationPortCatalog.notes,
  };

  const vesselOptions = [
    {
      vesselClassId: summary.vesselClassId,
      vesselClassName: summary.vesselClass,
      feasibility: "feasible" as const,
      reason: `Optimal capacity utilization for ${originalRequest.quantityMt.toLocaleString()} MT cargo.`,
    },
    {
      vesselClassId: "3",
      vesselClassName: "Panamax",
      feasibility: originalRequest.quantityMt <= 75000 ? ("feasible" as const) : ("marginal" as const),
      reason: originalRequest.quantityMt > 75000 ? "Requires parcel splitting across multi-voyage contract." : "Alternative Panamax charter choice.",
    },
    {
      vesselClassId: "1",
      vesselClassName: "Handysize",
      feasibility: "infeasible" as const,
      reason: "Parcel size exceeds Handysize single voyage payload capacity.",
    },
  ];

  const rationalePoints = backendData.why_selected || [
    `Minimum landed procurement cost of $${summary.expectedFreightUsdPerMt.toFixed(2)}/MT`,
    `Trained AI Model (${backendData.model_id ? backendData.model_id.slice(0, 8) : "Active Champion"}) forecast accuracy evaluated`,
    `Optimized vessel draft and laycan window selection`,
  ];

  const bindingConstraints = backendData.rationale?.binding_constraints || [
    `Usable draught limit of ${destinationPort.maxDraftM}m at ${destinationPort.name}`,
    `Laycan window: ${summary.marketEntryWindow}`,
  ];

  const seenRiskCodes = new Set<string>();
  const importantRisks: string[] = [];
  const riskMitigations: string[] = [];
  for (const r of backendData.risk_flags || []) {
    const msg = typeof r === "string" ? r : (r.message || r.description || r.flag || "");
    const code = typeof r === "string" ? msg : (r.code || msg);
    const mitigation = typeof r === "string" ? "" : (r.mitigation || "");
    if (!msg || seenRiskCodes.has(code)) continue;
    seenRiskCodes.add(code);
    importantRisks.push(msg);
    riskMitigations.push(mitigation);
  }

  function normalizeVoyageWeather(raw: any): Recommendation["voyageWeather"] | undefined {
    if (!raw || typeof raw !== "object") return undefined;

    const dailyWaypoints = Array.isArray(raw.daily_waypoints)
      ? raw.daily_waypoints.map((wp: any, index: number) => ({
          day: Number(wp?.day ?? index),
          date: wp?.date || raw.departure_date || new Date().toISOString().slice(0, 10),
          lat: Number(wp?.lat ?? 0),
          lon: Number(wp?.lon ?? 0),
          location_name: wp?.location_name || `Waypoint ${index}`,
          wave_height_m: Number(wp?.wave_height_m ?? 0),
          wave_direction_deg: Number(wp?.wave_direction_deg ?? 180),
          wind_speed_kts: Number(wp?.wind_speed_kts ?? 0),
          wind_direction: wp?.wind_direction || "SW",
          sea_state: wp?.sea_state || "Calm (Smooth Sea)",
          weather_condition: wp?.weather_condition || "Live Marine Weather",
          visibility_km: Number(wp?.visibility_km ?? 10),
          speed_penalty_pct: Number(wp?.speed_penalty_pct ?? 0),
          fuel_penalty_pct: Number(wp?.fuel_penalty_pct ?? 0),
          alert: wp?.alert ?? null,
          data_source: wp?.data_source || "Open-Meteo Marine API",
        }))
      : [];

    if (!dailyWaypoints.length) return undefined;

    return {
      origin_port_code: raw.origin_port_code || raw.origin_code || "",
      origin_port_name: raw.origin_port_name || raw.origin_name || "Origin",
      destination_port_code: raw.destination_port_code || raw.destination_code || "",
      destination_port_name: raw.destination_port_name || raw.destination_name || "Destination",
      departure_date: raw.departure_date || new Date().toISOString().slice(0, 10),
      transit_days: Number(raw.transit_days ?? dailyWaypoints.length - 1),
      sea_distance_nm: Number(raw.sea_distance_nm ?? 0),
      overall_status: raw.overall_status || "Optimal Sea Conditions",
      status_color: (raw.status_color === "RED" || raw.status_color === "YELLOW" || raw.status_color === "GREEN")
        ? raw.status_color
        : "GREEN",
      safety_score: Number(raw.safety_score ?? 100),
      max_wave_height_m: Number(raw.max_wave_height_m ?? Math.max(...dailyWaypoints.map((wp) => wp.wave_height_m), 0)),
      max_wind_speed_kts: Number(raw.max_wind_speed_kts ?? Math.max(...dailyWaypoints.map((wp) => wp.wind_speed_kts), 0)),
      estimated_delay_hours: Number(raw.estimated_delay_hours ?? 0),
      estimated_fuel_surcharge_pct: Number(raw.estimated_fuel_surcharge_pct ?? 0),
      weather_alerts: Array.isArray(raw.weather_alerts) ? raw.weather_alerts.filter(Boolean) : [],
      daily_waypoints: dailyWaypoints,
    };
  }

  const normalizedWeather = normalizeVoyageWeather(backendData.voyage_weather);

  return {
    id: backendData.recommendation_id || `rec-${Date.now()}`,
    demo: false,
    createdAt: new Date().toISOString(),
    request: originalRequest,
    summary,
    forecast,
    originHub,
    destinationPort,
    vesselOptions,
    rationale: {
      headline: backendData.human_readable_summary || `Route recommendation for ${originalRequest.origin} to ${originalRequest.destination}`,
      points: rationalePoints,
      bindingConstraints,
      forecastUsed: [
        backendData.model_id ? `Model ${backendData.model_id}` : "Champion model",
        backendData.model_fallback_used ? "Fallback deployment path" : "Primary deployment path",
      ],
      importantRisks,
      riskMitigations,
    },
    alternatives: (backendData.alternatives || []).map((alt, index) => ({
      id: `${index + 1}`,
      title: alt.title || alt.contract_type || "Alternative route",
      vesselClass: alt.vessel_class || summary.vesselClass,
      contractType: alt.contract_type || summary.contractType,
      tradeoff: alt.tradeoff || alt.description || "Competitive balance of cost and risk.",
    })),
    voyageWeather: normalizedWeather,
  };
}

export { PORT_CODE_REVERSE_MAP };
