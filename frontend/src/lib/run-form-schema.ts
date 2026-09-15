import { z } from "zod";

import {
  parseNumberArrayInput,
  parseParameterBoundsInput,
  parseProvidedSectorRowsInput,
  parseProvidedStateVectorInput,
  parseRecordInput,
} from "@/components/forms/run-form/manual-mode-config";
import { RUN_CONSTRAINTS } from "./run-form-constraints";
import { BACKEND_TARGETS, EASY_GOALS, RUN_ALGORITHMS } from "@/types/run-status";
import type { SimulationRunFormData } from "@/types/run";

const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const AER_STATEVECTOR_METHODS = new Set(["automatic", "statevector", "matrix_product_state"]);
const HARDWARE_MATRIX_DIM_LIMIT = 8;
const KQD_EASY_DIMS = { fastest: 2, balanced: 8, best_accuracy: 8 } as const;
const QFD_EASY_DIMS = { fastest: 2, balanced: 8, best_accuracy: 8 } as const;
type OptionalNullableNumber = number | null | undefined;
type IssuePath = (string | number)[];
type RunFormData = SimulationRunFormData;
type SpinResolvedSamplingData = Pick<
  RunFormData["advanced_sqd"],
  | "num_elec_a"
  | "num_elec_b"
  | "min_selected_configurations"
  | "seed"
  | "symmetrize_spin"
  | "max_dim_mode"
  | "max_dim"
  | "max_dim_a"
  | "max_dim_b"
  | "spin_sq_target"
  | "sci_solver_options_text"
>;

const uuidSchema = z
  .string({ error: "Molecule selection is required" })
  .regex(UUID_REGEX, "Molecule ID must be a valid UUID");

const requiredString = (message: string) => z.string().trim().min(1, message);

const nullableInteger = (fieldLabel: string) =>
  z
    .number({ error: `${fieldLabel} is required` })
    .int(`${fieldLabel} must be an integer`)
    .nullable();

const nullableNumber = (fieldLabel: string) =>
  z.number({ error: `${fieldLabel} is required` }).nullable();

const optionalNullableNumber = (fieldLabel: string) =>
  z.number({ error: `${fieldLabel} must be a number` }).nullable();

const optionalNullableInteger = (fieldLabel: string) =>
  z
    .number({ error: `${fieldLabel} must be an integer` })
    .int(`${fieldLabel} must be an integer`)
    .nullable();

const thermalNoiseProfileSchema = z
  .object({
    source: z.literal("custom_preset"),
    preset: z.literal("thermal_relaxation"),
    t1_us: z.number({ error: "T1 is required" }).positive("T1 must be greater than 0"),
    t2_us: z.number({ error: "T2 is required" }).positive("T2 must be greater than 0"),
    gate_time_us: z
      .number({ error: "Gate time is required" })
      .positive("Gate time must be greater than 0"),
  })
  .refine((profile) => profile.t2_us <= 2 * profile.t1_us, {
    path: ["t2_us"],
    message: "T2 must not exceed 2 × T1",
  });

function addNullableIntegerRangeIssue(
  ctx: z.RefinementCtx,
  path: (string | number)[],
  value: number | null,
  fieldLabel: string,
  min: number,
  max: number,
) {
  if (value == null) {
    ctx.addIssue({ code: "custom", path, message: `${fieldLabel} is required` });
    return;
  }

  if (!Number.isInteger(value)) {
    ctx.addIssue({ code: "custom", path, message: `${fieldLabel} must be an integer` });
    return;
  }

  if (value < min) {
    ctx.addIssue({ code: "custom", path, message: `${fieldLabel} must be at least ${min}` });
    return;
  }

  if (value > max) {
    ctx.addIssue({ code: "custom", path, message: `${fieldLabel} cannot exceed ${max}` });
  }
}

function addOptionalNullableIntegerRangeIssue(
  ctx: z.RefinementCtx,
  path: (string | number)[],
  value: OptionalNullableNumber,
  fieldLabel: string,
  min: number,
  max: number,
) {
  if (value == null) {
    return;
  }

  if (!Number.isInteger(value)) {
    ctx.addIssue({ code: "custom", path, message: `${fieldLabel} must be an integer` });
    return;
  }

  if (value < min) {
    ctx.addIssue({ code: "custom", path, message: `${fieldLabel} must be at least ${min}` });
    return;
  }

  if (value > max) {
    ctx.addIssue({ code: "custom", path, message: `${fieldLabel} cannot exceed ${max}` });
  }
}

