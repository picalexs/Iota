/** Benchmark API calls. */

import type { BenchmarkEntry, SavedBenchmarkRun } from "@/types/benchmark";
import type { MoleculeResponse, UUID } from "@/types/run";
import type {
  ApiBenchmarkRunResponse,
  ApiBenchmarkRunCreate,
  ApiBenchmarkRunListResponse,
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
    (!("selectedBackendName" in value) ||
      value.selectedBackendName === null ||
      typeof value.selectedBackendName === "string") &&
    isFiniteNumber(value.chemicalAccuracyHa) &&
    value.chemicalAccuracyHa > 0 &&
    (!("customMolecules" in value) || isRecordArray(value.customMolecules)) &&
    (!("entries" in value) || isRecordArray(value.entries))
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
    shots: data.shots ?? 1024,
    selectedAerMethod: data.selectedAerMethod,
    selectedDevice: data.selectedDevice,
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
    selectedAerMethod: data.selectedAerMethod,
    selectedDevice: data.selectedDevice,
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
