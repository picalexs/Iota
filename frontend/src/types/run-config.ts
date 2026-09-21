/**
 * Run configuration, molecule, form, and validation request types.
 */

import type {
  BackendTarget,
  EasyGoal,
  JsonValue,
  RunAlgorithm,
  RunMode,
  RunStatus,
  UUID,
} from "@/types/run-status";
export type {
  ConfigChoiceMetadata,
  EasyGoalPresetMetadata,
  RunConfigMetadataResponse,
} from "@/types/api";

/**
 * Atom representation in Cartesian coordinates.
 * Matches backend AtomSchema.
 */
export interface AtomSchema {
  symbol: string;
  x: number;
  y: number;
  z: number;
}

/**
 * Active space definition for correlated calculations.
 * Matches backend ActiveSpaceSchema.
 */
export interface ActiveSpaceSchema {
  n_electrons: number;
  n_orbitals: number;
  [key: string]: unknown; // Allows additional fields like n_frozen_core
}

export interface MoleculeEligibilityResponse {
  selectable: boolean;
  label: string;
  reason?: string | null;
  capability_labels: string[];
}

/**
 * Complete molecule response from the backend.
 * Matches backend MoleculeResponse.
 */
export interface MoleculeResponse {
  id: UUID;
  name: string;
  atoms: AtomSchema[];
  basis_set?: string | null;
  charge: number;
  multiplicity: number;
  active_space: ActiveSpaceSchema | null;
  created_at: string; // ISO 8601 datetime string
  updated_at: string; // ISO 8601 datetime string
  eligibility?: MoleculeEligibilityResponse | null;
  visualizable?: boolean;
  runnable_algorithms?: RunAlgorithm[];
  blocking_reasons?: string[];
  warnings?: string[];
  // PubChem enrichment fields (null for manually-created molecules)
  pubchem_cid?: number | null;
  iupac_name?: string | null;
  description?: string | null;
  synonyms?: string[] | null;
  smiles?: string | null;
  inchi?: string | null;
  inchi_key?: string | null;
}

export interface MoleculeSummaryResponse {
  id: UUID;
  name: string;
  charge: number;
  atom_count: number;
  run_count: number;
  formula: string;
  iupac_name?: string | null;
  eligibility?: MoleculeEligibilityResponse | null;
  visualizable?: boolean;
  runnable_algorithms?: RunAlgorithm[];
  blocking_reasons?: string[];
  warnings?: string[];
}

/**
 * Noise profile discriminator shared by the algorithm-aware contract.
 */
export type NoiseModelSource = "backend_derived" | "custom_preset";

export type CustomNoisePreset = "depolarizing_cx" | "thermal_relaxation" | "readout_bias";

export interface BackendDerivedNoiseProfile {
  source: "backend_derived";
  reference_backend: string;
  temperature_mk?: number | null;
}

export interface DepolarizingCxNoiseProfile {
  source: "custom_preset";
  preset: "depolarizing_cx";
  strength: number;
}

export interface ReadoutBiasNoiseProfile {
  source: "custom_preset";
  preset: "readout_bias";
  p01: number;
  p10: number;
}

export interface ThermalRelaxationNoiseProfile {
  source: "custom_preset";
  preset: "thermal_relaxation";
  t1_us: number;
  t2_us: number;
  gate_time_us: number;
}

export type CustomPresetNoiseProfile =
  | DepolarizingCxNoiseProfile
  | ReadoutBiasNoiseProfile
  | ThermalRelaxationNoiseProfile;

export type NoiseProfile = BackendDerivedNoiseProfile | CustomPresetNoiseProfile;

export type BackendSelectionPolicy = "manual" | "least_busy" | "least_error";

export type ChemistryDevice = "CPU" | "GPU" | "AUTO";

export interface ChemistryOptions {
  reference_device?: ChemistryDevice | null;
  selected_ci_device?: ChemistryDevice | null;
}

