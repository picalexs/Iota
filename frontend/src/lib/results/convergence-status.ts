import type { RunEventResponse, RunResponse, RunResultResponse } from "@/types/run";

export interface ConvergenceInsight {
  label: string;
  value: string;
  helper?: string;
  tone: "success" | "warning" | "destructive" | "muted";
}

export interface ConvergenceResultLog {
  summary: string;
  details?: string;
  tone: ConvergenceInsight["tone"];
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function asBoolean(value: unknown): boolean | null {
  return typeof value === "boolean" ? value : null;
}

function asString(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function formatScientific(value: number): string {
  return value.toExponential(2);
}

function formatThresholdComparison(
  label: string,
  value: number | null,
  threshold: number | null,
  unit?: string,
): string | null {
  if (value == null) {
    return null;
  }
  if (threshold == null) {
    return [label, formatScientific(Math.abs(value)), unit].filter(Boolean).join(" ");
  }
  return [
    label,
    formatScientific(Math.abs(value)),
    Math.abs(value) <= threshold ? "<=" : ">",
    formatScientific(threshold),
    unit,
  ]
    .filter(Boolean)
    .join(" ");
}

function formatCountComparison(
  label: string,
  value: number | null,
  minimum: number | null,
): string | null {
  if (value == null) {
    return null;
  }
  if (minimum == null) {
    return `${label} ${value}`;
  }
  return `${label} ${value} ${value >= minimum ? ">=" : "<"} ${minimum}`;
}

function formatProgressCount(
  label: string,
  value: number | null,
  total: number | null,
): string | null {
  if (value == null) {
    return null;
  }
  if (total == null) {
    return `${label} ${value}`;
  }
  return `${label} ${value} / ${total}`;
}

function formatScientificDetail(label: string, value: number | null): string | null {
  if (value === null) return null;
  return `${label} ${formatScientific(value)}`;
}

function joinParts(parts: Array<string | null | undefined>): string | undefined {
  const filtered = parts.filter((part): part is string => Boolean(part));
  return filtered.length > 0 ? filtered.join(" · ") : undefined;
}

function yesNoGate(label: string, passed: boolean | null | undefined): string | null {
  if (passed == null) return null;
  return `${label} ${passed ? "yes" : "no"}`;
}

function skqdExtensionFailureMessage(
  fallback: string,
  sqdConverged: boolean | null,
  krylovConverged: boolean | null,
): string {
  if (sqdConverged === false) {
    return "The Krylov extension finished, but the SQD seed gate did not pass";
  }
  if (krylovConverged === false) {
    return "The Krylov extension residual stayed above tolerance";
  }
  return fallback;
}

function latestIterationPayload(events: RunEventResponse[]): Record<string, unknown> | null {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const event = events[index];
    if (!event) {
      continue;
    }
    if (event.type !== "iteration_update") {
      continue;
    }
    const payload = asRecord(event.payload);
    if (payload == null) {
      continue;
    }
    if (payload.stage !== "setup") {
      return payload;
    }
  }
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const event = events[index];
    if (!event) {
      continue;
    }
    if (event.type === "iteration_update") return asRecord(event.payload);
  }
  return null;
}

function metricsRecord(result: RunResultResponse | null): Record<string, unknown> | null {
  return result?.algorithm_metrics ? asRecord(result.algorithm_metrics) : null;
}

function getAdvancedConfig(run: RunResponse): Record<string, unknown> | null {
  const config = asRecord(run.config_json);
  return asRecord(config?.advanced_config);
}

function getBaseSamplingOptions(run: RunResponse): Record<string, unknown> | null {
  const advancedConfig = getAdvancedConfig(run);
  return asRecord(advancedConfig?.base_sampling_options);
}

function getConfiguredNumber(run: RunResponse, ...paths: string[][]): number | null {
  const config = asRecord(run.config_json);
  const advancedConfig = getAdvancedConfig(run);
  const baseSamplingOptions = getBaseSamplingOptions(run);
  const roots: Array<Record<string, unknown> | null> = [
    config,
    advancedConfig,
    baseSamplingOptions,
  ];

  for (const path of paths) {
    for (const root of roots) {
      let current: unknown = root;
      for (const segment of path) {
        current = asRecord(current)?.[segment];
      }
      const number = asNumber(current);
      if (number != null) {
        return number;
      }
    }
  }
  return null;
}

