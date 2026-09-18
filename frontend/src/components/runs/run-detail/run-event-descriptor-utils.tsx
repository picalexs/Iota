import {
  Activity,
  ArrowRightCircle,
  Atom,
  CheckCircle2,
  Cpu,
  FlaskConical,
  Grid3x3,
  Layers,
  Orbit,
  Radio,
  Search,
  Send,
  Sigma,
  Sparkles,
  Waves,
  XCircle,
  Zap,
} from "lucide-react";
import type React from "react";

import { getResultEventConvergenceLog } from "@/lib/results/convergence-status";
import { formatMeaningfulEta } from "@/lib/run-estimate-display";
import { getTimedOutFailureMessage } from "@/lib/run-failure";
import type { RunEstimate, RunEventType } from "@/types/run";
import { numberOrNull } from "./use-run-event-timeline";

export const EVENT_ICONS: Record<RunEventType, React.ReactNode> = {
  status_changed: <ArrowRightCircle className="size-3.5 text-info" />,
  iteration_update: <Activity className="size-3.5 text-warning" />,
  control_requested: <Activity className="size-3.5 text-info" />,
  checkpoint_saved: <CheckCircle2 className="size-3.5 text-success" />,
  resume_enqueued: <Activity className="size-3.5 text-info" />,
  restart_created: <Sparkles className="size-3.5 text-[var(--chart-4)]" />,
  error: <XCircle className="size-3.5 text-destructive" />,
  result: <CheckCircle2 className="size-3.5 text-success" />,
  ibm_job_submitted: <Send className="size-3.5 text-[var(--chart-4)]" />,
  ibm_status_poll: <Radio className="size-3.5 text-muted-foreground" />,
  estimate_updated: <Activity className="size-3.5 text-info" />,
};

export const EVENT_LABELS: Record<RunEventType, string> = {
  status_changed: "Status Changed",
  iteration_update: "Iteration",
  control_requested: "Control Requested",
  checkpoint_saved: "Checkpoint Saved",
  resume_enqueued: "Resume Enqueued",
  restart_created: "Restart Created",
  error: "Error",
  result: "Result",
  ibm_job_submitted: "IBM Job Submitted",
  ibm_status_poll: "IBM Status Poll",
  estimate_updated: "Estimate Updated",
};

interface IterationUpdatePresentation {
  icon: React.ReactNode;
  label: string;
  summary: string | null;
}

function projectedEnergyStateMessage(energyState: unknown): string | null {
  if (energyState === "provisional") {
    return "Provisional retained-subspace energy";
  }
  if (energyState === "unavailable") {
    return "Projected energy unavailable";
  }
  return null;
}

interface IterationUpdateContext {
  payload: Record<string, unknown>;
  stage: string | null;
  step: string | null;
  iterationAlgorithm: string | null;
  eta: string | null;
  energy: string | null;
  diagnosticEnergy: string | null;
  matrixElementValue: string | null;
  message: string | null;
  algorithm?: string | null;
}

type IterationUpdateFormatter = (
  context: IterationUpdateContext,
) => IterationUpdatePresentation | null;

function getTrimmedString(value: unknown): string | null {
  return typeof value === "string" && value.trim().length > 0 ? value.trim() : null;
}

function normalizeAlgorithm(value: unknown): string | null {
  const text = getTrimmedString(value);
  if (text === null) return null;
  return text.toLowerCase();
}

function resolveIterationAlgorithm(
  payload: Record<string, unknown>,
  algorithm?: string | null,
): string | null {
  return normalizeAlgorithm(payload.algorithm) ?? normalizeAlgorithm(algorithm);
}

function formatEnergy(value: unknown): string | null {
  const energy = numberOrNull(value);
  if (energy === null) return null;
  return `Energy ${energy.toFixed(6)} Ha`;
}

function formatDiagnosticEnergy(payload: Record<string, unknown>): string | null {
  if (payload.energy_state !== "diagnostic") return null;
  const energy = formatEnergy(payload.diagnostic_energy);
  return energy === null ? null : energy.replace(/^Energy /, "Diagnostic energy ");
}

