import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { formatConfigRows } from "./run-config-display";
import type { RunResponse } from "@/types/run";

const run: RunResponse = {
  id: "run-1",
  molecule_id: "mol-1",
  status: "COMPLETED",
  algorithm: "vqe",
  mode: "advanced",
  backend_target: "statevector",
  config_json: {
    algorithm: "vqe",
    mode: "advanced",
    chemical_accuracy_target_ha: 0.002,
    advanced_config: {
      algorithm: "vqe",
      ansatz_name: "EfficientSU2",
      optimizer_name: "COBYLA",
      max_iterations: 100,
    },
  },
  basis_set: "sto-3g",
  ibm_job_id: null,
  client_request_id: null,
  versions: null,
  metadata: null,
  created_at: "2025-06-01T10:00:00Z",
  updated_at: "2025-06-01T10:05:00Z",
};

describe("formatConfigRows", () => {
  it("includes the per-run chemical accuracy target in the options group", () => {
    const rows = formatConfigRows(run);
    const targetRow = rows.find((row) => row.label === "Chemical accuracy target");

    expect(targetRow?.group).toBe("Options");

    render(<div>{targetRow?.value}</div>);
    expect(screen.getByText("0.002000 Ha")).toBeInTheDocument();
  });

  it("formats backend, noise, easy-mode, and SKQD base sampling rows", () => {
    const rows = formatConfigRows({
      ...run,
      algorithm: "skqd",
      mode: "easy",
      backend_target: "ibm_runtime",
      config_json: {
        algorithm: "skqd",
        mode: "easy",
        backend_target: "ibm_runtime",
        basis_set: "6-31g",
        basis_set_override: "sto-3g",
        backend_options: {
          selection_policy: "manual",
          backend_name: "ibm_brisbane",
          shots: 4096,
          optimization_level: 1,
          seed_simulator: null,
          seed_transpiler: null,
          aer_method: "automatic",
        },
        noise_profile: {
          source: "backend_derived",
          reference_backend: "ibm_kyiv",
        },
        easy_options: {
          goal: "balanced",
        },
        advanced_config: {
          algorithm: "skqd",
          samples_per_state: 1024,
          krylov_extension_dim: 8,
          residual_tolerance: 1e-6,
          base_sampling_options: {
            max_dim: 32,
            spin_sq_target: 0,
          },
        },
      },
    });

    expect(rows).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ group: "Backend", label: "Backend name" }),
        expect.objectContaining({ group: "Backend", label: "Noise source" }),
        expect.objectContaining({ group: "Options", label: "Goal" }),
        expect.objectContaining({
          group: "Options",
          label: "SKQD sampling: Spin Sq Target",
        }),
      ]),
    );

    const backendNameRow = rows.find((row) => row.label === "Backend name");
    const goalRow = rows.find((row) => row.label === "Goal");
    const baseSamplingRow = rows.find((row) => row.label === "SKQD sampling: Max Dim");
    render(
      <div>
        {backendNameRow?.value}
        {goalRow?.value}
        {baseSamplingRow?.value}
      </div>,
    );

    expect(screen.getByText("ibm_brisbane")).toBeInTheDocument();
    expect(screen.getByText("Balanced")).toBeInTheDocument();
    expect(screen.getByText("32")).toBeInTheDocument();
  });

  it("falls back gracefully for unknown and missing values", () => {
    const rows = formatConfigRows({
      ...run,
      config_json: {
        algorithm: "custom_method",
        mode: "advanced",
        backend_target: "aer_simulator",
        advanced_config: {
          algorithm: "custom_method",
          strange_blob: { nested: true },
          enabled: false,
        },
      } as unknown as RunResponse["config_json"],
    });

    const algorithmRow = rows.find((row) => row.label === "Algorithm");
    const strangeBlobRow = rows.find((row) => row.label === "Advanced config: Strange Blob");
    const chemicalTargetRow = rows.find((row) => row.label === "Chemical accuracy target");

    expect(chemicalTargetRow).toBeUndefined();
    render(
      <div>
        {algorithmRow?.value}
        {strangeBlobRow?.value}
      </div>,
    );

    expect(screen.getByText("CUSTOM_METHOD")).toBeInTheDocument();
    expect(screen.getByText('{"nested":true}')).toBeInTheDocument();
  });
});
