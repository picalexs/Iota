import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { KqdRitzTile } from "./kqd-ritz-tile";

vi.mock("@/components/results/dashboard-tile", () => ({
  DashboardTile: ({ title, children }: { title: string; children: ReactNode }) => (
    <section>
      <h2>{title}</h2>
      {children}
    </section>
  ),
}));

vi.mock("@/components/results/charts/spectrum-ladder", () => ({
  SpectrumLadder: ({ energies }: { energies: number[] }) => (
    <div data-testid="spectrum-ladder">{energies.join(",")}</div>
  ),
}));

vi.mock("@/components/results/charts/chart-empty-state", () => ({
  ChartEmptyState: ({ message }: { message?: string }) => (
    <div data-testid="empty-state">{message}</div>
  ),
}));

describe("KqdRitzTile", () => {
  it("renders the spectrum and workflow rail when Ritz values are present", () => {
    render(
      <KqdRitzTile
        metrics={{
          ritz_values: [1.2, 3.4],
          raw_ritz_values: [1.2, 3.4],
          krylov_rank: 4,
          orthogonality_metrics: {
            overlap_condition: 2.1,
            relative_ritz_residual: 1e-8,
          },
          stability_summary: null,
          selected_level_index: 0,
          circuit_artifacts: [],
          circuit_artifact_policy: null,
        }}
      />,
    );

    expect(screen.getByRole("heading", { name: "KQD Ritz Values" })).toBeInTheDocument();
    expect(screen.getByTestId("spectrum-ladder")).toHaveTextContent("1.2,3.4");
    expect(screen.getByText("HF state")).toBeInTheDocument();
    expect(screen.getByText("Time propagation")).toBeInTheDocument();
    expect(screen.getByText("Projected Ritz solve")).toBeInTheDocument();
    expect(screen.getByText("Rank 4")).toBeInTheDocument();
    expect(screen.getByText("Krylov rank: 4")).toBeInTheDocument();
  });

  it("renders the empty state when Ritz values are missing", () => {
    render(
      <KqdRitzTile
        metrics={{
          ritz_values: [],
          raw_ritz_values: [],
          krylov_rank: 0,
          orthogonality_metrics: null,
          stability_summary: null,
          selected_level_index: null,
          circuit_artifacts: [],
          circuit_artifact_policy: null,
        }}
      />,
    );

    expect(screen.getByTestId("empty-state")).toHaveTextContent("No Ritz values recorded");
  });

  it("keeps the workflow rail visible when KQD circuit artifacts also exist", () => {
    render(
      <KqdRitzTile
        metrics={{
          ritz_values: [-1.2, -1],
          raw_ritz_values: [-1.2, -1],
          krylov_rank: 3,
          orthogonality_metrics: {
            overlap_condition: 3.5,
            relative_ritz_residual: 1e-7,
          },
          stability_summary: null,
          selected_level_index: 0,
          circuit_artifacts: [
            {
              id: "kqd.evolution",
              role: "evolution",
              representative: true,
              logical: { qasm: "OPENQASM 3.0; // kqd evolution" },
            },
          ],
          circuit_artifact_policy: null,
        }}
      />,
    );

    expect(screen.queryByText("Associated circuit")).not.toBeInTheDocument();
    expect(screen.queryByTestId("measurement-panel")).not.toBeInTheDocument();
    expect(screen.getByText("Krylov rank: 3")).toBeInTheDocument();
  });

  it("shows a stabilization note when raw Ritz levels were dropped", () => {
    render(
      <KqdRitzTile
        metrics={{
          ritz_values: [-1.2, -1],
          raw_ritz_values: [-99, -1.2, -1],
          krylov_rank: 3,
          orthogonality_metrics: null,
          stability_summary: {
            stability_state: "stabilized",
            dropped_rank: 1,
          },
          selected_level_index: 0,
          circuit_artifacts: [],
          circuit_artifact_policy: null,
        }}
      />,
    );

    expect(
      screen.getByText("Raw unstable levels hidden after overlap stabilization."),
    ).toBeInTheDocument();
  });
});