function formatEta(
  remainingSeconds: number | null | undefined,
  confidence: number | null | undefined,
): string | null {
  const etaLabel = formatMeaningfulEta(remainingSeconds, confidence);
  if (etaLabel == null) return null;
  return `ETA ${etaLabel}`;
}

function formatPrimitive(value: unknown): string | null {
  if (typeof value === "string") {
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : null;
  }
  if (typeof value === "number" && Number.isFinite(value)) return `${value}`;
  if (typeof value === "boolean") return value ? "true" : "false";
  return null;
}

function formatPrimitiveSegment(
  value: unknown,
  prefix: string,
  suffix = "",
  fallback: string | null = null,
): string | null {
  const formatted = formatPrimitive(value);
  if (formatted === null) return fallback;
  return `${prefix}${formatted}${suffix}`;
}

function formatBatchSegment(
  payload: Record<string, unknown>,
  fallback: string | null = null,
): string | null {
  const batch = formatPrimitive(payload.sci_batch);
  const batches = formatPrimitive(payload.sci_batches);
  if (batch === null || batches === null) return fallback;
  return `Batch ${batch}/${batches}`;
}

function buildIterationUpdateContext(
  payload: Record<string, unknown>,
  estimate?: RunEstimate | null,
  algorithm?: string | null,
): IterationUpdateContext {
  return {
    payload,
    stage: getTrimmedString(payload.stage),
    step: getTrimmedString(payload.step),
    iterationAlgorithm: resolveIterationAlgorithm(payload, algorithm),
    eta: formatEta(estimate?.estimated_remaining_seconds ?? null, estimate?.confidence ?? null),
    energy: formatEnergy(payload.energy),
    diagnosticEnergy: formatDiagnosticEnergy(payload),
    matrixElementValue: formatEnergy(payload.matrix_element_value),
    message: getTrimmedString(payload.message),
    algorithm,
  };
}

function localIteration(payload: Record<string, unknown>): number | null {
  return (
    numberOrNull(payload.phase_iteration) ??
    numberOrNull(payload.display_iteration) ??
    numberOrNull(payload.iteration)
  );
}

function localCompletedIterations(payload: Record<string, unknown>): number | null {
  return (
    numberOrNull(payload.phase_completed_iterations) ??
    numberOrNull(payload.display_iteration) ??
    numberOrNull(payload.completed_iterations) ??
    localIteration(payload)
  );
}

function pairLabel(payload: Record<string, unknown>): string | null {
  const pair = payload.matrix_element_pair;
  if (Array.isArray(pair) && pair.length >= 2) {
    const left = pair[0];
    const right = pair[1];
    if (typeof left === "number" && typeof right === "number") {
      return `Pair (${left}, ${right})`;
    }
  }
  return null;
}

function chunkLabel(payload: Record<string, unknown>): string | null {
  const chunk = payload.estimator_pub_chunk;
  if (Array.isArray(chunk) && chunk.length >= 2) {
    const start = chunk[0];
    const end = chunk[1];
    if (typeof start === "number" && typeof end === "number") {
      return `PUBs ${start}-${end}`;
    }
  }
  return null;
}

function joinSegments(...segments: Array<string | null | undefined>): string | null {
  const filtered = segments.filter((segment): segment is string =>
    Boolean(segment && segment.length > 0),
  );
  return filtered.length > 0 ? filtered.join(" · ") : null;
}

function sqdIterationPrefix(
  payload: Record<string, unknown>,
  runAlgorithm?: string | null,
): string {
  const iteration = localIteration(payload);
  const prefix = normalizeAlgorithm(runAlgorithm) === "skqd" ? "SQD core iter" : "SQD iter";
  if (iteration == null) return prefix;
  return `${prefix} ${iteration}`;
}

function formatProgressLabel(label: string, current: number, total: number | null): string {
  const totalSuffix = total == null ? "" : `/${total}`;
  return `${label} ${current}${totalSuffix}`;
}

