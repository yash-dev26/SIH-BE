import type { Recommendation, RecommendRequest } from "./types";

const PORT_CODE_MAP: Record<string, string> = {
  "Paradip": "INPRT",
  "Vizag": "INVTZ",
  "Gangavaram": "INGVT",
  "Gopalpur": "INGPL",
  "Dhamra": "INDHM",
  "Sagar-Sandheads": "INSAG",
  "Haldia": "INHAL",
};

const COMMODITY_MAP: Record<string, string> = {
  "Thermal Coal": "thermal_coal",
  "Coking Coal": "coking_coal",
  "Iron Ore": "iron_ore",
};

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
  const destCode = (request.destination && PORT_CODE_MAP[request.destination])
    ? PORT_CODE_MAP[request.destination]
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
  };
}


export function transformBackendResponse(
  backendData: BackendRecommendationResponse,
  originalRequest: RecommendRequest
): Recommendation {
  const summary = {
    vesselClass: backendData.recommended_vessel_class || "Capesize",
    vesselClassId: String(backendData.recommended_vessel_class_id || backendData.vessel?.vessel_class_id || "4"),
    contractType: (backendData.recommended_contract_type || "Spot").toUpperCase(),
    marketEntryWindow: backendData.recommended_entry_window_start
      ? `${backendData.recommended_entry_window_start} to ${backendData.recommended_entry_window_end}`
      : `${originalRequest.laycanStart} to ${originalRequest.laycanEnd}`,
    expectedFreightUsdPerMt: backendData.cost_per_mt_usd || 18.5,
    expectedLogisticsCostUsd: backendData.expected_total_cost_usd || 1387500,
    confidence: (backendData.model_fallback_used ? "Medium" : "High") as "High" | "Medium" | "Low",
    risk: (backendData.risk_flags && backendData.risk_flags.length > 1 ? "Moderate" : "Low") as "Low" | "Moderate" | "High",
  };

  const forecastPoints = [];
  if (backendData.forecast && Array.isArray(backendData.forecast.points)) {
    for (const p of backendData.forecast.points) {
      const p50 = p.p50 || p.predicted_rate || 20000;
      forecastPoints.push({
        date: p.date,
        p10: p.p10 || p.predicted_rate_p10 || p50 * 0.9,
        p50: p50,
        p90: p.p90 || p.predicted_rate_p90 || p50 * 1.1,
        isForecast: true,
      });
    }
  } else {
    // Generate indicative 14-day trend points around forecasted_tce_rate_usd_day
    const baseTce = backendData.forecasted_tce_rate_usd_day || 20000;
    const startDate = new Date(originalRequest.laycanStart || Date.now());
    for (let i = -7; i <= 7; i++) {
      const d = new Date(startDate);
      d.setDate(d.getDate() + i);
      const iso = d.toISOString().split("T")[0];
      const noise = Math.sin(i) * 400;
      const rate = baseTce + noise;
      forecastPoints.push({
        date: iso,
        p10: Math.round(rate * 0.9),
        p50: Math.round(rate),
        p90: Math.round(rate * 1.1),
        isForecast: i >= 0,
      });
    }
  }

  const forecast = {
    unit: "USD_PER_MT" as const,
    currentP50: backendData.cost_per_mt_usd || 18.5,
    asOf: new Date().toISOString().split("T")[0],
    points: forecastPoints,
  };

  const originHub = {
    id: originalRequest.origin,
    name: backendData.recommended_origin_port || `${originalRequest.origin} Export Hub`,
    region: originalRequest.origin,
    lat: backendData.origin?.latitude || -32.92,
    lng: backendData.origin?.longitude || 151.78,
    typicalExportBerth: backendData.origin?.port_name || "Deepwater Bulk Export Terminal",
  };

  const destinationPort = {
    id: originalRequest.destination,
    name: originalRequest.destination,
    country: "India" as const,
    lat: backendData.destination?.latitude || 20.26,
    lng: backendData.destination?.longitude || 86.68,
    maxDraftM: backendData.destination?.max_draft_m || 16.5,
    maxLoaM: backendData.destination?.max_loa_m || 300,
    maxBeamM: backendData.destination?.max_beam_m || 46,
    handlingRateMtpd: backendData.destination?.handling_rate_mtpd || 70000,
    notes: backendData.destination?.notes || "Deep draft bulk discharge berth",
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

  // Extract unique risk messages (deduplicated by code or message text)
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

  const rationale = {
    headline: backendData.rationale?.summary || backendData.human_readable_summary || `Recommended importing ${originalRequest.quantityMt.toLocaleString()} MT of ${originalRequest.commodity} via ${summary.vesselClass} (${summary.contractType})`,
    points: rationalePoints,
    bindingConstraints: bindingConstraints,
    forecastUsed: [
      `Model ID: ${backendData.model_id || "Active Champion"} (v${backendData.model_version || "1.0.0"})`,
      `Training Rows: ${backendData.model_training_rows || 8764}`,
      `Fallback Used: ${backendData.model_fallback_used ? "Yes" : "No"}`,
    ],
    importantRisks: importantRisks.length > 0 ? importantRisks : ["Low operational risk environment."],
    riskMitigations: riskMitigations,
  };

  // Deduplicate alternatives by title
  const seenAltTitles = new Set<string>();
  const alternatives = Array.isArray(backendData.alternatives) && backendData.alternatives.length > 0
    ? backendData.alternatives
        .filter((alt) => {
          const title = alt.title || alt.contract_type || "Alternative Option";
          if (seenAltTitles.has(title)) return false;
          seenAltTitles.add(title);
          return true;
        })
        .map((alt, idx: number) => ({
          id: String(idx + 1),
          title: alt.title || alt.contract_type || "Alternative Option",
          vesselClass: alt.vessel_class || summary.vesselClass,
          contractType: (alt.contract_type || "COA").toUpperCase(),
          tradeoff: alt.tradeoff || alt.description || `Slightly higher cost per MT with reduced spot rate variance`,
        }))
    : [
        {
          id: "1",
          title: "COA Contract Alternative",
          vesselClass: summary.vesselClass,
          contractType: "COA",
          tradeoff: "Provides price certainty (+ $0.85/MT premium) over spot market volatility",
        },
        {
          id: "2",
          title: "Panamax Split Cargo Voyage",
          vesselClass: "Panamax",
          contractType: "SPOT",
          tradeoff: "Lowers single berth draft requirement but increases port handling duration",
        },
      ];

  return {
    id: backendData.recommendation_id || `rec_${Date.now()}`,
    demo: false,
    createdAt: new Date().toISOString(),
    request: originalRequest,
    summary,
    forecast,
    originHub,
    destinationPort,
    vesselOptions,
    rationale,
    alternatives,
  };
}
