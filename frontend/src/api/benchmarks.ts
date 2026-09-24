/** Benchmark API calls. */

import type {
  BenchmarkEntry,
  SavedBenchmarkRun,
  SavedBenchmarkRunSummary,
} from "@/types/benchmark";
import type { MoleculeResponse, UUID } from "@/types/run";
import type {
  ApiBenchmarkRunResponse,
  ApiBenchmarkRunCreate,
  ApiBenchmarkRunListResponse,
  ApiBenchmarkRunSummaryListResponse,
  ApiBenchmarkRunSummaryResponse,
  ApiBenchmarkRunUpdate,
} from "@/types/api";
import { isRunAlgorithm } from "@/types/run-status";
import {
  API_BASE,
  fetchWithApiError,
  handleApiError,
  isFiniteNumber,
  isOptionalStringArray,
  isRecord,
  isRecordArray,
  invalidApiResponse,
  request,
} from "./http";

type BenchmarkOptimizationLevel = 0 | 1 | 2 | 3;

export interface BenchmarkRunListResponse {
  items: SavedBenchmarkRun[];
  total: number;
  limit: number;
  offset: number;
}

export type BenchmarkRunCreate = Omit<SavedBenchmarkRun, "id" | "createdAt" | "updatedAt"> & {
  id?: string;
  createdAt?: string;
  updatedAt?: string;
};

export type BenchmarkRunUpdate = Partial<BenchmarkRunCreate>;

export interface DeleteBenchmarkRunOptions {
  deleteAssociatedRuns?: boolean;
}

const BENCHMARK_BACKEND_MODES = new Set<ApiBenchmarkRunResponse["selectedBackendMode"]>([
  "statevector",
  "aer_simulator",
  "aer_simulator_backend_noise",
  "ibm_runtime",
]);

function isBenchmarkRunResponse(value: unknown): value is ApiBenchmarkRunResponse {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.name === "string" &&
    typeof value.createdAt === "string" &&
    typeof value.updatedAt === "string" &&
    isOptionalStringArray(value, "selectedMoleculeKeys") &&
    (!("selectedAlgorithms" in value) ||
      (Array.isArray(value.selectedAlgorithms) &&
        value.selectedAlgorithms.every(isRunAlgorithm))) &&
    typeof value.selectedBasis === "string" &&
    typeof value.selectedBackendMode === "string" &&
    BENCHMARK_BACKEND_MODES.has(
      value.selectedBackendMode as ApiBenchmarkRunResponse["selectedBackendMode"],
    ) &&
    (!("shots" in value) || (isFiniteNumber(value.shots) && value.shots >= 1)) &&
    (!("optimizationLevel" in value) ||
      (isFiniteNumber(value.optimizationLevel) &&
        value.optimizationLevel >= 0 &&
        value.optimizationLevel <= 3 &&
        Number.isInteger(value.optimizationLevel))) &&
    (!("seedTranspiler" in value) ||
      value.seedTranspiler === null ||
      (isFiniteNumber(value.seedTranspiler) && value.seedTranspiler >= 0)) &&
    (!("dynamicalDecoupling" in value) || typeof value.dynamicalDecoupling === "boolean") &&
    (!("twirling" in value) || typeof value.twirling === "boolean") &&
    (!("selectedBackendName" in value) ||
      value.selectedBackendName === null ||
      typeof value.selectedBackendName === "string") &&
    isFiniteNumber(value.chemicalAccuracyHa) &&
    value.chemicalAccuracyHa > 0 &&
    (!("customMolecules" in value) || isRecordArray(value.customMolecules)) &&
    (!("entries" in value) || isRecordArray(value.entries))
  );
}

function isBenchmarkRunSummaryResponse(value: unknown): value is ApiBenchmarkRunSummaryResponse {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.name === "string" &&
    typeof value.createdAt === "string" &&
    typeof value.updatedAt === "string" &&
    isOptionalStringArray(value, "selectedMoleculeKeys") &&
    typeof value.selectedBasis === "string" &&
    BENCHMARK_BACKEND_MODES.has(
      value.selectedBackendMode as ApiBenchmarkRunSummaryResponse["selectedBackendMode"],
    ) &&
    (!("selectedBackendName" in value) ||
      value.selectedBackendName === null ||
      typeof value.selectedBackendName === "string") &&
    typeof value.status === "string" &&
    [
      "draft",
      "running",
      "paused",
      "finished",
      "partial",
      "failed",
      "cancelled",
      "planned",
      "excluded",
    ].includes(value.status) &&
    [
      "rowCount",
      "completedCount",
      "activeCount",
      "pausedCount",
      "failedCount",
      "cancelledCount",
      "plannedCount",
      "excludedCount",
      "associatedRunCount",
    ].every((key) => isFiniteNumber(value[key]))
  );
}