function getVqeThreshold(
  run: RunResponse,
  result: RunResultResponse | null,
  payload: Record<string, unknown> | null,
): number | null {
  const metrics = metricsRecord(result);
  const diagnostics = asRecord(metrics?.optimizer_diagnostics);
  return (
    asNumber(payload?.convergence_threshold) ??
    asNumber(diagnostics?.convergence_threshold) ??
    getConfiguredNumber(run, ["convergence_threshold"])
  );
}

function getVqeBudget(
  run: RunResponse,
  result: RunResultResponse | null,
  payload: Record<string, unknown> | null,
): number | null {
  const metrics = metricsRecord(result);
  const diagnostics = asRecord(metrics?.optimizer_diagnostics);
  return (
    asNumber(payload?.max_function_evaluations) ??
    asNumber(metrics?.max_function_evaluations) ??
    asNumber(diagnostics?.max_function_evaluations) ??
    getConfiguredNumber(run, ["max_function_evaluations"], ["max_iterations"])
  );
}

function describeVqeRunning(
  run: RunResponse,
  result: RunResultResponse | null,
  payload: Record<string, unknown> | null,
): ConvergenceInsight {
  const deltaEnergy = Math.abs(asNumber(payload?.delta_energy) ?? Number.NaN);
  const threshold = getVqeThreshold(run, result, payload);
  const evaluations =
    asNumber(payload?.objective_evaluations) ?? asNumber(payload?.completed_iterations);
  const budget = getVqeBudget(run, result, payload);
  const hasThreshold = Number.isFinite(deltaEnergy) && threshold != null;
  let value = "Optimizer-controlled convergence is still in progress";
  if (hasThreshold) {
    value =
      deltaEnergy <= threshold
        ? "The last energy update is inside the configured threshold"
        : "The last energy update is still above the configured threshold";
  }

  return {
    label: "Convergence check",
    value,
    helper: joinParts([
      Number.isFinite(deltaEnergy)
        ? formatThresholdComparison("|dE|", deltaEnergy, threshold, "Ha")
        : null,
      formatProgressCount("evals", evaluations, budget),
    ]),
    tone: "warning",
  };
}

function describeVqeCompleted(
  run: RunResponse,
  result: RunResultResponse,
  payload: Record<string, unknown> | null,
): ConvergenceInsight {
  const metrics = metricsRecord(result);
  const diagnostics = asRecord(metrics?.optimizer_diagnostics);
  const terminationReason = asString(diagnostics?.termination_reason);
  const message = asString(diagnostics?.message);
  const finalDelta = Math.abs(asNumber(diagnostics?.final_delta_energy) ?? Number.NaN);
  const threshold = getVqeThreshold(run, result, payload);
  const evaluations =
    asNumber(metrics?.objective_evaluations) ??
    asNumber(diagnostics?.objective_evaluations) ??
    asNumber(diagnostics?.function_evaluations) ??
    result.iterations;
  const budget = getVqeBudget(run, result, payload);

  let value = result.converged
    ? "The optimizer reported convergence"
    : "The optimizer stopped without convergence";
  if (terminationReason === "ansatz_has_no_parameters") {
    value = "The ansatz had no free parameters";
  } else if (terminationReason === "max_function_evaluations") {
    value = "The run reached the function-evaluation budget";
  } else if (result.converged === false && message) {
    value = message;
  }

  return {
    label: "Stopped because",
    value,
    helper: joinParts([
      Number.isFinite(finalDelta)
        ? formatThresholdComparison("|dE|", finalDelta, threshold, "Ha")
        : null,
      formatProgressCount("evals", evaluations, budget),
    ]),
    tone: result.converged ? "success" : "warning",
  };
}

