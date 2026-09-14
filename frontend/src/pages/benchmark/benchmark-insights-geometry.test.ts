import { describe, expect, it } from "vitest";
import {
  buildLogTicks,
  buildRuntimeLogTicks,
  buildRuntimeScatterMetrics,
  filterRuntimeTicksBySpacing,
} from "./benchmark-insights-geometry";
import type { CompletedPoint } from "./benchmark-scatter-data";

function buildPoint(overrides: Partial<CompletedPoint> = {}): CompletedPoint {
  return {
    id: "point-1",
    familyKey: "vqe",
    familyLabel: "VQE",
    algorithm: "VQE · default",
    moleculeKey: "h2",
    molecule: "H2",
    moleculeShort: "H2",
    runId: "run-1",
    runtime: 1,
    energy: -1.137,
    absErrorMha: 0.4,
    verdict: "accurate",
    tooltipSections: [],
    ...overrides,
  };
}

describe("benchmark insights geometry", () => {
  it("keeps target and boundary values when sampling logarithmic ticks", () => {
    const ticks = buildLogTicks(0.01, 1000, 1.6);

    expect(ticks[0]).toBe(0.01);
    expect(ticks.at(-1)).toBe(1000);
    expect(ticks).toContain(1.6);
    expect(ticks).toHaveLength(6);
  });

  it("returns one runtime tick for a collapsed runtime range", () => {
    expect(buildRuntimeLogTicks(4, 4)).toEqual([4]);
  });

  it("builds log-scaled coordinates and label layouts for both scatter modes", () => {
    const points = [
      buildPoint({ id: "fast", runtime: 0.5, absErrorMha: 0.4 }),
      buildPoint({ id: "slow", runtime: 2055, absErrorMha: 2.2 }),
    ];
    const embedded = buildRuntimeScatterMetrics({
      points,
      chemicalAccuracyHa: 0.0016,
      mode: "embedded",
    });
    const fullscreen = buildRuntimeScatterMetrics({
      points,
      chemicalAccuracyHa: 0.0016,
      mode: "fullscreen",
    });

    expect(embedded.width).toBe(760);
    expect(embedded.height).toBe(360);
    expect(fullscreen.width).toBe(1120);
    expect(fullscreen.height).toBe(540);
    expect(embedded.targetMha).toBe(1.6);
    expect(embedded.xForRuntime(0.5)).toBe(embedded.leftPad);
    expect(embedded.xForRuntime(2055)).toBe(embedded.width - embedded.rightPad);
    expect(embedded.targetY).toBe(embedded.yForError(1.6));
    expect(embedded.labelLayouts.has("fast")).toBe(true);
    expect(embedded.labelLayouts.has("slow")).toBe(true);
  });

  it("replaces a crowded final tick with the range endpoint", () => {
    const ticks = filterRuntimeTicksBySpacing([1, 2, 3], (value) => value * 100);

    expect(ticks).toEqual([1, 2, 3]);
  });

  it("reduces inline label work for dense point sets", () => {
    const points = Array.from({ length: 13 }, (_, index) =>
      buildPoint({
        id: `point-${index}`,
        runtime: index + 1,
        absErrorMha: 0.4 + index * 0.1,
      }),
    );

    const metrics = buildRuntimeScatterMetrics({
      points,
      chemicalAccuracyHa: 0.0016,
      mode: "embedded",
    });

    expect(metrics.reduceInlineLabels).toBe(true);
  });
});
