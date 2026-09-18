import { describe, expect, it } from "vitest";

import type { BenchmarkAlgorithmVariant } from "./benchmark-variants";
import {
  buildBenchmarkVariantFormValues,
  buildBenchmarkVariantFromFormValues,
  createAdvancedBenchmarkVariant,
  duplicateBenchmarkVariant,
  kqdRequiresBranchEstimatorForBackendMode,
  normalizeBenchmarkVariantLabels,
} from "./benchmark-variants";

function buildVariant(overrides: Partial<BenchmarkAlgorithmVariant>): BenchmarkAlgorithmVariant {
  return {
    id: overrides.id ?? crypto.randomUUID(),
    algorithm: overrides.algorithm ?? "vqe",
    mode: overrides.mode ?? "advanced",
    label: overrides.label ?? "TwoLocal / L_BFGS_B",
    easyGoal: overrides.easyGoal ?? null,
    advancedConfig: overrides.advancedConfig ?? {
      algorithm: "vqe",
      ansatz_name: "TwoLocal",
      optimizer_name: "L_BFGS_B",
      max_iterations: 180,
      max_function_evaluations: 360,
      reps: 2,
      initial_point_strategy: "zero_plus_seeded_random",
      initial_point_candidates: 3,
      optimizer_options: { ftol: 1e-9, gtol: 1e-7, maxls: 20 },
    },
  };
}

describe("benchmark-variants", () => {
  it("recommends Trotter for KQD variants on IBM and noisy Aer paths only", () => {
    const local = createAdvancedBenchmarkVariant("kqd", 0.0016);
    const idealAer = createAdvancedBenchmarkVariant(
      "kqd",
      0.0016,
      null,
      kqdRequiresBranchEstimatorForBackendMode("aer_simulator"),
    );
    const ibm = createAdvancedBenchmarkVariant(
      "kqd",
      0.0016,
      null,
      kqdRequiresBranchEstimatorForBackendMode("ibm_runtime"),
    );
    const noisyAer = createAdvancedBenchmarkVariant(
      "kqd",
      0.0016,
      null,
      kqdRequiresBranchEstimatorForBackendMode("aer_simulator_backend_noise"),
    );
    const vqe = createAdvancedBenchmarkVariant("vqe", 0.0016, null, true);

    expect(local.advancedConfig).toMatchObject({ algorithm: "kqd", evolution_method: "exact" });
    expect(idealAer.advancedConfig).toMatchObject({ algorithm: "kqd", evolution_method: "exact" });
    expect(ibm.advancedConfig).toMatchObject({ algorithm: "kqd", evolution_method: "trotter" });
    expect(noisyAer.advancedConfig).toMatchObject({
      algorithm: "kqd",
      evolution_method: "trotter",
    });
    expect(vqe.advancedConfig).toMatchObject({ algorithm: "vqe" });
    expect(kqdRequiresBranchEstimatorForBackendMode("aer_simulator")).toBe(false);
    expect(kqdRequiresBranchEstimatorForBackendMode("statevector")).toBe(false);

    const explicitExactValues = buildBenchmarkVariantFormValues(ibm);
    explicitExactValues.advanced_kqd.evolution_method = "exact";
    const explicitlyEdited = buildBenchmarkVariantFromFormValues(ibm, explicitExactValues);
    expect(explicitlyEdited.advancedConfig).toMatchObject({
      algorithm: "kqd",
      evolution_method: "exact",
    });
  });

  it("normalizes generated and legacy copy labels to config-based row labels", () => {
    const variants = [
      buildVariant({
        id: "row-1",
        label: "EfficientSU2 / SPSA",
        advancedConfig: {
          algorithm: "vqe",
          ansatz_name: "EfficientSU2",
          optimizer_name: "SPSA",
          max_iterations: 600,
          max_function_evaluations: 6000,
          reps: 2,
          initial_point_strategy: "zero_plus_seeded_random",
          initial_point_candidates: 5,
        },
      }),
      buildVariant({
        id: "row-2",
        label: "EfficientSU2 / SPSA copy",
        advancedConfig: {
          algorithm: "vqe",
          ansatz_name: "EfficientSU2",
          optimizer_name: "SPSA",
          max_iterations: 600,
          max_function_evaluations: 6000,
          reps: 2,
          initial_point_strategy: "zero_plus_seeded_random",
          initial_point_candidates: 5,
        },
      }),
      buildVariant({ id: "row-3", label: "COBYLA baseline" }),
      buildVariant({
        id: "row-4",
        mode: "simple",
        label: "Balanced",
        easyGoal: "balanced",
        advancedConfig: null,
      }),
      buildVariant({
        id: "row-5",
        mode: "simple",
        label: "Balanced copy",
        easyGoal: "balanced",
        advancedConfig: null,
      }),
    ];

    expect(normalizeBenchmarkVariantLabels(variants)).toMatchObject([
      { id: "row-1", label: "EfficientSU2 / SPSA" },
      { id: "row-2", label: "EfficientSU2 / SPSA 2" },
      { id: "row-3", label: "COBYLA baseline" },
      { id: "row-4", label: "Balanced" },
      { id: "row-5", label: "Balanced 2" },
    ]);
  });

  it("uses algorithm-specific generated labels for non-vqe advanced rows", () => {
    const variants = [
      buildVariant({
        id: "sqd-1",
        algorithm: "sqd",
        label: "1",
        advancedConfig: {
          algorithm: "sqd",
          samples_per_batch: 256,
          num_batches: 6,
          max_iterations: 100,
          seed: 42,
        },
      }),
      buildVariant({
        id: "qfd-1",
        algorithm: "qfd",
        label: "2",
        advancedConfig: {
          algorithm: "qfd",
          num_time_points: 8,
          max_time: 1.5,
          time_grid_type: "geometric",
          trotter_steps: 4,
        },
      }),
    ];

    expect(normalizeBenchmarkVariantLabels(variants)).toMatchObject([
      { id: "sqd-1", label: "256 x 6" },
      { id: "qfd-1", label: "8 points" },
    ]);
  });

  it("duplicates advanced rows without introducing copy suffixes", () => {
    const duplicated = duplicateBenchmarkVariant(
      buildVariant({
        id: "source-row",
        label: "1",
        advancedConfig: {
          algorithm: "vqe",
          ansatz_name: "RealAmplitudes",
          optimizer_name: "SPSA",
          max_iterations: 180,
          max_function_evaluations: 900,
          reps: 1,
          initial_point_strategy: "zero_plus_seeded_random",
          initial_point_candidates: 2,
        },
      }),
    );

    expect(duplicated.id).not.toBe("source-row");
    expect(duplicated.label).toBe("1");
    expect(duplicated.advancedConfig).toEqual({
      algorithm: "vqe",
      ansatz_name: "RealAmplitudes",
      optimizer_name: "SPSA",
      max_iterations: 180,
      max_function_evaluations: 900,
      reps: 1,
      initial_point_strategy: "zero_plus_seeded_random",
      initial_point_candidates: 2,
    });
  });
});
