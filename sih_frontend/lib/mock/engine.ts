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
