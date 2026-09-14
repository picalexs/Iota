import type {
  AdvancedConfig,
  AlgorithmAwareRunCreate,
  RunAlgorithm,
  SimulationRunFormData,
} from "@/types/run";
import {
  parseNumberArrayInput,
  parseParameterBoundsInput,
  parseProvidedSectorRowsInput,
  parseProvidedStateVectorInput,
  parseRecordInput,
} from "@/components/forms/run-form/manual-mode-config";

function requireNumber(value: number | null, field: string): number {
  if (value == null) throw new Error(`${field} is required`);
  return value;
}

function requireParsed<T>(result: { values: T | null; error?: string }, field: string): T {
  if (result.values == null) {
    throw new Error(result.error ?? `${field} is invalid`);
  }
  return result.values;
}

function maybeSharedMaxDim(
  mode: "shared" | "spin_resolved",
  value: number | null,
  valueA: number | null,
  valueB: number | null,
): number | [number, number] | null {
  if (mode === "shared") {
    return value ?? null;
  }
  if (valueA == null || valueB == null) {
    return null;
  }
  return [valueA, valueB];
}

interface BuildRunCreateOptions {
  ibmRuntimeConfirmed?: boolean;
}

export function buildAdvancedConfigFromFormValues(values: SimulationRunFormData): AdvancedConfig {
  if (values.algorithm == null) {
    throw new Error("algorithm is required");
  }

  switch (values.algorithm) {
    case "vqe":
      return {
        algorithm: "vqe",
        ansatz_name: values.advanced_vqe.ansatz_name,
        optimizer_name: values.advanced_vqe.optimizer_name,
        max_iterations: requireNumber(values.advanced_vqe.max_iterations, "max_iterations"),
        max_function_evaluations: requireNumber(
          values.advanced_vqe.max_function_evaluations,
          "max_function_evaluations",
        ),
        reps: values.advanced_vqe.reps,
        initial_point_strategy: values.advanced_vqe.initial_point_strategy,
        initial_point_candidates: requireNumber(
          values.advanced_vqe.initial_point_candidates,
          "initial_point_candidates",
        ),
        optimizer_options: parseRecordInput(
          values.advanced_vqe.optimizer_options_text,
          "Optimizer options",
        ).values,
        initial_parameters: parseNumberArrayInput(
          values.advanced_vqe.initial_parameters_text,
          "Initial parameters",
        ).values,
        parameter_bounds: parseParameterBoundsInput(values.advanced_vqe.parameter_bounds_text)
          .values,
        seed: values.advanced_vqe.seed,
        convergence_threshold: values.advanced_vqe.convergence_threshold,
      };
    case "sqd":
      return {
        algorithm: "sqd",
        samples_per_batch: requireNumber(
          values.advanced_sqd.samples_per_batch,
          "samples_per_batch",
        ),
        num_batches: requireNumber(values.advanced_sqd.num_batches, "num_batches"),
        max_iterations: requireNumber(values.advanced_sqd.max_iterations, "max_iterations"),
        sampling_state_source: values.advanced_sqd.sampling_state_source,
        ...(values.advanced_sqd.sampling_state_source === "vqe"
          ? {
              sampling_vqe_ansatz_name: values.advanced_sqd.sampling_vqe_ansatz_name,
              sampling_vqe_optimizer_name: values.advanced_sqd.sampling_vqe_optimizer_name,
              sampling_vqe_max_iterations: requireNumber(
                values.advanced_sqd.sampling_vqe_max_iterations,
                "sampling_vqe_max_iterations",
              ),
              sampling_vqe_reps: requireNumber(
                values.advanced_sqd.sampling_vqe_reps,
                "sampling_vqe_reps",
              ),
              sampling_vqe_seed: values.advanced_sqd.sampling_vqe_seed,
            }
          : {}),
        num_elec_a: values.advanced_sqd.num_elec_a,
        num_elec_b: values.advanced_sqd.num_elec_b,
        energy_tol: values.advanced_sqd.energy_tol,
        occupancies_tol: values.advanced_sqd.occupancies_tol,
        min_selected_configurations: values.advanced_sqd.min_selected_configurations,
        seed: values.advanced_sqd.seed,
        symmetrize_spin: values.advanced_sqd.symmetrize_spin,
        carryover_threshold: values.advanced_sqd.carryover_threshold,
        max_dim: maybeSharedMaxDim(
          values.advanced_sqd.max_dim_mode,
          values.advanced_sqd.max_dim,
          values.advanced_sqd.max_dim_a,
          values.advanced_sqd.max_dim_b,
        ),
        spin_sq_target: values.advanced_sqd.spin_sq_target,
        sci_solver_options: parseRecordInput(
          values.advanced_sqd.sci_solver_options_text,
          "SCI solver options",
        ).values,
      };
    case "kqd":
      return {
        algorithm: "kqd",
        krylov_dim: requireNumber(values.advanced_kqd.krylov_dim, "krylov_dim"),
        time_step: requireNumber(values.advanced_kqd.time_step, "time_step"),
        evolution_method: values.advanced_kqd.evolution_method,
        trotter_steps: requireNumber(values.advanced_kqd.trotter_steps, "trotter_steps"),
        residual_tolerance: requireNumber(
          values.advanced_kqd.residual_tolerance,
          "residual_tolerance",
        ),
      };
    case "qfd":
      return {
        algorithm: "qfd",
        num_time_points: requireNumber(values.advanced_qfd.num_time_points, "num_time_points"),
        max_time: requireNumber(values.advanced_qfd.max_time, "max_time"),
        time_grid_type: values.advanced_qfd.time_grid_type,
        trotter_steps: requireNumber(values.advanced_qfd.trotter_steps, "trotter_steps"),
        residual_tolerance: requireNumber(
          values.advanced_qfd.residual_tolerance,
          "residual_tolerance",
        ),
      };
    case "qse": {
      const providedStateVector =
        values.advanced_qse.reference_method === "provided_state"
          ? requireParsed(
              parseProvidedStateVectorInput(values.advanced_qse.provided_state_vector_text),
              "provided_state_vector",
            )
          : null;
      const providedSectorAmplitudes =
        values.advanced_qse.reference_method === "provided_sector"
          ? requireParsed(
              parseProvidedSectorRowsInput(values.advanced_qse.provided_sector_rows),
              "provided_sector_amplitudes",
            )
          : null;
      return {
        algorithm: "qse",
        reference_method: values.advanced_qse.reference_method,
        provided_state_vector:
          values.advanced_qse.reference_method === "provided_state" ? providedStateVector : null,
        provided_sector_amplitudes:
          values.advanced_qse.reference_method === "provided_sector"
            ? providedSectorAmplitudes
            : null,
        excitation_level: values.advanced_qse.excitation_level,
        max_subspace_dim: requireNumber(values.advanced_qse.max_subspace_dim, "max_subspace_dim"),
        ...(values.advanced_qse.reference_method === "vqe"
          ? {
              vqe_reference_ansatz_name: values.advanced_qse.vqe_reference_ansatz_name,
              vqe_reference_optimizer_name: values.advanced_qse.vqe_reference_optimizer_name,
              vqe_reference_max_iterations: requireNumber(
                values.advanced_qse.vqe_reference_max_iterations,
                "vqe_reference_max_iterations",
              ),
              vqe_reference_reps: requireNumber(
                values.advanced_qse.vqe_reference_reps,
                "vqe_reference_reps",
              ),
            }
          : {}),
        regularization: values.advanced_qse.regularization,
        overlap_threshold: values.advanced_qse.overlap_threshold,
        residual_tolerance: requireNumber(
          values.advanced_qse.residual_tolerance,
          "residual_tolerance",
        ),
      };
    }
    case "skqd":
      return {
        algorithm: "skqd",
        samples_per_state: requireNumber(
          values.advanced_skqd.samples_per_state,
          "samples_per_state",
        ),
        base_sampling_options: {
          num_elec_a: values.advanced_skqd.num_elec_a,
          num_elec_b: values.advanced_skqd.num_elec_b,
          min_selected_configurations: values.advanced_skqd.min_selected_configurations,
          seed: values.advanced_skqd.seed,
          symmetrize_spin: values.advanced_skqd.symmetrize_spin,
          max_dim: maybeSharedMaxDim(
            values.advanced_skqd.max_dim_mode,
            values.advanced_skqd.max_dim,
            values.advanced_skqd.max_dim_a,
            values.advanced_skqd.max_dim_b,
          ),
          spin_sq_target: values.advanced_skqd.spin_sq_target,
          sci_solver_options: parseRecordInput(
            values.advanced_skqd.sci_solver_options_text,
            "SCI solver options",
          ).values,
        },
        krylov_extension_dim: requireNumber(
          values.advanced_skqd.krylov_extension_dim,
          "krylov_extension_dim",
        ),
        time_step: requireNumber(values.advanced_skqd.time_step, "time_step"),
        residual_tolerance: requireNumber(
          values.advanced_skqd.residual_tolerance,
          "residual_tolerance",
        ),
      };
    default: {
      const neverAlgorithm: never = values.algorithm;
      throw new Error(`Unsupported algorithm: ${String(neverAlgorithm)}`);
    }
  }
}

