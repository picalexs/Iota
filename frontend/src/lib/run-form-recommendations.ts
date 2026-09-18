import type {
  ActiveSpaceSchema,
  EasyGoal,
  EasyGoalPresetMetadata,
  RunAlgorithm,
  RunConfigMetadataResponse,
  SimulationRunFormData,
} from "@/types/run";

type OptionalActiveSpace = ActiveSpaceSchema | null | undefined;

export type ChemicalAccuracyTargetOption = {
  goal: EasyGoal;
  label: string;
  thresholdHa: number;
};

export const CHEMICAL_ACCURACY_TARGET_OPTIONS: ChemicalAccuracyTargetOption[] = [
  { goal: "fastest", label: "5.0 mHa", thresholdHa: 5e-3 },
  { goal: "balanced", label: "1.6 mHa", thresholdHa: 1.6e-3 },
  { goal: "best_accuracy", label: "0.5 mHa", thresholdHa: 5e-4 },
];

export function getChemicalAccuracyTargetOptions(
  presets: readonly EasyGoalPresetMetadata[] | null | undefined,
): ChemicalAccuracyTargetOption[] {
  if (presets == null || presets.length === 0) {
    return CHEMICAL_ACCURACY_TARGET_OPTIONS;
  }

  return presets.map((preset) => ({
    goal: preset.goal,
    label: preset.label,
    thresholdHa: preset.chemical_accuracy_target_ha,
  }));
}

type AdvancedField =
  | "advanced_vqe"
  | "advanced_sqd"
  | "advanced_kqd"
  | "advanced_qfd"
  | "advanced_qse"
  | "advanced_skqd";

export interface RecommendedAdvancedPatch {
  field: AdvancedField;
  value: SimulationRunFormData[AdvancedField];
}

type RecommendationMetadata = Pick<RunConfigMetadataResponse, "recommendations">;

function mergeServerRecommendation<T extends object>(
  fallback: T,
  algorithm: RunAlgorithm,
  goal: EasyGoal,
  metadata: RecommendationMetadata | null | undefined,
): T {
  const recommendation = metadata?.recommendations?.[algorithm]?.[goal];
  if (recommendation == null) {
    return fallback;
  }

  const knownFields = new Set(Object.keys(fallback));
  const serverFields = Object.fromEntries(
    Object.entries(recommendation).filter(([key]) => knownFields.has(key)),
  );
  return { ...fallback, ...serverFields };
}

function splitElectrons(activeSpace: OptionalActiveSpace): {
  num_elec_a: number;
  num_elec_b: number;
} | null {
  const totalElectrons = activeSpace?.n_electrons;
  if (
    typeof totalElectrons !== "number" ||
    !Number.isInteger(totalElectrons) ||
    totalElectrons < 0
  ) {
    return null;
  }
  const num_elec_a = Math.floor(totalElectrons / 2);
  return { num_elec_a, num_elec_b: totalElectrons - num_elec_a };
}

export function goalForChemicalAccuracyTarget(
  thresholdHa: number | null | undefined,
  options: readonly ChemicalAccuracyTargetOption[] = CHEMICAL_ACCURACY_TARGET_OPTIONS,
): EasyGoal {
  if (typeof thresholdHa !== "number" || !Number.isFinite(thresholdHa) || thresholdHa <= 0) {
    return "balanced";
  }

  const [firstOption, ...remainingOptions] = options;
  if (!firstOption) {
    return "balanced";
  }

  return remainingOptions.reduce((best, candidate) => {
    const bestDistance = Math.abs(best.thresholdHa - thresholdHa);
    const candidateDistance = Math.abs(candidate.thresholdHa - thresholdHa);
    return candidateDistance < bestDistance ? candidate : best;
  }, firstOption).goal;
}

