import { createRun } from "@/api/runs";
import type { MoleculePreset } from "@/lib/benchmark-presets";
import {
  assessChemicalAccuracy,
  type AccuracyAssessment,
  type AccuracyVerdict,
} from "@/lib/results/accuracy";
import { getErrorMessage, isApiErrorLike } from "@/lib/error-handler";
import { getTimedOutFailureMessage } from "@/lib/run-failure";
import type {
  BackendCapability,
  BackendDeviceSummary,
  BackendTarget,
  MoleculeResponse,
  RunAlgorithm,
  RunResponse,
  UUID,
} from "@/types/run";
import type {
  BenchmarkBackendMode,
  BenchmarkEntry,
  BenchmarkEntryUpdate,
  BenchmarkEntryWithRunId,
  BenchmarkExecutionSettings,
  EntryStatus,
} from "@/types/benchmark";
export type {
  BenchmarkBackendMode,
  BenchmarkEntry,
  BenchmarkEntryUpdate,
  BenchmarkEntryWithRunId,
  BenchmarkExecutionSettings,
  EntryStatus,
} from "@/types/benchmark";
export { isBenchmarkBackendMode } from "@/types/benchmark";
import {
  buildAdvancedBenchmarkRunConfig,
  buildSimpleBenchmarkRunConfig,
} from "./benchmark-run-config";
import { formatEasyGoalLabel } from "./benchmark-insights-formatters";
import { MoleculeAcquisitionError } from "./molecule-acquisition";
import type { MoleculeAcquisitionResult } from "./molecule-acquisition";
import type { BenchmarkAlgorithmVariant, BenchmarkVariantMode } from "./benchmark-variants";
export {
  MoleculeAcquisitionError,
  acquireMolecule,
  acquireMoleculeId,
} from "./molecule-acquisition";
export type {
  MoleculeAcquisitionAttempt,
  MoleculeAcquisitionAttemptKind,
  MoleculeAcquisitionFailureKind,
  MoleculeAcquisitionResult,
  MoleculeAcquisitionResultKind,
  MoleculeCacheState,
} from "./molecule-acquisition";

type OptionalBackendCapability = BackendCapability | null | undefined;

export interface BenchmarkSubmitResult {
  id: string;
  status: EntryStatus;
  moleculeId: UUID | null;
  runId: UUID | null;
  errorMessage: string | null;
}

export type BenchmarkAccuracyFilter = "all" | AccuracyVerdict;
export type BenchmarkAccuracySort = "default" | "lowest_error" | "highest_error";
export type BenchmarkEligibilityReason =
  | "not_completed"
  | "reported_energy_invalid"
  | "projected_solve_diagnostic"
  | "scientific_convergence_not_established"
  | "reference_provenance_unavailable";
export const TERMINAL: Set<EntryStatus> = new Set(["completed", "failed", "cancelled"]);
export const NON_EXECUTING: Set<EntryStatus> = new Set(["planned", "excluded"]);
export const RUNNING_POLL_INTERVAL_MS = 3000;
export const QUEUED_POLL_INTERVAL_MS = 12000;
export const POLL_INTERVAL_MS = RUNNING_POLL_INTERVAL_MS;
const BENCHMARK_SUBMIT_RETRY_DELAY_MS = 250;
const GENERIC_BENCHMARK_SUBMIT_ERROR = "An unexpected error occurred";

export const BASIS_OPTIONS = [
  { value: "sto-3g", label: "STO-3G" },
  { value: "6-31g", label: "6-31G" },
  { value: "6-31g*", label: "6-31G*" },
  { value: "cc-pvdz", label: "cc-pVDZ" },
];

export interface BenchmarkBackendOption {
  value: BenchmarkBackendMode;
  label: string;
  warning?: string;
  enabled: boolean;
}

interface BenchmarkBackendOptionsState {
  pending?: boolean;
}

export const DEFAULT_BENCHMARK_BACKEND_MODE: BenchmarkBackendMode = "statevector";

