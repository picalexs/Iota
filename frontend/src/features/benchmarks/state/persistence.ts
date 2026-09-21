/** Active benchmark entry and draft persistence synchronization. */

import type { QueryClient } from "@tanstack/react-query";
import {
  useEffect,
  useEffectEvent,
  type Dispatch,
  type RefObject,
  type SetStateAction,
} from "react";

import {
  updateBenchmarkRun,
  type BenchmarkRunCreate,
  type BenchmarkRunUpdate,
} from "@/api/benchmarks";
import { benchmarkKeys } from "@/hooks/query-keys";
import { logAppWarning } from "@/lib/app-logger";
import { getErrorMessage } from "@/lib/error-handler";
import type { MoleculeResponse, RunAlgorithm } from "@/types/run";
import type { BenchmarkEntry } from "@/pages/benchmark/benchmark-utils";
import type { BenchmarkBackendMode } from "@/types/benchmark";
import type { AerMethod } from "@/types/run-config";
import type {
  BenchmarkAlgorithmVariant,
  BenchmarkVariantMode,
} from "@/pages/benchmark/benchmark-variants";
import {
  benchmarkEntriesChanged,
  writeBenchmarkWorkspaceViewCache,
} from "@/features/benchmarks/state/normalization";
import { hasPendingEntrySubmission } from "@/features/benchmarks/state/selectors";
import type { BenchmarkPendingAction } from "@/features/benchmarks/state/controls";
import {
  upsertSavedBenchmarkRun,
  type SavedBenchmarkRun,
} from "@/pages/benchmark/benchmark-storage";

type TimerRef = RefObject<ReturnType<typeof setTimeout> | null>;

export type SavedBenchmarkRunsSetter = Dispatch<SetStateAction<SavedBenchmarkRun[]>>;

export interface BenchmarkRunListCache {
  items: SavedBenchmarkRun[];
  total: number;
  limit: number;
  offset: number;
}

const BENCHMARK_ACTIVE_PERSIST_DELAY_MS = 500;

export function buildOptimisticSavedBenchmarkRun(
  existing: SavedBenchmarkRun,
  entries: BenchmarkEntry[],
  updatedAt: string,
): SavedBenchmarkRun {
  return {
    ...existing,
    updatedAt,
    entries,
  };
}

export function mergeSavedBenchmarkRunIntoListCache(
  current: BenchmarkRunListCache | undefined,
  savedRun: SavedBenchmarkRun,
): BenchmarkRunListCache | undefined {
  if (current === undefined) return current;

  const alreadyTracked = current.items.some((run) => run.id === savedRun.id);
  return {
    ...current,
    items: upsertSavedBenchmarkRun(current.items, savedRun),
    total: alreadyTracked ? current.total : current.total + 1,
  };
}

export function persistActiveBenchmarkEntries(
  activeSavedBenchmarkId: string,
  entries: BenchmarkEntry[],
  queryClient: QueryClient,
  setSavedBenchmarkRuns: SavedBenchmarkRunsSetter,
): void {
  void updateBenchmarkRun(activeSavedBenchmarkId, { entries })
    .then((savedRun) => {
      setSavedBenchmarkRuns((current) => upsertSavedBenchmarkRun(current, savedRun));
      syncSavedBenchmarkRunQueryCache(queryClient, savedRun);
    })
    .catch((error) => {
      logAppWarning("benchmark.persist-active", "Failed to persist active benchmark entries.", {
        benchmarkId: activeSavedBenchmarkId,
        error: getErrorMessage(error),
      });
    });
}

export function flushPendingActiveBenchmarkEntriesPersist({
  benchmarkId,
  entries,
  benchmarkSaveTimerRef,
  queryClient,
}: {
  benchmarkId: string | null;
  entries: BenchmarkEntry[];
  benchmarkSaveTimerRef: TimerRef;
  queryClient: QueryClient;
}): void {
  if (benchmarkId === null || benchmarkSaveTimerRef.current === null) return;

  clearTimer(benchmarkSaveTimerRef);
  void updateBenchmarkRun(benchmarkId, { entries })
    .then((savedRun) => {
      syncSavedBenchmarkRunQueryCache(queryClient, savedRun);
    })
    .catch((error) => {
      logAppWarning("benchmark.persist-active-flush", "Failed to flush active benchmark rows.", {
        benchmarkId,
        error: getErrorMessage(error),
      });
    });
}

export function syncSavedBenchmarkRunQueryCache(
  queryClient: QueryClient,
  savedRun: SavedBenchmarkRun,
): void {
  queryClient.setQueriesData<BenchmarkRunListCache>(
    { queryKey: benchmarkKeys.listPrefix },
    (current) => mergeSavedBenchmarkRunIntoListCache(current, savedRun),
  );
}

