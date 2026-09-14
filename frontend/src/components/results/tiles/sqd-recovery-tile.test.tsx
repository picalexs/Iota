import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { SqdRecoveryTile } from "./sqd-recovery-tile";

vi.mock("@/components/results/dashboard-tile", () => ({
  DashboardTile: ({
    title,
    children,
  }: {
    readonly title: string;
    readonly children: ReactNode;
  }) => (
    <section>
      <h2>{title}</h2>
      {children}
    </section>
  ),
}));

vi.mock("@/components/results/measurement-outcomes-panel", () => ({
  MeasurementOutcomesPanel: ({
    outcomes,
    artifacts,
  }: {
    readonly outcomes: Array<{ readonly bitstring: string; readonly probability: number }>;
    readonly artifacts?: Array<{
      readonly iteration?: number | null;
      readonly logical?: { readonly qasm?: string | null } | null;
    }>;
  }) => {
    const artifact = artifacts?.[0];
    let iterationLabel = "";
    if (artifact?.iteration != null) {
      iterationLabel = `|iter:${artifact.iteration}`;
    }
    let qasmLabel = "";
    if (artifact?.logical?.qasm) {
      qasmLabel = `|${artifact.logical.qasm}`;
    }

    return (
      <div data-testid="measurement-panel">
        {outcomes.map((entry) => `${entry.bitstring}:${entry.probability}`).join(",")}
        {iterationLabel}
        {qasmLabel}
      </div>
    );
  },
}));

vi.mock("@/components/results/charts/chart-empty-state", () => ({
  ChartEmptyState: ({ message }: { readonly message?: string }) => (
    <div data-testid="empty-state">{message}</div>
  ),
}));

describe("SqdRecoveryTile", () => {
  it("renders summary stats, outcomes, and the selected circuit artifact", () => {
    render(
      <SqdRecoveryTile
        metrics={{
          sci_energies: [],
          configuration_recovery_trace: [
            { iteration: 1, energy: -1.1 },
            {
              iteration: 2,
              energy: -1.2,
              postselection_weight: 0.42,
              accepted_samples: 128,
              sampled_configurations: 256,
              occupancy_delta: 0.015,
              delta_energy: -0.004,
              iter_wall_seconds: 3.4,
            },
          ],
          spin_diagnostics: null,
          postselection_summary: null,
          subsampling_summary: { samples_per_batch: 64, num_batches: 4 },
          sci_result_package: {
            final_bitstring_probabilities: [
              { bitstring: "1100", normalized_probability: 0.7, count: 70 },
              { bitstring: "0011", normalized_probability: 0.3, count: 30 },
            ],
          },
          circuit_artifacts: [
            { id: "iter-1", iteration: 1, logical: { qasm: "OPENQASM 3.0; // 1" } },
            {
              id: "iter-2",
              iteration: 2,
              representative: true,
              logical: { qasm: "OPENQASM 3.0; // 2" },
            },
          ],
          circuit_artifact_policy: null,
        }}
      />,
    );

    expect(screen.getByRole("heading", { name: "SQD Recovery" })).toBeInTheDocument();
    expect(screen.getByTestId("measurement-panel")).toHaveTextContent("1100:0.7,0011:0.3");
    expect(screen.getByTestId("measurement-panel")).toHaveTextContent("iter:2");
    expect(screen.getByTestId("measurement-panel")).toHaveTextContent("OPENQASM 3.0; // 2");
    expect(screen.getByText("42.0%")).toBeInTheDocument();
    expect(screen.getByText("128")).toBeInTheDocument();
    expect(screen.getByText("64 shots/batch · 4 batches")).toBeInTheDocument();
    expect(screen.getByText(/Selected recovery step|Final recovery step/)).toHaveTextContent(
      "iter 2",
    );
  });

  it("falls back when no recovery artifacts exist", () => {
    render(
      <SqdRecoveryTile
        metrics={{
          sci_energies: [],
          configuration_recovery_trace: [],
          spin_diagnostics: null,
          postselection_summary: null,
          subsampling_summary: null,
          sci_result_package: null,
          circuit_artifacts: [],
          circuit_artifact_policy: null,
        }}
      />,
    );

    expect(screen.getByTestId("empty-state")).toHaveTextContent(
      "No SQD recovery artifacts recorded",
    );
  });
});
