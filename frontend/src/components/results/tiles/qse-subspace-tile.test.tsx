import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { QseSubspaceTile } from "./qse-subspace-tile";

vi.mock("@/components/results/dashboard-tile", () => ({
  DashboardTile: ({ title, children }: { title: string; children: ReactNode }) => (
    <section>
      <h2>{title}</h2>
      {children}
    </section>
  ),
}));

vi.mock("@/components/results/charts/spectrum-ladder", () => ({
  SpectrumLadder: ({
    energies,
    highlightedIndex,
  }: {
    energies: number[];
    highlightedIndex?: number;
  }) => (
    <div data-testid="spectrum-ladder" data-highlighted-index={highlightedIndex ?? -1}>
      {energies.join(",")}
    </div>
  ),
}));

vi.mock("@/components/results/charts/chart-empty-state", () => ({
  ChartEmptyState: ({ message }: { message?: string }) => (
    <div data-testid="empty-state">{message}</div>
  ),
}));

describe("QseSubspaceTile", () => {
  it("renders the QSE eigenspectrum", () => {
    render(
      <QseSubspaceTile
        metrics={{
          eigenvalues: [-1.1, -1],
          overlap_condition: 12,
          reference_state_energy: -1.05,
          residual_norm: 1e-7,
          relative_residual: 1e-8,
          convergence_threshold: 1e-8,
          circuit_artifacts: [],
          circuit_artifact_policy: null,
        }}
      />,
    );

    expect(screen.getByRole("heading", { name: "QSE Subspace" })).toBeInTheDocument();
    expect(screen.getByTestId("spectrum-ladder")).toHaveTextContent("-1.1,-1");
    expect(screen.getByTestId("spectrum-ladder")).toHaveAttribute("data-highlighted-index", "0");
    expect(screen.getByText("Subspace dim: 2")).toBeInTheDocument();
  });

  it("keeps the eigenspectrum focused even when circuit artifacts exist", () => {
    render(
      <QseSubspaceTile
        metrics={{
          eigenvalues: [-1.1, -1],
          overlap_condition: 12,
          reference_state_energy: -1.05,
          residual_norm: 1e-7,
          relative_residual: 1e-8,
          convergence_threshold: 1e-8,
          circuit_artifacts: [
            {
              id: "qse.reference.final",
              role: "reference",
              representative: true,
              logical: { qasm: "OPENQASM 3.0; // reference" },
            },
          ],
          circuit_artifact_policy: null,
        }}
      />,
    );

    expect(screen.queryByText("Reference circuit")).not.toBeInTheDocument();
    expect(screen.queryByTestId("measurement-panel")).not.toBeInTheDocument();
    expect(screen.getByText("Ref energy: -1.050000 Ha")).toBeInTheDocument();
  });
});
