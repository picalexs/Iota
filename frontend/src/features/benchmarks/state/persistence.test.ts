import { describe, expect, it } from "vitest";

import type { SavedBenchmarkRun } from "@/pages/benchmark/benchmark-storage";
import type { BenchmarkEntry } from "@/pages/benchmark/benchmark-utils";
import {
  buildOptimisticSavedBenchmarkRun,
  mergeSavedBenchmarkRunIntoListCache,
  type BenchmarkRunListCache,
} from "./persistence";

function savedRun(id: string, updatedAt: string): SavedBenchmarkRun {
  return {
    id,
    name: `${id} benchmark`,
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt,
    selectedMoleculeKeys: [],
    selectedAlgorithms: [],
    selectedBasis: "sto-3g",
    selectedBackendMode: "statevector",
    selectedBackendName: null,
    chemicalAccuracyHa: 0.0016,
    customMolecules: [],
    entries: [],
  };
}

describe("benchmark persistence helpers", () => {
  it("builds an optimistic entry snapshot without changing saved metadata", () => {
    const existing = savedRun("benchmark-1", "2026-01-01T00:00:00Z");
    const entries = [] as BenchmarkEntry[];

    const next = buildOptimisticSavedBenchmarkRun(existing, entries, "2026-01-02T00:00:00Z");

    expect(next).toEqual({
      ...existing,
      updatedAt: "2026-01-02T00:00:00Z",
      entries,
    });
    expect(existing.updatedAt).toBe("2026-01-01T00:00:00Z");
  });

  it("keeps an absent benchmark list cache absent", () => {
    const run = savedRun("benchmark-1", "2026-01-02T00:00:00Z");

    expect(mergeSavedBenchmarkRunIntoListCache(undefined, run)).toBeUndefined();
  });

  it("updates an existing list item without changing the total", () => {
    const current: BenchmarkRunListCache = {
      items: [savedRun("benchmark-1", "2026-01-01T00:00:00Z")],
      total: 1,
      limit: 25,
      offset: 0,
    };
    const updated = savedRun("benchmark-1", "2026-01-02T00:00:00Z");

    const next = mergeSavedBenchmarkRunIntoListCache(current, updated);

    expect(next?.items).toEqual([updated]);
    expect(next?.total).toBe(1);
    expect(current.items[0]?.updatedAt).toBe("2026-01-01T00:00:00Z");
  });

  it("adds a new list item and increments the total", () => {
    const current: BenchmarkRunListCache = {
      items: [savedRun("benchmark-1", "2026-01-01T00:00:00Z")],
      total: 1,
      limit: 25,
      offset: 0,
    };
    const added = savedRun("benchmark-2", "2026-01-02T00:00:00Z");

    const next = mergeSavedBenchmarkRunIntoListCache(current, added);

    expect(next?.items[0]?.id).toBe("benchmark-2");
    expect(next?.total).toBe(2);
    expect(next?.limit).toBe(25);
    expect(next?.offset).toBe(0);
  });
});
