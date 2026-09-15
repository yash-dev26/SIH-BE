import type { CargoFormValues } from "@/lib/schema";

export type Commodity = CargoFormValues["commodity"];
export type Origin = CargoFormValues["origin"];
export type Destination = CargoFormValues["destination"];
export type ContractPreference = CargoFormValues["contractPreference"];
export type RiskTolerance = CargoFormValues["riskTolerance"];
export type Confidence = "High" | "Medium" | "Low";
export type RiskLevel = "Low" | "Moderate" | "High";
export type Feasibility = "feasible" | "marginal" | "infeasible";

export interface RecommendRequest {
  commodity: Commodity;
  quantityMt: number;
  origin: Origin;
  destination: Destination;
  laycanStart: string;
  laycanEnd: string;
  contractPreference: ContractPreference;
  riskTolerance: RiskTolerance;
}

export interface Port {
  id: string;
  name: Destination;
  country: "India";
  lat: number;
  lng: number;
  maxDraftM: number;
  maxLoaM: number;
  maxBeamM: number;
  handlingRateMtpd: number;
  notes: string;
}

export interface OriginHub {
  id: Origin;
  name: string;
  region: Origin;
  lat: number;
  lng: number;
  typicalExportBerth: string;
}

export interface VesselClass {
  id: string;
  name: string;
  typicalDwt: number;
  loaM: number;
  beamM: number;
  designDraftM: number;
}

export interface VesselOption {
  vesselClassId: string;
  vesselClassName: string;
  feasibility: Feasibility;
  reason: string;
}

export interface ForecastPoint {
  date: string;
  p10: number;
  p50: number;
  p90: number;
  actual?: number;
  isForecast: boolean;
}

export interface FreightForecast {
  unit: "USD_PER_MT";
  currentP50: number;
  asOf: string;
  points: ForecastPoint[];
}

export interface RecommendationSummary {
  vesselClass: string;
  vesselClassId: string;
  contractType: string;
  marketEntryWindow: string;
  expectedFreightUsdPerMt: number;
  expectedLogisticsCostUsd: number;
  confidence: Confidence;
  risk: RiskLevel;
}

export interface Rationale {
  headline: string;
  points: string[];
  bindingConstraints: string[];
  forecastUsed: string[];
  importantRisks: string[];
  riskMitigations: string[];
}

export interface Alternative {
  id: string;
  title: string;
  vesselClass: string;
  contractType: string;
  tradeoff: string;
}

export interface Recommendation {
  id: string;
  demo: boolean;
  createdAt: string;
  request: RecommendRequest;
  summary: RecommendationSummary;
  forecast: FreightForecast;
  originHub: OriginHub;
  destinationPort: Port;
  vesselOptions: VesselOption[];
  rationale: Rationale;
  alternatives: Alternative[];
}
