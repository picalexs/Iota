import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { SkqdSpectrumTile } from "./skqd-spectrum-tile";

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

describe("SkqdSpectrumTile", () => {
  it("renders the SKQD Ritz spectrum and workflow rail", () => {
    render(
      <SkqdSpectrumTile
        metrics={{
          sqd_core: null,
          krylov_extension_diagnostics: {
            ritz_values: [-1.13, -0.72, -0.61],
            basis_rank: 4,
            relative_ritz_residual: 2.9e-16,
            seed_source: "sqd_bitstring_probabilities",
          },
          circuit_artifacts: [],
          circuit_artifact_policy: null,
        }}
      />,
    );

    expect(screen.getByRole("heading", { name: "SKQD Spectrum" })).toBeInTheDocument();
    expect(screen.getByTestId("spectrum-ladder")).toHaveTextContent("-1.13,-0.72,-0.61");
    expect(screen.getByText("sqd bitstring probabilities")).toBeInTheDocument();
    expect(screen.getByText("Krylov basis")).toBeInTheDocument();
    expect(screen.getByText("Rank 4")).toBeInTheDocument();
    expect(screen.getByText("Ritz spectrum")).toBeInTheDocument();
    expect(screen.getByText("3 levels")).toBeInTheDocument();
    expect(screen.getByText("Residual: 2.90e-16")).toBeInTheDocument();
  });

  it("renders the empty state when Ritz values are missing", () => {
    render(
      <SkqdSpectrumTile
        metrics={{
          sqd_core: null,
          krylov_extension_diagnostics: null,
          circuit_artifacts: [],
          circuit_artifact_policy: null,
        }}
      />,
    );

    expect(screen.getByTestId("empty-state")).toHaveTextContent("No Krylov Ritz values recorded");
    expect(screen.getByText("Ritz levels: 0")).toBeInTheDocument();
  });
});
