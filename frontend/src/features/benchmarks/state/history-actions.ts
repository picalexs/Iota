import type { QueryClient } from "@tanstack/react-query";
import {
  deleteBenchmarkRun,
  updateBenchmarkRun,
  type BenchmarkRunListResponse,
} from "@/api/benchmarks";
import { cancelRun, pauseRun, restartRun, resumeRun } from "@/api/runs";
import { benchmarkKeys } from "@/hooks/query-keys";
import { getErrorMessage } from "@/lib/error-handler";
import type { SavedBenchmarkRun } from "@/pages/benchmark/benchmark-storage";
import { getRestartTargetRunId } from "@/features/benchmarks/state/normalization";
import {
  isCancellableBenchmarkEntry,
  isPausedBenchmarkEntry,
  isPausableBenchmarkEntry,
} from "@/features/benchmarks/state/selectors";
import { runStatusToEntryStatus } from "@/pages/benchmark/benchmark-utils";

export type BenchmarkExecutableAction = "pause" | "resume" | "restart" | "cancel";
export type BenchmarkDeleteProgress = { completed: number; total: number };
export type BenchmarkActionResult = {
  updatedRun: SavedBenchmarkRun;
  hadEntryFailures: boolean;
};
export type BenchmarkActionBatchResult = {
  readonly results: PromiseSettledResult<BenchmarkActionResult>[];
  readonly updatedRuns: SavedBenchmarkRun[];
  readonly failedIds: string[];
  readonly partialIds: string[];
};
export type BenchmarkDeleteBatchResult = {
  readonly results: PromiseSettledResult<string>[];
  readonly failedIds: string[];
  readonly deletedIds: string[];
};

export function buildDeleteBenchmarksSummary(
  results: PromiseSettledResult<string>[],
  failedIds: string[],
): string {
  const firstError = getErrorMessage(
    results.find((result) => result.status === "rejected")?.reason,
    "Failed to delete benchmarks.",
  );

  if (failedIds.length === 0) {
    return firstError;
  }

  const deletedCount = results.length - failedIds.length;
  if (deletedCount === 0) {
    return firstError;
  }

  const benchmarkLabel = deletedCount === 1 ? "benchmark" : "benchmarks";
  return `Deleted ${deletedCount} ${benchmarkLabel}, ${failedIds.length} failed. ${firstError}`;
}

const BULK_ACTION_PAST_TENSE = {
  pause: "Paused",
  resume: "Resumed",
  restart: "Restarted",
  cancel: "Cancelled",
} as const;

export function buildBenchmarkActionSummary(
  action: BenchmarkExecutableAction,
  targetCount: number,
  failedCount: number,
  partialCount: number,
  firstError?: unknown,
): string | null {
  if (failedCount === 0 && partialCount === 0) {
    return null;
  }

  const completedCount = targetCount - failedCount;
  const completedLabel = completedCount === 1 ? "benchmark" : "benchmarks";
  if (failedCount === 0) {
    const pendingLabel =
      partialCount === 1 ? "selection still needs attention" : "selections still need attention";
    return `${BULK_ACTION_PAST_TENSE[action]} ${completedCount} ${completedLabel}, but ${partialCount} ${pendingLabel}. Some row actions failed.`;
  }

  return `${BULK_ACTION_PAST_TENSE[action]} ${completedCount} ${completedLabel}, ${failedCount} failed. ${getErrorMessage(
    firstError,
    `Failed to ${action} selected benchmarks.`,
  )}`;
}

function getBenchmarkActionPerformer(
  action: BenchmarkExecutableAction,
): (savedRun: SavedBenchmarkRun) => Promise<BenchmarkActionResult> {
  switch (action) {
    case "pause":
      return pauseSavedBenchmarkRun;
    case "resume":
      return resumeSavedBenchmarkRun;
    case "restart":
      return restartSavedBenchmarkRun;
    case "cancel":
      return cancelSavedBenchmarkRun;
  }
}

function mapSettledResultsByEntryId<T>(
  entries: readonly { readonly id: string }[],
  results: readonly PromiseSettledResult<T>[],
): Map<string, PromiseSettledResult<T>> {
  return new Map(
    results.flatMap((result, index) => {
      const entry = entries[index];
      return entry ? [[entry.id, result] as const] : [];
    }),
  );
}

