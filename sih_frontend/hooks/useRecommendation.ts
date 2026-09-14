"use client";

import { createRecommendation, getRecommendation } from "@/lib/api";
import type { RecommendRequest } from "@/lib/types";
import { useMutation, useQuery } from "@tanstack/react-query";

export function useRecommendation(id: string | undefined) {
  return useQuery({
    queryKey: ["recommendation", id],
    queryFn: () => getRecommendation(id!),
    enabled: Boolean(id),
  });
}

export function useCreateRecommendation() {
  return useMutation({
    mutationFn: (request: RecommendRequest) => createRecommendation(request),
  });
}