function formatProgressLabelOrFallback(
  label: string,
  current: number | null,
  total: number | null,
  fallback: string,
): string {
  if (current === null) return fallback;
  return formatProgressLabel(label, current, total);
}

function formatIterationSummary(prefix: string, value: number | null, fallback: string): string {
  if (value === null) return fallback;
  return `${prefix} ${value}`;
}

function humanizeHardwareStatus(status: string): string {
  return status
    .split("_")
    .map((part) =>
      part.length > 0 ? `${part.charAt(0).toUpperCase()}${part.slice(1).toLowerCase()}` : part,
    )
    .join(" ");
}

function humanizeNullableHardwareStatus(status: string | null): string | null {
  if (status === null) return null;
  return humanizeHardwareStatus(status);
}

function humanizeHardwareStatusOrFallback(status: string | null, fallback: string): string {
  if (status === null) return fallback;
  return humanizeHardwareStatus(status);
}

function formatExcitationKind(payload: Record<string, unknown>): string | null {
  const excitationKind = getTrimmedString(payload.excitation_kind);
  if (excitationKind == null) return null;
  return `${excitationKind.replaceAll("_", " ")} excitation`;
}

function formatSetupPresentation(
  context: IterationUpdateContext,
): IterationUpdatePresentation | null {
  if (context.stage === "setup" && context.step === "backend_selected") {
    return {
      icon: <Cpu className="size-3.5 text-info" />,
      label: "Backend selected",
      summary: context.message ?? "Backend selected for run execution",
    };
  }

  if (context.stage === "setup" && context.step === "hamiltonian_building") {
    return {
      icon: <FlaskConical className="size-3.5 text-info" />,
      label: "Hamiltonian build",
      summary: context.message ?? "Building molecular Hamiltonian",
    };
  }

  if (context.stage === "setup") {
    return {
      icon: <Atom className="size-3.5 text-success" />,
      label: "Chemistry ready",
      summary:
        context.message ??
        joinSegments(
          formatPrimitiveSegment(context.payload.num_qubits, "", " qubits"),
          formatPrimitiveSegment(context.payload.num_spatial_orbitals, "", " orbitals"),
          context.energy,
        ) ??
        "Chemistry setup completed",
    };
  }

  return null;
}

function formatVqeOptimizePresentation(
  context: IterationUpdateContext,
): IterationUpdatePresentation | null {
  if (context.iterationAlgorithm === "vqe" && context.step === "optimize") {
    const iteration = localIteration(context.payload);
    const objective = getTrimmedString(context.payload.objective);

    return {
      icon: <Zap className="size-3.5 text-warning" />,
      label: "Objective eval",
      summary: joinSegments(
        formatIterationSummary("Objective eval", iteration, "Objective evaluation"),
        context.energy,
        context.eta,
        objective,
      ),
    };
  }

  return null;
}

function formatQseReferencePresentation(
  context: IterationUpdateContext,
): IterationUpdatePresentation | null {
  if (context.iterationAlgorithm === "qse" && context.step === "reference_vqe") {
    const evaluation = localIteration(context.payload);

    return {
      icon: <Zap className="size-3.5 text-warning" />,
      label: "Reference VQE",
      summary: joinSegments(
        formatIterationSummary("Reference eval", evaluation, "Optimizing reference state"),
        context.energy,
        context.eta,
      ),
    };
  }

  return null;
}

function formatQseBasisPresentation(
  context: IterationUpdateContext,
): IterationUpdatePresentation | null {
  if (context.iterationAlgorithm === "qse" && context.step === "build_basis") {
    const basisVector = localCompletedIterations(context.payload);
    const maxSubspace = numberOrNull(context.payload.total_iterations);

    return {
      icon: <Layers className="size-3.5 text-[var(--chart-4)]" />,
      label: "Excitation basis",
      summary: joinSegments(
        formatProgressLabelOrFallback(
          "Basis vector",
          basisVector,
          maxSubspace,
          "Building excitation basis",
        ),
        formatExcitationKind(context.payload),
        context.energy,
        context.eta,
      ),
    };
  }

  return null;
}

