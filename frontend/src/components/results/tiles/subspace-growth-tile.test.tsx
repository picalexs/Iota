import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { SubspaceGrowthTile } from "./subspace-growth-tile";
import type { RunEventResponse } from "@/types/run";

vi.mock("@/components/results/dashboard-tile", () => ({
  DashboardTile: ({ title, children }: { title: string; children: ReactNode }) => (
    <section>
      <h2>{title}</h2>
      {children}
    </section>
  ),
}));

vi.mock("@/components/results/charts/chart-empty-state", () => ({
  ChartEmptyState: ({ message }: { message?: string }) => <div>{message}</div>,
}));

vi.mock("@/components/results/charts/chart-legend", () => ({
  ChartLegend: () => <div>Legend</div>,
}));

vi.mock("@/components/results/charts/line-plot", () => ({
  LinePlot: ({ data }: { data: Array<{ x: number; y: number }> }) => (
    <div data-testid="line-plot">{data.map((point) => `${point.x}:${point.y}`).join("|")}</div>
  ),
}));

describe("SubspaceGrowthTile", () => {
  it("renders the projected growth trace for QSE events", () => {
    const events: RunEventResponse[] = [
      {
        id: 1,
        run_id: "run-1",
        sequence: 1,
        type: "iteration_update",
        payload: {
          algorithm: "qse",
          step: "build_basis",
          completed_iterations: 1,
          energy: -1.0,
        },
        created_at: "2026-01-01T10:00:00Z",
      },
      {
        id: 2,
        run_id: "run-1",
        sequence: 2,
        type: "iteration_update",
        payload: {
          algorithm: "qse",
          step: "solve",
          subspace_dim: 2,
          energy: -1.2,
        },
        created_at: "2026-01-01T10:00:01Z",
      },
    ];

    render(<SubspaceGrowthTile algorithm="qse" events={events} finalEnergy={-1.2} />);

    expect(screen.getByRole("heading", { name: "Subspace Growth" })).toBeInTheDocument();
    expect(screen.getByTestId("line-plot")).toHaveTextContent("1:-1|2:-1.2");
  });
});
