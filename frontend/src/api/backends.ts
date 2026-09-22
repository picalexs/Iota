/** Backend discovery, capability normalization, and cache refresh API calls. */

import type {
  ApiBackendTarget,
  ApiBackendListResponse,
  ApiTranspilePreviewRequest,
  ApiTranspilePreviewResponse,
} from "@/types/api";
import type {
  BackendCapabilitiesResponse,
  BackendTarget,
  TranspilationPreviewRequest,
  TranspilationPreviewResponse,
  UUID,
} from "@/types/run";
import { invalidApiResponse, isRecord, operatorProtectedApiUrl, request } from "./http";
import {
  ACTIVE_BACKEND_CAPABILITIES_CACHE_KEY,
  BACKEND_CAPABILITIES_BACKGROUND_RETRY_DELAY_MS,
  clearBackgroundRefreshTimer,
  deleteBackendCapabilitiesRequest,
  getActiveBackendCapabilitiesProfile,
  getBackendCapabilitiesFetchProfileId,
  getBackgroundRefreshTimer,
  getBackendCapabilitiesRefreshKeys,
  getBackendCapabilitiesRequest,
  getCachedBackendCapabilitiesEntry,
  hasBackendCapabilitiesRequest,
  resetBackendCapabilitiesState,
  setBackendCapabilitiesRequest,
  setBackgroundRefreshTimer,
  storeBackendCapabilitiesCache,
} from "./backend-capabilities-cache";
import { notifyIbmCredentialProfilesChanged } from "@/lib/ibm-profile-events";

export { setActiveBackendCapabilitiesProfile } from "./backend-capabilities-cache";

type BackendCapabilityApiEntry = ApiBackendListResponse["backends"][number];

const BACKEND_TARGET_VALUES = new Set<ApiBackendTarget>([
  "statevector",
  "aer_simulator",
  "ibm_runtime",
]);

function isBackendSummary(value: unknown): value is BackendCapabilityApiEntry {
  return (
    isRecord(value) &&
    BACKEND_TARGET_VALUES.has(value.target as ApiBackendTarget) &&
    typeof value.name === "string" &&
    typeof value.display_name === "string" &&
    typeof value.available === "boolean" &&
    typeof value.simulator === "boolean" &&
    typeof value.supports_noise_profile === "boolean" &&
    typeof value.supports_transpile_preview === "boolean"
  );
}

export function parseBackendListResponse(value: unknown): ApiBackendListResponse {
  if (
    !isRecord(value) ||
    !Array.isArray(value.backends) ||
    !value.backends.every(isBackendSummary) ||
    ("warnings" in value &&
      (!Array.isArray(value.warnings) ||
        !value.warnings.every((warning) => typeof warning === "string")))
  ) {
    throw invalidApiResponse("Invalid backend list response");
  }
  return value as ApiBackendListResponse;
}

export function parseTranspilePreviewResponse(value: unknown): ApiTranspilePreviewResponse {
  if (
    !isRecord(value) ||
    !BACKEND_TARGET_VALUES.has(value.target as ApiBackendTarget) ||
    typeof value.feasible !== "boolean" ||
    typeof value.requested_qubits !== "number" ||
    !Number.isFinite(value.requested_qubits) ||
    !(
      !("backend_name" in value) ||
      value.backend_name === null ||
      typeof value.backend_name === "string"
    ) ||
    ("metadata" in value && !isRecord(value.metadata)) ||
    ("warnings" in value &&
      (!Array.isArray(value.warnings) ||
        !value.warnings.every((warning) => typeof warning === "string")))
  ) {
    throw invalidApiResponse("Invalid transpilation preview response");
  }
  return value as ApiTranspilePreviewResponse;
}

function backendCapabilitiesUrl(profileId?: UUID | null): string {
  if (profileId == null) {
    return operatorProtectedApiUrl("/api/backends");
  }
  const query = new URLSearchParams({ credential_profile_id: profileId });
  return operatorProtectedApiUrl(`/api/backends?${query.toString()}`);
}

function groupBackendCapabilitiesByTarget(
  backends: BackendCapabilityApiEntry[],
): Map<BackendTarget, BackendCapabilityApiEntry[]> {
  const grouped = new Map<BackendTarget, BackendCapabilityApiEntry[]>();
  for (const backend of backends) {
    const group = grouped.get(backend.target) ?? [];
    group.push(backend);
    grouped.set(backend.target, group);
  }
  return grouped;
}

function summarizeBackendBooleanState(
  entries: BackendCapabilityApiEntry[],
  key: "credential_configured" | "credentials_usable",
): boolean | null {
  if (entries.some((entry) => entry[key] === true)) {
    return true;
  }
  if (entries.some((entry) => entry[key] === false)) {
    return false;
  }
  return null;
}

function isBackendCapabilityDevice(
  target: BackendTarget,
  entry: BackendCapabilityApiEntry,
): boolean {
  if (target === "statevector" || target === "ibm_runtime") {
    return entry.name !== target;
  }
  return true;
}