function buildSqdHelper(payload: Record<string, unknown> | null): string | undefined {
  const deltaEnergy = asNumber(payload?.delta_energy);
  const energyTol = asNumber(payload?.energy_tol);
  const occupancyDelta = asNumber(payload?.occupancy_delta);
  const occupancyTol = asNumber(payload?.occupancies_tol);
  const selected = asNumber(payload?.selected_samples);
  const minimumSelected = asNumber(payload?.min_selected_configurations);

  return joinParts([
    formatThresholdComparison("dE", deltaEnergy, energyTol, "Ha"),
    formatThresholdComparison("dOcc", occupancyDelta, occupancyTol),
    formatCountComparison("selected", selected, minimumSelected),
  ]);
}

function describeSqdRunning(payload: Record<string, unknown> | null): ConvergenceInsight {
  const blockedReason = asString(payload?.convergence_blocked_reason);
  const deltaEnergy = asNumber(payload?.delta_energy);
  const energyTol = asNumber(payload?.energy_tol);
  const occupancyDelta = asNumber(payload?.occupancy_delta);
  const occupancyTol = asNumber(payload?.occupancies_tol);
  const convergedCandidate = asBoolean(payload?.converged_candidate) === true;

  let value = "SQD recovery is still collecting evidence";
  if (convergedCandidate) {
    value = "This SQD recovery step already satisfies the convergence gate";
  } else if (blockedReason === "insufficient_selected_configurations") {
    value = "Energy and occupancies look stable, but too few configurations survived";
  } else if (
    deltaEnergy != null &&
    energyTol != null &&
    occupancyDelta != null &&
    occupancyTol != null
  ) {
    const energyPassed = Math.abs(deltaEnergy) <= energyTol;
    const occupancyPassed = Math.abs(occupancyDelta) <= occupancyTol;
    if (!energyPassed && !occupancyPassed) {
      value = "Energy and occupancies are still outside the SQD tolerances";
    } else if (!energyPassed) {
      value = "Energy is still outside the SQD tolerance";
    } else if (!occupancyPassed) {
      value = "Occupancies are still outside the SQD tolerance";
    }
  }

  return {
    label: "Convergence check",
    value,
    helper: buildSqdHelper(payload),
    tone: "warning",
  };
}

function describeSqdCompleted(
  run: RunResponse,
  result: RunResultResponse,
  payload: Record<string, unknown> | null,
): ConvergenceInsight {
  const blockedReason = asString(payload?.convergence_blocked_reason);
  const iterationCap = getConfiguredNumber(run, ["max_iterations"]);

  let value = result.converged
    ? "The SQD recovery gate passed"
    : "The SQD recovery gate was not satisfied";
  if (!result.converged) {
    if (blockedReason === "insufficient_selected_configurations") {
      value = "Energy and occupancies stabilized, but too few configurations survived";
    } else if (iterationCap != null && result.iterations >= iterationCap) {
      value = "The run hit the SQD iteration cap";
    }
  }

  return {
    label: "Stopped because",
    value,
    helper: buildSqdHelper(payload),
    tone: result.converged ? "success" : "warning",
  };
}

function describeProjectedRunning(
  payload: Record<string, unknown> | null,
  noun: string,
): ConvergenceInsight {
  return {
    label: "Convergence check",
    value: "The final residual gate is evaluated at the projected solve",
    helper: joinParts([
      formatProgressCount(
        noun,
        asNumber(payload?.completed_iterations),
        asNumber(payload?.total_iterations),
      ),
    ]),
    tone: "warning",
  };
}

function describeResidualCompleted(
  relativeResidual: number | null,
  threshold: number | null,
  converged: boolean,
): ConvergenceInsight {
  return {
    label: "Stopped because",
    value: converged
      ? "The projected residual fell within tolerance"
      : "The projected residual stayed above tolerance",
    helper: joinParts([formatThresholdComparison("residual", relativeResidual, threshold)]),
    tone: converged ? "success" : "warning",
  };
}

