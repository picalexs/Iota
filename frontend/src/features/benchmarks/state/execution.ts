/** Benchmark submission helpers and execution orchestration. */

import type { QueryClient } from "@tanstack/react-query";
import { useCallback, type Dispatch, type RefObject, type SetStateAction } from "react";

import {
  createBenchmarkRun,
  deleteBenchmarkRun,
  updateBenchmarkRun,
  type BenchmarkRunCreate,
  type BenchmarkRunUpdate,
} from "@/api/benchmarks";
import { invalidateBenchmarkRunQueries, invalidateRunsQueries } from "@/hooks/use-query-hooks";
import { logAppWarning } from "@/lib/app-logger";
import { getErrorMessage } from "@/lib/error-handler";
import type { MoleculePreset } from "@/lib/benchmark-presets";
import {
  buildInitialEntries,
  getBenchmarkMoleculeBlocker,
  requiresIbmConfirmation,
  submitBenchmarkEntry,
  type BenchmarkBackendMode,
} from "@/pages/benchmark/benchmark-utils";
import {
  acquireMolecule,
  type MoleculeAcquisitionResult,
} from "@/pages/benchmark/molecule-acquisition";
import { getBenchmarkSubmissionConcurrency } from "@/features/benchmarks/state/normalization";
import {
  upsertSavedBenchmarkRun,
  type SavedBenchmarkRun,
} from "@/pages/benchmark/benchmark-storage";
import type { BenchmarkAlgorithmVariant } from "@/pages/benchmark/benchmark-variants";

import type { BenchmarkEntriesSetter } from "@/features/benchmarks/state/polling";
import type { BenchmarkEntry, BenchmarkSubmitResult } from "@/pages/benchmark/benchmark-utils";
import type { BenchmarkExecutionSettings } from "@/types/benchmark";

export async function mapWithConcurrencyLimit<T, R>(
  items: readonly T[],
  concurrency: number,
  mapper: (item: T, index: number) => Promise<R>,
): Promise<PromiseSettledResult<R>[]> {
  const limit = Math.max(1, Math.floor(concurrency));
  const results: PromiseSettledResult<R>[] = new Array(items.length);
  let nextIndex = 0;

  async function worker() {
    while (nextIndex < items.length) {
      const currentIndex = nextIndex;
      nextIndex += 1;
      const item = items[currentIndex];
      if (item === undefined) {
        results[currentIndex] = {
          status: "rejected",
          reason: new Error("Benchmark execution item is missing"),
        };
        continue;
      }
      try {
        const value = await mapper(item, currentIndex);
        results[currentIndex] = { status: "fulfilled", value };
      } catch (reason) {
        results[currentIndex] = { status: "rejected", reason };
      }
    }
  }

  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, () => worker()));
  return results;
}

export function applySubmitResults(
  entries: readonly BenchmarkEntry[],
  results: readonly PromiseSettledResult<BenchmarkSubmitResult>[],
): BenchmarkEntry[] {
  const resultMap = new Map(
    results
      .filter((result): result is PromiseFulfilledResult<BenchmarkSubmitResult> => {
        return result.status === "fulfilled";
      })
      .map((result) => [result.value.id, result.value]),
  );

  return entries.map((entry) => {
    const result = resultMap.get(entry.id);
    if (!result) return entry;
    return {
      ...entry,
      status: result.status,
      moleculeId: result.moleculeId,
      runId: result.runId,
      errorMessage: result.errorMessage,
    };
  });
}

type TimerRef = RefObject<ReturnType<typeof setTimeout> | null>;
type SavedBenchmarkRunsSetter = Dispatch<SetStateAction<SavedBenchmarkRun[]>>;
type BenchmarkActionErrorReporter = (scope: string, title: string, error: unknown) => void;