function mapBackendCapabilityDevice(
  entry: BackendCapabilityApiEntry,
): NonNullable<BackendCapabilitiesResponse["backends"][number]["backends"]>[number] {
  return {
    name: entry.name,
    simulator: entry.simulator,
    operational: entry.operational,
    pending_jobs: entry.pending_jobs,
    num_qubits: entry.num_qubits,
    basis_gates: entry.basis_gates,
    coupling_map: entry.coupling_map,
    coupling_map_edges: entry.coupling_map_edges,
    max_shots: entry.max_shots,
    error_rate: entry.error_rate,
    processor_type: entry.processor_type,
    qubit_errors: entry.qubit_errors as NonNullable<
      BackendCapabilitiesResponse["backends"][number]["backends"]
    >[number]["qubit_errors"],
    gate_errors: entry.gate_errors as NonNullable<
      BackendCapabilitiesResponse["backends"][number]["backends"]
    >[number]["gate_errors"],
  };
}

function buildBackendCapabilitySummary(
  target: BackendTarget,
  entries: BackendCapabilityApiEntry[],
): BackendCapabilitiesResponse["backends"][number] {
  const primary = entries[0];
  const credentialConfigured = summarizeBackendBooleanState(entries, "credential_configured");
  const credentialsUsable = summarizeBackendBooleanState(entries, "credentials_usable");
  const devices = entries
    .filter((entry) => isBackendCapabilityDevice(target, entry))
    .map(mapBackendCapabilityDevice);
  const available = entries.some((entry) => entry.available);
  const isIbmRuntime = target === "ibm_runtime";

  return {
    target,
    enabled: isIbmRuntime ? available || credentialsUsable === true : available,
    available,
    credential_configured: isIbmRuntime ? credentialConfigured : true,
    credentials_usable: isIbmRuntime ? credentialsUsable : true,
    supports_noise_profile: entries.some((entry) => entry.supports_noise_profile),
    supports_transpilation_preview: entries.some((entry) => entry.supports_transpile_preview),
    reason: primary?.status_message ?? null,
    status: primary?.available ? "available" : "unavailable",
    backends: devices,
    default_backend: devices[0]?.name ?? primary?.name ?? null,
  };
}

function shouldRetryIbmCapabilityWarmup(data: BackendCapabilitiesResponse): boolean {
  const ibmCapability = data.backends.find((backend) => backend.target === "ibm_runtime");
  return (
    ibmCapability?.credential_configured === true &&
    ibmCapability.available !== true &&
    ibmCapability.credentials_usable !== false
  );
}

function toApiBackendOptions(
  data: TranspilationPreviewRequest["backend_options"],
): NonNullable<ApiTranspilePreviewRequest["backend_options"]> {
  return {
    ...data,
    aer_method: data.aer_method ?? "automatic",
    estimator_precision: 0,
  };
}

function queueBackgroundBackendCapabilitiesRefresh(profileId?: UUID | null): void {
  if (getBackgroundRefreshTimer(profileId) != null) {
    return;
  }

  const timer = setTimeout(() => {
    clearBackgroundRefreshTimer(profileId);
    void forceRefreshBackendCapabilities(profileId).catch(() => undefined);
  }, BACKEND_CAPABILITIES_BACKGROUND_RETRY_DELAY_MS);
  setBackgroundRefreshTimer(profileId, timer);
}

export async function fetchBackendCapabilities(
  profileId?: UUID | null,
): Promise<BackendCapabilitiesResponse> {
  const resolvedProfileId = getBackendCapabilitiesFetchProfileId(profileId);
  const inflight = getBackendCapabilitiesRequest(resolvedProfileId);
  if (inflight != null) {
    return inflight;
  }

  const cached = getCachedBackendCapabilitiesEntry(resolvedProfileId);
  if (cached != null) {
    return cached.data;
  }

  const stale = getCachedBackendCapabilitiesEntry(resolvedProfileId, { allowStale: true });
  if (stale != null) {
    void forceRefreshBackendCapabilities(resolvedProfileId).catch(() => undefined);
    return stale.data;
  }

  const request = fetchBackendCapabilitiesUncached(resolvedProfileId)
    .then((data) => {
      storeBackendCapabilitiesCache(resolvedProfileId, data);
      return data;
    })
    .finally(() => {
      deleteBackendCapabilitiesRequest(resolvedProfileId);
    });
  setBackendCapabilitiesRequest(resolvedProfileId, request);

  void request.then((data) => {
    if (shouldRetryIbmCapabilityWarmup(data)) {
      queueBackgroundBackendCapabilitiesRefresh(resolvedProfileId);
    }
  });

  return request;
}