function getProjectedOverlapSummary(converged: boolean, stabilityState: string | null): string {
  if (converged) {
    return "The projected overlap gate passed";
  }
  if (stabilityState === "stabilized") {
    return "The projected overlap solve needed stabilization, so it was not treated as converged";
  }
  return "The projected overlap gate was not satisfied";
}

function describeOverlapCompleted(
  overlapCondition: number | null,
  minEigenvalue: number | null,
  converged: boolean,
  stabilityState: string | null,
): ConvergenceInsight {
  return {
    label: "Stopped because",
    value: getProjectedOverlapSummary(converged, stabilityState),
    helper: joinParts([
      formatScientificDetail("condition", overlapCondition),
      formatScientificDetail("min eigenvalue", minEigenvalue),
    ]),
    tone: converged ? "success" : "warning",
  };
}

function describeKqdOrQfdCompleted(result: RunResultResponse): ConvergenceInsight {
  const metrics = metricsRecord(result);
  const matrixSummary = asRecord(metrics?.matrix_element_summary);
  const details =
    asRecord(metrics?.orthogonality_metrics) ?? asRecord(metrics?.conditioning_summary) ?? metrics;
  const convergenceBasis = asString(matrixSummary?.convergence_basis);
  const stabilityState =
    asString(asRecord(metrics?.stability_summary)?.stability_state) ??
    asString(asRecord(metrics?.orthogonality_metrics)?.stability_state) ??
    asString(asRecord(metrics?.conditioning_summary)?.stability_state) ??
    asString(details?.stability_state);

  if (convergenceBasis === "projected_overlap_condition") {
    return describeOverlapCompleted(
      asNumber(details?.overlap_condition),
      asNumber(details?.overlap_min_eigenvalue),
      result.converged,
      stabilityState,
    );
  }

  return describeResidualCompleted(
    asNumber(details?.relative_residual) ?? asNumber(details?.relative_ritz_residual),
    asNumber(details?.residual_tolerance) ?? asNumber(details?.residual_convergence_threshold),
    result.converged,
  );
}

function describeQseCompleted(result: RunResultResponse): ConvergenceInsight {
  const metrics = metricsRecord(result);
  return describeResidualCompleted(
    asNumber(metrics?.relative_residual),
    asNumber(metrics?.convergence_threshold),
    result.converged,
  );
}

function describeSkqdCompleted(result: RunResultResponse): ConvergenceInsight {
  const metrics = metricsRecord(result);
  const diagnostics = asRecord(metrics?.krylov_extension_diagnostics);
  const selectedSolution = asString(diagnostics?.selected_solution);
  const sqdConverged = asBoolean(diagnostics?.sqd_converged);
  const krylovConverged = asBoolean(diagnostics?.krylov_converged);

  let value = result.converged
    ? "The selected SKQD path satisfied its convergence gate"
    : "The selected SKQD path did not satisfy all convergence gates";
  if (selectedSolution === "sqd_core") {
    value = result.converged
      ? "The SQD core was selected and its recovery gate passed"
      : "The SQD core was selected, but its recovery gate did not pass";
  } else if (selectedSolution === "krylov_extension" && !result.converged) {
    value = skqdExtensionFailureMessage(value, sqdConverged, krylovConverged);
  } else if (selectedSolution === "krylov_extension" && result.converged) {
    value = "The Krylov extension was selected after both gates passed";
  }

  return {
    label: "Stopped because",
    value,
    helper: joinParts([
      selectedSolution ? `selected ${selectedSolution.replaceAll("_", " ")}` : null,
      yesNoGate("SQD", sqdConverged),
      yesNoGate("Krylov", krylovConverged),
      formatThresholdComparison(
        "residual",
        asNumber(diagnostics?.relative_residual) ?? asNumber(diagnostics?.relative_ritz_residual),
        asNumber(diagnostics?.residual_tolerance) ??
          asNumber(diagnostics?.residual_convergence_threshold),
      ),
    ]),
    tone: result.converged ? "success" : "warning",
  };
}

function describeCancelled(): ConvergenceInsight {
  return {
    label: "Stopped because",
    value: "The run was cancelled",
    tone: "muted",
  };
}