export type AerMethod =
  | "automatic"
  | "statevector"
  | "density_matrix"
  | "matrix_product_state"
  | "stabilizer"
  | "extended_stabilizer"
  | "unitary"
  | "superop";

export interface BackendOptions {
  selection_policy: BackendSelectionPolicy;
  backend_name: string | null;
  shots: number;
  estimator_precision?: number | null;
  optimization_level: 0 | 1 | 2 | 3;
  seed_simulator: number | null;
  seed_transpiler: number | null;
  aer_method: AerMethod | null;
  device?: "CPU" | "GPU" | null;
  batched_shots_gpu?: boolean | null;
  runtime_parameter_bind_enable?: boolean | null;
  shot_branching_enable?: boolean | null;
  blocking_enable?: boolean | null;
  cuStateVec_enable?: boolean | null;
  max_parallel_threads?: number | null;
  max_parallel_experiments?: number | null;
  max_parallel_shots?: number | null;
  aer_pub_chunk_size?: number | null;
  credential_profile_id?: UUID | null;
}

export interface BackendCapability {
  target: BackendTarget;
  enabled: boolean;
  available?: boolean | null;
  credential_configured?: boolean | null;
  credentials_usable?: boolean | null;
  supports_noise_profile?: boolean | null;
  supports_shots?: boolean | null;
  supports_transpilation_preview?: boolean | null;
  reason?: string | null;
  status?: string | null;
  backends?: BackendDeviceSummary[];
  default_backend?: string | null;
}

export interface BackendDeviceSummary {
  name: string;
  simulator?: boolean | null;
  operational?: boolean | null;
  pending_jobs?: number | null;
  num_qubits?: number | null;
  basis_gates?: string[] | null;
  coupling_map?: number[][] | null;
  coupling_map_edges?: number | null;
  max_shots?: number | null;
  error_rate?: number | null;
  processor_type?: BackendProcessorTypeSummary | null;
  qubit_errors?: BackendQubitErrorSummary[] | null;
  gate_errors?: BackendGateErrorSummary[] | null;
}

export interface BackendProcessorTypeSummary {
  family?: string | null;
  revision?: string | null;
  segment?: string | null;
}

export interface BackendQubitErrorSummary {
  qubit: number;
  readout_error?: number | null;
  t1_us?: number | null;
  t2_us?: number | null;
  operational?: boolean | null;
}

export interface BackendGateErrorSummary {
  source: number;
  target: number;
  gate?: string | null;
  error?: number | null;
  length_ns?: number | null;
}

export interface BackendCapabilitiesResponse {
  backends: BackendCapability[];
}

export interface TranspilationPreviewRequest {
  molecule_id: UUID;
  algorithm: RunAlgorithm;
  backend_target: BackendTarget;
  num_qubits: number;
  backend_options: BackendOptions;
  noise_profile?: NoiseProfile | null;
  basis_set_override?: string | null;
}

export interface TranspilationPreviewResponse {
  available: boolean;
  backend_name?: string | null;
  num_qubits?: number | null;
  circuit_depth?: number | null;
  two_qubit_depth?: number | null;
  transpiled_depth?: number | null;
  estimated_queue_seconds?: number | null;
  warnings?: string[];
  message?: string | null;
}

export interface EasyOptions {
  goal: EasyGoal;
}

export interface VQEAdvancedConfig {
  algorithm: "vqe";
  ansatz_name: string;
  optimizer_name: string;
  max_iterations: number;
  max_function_evaluations?: number | null;
  reps?: number;
  optimizer_options?: Record<string, unknown> | null;
  initial_parameters?: number[] | null;
  initial_point_strategy?: "seeded_random" | "zero" | "zero_plus_seeded_random" | null;
  initial_point_candidates?: number | null;
  seed?: number | null;
  convergence_threshold?: number | null;
  parameter_bounds?: number[][] | null;
}

