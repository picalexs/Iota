/** In-memory and localStorage state shared by backend/profile API modules. */

import type { BackendCapabilitiesResponse, UUID } from "@/types/run";

export const ACTIVE_BACKEND_CAPABILITIES_CACHE_KEY = "__active__";
const BACKEND_CAPABILITIES_CACHE_MS = 1000 * 60 * 10;
const BACKEND_CAPABILITIES_BACKGROUND_RETRY_MS = 1500;
const BACKEND_CAPABILITIES_STORAGE_KEY = "qss-backend-capabilities-cache-v1";

export type BackendCapabilitiesCacheKey = UUID | typeof ACTIVE_BACKEND_CAPABILITIES_CACHE_KEY;

type BackendCapabilitiesCacheEntry = {
  data: BackendCapabilitiesResponse;
  expiresAt: number;
};

type SerializedBackendCapabilitiesCache = {
  activeProfileId: UUID | null;
  entries: Array<{
    key: string;
    data: BackendCapabilitiesResponse;
    expiresAt: number;
  }>;
  knownProfileIds: UUID[];
};

const backendCapabilitiesCache = new Map<
  BackendCapabilitiesCacheKey,
  BackendCapabilitiesCacheEntry
>();
const backendCapabilitiesRequests = new Map<
  BackendCapabilitiesCacheKey,
  Promise<BackendCapabilitiesResponse>
>();
const backendCapabilitiesBackgroundRefreshTimers = new Map<
  BackendCapabilitiesCacheKey,
  ReturnType<typeof setTimeout>
>();
const knownBackendCapabilityProfileIds = new Set<UUID>();

let activeBackendCapabilitiesProfileId: UUID | null = null;

function hasLocalStorage(): boolean {
  return typeof globalThis.localStorage !== "undefined";
}

export function getBackendCapabilitiesCacheKey(
  profileId?: UUID | null,
): BackendCapabilitiesCacheKey {
  return profileId ?? ACTIVE_BACKEND_CAPABILITIES_CACHE_KEY;
}

export function getBackendCapabilitiesFetchProfileId(profileId?: UUID | null): UUID | null {
  return profileId ?? activeBackendCapabilitiesProfileId;
}

export function getActiveBackendCapabilitiesProfile(): UUID | null {
  return activeBackendCapabilitiesProfileId;
}

export function persistBackendCapabilitiesCache(): void {
  if (!hasLocalStorage()) {
    return;
  }

  const payload: SerializedBackendCapabilitiesCache = {
    activeProfileId: activeBackendCapabilitiesProfileId,
    entries: Array.from(backendCapabilitiesCache.entries()).map(([key, entry]) => ({
      key,
      data: entry.data,
      expiresAt: entry.expiresAt,
    })),
    knownProfileIds: Array.from(knownBackendCapabilityProfileIds),
  };

  try {
    globalThis.localStorage.setItem(BACKEND_CAPABILITIES_STORAGE_KEY, JSON.stringify(payload));
  } catch {
    // Ignore storage failures and keep the in-memory cache as the source of truth.
  }
}

function loadBackendCapabilitiesCacheFromStorage(): void {
  if (!hasLocalStorage()) {
    return;
  }

  try {
    const raw = globalThis.localStorage.getItem(BACKEND_CAPABILITIES_STORAGE_KEY);
    if (!raw) {
      return;
    }

    const parsed = JSON.parse(raw) as SerializedBackendCapabilitiesCache;
    activeBackendCapabilitiesProfileId =
      typeof parsed.activeProfileId === "string" ? parsed.activeProfileId : null;

    for (const profileId of parsed.knownProfileIds ?? []) {
      if (typeof profileId === "string") {
        knownBackendCapabilityProfileIds.add(profileId);
      }
    }

    for (const entry of parsed.entries ?? []) {
      if (
        typeof entry?.key !== "string" ||
        typeof entry?.expiresAt !== "number" ||
        entry.data == null
      ) {
        continue;
      }
      const key =
        entry.key === ACTIVE_BACKEND_CAPABILITIES_CACHE_KEY
          ? ACTIVE_BACKEND_CAPABILITIES_CACHE_KEY
          : (entry.key as UUID);
      backendCapabilitiesCache.set(key, {
        data: entry.data,
        expiresAt: entry.expiresAt,
      });
    }
  } catch {
    // Ignore malformed persisted state; the next background refresh repopulates it.
  }
}

export function setActiveBackendCapabilitiesProfile(profileId: UUID | null): void {
  activeBackendCapabilitiesProfileId = profileId;
  if (profileId == null) {
    persistBackendCapabilitiesCache();
    return;
  }

  const explicitEntry = backendCapabilitiesCache.get(profileId);
  if (explicitEntry != null) {
    backendCapabilitiesCache.set(ACTIVE_BACKEND_CAPABILITIES_CACHE_KEY, {
      data: explicitEntry.data,
      expiresAt: explicitEntry.expiresAt,
    });
  }
  persistBackendCapabilitiesCache();
}

export function rememberBackendCapabilityProfile(profileId: UUID): void {
  knownBackendCapabilityProfileIds.add(profileId);
}

export function getKnownBackendCapabilityProfiles(): UUID[] {
  return Array.from(knownBackendCapabilityProfileIds);
}

