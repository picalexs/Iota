/** IBM credential-profile API calls and capability warm-up coordination. */

import type { IbmBackendWarmupProgress } from "@/lib/ibm-profile-events";
import type {
  IbmCredentialProfile,
  IbmCredentialProfileCreate,
  IbmCredentialProfileListResponse,
  IbmCredentialProfileTestResponse,
  IbmCredentialProfileUpdate,
} from "@/types/profile";
import type {
  ApiIbmCredentialProfileCreate,
  ApiIbmCredentialProfileListResponse,
  ApiIbmCredentialProfileResponse,
  ApiIbmCredentialProfileTestResponse,
  ApiIbmCredentialProfileUpdate,
} from "@/types/api";
import type { UUID } from "@/types/run";
import {
  fetchWithApiError,
  handleApiError,
  invalidApiResponse,
  isRecord,
  isOptionalNullableString,
  operatorProtectedApiUrl,
  request,
} from "./http";
import {
  getKnownBackendCapabilityProfiles,
  persistBackendCapabilitiesCache,
  rememberBackendCapabilityProfile,
  removeBackendCapabilityProfile,
  setActiveBackendCapabilitiesProfile,
} from "./backend-capabilities-cache";
import { refreshBackendCapabilitiesWithWarmupRetry } from "./backends";

export interface WarmBackendCapabilitiesOptions {
  onProgress?: (progress: IbmBackendWarmupProgress) => void;
}

type WarmupProgressState = {
  loadedProfiles: number;
  totalProfiles: number;
};

function trackedProfileIds(activeProfileId: UUID | null): UUID[] {
  const knownProfileIds = new Set(getKnownBackendCapabilityProfiles());
  const tracked = Array.from(knownProfileIds);
  if (activeProfileId != null && !knownProfileIds.has(activeProfileId)) {
    tracked.unshift(activeProfileId);
  }
  return tracked;
}

async function warmProfileWithProgress(
  profileId: UUID,
  state: WarmupProgressState,
  onProgress?: (progress: IbmBackendWarmupProgress) => void,
): Promise<void> {
  try {
    await refreshBackendCapabilitiesWithWarmupRetry(profileId);
  } finally {
    state.loadedProfiles += 1;
    onProgress?.(state);
  }
}

function startBackgroundProfileWarmups(
  profileIds: Iterable<UUID>,
  activeProfileId: UUID | null,
  state: WarmupProgressState,
  onProgress?: (progress: IbmBackendWarmupProgress) => void,
): void {
  for (const profileId of profileIds) {
    if (profileId === activeProfileId) continue;
    void warmProfileWithProgress(profileId, state, onProgress).catch(() => undefined);
  }
}

function isIbmCredentialProfile(value: unknown): value is ApiIbmCredentialProfileResponse {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.name === "string" &&
    typeof value.channel === "string" &&
    typeof value.active === "boolean" &&
    typeof value.created_at === "string" &&
    typeof value.updated_at === "string"
  );
}

export function parseIbmCredentialProfileResponse(value: unknown): ApiIbmCredentialProfileResponse {
  if (!isIbmCredentialProfile(value)) {
    throw invalidApiResponse("Invalid IBM credential profile response");
  }
  return value;
}

export function parseIbmCredentialProfileListResponse(
  value: unknown,
): ApiIbmCredentialProfileListResponse {
  if (
    !isRecord(value) ||
    !Array.isArray(value.profiles) ||
    !value.profiles.every(isIbmCredentialProfile) ||
    !isOptionalNullableString(value, "active_profile_id") ||
    typeof value.encryption_key_source !== "string" ||
    !isOptionalNullableString(value, "encryption_warning")
  ) {
    throw invalidApiResponse("Invalid IBM credential profile list response");
  }
  return value as ApiIbmCredentialProfileListResponse;
}

export function parseIbmCredentialProfileTestResponse(
  value: unknown,
): ApiIbmCredentialProfileTestResponse {
  if (
    !isRecord(value) ||
    typeof value.id !== "string" ||
    typeof value.ok !== "boolean" ||
    typeof value.message !== "string" ||
    !isOptionalNullableString(value, "active_instance")
  ) {
    throw invalidApiResponse("Invalid IBM credential profile test response");
  }
  return value as ApiIbmCredentialProfileTestResponse;
}

function toIbmCredentialProfile(data: ApiIbmCredentialProfileResponse): IbmCredentialProfile {
  return {
    ...data,
    id: data.id as UUID,
  };
}

function toIbmCredentialProfileList(
  data: ApiIbmCredentialProfileListResponse,
): IbmCredentialProfileListResponse {
  return {
    ...data,
    active_profile_id: (data.active_profile_id ?? null) as UUID | null,
    encryption_warning: data.encryption_warning ?? null,
    profiles: data.profiles.map(toIbmCredentialProfile),
  };
}

