/** Server-sent event transport for run updates. */

import { logAppWarning } from "@/lib/app-logger";
import type { ApiRunEventResponse } from "@/types/api";
import { isRunEventType, type RunEventResponse, type UUID } from "@/types/run";
import { API_BASE, ApiError, fetchWithApiError, handleApiError, isRecord } from "./http";

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isRunEventResponse(value: unknown): value is ApiRunEventResponse {
  return (
    isRecord(value) &&
    isFiniteNumber(value.id) &&
    typeof value.run_id === "string" &&
    isFiniteNumber(value.sequence) &&
    isRunEventType(value.type) &&
    isRecord(value.payload) &&
    typeof value.created_at === "string"
  );
}

function toRunEvent(data: ApiRunEventResponse): RunEventResponse {
  return {
    ...data,
    run_id: data.run_id as UUID,
  };
}

type SseBlock = {
  eventName: string | null;
  dataLine: string | null;
};

function parseSseBlock(eventBlock: string): SseBlock {
  const parsed: SseBlock = { eventName: null, dataLine: null };

  for (const eventLine of eventBlock.split("\n")) {
    if (eventLine.startsWith("event: ")) {
      parsed.eventName = eventLine.slice(7).trim();
    }
    if (eventLine.startsWith("data: ")) {
      parsed.dataLine = eventLine.slice(6);
    }
  }

  return parsed;
}

function warnMalformedSseEvent(
  runId: UUID,
  reason: "invalid event shape" | "invalid JSON",
  onMalformedEvent?: (message: string) => void,
): void {
  const message = `[SSE] Skipped malformed event for run ${runId}: ${reason}.`;
  if (onMalformedEvent) {
    onMalformedEvent(message);
    return;
  }
  logAppWarning("api.sse", message, { runId, reason });
}

function dispatchSseDataLine(
  dataLine: string,
  runId: UUID,
  onEvent: (event: RunEventResponse) => void,
  onMalformedEvent?: (message: string) => void,
): "continue" | "end" {
  try {
    const event: unknown = JSON.parse(dataLine);
    if (isRecord(event) && event.type === "stream_end") {
      return "end";
    }
    if (isRunEventResponse(event)) {
      onEvent(toRunEvent(event));
    } else {
      warnMalformedSseEvent(runId, "invalid event shape", onMalformedEvent);
    }
  } catch {
    warnMalformedSseEvent(runId, "invalid JSON", onMalformedEvent);
  }

  return "continue";
}

function handleSseBlock(
  eventBlock: string,
  runId: UUID,
  onEvent: (event: RunEventResponse) => void,
  onMalformedEvent?: (message: string) => void,
): "continue" | "end" {
  const { eventName, dataLine } = parseSseBlock(eventBlock);
  if (eventName === "stream_end") {
    return "end";
  }
  if (dataLine === null) {
    return "continue";
  }

  return dispatchSseDataLine(dataLine, runId, onEvent, onMalformedEvent);
}

async function readRunEventStream(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  runId: UUID,
  onEvent: (event: RunEventResponse) => void,
  onMalformedEvent?: (message: string) => void,
): Promise<void> {
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";

    for (const eventBlock of events) {
      if (handleSseBlock(eventBlock, runId, onEvent, onMalformedEvent) === "end") {
        return;
      }
    }
  }
}

// Streams SSE run events and buffers partial chunks between reads.
export function subscribeToRunEvents(
  id: UUID,
  onEvent: (event: RunEventResponse) => void,
  lastEventId?: number,
  onError?: (error: unknown) => void,
  onMalformedEvent?: (message: string) => void,
): AbortController {
  const controller = new AbortController();

  (async () => {
    try {
      const headers: Record<string, string> = {};
      if (lastEventId != null) {
        headers["Last-Event-ID"] = String(lastEventId);
      }
      const response = await fetchWithApiError(
        `${API_BASE}/api/runs/${id}/events/stream`,
        {
          signal: controller.signal,
          headers,
        },
        "Unable to connect to the live updates stream. Please try again.",
      );

      if (!response.ok) {
        await handleApiError(response, {
          method: "GET",
          url: `${API_BASE}/api/runs/${id}/events/stream`,
        });
      }

      if (!response.body) {
        throw new ApiError(
          "stream_unavailable",
          "Streaming is not supported in this environment or the response has no body.",
          response.status,
        );
      }
      const reader = response.body.getReader();
      const cancelReader = () => {
        void reader.cancel().catch(() => undefined);
      };

      if (controller.signal.aborted) {
        cancelReader();
      } else {
        controller.signal.addEventListener("abort", cancelReader, { once: true });
      }

      try {
        await readRunEventStream(reader, id, onEvent, onMalformedEvent);
      } finally {
        controller.signal.removeEventListener("abort", cancelReader);
      }
    } catch (error) {
      if (error instanceof Error && error.name === "AbortError") {
        // Expected cancellation
        return;
      }
      throw error;
    }
  })().catch((error) => onError?.(error));

  return controller;
}
