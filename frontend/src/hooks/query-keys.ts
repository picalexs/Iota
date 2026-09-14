import type { MoleculeListParams, RunListParams, UUID } from "@/types/run";

export const runKeys = {
  all: ["runs"] as const,
  listPrefix: ["runs", "list"] as const,
  summariesPrefix: ["runs", "summaries"] as const,
  list: (params?: RunListParams) => ["runs", "list", params] as const,
  summaries: (params?: RunListParams) => ["runs", "summaries", params] as const,
  allSummaries: ["runs", "summaries", "all"] as const,
  detail: (runId: UUID | null) => ["runs", "detail", runId] as const,
  events: (runId: UUID) => ["runs", "events", runId] as const,
};

export const moleculeKeys = {
  all: ["molecules"] as const,
  listPrefix: ["molecules", "list"] as const,
  summariesPrefix: ["molecules", "summaries"] as const,
  list: (params: MoleculeListParams) => ["molecules", "list", params] as const,
  summaries: (params: MoleculeListParams) => ["molecules", "summaries", params] as const,
  allMolecules: ["molecules", "all"] as const,
  allSummaries: ["molecules", "summaries", "all"] as const,
  detail: (moleculeId: UUID | null) => ["molecules", "detail", moleculeId] as const,
};

export const benchmarkKeys = {
  all: ["benchmarks"] as const,
  listPrefix: ["benchmarks", "list"] as const,
  list: (params?: { limit?: number; offset?: number }) => ["benchmarks", "list", params] as const,
};

export const profileKeys = {
  all: ["profiles"] as const,
  list: ["profiles", "list"] as const,
};

export const backendKeys = {
  all: ["backends"] as const,
  catalog: ["backends", "catalog"] as const,
};

export const configKeys = {
  metadata: ["run-config", "metadata"] as const,
};
