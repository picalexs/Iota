import { Activity, AlertCircle, CheckCircle2, XCircle } from "lucide-react";

import { ConvergenceStatusIndicator } from "@/components/results/convergence-status-indicator";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  assessChemicalAccuracy,
  formatAccuracyVerdict,
  resolveChemicalAccuracyTargetHa,
} from "@/lib/results/accuracy";
import { getConvergenceInsight, type ConvergenceInsight } from "@/lib/results/convergence-status";
import { formatMeaningfulEta } from "@/lib/run-estimate-display";
import { extractClassicalReferences } from "@/lib/results/benchmarks";
import type { RunEventResponse, RunResponse, RunResultResponse } from "@/types/run";
import { getErrorPayloadText } from "./run-event-descriptor-utils";
import { IterationStat, OutcomeStat } from "./run-outcome-stats";
import { numberOrNull } from "./use-run-event-timeline";

interface RunOutcomeCardProps {
  readonly run: RunResponse;
  readonly events: RunEventResponse[];
  readonly result: RunResultResponse | null;
  readonly isRunning: boolean;
}

export function RunOutcomeCard({ run, events, result, isRunning }: RunOutcomeCardProps) {
  const outcome = buildRunOutcome(run, events, result, isRunning);

  return (
    <Card className="md:col-span-2 border-border/80">
      <CardHeader>
        <CardTitle className="text-sm flex items-center gap-2">
          <OutcomeIcon status={run.status} />
          Run Outcome
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <RunOutcomeContent outcome={outcome} />
      </CardContent>
    </Card>
  );
}

type OptionalNumber = number | null | undefined;

interface BuiltRunOutcome {
  run: RunResponse;
  result: RunResultResponse | null;
  progressProps: ProgressStatsProps;
  showActiveProgress: boolean;
  showProgressSnapshot: boolean;
  completedIterations: OptionalNumber;
  completedIterationLabel: string;
  displayMaxIterations: number;
  errorMessage: string;
  tracebackText: string | null;
  cancelledMessage: string;
  accuracy: ReturnType<typeof assessChemicalAccuracy> | null;
}

interface RunProgressSnapshot {
  isVqe: boolean;
  displayIteration: number | null;
  displayMaxIterations: number;
  hasProgressSnapshot: boolean;
  iterationLabel: string;
  bestEnergy: number | null;
  etaLabel: string;
  confidenceLabel: string;
}

function formatCompletedIterationLabel(
  completedIterations: OptionalNumber,
  fallback: string,
): string {
  if (completedIterations === null || completedIterations === undefined) return fallback;
  return String(completedIterations);
}

function formatNullableNumberLabel(value: number | null): string {
  if (value === null) return "—";
  return String(value);
}

function formatNullableEnergyLabel(value: number | null): string {
  if (value === null) return "—";
  return `${value.toFixed(6)} Ha`;
}

function formatConfidenceLabel(confidence: OptionalNumber): string {
  if (confidence === null || confidence === undefined) return "—";
  return `${Math.round(confidence * 100)}%`;
}

function primitiveText(value: unknown): string | null {
  if (typeof value === "string") {
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : null;
  }
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  if (typeof value === "boolean") return value ? "true" : "false";
  return null;
}

