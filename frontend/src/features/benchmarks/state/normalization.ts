/** Pure benchmark state normalization and in-memory view-cache helpers. */

import type { MoleculeResponse, RunEventResponse, RunRestartResponse, UUID } from "@/types/run";
import type {
  BenchmarkWorkspaceStateSnapshot,
  SavedBenchmarkRun,
} from "@/pages/benchmark/benchmark-storage";
import {
  normalizeBenchmarkVariantLabels,
  createAdvancedBenchmarkVariant,
  createSimpleBenchmarkVariant,
  type BenchmarkAlgorithmVariant,
} from "@/pages/benchmark/benchmark-variants";
import { normalizeStoredEntry } from "@/pages/benchmark/benchmark-utils";
import type { BenchmarkBackendMode, BenchmarkEntry } from "@/pages/benchmark/benchmark-utils";

export type BenchmarkPreset = BenchmarkEntry["preset"];

const benchmarkWorkspaceViewCache = new Map<string, BenchmarkWorkspaceStateSnapshot>();

export function getBenchmarkSubmissionConcurrency(
  selectedBackendMode: BenchmarkBackendMode,
): number {
  switch (selectedBackendMode) {
    case "ibm_runtime":
      return 1;
    case "aer_simulator_backend_noise":
      return 2;
    case "aer_simulator":
      return 2;
    case "statevector":
    default:
      return 3;
  }
}

function cloneBenchmarkWorkspaceSnapshot(
  snapshot: BenchmarkWorkspaceStateSnapshot,
): BenchmarkWorkspaceStateSnapshot {
  return {
    benchmarkMode: snapshot.benchmarkMode,
    selectedMoleculeKeys: [...snapshot.selectedMoleculeKeys],
    selectedAlgorithms: [...snapshot.selectedAlgorithms],
    algorithmVariants: snapshot.algorithmVariants.map((variant) => ({
      ...variant,
      advancedConfig: variant.advancedConfig ? structuredClone(variant.advancedConfig) : null,
    })),
    selectedBasis: snapshot.selectedBasis,
    selectedBackendMode: snapshot.selectedBackendMode,
    selectedBackendName: snapshot.selectedBackendName,
    shots: snapshot.shots ?? 4096,
    optimizationLevel: snapshot.optimizationLevel ?? 1,
    seedTranspiler: snapshot.seedTranspiler ?? null,
    dynamicalDecoupling: snapshot.dynamicalDecoupling ?? false,
    twirling: snapshot.twirling ?? false,
    chemicalAccuracyHa: snapshot.chemicalAccuracyHa,
    customMolecules: [...snapshot.customMolecules],
    entries: snapshot.entries.map(normalizeStoredEntry),
  };
}

export function readBenchmarkWorkspaceViewCache(
  benchmarkId: string | null,
): BenchmarkWorkspaceStateSnapshot | null {
  if (benchmarkId === null) return null;
  const snapshot = benchmarkWorkspaceViewCache.get(benchmarkId);
  return snapshot ? cloneBenchmarkWorkspaceSnapshot(snapshot) : null;
}

export function writeBenchmarkWorkspaceViewCache(
  benchmarkId: string,
  snapshot: BenchmarkWorkspaceStateSnapshot,
): void {
  benchmarkWorkspaceViewCache.set(benchmarkId, cloneBenchmarkWorkspaceSnapshot(snapshot));
}

export function deleteBenchmarkWorkspaceViewCache(benchmarkId: string): void {
  benchmarkWorkspaceViewCache.delete(benchmarkId);
}

export function hasRestorableBenchmarkWorkspaceSnapshot(
  snapshot: BenchmarkWorkspaceStateSnapshot | null,
): snapshot is BenchmarkWorkspaceStateSnapshot {
  return (
    snapshot !== null && (snapshot.entries.length > 0 || snapshot.selectedMoleculeKeys.length > 0)
  );
}

export function clearBenchmarkWorkspaceViewCache(): void {
  benchmarkWorkspaceViewCache.clear();
}

