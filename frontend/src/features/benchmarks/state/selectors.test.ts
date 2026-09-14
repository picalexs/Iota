import { describe, expect, it } from "vitest";

import { BENCHMARK_MOLECULE_PRESETS } from "@/lib/benchmark-presets";
import type { UUID } from "@/types/run";
import {
  createAdvancedBenchmarkVariant,
  createSimpleBenchmarkVariant,
} from "@/pages/benchmark/benchmark-variants";
import { buildInitialEntries } from "@/pages/benchmark/benchmark-utils";
import {
  buildGroupedBenchmarkEntries,
  describeBenchmarkBackendMode,
  hasPendingEntrySubmission,
  insertAdvancedVariantAfterAlgorithmTail,
  isCancellableBenchmarkEntry,
  isPausableBenchmarkEntry,
  isRestartableBenchmarkEntry,
  isResumableBenchmarkEntry,
  isRetryableBenchmarkEntry,
} from "./selectors";

function getPreset(index: number) {
  const preset = BENCHMARK_MOLECULE_PRESETS[index];
  if (!preset) {
    throw new Error(`Expected benchmark molecule preset at index ${index}`);
  }
  return preset;
}

const firstPreset = getPreset(0);
const secondPreset = getPreset(1);

function entryWithStatus(
  status: Parameters<typeof hasPendingEntrySubmission>[0][number]["status"],
  runId: UUID | null = "run-1" as UUID,
) {
  const [initialEntry] = buildInitialEntries([firstPreset], [createSimpleBenchmarkVariant("vqe")]);
  if (!initialEntry) {
    throw new Error("Expected an initial benchmark entry");
  }

  return {
    ...initialEntry,
    status,
    runId,
  };
}

describe("benchmark entry selectors", () => {
  it("describes local and remote benchmark execution modes", () => {
    expect(describeBenchmarkBackendMode("statevector", null, 2)).toBe(
      "Benchmark jobs will run locally.",
    );
    expect(describeBenchmarkBackendMode("ibm_runtime", "ibm_brisbane", 1)).toContain(
      "1 benchmark job will be submitted to ibm_brisbane",
    );
    expect(describeBenchmarkBackendMode("aer_simulator_backend_noise", null, 2)).toContain(
      "derive noise",
    );
  });

  it("classifies action eligibility without accepting missing run IDs", () => {
    expect(isPausableBenchmarkEntry(entryWithStatus("queued"))).toBe(true);
    expect(isPausableBenchmarkEntry(entryWithStatus("queued", null))).toBe(false);
    expect(isResumableBenchmarkEntry(entryWithStatus("paused"))).toBe(true);
    expect(isRestartableBenchmarkEntry(entryWithStatus("completed"))).toBe(true);
    expect(isRetryableBenchmarkEntry(entryWithStatus("failed", null))).toBe(true);
    expect(isCancellableBenchmarkEntry(entryWithStatus("running"))).toBe(true);
    expect(isCancellableBenchmarkEntry(entryWithStatus("completed"))).toBe(false);
  });

  it("detects pending submissions and preserves variant grouping order", () => {
    expect(hasPendingEntrySubmission([entryWithStatus("submitting")])).toBe(true);
    const vqe = createAdvancedBenchmarkVariant("vqe", 0.0016);
    const sqd = createAdvancedBenchmarkVariant("sqd", 0.0016);
    const inserted = insertAdvancedVariantAfterAlgorithmTail(
      [vqe, sqd],
      createAdvancedBenchmarkVariant("vqe", 0.0016),
    );
    expect(inserted.map((variant) => variant.algorithm)).toEqual(["vqe", "vqe", "sqd"]);

    const secondEntry = {
      ...entryWithStatus("idle", null),
      preset: secondPreset,
    };
    const groups = buildGroupedBenchmarkEntries(
      [firstPreset],
      new Set([firstPreset.key, secondPreset.key]),
      [entryWithStatus("idle", null), secondEntry],
    );
    expect(groups.map((group) => group.preset.key)).toEqual([firstPreset.key, secondPreset.key]);
    expect(groups.map((group) => group.rows)).toHaveLength(2);
  });
});
