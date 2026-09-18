import {
  useCallback,
  useEffect,
  useRef,
  type Dispatch,
  type RefObject,
  type SetStateAction,
} from "react";

import { getRun, getRunEvents, getRunResult } from "@/api/runs";
import { runtimeSecondsFromEvents, runtimeSecondsFromRun } from "@/lib/run-runtime";
import type { RunResultResponse } from "@/types/run";

import {
  applyEntryUpdates,
  extractClassicalRefs,
  extractClassicalRefsFromEvents,
  extractRunErrorMessage,
  normalizeStoredEntry,
  POLL_INTERVAL_MS,
  runStatusToEntryStatus,
  shouldPollBenchmarkEntryNow,
  shouldPollEntry,
  shouldSyncBenchmarkEntryEvents,
  type BenchmarkEntry,
  type BenchmarkEntryUpdate,
  type BenchmarkEntryWithRunId,
} from "@/pages/benchmark/benchmark-utils";
import { latestEnergyFromEvents } from "@/features/benchmarks/state/normalization";

export type BenchmarkEntriesSetter = Dispatch<SetStateAction<BenchmarkEntry[]>>;

type PolledEntryState = Pick<
  BenchmarkEntry,
  | "energy"
  | "currentEnergy"
  | "converged"
  | "classicalRefs"
  | "errorMessage"
  | "elapsedSeconds"
  | "latestEventSequence"
>;

async function syncBenchmarkEntryEvents(
  entry: BenchmarkEntryWithRunId,
  run: Awaited<ReturnType<typeof getRun>>,
) {
  let currentEnergy: number | null = entry.currentEnergy;
  let classicalRefs: { hf: number; fci: number } | null = entry.classicalRefs;
  let latestEventSequence = entry.latestEventSequence ?? 0;
  let elapsedSeconds = runtimeSecondsFromRun(run) ?? entry.elapsedSeconds;

  try {
    const events = await getRunEvents(entry.runId, latestEventSequence);
    latestEventSequence = events.last_sequence;
    currentEnergy = latestEnergyFromEvents(events.events) ?? currentEnergy;
    classicalRefs = extractClassicalRefsFromEvents(events.events) ?? classicalRefs;
    elapsedSeconds =
      runtimeSecondsFromEvents(run, events.events) ?? elapsedSeconds ?? entry.elapsedSeconds;
  } catch {
    // Progress events can lag or fail independently of run status polling.
  }

  return {
    currentEnergy,
    classicalRefs,
    latestEventSequence,
    elapsedSeconds,
  };
}

async function syncCompletedBenchmarkEntryResult(
  entry: BenchmarkEntryWithRunId,
  run: Awaited<ReturnType<typeof getRun>>,
  nextEntry: PolledEntryState,
) {
  let result: RunResultResponse;
  try {
    result = await getRunResult(entry.runId);
  } catch {
    // Result can lag behind run completion.
    return nextEntry;
  }

  const resultEntry = {
    ...nextEntry,
    energy: result.energy,
    currentEnergy: result.energy,
    converged: result.converged,
    classicalRefs: extractClassicalRefs(result.algorithm_metrics) ?? nextEntry.classicalRefs,
  };

  if (resultEntry.classicalRefs !== null) return resultEntry;

  try {
    const eventState = await syncBenchmarkEntryEvents(entry, run);
    return {
      ...resultEntry,
      currentEnergy: eventState.currentEnergy,
      classicalRefs: eventState.classicalRefs,
      latestEventSequence: eventState.latestEventSequence,
      elapsedSeconds: eventState.elapsedSeconds,
    };
  } catch {
    // Progress events can fail after the terminal result is available.
    return resultEntry;
  }
}

