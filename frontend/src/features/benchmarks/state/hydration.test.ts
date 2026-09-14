import { beforeEach, describe, expect, it, vi } from "vitest";
import { BENCHMARK_MOLECULE_PRESETS } from "@/lib/benchmark-presets";
import type { BenchmarkEntry } from "@/pages/benchmark/benchmark-utils";
import { buildInitialEntries } from "@/pages/benchmark/benchmark-utils";
import { createSimpleBenchmarkVariant } from "@/pages/benchmark/benchmark-variants";
import type { SavedBenchmarkRun } from "@/pages/benchmark/benchmark-storage";
import { hydrateSavedBenchmarkState, resetBenchmarkWorkspaceState } from "./hydration";

const benchmarkPreset = BENCHMARK_MOLECULE_PRESETS[0];
if (!benchmarkPreset) {
  throw new Error("Expected a benchmark preset");
}

const savedRun: SavedBenchmarkRun = {
  id: "benchmark-1",
  name: "H2 benchmark",
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:00:00Z",
  selectedMoleculeKeys: [],
  selectedAlgorithms: [],
  selectedBasis: "sto-3g",
  selectedBackendMode: "statevector",
  selectedBackendName: null,
  chemicalAccuracyHa: 0.0016,
  customMolecules: [],
  entries: buildInitialEntries([benchmarkPreset], [createSimpleBenchmarkVariant("vqe")]),
};

function makeSetter() {
  return vi.fn();
}

describe("benchmark state hydration", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("restores the saved workspace and starts polling when a row is active", () => {
    const savedEntry = savedRun.entries[0];
    if (!savedEntry) throw new Error("Expected a saved benchmark entry");
    const activeEntry: BenchmarkEntry = {
      ...savedEntry,
      status: "running",
      runId: "run-1",
      moleculeId: "molecule-1",
    };
    const activeRun = { ...savedRun, entries: [activeEntry] };
    const setEntries = makeSetter();
    const startPolling = vi.fn();
    const setSelectedSavedBenchmarkId = makeSetter();
    const setSelectedMoleculeKeys = makeSetter();
    const setBenchmarkMode = makeSetter();
    const setSelectedAlgorithms = makeSetter();
    const setAlgorithmVariants = makeSetter();
    const setSelectedBasis = makeSetter();
    const setSelectedBackendMode = makeSetter();
    const setSelectedBackendName = makeSetter();
    const setChemicalAccuracyHa = makeSetter();
    const setCustomMolecules = makeSetter();
    const setActiveSavedBenchmarkId = makeSetter();
    const setRunning = makeSetter();

    hydrateSavedBenchmarkState({
      savedRun: activeRun,
      startPolling,
      setSelectedSavedBenchmarkId,
      setSelectedMoleculeKeys,
      setBenchmarkMode,
      setSelectedAlgorithms,
      setAlgorithmVariants,
      setSelectedBasis,
      setSelectedBackendMode,
      setSelectedBackendName,
      setChemicalAccuracyHa,
      setCustomMolecules,
      setEntries,
      setActiveSavedBenchmarkId,
      setRunning,
    });

    expect(setSelectedSavedBenchmarkId).toHaveBeenCalledWith("benchmark-1");
    expect(setSelectedMoleculeKeys).toHaveBeenCalledWith([benchmarkPreset.key]);
    expect(setSelectedAlgorithms).toHaveBeenCalledWith(["vqe"]);
    expect(setEntries).toHaveBeenCalledWith([expect.objectContaining({ runId: "run-1" })]);
    expect(setActiveSavedBenchmarkId).toHaveBeenCalledWith("benchmark-1");
    expect(setRunning).toHaveBeenCalledWith(true);
    expect(startPolling).toHaveBeenCalledWith([expect.objectContaining({ runId: "run-1" })]);
  });

  it("resets all workspace state and stops polling", () => {
    const stopPolling = vi.fn();
    const setSelectedSavedBenchmarkId = makeSetter();
    const setActiveSavedBenchmarkId = makeSetter();
    const setHydratedBenchmarkId = makeSetter();
    const setRunning = makeSetter();
    const setEntries = makeSetter();
    const setSelectedMoleculeKeys = makeSetter();
    const setBenchmarkMode = makeSetter();
    const setSelectedAlgorithms = makeSetter();
    const setAlgorithmVariants = makeSetter();
    const setSelectedBasis = makeSetter();
    const setSelectedBackendMode = makeSetter();
    const setSelectedBackendName = makeSetter();
    const setChemicalAccuracyHa = makeSetter();
    const setCustomMolecules = makeSetter();

    resetBenchmarkWorkspaceState({
      stopPolling,
      setSelectedSavedBenchmarkId,
      setActiveSavedBenchmarkId,
      setHydratedBenchmarkId,
      setRunning,
      setEntries,
      setSelectedMoleculeKeys,
      setBenchmarkMode,
      setSelectedAlgorithms,
      setAlgorithmVariants,
      setSelectedBasis,
      setSelectedBackendMode,
      setSelectedBackendName,
      setChemicalAccuracyHa,
      setCustomMolecules,
    });

    expect(stopPolling).toHaveBeenCalledOnce();
    expect(setSelectedSavedBenchmarkId).toHaveBeenCalledWith(null);
    expect(setActiveSavedBenchmarkId).toHaveBeenCalledWith(null);
    expect(setHydratedBenchmarkId).toHaveBeenCalledWith(null);
    expect(setRunning).toHaveBeenCalledWith(false);
    expect(setEntries).toHaveBeenCalledWith([]);
    expect(setSelectedMoleculeKeys).toHaveBeenCalledWith([]);
    expect(setBenchmarkMode).toHaveBeenCalledWith("simple");
    expect(setSelectedBackendMode).toHaveBeenCalledWith("statevector");
    expect(setSelectedBackendName).toHaveBeenCalledWith(null);
    expect(setCustomMolecules).toHaveBeenCalledWith([]);
  });
});