export interface SQDAdvancedConfig {
  algorithm: "sqd";
  samples_per_batch: number;
  num_batches: number;
  max_iterations: number;
  sampling_state_source?: "hf" | "vqe";
  sampling_vqe_ansatz_name?: string | null;
  sampling_vqe_optimizer_name?: string | null;
  sampling_vqe_max_iterations?: number | null;
  sampling_vqe_reps?: number | null;
  sampling_vqe_seed?: number | null;
  num_elec_a?: number | null;
  num_elec_b?: number | null;
  energy_tol?: number | null;
  occupancies_tol?: number | null;
  min_selected_configurations?: number | null;
  seed?: number | null;
  symmetrize_spin?: boolean | null;
  carryover_threshold?: number | null;
  max_dim?: number | [number, number] | null;
  spin_sq_target?: number | null;
  sci_solver_options?: Record<string, unknown> | null;
}

export interface SQDSamplingParams {
  samples_per_batch: number;
  num_batches: number;
  max_iterations: number;
  num_elec_a?: number | null;
  num_elec_b?: number | null;
  energy_tol?: number | null;
  occupancies_tol?: number | null;
  min_selected_configurations?: number | null;
  seed?: number | null;
  symmetrize_spin?: boolean | null;
  carryover_threshold?: number | null;
  max_dim?: number | [number, number] | null;
  spin_sq_target?: number | null;
  sci_solver_options?: Record<string, unknown> | null;
}

export interface SKQDSamplingParams {
  num_elec_a?: number | null;
  num_elec_b?: number | null;
  min_selected_configurations?: number | null;
  seed?: number | null;
  symmetrize_spin?: boolean | null;
  max_dim?: number | [number, number] | "full" | null;
  spin_sq_target?: number | null;
  sci_solver_options?: Record<string, unknown> | null;
}

export interface KQDAdvancedConfig {
  algorithm: "kqd";
  krylov_dim: number;
  time_step: number;
  evolution_method?: "exact" | "trotter";
  trotter_steps?: number;
  residual_tolerance?: number | null;
}

export interface QFDAdvancedConfig {
  algorithm: "qfd";
  num_time_points: number;
  max_time: number;
  time_grid_type?: "linear" | "geometric";
  trotter_steps?: number;
  residual_tolerance?: number | null;
}

export interface QSEComplexScalar {
  real: number;
  imag: number;
}

export type QSEReferenceScalar = number | QSEComplexScalar;

export interface QSESectorAmplitude {
  bitstring: string;
  amplitude: QSEReferenceScalar;
}

export interface QSEAdvancedConfig {
  algorithm: "qse";
  reference_method: "hf" | "vqe" | "provided_state" | "provided_sector";
  provided_state_vector?: QSEReferenceScalar[] | null;
  provided_sector_amplitudes?: QSESectorAmplitude[] | null;
  excitation_level: "singles" | "singles_doubles";
  max_subspace_dim?: number | null;
  vqe_reference_ansatz_name?: string | null;
  vqe_reference_optimizer_name?: string | null;
  vqe_reference_max_iterations?: number | null;
  vqe_reference_reps?: number | null;
  regularization?: number | null;
  overlap_threshold?: number | null;
  residual_tolerance?: number | null;
}

export interface SKQDAdvancedConfig {
  algorithm: "skqd";
  samples_per_state: number;
  base_sampling_options: SKQDSamplingParams;
  krylov_extension_dim: number;
  time_step?: number | null;
  residual_tolerance?: number | null;
}

export type AdvancedConfig =
  | VQEAdvancedConfig
  | SQDAdvancedConfig
  | KQDAdvancedConfig
  | QFDAdvancedConfig
  | QSEAdvancedConfig
  | SKQDAdvancedConfig;

export type RunConfigValue =
  | JsonValue
  | EasyOptions
  | AdvancedConfig
  | BackendOptions
  | ChemistryOptions
  | NoiseProfile
  | undefined;

