import type {
  ChartTooltipRow,
  ChartTooltipSection,
} from "@/components/results/charts/chart-tooltip";
import { buildRecommendedAdvancedPatch } from "@/lib/run-form-recommendations";
import type {
  ActiveSpaceSchema,
  EasyGoal,
  KQDAdvancedConfig,
  QFDAdvancedConfig,
  QSEAdvancedConfig,
  SKQDAdvancedConfig,
  SimulationRunFormData,
  SQDAdvancedConfig,
  VQEAdvancedConfig,
} from "@/types/run";
import type { MoleculePreset } from "@/lib/benchmark-presets";
import type { BenchmarkEntry } from "./benchmark-utils";
import {
  formatEasyGoalLabel,
  formatParameterNumber,
  formatRuntimeMinutes,
} from "./benchmark-insights-formatters";

function joinTooltipSegments(
  ...segments: ReadonlyArray<string | null | undefined | false>
): string | null {
  const filtered = segments.filter(
    (segment): segment is string => typeof segment === "string" && segment.trim().length > 0,
  );
  return filtered.length > 0 ? filtered.join(" · ") : null;
}

function buildTooltipRows(
  rows: ReadonlyArray<ChartTooltipRow | null | undefined>,
): ChartTooltipRow[] {
  return rows.filter((row): row is ChartTooltipRow => row != null);
}

function normalizeQseExcitationLevel(value: QSEAdvancedConfig["excitation_level"]): string {
  return value === "singles_doubles" ? "s+d" : "singles";
}

function normalizeQseReferenceMethod(value: QSEAdvancedConfig["reference_method"]): string {
  switch (value) {
    case "hf":
      return "HF";
    case "vqe":
      return "VQE";
    case "provided_state":
      return "State vector";
    case "provided_sector":
      return "Sector amplitudes";
  }
}

function buildVqeTooltipDetailLines(
  config: Pick<
    VQEAdvancedConfig,
    "ansatz_name" | "optimizer_name" | "reps" | "max_iterations" | "max_function_evaluations"
  >,
): ChartTooltipRow[] {
  const budgetLabel = joinTooltipSegments(
    config.max_iterations != null ? `${config.max_iterations} iters` : null,
    config.max_function_evaluations != null ? `${config.max_function_evaluations} evals` : null,
  );

  return buildTooltipRows([
    { label: "Ansatz", value: config.ansatz_name },
    config.optimizer_name ? { label: "Optimizer", value: config.optimizer_name } : null,
    config.reps != null ? { label: "Depth", value: `reps ${config.reps}` } : null,
    budgetLabel
      ? {
          label: "Budget",
          value: budgetLabel,
        }
      : null,
  ]);
}

function buildSqdTooltipDetailLines(
  config: Pick<
    SQDAdvancedConfig,
    | "samples_per_batch"
    | "num_batches"
    | "max_iterations"
    | "energy_tol"
    | "symmetrize_spin"
    | "spin_sq_target"
  >,
): ChartTooltipRow[] {
  return buildTooltipRows([
    { label: "Sampling", value: `${config.samples_per_batch} x ${config.num_batches}` },
    { label: "Iterations", value: `${config.max_iterations}` },
    config.energy_tol != null
      ? { label: "Tolerance", value: formatParameterNumber(config.energy_tol) ?? "n/a" }
      : null,
    config.symmetrize_spin ? { label: "Spin", value: "Symmetrized" } : null,
    config.spin_sq_target != null
      ? { label: "S^2 target", value: formatParameterNumber(config.spin_sq_target) ?? "n/a" }
      : null,
  ]);
}

function buildKqdTooltipDetailLines(
  config: Pick<
    KQDAdvancedConfig,
    "krylov_dim" | "time_step" | "evolution_method" | "trotter_steps" | "residual_tolerance"
  >,
): ChartTooltipRow[] {
  return buildTooltipRows([
    { label: "Krylov dim", value: `${config.krylov_dim}` },
    config.time_step != null
      ? { label: "Time step", value: formatParameterNumber(config.time_step) ?? "n/a" }
      : null,
    {
      label: "Evolution",
      value:
        config.evolution_method === "trotter"
          ? `Trotter (${config.trotter_steps ?? 1} steps)`
          : "Exact",
    },
    config.residual_tolerance != null
      ? {
          label: "Residual",
          value: formatParameterNumber(config.residual_tolerance) ?? "n/a",
        }
      : null,
  ]);
}

function buildQfdTooltipDetailLines(
  config: Pick<
    QFDAdvancedConfig,
    "num_time_points" | "max_time" | "time_grid_type" | "trotter_steps" | "residual_tolerance"
  >,
): ChartTooltipRow[] {
  return buildTooltipRows([
    { label: "Time points", value: `${config.num_time_points}` },
    config.max_time != null
      ? { label: "Max time", value: formatParameterNumber(config.max_time) ?? "n/a" }
      : null,
    {
      label: "Grid",
      value: config.time_grid_type === "geometric" ? "Geometric" : "Linear",
    },
    config.trotter_steps && config.trotter_steps > 1
      ? { label: "Trotter", value: `${config.trotter_steps} steps` }
      : null,
    config.residual_tolerance != null
      ? {
          label: "Residual",
          value: formatParameterNumber(config.residual_tolerance) ?? "n/a",
        }
      : null,
  ]);
}

