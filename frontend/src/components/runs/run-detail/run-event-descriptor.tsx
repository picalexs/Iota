import { CheckCircle2, XCircle } from "lucide-react";
import type React from "react";

import { formatDuration } from "@/lib/format-duration";
import { formatRunStatusLine } from "@/lib/format-run-status";
import { getResultEventConvergenceLog } from "@/lib/results/convergence-status";
import { formatMeaningfulEta } from "@/lib/run-estimate-display";
import type { RunEstimate, RunEventType, RunResponse } from "@/types/run";
import {
  getErrorPayloadText,
  getSpecificIterationUpdatePresentation,
} from "./run-event-descriptor-utils";
import { numberOrNull } from "./use-run-event-timeline";

interface RunEventDescriptorProps {
  type: RunEventType;
  payload: Record<string, unknown>;
  estimate?: RunEstimate | null;
  verbose?: boolean;
  algorithm?: string | null;
}

interface ResolvedRunEventDescriptorProps extends Omit<
  RunEventDescriptorProps,
  "estimate" | "verbose" | "algorithm"
> {
  estimate: RunEstimate | null;
  verbose: boolean;
  algorithm: string | null;
}

type RunEventRenderer = (props: ResolvedRunEventDescriptorProps) => React.ReactNode;

const STATUS_DESCRIPTIONS: Partial<Record<RunResponse["status"], string>> = {
  RUNNING: "Run is executing",
  PAUSING: "Pause requested",
  QUEUED: "Waiting in job queue",
  PAUSED: "Run is paused",
  COMPLETED: "Finished successfully",
  FAILED: "Encountered an error",
  CANCELLED: "Run was cancelled",
  EXCLUDED: "Excluded: unsupported on the selected target",
  SUBMITTED_TO_IBM: "IBM Quantum job is pending",
  CREATED: "Run was created",
};

const VERBOSE_DETAIL_ORDER = [
  "message",
  "step",
  "status",
  "evaluation",
  "delta_energy",
  "selected_fraction",
  "selected_samples",
  "occupancy_delta",
  "postselection_weight",
  "batch_energy",
  "selected_ci_dimension",
  "candidate_norm",
  "parameter_l2_norm",
  "time_point",
  "basis_dimension",
  "overlap_condition",
  "basis_rank",
  "krylov_rank",
  "subspace_dim",
  "max_iterations",
];

const HIDDEN_VERBOSE_DETAIL_KEYS = new Set([
  "algorithm",
  "stage",
  "iteration",
  "energy",
  "remaining_seconds",
]);

function toScalarLabel(value: unknown): string | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return Number.isInteger(value) ? String(value) : value.toFixed(6);
  }

  if (typeof value === "boolean") {
    return value ? "true" : "false";
  }

  if (typeof value === "string" && value.trim().length > 0) {
    return value;
  }

  return null;
}

function toPayloadTextOrNull(value: unknown): string | null {
  if (typeof value === "string") {
    return value;
  }

  if (typeof value === "number" || typeof value === "boolean" || typeof value === "bigint") {
    return String(value);
  }

  return null;
}

function toPayloadText(value: unknown, fallback: string): string {
  return toPayloadTextOrNull(value) ?? fallback;
}

function buildVerboseDetails(
  payload: Record<string, unknown>,
  extraOrder: string[],
): React.ReactNode | null {
  const details: Array<{ label: string; value: string }> = [];
  const included = new Set<string>();

  for (const key of extraOrder) {
    const value = toScalarLabel(payload[key]);
    if (value === null) {
      continue;
    }
    included.add(key);
    details.push({ label: key.replaceAll("_", " "), value });
  }

  for (const [key, rawValue] of Object.entries(payload)) {
    if (included.has(key) || HIDDEN_VERBOSE_DETAIL_KEYS.has(key)) {
      continue;
    }

    const value = toScalarLabel(rawValue);
    if (value === null) {
      continue;
    }

    details.push({ label: key.replaceAll("_", " "), value });
  }

  if (details.length === 0) {
    return null;
  }

  return (
    <div className="mt-1 flex flex-wrap gap-1">
      {details.map((detail) => (
        <span
          key={`${detail.label}:${detail.value}`}
          className="rounded bg-muted px-1.5 py-0.5 text-[11px] text-foreground/85"
        >
          <span className="text-muted-foreground">{detail.label}: </span>
          <span className="font-medium">{detail.value}</span>
        </span>
      ))}
    </div>
  );
}