export function benchmarkEntryDisplayLabel(
  entry: Pick<BenchmarkEntry, "algorithm" | "variantLabel">,
): string {
  const label = entry.variantLabel?.trim() ?? "";
  if (label.length === 0) {
    return entry.algorithm.toUpperCase();
  }
  return `${entry.algorithm.toUpperCase()} · ${label}`;
}

function resolveBenchmarkVariantMode(
  entry: Pick<BenchmarkEntry, "mode" | "advancedConfig">,
): BenchmarkVariantMode {
  if (entry.mode === "advanced" || entry.mode === "simple") {
    return entry.mode;
  }
  if (entry.advancedConfig) {
    return "advanced";
  }
  return "simple";
}

export function getAssociatedBenchmarkRunIds(entries: readonly BenchmarkEntry[]): UUID[] {
  const runIds = new Set<UUID>();
  for (const entry of entries) {
    if (entry.runId) {
      runIds.add(entry.runId);
    }
  }
  return Array.from(runIds);
}

export function getBenchmarkIbmBackends(
  capability: OptionalBackendCapability,
): BackendDeviceSummary[] {
  return (
    capability?.backends
      ?.filter((device) => device.name.trim().length > 0)
      .filter((device) => device.operational !== false) ?? []
  );
}

export function resolveBenchmarkBackendName(
  selectedBackendName: string | null | undefined,
  capability: OptionalBackendCapability,
): string | null {
  const devices = getBenchmarkIbmBackends(capability);
  if (
    selectedBackendName != null &&
    devices.some((device) => device.name === selectedBackendName)
  ) {
    return selectedBackendName;
  }
  return devices[0]?.name ?? null;
}

export function getBenchmarkBackendOptions(
  ibmCapability: OptionalBackendCapability,
  state: BenchmarkBackendOptionsState = {},
): BenchmarkBackendOption[] {
  const pending = state.pending === true;
  const ibmBackends = getBenchmarkIbmBackends(ibmCapability);
  const pendingReason = "Checking IBM backend availability...";
  let ibmUnavailableReason = ibmCapability?.reason ?? "IBM backend data is unavailable right now.";
  if (pending) {
    ibmUnavailableReason = pendingReason;
  } else if (ibmCapability?.credential_configured === false) {
    ibmUnavailableReason =
      "Activate an IBM profile in Settings to enable hardware-backed benchmarks.";
  }
  const ibmEnabled =
    ibmCapability?.enabled === true &&
    ibmCapability?.available !== false &&
    ibmCapability?.credential_configured !== false &&
    ibmBackends.length > 0;
  const pendingSuffix = pending && !ibmEnabled ? " (Checking IBM...)" : "";

  return [
    { value: "statevector", label: "Statevector (exact)", enabled: true },
    { value: "aer_simulator", label: "Aer simulator", enabled: true },
    {
      value: "aer_simulator_backend_noise",
      label: `Aer simulator with backend noise${pendingSuffix}`,
      warning: ibmEnabled
        ? ""
        : ibmUnavailableReason,
      enabled: ibmEnabled,
    },
    {
      value: "ibm_runtime",
      label: `IBM Quantum backend${pendingSuffix}`,
      ...(ibmEnabled ? {} : { warning: ibmUnavailableReason }),
      enabled: ibmEnabled,
    },
  ];
}

export function benchmarkModeToBackendTarget(mode: BenchmarkBackendMode): BackendTarget {
  return mode === "aer_simulator_backend_noise" ? "aer_simulator" : mode;
}

export function requiresIbmBackendSelection(mode: BenchmarkBackendMode): boolean {
  return mode === "aer_simulator_backend_noise" || mode === "ibm_runtime";
}

export function resolveBenchmarkBackendNameForMode(
  mode: BenchmarkBackendMode,
  selectedBackendName: string | null | undefined,
  capability: OptionalBackendCapability,
): string | null {
  if (!requiresIbmBackendSelection(mode)) return null;
  return resolveBenchmarkBackendName(selectedBackendName, capability);
}

