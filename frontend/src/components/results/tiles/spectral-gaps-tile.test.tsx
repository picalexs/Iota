import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { SpectralGapsTile } from "./spectral-gaps-tile";

vi.mock("@/components/results/dashboard-tile", () => ({
  DashboardTile: ({ title, children }: { title: string; children: ReactNode }) => (
    <section>
      <h2>{title}</h2>
      {children}
    </section>
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

vi.mock("@/components/results/charts/bar-plot", () => ({
  BarPlot: ({ data }: { data: Array<{ label: string; value: number | null }> }) => (
    <div data-testid="bar-plot">{data.map((bar) => `${bar.label}:${bar.value}`).join("|")}</div>
  ),
}));

describe("SpectralGapsTile", () => {
  it("renders excitation gaps relative to the lowest level", () => {
    render(<SpectralGapsTile title="Gaps" energies={[-1.2, -1, -0.9]} />);

    expect(screen.getByRole("heading", { name: "Gaps" })).toBeInTheDocument();
    expect(screen.getByTestId("bar-plot")).toHaveTextContent("ΔE1:0.2|ΔE2:0.3");
  });

  it("marks gaps as pending until enough projected levels arrive", () => {
    render(<SpectralGapsTile title="Gaps" energies={[-1.2]} isRunning />);

    expect(screen.getByTestId("empty-state")).toHaveAttribute("data-pending", "true");
    expect(screen.getByTestId("empty-state")).toHaveTextContent("Awaiting projected levels");
  });
});
