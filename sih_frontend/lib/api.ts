import {
  mockCreateRecommendation,
  mockGetPorts,
  mockGetRecommendation,
  mockGetVesselClasses,
} from "@/lib/mock/adapter";
import type { Port, Recommendation, RecommendRequest, VesselClass } from "@/lib/types";
import {
  mapFrontendRequestToBackend,
  PORT_CODE_REVERSE_MAP,
  transformBackendResponse,
  type BackendRecommendationResponse,
} from "@/lib/transform";

export type { Port, Recommendation, RecommendRequest, VesselClass };

const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK === "true";
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || process.env.API_BASE_URL || "http://localhost:8000";

// ── Persistence helpers (mirrors mock/adapter.ts version key) ─────────────────
const SS_VERSION = "v3";
const SS_STORE_KEY = `freightiq.recommendations.${SS_VERSION}`;
const SS_LAST_KEY = `freightiq.lastId.${SS_VERSION}`;

function ssRead(): Record<string, Recommendation> {
  if (typeof window === "undefined") return {};
  try { return JSON.parse(sessionStorage.getItem(SS_STORE_KEY) ?? "null") ?? {}; } catch { return {}; }
}
function ssWrite(rec: Recommendation, asLatest = true) {
  if (typeof window === "undefined") return;
  try {
    const store = ssRead();
    store[rec.id] = rec;
    sessionStorage.setItem(SS_STORE_KEY, JSON.stringify(store));
    if (asLatest) sessionStorage.setItem(SS_LAST_KEY, rec.id);
  } catch { /* quota exceeded – ignore */ }
}
function ssGet(id: string): Recommendation | undefined {
  if (typeof window === "undefined") return undefined;
  const store = ssRead();
  if (id === "latest") {
    const lastId = sessionStorage.getItem(SS_LAST_KEY);
    if (lastId) {
      const rec = store[lastId];
      // Only return if it has voyage weather (v3+)
      if (rec?.voyageWeather?.daily_waypoints?.length) return rec;
    }
    return undefined;
  }
  return store[id];
}

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
  ssWrite(rec); // persist to sessionStorage so /dashboard survives refresh
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
  // Hydrate from sessionStorage if in-memory cache was lost (e.g., page refresh)
  const stored = ssGet(id);
  if (stored) {
    recommendationCache.set(id, stored);
    return stored;
  }

  try {
    const raw = await fetchJson<BackendRecommendationResponse>(`/api/recommendations/${id}`);

    const originName = (raw.recommended_origin_port || raw.origin?.port_name || "").toLowerCase();
    const origin = (["Australia", "US", "Mozambique", "Russia", "Indonesia"].find((candidate) => {
      const lower = candidate.toLowerCase();
      return originName.includes(lower) || originName.includes(lower.replace(" ", ""));
    }) ?? "Australia") as RecommendRequest["origin"];
    const destCode = (raw.destination_port_code || "").toUpperCase();
    const destination = (PORT_CODE_REVERSE_MAP[destCode] || "Paradip") as RecommendRequest["destination"];

    const dummyReq: RecommendRequest = {
      commodity: (raw.commodity as RecommendRequest["commodity"]) || "Thermal Coal",
      quantityMt: raw.cargo_qty_mt || 75000,
      origin,
      destination,
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
