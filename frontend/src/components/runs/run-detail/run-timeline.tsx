import { ArrowRightCircle, Cloud } from "lucide-react";
import type React from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { RunEventDescriptor } from "./run-event-descriptor";
import {
  EVENT_ICONS,
  EVENT_LABELS,
  getIterationUpdatePresentation,
} from "./run-event-descriptor-utils";
import { numberOrNull, TAIL_WINDOW, type TimelineEventEntry } from "./use-run-event-timeline";

interface RunTimelineProps {
  timelineEvents: TimelineEventEntry[];
  displayEvents: TimelineEventEntry[];
  algorithm?: string | null;
  isRunning: boolean;
  activityLabel?: string | null;
  sseDisconnected: boolean;
  autoScrollEnabled: boolean;
  setAutoScrollEnabled: React.Dispatch<React.SetStateAction<boolean>>;
  verboseMode: boolean;
  setVerboseMode: React.Dispatch<React.SetStateAction<boolean>>;
  timelineBoxRef: React.RefObject<HTMLDivElement | null>;
  timelineInteractedRef: React.RefObject<boolean>;
}

export interface TimelineContentProps extends RunTimelineProps {
  maxHeight?: string;
  pending?: boolean;
}

function getIterationEventCollectionLabel(algorithm?: string | null): string {
  return algorithm === "vqe" ? "objective updates" : "progress updates";
}

export function TimelineContent({
  timelineEvents,
  displayEvents,
  algorithm = null,
  isRunning,
  activityLabel = null,
  sseDisconnected,
  autoScrollEnabled,
  setAutoScrollEnabled,
  verboseMode,
  setVerboseMode,
  timelineBoxRef,
  timelineInteractedRef,
  maxHeight = "max-h-80",
  pending = false,
}: TimelineContentProps) {
  if (timelineEvents.length === 0) {
    return (
      <div className="py-8 text-center">
        <p className="text-sm text-muted-foreground">
          {isRunning || pending ? "Waiting for events…" : "No events were recorded for this run."}
        </p>
      </div>
    );
  }

  const iterationEventCount = timelineEvents.filter(
    (event) => event.type === "iteration_update",
  ).length;
  const visibleIterationEventCount = displayEvents.filter(
    (event) => event.type === "iteration_update",
  ).length;
  const iterationEventLabel = getIterationEventCollectionLabel(algorithm);

  return (
    <div className="flex h-full min-h-0 flex-col">
      {/* Controls bar */}
      <div className="flex items-center gap-1.5 px-3 py-1.5 border-b border-border/50 shrink-0">
        {activityLabel && !sseDisconnected && (
          <span className="flex items-center gap-1 text-xs font-medium text-success">
            <span className="size-1.5 rounded-full bg-success animate-pulse" aria-hidden />
            {activityLabel}
          </span>
        )}
        <div className="flex items-center gap-1.5 ml-auto">
          {isRunning && (
            <button
              type="button"
              onClick={() => {
                timelineInteractedRef.current = true;
                setAutoScrollEnabled((value) => !value);
              }}
              className={`rounded-full px-2 py-0.5 text-xs font-medium transition-colors ${
                autoScrollEnabled ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"
              }`}
              aria-pressed={autoScrollEnabled}
            >
              Auto-scroll {autoScrollEnabled ? "on" : "off"}
            </button>
          )}
          <button
            type="button"
            onClick={() => setVerboseMode((value) => !value)}
            className={`rounded-full px-2 py-0.5 text-xs font-medium transition-colors ${
              verboseMode ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"
            }`}
            aria-pressed={verboseMode}
          >
            {verboseMode ? "Verbose" : "Normal"}
          </button>
          <Badge variant="secondary" className="font-mono tabular-nums shrink-0">
            {timelineEvents.length}
          </Badge>
        </div>
      </div>

      {/* Event list */}
      <div
        ref={timelineBoxRef}
        className={`${maxHeight} flex-1 min-h-0 overflow-y-auto divide-y divide-border`}
        aria-label="Run event timeline"
        role="log"
        aria-live={isRunning ? "polite" : "off"}
        aria-relevant="additions"
        onScroll={(event) => {
          const element = event.currentTarget;
          const nearBottom = element.scrollHeight - element.scrollTop - element.clientHeight < 32;
          timelineInteractedRef.current = true;
          setAutoScrollEnabled(nearBottom);
        }}
      >
        {!verboseMode && iterationEventCount > TAIL_WINDOW && (
          <div className="px-4 py-2 bg-muted/20 border-b border-border/50 flex items-center gap-2">
            <span className="text-xs text-muted-foreground">
              Showing{" "}
              <span className="font-medium text-foreground">{visibleIterationEventCount}</span> of{" "}
              <span className="font-medium text-foreground">{iterationEventCount}</span>{" "}
              {iterationEventLabel} · toggle <span className="font-medium">Verbose</span> to see all
            </span>
          </div>
        )}
        {displayEvents.map((event, index) => (
          <TimelineRow
            key={event.id}
            event={event}
            previousEvents={displayEvents.slice(0, index)}
            verboseMode={verboseMode}
            algorithm={algorithm}
          />
        ))}
      </div>
    </div>
  );
}