export function buildAlgorithmAwareRunCreate(
  values: SimulationRunFormData,
  options: BuildRunCreateOptions = {},
): AlgorithmAwareRunCreate {
  if (!values.molecule_id) {
    throw new Error("molecule_id is required");
  }
  if (!values.algorithm) {
    throw new Error("algorithm is required");
  }
  if (!values.backend_target) {
    throw new Error("backend_target is required");
  }

  const payloadBase: Omit<AlgorithmAwareRunCreate, "easy_options" | "advanced_config"> = {
    molecule_id: values.molecule_id,
    algorithm: values.algorithm,
    mode: values.mode,
    backend_target: values.backend_target,
    chemical_accuracy_target_ha: values.chemical_accuracy_target_ha,
    backend_options: {
      ...values.backend_options,
      backend_name:
        values.backend_options.backend_name != null &&
        values.backend_options.backend_name.trim().length > 0
          ? values.backend_options.backend_name.trim()
          : null,
      aer_method:
        values.backend_target === "aer_simulator"
          ? (values.backend_options.aer_method ?? "automatic")
          : "automatic",
      seed_simulator: values.backend_options.seed_simulator ?? null,
      seed_transpiler: values.backend_options.seed_transpiler ?? null,
    },
    noise_profile: values.noise_profile,
    ...(options.ibmRuntimeConfirmed ? { ibm_runtime_confirmed: true } : {}),
    ...(values.basis_set_override.trim().length > 0
      ? { basis_set_override: values.basis_set_override.trim() }
      : {}),
  };

  if (values.mode === "easy") {
    return {
      ...payloadBase,
      easy_options: values.easy_options,
    };
  }

  return {
    ...payloadBase,
    advanced_config: buildAdvancedConfigFromFormValues(values),
  };
}

export const RUN_ALGORITHM_OPTIONS: Array<{ value: RunAlgorithm; label: string }> = [
  { value: "vqe", label: "VQE" },
  { value: "qse", label: "QSE" },
  { value: "kqd", label: "KQD" },
  { value: "qfd", label: "QFD" },
  { value: "sqd", label: "SQD" },
  { value: "skqd", label: "SKQD" },
];
