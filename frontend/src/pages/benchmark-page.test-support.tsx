import { render, screen, type RenderResult } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  RouterProvider,
} from "@tanstack/react-router";
import { vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { BenchmarkPage } from "./benchmark-page";
import { getBenchmarkPageMocks } from "./benchmark-page.test-mocks";
export { getBenchmarkPageMocks } from "./benchmark-page.test-mocks";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { MoleculeResponse, RunAlgorithm, RunResponse, RunResultResponse } from "@/types/run";
import { SAVED_BENCHMARK_LIST_LIMIT, type SavedBenchmarkRun } from "./benchmark/benchmark-storage";
import type { BenchmarkEntry } from "./benchmark/benchmark-utils";
import { clearBenchmarkWorkspaceViewCache } from "./benchmark/use-benchmark-state";
import {
  createBenchmarkRun,
  deleteBenchmarkRun,
  getBenchmarkRun,
  listBenchmarkRuns,
  updateBenchmarkRun,
} from "@/api/benchmarks";
import {
  fetchBackendCapabilities,
  forceRefreshBackendCapabilities,
  getBackendCapabilitiesCached,
} from "@/api/backends";
import { createMolecule, fetchBasisSets, fetchMolecules } from "@/api/molecules";
import { warmAllBackendCapabilitiesCache } from "@/api/profiles";
import {
  cancelRun,
  createRun,
  getRun,
  getRunEvents,
  getRunResult,
  pauseRun,
  restartRun,
  resumeRun,
} from "@/api/runs";

export const runId = "aaaaaaaa-0000-0000-0000-000000000001";
export const restartedRunId = "cccccc00-0000-0000-0000-000000000001";
export const moleculeId = "bbbbbbbb-0000-0000-0000-000000000001";

export const completedRun: RunResponse = {
  id: runId,
  molecule_id: moleculeId,
  status: "COMPLETED",
  algorithm: "vqe",
  mode: "advanced",
  backend_target: "statevector",
  config_json: {},
  ibm_job_id: null,
  client_request_id: null,
  versions: null,
  metadata: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:05:00Z",
};

export const runningRun: RunResponse = {
  ...completedRun,
  status: "RUNNING",
  updated_at: "2026-01-01T00:01:00Z",
};

export const runResult: RunResultResponse = {
  run_id: runId,
  energy: -1.137283,
  iterations: 12,
  optimal_parameters: [],
  converged: true,
  algorithm_metrics: {
    classical_references: { hf: -1.116, fci: -1.137 },
  },
  created_at: "2026-01-01T00:05:00Z",
};

export const backendCapabilitiesResponse = {
  backends: [
    {
      target: "statevector",
      enabled: true,
      available: true,
      credential_configured: true,
      supports_noise_profile: false,
      backends: [],
      default_backend: "statevector",
    },
    {
      target: "aer_simulator",
      enabled: true,
      available: true,
      credential_configured: true,
      supports_noise_profile: true,
      backends: [{ name: "aer_simulator", simulator: true, operational: true }],
      default_backend: "aer_simulator",
    },
    {
      target: "ibm_runtime",
      enabled: true,
      available: true,
      credential_configured: true,
      supports_noise_profile: false,
      backends: [
        { name: "ibm_brisbane", operational: true, pending_jobs: 3 },
        { name: "ibm_kyiv", operational: true, pending_jobs: 1 },
      ],
      default_backend: "ibm_brisbane",
    },
  ],
} as const;

export function libraryMolecule(index: number): MoleculeResponse {
  return {
    id: `11111111-0000-0000-0000-${String(index).padStart(12, "0")}`,
    name: `Library molecule ${index}`,
    atoms: [
      { symbol: "H", x: 0, y: 0, z: 0 },
      { symbol: "H", x: 0, y: 0, z: 0.735 },
    ],
    basis_set: "sto-3g",
    charge: 0,
    multiplicity: 1,
    active_space: { n_electrons: 2, n_orbitals: 2 },
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    iupac_name: `H2-${index}`,
    description: "Random library molecule",
  };
}

export function renderBenchmarkPage(initialPath = "/benchmarks/new"): RenderResult {
  const rootRoute = createRootRoute();
  const benchmarkListRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/benchmarks",
    component: BenchmarkPage,
  });
  const benchmarkLegacyRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/benchmark",
    component: BenchmarkPage,
  });
  const newBenchmarkRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/benchmarks/new",
    component: BenchmarkPage,
  });
  const benchmarkDetailRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/benchmarks/$benchmarkId",
    component: BenchmarkPage,
  });
  const runDetailRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/runs/$runId",
    component: () => null,
  });
  const routeTree = rootRoute.addChildren([
    benchmarkListRoute,
    benchmarkLegacyRoute,
    newBenchmarkRoute,
    benchmarkDetailRoute,
    runDetailRoute,
  ]);
  const history = createMemoryHistory({ initialEntries: [initialPath] });
  const router = createRouter({ routeTree, history });
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        enabled: false,
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <RouterProvider router={router} />
      </TooltipProvider>
    </QueryClientProvider>,
  );
}

