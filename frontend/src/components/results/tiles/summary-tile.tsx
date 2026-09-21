import type { ReactNode } from "react";
import { Link } from "@tanstack/react-router";
import { Badge } from "@/components/ui/badge";
import { ConvergenceStatusIndicator } from "@/components/results/convergence-status-indicator";
import { DashboardTile } from "@/components/results/dashboard-tile";
import { SummaryTileLoadingContent } from "@/components/results/tile-loading-content";
import { assessChemicalAccuracy, formatAccuracyVerdict } from "@/lib/results/accuracy";
import { getConvergenceInsight } from "@/lib/results/convergence-status";
import { formatSelectionPolicy, getRunExecutionMetadata } from "@/lib/results/execution-metadata";
import { cn } from "@/lib/utils";
import type {
  AlgorithmMetrics,
  MoleculeResponse,
  RunEventResponse,
  RunResponse,
  RunResultResponse,
} from "@/types/run";
import { formatDuration } from "@/lib/format-duration";

type OptionalString = string | null | undefined;
type AccuracyAssessment = ReturnType<typeof assessChemicalAccuracy>;
type ExecutionMetadata = ReturnType<typeof getRunExecutionMetadata>;

interface SummaryTileProps {
  readonly run: RunResponse;
  readonly result: RunResultResponse | null;
  readonly events: RunEventResponse[];
  readonly molecule?: MoleculeResponse | null;
  readonly currentIteration?: number | null;
  readonly currentEnergy?: number | null;
  readonly liveBestEnergy?: number | null;
  readonly runtimeSeconds?: number | null;
  readonly hfEnergy?: number;
  readonly fciEnergy?: number;
  readonly chemicalAccuracyHa: number;
  readonly isRunning?: boolean;
  readonly pending?: boolean;
  readonly editMode?: boolean;
}

function hasValue<T>(value: T | null | undefined): value is NonNullable<T> {
  if (value === null) {
    return false;
  }
  if (value === undefined) {
    return false;
  }
  return true;
}