export function storeBackendCapabilitiesCache(
  profileId: UUID | null,
  data: BackendCapabilitiesResponse,
): void {
  const entry = {
    data,
    expiresAt: Date.now() + BACKEND_CAPABILITIES_CACHE_MS,
  };
  const key = getBackendCapabilitiesCacheKey(profileId);
  backendCapabilitiesCache.set(key, entry);

  if (profileId != null) {
    knownBackendCapabilityProfileIds.add(profileId);
    if (activeBackendCapabilitiesProfileId === profileId) {
      backendCapabilitiesCache.set(ACTIVE_BACKEND_CAPABILITIES_CACHE_KEY, entry);
    }
    persistBackendCapabilitiesCache();
    return;
  }

  if (activeBackendCapabilitiesProfileId != null) {
    backendCapabilitiesCache.set(activeBackendCapabilitiesProfileId, entry);
  }

  persistBackendCapabilitiesCache();
}

export function getCachedBackendCapabilitiesEntry(
  profileId?: UUID | null,
  { allowStale = false }: { allowStale?: boolean } = {},
): BackendCapabilitiesCacheEntry | null {
  const cached = backendCapabilitiesCache.get(getBackendCapabilitiesCacheKey(profileId));
  if (cached != null && (allowStale || cached.expiresAt > Date.now())) {
    return cached;
  }
  return null;
}

export function getBackendCapabilitiesRequest(
  profileId?: UUID | null,
): Promise<BackendCapabilitiesResponse> | null {
  return backendCapabilitiesRequests.get(getBackendCapabilitiesCacheKey(profileId)) ?? null;
}

export function setBackendCapabilitiesRequest(
  profileId: UUID | null,
  request: Promise<BackendCapabilitiesResponse>,
): void {
  backendCapabilitiesRequests.set(getBackendCapabilitiesCacheKey(profileId), request);
}

export function deleteBackendCapabilitiesRequest(profileId?: UUID | null): void {
  backendCapabilitiesRequests.delete(getBackendCapabilitiesCacheKey(profileId));
}

export function hasBackendCapabilitiesRequest(key: BackendCapabilitiesCacheKey): boolean {
  return backendCapabilitiesRequests.has(key);
}

export function getBackendCapabilitiesRefreshKeys(): Set<BackendCapabilitiesCacheKey> {
  return activeBackendCapabilitiesProfileId == null
    ? new Set<BackendCapabilitiesCacheKey>([
        ACTIVE_BACKEND_CAPABILITIES_CACHE_KEY,
        ...knownBackendCapabilityProfileIds,
      ])
    : new Set<BackendCapabilitiesCacheKey>(knownBackendCapabilityProfileIds);
}

export function getBackgroundRefreshTimer(
  profileId?: UUID | null,
): ReturnType<typeof setTimeout> | undefined {
  return backendCapabilitiesBackgroundRefreshTimers.get(getBackendCapabilitiesCacheKey(profileId));
}

export function setBackgroundRefreshTimer(
  profileId: UUID | null | undefined,
  timer: ReturnType<typeof setTimeout>,
): void {
  backendCapabilitiesBackgroundRefreshTimers.set(getBackendCapabilitiesCacheKey(profileId), timer);
}

export function clearBackgroundRefreshTimer(profileId?: UUID | null): void {
  const key = getBackendCapabilitiesCacheKey(profileId);
  const timer = backendCapabilitiesBackgroundRefreshTimers.get(key);
  if (timer != null) {
    clearTimeout(timer);
    backendCapabilitiesBackgroundRefreshTimers.delete(key);
  }
}

export function removeBackendCapabilityProfile(profileId: UUID): void {
  knownBackendCapabilityProfileIds.delete(profileId);
  backendCapabilitiesCache.delete(getBackendCapabilitiesCacheKey(profileId));
  backendCapabilitiesRequests.delete(getBackendCapabilitiesCacheKey(profileId));
  if (activeBackendCapabilitiesProfileId === profileId) {
    activeBackendCapabilitiesProfileId = null;
    backendCapabilitiesCache.delete(ACTIVE_BACKEND_CAPABILITIES_CACHE_KEY);
    backendCapabilitiesRequests.delete(ACTIVE_BACKEND_CAPABILITIES_CACHE_KEY);
  }
  persistBackendCapabilitiesCache();
}

export function resetBackendCapabilitiesState(): void {
  for (const timer of backendCapabilitiesBackgroundRefreshTimers.values()) {
    clearTimeout(timer);
  }
  backendCapabilitiesBackgroundRefreshTimers.clear();
  backendCapabilitiesCache.clear();
  backendCapabilitiesRequests.clear();
  knownBackendCapabilityProfileIds.clear();
  activeBackendCapabilitiesProfileId = null;
  if (hasLocalStorage()) {
    globalThis.localStorage.removeItem(BACKEND_CAPABILITIES_STORAGE_KEY);
  }
}

export const BACKEND_CAPABILITIES_BACKGROUND_RETRY_DELAY_MS =
  BACKEND_CAPABILITIES_BACKGROUND_RETRY_MS;

loadBackendCapabilitiesCacheFromStorage();
