/**
 * Run response, result, metric, event, and health types.
 */

import type { RunConfigJson, RunControlResponse } from "@/types/run-config";
import type {
  JsonObject,
  BackendTarget,
  RunAlgorithm,
  RunEventType,
  RunStatus,
  UUID,
  ValidationErrorCode,
} from "@/types/run-status";

export interface ClassicalReferenceMetrics extends JsonObject {
  hf?: number | null;
  fci?: number | null;
}

export interface EnergyPolicy extends JsonObject {
  reported_energy_field?: string | null;
  primary_energy_field?: string | null;
  primary_energy_source?: string | null;
  selection_rule?: string | null;
  candidate_energy_fields?: string[] | null;
  classical_references_are_context_only?: boolean | null;
}

export interface CircuitPreview extends JsonObject {
  qasm?: string | null;
  diagram_svg?: string | null;
  qubits?: number | null;
  classical_bits?: number | null;
  style?: string | null;
}

export interface CircuitArtifact extends JsonObject {
  id?: string | null;
  artifact_id?: string | null;
  role?: string | null;
  phase?: string | null;
  iteration?: number | null;
  representative?: boolean | null;
  label?: string | null;
  source?: string | null;
  logical?: CircuitPreview | null;
  preview?: CircuitPreview | null;
  transpiled?: CircuitPreview | null;
  transpiled_preview?: CircuitPreview | null;
  backend_target?: string | null;
  primitive_family?: string | null;
  job_ids?: string[] | null;
  pub_count?: number | null;
  shots?: number | null;
  transpilation_summary?: JsonObject | null;
  downsampling?: JsonObject | null;
}

export interface VqeAlgorithmMetrics extends JsonObject {
  convergence_trace?: number[];
  optimizer_diagnostics?: JsonObject | null;
  objective_evaluations?: number | null;
  optimizer_iterations?: number | null;
  effective_max_iterations?: number | null;
  max_function_evaluations?: number | null;
  bloch_vectors?: number[][] | null;
  density_matrix_real?: number[][] | null;
  density_matrix_imag?: number[][] | null;
  circuit_artifacts?: CircuitArtifact[] | null;
  classical_references?: ClassicalReferenceMetrics | null;
  energy_policy?: EnergyPolicy | null;
}

export interface SqdAlgorithmMetrics extends JsonObject {
  sci_energies?: number[];
  configuration_recovery_trace?: JsonObject[];
  spin_diagnostics?: JsonObject | null;
  postselection_summary?: JsonObject | null;
  subsampling_summary?: JsonObject | null;
  sci_result_package?: JsonObject | null;
  circuit_artifacts?: CircuitArtifact[] | null;
  circuit_artifact_policy?: JsonObject | null;
  classical_references?: ClassicalReferenceMetrics | null;
  energy_policy?: EnergyPolicy | null;
}

export interface KqdAlgorithmMetrics extends JsonObject {
  ritz_values?: number[];
  raw_ritz_values?: number[];
  krylov_rank?: number;
  orthogonality_metrics?: JsonObject | null;
  stability_summary?: JsonObject | null;
  selected_level_index?: number | null;
  circuit_artifacts?: CircuitArtifact[] | null;
  classical_references?: ClassicalReferenceMetrics | null;
  energy_policy?: EnergyPolicy | null;
}

export interface QfdAlgorithmMetrics extends JsonObject {
  filter_eigenvalues?: number[];
  raw_filter_eigenvalues?: number[];
  conditioning_summary?: JsonObject | null;
  stability_summary?: JsonObject | null;
  selected_level_index?: number | null;
  classical_references?: ClassicalReferenceMetrics | null;
  energy_policy?: EnergyPolicy | null;
}

export interface QseAlgorithmMetrics extends JsonObject {
  eigenvalues?: number[];
  overlap_condition?: number | null;
  reference_state_energy?: number | null;
  residual_norm?: number | null;
  relative_residual?: number | null;
  convergence_threshold?: number | null;
  circuit_artifacts?: CircuitArtifact[] | null;
  classical_references?: ClassicalReferenceMetrics | null;
  energy_policy?: EnergyPolicy | null;
}

export interface SkqdAlgorithmMetrics extends JsonObject {
  sqd_core?: JsonObject | null;
  krylov_extension_diagnostics?: JsonObject | null;
  circuit_artifacts?: CircuitArtifact[] | null;
  circuit_artifact_policy?: JsonObject | null;
  classical_references?: ClassicalReferenceMetrics | null;
  energy_policy?: EnergyPolicy | null;
}

