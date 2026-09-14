import { describe, expect, it } from "vitest";

import {
  buildScatterMarkerPath,
  scatterFamilyColor,
  scatterMarkerShape,
} from "./benchmark-scatter-markers";

describe("benchmark scatter markers", () => {
  it("keeps algorithm families mapped to stable marker shapes and colors", () => {
    const theme = {
      chart1: "chart-one",
      chart2: "chart-two",
      chart5: "chart-five",
      destructive: "destructive",
    };

    expect(scatterMarkerShape("vqe")).toBe("circle");
    expect(scatterMarkerShape("skqd")).toBe("hexagon");
    expect(scatterFamilyColor("vqe", theme)).toBe("chart-one");
    expect(scatterFamilyColor("qfd", theme)).toBe("chart-five");
    expect(scatterFamilyColor("skqd", theme)).toBe("destructive");
  });

  it("builds closed paths for non-circular marker shapes", () => {
    expect(buildScatterMarkerPath("circle", 8, 8, 4)).toBeNull();
    expect(buildScatterMarkerPath("square", 8, 8, 4)).toBe("M 4 4 L 12 4 L 12 12 L 4 12 Z");
    expect(buildScatterMarkerPath("triangle", 8, 8, 4)).toContain("M ");
  });
});