export function useBenchmarkExecutionStartActions({
  benchmarkId,
  selectedSavedBenchmarkId,
  selectedPresets,
  activeVariants,
  selectedBasis,
  selectedBackendMode,
  resolvedBackendName,
  shots,
  selectedAerMethod,
  selectedDevice,
  stopPolling,
  startPolling,
  runGenerationRef,
  benchmarkSaveTimerRef,
  benchmarkConfigSaveTimerRef,
  benchmarkConfigSignatureRef,
  buildBenchmarkPayload,
  buildBenchmarkSignature,
  setEntries,
  setRunning,
  setSavedBenchmarkRuns,
  setSelectedSavedBenchmarkId,
  setActiveSavedBenchmarkId,
  setHydratedBenchmarkId,
  queryClient,
  setIbmConfirmationOpen,
  persistSubmittedEntries,
  reportActionError,
}: {
  benchmarkId: string | null;
  selectedSavedBenchmarkId: string | null;
  selectedPresets: readonly MoleculePreset[];
  activeVariants: readonly BenchmarkAlgorithmVariant[];
  selectedBasis: string;
  selectedBackendMode: BenchmarkBackendMode;
  resolvedBackendName: string | null;
  shots: number;
  selectedAerMethod: BenchmarkExecutionSettings["aerMethod"];
  selectedDevice: BenchmarkExecutionSettings["device"];
  stopPolling: () => void;
  startPolling: (entries?: BenchmarkEntry[]) => void;
  runGenerationRef: RefObject<number>;
  benchmarkSaveTimerRef: TimerRef;
  benchmarkConfigSaveTimerRef: TimerRef;
  benchmarkConfigSignatureRef: RefObject<string | null>;
  buildBenchmarkPayload: (nextEntries: BenchmarkEntry[]) => BenchmarkRunCreate;
  buildBenchmarkSignature: (nextEntries: BenchmarkEntry[]) => string;
  setEntries: BenchmarkEntriesSetter;
  setRunning: Dispatch<SetStateAction<boolean>>;
  setSavedBenchmarkRuns: SavedBenchmarkRunsSetter;
  setSelectedSavedBenchmarkId: Dispatch<SetStateAction<string | null>>;
  setActiveSavedBenchmarkId: Dispatch<SetStateAction<string | null>>;
  setHydratedBenchmarkId: Dispatch<SetStateAction<string | null>>;
  queryClient: QueryClient;
  setIbmConfirmationOpen: Dispatch<SetStateAction<boolean>>;
  persistSubmittedEntries: (
    snapshot: SavedBenchmarkRun,
    entries: BenchmarkEntry[],
    isCurrentGeneration: () => boolean,
  ) => void;
  reportActionError: BenchmarkActionErrorReporter;
}) {
  const runBenchmark = useCallback(
    async (runOptions: { ibmRuntimeConfirmed?: boolean } = {}) => {
      if (requiresIbmConfirmation(selectedBackendMode) && !runOptions.ibmRuntimeConfirmed) {
        setIbmConfirmationOpen(true);
        return;
      }

      await executeBenchmarkRun({
        options: runOptions,
        benchmarkId,
        selectedSavedBenchmarkId,
        selectedPresets,
        activeVariants,
        selectedBasis,
        selectedBackendMode,
        resolvedBackendName,
        shots,
        selectedAerMethod,
        selectedDevice,
        stopPolling,
        startPolling,
        runGenerationRef,
        benchmarkSaveTimerRef,
        benchmarkConfigSaveTimerRef,
        benchmarkConfigSignatureRef,
        buildBenchmarkPayload,
        buildBenchmarkSignature,
        setEntries,
        setRunning,
        setSavedBenchmarkRuns,
        setSelectedSavedBenchmarkId,
        setActiveSavedBenchmarkId,
        setHydratedBenchmarkId,
        queryClient,
        persistSubmittedEntries,
      });
    },
    [
      activeVariants,
      benchmarkConfigSaveTimerRef,
      benchmarkConfigSignatureRef,
      benchmarkId,
      benchmarkSaveTimerRef,
      buildBenchmarkPayload,
      buildBenchmarkSignature,
      queryClient,
      resolvedBackendName,
      selectedAerMethod,
      selectedDevice,
      runGenerationRef,
      shots,
      selectedBackendMode,
      selectedBasis,
      selectedPresets,
      selectedSavedBenchmarkId,
      setActiveSavedBenchmarkId,
      setEntries,
      setHydratedBenchmarkId,
      setIbmConfirmationOpen,
      setRunning,
      setSavedBenchmarkRuns,
      setSelectedSavedBenchmarkId,
      startPolling,
      stopPolling,
      persistSubmittedEntries,
    ],
  );

  const handleRunBenchmark = useCallback(() => {
    void runBenchmark().catch((error) => {
      reportActionError("benchmark.run", "Failed to start benchmark", error);
    });
  }, [reportActionError, runBenchmark]);

  const confirmIbmBenchmarkRun = useCallback(async () => {
    try {
      await runBenchmark({ ibmRuntimeConfirmed: true });
      setIbmConfirmationOpen(false);
    } catch (error) {
      reportActionError("benchmark.run", "Failed to start benchmark", error);
      throw error;
    }
  }, [reportActionError, runBenchmark, setIbmConfirmationOpen]);

  return {
    handleRunBenchmark,
    confirmIbmBenchmarkRun,
  };
}