export function updateSavedBenchmarksInCache(
  queryClient: QueryClient,
  updatedRuns: readonly SavedBenchmarkRun[],
) {
  const updatedById = new Map(updatedRuns.map((run) => [run.id, run]));
  queryClient.setQueriesData<BenchmarkRunListResponse>(
    { queryKey: benchmarkKeys.listPrefix },
    (current) => {
      if (!current) {
        return current;
      }

      return {
        ...current,
        items: current.items.map((run) => updatedById.get(run.id) ?? run),
      };
    },
  );
}

export function removeSavedBenchmarksFromCache(
  queryClient: QueryClient,
  removedIds: readonly string[],
) {
  const removedIdSet = new Set(removedIds);
  queryClient.setQueriesData<BenchmarkRunListResponse>(
    { queryKey: benchmarkKeys.listPrefix },
    (current) => {
      if (!current) {
        return current;
      }

      const items = current.items.filter((run) => !removedIdSet.has(run.id));
      return {
        ...current,
        items,
        total: Math.max(0, current.total - removedIds.length),
      };
    },
  );
}

export async function runDeleteSelectedBenchmarksBatch(
  selectedRuns: readonly SavedBenchmarkRun[],
  deleteAssociatedRuns: boolean,
  setDeleteProgress: (progress: BenchmarkDeleteProgress) => void,
): Promise<BenchmarkDeleteBatchResult> {
  const results: PromiseSettledResult<string>[] = [];

  for (const [index, run] of selectedRuns.entries()) {
    try {
      await deleteBenchmarkRun(run.id, { deleteAssociatedRuns });
      results.push({ status: "fulfilled", value: run.id });
    } catch (actionError) {
      results.push({ status: "rejected", reason: actionError });
    } finally {
      setDeleteProgress({ completed: index + 1, total: selectedRuns.length });
    }
  }

  const failedIds = results.flatMap((result, index) => {
    const selectedRun = selectedRuns[index];
    return result.status === "rejected" && selectedRun ? [selectedRun.id] : [];
  });
  const failedIdSet = new Set(failedIds);
  const deletedIds = selectedRuns.map((run) => run.id).filter((runId) => !failedIdSet.has(runId));

  return { results, failedIds, deletedIds };
}

export function getSkippedSelectedBenchmarkIds(
  selectedRuns: readonly SavedBenchmarkRun[],
  eligibleRuns: readonly SavedBenchmarkRun[],
): string[] {
  const eligibleRunIds = new Set(eligibleRuns.map((run) => run.id));
  return selectedRuns.filter((run) => !eligibleRunIds.has(run.id)).map((run) => run.id);
}

export async function runSelectedBenchmarkActionBatch(
  action: BenchmarkExecutableAction,
  eligibleRuns: readonly SavedBenchmarkRun[],
): Promise<BenchmarkActionBatchResult> {
  const performer = getBenchmarkActionPerformer(action);
  const results = await Promise.allSettled(eligibleRuns.map((run) => performer(run)));
  const updatedRuns = results.flatMap((result) =>
    result.status === "fulfilled" ? [result.value.updatedRun] : [],
  );
  const failedIds = results.flatMap((result, index) => {
    const eligibleRun = eligibleRuns[index];
    return result.status === "rejected" && eligibleRun ? [eligibleRun.id] : [];
  });
  const partialIds = results.flatMap((result, index) => {
    const eligibleRun = eligibleRuns[index];
    return result.status === "fulfilled" && result.value.hadEntryFailures && eligibleRun
      ? [eligibleRun.id]
      : [];
  });

  return { results, updatedRuns, failedIds, partialIds };
}

async function pauseSavedBenchmarkRun(savedRun: SavedBenchmarkRun): Promise<BenchmarkActionResult> {
  const pausableEntries = savedRun.entries.filter(isPausableBenchmarkEntry);
  const pauseResults = await Promise.allSettled(
    pausableEntries.map(async (entry) => ({
      id: entry.id,
      response: await pauseRun(entry.runId),
    })),
  );
  const resultMap = mapSettledResultsByEntryId(pausableEntries, pauseResults);

  const nextEntries = savedRun.entries.map((entry) => {
    const result = resultMap.get(entry.id);
    if (!result) {
      return entry;
    }

    if (result.status === "fulfilled") {
      return {
        ...entry,
        status: runStatusToEntryStatus(result.value.response),
        errorMessage: null,
      };
    }

    return {
      ...entry,
      errorMessage: getErrorMessage(result.reason, "Failed to pause run. Please try again."),
    };
  });

  return {
    updatedRun: await updateBenchmarkRun(savedRun.id, { entries: nextEntries }),
    hadEntryFailures: pauseResults.some((result) => result.status === "rejected"),
  };
}

