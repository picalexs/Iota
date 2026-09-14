import type { MoleculePreset } from "@/lib/benchmark-presets";
import type { RunAlgorithm } from "@/types/run";
import {
  getBenchmarkMoleculeBlocker,
  type BenchmarkBackendMode,
} from "@/pages/benchmark/benchmark-utils";
import type {
  BenchmarkAlgorithmVariant,
  BenchmarkVariantMode,
} from "@/pages/benchmark/benchmark-variants";

export function getSelectedBlockedReasons(
  moleculeOptions: readonly MoleculePreset[],
  selectedMolecules: ReadonlySet<string>,
): string[] {
  return moleculeOptions
    .filter((preset) => selectedMolecules.has(preset.key))
    .map((preset) => getBenchmarkMoleculeBlocker(preset))
    .filter((reason): reason is string => reason !== null);
}

export function getBackendNameLabel(selectedBackendMode: BenchmarkBackendMode): string {
  return selectedBackendMode === "aer_simulator_backend_noise"
    ? "Noise reference backend"
    : "IBM backend";
}

export function getBenchmarkCompletionRatio(total: number, done: number): number {
  return total > 0 ? (done / total) * 100 : 0;
}

export function isBenchmarkWorkspaceLocked({
  total,
  running,
  hasPausedBenchmark,
  actionInProgress,
}: {
  total: number;
  running: boolean;
  hasPausedBenchmark: boolean;
  actionInProgress: boolean;
}): boolean {
  return total > 0 || running || hasPausedBenchmark || actionInProgress;
}

export function isBenchmarkRunDisabled({
  workspaceLocked,
  selectedMolecules,
  benchmarkMode,
  selectedAlgorithms,
  algorithmVariants,
  hasBlockedSelection,
  backendReady,
}: {
  workspaceLocked: boolean;
  selectedMolecules: ReadonlySet<string>;
  benchmarkMode: BenchmarkVariantMode;
  selectedAlgorithms: ReadonlySet<RunAlgorithm>;
  algorithmVariants: readonly BenchmarkAlgorithmVariant[];
  hasBlockedSelection: boolean;
  backendReady: boolean;
}): boolean {
  return (
    workspaceLocked ||
    selectedMolecules.size === 0 ||
    (benchmarkMode === "advanced"
      ? algorithmVariants.length === 0
      : selectedAlgorithms.size === 0) ||
    hasBlockedSelection ||
    backendReady === false
  );
}

export function shouldShowBenchmarkResetResults({
  total,
  running,
  hasPausedBenchmark,
  actionInProgress,
}: {
  total: number;
  running: boolean;
  hasPausedBenchmark: boolean;
  actionInProgress: boolean;
}): boolean {
  return total > 0 && !running && !hasPausedBenchmark && !actionInProgress;
}