export function parseBenchmarkRunResponse(value: unknown): ApiBenchmarkRunResponse {
  if (!isBenchmarkRunResponse(value)) {
    throw invalidApiResponse("Invalid benchmark run response");
  }
  return value;
}

export function parseBenchmarkRunListResponse(value: unknown): ApiBenchmarkRunListResponse {
  if (
    !isRecord(value) ||
    !Array.isArray(value.items) ||
    !value.items.every(isBenchmarkRunResponse) ||
    !isFiniteNumber(value.total) ||
    !isFiniteNumber(value.limit) ||
    !isFiniteNumber(value.offset)
  ) {
    throw invalidApiResponse("Invalid benchmark run list response");
  }
  return value as ApiBenchmarkRunListResponse;
}

export function parseBenchmarkRunSummaryListResponse(
  value: unknown,
): ApiBenchmarkRunSummaryListResponse {
  if (
    !isRecord(value) ||
    !Array.isArray(value.items) ||
    !value.items.every(isBenchmarkRunSummaryResponse) ||
    !isFiniteNumber(value.total) ||
    !isFiniteNumber(value.limit) ||
    !isFiniteNumber(value.offset)
  ) {
    throw invalidApiResponse("Invalid benchmark run summary list response");
  }
  return value as ApiBenchmarkRunSummaryListResponse;
}

function toJsonObjects<T extends object>(
  values: T[] | undefined,
): Record<string, unknown>[] | undefined {
  return values?.map((value) => ({ ...value }) as Record<string, unknown>);
}

function toSavedBenchmarkRun(data: ApiBenchmarkRunResponse): SavedBenchmarkRun {
  return {
    ...data,
    selectedMoleculeKeys: data.selectedMoleculeKeys ?? [],
    selectedAlgorithms: data.selectedAlgorithms ?? [],
    selectedBackendName: data.selectedBackendName ?? null,
    shots: data.shots ?? 4096,
    optimizationLevel: (data.optimizationLevel ?? 1) as BenchmarkOptimizationLevel,
    seedTranspiler: data.seedTranspiler ?? null,
    dynamicalDecoupling: data.dynamicalDecoupling ?? false,
    twirling: data.twirling ?? false,
    customMolecules: (data.customMolecules ?? []) as unknown as MoleculeResponse[],
    entries: (data.entries ?? []) as unknown as BenchmarkEntry[],
  };
}

function toBenchmarkRunList(data: ApiBenchmarkRunListResponse): BenchmarkRunListResponse {
  return {
    ...data,
    items: data.items.map(toSavedBenchmarkRun),
  };
}

function toSavedBenchmarkRunSummary(
  data: ApiBenchmarkRunSummaryResponse,
): SavedBenchmarkRunSummary {
  return {
    ...data,
    selectedMoleculeKeys: data.selectedMoleculeKeys ?? [],
    selectedBackendName: data.selectedBackendName ?? null,
  };
}

function toBenchmarkRunCreate(data: BenchmarkRunCreate): ApiBenchmarkRunCreate {
  return {
    name: data.name,
    campaignId: data.campaignId,
    campaignMetadata: data.campaignMetadata,
    registrationDigest: data.registrationDigest,
    selectedMoleculeKeys: data.selectedMoleculeKeys,
    selectedAlgorithms: data.selectedAlgorithms,
    selectedBasis: data.selectedBasis,
    selectedBackendMode: data.selectedBackendMode,
    selectedBackendName: data.selectedBackendName,
    shots: data.shots ?? 4096,
    optimizationLevel: data.optimizationLevel ?? 1,
    seedTranspiler: data.seedTranspiler ?? null,
    dynamicalDecoupling: data.dynamicalDecoupling ?? false,
    twirling: data.twirling ?? false,
    chemicalAccuracyHa: data.chemicalAccuracyHa,
    customMolecules: toJsonObjects(data.customMolecules),
    entries: toJsonObjects(data.entries),
  };
}

