import type { BenchmarkRunCreate } from "@/api/benchmarks";
import type { MoleculePreset } from "@/lib/benchmark-presets";
import type { MoleculeResponse, RunAlgorithm } from "@/types/run";
import type { BenchmarkEntry } from "@/pages/benchmark/benchmark-utils";
import { buildSavedBenchmarkRunName } from "@/pages/benchmark/benchmark-storage";
import { entrySaveSignature } from "@/features/benchmarks/state/normalization";

export interface BenchmarkPayloadContext {
  selectedPresets: readonly MoleculePreset[];
  selectedAlgorithms: ReadonlySet<RunAlgorithm>;
  algorithmCount: number;
  selectedBasis: string;
  selectedBackendMode: BenchmarkRunCreate["selectedBackendMode"];
  selectedBackendName: string | null;
  shots?: number;
  optimizationLevel?: 0 | 1 | 2 | 3;
  seedTranspiler?: number | null;
  dynamicalDecoupling?: boolean;
  twirling?: boolean;
  chemicalAccuracyHa: number;
  customMolecules: readonly MoleculeResponse[];
}

export type BenchmarkSignatureContext = Omit<BenchmarkPayloadContext, "algorithmCount">;

export function buildBenchmarkPayload(
  context: BenchmarkPayloadContext,
  nextEntries: BenchmarkEntry[],
): BenchmarkRunCreate {
  return {
    name: buildSavedBenchmarkRunName({
      createdAt: new Date().toISOString(),
      moleculeCount: context.selectedPresets.length,
      algorithmCount: context.algorithmCount,
      basis: context.selectedBasis,
    }),
    selectedMoleculeKeys: context.selectedPresets.map((preset) => preset.key),
    selectedAlgorithms: Array.from(context.selectedAlgorithms),
    selectedBasis: context.selectedBasis,
    selectedBackendMode: context.selectedBackendMode,
    selectedBackendName: context.selectedBackendName,
    shots: context.shots ?? 4096,
    optimizationLevel: context.optimizationLevel ?? 1,
    seedTranspiler: context.seedTranspiler ?? null,
    dynamicalDecoupling: context.dynamicalDecoupling ?? false,
    twirling: context.twirling ?? false,
    chemicalAccuracyHa: context.chemicalAccuracyHa,
    customMolecules: [...context.customMolecules],
    entries: nextEntries,
  };
}

export function buildBenchmarkSignature(
  context: BenchmarkSignatureContext,
  nextEntries: BenchmarkEntry[],
): string {
  return JSON.stringify({
    selectedMoleculeKeys: context.selectedPresets.map((preset) => preset.key),
    selectedAlgorithms: Array.from(context.selectedAlgorithms),
    selectedBasis: context.selectedBasis,
    selectedBackendMode: context.selectedBackendMode,
    selectedBackendName: context.selectedBackendName,
    shots: context.shots ?? 4096,
    optimizationLevel: context.optimizationLevel ?? 1,
    seedTranspiler: context.seedTranspiler ?? null,
    dynamicalDecoupling: context.dynamicalDecoupling ?? false,
    twirling: context.twirling ?? false,
    chemicalAccuracyHa: context.chemicalAccuracyHa,
    customMolecules: context.customMolecules.map((molecule) => molecule.id),
    entries: nextEntries.map(entrySaveSignature),
  });
}
