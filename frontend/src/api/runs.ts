/** Run, run-control, result, metadata, and validation API calls. */

import type {
  ApiRunActionResponse,
  ApiRunCancelResponse,
  ApiRunCreate,
  ApiRunEstimate,
  ApiRunEventListResponse,
  ApiRunEventResponse,
  ApiExportBundle,
  ApiRunListResponse,
  ApiRunResponse,
  ApiRunResultResponse,
  ApiRunRestartRequest,
  ApiRunSummaryListResponse,
  ApiRunSummaryResponse,
  ApiRunValidationErrorDetail,
  ApiRunValidationRequest,
  ApiRunValidationResponse,
  GetRunConfigMetadataResponse,
} from "@/types/api";
import type {
  BackendTarget,
  RunConfigJson,
  RunEstimate,
  RunCancelResponse,
  RunControlResponse,
  RunCreate,
  RunEventResponse,
  RunEventListResponse,
  RunListParams,
  RunListResponse,
  RunResponse,
  RunRestartResponse,
  RunResultResponse,
  RunSummaryListResponse,
  RunSummaryResponse,
  RunValidationRequest,
  RunValidationResponse,
  RunValidationErrorDetail,
  UUID,
} from "@/types/run";
import { isBackendTarget, isRunAlgorithm, isRunEventType, isRunStatus } from "@/types/run-status";
import {
  API_BASE,
  fetchWithApiError,
  handleApiError,
  invalidApiResponse,
  isFiniteNumber,
  isOptionalNullableBoolean,
  isOptionalNullableGuard,
  isOptionalNullableNumber,
  isOptionalNullableRecord,
  isOptionalNullableString,
  isStringArray,
  isRecord,
  operatorProtectedApiUrl,
  request,
} from "./http";

const RUN_MODE_VALUES = new Set(["easy", "advanced"] as const);
const EASY_GOAL_VALUES = new Set(["fastest", "balanced", "best_accuracy"] as const);

function isConfigChoiceMetadata(value: unknown): boolean {
  if (
    !isRecord(value) ||
    typeof value.id !== "string" ||
    typeof value.label !== "string" ||
    ("aliases" in value && !isStringArray(value.aliases)) ||
    !isOptionalNullableString(value, "description") ||
    ("metadata" in value && !isRecord(value.metadata)) ||
    ("supported_algorithms" in value &&
      (!Array.isArray(value.supported_algorithms) ||
        !value.supported_algorithms.every(isRunAlgorithm)))
  ) {
    return false;
  }
  return true;
}

function isEasyGoalPreset(value: unknown): boolean {
  return (
    isRecord(value) &&
    EASY_GOAL_VALUES.has(value.goal as "fastest" | "balanced" | "best_accuracy") &&
    typeof value.label === "string" &&
    isFiniteNumber(value.chemical_accuracy_target_ha) &&
    value.chemical_accuracy_target_ha > 0
  );
}

function isBooleanRecordMap(value: unknown): boolean {
  return (
    isRecord(value) &&
    Object.values(value).every(
      (entry) => isRecord(entry) && Object.values(entry).every((item) => typeof item === "boolean"),
    )
  );
}

function isRecommendationCatalog(value: unknown): boolean {
  return (
    isRecord(value) &&
    Object.values(value).every(
      (goalMap) =>
        isRecord(goalMap) &&
        Object.values(goalMap).every((recommendation) => isRecord(recommendation)),
    )
  );
}

function isNumberRecordMap(value: unknown): boolean {
  return (
    isRecord(value) &&
    Object.values(value).every(
      (entry) => isRecord(entry) && Object.values(entry).every(isFiniteNumber),
    )
  );
}