function formatQseMeasuredMatrixElementsPresentation(
  context: IterationUpdateContext,
): IterationUpdatePresentation | null {
  if (
    context.iterationAlgorithm === "qse" &&
    context.step === "measured_matrix_elements" &&
    context.stage !== "completed"
  ) {
    const step = localCompletedIterations(context.payload);
    const total = numberOrNull(context.payload.total_iterations);

    return {
      icon: <Layers className="size-3.5 text-[var(--chart-4)]" />,
      label: "Measurement step",
      summary: joinSegments(
        formatProgressLabelOrFallback(
          "Measurement step",
          step,
          total,
          "Measuring projected matrix elements",
        ),
        formatPrimitiveSegment(context.payload.matrix_element_pair, "Pair "),
        context.eta,
      ),
    };
  }

  return null;
}

function formatQseSolvePresentation(
  context: IterationUpdateContext,
): IterationUpdatePresentation | null {
  if (
    context.iterationAlgorithm === "qse" &&
    (context.step === "solve" || context.stage === "completed")
  ) {
    return {
      icon: <Sigma className="size-3.5 text-success" />,
      label: "Subspace solve",
      summary: joinSegments(
        formatPrimitiveSegment(
          context.payload.subspace_dim,
          "Subspace dim ",
          "",
          "Subspace solve complete",
        ),
        context.energy,
      ),
    };
  }

  return null;
}

function formatSqdSamplingPresentation(
  context: IterationUpdateContext,
): IterationUpdatePresentation | null {
  if (context.iterationAlgorithm === "sqd" && context.step === "sampling") {
    const sampleSetReused = context.payload.sample_set_reused === true;
    return {
      icon: <Waves className="size-3.5 text-info" />,
      label: sampleSetReused ? "Measured set reused" : "Sampling",
      summary: joinSegments(
        sqdIterationPrefix(context.payload, context.algorithm),
        sampleSetReused
          ? formatPrimitiveSegment(
              context.payload.total_samples,
              "Reusing ",
              " measured samples",
              "Reusing the measured sample set",
            )
          : formatPrimitiveSegment(
              context.payload.total_samples,
              "Sampling ",
              " samples",
              "Sampling bitstrings",
            ),
        context.eta,
      ),
    };
  }

  return null;
}

function formatSqdPostselectionPresentation(
  context: IterationUpdateContext,
): IterationUpdatePresentation | null {
  if (context.iterationAlgorithm === "sqd" && context.step === "postselection") {
    return {
      icon: <Search className="size-3.5 text-warning" />,
      label: "Postselection",
      summary: joinSegments(
        sqdIterationPrefix(context.payload, context.algorithm),
        formatPrimitiveSegment(
          context.payload.selected_samples,
          "Selected ",
          " configs",
          "Filtering bitstrings",
        ),
        context.eta,
      ),
    };
  }

  return null;
}

function formatSqdSelectedCiSolvePresentation(
  context: IterationUpdateContext,
): IterationUpdatePresentation | null {
  if (context.iterationAlgorithm === "sqd" && context.step === "selected_ci_solve") {
    return {
      icon: <Layers className="size-3.5 text-[var(--chart-4)]" />,
      label: "Selected-CI solve",
      summary: joinSegments(
        sqdIterationPrefix(context.payload, context.algorithm),
        formatBatchSegment(context.payload, "Building selected-CI batch"),
        formatPrimitiveSegment(context.payload.selected_ci_dimension, "Dim "),
        context.eta,
      ),
    };
  }

  return null;
}

function formatSqdBatchCompletedPresentation(
  context: IterationUpdateContext,
): IterationUpdatePresentation | null {
  if (context.iterationAlgorithm === "sqd" && context.step === "selected_ci_batch_completed") {
    return {
      icon: <Grid3x3 className="size-3.5 text-[var(--chart-5)]" />,
      label: "Batch energy",
      summary: joinSegments(
        sqdIterationPrefix(context.payload, context.algorithm),
        formatBatchSegment(context.payload),
        formatEnergy(context.payload.batch_energy ?? context.payload.energy),
        context.eta,
      ),
    };
  }

  return null;
}

