/** Benchmark pause/resume actions and their state transitions. */

import type { QueryClient } from "@tanstack/react-query";
import { useCallback, type Dispatch, type RefObject, type SetStateAction } from "react";

import { cancelRun, pauseRun, restartRun, resumeRun } from "@/api/runs";
import { invalidateRunsQueries } from "@/hooks/use-query-hooks";
import { getErrorMessage } from "@/lib/error-handler";

import { acquireMolecule } from "@/pages/benchmark/molecule-acquisition";
import {
  createBenchmarkRunForEntry,
  formatBenchmarkSubmitError,
  getBenchmarkMoleculeBlocker,
  runStatusToEntryStatus,
  shouldPollEntry,
  TERMINAL,
  type BenchmarkBackendMode,
  type BenchmarkEntry,
} from "@/pages/benchmark/benchmark-utils";
import { getRestartTargetRunId } from "@/features/benchmarks/state/normalization";
import {
  hasRunId,
  isPausableBenchmarkEntry,
  isRestartableBenchmarkEntry,
  isRetryableBenchmarkEntry,
  isResumableBenchmarkEntry,
  isCancellableBenchmarkEntry,
} from "@/features/benchmarks/state/selectors";
import type { BenchmarkEntriesSetter } from "@/features/benchmarks/state/polling";

export type BenchmarkPendingAction = "pause" | "resume" | "restart" | "retry" | "cancel" | null;
type BenchmarkActionErrorReporter = (scope: string, title: string, error: unknown) => void;

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

type RetryEntryResult =
  | {
      id: string;
      kind: "restart";
      sourceRunId: string;
      response: Awaited<ReturnType<typeof restartRun>>;
    }
  | {
      id: string;
      kind: "failed";
      moleculeId: string | null;
      errorMessage: string;
    }
  | {
      id: string;
      kind: "submit";
      response: Awaited<ReturnType<typeof createBenchmarkRunForEntry>>;
    };

async function retryOneBenchmarkEntry(
  entry: BenchmarkEntry,
  selectedBasis: string,
  selectedBackendMode: BenchmarkBackendMode,
  resolvedBackendName: string | null,
): Promise<RetryEntryResult> {
  if (entry.runId !== null) {
    return {
      id: entry.id,
      kind: "restart",
      sourceRunId: entry.runId,
      response: await restartRun(entry.runId),
    };
  }

  const blocker = getBenchmarkMoleculeBlocker(entry.preset);
  if (blocker) {
    return { id: entry.id, kind: "failed", moleculeId: null, errorMessage: blocker };
  }

  try {
    const moleculeId = entry.moleculeId ?? (await acquireMolecule(entry.preset)).moleculeId;
    return {
      id: entry.id,
      kind: "submit",
      response: await createBenchmarkRunForEntry(
        entry,
        moleculeId,
        selectedBasis,
        { mode: selectedBackendMode, backendName: resolvedBackendName },
        { clientRequestId: crypto.randomUUID() },
      ),
    };
  } catch (error) {
    return {
      id: entry.id,
      kind: "failed",
      moleculeId: entry.moleculeId,
      errorMessage: formatBenchmarkSubmitError(error),
    };
  }
}

function applyRetryResult(
  entry: BenchmarkEntry,
  result: PromiseSettledResult<RetryEntryResult>,
): BenchmarkEntry {
  if (result.status === "rejected") {
    return {
      ...entry,
      status: "failed",
      errorMessage: getErrorMessage(result.reason, "Failed to retry run. Please try again."),
    };
  }

  if (result.value.kind === "failed") {
    return {
      ...entry,
      status: "failed",
      moleculeId: result.value.moleculeId,
      runId: null,
      errorMessage: result.value.errorMessage,
    };
  }

  if (result.value.kind === "restart") {
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
    moleculeId: result.value.response.moleculeId,
    runId: result.value.response.runId,
    status: result.value.response.status,
    energy: null,
    currentEnergy: null,
    converged: null,
    errorMessage: null,
    elapsedSeconds: null,
    latestEventSequence: 0,
  };
}

