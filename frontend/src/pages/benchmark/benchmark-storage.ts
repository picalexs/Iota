import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type Dispatch,
  type SetStateAction,
} from "react";
import { BENCHMARK_ALGORITHMS, DEFAULT_CHEMICAL_ACCURACY_HA } from "@/lib/benchmark-presets";
import type { RunAlgorithm, MoleculeResponse } from "@/types/run";
import type { AerMethod } from "@/types/run-config";
import {
  getDefaultBenchmarkShots,
  type BenchmarkBackendMode,
  type BenchmarkEntry,
  type SavedBenchmarkRun,
} from "@/types/benchmark";
import type { BenchmarkAlgorithmVariant, BenchmarkVariantMode } from "./benchmark-variants";
import {
  DEFAULT_BENCHMARK_BACKEND_MODE,
  loadMoleculeCache,
  normalizeChemicalAccuracy,
  normalizeEntries,
  normalizeStoredBenchmarkMode,
  removeLegacyWorkspaceKeys,
  resolveStateUpdate,
  saveMoleculeCache,
} from "./benchmark-storage-serialization";
export { loadMoleculeCache, saveMoleculeCache } from "./benchmark-storage-serialization";
export type { SavedBenchmarkRun } from "@/types/benchmark";

const MAX_SAVED_BENCHMARK_RUNS = 1000;
export const SAVED_BENCHMARK_LIST_LIMIT = 1000;

const DEFAULT_ALGORITHMS: RunAlgorithm[] = BENCHMARK_ALGORITHMS.map((algorithm) => algorithm.value);
const DEFAULT_BASIS = "sto-3g";

export interface BenchmarkWorkspaceStateSnapshot {
  benchmarkMode: BenchmarkVariantMode;
  selectedMoleculeKeys: string[];
  selectedAlgorithms: RunAlgorithm[];
  algorithmVariants: BenchmarkAlgorithmVariant[];
  selectedBasis: string;
  selectedBackendMode: BenchmarkBackendMode;
  selectedBackendName: string | null;
  shots?: number;
  selectedAerMethod?: AerMethod | null;
  selectedDevice?: "CPU" | "GPU" | null;
  chemicalAccuracyHa: number;
  customMolecules: MoleculeResponse[];
  entries: BenchmarkEntry[];
}

function useLegacyWorkspaceCleanup() {
  useEffect(() => {
    removeLegacyWorkspaceKeys();
  }, []);
}

function useNormalizedEntriesSetter(
  normalizeEntry: (entry: BenchmarkEntry) => BenchmarkEntry,
  setEntriesState: Dispatch<SetStateAction<BenchmarkEntry[]>>,
): Dispatch<SetStateAction<BenchmarkEntry[]>> {
  return useCallback(
    (next) => {
      setEntriesState((current) =>
        normalizeEntries(resolveStateUpdate(next, current), normalizeEntry),
      );
    },
    [normalizeEntry, setEntriesState],
  );
}

function useNormalizedBackendModeSetter(
  setStoredBackendMode: Dispatch<SetStateAction<BenchmarkBackendMode>>,
): Dispatch<SetStateAction<BenchmarkBackendMode>> {
  return useCallback(
    (next) => {
      setStoredBackendMode((current) =>
        normalizeStoredBenchmarkMode(resolveStateUpdate(next, current)),
      );
    },
    [setStoredBackendMode],
  );
}

function useNormalizedChemicalAccuracySetter(
  setStoredChemicalAccuracyHa: Dispatch<SetStateAction<number>>,
): Dispatch<SetStateAction<number>> {
  return useCallback(
    (next) => {
      setStoredChemicalAccuracyHa((current) =>
        normalizeChemicalAccuracy(resolveStateUpdate(next, current)),
      );
    },
    [setStoredChemicalAccuracyHa],
  );
}

function compareSavedRuns(left: SavedBenchmarkRun, right: SavedBenchmarkRun): number {
  return (
    right.updatedAt.localeCompare(left.updatedAt) || right.createdAt.localeCompare(left.createdAt)
  );
}

export function buildSavedBenchmarkRunName({
  createdAt,
  moleculeCount,
  algorithmCount,
  basis,
}: {
  createdAt: string;
  moleculeCount: number;
  algorithmCount: number;
  basis: string;
}): string {
  const stamp =
    typeof createdAt === "string" && createdAt.length >= 16
      ? createdAt.slice(0, 16).replace("T", " ")
      : "Saved benchmark";
  return `${stamp} · ${moleculeCount} mol · ${algorithmCount} alg · ${basis}`;
}

export function upsertSavedBenchmarkRun(
  current: readonly SavedBenchmarkRun[],
  nextRun: SavedBenchmarkRun,
): SavedBenchmarkRun[] {
  return [nextRun, ...current.filter((run) => run.id !== nextRun.id)]
    .sort(compareSavedRuns)
    .slice(0, MAX_SAVED_BENCHMARK_RUNS);
}

export function primeCustomMoleculeCache(customMolecules: readonly MoleculeResponse[]) {
  const cache = loadMoleculeCache();
  let changed = false;

  for (const mol of customMolecules) {
    const key = `custom:${mol.id}`;
    if (cache[key] !== mol.id) {
      cache[key] = mol.id;
      changed = true;
    }
  }

  if (changed) saveMoleculeCache(cache);
}