export function parseRunConfigMetadataResponse(value: unknown): GetRunConfigMetadataResponse {
  if (
    !isRecord(value) ||
    !Array.isArray(value.algorithms) ||
    !value.algorithms.every(isRunAlgorithm) ||
    !Array.isArray(value.ansatzes) ||
    !value.ansatzes.every(isConfigChoiceMetadata) ||
    !Array.isArray(value.backend_targets) ||
    !value.backend_targets.every(isBackendTarget) ||
    typeof value.catalog_version !== "string" ||
    !Array.isArray(value.easy_goals) ||
    !value.easy_goals.every((goal) =>
      EASY_GOAL_VALUES.has(goal as "fastest" | "balanced" | "best_accuracy"),
    ) ||
    !Array.isArray(value.easy_goal_presets) ||
    !value.easy_goal_presets.every(isEasyGoalPreset) ||
    !Array.isArray(value.optimizers) ||
    !value.optimizers.every(isConfigChoiceMetadata) ||
    ("capabilities" in value && !isBooleanRecordMap(value.capabilities)) ||
    ("defaults" in value && !isRecord(value.defaults)) ||
    ("limits" in value && !isNumberRecordMap(value.limits)) ||
    ("recommendations" in value && !isRecommendationCatalog(value.recommendations))
  ) {
    throw invalidApiResponse("Invalid run configuration metadata response");
  }
  return value as GetRunConfigMetadataResponse;
}

function isRunResponse(value: unknown): value is ApiRunResponse {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.molecule_id === "string" &&
    isRecord(value.config_json) &&
    typeof value.created_at === "string" &&
    isFiniteNumber(value.execution_generation) &&
    isRunStatus(value.status) &&
    typeof value.updated_at === "string" &&
    isOptionalNullableGuard(value, "algorithm", isRunAlgorithm) &&
    isOptionalNullableGuard(value, "backend_target", isBackendTarget) &&
    isOptionalNullableString(value, "basis_set") &&
    isOptionalNullableString(value, "client_request_id") &&
    isOptionalNullableString(value, "credential_profile_id") &&
    isOptionalNullableString(value, "credential_profile_name") &&
    isOptionalNullableString(value, "ibm_job_id") &&
    isOptionalNullableRecord(value, "initial_estimate") &&
    isOptionalNullableRecord(value, "latest_estimate") &&
    isOptionalNullableRecord(value, "metadata") &&
    isOptionalNullableGuard(value, "mode", (candidate) =>
      RUN_MODE_VALUES.has(candidate as "easy" | "advanced"),
    ) &&
    isOptionalNullableString(value, "restarted_from_run_id") &&
    isOptionalNullableRecord(value, "versions")
  );
}

function isRunExecutionSegmentResponse(value: unknown): boolean {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.run_id === "string" &&
    isFiniteNumber(value.execution_generation) &&
    isFiniteNumber(value.attempt_number) &&
    typeof value.status === "string" &&
    typeof value.worker_started_at === "string" &&
    isOptionalNullableString(value, "rq_job_id") &&
    isOptionalNullableString(value, "worker_finished_at") &&
    isOptionalNullableNumber(value, "duration_seconds") &&
    isOptionalNullableString(value, "last_heartbeat_at") &&
    isOptionalNullableNumber(value, "last_heartbeat_duration_seconds") &&
    isOptionalNullableString(value, "termination_reason")
  );
}

export function parseRunResponse(value: unknown): ApiRunResponse {
  if (!isRunResponse(value)) {
    throw invalidApiResponse("Invalid run response");
  }
  return value;
}

function isRunSummaryResponse(value: unknown): value is ApiRunSummaryResponse {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.molecule_id === "string" &&
    typeof value.created_at === "string" &&
    isFiniteNumber(value.execution_generation) &&
    isRunStatus(value.status) &&
    typeof value.updated_at === "string" &&
    isOptionalNullableGuard(value, "algorithm", isRunAlgorithm) &&
    isOptionalNullableGuard(value, "backend_target", isBackendTarget) &&
    isOptionalNullableString(value, "backend_name") &&
    isOptionalNullableString(value, "basis_set") &&
    isOptionalNullableBoolean(value, "chemical_accurate") &&
    isOptionalNullableBoolean(value, "converged") &&
    isOptionalNullableString(value, "credential_profile_id") &&
    isOptionalNullableString(value, "credential_profile_name") &&
    isOptionalNullableRecord(value, "latest_estimate") &&
    isOptionalNullableRecord(value, "metadata") &&
    isOptionalNullableString(value, "molecule_name") &&
    isOptionalNullableString(value, "restarted_from_run_id")
  );
}

export function parseRunListResponse(value: unknown): ApiRunListResponse {
  if (
    !isRecord(value) ||
    !Array.isArray(value.items) ||
    !value.items.every(isRunResponse) ||
    !isFiniteNumber(value.total) ||
    !isFiniteNumber(value.limit) ||
    !isFiniteNumber(value.offset)
  ) {
    throw invalidApiResponse("Invalid run list response");
  }
  return value as ApiRunListResponse;
}

