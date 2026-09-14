import { vi } from "vitest";

const benchmarkPageMocks = vi.hoisted(() => ({
  invalidateQueries: vi.fn(),
  setQueriesData: vi.fn(),
}));

export function getBenchmarkPageMocks() {
  return benchmarkPageMocks;
}

vi.mock("@tanstack/react-query", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@tanstack/react-query")>();
  return {
    ...actual,
    useQueryClient: () => ({
      invalidateQueries: benchmarkPageMocks.invalidateQueries,
      setQueriesData: benchmarkPageMocks.setQueriesData,
    }),
  };
});

vi.mock("@/hooks/use-smart-back", () => ({
  useSmartBack: () => vi.fn(),
}));

vi.mock("@/api/benchmarks", () => ({
  createBenchmarkRun: vi.fn(),
  deleteBenchmarkRun: vi.fn(),
  getBenchmarkRun: vi.fn(),
  listBenchmarkRuns: vi.fn(),
  updateBenchmarkRun: vi.fn(),
}));

vi.mock("@/api/backends", () => ({
  fetchBackendCapabilities: vi.fn(),
  forceRefreshBackendCapabilities: vi.fn(),
  getBackendCapabilitiesCached: vi.fn(),
}));

vi.mock("@/api/molecules", () => ({
  createMolecule: vi.fn(),
  fetchBasisSets: vi.fn(),
  fetchMolecules: vi.fn(),
}));

vi.mock("@/api/profiles", () => ({
  warmAllBackendCapabilitiesCache: vi.fn(),
}));

vi.mock("@/api/runs", () => ({
  createRun: vi.fn(),
  cancelRun: vi.fn(),
  getRun: vi.fn(),
  getRunEvents: vi.fn(),
  getRunResult: vi.fn(),
  pauseRun: vi.fn(),
  restartRun: vi.fn(),
  resumeRun: vi.fn(),
}));