function buildRunOutcome(
  run: RunResponse,
  events: RunEventResponse[],
  result: RunResultResponse | null,
  isRunning: boolean,
): BuiltRunOutcome {
  const progress = getRunProgressSnapshot(run, events);
  const convergenceInsight = getConvergenceInsight(run, result, events);
  const completedIterations = getCompletedIterations(
    result,
    progress.isVqe,
    progress.displayIteration,
  );
  const errorDetails = getLatestErrorDetails(run, events);
  const showActiveProgress = isRunning && run.status !== "FAILED" && run.status !== "CANCELLED";

  return {
    run,
    result,
    progressProps: {
      isRunning,
      iterationLabel: progress.iterationLabel,
      displayIteration: progress.displayIteration,
      displayMaxIterations: progress.displayMaxIterations,
      iterationStatLabel: progress.isVqe ? "Objective evals" : "Iteration",
      bestEnergy: progress.bestEnergy,
      etaLabel: progress.etaLabel,
      confidenceLabel: progress.confidenceLabel,
      convergenceInsight,
    },
    showActiveProgress,
    showProgressSnapshot: progress.hasProgressSnapshot,
    completedIterations,
    completedIterationLabel: formatCompletedIterationLabel(
      completedIterations,
      progress.iterationLabel,
    ),
    displayMaxIterations: progress.displayMaxIterations,
    errorMessage: errorDetails.message,
    tracebackText: errorDetails.traceback,
    cancelledMessage: getCancelledMessage(progress.displayIteration),
    accuracy: getOutcomeAccuracy(run, result),
  };
}

function getRunProgressSnapshot(run: RunResponse, events: RunEventResponse[]): RunProgressSnapshot {
  const iterationEvents = events.filter((event) => event.type === "iteration_update");
  const latestProgress = iterationEvents.at(-1) ?? null;
  const latestEstimate = run.latest_estimate ?? null;
  const displayIteration =
    latestMonotonicIteration(iterationEvents) ?? getEstimatedCompletedIterations(latestEstimate);
  const bestEnergy = numberOrNull(latestProgress?.payload.energy);

  return {
    isVqe: run.algorithm === "vqe",
    displayIteration,
    displayMaxIterations: latestEstimate?.estimated_total_iterations ?? getMaxIterations(run),
    hasProgressSnapshot:
      displayIteration !== null || bestEnergy !== null || latestEstimate !== null,
    iterationLabel: formatNullableNumberLabel(displayIteration),
    bestEnergy,
    etaLabel:
      formatMeaningfulEta(
        latestEstimate?.estimated_remaining_seconds ?? null,
        latestEstimate?.confidence ?? null,
      ) ?? "—",
    confidenceLabel: formatConfidenceLabel(latestEstimate?.confidence),
  };
}

function getEstimatedCompletedIterations(estimate: RunResponse["latest_estimate"]): number | null {
  if (
    estimate?.estimated_total_iterations === null ||
    estimate?.estimated_total_iterations === undefined ||
    estimate.estimated_remaining_iterations === null ||
    estimate.estimated_remaining_iterations === undefined
  ) {
    return null;
  }
  return Math.max(0, estimate.estimated_total_iterations - estimate.estimated_remaining_iterations);
}

function getCancelledMessage(displayIteration: number | null): string {
  if (displayIteration === null) return "Cancelled before any iterations were recorded.";
  return `Cancelled after ${displayIteration} iterations.`;
}

function getOutcomeAccuracy(
  run: RunResponse,
  result: RunResultResponse | null,
): ReturnType<typeof assessChemicalAccuracy> | null {
  if (result === null) {
    return null;
  }

  const refs = extractClassicalReferences(result);
  return assessChemicalAccuracy({
    energy: result.energy,
    hf: refs.hf,
    fci: refs.fci,
    thresholdHa: resolveChemicalAccuracyTargetHa(run),
    converged: result.converged,
  });
}

function getLatestErrorDetails(
  run: RunResponse,
  events: RunEventResponse[],
): {
  message: string;
  traceback: string | null;
} {
  const errorEvent =
    events
      .slice()
      .reverse()
      .find((event) => event.type === "error") ?? null;

  if (errorEvent === null) {
    const metadataError = getRunMetadataErrorDetails(run);
    if (metadataError !== null) {
      return metadataError;
    }

    return {
      message: "The run failed without an error message.",
      traceback: null,
    };
  }

  const eventMessage = getErrorPayloadText(errorEvent.payload);
  if (eventMessage === "Unknown error") {
    const metadataError = getRunMetadataErrorDetails(run);
    if (metadataError !== null) {
      return metadataError;
    }
  }

  return {
    message: eventMessage,
    traceback: primitiveText(errorEvent.payload.traceback),
  };
}