export function parseRunSummaryListResponse(value: unknown): ApiRunSummaryListResponse {
  if (
    !isRecord(value) ||
    !Array.isArray(value.items) ||
    !value.items.every(isRunSummaryResponse) ||
    !isFiniteNumber(value.total) ||
    !isFiniteNumber(value.limit) ||
    !isFiniteNumber(value.offset)
  ) {
    throw invalidApiResponse("Invalid run summary list response");
  }
  return value as ApiRunSummaryListResponse;
}

function isRunActionResponse(value: unknown): value is ApiRunActionResponse {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    isFiniteNumber(value.execution_generation) &&
    isRunStatus(value.status) &&
    isOptionalNullableString(value, "checkpoint_id") &&
    isOptionalNullableString(value, "child_run_id") &&
    isOptionalNullableString(value, "message")
  );
}

export function parseRunActionResponse(value: unknown): ApiRunActionResponse {
  if (!isRunActionResponse(value)) {
    throw invalidApiResponse("Invalid run action response");
  }
  return value;
}

function isRunCancelResponse(value: unknown): value is ApiRunCancelResponse {
  return isRecord(value) && typeof value.id === "string" && isRunStatus(value.status);
}

export function parseRunCancelResponse(value: unknown): ApiRunCancelResponse {
  if (!isRunCancelResponse(value)) {
    throw invalidApiResponse("Invalid run cancellation response");
  }
  return value;
}

function isRunResultResponse(value: unknown): value is ApiRunResultResponse {
  return (
    isRecord(value) &&
    typeof value.run_id === "string" &&
    isFiniteNumber(value.energy) &&
    isFiniteNumber(value.iterations) &&
    Array.isArray(value.optimal_parameters) &&
    value.optimal_parameters.every(isFiniteNumber) &&
    typeof value.converged === "boolean" &&
    typeof value.created_at === "string" &&
    isOptionalNullableRecord(value, "algorithm_metrics") &&
    isOptionalNullableNumber(value, "best_observed_energy") &&
    isOptionalNullableRecord(value, "energy_policy") &&
    isOptionalNullableNumber(value, "final_energy") &&
    isOptionalNullableString(value, "reference_basis") &&
    isOptionalNullableNumber(value, "reference_energy") &&
    isOptionalNullableNumber(value, "reported_energy") &&
    isOptionalNullableString(value, "reported_energy_source") &&
    isOptionalNullableNumber(value, "signed_error")
  );
}

export function parseRunResultResponse(value: unknown): ApiRunResultResponse {
  if (!isRunResultResponse(value)) {
    throw invalidApiResponse("Invalid run result response");
  }
  return value;
}

function isRunEventResponse(value: unknown): value is ApiRunEventResponse {
  return (
    isRecord(value) &&
    isFiniteNumber(value.id) &&
    isRecord(value.payload) &&
    typeof value.run_id === "string" &&
    isFiniteNumber(value.sequence) &&
    isRunEventType(value.type) &&
    typeof value.created_at === "string"
  );
}

export function parseRunEventListResponse(value: unknown): ApiRunEventListResponse {
  if (
    !isRecord(value) ||
    !Array.isArray(value.events) ||
    !value.events.every(isRunEventResponse) ||
    !isFiniteNumber(value.last_sequence)
  ) {
    throw invalidApiResponse("Invalid run event list response");
  }
  return value as ApiRunEventListResponse;
}

function isRunValidationError(value: unknown): value is ApiRunValidationErrorDetail {
  return (
    isRecord(value) &&
    typeof value.field === "string" &&
    typeof value.message === "string" &&
    isOptionalNullableString(value, "code") &&
    isOptionalNullableString(value, "suggestion")
  );
}

export function parseRunValidationResponse(value: unknown): ApiRunValidationResponse {
  if (
    !isRecord(value) ||
    typeof value.valid !== "boolean" ||
    ("errors" in value &&
      (!Array.isArray(value.errors) || !value.errors.every(isRunValidationError))) ||
    ("warnings" in value &&
      (!Array.isArray(value.warnings) ||
        !value.warnings.every((warning) => typeof warning === "string"))) ||
    !isOptionalNullableRecord(value, "estimate")
  ) {
    throw invalidApiResponse("Invalid run validation response");
  }
  return value as ApiRunValidationResponse;
}