function numberMetric(metrics: AlgorithmMetrics | null | undefined, key: string): number | null {
  const value = metrics?.[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  if (typeof value === "object" && hasValue(value)) {
    if (Array.isArray(value)) {
      return false;
    }
    return true;
  }

  return false;
}

function recordMetric(
  metrics: AlgorithmMetrics | null | undefined,
  key: string,
): Record<string, unknown> | null {
  const value = metrics?.[key];
  return isRecord(value) ? value : null;
}

function isNonEmptyString(value: OptionalString): value is string {
  return typeof value === "string" && value.length > 0;
}

function formatEnumLabel(value: OptionalString): string {
  if (isNonEmptyString(value)) {
    return value
      .replaceAll("_", " ")
      .replace(/\b\w/g, (letter) => letter.toUpperCase())
      .replace(/\bIbm\b/g, "IBM")
      .replace(/\bAer\b/g, "Aer");
  }

  return "—";
}

function formatBackendTarget(value: OptionalString): string {
  switch (value) {
    case "statevector":
      return "Statevector";
    case "aer_simulator":
      return "Aer simulator";
    case "ibm_runtime":
      return "IBM Runtime";
    default:
      return formatEnumLabel(value);
  }
}

function normalizeLowercase(value: OptionalString): string | null {
  return value ? value.trim().toLowerCase() : null;
}

function verdictClasses(verdict: AccuracyAssessment["verdict"]): string {
  switch (verdict) {
    case "accurate":
      return "border-success/45 bg-success/15 text-success";
    case "not_accurate":
      return "border-destructive/45 bg-destructive/15 text-destructive";
    case "unscored":
      return "border-warning/45 bg-warning/15 text-warning";
  }
}

interface SummaryMetricProps {
  readonly label: string;
  readonly value: ReactNode;
  readonly helper?: ReactNode;
  readonly className?: string;
  readonly valueClassName?: string;
}

interface SummaryMetricHelperProps {
  readonly helper?: ReactNode;
}

function SummaryMetricHelper({ helper }: SummaryMetricHelperProps) {
  if (helper) {
    return <dd className="mt-1 text-[11px] leading-snug text-muted-foreground">{helper}</dd>;
  }

  return null;
}

function SummaryMetric({ label, value, helper, className, valueClassName }: SummaryMetricProps) {
  return (
    <div className={cn("flex min-w-0 flex-col", className)}>
      <dt className="text-[11px] font-medium text-muted-foreground">{label}</dt>
      <dd className={cn("mt-1 min-w-0 text-sm font-semibold leading-tight", valueClassName)}>
        {value}
      </dd>
      <SummaryMetricHelper helper={helper} />
    </div>
  );
}

function getNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function getString(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function getActiveSpaceLabel(value: unknown): string | null {
  if (Array.isArray(value) && value.length >= 2) {
    return `(${value[0]}e, ${value[1]}o)`;
  }
  return getString(value);
}

function formatAccuracyDeltaText(
  accuracy: AccuracyAssessment,
  fciEnergy: number | undefined,
): string | null {
  const absErrorMha = accuracy.absErrorMha;

  if (accuracy.isScorable && hasValue(fciEnergy) && hasValue(absErrorMha)) {
    const thresholdMha = accuracy.thresholdHa * 1000;
    const deltaFromThresholdMha = absErrorMha - thresholdMha;
    if (!accuracy.withinThreshold) {
      return `+${deltaFromThresholdMha.toFixed(2)} mHa over ${thresholdMha.toFixed(2)} mHa threshold`;
    }

    return `${absErrorMha.toFixed(2)} mHa difference from CASCI active-space · ${Math.abs(
      deltaFromThresholdMha,
    ).toFixed(2)} mHa under ${thresholdMha.toFixed(2)} mHa threshold`;
  }

  return null;
}

function resolveIterationValue(
  result: RunResultResponse | null,
  currentIteration: number | null | undefined,
  objectiveEvaluations: number | null,
): number | null {
  if (hasValue(objectiveEvaluations)) {
    return objectiveEvaluations;
  }

  if (hasValue(result?.iterations) && hasValue(currentIteration)) {
    return Math.max(result.iterations, currentIteration);
  }

  return result?.iterations ?? currentIteration ?? null;
}

function getEnergyPolicySummary(result: RunResultResponse | null) {
  const energyPolicy =
    result?.energy_policy ?? recordMetric(result?.algorithm_metrics, "energy_policy");

  return {
    energySource:
      typeof energyPolicy?.primary_energy_source === "string"
        ? formatEnumLabel(energyPolicy.primary_energy_source)
        : null,
    energyPolicyRule:
      typeof energyPolicy?.selection_rule === "string" ? energyPolicy.selection_rule : undefined,
  };
}

function getSetupPayload(events: RunEventResponse[]): RunEventResponse["payload"] | undefined {
  return events.find(
    (event) => event.type === "iteration_update" && event.payload["stage"] === "setup",
  )?.payload;
}

function buildRuntimeSummary(
  run: RunResponse,
  execution: ExecutionMetadata,
  runtimeSeconds: number | null | undefined,
) {
  const ibmTiming = execution.ibmTiming;
  const totalSeconds = ibmTiming?.totalSeconds;
  const usageSeconds = ibmTiming?.usageSeconds;
  const pendingSeconds = ibmTiming?.pendingSeconds;
  const hasIbmTotal = hasValue(totalSeconds);
  const primaryRuntimeSeconds = totalSeconds ?? usageSeconds ?? runtimeSeconds ?? null;

  let runtimeLabel = "Runtime";
  if (hasIbmTotal) {
    runtimeLabel = "IBM total";
  } else if (hasValue(usageSeconds)) {
    runtimeLabel = "IBM usage";
  } else if (run.status === "SUBMITTED_TO_IBM") {
    runtimeLabel = "IBM pending";
  }

  const runtimeHelperParts: string[] = [];
  if (hasIbmTotal && hasValue(usageSeconds)) {
    runtimeHelperParts.push(`Usage ${formatDuration(usageSeconds)}`);
  }
  if (hasValue(pendingSeconds)) {
    runtimeHelperParts.push(`Pending ${formatDuration(pendingSeconds)}`);
  }

  return {
    runtimeLabel,
    primaryRuntimeSeconds,
    runtimeHelper: runtimeHelperParts.length > 0 ? runtimeHelperParts.join(" · ") : null,
  };
}

function getCredentialProfileLabel(run: RunResponse): string | null {
  if (hasValue(run.credential_profile_name)) {
    return hasValue(run.credential_profile_id)
      ? run.credential_profile_name
      : `${run.credential_profile_name} (Deleted)`;
  }

  return null;
}

function pushMetric(details: SummaryMetricProps[], detail: SummaryMetricProps | null) {
  if (hasValue(detail)) {
    details.push(detail);
  }
}

function metricFromValue<T>(
  value: T | null | undefined,
  buildMetric: (definedValue: NonNullable<T>) => SummaryMetricProps,
): SummaryMetricProps | null {
  return hasValue(value) ? buildMetric(value) : null;
}

function getBackendDeviceMetric(
  execution: ExecutionMetadata,
  run: RunResponse,
): SummaryMetricProps | null {
  if (hasValue(execution.backendName)) {
    if (execution.backendName === run.backend_target) {
      return null;
    }

    return {
      label: "Device",
      value: execution.backendName,
      valueClassName: "font-mono text-xs",
    };
  }

  return null;
}

function getSimulatorMethodMetric(
  execution: ExecutionMetadata,
  showSimulatorMethod: boolean,
): SummaryMetricProps | null {
  if (showSimulatorMethod) {
    return { label: "Simulator method", value: execution.simulatorMethod };
  }

  return null;
}

function getExecutionDeviceMetric(execution: ExecutionMetadata): SummaryMetricProps | null {
  if (!hasValue(execution.actualDevice)) return null;
  const requested =
    hasValue(execution.requestedDevice) && execution.requestedDevice !== execution.actualDevice
      ? ` (requested ${execution.requestedDevice})`
      : "";
  return { label: "Execution device", value: `${execution.actualDevice}${requested}` };
}

function renderCredentialProfileValue(run: RunResponse, profileLabel: string): ReactNode {
  if (hasValue(run.credential_profile_id)) {
    return (
      <Link to="/settings" className="text-primary hover:underline">
        {profileLabel}
      </Link>
    );
  }

  return profileLabel;
}

function buildCoreExecutionDetails({
  execution,
  run,
  policyLabel,
  numQubits,
  numOrbitals,
  activeSpaceLabel,
  basisSet,
  pipeline,
  nuclearRepulsion,
  showSimulatorMethod,
}: {
  readonly execution: ExecutionMetadata;
  readonly run: RunResponse;
  readonly policyLabel: string;
  readonly numQubits: number | null;
  readonly numOrbitals: number | null;
  readonly activeSpaceLabel: string | null;
  readonly basisSet: string | null;
  readonly pipeline: string | null;
  readonly nuclearRepulsion: number | null;
  readonly showSimulatorMethod: boolean;
}): SummaryMetricProps[] {
  const details: SummaryMetricProps[] = [{ label: "Policy", value: policyLabel }];

  pushMetric(details, getBackendDeviceMetric(execution, run));
  pushMetric(details, getExecutionDeviceMetric(execution));
  pushMetric(
    details,
    metricFromValue(execution.shots, (shots) => ({
      label: "Shots",
      value: shots.toLocaleString(),
    })),
  );
  pushMetric(
    details,
    metricFromValue(numQubits, (qubits) => ({
      label: "Qubits",
      value: qubits.toLocaleString(),
      valueClassName: "tabular-nums",
    })),
  );
  pushMetric(
    details,
    metricFromValue(numOrbitals, (orbitals) => ({
      label: "Spatial orbitals",
      value: orbitals.toLocaleString(),
      valueClassName: "tabular-nums",
    })),
  );
  pushMetric(
    details,
    metricFromValue(activeSpaceLabel, (label) => ({ label: "Active space", value: label })),
  );
  pushMetric(
    details,
    metricFromValue(basisSet, (value) => ({ label: "Basis set", value })),
  );
  pushMetric(
    details,
    metricFromValue(pipeline, (value) => ({ label: "Pipeline", value })),
  );
  pushMetric(
    details,
    metricFromValue(nuclearRepulsion, (repulsion) => ({
      label: "Nuclear repulsion",
      value: `${repulsion.toFixed(6)} Ha`,
      valueClassName: "font-mono text-xs",
    })),
  );
  pushMetric(
    details,
    metricFromValue(execution.depth, (depth) => ({
      label: "Depth",
      value: depth.toLocaleString(),
      valueClassName: "tabular-nums",
    })),
  );
  pushMetric(
    details,
    metricFromValue(execution.twoQubitDepth, (depth) => ({
      label: "2Q depth",
      value: depth.toLocaleString(),
      valueClassName: "tabular-nums",
    })),
  );
  pushMetric(
    details,
    metricFromValue(execution.optimizationLevel, (level) => ({
      label: "Optimization",
      value: String(level),
    })),
  );
  pushMetric(
    details,
    metricFromValue(execution.aerMethod, (method) => ({ label: "Aer method", value: method })),
  );
  pushMetric(details, getSimulatorMethodMetric(execution, showSimulatorMethod));
  pushMetric(
    details,
    metricFromValue(execution.primitiveFamily, (family) => ({
      label: "Primitive family",
      value: family,
    })),
  );

  return details;
}

function buildIbmExecutionDetails(
  execution: ExecutionMetadata,
  run: RunResponse,
  credentialProfileLabel: string | null,
): SummaryMetricProps[] {
  const details: SummaryMetricProps[] = [];

  pushMetric(
    details,
    metricFromValue(execution.ibmStatus, (status) => ({ label: "IBM status", value: status })),
  );
  pushMetric(
    details,
    metricFromValue(credentialProfileLabel, (profileLabel) => ({
      label: "IBM Account",
      value: renderCredentialProfileValue(run, profileLabel),
    })),
  );
  pushMetric(
    details,
    metricFromValue(execution.ibmQueuePosition, (position) => ({
      label: "Queue position",
      value: position.toLocaleString(),
    })),
  );
  pushMetric(
    details,
    metricFromValue(execution.ibmPubCount, (pubCount) => ({
      label: "PUBs",
      value: pubCount.toLocaleString(),
    })),
  );
  pushMetric(
    details,
    metricFromValue(execution.seedSimulator, (seed) => ({
      label: "Simulator seed",
      value: String(seed),
    })),
  );
  pushMetric(
    details,
    metricFromValue(execution.seedTranspiler, (seed) => ({
      label: "Transpiler seed",
      value: String(seed),
    })),
  );
  pushMetric(
    details,
    metricFromValue(execution.ibmJobId, (jobId) => ({
      label: "IBM Job ID",
      value: <code className="break-all text-[10px]">{jobId}</code>,
      valueClassName: "font-mono",
    })),
  );

  return details;
}

function buildExecutionDetails(args: {
  readonly execution: ExecutionMetadata;
  readonly run: RunResponse;
  readonly policyLabel: string;
  readonly numQubits: number | null;
  readonly numOrbitals: number | null;
  readonly activeSpaceLabel: string | null;
  readonly basisSet: string | null;
  readonly pipeline: string | null;
  readonly nuclearRepulsion: number | null;
  readonly showSimulatorMethod: boolean;
  readonly credentialProfileLabel: string | null;
}): SummaryMetricProps[] {
  return [
    ...buildCoreExecutionDetails(args),
    ...buildIbmExecutionDetails(args.execution, args.run, args.credentialProfileLabel),
  ];
}

function formatPolicyLabel(execution: ExecutionMetadata): string {
  if (hasValue(execution.selectionPolicy)) {
    return formatEnumLabel(formatSelectionPolicy(execution.selectionPolicy));
  }

  return "—";
}

function shouldShowSimulatorMethod(
  simulatorMethod: OptionalString,
  backendTarget: OptionalString,
): boolean {
  if (hasValue(simulatorMethod)) {
    const simulatorMethodValue = normalizeLowercase(simulatorMethod);
    const backendTargetValue = normalizeLowercase(backendTarget);
    if (simulatorMethodValue === backendTargetValue) {
      return false;
    }

    return true;
  }

  return false;
}

function buildSummaryTileModel({
  run,
  result,
  events,
  molecule,
  currentIteration,
  currentEnergy,
  liveBestEnergy,
  runtimeSeconds,
  hfEnergy,
  fciEnergy,
  chemicalAccuracyHa,
  isRunning,
}: SummaryTileProps) {
  const execution = getRunExecutionMetadata(run, events, result);
  const isVqe = run.algorithm === "vqe";
  const objectiveEvaluations = numberMetric(result?.algorithm_metrics, "objective_evaluations");
  const optimizerIterations = numberMetric(result?.algorithm_metrics, "optimizer_iterations");
  const iterationValue = resolveIterationValue(result, currentIteration, objectiveEvaluations);
  const energyValue = result?.energy ?? currentEnergy ?? null;
  const accuracyEnergy = result?.energy ?? liveBestEnergy ?? currentEnergy ?? null;
  const { energySource, energyPolicyRule } = getEnergyPolicySummary(result);
  const accuracy = assessChemicalAccuracy({
    energy: accuracyEnergy,
    hf: hfEnergy,
    fci: fciEnergy,
    thresholdHa: chemicalAccuracyHa,
    converged: result?.converged ?? null,
  });

  const algorithmLabel = run.algorithm ? run.algorithm.toUpperCase() : "—";
  const backendLabel = formatBackendTarget(run.backend_target);
  const modeLabel = formatEnumLabel(run.mode);
  const policyLabel = formatPolicyLabel(execution);
  const setup = getSetupPayload(events);
  const metadata = run.metadata;
  const config = run.config_json;
  const numQubits =
    execution.qubits ?? getNumber(setup?.["num_qubits"]) ?? getNumber(metadata?.["num_qubits"]);
  const numOrbitals = getNumber(setup?.["num_spatial_orbitals"]);
  const activeSpaceLabel = getActiveSpaceLabel(setup?.["active_space"]);
  const pipeline = getString(setup?.["chemistry_pipeline"]);
  const nuclearRepulsion = getNumber(setup?.["nuclear_repulsion"]);
  const basisSet =
    config.basis_set_override ?? config.basis_set ?? run.basis_set ?? molecule?.basis_set ?? null;
  const { runtimeLabel, primaryRuntimeSeconds, runtimeHelper } = buildRuntimeSummary(
    run,
    execution,
    runtimeSeconds,
  );
  const accuracyDeltaText = formatAccuracyDeltaText(accuracy, fciEnergy);
  const showSimulatorMethod = shouldShowSimulatorMethod(
    execution.simulatorMethod,
    run.backend_target,
  );
  const convergenceInsight = getConvergenceInsight(run, result, events);
  const credentialProfileLabel = getCredentialProfileLabel(run);
  const executionDetails = buildExecutionDetails({
    execution,
    run,
    policyLabel,
    numQubits,
    numOrbitals,
    activeSpaceLabel,
    basisSet,
    pipeline,
    nuclearRepulsion,
    showSimulatorMethod,
    credentialProfileLabel,
  });

  return {
    run,
    result,
    molecule,
    isVqe,
    algorithmLabel,
    backendLabel,
    modeLabel,
    accuracy,
    accuracyDeltaText,
    energyValue,
    energySource,
    energyPolicyRule,
    convergenceInsight,
    iterationValue,
    runtimeLabel,
    primaryRuntimeSeconds,
    runtimeHelper,
    optimizerIterations,
    executionDetails,
    isRunning,
  };
}

interface SummaryHeaderProps {
  readonly run: RunResponse;
  readonly molecule?: MoleculeResponse | null;
  readonly algorithmLabel: string;
  readonly backendLabel: string;
  readonly modeLabel: string;
}

function renderMoleculeValue(run: RunResponse, molecule?: MoleculeResponse | null): ReactNode {
  if (hasValue(molecule) && hasValue(run.molecule_id)) {
    return (
      <Link
        to="/molecules/$moleculeId"
        params={{ moleculeId: run.molecule_id }}
        className="block truncate text-primary hover:underline"
      >
        {molecule.name}
      </Link>
    );
  }

  return "—";
}

function SummaryHeader({
  run,
  molecule,
  algorithmLabel,
  backendLabel,
  modeLabel,
}: SummaryHeaderProps) {
  return (
    <div className="grid gap-3 border-b border-border/60 pb-2.5 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
      <SummaryMetric
        label="Molecule"
        className="min-w-40 flex-1"
        value={renderMoleculeValue(run, molecule)}
        valueClassName="text-xl"
      />
      <div className="flex flex-wrap items-center justify-start gap-x-4 gap-y-1 text-sm lg:justify-end">
        <span className="font-bold text-muted-foreground">{algorithmLabel}</span>
        <span className="font-medium text-muted-foreground">{backendLabel}</span>
        <span className="font-medium text-muted-foreground">{modeLabel}</span>
      </div>
    </div>
  );
}

interface EnergySourceLabelProps {
  readonly energySource: string | null;
  readonly energyPolicyRule: string | undefined;
}

function EnergySourceLabel({ energySource, energyPolicyRule }: EnergySourceLabelProps) {
  if (isNonEmptyString(energySource)) {
    return (
      <div
        className="max-w-full truncate text-[10px] font-medium text-current/70"
        title={energyPolicyRule}
      >
        {energySource}
      </div>
    );
  }

  return null;
}

function formatEnergyValue(energyValue: number | null): string {
  if (hasValue(energyValue)) {
    return `${energyValue.toFixed(6)} Ha`;
  }

  return "—";
}

interface AccuracyVerdictCardProps {
  readonly accuracy: AccuracyAssessment;
  readonly accuracyDeltaText: string | null;
  readonly energyValue: number | null;
  readonly energySource: string | null;
  readonly energyPolicyRule: string | undefined;
}

function AccuracyVerdictCard({
  accuracy,
  accuracyDeltaText,
  energyValue,
  energySource,
  energyPolicyRule,
}: AccuracyVerdictCardProps) {
  return (
    <div className={cn("rounded-md border px-3 py-2", verdictClasses(accuracy.verdict))}>
      <div className="grid gap-3 md:grid-cols-2 md:items-center">
        <div
          className="flex min-w-0 flex-col items-center justify-center gap-2 text-center"
          aria-label="Chemical accuracy verdict"
        >
          <Badge
            variant="outline"
            className={cn(
              "max-w-full justify-center whitespace-normal rounded-full px-4 py-1 text-center text-sm font-semibold leading-tight",
              verdictClasses(accuracy.verdict),
            )}
          >
            {formatAccuracyVerdict(accuracy.verdict)}
          </Badge>
          <div className="text-center text-xs font-medium tabular-nums md:text-[11px]">
            {accuracyDeltaText ?? "—"}
          </div>
        </div>
        <div className="flex min-w-0 flex-col items-center justify-center text-center">
          <div className="text-[11px] font-medium text-current/80">Best Energy</div>
          <div className="font-mono text-xl font-semibold tabular-nums">
            {formatEnergyValue(energyValue)}
          </div>
          <EnergySourceLabel energySource={energySource} energyPolicyRule={energyPolicyRule} />
        </div>
      </div>
    </div>
  );
}

interface SummaryPrimaryMetricsProps {
  readonly result: RunResultResponse | null;
  readonly status: RunResponse["status"];
  readonly isRunning?: boolean;
  readonly convergenceInsight: ReturnType<typeof getConvergenceInsight>;
  readonly isVqe: boolean;
  readonly iterationValue: number | null;
  readonly runtimeLabel: string;
  readonly primaryRuntimeSeconds: number | null;
  readonly runtimeHelper: string | null;
  readonly optimizerIterations: number | null;
}

interface OptimizerIterationsMetricProps {
  readonly isVqe: boolean;
  readonly optimizerIterations: number | null;
}

function formatIntegerValue(value: number | null): string {
  if (hasValue(value)) {
    return value.toLocaleString();
  }

  return "—";
}

function formatRuntimeValue(value: number | null): string {
  if (hasValue(value)) {
    return formatDuration(value);
  }

  return "—";
}

function OptimizerIterationsMetric({ isVqe, optimizerIterations }: OptimizerIterationsMetricProps) {
  if (isVqe && hasValue(optimizerIterations)) {
    return (
      <SummaryMetric
        label="Optimizer iters"
        value={optimizerIterations.toLocaleString()}
        valueClassName="tabular-nums"
      />
    );
  }

  return null;
}

function SummaryPrimaryMetrics({
  result,
  status,
  isRunning,
  convergenceInsight,
  isVqe,
  iterationValue,
  runtimeLabel,
  primaryRuntimeSeconds,
  runtimeHelper,
  optimizerIterations,
}: SummaryPrimaryMetricsProps) {
  return (
    <div className="grid auto-rows-fr gap-x-5 gap-y-2.5 sm:grid-cols-3 [&>div]:items-center [&>div]:justify-start [&>div]:text-center">
      <SummaryMetric
        label="Converged"
        value={
          <ConvergenceStatusIndicator
            result={result}
            status={status}
            isRunning={isRunning}
            insight={convergenceInsight}
          />
        }
      />
      <SummaryMetric
        label={isVqe ? "Objective evals" : "Iterations"}
        value={formatIntegerValue(iterationValue)}
        valueClassName="tabular-nums"
      />
      <SummaryMetric
        label={runtimeLabel}
        value={formatRuntimeValue(primaryRuntimeSeconds)}
        helper={runtimeHelper}
        valueClassName="tabular-nums"
      />
      <OptimizerIterationsMetric isVqe={isVqe} optimizerIterations={optimizerIterations} />
    </div>
  );
}

interface ExecutionDetailsGridProps {
  readonly executionDetails: SummaryMetricProps[];
}

function ExecutionDetailsGrid({ executionDetails }: ExecutionDetailsGridProps) {
  if (executionDetails.length === 0) {
    return null;
  }

  return (
    <div className="grid gap-x-5 gap-y-2.5 border-t border-border/60 pt-2.5 sm:grid-cols-3 [&>div]:items-center [&>div]:text-center">
      {executionDetails.map((detail) => (
        <SummaryMetric key={detail.label} {...detail} />
      ))}
    </div>
  );
}

export function SummaryTile(props: SummaryTileProps) {
  if (props.pending) {
    return (
      <DashboardTile
        title="Summary"
        helpText="Primary outcome metrics and execution metadata for this run."
        editMode={props.editMode}
      >
        <SummaryTileLoadingContent />
      </DashboardTile>
    );
  }

  const {
    run,
    result,
    molecule,
    isVqe,
    algorithmLabel,
    backendLabel,
    modeLabel,
    accuracy,
    accuracyDeltaText,
    energyValue,
    energySource,
    energyPolicyRule,
    convergenceInsight,
    iterationValue,
    runtimeLabel,
    primaryRuntimeSeconds,
    runtimeHelper,
    optimizerIterations,
    executionDetails,
    isRunning,
  } = buildSummaryTileModel(props);

  return (
    <DashboardTile
      title="Summary"
      helpText="Primary outcome metrics and execution metadata for this run."
      editMode={props.editMode}
    >
      <dl className="flex h-full min-h-0 flex-col gap-2.5 overflow-auto">
        <SummaryHeader
          run={run}
          molecule={molecule}
          algorithmLabel={algorithmLabel}
          backendLabel={backendLabel}
          modeLabel={modeLabel}
        />
        <AccuracyVerdictCard
          accuracy={accuracy}
          accuracyDeltaText={accuracyDeltaText}
          energyValue={energyValue}
          energySource={energySource}
          energyPolicyRule={energyPolicyRule}
        />
        <SummaryPrimaryMetrics
          result={result}
          status={run.status}
          isRunning={isRunning}
          convergenceInsight={convergenceInsight}
          isVqe={isVqe}
          iterationValue={iterationValue}
          runtimeLabel={runtimeLabel}
          primaryRuntimeSeconds={primaryRuntimeSeconds}
          runtimeHelper={runtimeHelper}
          optimizerIterations={optimizerIterations}
        />
        <ExecutionDetailsGrid executionDetails={executionDetails} />
      </dl>
    </DashboardTile>
  );
}
