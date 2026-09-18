import { describe, expect, it } from "vitest";

import type { RunConfigMetadataResponse } from "@/types/run";
import {
  buildRecommendedAdvancedPatch,
  getChemicalAccuracyTargetOptions,
  goalForChemicalAccuracyTarget,
  kqdUsesKnownBranchEstimatorPath,
} from "./run-form-recommendations";

describe("goalForChemicalAccuracyTarget", () => {
  it("falls back to balanced for invalid targets and chooses the nearest preset otherwise", () => {
    expect(goalForChemicalAccuracyTarget(undefined)).toBe("balanced");
    expect(goalForChemicalAccuracyTarget(-1)).toBe("balanced");
    expect(goalForChemicalAccuracyTarget(Number.NaN)).toBe("balanced");
    expect(goalForChemicalAccuracyTarget(4.8e-3)).toBe("fastest");
    expect(goalForChemicalAccuracyTarget(1.4e-3)).toBe("balanced");
    expect(goalForChemicalAccuracyTarget(4.5e-4)).toBe("best_accuracy");
  });

  it("uses the server catalog target ladder when it is available", () => {
    const options = getChemicalAccuracyTargetOptions([
      { goal: "fastest", label: "9.0 mHa", chemical_accuracy_target_ha: 9e-3 },
      { goal: "balanced", label: "2.0 mHa", chemical_accuracy_target_ha: 2e-3 },
      { goal: "best_accuracy", label: "0.2 mHa", chemical_accuracy_target_ha: 2e-4 },
    ]);

    expect(options).toEqual([
      { goal: "fastest", label: "9.0 mHa", thresholdHa: 9e-3 },
      { goal: "balanced", label: "2.0 mHa", thresholdHa: 2e-3 },
      { goal: "best_accuracy", label: "0.2 mHa", thresholdHa: 2e-4 },
    ]);
    expect(goalForChemicalAccuracyTarget(8e-3, options)).toBe("fastest");
    expect(goalForChemicalAccuracyTarget(3e-4, options)).toBe("best_accuracy");
  });
});

