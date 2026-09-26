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
import type { RunExecutionMetadata } from "@/lib/results/execution-metadata";

export type BenchmarkVariantMode = "simple" | "advanced";

export type BenchmarkRunHistoryStatus =
  | "draft"
  | "running"
  | "paused"
  | "finished"
  | "partial"
  | "failed"
  | "cancelled"
  | "planned"
  | "excluded";

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
  optimizationLevel?: 0 | 1 | 2 | 3;
  seedTranspiler?: number | null;
  dynamicalDecoupling?: boolean;
  twirling?: boolean;
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
  optimizationLevel?: 0 | 1 | 2 | 3;
  seedTranspiler?: number | null;
  dynamicalDecoupling?: boolean;
  twirling?: boolean;
  chemicalAccuracyHa: number;
  customMolecules: MoleculeResponse[];
  entries: BenchmarkEntry[];
}

export interface SavedBenchmarkRunSummary {
  id: string;
  name: string;
  createdAt: string;
  updatedAt: string;
  selectedMoleculeKeys: string[];
  selectedBasis: string;
  selectedBackendMode: BenchmarkBackendMode;
  selectedBackendName: string | null;
  status: BenchmarkRunHistoryStatus;
  rowCount: number;
  completedCount: number;
  activeCount: number;
  pausedCount: number;
  failedCount: number;
  cancelledCount: number;
  plannedCount: number;
  excludedCount: number;
  associatedRunCount: number;
}
