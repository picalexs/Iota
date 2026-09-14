import { useState, useEffect, useRef } from "react";
import { DashboardTile } from "@/components/results/dashboard-tile";
import { TimelineTileLoadingContent } from "@/components/results/tile-loading-content";
import { TimelineContent } from "@/components/runs/run-detail/run-timeline";
import { useRunEventTimeline } from "@/components/runs/run-detail/use-run-event-timeline";
import type { RunEventResponse } from "@/types/run";

interface TimelineTileProps {
  readonly events: RunEventResponse[];
  readonly algorithm?: string | null;
  readonly isRunning: boolean;
  readonly activityLabel?: string | null;
  readonly sseDisconnected: boolean;
  readonly pending?: boolean;
  readonly editMode?: boolean;
}

export function TimelineTile({
  events,
  algorithm = null,
  isRunning,
  activityLabel = null,
  sseDisconnected,
  pending = false,
  editMode,
}: TimelineTileProps) {
  const [verboseMode, setVerboseMode] = useState(false);
  const [autoScrollEnabled, setAutoScrollEnabled] = useState(true);
  const timelineBoxRef = useRef<HTMLDivElement | null>(null);
  const timelineInteractedRef = useRef(false);
  const previousLengthRef = useRef(0);

  const { timelineEvents, displayEvents } = useRunEventTimeline(events, verboseMode);

  useEffect(() => {
    const box = timelineBoxRef.current;
    const grew = timelineEvents.length > previousLengthRef.current;
    previousLengthRef.current = timelineEvents.length;
    const shouldScroll = !timelineInteractedRef.current || autoScrollEnabled;
    if (!box || !grew || !shouldScroll) return;
    const frameId = globalThis.requestAnimationFrame(() => {
      box.scrollTop = box.scrollHeight;
    });
    return () => globalThis.cancelAnimationFrame(frameId);
  }, [timelineEvents.length, autoScrollEnabled]);

  return (
    <DashboardTile title="Event Log" editMode={editMode}>
      {pending ? (
        <TimelineTileLoadingContent />
      ) : (
        <div className="-mx-3 -my-2 flex h-full min-h-0 flex-col">
          <TimelineContent
            timelineEvents={timelineEvents}
            displayEvents={displayEvents}
            algorithm={algorithm}
            isRunning={isRunning}
            activityLabel={activityLabel}
            sseDisconnected={sseDisconnected}
            autoScrollEnabled={autoScrollEnabled}
            setAutoScrollEnabled={setAutoScrollEnabled}
            verboseMode={verboseMode}
            setVerboseMode={setVerboseMode}
            timelineBoxRef={timelineBoxRef}
            timelineInteractedRef={timelineInteractedRef}
            maxHeight=""
            pending={pending}
          />
        </div>
      )}
    </DashboardTile>
  );
}