export function useBenchmarkWorkspaceCacheSync({
  benchmarkId,
  benchmarkMode,
  selectedMoleculeKeys,
  selectedAlgorithms,
  algorithmVariants,
  selectedBasis,
  selectedBackendMode,
  selectedBackendName,
  shots,
  selectedAerMethod,
  selectedDevice,
  chemicalAccuracyHa,
  customMolecules,
  entries,
}: {
  benchmarkId: string | null;
  benchmarkMode: BenchmarkVariantMode;
  selectedMoleculeKeys: string[];
  selectedAlgorithms: RunAlgorithm[];
  algorithmVariants: BenchmarkAlgorithmVariant[];
  selectedBasis: string;
  selectedBackendMode: BenchmarkBackendMode;
  selectedBackendName: string | null;
  shots: number;
  selectedAerMethod: AerMethod | null;
  selectedDevice: "CPU" | "GPU" | null;
  chemicalAccuracyHa: number;
  customMolecules: MoleculeResponse[];
  entries: BenchmarkEntry[];
}): void {
  useEffect(() => {
    if (benchmarkId === null) return;

    writeBenchmarkWorkspaceViewCache(benchmarkId, {
      benchmarkMode,
      selectedMoleculeKeys,
      selectedAlgorithms,
      algorithmVariants,
      selectedBasis,
      selectedBackendMode,
      selectedBackendName,
      shots,
      selectedAerMethod,
      selectedDevice,
      chemicalAccuracyHa,
      customMolecules,
      entries,
    });
  }, [
    benchmarkId,
    benchmarkMode,
    chemicalAccuracyHa,
    algorithmVariants,
    customMolecules,
    entries,
    selectedAlgorithms,
    selectedBackendMode,
    selectedBackendName,
    selectedAerMethod,
    selectedDevice,
    selectedBasis,
    selectedMoleculeKeys,
    shots,
  ]);
}

function clearTimer(timerRef: TimerRef): void {
  if (timerRef.current !== null) {
    clearTimeout(timerRef.current);
    timerRef.current = null;
  }
}

function clearTimers(...timerRefs: TimerRef[]): void {
  for (const timerRef of timerRefs) {
    clearTimer(timerRef);
  }
}

function scheduleActiveBenchmarkEntriesPersist({
  benchmarkId,
  entries,
  benchmarkSaveTimerRef,
  queryClient,
  savedBenchmarkRuns,
  setSavedBenchmarkRuns,
  existingSnapshot,
  delayMs = BENCHMARK_ACTIVE_PERSIST_DELAY_MS,
}: {
  benchmarkId: string;
  entries: BenchmarkEntry[];
  benchmarkSaveTimerRef: TimerRef;
  queryClient: QueryClient;
  savedBenchmarkRuns: SavedBenchmarkRun[];
  setSavedBenchmarkRuns: SavedBenchmarkRunsSetter;
  existingSnapshot?: SavedBenchmarkRun;
  delayMs?: number;
}): void {
  const existing = existingSnapshot ?? savedBenchmarkRuns.find((run) => run.id === benchmarkId);
  if (!existing || !benchmarkEntriesChanged(existing.entries, entries)) return;

  clearTimer(benchmarkSaveTimerRef);

  const nextSnapshot = buildOptimisticSavedBenchmarkRun(
    existing,
    entries,
    new Date().toISOString(),
  );
  setSavedBenchmarkRuns((current) => upsertSavedBenchmarkRun(current, nextSnapshot));
  syncSavedBenchmarkRunQueryCache(queryClient, nextSnapshot);
  benchmarkSaveTimerRef.current = setTimeout(
    () => persistActiveBenchmarkEntries(benchmarkId, entries, queryClient, setSavedBenchmarkRuns),
    delayMs,
  );
}

export function useActiveBenchmarkEntrySync({
  activeSavedBenchmarkId,
  entries,
  savedBenchmarkRuns,
  benchmarkSaveTimerRef,
  queryClient,
  setSavedBenchmarkRuns,
}: {
  activeSavedBenchmarkId: string | null;
  entries: BenchmarkEntry[];
  savedBenchmarkRuns: SavedBenchmarkRun[];
  benchmarkSaveTimerRef: TimerRef;
  queryClient: QueryClient;
  setSavedBenchmarkRuns: SavedBenchmarkRunsSetter;
}): void {
  useEffect(() => {
    if (activeSavedBenchmarkId === null) return;
    if (hasPendingEntrySubmission(entries)) return;
    scheduleActiveBenchmarkEntriesPersist({
      benchmarkId: activeSavedBenchmarkId,
      entries,
      benchmarkSaveTimerRef,
      queryClient,
      savedBenchmarkRuns,
      setSavedBenchmarkRuns,
    });
  }, [
    activeSavedBenchmarkId,
    benchmarkSaveTimerRef,
    entries,
    queryClient,
    savedBenchmarkRuns,
    setSavedBenchmarkRuns,
  ]);
}

