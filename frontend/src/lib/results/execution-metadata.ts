import type { BackendOptions, RunEventResponse, RunResponse, RunResultResponse } from "@/types/run";

export interface TranspilationLayoutPair {
  logical: number;
  physical: number;
}

export interface IbmRuntimeTiming {
  createdAt: string | null;
  runningAt: string | null;
  finishedAt: string | null;
  pendingSeconds: number | null;
  usageSeconds: number | null;
  totalSeconds: number | null;
}

export interface RunExecutionMetadata {
  backendName: string | null;
  actualExecutionTarget?: string | null;
  actualPathClass?: string | null;
  requestedDevice?: string | null;
  actualDevice?: string | null;
  aerVersion?: string | null;
  aerPreflight?: string | null;
  backendPrimitivesUsed?: boolean | null;
  selectionPolicy: string | null;
  shots: number | null;
  requestedShots?: number | null;
  effectiveShots?: number | null;
  requestedEstimatorPrecision?: number | null;
  effectiveEstimatorPrecision?: number | null;
  reportedEnergySource?: string | null;
  reportedEnergyIsValid?: boolean | null;
  projectedSolveIsDiagnostic?: boolean | null;
  scientificConverged?: boolean | null;
  benchmarkEligible?: boolean | null;
  benchmarkExclusionReason?: string | null;
  noiseSource?: string | null;
  noiseFingerprint?: string | null;
  workLedger?: Record<string, unknown> | null;
  optimizationLevel: number | null;
  aerMethod: string | null;
  simulatorMethod: string | null;
  primitiveFamily: string | null;
  qubits: number | null;
  depth: number | null;
  twoQubitDepth: number | null;
  seedSimulator: number | null;
  seedTranspiler: number | null;
  ibmJobId: string | null;
  ibmStatus: string | null;
  ibmQueuePosition: number | null;
  ibmPubCount: number | null;
  ibmTiming: IbmRuntimeTiming | null;
  transpilationLayout: TranspilationLayoutPair[];
  usedPhysicalQubits: number[];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function getString(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function normalizeBackendName(value: unknown): string | null {
  const backendName = getString(value)?.trim();
  if (backendName == null || backendName.length === 0) return null;
  if (backendName === "least_busy" || backendName === "least_error") return null;
  return backendName;
}

function getNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function getInteger(value: unknown): number | null {
  const parsed = getNumber(value);
  return parsed != null && Number.isInteger(parsed) ? parsed : null;
}

function getIntegerList(value: unknown): number[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) =>
    typeof item === "number" && Number.isInteger(item) ? [item] : [],
  );
}

function getLayoutPairs(value: unknown): TranspilationLayoutPair[] {
  if (!Array.isArray(value)) return [];

  const recordPairs = value.flatMap((item) => {
    if (!isRecord(item)) return [];
    const logical = getNumber(item.logical);
    const physical = getNumber(item.physical);
    if (logical == null || physical == null) return [];
    return [{ logical, physical } satisfies TranspilationLayoutPair];
  });
  if (recordPairs.length > 0) {
    return [...recordPairs].sort((left, right) => left.logical - right.logical);
  }

  const integerLayout = getIntegerList(value);
  return integerLayout.map((physical, logical) => ({ logical, physical }));
}

function getConfigBackendOptions(run: RunResponse): BackendOptions | null {
  const options = run.config_json.backend_options;
  return isRecord(options) ? options : null;
}

function latestPayload(
  events: RunEventResponse[],
  stageNames: ReadonlySet<string>,
): Record<string, unknown> | null {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const event = events[index];
    if (!event) {
      continue;
    }
    const stage = getString(event.payload.stage);
    if (stage != null && stageNames.has(stage)) return event.payload;
  }
  return null;
}

function latestEventPayload(
  events: RunEventResponse[],
  eventType: RunEventResponse["type"],
): Record<string, unknown> | null {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const event = events[index];
    if (!event) {
      continue;
    }
    if (event.type === eventType) return event.payload;
  }
  return null;
}