export interface RunConfigJson {
  [key: string]: RunConfigValue;
  algorithm?: RunAlgorithm | null;
  mode?: RunMode | null;
  backend_target?: BackendTarget | null;
  chemical_accuracy_target_ha?: number | null;
  basis_set?: string | null;
  basis_set_override?: string | null;
  easy_options?: EasyOptions | null;
  advanced_config?: AdvancedConfig | null;
  backend_options?: BackendOptions | null;
  chemistry_options?: ChemistryOptions | null;
  noise_profile?: NoiseProfile | null;
  client_request_id?: UUID | null;
  versions?: Record<string, string> | null;
}

/**
 * Algorithm-aware run creation payload.
 */
export interface AlgorithmAwareRunCreate {
  molecule_id: UUID;
  client_request_id?: UUID;
  algorithm: RunAlgorithm;
  mode: RunMode;
  backend_target: BackendTarget;
  chemical_accuracy_target_ha?: number | null;
  easy_options?: EasyOptions;
  advanced_config?: AdvancedConfig;
  backend_options?: BackendOptions;
  chemistry_options?: ChemistryOptions | null;
  basis_set_override?: string;
  noise_profile?: NoiseProfile | null;
  ibm_runtime_confirmed?: boolean;
}

export interface QSEProvidedSectorRow {
  bitstring: string;
  real: string;
  imag: string;
}

/**
 * Algorithm-aware form state used by the simulation run builder UI.
 * This is a frontend-only state model (not a direct API DTO).
 */
export interface SimulationRunFormData {
  molecule_id: UUID | null;
  algorithm: RunAlgorithm | null;
  mode: RunMode;
  backend_target: BackendTarget | null;
  chemical_accuracy_target_ha: number | null;
  backend_options: BackendOptions;
  chemistry_options?: ChemistryOptions | null;
  noise_profile: NoiseProfile | null;
  basis_set_override: string;
  easy_options: EasyOptions;
  advanced_vqe: {
    ansatz_name: string;
    optimizer_name: string;
    max_iterations: number | null;
    max_function_evaluations: number | null;
    reps: number;
    initial_point_strategy: "seeded_random" | "zero" | "zero_plus_seeded_random";
    initial_point_candidates: number | null;
    optimizer_options_text: string;
    initial_parameters_text: string;
    parameter_bounds_text: string;
    seed: number | null;
    convergence_threshold: number | null;
  };
  advanced_sqd: {
    samples_per_batch: number | null;
    num_batches: number | null;
    max_iterations: number | null;
    sampling_state_source: "hf" | "vqe";
    sampling_vqe_ansatz_name: string;
    sampling_vqe_optimizer_name: string;
    sampling_vqe_max_iterations: number | null;
    sampling_vqe_reps: number | null;
    sampling_vqe_seed: number | null;
    num_elec_a: number | null;
    num_elec_b: number | null;
    energy_tol: number | null;
    occupancies_tol: number | null;
    min_selected_configurations: number | null;
    seed: number | null;
    symmetrize_spin: boolean;
    carryover_threshold: number | null;
    max_dim_mode: "shared" | "spin_resolved";
    max_dim: number | null;
    max_dim_a: number | null;
    max_dim_b: number | null;
    spin_sq_target: number | null;
    sci_solver_options_text: string;
  };
  advanced_kqd: {
    krylov_dim: number | null;
    time_step: number | null;
    evolution_method: "exact" | "trotter";
    trotter_steps: number | null;
    residual_tolerance: number | null;
  };
  advanced_qfd: {
    num_time_points: number | null;
    max_time: number | null;
    time_grid_type: "linear" | "geometric";
    trotter_steps: number | null;
    residual_tolerance: number | null;
  };
  advanced_qse: {
    reference_method: "hf" | "vqe" | "provided_state" | "provided_sector";
    provided_state_vector_text: string;
    provided_sector_rows: QSEProvidedSectorRow[];
    excitation_level: "singles" | "singles_doubles";
    max_subspace_dim: number | null;
    vqe_reference_ansatz_name: string;
    vqe_reference_optimizer_name: string;
    vqe_reference_max_iterations: number | null;
    vqe_reference_reps: number | null;
    regularization: number | null;
    overlap_threshold: number | null;
    residual_tolerance: number | null;
  };
  advanced_skqd: {
    num_elec_a: number | null;
    num_elec_b: number | null;
    min_selected_configurations: number | null;
    seed: number | null;
    symmetrize_spin: boolean;
    max_dim_mode: "shared" | "spin_resolved";
    max_dim: number | null;
    max_dim_a: number | null;
    max_dim_b: number | null;
    spin_sq_target: number | null;
    sci_solver_options_text: string;
    samples_per_state: number | null;
    krylov_extension_dim: number | null;
    time_step: number | null;
    residual_tolerance: number | null;
  };
}

