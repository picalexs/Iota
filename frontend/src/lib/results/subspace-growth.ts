import type { RunEventResponse } from "@/types/run";

export type SubspaceGrowthAlgorithm = "kqd" | "qfd" | "qse" | "skqd";

export interface SubspaceGrowthPoint {
  stepIndex: number;
  energy: number;
  timePoint?: number;
  relativeResidual?: number;
}

const ALLOWED_STEPS: Record<SubspaceGrowthAlgorithm, Set<string>> = {
  kqd: new Set(["time_evolution", "projected_subspace_progress", "solve"]),
  qfd: new Set(["time_evolution", "projected_subspace_progress", "solve"]),
  qse: new Set(["build_basis", "solve"]),
  skqd: new Set(["krylov_extension"]),
};

function numericValue(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function resolveStepIndex(payload: Record<string, unknown>): number | null {
  return (
    numericValue(payload.convergence_iteration) ??
    numericValue(payload.basis_rank) ??
    numericValue(payload.subspace_dim) ??
    numericValue(payload.completed_iterations) ??
    numericValue(payload.iteration)
  );
}

export function subspaceGrowthFromEvents(
  events: RunEventResponse[],
  algorithm: SubspaceGrowthAlgorithm,
): SubspaceGrowthPoint[] {
  const allowedSteps = ALLOWED_STEPS[algorithm];
  const pointsByIndex = new Map<number, SubspaceGrowthPoint>();

  for (const event of events) {
    if (event.type !== "iteration_update") continue;
    const payload = event.payload;
    if (payload.algorithm !== algorithm) continue;
    const step = typeof payload.step === "string" ? payload.step : null;
    if (step == null || !allowedSteps.has(step)) continue;

    const energy = numericValue(payload.energy);
    const stepIndex = resolveStepIndex(payload);
    if (energy == null || stepIndex == null) continue;

    pointsByIndex.set(stepIndex, {
      stepIndex,
      energy,
      timePoint: numericValue(payload.time_point) ?? undefined,
      relativeResidual: numericValue(payload.relative_residual) ?? undefined,
    });
  }

  return Array.from(pointsByIndex.values()).sort((left, right) => left.stepIndex - right.stepIndex);
}
