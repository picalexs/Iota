import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactNode } from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  useListRuns,
  useRunConfigMetadata,
  useListBenchmarkRuns,
  useAllRunSummaries,
  useAllMoleculeSummaries,
  useFetchMolecules,
  useGetRun,
  useInvalidateRunsList,
  useInvalidateMoleculesList,
  useInvalidateRun,
  useClearAllQueries,
} from "./use-query-hooks";
import type {
  RunConfigMetadataResponse,
  RunListResponse,
  RunSummaryListResponse,
  RunResponse,
  MoleculeListResponse,
  MoleculeSummaryListResponse,
} from "@/types/run";
import type { BenchmarkRunListResponse } from "@/api/benchmarks";

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 0,
        retry: false,
        gcTime: 0,
      },
    },
  });
}

interface WrapperProps {
  children: ReactNode;
}

function createWrapper(client: QueryClient) {
  return function Wrapper({ children }: Omit<WrapperProps, "client">) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

const mockRunListResponse: RunListResponse = {
  items: [
    {
      id: "run-1",
      molecule_id: "mol-1",
      status: "COMPLETED",
      config_json: {},
      ibm_job_id: null,
      client_request_id: null,
      versions: null,
      metadata: null,
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
    },
  ],
  total: 1,
  limit: 50,
  offset: 0,
};

const mockMoleculeListResponse: MoleculeListResponse = {
  items: [
    {
      id: "mol-1",
      name: "Ethylene",
      atoms: [
        { symbol: "C", x: 0, y: 0, z: 0 },
        { symbol: "C", x: 1.34, y: 0, z: 0 },
      ],
      charge: 0,
      multiplicity: 1,
      basis_set: "sto-3g",
      active_space: null,
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
    },
  ],
  total: 1,
};

const mockRunResponse: RunResponse = {
  id: "run-1",
  molecule_id: "mol-1",
  status: "COMPLETED",
  config_json: {},
  ibm_job_id: null,
  client_request_id: null,
  versions: null,
  metadata: null,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};

const mockRunSummaryListPage1: RunSummaryListResponse = {
  items: [
    {
      id: "run-1",
      molecule_id: "mol-1",
      status: "COMPLETED",
      algorithm: "vqe",
      backend_target: "statevector",
      backend_name: null,
      metadata: null,
      created_at: "2024-01-02T00:00:00Z",
      updated_at: "2024-01-02T00:00:00Z",
    },
    {
      id: "run-2",
      molecule_id: "mol-2",
      status: "FAILED",
      algorithm: "qse",
      backend_target: "aer_simulator",
      backend_name: null,
      metadata: null,
      created_at: "2024-01-01T12:00:00Z",
      updated_at: "2024-01-01T12:30:00Z",
    },
  ],
  total: 3,
  limit: 50,
  offset: 0,
};

const mockRunSummaryListPage2: RunSummaryListResponse = {
  items: [
    {
      id: "run-3",
      molecule_id: "mol-3",
      status: "COMPLETED",
      algorithm: "kqd",
      backend_target: "ibm_runtime",
      backend_name: "ibm_test",
      metadata: null,
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:15:00Z",
    },
  ],
  total: 3,
  limit: 50,
  offset: 2,
};

const mockMoleculeSummaryListPage1: MoleculeSummaryListResponse = {
  items: [
    {
      id: "mol-1",
      name: "Ethylene",
      charge: 0,
      atom_count: 6,
      formula: "C2H4",
      iupac_name: null,
      run_count: 0,
    },
  ],
  total: 2,
};

const mockMoleculeSummaryListPage2: MoleculeSummaryListResponse = {
  items: [
    {
      id: "mol-2",
      name: "Water",
      charge: 0,
      atom_count: 3,
      formula: "H2O",
      iupac_name: "oxidane",
      run_count: 0,
    },
  ],
  total: 2,
};

const mockBenchmarkRunListResponse: BenchmarkRunListResponse = {
  items: [
    {
      id: "benchmark-1",
      name: "Saved benchmark",
      createdAt: "2026-06-04T12:00:00.000Z",
      updatedAt: "2026-06-04T12:05:00.000Z",
      selectedMoleculeKeys: ["h2"],
      selectedAlgorithms: ["vqe"],
      selectedBasis: "sto-3g",
      selectedBackendMode: "statevector",
      selectedBackendName: null,
      chemicalAccuracyHa: 0.0016,
      customMolecules: [],
      entries: [],
    },
  ],
  total: 1,
  limit: 50,
  offset: 0,
};

const mockRunConfigMetadata: RunConfigMetadataResponse = {
  catalog_version: "test-catalog",
  algorithms: ["vqe", "qse", "kqd", "qfd", "sqd", "skqd"],
  backend_targets: ["statevector", "aer_simulator", "ibm_runtime"],
  easy_goals: ["fastest", "balanced", "best_accuracy"],
  easy_goal_presets: [
    { goal: "fastest", label: "5.0 mHa", chemical_accuracy_target_ha: 5e-3 },
    { goal: "balanced", label: "1.6 mHa", chemical_accuracy_target_ha: 1.6e-3 },
    { goal: "best_accuracy", label: "0.5 mHa", chemical_accuracy_target_ha: 5e-4 },
  ],
  ansatzes: [],
  optimizers: [],
  limits: {},
  defaults: {},
  capabilities: {},
};

describe("useRunConfigMetadata", () => {
  it("deduplicates and caches the server-owned catalog", async () => {
    const fetcher = vi.fn().mockResolvedValue(mockRunConfigMetadata);
    const wrapper = createWrapper(createTestQueryClient());

    const { result } = renderHook(() => useRunConfigMetadata(fetcher), { wrapper });

    await waitFor(() => {
      expect(result.current.data).toEqual(mockRunConfigMetadata);
    });

    renderHook(() => useRunConfigMetadata(fetcher), { wrapper });
    expect(fetcher).toHaveBeenCalledOnce();
  });
});

describe("useListRuns", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = createTestQueryClient();
  });

  it("should fetch runs and cache the result", async () => {
    const mockFetch = vi.fn().mockResolvedValue(mockRunListResponse);

    const { result } = renderHook(() => useListRuns(mockFetch), {
      wrapper: createWrapper(queryClient),
    });

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toEqual(mockRunListResponse);
    expect(mockFetch).toHaveBeenCalledOnce();
  });

  it("deduplicates in-flight identical requests", () => {
    const fetcher = vi.fn(async () => mockRunListResponse);
    renderHook(() => useListRuns(fetcher), { wrapper: createWrapper(queryClient) });
    renderHook(() => useListRuns(fetcher), { wrapper: createWrapper(queryClient) });
    renderHook(() => useListRuns(fetcher), { wrapper: createWrapper(queryClient) });
    renderHook(() => useListRuns(fetcher), { wrapper: createWrapper(queryClient) });
    renderHook(() => useListRuns(fetcher), { wrapper: createWrapper(queryClient) });

    expect(fetcher).toHaveBeenCalledOnce();
  });

  it("returns cached data on subsequent calls with same params", async () => {
    const fetcher = vi.fn(async () => mockRunListResponse);
    const params = { limit: 10 };

    const { result: result1 } = renderHook(() => useListRuns(fetcher, params), {
      wrapper: createWrapper(queryClient),
    });

    await waitFor(() => {
      expect(result1.current.data).toEqual(mockRunListResponse);
    });

    // Second render should use cache
    const { result: result2 } = renderHook(() => useListRuns(fetcher, params), {
      wrapper: createWrapper(queryClient),
    });

    expect(result2.current.data).toEqual(mockRunListResponse);
    expect(fetcher).toHaveBeenCalledOnce();
  });

  it("handles fetch errors correctly", async () => {
    const error = new Error("Network error");
    const fetcher = vi.fn().mockRejectedValue(error);

    const { result } = renderHook(() => useListRuns(fetcher), {
      wrapper: createWrapper(queryClient),
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toEqual(error);
  });

  it("refetches data when params change", async () => {
    const fetcher = vi.fn().mockResolvedValue(mockRunListResponse);

    const { rerender } = renderHook(({ params }) => useListRuns(fetcher, params), {
      wrapper: createWrapper(queryClient),
      initialProps: { params: { limit: 10 } },
    });

    await waitFor(() => {
      expect(fetcher).toHaveBeenCalledWith({ limit: 10 });
    });

    // Change params
    rerender({ params: { limit: 20 } });

    await waitFor(() => {
      expect(fetcher).toHaveBeenCalledWith({ limit: 20 });
    });

    expect(fetcher).toHaveBeenCalledTimes(2);
  });
});

