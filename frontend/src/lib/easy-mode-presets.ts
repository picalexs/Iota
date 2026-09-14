import type { EasyGoal, RunAlgorithm } from "@/types/run";

export const GUIDED_GOAL_OPTIONS: Array<{
  value: EasyGoal;
  label: string;
  description: string;
}> = [
  {
    value: "fastest",
    label: "Quick scan",
    description: "Small search spaces and loose tolerances for fast feedback.",
  },
  {
    value: "balanced",
    label: "Production default",
    description: "Moderate budgets that are useful for day-to-day comparisons.",
  },
  {
    value: "best_accuracy",
    label: "High accuracy",
    description: "Larger subspaces, samples, and VQE budgets for tighter energies.",
  },
];

export function guidedPresetHighlights(algorithm: RunAlgorithm | null, goal: EasyGoal): string[] {
  if (algorithm === null) {
    return ["Pick an algorithm to see the exact preset values."];
  }

  const highlights: Record<RunAlgorithm, Record<EasyGoal, string[]>> = {
    vqe: {
      fastest: ["NumberPreserving reps 2", "128 COBYLA iterations", "1 start candidate"],
      balanced: ["NumberPreserving reps 2", "448 COBYLA iterations", "2 start candidates"],
      best_accuracy: ["NumberPreserving reps 2", "512 COBYLA iterations", "4 start candidates"],
    },
    sqd: {
      fastest: ["256 samples x 4 batches", "4 recovery rounds", "VQE sampling: 128 iterations"],
      balanced: ["512 samples x 8 batches", "8 recovery rounds", "VQE sampling: 448 iterations"],
      best_accuracy: [
        "1024 samples x 16 batches",
        "12 recovery rounds",
        "VQE sampling: 512 iterations",
      ],
    },
    kqd: {
      fastest: ["Krylov dim 4", "Exact evolution", "time step 0.35"],
      balanced: ["Krylov dim 8", "Exact evolution", "time step 0.35"],
      best_accuracy: ["Krylov dim 12", "Exact evolution", "time step 0.50"],
    },
    qfd: {
      fastest: ["4 time points", "max time 0.5", "linear grid"],
      balanced: ["8 time points", "max time 2.5", "linear grid"],
      best_accuracy: ["12 time points", "max time 4.0", "geometric grid"],
    },
    qse: {
      fastest: ["HF reference", "subspace dim 4", "singles excitations"],
      balanced: ["HF reference", "subspace dim 8", "singles + doubles"],
      best_accuracy: ["HF reference", "subspace dim 12", "singles + doubles"],
    },
    skqd: {
      fastest: ["512 samples per Krylov state", "selected-CI cap 16", "Krylov extension 1"],
      balanced: ["1024 samples per Krylov state", "selected-CI cap 32", "Krylov extension 4"],
      best_accuracy: ["2048 samples per Krylov state", "selected-CI cap 64", "Krylov extension 6"],
    },
  };

  return highlights[algorithm][goal];
}
