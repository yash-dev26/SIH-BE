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
  overallTceRateUsdDay: number;
  overallVoyageCostUsd: number;
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

export interface DailyWaypoint {
  day: number;
  date: string;
  lat: number;
  lon: number;
  location_name: string;
  wave_height_m: number;
  wave_direction_deg: number;
  wind_speed_kts: number;
  wind_direction: string;
  sea_state: string;
  weather_condition: string;
  visibility_km: number;
  speed_penalty_pct: number;
  fuel_penalty_pct: number;
  alert?: string | null;
  data_source: string;
}

export interface VoyageWeather {
  origin_port_code: string;
  origin_port_name: string;
  destination_port_code: string;
  destination_port_name: string;
  departure_date: string;
  transit_days: number;
  sea_distance_nm: number;
  overall_status: string;
  status_color: "GREEN" | "YELLOW" | "RED";
  safety_score: number;
  max_wave_height_m: number;
  max_wind_speed_kts: number;
  estimated_delay_hours: number;
  estimated_fuel_surcharge_pct: number;
  weather_alerts: string[];
  daily_waypoints: DailyWaypoint[];
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
  voyageWeather?: VoyageWeather;
}
