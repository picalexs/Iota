import { useCallback, useEffect, type Dispatch, type RefObject, type SetStateAction } from "react";

import { getBenchmarkRun } from "@/api/benchmarks";
import { logAppError } from "@/lib/app-logger";
import { getErrorMessage } from "@/lib/error-handler";
import type { MoleculeResponse, RunAlgorithm } from "@/types/run";

import {
  type BenchmarkWorkspaceStateSnapshot,
  type SavedBenchmarkRun,
  upsertSavedBenchmarkRun,
} from "@/pages/benchmark/benchmark-storage";
import {
  benchmarkEntriesChanged,
  benchmarkWorkspaceSnapshotChanged,
  buildBenchmarkWorkspaceSnapshotFromSavedRun,
  hasRestorableBenchmarkWorkspaceSnapshot,
  readBenchmarkWorkspaceViewCache,
} from "@/features/benchmarks/state/normalization";
import { resetBenchmarkWorkspaceState } from "@/features/benchmarks/state/hydration";
import { reconcileSavedBenchmarkRun } from "@/features/benchmarks/state/saved-catalog";
import {
  shouldPollEntry,
  NON_EXECUTING,
  TERMINAL,
  type BenchmarkBackendMode,
  type BenchmarkEntry,
} from "@/pages/benchmark/benchmark-utils";
import type {
  BenchmarkAlgorithmVariant,
  BenchmarkVariantMode,
} from "@/pages/benchmark/benchmark-variants";
import type { BenchmarkPendingAction } from "@/features/benchmarks/state/controls";

export type SavedBenchmarkRunsSetter = Dispatch<SetStateAction<SavedBenchmarkRun[]>>;

export function useBenchmarkRouteReset({
  benchmarkId,
  runGenerationRef,
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
  setSavedBenchmarkLoadError,
}: {
  benchmarkId: string | null;
  runGenerationRef: RefObject<number>;
  stopPolling: () => void;
  setSelectedSavedBenchmarkId: Dispatch<SetStateAction<string | null>>;
  setActiveSavedBenchmarkId: Dispatch<SetStateAction<string | null>>;
  setHydratedBenchmarkId: Dispatch<SetStateAction<string | null>>;
  setRunning: Dispatch<SetStateAction<boolean>>;
  setEntries: Dispatch<SetStateAction<BenchmarkEntry[]>>;
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
  setSavedBenchmarkLoadError: Dispatch<SetStateAction<string | null>>;
}): void {
  useEffect(() => {
    if (benchmarkId !== null) return;

    runGenerationRef.current += 1;
    setSavedBenchmarkLoadError(null);
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
      setShots,
      setOptimizationLevel,
      setSeedTranspiler,
      setDynamicalDecoupling,
      setTwirling,
      setChemicalAccuracyHa,
      setCustomMolecules,
    });
  }, [
    benchmarkId,
    runGenerationRef,
    setActiveSavedBenchmarkId,
    setChemicalAccuracyHa,
    setCustomMolecules,
    setEntries,
    setBenchmarkMode,
    setHydratedBenchmarkId,
    setRunning,
    setSelectedAlgorithms,
    setAlgorithmVariants,
    setSelectedBackendMode,
    setSelectedBackendName,
    setShots,
    setOptimizationLevel,
    setSeedTranspiler,
    setDynamicalDecoupling,
    setTwirling,
    setSelectedBasis,
    setSelectedMoleculeKeys,
    setSelectedSavedBenchmarkId,
    setSavedBenchmarkLoadError,
    stopPolling,
  ]);
}