export function requiresIbmConfirmation(mode: BenchmarkBackendMode): boolean {
  return mode === "ibm_runtime";
}

export function getBenchmarkMoleculeBlocker(preset: MoleculePreset): string | null {
  if (preset.multiplicity !== 1) {
    return "Only singlet molecules can run in the current benchmark rollout.";
  }

  if (!preset.active_space) {
    return "No active space is set; benchmark runs need a bounded active space first.";
  }

  const { n_electrons: nElectrons, n_orbitals: nOrbitals } = preset.active_space;
  if (nElectrons <= 0 || nOrbitals <= 0) {
    return "Active-space electrons and orbitals must be positive.";
  }
  if (nElectrons % 2 !== 0) {
    return "Odd active-space electron counts are not supported in this rollout.";
  }
  if (nElectrons > 2 * nOrbitals) {
    return "Active-space electrons cannot exceed twice the active orbitals.";
  }
  return null;
}

export function getBenchmarkAlgorithmBlockers(
  _presets: readonly MoleculePreset[],
  _backendMode?: BenchmarkBackendMode,
): Map<RunAlgorithm, string> {
  // Oversize projected-matrix runs (KQD/QFD/QSE beyond the noisy/hardware
  // orbital cap) are no longer blocked at selection. They can be selected and
  // submitted; the worker marks any oversize row EXCLUDED at execution rather
  // than failing, so smaller molecules in the same selection still run.
  return new Map<RunAlgorithm, string>();
}

export function moleculeToPreset(mol: MoleculeResponse): MoleculePreset {
  return {
    key: `custom:${mol.id}`,
    name: mol.name,
    formula: mol.iupac_name ?? mol.name,
    description: mol.description ?? "From molecule library",
    atoms: mol.atoms,
    charge: mol.charge,
    multiplicity: mol.multiplicity,
    active_space: mol.active_space,
    basis: "sto-3g",
    references: { hf: 0, fci: null, source: "unknown" },
  };
}

export function runStatusToEntryStatus(run: Pick<RunResponse, "status">): EntryStatus {
  switch (run.status) {
    case "CREATED":
    case "QUEUED":
    case "SUBMITTED_TO_IBM":
      return "queued";
    case "PAUSING":
      return "pausing";
    case "PAUSED":
      return "paused";
    case "RUNNING":
      return "running";
    case "COMPLETED":
      return "completed";
    case "FAILED":
      return "failed";
    case "CANCELLED":
      return "cancelled";
    case "EXCLUDED":
      return "excluded";
  }
}

export function normalizeStoredEntry(entry: BenchmarkEntry): BenchmarkEntry {
  const variantId =
    typeof entry.variantId === "string" && entry.variantId.trim().length > 0
      ? entry.variantId
      : entry.algorithm;
  const storedVariantLabel =
    typeof entry.variantLabel === "string" && entry.variantLabel.trim().length > 0
      ? entry.variantLabel
      : entry.algorithm.toUpperCase();
  const variantLabel = migrateLegacySimpleVariantLabel(entry, storedVariantLabel);
  const mode = resolveBenchmarkVariantMode(entry);
  const normalized = {
    ...entry,
    runId: entry.runId ?? null,
    variantId,
    variantLabel,
    mode,
    easyOptions: entry.easyOptions ?? null,
    advancedConfig: entry.advancedConfig ?? null,
    energy: entry.energy ?? null,
    currentEnergy: entry.currentEnergy ?? entry.energy ?? null,
    elapsedSeconds: entry.elapsedSeconds ?? null,
    executionMetadata: entry.executionMetadata ?? null,
    latestEventSequence: entry.latestEventSequence ?? 0,
  };

  return normalizeStoredEntryStatus(entry, normalized);
}