function formatSqdRecoveryPresentation(
  context: IterationUpdateContext,
): IterationUpdatePresentation | null {
  if (context.iterationAlgorithm === "sqd" && context.step === "configuration_recovery") {
    return {
      icon: <Sparkles className="size-3.5 text-success" />,
      label: normalizeAlgorithm(context.algorithm) === "skqd" ? "SQD core recovery" : "Recovery",
      summary: joinSegments(
        sqdIterationPrefix(context.payload, context.algorithm),
        context.energy,
        formatPrimitiveSegment(context.payload.selected_samples, "", " accepted"),
        context.eta,
      ),
    };
  }

  return null;
}

function formatHardwareMatrixPresentation(
  context: IterationUpdateContext,
): IterationUpdatePresentation | null {
  if (context.step === "hardware_matrix_elements") {
    const statusText = getTrimmedString(context.payload.status);
    const current = localCompletedIterations(context.payload);
    const total = numberOrNull(context.payload.total_iterations);

    return {
      icon: <Cpu className="size-3.5 text-info" />,
      label: "Matrix element",
      summary: joinSegments(
        humanizeNullableHardwareStatus(statusText),
        formatProgressLabelOrFallback(
          "Matrix element",
          current,
          total,
          "Matrix element measurement",
        ),
        pairLabel(context.payload),
        chunkLabel(context.payload),
        context.matrixElementValue
          ? context.matrixElementValue.replace(/^Energy /, "H diagonal ")
          : context.energy,
        context.eta,
      ),
    };
  }

  return null;
}

function formatProjectedSubspacePresentation(
  context: IterationUpdateContext,
): IterationUpdatePresentation | null {
  if (context.step === "projected_subspace_progress") {
    return {
      icon: <Layers className="size-3.5 text-[var(--chart-4)]" />,
      label: "Projected solve",
      summary: joinSegments(
        formatPrimitiveSegment(
          context.payload.basis_rank,
          "Projected rank ",
          "",
          "Projected solve",
        ),
        projectedEnergyStateMessage(context.payload.energy_state),
        context.energy,
        context.eta,
      ),
    };
  }

  return null;
}

function formatKqdTimeEvolutionPresentation(
  context: IterationUpdateContext,
): IterationUpdatePresentation | null {
  if (context.iterationAlgorithm === "kqd" && context.step === "time_evolution") {
    const timePoint = localIteration(context.payload);
    const total = numberOrNull(context.payload.total_iterations);

    return {
      icon: <Orbit className="size-3.5 text-info" />,
      label: "Krylov state",
      summary: joinSegments(
        formatProgressLabelOrFallback("Time point", timePoint, total, "Building Krylov basis"),
        formatPrimitiveSegment(context.payload.time_point, "t="),
        context.energy,
        context.eta,
      ),
    };
  }

  return null;
}

function formatKqdSolvePresentation(
  context: IterationUpdateContext,
): IterationUpdatePresentation | null {
  if (
    context.iterationAlgorithm === "kqd" &&
    (context.step === "solve" || context.stage === "completed")
  ) {
    return {
      icon: <Sigma className="size-3.5 text-success" />,
      label: "Krylov solve",
      summary: joinSegments(
        formatPrimitiveSegment(
          context.payload.basis_rank,
          "Basis rank ",
          "",
          "Krylov solve complete",
        ),
        context.energy ?? context.diagnosticEnergy,
      ),
    };
  }

  return null;
}

function formatQfdTimeEvolutionPresentation(
  context: IterationUpdateContext,
): IterationUpdatePresentation | null {
  if (context.iterationAlgorithm === "qfd" && context.step === "time_evolution") {
    const timePoint = localIteration(context.payload);
    const total = numberOrNull(context.payload.total_iterations);

    return {
      icon: <Waves className="size-3.5 text-info" />,
      label: "Time point",
      summary: joinSegments(
        formatProgressLabelOrFallback("Time point", timePoint, total, "Filter time point"),
        formatPrimitiveSegment(context.payload.time_point, "t="),
        context.energy,
        context.eta,
      ),
    };
  }

  return null;
}

