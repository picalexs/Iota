import { useCallback, useEffect, useRef, useState } from "react";
import type { Dispatch, RefObject, SetStateAction } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { getRun, getRunEvents, getRunResult } from "@/api/runs";
import { subscribeToRunEvents } from "@/api/sse";
import { logAppError } from "@/lib/app-logger";
import { showErrorToast } from "@/lib/error-handler";
import { isRunStreaming } from "@/lib/run-status-display";
import { runKeys } from "@/hooks/query-keys";
import { isRunStatus } from "@/types/run";
import type {
  RunEventResponse,
  RunListResponse,
  RunResponse,
  RunResultResponse,
  RunSummaryListResponse,
  RunSummaryResponse,
} from "@/types/run";
import { toRunEstimate } from "./use-run-event-timeline";

const SSE_RETRY_DELAYS_MS = [1000, 2000, 5000, 10000] as const;
type TimeoutId = ReturnType<typeof globalThis.setTimeout>;

export const TERMINAL_STATUSES = new Set<RunResponse["status"]>([
  "COMPLETED",
  "FAILED",
  "CANCELLED",
  "EXCLUDED",
  "PAUSED",
]);

function toRunSummary(run: RunResponse): RunSummaryResponse {
  const backendName = run.config_json.backend_options?.backend_name;
  return {
    id: run.id,
    molecule_id: run.molecule_id,
    status: run.status,
    algorithm: run.algorithm,
    backend_target: run.backend_target,
    backend_name: typeof backendName === "string" && backendName.trim() ? backendName : null,
    credential_profile_name: run.credential_profile_name ?? null,
    metadata: run.metadata,
    latest_estimate: run.latest_estimate,
    created_at: run.created_at,
    updated_at: run.updated_at,
  };
}

function isRunListResponse(value: unknown): value is RunListResponse {
  return (
    typeof value === "object" &&
    value !== null &&
    "items" in value &&
    Array.isArray((value as { items?: unknown }).items)
  );
}

function isRunSummaryListResponse(value: unknown): value is RunSummaryListResponse {
  return isRunListResponse(value);
}

function updateRunInList(current: unknown, run: RunResponse): unknown {
  if (!isRunListResponse(current)) {
    return current;
  }

  return {
    ...current,
    items: current.items.map((item) => (item.id === run.id ? { ...item, ...run } : item)),
  };
}

function updateRunSummaryCache(current: unknown, run: RunResponse): unknown {
  const nextSummary = toRunSummary(run);

  if (Array.isArray(current)) {
    return current.map((item) =>
      typeof item === "object" && item !== null && "id" in item && item.id === run.id
        ? { ...item, ...nextSummary }
        : item,
    );
  }

  if (!isRunSummaryListResponse(current)) {
    return current;
  }

  return {
    ...current,
    items: current.items.map((item) => (item.id === run.id ? { ...item, ...nextSummary } : item)),
  };
}

function retryDelayForFailure(failureCount: number): number {
  return (
    SSE_RETRY_DELAYS_MS[Math.min(failureCount - 1, SSE_RETRY_DELAYS_MS.length - 1)] ??
    SSE_RETRY_DELAYS_MS[SSE_RETRY_DELAYS_MS.length - 1] ??
    0
  );
}

function scheduleReconnectRetry(
  retryDelay: number,
  isActive: () => boolean,
  setSseRetryToken: Dispatch<SetStateAction<number>>,
): TimeoutId {
  return globalThis.setTimeout(() => {
    if (isActive()) {
      setSseRetryToken((value) => value + 1);
    }
  }, retryDelay);
}

function addSeenEvent(event: RunEventResponse, seenSequences: RefObject<Set<number>>): boolean {
  if (seenSequences.current.has(event.sequence)) {
    return false;
  }

  seenSequences.current.add(event.sequence);
  return true;
}