function migrateLegacySimpleVariantLabel(entry: BenchmarkEntry, label: string): string {
  const match = /^(?<algorithm>[a-z]+)\.easy\.(?<goal>fastest|balanced|best_accuracy)$/iu.exec(
    label.trim(),
  );
  if (match?.groups?.algorithm?.toLowerCase() !== entry.algorithm) {
    return label;
  }

  return formatEasyGoalLabel(match.groups.goal as "fastest" | "balanced" | "best_accuracy");
}

function normalizeStoredEntryStatus(
  entry: BenchmarkEntry,
  normalized: BenchmarkEntry,
): BenchmarkEntry {
  if (entry.runId)
    return hasQueuedStatus(entry.status) ? { ...normalized, status: "queued" } : normalized;
  const hasKnownStatus =
    entry.status === "idle" || TERMINAL.has(entry.status) || NON_EXECUTING.has(entry.status);
  return hasKnownStatus ? normalized : { ...normalized, status: "idle" };
}

function hasQueuedStatus(status: BenchmarkEntry["status"]): boolean {
  return status === "idle" || status === "acquiring_molecule" || status === "submitting";
}

export function shouldPollEntry(entry: BenchmarkEntry): entry is BenchmarkEntryWithRunId {
  return (
    typeof entry.runId === "string" &&
    entry.runId.length > 0 &&
    !TERMINAL.has(entry.status) &&
    entry.status !== "paused"
  );
}

export function shouldSyncBenchmarkEntryEvents(status: EntryStatus): boolean {
  return status === "running" || status === "pausing";
}

export function shouldPollBenchmarkEntryNow(
  entry: Pick<BenchmarkEntry, "status">,
  pollCycle: number,
): boolean {
  if (entry.status === "queued") {
    const queuedPollEveryCycles = Math.max(
      1,
      Math.round(QUEUED_POLL_INTERVAL_MS / RUNNING_POLL_INTERVAL_MS),
    );
    return pollCycle % queuedPollEveryCycles === 0;
  }
  return true;
}

export function buildInitialEntries(
  presets: readonly MoleculePreset[],
  variants: readonly BenchmarkAlgorithmVariant[],
): BenchmarkEntry[] {
  return presets.flatMap((preset) =>
    variants.map((variant) => ({
      id: `${preset.key}:${variant.algorithm}:${variant.id}`,
      preset,
      algorithm: variant.algorithm,
      variantId: variant.id,
      variantLabel: variant.label,
      mode: variant.mode,
      easyOptions:
        variant.mode === "simple" && variant.easyGoal ? { goal: variant.easyGoal } : null,
      advancedConfig: variant.mode === "advanced" ? variant.advancedConfig : null,
      status: "acquiring_molecule",
      moleculeId: null,
      runId: null,
      energy: null,
      currentEnergy: null,
      converged: null,
      errorMessage: null,
      classicalRefs: null,
      elapsedSeconds: null,
      executionMetadata: null,
      latestEventSequence: 0,
    })),
  );
}

export function extractClassicalRefs(
  metrics: Record<string, unknown> | null | undefined,
): { hf: number; fci: number } | null {
  if (!metrics) return null;
  const refs = metrics.classical_references as { hf?: number; fci?: number } | null | undefined;
  if (refs && typeof refs.hf === "number" && typeof refs.fci === "number") {
    return { hf: refs.hf, fci: refs.fci };
  }
  return null;
}

export function extractClassicalRefsFromEvents(
  events: Array<{ payload?: Record<string, unknown> | null }>,
): { hf: number; fci: number } | null {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const event = events[index];
    if (!event) continue;
    const payload = event.payload;
    if (!payload) continue;
    const hf = payload.hf_energy;
    const casci = payload.casci_energy;
    if (
      typeof hf === "number" &&
      Number.isFinite(hf) &&
      typeof casci === "number" &&
      Number.isFinite(casci)
    ) {
      return { hf, fci: casci };
    }
  }
  return null;
}