export function useBenchmarkRouteHydration({
  benchmarkId,
  hydrateSavedBenchmark,
  runGenerationRef,
  setSavedBenchmarkRuns,
  setHydratedBenchmarkId,
  setSavedBenchmarkLoadError,
}: {
  benchmarkId: string | null;
  hydrateSavedBenchmark: (savedRun: SavedBenchmarkRun) => void;
  runGenerationRef: RefObject<number>;
  setSavedBenchmarkRuns: SavedBenchmarkRunsSetter;
  setHydratedBenchmarkId: Dispatch<SetStateAction<string | null>>;
  setSavedBenchmarkLoadError: Dispatch<SetStateAction<string | null>>;
}): void {
  const hydrateBenchmarkRoute = useCallback(
    async (currentBenchmarkId: string, isCancelledOrStale: () => boolean): Promise<void> => {
      const cachedWorkspaceSnapshot = readBenchmarkWorkspaceViewCache(currentBenchmarkId);
      const restorableCachedWorkspaceSnapshot = hasRestorableBenchmarkWorkspaceSnapshot(
        cachedWorkspaceSnapshot,
      )
        ? cachedWorkspaceSnapshot
        : null;

      try {
        const savedRun = await getBenchmarkRun(currentBenchmarkId);
        if (isCancelledOrStale()) return;

        setSavedBenchmarkRuns((current) => upsertSavedBenchmarkRun(current, savedRun));
        if (restorableCachedWorkspaceSnapshot === null) {
          hydrateSavedBenchmark(savedRun);
        }
        setHydratedBenchmarkId(savedRun.id);
        setSavedBenchmarkLoadError(null);

        const refreshedRun = await reconcileSavedBenchmarkRun(savedRun, {
          refreshActiveRows: restorableCachedWorkspaceSnapshot !== null,
          refreshCompletedRows: true,
        });
        if (isCancelledOrStale()) return;

        const refreshedSnapshot = buildBenchmarkWorkspaceSnapshotFromSavedRun(refreshedRun);
        const shouldHydrateRefreshedRun =
          restorableCachedWorkspaceSnapshot === null ||
          benchmarkWorkspaceSnapshotChanged(restorableCachedWorkspaceSnapshot, refreshedSnapshot);
        if (
          !benchmarkEntriesChanged(savedRun.entries, refreshedRun.entries) &&
          !shouldHydrateRefreshedRun
        ) {
          return;
        }

        setSavedBenchmarkRuns((current) => upsertSavedBenchmarkRun(current, refreshedRun));
        if (shouldHydrateRefreshedRun) {
          hydrateSavedBenchmark(refreshedRun);
        }
      } catch (error) {
        if (isCancelledOrStale()) return;

        logAppError("benchmark.hydration", "Failed to load saved benchmark.", error, {
          benchmarkId: currentBenchmarkId,
        });
        setSavedBenchmarkLoadError(getErrorMessage(error, "Failed to load benchmark."));
        setHydratedBenchmarkId(currentBenchmarkId);
      }
    },
    [
      hydrateSavedBenchmark,
      setHydratedBenchmarkId,
      setSavedBenchmarkLoadError,
      setSavedBenchmarkRuns,
    ],
  );

  useEffect(() => {
    if (benchmarkId === null) return;

    setSavedBenchmarkLoadError(null);
    setHydratedBenchmarkId(null);
    const routeGeneration = runGenerationRef.current;
    let cancelled = false;
    void hydrateBenchmarkRoute(
      benchmarkId,
      () => cancelled || runGenerationRef.current !== routeGeneration,
    );

    return () => {
      cancelled = true;
    };
  }, [
    benchmarkId,
    hydrateBenchmarkRoute,
    runGenerationRef,
    setHydratedBenchmarkId,
    setSavedBenchmarkLoadError,
  ]);
}

export function useDeactivateActiveBenchmark({
  activeSavedBenchmarkId,
  entries,
  pendingBenchmarkAction,
  setActiveSavedBenchmarkId,
}: {
  activeSavedBenchmarkId: string | null;
  entries: BenchmarkEntry[];
  pendingBenchmarkAction: BenchmarkPendingAction;
  setActiveSavedBenchmarkId: Dispatch<SetStateAction<string | null>>;
}): void {
  useEffect(() => {
    if (activeSavedBenchmarkId === null) return;
    if (
      entries.some(
        (entry) =>
          entry.status !== "idle" &&
          !TERMINAL.has(entry.status) &&
          !NON_EXECUTING.has(entry.status),
      ) ||
      pendingBenchmarkAction !== null
    ) {
      return;
    }
    setActiveSavedBenchmarkId(null);
  }, [activeSavedBenchmarkId, entries, pendingBenchmarkAction, setActiveSavedBenchmarkId]);
}

export function hasInitialPollableBenchmarkEntries(
  snapshot: Pick<BenchmarkWorkspaceStateSnapshot, "entries"> | null,
  restoredEntries: BenchmarkEntry[],
): boolean {
  return snapshot?.entries.some(shouldPollEntry) ?? restoredEntries.some(shouldPollEntry);
}

export function initialActiveSavedBenchmarkIdFor(
  benchmarkId: string | null,
  hasPollableEntries: boolean,
): string | null {
  return benchmarkId !== null && hasPollableEntries ? benchmarkId : null;
}

export function appendCustomMoleculeIfMissing(
  previous: MoleculeResponse[],
  molecule: MoleculeResponse,
): MoleculeResponse[] {
  return previous.some((entry) => entry.id === molecule.id) ? previous : [...previous, molecule];
}

export function toggleDistinctValue<T extends string>(previous: T[], value: T): T[] {
  const next = new Set(previous);
  if (next.has(value)) {
    next.delete(value);
  } else {
    next.add(value);
  }
  return Array.from(next);
}

export function hasCachedSavedBenchmarkSelection({
  benchmarkId,
  selectedSavedBenchmarkId,
  entries,
  selectedMoleculeKeys,
}: {
  benchmarkId: string | null;
  selectedSavedBenchmarkId: string | null;
  entries: BenchmarkEntry[];
  selectedMoleculeKeys: string[];
}): boolean {
  return (
    benchmarkId !== null &&
    selectedSavedBenchmarkId === benchmarkId &&
    (entries.length > 0 || selectedMoleculeKeys.length > 0)
  );
}
