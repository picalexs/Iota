import { describe, expect, it, vi } from "vitest";
import { BENCHMARK_MOLECULE_PRESETS } from "@/lib/benchmark-presets";
import { buildInitialEntries, type BenchmarkSubmitResult } from "@/pages/benchmark/benchmark-utils";
import { createSimpleBenchmarkVariant } from "@/pages/benchmark/benchmark-variants";
import { applySubmitResults, beginBenchmarkExecution, mapWithConcurrencyLimit } from "./execution";

describe("benchmark execution helpers", () => {
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
});
