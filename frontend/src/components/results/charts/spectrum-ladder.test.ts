import { render, screen } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { SpectrumLadder } from "./spectrum-ladder";
import {
  formatSpectrumEnergy,
  layoutSpectrumLabels,
  spectrumDecimalPlaces,
} from "./spectrum-ladder-utils";

vi.mock("./use-chart-theme", () => ({
  useChartTheme: () => ({
    primary: "#111111",
    muted: "#667788",
    foreground: "#000000",
    border: "#ccddee",
    background: "#ffffff",
    card: "#ffffff",
    destructive: "#cc3344",
    success: "#22aa55",
    warning: "#ffaa33",
    info: "#3388ff",
    chart1: "#2244ff",
    chart2: "#66bbff",
    chart3: "#bbbbbb",
    chart4: "#888888",
    chart5: "#444444",
  }),
}));

vi.mock("@visx/responsive", () => ({
  ParentSize: ({
    children,
  }: {
    children: (size: { width: number; height: number }) => ReactNode;
  }) => children({ width: 420, height: 240 }),
}));

describe("spectrum ladder helpers", () => {
  it("uses more precision when eigenvalues are close together", () => {
    const decimals = spectrumDecimalPlaces([-619.23451, -619.23456, -528.4038]);

    expect(decimals).toBeGreaterThan(4);
    expect(formatSpectrumEnergy(-619.23451, decimals)).toBe("-619.2345100");
  });

  it("keeps clustered labels separated vertically", () => {
    const labels = layoutSpectrumLabels(
      [
        { index: 0, energy: -1, lineY: 20 },
        { index: 1, energy: -1.00001, lineY: 22 },
        { index: 2, energy: -1.00002, lineY: 23 },
      ],
      80,
      14,
    );
    const [first, second, third] = labels;
    if (!first || !second || !third) {
      throw new Error("Expected three spectrum labels");
    }

    expect(second.labelY - first.labelY).toBeGreaterThanOrEqual(14);
    expect(third.labelY - second.labelY).toBeGreaterThanOrEqual(14);
  });

  it("emphasizes the highlighted energy label", () => {
    render(createElement(SpectrumLadder, { energies: [-1, -0.9], highlightedIndex: 0 }));

    expect(screen.getByText("-1.0000")).toHaveAttribute("fill", "#22aa55");
    expect(screen.getByText("-1.0000")).toHaveAttribute("font-weight", "700");
    expect(screen.getByText("-0.9000")).toHaveAttribute("fill", "#667788");
  });
});
