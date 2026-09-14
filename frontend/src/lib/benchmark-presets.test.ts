import { describe, expect, it } from "vitest";
import {
  BENCHMARK_MOLECULE_PRESETS,
  chemicalAccuracy,
  DEFAULT_CHEMICAL_ACCURACY_HA,
  percentCorrelationRecovered,
  usesLargeBenchmarkActiveSpace,
} from "./benchmark-presets";

describe("benchmark scoring helpers", () => {
  it("bounds percent correlation recovered to the displayable 0-100 range", () => {
    expect(percentCorrelationRecovered(-1.2, -1, -1.1)).toBe(100);
    expect(percentCorrelationRecovered(-0.95, -1, -1.1)).toBe(0);
    expect(percentCorrelationRecovered(-1.05, -1, -1.1)).toBeCloseTo(50);
  });

  it("uses the default chemical accuracy threshold and accepts overrides", () => {
    expect(chemicalAccuracy(DEFAULT_CHEMICAL_ACCURACY_HA)).toBe(true);
    expect(chemicalAccuracy(DEFAULT_CHEMICAL_ACCURACY_HA + 1e-6)).toBe(false);
    expect(chemicalAccuracy(0.002, 0.0025)).toBe(true);
  });

  it("marks the N2 benchmark preset as a large-active-space case", () => {
    const n2 = BENCHMARK_MOLECULE_PRESETS.find((preset) => preset.key === "n2");
    expect(n2?.active_space).toEqual({ n_electrons: 10, n_orbitals: 8 });
    expect(usesLargeBenchmarkActiveSpace(n2?.active_space)).toBe(true);
  });
});
