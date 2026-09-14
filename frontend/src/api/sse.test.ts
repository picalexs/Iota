import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { RunEventResponse } from "@/types/run";

import { subscribeToRunEvents } from "./sse";
import { mockJsonResponse } from "./test-helpers";

const runEvent: RunEventResponse = {
  id: 1,
  run_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  sequence: 4,
  type: "status_changed",
  payload: { new_status: "RUNNING" },
  created_at: "2026-01-01T00:00:00Z",
};

function encode(value: string): Uint8Array<ArrayBuffer> {
  return new TextEncoder().encode(value);
}

function stream(chunks: string[]): ReadableStream<Uint8Array<ArrayBuffer>> {
  return new ReadableStream<Uint8Array<ArrayBuffer>>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encode(chunk));
      }
      controller.close();
    },
  });
}

function streamResponse(body: ReadableStream<Uint8Array<ArrayBuffer>>): Response {
  return {
    ok: true,
    status: 200,
    body,
  } as unknown as Response;
}

describe("run SSE transport", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("buffers partial chunks and delivers validated run events", async () => {
    const onEvent = vi.fn();
    const payload = `data: ${JSON.stringify(runEvent)}\n\n`;
    vi.mocked(fetch).mockResolvedValueOnce(
      streamResponse(
        stream([payload.slice(0, 12), payload.slice(12), 'data: {"type":"stream_end"}\n\n']),
      ),
    );

    subscribeToRunEvents(runEvent.run_id, onEvent);

    await vi.waitFor(() => expect(onEvent).toHaveBeenCalledOnce());
    expect(onEvent).toHaveBeenCalledWith(runEvent);
  });

  it("stops at both stream-end sentinel forms", async () => {
    const onEvent = vi.fn();
    vi.mocked(fetch).mockResolvedValueOnce(
      streamResponse(stream(['event: stream_end\ndata: {"status":"COMPLETED"}\n\n'])),
    );

    subscribeToRunEvents(runEvent.run_id, onEvent);

    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(onEvent).not.toHaveBeenCalled();

    vi.mocked(fetch).mockResolvedValueOnce(
      streamResponse(stream(['data: {"type":"stream_end"}\n\n'])),
    );
    subscribeToRunEvents(runEvent.run_id, onEvent);
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(onEvent).not.toHaveBeenCalled();
  });

  it("reports malformed JSON and event shapes without forwarding payloads", async () => {
    const onEvent = vi.fn();
    const warnings: string[] = [];
    vi.mocked(fetch).mockResolvedValueOnce(
      streamResponse(
        stream(['data: {"token":"secret"\n\n', "data: {}\n\n", 'data: {"type":"stream_end"}\n\n']),
      ),
    );

    subscribeToRunEvents(runEvent.run_id, onEvent, undefined, undefined, (message) => {
      warnings.push(message);
    });

    await vi.waitFor(() => expect(warnings).toHaveLength(2));
    expect(onEvent).not.toHaveBeenCalled();
    expect(warnings).toContain(
      `[SSE] Skipped malformed event for run ${runEvent.run_id}: invalid JSON.`,
    );
    expect(warnings.join(" ")).not.toContain("secret");
  });

  it("passes the resume sequence and reports connection failures", async () => {
    const onError = vi.fn();
    vi.mocked(fetch).mockResolvedValueOnce(mockJsonResponse({ detail: "unavailable" }, 503));

    subscribeToRunEvents(runEvent.run_id, vi.fn(), 42, onError);

    await vi.waitFor(() => expect(onError).toHaveBeenCalledOnce());
    expect(onError.mock.calls[0]?.[0]).toMatchObject({ status: 503 });
    expect(new Headers(vi.mocked(fetch).mock.calls[0]?.[1]?.headers).get("Last-Event-ID")).toBe(
      "42",
    );

    vi.mocked(fetch).mockRejectedValueOnce(new TypeError("Failed to fetch"));
    subscribeToRunEvents(runEvent.run_id, vi.fn(), undefined, onError);
    await vi.waitFor(() => expect(onError).toHaveBeenCalledTimes(2));
    expect(onError.mock.calls[1]?.[0]).toMatchObject({
      code: "NETWORK_ERROR",
      message: "Unable to connect to the live updates stream. Please try again.",
    });
  });

  it("returns an AbortController and does not report normal cancellation", async () => {
    const onError = vi.fn();
    const neverEnding = new ReadableStream<Uint8Array<ArrayBuffer>>({
      start() {
        // The stream remains open until the returned controller is aborted.
      },
    });
    vi.mocked(fetch).mockResolvedValueOnce(streamResponse(neverEnding));

    const controller = subscribeToRunEvents(runEvent.run_id, vi.fn(), undefined, onError);
    controller.abort();
    await new Promise((resolve) => setTimeout(resolve, 20));

    expect(controller.signal.aborted).toBe(true);
    expect(onError).not.toHaveBeenCalled();
  });
});
