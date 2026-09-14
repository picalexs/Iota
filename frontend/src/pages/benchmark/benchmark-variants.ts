import { initialValues } from "@/components/forms/run-form/constants";
import {
  buildRecommendedAdvancedPatch,
  goalForChemicalAccuracyTarget,
} from "@/lib/run-form-recommendations";
import { buildAdvancedConfigFromFormValues } from "@/lib/run-create-payload";
import type {
  AdvancedConfig,
  EasyGoal,
  KQDAdvancedConfig,
  QFDAdvancedConfig,
  QSEAdvancedConfig,
  RunAlgorithm,
  RunConfigMetadataResponse,
  SimulationRunFormData,
  SKQDAdvancedConfig,
  SQDAdvancedConfig,
  VQEAdvancedConfig,
} from "@/types/run";

export type BenchmarkVariantMode = "simple" | "advanced";

export interface BenchmarkAlgorithmVariant {
  id: string;
  algorithm: RunAlgorithm;
  mode: BenchmarkVariantMode;
  label: string;
  easyGoal: EasyGoal | null;
  advancedConfig: AdvancedConfig | null;
}

let benchmarkVariantCounter = 0;

function normalizeVariantLabelValue(label: string): string {
  return label.trim().toLowerCase();
}

function matchesLegacyCopyLabel(candidate: string, baseLabel: string): boolean {
  const normalizedCandidate = normalizeVariantLabelValue(candidate);
  const normalizedBaseLabel = normalizeVariantLabelValue(baseLabel);
  if (normalizedBaseLabel.length === 0) {
    return false;
  }
  if (normalizedCandidate === normalizedBaseLabel) {
    return true;
  }
  return normalizedCandidate === `${normalizedBaseLabel} copy` ||
    normalizedCandidate.startsWith(`${normalizedBaseLabel} copy `)
    ? /^copy(?: copy)*$/.test(normalizedCandidate.slice(normalizedBaseLabel.length + 1).trim())
    : false;
}

function cloneInitialValues(): SimulationRunFormData {
  return {
    ...initialValues,
    backend_options: { ...initialValues.backend_options },
    easy_options: { ...initialValues.easy_options },
    advanced_vqe: { ...initialValues.advanced_vqe },
    advanced_sqd: { ...initialValues.advanced_sqd },
    advanced_kqd: { ...initialValues.advanced_kqd },
    advanced_qfd: { ...initialValues.advanced_qfd },
    advanced_qse: {
      ...initialValues.advanced_qse,
      provided_sector_rows: initialValues.advanced_qse.provided_sector_rows.map((row) => ({
        ...row,
      })),
    },
    advanced_skqd: { ...initialValues.advanced_skqd },
  };
}

function createVariantId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  benchmarkVariantCounter += 1;
  return `variant-${Date.now()}-${benchmarkVariantCounter}`;
}

function applyRecommendedPatch(
  values: SimulationRunFormData,
  algorithm: RunAlgorithm,
  chemicalAccuracyHa: number,
  configMetadata?: RunConfigMetadataResponse | null,
) {
  const goal = goalForChemicalAccuracyTarget(chemicalAccuracyHa);
  const patch = buildRecommendedAdvancedPatch(algorithm, goal, null, configMetadata);
  switch (patch.field) {
    case "advanced_vqe":
      values.advanced_vqe = patch.value as SimulationRunFormData["advanced_vqe"];
      return;
    case "advanced_sqd":
      values.advanced_sqd = patch.value as SimulationRunFormData["advanced_sqd"];
      return;
    case "advanced_kqd":
      values.advanced_kqd = patch.value as SimulationRunFormData["advanced_kqd"];
      return;
    case "advanced_qfd":
      values.advanced_qfd = patch.value as SimulationRunFormData["advanced_qfd"];
      return;
    case "advanced_qse":
      values.advanced_qse = patch.value as SimulationRunFormData["advanced_qse"];
      return;
    case "advanced_skqd":
      values.advanced_skqd = patch.value as SimulationRunFormData["advanced_skqd"];
      return;
  }
}