const h2Preset = {
  key: "h2",
  name: "Hydrogen",
  formula: "H2",
  description: "Hydrogen molecule",
  atoms: [
    { symbol: "H", x: 0, y: 0, z: 0 },
    { symbol: "H", x: 0, y: 0, z: 0.735 },
  ],
  charge: 0,
  multiplicity: 1,
  active_space: { n_electrons: 2, n_orbitals: 2 },
  basis: "sto-3g",
  references: { hf: -1.116, fci: -1.137, source: "test" },
};

export function benchmarkEntry(overrides: Partial<BenchmarkEntry> = {}): BenchmarkEntry {
  return {
    id: overrides.id ?? "h2:vqe",
    preset: h2Preset,
    algorithm: "vqe",
    status: "queued",
    moleculeId,
    runId,
    energy: null,
    currentEnergy: null,
    converged: null,
    errorMessage: null,
    classicalRefs: null,
    elapsedSeconds: null,
    latestEventSequence: 0,
    ...overrides,
  };
}

export function pausedBenchmarkEntry() {
  return benchmarkEntry({
    status: "paused",
    currentEnergy: -1.125,
    elapsedSeconds: 12,
    latestEventSequence: 2,
  });
}

export function failedBenchmarkEntry(overrides: Partial<BenchmarkEntry> = {}) {
  return benchmarkEntry({
    status: "failed",
    currentEnergy: -1.125,
    errorMessage: "Solver failed",
    elapsedSeconds: 12,
    latestEventSequence: 2,
    ...overrides,
  });
}

export function customPausedBenchmarkEntry() {
  return benchmarkEntry({
    id: "custom:33333333-3333-3333-3333-333333333333:vqe",
    preset: {
      key: "custom:33333333-3333-3333-3333-333333333333",
      name: "Recovered custom molecule",
      atoms: [
        { symbol: "H", x: 0, y: 0, z: 0 },
        { symbol: "H", x: 0, y: 0, z: 0.735 },
      ],
      basis: "sto-3g",
      charge: 0,
      formula: "H2",
      references: { hf: -1.116, fci: -1.137, source: "unknown" },
      description: "Recovered from persisted benchmark entries.",
      active_space: { n_electrons: 2, n_orbitals: 2 },
      multiplicity: 1,
    },
    moleculeId: "33333333-3333-3333-3333-333333333333",
    status: "paused",
    currentEnergy: -1.125,
    elapsedSeconds: 12,
    latestEventSequence: 2,
  });
}

export function savedBenchmarkWithEntries(
  entries: BenchmarkEntry[],
  overrides: Partial<SavedBenchmarkRun> = {},
): SavedBenchmarkRun {
  return {
    id: "saved-benchmark-1",
    name: "Saved benchmark",
    createdAt: "2026-06-01T16:20:00Z",
    updatedAt: "2026-06-01T16:25:00Z",
    selectedMoleculeKeys: Array.from(new Set(entries.map((entry) => entry.preset.key))),
    selectedAlgorithms: Array.from(new Set(entries.map((entry) => entry.algorithm))),
    selectedBasis: "sto-3g",
    selectedBackendMode: "statevector",
    selectedBackendName: null,
    chemicalAccuracyHa: 0.0016,
    customMolecules: [],
    entries,
    ...overrides,
  };
}

export function mockBenchmarkDetail(benchmark: SavedBenchmarkRun) {
  (listBenchmarkRuns as ReturnType<typeof vi.fn>).mockResolvedValue({
    items: [benchmark],
    total: 1,
    limit: SAVED_BENCHMARK_LIST_LIMIT,
    offset: 0,
  });
  (getBenchmarkRun as ReturnType<typeof vi.fn>).mockResolvedValue(benchmark);
}

export async function selectHydrogen() {
  await userEvent.click(await screen.findByRole("button", { name: /H2\s+Hydrogen/i }));
}

export async function selectOnlyHydrogenVqe() {
  await selectHydrogen();
  await userEvent.click(screen.getByRole("button", { name: "None" }));
  await userEvent.click(screen.getByRole("button", { name: /VQEvqe/i }));
}

