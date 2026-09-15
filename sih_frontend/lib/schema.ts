import { z } from "zod";

export const COMMODITIES = ["Thermal Coal", "Coking Coal", "Iron Ore"] as const;
export const ORIGINS = ["Australia", "US", "Mozambique", "Russia", "Indonesia"] as const;
export const DESTINATIONS = [
  "Paradip",
  "Vizag",
  "Gangavaram",
  "Gopalpur",
  "Dhamra",
  "Sagar-Sandheads",
  "Haldia",
] as const;
export const CONTRACT_PREFERENCES = [
  "let_system_decide",
  "spot",
  "short_term",
  "coa",
  "period",
] as const;
export const RISK_TOLERANCES = ["conservative", "balanced", "aggressive"] as const;

export const cargoFormSchema = z
  .object({
    commodity: z.enum(COMMODITIES),
    quantityMt: z.coerce
      .number({ invalid_type_error: "Enter cargo quantity in MT" })
      .positive("Quantity must be greater than 0")
      .max(400000, "Quantity exceeds a single-voyage bulk parcel"),
    origin: z.enum(ORIGINS),
    destination: z.enum(DESTINATIONS),
    laycanStart: z.string().min(1, "Laycan start is required"),
    laycanEnd: z.string().min(1, "Laycan end is required"),
    contractPreference: z.enum(CONTRACT_PREFERENCES),
    riskTolerance: z.enum(RISK_TOLERANCES),
  })
  .refine((v) => v.laycanEnd >= v.laycanStart, {
    message: "Laycan end must be on or after start",
    path: ["laycanEnd"],
  });

export type CargoFormValues = z.infer<typeof cargoFormSchema>;
