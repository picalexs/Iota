import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { RunEventResponse } from "@/types/run";
import {
  RUN_ID,
  abortControllerMock,
  api,
  baseRun,
  renderRunDetail,
  resetRunDetailMocks,
  setupRunDetailMocks as setup,
} from "./run-detail.test-utils";

beforeEach(resetRunDetailMocks);

afterEach(() => {
  vi.useRealTimers();
});

describe("RunDetail actions and SSE", () => {
  it("shows cancel action for running runs", async () => {
    const user = userEvent.setup();
    setup({ status: "RUNNING" });

    renderRunDetail();
    await waitFor(() => {
      expect(screen.getByText("Cancel Run")).toBeInTheDocument();
      expect(screen.getByText("Pause Run")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Cancel Run"));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("pauses and resumes runs through run controls", async () => {
    const user = userEvent.setup();
    setup({ status: "RUNNING" });
    vi.mocked(api.pauseRun).mockImplementation(async () => {
      vi.mocked(api.getRun).mockResolvedValue({ ...baseRun, status: "PAUSED" });
      return { id: RUN_ID, status: "PAUSED" };
    });

    renderRunDetail();

    await screen.findByRole("button", { name: /pause run/i });
    await screen.findByText("Summary");

    await user.click(screen.getByRole("button", { name: /pause run/i }));
    await user.click(screen.getByRole("button", { name: /^pause$/i }));

    await waitFor(() => {
      expect(api.pauseRun).toHaveBeenCalledWith(RUN_ID);
      expect(screen.getByLabelText("Status: PAUSED")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /resume run/i }));

    await waitFor(() => {
      expect(api.resumeRun).toHaveBeenCalledWith(RUN_ID);
    });
  });

  it("keeps the pause button visible with a spinner while the run is pausing", async () => {
    const user = userEvent.setup();
    setup({ status: "RUNNING" });
    vi.mocked(api.pauseRun).mockImplementation(async () => {
      vi.mocked(api.getRun).mockResolvedValue({ ...baseRun, status: "PAUSING" });
      return { id: RUN_ID, status: "PAUSING" };
    });

    renderRunDetail();

    await screen.findByText("Summary");
    await user.click(await screen.findByRole("button", { name: /pause run/i }));
    await user.click(screen.getByRole("button", { name: /^pause$/i }));

    await waitFor(() => {
      expect(api.pauseRun).toHaveBeenCalledWith(RUN_ID);
    });

    const pauseButton = await screen.findByRole("button", { name: /pausing/i });

    expect(pauseButton).toBeDisabled();
    expect(pauseButton).toHaveAttribute("aria-busy", "true");
    expect(pauseButton.querySelector("[data-slot='spinner']")).toBeInTheDocument();
  });

  it("shows restart action for terminal runs", async () => {
    const user = userEvent.setup();
    setup({ status: "FAILED" });

    renderRunDetail();

    expect(await screen.findByRole("button", { name: /resume run/i })).toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: /restart run/i }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /^restart$/i }));

    await waitFor(() => {
      expect(api.restartRun).toHaveBeenCalledWith(RUN_ID);
    });
  });

  it("resumes failed runs through run controls", async () => {
    const user = userEvent.setup();
    setup({ status: "FAILED" });

    renderRunDetail();

    await user.click(await screen.findByRole("button", { name: /resume run/i }));

    await waitFor(() => {
      expect(api.resumeRun).toHaveBeenCalledWith(RUN_ID);
    });
  });

  it("hides cancel action for completed runs", async () => {
    setup({ status: "COMPLETED" });
    renderRunDetail();

    await waitFor(() => {
      expect(screen.queryByText("Cancel Run")).not.toBeInTheDocument();
    });
  });

  it("does not subscribe to SSE for terminal runs", async () => {
    setup({ status: "COMPLETED" });
    renderRunDetail();

    await waitFor(() => {
      expect(screen.getByText("Summary")).toBeInTheDocument();
    });

    expect(api.subscribeToRunEvents).not.toHaveBeenCalled();
  });

  it("does not subscribe to SSE for paused runs", async () => {
    setup({ status: "PAUSED" });
    renderRunDetail();

    await waitFor(() => {
      expect(screen.getByText("Summary")).toBeInTheDocument();
    });

    expect(api.subscribeToRunEvents).not.toHaveBeenCalled();
  });

  it("aborts SSE stream on unmount", async () => {
    setup();
    const { unmount } = renderRunDetail();

    await waitFor(() => {
      expect(screen.getByText("Summary")).toBeInTheDocument();
    });

    unmount();
    expect(abortControllerMock.abort).toHaveBeenCalled();
  });

  it("deduplicates SSE events by sequence", async () => {
    setup();

    let eventHandler: ((event: RunEventResponse) => void) | null = null;
    vi.mocked(api.subscribeToRunEvents).mockImplementation((_id, onEvent) => {
      eventHandler = onEvent;
      return abortControllerMock;
    });

    renderRunDetail();

    await waitFor(() => {
      expect(eventHandler).not.toBeNull();
    });

    const duplicateEvent: RunEventResponse = {
      id: 7,
      run_id: RUN_ID,
      sequence: 99,
      type: "iteration_update",
      payload: { iteration: 9, energy: -1.2, parameters: [] },
      created_at: "2025-06-01T10:06:00Z",
    };

    act(() => {
      eventHandler?.(duplicateEvent);
      eventHandler?.(duplicateEvent);
    });

    await waitFor(() => {
      const timeline = screen.getByRole("log");
      const entries = within(timeline).getAllByText(/Iteration 9 · Energy -1\.200000 Ha/);
      expect(entries.length).toBe(1);
    });
  });

  it("uses QFD-specific labels for progress rows", async () => {
    setup({
      algorithm: "qfd",
      config_json: {
        algorithm: "qfd",
        mode: "advanced",
        backend_target: "aer_simulator",
      },
    });

    vi.mocked(api.getRunEvents).mockResolvedValue({
      events: [
        {
          id: 11,
          run_id: RUN_ID,
          sequence: 11,
          type: "iteration_update",
          payload: {
            algorithm: "qfd",
            step: "hardware_matrix_elements",
            iteration: 1,
            completed_iterations: 1,
            energy: -1.2,
            matrix_element_pair: [0, 0],
          },
          created_at: "2025-06-01T10:06:00Z",
        },
      ],
      last_sequence: 11,
    });

    renderRunDetail();

    await waitFor(() => {
      expect(screen.getByRole("log")).toBeInTheDocument();
    });

    const timeline = screen.getByRole("log");
    expect(within(timeline).getByText("Matrix element")).toBeInTheDocument();
    expect(
      within(timeline).getByText(/Matrix element 1 · Pair \(0, 0\) · Energy -1\.200000 Ha/),
    ).toBeInTheDocument();
  });
});