function getBlockedMoleculeReasons(presets: readonly MoleculePreset[]) {
  return new Map(
    presets
      .map((preset) => [preset.key, getBenchmarkMoleculeBlocker(preset)] as const)
      .filter(([, reason]) => reason !== null),
  );
}

async function resolveMoleculeIds(presets: readonly MoleculePreset[]) {
  const moleculeIdMap = new Map<string, MoleculeAcquisitionResult | Error>();

  await Promise.allSettled(
    presets.map(async (preset) => {
      try {
        const acquisition = await acquireMolecule(preset);
        moleculeIdMap.set(preset.key, acquisition);
      } catch (error) {
        moleculeIdMap.set(preset.key, error instanceof Error ? error : new Error(String(error)));
      }
    }),
  );

  return moleculeIdMap;
}

export function beginBenchmarkExecution({
  stopPolling,
  runGenerationRef,
  benchmarkSaveTimerRef,
  benchmarkConfigSaveTimerRef,
  selectedPresets,
  activeVariants,
  setEntries,
}: {
  stopPolling: () => void;
  runGenerationRef: RefObject<number>;
  benchmarkSaveTimerRef: TimerRef;
  benchmarkConfigSaveTimerRef: TimerRef;
  selectedPresets: readonly MoleculePreset[];
  activeVariants: readonly BenchmarkAlgorithmVariant[];
  setEntries: BenchmarkEntriesSetter;
}) {
  stopPolling();
  runGenerationRef.current += 1;
  const generation = runGenerationRef.current;
  const isCurrentGeneration = () => runGenerationRef.current === generation;
  const guardedSetEntries = (updater: (entries: BenchmarkEntry[]) => BenchmarkEntry[]) => {
    setEntries((entries) => (isCurrentGeneration() ? updater(entries) : entries));
  };

  clearTimeoutValue(benchmarkSaveTimerRef);
  clearTimeoutValue(benchmarkConfigSaveTimerRef);

  const initialEntries = buildInitialEntries(selectedPresets, activeVariants);
  setEntries(initialEntries);

  return { initialEntries, isCurrentGeneration, guardedSetEntries };
}

function clearTimeoutValue(timerRef: TimerRef) {
  if (timerRef.current !== null) {
    clearTimeout(timerRef.current);
    timerRef.current = null;
  }
}

export function markBlockedBenchmarkEntries({
  initialEntries,
  selectedPresets,
  setEntries,
  setRunning,
}: {
  initialEntries: BenchmarkEntry[];
  selectedPresets: readonly MoleculePreset[];
  setEntries: BenchmarkEntriesSetter;
  setRunning: Dispatch<SetStateAction<boolean>>;
}) {
  const blocked = getBlockedMoleculeReasons(selectedPresets);
  if (blocked.size === 0) return false;

  setEntries(
    initialEntries.map((entry) => {
      const reason = blocked.get(entry.preset.key);
      return reason
        ? { ...entry, status: "failed", errorMessage: reason, moleculeId: null, runId: null }
        : entry;
    }),
  );
  setRunning(false);
  return true;
}

async function saveBenchmarkSnapshot({
  benchmarkRunId,
  payload,
}: {
  benchmarkRunId: string | null;
  payload: BenchmarkRunCreate;
}): Promise<SavedBenchmarkRun> {
  if (benchmarkRunId === null) {
    return createBenchmarkRun(payload);
  }

  return updateBenchmarkRun(benchmarkRunId, payload);
}