export function RunTimeline(props: RunTimelineProps) {
  if (props.timelineEvents.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm flex items-center gap-2">
            <Cloud className="size-4 text-muted-foreground" />
            Event Timeline
          </CardTitle>
        </CardHeader>
        <CardContent className="py-8 text-center">
          <p className="text-sm text-muted-foreground">
            {props.isRunning ? "Waiting for events…" : "No events were recorded for this run."}
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2">
          <span className="shrink-0">Event Timeline</span>
          {props.activityLabel && !props.sseDisconnected && (
            <span className="flex items-center gap-1 text-xs font-medium text-success">
              <span className="size-1.5 rounded-full bg-success animate-pulse" aria-hidden />
              {props.activityLabel}
            </span>
          )}
          <div className="flex items-center gap-1.5 ml-auto">
            {props.isRunning && (
              <button
                type="button"
                onClick={() => {
                  props.timelineInteractedRef.current = true;
                  props.setAutoScrollEnabled((value) => !value);
                }}
                className={`rounded-full px-2 py-0.5 text-xs font-medium transition-colors ${
                  props.autoScrollEnabled
                    ? "bg-primary/10 text-primary"
                    : "bg-muted text-muted-foreground"
                }`}
                aria-pressed={props.autoScrollEnabled}
              >
                Auto-scroll {props.autoScrollEnabled ? "on" : "off"}
              </button>
            )}
            <button
              type="button"
              onClick={() => props.setVerboseMode((value) => !value)}
              className={`rounded-full px-2 py-0.5 text-xs font-medium transition-colors ${
                props.verboseMode ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"
              }`}
              aria-pressed={props.verboseMode}
            >
              {props.verboseMode ? "Verbose" : "Normal"}
            </button>
            <Badge variant="secondary" className="font-mono tabular-nums shrink-0">
              {props.timelineEvents.length}
            </Badge>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <div
          ref={props.timelineBoxRef}
          className="max-h-80 overflow-y-auto divide-y divide-border"
          aria-label="Run event timeline"
          role="log"
          aria-live={props.isRunning ? "polite" : "off"}
          aria-relevant="additions"
          onScroll={(event) => {
            const element = event.currentTarget;
            const nearBottom = element.scrollHeight - element.scrollTop - element.clientHeight < 32;
            props.timelineInteractedRef.current = true;
            props.setAutoScrollEnabled(nearBottom);
          }}
        >
          {!props.verboseMode &&
            props.timelineEvents.filter((e) => e.type === "iteration_update").length >
              TAIL_WINDOW && (
              <div className="px-4 py-2 bg-muted/20 border-b border-border/50 flex items-center gap-2">
                <span className="text-xs text-muted-foreground">
                  Showing{" "}
                  <span className="font-medium text-foreground">
                    {props.displayEvents.filter((e) => e.type === "iteration_update").length}
                  </span>{" "}
                  of{" "}
                  <span className="font-medium text-foreground">
                    {props.timelineEvents.filter((e) => e.type === "iteration_update").length}
                  </span>{" "}
                  {getIterationEventCollectionLabel(props.algorithm)} · toggle{" "}
                  <span className="font-medium">Verbose</span> to see all
                </span>
              </div>
            )}
          {props.displayEvents.map((event, index) => (
            <TimelineRow
              key={event.id}
              event={event}
              previousEvents={props.displayEvents.slice(0, index)}
              verboseMode={props.verboseMode}
              algorithm={props.algorithm}
            />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

interface TimelineRowProps {
  event: TimelineEventEntry;
  previousEvents: TimelineEventEntry[];
  verboseMode: boolean;
  algorithm?: string | null;
}

function TimelineRow({ event, previousEvents, verboseMode, algorithm = null }: TimelineRowProps) {
  const prevIterEvent = previousEvents
    .slice()
    .reverse()
    .find((entry) => entry.type === "iteration_update");
  const isPhaseBreak =
    event.type === "iteration_update" &&
    prevIterEvent !== undefined &&
    numberOrNull(event.payload.display_iteration) !== null &&
    numberOrNull(prevIterEvent.payload.display_iteration) !== null &&
    (numberOrNull(event.payload.display_iteration) ?? 0) <
      (numberOrNull(prevIterEvent.payload.display_iteration) ?? 0);
  const iterationPresentation =
    event.type === "iteration_update"
      ? getIterationUpdatePresentation(event.payload, event.estimate, algorithm)
      : null;
  const eventLabel = iterationPresentation?.label ?? EVENT_LABELS[event.type];
  const eventIcon = iterationPresentation?.icon ?? EVENT_ICONS[event.type];

  return (
    <div>
      {isPhaseBreak && (
        <div className="flex items-center gap-2 px-4 py-1.5 bg-primary/5 border-b border-primary/10">
          <ArrowRightCircle className="size-3 text-primary/60 shrink-0" />
          <span className="text-xs font-medium text-primary/70">Algorithm phase change</span>
          <span className="text-xs text-muted-foreground">
            · iteration counter reset, entering next stage
          </span>
        </div>
      )}
      <div className="flex items-start gap-3 px-4 py-2.5 hover:bg-muted/40 transition-colors">
        <span className="mt-0.5 shrink-0">{eventIcon}</span>
        <div className="flex-1 min-w-0 flex flex-col gap-0.5">
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-medium">{eventLabel}</span>
            <span className="text-xs text-muted-foreground tabular-nums shrink-0">
              {new Date(event.created_at).toLocaleTimeString()}
            </span>
          </div>
          <RunEventDescriptor
            type={event.type}
            payload={event.payload}
            estimate={event.estimate}
            verbose={verboseMode}
            algorithm={algorithm}
          />
        </div>
      </div>
    </div>
  );
}
