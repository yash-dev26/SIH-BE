import {
  mockCreateRecommendation,
  mockGetPorts,
  mockGetRecommendation,
  mockGetVesselClasses,
} from "@/lib/mock/adapter";
import type { Port, Recommendation, RecommendRequest, VesselClass } from "@/lib/types";
import {
  mapFrontendRequestToBackend,
  transformBackendResponse,
  type BackendRecommendationResponse,
} from "@/lib/transform";

export type { Port, Recommendation, RecommendRequest, VesselClass };

const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK === "true";
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || process.env.API_BASE_URL || "http://localhost:8000";

// In-memory cache for recommendations created in current session
const recommendationCache = new Map<string, Recommendation>();

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  const res = await fetch(url, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${path}`);
  }
  return res.json() as Promise<T>;
}

/** GET /api/ports */
export async function getPorts(): Promise<Port[]> {
  if (USE_MOCK) return mockGetPorts();
  try {
    return await fetchJson<Port[]>("/api/ports");
  } catch (err) {
    console.warn("Backend /api/ports fetch failed, falling back to mock catalog:", err);
    return mockGetPorts();
  }
}

/** GET /api/vessel-classes */
export async function getVesselClasses(): Promise<VesselClass[]> {
  if (USE_MOCK) return mockGetVesselClasses();
  try {
    return await fetchJson<VesselClass[]>("/api/vessel-classes");
  } catch (err) {
    console.warn("Backend /api/vessel-classes fetch failed, falling back to mock catalog:", err);
    return mockGetVesselClasses();
  }
}

/** POST /api/recommend */
export async function createRecommendation(request: RecommendRequest): Promise<Recommendation> {
  if (USE_MOCK) return mockCreateRecommendation(request);

  const payload = mapFrontendRequestToBackend(request);
  const backendResponse = await fetchJson<BackendRecommendationResponse>("/api/recommend", {
    method: "POST",
    body: JSON.stringify(payload),
  });

  const rec = transformBackendResponse(backendResponse, request);
  recommendationCache.set(rec.id, rec);
  recommendationCache.set("latest", rec);
  return rec;
}

/** GET /recommendations/{id} */
export async function getRecommendation(id: string): Promise<Recommendation> {
  if (USE_MOCK) return mockGetRecommendation(id);

  if (recommendationCache.has(id)) {
    return recommendationCache.get(id)!;
  }
  if (id === "latest" && recommendationCache.has("latest")) {
    return recommendationCache.get("latest")!;
  }

  try {
    const raw = await fetchJson<BackendRecommendationResponse>(`/api/recommendations/${id}`);
    const dummyReq: RecommendRequest = {
      commodity: (raw.commodity as RecommendRequest["commodity"]) || "Thermal Coal",
      quantityMt: raw.cargo_qty_mt || 75000,
      origin: "Australia",
      destination: (raw.destination_port_code as RecommendRequest["destination"]) || "Paradip",
      laycanStart: raw.recommended_entry_window_start || "2026-10-01",
      laycanEnd: raw.recommended_entry_window_end || "2026-10-10",
      contractPreference: "let_system_decide",
      riskTolerance: "balanced",
    };
    return transformBackendResponse(raw, dummyReq);
  } catch {
    return mockGetRecommendation(id);
  }
}
