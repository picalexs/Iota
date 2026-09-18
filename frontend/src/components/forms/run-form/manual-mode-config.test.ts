import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  buildRecommendedManualSettings,
  getRunFormConfigMetadata,
  loadRunFormConfigMetadata,
  parseNumberArrayInput,
  parseParameterBoundsInput,
  parseProvidedSectorRowsInput,
  parseProvidedStateVectorInput,
  parseRecordInput,
  recommendedSettingsSummary,
} from "./manual-mode-config";

vi.mock("@/api/runs", () => ({
  fetchRunConfigMetadata: vi.fn(),
}));

import { fetchRunConfigMetadata } from "@/api/runs";

describe("manual-mode-config helpers", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("parses provided state vectors and sector amplitudes with validation errors", () => {
    expect(parseProvidedStateVectorInput("")).toEqual({
      values: null,
      error: "Provide a state vector for the QSE reference",
    });
    expect(parseProvidedStateVectorInput("{")).toEqual({
      values: null,
      error: "Enter valid JSON",
    });
    expect(parseProvidedStateVectorInput("{}")).toEqual({
      values: null,
      error: "State vector JSON must be an array",
    });
    expect(parseProvidedStateVectorInput('[1, {"real": 0, "imag": 2}, [3, 4]]')).toEqual({
      values: [1, { real: 0, imag: 2 }, { real: 3, imag: 4 }],
    });
    expect(parseProvidedStateVectorInput('[1, "bad"]')).toEqual({
      values: null,
      error: "State vector entries must be numbers or { real, imag } objects",
    });

    expect(parseProvidedSectorRowsInput([{ bitstring: "", real: "", imag: "" }])).toEqual({
      values: null,
      error: "Provide at least one determinant amplitude",
    });
    expect(parseProvidedSectorRowsInput([{ bitstring: "10a", real: "1", imag: "" }])).toEqual({
      values: null,
      error: "Bitstrings must contain only 0 and 1",
    });
    expect(parseProvidedSectorRowsInput([{ bitstring: "10", real: "abc", imag: "" }])).toEqual({
      values: null,
      error: "Determinant amplitudes must be numeric",
    });
    expect(parseProvidedSectorRowsInput([{ bitstring: "10", real: "1.5", imag: "0.25" }])).toEqual({
      values: [{ bitstring: "10", amplitude: { real: 1.5, imag: 0.25 } }],
    });
  });

  it("parses records, numeric arrays, and parameter bounds", () => {
    expect(parseRecordInput("", "Optimizer options")).toEqual({ values: null });
    expect(parseRecordInput("{", "Optimizer options")).toEqual({
      values: null,
      error: "Optimizer options must be valid JSON",
    });
    expect(parseRecordInput("[]", "Optimizer options")).toEqual({
      values: null,
      error: "Optimizer options must be a JSON object",
    });
    expect(parseRecordInput('{"gtol": 1e-8}', "Optimizer options")).toEqual({
      values: { gtol: 1e-8 },
    });

    expect(parseNumberArrayInput("", "Initial parameters")).toEqual({ values: null });
    expect(parseNumberArrayInput("{", "Initial parameters")).toEqual({
      values: null,
      error: "Initial parameters must be valid JSON",
    });
    expect(parseNumberArrayInput('[1, "x"]', "Initial parameters")).toEqual({
      values: null,
      error: "Initial parameters must be a JSON array of numbers",
    });
    expect(parseNumberArrayInput("[1, 2, 3]", "Initial parameters")).toEqual({
      values: [1, 2, 3],
    });

    expect(parseParameterBoundsInput("")).toEqual({ values: null });
    expect(parseParameterBoundsInput("{")).toEqual({
      values: null,
      error: "Parameter bounds must be valid JSON",
    });
    expect(parseParameterBoundsInput("[[0, 1], [2]]")).toEqual({
      values: null,
      error: "Parameter bounds must be a JSON array of [min, max] numeric pairs",
    });
    expect(parseParameterBoundsInput("[[0, 1], [2, 3]]")).toEqual({
      values: [
        [0, 1],
        [2, 3],
      ],
    });
  });

  it("loads config metadata from the API and falls back to local defaults on failure", async () => {
    vi.mocked(fetchRunConfigMetadata).mockResolvedValueOnce({
      catalog_version: "2026-09-16-v22",
      algorithms: ["vqe", "qse", "kqd", "qfd", "sqd", "skqd"],
      backend_targets: ["statevector", "aer_simulator", "ibm_runtime"],
      easy_goals: ["fastest", "balanced", "best_accuracy"],
      easy_goal_presets: [
        { goal: "fastest", label: "5.0 mHa", chemical_accuracy_target_ha: 5e-3 },
        { goal: "balanced", label: "1.6 mHa", chemical_accuracy_target_ha: 1.6e-3 },
        { goal: "best_accuracy", label: "0.5 mHa", chemical_accuracy_target_ha: 5e-4 },
      ],
      ansatzes: [
        {
          id: "CustomAnsatz",
          label: "CustomAnsatz",
          aliases: [],
          description: "",
          supported_algorithms: ["vqe"],
          metadata: {},
        },
      ],
      optimizers: [
        {
          id: "CustomOpt",
          label: "CustomOpt",
          aliases: [],
          description: "",
          supported_algorithms: ["vqe"],
          metadata: {},
        },
      ],
      defaults: {
        ansatz_name: "CustomAnsatz",
        optimizer_name: "CustomOpt",
        qse_reference_ansatz_name: "CustomAnsatz",
        qse_reference_optimizer_name: "CustomOpt",
      },
      limits: {},
      capabilities: {},
    });

    const loaded = await loadRunFormConfigMetadata();
    expect(loaded.defaults.ansatz_name).toBe("CustomAnsatz");
    expect(getRunFormConfigMetadata()?.defaults.optimizer_name).toBe("CustomOpt");

    vi.resetModules();
    vi.mocked(fetchRunConfigMetadata).mockRejectedValueOnce(new Error("offline"));
    const freshManualMode = await import("./manual-mode-config");
    const fallback = await freshManualMode.loadRunFormConfigMetadata();
    expect(fallback.ansatzes.length).toBeGreaterThan(0);
    expect(fallback.defaults.ansatz_name).toBe("NumberPreserving");
    expect(fallback.defaults.qse_reference_ansatz_name).toBe("NumberPreserving");
    expect(fallback.ansatzes.find((entry) => entry.id === "NumberPreserving")).toMatchObject({
      metadata: {
        canonical_worker_id: "numberpreserving",
        default_reps: 2,
      },
    });
    expect(fallback.optimizers.find((entry) => entry.id === "L_BFGS_B")).toBeDefined();
  });

  it("builds recommendation summaries and algorithm-specific manual patches", () => {
    expect(recommendedSettingsSummary(5e-3)).toContain("quick-scan preset family");
    expect(recommendedSettingsSummary(5e-4)).toContain("high-accuracy preset family");
    expect(recommendedSettingsSummary(undefined)).toContain("balanced preset family");

    expect(buildRecommendedManualSettings(null, 1.6e-3, null)).toBeNull();
    expect(
      buildRecommendedManualSettings("vqe", 5e-4, {
        id: "m1",
        name: "H2",
        atoms: [],
        charge: 0,
        multiplicity: 1,
        active_space: { n_electrons: 2, n_orbitals: 2 },
        basis_set: "sto-3g",
        created_at: "",
        updated_at: "",
      }),
    ).toMatchObject({
      advanced_vqe: expect.objectContaining({
        ansatz_name: "NumberPreserving",
        optimizer_name: "COBYLA",
      }),
    });
  });
});
