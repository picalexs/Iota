import type { Dispatch, SetStateAction } from "react";

import { BENCHMARK_ALGORITHMS, DEFAULT_CHEMICAL_ACCURACY_HA } from "@/lib/benchmark-presets";
import type { MoleculeResponse, RunAlgorithm } from "@/types/run";

import {
  buildBenchmarkWorkspaceSnapshotFromSavedRun,
  mergeCustomMolecules,
} from "@/features/benchmarks/state/normalization";
import {
  normalizeStoredEntry,
  shouldPollEntry,
  type BenchmarkBackendMode,
  type BenchmarkEntry,
} from "@/pages/benchmark/benchmark-utils";
import type { SavedBenchmarkRun } from "@/pages/benchmark/benchmark-storage";
import type {
  BenchmarkAlgorithmVariant,
  BenchmarkVariantMode,
} from "@/pages/benchmark/benchmark-variants";

const DEFAULT_BENCHMARK_BASIS = "sto-3g";
const DEFAULT_BENCHMARK_ALGORITHMS = BENCHMARK_ALGORITHMS.map((algorithm) => algorithm.value);

export type BenchmarkEntriesSetter = Dispatch<SetStateAction<BenchmarkEntry[]>>;

export function hydrateSavedBenchmarkState({
  savedRun,
  startPolling,
  setSelectedSavedBenchmarkId,
  setSelectedMoleculeKeys,
  setBenchmarkMode,
  setSelectedAlgorithms,
  setAlgorithmVariants,
  setSelectedBasis,
  setSelectedBackendMode,
  setSelectedBackendName,
  setShots,
  setOptimizationLevel,
  setSeedTranspiler,
  setDynamicalDecoupling,
  setTwirling,
  setChemicalAccuracyHa,
  setCustomMolecules,
  setEntries,
  setActiveSavedBenchmarkId,
  setRunning,
}: {
  savedRun: SavedBenchmarkRun;
  startPolling: (entries?: BenchmarkEntry[]) => void;
  setSelectedSavedBenchmarkId: Dispatch<SetStateAction<string | null>>;
  setSelectedMoleculeKeys: Dispatch<SetStateAction<string[]>>;
  setBenchmarkMode: Dispatch<SetStateAction<BenchmarkVariantMode>>;
  setSelectedAlgorithms: Dispatch<SetStateAction<RunAlgorithm[]>>;
  setAlgorithmVariants: Dispatch<SetStateAction<BenchmarkAlgorithmVariant[]>>;
  setSelectedBasis: Dispatch<SetStateAction<string>>;
  setSelectedBackendMode: Dispatch<SetStateAction<BenchmarkBackendMode>>;
  setSelectedBackendName: Dispatch<SetStateAction<string | null>>;
  setShots?: Dispatch<SetStateAction<number>>;
  setOptimizationLevel?: Dispatch<SetStateAction<0 | 1 | 2 | 3>>;
  setSeedTranspiler?: Dispatch<SetStateAction<number | null>>;
  setDynamicalDecoupling?: Dispatch<SetStateAction<boolean>>;
  setTwirling?: Dispatch<SetStateAction<boolean>>;
  setChemicalAccuracyHa: Dispatch<SetStateAction<number>>;
  setCustomMolecules: Dispatch<SetStateAction<MoleculeResponse[]>>;
  setEntries: BenchmarkEntriesSetter;
  setActiveSavedBenchmarkId: Dispatch<SetStateAction<string | null>>;
  setRunning: Dispatch<SetStateAction<boolean>>;
}): void {
  const snapshot = buildBenchmarkWorkspaceSnapshotFromSavedRun(savedRun);
  setSelectedSavedBenchmarkId(savedRun.id);
  setSelectedMoleculeKeys(snapshot.selectedMoleculeKeys);
  setBenchmarkMode(snapshot.benchmarkMode);
  setSelectedAlgorithms(snapshot.selectedAlgorithms);
  setAlgorithmVariants(snapshot.algorithmVariants);
  setSelectedBasis(snapshot.selectedBasis);
  setSelectedBackendMode(snapshot.selectedBackendMode);
  setSelectedBackendName(snapshot.selectedBackendName);
  setShots?.(snapshot.shots ?? 4096);
  setOptimizationLevel?.(snapshot.optimizationLevel ?? 1);
  setSeedTranspiler?.(snapshot.seedTranspiler ?? null);
  setDynamicalDecoupling?.(snapshot.dynamicalDecoupling ?? false);
  setTwirling?.(snapshot.twirling ?? false);
  setChemicalAccuracyHa(snapshot.chemicalAccuracyHa);
  setCustomMolecules((current) => mergeCustomMolecules(current, snapshot.customMolecules));

  const restored = snapshot.entries.map(normalizeStoredEntry);
  setEntries(restored);

  const hasPollableEntries = restored.some(shouldPollEntry);
  setActiveSavedBenchmarkId(hasPollableEntries ? savedRun.id : null);
  setRunning(hasPollableEntries);
  if (hasPollableEntries) {
    startPolling(restored);
  }
}

