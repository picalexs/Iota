/** Pure benchmark entry predicates and presentation selectors. */

import { TERMINAL } from "@/pages/benchmark/benchmark-utils";
import type {
  BenchmarkBackendMode,
  BenchmarkEntry,
  BenchmarkEntryWithRunId,
} from "@/pages/benchmark/benchmark-utils";
import type { BenchmarkAlgorithmVariant } from "@/pages/benchmark/benchmark-variants";

export type BenchmarkPreset = BenchmarkEntry["preset"];
export type PausableBenchmarkEntry = BenchmarkEntryWithRunId & {
  status: "queued" | "running";
};
export type ResumableBenchmarkEntry = BenchmarkEntryWithRunId & {
  status: "paused" | "failed";
};
export type RestartableBenchmarkEntry = BenchmarkEntryWithRunId & {
  status: "paused" | "failed" | "completed" | "cancelled";
};
export type RetryableBenchmarkEntry = BenchmarkEntry & { status: "failed" };

export function describeBenchmarkBackendMode(
  mode: BenchmarkBackendMode,
  backendName: string | null,
  totalJobs: number,
): string {
  if (mode === "ibm_runtime") {
    const target = backendName ?? "the selected IBM backend";
    return `${totalJobs} benchmark job${totalJobs === 1 ? "" : "s"} will be submitted to ${target}. This can consume IBM Quantum quota and queue time.`;
  }

  if (mode === "aer_simulator_backend_noise") {
    const target = backendName ?? "the selected IBM backend";
    return `Aer will stay local and derive noise from ${target}.`;
  }

  return "Benchmark jobs will run locally.";
}

export function hasPendingEntrySubmission(entries: readonly BenchmarkEntry[]): boolean {
  return entries.some(
    (entry) => entry.status === "acquiring_molecule" || entry.status === "submitting",
  );
}

export function hasRunId(entry: BenchmarkEntry): entry is BenchmarkEntryWithRunId {
  return entry.runId !== null;
}

export function insertAdvancedVariantAfterAlgorithmTail(
  variants: readonly BenchmarkAlgorithmVariant[],
  nextVariant: BenchmarkAlgorithmVariant,
): BenchmarkAlgorithmVariant[] {
  let insertIndex = -1;
  for (let index = variants.length - 1; index >= 0; index -= 1) {
    if (variants[index]?.algorithm === nextVariant.algorithm) {
      insertIndex = index;
      break;
    }
  }

  if (insertIndex === -1) {
    return [...variants, nextVariant];
  }

  return [...variants.slice(0, insertIndex + 1), nextVariant, ...variants.slice(insertIndex + 1)];
}

export function isPausableBenchmarkEntry(entry: BenchmarkEntry): entry is PausableBenchmarkEntry {
  return hasRunId(entry) && (entry.status === "queued" || entry.status === "running");
}

export function isResumableBenchmarkEntry(entry: BenchmarkEntry): entry is ResumableBenchmarkEntry {
  return hasRunId(entry) && (entry.status === "paused" || entry.status === "failed");
}

export function isPausedBenchmarkEntry(entry: BenchmarkEntry): entry is BenchmarkEntryWithRunId {
  return hasRunId(entry) && entry.status === "paused";
}

export function isRestartableBenchmarkEntry(
  entry: BenchmarkEntry,
): entry is RestartableBenchmarkEntry {
  return (
    hasRunId(entry) &&
    (entry.status === "paused" ||
      entry.status === "failed" ||
      entry.status === "completed" ||
      entry.status === "cancelled")
  );
}

export function isRetryableBenchmarkEntry(entry: BenchmarkEntry): entry is RetryableBenchmarkEntry {
  return entry.status === "failed";
}

export function isCancellableBenchmarkEntry(
  entry: BenchmarkEntry,
): entry is BenchmarkEntryWithRunId {
  return hasRunId(entry) && !TERMINAL.has(entry.status);
}

export function buildGroupedBenchmarkEntries(
  allPresets: readonly BenchmarkPreset[],
  selectedMolecules: ReadonlySet<string>,
  entries: readonly BenchmarkEntry[],
) {
  const groupedPresets = allPresets.filter((preset) => selectedMolecules.has(preset.key));
  const knownPresetKeys = new Set(groupedPresets.map((preset) => preset.key));

  for (const entry of entries) {
    if (!selectedMolecules.has(entry.preset.key) || knownPresetKeys.has(entry.preset.key)) {
      continue;
    }
    groupedPresets.push(entry.preset);
    knownPresetKeys.add(entry.preset.key);
  }

  return groupedPresets.map((preset) => ({
    preset,
    rows: entries.filter((entry) => entry.preset.key === preset.key),
  }));
}

export { TERMINAL };
