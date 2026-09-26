import { describe, expect, it } from "vitest";

import type { VQEAdvancedConfig } from "@/types/run";
import {
  buildAdvancedBenchmarkRunConfig,
  buildSimpleBenchmarkRunConfig,
} from "./benchmark-run-config";

describe("benchmark-run-config", () => {
  it("builds simple benchmark rows with easy-mode payloads", () => {
    const config = buildSimpleBenchmarkRunConfig(
      "vqe",
      "sto-3g",
      {
        mode: "statevector",
        backendName: null,
      },
      "balanced",
    );

    expect(config.mode).toBe("easy");
    expect(config.easy_options).toEqual({ goal: "balanced" });
    expect(config.advanced_config).toBeUndefined();
    expect(config.backend_target).toBe("statevector");
  });

  it("builds advanced benchmark rows from the provided row config", () => {
    const advancedConfig: VQEAdvancedConfig = {
      algorithm: "vqe",
      ansatz_name: "EfficientSU2",
      optimizer_name: "COBYLA",
      max_iterations: 220,
      max_function_evaluations: 1800,
      reps: 2,
      initial_point_strategy: "zero_plus_seeded_random",
      initial_point_candidates: 2,
    };

    const config = buildAdvancedBenchmarkRunConfig(
      "vqe",
      "sto-3g",
      {
        mode: "ibm_runtime",
        backendName: "ibm_brisbane",
      },
      advancedConfig,
      { ibmRuntimeConfirmed: true },
    );

    expect(config.mode).toBe("advanced");
    expect(config.advanced_config).toEqual(advancedConfig);
    expect(config.backend_target).toBe("ibm_runtime");
    expect(config.backend_options?.backend_name).toBe("ibm_brisbane");
    expect(config.ibm_runtime_confirmed).toBe(true);
  });

  it("keeps backend-derived Aer noise on simple rows when requested", () => {
    const config = buildSimpleBenchmarkRunConfig(
      "qse",
      "sto-3g",
      {
        mode: "aer_simulator_backend_noise",
        backendName: "ibm_kyiv",
      },
      "balanced",
    );

    expect(config.backend_target).toBe("aer_simulator");
    expect(config.backend_options?.backend_name).toBe("ibm_kyiv");
    expect(config.noise_profile).toEqual({
      source: "backend_derived",
      reference_backend: "ibm_kyiv",
    });
  });

  it("sends IBM Runtime policy controls only to IBM Runtime", () => {
    const execution = {
      mode: "ibm_runtime" as const,
      backendName: "ibm_brisbane",
      dynamicalDecoupling: true,
      twirling: true,
    };

    const ibmConfig = buildSimpleBenchmarkRunConfig("vqe", "sto-3g", execution, "balanced");
    expect(ibmConfig.backend_options).toMatchObject({
      dynamical_decoupling: true,
      twirling: true,
    });

    const aerConfig = buildSimpleBenchmarkRunConfig(
      "vqe",
      "sto-3g",
      { ...execution, mode: "aer_simulator_backend_noise", backendName: "ibm_kyiv" },
      "balanced",
    );
    expect(aerConfig.backend_options).toMatchObject({
      dynamical_decoupling: false,
      twirling: false,
    });
  });
});
