import { useMemo } from "react";

import { getResultEventConvergenceLog } from "@/lib/results/convergence-status";
import type { RunEstimate, RunEventResponse, RunEventType } from "@/types/run";

export const TAIL_WINDOW = 20;

export interface TimelineEventEntry {
  id: number;
  run_id: string;
  sequence: number;
  type: RunEventType;
  payload: Record<string, unknown>;
  created_at: string;
  estimate: RunEstimate | null;
}

export function numberOrNull(value: unknown): number | null {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return null;
  }
  return value;
}

export function toRunEstimate(payload: Record<string, unknown>): RunEstimate | null {
  const source = payload.source;
  const algorithm = payload.algorithm;
  const updatedAt = payload.updated_at;
  if (
    typeof source !== "string" ||
    typeof algorithm !== "string" ||
    typeof updatedAt !== "string"
  ) {
    return null;
  }

  return {
    source,
    algorithm,
    estimated_total_iterations: numberOrNull(payload.estimated_total_iterations),
    estimated_remaining_iterations: numberOrNull(payload.estimated_remaining_iterations),
    estimated_total_seconds: numberOrNull(payload.estimated_total_seconds),
    estimated_remaining_seconds: numberOrNull(payload.estimated_remaining_seconds),
    confidence: numberOrNull(payload.confidence),
    updated_at: updatedAt,
  };
}

interface IterationDisplayState {
  offset: number;
  previousRaw: number | null;
  previousDisplay: number | null;
}

interface TimelineBuildState {
  pendingEstimate: RunEstimate | null;
  latestEstimate: RunEstimate | null;
  iterationDisplay: IterationDisplayState;
}

function timelinePayload(event: RunEventResponse): Record<string, unknown> {
  if (event.type !== "result") return event.payload;
  const payload = { ...event.payload };
  const convergenceLog = getResultEventConvergenceLog(payload);
  delete payload.algorithm_metrics;
  if (convergenceLog != null && payload.stop_reason == null) {
    payload.stop_reason = convergenceLog.summary;
    payload.stop_reason_details = convergenceLog.details;
    payload.stop_reason_tone = convergenceLog.tone;
  }
  return payload;
}

function sortedUniqueEvents(events: RunEventResponse[]): RunEventResponse[] {
  return [...new Map(events.map((event) => [event.sequence, event])).values()].sort(
    (left, right) => left.sequence - right.sequence,
  );
}

function rawIterationFrom(event: RunEventResponse): number | null {
  return numberOrNull(event.payload.completed_iterations) ?? numberOrNull(event.payload.iteration);
}

function nextDisplayIteration(rawIteration: number, state: IterationDisplayState): number {
  if (state.previousRaw !== null && rawIteration < state.previousRaw) {
    state.offset = state.previousDisplay ?? state.previousRaw;
  }

  const displayIteration = state.offset + rawIteration;
  if (state.previousDisplay === null || displayIteration >= state.previousDisplay) {
    return displayIteration;
  }
  return state.previousDisplay;
}

function withDisplayIteration(
  event: RunEventResponse,
  state: IterationDisplayState,
): RunEventResponse {
  const rawIteration = rawIterationFrom(event);
  if (rawIteration === null) return event;

  const displayIteration = nextDisplayIteration(rawIteration, state);
  state.previousRaw = rawIteration;
  state.previousDisplay = displayIteration;

  return {
    ...event,
    payload: {
      ...event.payload,
      display_iteration: displayIteration,
    },
  };
}

function timelineEntry(event: RunEventResponse, estimate: RunEstimate | null): TimelineEventEntry {
  return { ...event, payload: timelinePayload(event), estimate };
}

function applyEstimatePayload(
  payload: Record<string, unknown>,
  state: TimelineBuildState,
): RunEstimate | null {
  const estimate = toRunEstimate(payload);
  if (estimate) {
    state.pendingEstimate = estimate;
    state.latestEstimate = estimate;
  }
  return estimate;
}

function appendEstimateEvent(
  events: RunEventResponse[],
  index: number,
  timelineEvents: TimelineEventEntry[],
  state: TimelineBuildState,
): number {
  const event = events[index];
  if (!event) {
    return index + 1;
  }
  const estimate = applyEstimatePayload(event.payload, state);
  const nextEvent = events[index + 1];
  if (nextEvent?.type === "iteration_update") {
    return index + 1;
  }

  timelineEvents.push(timelineEntry(event, estimate));
  state.pendingEstimate = null;
  return index + 1;
}