describe("useFetchMolecules", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = createTestQueryClient();
  });

  it("should fetch molecules and cache the result", async () => {
    const fetcher = vi.fn().mockResolvedValue(mockMoleculeListResponse);

    const { result } = renderHook(() => useFetchMolecules(fetcher, { limit: 100 }), {
      wrapper: createWrapper(queryClient),
    });

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toEqual(mockMoleculeListResponse);
    expect(fetcher).toHaveBeenCalledOnce();
  });

  it("deduplicates in-flight identical molecule requests", () => {
    const fetcher = vi.fn().mockResolvedValue(mockMoleculeListResponse);
    const params = { limit: 100 };

    renderHook(() => useFetchMolecules(fetcher, params), { wrapper: createWrapper(queryClient) });
    renderHook(() => useFetchMolecules(fetcher, params), { wrapper: createWrapper(queryClient) });
    renderHook(() => useFetchMolecules(fetcher, params), { wrapper: createWrapper(queryClient) });

    expect(fetcher).toHaveBeenCalledOnce();
  });

  it("handles molecule fetch errors", async () => {
    const error = new Error("API error");
    const fetcher = vi.fn().mockRejectedValue(error);

    const { result } = renderHook(() => useFetchMolecules(fetcher, { limit: 100 }), {
      wrapper: createWrapper(queryClient),
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toEqual(error);
  });
});