function pickNestedRecord(...values: unknown[]): Record<string, unknown> | null {
  for (const value of values) {
    if (isRecord(value)) return value;
  }
  return null;
}

function firstString(...values: unknown[]): string | null {
  for (const value of values) {
    const stringValue = getString(value);
    if (stringValue != null) return stringValue;
  }
  return null;
}

function firstNumber(...values: unknown[]): number | null {
  for (const value of values) {
    const numberValue = getNumber(value);
    if (numberValue != null) return numberValue;
  }
  return null;
}

function firstInteger(...values: unknown[]): number | null {
  for (const value of values) {
    const integerValue = getInteger(value);
    if (integerValue != null) return integerValue;
  }
  return null;
}

function firstBoolean(...values: unknown[]): boolean | null {
  for (const value of values) {
    if (typeof value === "boolean") return value;
  }
  return null;
}

function uniqueSorted(values: number[]): number[] {
  return [...new Set(values)].sort((left, right) => left - right);
}

function firstNonEmptyLayout(...values: unknown[]): TranspilationLayoutPair[] {
  for (const value of values) {
    const layout = getLayoutPairs(value);
    if (layout.length > 0) return layout;
  }
  return [];
}

function getIbmRuntimeTiming(value: unknown): IbmRuntimeTiming | null {
  if (!isRecord(value)) return null;
  const timing = {
    createdAt: getString(value.created_at),
    runningAt: getString(value.running_at),
    finishedAt: getString(value.finished_at),
    pendingSeconds: getNumber(value.pending_seconds),
    usageSeconds: getNumber(value.usage_seconds),
    totalSeconds: getNumber(value.total_seconds),
  };
  return Object.values(timing).some((item) => item != null) ? timing : null;
}

function firstIbmRuntimeTiming(...values: unknown[]): IbmRuntimeTiming | null {
  for (const value of values) {
    const timing = getIbmRuntimeTiming(value);
    if (timing != null) return timing;
  }
  return null;
}

function chooseEarlierIso(left: string | null, right: string | null): string | null {
  if (left == null) return right;
  if (right == null) return left;
  return new Date(left).getTime() <= new Date(right).getTime() ? left : right;
}

function chooseLaterIso(left: string | null, right: string | null): string | null {
  if (left == null) return right;
  if (right == null) return left;
  return new Date(left).getTime() >= new Date(right).getTime() ? left : right;
}

function sumDefined(values: Array<number | null>): number | null {
  const numbers = values.filter((value): value is number => value != null);
  if (numbers.length === 0) return null;
  return numbers.reduce((sum, value) => sum + value, 0);
}

function aggregateIbmRuntimeTimings(timings: IbmRuntimeTiming[]): IbmRuntimeTiming | null {
  if (timings.length === 0) return null;

  return {
    createdAt: timings.reduce<string | null>(
      (earliest, timing) => chooseEarlierIso(earliest, timing.createdAt),
      null,
    ),
    runningAt: timings.reduce<string | null>(
      (earliest, timing) => chooseEarlierIso(earliest, timing.runningAt),
      null,
    ),
    finishedAt: timings.reduce<string | null>(
      (latest, timing) => chooseLaterIso(latest, timing.finishedAt),
      null,
    ),
    pendingSeconds: sumDefined(timings.map((timing) => timing.pendingSeconds)),
    usageSeconds: sumDefined(timings.map((timing) => timing.usageSeconds)),
    totalSeconds: sumDefined(timings.map((timing) => timing.totalSeconds)),
  };
}

