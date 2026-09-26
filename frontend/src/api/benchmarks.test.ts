import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createBenchmarkRun,
  listBenchmarkRuns,
  listBenchmarkRunSummaries,
  parseBenchmarkRunListResponse,
  parseBenchmarkRunSummaryListResponse,
  parseBenchmarkRunResponse,
  type BenchmarkRunCreate,
} from "./benchmarks";

function mockResponse(body: unknown, status = 200): Response {
  return {
    ok: status < 400,
    status,
    json: vi.fn().mockResolvedValue(body),
  } as unknown as Response;
}

const benchmarkResponse = {
  id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  name: "H2 benchmark",
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:10:00Z",
  selectedBackendMode: "statevector",
  selectedBasis: "sto-3g",
  chemicalAccuracyHa: 0.0016,
};

describe("benchmark API transport adapters", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("normalizes omitted collection and backend fields in saved runs", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      mockResponse({
        items: [benchmarkResponse],
        total: 1,
        limit: 20,
        offset: 0,
      }),
    );

    const result = await listBenchmarkRuns();

    expect(result.items[0]).toMatchObject({
      ...benchmarkResponse,
      selectedMoleculeKeys: [],
      selectedAlgorithms: [],
      selectedBackendName: null,
      customMolecules: [],
      entries: [],
    });
  });

  it("sends only the generated benchmark request fields", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(mockResponse(benchmarkResponse));

    const input: BenchmarkRunCreate = {
      id: "client-only-id",
      createdAt: "client-only-created-at",
      updatedAt: "client-only-updated-at",
      name: "H2 benchmark",
      selectedMoleculeKeys: ["h2"],
      selectedAlgorithms: ["vqe"],
      selectedBasis: "sto-3g",
      selectedBackendMode: "statevector",
      selectedBackendName: null,
      shots: 4096,
      optimizationLevel: 1,
      seedTranspiler: null,
      dynamicalDecoupling: false,
      twirling: false,
      chemicalAccuracyHa: 0.0016,
      customMolecules: [],
      entries: [],
    };

    await createBenchmarkRun(input);

    const [, options] = vi.mocked(fetch).mock.calls[0] ?? [];
    expect(JSON.parse(String(options?.body))).toEqual({
      name: "H2 benchmark",
      selectedMoleculeKeys: ["h2"],
      selectedAlgorithms: ["vqe"],
      selectedBasis: "sto-3g",
      selectedBackendMode: "statevector",
      selectedBackendName: null,
      shots: 4096,
      optimizationLevel: 1,
      seedTranspiler: null,
      dynamicalDecoupling: false,
      twirling: false,
      chemicalAccuracyHa: 0.0016,
      customMolecules: [],
      entries: [],
    });
  });

  it("rejects malformed benchmark response envelopes before adaptation", () => {
    expect(() =>
      parseBenchmarkRunResponse({ ...benchmarkResponse, chemicalAccuracyHa: 0 }),
    ).toThrow("Invalid benchmark run response");
    expect(() =>
      parseBenchmarkRunListResponse({
        items: [{ ...benchmarkResponse, selectedAlgorithms: ["not-an-algorithm"] }],
        total: 1,
        limit: 50,
        offset: 0,
      }),
    ).toThrow("Invalid benchmark run list response");
    expect(() =>
      parseBenchmarkRunSummaryListResponse({
        items: [{ ...benchmarkResponse, status: "unknown" }],
        total: 1,
        limit: 50,
        offset: 0,
      }),
    ).toThrow("Invalid benchmark run summary list response");
  });

  it("requests compact benchmark summaries with server-side list controls", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      mockResponse({
        items: [
          {
            ...benchmarkResponse,
            selectedMoleculeKeys: ["h2"],
            selectedBackendName: null,
            status: "running",
            rowCount: 2,
            completedCount: 1,
            activeCount: 1,
            pausedCount: 0,
            failedCount: 0,
            cancelledCount: 0,
            plannedCount: 0,
            excludedCount: 0,
            associatedRunCount: 2,
          },
        ],
        total: 1,
        limit: 50,
        offset: 50,
      }),
    );

    const result = await listBenchmarkRunSummaries({
      limit: 50,
      offset: 50,
      status: "running",
      backend: "statevector",
      sort: "updated",
      order: "desc",
    });

    expect(result.items[0]).toMatchObject({
      status: "running",
      rowCount: 2,
      activeCount: 1,
    });
    expect(vi.mocked(fetch)).toHaveBeenCalledWith(
      expect.stringContaining(
        "/api/benchmarks/summaries?limit=50&offset=50&status=running&backend=statevector&sort=updated&order=desc",
      ),
      expect.objectContaining({ method: "GET" }),
    );
  });
});