async function resumeSavedBenchmarkRun(
  savedRun: SavedBenchmarkRun,
): Promise<BenchmarkActionResult> {
  const resumableEntries = savedRun.entries.filter(isPausedBenchmarkEntry);
  const resumeResults = await Promise.allSettled(
    resumableEntries.map(async (entry) => ({
      id: entry.id,
      response: await resumeRun(entry.runId),
    })),
  );
  const resultMap = mapSettledResultsByEntryId(resumableEntries, resumeResults);

  const nextEntries = savedRun.entries.map((entry) => {
    const result = resultMap.get(entry.id);
    if (!result) {
      return entry;
    }

    if (result.status === "fulfilled") {
      return {
        ...entry,
        status: runStatusToEntryStatus(result.value.response),
        errorMessage: null,
      };
    }

    return {
      ...entry,
      errorMessage: getErrorMessage(result.reason, "Failed to resume run. Please try again."),
    };
  });

  return {
    updatedRun: await updateBenchmarkRun(savedRun.id, { entries: nextEntries }),
    hadEntryFailures: resumeResults.some((result) => result.status === "rejected"),
  };
}

async function restartSavedBenchmarkRun(
  savedRun: SavedBenchmarkRun,
): Promise<BenchmarkActionResult> {
  const restartableEntries = savedRun.entries.filter(isPausedBenchmarkEntry);
  const restartResults = await Promise.allSettled(
    restartableEntries.map(async (entry) => ({
      id: entry.id,
      sourceRunId: entry.runId,
      response: await restartRun(entry.runId),
    })),
  );
  const resultMap = mapSettledResultsByEntryId(restartableEntries, restartResults);

  const nextEntries = savedRun.entries.map((entry) => {
    const result = resultMap.get(entry.id);
    if (!result) {
      return entry;
    }

    if (result.status === "fulfilled") {
      const targetRunId = getRestartTargetRunId(result.value.response, result.value.sourceRunId);
      const targetStatus =
        targetRunId === result.value.sourceRunId
          ? runStatusToEntryStatus(result.value.response)
          : "queued";

      return {
        ...entry,
        runId: targetRunId,
        status: targetStatus,
        energy: null,
        currentEnergy: null,
        converged: null,
        errorMessage: null,
        elapsedSeconds: null,
        latestEventSequence: 0,
      };
    }

    return {
      ...entry,
      errorMessage: getErrorMessage(result.reason, "Failed to restart run. Please try again."),
    };
  });

  return {
    updatedRun: await updateBenchmarkRun(savedRun.id, { entries: nextEntries }),
    hadEntryFailures: restartResults.some((result) => result.status === "rejected"),
  };
}

async function cancelSavedBenchmarkRun(
  savedRun: SavedBenchmarkRun,
): Promise<BenchmarkActionResult> {
  const cancellableEntries = savedRun.entries.filter(isCancellableBenchmarkEntry);
  const cancelResults = await Promise.allSettled(
    cancellableEntries.map(async (entry) => ({
      id: entry.id,
      response: await cancelRun(entry.runId),
    })),
  );
  const resultMap = mapSettledResultsByEntryId(cancellableEntries, cancelResults);

  const nextEntries = savedRun.entries.map((entry) => {
    const result = resultMap.get(entry.id);
    if (!result) {
      return entry;
    }

    if (result.status === "fulfilled") {
      return {
        ...entry,
        status: runStatusToEntryStatus(result.value.response),
        errorMessage: null,
      };
    }

    return {
      ...entry,
      errorMessage: getErrorMessage(result.reason, "Failed to cancel run. Please try again."),
    };
  });

  return {
    updatedRun: await updateBenchmarkRun(savedRun.id, { entries: nextEntries }),
    hadEntryFailures: cancelResults.some((result) => result.status === "rejected"),
  };
}
