import type { Destination, Origin, OriginHub, Port, VesselClass } from "@/lib/types";

export const ORIGIN_HUBS: OriginHub[] = [
  {
    id: "Australia",
    name: "Hay Point / Newcastle corridor",
    region: "Australia",
    lat: -21.27,
    lng: 149.3,
    typicalExportBerth: "Hay Point (thermal coal)",
  },
  {
    id: "US",
    name: "US East Coast coal ports",
    region: "US",
    lat: 36.85,
    lng: -76.29,
    typicalExportBerth: "Norfolk / Newport News",
  },
  {
    id: "Mozambique",
    name: "Beira / Nacala",
    region: "Mozambique",
    lat: -19.82,
    lng: 34.87,
    typicalExportBerth: "Beira",
  },
  {
    id: "Russia",
    name: "Far East export ports",
    region: "Russia",
    lat: 42.76,
    lng: 133.05,
    typicalExportBerth: "Vostochny",
  },
  {
    id: "Indonesia",
    name: "Kalimantan anchorage",
    region: "Indonesia",
    lat: -3.7,
    lng: 114.5,
    typicalExportBerth: "Taboneo / South Kalimantan",
  },
];

export const PORTS: Port[] = [
  {
    id: "paradip",
    name: "Paradip",
    country: "India",
    lat: 20.265,
    lng: 86.677,
    maxDraftM: 14.5,
    maxLoaM: 260,
    maxBeamM: 38,
    handlingRateMtpd: 42000,
    notes: "East-coast discharge hub. Deep-draft Panamax acceptable; Capesize restricted on LOA/beam/draft in this mock.",
  },
  {
    id: "vizag",
    name: "Vizag",
    country: "India",
    lat: 17.687,
    lng: 83.219,
    maxDraftM: 16.5,
    maxLoaM: 280,
    maxBeamM: 45,
    handlingRateMtpd: 38000,
    notes: "Deeper than Paradip in this mock; still cargo-size driven.",
  },
  {
    id: "gangavaram",
    name: "Gangavaram",
    country: "India",
    lat: 17.627,
    lng: 83.23,
    maxDraftM: 18.0,
    maxLoaM: 300,
    maxBeamM: 50,
    handlingRateMtpd: 45000,
    notes: "Deep-water private port. Capesize physically feasible in this mock.",
  },
  {
    id: "gopalpur",
    name: "Gopalpur",
    country: "India",
    lat: 19.305,
    lng: 84.965,
    maxDraftM: 13.5,
    maxLoaM: 230,
    maxBeamM: 33,
    handlingRateMtpd: 22000,
    notes: "Tighter draft/LOA. Panamax is the ceiling in this mock.",
  },
  {
    id: "dhamra",
    name: "Dhamra",
    country: "India",
    lat: 20.823,
    lng: 86.963,
    maxDraftM: 18.0,
    maxLoaM: 300,
    maxBeamM: 48,
    handlingRateMtpd: 50000,
    notes: "Deep-draft east-coast port. Capesize feasible in this mock.",
  },
  {
    id: "sagar-sandheads",
    name: "Sagar-Sandheads",
    country: "India",
    lat: 21.65,
    lng: 88.05,
    maxDraftM: 12.5,
    maxLoaM: 230,
    maxBeamM: 32.5,
    handlingRateMtpd: 18000,
    notes: "Lightering / draft-limited approach. Capesize infeasible.",
  },
  {
    id: "haldia",
    name: "Haldia",
    country: "India",
    lat: 22.066,
    lng: 88.11,
    maxDraftM: 8.5,
    maxLoaM: 180,
    maxBeamM: 32,
    handlingRateMtpd: 15000,
    notes: "Severe draft constraint. Panamax/Capesize infeasible without lightering.",
  },
];

export const VESSEL_CLASSES: VesselClass[] = [
  {
    id: "supramax",
    name: "Supramax",
    typicalDwt: 58000,
    loaM: 190,
    beamM: 32.3,
    designDraftM: 12.8,
  },
  {
    id: "panamax",
    name: "Panamax",
    typicalDwt: 76000,
    loaM: 225,
    beamM: 32.3,
    designDraftM: 13.5,
  },
  {
    id: "kamsarmax",
    name: "Kamsarmax",
    typicalDwt: 82000,
    loaM: 229,
    beamM: 32.3,
    designDraftM: 14.4,
  },
  {
    id: "capesize",
    name: "Capesize",
    typicalDwt: 180000,
    loaM: 292,
    beamM: 45,
    designDraftM: 17.2,
  },
];

export function portByName(name: Destination): Port {
  return PORTS.find((p) => p.name === name)!;
}

export function originById(id: Origin): OriginHub {
  return ORIGIN_HUBS.find((o) => o.id === id)!;
}
