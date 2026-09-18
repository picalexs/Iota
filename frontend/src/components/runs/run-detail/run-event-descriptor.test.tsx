import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RunEventDescriptor } from "./run-event-descriptor";
import {
  getErrorPayloadText,
  getIterationUpdateLabel,
  getIterationUpdatePresentation,
  getSpecificIterationUpdatePresentation,
} from "./run-event-descriptor-utils";

describe("getIterationUpdatePresentation", () => {
  it("labels backend selection setup milestones explicitly", () => {
    const presentation = getIterationUpdatePresentation({
      stage: "setup",
      step: "backend_selected",
      message: "Selected aer_simulator backend; building molecular Hamiltonian next.",
    });

    expect(presentation.label).toBe("Backend selected");
    expect(presentation.summary).toBe(
      "Selected aer_simulator backend; building molecular Hamiltonian next.",
    );
  });

  it("labels measured-QSE matrix-element progress as measurement steps", () => {
    const presentation = getIterationUpdatePresentation({
      algorithm: "qse",
      step: "measured_matrix_elements",
      stage: "progress",
      completed_iterations: 12,
      total_iterations: 36,
    });

    expect(presentation.label).toBe("Measurement step");
    expect(
      getIterationUpdateLabel({
        algorithm: "qse",
        step: "measured_matrix_elements",
        stage: "progress",
      }),
    ).toBe("Measurement step");
  });

  it("describes VQE iterations as objective evaluations", () => {
    const presentation = getIterationUpdatePresentation(
      {
        algorithm: "vqe",
        step: "optimize",
        phase_iteration: 5,
        energy: -1.234567,
      },
      {
        source: "telemetry",
        algorithm: "vqe",
        estimated_total_iterations: 100,
        estimated_remaining_iterations: 95,
        estimated_total_seconds: 95,
        estimated_remaining_seconds: 95,
        confidence: 0.7,
        updated_at: "2025-06-01T10:00:00Z",
      },
    );

    expect(presentation.label).toBe("Objective eval");
    expect(presentation.summary).toContain("Objective eval 5");
    expect(presentation.summary).toContain("Energy -1.234567 Ha");
    expect(presentation.summary).toContain("ETA 1m 35s");
  });

  it("explains SQD selected-CI batch progress", () => {
    const presentation = getIterationUpdatePresentation({
      algorithm: "sqd",
      step: "selected_ci_solve",
      phase_iteration: 3,
      sci_batch: 2,
      sci_batches: 8,
      selected_ci_dimension: 32,
    });

    expect(presentation.label).toBe("Selected-CI solve");
    expect(presentation.summary).toBe("SQD iter 3 · Batch 2/8 · Dim 32");
  });

  it("describes SQD sampling as total samples rather than backend shots", () => {
    const presentation = getIterationUpdatePresentation({
      algorithm: "sqd",
      step: "sampling",
      phase_iteration: 1,
      total_samples: 24576,
    });

    expect(presentation.label).toBe("Sampling");
    expect(presentation.summary).toBe("SQD iter 1 · Sampling 24576 samples");
  });

  it("shows QSE reference optimization separately from the main solve", () => {
    const presentation = getIterationUpdatePresentation({
      algorithm: "qse",
      step: "reference_vqe",
      phase_iteration: 7,
      energy: -1.11,
    });

    expect(presentation.label).toBe("Reference VQE");
    expect(presentation.summary).toBe("Reference eval 7 · Energy -1.110000 Ha");
  });

  it("prefixes SQD core iterations inside SKQD runs", () => {
    const presentation = getIterationUpdatePresentation(
      {
        algorithm: "sqd",
        step: "configuration_recovery",
        phase_iteration: 4,
        energy: -1.9,
        selected_samples: 24,
      },
      null,
      "skqd",
    );

    expect(presentation.label).toBe("SQD core recovery");
    expect(presentation.summary).toBe("SQD core iter 4 · Energy -1.900000 Ha · 24 accepted");
  });

  it("formats hardware matrix element progress with pair details", () => {
    const presentation = getIterationUpdatePresentation({
      algorithm: "qfd",
      step: "hardware_matrix_elements",
      phase_completed_iterations: 3,
      total_iterations: 10,
      matrix_element_pair: [1, 2],
      energy: null,
      matrix_element_value: -1.2,
    });

    expect(presentation.label).toBe("Matrix element");
    expect(presentation.summary).toBe(
      "Matrix element 3/10 · Pair (1, 2) · H diagonal -1.200000 Ha",
    );
  });

  it("labels a stabilized projected energy as diagnostic", () => {
    const presentation = getIterationUpdatePresentation({
      algorithm: "qfd",
      step: "solve",
      stage: "completed",
      total_iterations: 8,
      energy: null,
      diagnostic_energy: -1.2,
      energy_state: "diagnostic",
    });

    expect(presentation.summary).toContain("Diagnostic energy -1.200000 Ha");
  });

  it("covers projected, Krylov, filter, and QSE progress labels", () => {
    expect(
      getIterationUpdatePresentation({
        algorithm: "qse",
        step: "build_basis",
        display_iteration: 2,
        total_iterations: 6,
        excitation_kind: "single_double",
        energy: -1.05,
      }).summary,
    ).toBe("Basis vector 2/6 · single double excitation · Energy -1.050000 Ha");

    expect(
      getIterationUpdatePresentation({
        algorithm: "qse",
        step: "solve",
        subspace_dim: 12,
        energy: -1.2,
      }).summary,
    ).toBe("Subspace dim 12 · Energy -1.200000 Ha");

    expect(
      getIterationUpdatePresentation({
        algorithm: "kqd",
        step: "time_evolution",
        phase_iteration: 4,
        total_iterations: 9,
        time_point: 0.75,
      }).summary,
    ).toBe("Time point 4/9 · t=0.75");

    expect(
      getIterationUpdatePresentation({
        algorithm: "qfd",
        step: "time_evolution",
        phase_iteration: 3,
        total_iterations: 5,
        time_point: 1.5,
      }).summary,
    ).toBe("Time point 3/5 · t=1.5");

    expect(
      getIterationUpdatePresentation({
        step: "projected_subspace_progress",
        basis_rank: 8,
        energy: -1.25,
      }).summary,
    ).toBe("Projected rank 8 · Energy -1.250000 Ha");
  });

  it("formats SQD postselection, batch completion, and SKQD extension events", () => {
    expect(
      getIterationUpdatePresentation({
        algorithm: "sqd",
        step: "postselection",
        phase_iteration: 2,
        selected_samples: 128,
      }).summary,
    ).toBe("SQD iter 2 · Selected 128 configs");

    expect(
      getIterationUpdatePresentation({
        algorithm: "sqd",
        step: "selected_ci_batch_completed",
        phase_iteration: 2,
        sci_batch: 1,
        sci_batches: 4,
        batch_energy: -1.3,
      }).summary,
    ).toBe("SQD iter 2 · Batch 1/4 · Energy -1.300000 Ha");

    expect(
      getIterationUpdatePresentation({
        algorithm: "skqd",
        step: "krylov_extension",
        phase_completed_iterations: 5,
        total_iterations: 7,
        energy: -1.4,
      }).summary,
    ).toBe("Extension vector 5/7 · Energy -1.400000 Ha");
  });

  it("formats non-algorithm stage events and fallback rows", () => {
    expect(
      getIterationUpdatePresentation({
        stage: "control",
        control: "pause_requested",
        message: "Pause accepted",
      }),
    ).toMatchObject({ label: "Pause Requested", summary: "Pause accepted" });

    expect(
      getIterationUpdatePresentation({
        stage: "restart",
        message: "Restarted from checkpoint",
        energy: -1.01,
      }),
    ).toMatchObject({
      label: "Restarted",
      summary: "Restarted from checkpoint · Energy -1.010000 Ha",
    });

    expect(getIterationUpdatePresentation({ stage: "checkpoint" })).toMatchObject({
      label: "Checkpoint saved",
      summary: "Saved an intermediate checkpoint",
    });

    expect(
      getIterationUpdatePresentation({
        stage: "hardware",
        status: "job_running",
        message: "IBM job is active",
      }),
    ).toMatchObject({ label: "Job Running", summary: "IBM job is active" });

    expect(
      getIterationUpdatePresentation({
        stage: "error",
        message: "Solver failed",
        error: "bad matrix",
      }),
    ).toMatchObject({ label: "Error", summary: "Solver failed · bad matrix" });

    expect(getIterationUpdatePresentation({ message: "Working", energy: -1.5 })).toMatchObject({
      label: "Iteration",
      summary: "Working · Energy -1.500000 Ha",
    });
  });

  it("exposes specific labels and error payload text fallbacks", () => {
    expect(getIterationUpdateLabel({ algorithm: "kqd", step: "solve", basis_rank: 3 })).toBe(
      "Krylov solve",
    );
    expect(getIterationUpdateLabel({ algorithm: "qfd", stage: "completed", energy: -1.7 })).toBe(
      "Filter solve",
    );
    expect(getSpecificIterationUpdatePresentation({ step: "unknown" })).toBeNull();
    expect(
      getErrorPayloadText({
        summary: "Summary",
        message: "Message",
        error_message: "Message",
        error: "Error",
        stack: "Stack",
      }),
    ).toBe("Summary\n\nMessage\n\nError\n\nStack");
    expect(
      getErrorPayloadText({
        error_message: "Run execution failed. Check worker logs for details.",
        error_type: "ValueError",
      }),
    ).toBe("Run execution failed. Check worker logs for details.\n\nValueError");
    expect(
      getErrorPayloadText({
        error_message: "Run execution failed. Check worker logs for details.",
        error_type: "JobTimeoutException",
        timeout_seconds: 3600,
      }),
    ).toBe("Run timed out after reaching the 1h 0m execution limit.");
    expect(getErrorPayloadText({})).toBe("Unknown error");
  });

  it("includes the stop reason in result log rows", () => {
    render(
      <RunEventDescriptor
        type="result"
        payload={{
          algorithm: "vqe",
          energy: -1.137,
          converged: false,
          iterations: 24,
          algorithm_metrics: {
            objective_evaluations: 24,
            max_function_evaluations: 24,
            optimizer_diagnostics: {
              termination_reason: "max_function_evaluations",
              final_delta_energy: 2e-4,
              convergence_threshold: 1e-5,
            },
          },
        }}
      />,
    );

    expect(screen.getByText(/function-evaluation budget/)).toBeInTheDocument();
  });
});