async function submitInitialBenchmarkEntries({
  initialEntries,
  selectedPresets,
  selectedBasis,
  selectedBackendMode,
  resolvedBackendName,
  shots,
  selectedAerMethod,
  selectedDevice,
  guardedSetEntries,
  persistSubmittedEntries,
  options,
  snapshot,
  isCurrentGeneration,
}: {
  initialEntries: BenchmarkEntry[];
  selectedPresets: readonly MoleculePreset[];
  selectedBasis: string;
  selectedBackendMode: BenchmarkBackendMode;
  resolvedBackendName: string | null;
  shots: number;
  selectedAerMethod: BenchmarkExecutionSettings["aerMethod"];
  selectedDevice: BenchmarkExecutionSettings["device"];
  guardedSetEntries: (updater: (entries: BenchmarkEntry[]) => BenchmarkEntry[]) => void;
  persistSubmittedEntries?: (
    snapshot: SavedBenchmarkRun,
    entries: BenchmarkEntry[],
    isCurrentGeneration: () => boolean,
  ) => void;
  options: { ibmRuntimeConfirmed?: boolean };
  snapshot: SavedBenchmarkRun;
  isCurrentGeneration: () => boolean;
}) {
  const moleculeIdMap = await resolveMoleculeIds(selectedPresets);
  let currentEntries = initialEntries;
  const submitted = await mapWithConcurrencyLimit(
    initialEntries,
    getBenchmarkSubmissionConcurrency(selectedBackendMode),
    async (entry) => {
      const moleculeResult = moleculeIdMap.get(entry.preset.key);
      const result = await submitBenchmarkEntry(
        entry,
        moleculeResult,
        selectedBasis,
        {
          mode: selectedBackendMode,
          backendName: resolvedBackendName,
          shots,
          aerMethod: selectedAerMethod,
          device: selectedDevice,
        },
        guardedSetEntries,
        options,
      );
      currentEntries = applySubmitResults(currentEntries, [{ status: "fulfilled", value: result }]);
      persistSubmittedEntries?.(snapshot, currentEntries, isCurrentGeneration);
      return result;
    },
  );

  return applySubmitResults(currentEntries, submitted);
}

async function cleanupEmptyBenchmarkSnapshot({
  benchmarkRunId,
  snapshotId,
  queryClient,
  setSavedBenchmarkRuns,
  setSelectedSavedBenchmarkId,
  setActiveSavedBenchmarkId,
  setRunning,
}: {
  benchmarkRunId: string | null;
  snapshotId: string;
  queryClient: QueryClient;
  setSavedBenchmarkRuns: SavedBenchmarkRunsSetter;
  setSelectedSavedBenchmarkId: Dispatch<SetStateAction<string | null>>;
  setActiveSavedBenchmarkId: Dispatch<SetStateAction<string | null>>;
  setRunning: Dispatch<SetStateAction<boolean>>;
}) {
  if (benchmarkRunId === null) {
    await deleteBenchmarkRun(snapshotId).catch((error) => {
      logAppWarning("benchmark.cleanup", "Failed to delete empty benchmark snapshot.", {
        benchmarkId: snapshotId,
        error: getErrorMessage(error),
      });
    });
    await invalidateBenchmarkRunQueries(queryClient);
    setSavedBenchmarkRuns((current) => current.filter((run) => run.id !== snapshotId));
    setSelectedSavedBenchmarkId(null);
  } else {
    setSelectedSavedBenchmarkId(snapshotId);
  }
  setActiveSavedBenchmarkId(null);
  setRunning(false);
}