function aggregateIbmRuntimeTimingFromEvents(events: RunEventResponse[]): IbmRuntimeTiming | null {
  const timingsByJobId = new Map<string, IbmRuntimeTiming>();
  const anonymousTimings: IbmRuntimeTiming[] = [];

  for (const event of events) {
    if (event.type !== "ibm_status_poll") continue;

    const phase = getString(event.payload.phase);
    if (phase != null && phase !== "complete") continue;

    const timing = getIbmRuntimeTiming(event.payload.ibm_timing);
    if (timing == null) continue;

    const jobId = getString(event.payload.ibm_job_id);
    if (jobId != null) {
      timingsByJobId.set(jobId, timing);
      continue;
    }

    anonymousTimings.push(timing);
  }

  return aggregateIbmRuntimeTimings([...timingsByJobId.values(), ...anonymousTimings]);
}

interface ExecutionMetadataSources {
  run: RunResponse;
  result: RunResultResponse | null | undefined;
  metadata: Record<string, unknown>;
  backendOptions: BackendOptions | null;
  transpilation: Record<string, unknown> | null;
  execution: Record<string, unknown> | null;
  transpilationSummary: Record<string, unknown> | null;
  resultExecution: Record<string, unknown> | null;
  resultEnergy: Record<string, unknown> | null;
  benchmarkProvenance: Record<string, unknown> | null;
  ibmSubmittedPayload: Record<string, unknown> | null;
  ibmStatusPayload: Record<string, unknown> | null;
}

function getExecutionMetadataSources(
  run: RunResponse,
  events: RunEventResponse[],
  result: RunResultResponse | null | undefined,
): ExecutionMetadataSources {
  const metadata = run.metadata ?? {};
  const backendOptions = getConfigBackendOptions(run);
  const transpilationPayload = latestPayload(
    events,
    new Set(["transpilation", "transpiled", "setup"]),
  );
  const executionPayload = latestPayload(events, new Set(["execution", "ibm", "sampling"]));
  const resultPayload = latestEventPayload(events, "result");
  const ibmSubmittedPayload = latestEventPayload(events, "ibm_job_submitted");
  const ibmStatusPayload = latestEventPayload(events, "ibm_status_poll");
  const resultMetrics = pickNestedRecord(resultPayload?.algorithm_metrics);
  const responseMetrics = pickNestedRecord(result?.algorithm_metrics);
  const resultProvenance = pickNestedRecord(
    resultMetrics?.benchmark_provenance,
    responseMetrics?.benchmark_provenance,
  );
  const resultEnergy = pickNestedRecord(resultProvenance?.energy);
  const resultExecution = pickNestedRecord(
    resultPayload?.backend_execution,
    resultMetrics?.backend_execution,
    responseMetrics?.backend_execution,
    resultProvenance?.execution,
  );
  const transpilation = pickNestedRecord(
    resultExecution,
    metadata.transpilation,
    metadata.transpilation_preview,
    transpilationPayload,
  );
  const execution = pickNestedRecord(resultExecution, metadata.execution, executionPayload);
  const transpilationSummary = pickNestedRecord(
    metadata.transpilation_summary,
    transpilation?.transpilation_summary,
    execution?.transpilation_summary,
  );

  return {
    run,
    result,
    metadata,
    backendOptions,
    transpilation,
    execution,
    transpilationSummary,
    resultExecution,
    resultEnergy,
    benchmarkProvenance: resultProvenance,
    ibmSubmittedPayload,
    ibmStatusPayload,
  };
}

function getExecutionBackendName({
  metadata,
  backendOptions,
  transpilation,
  execution,
  transpilationSummary,
}: ExecutionMetadataSources): string | null {
  return (
    normalizeBackendName(backendOptions?.backend_name) ??
    normalizeBackendName(transpilation?.backend_name) ??
    normalizeBackendName(execution?.backend_name) ??
    normalizeBackendName(transpilation?.resolved_backend_name) ??
    normalizeBackendName(execution?.resolved_backend_name) ??
    normalizeBackendName(transpilationSummary?.resolved_backend_name) ??
    normalizeBackendName(metadata.backend_name) ??
    normalizeBackendName(metadata.ibm_backend) ??
    normalizeBackendName(metadata.resolved_backend_name)
  );
}