export type AlgorithmMetrics =
  | VqeAlgorithmMetrics
  | SqdAlgorithmMetrics
  | KqdAlgorithmMetrics
  | QfdAlgorithmMetrics
  | QseAlgorithmMetrics
  | SkqdAlgorithmMetrics
  | JsonObject;

/**
 * Complete run response from the backend.
 * Matches backend RunResponse.
 */
export interface RunResponse {
  id: UUID;
  molecule_id: UUID;
  status: RunStatus;
  algorithm?: RunAlgorithm | null;
  mode?: "easy" | "advanced" | null;
  backend_target?: BackendTarget | null;
  config_json: RunConfigJson; // Includes basis_set
  basis_set?: string | null;
  ibm_job_id: string | null;
  client_request_id: UUID | null;
  versions: Record<string, string> | null;
  metadata: Record<string, unknown> | null;
  initial_estimate?: RunEstimate | null;
  latest_estimate?: RunEstimate | null;
  execution_generation?: number;
  restarted_from_run_id?: UUID | null;
  credential_profile_id?: UUID | null;
  credential_profile_name?: string | null;
  created_at: string; // ISO 8601 datetime string
  updated_at: string; // ISO 8601 datetime string
}

export type RunRestartResponse =
  | RunResponse
  | (RunControlResponse & {
      source_run_id?: UUID | null;
      new_run_id?: UUID | null;
      target_run_id?: UUID | null;
    });

export interface RunSummaryResponse {
  id: UUID;
  molecule_id: UUID;
  molecule_name?: string | null;
  status: RunStatus;
  algorithm?: RunAlgorithm | null;
  backend_target?: BackendTarget | null;
  backend_name?: string | null;
  converged?: boolean | null;
  chemical_accurate?: boolean | null;
  metadata: Record<string, unknown> | null;
  latest_estimate?: RunEstimate | null;
  execution_generation?: number;
  restarted_from_run_id?: UUID | null;
  credential_profile_id?: UUID | null;
  credential_profile_name?: string | null;
  basis_set?: string | null;
  created_at: string; // ISO 8601 datetime string
  updated_at: string; // ISO 8601 datetime string
}

export interface RunEstimate {
  source: string;
  algorithm: string;
  estimated_total_iterations: number | null;
  estimated_remaining_iterations: number | null;
  estimated_total_seconds: number | null;
  estimated_remaining_seconds: number | null;
  estimated_primary_iterations?: number | null;
  estimated_reference_iterations?: number | null;
  estimated_total_work_units?: number | null;
  work_unit_policy?: string | null;
  reference_workload?: string | null;
  confidence: number | null;
  updated_at: string; // ISO 8601 datetime string
}

/**
 * Paginated list of runs response.
 * Matches backend RunListResponse.
 */
export interface RunListResponse {
  items: RunResponse[];
  total: number;
  limit: number;
  offset: number;
}

export interface RunSummaryListResponse {
  items: RunSummaryResponse[];
  total: number;
  limit: number;
  offset: number;
}

/**
 * Run result response from the backend.
 * Matches backend RunResultResponse.
 */
export interface RunResultResponse {
  run_id: UUID;
  energy: number;
  final_energy?: number | null;
  best_observed_energy?: number | null;
  reported_energy?: number | null;
  reported_energy_source?: string | null;
  reference_energy?: number | null;
  reference_basis?: string | null;
  signed_error?: number | null;
  iterations: number;
  optimal_parameters: number[];
  converged: boolean;
  algorithm_metrics?: AlgorithmMetrics | null;
  energy_policy?: EnergyPolicy | null;
  created_at: string; // ISO 8601 datetime string
}

/**
 * Run event response.
 * Matches backend RunEventResponse.
 */
export interface RunEventResponse {
  id: number;
  run_id: UUID;
  sequence: number;
  type: RunEventType;
  payload: Record<string, unknown>;
  created_at: string; // ISO 8601 datetime string
}

/**
 * Paginated list of run events.
 * Matches backend RunEventListResponse.
 */
export interface RunEventListResponse {
  events: RunEventResponse[];
  last_sequence: number;
}

export interface RunValidationErrorDetail {
  field: string;
  message: string;
  code?: ValidationErrorCode | null;
  suggestion?: string | null;
}

export interface RunValidationResponse {
  valid: boolean;
  errors: RunValidationErrorDetail[];
  warnings: string[];
  estimate?: RunEstimate | null;
}

export interface HealthResponse {
  status: string;
}
