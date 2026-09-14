import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { LinePlot } from "./line-plot";

vi.mock("@visx/responsive", () => ({
  ParentSize: ({
    children,
  }: {
    children: (size: { width: number; height: number }) => ReactNode;
  }) => children({ width: 480, height: 320 }),
}));

describe("LinePlot", () => {
  it("renders primary and secondary series with accessible point tooltips", () => {
    const { container } = render(
      <LinePlot
        data={[
          { x: 0, y: -1.1, tooltipTitle: "Initial", tooltipValue: "-1.100 Ha" },
          { x: 1, y: -1.2, tooltipLines: ["Chemical accuracy reached"] },
        ]}
        secondaryData={[
          { x: 0, y: -1.05 },
          { x: 1, y: -1.16, displayY: -1.15 },
        ]}
        xLabel="Iteration"
        yLabel="Energy"
        referenceLines={[{ y: -1.18, label: "FCI", dashed: false }]}
        chemAccuracyBand={{ center: -1.18, halfWidth: 0.01 }}
        primarySeriesLabel="Best"
        secondarySeriesLabel="Raw"
      />,
    );

    expect(
      container.querySelector('svg[aria-label="Energy vs Iteration line chart"]'),
    ).not.toBeNull();

    const primaryPoint = screen.getByLabelText("Best iteration 0: -1.100000");
    fireEvent.mouseEnter(primaryPoint, { clientX: 120, clientY: 80 });

    expect(screen.getByText("Initial")).toBeInTheDocument();
    expect(screen.getByText("-1.100 Ha")).toBeInTheDocument();

    fireEvent.mouseLeave(primaryPoint);
    expect(screen.queryByText("Initial")).not.toBeInTheDocument();

    fireEvent.focus(screen.getByLabelText("Raw iteration 1: -1.150000"));
    expect(screen.getByText("Raw · iter 1")).toBeInTheDocument();
    expect(screen.getByText("-1.150000 Ha")).toBeInTheDocument();
  });

  it("renders an empty state when no points are available", () => {
    render(<LinePlot data={[]} />);

    expect(screen.getByText("No data available")).toBeInTheDocument();
  });
});
