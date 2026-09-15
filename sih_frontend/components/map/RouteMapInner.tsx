"use client";

import type { Recommendation } from "@/lib/types";
import { CircleMarker, MapContainer, Polyline, Popup, TileLayer } from "react-leaflet";

export function RouteMapInner({ rec }: { rec: Recommendation }) {
  const a: [number, number] = [rec.originHub.lat, rec.originHub.lng];
  const b: [number, number] = [rec.destinationPort.lat, rec.destinationPort.lng];
  const mid: [number, number] = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
  const port = rec.destinationPort;
  const recommended = rec.summary.vesselClassId;

  return (
    <MapContainer center={mid} zoom={3} scrollWheelZoom={false} className="h-[320px] w-full">
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <CircleMarker center={a} radius={8} pathOptions={{ color: "#065A82", fillColor: "#1C7293", fillOpacity: 1 }}>
        <Popup>
          <strong>{rec.originHub.region}</strong>
          <br />
          {rec.originHub.typicalExportBerth}
        </Popup>
      </CircleMarker>
      <CircleMarker center={b} radius={8} pathOptions={{ color: "#E8A33D", fillColor: "#E8A33D", fillOpacity: 1 }}>
        <Popup>
          <strong>{port.name}</strong>
          <br />
          Max draft {port.maxDraftM} m · LOA {port.maxLoaM} m · beam {port.maxBeamM} m
          <br />
          Handling {port.handlingRateMtpd.toLocaleString()} MT/day
        </Popup>
      </CircleMarker>
      <Polyline positions={[a, b]} pathOptions={{ color: "#21295C", weight: 2, dashArray: "6 6" }} />
      {rec.vesselOptions.map((v, i) => {
        const offset = (i - 1.5) * 1.1;
        const pt: [number, number] = [b[0] + offset * 0.35, b[1] + 1.8 + i * 0.15];
        const color =
          v.feasibility === "feasible" ? "#3E8C6B" : v.feasibility === "marginal" ? "#D69A3F" : "#C24A3B";
        const isRec = v.vesselClassId === recommended;
        return (
          <CircleMarker
            key={v.vesselClassId}
            center={pt}
            radius={isRec ? 7 : 5}
            pathOptions={{ color, fillColor: color, fillOpacity: isRec ? 1 : 0.7, weight: isRec ? 3 : 1 }}
          >
            <Popup>
              <strong>
                {v.vesselClassName}
                {isRec ? " · recommended" : ""}
              </strong>
              <br />
              {v.feasibility.toUpperCase()}
              <br />
              {v.reason}
            </Popup>
          </CircleMarker>
        );
      })}
    </MapContainer>
  );
}