export function applyEntryUpdates(
  entries: readonly BenchmarkEntry[],
  updates: readonly PromiseSettledResult<BenchmarkEntryUpdate>[],
): BenchmarkEntry[] {
  const map = new Map(entries.map((entry) => [entry.id, entry]));
  for (const update of updates) {
    if (update.status === "fulfilled") {
      const { id, status, energy, converged, classicalRefs, errorMessage } = update.value;
      const { currentEnergy, elapsedSeconds, latestEventSequence } = update.value;
      const existing = map.get(id);
      if (!existing) {
        continue;
      }

      const isStaleProgressUpdate =
        latestEventSequence < existing.latestEventSequence &&
        !TERMINAL.has(existing.status) &&
        !TERMINAL.has(status);
      if (isStaleProgressUpdate) {
        continue;
      }

      const nextEntry = {
        ...existing,
        status,
        energy,
        currentEnergy,
        converged,
        classicalRefs,
        errorMessage,
        elapsedSeconds,
        executionMetadata: update.value.executionMetadata,
        latestEventSequence: Math.max(existing.latestEventSequence, latestEventSequence),
      };
      if (
        existing.status === nextEntry.status &&
        existing.energy === nextEntry.energy &&
        existing.currentEnergy === nextEntry.currentEnergy &&
        existing.converged === nextEntry.converged &&
        existing.errorMessage === nextEntry.errorMessage &&
        existing.elapsedSeconds === nextEntry.elapsedSeconds &&
        existing.latestEventSequence === nextEntry.latestEventSequence &&
        JSON.stringify(existing.classicalRefs) === JSON.stringify(nextEntry.classicalRefs) &&
        JSON.stringify(existing.executionMetadata) === JSON.stringify(nextEntry.executionMetadata)
      ) {
        continue;
      }
      map.set(id, nextEntry);
    }
  }
  return Array.from(map.values());
}

export function effectiveRefs(entry: BenchmarkEntry): {
  hf: number;
  fci: number | null;
  computed: boolean;
} {
  if (entry.classicalRefs) {
    return { hf: entry.classicalRefs.hf, fci: entry.classicalRefs.fci, computed: true };
  }
  const presetReferences = entry.preset.references;
  const hf = presetReferences?.hf;
  const fci = presetReferences?.fci;
  return {
    hf: typeof hf === "number" && Number.isFinite(hf) ? hf : 0,
    fci: typeof fci === "number" && Number.isFinite(fci) ? fci : null,
    computed: false,
  };
}

export function getBenchmarkEligibility(entry: BenchmarkEntry): {
  eligible: boolean;
  reason: BenchmarkEligibilityReason | null;
} {
  if (entry.status !== "completed") {
    return { eligible: false, reason: "not_completed" };
  }

  const metadata = entry.executionMetadata;
  if (metadata?.benchmarkEligible === false) {
    const directReason = metadata.benchmarkExclusionReason;
    if (directReason === "projected_solve_diagnostic") {
      return { eligible: false, reason: "projected_solve_diagnostic" };
    }
    if (directReason === "reported_energy_invalid") {
      return { eligible: false, reason: "reported_energy_invalid" };
    }
    if (directReason === "reference_provenance_unavailable") {
      return { eligible: false, reason: "reference_provenance_unavailable" };
    }
    return { eligible: false, reason: "scientific_convergence_not_established" };
  }
  if (metadata?.reportedEnergyIsValid === false) {
    return { eligible: false, reason: "reported_energy_invalid" };
  }
  if (entry.classicalRefs === null) {
    return { eligible: false, reason: "reference_provenance_unavailable" };
  }
  if (metadata?.projectedSolveIsDiagnostic === true) {
    return { eligible: false, reason: "projected_solve_diagnostic" };
  }
  if (metadata?.scientificConverged === false || entry.converged === false) {
    return { eligible: false, reason: "scientific_convergence_not_established" };
  }

  return { eligible: true, reason: null };
}

