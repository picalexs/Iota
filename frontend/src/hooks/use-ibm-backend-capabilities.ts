import { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchBackendCapabilities,
  forceRefreshBackendCapabilities,
  getBackendCapabilitiesCached,
} from "@/api/backends";
import { logAppWarning } from "@/lib/app-logger";
import { getErrorMessage } from "@/lib/error-handler";
import {
  subscribeToIbmCredentialProfilesChanged,
  type IbmBackendWarmupProgress,
} from "@/lib/ibm-profile-events";
import type { BackendCapabilitiesResponse } from "@/types/run";

export const IBM_BACKEND_CAPABILITIES_ERROR = "IBM backend data is unavailable right now.";

function readCachedCapabilities(profileId?: string | null): BackendCapabilitiesResponse | null {
  return getBackendCapabilitiesCached(profileId ?? undefined);
}

/** Keep IBM backend availability consistent across Run and Benchmark flows. */
export function useIbmBackendCapabilities() {
  const mountedRef = useRef(true);
  const [activeProfileId, setActiveProfileId] = useState<string | null>(null);
  const [backendCapabilities, setBackendCapabilities] =
    useState<BackendCapabilitiesResponse | null>(() => readCachedCapabilities());
  const [capabilitiesLoading, setCapabilitiesLoading] = useState(
    () => readCachedCapabilities() == null,
  );
  const [capabilitiesRefreshing, setCapabilitiesRefreshing] = useState(false);
  const [capabilitiesError, setCapabilitiesError] = useState<string | null>(null);
  const [backendWarmupProgress, setBackendWarmupProgress] =
    useState<IbmBackendWarmupProgress | null>(null);

  useEffect(() => {
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const syncFromCache = useCallback((profileId?: string | null) => {
    const cached = readCachedCapabilities(profileId);
    if (cached == null) return false;
    setBackendCapabilities(cached);
    setCapabilitiesError(null);
    return true;
  }, []);

  useEffect(() => {
    if (syncFromCache()) {
      setCapabilitiesLoading(false);
      return;
    }

    let cancelled = false;
    setCapabilitiesLoading(true);
    setBackendWarmupProgress({ loadedProfiles: 0, totalProfiles: 1 });

    void fetchBackendCapabilities(activeProfileId ?? undefined)
      .then((data) => {
        if (cancelled || !mountedRef.current) return;
        setBackendCapabilities(data);
        setCapabilitiesError(null);
        setBackendWarmupProgress({ loadedProfiles: 1, totalProfiles: 1 });
      })
      .catch((error) => {
        if (cancelled || !mountedRef.current) return;
        logAppWarning("ibm-backend-capabilities", "Failed to load IBM backend data.", {
          error: getErrorMessage(error),
        });
        setCapabilitiesError(IBM_BACKEND_CAPABILITIES_ERROR);
        setBackendWarmupProgress({ loadedProfiles: 0, totalProfiles: 1 });
      })
      .finally(() => {
        if (!cancelled && mountedRef.current) {
          setCapabilitiesLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [activeProfileId, syncFromCache]);

  const refreshCapabilities = useCallback(async () => {
    setCapabilitiesRefreshing(true);
    setCapabilitiesLoading((current) => current || backendCapabilities == null);
    setBackendWarmupProgress({ loadedProfiles: 0, totalProfiles: 1 });
    try {
      const data = await forceRefreshBackendCapabilities(activeProfileId ?? undefined);
      if (!mountedRef.current) return;
      setBackendCapabilities(data);
      setCapabilitiesError(null);
      setBackendWarmupProgress({ loadedProfiles: 1, totalProfiles: 1 });
    } catch (error) {
      if (!mountedRef.current) return;
      logAppWarning("ibm-backend-capabilities", "Failed to refresh IBM backend data.", {
        error: getErrorMessage(error),
      });
      setCapabilitiesError(IBM_BACKEND_CAPABILITIES_ERROR);
      setBackendWarmupProgress({ loadedProfiles: 0, totalProfiles: 1 });
    } finally {
      if (mountedRef.current) {
        setCapabilitiesLoading(false);
        setCapabilitiesRefreshing(false);
      }
    }
  }, [activeProfileId, backendCapabilities]);

  const ensureBackendCapabilitiesLoaded = useCallback(() => {
    const cached = readCachedCapabilities();
    if (cached != null) {
      setBackendCapabilities(cached);
      setCapabilitiesError(null);
    }
    if (capabilitiesLoading || capabilitiesRefreshing) return;
    void refreshCapabilities();
  }, [capabilitiesLoading, capabilitiesRefreshing, refreshCapabilities]);

  useEffect(() => {
    return subscribeToIbmCredentialProfilesChanged((detail) => {
      if (detail.activeProfileId !== undefined) {
        setActiveProfileId(detail.activeProfileId ?? null);
      }

      const synced = syncFromCache(detail.activeProfileId ?? undefined);
      if (
        detail.backendCapabilitiesRefresh === "started" ||
        detail.backendCapabilitiesRefresh === "progress"
      ) {
        setCapabilitiesLoading(!synced);
        setCapabilitiesRefreshing(true);
        setCapabilitiesError(null);
        setBackendWarmupProgress(detail.backendWarmupProgress ?? null);
        return;
      }

      if (!synced && detail.backendCapabilitiesRefresh === "failed") {
        setCapabilitiesError(IBM_BACKEND_CAPABILITIES_ERROR);
      } else if (synced) {
        setCapabilitiesError(null);
      }
      setCapabilitiesLoading(false);
      setCapabilitiesRefreshing(false);
      setBackendWarmupProgress(detail.backendWarmupProgress ?? null);
    });
  }, [syncFromCache]);

  return {
    backendCapabilities,
    capabilitiesLoading,
    capabilitiesRefreshing,
    capabilitiesError,
    backendWarmupProgress,
    refreshCapabilities,
    ensureBackendCapabilitiesLoaded,
  };
}