function getTimingNumber(payload: Record<string, unknown>, key: string): number | null {
  const timing = payload.ibm_timing;
  if (typeof timing !== "object" || timing === null || Array.isArray(timing)) {
    return null;
  }

  return numberOrNull((timing as Record<string, unknown>)[key]);
}

function localIteration(payload: Record<string, unknown>): number | null {
  return (
    numberOrNull(payload.phase_iteration) ??
    numberOrNull(payload.display_iteration) ??
    numberOrNull(payload.iteration)
  );
}

function renderIterationUpdate({
  payload,
  estimate,
  verbose,
  algorithm,
}: ResolvedRunEventDescriptorProps): React.ReactNode {
  const specificPresentation = getSpecificIterationUpdatePresentation(payload, estimate, algorithm);
  const estimatedRemainingSeconds = estimate?.estimated_remaining_seconds ?? null;
  const estimatedEtaLabel = formatMeaningfulEta(
    estimatedRemainingSeconds,
    estimate?.confidence ?? null,
  );
  const summary =
    specificPresentation?.summary ??
    formatRunStatusLine({
      iteration: localIteration(payload),
      totalIterations: estimate?.estimated_total_iterations ?? null,
      energy: numberOrNull(payload.energy),
      remainingIterations: null,
      remainingSeconds: estimatedEtaLabel === null ? null : estimatedRemainingSeconds,
      iterationLabel: "Iteration",
    }) ??
    "Progress update recorded";

  if (verbose) {
    return (
      <div className="text-xs text-muted-foreground">
        <span>{summary}</span>
        {buildVerboseDetails(payload, VERBOSE_DETAIL_ORDER)}
      </div>
    );
  }

  return <span className="text-xs text-muted-foreground">{summary}</span>;
}

function renderStatusChanged({ payload }: ResolvedRunEventDescriptorProps): React.ReactNode {
  const statusValue = toPayloadText(payload.status, "UNKNOWN");
  const exclusionDetail =
    statusValue === "EXCLUDED"
      ? (toPayloadText(payload.exclusion_message, "") ||
          toPayloadText(payload.exclusion_reason, "") ||
          null)
      : null;
  const description = exclusionDetail ?? STATUS_DESCRIPTIONS[statusValue as RunResponse["status"]];

  return (
    <span className="text-xs text-muted-foreground">
      {"-> "}
      <span className="text-foreground font-medium text-xs uppercase">{statusValue}</span>
      {description && <span className="ml-1.5 text-muted-foreground/70">· {description}</span>}
    </span>
  );
}

function renderEstimateUpdated({
  payload,
  estimate,
}: ResolvedRunEventDescriptorProps): React.ReactNode {
  const remainingIterations =
    estimate?.estimated_remaining_iterations ??
    numberOrNull(payload.estimated_remaining_iterations);
  const remainingSeconds =
    estimate?.estimated_remaining_seconds ?? numberOrNull(payload.estimated_remaining_seconds);
  const confidence = estimate?.confidence ?? numberOrNull(payload.confidence);
  const etaLabel = formatMeaningfulEta(remainingSeconds, confidence);

  return (
    <span className="text-xs text-muted-foreground">
      Remaining{" "}
      <span className="text-foreground font-medium tabular-nums">{remainingIterations ?? "-"}</span>
      {" iterations"}
      {etaLabel != null && (
        <>
          {" · "}
          ETA <span className="text-foreground font-medium">{etaLabel}</span>
        </>
      )}
      {confidence != null && (
        <>
          {" · "}
          Confidence{" "}
          <span className="text-foreground font-medium">{Math.round(confidence * 100)}%</span>
        </>
      )}
    </span>
  );
}

function renderError({ payload }: ResolvedRunEventDescriptorProps): React.ReactNode {
  return (
    <span className="text-xs text-destructive truncate max-w-xs block">
      {getErrorPayloadText(payload)}
    </span>
  );
}