function getRunMetadataErrorDetails(run: RunResponse): { message: string; traceback: null } | null {
  const metadata = run.metadata;
  if (metadata === null || typeof metadata !== "object" || Array.isArray(metadata)) {
    return null;
  }

  const message = getErrorPayloadText(metadata);
  if (message === "Unknown error") {
    return null;
  }

  return {
    message,
    traceback: null,
  };
}

function getCompletedIterations(
  result: RunResultResponse | null,
  isVqe: boolean,
  displayIteration: number | null,
): OptionalNumber {
  if (isVqe && typeof result?.algorithm_metrics?.objective_evaluations === "number") {
    return result.algorithm_metrics.objective_evaluations;
  }
  if (
    result?.iterations !== null &&
    result?.iterations !== undefined &&
    displayIteration !== null
  ) {
    return Math.max(result.iterations, displayIteration);
  }
  return result?.iterations;
}

function RunOutcomeContent({ outcome }: Readonly<{ outcome: BuiltRunOutcome }>) {
  return (
    <>
      {outcome.showActiveProgress && <ProgressStats {...outcome.progressProps} />}
      {outcome.run.status === "COMPLETED" && <CompletedOutcome outcome={outcome} />}
      {outcome.run.status === "FAILED" && <FailedOutcome outcome={outcome} />}
      {outcome.run.status === "CANCELLED" && <CancelledOutcome outcome={outcome} />}
    </>
  );
}

function CompletedOutcome({ outcome }: Readonly<{ outcome: BuiltRunOutcome }>) {
  if (outcome.result === null) {
    return <ProgressStats {...outcome.progressProps} />;
  }

  const { accuracy, completedIterations, displayMaxIterations, result } = outcome;
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
      <OutcomeStat
        label="Chemical accuracy"
        value={accuracy ? formatAccuracyVerdict(accuracy.verdict) : "Unscored"}
        helper={accuracy?.isScorable ? undefined : "No FCI/Exact reference available."}
      />
      <OutcomeStat label="Energy" value={`${result.energy.toFixed(6)} Ha`} />
      <IterationStat
        label={outcome.run.algorithm === "vqe" ? "Objective evals" : "Iterations"}
        value={outcome.completedIterationLabel}
        valueNow={completedIterations ?? null}
        valueMax={displayMaxIterations}
        showIncomplete={
          completedIterations !== null &&
          completedIterations !== undefined &&
          completedIterations < displayMaxIterations
        }
      />
      <OutcomeStat
        label="Converged"
        value={
          <ConvergenceStatusIndicator
            result={result}
            status={outcome.run.status}
            insight={outcome.progressProps.convergenceInsight}
          />
        }
      />
      <OutcomeStat
        label="Parameters"
        value={result.optimal_parameters.length}
        helper="optimal parameters"
      />
    </div>
  );
}

function FailedOutcome({ outcome }: Readonly<{ outcome: BuiltRunOutcome }>) {
  return (
    <>
      <p className="text-sm text-destructive">{outcome.errorMessage}</p>
      {outcome.showProgressSnapshot ? <ProgressStats {...outcome.progressProps} /> : null}
      {renderTracebackDetails(outcome.tracebackText)}
    </>
  );
}

function renderTracebackDetails(tracebackText: string | null) {
  if (tracebackText === null) return null;
  return <TracebackDetails tracebackText={tracebackText} />;
}

function TracebackDetails({ tracebackText }: Readonly<{ tracebackText: string }>) {
  return (
    <details className="mt-1 w-full">
      <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground transition-colors select-none">
        Show traceback
      </summary>
      <pre className="mt-2 text-xs bg-muted rounded-md p-3 overflow-auto max-h-48 whitespace-pre-wrap font-mono">
        {tracebackText}
      </pre>
    </details>
  );
}