export function buildBenchmarkWorkspaceSnapshotFromSavedRun(
  savedRun: SavedBenchmarkRun,
): BenchmarkWorkspaceStateSnapshot {
  const normalizedEntries = savedRun.entries.map(normalizeStoredEntry);
  const recoveredBenchmarkMode = normalizedEntries.some((entry) => entry.mode === "advanced")
    ? "advanced"
    : "simple";
  const entrySelectedMoleculeKeys = deriveSelectedMoleculeKeysFromEntries(normalizedEntries);
  const savedSelectedMoleculeKeys = Array.from(savedRun.selectedMoleculeKeys);
  const missingEntryMoleculeKeys = entrySelectedMoleculeKeys.filter(
    (key) => !savedSelectedMoleculeKeys.includes(key),
  );
  const recoveredSelectedMoleculeKeys =
    savedSelectedMoleculeKeys.length > 0
      ? [...savedSelectedMoleculeKeys, ...missingEntryMoleculeKeys]
      : entrySelectedMoleculeKeys;
  const recoveredSelectedAlgorithms =
    normalizedEntries.length > 0
      ? Array.from(new Set(normalizedEntries.map((entry) => entry.algorithm)))
      : Array.from(savedRun.selectedAlgorithms);
  const recoveredVariants = deriveAlgorithmVariantsFromEntries(normalizedEntries);
  const finalizedVariants =
    recoveredVariants.length > 0
      ? recoveredVariants
      : recoveredSelectedAlgorithms.map((algorithm) =>
          recoveredBenchmarkMode === "advanced"
            ? createAdvancedBenchmarkVariant(algorithm, savedRun.chemicalAccuracyHa)
            : createSimpleBenchmarkVariant(algorithm),
        );
  const recoveredCustomMolecules = mergeCustomMolecules(
    savedRun.customMolecules,
    deriveCustomMoleculesFromEntries(
      normalizedEntries,
      savedRun.selectedBasis,
      savedRun.updatedAt ?? savedRun.createdAt,
    ),
  );

  return {
    benchmarkMode: recoveredBenchmarkMode,
    selectedMoleculeKeys: recoveredSelectedMoleculeKeys,
    selectedAlgorithms: recoveredSelectedAlgorithms,
    algorithmVariants: finalizedVariants,
    selectedBasis: savedRun.selectedBasis,
    selectedBackendMode: savedRun.selectedBackendMode,
    selectedBackendName: savedRun.selectedBackendName,
    shots: savedRun.shots ?? 4096,
    optimizationLevel: savedRun.optimizationLevel ?? 1,
    seedTranspiler: savedRun.seedTranspiler ?? null,
    dynamicalDecoupling: savedRun.dynamicalDecoupling ?? false,
    twirling: savedRun.twirling ?? false,
    chemicalAccuracyHa: savedRun.chemicalAccuracyHa,
    customMolecules: recoveredCustomMolecules,
    entries: normalizedEntries,
  };
}

function deriveSelectedMoleculeKeysFromEntries(entries: readonly BenchmarkEntry[]): string[] {
  const selectedMoleculeKeys: string[] = [];
  const seen = new Set<string>();

  for (const entry of entries) {
    const key = entry.preset.key.trim();
    if (!key || seen.has(key)) continue;
    seen.add(key);
    selectedMoleculeKeys.push(key);
  }

  return selectedMoleculeKeys;
}

function deriveCustomMoleculesFromEntries(
  entries: readonly BenchmarkEntry[],
  selectedBasis: string,
  fallbackTimestamp: string,
): MoleculeResponse[] {
  const customMolecules: MoleculeResponse[] = [];
  const seen = new Set<string>();

  for (const entry of entries) {
    const key = entry.preset.key.trim();
    if (!key.startsWith("custom:")) continue;

    const moleculeId = entry.moleculeId ?? key.slice("custom:".length);
    if (!moleculeId || seen.has(moleculeId)) continue;

    seen.add(moleculeId);
    customMolecules.push({
      id: moleculeId,
      name: entry.preset.name,
      atoms: entry.preset.atoms,
      basis_set: entry.preset.basis,
      charge: entry.preset.charge,
      multiplicity: entry.preset.multiplicity,
      active_space: entry.preset.active_space,
      created_at: fallbackTimestamp,
      updated_at: fallbackTimestamp,
      iupac_name: entry.preset.formula,
      description: entry.preset.description,
    });
  }

  return customMolecules.map((molecule) => ({
    ...molecule,
    basis_set: molecule.basis_set || selectedBasis,
  }));
}

function deriveAlgorithmVariantsFromEntries(
  entries: readonly BenchmarkEntry[],
): BenchmarkAlgorithmVariant[] {
  const variants = new Map<string, BenchmarkAlgorithmVariant>();

  for (const entry of entries) {
    const variantId = entry.variantId ?? entry.algorithm;
    if (variants.has(variantId)) {
      continue;
    }
    variants.set(variantId, {
      id: variantId,
      algorithm: entry.algorithm,
      mode: entry.mode ?? "simple",
      label: entry.variantLabel ?? entry.algorithm.toUpperCase(),
      easyGoal: entry.easyOptions?.goal ?? null,
      advancedConfig: entry.advancedConfig ?? null,
    });
  }

  return normalizeBenchmarkVariantLabels(Array.from(variants.values()));
}

function buildBenchmarkEntryId(presetKey: string, variant: BenchmarkAlgorithmVariant): string {
  return `${presetKey}:${variant.algorithm}:${variant.id}`;
}

function buildIdleBenchmarkEntry(
  preset: BenchmarkPreset,
  variant: BenchmarkAlgorithmVariant,
): BenchmarkEntry {
  return {
    id: buildBenchmarkEntryId(preset.key, variant),
    preset,
    algorithm: variant.algorithm,
    variantId: variant.id,
    variantLabel: variant.label,
    mode: variant.mode,
    easyOptions: variant.mode === "simple" && variant.easyGoal ? { goal: variant.easyGoal } : null,
    advancedConfig: variant.mode === "advanced" ? variant.advancedConfig : null,
    status: "idle",
    moleculeId: null,
    runId: null,
    energy: null,
    currentEnergy: null,
    converged: null,
    errorMessage: null,
    classicalRefs: null,
    elapsedSeconds: null,
    latestEventSequence: 0,
  };
}