function formatQfdSolvePresentation(
  context: IterationUpdateContext,
): IterationUpdatePresentation | null {
  if (
    context.iterationAlgorithm === "qfd" &&
    (context.step === "solve" || context.stage === "completed")
  ) {
    return {
      icon: <Sigma className="size-3.5 text-success" />,
      label: "Filter solve",
      summary: joinSegments(
        formatPrimitiveSegment(
          context.payload.total_iterations,
          "",
          " time points",
          "Filter solve complete",
        ),
        context.energy ?? context.diagnosticEnergy,
      ),
    };
  }

  return null;
}

function formatSkqdExtensionPresentation(
  context: IterationUpdateContext,
): IterationUpdatePresentation | null {
  if (context.iterationAlgorithm === "skqd" && context.step === "krylov_extension") {
    const basisVector = localCompletedIterations(context.payload);
    const total = numberOrNull(context.payload.total_iterations);

    return {
      icon: <Orbit className="size-3.5 text-info" />,
      label: "Krylov extension",
      summary: joinSegments(
        formatProgressLabelOrFallback("Extension vector", basisVector, total, "Extending SQD core"),
        context.energy,
        context.eta,
      ),
    };
  }

  return null;
}

function formatControlStagePresentation(
  context: IterationUpdateContext,
): IterationUpdatePresentation | null {
  if (context.stage === "control") {
    const control = getTrimmedString(context.payload.control);
    const controlLabel = humanizeHardwareStatusOrFallback(control, "Control request");

    return {
      icon: <Cpu className="size-3.5 text-info" />,
      label: controlLabel,
      summary: joinSegments(context.message, context.eta) ?? "Awaiting remote control response",
    };
  }

  return null;
}

function formatRestartStagePresentation(
  context: IterationUpdateContext,
): IterationUpdatePresentation | null {
  if (context.stage === "restart" || context.stage === "resubmission") {
    return {
      icon: <Sparkles className="size-3.5 text-[var(--chart-4)]" />,
      label: context.stage === "restart" ? "Restarted" : "Resubmitted",
      summary: joinSegments(context.message, context.energy, context.eta) ?? "Run was restarted",
    };
  }

  return null;
}

function formatCheckpointStagePresentation(
  context: IterationUpdateContext,
): IterationUpdatePresentation | null {
  if (context.stage === "checkpoint") {
    return {
      icon: <CheckCircle2 className="size-3.5 text-success" />,
      label: "Checkpoint saved",
      summary: joinSegments(context.message, context.eta) ?? "Saved an intermediate checkpoint",
    };
  }

  return null;
}

function formatResultStagePresentation(
  context: IterationUpdateContext,
): IterationUpdatePresentation | null {
  if (context.stage === "result") {
    const convergence =
      typeof context.payload.method === "string"
        ? getResultEventConvergenceLog(context.payload)
        : null;

    return {
      icon: <CheckCircle2 className="size-3.5 text-success" />,
      label: "Result ready",
      summary: joinSegments(context.message, convergence?.summary) ?? "Result data available",
    };
  }

  return null;
}

function formatHardwareStagePresentation(
  context: IterationUpdateContext,
): IterationUpdatePresentation | null {
  if (context.stage === "hardware") {
    const status = getTrimmedString(context.payload.status);

    return {
      icon: <Radio className="size-3.5 text-muted-foreground" />,
      label: humanizeHardwareStatusOrFallback(status, "Hardware status"),
      summary: joinSegments(context.message, context.eta) ?? "Hardware event received",
    };
  }

  return null;
}