function toBenchmarkRunUpdate(data: BenchmarkRunUpdate): ApiBenchmarkRunUpdate {
  return {
    name: data.name,
    selectedMoleculeKeys: data.selectedMoleculeKeys,
    selectedAlgorithms: data.selectedAlgorithms,
    selectedBasis: data.selectedBasis,
    selectedBackendMode: data.selectedBackendMode,
    selectedBackendName: data.selectedBackendName,
    shots: data.shots,
    optimizationLevel: data.optimizationLevel,
    seedTranspiler: data.seedTranspiler,
    dynamicalDecoupling: data.dynamicalDecoupling,
    twirling: data.twirling,
    chemicalAccuracyHa: data.chemicalAccuracyHa,
    customMolecules: toJsonObjects(data.customMolecules),
    entries: toJsonObjects(data.entries),
  };
}

export async function createBenchmarkRun(data: BenchmarkRunCreate): Promise<SavedBenchmarkRun> {
  const response = parseBenchmarkRunResponse(
    await request<unknown>(`${API_BASE}/api/benchmarks`, {
      method: "POST",
      body: JSON.stringify(toBenchmarkRunCreate(data)),
    }),
  );
  return toSavedBenchmarkRun(response);
}

export async function listBenchmarkRuns(params?: {
  limit?: number;
  offset?: number;
}): Promise<BenchmarkRunListResponse> {
  const query = new URLSearchParams();
  if (params?.limit !== undefined) query.append("limit", String(params.limit));
  if (params?.offset !== undefined) query.append("offset", String(params.offset));
  const queryString = query.toString();
  const url =
    queryString.length > 0
      ? `${API_BASE}/api/benchmarks?${queryString}`
      : `${API_BASE}/api/benchmarks`;

  const response = parseBenchmarkRunListResponse(await request<unknown>(url, { method: "GET" }));
  return toBenchmarkRunList(response);
}

export interface BenchmarkRunSummaryListResponse {
  items: SavedBenchmarkRunSummary[];
  total: number;
  limit: number;
  offset: number;
}

export async function listBenchmarkRunSummaries(params?: {
  limit?: number;
  offset?: number;
  status?: SavedBenchmarkRunSummary["status"];
  backend?: string;
  sort?: "name" | "rows" | "backend" | "updated" | "status";
  order?: "asc" | "desc";
}): Promise<BenchmarkRunSummaryListResponse> {
  const query = new URLSearchParams();
  if (params?.limit !== undefined) query.append("limit", String(params.limit));
  if (params?.offset !== undefined) query.append("offset", String(params.offset));
  if (params?.status !== undefined) query.append("status", params.status);
  if (params?.backend !== undefined) query.append("backend", params.backend);
  if (params?.sort !== undefined) query.append("sort", params.sort);
  if (params?.order !== undefined) query.append("order", params.order);
  const queryString = query.toString();
  const url =
    queryString.length > 0
      ? `${API_BASE}/api/benchmarks/summaries?${queryString}`
      : `${API_BASE}/api/benchmarks/summaries`;
  const response = parseBenchmarkRunSummaryListResponse(
    await request<unknown>(url, { method: "GET" }),
  );
  return {
    ...response,
    items: response.items.map(toSavedBenchmarkRunSummary),
  };
}

export async function getBenchmarkRun(id: UUID): Promise<SavedBenchmarkRun> {
  const response = parseBenchmarkRunResponse(
    await request<unknown>(`${API_BASE}/api/benchmarks/${id}`, {
      method: "GET",
    }),
  );
  return toSavedBenchmarkRun(response);
}

export async function updateBenchmarkRun(
  id: UUID,
  data: BenchmarkRunUpdate,
): Promise<SavedBenchmarkRun> {
  const response = parseBenchmarkRunResponse(
    await request<unknown>(`${API_BASE}/api/benchmarks/${id}`, {
      method: "PATCH",
      body: JSON.stringify(toBenchmarkRunUpdate(data)),
    }),
  );
  return toSavedBenchmarkRun(response);
}

export async function deleteBenchmarkRun(
  id: UUID,
  options: DeleteBenchmarkRunOptions = {},
): Promise<void> {
  const query = new URLSearchParams();
  if (options.deleteAssociatedRuns) {
    query.set("delete_associated_runs", "true");
  }
  const url =
    query.size > 0
      ? `${API_BASE}/api/benchmarks/${id}?${query.toString()}`
      : `${API_BASE}/api/benchmarks/${id}`;

  const response = await fetchWithApiError(url, {
    method: "DELETE",
    headers: new Headers({ Accept: "application/json" }),
  });
  if (!response.ok) {
    await handleApiError(response, { method: "DELETE", url });
  }
}