export async function buildBenchmarkEntryUpdate(
  entry: BenchmarkEntryWithRunId,
): Promise<BenchmarkEntryUpdate> {
  const run = await getRun(entry.runId);
  const status = runStatusToEntryStatus(run);
  const eventState = shouldSyncBenchmarkEntryEvents(status)
    ? await syncBenchmarkEntryEvents(entry, run)
    : {
        currentEnergy: entry.currentEnergy,
        classicalRefs: entry.classicalRefs,
        latestEventSequence: entry.latestEventSequence,
        elapsedSeconds: runtimeSecondsFromRun(run) ?? entry.elapsedSeconds,
      };
  let nextEntry = {
    energy: entry.energy,
    currentEnergy: eventState.currentEnergy,
    converged: entry.converged,
    classicalRefs: eventState.classicalRefs,
    errorMessage: status === "cancelled" ? entry.errorMessage : null,
    elapsedSeconds: eventState.elapsedSeconds,
    latestEventSequence: eventState.latestEventSequence,
  };

  if (status === "completed") {
    nextEntry = await syncCompletedBenchmarkEntryResult(entry, run, nextEntry);
  }
  if (status === "failed") {
    nextEntry = {
      ...nextEntry,
      errorMessage: extractRunErrorMessage(run) ?? entry.errorMessage,
    };
  }

  return {
    id: entry.id,
    status,
    ...nextEntry,
  };
}

export async function reconcileSavedBenchmarkEntries(
  entries: BenchmarkEntry[],
  options: { refreshActiveRows?: boolean; refreshCompletedRows?: boolean } = {},
): Promise<BenchmarkEntry[]> {
  const normalizedEntries = entries.map(normalizeStoredEntry);
  const refreshableEntries = normalizedEntries.filter(
    (entry): entry is BenchmarkEntryWithRunId =>
      entry.runId !== null &&
      (entry.status === "failed" ||
        ((options.refreshCompletedRows ?? false) && entry.status === "completed") ||
        ((options.refreshActiveRows ?? false) && shouldPollEntry(entry))),
  );

  if (refreshableEntries.length === 0) {
    return normalizedEntries;
  }

  const updates = await Promise.allSettled(refreshableEntries.map(buildBenchmarkEntryUpdate));
  return applyEntryUpdates(normalizedEntries, updates);
}

export function useBenchmarkPollingController({
  restoredEntries,
  runGenerationRef,
  setEntries,
  setRunning,
}: {
  restoredEntries: BenchmarkEntry[];
  runGenerationRef: RefObject<number>;
  setEntries: BenchmarkEntriesSetter;
  setRunning: Dispatch<SetStateAction<boolean>>;
}) {
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollInFlightRef = useRef(false);
  const pollCycleRef = useRef(0);

  const stopPolling = useCallback(() => {
    if (pollingRef.current !== null) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  const stopPollingIfIdle = useCallback(
    (activeEntries: BenchmarkEntry[], generation: number) => {
      if (activeEntries.length > 0) return false;
      stopPolling();
      if (runGenerationRef.current === generation) {
        setRunning(false);
      }
      return true;
    },
    [runGenerationRef, setRunning, stopPolling],
  );

  const pollEntries = useCallback(
    async (current: BenchmarkEntry[], pollCycle: number) => {
      if (pollInFlightRef.current) return;

      pollInFlightRef.current = true;
      const generation = runGenerationRef.current;

      try {
        const active = current.filter(shouldPollEntry);
        if (stopPollingIfIdle(active, generation)) return;
        const dueEntries = active.filter((entry) => shouldPollBenchmarkEntryNow(entry, pollCycle));
        if (dueEntries.length === 0) return;

        const updates = await Promise.allSettled(dueEntries.map(buildBenchmarkEntryUpdate));

        setEntries((previous) =>
          runGenerationRef.current === generation ? applyEntryUpdates(previous, updates) : previous,
        );
      } finally {
        pollInFlightRef.current = false;
      }
    },
    [runGenerationRef, setEntries, stopPollingIfIdle],
  );

  const startPolling = useCallback(
    (immediateEntries?: BenchmarkEntry[]) => {
      stopPolling();
      pollCycleRef.current = 0;
      if (immediateEntries) {
        void pollEntries(immediateEntries, pollCycleRef.current);
      }
      pollingRef.current = setInterval(() => {
        pollCycleRef.current += 1;
        setEntries((current) => {
          void pollEntries(current, pollCycleRef.current);
          return current;
        });
      }, POLL_INTERVAL_MS);
    },
    [pollEntries, setEntries, stopPolling],
  );

  useEffect(() => {
    return () => {
      stopPolling();
    };
  }, [stopPolling]);

  useEffect(() => {
    if (!restoredEntries.some(shouldPollEntry)) return;
    startPolling(restoredEntries);
  }, [restoredEntries, startPolling]);

  return { startPolling, stopPolling };
}