function buildVqePatch(goal: EasyGoal): RecommendedAdvancedPatch {
  const valueByGoal: Record<EasyGoal, SimulationRunFormData["advanced_vqe"]> = {
    fastest: {
      ansatz_name: "NumberPreserving",
      optimizer_name: "COBYLA",
      max_iterations: 128,
      max_function_evaluations: 128,
      reps: 2,
      initial_point_strategy: "zero_plus_seeded_random",
      initial_point_candidates: 1,
      optimizer_options_text: "",
      initial_parameters_text: "",
      parameter_bounds_text: "",
      seed: null,
      convergence_threshold: null,
    },
    balanced: {
      ansatz_name: "NumberPreserving",
      optimizer_name: "COBYLA",
      max_iterations: 448,
      max_function_evaluations: 448,
      reps: 2,
      initial_point_strategy: "zero_plus_seeded_random",
      initial_point_candidates: 2,
      optimizer_options_text: "",
      initial_parameters_text: "",
      parameter_bounds_text: "",
      seed: null,
      convergence_threshold: null,
    },
    best_accuracy: {
      ansatz_name: "NumberPreserving",
      optimizer_name: "COBYLA",
      max_iterations: 512,
      max_function_evaluations: 512,
      reps: 2,
      initial_point_strategy: "zero_plus_seeded_random",
      initial_point_candidates: 4,
      optimizer_options_text: "",
      initial_parameters_text: "",
      parameter_bounds_text: "",
      seed: null,
      convergence_threshold: null,
    },
  };

  return { field: "advanced_vqe", value: valueByGoal[goal] };
}

function buildSqdPatch(
  goal: EasyGoal,
  electronSplit: ReturnType<typeof splitElectrons>,
): RecommendedAdvancedPatch {
  const baseByGoal: Record<EasyGoal, SimulationRunFormData["advanced_sqd"]> = {
    fastest: {
      samples_per_batch: 256,
      num_batches: 4,
      max_iterations: 4,
      sampling_state_source: "vqe",
      sampling_vqe_ansatz_name: "NumberPreserving",
      sampling_vqe_optimizer_name: "COBYLA",
      sampling_vqe_max_iterations: 128,
      sampling_vqe_reps: 1,
      sampling_vqe_seed: null,
      num_elec_a: electronSplit?.num_elec_a ?? null,
      num_elec_b: electronSplit?.num_elec_b ?? null,
      energy_tol: 1e-4,
      occupancies_tol: 1e-4,
      min_selected_configurations: 2,
      seed: null,
      symmetrize_spin: false,
      carryover_threshold: null,
      max_dim_mode: "shared",
      max_dim: 16,
      max_dim_a: null,
      max_dim_b: null,
      spin_sq_target: null,
      sci_solver_options_text: "",
    },
    balanced: {
      samples_per_batch: 512,
      num_batches: 8,
      max_iterations: 8,
      sampling_state_source: "vqe",
      sampling_vqe_ansatz_name: "NumberPreserving",
      sampling_vqe_optimizer_name: "COBYLA",
      sampling_vqe_max_iterations: 448,
      sampling_vqe_reps: 2,
      sampling_vqe_seed: null,
      num_elec_a: electronSplit?.num_elec_a ?? null,
      num_elec_b: electronSplit?.num_elec_b ?? null,
      energy_tol: 7.5e-5,
      occupancies_tol: 7.5e-5,
      min_selected_configurations: 2,
      seed: null,
      symmetrize_spin: false,
      carryover_threshold: null,
      max_dim_mode: "shared",
      max_dim: 32,
      max_dim_a: null,
      max_dim_b: null,
      spin_sq_target: null,
      sci_solver_options_text: "",
    },
    best_accuracy: {
      samples_per_batch: 1024,
      num_batches: 16,
      max_iterations: 12,
      sampling_state_source: "vqe",
      sampling_vqe_ansatz_name: "NumberPreserving",
      sampling_vqe_optimizer_name: "COBYLA",
      sampling_vqe_max_iterations: 512,
      sampling_vqe_reps: 2,
      sampling_vqe_seed: null,
      num_elec_a: electronSplit?.num_elec_a ?? null,
      num_elec_b: electronSplit?.num_elec_b ?? null,
      energy_tol: 5e-5,
      occupancies_tol: 5e-5,
      min_selected_configurations: 2,
      seed: null,
      symmetrize_spin: false,
      carryover_threshold: null,
      max_dim_mode: "shared",
      max_dim: 64,
      max_dim_a: null,
      max_dim_b: null,
      spin_sq_target: null,
      sci_solver_options_text: "",
    },
  };

  return { field: "advanced_sqd", value: baseByGoal[goal] };
}