describe("useAllRunSummaries", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = createTestQueryClient();
  });

  it("walks paginated run-summary responses until the full history is loaded", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(mockRunSummaryListPage1)
      .mockResolvedValueOnce(mockRunSummaryListPage2);

    const { result } = renderHook(() => useAllRunSummaries(fetcher), {
      wrapper: createWrapper(queryClient),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(fetcher).toHaveBeenNthCalledWith(1, { limit: 50, offset: 0 });
    expect(fetcher).toHaveBeenNthCalledWith(2, { limit: 50, offset: 2 });
    expect(result.current.data).toEqual([
      ...mockRunSummaryListPage1.items,
      ...mockRunSummaryListPage2.items,
    ]);
  });
});

describe("useAllMoleculeSummaries", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = createTestQueryClient();
  });

  it("walks paginated molecule-summary responses in 50-row pages", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(mockMoleculeSummaryListPage1)
      .mockResolvedValueOnce(mockMoleculeSummaryListPage2);

    const { result } = renderHook(() => useAllMoleculeSummaries(fetcher), {
      wrapper: createWrapper(queryClient),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(fetcher).toHaveBeenNthCalledWith(1, { limit: 50, offset: 0 });
    expect(fetcher).toHaveBeenNthCalledWith(2, { limit: 50, offset: 1 });
    expect(result.current.data).toEqual([
      ...mockMoleculeSummaryListPage1.items,
      ...mockMoleculeSummaryListPage2.items,
    ]);
  });
});

