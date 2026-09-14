import { describe, expect, it } from "vitest";

import { getConvergenceInsight, getResultEventConvergenceLog } from "./convergence-status";
import type { RunEventResponse, RunResponse, RunResultResponse } from "@/types/run";

const baseRun: RunResponse = {
  id: "run-1",
  molecule_id: "mol-1",
  status: "RUNNING",
  algorithm: "vqe",
  mode: "advanced",
  backend_target: "aer_simulator",
  config_json: {},
  ibm_job_id: null,
  client_request_id: null,
  versions: null,
  metadata: null,
  created_at: "2025-06-01T10:00:00Z",
  updated_at: "2025-06-01T10:05:00Z",
};

const baseResult: RunResultResponse = {
  run_id: "run-1",
  energy: -1.137,
  iterations: 12,
  optimal_parameters: [],
  converged: false,
  created_at: "2025-06-01T10:05:00Z",
};

function iterationEvent(payload: Record<string, unknown>): RunEventResponse {
  return {
    id: 1,
    run_id: "run-1",
    sequence: 1,
    type: "iteration_update",
    payload,
    created_at: "2025-06-01T10:01:00Z",
  };
}

describe("getConvergenceInsight", () => {
  it("explains when SQD is close but blocked by too few selected configurations", () => {
    const insight = getConvergenceInsight({ ...baseRun, algorithm: "sqd" }, null, [
      iterationEvent({
        stage: "progress",
        step: "configuration_recovery",
        delta_energy: 2e-6,
        energy_tol: 1e-5,
        occupancy_delta: 5e-4,
        occupancies_tol: 1e-3,
        selected_samples: 1,
        min_selected_configurations: 4,
        converged_candidate: false,
        convergence_blocked_reason: "insufficient_selected_configurations",
      }),
    ]);

    expect(insight).not.toBeNull();
    expect(insight?.label).toBe("Convergence check");
    expect(insight?.value).toContain("too few configurations survived");
    expect(insight?.helper).toContain("dE 2.00e-6 <= 1.00e-5 Ha");
    expect(insight?.helper).toContain("selected 1 < 4");
  });

  it("explains when VQE stops at the evaluation budget", () => {
    const insight = getConvergenceInsight(
      {
        ...baseRun,
        status: "COMPLETED",
        config_json: {
          advanced_config: {
            algorithm: "vqe",
            ansatz_name: "EfficientSU2",
            optimizer_name: "COBYLA",
            max_iterations: 16,
            convergence_threshold: 1e-5,
            max_function_evaluations: 16,
          },
        },
      },
      {
        ...baseResult,
        iterations: 16,
        algorithm_metrics: {
          objective_evaluations: 16,
          optimizer_diagnostics: {
            termination_reason: "max_function_evaluations",
            final_delta_energy: 2e-4,
            max_function_evaluations: 16,
          },
        },
      },
      [],
    );

    expect(insight).not.toBeNull();
    expect(insight?.label).toBe("Stopped because");
    expect(insight?.value).toContain("function-evaluation budget");
    expect(insight?.helper).toContain("|dE| 2.00e-4 > 1.00e-5 Ha");
    expect(insight?.helper).toContain("evals 16 / 16");
  });

  it("explains residual-based QSE convergence", () => {
    const insight = getConvergenceInsight(
      { ...baseRun, status: "COMPLETED", algorithm: "qse" },
      {
        ...baseResult,
        converged: true,
        algorithm_metrics: {
          relative_residual: 5e-9,
          convergence_threshold: 1e-6,
        },
      },
      [],
    );

    expect(insight).not.toBeNull();
    expect(insight?.value).toContain("fell within tolerance");
    expect(insight?.helper).toContain("residual 5.00e-9 <= 1.00e-6");
  });

  it("surfaces the per-algorithm exclusion message from run metadata", () => {
    const insight = getConvergenceInsight(
      {
        ...baseRun,
        status: "EXCLUDED",
        algorithm: "skqd",
        metadata: {
          exclusion_reason: "skqd_sampler_circuit_exceeds_local_aer_limit",
          exclusion_message:
            "SKQD sampler execution needs to simulate 16-qubit Trotter circuits on the local Aer simulator, which exceeds the 14-qubit limit.",
        },
      },
      null,
      [],
    );

    expect(insight?.label).toBe("Not run because");
    expect(insight?.value).toContain("16-qubit Trotter circuits");
    expect(insight?.value).not.toContain("unsupported on the selected target");
  });

  it("surfaces the exclusion message from the EXCLUDED status event when metadata is absent", () => {
    const excludedEvent: RunEventResponse = {
      id: 2,
      run_id: "run-1",
      sequence: 2,
      type: "status_changed",
      payload: {
        status: "EXCLUDED",
        exclusion_reason: "projected_matrix_active_space_too_large",
        exclusion_message:
          "Noisy Aer QSE projected-matrix runs are limited to active spaces up to 6 orbitals in the current rollout.",
      },
      created_at: "2025-06-01T10:02:00Z",
    };
    const insight = getConvergenceInsight(
      { ...baseRun, status: "EXCLUDED", algorithm: "qse" },
      null,
      [excludedEvent],
    );

    expect(insight?.label).toBe("Not run because");
    expect(insight?.value).toContain("projected-matrix runs are limited");
  });

  it("humanizes a bare exclusion reason when no message is available", () => {
    const insight = getConvergenceInsight(
      {
        ...baseRun,
        status: "EXCLUDED",
        algorithm: "kqd",
        metadata: { exclusion_reason: "projected_matrix_active_space_too_large" },
      },
      null,
      [],
    );

    expect(insight?.value).toBe("Excluded: projected matrix active space too large");
  });
});