function consumeFollowingEstimate(
  nextEvent: RunEventResponse | undefined,
  currentEstimate: RunEstimate | null,
  state: TimelineBuildState,
): { estimate: RunEstimate | null; consumedNext: boolean } {
  if (nextEvent?.type !== "estimate_updated") {
    return { estimate: currentEstimate, consumedNext: false };
  }

  const nextEstimate = toRunEstimate(nextEvent.payload);
  if (nextEstimate) {
    state.latestEstimate = nextEstimate;
    return { estimate: nextEstimate, consumedNext: true };
  }

  return { estimate: currentEstimate, consumedNext: true };
}

function appendIterationEvent(
  events: RunEventResponse[],
  index: number,
  timelineEvents: TimelineEventEntry[],
  state: TimelineBuildState,
): number {
  const sourceEvent = events[index];
  if (!sourceEvent) {
    return index + 1;
  }
  const event = withDisplayIteration(sourceEvent, state.iterationDisplay);
  const estimateForIteration = state.pendingEstimate ?? state.latestEstimate;
  const consumed = consumeFollowingEstimate(events[index + 1], estimateForIteration, state);
  state.pendingEstimate = null;
  timelineEvents.push(timelineEntry(event, consumed.estimate));
  return index + (consumed.consumedNext ? 2 : 1);
}

export function buildTimelineEvents(events: RunEventResponse[]): TimelineEventEntry[] {
  const sortedEvents = sortedUniqueEvents(events);
  const timelineEvents: TimelineEventEntry[] = [];
  const state: TimelineBuildState = {
    pendingEstimate: null,
    latestEstimate: null,
    iterationDisplay: {
      offset: 0,
      previousRaw: null,
      previousDisplay: null,
    },
  };

  let index = 0;
  while (index < sortedEvents.length) {
    const event = sortedEvents[index];
    if (!event) {
      break;
    }

    if (event.type === "estimate_updated") {
      index = appendEstimateEvent(sortedEvents, index, timelineEvents, state);
      continue;
    }

    if (event.type === "iteration_update") {
      index = appendIterationEvent(sortedEvents, index, timelineEvents, state);
      continue;
    }

    state.pendingEstimate = null;
    timelineEvents.push(timelineEntry(event, null));
    index += 1;
  }

  return timelineEvents;
}

function shouldSelectIteration(index: number, tailStart: number, step: number): boolean {
  return index >= tailStart || index % step === 0;
}

function hasDisplayIterationRollback(
  event: TimelineEventEntry,
  previousEvent: TimelineEventEntry | undefined,
): boolean {
  if (!previousEvent) return false;
  const displayIteration = numberOrNull(event.payload.display_iteration);
  const previousDisplayIteration = numberOrNull(previousEvent.payload.display_iteration);
  return (
    displayIteration !== null &&
    previousDisplayIteration !== null &&
    displayIteration < previousDisplayIteration
  );
}

function selectedIterationSequences(iterEvents: TimelineEventEntry[]): Set<number> {
  const tailStart = iterEvents.length - TAIL_WINDOW;
  const step = Math.max(1, Math.ceil(tailStart / 8));
  const selectedSeqs = new Set<number>();

  iterEvents.forEach((event, index) => {
    if (shouldSelectIteration(index, tailStart, step)) {
      selectedSeqs.add(event.sequence);
    }

    const previousEvent = iterEvents[index - 1];
    if (previousEvent && hasDisplayIterationRollback(event, previousEvent)) {
      selectedSeqs.add(event.sequence);
      selectedSeqs.add(previousEvent.sequence);
    }
  });

  return selectedSeqs;
}

function filterTimelineEvents(
  timelineEvents: TimelineEventEntry[],
  verboseMode: boolean,
): TimelineEventEntry[] {
  if (verboseMode) return timelineEvents;

  const iterEvents = timelineEvents.filter((event) => event.type === "iteration_update");
  if (iterEvents.length <= TAIL_WINDOW) return timelineEvents;

  const selectedIterSeqs = selectedIterationSequences(iterEvents);
  return timelineEvents.filter(
    (event) => event.type !== "iteration_update" || selectedIterSeqs.has(event.sequence),
  );
}

export function useRunEventTimeline(events: RunEventResponse[], verboseMode: boolean) {
  const timelineEvents = useMemo(() => buildTimelineEvents(events), [events]);
  const displayEvents = useMemo(
    () => filterTimelineEvents(timelineEvents, verboseMode),
    [timelineEvents, verboseMode],
  );

  return { timelineEvents, displayEvents };
}
