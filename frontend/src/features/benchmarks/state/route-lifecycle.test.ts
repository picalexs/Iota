import { describe, expect, it } from "vitest";
import { BENCHMARK_MOLECULE_PRESETS } from "@/lib/benchmark-presets";
import type { MoleculeResponse } from "@/types/run";
import { buildInitialEntries, type BenchmarkEntry } from "@/pages/benchmark/benchmark-utils";
import { createSimpleBenchmarkVariant } from "@/pages/benchmark/benchmark-variants";
import {
  appendCustomMoleculeIfMissing,
  hasCachedSavedBenchmarkSelection,
  hasInitialPollableBenchmarkEntries,
  initialActiveSavedBenchmarkIdFor,
  toggleDistinctValue,
} from "./route-lifecycle";

function getBenchmarkPreset() {
  const [benchmarkPreset] = BENCHMARK_MOLECULE_PRESETS;
  if (!benchmarkPreset) {
    throw new Error("Expected a benchmark preset");
  }
  return benchmarkPreset;
}

const benchmarkPreset = getBenchmarkPreset();

function buildEntry(overrides: Partial<BenchmarkEntry> = {}): BenchmarkEntry {
  const entry = buildInitialEntries([benchmarkPreset], [createSimpleBenchmarkVariant("vqe")])[0];
  if (!entry) throw new Error("Expected a benchmark entry");
  return { ...entry, ...overrides };
}

describe("benchmark route lifecycle helpers", () => {
  it("detects pollable restored entries and initial active benchmark IDs", () => {
    const activeEntry = buildEntry({ status: "running", runId: "run-1" });

    expect(hasInitialPollableBenchmarkEntries({ entries: [activeEntry] }, [])).toBe(true);
    expect(hasInitialPollableBenchmarkEntries({ entries: [buildEntry()] }, [])).toBe(false);
    expect(initialActiveSavedBenchmarkIdFor("benchmark-1", true)).toBe("benchmark-1");
    expect(initialActiveSavedBenchmarkIdFor(null, true)).toBeNull();
  });

  it("recognizes a cached route selection only when workspace state exists", () => {
    const entry = buildEntry();

    expect(
      hasCachedSavedBenchmarkSelection({
        benchmarkId: "benchmark-1",
        selectedSavedBenchmarkId: "benchmark-1",
        entries: [entry],
        selectedMoleculeKeys: [],
      }),
    ).toBe(true);
    expect(
      hasCachedSavedBenchmarkSelection({
        benchmarkId: "benchmark-1",
        selectedSavedBenchmarkId: "other",
        entries: [entry],
        selectedMoleculeKeys: [],
      }),
    ).toBe(false);
  });

  it("keeps custom molecules distinct and preserves toggle order", () => {
    const molecule = { id: "molecule-1" } as MoleculeResponse;
    expect(appendCustomMoleculeIfMissing([], molecule)).toEqual([molecule]);
    expect(appendCustomMoleculeIfMissing([molecule], molecule)).toEqual([molecule]);
    expect(toggleDistinctValue(["h2", "lih"], "h2")).toEqual(["lih"]);
    expect(toggleDistinctValue(["h2"], "lih")).toEqual(["h2", "lih"]);
  });
});
