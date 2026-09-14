import type { AlgorithmMetrics, CircuitArtifact, CircuitPreview, JsonObject } from "@/types/run";

interface ArtifactBearingMetrics {
  circuit_artifacts: CircuitArtifact[];
  circuit_artifact_policy: JsonObject | null;
}

export interface VqeMetrics extends ArtifactBearingMetrics {
  convergence_trace: number[];
  optimizer_diagnostics?: JsonObject | null;
  objective_evaluations?: number | null;
  optimizer_iterations?: number | null;
  effective_max_iterations?: number | null;
  max_function_evaluations?: number | null;
  bloch_vectors: number[][] | null;
  density_matrix_real: number[][] | null;
  density_matrix_imag: number[][] | null;
}

export interface SqdMetrics extends ArtifactBearingMetrics {
  sci_energies: number[];
  configuration_recovery_trace: JsonObject[];
  spin_diagnostics: JsonObject | null;
  postselection_summary: JsonObject | null;
  subsampling_summary: JsonObject | null;
  sci_result_package: JsonObject | null;
}

export interface KqdMetrics {
  ritz_values: number[];
  raw_ritz_values: number[];
  krylov_rank: number;
  orthogonality_metrics: JsonObject | null;
  stability_summary: JsonObject | null;
  selected_level_index: number | null;
  circuit_artifacts: CircuitArtifact[];
  circuit_artifact_policy: JsonObject | null;
}

export interface QfdMetrics {
  filter_eigenvalues: number[];
  raw_filter_eigenvalues: number[];
  conditioning_summary: JsonObject | null;
  stability_summary: JsonObject | null;
  selected_level_index: number | null;
}

export interface QseMetrics extends ArtifactBearingMetrics {
  eigenvalues: number[];
  overlap_condition: number | null;
  reference_state_energy: number | null;
  residual_norm: number | null;
  relative_residual: number | null;
  convergence_threshold: number | null;
}

export interface SkqdMetrics extends ArtifactBearingMetrics {
  sqd_core: JsonObject | null;
  krylov_extension_diagnostics: JsonObject | null;
}

function isNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isRecord(value: unknown): value is JsonObject {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function asNumbers(v: unknown): number[] {
  if (!Array.isArray(v)) return [];
  return v.filter(isNumber);
}

function asRecord(v: unknown): JsonObject | null {
  return isRecord(v) ? v : null;
}

function asBlochVectors(v: unknown): number[][] | null {
  if (!Array.isArray(v) || v.length === 0) return null;
  const result = v
    .filter((row) => Array.isArray(row) && row.length === 3)
    .map((row) => row.map((x: unknown) => (isNumber(x) ? x : 0)));
  return result.length > 0 ? result : null;
}

function asMatrix(v: unknown): number[][] | null {
  if (!Array.isArray(v) || v.length === 0) return null;
  const rows = v
    .filter((row): row is unknown[] => Array.isArray(row) && row.length > 0)
    .map((row) => row.map((x) => (isNumber(x) ? x : 0)));
  return rows.length > 0 ? rows : null;
}

function asString(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function asStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((entry) => (typeof entry === "string" && entry ? [entry] : []));
}

function asCircuitPreview(value: unknown): CircuitPreview | null {
  const record = asRecord(value);
  if (!record) return null;
  const preview: CircuitPreview = {};
  const qasm = asString(record["qasm"]);
  const diagramSvg = asString(record["diagram_svg"]);
  const qubits = record["qubits"];
  const classicalBits = record["classical_bits"];
  const style = asString(record["style"]);
  if (qasm != null) preview.qasm = qasm;
  if (diagramSvg != null) preview.diagram_svg = diagramSvg;
  if (isNumber(qubits)) preview.qubits = qubits;
  if (isNumber(classicalBits)) preview.classical_bits = classicalBits;
  if (style != null) preview.style = style;
  return Object.keys(preview).length > 0 ? preview : null;
}

function normalizeCircuitArtifact(value: unknown, index: number): CircuitArtifact | null {
  const record = asRecord(value);
  if (!record) return null;
  const logical = asCircuitPreview(record["logical"]) ?? asCircuitPreview(record["preview"]);
  const transpiled =
    asCircuitPreview(record["transpiled"]) ?? asCircuitPreview(record["transpiled_preview"]);

  const artifact: CircuitArtifact = {
    id: asString(record["id"]) ?? asString(record["artifact_id"]) ?? `artifact-${index + 1}`,
    artifact_id: asString(record["artifact_id"]) ?? asString(record["id"]) ?? undefined,
    role: asString(record["role"]) ?? undefined,
    phase: asString(record["phase"]) ?? undefined,
    iteration: isNumber(record["iteration"]) ? record["iteration"] : undefined,
    representative:
      typeof record["representative"] === "boolean" ? record["representative"] : undefined,
    label: asString(record["label"]) ?? undefined,
    source: asString(record["source"]) ?? undefined,
    logical,
    preview: logical,
    transpiled,
    transpiled_preview: transpiled,
    backend_target: asString(record["backend_target"]) ?? undefined,
    primitive_family: asString(record["primitive_family"]) ?? undefined,
    job_ids: asStringList(record["job_ids"]),
    pub_count: isNumber(record["pub_count"]) ? record["pub_count"] : undefined,
    shots: isNumber(record["shots"]) ? record["shots"] : undefined,
    transpilation_summary: asRecord(record["transpilation_summary"]),
    downsampling: asRecord(record["downsampling"]),
  };
  return artifact;
}

function latestIteration(entries: JsonObject[]): number | null {
  for (let index = entries.length - 1; index >= 0; index -= 1) {
    const entry = entries[index];
    if (!entry) {
      continue;
    }
    const iteration = entry["iteration"];
    if (isNumber(iteration)) return iteration;
  }
  return null;
}

function legacySqdArtifact(metrics: AlgorithmMetrics): CircuitArtifact[] {
  const record = asRecord(metrics["sci_result_package"]);
  const logical = asCircuitPreview(record?.["circuit_preview"]);
  if (!logical) return [];
  return [
    {
      id: "sqd.legacy.latest",
      role: "sqd_sampling",
      phase: "recovery",
      iteration: latestIteration(
        Array.isArray(metrics["configuration_recovery_trace"])
          ? metrics["configuration_recovery_trace"].flatMap((entry) =>
              isRecord(entry) ? [entry] : [],
            )
          : [],
      ),
      representative: true,
      label: "Latest recovery iter",
      logical,
      preview: logical,
    },
  ];
}

function legacySkqdArtifact(metrics: AlgorithmMetrics): CircuitArtifact[] {
  const sqdCore = asRecord(metrics["sqd_core"]);
  const sqdPackage = asRecord(sqdCore?.["sci_result_package"]);
  const logical = asCircuitPreview(sqdPackage?.["circuit_preview"]);
  if (!logical) return [];
  return [
    {
      id: "skqd.legacy.seed",
      role: "sqd_seed",
      phase: "seed",
      representative: true,
      label: "SQD seed",
      logical,
      preview: logical,
    },
  ];
}

export function extractCircuitArtifacts(
  algorithm: string | undefined | null,
  metrics: AlgorithmMetrics,
): CircuitArtifact[] {
  const rawArtifacts = metrics["circuit_artifacts"];
  const normalized = Array.isArray(rawArtifacts)
    ? rawArtifacts.flatMap((artifact, index) => {
        const normalizedArtifact = normalizeCircuitArtifact(artifact, index);
        return normalizedArtifact ? [normalizedArtifact] : [];
      })
    : [];

  if (normalized.length > 0) {
    return normalized;
  }

  switch (algorithm?.toLowerCase()) {
    case "sqd":
      return legacySqdArtifact(metrics);
    case "skqd":
      return legacySkqdArtifact(metrics);
    default:
      return [];
  }
}

function extractCircuitArtifactPolicy(metrics: AlgorithmMetrics): JsonObject | null {
  return asRecord(metrics["circuit_artifact_policy"]);
}

export function parseVqeMetrics(m: AlgorithmMetrics): VqeMetrics {
  const objectiveEvaluations = m["objective_evaluations"];
  const optimizerIterations = m["optimizer_iterations"];
  const effectiveMaxIterations = m["effective_max_iterations"];
  const maxFunctionEvaluations = m["max_function_evaluations"];
  return {
    convergence_trace: asNumbers(m["convergence_trace"]),
    optimizer_diagnostics: asRecord(m["optimizer_diagnostics"]),
    objective_evaluations: isNumber(objectiveEvaluations) ? objectiveEvaluations : null,
    optimizer_iterations: isNumber(optimizerIterations) ? optimizerIterations : null,
    effective_max_iterations: isNumber(effectiveMaxIterations) ? effectiveMaxIterations : null,
    max_function_evaluations: isNumber(maxFunctionEvaluations) ? maxFunctionEvaluations : null,
    bloch_vectors: asBlochVectors(m["bloch_vectors"]),
    density_matrix_real: asMatrix(m["density_matrix_real"]),
    density_matrix_imag: asMatrix(m["density_matrix_imag"]),
    circuit_artifacts: extractCircuitArtifacts("vqe", m),
    circuit_artifact_policy: extractCircuitArtifactPolicy(m),
  };
}

export function parseSqdMetrics(m: AlgorithmMetrics): SqdMetrics {
  const recoveryRaw = m["configuration_recovery_trace"];
  const recovery: JsonObject[] = Array.isArray(recoveryRaw)
    ? recoveryRaw.flatMap((row) => (isRecord(row) ? [row] : []))
    : [];
  return {
    sci_energies: asNumbers(m["sci_energies"]),
    configuration_recovery_trace: recovery,
    spin_diagnostics: asRecord(m["spin_diagnostics"]),
    postselection_summary: asRecord(m["postselection_summary"]),
    subsampling_summary: asRecord(m["subsampling_summary"]),
    sci_result_package: asRecord(m["sci_result_package"]),
    circuit_artifacts: extractCircuitArtifacts("sqd", m),
    circuit_artifact_policy: extractCircuitArtifactPolicy(m),
  };
}

export function parseKqdMetrics(m: AlgorithmMetrics): KqdMetrics {
  const krylovRank = m["krylov_rank"];
  const selectedLevelIndex = m["selected_level_index"];
  return {
    ritz_values: asNumbers(m["ritz_values"]),
    raw_ritz_values: asNumbers(m["raw_ritz_values"]),
    krylov_rank: isNumber(krylovRank) ? krylovRank : 0,
    orthogonality_metrics: asRecord(m["orthogonality_metrics"]),
    stability_summary: asRecord(m["stability_summary"]),
    selected_level_index: isNumber(selectedLevelIndex) ? selectedLevelIndex : null,
    circuit_artifacts: extractCircuitArtifacts("kqd", m),
    circuit_artifact_policy: extractCircuitArtifactPolicy(m),
  };
}

export function parseQfdMetrics(m: AlgorithmMetrics): QfdMetrics {
  const selectedLevelIndex = m["selected_level_index"];
  return {
    filter_eigenvalues: asNumbers(m["filter_eigenvalues"]),
    raw_filter_eigenvalues: asNumbers(m["raw_filter_eigenvalues"]),
    conditioning_summary: asRecord(m["conditioning_summary"]),
    stability_summary: asRecord(m["stability_summary"]),
    selected_level_index: isNumber(selectedLevelIndex) ? selectedLevelIndex : null,
  };
}

export function parseQseMetrics(m: AlgorithmMetrics): QseMetrics {
  const overlapCondition = m["overlap_condition"];
  const referenceStateEnergy = m["reference_state_energy"];
  const residualNorm = m["residual_norm"];
  const relativeResidual = m["relative_residual"];
  const convergenceThreshold = m["convergence_threshold"];
  return {
    eigenvalues: asNumbers(m["eigenvalues"]),
    overlap_condition: isNumber(overlapCondition) ? overlapCondition : null,
    reference_state_energy: isNumber(referenceStateEnergy) ? referenceStateEnergy : null,
    residual_norm: isNumber(residualNorm) ? residualNorm : null,
    relative_residual: isNumber(relativeResidual) ? relativeResidual : null,
    convergence_threshold: isNumber(convergenceThreshold) ? convergenceThreshold : null,
    circuit_artifacts: extractCircuitArtifacts("qse", m),
    circuit_artifact_policy: extractCircuitArtifactPolicy(m),
  };
}

export function parseSkqdMetrics(m: AlgorithmMetrics): SkqdMetrics {
  return {
    sqd_core: asRecord(m["sqd_core"]),
    krylov_extension_diagnostics: asRecord(m["krylov_extension_diagnostics"]),
    circuit_artifacts: extractCircuitArtifacts("skqd", m),
    circuit_artifact_policy: extractCircuitArtifactPolicy(m),
  };
}

export type ParsedAlgorithmMetrics =
  | { type: "vqe"; metrics: VqeMetrics }
  | { type: "sqd"; metrics: SqdMetrics }
  | { type: "kqd"; metrics: KqdMetrics }
  | { type: "qfd"; metrics: QfdMetrics }
  | { type: "qse"; metrics: QseMetrics }
  | { type: "skqd"; metrics: SkqdMetrics }
  | { type: "unknown"; metrics: AlgorithmMetrics };

export function parseAlgorithmMetrics(
  algorithm: string | undefined | null,
  raw: AlgorithmMetrics | null | undefined,
): ParsedAlgorithmMetrics {
  const m = raw ?? {};
  switch (algorithm?.toLowerCase()) {
    case "vqe":
      return { type: "vqe", metrics: parseVqeMetrics(m) };
    case "sqd":
      return { type: "sqd", metrics: parseSqdMetrics(m) };
    case "kqd":
      return { type: "kqd", metrics: parseKqdMetrics(m) };
    case "qfd":
      return { type: "qfd", metrics: parseQfdMetrics(m) };
    case "qse":
      return { type: "qse", metrics: parseQseMetrics(m) };
    case "skqd":
      return { type: "skqd", metrics: parseSkqdMetrics(m) };
    default:
      return { type: "unknown", metrics: m };
  }
}