export function reconcileAdvancedBenchmarkEntries(
  selectedPresets: readonly BenchmarkPreset[],
  algorithmVariants: readonly BenchmarkAlgorithmVariant[],
  entries: readonly BenchmarkEntry[],
): BenchmarkEntry[] {
  const existingByPresetAndVariant = new Map<string, BenchmarkEntry>();

  for (const entry of entries) {
    const variantId = entry.variantId ?? entry.algorithm;
    existingByPresetAndVariant.set(`${entry.preset.key}:${variantId}`, entry);
  }

  return selectedPresets.flatMap((preset) =>
    algorithmVariants.map((variant) => {
      const existing = existingByPresetAndVariant.get(`${preset.key}:${variant.id}`);
      const sharedFields = {
        id: buildBenchmarkEntryId(preset.key, variant),
        preset,
        algorithm: variant.algorithm,
        variantId: variant.id,
        variantLabel: variant.label,
        mode: variant.mode,
        easyOptions:
          variant.mode === "simple" && variant.easyGoal ? { goal: variant.easyGoal } : null,
        advancedConfig: variant.mode === "advanced" ? variant.advancedConfig : null,
      };

      if (!existing) {
        return buildIdleBenchmarkEntry(preset, variant);
      }

      return normalizeStoredEntry({
        ...existing,
        ...sharedFields,
      });
    }),
  );
}

export function benchmarkWorkspaceSnapshotChanged(
  left: BenchmarkWorkspaceStateSnapshot,
  right: BenchmarkWorkspaceStateSnapshot,
): boolean {
  return (
    left.benchmarkMode !== right.benchmarkMode ||
    left.selectedBasis !== right.selectedBasis ||
    left.selectedBackendMode !== right.selectedBackendMode ||
    left.selectedBackendName !== right.selectedBackendName ||
    left.chemicalAccuracyHa !== right.chemicalAccuracyHa ||
    JSON.stringify(left.selectedMoleculeKeys) !== JSON.stringify(right.selectedMoleculeKeys) ||
    JSON.stringify(left.selectedAlgorithms) !== JSON.stringify(right.selectedAlgorithms) ||
    JSON.stringify(left.algorithmVariants) !== JSON.stringify(right.algorithmVariants) ||
    JSON.stringify(left.customMolecules) !== JSON.stringify(right.customMolecules) ||
    benchmarkEntriesChanged(left.entries, right.entries)
  );
}

export function latestEnergyFromEvents(events: readonly RunEventResponse[]): number | null {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const event = events[index];
    if (!event) {
      continue;
    }
    const energy = event.payload.energy;
    if (typeof energy === "number" && Number.isFinite(energy)) return energy;
  }
  return null;
}

export function mergeCustomMolecules(
  current: MoleculeResponse[],
  incoming: MoleculeResponse[],
): MoleculeResponse[] {
  const merged = new Map(current.map((molecule) => [molecule.id, molecule]));
  for (const molecule of incoming) {
    merged.set(molecule.id, molecule);
  }
  return Array.from(merged.values());
}

export function entrySaveSignature(entry: BenchmarkEntry): string {
  return JSON.stringify({
    id: entry.id,
    variantId: entry.variantId,
    variantLabel: entry.variantLabel,
    mode: entry.mode,
    easyOptions: entry.easyOptions,
    advancedConfig: entry.advancedConfig,
    status: entry.status,
    moleculeId: entry.moleculeId,
    runId: entry.runId,
    energy: entry.energy,
    currentEnergy: entry.currentEnergy,
    converged: entry.converged,
    errorMessage: entry.errorMessage,
    classicalRefs: entry.classicalRefs,
    elapsedSeconds: entry.elapsedSeconds,
    latestEventSequence: entry.latestEventSequence,
    executionMetadata: entry.executionMetadata,
  });
}

export { hasRunId } from "@/features/benchmarks/state/selectors";

export function benchmarkEntriesChanged(left: BenchmarkEntry[], right: BenchmarkEntry[]): boolean {
  if (left.length !== right.length) return true;
  return left.some((entry, index) => {
    const rightEntry = right[index];
    return rightEntry === undefined || entrySaveSignature(entry) !== entrySaveSignature(rightEntry);
  });
}

export function getRestartTargetRunId(response: RunRestartResponse, fallbackRunId: UUID): UUID {
  if ("child_run_id" in response && response.child_run_id) return response.child_run_id;
  if ("new_run_id" in response && response.new_run_id) return response.new_run_id;
  if ("target_run_id" in response && response.target_run_id) return response.target_run_id;
  return response.id ?? fallbackRunId;
}
