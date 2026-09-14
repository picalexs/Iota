/**
 * Per-algorithm numeric constraints matching backend/app/services/validation_service.py.
 * These are the ceilings enforced server-side; the frontend must mirror them
 * so users never build a payload that 422s on a limit check.
 */

// validation_service.py:96–105 (VQE max_iterations ≤ 5000)
// validation_service.py:107–127 (SQD samples_per_batch ≤ 2000, num_batches ≤ 128, max_iterations ≤ 5000)
// run_config.py (SKQD samples_per_state ≤ 4096)
// validation_service.py:138–147 (KQD krylov_dim ≤ 64)
// validation_service.py / guardrails.py (QFD num_time_points ≤ 128, trotter_steps ≤ 32)
export const RUN_CONSTRAINTS = {
  vqe: {
    max_iterations: { min: 1, max: 5000 },
    max_function_evaluations: { min: 1, max: 250000 },
    reps: { min: 1, max: 6 },
    initial_point_candidates: { min: 1, max: 16 },
  },
  sqd: {
    samples_per_batch: { min: 1, max: 2000 },
    num_batches: { min: 1, max: 128 },
    max_iterations: { min: 1, max: 5000 },
  },
  kqd: {
    krylov_dim: { min: 2, max: 64 },
    time_step: { min: 1e-6, max: Infinity },
    trotter_steps: { min: 1, max: 32 },
  },
  qfd: {
    num_time_points: { min: 2, max: 128 },
    max_time: { min: 1e-6, max: Infinity },
    trotter_steps: { min: 1, max: 32 },
  },
  qse: {
    max_subspace_dim: { min: 1, max: 96 },
    vqe_reference_max_iterations: { min: 1, max: 1000 },
    vqe_reference_reps: { min: 1, max: 6 },
  },
  skqd: {
    samples_per_state: { min: 1, max: 4096 },
    krylov_extension_dim: { min: 1, max: 32 },
    time_step: { min: 1e-6, max: Infinity },
  },
} as const;
