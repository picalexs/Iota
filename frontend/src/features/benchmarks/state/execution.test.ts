import type { QueryClient } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createBenchmarkRun, updateBenchmarkRun } from "@/api/benchmarks";
import { createRun } from "@/api/runs";
import { BENCHMARK_MOLECULE_PRESETS } from "@/lib/benchmark-presets";
import type { SavedBenchmarkRun } from "@/types/benchmark";
import type { RunResponse } from "@/types/run";
import { acquireMolecule } from "@/pages/benchmark/molecule-acquisition";
import { buildInitialEntries, type BenchmarkSubmitResult } from "@/pages/benchmark/benchmark-utils";
import { createSimpleBenchmarkVariant } from "@/pages/benchmark/benchmark-variants";
import {
  applySubmitResults,
  beginBenchmarkExecution,
  executeBenchmarkRun,
  mapWithConcurrencyLimit,
} from "./execution";

vi.mock("@/api/benchmarks", () => ({
  createBenchmarkRun: vi.fn(),
  deleteBenchmarkRun: vi.fn(),
  updateBenchmarkRun: vi.fn(),
}));

vi.mock("@/api/runs", () => ({
  createRun: vi.fn(),
}));

vi.mock("@/pages/benchmark/molecule-acquisition", () => ({
  acquireMolecule: vi.fn(),
  acquireMoleculeId: vi.fn(),
  MoleculeAcquisitionError: class MoleculeAcquisitionError extends Error {},
}));

