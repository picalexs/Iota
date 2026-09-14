import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@visx/responsive", () => ({
  ParentSize: ({
    children,
  }: {
    children: (size: { width: number; height: number }) => ReactNode;
  }) => children({ width: 420, height: 320 }),
}));

vi.mock("./use-chart-theme", () => ({
  useChartTheme: () => ({
    chart1: "#ff0000",
    chart2: "#00ff00",
    muted: "#666666",
    border: "#222222",
  }),
}));

import { BarPlot } from "./bar-plot";

describe("BarPlot", () => {
  it("shows an empty state when no numeric values are available", () => {
    render(
      <BarPlot
        data={[
          { label: "A", value: null },
          { label: "B", value: null },
        ]}
      />,
    );

    expect(screen.getByText("Reference energies unavailable")).toBeInTheDocument();
  });

  it("renders bars, labels, and stagger connectors when overlap avoidance is enabled", () => {
    const { container } = render(
      <BarPlot
        data={[
          { label: "VQE", value: -1.12, isHighlight: true },
          { label: "QSE", value: -1.121 },
          { label: "SKQD", value: -1.1205 },
        ]}
        yLabel="Energy"
        avoidValueLabelOverlap
      />,
    );

    expect(screen.getByLabelText("Energy bar chart")).toBeInTheDocument();
    expect(container.querySelectorAll("rect").length).toBeGreaterThan(0);
    expect(container.querySelectorAll("text").length).toBeGreaterThan(3);
    expect(container.querySelectorAll("line").length).toBeGreaterThan(0);
    expect(screen.getByText("VQE")).toBeInTheDocument();
  });
});
