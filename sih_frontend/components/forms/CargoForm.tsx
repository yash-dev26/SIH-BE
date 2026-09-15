"use client";

import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import { useCreateRecommendation } from "@/hooks/useRecommendation";
import {
  COMMODITIES,
  CONTRACT_PREFERENCES,
  DESTINATIONS,
  ORIGINS,
  RISK_TOLERANCES,
  cargoFormSchema,
  type CargoFormValues,
} from "@/lib/schema";
import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useForm, useWatch } from "react-hook-form";
import type { ReactNode } from "react";
import { ArrowRight, BriefcaseBusiness, CircleDot, Waves } from "lucide-react";

const CONTRACT_LABELS: Record<(typeof CONTRACT_PREFERENCES)[number], string> = {
  let_system_decide: "Let system decide",
  spot: "Spot",
  short_term: "Short-term",
  coa: "COA",
  period: "Period",
};

const RISK_LABELS: Record<(typeof RISK_TOLERANCES)[number], string> = {
  conservative: "Conservative",
  balanced: "Balanced",
  aggressive: "Aggressive",
};

function defaultDates() {
  const start = new Date();
  start.setDate(start.getDate() + 21);
  const end = new Date();
  end.setDate(end.getDate() + 35);
  const iso = (d: Date) => d.toISOString().slice(0, 10);
  return { laycanStart: iso(start), laycanEnd: iso(end) };
}

function Group({ title, index, children }: { title: string; index: string; children: ReactNode }) {
  return (
    <fieldset className="min-w-0">
      <legend className="mb-5 flex w-full items-center gap-3">
        <span className="grid h-6 w-6 place-items-center rounded-full bg-deep text-[10px] font-bold text-paper">{index}</span>
        <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-deep">{title}</span>
        <span className="h-px flex-1 bg-line" />
      </legend>
      <div className="grid gap-x-4 gap-y-4 sm:grid-cols-2">{children}</div>
    </fieldset>
  );
}

export function CargoForm() {
  const router = useRouter();
  const create = useCreateRecommendation();
  const dates = defaultDates();
  const form = useForm<CargoFormValues>({
    resolver: zodResolver(cargoFormSchema),
    defaultValues: {
      commodity: "Thermal Coal",
      quantityMt: 70000,
      origin: "Australia",
      destination: "Paradip",
      ...dates,
      contractPreference: "let_system_decide",
      riskTolerance: "balanced",
    },
  });
  const origin = useWatch({ control: form.control, name: "origin" });
  const destination = useWatch({ control: form.control, name: "destination" });

  const onSubmit = form.handleSubmit(async (values) => {
    const rec = await create.mutateAsync(values);
    router.push(`/dashboard/${rec.id}`);
  });

  return (
    <form onSubmit={onSubmit} className="overflow-hidden border border-line bg-paper shadow-[0_16px_45px_rgba(15,27,36,0.12)]">
      <div className="flex flex-col gap-5 border-b border-line bg-[#f6f9fb] px-5 py-5 md:flex-row md:items-center md:justify-between md:px-7">
        <div className="flex items-start gap-3">
          <span className="grid h-10 w-10 shrink-0 place-items-center bg-ink text-gold"><BriefcaseBusiness className="h-5 w-5" /></span>
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-teal">New decision brief</p>
            <h2 className="mt-0.5 font-serif text-2xl text-ink">Create Cargo Scenario</h2>
          </div>
        </div>
        <div className="flex items-center gap-2 border border-teal/20 bg-paper px-3 py-2 text-right">
          <CircleDot className="h-3.5 w-3.5 shrink-0 text-teal" />
          <div>
            <p className="text-[9px] font-bold uppercase tracking-[0.15em] text-muted">Route scenario</p>
            <p className="mt-0.5 text-xs font-semibold text-ink">{origin || "Origin"} <span className="mx-1 text-gold">→</span> {destination || "Destination"}</p>
          </div>
        </div>
      </div>

      <div className="grid gap-8 px-5 py-7 md:px-7 lg:grid-cols-[.84fr_1.28fr_.88fr] lg:gap-0 lg:py-8">
        <div className="lg:pr-7">
        <Group title="Cargo" index="01">
          <Field label="Commodity" error={form.formState.errors.commodity?.message}>
            <Select {...form.register("commodity")}>
              {COMMODITIES.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </Select>
          </Field>
          <Field label="Cargo quantity (MT)" error={form.formState.errors.quantityMt?.message}>
            <Input type="number" step="1" min="1" {...form.register("quantityMt", { valueAsNumber: true })} />
          </Field>
        </Group>
        </div>
        <div className="border-line lg:border-x lg:px-7">
        <Group title="Voyage" index="02">
          <Field label="Origin" error={form.formState.errors.origin?.message}>
            <Select {...form.register("origin")}>
              {ORIGINS.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </Select>
          </Field>
          <Field label="Destination port" error={form.formState.errors.destination?.message}>
            <Select {...form.register("destination")}>
              {DESTINATIONS.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </Select>
          </Field>
          <Field label="Laycan start" error={form.formState.errors.laycanStart?.message}>
            <Input type="date" {...form.register("laycanStart")} />
          </Field>
          <Field label="Laycan end" error={form.formState.errors.laycanEnd?.message}>
            <Input type="date" {...form.register("laycanEnd")} />
          </Field>
        </Group>
        </div>
        <div className="lg:pl-7">
        <Group title="Chartering preference" index="03">
          <Field label="Contract preference" error={form.formState.errors.contractPreference?.message}>
            <Select {...form.register("contractPreference")}>
              {CONTRACT_PREFERENCES.map((c) => (
                <option key={c} value={c}>
                  {CONTRACT_LABELS[c]}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Risk tolerance" error={form.formState.errors.riskTolerance?.message}>
            <Select {...form.register("riskTolerance")}>
              {RISK_TOLERANCES.map((c) => (
                <option key={c} value={c}>
                  {RISK_LABELS[c]}
                </option>
              ))}
            </Select>
          </Field>
        </Group>
        </div>
      </div>
      <div className="flex flex-col gap-4 border-t border-line bg-[#f6f9fb] px-5 py-5 sm:flex-row sm:items-center sm:justify-between md:px-7">
        <p className="flex items-center gap-2 text-xs text-muted"><Waves className="h-4 w-4 text-teal" /> Market, route and vessel feasibility assessment</p>
        <Button type="submit" disabled={create.isPending} className="group min-w-[260px] self-start sm:self-auto">
          {create.isPending ? "Generating…" : <>Generate recommendation <ArrowRight className="ml-2 h-4 w-4 transition-transform group-hover:translate-x-0.5" /></>}
        </Button>
      </div>
      {create.isError ? <p className="text-sm text-risk-high">Could not generate recommendation.</p> : null}
    </form>
  );
}