export function parseExportBundleResponse(value: unknown): ApiExportBundle {
  if (
    !isRecord(value) ||
    typeof value.export_version !== "string" ||
    typeof value.exported_at !== "string" ||
    !isRecord(value.molecule) ||
    !Array.isArray(value.events) ||
    !value.events.every(isRunEventResponse) ||
    !(value.result === null || isRunResultResponse(value.result)) ||
    !isRunResponse(value.run) ||
    ("execution_segments" in value &&
      (!Array.isArray(value.execution_segments) ||
        !value.execution_segments.every(isRunExecutionSegmentResponse))) ||
    !(value.versions === null || isRecord(value.versions))
  ) {
    throw invalidApiResponse("Invalid run export response");
  }
  return value as ApiExportBundle;
}

function requiresOperatorProtectedRunPath(data: {
  backend_target: BackendTarget;
  noise_profile?: { source?: string | null } | null;
}): boolean {
  return (
    data.backend_target === "ibm_runtime" ||
    (data.backend_target === "aer_simulator" && data.noise_profile?.source === "backend_derived")
  );
}

function toStringRecord(
  data: Record<string, unknown> | null | undefined,
): Record<string, string> | null {
  if (!data) {
    return null;
  }

  const result: Record<string, string> = {};
  for (const [key, value] of Object.entries(data)) {
    if (typeof value === "string") {
      result[key] = value;
    }
  }
  return result;
}

function toRunEstimate(data: ApiRunEstimate | null | undefined): RunEstimate | null {
  if (!data) {
    return null;
  }

  return {
    ...data,
    estimated_total_iterations: data.estimated_total_iterations ?? null,
    estimated_remaining_iterations: data.estimated_remaining_iterations ?? null,
    estimated_total_seconds: data.estimated_total_seconds ?? null,
    estimated_remaining_seconds: data.estimated_remaining_seconds ?? null,
    confidence: data.confidence ?? null,
  };
}

function toRunResponse(data: ApiRunResponse): RunResponse {
  return {
    ...data,
    id: data.id as UUID,
    molecule_id: data.molecule_id as UUID,
    config_json: data.config_json as RunConfigJson,
    ibm_job_id: data.ibm_job_id ?? null,
    client_request_id: data.client_request_id ? (data.client_request_id as UUID) : null,
    versions: toStringRecord(data.versions),
    metadata: data.metadata ?? null,
    initial_estimate: toRunEstimate(data.initial_estimate),
    latest_estimate: toRunEstimate(data.latest_estimate),
    execution_generation: data.execution_generation ?? 1,
    restarted_from_run_id: data.restarted_from_run_id ? (data.restarted_from_run_id as UUID) : null,
    credential_profile_id: data.credential_profile_id ? (data.credential_profile_id as UUID) : null,
    credential_profile_name: data.credential_profile_name ?? null,
  };
}

function toRunList(data: ApiRunListResponse): RunListResponse {
  return {
    ...data,
    items: data.items.map(toRunResponse),
  };
}

function toRunSummary(data: ApiRunSummaryResponse): RunSummaryResponse {
  return {
    ...data,
    id: data.id as UUID,
    molecule_id: data.molecule_id as UUID,
    metadata: data.metadata ?? null,
    latest_estimate: toRunEstimate(data.latest_estimate),
    execution_generation: data.execution_generation ?? 1,
    restarted_from_run_id: data.restarted_from_run_id ? (data.restarted_from_run_id as UUID) : null,
    credential_profile_id: data.credential_profile_id ? (data.credential_profile_id as UUID) : null,
    credential_profile_name: data.credential_profile_name ?? null,
  };
}

function toRunSummaryList(data: ApiRunSummaryListResponse): RunSummaryListResponse {
  return {
    ...data,
    items: data.items.map(toRunSummary),
  };
}

function toRunCancel(data: ApiRunCancelResponse): RunCancelResponse {
  return {
    ...data,
    id: data.id as UUID,
  };
}

