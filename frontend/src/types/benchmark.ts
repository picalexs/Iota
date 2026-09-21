/** Neutral benchmark domain types shared by API and benchmark features. */

import type { MoleculePreset } from "@/lib/benchmark-presets";
import type {
  AdvancedConfig,
  BackendTarget,
  EasyOptions,
  MoleculeResponse,
  RunAlgorithm,
  UUID,
} from "@/types/run";
import type { AerMethod } from "@/types/run-config";
import type { RunExecutionMetadata } from "@/lib/results/execution-metadata";

export type BenchmarkVariantMode = "simple" | "advanced";

export type EntryStatus =
  | "idle"
  | "acquiring_molecule"
  | "submitting"
  | "queued"
  | "running"
  | "pausing"
  | "paused"
  | "completed"
  | "failed"
  | "cancelled"
  | "planned"
  | "excluded";

export interface BenchmarkEntry {
  id: string;
  preset: MoleculePreset;
  algorithm: RunAlgorithm;
  variantId?: string;
  variantLabel?: string;
  mode?: BenchmarkVariantMode;
  easyOptions?: EasyOptions | null;
  advancedConfig?: AdvancedConfig | null;
  status: EntryStatus;
  moleculeId: UUID | null;
  runId: UUID | null;
  energy: number | null;
  currentEnergy: number | null;
  converged: boolean | null;
  errorMessage: string | null;
  classicalRefs: { hf: number; fci: number } | null;
  elapsedSeconds: number | null;
  executionMetadata?: RunExecutionMetadata | null;
  latestEventSequence: number;
}

export interface BenchmarkEntryUpdate {
  id: string;
  status: EntryStatus;
  energy: number | null;
  currentEnergy: number | null;
  converged: boolean | null;
  classicalRefs: { hf: number; fci: number } | null;
  errorMessage: string | null;
  elapsedSeconds: number | null;
  executionMetadata?: RunExecutionMetadata | null;
  latestEventSequence: number;
}

export type BenchmarkEntryWithRunId = BenchmarkEntry & { runId: UUID };

export type BenchmarkBackendMode = BackendTarget | "aer_simulator_backend_noise";

export const BENCHMARK_BACKEND_MODES = [
  "statevector",
  "aer_simulator",
  "aer_simulator_backend_noise",
  "ibm_runtime",
] as const satisfies readonly BenchmarkBackendMode[];

export function isBenchmarkBackendMode(value: unknown): value is BenchmarkBackendMode {
  return (
    typeof value === "string" && BENCHMARK_BACKEND_MODES.includes(value as BenchmarkBackendMode)
  );
}

export interface BenchmarkExecutionSettings {
  mode: BenchmarkBackendMode;
  backendName: string | null;
  shots?: number;
  aerMethod?: AerMethod | null;
  device?: "CPU" | "GPU" | null;
}

export const DEFAULT_BENCHMARK_SHOTS = 4096;
export const DEFAULT_NOISY_AER_SHOTS = 256;
export const DEFAULT_AER_SHOTS = 1024;

export function getDefaultBenchmarkShots(mode: BenchmarkBackendMode): number {
  switch (mode) {
    case "aer_simulator_backend_noise":
      return DEFAULT_NOISY_AER_SHOTS;
    case "aer_simulator":
      return DEFAULT_AER_SHOTS;
    case "ibm_runtime":
    case "statevector":
    default:
      return DEFAULT_BENCHMARK_SHOTS;
  }
}

export interface SavedBenchmarkRun {
  id: string;
  name: string;
  campaignId?: string | null;
  registrationDigest?: string | null;
  campaignMetadata?: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
  selectedMoleculeKeys: string[];
  selectedAlgorithms: RunAlgorithm[];
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