describe("getResultEventConvergenceLog", () => {
  it("prefers an explicit stop reason and normalizes unsupported tones", () => {
    expect(
      getResultEventConvergenceLog({
        stop_reason: "Operator stopped the run",
        stop_reason_details: "Manual cancellation requested",
        stop_reason_tone: "info",
      }),
    ).toEqual({
      summary: "Operator stopped the run",
      details: "Manual cancellation requested",
      tone: "muted",
    });
  });

  it("summarizes VQE budget stops with optimizer diagnostics", () => {
    expect(
      getResultEventConvergenceLog({
        algorithm: " VQE ",
        converged: false,
        iterations: 16,
        algorithm_metrics: {
          objective_evaluations: 16,
          optimizer_diagnostics: {
            termination_reason: "max_function_evaluations",
            final_delta_energy: 2e-4,
            convergence_threshold: 1e-5,
            max_function_evaluations: 16,
          },
        },
      }),
    ).toEqual({
      summary: "The run reached the function-evaluation budget",
      details: "|dE| 2.00e-4 > 1.00e-5 Ha · evals 16 / 16",
      tone: "warning",
    });
  });

  it("summarizes SQD selected-configuration stops", () => {
    expect(
      getResultEventConvergenceLog({
        algorithm: "sqd",
        converged: false,
        algorithm_metrics: {
          configuration_recovery_trace: [
            {
              accepted_samples: 2,
              delta_energy: 5e-6,
              occupancy_delta: 8e-4,
            },
          ],
          postselection_summary: {
            min_selected_configurations: 4,
          },
        },
      }),
    ).toEqual({
      summary: "The SQD recovery gate missed the minimum selected configuration count",
      details: "selected 2 < 4 · dE 5.00e-6 Ha · dOcc 8.00e-4",
      tone: "warning",
    });
  });

  it("summarizes projected overlap gates", () => {
    expect(
      getResultEventConvergenceLog({
        algorithm: "kqd",
        converged: true,
        algorithm_metrics: {
          matrix_element_summary: {
            convergence_basis: "projected_overlap_condition",
          },
          orthogonality_metrics: {
            overlap_condition: 2.5e-3,
            overlap_min_eigenvalue: 8e-4,
          },
        },
      }),
    ).toEqual({
      summary: "The projected overlap gate passed",
      details: "condition 2.50e-3 · min eigenvalue 8.00e-4",
      tone: "success",
    });
  });

  it("summarizes projected residual gates", () => {
    expect(
      getResultEventConvergenceLog({
        algorithm: "kqd",
        converged: false,
        algorithm_metrics: {
          relative_ritz_residual: 2e-4,
          residual_convergence_threshold: 1e-5,
        },
      }),
    ).toEqual({
      summary: "The projected residual stayed above tolerance",
      details: "residual 2.00e-4 > 1.00e-5",
      tone: "warning",
    });
  });

  it("summarizes stabilized projected overlap solves as not converged", () => {
    expect(
      getResultEventConvergenceLog({
        algorithm: "qfd",
        converged: false,
        algorithm_metrics: {
          matrix_element_summary: {
            convergence_basis: "projected_overlap_condition",
          },
          stability_summary: {
            stability_state: "stabilized",
          },
          conditioning_summary: {
            stability_state: "stabilized",
            overlap_condition: 88.1,
            overlap_min_eigenvalue: 8.98e-2,
          },
        },
      }),
    ).toEqual({
      summary:
        "The projected overlap solve needed stabilization, so it was not treated as converged",
      details: "condition 8.81e+1 · min eigenvalue 8.98e-2",
      tone: "warning",
    });
  });

  it("summarizes QSE residual gates", () => {
    expect(
      getResultEventConvergenceLog({
        algorithm: "qse",
        converged: true,
        algorithm_metrics: {
          relative_residual: 5e-9,
          convergence_threshold: 1e-6,
        },
      }),
    ).toEqual({
      summary: "The projected residual fell within tolerance",
      details: "residual 5.00e-9 <= 1.00e-6",
      tone: "success",
    });
  });

  it("summarizes SKQD selected paths", () => {
    expect(
      getResultEventConvergenceLog({
        algorithm: "skqd",
        converged: false,
        algorithm_metrics: {
          krylov_extension_diagnostics: {
            selected_solution: "krylov_extension",
            sqd_converged: true,
            krylov_converged: false,
          },
        },
      }),
    ).toEqual({
      summary: "The Krylov extension residual stayed above tolerance",
      details: "selected krylov extension · SQD yes · Krylov no",
      tone: "warning",
    });
  });

  it("returns null until a result event includes a boolean convergence value", () => {
    expect(
      getResultEventConvergenceLog({
        algorithm: "vqe",
        converged: "false",
      }),
    ).toBeNull();
  });
});