export async function listIbmCredentialProfiles(): Promise<IbmCredentialProfileListResponse> {
  const response = toIbmCredentialProfileList(
    parseIbmCredentialProfileListResponse(
      await request<unknown>(operatorProtectedApiUrl("/api/settings/ibm-profiles"), {
        method: "GET",
      }),
    ),
  );
  setActiveBackendCapabilitiesProfile(
    response.active_profile_id ?? response.profiles.find((profile) => profile.active)?.id ?? null,
  );
  for (const profile of response.profiles) {
    rememberBackendCapabilityProfile(profile.id);
  }
  persistBackendCapabilitiesCache();
  return response;
}

export async function createIbmCredentialProfile(
  data: IbmCredentialProfileCreate,
): Promise<IbmCredentialProfile> {
  const payload: ApiIbmCredentialProfileCreate = {
    ...data,
    activate: data.activate ?? true,
    channel: data.channel ?? "ibm_quantum_platform",
  };
  const response = toIbmCredentialProfile(
    parseIbmCredentialProfileResponse(
      await request<unknown>(operatorProtectedApiUrl("/api/settings/ibm-profiles"), {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    ),
  );
  rememberBackendCapabilityProfile(response.id);
  if (response.active) {
    setActiveBackendCapabilitiesProfile(response.id);
  } else {
    persistBackendCapabilitiesCache();
  }
  return response;
}

export async function updateIbmCredentialProfile(
  id: UUID,
  data: IbmCredentialProfileUpdate,
): Promise<IbmCredentialProfile> {
  const payload: ApiIbmCredentialProfileUpdate = { ...data };
  const response = toIbmCredentialProfile(
    parseIbmCredentialProfileResponse(
      await request<unknown>(operatorProtectedApiUrl(`/api/settings/ibm-profiles/${id}`), {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    ),
  );
  rememberBackendCapabilityProfile(response.id);
  if (response.active) {
    setActiveBackendCapabilitiesProfile(response.id);
  } else {
    persistBackendCapabilitiesCache();
  }
  return response;
}

export async function activateIbmCredentialProfile(id: UUID): Promise<IbmCredentialProfile> {
  const response = toIbmCredentialProfile(
    parseIbmCredentialProfileResponse(
      await request<unknown>(operatorProtectedApiUrl(`/api/settings/ibm-profiles/${id}/activate`), {
        method: "POST",
      }),
    ),
  );
  rememberBackendCapabilityProfile(id);
  setActiveBackendCapabilitiesProfile(id);
  return response;
}

export async function testIbmCredentialProfile(
  id: UUID,
): Promise<IbmCredentialProfileTestResponse> {
  const response = parseIbmCredentialProfileTestResponse(
    await request<unknown>(operatorProtectedApiUrl(`/api/settings/ibm-profiles/${id}/test`), {
      method: "POST",
    }),
  );
  return {
    ...response,
    id: response.id as UUID,
    active_instance: response.active_instance ?? null,
  };
}

export async function deleteIbmCredentialProfile(id: UUID, confirmName: string): Promise<void> {
  const query = new URLSearchParams({ confirm_name: confirmName });
  const url = operatorProtectedApiUrl(`/api/settings/ibm-profiles/${id}?${query.toString()}`);
  const response = await fetchWithApiError(url, {
    method: "DELETE",
    headers: new Headers(),
  });

  if (!response.ok) {
    await handleApiError(response, { method: "DELETE", url });
  }

  removeBackendCapabilityProfile(id);
}

let backendCapabilitiesWarmupRequest: Promise<{ activeProfileId: UUID | null }> | null = null;

export async function warmAllBackendCapabilitiesCache(
  options: WarmBackendCapabilitiesOptions = {},
): Promise<{ activeProfileId: UUID | null }> {
  if (backendCapabilitiesWarmupRequest != null) {
    return backendCapabilitiesWarmupRequest;
  }

  backendCapabilitiesWarmupRequest = (async () => {
    const profilesResponse = await listIbmCredentialProfiles().catch(() => null);
    const activeProfileId =
      profilesResponse?.active_profile_id ??
      profilesResponse?.profiles.find((profile) => profile.active)?.id ??
      null;

    if (activeProfileId != null) {
      setActiveBackendCapabilitiesProfile(activeProfileId);
    }

    const profileIdsToWarm = trackedProfileIds(activeProfileId);
    const state: WarmupProgressState = {
      loadedProfiles: 0,
      totalProfiles: profileIdsToWarm.length,
    };
    if (state.totalProfiles > 0) options.onProgress?.(state);

    const activeFetch =
      activeProfileId == null
        ? refreshBackendCapabilitiesWithWarmupRetry().catch(() => null)
        : warmProfileWithProgress(activeProfileId, state, options.onProgress).catch(() => null);

    startBackgroundProfileWarmups(
      profileIdsToWarm,
      activeProfileId,
      state,
      options.onProgress,
    );

    await activeFetch;
    return { activeProfileId };
  })().finally(() => {
    backendCapabilitiesWarmupRequest = null;
  });

  return backendCapabilitiesWarmupRequest;
}

export function resetProfileWarmupStateForTests(): void {
  backendCapabilitiesWarmupRequest = null;
}