function describeFailed(): ConvergenceInsight {
  return {
    label: "Stopped because",
    value: "The run failed before convergence could be confirmed",
    tone: "destructive",
  };
}

function excludedStatusPayload(events: RunEventResponse[]): Record<string, unknown> | null {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const event = events[index];
    if (event?.type !== "status_changed") {
      continue;
    }
    const payload = asRecord(event.payload);
    if (payload?.status === "EXCLUDED") {
      return payload;
    }
  }
  return null;
}

function humanizeExclusionReason(reason: string | null): string | null {
  if (reason == null) return null;
  const words = reason.replaceAll("_", " ").trim();
  if (words.length === 0) return null;
  return `Excluded: ${words}`;
}

function describeExcluded(
  run: RunResponse,
  events: RunEventResponse[],
): ConvergenceInsight {
  const metadata = asRecord(run.metadata);
  const eventPayload = excludedStatusPayload(events);
  const message =
    asString(metadata?.exclusion_message) ??
    asString(eventPayload?.exclusion_message) ??
    humanizeExclusionReason(
      asString(metadata?.exclusion_reason) ?? asString(eventPayload?.exclusion_reason),
    ) ??
    "This configuration is unsupported on the selected target and was excluded";

  return {
    label: "Not run because",
    value: message,
    tone: "muted",
  };
}

function isConvergenceTone(value: string | null): value is ConvergenceInsight["tone"] {
  return value === "success" || value === "warning" || value === "destructive" || value === "muted";
}

function getExplicitResultEventLog(payload: Record<string, unknown>): ConvergenceResultLog | null {
  const explicitSummary = asString(payload.stop_reason);
  if (explicitSummary == null) {
    return null;
  }

  const explicitTone = asString(payload.stop_reason_tone);
  return {
    summary: explicitSummary,
    details: asString(payload.stop_reason_details) ?? undefined,
    tone: isConvergenceTone(explicitTone) ? explicitTone : "muted",
  };
}

function getVqeResultEventLog(
  converged: boolean,
  metrics: Record<string, unknown> | null,
  iterations: number | null,
): ConvergenceResultLog {
  const diagnostics = asRecord(metrics?.optimizer_diagnostics);
  const terminationReason = asString(diagnostics?.termination_reason);
  const message = asString(diagnostics?.message);
  const evaluations =
    asNumber(metrics?.objective_evaluations) ??
    asNumber(diagnostics?.objective_evaluations) ??
    asNumber(diagnostics?.function_evaluations) ??
    iterations;
  const budget =
    asNumber(metrics?.max_function_evaluations) ?? asNumber(diagnostics?.max_function_evaluations);
  let summary = converged
    ? "The optimizer reported convergence"
    : "The optimizer stopped without convergence";
  if (terminationReason === "ansatz_has_no_parameters") {
    summary = "The ansatz had no free parameters";
  } else if (terminationReason === "max_function_evaluations") {
    summary = "The run reached the function-evaluation budget";
  } else if (converged === false && message) {
    summary = message;
  }

  return {
    summary,
    details: joinParts([
      formatThresholdComparison(
        "|dE|",
        asNumber(diagnostics?.final_delta_energy),
        asNumber(diagnostics?.convergence_threshold),
        "Ha",
      ),
      formatProgressCount("evals", evaluations, budget),
    ]),
    tone: converged ? "success" : "warning",
  };
}

function getSqdResultEventLog(
  converged: boolean,
  metrics: Record<string, unknown> | null,
): ConvergenceResultLog {
  const trace = Array.isArray(metrics?.configuration_recovery_trace)
    ? metrics.configuration_recovery_trace
    : [];
  const lastTrace = asRecord(trace.at(-1));
  const postselection = asRecord(metrics?.postselection_summary);
  const accepted = asNumber(lastTrace?.accepted_samples);
  const minimumSelected = asNumber(postselection?.min_selected_configurations);
  let summary = "The SQD recovery gate was not satisfied";
  if (converged) {
    summary = "The SQD recovery gate passed";
  } else if (accepted != null && minimumSelected != null && accepted < minimumSelected) {
    summary = "The SQD recovery gate missed the minimum selected configuration count";
  }

  return {
    summary,
    details: joinParts([
      formatCountComparison("selected", accepted, minimumSelected),
      formatThresholdComparison("dE", asNumber(lastTrace?.delta_energy), null, "Ha"),
      formatThresholdComparison("dOcc", asNumber(lastTrace?.occupancy_delta), null),
    ]),
    tone: converged ? "success" : "warning",
  };
}

