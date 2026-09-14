import { beforeEach, describe, expect, it } from "vitest";

import { DEFAULT_CHEMICAL_ACCURACY_HA } from "@/lib/benchmark-presets";
import {
  loadMoleculeCache,
  normalizeChemicalAccuracy,
  normalizeStoredBenchmarkMode,
  removeLegacyWorkspaceKeys,
  saveMoleculeCache,
} from "./benchmark-storage-serialization";
import { BENCHMARK_BACKEND_MODES, isBenchmarkBackendMode } from "@/types/benchmark";

describe("benchmark storage serialization", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("round-trips the molecule identifier cache", () => {
    const cache = {
      h2: "molecule-h2",
      "custom:water": "molecule-water",
    };

    saveMoleculeCache(cache);

    expect(loadMoleculeCache()).toEqual(cache);
  });

  it.each([
    ["malformed JSON", "{"],
    ["an array", JSON.stringify(["molecule-id"])],
    ["a record with a non-string value", JSON.stringify({ h2: 42 })],
    ["a record with an empty identifier", JSON.stringify({ h2: " " })],
  ])("returns an empty cache for %s", (_description, value) => {
    localStorage.setItem("benchmark_molecule_ids", value);

    expect(loadMoleculeCache()).toEqual({});
  });

  it("removes the legacy workspace keys after storage ownership moved to the API", () => {
    const legacyKeys = [
      "benchmark_selected_molecules",
      "benchmark_selected_algorithms",
      "benchmark_entries",
      "benchmark_basis",
      "benchmark_backend",
      "benchmark_backend_name",
      "benchmark_custom_molecules",
      "benchmark_chemical_accuracy_ha",
      "benchmark_saved_runs",
    ];
    for (const key of legacyKeys) localStorage.setItem(key, "legacy");

    removeLegacyWorkspaceKeys();

    expect(legacyKeys.every((key) => localStorage.getItem(key) === null)).toBe(true);
  });

  it("normalizes unsupported backend modes to the stable default", () => {
    expect(normalizeStoredBenchmarkMode("statevector")).toBe("statevector");
    expect(normalizeStoredBenchmarkMode("unknown-mode")).toBe("statevector");
  });

  it("keeps every persisted benchmark mode accepted by the shared guard", () => {
    expect(BENCHMARK_BACKEND_MODES).toEqual([
      "statevector",
      "aer_simulator",
      "aer_simulator_backend_noise",
      "ibm_runtime",
    ]);
    expect(BENCHMARK_BACKEND_MODES.every(isBenchmarkBackendMode)).toBe(true);
  });

  it("normalizes invalid chemical accuracy values to the stable default", () => {
    expect(normalizeChemicalAccuracy(0.002)).toBe(0.002);
    expect(normalizeChemicalAccuracy(0)).toBe(DEFAULT_CHEMICAL_ACCURACY_HA);
    expect(normalizeChemicalAccuracy(Number.NaN)).toBe(DEFAULT_CHEMICAL_ACCURACY_HA);
  });
});
