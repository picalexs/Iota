import { act, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { RunEventResponse } from "@/types/run";
import {
  RUN_ID,
  abortControllerMock,
  api,
  baseRun,
  emptyEvents,
  molecule,
  renderRunDetail,
  resetRunDetailMocks,
  result,
  setupRunDetailMocks as setup,
} from "./run-detail.test-utils";
import { buildTimelineEvents, numberOrNull } from "./run-detail/use-run-event-timeline";

beforeEach(resetRunDetailMocks);

afterEach(() => {
  vi.useRealTimers();
});

describe("RunDetail timeline refresh", () => {
  it("displays a monotonic iteration counter across internal phase resets", () => {
    const timeline = buildTimelineEvents([
      {
        id: 1,
        run_id: RUN_ID,
        sequence: 1,
        type: "iteration_update",
        payload: { iteration: 162, completed_iterations: 162, energy: -107.77 },
        created_at: "2025-06-01T10:01:00Z",
      },
      {
        id: 2,
        run_id: RUN_ID,
        sequence: 2,
        type: "iteration_update",
        payload: { iteration: 1, completed_iterations: 1, energy: -107.78 },
        created_at: "2025-06-01T10:01:01Z",
      },
      {
        id: 3,
        run_id: RUN_ID,
        sequence: 3,
        type: "iteration_update",
        payload: { iteration: 3, completed_iterations: 3, energy: -108.23 },
        created_at: "2025-06-01T10:01:02Z",
      },
    ]);

    expect(timeline.map((event) => numberOrNull(event.payload.display_iteration))).toEqual([
      162, 163, 165,
    ]);
  });

  it("merges estimate updates into iteration rows in the timeline", async () => {
    setup();
    vi.mocked(api.getRunEvents).mockResolvedValue({
      events: [
        {
          id: 1,
          run_id: RUN_ID,
          sequence: 1,
          type: "iteration_update",
          payload: { iteration: 5, energy: -1.1, parameters: [] },
          created_at: "2025-06-01T10:01:00Z",
        },
        {
          id: 2,
          run_id: RUN_ID,
          sequence: 2,
          type: "estimate_updated",
          payload: {
            source: "telemetry",
            algorithm: "vqe",
            estimated_total_iterations: 100,
            estimated_remaining_iterations: 95,
            estimated_total_seconds: 95,
            estimated_remaining_seconds: 95,
            confidence: 0.65,
            updated_at: "2025-06-01T10:01:01Z",
          },
          created_at: "2025-06-01T10:01:01Z",
        },
      ],
      last_sequence: 2,
    });

    renderRunDetail();

    await waitFor(() => {
      expect(screen.getByRole("log")).toBeInTheDocument();
    });

    expect(screen.queryByText("Estimate Updated")).not.toBeInTheDocument();
    expect(screen.getByText(/Iteration 5 · Energy -1\.100000 Ha/)).toBeInTheDocument();
    expect(screen.getByText(/ETA 1m 35s/)).toBeInTheDocument();
  });

  it("advances past estimate updates that arrive before iteration rows", () => {
    const timeline = buildTimelineEvents([
      {
        id: 1,
        run_id: RUN_ID,
        sequence: 1,
        type: "estimate_updated",
        payload: {
          source: "telemetry",
          algorithm: "sqd",
          estimated_total_iterations: 2,
          estimated_remaining_iterations: 2,
          estimated_total_seconds: 10,
          estimated_remaining_seconds: 10,
          confidence: 0.7,
          updated_at: "2025-06-01T10:01:00Z",
        },
        created_at: "2025-06-01T10:01:00Z",
      },
      {
        id: 2,
        run_id: RUN_ID,
        sequence: 2,
        type: "iteration_update",
        payload: { iteration: 1, energy: -1.1 },
        created_at: "2025-06-01T10:01:01Z",
      },
    ]);

    expect(timeline).toHaveLength(1);
    expect(timeline[0]).toMatchObject({
      sequence: 2,
      type: "iteration_update",
      estimate: {
        estimated_remaining_iterations: 2,
      },
    });
  });

  it("keeps result stop reasons after removing bulky algorithm metrics from timeline rows", () => {
    const timeline = buildTimelineEvents([
      {
        id: 1,
        run_id: RUN_ID,
        sequence: 1,
        type: "result",
        payload: {
          algorithm: "vqe",
          energy: -1.1,
          converged: false,
          iterations: 10,
          algorithm_metrics: {
            objective_evaluations: 10,
            max_function_evaluations: 10,
            optimizer_diagnostics: {
              termination_reason: "max_function_evaluations",
            },
          },
        },
        created_at: "2025-06-01T10:01:00Z",
      },
    ]);

    expect(timeline).toHaveLength(1);
    const firstTimelineEvent = timeline[0];
    if (!firstTimelineEvent) {
      throw new Error("Expected a timeline event");
    }
    expect(firstTimelineEvent.payload.algorithm_metrics).toBeUndefined();
    expect(firstTimelineEvent.payload.stop_reason).toBe(
      "The run reached the function-evaluation budget",
    );
    expect(firstTimelineEvent.payload.stop_reason_tone).toBe("warning");
  });

  it("shows standalone estimate updates before iteration events arrive", async () => {
    setup();
    vi.mocked(api.getRunEvents).mockResolvedValue({
      events: [
        {
          id: 1,
          run_id: RUN_ID,
          sequence: 1,
          type: "estimate_updated",
          payload: {
            source: "telemetry",
            algorithm: "vqe",
            estimated_total_iterations: 100,
            estimated_remaining_iterations: 100,
            estimated_total_seconds: 100,
            estimated_remaining_seconds: 100,
            confidence: 0.8,
            updated_at: "2025-06-01T10:01:00Z",
          },
          created_at: "2025-06-01T10:01:00Z",
        },
      ],
      last_sequence: 1,
    });

    renderRunDetail();

    await waitFor(() => {
      expect(screen.getByRole("log")).toBeInTheDocument();
    });

    const timeline = screen.getByRole("log");
    expect(screen.getByText("Estimate Updated")).toBeInTheDocument();
    expect(timeline).toHaveTextContent("Remaining 100 iterations");
    expect(timeline).toHaveTextContent("ETA 1m 40s");
    expect(screen.queryByText(/Waiting for events/)).not.toBeInTheDocument();
  });

  it("keeps refreshing run data in the background while the page stays open", async () => {
    const liveEvent: RunEventResponse = {
      id: 10,
      run_id: RUN_ID,
      sequence: 10,
      type: "iteration_update",
      payload: { iteration: 3, energy: -1.23, parameters: [] },
      created_at: "2025-06-01T10:02:00Z",
    };

    vi.mocked(api.getRun).mockResolvedValue(baseRun);
    vi.mocked(api.getRun)
      .mockResolvedValueOnce(baseRun)
      .mockResolvedValueOnce({
        ...baseRun,
        updated_at: "2025-06-01T10:02:00Z",
      });

    vi.mocked(api.getRunEvents).mockResolvedValue(emptyEvents);
    vi.mocked(api.getRunEvents)
      .mockResolvedValueOnce(emptyEvents)
      .mockResolvedValueOnce({ events: [liveEvent], last_sequence: 10 });

    vi.mocked(api.getMolecule).mockResolvedValue(molecule);
    vi.mocked(api.getRunResult).mockResolvedValue(result);
    vi.mocked(api.cancelRun).mockResolvedValue({ id: RUN_ID, status: "CANCELLED" });
    vi.mocked(api.subscribeToRunEvents).mockReturnValue(abortControllerMock);

    const setIntervalSpy = vi.spyOn(globalThis, "setInterval");
    const clearIntervalSpy = vi.spyOn(globalThis, "clearInterval");
    let intervalCallback: (() => void) | null = null;

    setIntervalSpy.mockImplementation(((callback: TimerHandler, delay?: number) => {
      if (delay === 2000) {
        intervalCallback = callback as () => void;
      }
      return 1;
    }) as typeof globalThis.setInterval);
    clearIntervalSpy.mockImplementation(() => {});

    try {
      renderRunDetail();

      await waitFor(() => {
        expect(screen.getByRole("button", { name: "Edit layout" })).toBeInTheDocument();
      });
      expect(intervalCallback).not.toBeNull();

      await act(async () => {
        intervalCallback?.();
      });

      await waitFor(() => {
        expect(api.getRunEvents).toHaveBeenCalledTimes(2);
      });
      expect(screen.getAllByText(/-1\.230000 Ha/).length).toBeGreaterThan(0);
    } finally {
      setIntervalSpy.mockRestore();
      clearIntervalSpy.mockRestore();
    }
  });

  it("shows an empty timeline state after a terminal run with no events", async () => {
    setup({ status: "CANCELLED" });
    renderRunDetail();

    await waitFor(() => {
      expect(screen.getByText("Event Log")).toBeInTheDocument();
    });

    expect(screen.getByText("No events were recorded for this run.")).toBeInTheDocument();
  });
});