export function resetBenchmarkPageTestState() {
  vi.clearAllMocks();
  localStorage.clear();
  clearBenchmarkWorkspaceViewCache();
  getBenchmarkPageMocks().invalidateQueries.mockResolvedValue(undefined);
  getBenchmarkPageMocks().setQueriesData.mockImplementation((_filters, updater) =>
    typeof updater === "function" ? updater(undefined) : undefined,
  );
  (getBackendCapabilitiesCached as ReturnType<typeof vi.fn>).mockReturnValue(null);
  (fetchBackendCapabilities as ReturnType<typeof vi.fn>).mockResolvedValue(
    backendCapabilitiesResponse,
  );
  (forceRefreshBackendCapabilities as ReturnType<typeof vi.fn>).mockResolvedValue(
    backendCapabilitiesResponse,
  );
  (warmAllBackendCapabilitiesCache as ReturnType<typeof vi.fn>).mockResolvedValue({
    activeProfileId: "profile-1",
  });
  (fetchBasisSets as ReturnType<typeof vi.fn>).mockResolvedValue({
    default_basis_set: "sto-3g",
    basis_sets: [
      {
        id: "sto-3g",
        label: "STO-3G",
        description: "Minimal basis",
        family: "minimal",
        recommended: true,
        supported_elements: [],
      },
      {
        id: "6-31g",
        label: "6-31G",
        description: "Split-valence",
        family: "split_valence",
        recommended: true,
        supported_elements: [],
      },
      {
        id: "6-31g*",
        label: "6-31G*",
        description: "Polarized split-valence",
        family: "split_valence",
        recommended: true,
        supported_elements: [],
      },
      {
        id: "cc-pvdz",
        label: "cc-pVDZ",
        description: "Correlation-consistent double-zeta",
        family: "correlation_consistent",
        recommended: true,
        supported_elements: [],
      },
      {
        id: "cc-pvtz",
        label: "cc-pVTZ",
        description: "Correlation-consistent triple-zeta",
        family: "correlation_consistent",
        recommended: false,
        supported_elements: [],
      },
    ],
  });
  (fetchMolecules as ReturnType<typeof vi.fn>).mockResolvedValue({ items: [], total: 0 });
  (createMolecule as ReturnType<typeof vi.fn>).mockResolvedValue({
    id: moleculeId,
    name: "Hydrogen",
    atoms: [],
    charge: 0,
    multiplicity: 1,
    active_space: { n_electrons: 2, n_orbitals: 2 },
    basis_set: "sto-3g",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  });
  (createRun as ReturnType<typeof vi.fn>).mockResolvedValue({ id: runId, status: "QUEUED" });
  (getRun as ReturnType<typeof vi.fn>).mockResolvedValue(completedRun);
  (getRunEvents as ReturnType<typeof vi.fn>).mockResolvedValue({ events: [], last_sequence: 0 });
  (getRunResult as ReturnType<typeof vi.fn>).mockResolvedValue(runResult);
  (listBenchmarkRuns as ReturnType<typeof vi.fn>).mockResolvedValue({
    items: [],
    total: 0,
    limit: SAVED_BENCHMARK_LIST_LIMIT,
    offset: 0,
  });
  (createBenchmarkRun as ReturnType<typeof vi.fn>).mockImplementation(async (payload) => ({
    id: "dddddddd-0000-0000-0000-000000000001",
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
    ...payload,
  }));
  (getBenchmarkRun as ReturnType<typeof vi.fn>).mockImplementation(async (id) => ({
    id,
    name: "Saved benchmark",
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
    selectedMoleculeKeys: ["h2"],
    selectedAlgorithms: ["vqe"] as RunAlgorithm[],
    selectedBasis: "sto-3g",
    selectedBackendMode: "statevector",
    selectedBackendName: null,
    chemicalAccuracyHa: 0.0016,
    customMolecules: [],
    entries: [],
  }));
  (updateBenchmarkRun as ReturnType<typeof vi.fn>).mockImplementation(async (id, patch) => ({
    id,
    name: "Saved benchmark",
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:01Z",
    selectedMoleculeKeys: ["h2"],
    selectedAlgorithms: ["vqe"] as RunAlgorithm[],
    selectedBasis: "sto-3g",
    selectedBackendMode: "statevector",
    selectedBackendName: null,
    chemicalAccuracyHa: 0.0016,
    customMolecules: [],
    entries: [],
    ...patch,
  }));
  (deleteBenchmarkRun as ReturnType<typeof vi.fn>).mockResolvedValue(undefined);
  (cancelRun as ReturnType<typeof vi.fn>).mockResolvedValue({ id: runId, status: "CANCELLED" });
  (pauseRun as ReturnType<typeof vi.fn>).mockResolvedValue({ id: runId, status: "PAUSING" });
  (resumeRun as ReturnType<typeof vi.fn>).mockResolvedValue({ id: runId, status: "QUEUED" });
  (restartRun as ReturnType<typeof vi.fn>).mockResolvedValue({
    id: runId,
    status: "PAUSED",
    child_run_id: restartedRunId,
  });
}

export type { SavedBenchmarkRun };

export {
  cancelRun,
  createBenchmarkRun,
  createMolecule,
  createRun,
  deleteBenchmarkRun,
  fetchBackendCapabilities,
  fetchBasisSets,
  fetchMolecules,
  forceRefreshBackendCapabilities,
  getBackendCapabilitiesCached,
  getBenchmarkRun,
  getRun,
  getRunEvents,
  getRunResult,
  listBenchmarkRuns,
  pauseRun,
  restartRun,
  resumeRun,
  updateBenchmarkRun,
  warmAllBackendCapabilitiesCache,
};