export async function pauseBenchmarkEntries({
  entries,
  setEntries,
  setRunning,
  setPendingBenchmarkAction,
  stopPolling,
  targetEntryIds,
}: {
  entries: BenchmarkEntry[];
  setEntries: BenchmarkEntriesSetter;
  setRunning: Dispatch<SetStateAction<boolean>>;
  setPendingBenchmarkAction: Dispatch<SetStateAction<BenchmarkPendingAction>>;
  stopPolling: () => void;
  targetEntryIds?: ReadonlySet<string>;
}) {
  const pausableEntries = entries
    .filter((entry) => targetEntryIds === undefined || targetEntryIds.has(entry.id))
    .filter(isPausableBenchmarkEntry);
  if (pausableEntries.length === 0) return;

  setPendingBenchmarkAction("pause");
  try {
    const pauseResults = await Promise.allSettled(
      pausableEntries.map(async (entry) => ({
        id: entry.id,
        response: await pauseRun(entry.runId),
      })),
    );
    const resultMap = mapSettledResultsByEntryId(pausableEntries, pauseResults);

    setEntries((current) =>
      current.map((entry) => {
        const result = resultMap.get(entry.id);
        if (!result) return entry;

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
      }),
    );

    const nextStatuses = new Map<string, BenchmarkEntry["status"]>(
      pausableEntries.map((entry) => [entry.id, entry.status]),
    );
    for (const [id, result] of resultMap) {
      if (result.status === "fulfilled") {
        nextStatuses.set(id, runStatusToEntryStatus(result.value.response));
      }
    }

    const hasPollableEntries = entries.some((entry) => {
      const nextStatus = nextStatuses.get(entry.id) ?? entry.status;
      return hasRunId(entry) && !TERMINAL.has(nextStatus) && nextStatus !== "paused";
    });
    if (!hasPollableEntries) {
      stopPolling();
      setRunning(false);
    }
  } finally {
    setPendingBenchmarkAction(null);
  }
}