export async function executeBenchmarkRun({
  options,
  benchmarkId,
  selectedSavedBenchmarkId,
  selectedPresets,
  activeVariants,
  selectedBasis,
  selectedBackendMode,
  resolvedBackendName,
  shots,
  selectedAerMethod,
  selectedDevice,
  stopPolling,
  startPolling,
  runGenerationRef,
  benchmarkSaveTimerRef,
  benchmarkConfigSaveTimerRef,
  benchmarkConfigSignatureRef,
  buildBenchmarkPayload,
  buildBenchmarkSignature,
  setEntries,
  setRunning,
  setSavedBenchmarkRuns,
  setSelectedSavedBenchmarkId,
  setActiveSavedBenchmarkId,
  setHydratedBenchmarkId,
  queryClient,
  persistSubmittedEntries,
}: {
  options: { ibmRuntimeConfirmed?: boolean };
  benchmarkId: string | null;
  selectedSavedBenchmarkId: string | null;
  selectedPresets: readonly MoleculePreset[];
  activeVariants: readonly BenchmarkAlgorithmVariant[];
  selectedBasis: string;
  selectedBackendMode: BenchmarkBackendMode;
  resolvedBackendName: string | null;
  shots: number;
  selectedAerMethod: BenchmarkExecutionSettings["aerMethod"];
  selectedDevice: BenchmarkExecutionSettings["device"];
  stopPolling: () => void;
  startPolling: (entries?: BenchmarkEntry[]) => void;
  runGenerationRef: RefObject<number>;
  benchmarkSaveTimerRef: TimerRef;
  benchmarkConfigSaveTimerRef: TimerRef;
  benchmarkConfigSignatureRef: RefObject<string | null>;
  buildBenchmarkPayload: (nextEntries: BenchmarkEntry[]) => BenchmarkRunCreate;
  buildBenchmarkSignature: (nextEntries: BenchmarkEntry[]) => string;
  setEntries: BenchmarkEntriesSetter;
  setRunning: Dispatch<SetStateAction<boolean>>;
  setSavedBenchmarkRuns: SavedBenchmarkRunsSetter;
  setSelectedSavedBenchmarkId: Dispatch<SetStateAction<string | null>>;
  setActiveSavedBenchmarkId: Dispatch<SetStateAction<string | null>>;
  setHydratedBenchmarkId: Dispatch<SetStateAction<string | null>>;
  queryClient: QueryClient;
  persistSubmittedEntries?: (
    snapshot: SavedBenchmarkRun,
    entries: BenchmarkEntry[],
    isCurrentGeneration: () => boolean,
  ) => void;
}) {
  const { initialEntries, isCurrentGeneration, guardedSetEntries } = beginBenchmarkExecution({
    stopPolling,
    runGenerationRef,
    benchmarkSaveTimerRef,
    benchmarkConfigSaveTimerRef,
    selectedPresets,
    activeVariants,
    setEntries,
  });

  if (
    markBlockedBenchmarkEntries({
      initialEntries,
      selectedPresets,
      setEntries,
      setRunning,
    })
  ) {
    return;
  }

  setRunning(true);

  const benchmarkRunId = selectedSavedBenchmarkId ?? benchmarkId;
  const snapshotPayload = buildBenchmarkPayload(initialEntries);
  const snapshot = await saveBenchmarkSnapshot({
    benchmarkRunId,
    payload: snapshotPayload,
  });
  if (!isCurrentGeneration()) return;

  setSavedBenchmarkRuns((current) => upsertSavedBenchmarkRun(current, snapshot));
  setSelectedSavedBenchmarkId(snapshot.id);
  setActiveSavedBenchmarkId(snapshot.id);
  setHydratedBenchmarkId(snapshot.id);
  benchmarkConfigSignatureRef.current = buildBenchmarkSignature(initialEntries);
  await invalidateBenchmarkRunQueries(queryClient);

  const submittedEntries = await submitInitialBenchmarkEntries({
    initialEntries,
    selectedPresets,
    selectedBasis,
    selectedBackendMode,
    resolvedBackendName,
    shots,
    selectedAerMethod,
    selectedDevice,
    guardedSetEntries,
    persistSubmittedEntries,
    options,
    snapshot,
    isCurrentGeneration,
  });
  const anySubmitted = submittedEntries.some((entry) => entry.runId !== null);
  const submittedPayload: BenchmarkRunUpdate = buildBenchmarkPayload(submittedEntries);
  clearTimeoutValue(benchmarkSaveTimerRef);
  const submittedSnapshot = await updateBenchmarkRun(snapshot.id, submittedPayload);
  setSavedBenchmarkRuns((current) => upsertSavedBenchmarkRun(current, submittedSnapshot));
  await invalidateBenchmarkRunQueries(queryClient);
  if (!isCurrentGeneration()) return;

  setEntries(submittedEntries);
  benchmarkConfigSignatureRef.current = buildBenchmarkSignature(submittedEntries);

  if (!anySubmitted) {
    await cleanupEmptyBenchmarkSnapshot({
      benchmarkRunId,
      snapshotId: snapshot.id,
      queryClient,
      setSavedBenchmarkRuns,
      setSelectedSavedBenchmarkId,
      setActiveSavedBenchmarkId,
      setRunning,
    });
    return;
  }

  await invalidateRunsQueries(queryClient);
  await invalidateBenchmarkRunQueries(queryClient);
  startPolling(submittedEntries);
}