function getExecutionCircuitShape({
  metadata,
  transpilation,
  execution,
  transpilationSummary,
}: ExecutionMetadataSources): Pick<RunExecutionMetadata, "depth" | "qubits" | "twoQubitDepth"> {
  return {
    depth:
      getNumber(transpilationSummary?.transpiled_depth) ??
      getNumber(transpilation?.transpiled_depth) ??
      getNumber(transpilation?.circuit_depth) ??
      getNumber(metadata.circuit_depth),
    qubits:
      getNumber(transpilation?.num_qubits) ??
      getNumber(execution?.num_qubits) ??
      getNumber(metadata.num_qubits),
    twoQubitDepth:
      getNumber(transpilationSummary?.two_qubit_depth) ??
      getNumber(transpilation?.two_qubit_depth) ??
      getNumber(metadata.two_qubit_depth),
  };
}

function getExecutionScalarFields({
  result,
  resultEnergy,
  backendOptions,
  transpilation,
  execution,
  transpilationSummary,
  resultExecution,
  benchmarkProvenance,
}: ExecutionMetadataSources): Pick<
  RunExecutionMetadata,
  | "actualExecutionTarget"
  | "actualPathClass"
  | "requestedDevice"
  | "actualDevice"
  | "aerVersion"
  | "aerPreflight"
  | "backendPrimitivesUsed"
  | "selectionPolicy"
  | "shots"
  | "requestedShots"
  | "effectiveShots"
  | "requestedEstimatorPrecision"
  | "effectiveEstimatorPrecision"
  | "reportedEnergySource"
  | "reportedEnergyIsValid"
  | "projectedSolveIsDiagnostic"
  | "scientificConverged"
  | "benchmarkEligible"
  | "benchmarkExclusionReason"
  | "noiseSource"
  | "noiseFingerprint"
  | "optimizationLevel"
  | "aerMethod"
  | "simulatorMethod"
  | "primitiveFamily"
  | "seedSimulator"
  | "seedTranspiler"
