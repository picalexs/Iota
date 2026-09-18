import { describe, expect, it } from "vitest";

import { runFormSchema } from "./run-form-schema";
import type { SimulationRunFormData } from "@/types/run";

const validFormData: SimulationRunFormData = {
  molecule_id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  algorithm: "vqe",
  mode: "easy",
  backend_target: "statevector",
  chemical_accuracy_target_ha: 1.6e-3,
  backend_options: {
    selection_policy: "manual",
    backend_name: null,
    shots: 1024,
    optimization_level: 1,
    seed_simulator: null,
    seed_transpiler: null,
    aer_method: "automatic",
  },
  noise_profile: null,
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

describe("runFormSchema", () => {
  it("accepts a complete easy-mode form", () => {
    expect(runFormSchema.safeParse(validFormData).success).toBe(true);
  });

  it("accepts Aer with backend options and a backend-derived noise profile", () => {
    expect(
      runFormSchema.safeParse({
        ...validFormData,
        backend_target: "aer_simulator",
        backend_options: {
          ...validFormData.backend_options,
          shots: 4096,
          aer_method: "density_matrix",
        },
        noise_profile: {
          source: "backend_derived",
          reference_backend: "ibm_brisbane",
        },
      }).success,
    ).toBe(true);
  });

  it("rejects simulator names as backend-derived noise references", () => {
    const result = runFormSchema.safeParse({
      ...validFormData,
      backend_target: "aer_simulator",
      noise_profile: {
        source: "backend_derived",
        reference_backend: "aer_simulator",
      },
    });

    expect(result.success).toBe(false);
  });

  it("accepts KQD on ideal Aer statevector simulation", () => {
    expect(
      runFormSchema.safeParse({
        ...validFormData,
        algorithm: "kqd",
        backend_target: "aer_simulator",
        backend_options: {
          ...validFormData.backend_options,
          aer_method: "statevector",
        },
      }).success,
    ).toBe(true);
  });

  it("accepts KQD Aer with a noise profile by switching to the projected-matrix path", () => {
    expect(
      runFormSchema.safeParse({
        ...validFormData,
        algorithm: "kqd",
        mode: "advanced",
        backend_target: "aer_simulator",
        noise_profile: {
          source: "custom_preset",
          preset: "readout_bias",
          p01: 0.01,
          p10: 0.02,
        },
        advanced_kqd: {
          ...validFormData.advanced_kqd,
          krylov_dim: 8,
          evolution_method: "trotter",
        },
      }).success,
    ).toBe(true);
  });

  it("caps noisy Aer KQD projected runs at the hardware matrix limit", () => {
    const result = runFormSchema.safeParse({
      ...validFormData,
      algorithm: "kqd",
      mode: "advanced",
      backend_target: "aer_simulator",
      noise_profile: {
        source: "custom_preset",
        preset: "readout_bias",
        p01: 0.01,
        p10: 0.02,
      },
      advanced_kqd: {
        ...validFormData.advanced_kqd,
        krylov_dim: 9,
      },
    });

    expect(result.success).toBe(false);
    expect(result.error?.issues.map((issue) => issue.path.join("."))).toEqual(
      expect.arrayContaining(["advanced_kqd.krylov_dim"]),
    );
  });

  it("rejects exact KQD evolution when noisy Aer selects the estimator path", () => {
    const result = runFormSchema.safeParse({
      ...validFormData,
      algorithm: "kqd",
      mode: "advanced",
      backend_target: "aer_simulator",
      noise_profile: {
        source: "custom_preset",
        preset: "readout_bias",
        p01: 0.01,
        p10: 0.02,
      },
      advanced_kqd: {
        ...validFormData.advanced_kqd,
        evolution_method: "exact",
      },
    });

    expect(result.success).toBe(false);
    expect(result.error?.issues.map((issue) => issue.path.join("."))).toContain(
      "advanced_kqd.evolution_method",
    );
  });

  it("rejects KQD Aer density-matrix evolution when no projected-matrix path is active", () => {
    const result = runFormSchema.safeParse({
      ...validFormData,
      algorithm: "kqd",
      backend_target: "aer_simulator",
      backend_options: {
        ...validFormData.backend_options,
        aer_method: "density_matrix",
      },
    });

    expect(result.success).toBe(false);
    expect(result.error?.issues.map((issue) => issue.path.join("."))).toEqual(
      expect.arrayContaining(["backend_options.aer_method"]),
    );
  });

  it("allows IBM runtime when manual selection names a backend", () => {
    expect(
      runFormSchema.safeParse({
        ...validFormData,
        backend_target: "ibm_runtime",
        backend_options: {
          ...validFormData.backend_options,
          backend_name: "ibm_brisbane",
        },
      }).success,
    ).toBe(true);
  });

  it("accepts KQD IBM matrix-element runs inside the hardware cap", () => {
    expect(
      runFormSchema.safeParse({
        ...validFormData,
        algorithm: "kqd",
        mode: "advanced",
        backend_target: "ibm_runtime",
        backend_options: {
          ...validFormData.backend_options,
          backend_name: "ibm_brisbane",
        },
        advanced_kqd: {
          ...validFormData.advanced_kqd,
          krylov_dim: 4,
          evolution_method: "trotter",
        },
      }).success,
    ).toBe(true);
  });

  it("rejects exact KQD evolution on IBM because the measured path needs circuits", () => {
    const result = runFormSchema.safeParse({
      ...validFormData,
      algorithm: "kqd",
      mode: "advanced",
      backend_target: "ibm_runtime",
      backend_options: {
        ...validFormData.backend_options,
        backend_name: "ibm_brisbane",
      },
      advanced_kqd: {
        ...validFormData.advanced_kqd,
        evolution_method: "exact",
      },
    });

    expect(result.success).toBe(false);
    expect(result.error?.issues).toContainEqual(
      expect.objectContaining({
        path: ["advanced_kqd", "evolution_method"],
        message: expect.stringContaining("Trotter"),
      }),
    );
  });

  it("rejects KQD IBM matrix-element runs above the hardware cap", () => {
    const result = runFormSchema.safeParse({
      ...validFormData,
      algorithm: "kqd",
      mode: "advanced",
      backend_target: "ibm_runtime",
      backend_options: {
        ...validFormData.backend_options,
        backend_name: "ibm_brisbane",
      },
      advanced_kqd: {
        ...validFormData.advanced_kqd,
        krylov_dim: 14,
      },
    });

    expect(result.success).toBe(false);
    expect(result.error?.issues.map((issue) => issue.path.join("."))).toContain(
      "advanced_kqd.krylov_dim",
    );
  });

  it("rejects QFD Trotter steps above the rollout cap", () => {
    const result = runFormSchema.safeParse({
      ...validFormData,
      algorithm: "qfd",
      mode: "advanced",
      advanced_qfd: {
        ...validFormData.advanced_qfd,
        trotter_steps: 33,
      },
    });

    expect(result.success).toBe(false);
    expect(result.error?.issues.map((issue) => issue.path.join("."))).toContain(
      "advanced_qfd.trotter_steps",
    );
  });

  it("accepts balanced easy-mode KQD on IBM after clamping the projected basis size", () => {
    const result = runFormSchema.safeParse({
      ...validFormData,
      algorithm: "kqd",
      mode: "easy",
      backend_target: "ibm_runtime",
      backend_options: {
        ...validFormData.backend_options,
        backend_name: "ibm_brisbane",
      },
      easy_options: {
        goal: "balanced",
      },
      advanced_kqd: {
        ...validFormData.advanced_kqd,
        evolution_method: "trotter",
      },
    });

    expect(result.success).toBe(true);
  });

  it("requires an IBM backend name for manual selection", () => {
    const result = runFormSchema.safeParse({
      ...validFormData,
      backend_target: "ibm_runtime",
      backend_options: {
        ...validFormData.backend_options,
        backend_name: null,
      },
    });

    expect(result.success).toBe(false);
    expect(result.error?.issues.map((issue) => issue.path.join("."))).toContain(
      "backend_options.backend_name",
    );
  });

  it("requires molecule, algorithm, and backend selections", () => {
    const result = runFormSchema.safeParse({
      ...validFormData,
      molecule_id: null,
      algorithm: null,
      backend_target: null,
    });

    expect(result.success).toBe(false);
    expect(result.error?.issues.map((issue) => issue.path.join("."))).toEqual(
      expect.arrayContaining(["molecule_id", "backend_target"]),
    );
  });

  it("validates only the selected advanced algorithm constraints", () => {
    const result = runFormSchema.safeParse({
      ...validFormData,
      algorithm: "kqd",
      mode: "advanced",
      advanced_vqe: {
        ...validFormData.advanced_vqe,
        max_iterations: 6000,
      },
      advanced_kqd: {
        ...validFormData.advanced_kqd,
        krylov_dim: 100,
      },
    });

    expect(result.success).toBe(false);
    expect(result.error?.issues.map((issue) => issue.path.join("."))).toEqual([
      "advanced_kqd.krylov_dim",
    ]);
  });

  it("accepts QSE provided-state input when the state vector editor is populated", () => {
    expect(
      runFormSchema.safeParse({
        ...validFormData,
        algorithm: "qse",
        mode: "advanced",
        advanced_qse: {
          ...validFormData.advanced_qse,
          reference_method: "provided_state",
          provided_state_vector_text: "[0.70710678, 0, 0, 0.70710678]",
        },
      }).success,
    ).toBe(true);
  });

  it("rejects malformed QSE provided-sector input", () => {
    const result = runFormSchema.safeParse({
      ...validFormData,
      algorithm: "qse",
      mode: "advanced",
      advanced_qse: {
        ...validFormData.advanced_qse,
        reference_method: "provided_sector",
        provided_sector_rows: [{ bitstring: "oops", real: "1", imag: "0" }],
      },
    });

    expect(result.success).toBe(false);
    expect(result.error?.issues.map((issue) => issue.path.join("."))).toContain(
      "advanced_qse.provided_sector_rows",
    );
  });
});