function buildAdvancedDefaultLabel(algorithm: RunAlgorithm, config: AdvancedConfig): string {
  switch (algorithm) {
    case "vqe": {
      const vqeConfig = config as VQEAdvancedConfig;
      return `${vqeConfig.ansatz_name} / ${vqeConfig.optimizer_name}`;
    }
    case "sqd": {
      const sqdConfig = config as SQDAdvancedConfig;
      return `${sqdConfig.samples_per_batch} x ${sqdConfig.num_batches}`;
    }
    case "kqd": {
      const kqdConfig = config as KQDAdvancedConfig;
      return `Krylov ${kqdConfig.krylov_dim}`;
    }
    case "qfd": {
      const qfdConfig = config as QFDAdvancedConfig;
      return `${qfdConfig.num_time_points} points`;
    }
    case "qse": {
      const qseConfig = config as QSEAdvancedConfig;
      return qseConfig.reference_method === "vqe"
        ? `VQE ref / ${qseConfig.excitation_level}`
        : `${qseConfig.reference_method} / ${qseConfig.excitation_level}`;
    }
    case "skqd": {
      const skqdConfig = config as SKQDAdvancedConfig;
      return `Ext ${skqdConfig.krylov_extension_dim}`;
    }
  }
}

function buildSimpleDefaultLabel(goal: EasyGoal | null): string {
  if (goal === "fastest") {
    return "Quick scan";
  }
  if (goal === "best_accuracy") {
    return "High accuracy";
  }
  return "Balanced";
}

function buildGeneratedBenchmarkVariantLabel(variant: BenchmarkAlgorithmVariant): string {
  if (variant.mode === "simple") {
    return buildSimpleDefaultLabel(variant.easyGoal);
  }
  if (variant.advancedConfig) {
    return buildAdvancedDefaultLabel(variant.algorithm, variant.advancedConfig);
  }
  return `${variant.algorithm.toUpperCase()} advanced row`;
}

function resolveSharedMaxDimFields(
  maxDim: SQDAdvancedConfig["max_dim"] | SKQDAdvancedConfig["base_sampling_options"]["max_dim"],
) {
  if (Array.isArray(maxDim)) {
    return {
      maxDimMode: "spin_resolved" as const,
      maxDim: null,
      maxDimA: maxDim[0],
      maxDimB: maxDim[1],
    };
  }
  if (typeof maxDim === "number") {
    return {
      maxDimMode: "shared" as const,
      maxDim,
      maxDimA: null,
      maxDimB: null,
    };
  }
  return {
    maxDimMode: "shared" as const,
    maxDim: null,
    maxDimA: null,
    maxDimB: null,
  };
}

function applyVqeAdvancedConfig(
  values: SimulationRunFormData,
  config: VQEAdvancedConfig,
): SimulationRunFormData {
  values.advanced_vqe = {
    ...values.advanced_vqe,
    ansatz_name: config.ansatz_name,
    optimizer_name: config.optimizer_name,
    max_iterations: config.max_iterations,
    max_function_evaluations: config.max_function_evaluations ?? null,
    reps: config.reps ?? 2,
    initial_point_strategy: config.initial_point_strategy ?? "zero_plus_seeded_random",
    initial_point_candidates: config.initial_point_candidates ?? null,
    optimizer_options_text: config.optimizer_options
      ? JSON.stringify(config.optimizer_options)
      : "",
    initial_parameters_text: config.initial_parameters
      ? JSON.stringify(config.initial_parameters)
      : "",
    parameter_bounds_text: config.parameter_bounds ? JSON.stringify(config.parameter_bounds) : "",
    seed: config.seed ?? null,
    convergence_threshold: config.convergence_threshold ?? null,
  };
  return values;
}

function applySqdAdvancedConfig(
  values: SimulationRunFormData,
  config: SQDAdvancedConfig,
): SimulationRunFormData {
  const maxDimFields = resolveSharedMaxDimFields(config.max_dim);

  values.advanced_sqd = {
    ...values.advanced_sqd,
    samples_per_batch: config.samples_per_batch,
    num_batches: config.num_batches,
    max_iterations: config.max_iterations,
    num_elec_a: config.num_elec_a ?? null,
    num_elec_b: config.num_elec_b ?? null,
    energy_tol: config.energy_tol ?? null,
    occupancies_tol: config.occupancies_tol ?? null,
    min_selected_configurations: config.min_selected_configurations ?? null,
    seed: config.seed ?? null,
    symmetrize_spin: config.symmetrize_spin ?? false,
    carryover_threshold: config.carryover_threshold ?? null,
    max_dim_mode: maxDimFields.maxDimMode,
    max_dim: maxDimFields.maxDim,
    max_dim_a: maxDimFields.maxDimA,
    max_dim_b: maxDimFields.maxDimB,
    spin_sq_target: config.spin_sq_target ?? null,
    sci_solver_options_text: config.sci_solver_options
      ? JSON.stringify(config.sci_solver_options)
      : "",
  };
  return values;
}