> {
  return {
    actualExecutionTarget: firstString(
      resultExecution?.actual_execution_target,
      execution?.actual_execution_target,
      transpilation?.actual_execution_target,
    ),
    actualPathClass: firstString(
      resultExecution?.actual_path_class,
      execution?.actual_path_class,
      transpilation?.actual_path_class,
    ),
    requestedDevice: firstString(
      resultExecution?.requested_device,
      execution?.requested_device,
      transpilation?.requested_device,
      backendOptions?.device,
    ),
    actualDevice: firstString(
      resultExecution?.actual_device,
      execution?.actual_device,
      transpilation?.actual_device,
    ),
    aerVersion: firstString(
      resultExecution?.aer_version,
      execution?.aer_version,
      transpilation?.aer_version,
    ),
    aerPreflight: firstString(
      resultExecution?.aer_preflight,
      execution?.aer_preflight,
      transpilation?.aer_preflight,
    ),
    backendPrimitivesUsed: firstBoolean(
      resultExecution?.backend_primitives_used,
      execution?.backend_primitives_used,
      transpilation?.backend_primitives_used,
    ),
    selectionPolicy: firstString(
      resultExecution?.selection_policy,
      transpilation?.selection_policy,
      execution?.selection_policy,
      backendOptions?.selection_policy,
    ),
    shots: firstNumber(
      resultExecution?.shots,
      transpilation?.shots,
      execution?.shots,
      backendOptions?.shots,
    ),
    requestedShots: firstNumber(
      resultExecution?.requested_shots,
      execution?.requested_shots,
      transpilation?.requested_shots,
      backendOptions?.shots,
    ),
    effectiveShots: firstNumber(
      resultExecution?.effective_shots,
      execution?.effective_shots,
      transpilation?.effective_shots,
      resultExecution?.shots,
      execution?.shots,
    ),
    requestedEstimatorPrecision: firstNumber(
      resultExecution?.requested_estimator_precision,
      execution?.requested_estimator_precision,
      transpilation?.requested_estimator_precision,
    ),
    effectiveEstimatorPrecision: firstNumber(
      resultExecution?.effective_estimator_precision,
      execution?.effective_estimator_precision,
      transpilation?.effective_estimator_precision,
    ),
    reportedEnergySource: firstString(
      resultEnergy?.reported_energy_source,
      result?.reported_energy_source,
    ),
    reportedEnergyIsValid: firstBoolean(resultEnergy?.reported_energy_is_valid),
    projectedSolveIsDiagnostic: firstBoolean(resultEnergy?.projected_solve_is_diagnostic),
    scientificConverged: firstBoolean(resultEnergy?.scientific_converged, result?.converged),
    benchmarkEligible: firstBoolean(
      benchmarkProvenance?.benchmark_eligible,
      benchmarkProvenance?.benchmarkEligible,
    ),
    benchmarkExclusionReason: firstString(
      benchmarkProvenance?.benchmark_exclusion_reason,
      benchmarkProvenance?.benchmarkExclusionReason,
    ),
    noiseSource: firstString(
      pickNestedRecord(resultExecution?.noise_summary)?.source,
      pickNestedRecord(execution?.noise_summary)?.source,
      pickNestedRecord(transpilation?.noise_summary)?.source,
    ),
    noiseFingerprint: firstString(
      pickNestedRecord(resultExecution?.noise_summary)?.model_fingerprint_sha256,
      pickNestedRecord(execution?.noise_summary)?.model_fingerprint_sha256,
      pickNestedRecord(transpilation?.noise_summary)?.model_fingerprint_sha256,
    ),
    optimizationLevel: firstNumber(
      transpilationSummary?.optimization_level,
      transpilation?.optimization_level,
      execution?.optimization_level,
      backendOptions?.optimization_level,
    ),
    aerMethod: firstString(backendOptions?.aer_method),
    simulatorMethod: firstString(transpilation?.simulator_method, execution?.simulator_method),
    primitiveFamily: firstString(transpilation?.primitive_family, execution?.primitive_family),
    seedSimulator: firstNumber(backendOptions?.seed_simulator),
    seedTranspiler: firstNumber(backendOptions?.seed_transpiler),
  };
}

function getResultWorkLedger(
  result: RunResultResponse | null | undefined,
): Record<string, unknown> | null {
  const metrics = result?.algorithm_metrics;
  if (!isRecord(metrics)) return null;
  const candidates = [
    pickNestedRecord(metrics.benchmark_provenance)?.work_ledger,
    metrics.work_ledger,
    pickNestedRecord(metrics.matrix_element_summary)?.work_ledger,
    pickNestedRecord(metrics.sci_result_package)?.work_ledger,
    pickNestedRecord(metrics.optimizer_diagnostics)?.work_ledger,
  ];
  return candidates.find(isRecord) ?? null;
}

function getExecutionLayout(
  transpilationSummary: Record<string, unknown> | null,
): Pick<RunExecutionMetadata, "transpilationLayout" | "usedPhysicalQubits"> {
  const transpilationLayout = firstNonEmptyLayout(
    transpilationSummary?.logical_to_physical,
    transpilationSummary?.final_layout,
    transpilationSummary?.initial_layout,
  );
  const explicitUsedQubits = getIntegerList(transpilationSummary?.used_physical_qubits);

  return {
    transpilationLayout,
    usedPhysicalQubits: uniqueSorted(
      explicitUsedQubits.length > 0
        ? explicitUsedQubits
        : transpilationLayout.map((pair) => pair.physical),
    ),
  };
}