function renderResult({ payload, verbose }: ResolvedRunEventDescriptorProps): React.ReactNode {
  const energy = numberOrNull(payload.energy);
  const converged = payload.converged as boolean;
  const convergenceLog = getResultEventConvergenceLog(payload);
  const summary = (
    <span className="text-xs text-muted-foreground">
      Energy <span className="text-foreground font-mono">{energy?.toFixed(6) ?? "—"}</span> Ha
      {converged ? (
        <>
          {" · "}
          <CheckCircle2 className="inline size-3 text-success" /> Converged
        </>
      ) : (
        <>
          {" · "}
          <XCircle className="inline size-3 text-destructive" /> Not converged
        </>
      )}
      {convergenceLog?.summary ? <span className="ml-1.5">· {convergenceLog.summary}</span> : null}
    </span>
  );

  if (!verbose || !convergenceLog?.details) {
    return summary;
  }

  return (
    <div className="text-xs text-muted-foreground">
      {summary}
      <div className="mt-1 text-[11px] text-muted-foreground/80">{convergenceLog.details}</div>
    </div>
  );
}

function renderIbmJobSubmitted({ payload }: ResolvedRunEventDescriptorProps): React.ReactNode {
  const ibmJobId =
    typeof payload.ibm_job_id === "string" && payload.ibm_job_id.length > 0
      ? payload.ibm_job_id
      : null;
  const backendName =
    typeof payload.backend === "string" && payload.backend.length > 0 ? payload.backend : null;

  return (
    <span className="text-xs text-muted-foreground">
      IBM Quantum job pending.{" "}
      {ibmJobId && (
        <>
          ID: <code className="font-mono text-foreground text-xs">{ibmJobId}</code>
        </>
      )}
      {backendName && (
        <span className="ml-1.5">
          · Backend: <span className="text-foreground font-medium">{backendName}</span>
        </span>
      )}
    </span>
  );
}

function renderIbmStatusPoll({ payload }: ResolvedRunEventDescriptorProps): React.ReactNode {
  const pendingSeconds = getTimingNumber(payload, "pending_seconds");
  const usageSeconds = getTimingNumber(payload, "usage_seconds");
  const totalSeconds = getTimingNumber(payload, "total_seconds");
  const ibmStatus = toPayloadText(payload.ibm_status, "—");
  const queuedCount = toPayloadTextOrNull(payload.queued_count);

  return (
    <span className="text-xs text-muted-foreground">
      IBM backend status: <span className="text-foreground font-medium">{ibmStatus}</span>
      {queuedCount === null ? null : (
        <span className="ml-1.5">· Queue position: {queuedCount}</span>
      )}
      {payload.elapsed_seconds != null && (
        <span className="ml-1.5">
          · Elapsed: {formatDuration(numberOrNull(payload.elapsed_seconds))}
        </span>
      )}
      {usageSeconds != null && (
        <span className="ml-1.5">· Usage: {formatDuration(usageSeconds)}</span>
      )}
      {pendingSeconds != null && (
        <span className="ml-1.5">· Pending: {formatDuration(pendingSeconds)}</span>
      )}
      {totalSeconds != null && (
        <span className="ml-1.5">· Total: {formatDuration(totalSeconds)}</span>
      )}
    </span>
  );
}

const EVENT_RENDERERS: Partial<Record<RunEventType, RunEventRenderer>> = {
  iteration_update: renderIterationUpdate,
  status_changed: renderStatusChanged,
  estimate_updated: renderEstimateUpdated,
  error: renderError,
  result: renderResult,
  ibm_job_submitted: renderIbmJobSubmitted,
  ibm_status_poll: renderIbmStatusPoll,
};

export function RunEventDescriptor({
  type,
  payload,
  estimate = null,
  verbose = false,
  algorithm = null,
}: RunEventDescriptorProps) {
  const render = EVENT_RENDERERS[type];

  if (render == null) {
    return null;
  }

  return render({
    type,
    payload,
    estimate,
    verbose,
    algorithm,
  });
}