function buildQseTooltipDetailLines(
  config: Pick<
    QSEAdvancedConfig,
    | "reference_method"
    | "excitation_level"
    | "max_subspace_dim"
    | "vqe_reference_ansatz_name"
    | "vqe_reference_optimizer_name"
    | "vqe_reference_max_iterations"
    | "vqe_reference_reps"
  >,
): ChartTooltipRow[] {
  return buildTooltipRows([
    {
      label: "Reference",
      value:
        config.reference_method === "vqe"
          ? (joinTooltipSegments(
              "VQE",
              config.vqe_reference_ansatz_name,
              config.vqe_reference_optimizer_name,
            ) ?? "VQE")
          : normalizeQseReferenceMethod(config.reference_method),
    },
    { label: "Excitations", value: normalizeQseExcitationLevel(config.excitation_level) },
    config.max_subspace_dim != null
      ? { label: "Subspace", value: `${config.max_subspace_dim}` }
      : null,
    config.reference_method === "vqe" && config.vqe_reference_reps != null
      ? { label: "Ref depth", value: `reps ${config.vqe_reference_reps}` }
      : null,
    config.reference_method === "vqe" && config.vqe_reference_max_iterations != null
      ? { label: "Ref budget", value: `${config.vqe_reference_max_iterations} iters` }
      : null,
  ]);
}

function buildSkqdTooltipDetailLines(
  config: Pick<
    SKQDAdvancedConfig,
    | "samples_per_state"
    | "base_sampling_options"
    | "krylov_extension_dim"
    | "time_step"
    | "residual_tolerance"
  >,
): ChartTooltipRow[] {
  return buildTooltipRows([
    {
      label: "Samples/state",
      value: `${config.samples_per_state}`,
    },
    {
      label: "Selected-CI cap",
      value: `${config.base_sampling_options.max_dim ?? "default"}`,
    },
    { label: "Krylov states", value: `${config.krylov_extension_dim}` },
    config.time_step != null
      ? { label: "Time step", value: formatParameterNumber(config.time_step) ?? "n/a" }
      : null,
    config.residual_tolerance != null
      ? {
          label: "Residual",
          value: formatParameterNumber(config.residual_tolerance) ?? "n/a",
        }
      : null,
  ]);
}

function buildAdvancedTooltipDetailLines(
  config: BenchmarkEntry["advancedConfig"],
): ChartTooltipRow[] {
  if (!config) return [];

  switch (config.algorithm) {
    case "vqe":
      return buildVqeTooltipDetailLines(config);
    case "sqd":
      return buildSqdTooltipDetailLines(config);
    case "kqd":
      return buildKqdTooltipDetailLines(config);
    case "qfd":
      return buildQfdTooltipDetailLines(config);
    case "qse":
      return buildQseTooltipDetailLines(config);
    case "skqd":
      return buildSkqdTooltipDetailLines(config);
  }
}

type SimpleTooltipActiveSpace = ActiveSpaceSchema | null | undefined;
type SimpleTooltipDetailBuilder = (
  goal: EasyGoal,
  activeSpace: SimpleTooltipActiveSpace,
) => ChartTooltipRow[];

function buildSimpleVqeTooltipDetailLines(
  goal: EasyGoal,
  activeSpace: SimpleTooltipActiveSpace,
): ChartTooltipRow[] {
  const recommendedPatch = buildRecommendedAdvancedPatch("vqe", goal, activeSpace);
  const value = recommendedPatch.value as SimulationRunFormData["advanced_vqe"];

  return buildVqeTooltipDetailLines({
    ansatz_name: value.ansatz_name,
    optimizer_name: value.optimizer_name,
    reps: value.reps,
    max_iterations: value.max_iterations ?? 0,
    max_function_evaluations: value.max_function_evaluations,
  });
}

function buildSimpleSqdTooltipDetailLines(
  goal: EasyGoal,
  activeSpace: SimpleTooltipActiveSpace,
): ChartTooltipRow[] {
  const recommendedPatch = buildRecommendedAdvancedPatch("sqd", goal, activeSpace);
  const value = recommendedPatch.value as SimulationRunFormData["advanced_sqd"];

  return buildSqdTooltipDetailLines({
    samples_per_batch: value.samples_per_batch ?? 0,
    num_batches: value.num_batches ?? 0,
    max_iterations: value.max_iterations ?? 0,
    energy_tol: value.energy_tol,
    symmetrize_spin: value.symmetrize_spin,
    spin_sq_target: value.spin_sq_target,
  });
}

