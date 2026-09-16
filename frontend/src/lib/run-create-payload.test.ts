import { describe, expect, it } from "vitest";

import { buildAlgorithmAwareRunCreate } from "./run-create-payload";
import type { SimulationRunFormData } from "@/types/run";

const baseValues: SimulationRunFormData = {
  molecule_id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  algorithm: "vqe",
  mode: "easy",
  backend_target: "aer_simulator",
  chemical_accuracy_target_ha: 1.6e-3,
  backend_options: {
    selection_policy: "manual",
    backend_name: "aer_simulator",
    shots: 2048,
    optimization_level: 2,
    seed_simulator: 11,
    seed_transpiler: 17,
    aer_method: "density_matrix",
  },
  noise_profile: {
    source: "backend_derived",
    reference_backend: "ibm_brisbane",
  },
  basis_set_override: "",
  easy_options: {
    goal: "balanced",
  },
  advanced_vqe: {
    ansatz_name: "EfficientSU2",
    optimizer_name: "COBYLA",
    max_iterations: 240,
    max_function_evaluations: 240,
    reps: 1,
    initial_point_strategy: "zero_plus_seeded_random",
    initial_point_candidates: 3,
    optimizer_options_text: "",
    initial_parameters_text: "",
    parameter_bounds_text: "",
    seed: null,
    convergence_threshold: null,
  },
  advanced_sqd: {
    samples_per_batch: 320,
    num_batches: 6,
    max_iterations: 48,
    sampling_state_source: "vqe",
    sampling_vqe_ansatz_name: "NumberPreserving",
    sampling_vqe_optimizer_name: "COBYLA",
    sampling_vqe_max_iterations: 128,
    sampling_vqe_reps: 1,
    sampling_vqe_seed: null,
    num_elec_a: null,
    num_elec_b: null,
    energy_tol: 7.5e-5,
    occupancies_tol: 7.5e-5,
    min_selected_configurations: null,
    seed: null,
    symmetrize_spin: false,
    carryover_threshold: null,
    max_dim_mode: "shared",
    max_dim: 24,
    max_dim_a: null,
    max_dim_b: null,
    spin_sq_target: null,
    sci_solver_options_text: "",
  },
  advanced_kqd: {
    krylov_dim: 12,
    time_step: 0.35,
    evolution_method: "exact",
    trotter_steps: 1,
    residual_tolerance: 1e-8,
  },
  advanced_qfd: {
    num_time_points: 16,
    max_time: 2.5,
    time_grid_type: "linear",
    trotter_steps: 1,
    residual_tolerance: 1e-6,
  },
  advanced_qse: {
    reference_method: "vqe",
    provided_state_vector_text: "",
    provided_sector_rows: [{ bitstring: "", real: "1", imag: "0" }],
    excitation_level: "singles_doubles",
    max_subspace_dim: 8,
    vqe_reference_ansatz_name: "EfficientSU2",
    vqe_reference_optimizer_name: "COBYLA",
    vqe_reference_max_iterations: 240,
    vqe_reference_reps: 1,
    regularization: 1e-7,
    overlap_threshold: 1e-5,
    residual_tolerance: 1e-8,
  },
  advanced_skqd: {
    samples_per_state: 1024,
    num_elec_a: null,
    num_elec_b: null,
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
};

describe("buildAlgorithmAwareRunCreate", () => {
  it("includes backend options and noise profile in the payload", () => {
    expect(buildAlgorithmAwareRunCreate(baseValues)).toMatchObject({
      backend_target: "aer_simulator",
      backend_options: {
        selection_policy: "manual",
        backend_name: "aer_simulator",
        shots: 2048,
        optimization_level: 2,
        seed_simulator: 11,
        seed_transpiler: 17,
        aer_method: "density_matrix",
      },
      noise_profile: {
        source: "backend_derived",
        reference_backend: "ibm_brisbane",
      },
    });
  });

  it("includes the correlated SQD sampling-state configuration", () => {
    const payload = buildAlgorithmAwareRunCreate({
      ...baseValues,
      algorithm: "sqd",
      mode: "advanced",
    });

    expect(payload.advanced_config).toMatchObject({
      algorithm: "sqd",
      sampling_state_source: "vqe",
      sampling_vqe_ansatz_name: "NumberPreserving",
      sampling_vqe_optimizer_name: "COBYLA",
      sampling_vqe_max_iterations: 128,
      sampling_vqe_reps: 1,
    });
  });

  it("maps disabled noise to null", () => {
    expect(
      buildAlgorithmAwareRunCreate({
        ...baseValues,
        noise_profile: null,
      }).noise_profile,
    ).toBeNull();
  });

  it("includes QFD trotter steps in advanced payloads", () => {
    const payload = buildAlgorithmAwareRunCreate({
      ...baseValues,
      algorithm: "qfd",
      mode: "advanced",
      noise_profile: null,
      advanced_qfd: {
        ...baseValues.advanced_qfd,
        trotter_steps: 4,
      },
    });

    expect(payload.advanced_config).toMatchObject({
      algorithm: "qfd",
      trotter_steps: 4,
    });
  });

  it("maps QSE provided-sector editor text into sparse amplitudes", () => {
    const payload = buildAlgorithmAwareRunCreate({
      ...baseValues,
      algorithm: "qse",
      mode: "advanced",
      noise_profile: null,
      advanced_qse: {
        ...baseValues.advanced_qse,
        reference_method: "provided_sector",
        provided_sector_rows: [
          { bitstring: "1100", real: "0.8", imag: "0" },
          { bitstring: "1010", real: "-0.2", imag: "0" },
        ],
      },
    });

    expect(payload.advanced_config).toMatchObject({
      algorithm: "qse",
      reference_method: "provided_sector",
      provided_sector_amplitudes: [
        { bitstring: "1100", amplitude: 0.8 },
        { bitstring: "1010", amplitude: -0.2 },
      ],
    });
  });
});