function buildKqdPatch(goal: EasyGoal): RecommendedAdvancedPatch {
  const valueByGoal: Record<EasyGoal, SimulationRunFormData["advanced_kqd"]> = {
    fastest: {
      krylov_dim: 4,
      time_step: 0.35,
      evolution_method: "exact",
      trotter_steps: 1,
      residual_tolerance: 1e-8,
    },
    balanced: {
      krylov_dim: 8,
      time_step: 0.35,
      evolution_method: "exact",
      trotter_steps: 1,
      residual_tolerance: 1e-8,
    },
    best_accuracy: {
      krylov_dim: 12,
      time_step: 0.5,
      evolution_method: "exact",
      trotter_steps: 1,
      residual_tolerance: 1e-8,
    },
  };

  return { field: "advanced_kqd", value: valueByGoal[goal] };
}

function buildQfdPatch(goal: EasyGoal): RecommendedAdvancedPatch {
  const valueByGoal: Record<EasyGoal, SimulationRunFormData["advanced_qfd"]> = {
    fastest: {
      num_time_points: 4,
      max_time: 0.5,
      time_grid_type: "linear",
      trotter_steps: 1,
      residual_tolerance: 1e-6,
    },
    balanced: {
      num_time_points: 8,
      max_time: 2.5,
      time_grid_type: "linear",
      trotter_steps: 1,
      residual_tolerance: 1e-6,
    },
    best_accuracy: {
      num_time_points: 12,
      max_time: 4,
      time_grid_type: "geometric",
      trotter_steps: 1,
      residual_tolerance: 1e-6,
    },
  };

  return { field: "advanced_qfd", value: valueByGoal[goal] };
}

function buildQsePatch(goal: EasyGoal): RecommendedAdvancedPatch {
  const vqeReferenceByGoal = {
    fastest: {
      ansatz: "EfficientSU2",
      optimizer: "COBYLA",
      iterations: 128,
      reps: 1,
    },
    balanced: {
      ansatz: "EfficientSU2",
      optimizer: "COBYLA",
      iterations: 256,
      reps: 1,
    },
    best_accuracy: {
      ansatz: "EfficientSU2",
      optimizer: "COBYLA",
      iterations: 512,
      reps: 1,
    },
  } as const;
  const selectedVqe = vqeReferenceByGoal[goal];

  const valueByGoal: Record<EasyGoal, SimulationRunFormData["advanced_qse"]> = {
    fastest: {
      reference_method: "hf",
      provided_state_vector_text: "[1, 0]",
      provided_sector_rows: [{ bitstring: "", real: "1", imag: "0" }],
      excitation_level: "singles",
      max_subspace_dim: 4,
      vqe_reference_ansatz_name: selectedVqe.ansatz,
      vqe_reference_optimizer_name: selectedVqe.optimizer,
      vqe_reference_max_iterations: selectedVqe.iterations,
      vqe_reference_reps: selectedVqe.reps,
      regularization: 1e-6,
      overlap_threshold: 1e-4,
      residual_tolerance: 1e-8,
    },
    balanced: {
      reference_method: "hf",
      provided_state_vector_text: "[1, 0]",
      provided_sector_rows: [{ bitstring: "", real: "1", imag: "0" }],
      excitation_level: "singles_doubles",
      max_subspace_dim: 8,
      vqe_reference_ansatz_name: selectedVqe.ansatz,
      vqe_reference_optimizer_name: selectedVqe.optimizer,
      vqe_reference_max_iterations: selectedVqe.iterations,
      vqe_reference_reps: selectedVqe.reps,
      regularization: 1e-7,
      overlap_threshold: 1e-5,
      residual_tolerance: 1e-8,
    },
    best_accuracy: {
      reference_method: "hf",
      provided_state_vector_text: "[1, 0]",
      provided_sector_rows: [{ bitstring: "", real: "1", imag: "0" }],
      excitation_level: "singles_doubles",
      max_subspace_dim: 12,
      vqe_reference_ansatz_name: selectedVqe.ansatz,
      vqe_reference_optimizer_name: selectedVqe.optimizer,
      vqe_reference_max_iterations: selectedVqe.iterations,
      vqe_reference_reps: selectedVqe.reps,
      regularization: 1e-7,
      overlap_threshold: 5e-6,
      residual_tolerance: 1e-8,
    },
  };

  return { field: "advanced_qse", value: valueByGoal[goal] };
}

