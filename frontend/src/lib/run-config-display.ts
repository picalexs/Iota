import { createElement } from "react";
import type { ReactNode } from "react";
import type { RunResponse } from "@/types/run";

export type ConfigRowGroup = "Molecule" | "Algorithm" | "Backend" | "Options";

export interface ConfigRow {
  group: ConfigRowGroup;
  label: string;
  value: ReactNode;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function formatLabel(key: string): string {
  return key.replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatEnumValue(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatConfigValueText(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value) ?? "";
}

function formatEnumNode(value: unknown): ReactNode {
  return createElement(
    "span",
    { className: "font-medium" },
    formatEnumValue(formatConfigValueText(value)),
  );
}

function formatFallbackValue(value: unknown): ReactNode {
  if (value == null) return "—";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return createElement("code", { className: "font-mono text-xs" }, formatConfigValueText(value));
  }

  return createElement("code", { className: "font-mono text-xs" }, JSON.stringify(value));
}

function formatKnownValue(value: unknown): ReactNode {
  if (value == null) return "—";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return createElement("span", { className: "font-medium" }, formatConfigValueText(value));
  }

  return createElement("code", { className: "font-mono text-xs" }, JSON.stringify(value));
}

function formatHartreeValue(value: unknown): ReactNode {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return formatKnownValue(value);
  }

  return createElement("span", { className: "font-medium" }, `${value.toFixed(6)} Ha`);
}

function pushRow(
  rows: ConfigRow[],
  group: ConfigRowGroup,
  label: string,
  value: unknown,
  formatter?: (value: unknown) => ReactNode,
) {
  if (value == null) return;
  rows.push({
    group,
    label,
    value: formatter ? formatter(value) : formatKnownValue(value),
  });
}

type AdvancedRowSpec = [key: string, label: string, formatter?: (value: unknown) => ReactNode];

const CONSUMED_TOP_LEVEL_KEYS = new Set<string>([
  "algorithm",
  "mode",
  "backend_target",
  "chemical_accuracy_target_ha",
  "basis_set",
  "basis_set_override",
  "easy_options",
  "advanced_config",
  "backend_options",
  "noise_profile",
  "client_request_id",
  "versions",
]);

const VQE_ADVANCED_ROWS: AdvancedRowSpec[] = [
  ["ansatz_name", "Ansatz"],
  ["optimizer_name", "Optimizer"],
  ["max_iterations", "Max iterations"],
  ["max_function_evaluations", "Max function evaluations"],
  ["optimizer_options", "Optimizer options"],
  ["initial_parameters", "Initial parameters"],
  ["initial_point_strategy", "Start strategy", formatEnumNode],
  ["initial_point_candidates", "Starting candidates"],
  ["seed", "Seed"],
  ["convergence_threshold", "Convergence threshold"],
  ["parameter_bounds", "Parameter bounds"],
];

const SQD_ADVANCED_ROWS: AdvancedRowSpec[] = [
  ["samples_per_batch", "Samples per batch"],
  ["num_batches", "Num batches"],
  ["max_iterations", "Max iterations"],
  ["num_elec_a", "Num elec a"],
  ["num_elec_b", "Num elec b"],
  ["energy_tol", "Energy tol"],
  ["occupancies_tol", "Occupancies tol"],
  ["min_selected_configurations", "Min selected configurations"],
  ["symmetrize_spin", "Symmetrize spin"],
  ["carryover_threshold", "Carryover threshold"],
  ["max_dim", "Max dim"],
  ["spin_sq_target", "Spin sq target"],
  ["sci_solver_options", "Sci solver options"],
];

const KQD_ADVANCED_ROWS: AdvancedRowSpec[] = [
  ["krylov_dim", "Krylov dim"],
  ["time_step", "Time step"],
  ["evolution_method", "Evolution method", formatEnumNode],
  ["trotter_steps", "Trotter steps"],
  ["residual_tolerance", "Residual tolerance"],
];

const QFD_ADVANCED_ROWS: AdvancedRowSpec[] = [
  ["num_time_points", "Num time points"],
  ["max_time", "Max time"],
  ["time_grid_type", "Time grid type", formatEnumNode],
  ["trotter_steps", "Trotter steps"],
  ["residual_tolerance", "Residual tolerance"],
];

const QSE_ADVANCED_ROWS: AdvancedRowSpec[] = [
  ["reference_method", "Reference method", formatEnumNode],
  ["excitation_level", "Excitation level", formatEnumNode],
  ["provided_state_vector", "Provided state vector"],
  ["provided_sector_amplitudes", "Provided sector amplitudes"],
  ["max_subspace_dim", "Max subspace dim"],
  ["vqe_reference_ansatz_name", "Reference VQE ansatz"],
  ["vqe_reference_optimizer_name", "Reference VQE optimizer"],
  ["vqe_reference_max_iterations", "Reference VQE iterations"],
  ["vqe_reference_reps", "Reference VQE depth"],
  ["regularization", "Regularization"],
  ["overlap_threshold", "Overlap threshold"],
  ["residual_tolerance", "Residual tolerance"],
];

const SKQD_ADVANCED_ROWS: AdvancedRowSpec[] = [
  ["samples_per_state", "Samples per Krylov state"],
  ["krylov_extension_dim", "Krylov extension dim"],
  ["residual_tolerance", "Residual tolerance"],
];

function pushAdvancedSpecRows(
  rows: ConfigRow[],
  advanced: Record<string, unknown>,
  handledKeys: Set<string>,
  specs: AdvancedRowSpec[],
) {
  for (const [key, label, formatter] of specs) {
    handledKeys.add(key);
    pushRow(rows, "Options", label, advanced[key], formatter);
  }
}