export function benchmarkEligibilityMessage(reason: BenchmarkEligibilityReason | null): string {
  switch (reason) {
    case "not_completed":
      return "row is not completed";
    case "reported_energy_invalid":
      return "reported energy is invalid";
    case "projected_solve_diagnostic":
      return "projected solve is diagnostic only";
    case "scientific_convergence_not_established":
      return "scientific convergence was not established";
    case "reference_provenance_unavailable":
      return "runtime CASCI reference provenance is unavailable";
    default:
      return "reference or energy data is unavailable";
  }
}

export function getBenchmarkEligibility(entry: BenchmarkEntry): {
  eligible: boolean;
  reason: BenchmarkEligibilityReason | null;
} {
  if (entry.status !== "completed") {
    return { eligible: false, reason: "not_completed" };
  }

  const metadata = entry.executionMetadata;
  if (metadata?.benchmarkEligible === false) {
    const directReason = metadata.benchmarkExclusionReason;
    if (directReason === "projected_solve_diagnostic") {
      return { eligible: false, reason: "projected_solve_diagnostic" };
    }
    if (directReason === "reported_energy_invalid") {
      return { eligible: false, reason: "reported_energy_invalid" };
    }
    if (directReason === "reference_provenance_unavailable") {
      return { eligible: false, reason: "reference_provenance_unavailable" };
    }
    return { eligible: false, reason: "scientific_convergence_not_established" };
  }
  if (metadata?.reportedEnergyIsValid === false) {
    return { eligible: false, reason: "reported_energy_invalid" };
  }
  if (entry.classicalRefs === null) {
    return { eligible: false, reason: "reference_provenance_unavailable" };
  }
  if (metadata?.projectedSolveIsDiagnostic === true) {
    return { eligible: false, reason: "projected_solve_diagnostic" };
  }
  if (metadata?.scientificConverged === false || entry.converged === false) {
    return { eligible: false, reason: "scientific_convergence_not_established" };
  }

  return { eligible: true, reason: null };
}

export function benchmarkEligibilityMessage(reason: BenchmarkEligibilityReason | null): string {
  switch (reason) {
    case "not_completed":
      return "row is not completed";
    case "reported_energy_invalid":
      return "reported energy is invalid";
    case "projected_solve_diagnostic":
      return "projected solve is diagnostic only";
    case "scientific_convergence_not_established":
      return "scientific convergence was not established";
    case "reference_provenance_unavailable":
      return "runtime CASCI reference provenance is unavailable";
    default:
      return "reference or energy data is unavailable";
  }
}

export function extractRunErrorMessage(run: RunResponse): string | null {
  const metadata = run.metadata;
  if (!metadata || typeof metadata !== "object") return null;
  const timeoutMessage = getTimedOutFailureMessage(metadata);
  if (timeoutMessage !== null) {
    return timeoutMessage;
  }
  const message = metadata["error_message"];
  if (typeof message === "string" && message.trim()) return message;
  return null;
}

export function getBenchmarkStats(entries: BenchmarkEntry[], chemicalAccuracyHa: number) {
  const total = entries.length;
  const done = entries.filter((entry) => TERMINAL.has(entry.status)).length;
  const completed = entries.filter((entry) => entry.status === "completed").length;
  const failed = entries.filter((entry) => entry.status === "failed").length;
  const cancelled = entries.filter((entry) => entry.status === "cancelled").length;
  let accurate = 0;
  let notAccurate = 0;
  let unscored = 0;
  let notConverged = 0;

  for (const entry of entries) {
    if (entry.status !== "completed" || entry.energy === null) continue;
    const assessment = assessBenchmarkEntry(entry, chemicalAccuracyHa);
    if (getBenchmarkEligibility(entry).reason === "scientific_convergence_not_established") {
      notConverged += 1;
    }
    if (!assessment.isScorable) {
      unscored += 1;
      continue;
    }
    if (assessment.verdict === "accurate") {
      accurate += 1;
    } else {
      notAccurate += 1;
    }
  }

  return {
    total,
    done,
    completed,
    failed,
    cancelled,
    accurate,
    notAccurate,
    unscored,
    notConverged,
  };
}

