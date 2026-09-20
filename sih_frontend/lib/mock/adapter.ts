import { ORIGIN_HUBS, PORTS, VESSEL_CLASSES } from "@/lib/mock/catalog";
import { buildRecommendation, DEMO_ID, getDemoRecommendation } from "@/lib/mock/engine";
import type { Recommendation, RecommendRequest } from "@/lib/types";

const STORE_VERSION = "v3"; // bump whenever Recommendation shape changes
const STORE_KEY = `freightiq.recommendations.${STORE_VERSION}`;
const LAST_KEY = `freightiq.lastId.${STORE_VERSION}`;

function delay(ms = 220) {
  return new Promise((r) => setTimeout(r, ms));
}

function readStore(): Record<string, Recommendation> {
  if (typeof window === "undefined") return {};
  try {
    const raw = sessionStorage.getItem(STORE_KEY);
    return raw ? (JSON.parse(raw) as Record<string, Recommendation>) : {};
  } catch {
    return {};
  }
}

function writeStore(store: Record<string, Recommendation>, lastId: string) {
  if (typeof window === "undefined") return;
  sessionStorage.setItem(STORE_KEY, JSON.stringify(store));
  sessionStorage.setItem(LAST_KEY, lastId);
}

export async function mockGetPorts() {
  await delay();
  return PORTS;
}

export async function mockGetOriginHubs() {
  await delay();
  return ORIGIN_HUBS;
}

export async function mockGetVesselClasses() {
  await delay();
  return VESSEL_CLASSES;
}

export async function mockCreateRecommendation(request: RecommendRequest): Promise<Recommendation> {
  await delay(380);
  const rec = buildRecommendation(request);
  const store = readStore();
  store[rec.id] = rec;
  writeStore(store, rec.id);
  return rec;
}

export async function mockGetRecommendation(id: string): Promise<Recommendation> {
  await delay();
  if (id === DEMO_ID || id === "latest") {
    const last = typeof window !== "undefined" ? sessionStorage.getItem(LAST_KEY) : null;
    if (id === "latest" && last) {
      const stored = readStore()[last];
      // Validate the stored object has voyageWeather (added in v3)
      if (stored && stored.voyageWeather && stored.voyageWeather.daily_waypoints?.length) return stored;
    }
    return getDemoRecommendation();
  }
  const stored = readStore()[id];
  if (stored) return stored;
  throw new Error(`Recommendation ${id} not found`);
}