describe("benchmark execution helpers", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("starts a new guarded generation and rebuilds benchmark entries", () => {
    const stopPolling = vi.fn();
    const setEntries = vi.fn();
    const runGenerationRef = { current: 4 };
    const preset = BENCHMARK_MOLECULE_PRESETS[0];

    if (!preset) throw new Error("Expected a benchmark preset");

    const result = beginBenchmarkExecution({
      stopPolling,
      runGenerationRef,
      benchmarkSaveTimerRef: { current: null },
      benchmarkConfigSaveTimerRef: { current: null },
      selectedPresets: [preset],
      activeVariants: [createSimpleBenchmarkVariant("vqe")],
      setEntries,
    });

    expect(stopPolling).toHaveBeenCalledOnce();
    expect(runGenerationRef.current).toBe(5);
    expect(result.initialEntries).toHaveLength(1);
    expect(setEntries).toHaveBeenCalledWith(result.initialEntries);
  });

  it("limits concurrent work while preserving mapper result order", async () => {
    let inFlight = 0;
    let maxInFlight = 0;

    const results = await mapWithConcurrencyLimit([1, 2, 3, 4], 2, async (value) => {
      inFlight += 1;
      maxInFlight = Math.max(maxInFlight, inFlight);
      await new Promise((resolve) => setTimeout(resolve, value === 1 ? 5 : 0));
      inFlight -= 1;
      return value * 2;
    });

    expect(maxInFlight).toBe(2);
    expect(results).toEqual([
      { status: "fulfilled", value: 2 },
      { status: "fulfilled", value: 4 },
      { status: "fulfilled", value: 6 },
      { status: "fulfilled", value: 8 },
    ]);
  });

  it("captures rejected mapper results without shifting later results", async () => {
    const results = await mapWithConcurrencyLimit(["first", "bad", "last"], 2, async (value) => {
      if (value === "bad") {
        throw new Error("submission failed");
      }
      return value.toUpperCase();
    });

    expect(results[0]).toEqual({ status: "fulfilled", value: "FIRST" });
    expect(results[1]).toMatchObject({ status: "rejected" });
    expect(results[2]).toEqual({ status: "fulfilled", value: "LAST" });
  });

  it("applies fulfilled submissions and preserves untouched or rejected entries", () => {
    const preset = BENCHMARK_MOLECULE_PRESETS[0];
    if (!preset) throw new Error("Expected a benchmark preset");
    const entries = buildInitialEntries(
      [preset],
      [createSimpleBenchmarkVariant("vqe"), createSimpleBenchmarkVariant("sqd")],
    );
    const firstEntry = entries[0];
    if (!firstEntry) throw new Error("Expected an initial benchmark entry");

    const result = {
      id: firstEntry.id,
      status: "queued",
      moleculeId: "molecule-1",
      runId: "run-1",
      errorMessage: null,
    } satisfies BenchmarkSubmitResult;

    const updated = applySubmitResults(entries, [
      { status: "fulfilled", value: result },
      { status: "rejected", reason: new Error("ignored here") },
    ]);

    expect(updated[0]).toMatchObject({
      id: firstEntry.id,
      status: "queued",
      moleculeId: "molecule-1",
      runId: "run-1",
    });
    expect(updated[1]).toBe(entries[1]);
  });

  it("passes the selected execution settings into every submitted run", async () => {
    const preset = BENCHMARK_MOLECULE_PRESETS[0];
    if (!preset) throw new Error("Expected a benchmark preset");

    const snapshot = {
      id: "benchmark-id",
      name: "Benchmark",
      createdAt: "2026-01-01T00:00:00Z",
      updatedAt: "2026-01-01T00:00:00Z",
      selectedMoleculeKeys: [preset.key],
      selectedAlgorithms: ["vqe"],
      selectedBasis: "sto-3g",
      selectedBackendMode: "aer_simulator",
      selectedBackendName: null,
      shots: 1000,
      optimizationLevel: 3,
      seedTranspiler: 17,
      dynamicalDecoupling: false,
      twirling: false,
      chemicalAccuracyHa: 0.0016,
      customMolecules: [],
      entries: [],
    } satisfies SavedBenchmarkRun;

    vi.mocked(acquireMolecule).mockResolvedValue({
      kind: "existing",
      moleculeId: "molecule-id",
      cacheState: "hit",
      attempts: [],
    });
    vi.mocked(createBenchmarkRun).mockResolvedValue(snapshot);
    vi.mocked(updateBenchmarkRun).mockResolvedValue(snapshot);
    vi.mocked(createRun).mockResolvedValue({
      id: "run-id",
      status: "QUEUED",
    } as RunResponse);

    const noOpSetter = () => {};
    const queryClient = {
      invalidateQueries: vi.fn().mockResolvedValue(undefined),
    } as unknown as QueryClient;

    await executeBenchmarkRun({
      options: {},
      benchmarkId: null,
      selectedSavedBenchmarkId: null,
      selectedPresets: [preset],
      activeVariants: [createSimpleBenchmarkVariant("vqe")],
      selectedBasis: "sto-3g",
      execution: {
        mode: "aer_simulator",
        backendName: null,
        shots: 1000,
        optimizationLevel: 3,
        seedTranspiler: 17,
      },
      stopPolling: vi.fn(),
      startPolling: vi.fn(),
      runGenerationRef: { current: 0 },
      benchmarkSaveTimerRef: { current: null },
      benchmarkConfigSaveTimerRef: { current: null },
      benchmarkConfigSignatureRef: { current: null },
      buildBenchmarkPayload: (entries) => ({ ...snapshot, entries }),
      buildBenchmarkSignature: () => "signature",
      setEntries: noOpSetter,
      setRunning: noOpSetter,
      setSavedBenchmarkRuns: noOpSetter,
      setSelectedSavedBenchmarkId: noOpSetter,
      setActiveSavedBenchmarkId: noOpSetter,
      setHydratedBenchmarkId: noOpSetter,
      queryClient,
    });

    expect(createRun).toHaveBeenCalledWith(
      expect.objectContaining({
        backend_target: "aer_simulator",
        backend_options: expect.objectContaining({
          shots: 1000,
          optimization_level: 3,
          seed_transpiler: 17,
        }),
      }),
    );
  });
});