function buildSkqdPatch(
  goal: EasyGoal,
  electronSplit: ReturnType<typeof splitElectrons>,
): RecommendedAdvancedPatch {
  const valueByGoal: Record<EasyGoal, SimulationRunFormData["advanced_skqd"]> = {
    fastest: {
      samples_per_state: 512,
      num_elec_a: electronSplit?.num_elec_a ?? null,
      num_elec_b: electronSplit?.num_elec_b ?? null,
      min_selected_configurations: 2,
      seed: null,
      symmetrize_spin: false,
      max_dim_mode: "shared",
      max_dim: 16,
      max_dim_a: null,
      max_dim_b: null,
      spin_sq_target: null,
      sci_solver_options_text: "",
      krylov_extension_dim: 1,
      time_step: 0.2,
      residual_tolerance: 1e-6,
    },
    balanced: {
      samples_per_state: 1024,
      num_elec_a: electronSplit?.num_elec_a ?? null,
      num_elec_b: electronSplit?.num_elec_b ?? null,
      min_selected_configurations: 2,
      seed: null,
      symmetrize_spin: false,
      max_dim_mode: "shared",
      max_dim: 32,
      max_dim_a: null,
      max_dim_b: null,
      spin_sq_target: null,
      sci_solver_options_text: "",
      krylov_extension_dim: 4,
      time_step: 0.22,
      residual_tolerance: 1e-6,
    },
    best_accuracy: {
      samples_per_state: 2048,
      num_elec_a: electronSplit?.num_elec_a ?? null,
      num_elec_b: electronSplit?.num_elec_b ?? null,
      min_selected_configurations: 2,
      seed: null,
      symmetrize_spin: false,
      max_dim_mode: "shared",
      max_dim: 64,
      max_dim_a: null,
      max_dim_b: null,
      spin_sq_target: null,
      sci_solver_options_text: "",
      krylov_extension_dim: 6,
      time_step: 0.26,
      residual_tolerance: 1e-6,
    },
  };

  return { field: "advanced_skqd", value: valueByGoal[goal] };
}

export function buildRecommendedAdvancedPatch(
  algorithm: RunAlgorithm,
  goal: EasyGoal,
  activeSpace: OptionalActiveSpace,
  metadata?: RecommendationMetadata | null,
): RecommendedAdvancedPatch {
  const electronSplit = splitElectrons(activeSpace);

  let patch: RecommendedAdvancedPatch;
  switch (algorithm) {
    case "vqe":
      patch = buildVqePatch(goal);
      break;
    case "sqd":
      patch = buildSqdPatch(goal, electronSplit);
      break;
    case "kqd":
      patch = buildKqdPatch(goal);
      break;
    case "qfd":
      patch = buildQfdPatch(goal);
      break;
    case "qse":
      patch = buildQsePatch(goal);
      break;
    default:
      patch = buildSkqdPatch(goal, electronSplit);
  }

  return {
    field: patch.field,
    value: mergeServerRecommendation(patch.value, algorithm, goal, metadata),
  } as RecommendedAdvancedPatch;
}