function addPositiveNumberIssue(
  ctx: z.RefinementCtx,
  path: (string | number)[],
  value: number | null,
  fieldLabel: string,
) {
  if (value == null) {
    ctx.addIssue({ code: "custom", path, message: `${fieldLabel} is required` });
    return;
  }

  if (value <= 0) {
    ctx.addIssue({ code: "custom", path, message: `${fieldLabel} must be greater than 0` });
  }
}

function addOptionalPositiveNumberIssue(
  ctx: z.RefinementCtx,
  path: (string | number)[],
  value: OptionalNullableNumber,
  fieldLabel: string,
) {
  if (value == null) {
    return;
  }

  if (value <= 0) {
    ctx.addIssue({ code: "custom", path, message: `${fieldLabel} must be greater than 0` });
  }
}

function addOptionalNonNegativeNumberIssue(
  ctx: z.RefinementCtx,
  path: (string | number)[],
  value: OptionalNullableNumber,
  fieldLabel: string,
) {
  if (value == null) {
    return;
  }

  if (value < 0) {
    ctx.addIssue({ code: "custom", path, message: `${fieldLabel} cannot be negative` });
  }
}

function addCustomIssue(ctx: z.RefinementCtx, path: IssuePath, message: string) {
  ctx.addIssue({ code: "custom", path, message });
}

function addParserIssue(ctx: z.RefinementCtx, path: IssuePath, result: { error?: string | null }) {
  if (result.error) {
    addCustomIssue(ctx, path, result.error);
  }
}

function validateRequiredSelections(data: RunFormData, ctx: z.RefinementCtx) {
  if (data.molecule_id == null) {
    addCustomIssue(ctx, ["molecule_id"], "Molecule selection is required");
  }

  if (data.algorithm == null) {
    addCustomIssue(ctx, ["algorithm"], "Algorithm is required");
  }

  if (data.backend_target == null) {
    addCustomIssue(ctx, ["backend_target"], "Backend target is required");
  }
}

function validateManualIbmBackendSelection(data: RunFormData, ctx: z.RefinementCtx) {
  if (
    data.backend_target === "ibm_runtime" &&
    data.backend_options.selection_policy === "manual" &&
    (!data.backend_options.backend_name || data.backend_options.backend_name.trim().length === 0)
  ) {
    addCustomIssue(
      ctx,
      ["backend_options", "backend_name"],
      "Backend name is required for manual IBM selection",
    );
  }
}

function validateAerDenseProjectionRules(data: RunFormData, ctx: z.RefinementCtx) {
  const usesDenseProjection = data.algorithm === "kqd" || data.algorithm === "qfd";
  if (data.backend_target !== "aer_simulator" || !usesDenseProjection) {
    return;
  }

  const usesProjectedMatrixPath = data.noise_profile != null;
  const aerMethod = data.backend_options.aer_method ?? "automatic";
  if (!usesProjectedMatrixPath && !AER_STATEVECTOR_METHODS.has(aerMethod)) {
    addCustomIssue(
      ctx,
      ["backend_options", "aer_method"],
      "KQD and QFD require Aer method Automatic, Statevector, or MPS.",
    );
  }
}

function usesProjectedMatrixHardwareCap(data: RunFormData): boolean {
  return (
    (data.backend_target === "ibm_runtime" || data.noise_profile != null) &&
    (data.algorithm === "kqd" || data.algorithm === "qfd")
  );
}

function validateEasyModeProjectedMatrixCap(data: RunFormData, ctx: z.RefinementCtx) {
  if (
    !usesProjectedMatrixHardwareCap(data) ||
    data.mode !== "easy" ||
    (data.algorithm !== "kqd" && data.algorithm !== "qfd")
  ) {
    return;
  }

  const expandedDimension =
    data.algorithm === "kqd"
      ? KQD_EASY_DIMS[data.easy_options.goal]
      : QFD_EASY_DIMS[data.easy_options.goal];
  if (expandedDimension > HARDWARE_MATRIX_DIM_LIMIT) {
    const targetLabel =
      data.backend_target === "ibm_runtime" ? "IBM matrix-element" : "Aer projected";
    addCustomIssue(
      ctx,
      ["easy_options", "goal"],
      `${targetLabel} ${data.algorithm.toUpperCase()} is capped at ${HARDWARE_MATRIX_DIM_LIMIT} basis states.`,
    );
  }
}