export function resetBenchmarkWorkspaceState({
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
  setShots,
  setOptimizationLevel,
  setSeedTranspiler,
  setDynamicalDecoupling,
  setTwirling,
  setChemicalAccuracyHa,
  setCustomMolecules,
}: {
  stopPolling: () => void;
  setSelectedSavedBenchmarkId: Dispatch<SetStateAction<string | null>>;
  setActiveSavedBenchmarkId: Dispatch<SetStateAction<string | null>>;
  setHydratedBenchmarkId: Dispatch<SetStateAction<string | null>>;
  setRunning: Dispatch<SetStateAction<boolean>>;
  setEntries: BenchmarkEntriesSetter;
  setSelectedMoleculeKeys: Dispatch<SetStateAction<string[]>>;
  setBenchmarkMode: Dispatch<SetStateAction<BenchmarkVariantMode>>;
  setSelectedAlgorithms: Dispatch<SetStateAction<RunAlgorithm[]>>;
  setAlgorithmVariants: Dispatch<SetStateAction<BenchmarkAlgorithmVariant[]>>;
  setSelectedBasis: Dispatch<SetStateAction<string>>;
  setSelectedBackendMode: Dispatch<SetStateAction<BenchmarkBackendMode>>;
  setSelectedBackendName: Dispatch<SetStateAction<string | null>>;
  setShots?: Dispatch<SetStateAction<number>>;
  setOptimizationLevel?: Dispatch<SetStateAction<0 | 1 | 2 | 3>>;
  setSeedTranspiler?: Dispatch<SetStateAction<number | null>>;
  setDynamicalDecoupling?: Dispatch<SetStateAction<boolean>>;
  setTwirling?: Dispatch<SetStateAction<boolean>>;
  setChemicalAccuracyHa: Dispatch<SetStateAction<number>>;
  setCustomMolecules: Dispatch<SetStateAction<MoleculeResponse[]>>;
}): void {
  stopPolling();
  setSelectedSavedBenchmarkId(null);
  setActiveSavedBenchmarkId(null);
  setHydratedBenchmarkId(null);
  setRunning(false);
  setEntries([]);
  setSelectedMoleculeKeys([]);
  setBenchmarkMode("simple");
  setSelectedAlgorithms(DEFAULT_BENCHMARK_ALGORITHMS);
  setAlgorithmVariants([]);
  setSelectedBasis(DEFAULT_BENCHMARK_BASIS);
  setSelectedBackendMode("statevector");
  setSelectedBackendName(null);
  setShots?.(4096);
  setOptimizationLevel?.(1);
  setSeedTranspiler?.(null);
  setDynamicalDecoupling?.(false);
  setTwirling?.(false);
  setChemicalAccuracyHa(DEFAULT_CHEMICAL_ACCURACY_HA);
  setCustomMolecules([]);
}
