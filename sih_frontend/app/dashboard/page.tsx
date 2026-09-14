"use client";

import { DashboardView } from "@/components/dashboard/DashboardView";
import { DeskError, DeskLoading } from "@/components/dashboard/DeskState";
import { useRecommendation } from "@/hooks/useRecommendation";

export default function DashboardPage() {
  const { data, isLoading, error } = useRecommendation("latest");
  if (isLoading) return <DeskLoading />;
  if (error || !data) return <DeskError message="Could not load demo recommendation." />;
  return <DashboardView rec={data} />;
}
