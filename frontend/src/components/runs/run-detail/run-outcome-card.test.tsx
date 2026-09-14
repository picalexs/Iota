import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RunOutcomeCard } from "./run-outcome-card";
import type { RunEventResponse, RunResponse, RunResultResponse } from "@/types/run";

const baseRun: RunResponse = {
  id: "aaaaaaaa-0000-0000-0000-000000000001",
  molecule_id: "bbbbbbbb-0000-0000-0000-000000000001",
  status: "RUNNING",
  algorithm: "vqe",
  mode: "advanced",
  backend_target: "statevector",
  config_json: {
    algorithm: "vqe",
    advanced_config: {
      algorithm: "vqe",
      ansatz_name: "EfficientSU2",
      optimizer_name: "COBYLA",
      max_iterations: 12,
      max_function_evaluations: 12,
    },
  },
  ibm_job_id: null,
  client_request_id: null,
  versions: null,
  metadata: null,
  latest_estimate: {
    source: "worker",
    algorithm: "vqe",
    estimated_total_iterations: 12,
    estimated_remaining_iterations: 5,
    estimated_total_seconds: 120,
    estimated_remaining_seconds: 50,
    confidence: 0.84,
    updated_at: "2026-01-01T00:00:05Z",
  },
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:05Z",
};

const iterationEvent: RunEventResponse = {
  id: 1,
  run_id: baseRun.id,
  sequence: 1,
  type: "iteration_update",
  payload: { iteration: 3, energy: -1.12 },
  created_at: "2026-01-01T00:00:03Z",
};

const result: RunResultResponse = {
  run_id: baseRun.id,
  energy: -1.137,
  iterations: 8,
  optimal_parameters: [0.1, -0.2],
  converged: true,
  algorithm_metrics: {
    objective_evaluations: 9,
    classical_reference: { hf_energy: -1.11, fci_energy: -1.137 },
  },
  created_at: "2026-01-01T00:00:10Z",
};

function runFixture(overrides: Partial<RunResponse>): RunResponse {
  return { ...baseRun, ...overrides };
}

describe("RunOutcomeCard", () => {
  it("shows active progress for running runs", () => {
    render(<RunOutcomeCard run={baseRun} events={[iterationEvent]} result={null} isRunning />);

    expect(screen.getByText("Run Outcome")).toBeInTheDocument();
    expect(screen.getByText("Objective evals")).toBeInTheDocument();
    expect(screen.getByText("-1.120000 Ha")).toBeInTheDocument();
    expect(screen.getByText("84%")).toBeInTheDocument();
  });

  it("shows completed outcome stats with VQE objective evaluations", () => {
    render(
      <RunOutcomeCard
        run={runFixture({ status: "COMPLETED" })}
        events={[iterationEvent]}
        result={result}
        isRunning={false}
      />,
    );

    expect(screen.getByText("-1.137000 Ha")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("optimal parameters")).toBeInTheDocument();
    expect(screen.getByText("9")).toBeInTheDocument();
  });

  it("shows failed errors, progress snapshots, and traceback details", () => {
    const errorEvent: RunEventResponse = {
      id: 2,
      run_id: baseRun.id,
      sequence: 2,
      type: "error",
      payload: { message: "Optimizer failed", traceback: "Traceback line" },
      created_at: "2026-01-01T00:00:04Z",
    };

    render(
      <RunOutcomeCard
        run={runFixture({ status: "FAILED" })}
        events={[iterationEvent, errorEvent]}
        result={null}
        isRunning={false}
      />,
    );

    expect(screen.getByText("Optimizer failed")).toBeInTheDocument();
    expect(screen.getByText("Show traceback")).toBeInTheDocument();
    expect(screen.getByText("Traceback line")).toBeInTheDocument();
    expect(screen.getByText("-1.120000 Ha")).toBeInTheDocument();
  });

  it("falls back to persisted run metadata when the error event uses sanitized fields", () => {
    render(
      <RunOutcomeCard
        run={runFixture({
          status: "FAILED",
          metadata: {
            error_message: "Run execution failed. Check worker logs for details.",
            error_type: "ValueError",
          },
        })}
        events={[
          {
            id: 2,
            run_id: baseRun.id,
            sequence: 2,
            type: "error",
            payload: { error_code: "worker_job_failed" },
            created_at: "2026-01-01T00:00:04Z",
          },
        ]}
        result={null}
        isRunning={false}
      />,
    );

    expect(
      screen.getByText(/Run execution failed\. Check worker logs for details\.\s+ValueError/),
    ).toBeInTheDocument();
  });

  it("explains cancellations with and without iteration progress", () => {
    const { rerender } = render(
      <RunOutcomeCard
        run={runFixture({ status: "CANCELLED" })}
        events={[iterationEvent]}
        result={null}
        isRunning={false}
      />,
    );

    expect(screen.getByText("Cancelled after 3 iterations.")).toBeInTheDocument();

    rerender(
      <RunOutcomeCard
        run={runFixture({ status: "CANCELLED", latest_estimate: null })}
        events={[]}
        result={null}
        isRunning={false}
      />,
    );

    expect(screen.getByText("Cancelled before any iterations were recorded.")).toBeInTheDocument();
  });
});
