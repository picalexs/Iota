import { DEFAULT_CHEMICAL_ACCURACY_HA } from "@/lib/benchmark-presets";
import type { SetStateAction } from "react";
import type { UUID } from "@/types/run";
import {
  isBenchmarkBackendMode,
  type BenchmarkBackendMode,
  type BenchmarkEntry,
} from "@/types/benchmark";

const LS_MOLECULES = "benchmark_selected_molecules";
const LS_ALGORITHMS = "benchmark_selected_algorithms";
const LS_ENTRIES = "benchmark_entries";
const LS_BASIS = "benchmark_basis";
const LS_BACKEND = "benchmark_backend";
const LS_BACKEND_NAME = "benchmark_backend_name";
const LS_CUSTOM_MOLECULES = "benchmark_custom_molecules";
const LS_CHEMICAL_ACCURACY_HA = "benchmark_chemical_accuracy_ha";
const LS_SAVED_RUNS = "benchmark_saved_runs";
const MOL_CACHE_KEY = "benchmark_molecule_ids";

const LEGACY_WORKSPACE_KEYS = [
  LS_MOLECULES,
  LS_ALGORITHMS,
  LS_ENTRIES,
  LS_BASIS,
  LS_BACKEND,
  LS_BACKEND_NAME,
  LS_CUSTOM_MOLECULES,
  LS_CHEMICAL_ACCURACY_HA,
  LS_SAVED_RUNS,
];

export const DEFAULT_BENCHMARK_BACKEND_MODE: BenchmarkBackendMode = "statevector";

export function resolveStateUpdate<T>(next: SetStateAction<T>, current: T): T {
  return typeof next === "function" ? (next as (previous: T) => T)(current) : next;
}

export function readStoredValue<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

export function writeStoredValue(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Best-effort cache only.
  }
}

export function removeLegacyWorkspaceKeys(): void {
  for (const key of LEGACY_WORKSPACE_KEYS) {
    try {
      localStorage.removeItem(key);
    } catch {
      // Local cleanup is best-effort only; the DB is now the source of truth.
    }
  }
}

export function normalizeEntries(
  entries: readonly BenchmarkEntry[],
  normalizeEntry: (entry: BenchmarkEntry) => BenchmarkEntry,
): BenchmarkEntry[] {
  return entries.map(normalizeEntry);
}

export function normalizeStoredBenchmarkMode(value: string): BenchmarkBackendMode {
  return isBenchmarkBackendMode(value) ? value : DEFAULT_BENCHMARK_BACKEND_MODE;
}

export function normalizeChemicalAccuracy(value: number): number {
  return Number.isFinite(value) && value > 0 ? value : DEFAULT_CHEMICAL_ACCURACY_HA;
}

function isStringRecord(value: unknown): value is Record<string, string> {
  return (
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value) &&
    Object.values(value).every((item) => typeof item === "string" && item.trim().length > 0)
  );
}

export function loadMoleculeCache(): Record<string, UUID> {
  const stored = readStoredValue<unknown>(MOL_CACHE_KEY);
  return isStringRecord(stored) ? stored : {};
}

export function saveMoleculeCache(cache: Record<string, UUID>): void {
  writeStoredValue(MOL_CACHE_KEY, cache);
}