export function assessBenchmarkEntry(
  entry: BenchmarkEntry,
  chemicalAccuracyHa: number,
  energy = entry.energy,
): AccuracyAssessment {
  const refs = effectiveRefs(entry);
  const assessment = assessChemicalAccuracy({
    energy,
    hf: refs.hf,
    fci: refs.fci,
    thresholdHa: chemicalAccuracyHa,
    converged: entry.converged,
  });
  if (!getBenchmarkEligibility(entry).eligible) {
    return {
      ...assessment,
      verdict: "unscored",
      errorHa: null,
      errorMha: null,
      absErrorHa: null,
      absErrorMha: null,
      withinThreshold: false,
      correlationRecoveredPct: null,
      isScorable: false,
    };
  }
  return assessment;
}

export function sortBenchmarkRows(
  rows: BenchmarkEntry[],
  chemicalAccuracyHa: number,
  sortMode: BenchmarkAccuracySort,
): BenchmarkEntry[] {
  if (sortMode === "default") {
    return rows;
  }

  return [...rows].sort((left, right) => {
    const leftAssessment = assessBenchmarkEntry(left, chemicalAccuracyHa);
    const rightAssessment = assessBenchmarkEntry(right, chemicalAccuracyHa);

    const leftError = leftAssessment.absErrorHa ?? Number.POSITIVE_INFINITY;
    const rightError = rightAssessment.absErrorHa ?? Number.POSITIVE_INFINITY;
    if (leftError !== rightError) {
      return sortMode === "lowest_error" ? leftError - rightError : rightError - leftError;
    }
    return benchmarkEntryDisplayLabel(left).localeCompare(benchmarkEntryDisplayLabel(right));
  });
}

export function filterBenchmarkRows(
  rows: BenchmarkEntry[],
  chemicalAccuracyHa: number,
  filter: BenchmarkAccuracyFilter,
): BenchmarkEntry[] {
  if (filter === "all") {
    return rows;
  }
  return rows.filter((row) => assessBenchmarkEntry(row, chemicalAccuracyHa).verdict === filter);
}

function updateBenchmarkEntry(
  setEntries: (updater: (entries: BenchmarkEntry[]) => BenchmarkEntry[]) => void,
  entryId: string,
  patch: Partial<BenchmarkEntry>,
): void {
  setEntries((entries) =>
    entries.map((existing) => (existing.id === entryId ? { ...existing, ...patch } : existing)),
  );
}

function failedSubmitResult(
  entryId: string,
  errorMessage: string,
  moleculeId: UUID | null,
): BenchmarkSubmitResult {
  return {
    id: entryId,
    status: "failed",
    moleculeId,
    runId: null,
    errorMessage,
  };
}

function shouldRetryBenchmarkSubmit(error: unknown): boolean {
  if (!isApiErrorLike(error)) {
    return false;
  }

  return (
    error.code === "NETWORK_ERROR" ||
    error.code === "INVALID_RESPONSE" ||
    error.status === 0 ||
    error.status === 502 ||
    error.status === 503 ||
    error.status === 504
  );
}

export function formatBenchmarkSubmitError(error: unknown): string {
  if (error instanceof MoleculeAcquisitionError) {
    return error.message;
  }

  if (isApiErrorLike(error)) {
    if (error.code === "NETWORK_ERROR" || error.status === 0) {
      return "Unable to reach the API while creating this run. Refresh Benchmarks or Runs before retrying.";
    }

    if (error.code === "INVALID_RESPONSE") {
      return "The API returned an invalid response while creating this run. Refresh Benchmarks or Runs before retrying.";
    }

    if (
      error.status !== undefined &&
      error.status >= 500 &&
      getErrorMessage(error, GENERIC_BENCHMARK_SUBMIT_ERROR) === GENERIC_BENCHMARK_SUBMIT_ERROR
    ) {
      return `The API failed while creating this run (HTTP ${error.status}). Refresh Benchmarks or Runs before retrying.`;
    }
  }

  return getErrorMessage(error, GENERIC_BENCHMARK_SUBMIT_ERROR);
}