function validateAdvancedModeProjectedMatrixCap(data: RunFormData, ctx: z.RefinementCtx) {
  if (!usesProjectedMatrixHardwareCap(data) || data.mode !== "advanced") {
    return;
  }

  const targetLabel =
    data.backend_target === "ibm_runtime" ? "IBM matrix-element" : "Aer projected";

  if (
    data.algorithm === "kqd" &&
    data.advanced_kqd.krylov_dim != null &&
    data.advanced_kqd.krylov_dim > HARDWARE_MATRIX_DIM_LIMIT
  ) {
    addCustomIssue(
      ctx,
      ["advanced_kqd", "krylov_dim"],
      `${targetLabel} KQD is capped at ${HARDWARE_MATRIX_DIM_LIMIT} Krylov states.`,
    );
  }

  if (
    data.algorithm === "qfd" &&
    data.advanced_qfd.num_time_points != null &&
    data.advanced_qfd.num_time_points > HARDWARE_MATRIX_DIM_LIMIT
  ) {
    addCustomIssue(
      ctx,
      ["advanced_qfd", "num_time_points"],
      `${targetLabel} QFD is capped at ${HARDWARE_MATRIX_DIM_LIMIT} time points.`,
    );
  }
}

function validateVqeAdvanced(data: RunFormData, ctx: z.RefinementCtx) {
  addNullableIntegerRangeIssue(
    ctx,
    ["advanced_vqe", "max_iterations"],
    data.advanced_vqe.max_iterations,
    "Max iterations",
    RUN_CONSTRAINTS.vqe.max_iterations.min,
    RUN_CONSTRAINTS.vqe.max_iterations.max,
  );
  addNullableIntegerRangeIssue(
    ctx,
    ["advanced_vqe", "max_function_evaluations"],
    data.advanced_vqe.max_function_evaluations,
    "Max objective evaluations",
    RUN_CONSTRAINTS.vqe.max_function_evaluations.min,
    RUN_CONSTRAINTS.vqe.max_function_evaluations.max,
  );
  addNullableIntegerRangeIssue(
    ctx,
    ["advanced_vqe", "reps"],
    data.advanced_vqe.reps,
    "Ansatz depth",
    RUN_CONSTRAINTS.vqe.reps.min,
    RUN_CONSTRAINTS.vqe.reps.max,
  );
  addNullableIntegerRangeIssue(
    ctx,
    ["advanced_vqe", "initial_point_candidates"],
    data.advanced_vqe.initial_point_candidates,
    "Starting candidates",
    RUN_CONSTRAINTS.vqe.initial_point_candidates.min,
    RUN_CONSTRAINTS.vqe.initial_point_candidates.max,
  );
  addOptionalNullableIntegerRangeIssue(
    ctx,
    ["advanced_vqe", "seed"],
    data.advanced_vqe.seed,
    "Seed",
    0,
    2 ** 32 - 1,
  );
  addOptionalPositiveNumberIssue(
    ctx,
    ["advanced_vqe", "convergence_threshold"],
    data.advanced_vqe.convergence_threshold,
    "Convergence threshold",
  );

  for (const [path, result] of [
    [
      ["advanced_vqe", "optimizer_options_text"],
      parseRecordInput(data.advanced_vqe.optimizer_options_text, "Optimizer options"),
    ],
    [
      ["advanced_vqe", "initial_parameters_text"],
      parseNumberArrayInput(data.advanced_vqe.initial_parameters_text, "Initial parameters"),
    ],
    [
      ["advanced_vqe", "parameter_bounds_text"],
      parseParameterBoundsInput(data.advanced_vqe.parameter_bounds_text),
    ],
  ] as const) {
    addParserIssue(ctx, Array.from(path), result);
  }
}

function validateSharedSpinResolvedMaxDims(
  ctx: z.RefinementCtx,
  prefix: "advanced_sqd" | "advanced_skqd",
  data: SpinResolvedSamplingData,
) {
  if (data.max_dim_mode === "shared") {
    addOptionalNullableIntegerRangeIssue(
      ctx,
      [prefix, "max_dim"],
      data.max_dim,
      "Shared max dimension",
      1,
      100_000,
    );
    return;
  }

  const hasEither = data.max_dim_a != null || data.max_dim_b != null;
  if (hasEither && (data.max_dim_a == null || data.max_dim_b == null)) {
    addCustomIssue(
      ctx,
      [prefix, "max_dim_b"],
      "Set both spin-resolved max dimensions or leave both empty",
    );
  }
  addOptionalNullableIntegerRangeIssue(
    ctx,
    [prefix, "max_dim_a"],
    data.max_dim_a,
    "Alpha max dimension",
    1,
    100_000,
  );
  addOptionalNullableIntegerRangeIssue(
    ctx,
    [prefix, "max_dim_b"],
    data.max_dim_b,
    "Beta max dimension",
    1,
    100_000,
  );
}