function getProjectedDetails(
  metrics: Record<string, unknown> | null,
): Record<string, unknown> | null {
  return (
    asRecord(metrics?.orthogonality_metrics) ?? asRecord(metrics?.conditioning_summary) ?? metrics
  );
}

function getProjectedStabilityState(
  metrics: Record<string, unknown> | null,
  details: Record<string, unknown> | null,
): string | null {
  return (
    asString(asRecord(metrics?.stability_summary)?.stability_state) ??
    asString(asRecord(metrics?.orthogonality_metrics)?.stability_state) ??
    asString(asRecord(metrics?.conditioning_summary)?.stability_state) ??
    asString(details?.stability_state)
  );
}

function getProjectedOverlapResultEventLog(
  converged: boolean,
  details: Record<string, unknown> | null,
  stabilityState: string | null,
): ConvergenceResultLog {
  return {
    summary: getProjectedOverlapSummary(converged, stabilityState),
    details: joinParts([
      formatScientificDetail("condition", asNumber(details?.overlap_condition)),
      formatScientificDetail("min eigenvalue", asNumber(details?.overlap_min_eigenvalue)),
    ]),
    tone: converged ? "success" : "warning",
  };
}

function getProjectedResultEventLog(
  converged: boolean,
  metrics: Record<string, unknown> | null,
): ConvergenceResultLog {
  const details = getProjectedDetails(metrics);
  const convergenceBasis = asString(asRecord(metrics?.matrix_element_summary)?.convergence_basis);
  if (convergenceBasis === "projected_overlap_condition") {
    return getProjectedOverlapResultEventLog(
      converged,
      details,
      getProjectedStabilityState(metrics, details),
    );
  }

  return getResidualResultEventLog(
    converged,
    asNumber(details?.relative_residual) ?? asNumber(details?.relative_ritz_residual),
    asNumber(details?.residual_tolerance) ?? asNumber(details?.residual_convergence_threshold),
  );
}

function getResidualResultEventLog(
  converged: boolean,
  relativeResidual: number | null,
  threshold: number | null,
): ConvergenceResultLog {
  return {
    summary: converged
      ? "The projected residual fell within tolerance"
      : "The projected residual stayed above tolerance",
    details: formatThresholdComparison("residual", relativeResidual, threshold) ?? undefined,
    tone: converged ? "success" : "warning",
  };
}

function getSkqdResultEventLog(
  converged: boolean,
  metrics: Record<string, unknown> | null,
): ConvergenceResultLog {
  const diagnostics = asRecord(metrics?.krylov_extension_diagnostics);
  const selectedSolution = asString(diagnostics?.selected_solution);
  const sqdConverged = asBoolean(diagnostics?.sqd_converged);
  const krylovConverged = asBoolean(diagnostics?.krylov_converged);

  let summary = converged
    ? "The selected SKQD path satisfied its convergence gate"
    : "The selected SKQD path did not satisfy all convergence gates";
  if (selectedSolution === "sqd_core") {
    summary = converged
      ? "The SQD core was selected and its recovery gate passed"
      : "The SQD core was selected, but its recovery gate did not pass";
  } else if (selectedSolution === "krylov_extension" && !converged) {
    summary = skqdExtensionFailureMessage(summary, sqdConverged, krylovConverged);
  } else if (selectedSolution === "krylov_extension" && converged) {
    summary = "The Krylov extension was selected after both gates passed";
  }

  return {
    summary,
    details: joinParts([
      selectedSolution ? `selected ${selectedSolution.replaceAll("_", " ")}` : null,
      yesNoGate("SQD", sqdConverged),
      yesNoGate("Krylov", krylovConverged),
    ]),
    tone: converged ? "success" : "warning",
  };
}

