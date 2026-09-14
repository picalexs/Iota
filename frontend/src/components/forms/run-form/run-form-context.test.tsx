import { render, screen } from "@testing-library/react";
import { useForm } from "react-hook-form";
import { describe, expect, it } from "vitest";

import { RunFormProvider, useRunFormContext } from "./run-form-context";
import type { SimulationRunFormData } from "@/types/run";

const defaultValues = {
  molecule_id: null,
  algorithm: "vqe",
  mode: "easy",
  backend_target: null,
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
  easy_options: { goal: "balanced" },
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
    provided_state_vector_text: "[1, 0]",
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
} satisfies SimulationRunFormData;

function ContextProbe() {
  const form = useRunFormContext();
  return <div>{form.watch("advanced_vqe.ansatz_name")}</div>;
}

function TestProvider() {
  const form = useForm<SimulationRunFormData, unknown, SimulationRunFormData>({ defaultValues });
  return (
    <RunFormProvider form={form}>
      <ContextProbe />
    </RunFormProvider>
  );
}

describe("RunFormProvider", () => {
  it("exposes typed form values to nested run-form components", () => {
    render(<TestProvider />);
    expect(screen.getByText("EfficientSU2")).toBeInTheDocument();
  });
});