/**
 * Form validation error types
 */
export type ValidationError = {
  [key: string]: string; // Field name -> error message
};

// --- Additional API types ---

export type RunCreate = AlgorithmAwareRunCreate;

export interface RunCancelResponse {
  id: UUID;
  status: RunStatus;
}

export interface RunControlResponse {
  id: UUID;
  status: RunStatus;
  execution_generation?: number;
  message?: string | null;
  child_run_id?: UUID | null;
  checkpoint_id?: UUID | null;
}

export interface MoleculeCreate {
  name: string;
  atoms: AtomSchema[];
  charge?: number;
  multiplicity?: number;
  active_space?: ActiveSpaceSchema | null;
}

export interface MoleculeUpdate {
  name?: string;
  atoms?: AtomSchema[];
  charge?: number;
  multiplicity?: number;
  active_space?: ActiveSpaceSchema | null;
}

export interface RunListParams {
  molecule_id?: UUID;
  status?: RunStatus;
  backend_target?: BackendTarget;
  converged?: boolean;
  chemical_accurate?: boolean;
  limit?: number;
  offset?: number;
}

export interface MoleculeListParams {
  q?: string;
  charge?: number;
  limit?: number;
  offset?: number;
}

export interface MoleculeListResponse {
  items: MoleculeResponse[];
  total: number;
}

export interface MoleculeSummaryListResponse {
  items: MoleculeSummaryResponse[];
  total: number;
}

export interface BasisSetMetadata {
  id: string;
  label: string;
  description: string;
  family: string;
  recommended: boolean;
  supported_elements: string[];
}

export interface BasisSetListResponse {
  default_basis_set: string;
  basis_sets: BasisSetMetadata[];
}

export interface PubChemImportRequest {
  name: string;
  display_name?: string;
}

export interface XYZPreviewRequest {
  xyz: string;
  name?: string;
  charge?: number;
  multiplicity?: number;
  active_space?: ActiveSpaceSchema | null;
  derive_active_space?: boolean;
}

export interface XYZImportRequest extends XYZPreviewRequest {
  name: string;
}

export interface MoleculeImportPreviewResponse {
  source: "pubchem" | "xyz";
  name: string;
  atoms: AtomSchema[];
  charge: number;
  multiplicity: number;
  active_space: ActiveSpaceSchema | null;
  atom_count: number;
  formula: string;
  eligibility: MoleculeEligibilityResponse;
  visualizable?: boolean;
  runnable_algorithms?: RunAlgorithm[];
  blocking_reasons?: string[];
  warnings?: string[];
  commit_action: "create" | "reuse" | "name_conflict";
  existing_molecule_id?: UUID | null;
  existing_molecule_name?: string | null;
  pubchem_cid?: number | null;
  iupac_name?: string | null;
  description?: string | null;
  synonyms?: string[] | null;
  smiles?: string | null;
  inchi?: string | null;
  inchi_key?: string | null;
}

export interface PubChemSearchResult {
  name: string;
  iupac_name: string;
  formula: string;
  cid: number | null;
}

export interface PubChemSearchResponse {
  results: PubChemSearchResult[];
}

export interface RunValidationRequest {
  molecule_id: UUID;
  run: RunCreate;
}
