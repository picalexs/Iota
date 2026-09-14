import { describe, expect, it } from "vitest";

import type { BenchmarkEntry, SavedBenchmarkRun } from "@/types/benchmark";
import * as featureHistory from "./history";
import * as featureHistoryActions from "./history-actions";
import * as legacyHistory from "@/pages/benchmark/benchmark-history-utils";
import * as legacyHistoryActions from "@/pages/benchmark/benchmark-history-actions";
import {
  deriveBenchmarkHistorySelection,
  filterAndSortSavedBenchmarkRuns,
  type BenchmarkHistorySelection,
} from "./history";

function entry(id: string, status: BenchmarkEntry["status"], runId: string): BenchmarkEntry {
  return {
    id,
    preset: {} as BenchmarkEntry["preset"],
    algorithm: "vqe",
    status,
    moleculeId: null,
    runId,
    energy: null,
    currentEnergy: null,
    converged: null,
    errorMessage: null,
    classicalRefs: null,
    elapsedSeconds: null,
    latestEventSequence: 0,
  };
}

function savedRun(id: string, entries: BenchmarkEntry[]): SavedBenchmarkRun {
  return {
    id,
    name: id,
    createdAt: "2026-06-04T12:00:00.000Z",
    updatedAt: "2026-06-04T12:05:00.000Z",
    selectedMoleculeKeys: [],
    selectedAlgorithms: ["vqe"],
    selectedBasis: "sto-3g",
    selectedBackendMode: "statevector",
    selectedBackendName: null,
    chemicalAccuracyHa: 1.6e-3,
    customMolecules: [],
    entries,
  };
}

function ids(selection: BenchmarkHistorySelection, field: keyof BenchmarkHistorySelection) {
  const runs = selection[field];
  if (!Array.isArray(runs)) {
    throw new Error(`Expected run list for ${field}`);
  }
  return runs.map((run) => run.id);
}

describe("deriveBenchmarkHistorySelection", () => {
  it("keeps the legacy module as an identity-preserving compatibility facade", () => {
    expect(legacyHistory.deriveBenchmarkHistorySelection).toBe(
      featureHistory.deriveBenchmarkHistorySelection,
    );
    expect(legacyHistory.filterAndSortSavedBenchmarkRuns).toBe(
      featureHistory.filterAndSortSavedBenchmarkRuns,
    );
    expect(legacyHistoryActions.buildBenchmarkActionSummary).toBe(
      featureHistoryActions.buildBenchmarkActionSummary,
    );
    expect(legacyHistoryActions.runSelectedBenchmarkActionBatch).toBe(
      featureHistoryActions.runSelectedBenchmarkActionBatch,
    );
  });

  it("derives eligible action groups and unique associated runs", () => {
    const runs = [
      savedRun("queued", [entry("queued-entry", "queued", "run-1")]),
      savedRun("paused", [entry("paused-entry", "paused", "run-2")]),
      savedRun("failed", [
        entry("failed-entry", "failed", "run-3"),
        entry("failed-entry-duplicate", "failed", "run-3"),
      ]),
      savedRun("running-unselected", [entry("running-entry", "running", "run-4")]),
    ];

    const selection = deriveBenchmarkHistorySelection(
      runs,
      new Set(["queued", "paused", "failed"]),
    );

    expect(ids(selection, "selectedRuns")).toEqual(["queued", "paused", "failed"]);
    expect(ids(selection, "pausableSelectedRuns")).toEqual(["queued"]);
    expect(ids(selection, "resumableSelectedRuns")).toEqual(["paused"]);
    expect(ids(selection, "restartableSelectedRuns")).toEqual(["paused"]);
    expect(ids(selection, "cancellableSelectedRuns")).toEqual(["queued", "paused"]);
    expect(selection.associatedRunCount).toBe(3);
  });

  it("returns empty action groups when no visible run is selected", () => {
    const selection = deriveBenchmarkHistorySelection(
      [savedRun("draft", [])],
      new Set(["missing"]),
    );

    expect(selection.selectedRuns).toEqual([]);
    expect(selection.associatedRunCount).toBe(0);
  });
});

describe("filterAndSortSavedBenchmarkRuns", () => {
  it("filters by status and sorts the remaining runs", () => {
    const runs = [
      savedRun("z-finished", [entry("completed-entry", "completed", "run-1")]),
      savedRun("a-draft", []),
      savedRun("a-finished", [entry("completed-entry-2", "completed", "run-2")]),
    ];

    expect(
      filterAndSortSavedBenchmarkRuns(runs, "finished", "all", "name", "asc").map((run) => run.id),
    ).toEqual(["a-finished", "z-finished"]);
  });
});
