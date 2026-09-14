import { describe, expect, it } from "vitest";

import {
  assessChemicalAccuracy,
  formatAccuracyVerdict,
  resolveChemicalAccuracyTargetHa,
} from "./accuracy";
import type { RunConfigJson } from "@/types/run";

function runConfig(config_json: RunConfigJson) {
  return { config_json };
}

describe("assessChemicalAccuracy", () => {
  it("marks chemically accurate results within threshold", () => {
    const assessment = assessChemicalAccuracy({
      energy: -1.1372,
      hf: -1.116,
      fci: -1.137,
      thresholdHa: 0.0016,
      converged: true,
    });

    expect(assessment.verdict).toBe("accurate");
    expect(assessment.withinThreshold).toBe(true);
    expect(assessment.absErrorMha).toBeCloseTo(0.2);
  });

  it("marks inaccurate results outside threshold", () => {
    const assessment = assessChemicalAccuracy({
      energy: -1.12,
      hf: -1.116,
      fci: -1.137,
      thresholdHa: 0.0016,
      converged: true,
    });

    expect(assessment.verdict).toBe("not_accurate");
    expect(assessment.withinThreshold).toBe(false);
    expect(assessment.errorMha).toBeCloseTo(17);
  });

  it("returns unscored when no exact reference is available", () => {
    const assessment = assessChemicalAccuracy({
      energy: -1.12,
      hf: -1.116,
      fci: null,
      thresholdHa: 0.0016,
      converged: false,
    });

    expect(assessment.verdict).toBe("unscored");
    expect(assessment.isScorable).toBe(false);
    expect(assessment.absErrorHa).toBeNull();
  });
});

describe("formatAccuracyVerdict", () => {
  it("returns user-facing verdict labels", () => {
    expect(formatAccuracyVerdict("accurate")).toBe("Chemically accurate");
    expect(formatAccuracyVerdict("not_accurate")).toBe("Not chemically accurate");
    expect(formatAccuracyVerdict("unscored")).toBe("Unscored");
  });
});

describe("resolveChemicalAccuracyTargetHa", () => {
  it("uses the per-run threshold when present", () => {
    expect(
      resolveChemicalAccuracyTargetHa(runConfig({ chemical_accuracy_target_ha: 0.0025 })),
    ).toBe(0.0025);
  });

  it("falls back to the default threshold when the run config does not provide one", () => {
    expect(resolveChemicalAccuracyTargetHa(runConfig({}))).toBe(0.0016);
  });
});
