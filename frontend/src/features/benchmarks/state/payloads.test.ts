import { BENCHMARK_MOLECULE_PRESETS } from "@/lib/benchmark-presets";
import type { BenchmarkEntry } from "@/pages/benchmark/benchmark-utils";
import { buildBenchmarkPayload, buildBenchmarkSignature } from "./payloads";

const context = {
  selectedPresets: BENCHMARK_MOLECULE_PRESETS.slice(0, 1),
  selectedAlgorithms: new Set(["vqe"] as const),
  algorithmCount: 1,
  selectedBasis: "sto-3g",
  selectedBackendMode: "statevector" as const,
  selectedBackendName: null,
  chemicalAccuracyHa: 1.6e-3,
  customMolecules: [],
};

const entries: BenchmarkEntry[] = [];

test("buildBenchmarkPayload creates the API-owned benchmark snapshot", () => {
  const payload = buildBenchmarkPayload(context, entries);

  expect(payload.selectedMoleculeKeys).toEqual(["h2"]);
  expect(payload.selectedAlgorithms).toEqual(["vqe"]);
  expect(payload.selectedBasis).toBe("sto-3g");
  expect(payload.entries).toBe(entries);
  expect(payload.name).toContain("1 mol");
  expect(payload.name).toContain("1 alg");
});

test("buildBenchmarkSignature excludes generated names and includes entry identity", () => {
  const signature = buildBenchmarkSignature(context, entries);

  expect(signature).toContain('"selectedMoleculeKeys":["h2"]');
  expect(signature).toContain('"selectedAlgorithms":["vqe"]');
  expect(signature).not.toContain("name");
});