export async function resumeBenchmarkEntries({
  entries,
  selectedSavedBenchmarkId,
  setEntries,
  setRunning,
  setPendingBenchmarkAction,
  setActiveSavedBenchmarkId,
  startPolling,
  stopPolling,
  queryClient,
  targetEntryIds,
}: {
  entries: BenchmarkEntry[];
  selectedSavedBenchmarkId: string | null;
  setEntries: BenchmarkEntriesSetter;
  setRunning: Dispatch<SetStateAction<boolean>>;
  setPendingBenchmarkAction: Dispatch<SetStateAction<BenchmarkPendingAction>>;
  setActiveSavedBenchmarkId: Dispatch<SetStateAction<string | null>>;
  startPolling: (entries?: BenchmarkEntry[]) => void;
  stopPolling: () => void;
  queryClient: QueryClient;
  targetEntryIds?: ReadonlySet<string>;
}) {
  const resumableEntries = entries
    .filter((entry) => targetEntryIds === undefined || targetEntryIds.has(entry.id))
    .filter(isResumableBenchmarkEntry);
  if (resumableEntries.length === 0) return;

  setPendingBenchmarkAction("resume");
  try {
    const resumeResults = await Promise.allSettled(
      resumableEntries.map(async (entry) => ({
        id: entry.id,
        response: await resumeRun(entry.runId),
      })),
    );
    const resultMap = mapSettledResultsByEntryId(resumableEntries, resumeResults);

    const nextEntries: BenchmarkEntry[] = entries.map((entry): BenchmarkEntry => {
      const result = resultMap.get(entry.id);
      if (!result) return entry;

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

    setEntries(nextEntries);
    const hasPollableEntries = nextEntries.some(shouldPollEntry);
    setRunning(hasPollableEntries);
    if (hasPollableEntries) {
      if (selectedSavedBenchmarkId !== null) {
        setActiveSavedBenchmarkId(selectedSavedBenchmarkId);
      }
      startPolling(nextEntries);
    } else {
      stopPolling();
    }

    await invalidateRunsQueries(queryClient);
  } finally {
    setPendingBenchmarkAction(null);
  }
}

export async function restartBenchmarkEntries({
  entries,
  selectedSavedBenchmarkId,
  setEntries,
  setRunning,
  setPendingBenchmarkAction,
  setActiveSavedBenchmarkId,
  startPolling,
  stopPolling,
  queryClient,
  targetEntryIds,
}: {
  entries: BenchmarkEntry[];
  selectedSavedBenchmarkId: string | null;
  setEntries: BenchmarkEntriesSetter;
  setRunning: Dispatch<SetStateAction<boolean>>;
  setPendingBenchmarkAction: Dispatch<SetStateAction<BenchmarkPendingAction>>;
  setActiveSavedBenchmarkId: Dispatch<SetStateAction<string | null>>;
  startPolling: (entries?: BenchmarkEntry[]) => void;
  stopPolling: () => void;
  queryClient: QueryClient;
  targetEntryIds?: ReadonlySet<string>;
}) {
  const restartableEntries = entries
    .filter((entry) => targetEntryIds === undefined || targetEntryIds.has(entry.id))
    .filter(isRestartableBenchmarkEntry);
  if (restartableEntries.length === 0) return;

  setPendingBenchmarkAction("restart");
  try {
    const restartResults = await Promise.allSettled(
      restartableEntries.map(async (entry) => ({
        id: entry.id,
        sourceRunId: entry.runId,
        response: await restartRun(entry.runId),
      })),
    );
    const resultMap = mapSettledResultsByEntryId(restartableEntries, restartResults);

    const nextEntries: BenchmarkEntry[] = entries.map((entry): BenchmarkEntry => {
      const result = resultMap.get(entry.id);
      if (!result) return entry;

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

    setEntries(nextEntries);
    const hasPollableEntries = nextEntries.some(shouldPollEntry);
    setRunning(hasPollableEntries);
    if (hasPollableEntries) {
      if (selectedSavedBenchmarkId !== null) {
        setActiveSavedBenchmarkId(selectedSavedBenchmarkId);
      }
      startPolling(nextEntries);
    } else {
      stopPolling();
    }

    await invalidateRunsQueries(queryClient);
  } finally {
    setPendingBenchmarkAction(null);
  }
}

export async function retryFailedBenchmarkEntries({
  entries,
  selectedSavedBenchmarkId,
  selectedBasis,
  selectedBackendMode,
  resolvedBackendName,
  setEntries,
  setRunning,
  setPendingBenchmarkAction,
  setActiveSavedBenchmarkId,
  startPolling,
  stopPolling,
  queryClient,
  targetEntryIds,
}: {
  entries: BenchmarkEntry[];
  selectedSavedBenchmarkId: string | null;
  selectedBasis: string;
  selectedBackendMode: BenchmarkBackendMode;
  resolvedBackendName: string | null;
  setEntries: BenchmarkEntriesSetter;
  setRunning: Dispatch<SetStateAction<boolean>>;
  setPendingBenchmarkAction: Dispatch<SetStateAction<BenchmarkPendingAction>>;
  setActiveSavedBenchmarkId: Dispatch<SetStateAction<string | null>>;
  startPolling: (entries?: BenchmarkEntry[]) => void;
  stopPolling: () => void;
  queryClient: QueryClient;
  targetEntryIds: ReadonlySet<string>;
}) {
  const retryableEntries = entries
    .filter((entry) => targetEntryIds.has(entry.id))
    .filter(isRetryableBenchmarkEntry);
  if (retryableEntries.length === 0) return;

  setPendingBenchmarkAction("retry");
  setEntries((current) =>
    current.map((entry) =>
      targetEntryIds.has(entry.id) && entry.status === "failed" && entry.runId === null
        ? { ...entry, status: "submitting", errorMessage: null }
        : entry,
    ),
  );

  try {
    const retryResults = await Promise.allSettled(
      retryableEntries.map((entry) =>
        retryOneBenchmarkEntry(entry, selectedBasis, selectedBackendMode, resolvedBackendName),
      ),
    );
    const resultMap = mapSettledResultsByEntryId(retryableEntries, retryResults);

    const nextEntries: BenchmarkEntry[] = entries.map((entry): BenchmarkEntry => {
      const result = resultMap.get(entry.id);
      return result ? applyRetryResult(entry, result) : entry;
    });

    setEntries(nextEntries);
    const hasPollableEntries = nextEntries.some(shouldPollEntry);
    setRunning(hasPollableEntries);
    if (hasPollableEntries) {
      if (selectedSavedBenchmarkId !== null) {
        setActiveSavedBenchmarkId(selectedSavedBenchmarkId);
      }
      startPolling(nextEntries);
    } else {
      stopPolling();
    }

    await invalidateRunsQueries(queryClient);
  } finally {
    setPendingBenchmarkAction(null);
  }
}

export async function cancelSelectedBenchmarkEntries({
  entries,
  selectedSavedBenchmarkId,
  setEntries,
  setRunning,
  setPendingBenchmarkAction,
  setActiveSavedBenchmarkId,
  startPolling,
  stopPolling,
  queryClient,
  targetEntryIds,
}: {
  entries: BenchmarkEntry[];
  selectedSavedBenchmarkId: string | null;
  setEntries: BenchmarkEntriesSetter;
  setRunning: Dispatch<SetStateAction<boolean>>;
  setPendingBenchmarkAction: Dispatch<SetStateAction<BenchmarkPendingAction>>;
  setActiveSavedBenchmarkId: Dispatch<SetStateAction<string | null>>;
  startPolling: (entries?: BenchmarkEntry[]) => void;
  stopPolling: () => void;
  queryClient: QueryClient;
  targetEntryIds: ReadonlySet<string>;
}) {
  const cancellableEntries = entries
    .filter((entry) => targetEntryIds.has(entry.id))
    .filter(isCancellableBenchmarkEntry);
  if (cancellableEntries.length === 0) return;

  setPendingBenchmarkAction("cancel");
  try {
    const cancelResults = await Promise.allSettled(
      cancellableEntries.map(async (entry) => ({
        id: entry.id,
        response: await cancelRun(entry.runId),
      })),
    );
    const resultMap = mapSettledResultsByEntryId(cancellableEntries, cancelResults);

    const nextEntries = entries.map((entry) => {
      const result = resultMap.get(entry.id);
      if (!result) return entry;

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

    setEntries(nextEntries);
    const hasPollableEntries = nextEntries.some(shouldPollEntry);
    setRunning(hasPollableEntries);
    if (hasPollableEntries) {
      if (selectedSavedBenchmarkId !== null) {
        setActiveSavedBenchmarkId(selectedSavedBenchmarkId);
      }
      startPolling(nextEntries);
    } else {
      stopPolling();
    }

    await invalidateRunsQueries(queryClient);
  } finally {
    setPendingBenchmarkAction(null);
  }
}

export function cancelBenchmarkEntries({
  setIbmConfirmationOpen,
  runGenerationRef,
  stopPolling,
  setRunning,
  setEntries,
}: {
  setIbmConfirmationOpen: Dispatch<SetStateAction<boolean>>;
  runGenerationRef: RefObject<number>;
  stopPolling: () => void;
  setRunning: Dispatch<SetStateAction<boolean>>;
  setEntries: BenchmarkEntriesSetter;
}) {
  setIbmConfirmationOpen(false);
  runGenerationRef.current += 1;
  stopPolling();
  setRunning(false);
  setEntries((current) => {
    const runIds = Array.from(
      new Set(current.filter(isCancellableBenchmarkEntry).map((entry) => entry.runId)),
    );
    void Promise.allSettled(runIds.map((runId) => cancelRun(runId)));
    return current.map((entry) =>
      TERMINAL.has(entry.status)
        ? entry
        : {
            ...entry,
            status: "cancelled",
            errorMessage: entry.errorMessage ?? "Benchmark cancelled by user.",
          },
    );
  });
}

export function useBenchmarkControlActions({
  entries,
  selectedSavedBenchmarkId,
  selectedBasis,
  selectedBackendMode,
  resolvedBackendName,
  setEntries,
  setRunning,
  setPendingBenchmarkAction,
  setActiveSavedBenchmarkId,
  startPolling,
  stopPolling,
  queryClient,
  setIbmConfirmationOpen,
  runGenerationRef,
  reportActionError,
}: {
  entries: BenchmarkEntry[];
  selectedSavedBenchmarkId: string | null;
  selectedBasis: string;
  selectedBackendMode: BenchmarkBackendMode;
  resolvedBackendName: string | null;
  setEntries: BenchmarkEntriesSetter;
  setRunning: Dispatch<SetStateAction<boolean>>;
  setPendingBenchmarkAction: Dispatch<SetStateAction<BenchmarkPendingAction>>;
  setActiveSavedBenchmarkId: Dispatch<SetStateAction<string | null>>;
  startPolling: (entries?: BenchmarkEntry[]) => void;
  stopPolling: () => void;
  queryClient: QueryClient;
  setIbmConfirmationOpen: Dispatch<SetStateAction<boolean>>;
  runGenerationRef: RefObject<number>;
  reportActionError: BenchmarkActionErrorReporter;
}) {
  const handleCancelBenchmark = useCallback(() => {
    cancelBenchmarkEntries({
      setIbmConfirmationOpen,
      runGenerationRef,
      stopPolling,
      setRunning,
      setEntries,
    });
  }, [runGenerationRef, setEntries, setIbmConfirmationOpen, setRunning, stopPolling]);

  const pauseBenchmark = useCallback(async () => {
    await pauseBenchmarkEntries({
      entries,
      setEntries,
      setRunning,
      setPendingBenchmarkAction,
      stopPolling,
    });
  }, [entries, setEntries, setPendingBenchmarkAction, setRunning, stopPolling]);

  const handlePauseBenchmark = useCallback(() => {
    void pauseBenchmark().catch((error) => {
      reportActionError("benchmark.pause", "Failed to pause benchmark", error);
    });
  }, [pauseBenchmark, reportActionError]);

  const resumeBenchmark = useCallback(async () => {
    await resumeBenchmarkEntries({
      entries,
      selectedSavedBenchmarkId,
      setEntries,
      setRunning,
      setPendingBenchmarkAction,
      setActiveSavedBenchmarkId,
      startPolling,
      stopPolling,
      queryClient,
    });
  }, [
    entries,
    queryClient,
    selectedSavedBenchmarkId,
    setEntries,
    setActiveSavedBenchmarkId,
    setPendingBenchmarkAction,
    setRunning,
    startPolling,
    stopPolling,
  ]);

  const handleResumeBenchmark = useCallback(() => {
    void resumeBenchmark().catch((error) => {
      reportActionError("benchmark.resume", "Failed to resume benchmark", error);
    });
  }, [reportActionError, resumeBenchmark]);

  const restartBenchmark = useCallback(async () => {
    await restartBenchmarkEntries({
      entries,
      selectedSavedBenchmarkId,
      setEntries,
      setRunning,
      setPendingBenchmarkAction,
      setActiveSavedBenchmarkId,
      startPolling,
      stopPolling,
      queryClient,
    });
  }, [
    entries,
    queryClient,
    selectedSavedBenchmarkId,
    setEntries,
    setActiveSavedBenchmarkId,
    setPendingBenchmarkAction,
    setRunning,
    startPolling,
    stopPolling,
  ]);

  const handleRestartBenchmark = useCallback(async () => {
    try {
      await restartBenchmark();
    } catch (error) {
      reportActionError("benchmark.restart", "Failed to restart benchmark", error);
      throw error;
    }
  }, [reportActionError, restartBenchmark]);

  const handleBenchmarkEntryAction = useCallback(
    async (entry: BenchmarkEntry, action: "pause" | "resume" | "restart" | "retry" | "cancel") => {
      const targetEntryIds = new Set([entry.id]);

      try {
        if (action === "pause") {
          await pauseBenchmarkEntries({
            entries,
            setEntries,
            setRunning,
            setPendingBenchmarkAction,
            stopPolling,
            targetEntryIds,
          });
          return;
        }

        if (action === "resume") {
          await resumeBenchmarkEntries({
            entries,
            selectedSavedBenchmarkId,
            setEntries,
            setRunning,
            setPendingBenchmarkAction,
            setActiveSavedBenchmarkId,
            startPolling,
            stopPolling,
            queryClient,
            targetEntryIds,
          });
          return;
        }

        if (action === "restart") {
          await restartBenchmarkEntries({
            entries,
            selectedSavedBenchmarkId,
            setEntries,
            setRunning,
            setPendingBenchmarkAction,
            setActiveSavedBenchmarkId,
            startPolling,
            stopPolling,
            queryClient,
            targetEntryIds,
          });
          return;
        }

        if (action === "retry") {
          await retryFailedBenchmarkEntries({
            entries,
            selectedSavedBenchmarkId,
            selectedBasis,
            selectedBackendMode,
            resolvedBackendName,
            setEntries,
            setRunning,
            setPendingBenchmarkAction,
            setActiveSavedBenchmarkId,
            startPolling,
            stopPolling,
            queryClient,
            targetEntryIds,
          });
          return;
        }

        await cancelSelectedBenchmarkEntries({
          entries,
          selectedSavedBenchmarkId,
          setEntries,
          setRunning,
          setPendingBenchmarkAction,
          setActiveSavedBenchmarkId,
          startPolling,
          stopPolling,
          queryClient,
          targetEntryIds,
        });
      } catch (error) {
        reportActionError(
          "benchmark.entry." + action,
          "Failed to " + action + " benchmark row",
          error,
        );
        throw error;
      }
    },
    [
      entries,
      queryClient,
      reportActionError,
      resolvedBackendName,
      setActiveSavedBenchmarkId,
      selectedBackendMode,
      selectedBasis,
      selectedSavedBenchmarkId,
      setEntries,
      setPendingBenchmarkAction,
      setRunning,
      startPolling,
      stopPolling,
    ],
  );

  return {
    handleCancelBenchmark,
    handlePauseBenchmark,
    handleResumeBenchmark,
    handleRestartBenchmark,
    handleBenchmarkEntryAction,
  };
}