describe("buildRecommendedAdvancedPatch", () => {
  const recommendationMetadata: Pick<RunConfigMetadataResponse, "recommendations"> = {
    recommendations: {
      vqe: {
        balanced: {
          max_iterations: 999,
          unexpected_field: "ignored",
        },
      },
    },
  };

  it("uses server recommendation fields and keeps form-only fallback fields", () => {
    const patch = buildRecommendedAdvancedPatch("vqe", "balanced", null, recommendationMetadata);

    expect(patch.value).toMatchObject({
      max_iterations: 999,
      max_function_evaluations: 448,
      optimizer_options_text: "",
    });
    expect(patch.value).not.toHaveProperty("unexpected_field");
  });

  it("returns algorithm-specific presets with split electrons for SQD-like methods", () => {
    const sqd = buildRecommendedAdvancedPatch("sqd", "balanced", {
      n_electrons: 6,
      n_orbitals: 4,
    });
    const skqdFastest = buildRecommendedAdvancedPatch("skqd", "fastest", {
      n_electrons: 5,
      n_orbitals: 4,
    });
    const skqd = buildRecommendedAdvancedPatch("skqd", "best_accuracy", {
      n_electrons: 5,
      n_orbitals: 4,
    });

    expect(sqd.field).toBe("advanced_sqd");
    expect(sqd.value).toMatchObject({
      samples_per_batch: 512,
      num_batches: 8,
      max_iterations: 8,
      sampling_state_source: "vqe",
      sampling_vqe_ansatz_name: "NumberPreserving",
      sampling_vqe_optimizer_name: "COBYLA",
      sampling_vqe_max_iterations: 448,
      sampling_vqe_reps: 2,
      max_dim: 32,
      num_elec_a: 3,
      num_elec_b: 3,
    });

    expect(skqdFastest.field).toBe("advanced_skqd");
    expect(skqdFastest.value).toMatchObject({
      num_elec_a: 2,
      num_elec_b: 3,
      samples_per_state: 512,
      max_dim: 16,
      krylov_extension_dim: 1,
      time_step: 0.2,
    });

    expect(skqd.field).toBe("advanced_skqd");
    expect(skqd.value).toMatchObject({
      num_elec_a: 2,
      num_elec_b: 3,
      samples_per_state: 2048,
      max_dim: 64,
      krylov_extension_dim: 6,
      time_step: 0.26,
    });
  });

  it("uses an HF reference for guided QSE presets", () => {
    const qse = buildRecommendedAdvancedPatch("qse", "fastest", {
      n_electrons: 8,
      n_orbitals: 7,
    });

    expect(qse.field).toBe("advanced_qse");
    expect(qse.value).toMatchObject({
      reference_method: "hf",
      excitation_level: "singles",
      max_subspace_dim: 4,
      vqe_reference_ansatz_name: "NumberPreserving",
    });
  });

  it("keeps the non-QSE presets intact and uses HF across the QSE guided ladder", () => {
    const balancedVqe = buildRecommendedAdvancedPatch("vqe", "balanced", null);
    const vqe = buildRecommendedAdvancedPatch("vqe", "best_accuracy", null);
    const kqd = buildRecommendedAdvancedPatch("kqd", "fastest", null);
    const qfdFastest = buildRecommendedAdvancedPatch("qfd", "fastest", null);
    const qfd = buildRecommendedAdvancedPatch("qfd", "balanced", null);
    const qse = buildRecommendedAdvancedPatch("qse", "balanced", {
      n_electrons: 2,
      n_orbitals: 6,
    });

    expect(balancedVqe.value).toMatchObject({
      ansatz_name: "NumberPreserving",
      optimizer_name: "COBYLA",
      max_iterations: 448,
      max_function_evaluations: 448,
      reps: 2,
      initial_point_candidates: 2,
    });
    expect(vqe.value).toMatchObject({
      ansatz_name: "NumberPreserving",
      optimizer_name: "COBYLA",
      max_iterations: 512,
      max_function_evaluations: 512,
      reps: 2,
      initial_point_candidates: 4,
    });
    expect(kqd.value).toMatchObject({
      krylov_dim: 4,
      time_step: 0.35,
      evolution_method: "exact",
    });
    expect(qfdFastest.value).toMatchObject({
      num_time_points: 4,
      max_time: 0.5,
      time_grid_type: "linear",
    });
    expect(qfd.value).toMatchObject({
      num_time_points: 8,
      max_time: 2.5,
      time_grid_type: "linear",
    });
    expect(qse.value).toMatchObject({
      reference_method: "hf",
      excitation_level: "singles_doubles",
      max_subspace_dim: 8,
      vqe_reference_ansatz_name: "NumberPreserving",
      vqe_reference_optimizer_name: "COBYLA",
      vqe_reference_max_iterations: 256,
      vqe_reference_reps: 1,
    });
  });

  it("uses Trotter for KQD recommendations that require an estimator circuit", () => {
    const metadata: Pick<RunConfigMetadataResponse, "recommendations"> = {
      recommendations: {
        kqd: { fastest: { evolution_method: "exact" } },
      },
    };

    const patch = buildRecommendedAdvancedPatch("kqd", "fastest", null, metadata, true);

    expect(patch.value).toMatchObject({
      evolution_method: "trotter",
      trotter_steps: 1,
    });
    expect(kqdUsesKnownBranchEstimatorPath("ibm_runtime", false)).toBe(true);
    expect(kqdUsesKnownBranchEstimatorPath("aer_simulator", true)).toBe(true);
    expect(kqdUsesKnownBranchEstimatorPath("aer_simulator", false)).toBe(false);
    expect(kqdUsesKnownBranchEstimatorPath("statevector", true)).toBe(false);
  });
});
