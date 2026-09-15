import { CargoForm } from "@/components/forms/CargoForm";
import { SamundraSetuLogo } from "@/components/brand/SamundraSetuLogo";
import { ArrowUpRight, Compass, Route, ShieldCheck, ShipWheel, type LucideIcon } from "lucide-react";
import Link from "next/link";

export default function HomePage() {
  const highlights: Array<{ icon: LucideIcon; title: string; detail: string }> = [
    { icon: Compass, title: "Freight market insights", detail: "Data-driven forecasts" },
    { icon: Route, title: "Vessel & port feasibility", detail: "Physical constraints" },
    { icon: ShieldCheck, title: "Actionable recommendations", detail: "Smarter chartering decisions" },
  ];

  return (
    <div className="min-h-screen overflow-hidden bg-ice">
      <header className="relative z-10 border-b border-white/10 bg-ink text-paper">
        <div className="mx-auto flex max-w-[1280px] items-center justify-between px-5 py-4 md:px-8">
          <Link href="/" className="flex items-center gap-2.5">
            <SamundraSetuLogo className="w-10" />
            <span className="font-serif text-xl tracking-tight text-paper sm:text-[22px]">Samundra Setu</span>
            <span className="hidden h-5 w-px bg-white/20 sm:block" />
            <span className="hidden text-[9px] font-semibold uppercase tracking-[0.18em] text-ice/55 sm:block">Maritime intelligence system</span>
          </Link>
          <Link
            href="/dashboard"
            className="group inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-gold"
          >
            Decision desk <ArrowUpRight className="h-3.5 w-3.5 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
          </Link>
        </div>
      </header>

      <main>
        <section className="relative isolate overflow-hidden bg-ink pb-24 pt-14 text-paper md:pb-32 md:pt-20">
          <div className="pointer-events-none absolute inset-0 opacity-30 [background-image:linear-gradient(90deg,transparent_0%,rgba(111,182,208,.18)_1px,transparent_1px),linear-gradient(0deg,transparent_0%,rgba(111,182,208,.12)_1px,transparent_1px)] [background-size:72px_72px]" />
          <div className="pointer-events-none absolute -right-16 top-[-220px] h-[540px] w-[540px] rounded-full border border-teal/30" />
          <div className="pointer-events-none absolute -right-3 top-[-155px] h-[410px] w-[410px] rounded-full border border-teal/25" />
          <div className="pointer-events-none absolute right-[15%] top-24 h-px w-[42%] rotate-[27deg] bg-gradient-to-r from-transparent via-gold/80 to-transparent" />
          <div className="relative mx-auto max-w-[1280px] px-5 md:px-8">
            <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_280px] lg:items-end">
              <div>
                <p className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.2em] text-gold">
                  <Compass className="h-3.5 w-3.5" /> Chartering decision workspace
                </p>
                <h1 className="mt-5 max-w-4xl font-serif text-[42px] leading-[1.04] tracking-[-0.025em] md:text-6xl">
                  Make the right chartering decision before the market moves.
                </h1>
                <p className="mt-5 max-w-xl text-[15px] leading-7 text-ice/70 md:text-base">
                  Turn cargo requirements into a defensible chartering recommendation in one focused brief.
                </p>
                <div className="mt-8 grid max-w-2xl gap-4 sm:grid-cols-3">
                  {highlights.map(({ icon: FeatureIcon, title, detail }) => {
                    return <div key={title} className="flex items-center gap-2.5 border-l border-white/15 pl-3"><FeatureIcon className="h-5 w-5 text-teal" /><span><span className="block text-[11px] font-semibold text-paper">{title}</span><span className="block text-[10px] text-ice/50">{detail}</span></span></div>;
                  })}
                </div>
              </div>
              <div className="hidden border-l border-white/15 pl-6 lg:block">
                <ShipWheel className="h-6 w-6 text-gold" />
                <p className="mt-7 text-[10px] font-semibold uppercase tracking-[0.18em] text-ice/50">Built for the desk</p>
                <p className="mt-2 text-sm leading-6 text-ice/75">Freight outlook, vessel fit and contracting posture in one decision flow.</p>
              </div>
            </div>
          </div>
        </section>

        <section className="relative mx-auto -mt-12 max-w-[1280px] px-5 pb-12 md:-mt-16 md:px-8 md:pb-20">
          <CargoForm />
        </section>
      </main>
    </div>
  );
}