function validateSqdAdvanced(ctx: z.RefinementCtx, data: RunFormData["advanced_sqd"]) {
  addNullableIntegerRangeIssue(
    ctx,
    ["advanced_sqd", "samples_per_batch"],
    data.samples_per_batch,
    "Samples per batch",
    RUN_CONSTRAINTS.sqd.samples_per_batch.min,
    RUN_CONSTRAINTS.sqd.samples_per_batch.max,
  );
  addNullableIntegerRangeIssue(
    ctx,
    ["advanced_sqd", "num_batches"],
    data.num_batches,
    "Number of batches",
    RUN_CONSTRAINTS.sqd.num_batches.min,
    RUN_CONSTRAINTS.sqd.num_batches.max,
  );
  addNullableIntegerRangeIssue(
    ctx,
    ["advanced_sqd", "max_iterations"],
    data.max_iterations,
    "Max iterations",
    RUN_CONSTRAINTS.sqd.max_iterations.min,
    RUN_CONSTRAINTS.sqd.max_iterations.max,
  );
  if (data.sampling_state_source === "vqe") {
    if (data.sampling_vqe_ansatz_name.trim().length === 0) {
      addCustomIssue(
        ctx,
        ["advanced_sqd", "sampling_vqe_ansatz_name"],
        "Sampling VQE ansatz is required",
      );
    }
    if (data.sampling_vqe_optimizer_name.trim().length === 0) {
      addCustomIssue(
        ctx,
        ["advanced_sqd", "sampling_vqe_optimizer_name"],
        "Sampling VQE optimizer is required",
      );
    }
    addNullableIntegerRangeIssue(
      ctx,
      ["advanced_sqd", "sampling_vqe_max_iterations"],
      data.sampling_vqe_max_iterations,
      "Sampling VQE iterations",
      RUN_CONSTRAINTS.vqe.max_iterations.min,
      RUN_CONSTRAINTS.vqe.max_iterations.max,
    );
    addNullableIntegerRangeIssue(
      ctx,
      ["advanced_sqd", "sampling_vqe_reps"],
      data.sampling_vqe_reps,
      "Sampling VQE reps",
      RUN_CONSTRAINTS.vqe.reps.min,
      RUN_CONSTRAINTS.vqe.reps.max,
    );
  }
  addOptionalNullableIntegerRangeIssue(
    ctx,
    ["advanced_sqd", "sampling_vqe_seed"],
    data.sampling_vqe_seed,
    "Sampling VQE seed",
    0,
    2 ** 32 - 1,
  );
  addOptionalPositiveNumberIssue(
    ctx,
    ["advanced_sqd", "energy_tol"],
    data.energy_tol,
    "Energy tolerance",
  );
  addOptionalPositiveNumberIssue(
    ctx,
    ["advanced_sqd", "occupancies_tol"],
    data.occupancies_tol,
    "Occupancies tolerance",
  );
  addOptionalNonNegativeNumberIssue(
    ctx,
    ["advanced_sqd", "carryover_threshold"],
    data.carryover_threshold,
    "Carryover threshold",
  );
  if (data.carryover_threshold != null && data.carryover_threshold > 1) {
    addCustomIssue(
      ctx,
      ["advanced_sqd", "carryover_threshold"],
      "Carryover threshold cannot exceed 1",
    );
  }
  validateSqdSamplingControls(ctx, "advanced_sqd", data);
}

