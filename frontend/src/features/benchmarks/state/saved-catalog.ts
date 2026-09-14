import { useCallback, useEffect, type Dispatch, type RefObject, type SetStateAction } from "react";
import type { QueryClient } from "@tanstack/react-query";

import {
  deleteBenchmarkRun,
  getBenchmarkRun,
  listBenchmarkRuns,
  updateBenchmarkRun,
} from "@/api/benchmarks";
import { invalidateBenchmarkRunQueries, invalidateRunsQueries } from "@/hooks/use-query-hooks";
import { logAppWarning } from "@/lib/app-logger";
import { getErrorMessage } from "@/lib/error-handler";

import {
  SAVED_BENCHMARK_LIST_LIMIT,
  type SavedBenchmarkRun,
  upsertSavedBenchmarkRun,
} from "@/pages/benchmark/benchmark-storage";
import {
  benchmarkEntriesChanged,
  benchmarkWorkspaceSnapshotChanged,
  buildBenchmarkWorkspaceSnapshotFromSavedRun,
  deleteBenchmarkWorkspaceViewCache,
  hasRestorableBenchmarkWorkspaceSnapshot,
  readBenchmarkWorkspaceViewCache,
} from "@/features/benchmarks/state/normalization";
import { reconcileSavedBenchmarkEntries } from "@/features/benchmarks/state/polling";

export type SavedBenchmarkRunsSetter = Dispatch<SetStateAction<SavedBenchmarkRun[]>>;
export type ReportBenchmarkActionError = (scope: string, title: string, error: unknown) => void;

export async function reconcileSavedBenchmarkRun(
  savedRun: SavedBenchmarkRun,
  options: { refreshActiveRows?: boolean; refreshCompletedRows?: boolean } = {},
): Promise<SavedBenchmarkRun> {
  const refreshedEntries = await reconcileSavedBenchmarkEntries(savedRun.entries, options);
  if (!benchmarkEntriesChanged(savedRun.entries, refreshedEntries)) {
    return savedRun;
  }

  try {
    return await updateBenchmarkRun(savedRun.id, { entries: refreshedEntries });
  } catch (error) {
    logAppWarning("benchmark.reconcile", "Failed to persist refreshed benchmark rows.", {
      benchmarkId: savedRun.id,
      error: getErrorMessage(error),
    });
    return {
      ...savedRun,
      entries: refreshedEntries,
    };
  }
}

export function useSavedBenchmarkCatalog(setSavedBenchmarkRuns: SavedBenchmarkRunsSetter) {
  useEffect(() => {
    let cancelled = false;

    void listBenchmarkRuns({ limit: SAVED_BENCHMARK_LIST_LIMIT, offset: 0 })
      .then((response) => {
        if (!cancelled) {
          setSavedBenchmarkRuns(response.items);
        }
      })
      .catch((error) => {
        logAppWarning("benchmark.catalog", "Failed to load saved benchmark runs.", {
          error: getErrorMessage(error),
        });
      });

    return () => {
      cancelled = true;
    };
  }, [setSavedBenchmarkRuns]);
}

export function useSavedBenchmarkActions({
  activeSavedBenchmarkId,
  selectedSavedBenchmarkId,
  hydrateSavedBenchmark,
  queryClient,
  runGenerationRef,
  stopPolling,
  setSavedBenchmarkLoadError,
  setSavedBenchmarkRuns,
  setActiveSavedBenchmarkId,
  setSelectedSavedBenchmarkId,
  reportActionError,
}: {
  activeSavedBenchmarkId: string | null;
  selectedSavedBenchmarkId: string | null;
  hydrateSavedBenchmark: (savedRun: SavedBenchmarkRun) => void;
  queryClient: QueryClient;
  runGenerationRef: RefObject<number>;
  stopPolling: () => void;
  setSavedBenchmarkLoadError: Dispatch<SetStateAction<string | null>>;
  setSavedBenchmarkRuns: SavedBenchmarkRunsSetter;
  setActiveSavedBenchmarkId: Dispatch<SetStateAction<string | null>>;
  setSelectedSavedBenchmarkId: Dispatch<SetStateAction<string | null>>;
  reportActionError: ReportBenchmarkActionError;
}) {
  const handleLoadSavedBenchmark = useCallback(
    async (savedRunId: string) => {
      try {
        runGenerationRef.current += 1;
        stopPolling();
        const cachedWorkspaceSnapshot = readBenchmarkWorkspaceViewCache(savedRunId);
        const restorableCachedWorkspaceSnapshot = hasRestorableBenchmarkWorkspaceSnapshot(
          cachedWorkspaceSnapshot,
        )
          ? cachedWorkspaceSnapshot
          : null;

        const savedRun = await getBenchmarkRun(savedRunId);
        setSavedBenchmarkLoadError(null);
        setSavedBenchmarkRuns((current) => upsertSavedBenchmarkRun(current, savedRun));
        if (restorableCachedWorkspaceSnapshot === null) {
          hydrateSavedBenchmark(savedRun);
        }

        void reconcileSavedBenchmarkRun(savedRun, {
          refreshActiveRows: restorableCachedWorkspaceSnapshot !== null,
          refreshCompletedRows: true,
        }).then((refreshedRun) => {
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
        });
      } catch (error) {
        reportActionError("benchmark.load-saved", "Failed to load saved benchmark", error);
        throw error;
      }
    },
    [
      hydrateSavedBenchmark,
      reportActionError,
      runGenerationRef,
      setSavedBenchmarkLoadError,
      setSavedBenchmarkRuns,
      stopPolling,
    ],
  );

  const handleDeleteSavedBenchmark = useCallback(
    async (
      savedRunId: string,
      options: {
        deleteAssociatedRuns: boolean;
      } = { deleteAssociatedRuns: false },
    ) => {
      try {
        await deleteBenchmarkRun(savedRunId, options);
        deleteBenchmarkWorkspaceViewCache(savedRunId);
        if (savedRunId === activeSavedBenchmarkId) {
          setActiveSavedBenchmarkId(null);
        }
        if (savedRunId === selectedSavedBenchmarkId) {
          setSelectedSavedBenchmarkId(null);
        }
        setSavedBenchmarkRuns((current) => current.filter((run) => run.id !== savedRunId));
        await invalidateBenchmarkRunQueries(queryClient);
        if (options.deleteAssociatedRuns) {
          await invalidateRunsQueries(queryClient);
        }
      } catch (error) {
        reportActionError("benchmark.delete-saved", "Failed to delete benchmark", error);
        throw error;
      }
    },
    [
      activeSavedBenchmarkId,
      queryClient,
      reportActionError,
      selectedSavedBenchmarkId,
      setActiveSavedBenchmarkId,
      setSavedBenchmarkRuns,
      setSelectedSavedBenchmarkId,
    ],
  );

  return {
    handleLoadSavedBenchmark,
    handleDeleteSavedBenchmark,
  };
}