function appendSkqdSamplingRows(
  rows: ConfigRow[],
  advanced: Record<string, unknown>,
  handledKeys: Set<string>,
) {
  if (!isRecord(advanced.base_sampling_options)) return;

  const base = advanced.base_sampling_options;
  for (const [key, value] of Object.entries(base)) {
    rows.push({
      group: "Options",
      label: `SKQD sampling: ${formatLabel(key)}`,
      value: formatFallbackValue(value),
    });
  }
  handledKeys.add("base_sampling_options");
}

function appendAdvancedRows(
  rows: ConfigRow[],
  advanced: Record<string, unknown>,
  algorithm: string,
  handledKeys: Set<string>,
) {
  const rowsByAlgorithm: Partial<Record<string, AdvancedRowSpec[]>> = {
    vqe: VQE_ADVANCED_ROWS,
    sqd: SQD_ADVANCED_ROWS,
    kqd: KQD_ADVANCED_ROWS,
    qfd: QFD_ADVANCED_ROWS,
    qse: QSE_ADVANCED_ROWS,
    skqd: SKQD_ADVANCED_ROWS,
  };

  if (algorithm === "skqd") {
    appendSkqdSamplingRows(rows, advanced, handledKeys);
  }
  pushAdvancedSpecRows(rows, advanced, handledKeys, rowsByAlgorithm[algorithm] ?? []);
}

function appendAlgorithmRows(rows: ConfigRow[], config: Record<string, unknown>, run: RunResponse) {
  pushRow(rows, "Algorithm", "Algorithm", config.algorithm ?? run.algorithm, (value) =>
    createElement("span", { className: "font-medium" }, formatConfigValueText(value).toUpperCase()),
  );
  pushRow(rows, "Algorithm", "Mode", config.mode ?? run.mode, formatEnumNode);
}

function appendMoleculeRows(rows: ConfigRow[], config: Record<string, unknown>) {
  pushRow(rows, "Molecule", "Basis set", config.basis_set);
  pushRow(rows, "Molecule", "Basis set override", config.basis_set_override);
}

function appendBackendRows(rows: ConfigRow[], config: Record<string, unknown>, run: RunResponse) {
  pushRow(
    rows,
    "Backend",
    "Backend target",
    config.backend_target ?? run.backend_target,
    formatEnumNode,
  );
  if (!isRecord(config.backend_options)) return;

  pushRow(
    rows,
    "Backend",
    "Selection policy",
    config.backend_options.selection_policy,
    formatEnumNode,
  );
  pushRow(rows, "Backend", "Backend name", config.backend_options.backend_name);
  pushRow(rows, "Backend", "Shots", config.backend_options.shots);
  pushRow(rows, "Backend", "Optimization level", config.backend_options.optimization_level);
  pushRow(rows, "Backend", "Aer method", config.backend_options.aer_method, formatEnumNode);
}

function appendNoiseProfileRows(rows: ConfigRow[], config: Record<string, unknown>) {
  if (!isRecord(config.noise_profile)) return;
  pushRow(rows, "Backend", "Noise source", config.noise_profile.source, formatEnumNode);
}

function appendEasyOptionRows(rows: ConfigRow[], easyOptions: Record<string, unknown>) {
  pushRow(rows, "Options", "Goal", easyOptions.goal, formatEnumNode);

  for (const [key, value] of Object.entries(easyOptions)) {
    if (key === "goal") continue;
    rows.push({
      group: "Options",
      label: `Easy options: ${formatLabel(key)}`,
      value: formatFallbackValue(value),
    });
  }
}

function appendAdvancedConfigRows(
  rows: ConfigRow[],
  advanced: Record<string, unknown>,
  run: RunResponse,
) {
  const algorithm = formatConfigValueText(advanced.algorithm ?? run.algorithm ?? "").toLowerCase();
  const handledAdvancedKeys = new Set<string>(["algorithm"]);
  appendAdvancedRows(rows, advanced, algorithm, handledAdvancedKeys);

  for (const [key, value] of Object.entries(advanced)) {
    if (handledAdvancedKeys.has(key)) continue;
    rows.push({
      group: "Options",
      label: `Advanced config: ${formatLabel(key)}`,
      value: formatFallbackValue(value),
    });
  }
}

function appendRemainingTopLevelRows(rows: ConfigRow[], config: Record<string, unknown>) {
  for (const [key, value] of Object.entries(config)) {
    if (CONSUMED_TOP_LEVEL_KEYS.has(key)) continue;
    rows.push({
      group: "Options",
      label: formatLabel(key),
      value: formatFallbackValue(value),
    });
  }
}

export function formatConfigRows(run: RunResponse): ConfigRow[] {
  const rows: ConfigRow[] = [];
  const config = isRecord(run.config_json) ? run.config_json : {};
  appendAlgorithmRows(rows, config, run);
  appendMoleculeRows(rows, config);
  appendBackendRows(rows, config, run);
  appendNoiseProfileRows(rows, config);

  pushRow(
    rows,
    "Options",
    "Chemical accuracy target",
    config.chemical_accuracy_target_ha,
    formatHartreeValue,
  );

  if (isRecord(config.easy_options)) {
    appendEasyOptionRows(rows, config.easy_options);
  }

  if (isRecord(config.advanced_config)) {
    appendAdvancedConfigRows(rows, config.advanced_config, run);
  }

  appendRemainingTopLevelRows(rows, config);

  return rows;
}