async function fetchBackendCapabilitiesUncached(
  profileId?: UUID | null,
): Promise<BackendCapabilitiesResponse> {
  const response = parseBackendListResponse(
    await request<unknown>(backendCapabilitiesUrl(profileId), {
      method: "GET",
    }),
  );
  const grouped = groupBackendCapabilitiesByTarget(response.backends);

  return {
    backends: Array.from(grouped.entries()).map(([target, entries]) =>
      buildBackendCapabilitySummary(target, entries),
    ),
  };
}

export function getBackendCapabilitiesCached(
  profileId?: UUID | null,
): BackendCapabilitiesResponse | null {
  const cached =
    getCachedBackendCapabilitiesEntry(profileId, { allowStale: true }) ??
    (profileId == null && getActiveBackendCapabilitiesProfile() != null
      ? getCachedBackendCapabilitiesEntry(getActiveBackendCapabilitiesProfile(), {
          allowStale: true,
        })
      : null);
  return cached?.data ?? null;
}

export async function forceRefreshBackendCapabilities(
  profileId?: UUID | null,
): Promise<BackendCapabilitiesResponse> {
  const resolvedProfileId = getBackendCapabilitiesFetchProfileId(profileId);
  const inflight = getBackendCapabilitiesRequest(resolvedProfileId);
  if (inflight != null) {
    return inflight;
  }

  const request = fetchBackendCapabilitiesUncached(resolvedProfileId)
    .then((data) => {
      storeBackendCapabilitiesCache(resolvedProfileId, data);
      return data;
    })
    .finally(() => {
      deleteBackendCapabilitiesRequest(resolvedProfileId);
    });
  setBackendCapabilitiesRequest(resolvedProfileId, request);
  return request;
}

export async function refreshBackendCapabilitiesWithWarmupRetry(
  profileId?: UUID | null,
): Promise<BackendCapabilitiesResponse> {
  const data = await forceRefreshBackendCapabilities(profileId);
  if (shouldRetryIbmCapabilityWarmup(data)) {
    queueBackgroundBackendCapabilitiesRefresh(profileId);
  }
  return data;
}

let autoRefreshInterval: ReturnType<typeof setInterval> | null = null;
const BACKEND_CAPABILITIES_AUTO_REFRESH_INTERVAL_MS = 1000 * 60;

export function startBackendCapabilitiesAutoRefresh(): void {
  if (autoRefreshInterval != null) return;
  autoRefreshInterval = setInterval(() => {
    for (const key of getBackendCapabilitiesRefreshKeys()) {
      if (hasBackendCapabilitiesRequest(key)) {
        continue;
      }
      const profileId = key === ACTIVE_BACKEND_CAPABILITIES_CACHE_KEY ? null : key;
      const activeProfileId = getActiveBackendCapabilitiesProfile();
      const isActiveProfile = profileId === activeProfileId;
      if (isActiveProfile) {
        notifyIbmCredentialProfilesChanged({
          activeProfileId,
          backendCapabilitiesRefresh: "started",
        });
      }
      void forceRefreshBackendCapabilities(profileId)
        .then(() => {
          if (isActiveProfile) {
            notifyIbmCredentialProfilesChanged({
              activeProfileId,
              backendCapabilitiesRefresh: "completed",
            });
          }
        })
        .catch(() => {
          if (isActiveProfile) {
            notifyIbmCredentialProfilesChanged({
              activeProfileId,
              backendCapabilitiesRefresh: "failed",
            });
          }
        });
    }
  }, BACKEND_CAPABILITIES_AUTO_REFRESH_INTERVAL_MS);
}

export function warmBackendCapabilitiesCache(profileId?: UUID | null): void {
  void fetchBackendCapabilities(profileId).catch(() => undefined);
}

export async function previewTranspilation(
  data: TranspilationPreviewRequest,
): Promise<TranspilationPreviewResponse> {
  const payload: ApiTranspilePreviewRequest = {
    target: data.backend_target,
    algorithm: data.algorithm,
    num_qubits: data.num_qubits,
    backend_options: toApiBackendOptions(data.backend_options),
  };
  const response = parseTranspilePreviewResponse(
    await request<unknown>(operatorProtectedApiUrl("/api/backends/transpile-preview"), {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  );

  const metadata = response.metadata ?? {};
  const pendingJobs =
    typeof metadata.pending_jobs === "number" ? Math.max(0, metadata.pending_jobs) : null;
  return {
    available: response.feasible,
    backend_name: response.backend_name,
    num_qubits: response.requested_qubits,
    circuit_depth: typeof metadata.input_depth === "number" ? metadata.input_depth : null,
    transpiled_depth:
      typeof metadata.estimated_depth === "number" ? metadata.estimated_depth : null,
    estimated_queue_seconds: pendingJobs === null ? null : pendingJobs * 60,
    warnings: response.warnings ?? [],
  };
}

export function resetBackendCapabilitiesStateForTests(): void {
  if (autoRefreshInterval != null) {
    clearInterval(autoRefreshInterval);
    autoRefreshInterval = null;
  }
  resetBackendCapabilitiesState();
}