export function useBenchmarkStorage(
  normalizeEntry: (entry: BenchmarkEntry) => BenchmarkEntry,
  initialSnapshot: BenchmarkWorkspaceStateSnapshot | null = null,
): {
  selectedMoleculeKeys: string[];
  setSelectedMoleculeKeys: Dispatch<SetStateAction<string[]>>;
  benchmarkMode: BenchmarkVariantMode;
  setBenchmarkMode: Dispatch<SetStateAction<BenchmarkVariantMode>>;
  selectedAlgorithms: RunAlgorithm[];
  setSelectedAlgorithms: Dispatch<SetStateAction<RunAlgorithm[]>>;
  algorithmVariants: BenchmarkAlgorithmVariant[];
  setAlgorithmVariants: Dispatch<SetStateAction<BenchmarkAlgorithmVariant[]>>;
  entries: BenchmarkEntry[];
  setEntries: Dispatch<SetStateAction<BenchmarkEntry[]>>;
  restoredEntries: BenchmarkEntry[];
  selectedBasis: string;
  setSelectedBasis: Dispatch<SetStateAction<string>>;
  selectedBackendMode: BenchmarkBackendMode;
  setSelectedBackendMode: Dispatch<SetStateAction<BenchmarkBackendMode>>;
  selectedBackendName: string | null;
  setSelectedBackendName: Dispatch<SetStateAction<string | null>>;
  shots: number;
  setShots: Dispatch<SetStateAction<number>>;
  selectedAerMethod: AerMethod | null;
  setSelectedAerMethod: Dispatch<SetStateAction<AerMethod | null>>;
  selectedDevice: "CPU" | "GPU" | null;
  setSelectedDevice: Dispatch<SetStateAction<"CPU" | "GPU" | null>>;
  customMolecules: MoleculeResponse[];
  setCustomMolecules: Dispatch<SetStateAction<MoleculeResponse[]>>;
  chemicalAccuracyHa: number;
  setChemicalAccuracyHa: Dispatch<SetStateAction<number>>;
} {
  const initialEntriesRef = useRef<BenchmarkEntry[]>(
    normalizeEntries(initialSnapshot?.entries ?? [], normalizeEntry),
  );
  const [selectedMoleculeKeys, setSelectedMoleculeKeys] = useState<string[]>(
    () => initialSnapshot?.selectedMoleculeKeys ?? [],
  );
  const [benchmarkMode, setBenchmarkMode] = useState<BenchmarkVariantMode>(
    () => initialSnapshot?.benchmarkMode ?? "simple",
  );
  const [selectedAlgorithms, setSelectedAlgorithms] = useState<RunAlgorithm[]>(
    () => initialSnapshot?.selectedAlgorithms ?? DEFAULT_ALGORITHMS,
  );
  const [algorithmVariants, setAlgorithmVariants] = useState<BenchmarkAlgorithmVariant[]>(
    () => initialSnapshot?.algorithmVariants ?? [],
  );
  const [entries, setEntries] = useState<BenchmarkEntry[]>(() => initialEntriesRef.current);
  const [selectedBasis, setSelectedBasis] = useState<string>(
    () => initialSnapshot?.selectedBasis ?? DEFAULT_BASIS,
  );
  const [storedBackendMode, setStoredBackendMode] = useState<BenchmarkBackendMode>(
    () => initialSnapshot?.selectedBackendMode ?? DEFAULT_BENCHMARK_BACKEND_MODE,
  );
  const [selectedBackendName, setSelectedBackendName] = useState<string | null>(
    () => initialSnapshot?.selectedBackendName ?? null,
  );
  const [shots, setShots] = useState<number>(
    () => initialSnapshot?.shots ?? getDefaultBenchmarkShots(storedBackendMode),
  );
  const [selectedAerMethod, setSelectedAerMethod] = useState<AerMethod | null>(
    () => initialSnapshot?.selectedAerMethod ?? "automatic",
  );
  const [selectedDevice, setSelectedDevice] = useState<"CPU" | "GPU" | null>(
    () => initialSnapshot?.selectedDevice ?? null,
  );
  const [customMolecules, setCustomMolecules] = useState<MoleculeResponse[]>(
    () => initialSnapshot?.customMolecules ?? [],
  );
  const [storedChemicalAccuracyHa, setStoredChemicalAccuracyHa] = useState<number>(
    () => initialSnapshot?.chemicalAccuracyHa ?? DEFAULT_CHEMICAL_ACCURACY_HA,
  );

  useLegacyWorkspaceCleanup();

  const restoredEntries = initialEntriesRef.current;
  const restoredEntriesRef = useRef(restoredEntries);

  const setNormalizedEntries = useNormalizedEntriesSetter(normalizeEntry, setEntries);

  const setSelectedBackendMode = useNormalizedBackendModeSetter(setStoredBackendMode);

  const chemicalAccuracyHa = normalizeChemicalAccuracy(storedChemicalAccuracyHa);

  const setChemicalAccuracyHa = useNormalizedChemicalAccuracySetter(setStoredChemicalAccuracyHa);

  return {
    selectedMoleculeKeys,
    setSelectedMoleculeKeys,
    benchmarkMode,
    setBenchmarkMode,
    selectedAlgorithms,
    setSelectedAlgorithms,
    algorithmVariants,
    setAlgorithmVariants,
    entries,
    setEntries: setNormalizedEntries,
    restoredEntries: restoredEntriesRef.current,
    selectedBasis,
    setSelectedBasis,
    selectedBackendMode: normalizeStoredBenchmarkMode(storedBackendMode),
    setSelectedBackendMode,
    selectedBackendName,
    setSelectedBackendName,
    shots,
    setShots,
    selectedAerMethod,
    setSelectedAerMethod,
    selectedDevice,
    setSelectedDevice,
    customMolecules,
    setCustomMolecules,
    chemicalAccuracyHa,
    setChemicalAccuracyHa,
  };
}
