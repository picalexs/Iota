import { describe, expect, it } from "vitest";

import { formatDuration } from "./format-duration";

describe("formatDuration", () => {
  it("returns a dash for nullish values", () => {
    expect(formatDuration(null)).toBe("-");
  });

  it("formats short durations in seconds", () => {
    expect(formatDuration(12.2)).toBe("12s");
  });

  it("formats minute-second durations", () => {
    expect(formatDuration(125)).toBe("2m 5s");
  });

  it("formats hour durations", () => {
    expect(formatDuration(3661)).toBe("1h 1m");
  });

  it("clamps negative values to zero", () => {
    expect(formatDuration(-2)).toBe("0s");
  });
});