function applyKqdAdvancedConfig(
  values: SimulationRunFormData,
  config: KQDAdvancedConfig,
): SimulationRunFormData {
  values.advanced_kqd = {
    ...values.advanced_kqd,
    krylov_dim: config.krylov_dim,
    time_step: config.time_step,
    evolution_method: config.evolution_method ?? "exact",
    trotter_steps: config.trotter_steps ?? 1,
    residual_tolerance: config.residual_tolerance ?? null,
  };
  return values;
}

function applyQfdAdvancedConfig(
  values: SimulationRunFormData,
  config: QFDAdvancedConfig,
): SimulationRunFormData {
  values.advanced_qfd = {
    ...values.advanced_qfd,
    num_time_points: config.num_time_points,
    max_time: config.max_time,
    time_grid_type: config.time_grid_type ?? "linear",
    trotter_steps: config.trotter_steps ?? 1,
    residual_tolerance: config.residual_tolerance ?? null,
  };
  return values;
}

function mapQseProvidedSectorRows(config: QSEAdvancedConfig, values: SimulationRunFormData) {
  if (!config.provided_sector_amplitudes) {
    return values.advanced_qse.provided_sector_rows;
  }
  return config.provided_sector_amplitudes.map((row) => ({
    bitstring: row.bitstring,
    real: typeof row.amplitude === "number" ? String(row.amplitude) : String(row.amplitude.real),
    imag: typeof row.amplitude === "number" ? "0" : String(row.amplitude.imag),
  }));
}

function applyQseAdvancedConfig(
  values: SimulationRunFormData,
  config: QSEAdvancedConfig,
): SimulationRunFormData {
  values.advanced_qse = {
    ...values.advanced_qse,
    reference_method: config.reference_method,
    provided_state_vector_text: config.provided_state_vector
      ? JSON.stringify(config.provided_state_vector)
      : values.advanced_qse.provided_state_vector_text,
    provided_sector_rows: mapQseProvidedSectorRows(config, values),
    excitation_level: config.excitation_level,
    max_subspace_dim: config.max_subspace_dim ?? null,
    vqe_reference_ansatz_name: config.vqe_reference_ansatz_name ?? "EfficientSU2",
    vqe_reference_optimizer_name: config.vqe_reference_optimizer_name ?? "COBYLA",
    vqe_reference_max_iterations: config.vqe_reference_max_iterations ?? null,
    vqe_reference_reps: config.vqe_reference_reps ?? null,
    regularization: config.regularization ?? null,
    overlap_threshold: config.overlap_threshold ?? null,
    residual_tolerance: config.residual_tolerance ?? null,
  };
  return values;
}

function applySkqdAdvancedConfig(
  values: SimulationRunFormData,
  config: SKQDAdvancedConfig,
): SimulationRunFormData {
  const maxDimFields = resolveSharedMaxDimFields(config.base_sampling_options.max_dim);

  values.advanced_skqd = {
    ...values.advanced_skqd,
    samples_per_state: config.samples_per_state,
    num_elec_a: config.base_sampling_options.num_elec_a ?? null,
    num_elec_b: config.base_sampling_options.num_elec_b ?? null,
    min_selected_configurations: config.base_sampling_options.min_selected_configurations ?? null,
    seed: config.base_sampling_options.seed ?? null,
    symmetrize_spin: config.base_sampling_options.symmetrize_spin ?? false,
    max_dim_mode: maxDimFields.maxDimMode,
    max_dim: maxDimFields.maxDim,
    max_dim_a: maxDimFields.maxDimA,
    max_dim_b: maxDimFields.maxDimB,
    spin_sq_target: config.base_sampling_options.spin_sq_target ?? null,
    sci_solver_options_text: config.base_sampling_options.sci_solver_options
      ? JSON.stringify(config.base_sampling_options.sci_solver_options)
      : "",
    krylov_extension_dim: config.krylov_extension_dim,
    time_step: config.time_step ?? null,
    residual_tolerance: config.residual_tolerance ?? null,
  };
  return values;
}

function applyAdvancedConfigToFormValues(
  values: SimulationRunFormData,
  config: AdvancedConfig,
): SimulationRunFormData {
  switch (config.algorithm) {
    case "vqe":
      return applyVqeAdvancedConfig(values, config);
    case "sqd":
      return applySqdAdvancedConfig(values, config);
    case "kqd":
      return applyKqdAdvancedConfig(values, config);
    case "qfd":
      return applyQfdAdvancedConfig(values, config);
    case "qse":
      return applyQseAdvancedConfig(values, config);
    case "skqd":
      return applySkqdAdvancedConfig(values, config);
  }
}