function validateSqdSamplingControls(
  ctx: z.RefinementCtx,
  prefix: "advanced_sqd" | "advanced_skqd",
  data: SpinResolvedSamplingData,
) {
  addOptionalNullableIntegerRangeIssue(
    ctx,
    [prefix, "num_elec_a"],
    data.num_elec_a,
    "Alpha electrons",
    0,
    10_000,
  );
  addOptionalNullableIntegerRangeIssue(
    ctx,
    [prefix, "num_elec_b"],
    data.num_elec_b,
    "Beta electrons",
    0,
    10_000,
  );
  addOptionalNullableIntegerRangeIssue(
    ctx,
    [prefix, "min_selected_configurations"],
    data.min_selected_configurations,
    "Min selected configurations",
    1,
    100_000,
  );
  addOptionalNullableIntegerRangeIssue(ctx, [prefix, "seed"], data.seed, "Seed", 0, 2 ** 32 - 1);
  addOptionalNonNegativeNumberIssue(
    ctx,
    [prefix, "spin_sq_target"],
    data.spin_sq_target,
    "Spin-squared target",
  );
  validateSharedSpinResolvedMaxDims(ctx, prefix, data);
  addParserIssue(
    ctx,
    [prefix, "sci_solver_options_text"],
    parseRecordInput(data.sci_solver_options_text, "SCI solver options"),
  );
}

function validateKqdAdvanced(data: RunFormData, ctx: z.RefinementCtx) {
  addNullableIntegerRangeIssue(
    ctx,
    ["advanced_kqd", "krylov_dim"],
    data.advanced_kqd.krylov_dim,
    "Krylov dimension",
    RUN_CONSTRAINTS.kqd.krylov_dim.min,
    RUN_CONSTRAINTS.kqd.krylov_dim.max,
  );
  addPositiveNumberIssue(
    ctx,
    ["advanced_kqd", "time_step"],
    data.advanced_kqd.time_step,
    "Time step",
  );
  if (data.advanced_kqd.evolution_method === "trotter") {
    addNullableIntegerRangeIssue(
      ctx,
      ["advanced_kqd", "trotter_steps"],
      data.advanced_kqd.trotter_steps,
      "Trotter steps",
      RUN_CONSTRAINTS.kqd.trotter_steps.min,
      RUN_CONSTRAINTS.kqd.trotter_steps.max,
    );
  }
  addPositiveNumberIssue(
    ctx,
    ["advanced_kqd", "residual_tolerance"],
    data.advanced_kqd.residual_tolerance,
    "Residual tolerance",
  );
}

function validateQfdAdvanced(data: RunFormData, ctx: z.RefinementCtx) {
  addNullableIntegerRangeIssue(
    ctx,
    ["advanced_qfd", "num_time_points"],
    data.advanced_qfd.num_time_points,
    "Time points",
    RUN_CONSTRAINTS.qfd.num_time_points.min,
    RUN_CONSTRAINTS.qfd.num_time_points.max,
  );
  addPositiveNumberIssue(ctx, ["advanced_qfd", "max_time"], data.advanced_qfd.max_time, "Max time");
  addNullableIntegerRangeIssue(
    ctx,
    ["advanced_qfd", "trotter_steps"],
    data.advanced_qfd.trotter_steps,
    "Trotter steps",
    RUN_CONSTRAINTS.qfd.trotter_steps.min,
    RUN_CONSTRAINTS.qfd.trotter_steps.max,
  );
  addPositiveNumberIssue(
    ctx,
    ["advanced_qfd", "residual_tolerance"],
    data.advanced_qfd.residual_tolerance,
    "Residual tolerance",
  );
}

function validateQseVqeReference(data: RunFormData, ctx: z.RefinementCtx) {
  if (data.advanced_qse.vqe_reference_ansatz_name.trim().length === 0) {
    addCustomIssue(
      ctx,
      ["advanced_qse", "vqe_reference_ansatz_name"],
      "Reference VQE ansatz is required",
    );
  }
  if (data.advanced_qse.vqe_reference_optimizer_name.trim().length === 0) {
    addCustomIssue(
      ctx,
      ["advanced_qse", "vqe_reference_optimizer_name"],
      "Reference VQE optimizer is required",
    );
  }
  addNullableIntegerRangeIssue(
    ctx,
    ["advanced_qse", "vqe_reference_max_iterations"],
    data.advanced_qse.vqe_reference_max_iterations,
    "Reference VQE iterations",
    RUN_CONSTRAINTS.qse.vqe_reference_max_iterations.min,
    RUN_CONSTRAINTS.qse.vqe_reference_max_iterations.max,
  );
  addNullableIntegerRangeIssue(
    ctx,
    ["advanced_qse", "vqe_reference_reps"],
    data.advanced_qse.vqe_reference_reps,
    "Reference VQE depth",
    RUN_CONSTRAINTS.qse.vqe_reference_reps.min,
    RUN_CONSTRAINTS.qse.vqe_reference_reps.max,
  );
}

