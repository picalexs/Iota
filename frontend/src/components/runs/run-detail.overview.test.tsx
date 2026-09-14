import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { RunEventListResponse } from "@/types/run";
import {
  RUN_ID,
  api,
  renderRunDetail,
  resetRunDetailMocks,
  routerMocks,
  setupRunDetailMocks as setup,
  setRunDetailLocationState,
} from "./run-detail.test-utils";

beforeEach(resetRunDetailMocks);

afterEach(() => {
  vi.useRealTimers();
});

describe("RunDetail overview and outcome", () => {
  it("renders summary metadata with merged execution details", async () => {
    setup();
    renderRunDetail();

    await waitFor(() => {
      expect(screen.getByText("H2")).toBeInTheDocument();
    });

    expect(screen.getByText("Summary")).toBeInTheDocument();
    expect(screen.getByText("Molecule")).toBeInTheDocument();
    expect(screen.getAllByText("VQE").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Aer simulator").length).toBeGreaterThan(0);
    expect(screen.getByText("Basis set")).toBeInTheDocument();
    expect(screen.getByText("sto-3g")).toBeInTheDocument();
    expect(screen.queryByText("Circuit Info")).not.toBeInTheDocument();
  });

  it("returns to the runs list when opened from the run form", async () => {
    setup();
    setRunDetailLocationState({ __source: "run-create" });
    renderRunDetail();
    const user = userEvent.setup();

    await waitFor(() => {
      expect(screen.getByText("Summary")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /go back/i }));

    expect(routerMocks.navigate).toHaveBeenCalledWith({ to: "/runs" });
    expect(routerMocks.historyBack).not.toHaveBeenCalled();
  });

  it("links the IBM account name to Settings while the profile still exists", async () => {
    setup({
      backend_target: "ibm_runtime",
      credential_profile_id: "profile-1",
      credential_profile_name: "Main IBM",
    });
    renderRunDetail();

    await waitFor(() => {
      expect(screen.getByText("H2")).toBeInTheDocument();
    });

    expect(screen.getByText("IBM Account")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Main IBM" })).toHaveAttribute("href", "/settings");
  });

  it("marks a deleted IBM account next to the preserved name", async () => {
    setup({
      backend_target: "ibm_runtime",
      credential_profile_id: null,
      credential_profile_name: "Lab IBM",
    });
    renderRunDetail();

    await waitFor(() => {
      expect(screen.getByText("H2")).toBeInTheDocument();
    });

    expect(screen.getByText("Lab IBM (Deleted)")).toBeInTheDocument();
  });

  it("renders live summary while run is active", async () => {
    const events: RunEventListResponse = {
      events: [
        {
          id: 1,
          run_id: RUN_ID,
          sequence: 1,
          type: "iteration_update",
          payload: { iteration: 5, energy: -1.1, parameters: [] },
          created_at: "2025-06-01T10:01:00Z",
        },
      ],
      last_sequence: 1,
    };

    setup({
      latest_estimate: {
        source: "worker_runtime",
        algorithm: "vqe",
        estimated_total_iterations: 100,
        estimated_remaining_iterations: 95,
        estimated_total_seconds: 100,
        estimated_remaining_seconds: 95,
        confidence: 0.65,
        updated_at: "2025-06-01T10:01:00Z",
      },
    });
    vi.mocked(api.getRunEvents).mockResolvedValue(events);

    renderRunDetail();

    await waitFor(() => {
      expect(screen.getByText("Summary")).toBeInTheDocument();
    });

    expect(screen.getByText("-1.100000 Ha")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.queryByText(/^Remaining$/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Final result pending/)).not.toBeInTheDocument();
  });

  it("shows queued wording when a rerun is waiting in the queue", async () => {
    setup({ status: "QUEUED" });

    renderRunDetail();

    await waitFor(() => {
      expect(screen.getByText("Summary")).toBeInTheDocument();
    });

    expect(screen.getByLabelText("Status: QUEUED")).toBeInTheDocument();
    expect(screen.getAllByText("Queued").length).toBeGreaterThan(0);
    expect(screen.queryByText("Running")).not.toBeInTheDocument();
  });

  it("renders completed outcome with converged indicator", async () => {
    setup({ status: "COMPLETED" });
    renderRunDetail();

    await waitFor(() => {
      expect(screen.getByText("Summary")).toBeInTheDocument();
    });

    expect(screen.getByText("Unscored")).toBeInTheDocument();
    expect(screen.getByText("-1.137270 Ha")).toBeInTheDocument();
    expect(screen.getByText(/Converged/)).toBeInTheDocument();
    expect(screen.getByText(/Yes/)).toBeInTheDocument();
  });

  it("renders the dashboard shell before completed-run result data finishes loading", async () => {
    setup({ status: "COMPLETED" });
    vi.mocked(api.getRunEvents).mockReturnValue(new Promise(() => {}));
    vi.mocked(api.getRunResult).mockReturnValue(new Promise(() => {}));

    const { container } = renderRunDetail();

    await waitFor(() => {
      expect(screen.getByText("Summary")).toBeInTheDocument();
    });

    expect(screen.queryByLabelText("Loading run details")).not.toBeInTheDocument();
    expect(screen.getByText("Event Log")).toBeInTheDocument();
    expect(screen.getByText("Benchmark Comparison")).toBeInTheDocument();
    expect(screen.queryByText("Unscored")).not.toBeInTheDocument();
    expect(screen.queryByText("Waiting for events…")).not.toBeInTheDocument();
    expect(screen.queryByText("Awaiting first energy evaluation")).not.toBeInTheDocument();
    expect(container.querySelectorAll("[data-slot='skeleton']").length).toBeGreaterThan(0);
  });

  it("shows the active convergence gate for SQD runs on hover", async () => {
    const user = userEvent.setup();

    setup({ algorithm: "sqd", status: "RUNNING" });
    vi.mocked(api.getRunEvents).mockResolvedValue({
      events: [
        {
          id: 1,
          run_id: RUN_ID,
          sequence: 1,
          type: "iteration_update",
          payload: {
            stage: "progress",
            step: "configuration_recovery",
            iteration: 3,
            completed_iterations: 3,
            energy: -1.1002,
            delta_energy: 2e-6,
            energy_tol: 1e-5,
            occupancy_delta: 5e-4,
            occupancies_tol: 1e-3,
            selected_samples: 1,
            min_selected_configurations: 4,
            converged_candidate: false,
            convergence_blocked_reason: "insufficient_selected_configurations",
          },
          created_at: "2025-06-01T10:01:00Z",
        },
      ],
      last_sequence: 1,
    });

    renderRunDetail();

    const triggers = await screen.findAllByRole("button", { name: "Convergence status details" });
    const firstTrigger = triggers[0];
    if (!firstTrigger) {
      throw new Error("Expected a convergence status trigger");
    }
    await user.hover(firstTrigger);

    expect(
      (
        await screen.findAllByText(
          "Energy and occupancies look stable, but too few configurations survived",
        )
      ).length,
    ).toBeGreaterThan(0);
    expect(screen.getAllByText(/selected 1 < 4/).length).toBeGreaterThan(0);
  });

  it("shows IBM total first and aggregates usage across completed IBM jobs", async () => {
    setup({
      status: "COMPLETED",
      backend_target: "ibm_runtime",
      metadata: {
        resolved_backend_name: "ibm_pittsburgh",
      },
    });
    vi.mocked(api.getRunEvents).mockResolvedValue({
      events: [
        {
          id: 1,
          run_id: RUN_ID,
          sequence: 1,
          type: "ibm_status_poll",
          payload: {
            phase: "complete",
            ibm_job_id: "runtime-job-1",
            ibm_status: "DONE",
            ibm_timing: {
              created_at: "2026-05-18T20:00:00+00:00",
              running_at: "2026-05-18T20:00:01+00:00",
              finished_at: "2026-05-18T20:00:05+00:00",
              pending_seconds: 1,
              usage_seconds: 4,
              total_seconds: 5,
            },
          },
          created_at: "2026-05-18T20:00:06Z",
        },
        {
          id: 2,
          run_id: RUN_ID,
          sequence: 2,
          type: "ibm_status_poll",
          payload: {
            phase: "complete",
            ibm_job_id: "runtime-job-2",
            ibm_status: "DONE",
            ibm_timing: {
              created_at: "2026-05-18T20:00:10+00:00",
              running_at: "2026-05-18T20:00:10+00:00",
              finished_at: "2026-05-18T20:00:14+00:00",
              pending_seconds: 0,
              usage_seconds: 4,
              total_seconds: 4,
            },
          },
          created_at: "2026-05-18T20:00:15Z",
        },
      ],
      last_sequence: 2,
    });

    renderRunDetail();

    await waitFor(() => {
      expect(screen.getByText("IBM total")).toBeInTheDocument();
    });

    expect(screen.getByText("9s")).toBeInTheDocument();
    expect(screen.getByText("Usage 8s · Pending 1s")).toBeInTheDocument();
  });

  it("uses the fixed 1.6 mHa threshold on run detail even if benchmark storage was customized", async () => {
    localStorage.setItem("benchmark_chemical_accuracy_ha", "0.02");
    setup({ status: "COMPLETED" });
    vi.mocked(api.getRunResult).mockResolvedValue({
      run_id: RUN_ID,
      energy: -1.127,
      iterations: 42,
      optimal_parameters: [0.1, 0.2],
      converged: true,
      algorithm_metrics: {
        classical_references: { hf: -1.116, fci: -1.137 },
      },
      created_at: "2025-06-01T10:05:00Z",
    });

    renderRunDetail();

    await waitFor(() => {
      expect(screen.getByText("Not chemically accurate")).toBeInTheDocument();
    });

    expect(screen.queryByText(/threshold 1.60 mHa/)).not.toBeInTheDocument();
  });

  it("uses the per-run chemical accuracy target when the run config provides one", async () => {
    setup({
      status: "COMPLETED",
      config_json: {
        algorithm: "vqe",
        mode: "advanced",
        backend_target: "aer_simulator",
        chemical_accuracy_target_ha: 0.002,
        advanced_config: {
          algorithm: "vqe",
          ansatz_name: "EfficientSU2",
          optimizer_name: "COBYLA",
          max_iterations: 100,
        },
      },
    });
    vi.mocked(api.getRunResult).mockResolvedValue({
      run_id: RUN_ID,
      energy: -1.1358,
      iterations: 42,
      optimal_parameters: [0.1, 0.2],
      converged: true,
      algorithm_metrics: {
        classical_references: { hf: -1.116, fci: -1.137 },
      },
      created_at: "2025-06-01T10:05:00Z",
    });

    renderRunDetail();

    await waitFor(() => {
      expect(screen.getByText("Chemically accurate")).toBeInTheDocument();
    });
  });

  it("renders failed outcome message in merged card", async () => {
    setup({ status: "FAILED" });
    vi.mocked(api.getRunEvents).mockResolvedValue({
      events: [
        {
          id: 1,
          run_id: RUN_ID,
          sequence: 1,
          type: "error",
          payload: { summary: "Simulation crashed", traceback: null },
          created_at: "2025-06-01T10:05:00Z",
        },
      ],
      last_sequence: 1,
    });

    renderRunDetail();

    await waitFor(() => {
      expect(screen.getByText("Event Log")).toBeInTheDocument();
    });

    expect(screen.getAllByText("Simulation crashed").length).toBeGreaterThan(0);
  });
});