function statusFromEvent(event: RunEventResponse): RunResponse["status"] | null {
  if (event.type !== "status_changed") {
    return null;
  }

  const nextStatus = event.payload.status;
  return isRunStatus(nextStatus) ? nextStatus : null;
}

function applyRunEvent(run: RunResponse | null, event: RunEventResponse): RunResponse | null {
  if (run === null) {
    return run;
  }

  const nextRun = { ...run, updated_at: event.created_at };
  const nextStatus = statusFromEvent(event);
  if (nextStatus !== null) {
    nextRun.status = nextStatus;
  }

  if (event.type !== "estimate_updated") {
    return nextRun;
  }

  const estimate = toRunEstimate(event.payload);
  return estimate === null ? nextRun : { ...nextRun, latest_estimate: estimate };
}

interface UseRunSseSubscriptionParams {
  runId: string;
  run: RunResponse | null;
  setRun: Dispatch<SetStateAction<RunResponse | null>>;
  setResult: Dispatch<SetStateAction<RunResultResponse | null>>;
  setEvents: Dispatch<SetStateAction<RunEventResponse[]>>;
  lastSequenceRef: RefObject<number>;
  seenSequencesRef: RefObject<Set<number>>;
}

export function useRunSseSubscription({
  runId,
  run,
  setRun,
  setResult,
  setEvents,
  lastSequenceRef,
  seenSequencesRef,
}: UseRunSseSubscriptionParams) {
  const queryClient = useQueryClient();
  const [sseDisconnected, setSseDisconnected] = useState(false);
  const [sseRetryToken, setSseRetryToken] = useState(0);
  const [terminalRefreshCycle, setTerminalRefreshCycle] = useState(0);
  const sseFailureCountRef = useRef(0);
  const previousTerminalRef = useRef(false);

  const resetSseSubscriptionState = useCallback(() => {
    setSseDisconnected(false);
    setSseRetryToken(0);
    setTerminalRefreshCycle(0);
    sseFailureCountRef.current = 0;
    previousTerminalRef.current = false;
  }, []);

  const appendEvents = useCallback(
    (incomingEvents: RunEventResponse[]) => {
      const newEvents = incomingEvents.filter(
        (event) => !seenSequencesRef.current.has(event.sequence),
      );
      for (const event of newEvents) {
        seenSequencesRef.current.add(event.sequence);
      }
      if (newEvents.length > 0) {
        setEvents((previousEvents) => [...previousEvents, ...newEvents]);
      }
    },
    [seenSequencesRef, setEvents],
  );

  const refreshTerminalData = useCallback(async () => {
    try {
      const freshRun = await getRun(runId);
      const [freshResult, eventsResponse] = await Promise.all([
        freshRun.status === "COMPLETED"
          ? getRunResult(runId).catch(() => null)
          : Promise.resolve(null),
        getRunEvents(
          runId,
          lastSequenceRef.current > 0 ? lastSequenceRef.current : undefined,
        ).catch(() => null),
      ]);

      setRun(freshRun);
      if (eventsResponse?.events.length) {
        appendEvents(eventsResponse.events);
        lastSequenceRef.current = Math.max(lastSequenceRef.current, eventsResponse.last_sequence);
      }
      setResult(freshRun.status === "COMPLETED" ? freshResult : null);
    } catch {
      // Best effort refresh; keep existing UI state if this fetch fails.
    }
  }, [appendEvents, lastSequenceRef, runId, setResult, setRun]);

  const syncLiveData = useCallback(async () => {
    try {
      const [latestRun, eventsResponse] = await Promise.all([
        getRun(runId),
        getRunEvents(runId, lastSequenceRef.current > 0 ? lastSequenceRef.current : undefined),
      ]);

      setRun(latestRun);

      if (eventsResponse.events.length > 0) {
        appendEvents(eventsResponse.events);
      }

      lastSequenceRef.current = Math.max(lastSequenceRef.current, eventsResponse.last_sequence);

      if (TERMINAL_STATUSES.has(latestRun.status)) {
        setSseDisconnected(false);
      }
    } catch {
      // Keep the current UI state and try again on the next tick.
    }
  }, [appendEvents, lastSequenceRef, runId, setRun]);

  const handleRunEvent = useCallback(
    (event: RunEventResponse) => {
      setSseDisconnected(false);
      sseFailureCountRef.current = 0;

      if (addSeenEvent(event, seenSequencesRef)) {
        setEvents((previousEvents) => [...previousEvents, event]);
      }

      lastSequenceRef.current = event.sequence;
      setRun((previousRun) => applyRunEvent(previousRun, event));
    },
    [lastSequenceRef, seenSequencesRef, setEvents, setRun],
  );

  const isTerminal = run !== null && TERMINAL_STATUSES.has(run.status);
  const shouldSubscribeToSSE = run !== null && isRunStreaming(run.status);

  useEffect(() => {
    if (!shouldSubscribeToSSE) return;

    let isActive = true;
    let retryTimeoutId: TimeoutId | null = null;

    const handleStreamError = (error: unknown) => {
      if (!isActive) {
        return;
      }

      setSseDisconnected(true);
      const failureCount = ++sseFailureCountRef.current;
      const retryDelay = retryDelayForFailure(failureCount);
      logAppError("run-detail.sse", "Live updates stream disconnected.", error, {
        runId,
        failureCount,
        retryDelayMs: retryDelay,
        lastSequence: lastSequenceRef.current,
      });

      if (failureCount >= 3) {
        showErrorToast(error, {
          title: "Live updates interrupted. Keeping the page in sync in the background.",
          description: null,
        });
      }

      retryTimeoutId = scheduleReconnectRetry(retryDelay, () => isActive, setSseRetryToken);
    };

    const controller = subscribeToRunEvents(
      runId,
      handleRunEvent,
      lastSequenceRef.current > 0 ? lastSequenceRef.current : undefined,
      handleStreamError,
    );

    return () => {
      isActive = false;
      controller.abort();
      if (retryTimeoutId !== null) {
        globalThis.clearTimeout(retryTimeoutId);
      }
    };
  }, [lastSequenceRef, handleRunEvent, runId, shouldSubscribeToSSE, sseRetryToken]);

  useEffect(() => {
    if (!shouldSubscribeToSSE) {
      return;
    }

    const intervalId = globalThis.setInterval(() => {
      void syncLiveData();
    }, 2000);

    return () => globalThis.clearInterval(intervalId);
  }, [shouldSubscribeToSSE, syncLiveData]);

  useEffect(() => {
    if (!run) {
      return;
    }

    queryClient.setQueryData(runKeys.detail(runId), run);
    queryClient.setQueriesData(
      { queryKey: runKeys.listPrefix },
      (current: RunListResponse | undefined) => updateRunInList(current, run) as typeof current,
    );
    queryClient.setQueriesData(
      { queryKey: runKeys.summariesPrefix },
      (current: RunSummaryListResponse | RunSummaryResponse[] | undefined) =>
        updateRunSummaryCache(current, run) as typeof current,
    );

    const nowTerminal = TERMINAL_STATUSES.has(run.status);
    if (nowTerminal && !previousTerminalRef.current) {
      setTerminalRefreshCycle((value) => value + 1);
      void refreshTerminalData();
    }
    previousTerminalRef.current = nowTerminal;
  }, [queryClient, refreshTerminalData, run, runId]);

  useEffect(() => {
    if (terminalRefreshCycle === 0) {
      return;
    }

    let attempts = 0;
    const intervalId = globalThis.setInterval(() => {
      attempts += 1;
      void refreshTerminalData();

      if (attempts >= 3) {
        globalThis.clearInterval(intervalId);
      }
    }, 1000);

    return () => globalThis.clearInterval(intervalId);
  }, [refreshTerminalData, terminalRefreshCycle]);

  return {
    isTerminal,
    shouldSubscribeToSSE,
    sseDisconnected,
    resetSseSubscriptionState,
  };
}
