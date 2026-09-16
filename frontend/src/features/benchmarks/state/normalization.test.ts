import { beforeEach, describe, expect, it } from "vitest";
import { BENCHMARK_MOLECULE_PRESETS } from "@/lib/benchmark-presets";
import type { RunRestartResponse, UUID } from "@/types/run";
import { buildInitialEntries } from "@/pages/benchmark/benchmark-utils";
import {
  buildBenchmarkWorkspaceSnapshotFromSavedRun,
  benchmarkEntriesChanged,
  clearBenchmarkWorkspaceViewCache,
  entrySaveSignature,
  getBenchmarkSubmissionConcurrency,
  getRestartTargetRunId,
  readBenchmarkWorkspaceViewCache,
  writeBenchmarkWorkspaceViewCache,
} from "./normalization";
import { createSimpleBenchmarkVariant } from "@/pages/benchmark/benchmark-variants";
import type { SavedBenchmarkRun } from "@/pages/benchmark/benchmark-storage";

const preset = BENCHMARK_MOLECULE_PRESETS[0];
if (!preset) {
  throw new Error("Expected a benchmark preset");
}
const variant = createSimpleBenchmarkVariant("vqe");

function savedBenchmarkRun(): SavedBenchmarkRun {
  const selectedPreset = preset;
  if (!selectedPreset) {
    throw new Error("Expected a benchmark preset");
  }
  return {
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
    entries: buildInitialEntries([selectedPreset], [variant]),
  };
}

describe("benchmark state normalization", () => {
  beforeEach(() => {
    clearBenchmarkWorkspaceViewCache();
  });

  it("recovers selected molecules and algorithms from saved entries", () => {
    const snapshot = buildBenchmarkWorkspaceSnapshotFromSavedRun(savedBenchmarkRun());

    expect(snapshot.selectedMoleculeKeys).toEqual([preset.key]);
    expect(snapshot.selectedAlgorithms).toEqual(["vqe"]);
    expect(snapshot.algorithmVariants).toHaveLength(1);
    expect(snapshot.entries).toHaveLength(1);
  });

  it("uses explicit submission concurrency for each backend mode", () => {
    expect(getBenchmarkSubmissionConcurrency("statevector")).toBe(3);
    expect(getBenchmarkSubmissionConcurrency("aer_simulator")).toBe(2);
    expect(getBenchmarkSubmissionConcurrency("aer_simulator_backend_noise")).toBe(2);
    expect(getBenchmarkSubmissionConcurrency("ibm_runtime")).toBe(1);
  });

  it.each([
    [{ id: "base", status: "QUEUED" }, "base"],
    [{ id: "source", status: "PAUSED", child_run_id: "child" }, "child"],
    [{ id: "source", status: "PAUSED", new_run_id: "new" }, "new"],
    [{ id: "source", status: "PAUSED", target_run_id: "target" }, "target"],
    [{ id: "source", status: "PAUSED" }, "source"],
  ] satisfies Array<[RunRestartResponse, UUID]>)(
    "resolves the restart target from the compatible response fields",
    (response, expected) => {
      expect(getRestartTargetRunId(response, "fallback")).toBe(expected);
    },
  );

  it("returns cloned cached snapshots so callers cannot mutate shared state", () => {
    const snapshot = buildBenchmarkWorkspaceSnapshotFromSavedRun(savedBenchmarkRun());
    writeBenchmarkWorkspaceViewCache("benchmark-1", snapshot);

    const firstRead = readBenchmarkWorkspaceViewCache("benchmark-1");
    if (!firstRead) throw new Error("Expected cached benchmark snapshot");
    firstRead.selectedMoleculeKeys.push("mutated");

    expect(readBenchmarkWorkspaceViewCache("benchmark-1")?.selectedMoleculeKeys).toEqual([
      preset.key,
    ]);
  });

  it("persists execution metadata changes in the saved-entry signature", () => {
    const entry = savedBenchmarkRun().entries[0];
    if (!entry) throw new Error("Expected a benchmark entry");

    const updatedEntry = {
      ...entry,
      executionMetadata: {
        shots: 1024,
        actualExecutionTarget: "local_classical",
      },
    };

    expect(entrySaveSignature(updatedEntry)).not.toBe(entrySaveSignature(entry));
    expect(benchmarkEntriesChanged([entry], [updatedEntry])).toBe(true);
  });
});