function toRunControl(data: ApiRunActionResponse): RunControlResponse {
  return {
    ...data,
    id: data.id as UUID,
    execution_generation: data.execution_generation ?? 1,
    child_run_id: data.child_run_id ? (data.child_run_id as UUID) : null,
    checkpoint_id: data.checkpoint_id ? (data.checkpoint_id as UUID) : null,
    message: data.message ?? null,
  };
}

function toRunResult(data: ApiRunResultResponse): RunResultResponse {
  return {
    ...data,
    run_id: data.run_id as UUID,
    algorithm_metrics: data.algorithm_metrics as RunResultResponse["algorithm_metrics"],
    energy_policy: data.energy_policy as RunResultResponse["energy_policy"],
  };
}

function toRunEvent(data: ApiRunEventResponse): RunEventResponse {
  return {
    ...data,
    run_id: data.run_id as UUID,
  };
}

function toRunEventList(data: ApiRunEventListResponse): RunEventListResponse {
  return {
    ...data,
    events: data.events.map(toRunEvent),
  };
}

function toValidationError(data: ApiRunValidationErrorDetail): RunValidationErrorDetail {
  return {
    ...data,
    code: data.code ?? null,
    suggestion: data.suggestion ?? null,
  };
}

function toValidationResponse(data: ApiRunValidationResponse): RunValidationResponse {
  return {
    ...data,
    errors: (data.errors ?? []).map(toValidationError),
    warnings: data.warnings ?? [],
    estimate: toRunEstimate(data.estimate),
  };
}

function toApiRunCreate(data: RunCreate): ApiRunCreate {
  return {
    ...data,
    molecule_id: data.molecule_id as string,
    client_request_id: data.client_request_id as string | undefined,
    ibm_runtime_confirmed: data.ibm_runtime_confirmed ?? false,
  } as ApiRunCreate;
}

function toApiRunValidationRequest(data: RunValidationRequest): ApiRunValidationRequest {
  return {
    molecule_id: data.molecule_id as string,
    run: toApiRunCreate(data.run),
  };
}

function toApiRunRestartRequest(cancelActive: boolean): ApiRunRestartRequest {
  return {
    cancel_active: cancelActive,
  };
}

export async function createRun(data: RunCreate): Promise<RunResponse> {
  const url = requiresOperatorProtectedRunPath(data)
    ? operatorProtectedApiUrl("/api/runs")
    : `${API_BASE}/api/runs`;
  const response = parseRunResponse(
    await request<unknown>(url, {
      method: "POST",
      body: JSON.stringify(toApiRunCreate(data)),
    }),
  );
  return toRunResponse(response);
}

export async function getRun(id: UUID): Promise<RunResponse> {
  const response = parseRunResponse(
    await request<unknown>(`${API_BASE}/api/runs/${id}`, {
      method: "GET",
    }),
  );
  return toRunResponse(response);
}

export async function deleteRun(id: UUID): Promise<void> {
  const response = await fetchWithApiError(`${API_BASE}/api/runs/${id}`, {
    method: "DELETE",
    headers: new Headers({ Accept: "application/json" }),
  });
  if (!response.ok) {
    await handleApiError(response);
  }
}

function appendDefinedQueryParam(
  query: URLSearchParams,
  key: string,
  value: string | number | boolean | undefined,
): void {
  if (value !== undefined) {
    query.append(key, String(value));
  }
}

function buildRunsQuery(params?: RunListParams): string {
  if (!params) {
    return "";
  }

  const query = new URLSearchParams();
  appendDefinedQueryParam(query, "molecule_id", params.molecule_id);
  appendDefinedQueryParam(query, "status", params.status);
  appendDefinedQueryParam(query, "backend_target", params.backend_target);
  appendDefinedQueryParam(query, "converged", params.converged);
  appendDefinedQueryParam(query, "chemical_accurate", params.chemical_accurate);
  appendDefinedQueryParam(query, "limit", params.limit);
  appendDefinedQueryParam(query, "offset", params.offset);

  return query.toString();
}

function urlWithQuery(path: string, queryString: string): string {
  const basePath = `${API_BASE}${path}`;
  return queryString.length === 0 ? basePath : `${basePath}?${queryString}`;
}

export async function listRuns(params?: RunListParams): Promise<RunListResponse> {
  const url = urlWithQuery("/api/runs", buildRunsQuery(params));
  const response = parseRunListResponse(
    await request<unknown>(url, {
      method: "GET",
    }),
  );
  return toRunList(response);
}

