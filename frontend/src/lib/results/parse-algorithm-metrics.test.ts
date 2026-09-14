import { describe, expect, it } from "vitest";

import {
  extractCircuitArtifacts,
  parseAlgorithmMetrics,
  parseKqdMetrics,
  parseQfdMetrics,
  parseQseMetrics,
  parseVqeMetrics,
} from "./parse-algorithm-metrics";

describe("parse-algorithm-metrics", () => {
  it("normalizes VQE metrics, matrices, and rich circuit artifacts", () => {
    const metrics = parseVqeMetrics({
      convergence_trace: [1, "bad", 2],
      optimizer_diagnostics: { ok: true },
      objective_evaluations: 18,
      optimizer_iterations: 12,
      effective_max_iterations: 24,
      max_function_evaluations: 60,
      bloch_vectors: [
        [1, 0, 0],
        [0, "bad", 1],
      ],
      density_matrix_real: [
        [1, 0],
        [0, "oops"],
      ],
      density_matrix_imag: [],
      circuit_artifacts: [
        {
          id: "artifact-1",
          role: "ansatz",
          representative: true,
          logical: {
            qasm: "OPENQASM 3;",
            diagram_svg: "<svg />",
            qubits: 2,
            classical_bits: 1,
            style: "light",
          },
          transpiled: {
            qasm: "transpiled",
            qubits: 2,
          },
          job_ids: ["job-1", "", 12],
          shots: 4096,
          transpilation_summary: { depth: 8 },
        },
      ],
      circuit_artifact_policy: { publish: "latest" },
    });

    expect(metrics).toMatchObject({
      convergence_trace: [1, 2],
      objective_evaluations: 18,
      optimizer_iterations: 12,
      effective_max_iterations: 24,
      max_function_evaluations: 60,
      bloch_vectors: [
        [1, 0, 0],
        [0, 0, 1],
      ],
      density_matrix_real: [
        [1, 0],
        [0, 0],
      ],
      density_matrix_imag: null,
      circuit_artifact_policy: { publish: "latest" },
    });
    expect(metrics.circuit_artifacts[0]).toMatchObject({
      id: "artifact-1",
      role: "ansatz",
      preview: expect.objectContaining({ qasm: "OPENQASM 3;" }),
      transpiled_preview: expect.objectContaining({ qasm: "transpiled" }),
      job_ids: ["job-1"],
      shots: 4096,
    });
  });

  it("falls back to legacy SQD and SKQD circuit previews when artifacts are absent", () => {
    const sqdArtifacts = extractCircuitArtifacts("sqd", {
      configuration_recovery_trace: [{ iteration: 3 }],
      sci_result_package: {
        circuit_preview: {
          qasm: "legacy-sqd",
        },
      },
    });
    const skqdArtifacts = extractCircuitArtifacts("skqd", {
      sqd_core: {
        sci_result_package: {
          circuit_preview: {
            qasm: "legacy-skqd",
          },
        },
      },
    });

    expect(sqdArtifacts[0]).toMatchObject({
      id: "sqd.legacy.latest",
      iteration: 3,
      preview: expect.objectContaining({ qasm: "legacy-sqd" }),
    });
    expect(skqdArtifacts[0]).toMatchObject({
      id: "skqd.legacy.seed",
      preview: expect.objectContaining({ qasm: "legacy-skqd" }),
    });
  });

  it("parses QFD, QSE, and unknown metrics with null-safe normalization", () => {
    expect(
      parseKqdMetrics({
        ritz_values: [1, "bad", 2],
        raw_ritz_values: [-99, 1, 2],
        krylov_rank: 4,
        orthogonality_metrics: { overlap_condition: 8 },
        stability_summary: { stability_state: "stabilized" },
        selected_level_index: 0,
      }),
    ).toEqual({
      ritz_values: [1, 2],
      raw_ritz_values: [-99, 1, 2],
      krylov_rank: 4,
      orthogonality_metrics: { overlap_condition: 8 },
      stability_summary: { stability_state: "stabilized" },
      selected_level_index: 0,
      circuit_artifacts: [],
      circuit_artifact_policy: null,
    });

    expect(
      parseQfdMetrics({
        filter_eigenvalues: [1, "bad", 2],
        raw_filter_eigenvalues: [-99, 1, 2],
        conditioning_summary: { cond: 5 },
        stability_summary: { stability_state: "stabilized" },
        selected_level_index: 0,
      }),
    ).toEqual({
      filter_eigenvalues: [1, 2],
      raw_filter_eigenvalues: [-99, 1, 2],
      conditioning_summary: { cond: 5 },
      stability_summary: { stability_state: "stabilized" },
      selected_level_index: 0,
    });

    expect(
      parseQseMetrics({
        eigenvalues: [1, "bad", 3],
        overlap_condition: 1e4,
        reference_state_energy: -1.23,
        residual_norm: "bad",
        relative_residual: 1e-8,
        convergence_threshold: null,
      }),
    ).toMatchObject({
      eigenvalues: [1, 3],
      overlap_condition: 1e4,
      reference_state_energy: -1.23,
      residual_norm: null,
      relative_residual: 1e-8,
      convergence_threshold: null,
    });

    expect(parseAlgorithmMetrics("mystery", { anything: 1 })).toEqual({
      type: "unknown",
      metrics: { anything: 1 },
    });
  });

  it("routes algorithm-specific parsing through parseAlgorithmMetrics", () => {
    expect(parseAlgorithmMetrics("kqd", { krylov_rank: 9 }).type).toBe("kqd");
    expect(parseAlgorithmMetrics("sqd", { sci_energies: [1] }).type).toBe("sqd");
    expect(parseAlgorithmMetrics("qfd", { filter_eigenvalues: [1] }).type).toBe("qfd");
    expect(parseAlgorithmMetrics("qse", { eigenvalues: [1] }).type).toBe("qse");
    expect(parseAlgorithmMetrics("skqd", { sqd_core: {} }).type).toBe("skqd");
    expect(parseAlgorithmMetrics("vqe", undefined).type).toBe("vqe");
  });
});