describe("useListBenchmarkRuns", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = createTestQueryClient();
  });

  it("refetches saved benchmarks when the history page remounts", async () => {
    const fetcher = vi.fn().mockResolvedValue(mockBenchmarkRunListResponse);
    const wrapper = createWrapper(queryClient);

    const firstRender = renderHook(() => useListBenchmarkRuns(fetcher, { limit: 50, offset: 0 }), {
      wrapper,
    });

    await waitFor(() => {
      expect(firstRender.result.current.data).toEqual(mockBenchmarkRunListResponse);
    });
    expect(fetcher).toHaveBeenCalledTimes(1);

    firstRender.unmount();

    renderHook(() => useListBenchmarkRuns(fetcher, { limit: 50, offset: 0 }), {
      wrapper,
    });

    await waitFor(() => {
      expect(fetcher).toHaveBeenCalledTimes(2);
    });
  });
});

describe("useGetRun", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = createTestQueryClient();
  });

  it("should not fetch when runId is not provided", () => {
    const fetcher = vi.fn();

    renderHook(() => useGetRun(fetcher, null), {
      wrapper: createWrapper(queryClient),
    });

    expect(fetcher).not.toHaveBeenCalled();
  });

  it("should fetch run when runId is provided", async () => {
    const fetcher = vi.fn().mockResolvedValue(mockRunResponse);

    const { result } = renderHook(() => useGetRun(fetcher, "run-1"), {
      wrapper: createWrapper(queryClient),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toEqual(mockRunResponse);
    expect(fetcher).toHaveBeenCalledWith("run-1");
  });
});

describe("Cache Invalidation", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = createTestQueryClient();
  });

  it("invalidateRunsList triggers refetch", async () => {
    const fetcher = vi.fn().mockResolvedValue(mockRunListResponse);

    const { result } = renderHook(() => useListRuns(fetcher), {
      wrapper: createWrapper(queryClient),
    });

    await waitFor(() => {
      expect(result.current.data).toBeDefined();
    });

    const { result: invalidateResult } = renderHook(() => useInvalidateRunsList(), {
      wrapper: createWrapper(queryClient),
    });

    await invalidateResult.current();

    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("invalidateMoleculesList triggers refetch", async () => {
    const fetcher = vi.fn().mockResolvedValue(mockMoleculeListResponse);
    const params = { limit: 100 };

    const { result } = renderHook(() => useFetchMolecules(fetcher, params), {
      wrapper: createWrapper(queryClient),
    });

    await waitFor(() => {
      expect(result.current.data).toBeDefined();
    });

    const { result: invalidateResult } = renderHook(() => useInvalidateMoleculesList(), {
      wrapper: createWrapper(queryClient),
    });

    await invalidateResult.current();

    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("invalidateRun triggers refetch for specific run", async () => {
    const fetcher = vi.fn().mockResolvedValue(mockRunResponse);

    const { result } = renderHook(() => useGetRun(fetcher, "run-1"), {
      wrapper: createWrapper(queryClient),
    });

    await waitFor(() => {
      expect(result.current.data).toBeDefined();
    });

    const { result: invalidateResult } = renderHook(() => useInvalidateRun(), {
      wrapper: createWrapper(queryClient),
    });

    await invalidateResult.current("run-1");

    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("clearAllQueries clears entire cache", async () => {
    const runsFetcher = vi.fn().mockResolvedValue(mockRunListResponse);
    const moleculesFetcher = vi.fn().mockResolvedValue(mockMoleculeListResponse);

    const { result: runsResult } = renderHook(() => useListRuns(runsFetcher), {
      wrapper: createWrapper(queryClient),
    });

    const { result: moleculesResult } = renderHook(
      () => useFetchMolecules(moleculesFetcher, { limit: 100 }),
      {
        wrapper: createWrapper(queryClient),
      },
    );

    await waitFor(() => {
      expect(runsResult.current.data).toBeDefined();
      expect(moleculesResult.current.data).toBeDefined();
    });

    const { result: clearResult } = renderHook(() => useClearAllQueries(), {
      wrapper: createWrapper(queryClient),
    });

    clearResult.current();

    expect(queryClient.getQueryState(["runs", "list", undefined])).toBeUndefined();
    expect(queryClient.getQueryState(["molecules", "list", { limit: 100 }])).toBeUndefined();
  });
});