function validateQseProvidedStateReference(data: RunFormData, ctx: z.RefinementCtx) {
  const parsed = parseProvidedStateVectorInput(data.advanced_qse.provided_state_vector_text);
  if (parsed.values == null || parsed.values.length === 0) {
    addCustomIssue(
      ctx,
      ["advanced_qse", "provided_state_vector_text"],
      parsed.error ?? "Provide a state vector for the QSE reference",
    );
  } else if (parsed.error) {
    addCustomIssue(ctx, ["advanced_qse", "provided_state_vector_text"], parsed.error);
  }
}

function validateQseProvidedSectorReference(data: RunFormData, ctx: z.RefinementCtx) {
  const parsed = parseProvidedSectorRowsInput(data.advanced_qse.provided_sector_rows);
  if (parsed.values == null || parsed.values.length === 0) {
    addCustomIssue(
      ctx,
      ["advanced_qse", "provided_sector_rows"],
      parsed.error ?? "Provide sector amplitudes for the QSE reference",
    );
  } else if (parsed.error) {
    addCustomIssue(ctx, ["advanced_qse", "provided_sector_rows"], parsed.error);
  }
}

function validateQseReferenceInputs(data: RunFormData, ctx: z.RefinementCtx) {
  switch (data.advanced_qse.reference_method) {
    case "vqe":
      validateQseVqeReference(data, ctx);
      break;
    case "provided_state":
      validateQseProvidedStateReference(data, ctx);
      break;
    case "provided_sector":
      validateQseProvidedSectorReference(data, ctx);
      break;
    default:
      break;
  }
}

function validateQseAdvanced(data: RunFormData, ctx: z.RefinementCtx) {
  addNullableIntegerRangeIssue(
    ctx,
    ["advanced_qse", "max_subspace_dim"],
    data.advanced_qse.max_subspace_dim,
    "Max subspace dimension",
    RUN_CONSTRAINTS.qse.max_subspace_dim.min,
    RUN_CONSTRAINTS.qse.max_subspace_dim.max,
  );
  validateQseReferenceInputs(data, ctx);
  addOptionalNonNegativeNumberIssue(
    ctx,
    ["advanced_qse", "regularization"],
    data.advanced_qse.regularization,
    "Regularization",
  );
  addOptionalPositiveNumberIssue(
    ctx,
    ["advanced_qse", "overlap_threshold"],
    data.advanced_qse.overlap_threshold,
    "Overlap threshold",
  );
  addPositiveNumberIssue(
    ctx,
    ["advanced_qse", "residual_tolerance"],
    data.advanced_qse.residual_tolerance,
    "Residual tolerance",
  );
}

function validateSkqdAdvanced(data: RunFormData, ctx: z.RefinementCtx) {
  addNullableIntegerRangeIssue(
    ctx,
    ["advanced_skqd", "samples_per_state"],
    data.advanced_skqd.samples_per_state,
    "Samples per Krylov state",
    RUN_CONSTRAINTS.skqd.samples_per_state.min,
    RUN_CONSTRAINTS.skqd.samples_per_state.max,
  );
  validateSqdSamplingControls(ctx, "advanced_skqd", data.advanced_skqd);
  addNullableIntegerRangeIssue(
    ctx,
    ["advanced_skqd", "krylov_extension_dim"],
    data.advanced_skqd.krylov_extension_dim,
    "Krylov extension dimension",
    RUN_CONSTRAINTS.skqd.krylov_extension_dim.min,
    RUN_CONSTRAINTS.skqd.krylov_extension_dim.max,
  );
  addPositiveNumberIssue(
    ctx,
    ["advanced_skqd", "time_step"],
    data.advanced_skqd.time_step,
    "Time step",
  );
  addPositiveNumberIssue(
    ctx,
    ["advanced_skqd", "residual_tolerance"],
    data.advanced_skqd.residual_tolerance,
    "Residual tolerance",
  );
}

