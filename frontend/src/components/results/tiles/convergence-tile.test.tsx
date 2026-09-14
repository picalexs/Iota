import { fireEvent, render, screen, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { ConvergenceTile } from "./convergence-tile";
import type { ReferenceLineSpec } from "@/components/results/charts/line-plot";
import type { RunResultResponse } from "@/types/run";

vi.mock("@/components/results/dashboard-tile", () => ({
  DashboardTile: ({
    title,
    actions,
    children,
  }: {
    title: string;
    actions?: ReactNode;
    children: ReactNode;
  }) => (
    <section>
      <h2>{title}</h2>
      {actions}
      {children}
    </section>
  ),
}));

vi.mock("@/components/results/charts/line-plot", () => ({
  LinePlot: ({
    data,
    referenceLines,
    secondaryData,
    yLabel,
    yTickFormat,
    xTickFormat,
    xTickValues,
  }: {
    data?: Array<{ x: number; y: number }>;
    referenceLines?: ReferenceLineSpec[];
    secondaryData?: Array<{ x: number; y: number }>;
    yLabel?: string;
    yTickFormat?: (value: number) => string;
    xTickFormat?: (value: number) => string;
    xTickValues?: number[];
  }) => (
    <div data-testid="line-plot">
      {data ? <span>points {data.length}</span> : null}
      {secondaryData ? <span>raw points {secondaryData.length}</span> : null}
      {yLabel ? <span>y label {yLabel}</span> : null}
      {yTickFormat ? <span>y tick {yTickFormat(0.61234)}</span> : null}
      {xTickFormat ? <span>x tick {xTickFormat(1.5)}</span> : null}
      {xTickValues ? <span>x ticks {xTickValues.join(",")}</span> : null}
      {(referenceLines ?? []).map((line) => (
        <span key={line.label}>{line.label}</span>
      ))}
    </div>
  ),
}));

vi.mock("@/components/results/charts/chart-legend", () => ({
  ChartLegend: ({ items }: { items: Array<{ label: string }> }) => (
    <div data-testid="chart-legend">
      {items.map((item) => (
        <span key={item.label}>{item.label}</span>
      ))}
    </div>
  ),
}));

const result: RunResultResponse = {
  run_id: "aaaaaaaa-0000-0000-0000-000000000001",
  energy: -1.137,
  iterations: 2,
  optimal_parameters: [],
  converged: true,
  algorithm_metrics: {
    convergence_trace: [-1, -1.1],
  },
  created_at: "2026-01-01T00:00:00Z",
};

function getFirstLinePlot(): HTMLElement {
  const chart = screen.getAllByTestId("line-plot")[0];
  if (!chart) {
    throw new Error("Expected a line plot");
  }
  return chart;
}

describe("ConvergenceTile", () => {
  it("passes numeric HF and FCI reference labels to the energy chart", () => {
    render(
      <ConvergenceTile
        events={[]}
        result={result}
        algorithm="kqd"
        hfEnergy={-1.116}
        fciEnergy={-1.137}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Linear" }));

    const energyChart = getFirstLinePlot();
    expect(within(energyChart).getByText("HF -1.11600 Ha")).toBeInTheDocument();
    expect(within(energyChart).getByText("FCI -1.13700 Ha")).toBeInTheDocument();

    const legend = screen.getByTestId("chart-legend");
    expect(within(legend).getByText("HF -1.11600 Ha")).toBeInTheDocument();
    expect(within(legend).getByText("FCI/Exact -1.13700 Ha")).toBeInTheDocument();
  });

  it("formats iteration ticks as whole numbers", () => {
    render(<ConvergenceTile events={[]} result={result} algorithm="kqd" />);

    const energyChart = getFirstLinePlot();
    expect(within(energyChart).getByText("x tick 2")).toBeInTheDocument();
    expect(within(energyChart).getByText("x ticks 1,2")).toBeInTheDocument();
  });

  it("shows raw evaluations by default for VQE", () => {
    render(<ConvergenceTile events={[]} result={result} algorithm="vqe" />);

    const initialEnergyChart = getFirstLinePlot();
    expect(within(initialEnergyChart).getByText("raw points 2")).toBeInTheDocument();
  });

  it("shows raw evaluations by default for non-QSE runs", () => {
    render(<ConvergenceTile events={[]} result={result} algorithm="kqd" />);

    const initialEnergyChart = getFirstLinePlot();
    expect(within(initialEnergyChart).getByText("raw points 2")).toBeInTheDocument();
  });

  it("keeps raw evaluations hidden by default for QSE", () => {
    render(<ConvergenceTile events={[]} result={result} algorithm="qse" />);

    const initialEnergyChart = getFirstLinePlot();
    expect(within(initialEnergyChart).queryByText("raw points 2")).not.toBeInTheDocument();
  });

  it("defaults to linear energy with a secondary log scale chart", () => {
    render(<ConvergenceTile events={[]} result={result} algorithm="kqd" fciEnergy={-1.137} />);

    const charts = screen.getAllByTestId("line-plot");
    const [energyChart, logChart] = charts;
    if (!energyChart || !logChart) {
      throw new Error("Expected linear and log convergence charts");
    }
    expect(charts).toHaveLength(2);
    expect(within(energyChart).getByText("y label Energy (Ha)")).toBeInTheDocument();
    expect(within(energyChart).getByText("FCI -1.13700 Ha")).toBeInTheDocument();
    expect(within(logChart).getByText("y label log10|E-FCI|")).toBeInTheDocument();
    expect(within(logChart).getByText("raw points 2")).toBeInTheDocument();
  });

  it("switches the main energy chart to log scale", () => {
    render(<ConvergenceTile events={[]} result={result} algorithm="kqd" fciEnergy={-1.137} />);

    fireEvent.click(screen.getByRole("button", { name: "Log scale" }));

    const charts = screen.getAllByTestId("line-plot");
    const logChart = charts[0];
    if (!logChart) {
      throw new Error("Expected a convergence chart");
    }
    expect(charts).toHaveLength(1);
    expect(within(logChart).getByText("y label log10|E-FCI|")).toBeInTheDocument();
    expect(within(logChart).getByText("y tick 0.612")).toBeInTheDocument();
  });
});
