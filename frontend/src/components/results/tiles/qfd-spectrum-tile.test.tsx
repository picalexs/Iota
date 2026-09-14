import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { QfdSpectrumTile } from "./qfd-spectrum-tile";

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
  ChartEmptyState: ({
    message,
    pending,
    pendingMessage,
  }: {
    message?: string;
    pending?: boolean;
    pendingMessage?: string;
  }) => (
    <div data-pending={pending ? "true" : "false"} data-testid="empty-state">
      {pending ? pendingMessage : message}
    </div>
  ),
}));

describe("QfdSpectrumTile", () => {
  it("renders the spectrum and workflow rail", () => {
    render(
      <QfdSpectrumTile
        metrics={{
          filter_eigenvalues: [0.5, 0.7],
          raw_filter_eigenvalues: [0.5, 0.7],
          conditioning_summary: {
            max_time: 2.5,
            overlap_condition: 4.2,
            relative_ritz_residual: 2e-7,
          },
          stability_summary: null,
          selected_level_index: 0,
        }}
      />,
    );

    expect(screen.getByRole("heading", { name: "QFD Spectrum" })).toBeInTheDocument();
    expect(screen.getByTestId("spectrum-ladder")).toHaveTextContent("0.5,0.7");
    expect(screen.getByText("HF state")).toBeInTheDocument();
    expect(screen.getByText("Time grid")).toBeInTheDocument();
    expect(screen.getByText("2 points")).toBeInTheDocument();
    expect(screen.getByText("Filtered subspace")).toBeInTheDocument();
    expect(screen.getByText("Tmax 2.500")).toBeInTheDocument();
  });

  it("marks missing spectrum data as pending while the run is active", () => {
    render(
      <QfdSpectrumTile
        metrics={{
          filter_eigenvalues: [],
          raw_filter_eigenvalues: [],
          conditioning_summary: null,
          stability_summary: null,
          selected_level_index: null,
        }}
        isRunning
      />,
    );

    expect(screen.getByTestId("empty-state")).toHaveAttribute("data-pending", "true");
    expect(screen.getByTestId("empty-state")).toHaveTextContent("Awaiting filter eigenvalues");
  });

  it("shows a stabilization note when raw filter levels were dropped", () => {
    render(
      <QfdSpectrumTile
        metrics={{
          filter_eigenvalues: [0.5, 0.7],
          raw_filter_eigenvalues: [-999, 0.5, 0.7],
          conditioning_summary: null,
          stability_summary: {
            stability_state: "stabilized",
            dropped_rank: 1,
          },
          selected_level_index: 0,
        }}
      />,
    );

    expect(
      screen.getByText("Raw unstable levels hidden after overlap stabilization."),
    ).toBeInTheDocument();
  });
});