function validateAdvancedAlgorithmSettings(data: RunFormData, ctx: z.RefinementCtx) {
  if (data.mode === "easy" || data.algorithm == null) {
    return;
  }

  switch (data.algorithm) {
    case "vqe":
      validateVqeAdvanced(data, ctx);
      return;
    case "sqd":
      validateSqdAdvanced(ctx, data.advanced_sqd);
      return;
    case "kqd":
      validateKqdAdvanced(data, ctx);
      return;
    case "qfd":
      validateQfdAdvanced(data, ctx);
      return;
    case "qse":
      validateQseAdvanced(data, ctx);
      return;
    case "skqd":
      validateSkqdAdvanced(data, ctx);
      return;
  }
}

export const runFormSchema = z
  .object({
    molecule_id: uuidSchema.nullable(),
    algorithm: z.enum(RUN_ALGORITHMS).nullable(),
    mode: z.enum(["easy", "advanced"]),
    backend_target: z.enum(BACKEND_TARGETS).nullable(),
    chemical_accuracy_target_ha: z.number().positive().nullable(),
    backend_options: z.object({
      selection_policy: z.enum(["manual", "least_busy", "least_error"]),
      backend_name: z.string().trim().nullable(),
      shots: z
        .number({ error: "Shots is required" })
        .int("Shots must be an integer")
        .min(1, "Shots must be at least 1")
        .max(1_000_000, "Shots cannot exceed 1000000"),
      optimization_level: z.union([z.literal(0), z.literal(1), z.literal(2), z.literal(3)], {
        error: "Optimization level must be between 0 and 3",
      }),
      seed_simulator: nullableInteger("Simulator seed"),
      seed_transpiler: nullableInteger("Transpiler seed"),
      aer_method: z
        .enum([
          "automatic",
          "statevector",
          "density_matrix",
          "matrix_product_state",
          "stabilizer",
          "extended_stabilizer",
          "unitary",
          "superop",
        ])
        .nullable(),
    }),
    noise_profile: z
      .union([
        z.object({
          source: z.literal("backend_derived"),
          reference_backend: requiredString("Reference backend is required").refine(
            (value) =>
              !["aer_simulator", "aer_simulator_statevector", "statevector"].includes(
                value.toLowerCase(),
              ),
            "Reference backend must be an IBM backend",
          ),
          temperature_mk: z
            .number()
            .nonnegative("Temperature must be non-negative")
            .nullable()
            .optional(),
        }),
        z.object({
          source: z.literal("custom_preset"),
          preset: z.literal("depolarizing_cx"),
          strength: z
            .number({ error: "Depolarizing probability is required" })
            .min(0, "Depolarizing probability must be at least 0")
            .max(1, "Depolarizing probability cannot exceed 1"),
        }),
        z.object({
          source: z.literal("custom_preset"),
          preset: z.literal("readout_bias"),
          p01: z
            .number({ error: "P(1|0) is required" })
            .min(0, "P(1|0) must be at least 0")
            .max(1, "P(1|0) cannot exceed 1"),
          p10: z
            .number({ error: "P(0|1) is required" })
            .min(0, "P(0|1) must be at least 0")
            .max(1, "P(0|1) cannot exceed 1"),
        }),
        thermalNoiseProfileSchema,
      ])
      .nullable(),
    basis_set_override: z.string(),
    easy_options: z.object({
      goal: z.enum(EASY_GOALS, { error: "Select a run goal" }),
    }),
    advanced_vqe: z.object({
      ansatz_name: requiredString("Ansatz is required"),
      optimizer_name: requiredString("Optimizer is required"),
      max_iterations: nullableInteger("Max iterations"),
      max_function_evaluations: nullableInteger("Max objective evaluations"),
      reps: z.number().int("Ansatz depth must be an integer"),
      initial_point_strategy: z.enum(["seeded_random", "zero", "zero_plus_seeded_random"], {
        error: "Initial point strategy is required",
      }),
      initial_point_candidates: nullableInteger("Starting candidates"),
      optimizer_options_text: z.string(),
      initial_parameters_text: z.string(),
      parameter_bounds_text: z.string(),
      seed: optionalNullableInteger("Seed"),
      convergence_threshold: optionalNullableNumber("Convergence threshold"),
    }),
    advanced_sqd: z.object({
      samples_per_batch: nullableInteger("Samples per batch"),
      num_batches: nullableInteger("Number of batches"),
      max_iterations: nullableInteger("Max iterations"),
      sampling_state_source: z.enum(["hf", "vqe"]),
      sampling_vqe_ansatz_name: z.string(),
      sampling_vqe_optimizer_name: z.string(),
      sampling_vqe_max_iterations: optionalNullableInteger("Sampling VQE iterations"),
      sampling_vqe_reps: optionalNullableInteger("Sampling VQE reps"),
      sampling_vqe_seed: optionalNullableInteger("Sampling VQE seed"),
      num_elec_a: optionalNullableInteger("Alpha electrons"),
      num_elec_b: optionalNullableInteger("Beta electrons"),
      energy_tol: optionalNullableNumber("Energy tolerance"),
      occupancies_tol: optionalNullableNumber("Occupancies tolerance"),
      min_selected_configurations: optionalNullableInteger("Min selected configurations"),
      seed: optionalNullableInteger("Seed"),
      symmetrize_spin: z.boolean(),
      carryover_threshold: optionalNullableNumber("Carryover threshold"),
      max_dim_mode: z.enum(["shared", "spin_resolved"]),
      max_dim: optionalNullableInteger("Shared max dimension"),
      max_dim_a: optionalNullableInteger("Alpha max dimension"),
      max_dim_b: optionalNullableInteger("Beta max dimension"),
      spin_sq_target: optionalNullableNumber("Spin-squared target"),
      sci_solver_options_text: z.string(),
    }),
    advanced_kqd: z.object({
      krylov_dim: nullableInteger("Krylov dimension"),
      time_step: nullableNumber("Time step"),
      evolution_method: z.enum(["exact", "trotter"], { error: "Evolution method is required" }),
      trotter_steps: nullableInteger("Trotter steps"),
      residual_tolerance: nullableNumber("Residual tolerance"),
    }),
    advanced_qfd: z.object({
      num_time_points: nullableInteger("Time points"),
      max_time: nullableNumber("Max time"),
      time_grid_type: z.enum(["linear", "geometric"]),
      trotter_steps: nullableInteger("Trotter steps"),
      residual_tolerance: nullableNumber("Residual tolerance"),
    }),
    advanced_qse: z.object({
      reference_method: z.enum(["hf", "vqe", "provided_state", "provided_sector"], {
        error: "Reference method is required",
      }),
      provided_state_vector_text: z.string(),
      provided_sector_rows: z.array(
        z.object({
          bitstring: z.string(),
          real: z.string(),
          imag: z.string(),
        }),
      ),
      excitation_level: z.enum(["singles", "singles_doubles"], {
        error: "Excitation level is required",
      }),
      max_subspace_dim: nullableInteger("Max subspace dimension"),
      vqe_reference_ansatz_name: z.string().trim(),
      vqe_reference_optimizer_name: z.string().trim(),
      vqe_reference_max_iterations: nullableInteger("Reference VQE iterations"),
      vqe_reference_reps: nullableInteger("Reference VQE depth"),
      regularization: optionalNullableNumber("Regularization"),
      overlap_threshold: optionalNullableNumber("Overlap threshold"),
      residual_tolerance: nullableNumber("Residual tolerance"),
    }),
    advanced_skqd: z.object({
      samples_per_state: nullableInteger("Samples per Krylov state"),
      num_elec_a: optionalNullableInteger("Alpha electrons"),
      num_elec_b: optionalNullableInteger("Beta electrons"),
      min_selected_configurations: optionalNullableInteger("Min selected configurations"),
      seed: optionalNullableInteger("Seed"),
      symmetrize_spin: z.boolean(),
      max_dim_mode: z.enum(["shared", "spin_resolved"]),
      max_dim: optionalNullableInteger("Shared max dimension"),
      max_dim_a: optionalNullableInteger("Alpha max dimension"),
      max_dim_b: optionalNullableInteger("Beta max dimension"),
      spin_sq_target: optionalNullableNumber("Spin-squared target"),
      sci_solver_options_text: z.string(),
      krylov_extension_dim: nullableInteger("Krylov extension dimension"),
      time_step: nullableNumber("Time step"),
      residual_tolerance: nullableNumber("Residual tolerance"),
    }),
  })
  .superRefine((data, ctx) => {
    validateRequiredSelections(data, ctx);
    validateManualIbmBackendSelection(data, ctx);

    if (data.algorithm == null) {
      return;
    }

    validateAerDenseProjectionRules(data, ctx);
    validateEasyModeProjectedMatrixCap(data, ctx);
    validateAdvancedModeProjectedMatrixCap(data, ctx);
    validateAdvancedAlgorithmSettings(data, ctx);
  }) satisfies z.ZodType<SimulationRunFormData>;

export type RunFormSchemaData = z.infer<typeof runFormSchema>;