// Run summaries avoid fetching full config/version payloads for every visible row.
export async function listRunSummaries(params?: RunListParams): Promise<RunSummaryListResponse> {
  const url = urlWithQuery("/api/runs/summaries", buildRunsQuery(params));
  const response = parseRunSummaryListResponse(
    await request<unknown>(url, {
      method: "GET",
    }),
  );
  return toRunSummaryList(response);
}

let runConfigMetadataCache: GetRunConfigMetadataResponse | null = null;
let runConfigMetadataRequest: Promise<GetRunConfigMetadataResponse> | null = null;
const RUN_CONFIG_METADATA_TIMEOUT_MS = 1500;

export async function fetchRunConfigMetadata(): Promise<GetRunConfigMetadataResponse> {
  if (runConfigMetadataCache) {
    return runConfigMetadataCache;
  }
  if (runConfigMetadataRequest) {
    return runConfigMetadataRequest;
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), RUN_CONFIG_METADATA_TIMEOUT_MS);
  runConfigMetadataRequest = request<unknown>(`${API_BASE}/api/runs/config-metadata`, {
    method: "GET",
    signal: controller.signal,
  })
    .then(parseRunConfigMetadataResponse)
    .then((response) => {
      runConfigMetadataCache = response;
      return response;
    })
    .finally(() => {
      clearTimeout(timeoutId);
      runConfigMetadataRequest = null;
    });

  return runConfigMetadataRequest;
}

export async function cancelRun(id: UUID): Promise<RunCancelResponse> {
  const response = parseRunCancelResponse(
    await request<unknown>(`${API_BASE}/api/runs/${id}/cancel`, {
      method: "POST",
    }),
  );
  return toRunCancel(response);
}

export async function pauseRun(id: UUID): Promise<RunControlResponse> {
  const response = parseRunActionResponse(
    await request<unknown>(`${API_BASE}/api/runs/${id}/pause`, {
      method: "POST",
    }),
  );
  return toRunControl(response);
}

export async function resumeRun(id: UUID): Promise<RunControlResponse> {
  const response = parseRunActionResponse(
    await request<unknown>(operatorProtectedApiUrl(`/api/runs/${id}/resume`), {
      method: "POST",
    }),
  );
  return toRunControl(response);
}

// Restart returns the compact action response described by the OpenAPI contract.
export async function restartRun(id: UUID, cancelActive = false): Promise<RunRestartResponse> {
  const response = parseRunActionResponse(
    await request<unknown>(operatorProtectedApiUrl(`/api/runs/${id}/restart`), {
      method: "POST",
      body: JSON.stringify(toApiRunRestartRequest(cancelActive)),
    }),
  );
  return toRunControl(response);
}

export async function getRunResult(id: UUID): Promise<RunResultResponse> {
  const response = parseRunResultResponse(
    await request<unknown>(`${API_BASE}/api/runs/${id}/result`, {
      method: "GET",
    }),
  );
  return toRunResult(response);
}

export async function getRunEvents(
  id: UUID,
  afterSequence?: number,
): Promise<RunEventListResponse> {
  const query = new URLSearchParams();
  if (afterSequence !== undefined) query.append("after_sequence", String(afterSequence));

  const queryString = query.toString();
  const url =
    queryString.length > 0
      ? `${API_BASE}/api/runs/${id}/events?${queryString}`
      : `${API_BASE}/api/runs/${id}/events`;

  const response = parseRunEventListResponse(
    await request<unknown>(url, {
      method: "GET",
    }),
  );
  return toRunEventList(response);
}

export async function exportRun(id: UUID): Promise<ApiExportBundle> {
  return parseExportBundleResponse(
    await request<unknown>(`${API_BASE}/api/runs/${id}/export`, {
      method: "GET",
    }),
  );
}

export async function validateRunRequest(
  data: RunValidationRequest,
): Promise<RunValidationResponse> {
  const url = requiresOperatorProtectedRunPath(data.run)
    ? operatorProtectedApiUrl("/api/validate/config")
    : `${API_BASE}/api/validate/config`;
  const response = parseRunValidationResponse(
    await request<unknown>(url, {
      method: "POST",
      body: JSON.stringify(toApiRunValidationRequest(data)),
    }),
  );
  return toValidationResponse(response);
}
