import { describe, expect, it } from "vitest";
import type { CompletedPoint } from "./benchmark-scatter-data";
import {
  buildScatterAlgorithmOptions,
  buildScatterFamilyOptions,
  buildScatterMoleculeOptions,
  hideAllFilters,
  reconcileHiddenFilters,
  toggleHiddenFilter,
} from "./benchmark-scatter-data";

const points: CompletedPoint[] = [
  {
    id: "h2:vqe",
    familyKey: "vqe",
    familyLabel: "VQE",
    algorithm: "VQE / COBYLA",
    moleculeKey: "h2",
    molecule: "H2",
    moleculeShort: "H2",
    runId: null,
    runtime: 1,
    energy: -1.13,
    absErrorMha: 1,
    verdict: "accurate",
    tooltipSections: [],
  },
  {
    id: "h2:vqe:2",
    familyKey: "vqe",
    familyLabel: "VQE",
    algorithm: "VQE / SLSQP",
    moleculeKey: "h2",
    molecule: "H2",
    moleculeShort: "H2",
    runId: "run-2",
    runtime: 2,
    energy: -1.12,
    absErrorMha: 2,
    verdict: "not_accurate",
    tooltipSections: [],
  },
  {
    id: "beh2:qfd",
    familyKey: "qfd",
    familyLabel: "QFD",
    algorithm: "QFD",
    moleculeKey: "beh2",
    molecule: "BeH2",
    moleculeShort: "BeH2",
    runId: null,
    runtime: 3,
    energy: -15.5,
    absErrorMha: 3,
    verdict: "accurate",
    tooltipSections: [],
  },
];

describe("benchmark scatter data", () => {
  it("deduplicates filter options in point order", () => {
    expect(buildScatterFamilyOptions(points)).toEqual([
      { value: "vqe", label: "VQE" },
      { value: "qfd", label: "QFD" },
    ]);
    expect(buildScatterAlgorithmOptions(points)).toEqual([
      { value: "VQE / COBYLA", label: "VQE / COBYLA" },
      { value: "VQE / SLSQP", label: "VQE / SLSQP" },
      { value: "QFD", label: "QFD" },
    ]);
    expect(buildScatterMoleculeOptions(points)).toEqual([
      { value: "h2", label: "H2" },
      { value: "beh2", label: "BeH2" },
    ]);
  });

  it("keeps hidden filter state aligned with available values", () => {
    expect(reconcileHiddenFilters(["h2", "stale"], ["h2", "beh2"])).toEqual(["h2"]);
    expect(toggleHiddenFilter(["h2"], "h2")).toEqual([]);
    expect(toggleHiddenFilter([], "beh2")).toEqual(["beh2"]);
    expect(hideAllFilters(["h2", "beh2"])).toEqual(["h2", "beh2"]);
  });
});