function getGenericResultEventLog(converged: boolean): ConvergenceResultLog {
  return {
    summary: converged
      ? "The solver-specific convergence rule passed"
      : "The solver-specific convergence rule did not pass",
    tone: converged ? "success" : "warning",
  };
}

export function getResultEventConvergenceLog(
  payload: Record<string, unknown>,
): ConvergenceResultLog | null {
  const explicitLog = getExplicitResultEventLog(payload);
  if (explicitLog != null) {
    return explicitLog;
  }

  const algorithm = asString(payload.algorithm)?.trim().toLowerCase();
  const converged = asBoolean(payload.converged);
  const iterations = asNumber(payload.iterations);
  const metrics = asRecord(payload.algorithm_metrics);

  if (converged == null) {
    return null;
  }

  if (algorithm === "vqe") return getVqeResultEventLog(converged, metrics, iterations);
  if (algorithm === "sqd") return getSqdResultEventLog(converged, metrics);
  if (algorithm === "kqd" || algorithm === "qfd") {
    return getProjectedResultEventLog(converged, metrics);
  }
  if (algorithm === "qse") {
    return getResidualResultEventLog(
      converged,
      asNumber(metrics?.relative_residual),
      asNumber(metrics?.convergence_threshold),
    );
  }
  if (algorithm === "skqd") return getSkqdResultEventLog(converged, metrics);
  return getGenericResultEventLog(converged);
}

function describeMissingResult(
  run: RunResponse,
  payload: Record<string, unknown> | null,
): ConvergenceInsight {
  if (payload == null) {
    return {
      label: "Convergence check",
      value: "Waiting for the first convergence sample",
      helper: "The solver has not emitted a progress update yet.",
      tone: "muted",
    };
  }
  if (
    run.algorithm === "sqd" ||
    (run.algorithm === "skqd" &&
      (payload.step === "configuration_recovery" || payload.occupancy_delta != null))
  ) {
    return describeSqdRunning(payload);
  }
  if (run.algorithm === "vqe") return describeVqeRunning(run, null, payload);
  if (run.algorithm === "kqd") return describeProjectedRunning(payload, "basis");
  if (run.algorithm === "qfd") return describeProjectedRunning(payload, "time points");
  if (run.algorithm === "qse") return describeProjectedRunning(payload, "subspace");
  if (run.algorithm === "skqd") return describeProjectedRunning(payload, "basis");
  return {
    label: "Convergence check",
    value: "Progress is still being collected",
    tone: "warning",
  };
}

function describeCompletedResult(
  run: RunResponse,
  result: RunResultResponse,
  payload: Record<string, unknown> | null,
): ConvergenceInsight {
  if (run.algorithm === "vqe") return describeVqeCompleted(run, result, payload);
  if (run.algorithm === "sqd") return describeSqdCompleted(run, result, payload);
  if (run.algorithm === "kqd" || run.algorithm === "qfd") {
    return describeKqdOrQfdCompleted(result);
  }
  if (run.algorithm === "qse") return describeQseCompleted(result);
  if (run.algorithm === "skqd") return describeSkqdCompleted(result);
  return {
    label: "Stopped because",
    value: result.converged
      ? "The solver-specific convergence rule passed"
      : "The solver-specific convergence rule did not pass",
    tone: result.converged ? "success" : "warning",
  };
}

export function getConvergenceInsight(
  run: RunResponse,
  result: RunResultResponse | null,
  events: RunEventResponse[],
): ConvergenceInsight | null {
  const payload = latestIterationPayload(events);

  if (run.status === "FAILED") {
    return describeFailed();
  }
  if (run.status === "CANCELLED") {
    return describeCancelled();
  }
  if (run.status === "EXCLUDED") {
    return describeExcluded(run, events);
  }
  if (result == null) {
    return describeMissingResult(run, payload);
  }

  return describeCompletedResult(run, result, payload);
}