function buildSimpleKqdTooltipDetailLines(
  goal: EasyGoal,
  activeSpace: SimpleTooltipActiveSpace,
): ChartTooltipRow[] {
  const recommendedPatch = buildRecommendedAdvancedPatch("kqd", goal, activeSpace);
  const value = recommendedPatch.value as SimulationRunFormData["advanced_kqd"];

  return buildKqdTooltipDetailLines({
    krylov_dim: value.krylov_dim ?? 0,
    time_step: value.time_step ?? 0,
    evolution_method: value.evolution_method,
    trotter_steps: value.trotter_steps ?? undefined,
    residual_tolerance: value.residual_tolerance,
  });
}

function buildSimpleQfdTooltipDetailLines(
  goal: EasyGoal,
  activeSpace: SimpleTooltipActiveSpace,
): ChartTooltipRow[] {
  const recommendedPatch = buildRecommendedAdvancedPatch("qfd", goal, activeSpace);
  const value = recommendedPatch.value as SimulationRunFormData["advanced_qfd"];

  return buildQfdTooltipDetailLines({
    num_time_points: value.num_time_points ?? 0,
    max_time: value.max_time ?? 0,
    time_grid_type: value.time_grid_type,
    trotter_steps: value.trotter_steps ?? undefined,
    residual_tolerance: value.residual_tolerance,
  });
}

function buildSimpleQseTooltipDetailLines(
  goal: EasyGoal,
  activeSpace: SimpleTooltipActiveSpace,
): ChartTooltipRow[] {
  const recommendedPatch = buildRecommendedAdvancedPatch("qse", goal, activeSpace);
  const value = recommendedPatch.value as SimulationRunFormData["advanced_qse"];

  return buildQseTooltipDetailLines({
    reference_method: value.reference_method,
    excitation_level: value.excitation_level,
    max_subspace_dim: value.max_subspace_dim,
    vqe_reference_ansatz_name: value.vqe_reference_ansatz_name,
    vqe_reference_optimizer_name: value.vqe_reference_optimizer_name,
    vqe_reference_max_iterations: value.vqe_reference_max_iterations,
    vqe_reference_reps: value.vqe_reference_reps,
  });
}

function buildSimpleSkqdTooltipDetailLines(
  goal: EasyGoal,
  activeSpace: SimpleTooltipActiveSpace,
): ChartTooltipRow[] {
  const recommendedPatch = buildRecommendedAdvancedPatch("skqd", goal, activeSpace);
  const value = recommendedPatch.value as SimulationRunFormData["advanced_skqd"];

  return buildSkqdTooltipDetailLines({
    samples_per_state: value.samples_per_state ?? 0,
    base_sampling_options: {
      max_dim:
        value.max_dim_mode === "shared"
          ? value.max_dim
          : [value.max_dim_a ?? 0, value.max_dim_b ?? 0],
    },
    krylov_extension_dim: value.krylov_extension_dim ?? 0,
    time_step: value.time_step,
    residual_tolerance: value.residual_tolerance,
  });
}

const simpleTooltipDetailBuilders: Record<BenchmarkEntry["algorithm"], SimpleTooltipDetailBuilder> =
  {
    vqe: buildSimpleVqeTooltipDetailLines,
    sqd: buildSimpleSqdTooltipDetailLines,
    kqd: buildSimpleKqdTooltipDetailLines,
    qfd: buildSimpleQfdTooltipDetailLines,
    qse: buildSimpleQseTooltipDetailLines,
    skqd: buildSimpleSkqdTooltipDetailLines,
  };

function buildSimpleTooltipDetailLines(
  algorithm: BenchmarkEntry["algorithm"],
  goal: EasyGoal | null | undefined,
  activeSpace: SimpleTooltipActiveSpace,
): ChartTooltipRow[] {
  const resolvedGoal = goal ?? "balanced";
  const presetRow: ChartTooltipRow = { label: "Preset", value: formatEasyGoalLabel(resolvedGoal) };
  const buildTooltipDetails = simpleTooltipDetailBuilders[algorithm];

  return [presetRow, ...buildTooltipDetails(resolvedGoal, activeSpace)];
}

export function buildBenchmarkTooltipLines(
  preset: MoleculePreset,
  entry: BenchmarkEntry,
  absErrorMha: number,
): ChartTooltipSection[] {
  const detailRows =
    entry.mode === "advanced" && entry.advancedConfig
      ? buildAdvancedTooltipDetailLines(entry.advancedConfig)
      : buildSimpleTooltipDetailLines(
          entry.algorithm,
          entry.easyOptions?.goal,
          preset.active_space ?? null,
        );

  return [
    {
      title: "Stats",
      rows: [
        { label: "Abs. error", value: `${absErrorMha.toFixed(2)} mHa` },
        { label: "Runtime", value: formatRuntimeMinutes(entry.elapsedSeconds ?? 0) },
      ],
    },
    ...(detailRows.length > 0 ? [{ title: "Configuration", rows: detailRows }] : []),
  ];
}