function getExecutionIbmTiming(
  events: RunEventResponse[],
  {
    metadata,
    execution,
    resultExecution,
    ibmSubmittedPayload,
    ibmStatusPayload,
  }: ExecutionMetadataSources,
): IbmRuntimeTiming | null {
  return (
    aggregateIbmRuntimeTimingFromEvents(events) ??
    firstIbmRuntimeTiming(
      metadata.ibm_timing,
      ibmStatusPayload?.ibm_timing,
      ibmSubmittedPayload?.ibm_timing,
      execution?.ibm_timing,
      resultExecution?.ibm_timing,
    )
  );
}

function getExecutionIbmJobId({
  run,
  metadata,
  execution,
  transpilation,
  ibmSubmittedPayload,
  ibmStatusPayload,
}: ExecutionMetadataSources): string | null {
  return firstString(
    run.ibm_job_id,
    ibmStatusPayload?.ibm_job_id,
    ibmSubmittedPayload?.ibm_job_id,
    transpilation?.ibm_job_id,
    execution?.ibm_job_id,
    metadata.ibm_job_id,
  );
}

function getExecutionIbmStatus({
  metadata,
  execution,
  ibmSubmittedPayload,
  ibmStatusPayload,
}: ExecutionMetadataSources): string | null {
  return firstString(
    ibmStatusPayload?.ibm_status,
    ibmSubmittedPayload?.ibm_status,
    metadata.ibm_status,
    execution?.ibm_status,
  );
}

function getExecutionIbmQueuePosition({
  metadata,
  ibmSubmittedPayload,
  ibmStatusPayload,
}: ExecutionMetadataSources): number | null {
  return firstInteger(
    ibmStatusPayload?.queue_position,
    ibmStatusPayload?.queued_count,
    ibmSubmittedPayload?.queue_position,
    ibmSubmittedPayload?.queued_count,
    metadata.ibm_queue_position,
  );
}

function getExecutionIbmPubCount({
  metadata,
  execution,
  resultExecution,
  ibmSubmittedPayload,
  ibmStatusPayload,
}: ExecutionMetadataSources): number | null {
  return firstInteger(
    ibmStatusPayload?.pub_count,
    ibmSubmittedPayload?.pub_count,
    metadata.ibm_pub_count,
    execution?.ibm_pub_count,
    resultExecution?.ibm_pub_count,
  );
}

function getExecutionIbmFields(
  sources: ExecutionMetadataSources,
): Pick<RunExecutionMetadata, "ibmJobId" | "ibmStatus" | "ibmQueuePosition" | "ibmPubCount"> {
  return {
    ibmJobId: getExecutionIbmJobId(sources),
    ibmStatus: getExecutionIbmStatus(sources),
    ibmQueuePosition: getExecutionIbmQueuePosition(sources),
    ibmPubCount: getExecutionIbmPubCount(sources),
  };
}

export function getRunExecutionMetadata(
  run: RunResponse,
  events: RunEventResponse[],
  result?: RunResultResponse | null,
): RunExecutionMetadata {
  const sources = getExecutionMetadataSources(run, events, result);
  const circuitShape = getExecutionCircuitShape(sources);
  const layout = getExecutionLayout(sources.transpilationSummary);

  return {
    backendName: getExecutionBackendName(sources),
    ...getExecutionScalarFields(sources),
    workLedger: getResultWorkLedger(result),
    ...circuitShape,
    ...getExecutionIbmFields(sources),
    ibmTiming: getExecutionIbmTiming(events, sources),
    ...layout,
  };
}

export function formatSelectionPolicy(value: string | null): string | null {
  return value?.replaceAll("_", " ") ?? null;
}

export function formatTranspilationLayout(layout: TranspilationLayoutPair[]): string | null {
  if (layout.length === 0) return null;
  return layout.map((pair) => `q${pair.logical}→${pair.physical}`).join(", ");
}

export function formatPhysicalQubitList(qubits: number[]): string | null {
  return qubits.length === 0 ? null : qubits.join(", ");
}
