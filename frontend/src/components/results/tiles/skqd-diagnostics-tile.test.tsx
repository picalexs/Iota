import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { SkqdDiagnosticsTile } from "./skqd-diagnostics-tile";

vi.mock("@/components/results/dashboard-tile", () => ({
  DashboardTile: ({ title, children }: { title: string; children: ReactNode }) => (
    <section>
      <h2>{title}</h2>
      {children}
    </section>
  ),
}));

vi.mock("@/components/results/measurement-outcomes-panel", () => ({
  MeasurementOutcomesPanel: ({
    outcomes,
  }: {
    outcomes: Array<{ bitstring: string; probability: number }>;
  }) => (
    <div data-testid="measurement-panel">
      {outcomes.map((entry) => `${entry.bitstring}:${entry.probability}`).join(",")}
    </div>
  ),
}));

describe("SkqdDiagnosticsTile", () => {
  it("renders Krylov diagnostics and outcomes without embedding the SQD circuit preview", () => {
    render(
      <SkqdDiagnosticsTile
        metrics={{
          sqd_core: null,
          krylov_extension_diagnostics: {
            ritz_values: [0.5, 0.7],
            basis_rank: 4,
            relative_ritz_residual: 1e-6,
            residual_tolerance: 1e-5,
            krylov_state_bitstring_distribution: [{ bitstring: "1010", probability: 0.75 }],
            overall_converged: true,
          },
          circuit_artifacts: [
            {
              id: "skqd.seed",
              role: "sqd_seed",
              representative: true,
              logical: { qasm: "OPENQASM 3.0;" },
            },
          ],
          circuit_artifact_policy: null,
        }}
      />,
    );

    expect(screen.getByRole("heading", { name: "SKQD Diagnostics" })).toBeInTheDocument();
    expect(screen.getByText("Basis rank")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
    expect(screen.getByText("1.00e-6")).toBeInTheDocument();
    expect(screen.getByText("yes")).toBeInTheDocument();
    expect(screen.getByTestId("measurement-panel")).toHaveTextContent("1010:0.75");
    expect(screen.getByText(/Krylov rank: 4/)).toBeInTheDocument();
  });

  it("falls back cleanly when diagnostics are missing", () => {
    render(
      <SkqdDiagnosticsTile
        metrics={{
          sqd_core: null,
          krylov_extension_diagnostics: null,
          circuit_artifacts: [],
          circuit_artifact_policy: null,
        }}
      />,
    );

    expect(screen.getAllByText("-").length).toBeGreaterThan(0);
    expect(screen.queryByTestId("measurement-panel")).not.toBeInTheDocument();
    expect(screen.getByText(/Krylov rank: 0/)).toBeInTheDocument();
  });
});
