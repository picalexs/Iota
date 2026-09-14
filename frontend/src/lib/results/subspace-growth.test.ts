import { describe, expect, it } from "vitest";

import { subspaceGrowthFromEvents } from "./subspace-growth";
import type { RunEventResponse } from "@/types/run";

describe("subspaceGrowthFromEvents", () => {
  it("keeps QSE build-basis and solve points ordered by subspace size", () => {
    const events: RunEventResponse[] = [
      {
        id: 1,
        run_id: "run-1",
        sequence: 1,
        type: "iteration_update",
        payload: {
          algorithm: "qse",
          step: "build_basis",
          completed_iterations: 1,
          energy: -1,
        },
        created_at: "2026-01-01T10:00:00Z",
      },
      {
        id: 2,
        run_id: "run-1",
        sequence: 2,
        type: "iteration_update",
        payload: {
          algorithm: "qse",
          step: "solve",
          subspace_dim: 2,
          energy: -1.2,
        },
        created_at: "2026-01-01T10:00:01Z",
      },
    ];

    expect(subspaceGrowthFromEvents(events, "qse")).toEqual([
      { stepIndex: 1, energy: -1, timePoint: undefined, relativeResidual: undefined },
      { stepIndex: 2, energy: -1.2, timePoint: undefined, relativeResidual: undefined },
    ]);
  });

  it("uses projected-subspace progress for branch-estimator KQD runs", () => {
    const events: RunEventResponse[] = [
      {
        id: 1,
        run_id: "run-1",
        sequence: 1,
        type: "iteration_update",
        payload: {
          algorithm: "kqd",
          step: "projected_subspace_progress",
          convergence_iteration: 3,
          energy: -108.4,
          relative_residual: 1e-7,
        },
        created_at: "2026-01-01T10:00:00Z",
      },
    ];

    expect(subspaceGrowthFromEvents(events, "kqd")).toEqual([
      { stepIndex: 3, energy: -108.4, timePoint: undefined, relativeResidual: 1e-7 },
    ]);
  });
});
