"use client";

import { DashboardView } from "@/components/dashboard/DashboardView";
import { DeskError, DeskLoading } from "@/components/dashboard/DeskState";
import { useRecommendation } from "@/hooks/useRecommendation";
import { useParams } from "next/navigation";

export default function RecommendationByIdPage() {
  const params = useParams<{ id: string }>();
  const id = Array.isArray(params.id) ? params.id[0] : params.id;
  const { data, isLoading, error } = useRecommendation(id);
  if (isLoading) return <DeskLoading />;
  if (error || !data) return <DeskError message="Recommendation not found. Generate one from the cargo form." />;
  return <DashboardView rec={data} />;
}