function persistBenchmarkDraft(
  draftBenchmarkId: string,
  payload: BenchmarkRunUpdate,
  queryClient: QueryClient,
  benchmarkConfigSignatureRef: RefObject<string | null>,
  setSavedBenchmarkRuns: SavedBenchmarkRunsSetter,
): void {
  void updateBenchmarkRun(draftBenchmarkId, payload)
    .then((savedRun) => {
      setSavedBenchmarkRuns((current) => upsertSavedBenchmarkRun(current, savedRun));
      syncSavedBenchmarkRunQueryCache(queryClient, savedRun);
    })
    .catch((error) => {
      logAppWarning("benchmark.persist-draft", "Failed to persist benchmark draft.", {
        benchmarkId: draftBenchmarkId,
        error: getErrorMessage(error),
      });
      benchmarkConfigSignatureRef.current = null;
    });
}

export function useBenchmarkDraftSync({
  benchmarkId,
  selectedSavedBenchmarkId,
  hydratedBenchmarkId,
  activeSavedBenchmarkId,
  pendingBenchmarkAction,
  running,
  entries,
  buildBenchmarkPayload,
  buildBenchmarkSignature,
  benchmarkConfigSaveTimerRef,
  benchmarkConfigSignatureRef,
  queryClient,
  setSavedBenchmarkRuns,
}: {
  benchmarkId: string | null;
  selectedSavedBenchmarkId: string | null;
  hydratedBenchmarkId: string | null;
  activeSavedBenchmarkId: string | null;
  pendingBenchmarkAction: BenchmarkPendingAction;
  running: boolean;
  entries: BenchmarkEntry[];
  buildBenchmarkPayload: (nextEntries: BenchmarkEntry[]) => BenchmarkRunCreate;
  buildBenchmarkSignature: (nextEntries: BenchmarkEntry[]) => string;
  benchmarkConfigSaveTimerRef: TimerRef;
  benchmarkConfigSignatureRef: RefObject<string | null>;
  queryClient: QueryClient;
  setSavedBenchmarkRuns: SavedBenchmarkRunsSetter;
}): void {
  useEffect(() => {
    const draftBenchmarkId = selectedSavedBenchmarkId ?? benchmarkId;
    if (draftBenchmarkId === null) return;
    if (benchmarkId !== null && hydratedBenchmarkId !== benchmarkId) return;
    if (running || activeSavedBenchmarkId !== null || pendingBenchmarkAction !== null) return;

    const signature = buildBenchmarkSignature(entries);
    if (benchmarkConfigSignatureRef.current === signature) return;
    benchmarkConfigSignatureRef.current = signature;

    clearTimer(benchmarkConfigSaveTimerRef);

    const payload = buildBenchmarkPayload(entries);
    const updatePayload: BenchmarkRunUpdate = payload;
    const updatedAt = new Date().toISOString();
    setSavedBenchmarkRuns((current) => {
      const existing = current.find((run) => run.id === draftBenchmarkId);
      return upsertSavedBenchmarkRun(current, {
        id: draftBenchmarkId,
        createdAt: existing?.createdAt ?? updatedAt,
        updatedAt,
        ...payload,
      });
    });

    benchmarkConfigSaveTimerRef.current = setTimeout(
      () =>
        persistBenchmarkDraft(
          draftBenchmarkId,
          updatePayload,
          queryClient,
          benchmarkConfigSignatureRef,
          setSavedBenchmarkRuns,
        ),
      250,
    );
  }, [
    activeSavedBenchmarkId,
    benchmarkConfigSaveTimerRef,
    benchmarkConfigSignatureRef,
    benchmarkId,
    buildBenchmarkPayload,
    buildBenchmarkSignature,
    entries,
    hydratedBenchmarkId,
    pendingBenchmarkAction,
    queryClient,
    running,
    selectedSavedBenchmarkId,
    setSavedBenchmarkRuns,
  ]);
}

export function useBenchmarkTimerCleanup(
  benchmarkSaveTimerRef: TimerRef,
  benchmarkConfigSaveTimerRef: TimerRef,
  flushPendingActivePersist: () => void,
): void {
  const handleCleanup = useEffectEvent(() => {
    flushPendingActivePersist();
    clearTimers(benchmarkSaveTimerRef, benchmarkConfigSaveTimerRef);
  });

  useEffect(() => {
    return () => {
      handleCleanup();
    };
  }, [benchmarkConfigSaveTimerRef, benchmarkSaveTimerRef]);
}