async function delayBenchmarkSubmitRetry(): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, BENCHMARK_SUBMIT_RETRY_DELAY_MS));
}

async function createBenchmarkRunWithRetry(
  config: Parameters<typeof createRun>[0],
): Promise<RunResponse> {
  try {
    return await createRun(config);
  } catch (error) {
    if (!shouldRetryBenchmarkSubmit(error)) {
      throw error;
    }

    await delayBenchmarkSubmitRetry();
    return createRun(config);
  }
}

export async function submitBenchmarkEntry(
  entry: BenchmarkEntry,
  molResult: UUID | MoleculeAcquisitionResult | Error | undefined,
  basis: string,
  execution: BenchmarkExecutionSettings,
  setEntries: (updater: (entries: BenchmarkEntry[]) => BenchmarkEntry[]) => void,
  options: { ibmRuntimeConfirmed?: boolean } = {},
): Promise<BenchmarkSubmitResult> {
  const blocker = getBenchmarkMoleculeBlocker(entry.preset);
  if (blocker) {
    updateBenchmarkEntry(setEntries, entry.id, { status: "failed", errorMessage: blocker });
    return failedSubmitResult(entry.id, blocker, null);
  }

  if (molResult instanceof Error || molResult === undefined) {
    const moleculeErrorMessage =
      molResult instanceof Error
        ? formatBenchmarkSubmitError(molResult)
        : "Molecule acquisition failed";
    updateBenchmarkEntry(setEntries, entry.id, {
      status: "failed",
      errorMessage: moleculeErrorMessage,
    });
    return failedSubmitResult(entry.id, moleculeErrorMessage, null);
  }
  const moleculeId = typeof molResult === "string" ? molResult : molResult.moleculeId;
  const clientRequestId = crypto.randomUUID();

  updateBenchmarkEntry(setEntries, entry.id, { status: "submitting", moleculeId });

  try {
    const { runId, status } = await createBenchmarkRunForEntry(
      entry,
      moleculeId,
      basis,
      execution,
      {
        ...options,
        clientRequestId,
      },
    );
    updateBenchmarkEntry(setEntries, entry.id, { status, runId });
    return {
      id: entry.id,
      status,
      moleculeId,
      runId,
      errorMessage: null,
    };
  } catch (err) {
    const message = formatBenchmarkSubmitError(err);
    updateBenchmarkEntry(setEntries, entry.id, { status: "failed", errorMessage: message });
    return failedSubmitResult(entry.id, message, moleculeId);
  }
}

export async function createBenchmarkRunForEntry(
  entry: BenchmarkEntry,
  moleculeId: UUID,
  basis: string,
  execution: BenchmarkExecutionSettings,
  options: { ibmRuntimeConfirmed?: boolean; clientRequestId?: string } = {},
): Promise<{ status: EntryStatus; runId: UUID; moleculeId: UUID }> {
  const config =
    entry.mode === "advanced" && entry.advancedConfig
      ? buildAdvancedBenchmarkRunConfig(
          entry.algorithm,
          basis,
          execution,
          entry.advancedConfig,
          options,
        )
      : buildSimpleBenchmarkRunConfig(
          entry.algorithm,
          basis,
          execution,
          entry.easyOptions?.goal ?? "balanced",
          options,
        );
  config.molecule_id = moleculeId;
  const run = await createBenchmarkRunWithRetry(config);
  return {
    status: runStatusToEntryStatus(run),
    runId: run.id,
    moleculeId,
  };
}