function formatErrorStagePresentation(
  context: IterationUpdateContext,
): IterationUpdatePresentation | null {
  if (context.stage === "error") {
    return {
      icon: <XCircle className="size-3.5 text-destructive" />,
      label: "Error",
      summary:
        joinSegments(context.message, getTrimmedString(context.payload.error)) ??
        "Run error encountered",
    };
  }

  return null;
}

const ITERATION_UPDATE_FORMATTERS: IterationUpdateFormatter[] = [
  formatSetupPresentation,
  formatVqeOptimizePresentation,
  formatQseReferencePresentation,
  formatQseBasisPresentation,
  formatQseMeasuredMatrixElementsPresentation,
  formatQseSolvePresentation,
  formatSqdSamplingPresentation,
  formatSqdPostselectionPresentation,
  formatSqdSelectedCiSolvePresentation,
  formatSqdBatchCompletedPresentation,
  formatSqdRecoveryPresentation,
  formatHardwareMatrixPresentation,
  formatProjectedSubspacePresentation,
  formatKqdTimeEvolutionPresentation,
  formatKqdSolvePresentation,
  formatQfdTimeEvolutionPresentation,
  formatQfdSolvePresentation,
  formatSkqdExtensionPresentation,
  formatControlStagePresentation,
  formatRestartStagePresentation,
  formatCheckpointStagePresentation,
  formatResultStagePresentation,
  formatHardwareStagePresentation,
  formatErrorStagePresentation,
];

function resolveSpecificIterationUpdatePresentation(
  context: IterationUpdateContext,
): IterationUpdatePresentation | null {
  for (const formatPresentation of ITERATION_UPDATE_FORMATTERS) {
    const presentation = formatPresentation(context);
    if (presentation != null) {
      return presentation;
    }
  }

  return null;
}

export function getSpecificIterationUpdatePresentation(
  payload: Record<string, unknown>,
  estimate?: RunEstimate | null,
  algorithm?: string | null,
): IterationUpdatePresentation | null {
  return resolveSpecificIterationUpdatePresentation(
    buildIterationUpdateContext(payload, estimate, algorithm),
  );
}

function buildFallbackIterationUpdatePresentation(
  context: IterationUpdateContext,
): IterationUpdatePresentation {
  const fallbackLabel = EVENT_LABELS.iteration_update;

  return {
    icon: <Activity className="size-3.5 text-info" />,
    label: fallbackLabel,
    summary: joinSegments(context.message, context.energy, context.eta) ?? fallbackLabel,
  };
}

export function getIterationUpdateLabel(
  payload: Record<string, unknown>,
  algorithm?: string | null,
): string {
  return getIterationUpdatePresentation(payload, null, algorithm).label;
}

export function getIterationUpdatePresentation(
  payload: Record<string, unknown>,
  estimate?: RunEstimate | null,
  algorithm?: string | null,
): IterationUpdatePresentation {
  const context = buildIterationUpdateContext(payload, estimate, algorithm);
  return (
    resolveSpecificIterationUpdatePresentation(context) ??
    buildFallbackIterationUpdatePresentation(context)
  );
}

export function getErrorPayloadText(payload: Record<string, unknown>): string {
  const timeoutMessage = getTimedOutFailureMessage(payload);
  if (timeoutMessage !== null) {
    return timeoutMessage;
  }

  const primaryDetails = [
    payload.summary,
    payload.message,
    payload.error_message,
    payload.detail,
    payload.error_detail,
    payload.reason,
    payload.error,
    payload.stack,
  ]
    .map((entry) => (typeof entry === "string" ? entry.trim() : ""))
    .filter((entry) => entry.length > 0)
    .filter((entry, index, values) => values.indexOf(entry) === index);

  const secondaryDetails = [payload.error_type]
    .map((entry) => (typeof entry === "string" ? entry.trim() : ""))
    .filter((entry) => entry.length > 0)
    .filter((entry, index, values) => values.indexOf(entry) === index);

  if (primaryDetails.length > 0) {
    return [...primaryDetails, ...secondaryDetails].join("\n\n");
  }

  return secondaryDetails.length > 0 ? secondaryDetails.join("\n\n") : "Unknown error";
}