function CancelledOutcome({ outcome }: Readonly<{ outcome: BuiltRunOutcome }>) {
  return (
    <>
      <p className="text-sm text-muted-foreground">{outcome.cancelledMessage}</p>
      {outcome.showProgressSnapshot ? <ProgressStats {...outcome.progressProps} /> : null}
    </>
  );
}

function latestMonotonicIteration(events: RunEventResponse[]): number | null {
  let offset = 0;
  let previousRaw: number | null = null;
  let previousDisplay: number | null = null;

  for (const event of events) {
    const raw =
      numberOrNull(event.payload.completed_iterations) ?? numberOrNull(event.payload.iteration);
    if (raw === null) continue;
    if (previousRaw !== null && raw < previousRaw) {
      offset = previousDisplay ?? previousRaw;
    }
    let display = offset + raw;
    if (previousDisplay !== null && display < previousDisplay) {
      display = previousDisplay;
    }
    previousRaw = raw;
    previousDisplay = display;
  }

  return previousDisplay;
}

function getMaxIterations(run: RunResponse): number {
  const estimateIterations =
    run.latest_estimate?.estimated_total_iterations ??
    run.initial_estimate?.estimated_total_iterations;
  if (isPositiveNumber(estimateIterations)) {
    return estimateIterations;
  }

  const config = run.config_json as Record<string, unknown>;
  const advancedConfig = objectRecord(config.advanced_config);
  if (run.algorithm === "vqe") {
    const evaluations = firstPositiveNumber(
      config.max_function_evaluations,
      advancedConfig?.max_function_evaluations,
    );
    if (evaluations !== null) {
      return evaluations;
    }
  }

  const configuredIterations = firstPositiveNumber(
    config.max_iterations,
    advancedConfig?.max_iterations,
    objectRecord(advancedConfig?.base_sampling_options)?.max_iterations,
  );
  if (configuredIterations !== null) {
    return configuredIterations;
  }

  return 0;
}

function objectRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null ? (value as Record<string, unknown>) : null;
}

function isPositiveNumber(value: unknown): value is number {
  return typeof value === "number" && value > 0;
}

function firstPositiveNumber(...values: unknown[]): number | null {
  return values.find(isPositiveNumber) ?? null;
}

function OutcomeIcon({ status }: Readonly<{ status: RunResponse["status"] }>) {
  if (status === "FAILED") return <AlertCircle className="size-4 text-destructive" />;
  if (status === "COMPLETED") return <CheckCircle2 className="size-4 text-success" />;
  if (status === "CANCELLED") return <XCircle className="size-4 text-muted-foreground" />;
  return <Activity className="size-4 text-warning" />;
}

interface ProgressStatsProps {
  readonly isRunning: boolean;
  readonly iterationLabel: string;
  readonly displayIteration: number | null;
  readonly displayMaxIterations: number;
  readonly iterationStatLabel: string;
  readonly bestEnergy: number | null;
  readonly etaLabel: string;
  readonly confidenceLabel: string;
  readonly convergenceInsight: ConvergenceInsight | null;
}

function ProgressStats({
  isRunning,
  iterationLabel,
  displayIteration,
  displayMaxIterations,
  iterationStatLabel,
  bestEnergy,
  etaLabel,
  confidenceLabel,
  convergenceInsight,
}: ProgressStatsProps) {
  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <IterationStat
          label={iterationStatLabel}
          value={iterationLabel}
          valueNow={displayIteration}
          valueMax={displayMaxIterations}
          showIncomplete={isRunning === false}
        />
        <OutcomeStat label="Energy" value={formatNullableEnergyLabel(bestEnergy)} />
        <OutcomeStat label="ETA" value={etaLabel} />
        <OutcomeStat label="Confidence" value={confidenceLabel} />
        <OutcomeStat
          label="Convergence"
          value={
            <ConvergenceStatusIndicator
              result={null}
              status={null}
              isRunning={isRunning}
              insight={convergenceInsight}
            />
          }
        />
      </div>
    </div>
  );
}
