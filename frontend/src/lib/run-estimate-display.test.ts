import { describe, expect, it } from "vitest";

import {
  MIN_DISPLAYABLE_ETA_CONFIDENCE,
  MIN_DISPLAYABLE_ETA_SECONDS,
  formatMeaningfulEta,
  hasMeaningfulEta,
} from "./run-estimate-display";

describe("run-estimate-display", () => {
  it("hides very small ETAs even when confidence is high", () => {
    expect(hasMeaningfulEta(MIN_DISPLAYABLE_ETA_SECONDS - 1, 0.9)).toBe(false);
    expect(formatMeaningfulEta(MIN_DISPLAYABLE_ETA_SECONDS - 1, 0.9)).toBeNull();
  });

  it("hides low-confidence ETAs", () => {
    expect(hasMeaningfulEta(90, MIN_DISPLAYABLE_ETA_CONFIDENCE - 0.01)).toBe(false);
    expect(formatMeaningfulEta(90, MIN_DISPLAYABLE_ETA_CONFIDENCE - 0.01)).toBeNull();
  });

  it("shows ETA once it is both large enough and confident enough", () => {
    expect(hasMeaningfulEta(95, MIN_DISPLAYABLE_ETA_CONFIDENCE)).toBe(true);
    expect(formatMeaningfulEta(95, MIN_DISPLAYABLE_ETA_CONFIDENCE)).toBe("1m 35s");
  });

  it("allows ETA display when confidence is missing but the duration is meaningful", () => {
    expect(hasMeaningfulEta(125, null)).toBe(true);
    expect(formatMeaningfulEta(125, null)).toBe("2m 5s");
  });
});
