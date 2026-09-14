import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { SqdOccupancyTile } from "./sqd-occupancy-tile";

vi.mock("@/components/results/dashboard-tile", () => ({
  DashboardTile: ({ title, children }: { title: string; children: ReactNode }) => (
    <section>
      <h2>{title}</h2>
      {children}
    </section>
  ),
}));

vi.mock("@/components/results/charts/bar-plot", () => ({
  BarPlot: ({
    data,
    yLabel,
    avoidValueLabelOverlap,
  }: {
    data: Array<{ label: string; value: number | null }>;
    yLabel?: string;
    avoidValueLabelOverlap?: boolean;
  }) => (
    <div aria-label={`${yLabel ?? "Value"} bar chart`} data-testid="bar-plot">
      <span>avoid overlap {String(avoidValueLabelOverlap)}</span>
      {data.map((item) => (
        <span key={item.label}>
          {item.label}:{item.value}
        </span>
      ))}
    </div>
  ),
}));

vi.mock("@/components/results/charts/chart-empty-state", () => ({
  ChartEmptyState: ({ message }: { message?: string }) => <div>{message}</div>,
}));

describe("SqdOccupancyTile", () => {
  it("prefers best-iteration occupancies from the SQD result package", () => {
    render(
      <SqdOccupancyTile
        metrics={{
          sci_energies: [-1.2, -1.25],
          configuration_recovery_trace: [],
          spin_diagnostics: null,
          postselection_summary: null,
          subsampling_summary: null,
          sci_result_package: {
            best_occupancies: [0.9, 0.1, 0.2, 0.8],
            final_occupancies: [0.98, 0.02, 0.01, 0.99],
          },
          circuit_artifacts: [],
          circuit_artifact_policy: null,
        }}
      />,
    );

    expect(screen.getByText("α0:0.9")).toBeInTheDocument();
    expect(screen.getByText("β1:0.8")).toBeInTheDocument();
    expect(screen.queryByText("α0:0.98")).not.toBeInTheDocument();
  });

  it("renders occupancies from the SQD result package", () => {
    render(
      <SqdOccupancyTile
        metrics={{
          sci_energies: [-1.2, -1.25],
          configuration_recovery_trace: [],
          spin_diagnostics: null,
          postselection_summary: null,
          subsampling_summary: null,
          sci_result_package: {
            final_occupancies: [0.98, 0.02, 0.01, 0.99],
          },
          circuit_artifacts: [],
          circuit_artifact_policy: null,
        }}
      />,
    );

    expect(screen.getByRole("heading", { name: "Orbital Occupancies" })).toBeInTheDocument();
    expect(screen.getByTestId("bar-plot")).toBeInTheDocument();
    expect(screen.getByText("α0:0.98")).toBeInTheDocument();
    expect(screen.getByText("α1:0.02")).toBeInTheDocument();
    expect(screen.getByText("β0:0.01")).toBeInTheDocument();
    expect(screen.getByText("β1:0.99")).toBeInTheDocument();
    expect(screen.getByText("avoid overlap true")).toBeInTheDocument();
    expect(screen.queryByText("No occupancy data available")).not.toBeInTheDocument();
  });

  it("falls back to the empty state when no occupancy data is present", () => {
    render(
      <SqdOccupancyTile
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

    expect(screen.getByText("No occupancy data available")).toBeInTheDocument();
  });
});
