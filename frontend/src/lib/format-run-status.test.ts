import { describe, expect, it } from "vitest";

import { formatRunStatusLine } from "./format-run-status";

describe("formatRunStatusLine", () => {
  it("returns null when no fields are present", () => {
    expect(
      formatRunStatusLine({
        iteration: null,
        totalIterations: null,
        energy: null,
        remainingIterations: null,
        remainingSeconds: null,
      }),
    ).toBeNull();
  });

  it("formats iteration, energy, remaining iterations, and ETA without estimated totals", () => {
    expect(
      formatRunStatusLine({
        iteration: 3,
        totalIterations: 10,
        energy: -1.23456789,
        remainingIterations: 7,
        remainingSeconds: 125,
      }),
    ).toBe("Iteration 3 · Energy -1.234568 Ha · Remaining 7 · ETA 2m 5s");
  });

  it("omits saturated zero-second ETA values", () => {
    expect(
      formatRunStatusLine({
        iteration: 3,
        totalIterations: 10,
        energy: null,
        remainingIterations: null,
        remainingSeconds: 0,
      }),
    ).toBe("Iteration 3");
  });
});