export function createSimpleBenchmarkVariant(
  algorithm: RunAlgorithm,
  goal: EasyGoal = "balanced",
): BenchmarkAlgorithmVariant {
  return {
    id: createVariantId(),
    algorithm,
    mode: "simple",
    label: buildSimpleDefaultLabel(goal),
    easyGoal: goal,
    advancedConfig: null,
  };
}

export function createAdvancedBenchmarkVariant(
  algorithm: RunAlgorithm,
  chemicalAccuracyHa: number,
  configMetadata?: RunConfigMetadataResponse | null,
): BenchmarkAlgorithmVariant {
  const values = cloneInitialValues();
  values.algorithm = algorithm;
  values.mode = "advanced";
  applyRecommendedPatch(values, algorithm, chemicalAccuracyHa, configMetadata);
  const advancedConfig = buildAdvancedConfigFromFormValues(values);
  return {
    id: createVariantId(),
    algorithm,
    mode: "advanced",
    label: buildAdvancedDefaultLabel(algorithm, advancedConfig),
    easyGoal: null,
    advancedConfig,
  };
}

export function duplicateBenchmarkVariant(
  variant: BenchmarkAlgorithmVariant,
): BenchmarkAlgorithmVariant {
  return {
    ...variant,
    id: createVariantId(),
    label: variant.label,
    advancedConfig: variant.advancedConfig ? structuredClone(variant.advancedConfig) : null,
  };
}

export function buildBenchmarkVariantFormValues(
  variant: BenchmarkAlgorithmVariant,
): SimulationRunFormData {
  const values = cloneInitialValues();
  values.algorithm = variant.algorithm;
  values.mode = variant.mode === "simple" ? "easy" : "advanced";
  values.easy_options.goal = variant.easyGoal ?? "balanced";
  if (variant.advancedConfig) {
    return applyAdvancedConfigToFormValues(values, variant.advancedConfig);
  }
  return values;
}

export function buildBenchmarkVariantFromFormValues(
  variant: BenchmarkAlgorithmVariant,
  values: SimulationRunFormData,
): BenchmarkAlgorithmVariant {
  if (values.mode === "easy") {
    return {
      ...variant,
      mode: "simple",
      easyGoal: values.easy_options.goal,
      advancedConfig: null,
    };
  }

  const advancedConfig = buildAdvancedConfigFromFormValues(values);
  return {
    ...variant,
    mode: "advanced",
    easyGoal: null,
    advancedConfig,
  };
}

export function benchmarkVariantSummary(variant: BenchmarkAlgorithmVariant): string {
  if (variant.mode === "simple") {
    return `${variant.algorithm.toUpperCase()} easy preset`;
  }
  if (variant.advancedConfig) {
    return buildAdvancedDefaultLabel(variant.algorithm, variant.advancedConfig);
  }
  return `${variant.algorithm.toUpperCase()} advanced row`;
}

export function isGeneratedBenchmarkVariantLabel(variant: BenchmarkAlgorithmVariant): boolean {
  const normalizedLabel = normalizeVariantLabelValue(variant.label);
  if (normalizedLabel.length === 0 || /^\d+$/.test(normalizedLabel)) {
    return true;
  }

  const generatedBaseLabels = new Set<string>([
    variant.algorithm.toUpperCase(),
    benchmarkVariantSummary(variant),
    buildGeneratedBenchmarkVariantLabel(variant),
  ]);

  for (const baseLabel of generatedBaseLabels) {
    if (!baseLabel) continue;
    if (matchesLegacyCopyLabel(variant.label, baseLabel)) {
      return true;
    }
  }

  return false;
}

export function normalizeBenchmarkVariantLabels(
  variants: readonly BenchmarkAlgorithmVariant[],
): BenchmarkAlgorithmVariant[] {
  const usedLabelsByAlgorithm = new Map<RunAlgorithm, Set<string>>();

  return variants.map((variant) => {
    const usedLabels = usedLabelsByAlgorithm.get(variant.algorithm) ?? new Set<string>();
    usedLabelsByAlgorithm.set(variant.algorithm, usedLabels);

    if (!isGeneratedBenchmarkVariantLabel(variant)) {
      usedLabels.add(normalizeVariantLabelValue(variant.label));
      return variant;
    }

    const baseLabel = buildGeneratedBenchmarkVariantLabel(variant);
    let nextLabel = baseLabel;
    let suffix = 2;
    while (usedLabels.has(normalizeVariantLabelValue(nextLabel))) {
      nextLabel = `${baseLabel} ${suffix}`;
      suffix += 1;
    }
    usedLabels.add(normalizeVariantLabelValue(nextLabel));

    return {
      ...variant,
      label: nextLabel,
    };
  });
}
