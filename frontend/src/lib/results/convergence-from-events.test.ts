import { describe, expect, it } from "vitest";

import { convergenceFromEvents, mergeConvergenceTrace } from "./convergence-from-events";
import type { RunEventResponse } from "@/types/run";

function iterationEvent(payload: Record<string, unknown>, sequence: number): RunEventResponse {
  return {
    id: sequence,
    run_id: "aaaaaaaa-0000-0000-0000-000000000001",
    sequence,
    type: "iteration_update",
    payload,
    created_at: "2026-01-01T00:00:00Z",
  };
}

describe("convergenceFromEvents", () => {
  it("plots a measured-QSE solve energy at iteration 1, not its measurement-step count", () => {
    const points = convergenceFromEvents([
      iterationEvent(
        {
          algorithm: "qse",
          step: "solve",
          stage: "completed",
          energy: -1.1366508,
          iteration: 44,
          completed_iterations: 44,
          convergence_iteration: null,
          subspace_dim: 8,
        },
        1,
      ),
    ]);

    expect(points).toEqual([{ iteration: 1, energy: -1.1366508 }]);
  });

  it("uses normalized completed iterations for x values", () => {
    const points = convergenceFromEvents([
      iterationEvent({ energy: -1, completed_iterations: 3 }, 1),
      iterationEvent({ energy: -1.1, iteration: 5 }, 2),
    ]);

    expect(points.map((point) => point.iteration)).toEqual([3, 5]);
  });

  it("keeps the latest energy for duplicate final iteration markers", () => {
    const points = convergenceFromEvents([
      iterationEvent({ energy: -1, completed_iterations: 1 }, 1),
      iterationEvent({ energy: -1.1, completed_iterations: 2, stage: "progress" }, 2),
      iterationEvent({ energy: -1.2, completed_iterations: 2, stage: "completed" }, 3),
    ]);

    expect(points).toHaveLength(2);
    expect(points[1]).toMatchObject({ iteration: 2, energy: -1.2 });
  });

  it("ignores diagonal hardware matrix-element values as algorithm energies", () => {
    const points = convergenceFromEvents([
      iterationEvent(
        {
          energy: -108,
          completed_iterations: 9,
          step: "hardware_matrix_elements",
          matrix_element_pair: [1, 1],
        },
        1,
      ),
      iterationEvent({ energy: -109, completed_iterations: 1, step: "solve" }, 2),
    ]);

    expect(points).toEqual([{ iteration: 1, energy: -109 }]);
  });

  it("keeps projected branch progress as the algorithm energy", () => {
    const points = convergenceFromEvents([
      iterationEvent(
        {
          energy: -108,
          completed_iterations: 9,
          step: "hardware_matrix_elements",
          matrix_element_pair: [1, 1],
        },
        1,
      ),
      iterationEvent(
        {
          energy: -108.8,
          completed_iterations: 9,
          convergence_iteration: 2,
          step: "projected_subspace_progress",
        },
        2,
      ),
    ]);

    expect(points).toEqual([{ iteration: 2, energy: -108.8 }]);
  });

  it("uses explicit convergence iteration for branch-estimator projected progress", () => {
    const points = convergenceFromEvents([
      iterationEvent(
        {
          energy: -108.8,
          completed_iterations: 9,
          convergence_iteration: 2,
          step: "projected_subspace_progress",
        },
        1,
      ),
      iterationEvent(
        {
          energy: -109,
          completed_iterations: 44,
          convergence_iteration: 8,
          step: "solve",
        },
        2,
      ),
    ]);

    expect(points).toEqual([
      { iteration: 2, energy: -108.8 },
      { iteration: 8, energy: -109 },
    ]);
  });

  it("does not present final eigenspectra as fallback convergence traces", () => {
    expect(
      mergeConvergenceTrace([], {
        ritz_values: [-1, -0.5],
        filter_eigenvalues: [-1, -0.5],
        eigenvalues: [-1, -0.5],
        krylov_extension_diagnostics: { ritz_values: [-1, -0.5] },
      }),
    ).toEqual([]);
  });
});
