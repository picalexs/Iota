import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type Dispatch,
  type RefObject,
  type SetStateAction,
} from "react";
import {
  fetchBackendCapabilities,
  forceRefreshBackendCapabilities,
  getBackendCapabilitiesCached,
} from "@/api/backends";
import { warmAllBackendCapabilitiesCache } from "@/api/profiles";
import { logAppWarning } from "@/lib/app-logger";
import { getErrorMessage } from "@/lib/error-handler";
import type { BackendCapabilitiesResponse, BackendCapability } from "@/types/run";
import {
  getBenchmarkBackendOptions,
  getBenchmarkIbmBackends,
  requiresIbmBackendSelection,
  resolveBenchmarkBackendNameForMode,
  type BenchmarkBackendMode,
} from "@/pages/benchmark/benchmark-utils";

function useMountedRef() {
  const mountedRef = useRef(true);

  useEffect(() => {
    return () => {
      mountedRef.current = false;
    };
  }, []);

  return mountedRef;
}

function applyCachedBackendCapabilitiesState(
  cached: BackendCapabilitiesResponse | null,
  setBackendCapabilities: Dispatch<SetStateAction<BackendCapabilitiesResponse | null>>,
  setCapabilitiesError: Dispatch<SetStateAction<string | null>>,
  setCapabilitiesLoading: Dispatch<SetStateAction<boolean>>,
): boolean {
  if (cached === null) return false;
  setBackendCapabilities(cached);
  setCapabilitiesError(null);
  setCapabilitiesLoading(false);
  return true;
}

function refreshBackendCapabilities({
  mountedRef,
  setBackendCapabilities,
  setCapabilitiesError,
  setCapabilitiesLoading,
  force = false,
}: {
  mountedRef: RefObject<boolean>;
  setBackendCapabilities: Dispatch<SetStateAction<BackendCapabilitiesResponse | null>>;
  setCapabilitiesError: Dispatch<SetStateAction<string | null>>;
  setCapabilitiesLoading: Dispatch<SetStateAction<boolean>>;
  force?: boolean;
}) {
  const request = warmAllBackendCapabilitiesCache()
    .catch(() => null)
    .then(() => {
      const warmed = getBackendCapabilitiesCached();
      if (!force && warmed !== null) {
        return warmed;
      }
      return force ? forceRefreshBackendCapabilities() : fetchBackendCapabilities();
    });
  return request
    .then((data) => {
      if (!mountedRef.current) return;
      setBackendCapabilities(data);
      setCapabilitiesError(null);
    })
    .catch((error) => {
      if (!mountedRef.current) return;
      logAppWarning("benchmark.backend-capabilities", "Failed to load IBM backend data.", {
        error: getErrorMessage(error),
      });
      setCapabilitiesError("IBM backend data is unavailable right now.");
    })
    .finally(() => {
      if (mountedRef.current) {
        setCapabilitiesLoading(false);
      }
    });
}

function getBackendCapabilityHelperText({
  capabilitiesError,
  capabilitiesLoading,
  backendSelectionRequired,
  selectedBackendOption,
}: {
  capabilitiesError: string | null;
  capabilitiesLoading: boolean;
  backendSelectionRequired: boolean;
  selectedBackendOption: { warning?: string | null } | undefined;
}) {
  if (capabilitiesError) return capabilitiesError;
  if (capabilitiesLoading && backendSelectionRequired) {
    return "Loading IBM backend availability...";
  }
  return selectedBackendOption?.warning;
}

export function useBackendCapabilityState({
  selectedBackendMode,
  selectedBackendName,
  setSelectedBackendName,
}: {
  selectedBackendMode: BenchmarkBackendMode;
  selectedBackendName: string | null;
  setSelectedBackendName: Dispatch<SetStateAction<string | null>>;
}) {
  const mountedRef = useMountedRef();
  const [backendCapabilities, setBackendCapabilities] =
    useState<BackendCapabilitiesResponse | null>(() => getBackendCapabilitiesCached());
  const [capabilitiesLoading, setCapabilitiesLoading] = useState(false);
  const [capabilitiesError, setCapabilitiesError] = useState<string | null>(null);

  const primeBackendCapabilities = useCallback(() => {
    if (
      applyCachedBackendCapabilitiesState(
        getBackendCapabilitiesCached(),
        setBackendCapabilities,
        setCapabilitiesError,
        setCapabilitiesLoading,
      ) ||
      capabilitiesLoading
    ) {
      return;
    }

    setCapabilitiesLoading(true);
    void refreshBackendCapabilities({
      mountedRef,
      setBackendCapabilities,
      setCapabilitiesError,
      setCapabilitiesLoading,
    });
  }, [capabilitiesLoading, mountedRef]);

  const ensureBackendCapabilitiesLoaded = useCallback(() => {
    const cached = getBackendCapabilitiesCached();
    applyCachedBackendCapabilitiesState(
      cached,
      setBackendCapabilities,
      setCapabilitiesError,
      setCapabilitiesLoading,
    );
    if (capabilitiesLoading) {
      return;
    }

    setCapabilitiesLoading(true);
    void refreshBackendCapabilities({
      mountedRef,
      setBackendCapabilities,
      setCapabilitiesError,
      setCapabilitiesLoading,
      force: true,
    });
  }, [capabilitiesLoading, mountedRef]);

  const ibmCapability = useMemo<BackendCapability | null>(
    () =>
      backendCapabilities?.backends.find((capability) => capability.target === "ibm_runtime") ??
      null,
    [backendCapabilities],
  );
  const ibmCapabilityPending = capabilitiesLoading && ibmCapability === null;
  const backendOptions = useMemo(
    () => getBenchmarkBackendOptions(ibmCapability, { pending: ibmCapabilityPending }),
    [ibmCapability, ibmCapabilityPending],
  );
  const ibmBackends = useMemo(() => getBenchmarkIbmBackends(ibmCapability), [ibmCapability]);
  const resolvedBackendName = useMemo(
    () =>
      resolveBenchmarkBackendNameForMode(
        selectedBackendMode,
        selectedBackendName,
        ibmCapability,
      ),
    [ibmCapability, selectedBackendMode, selectedBackendName],
  );
  const selectedBackendOption = useMemo(
    () =>
      backendOptions.find((option) => option.value === selectedBackendMode) ?? backendOptions[0],
    [backendOptions, selectedBackendMode],
  );
  const backendSelectionRequired = requiresIbmBackendSelection(selectedBackendMode);
  const backendReady =
    selectedBackendOption?.enabled === true &&
    (!backendSelectionRequired || resolvedBackendName !== null);
  const backendHelperText = getBackendCapabilityHelperText({
    capabilitiesError,
    capabilitiesLoading,
    backendSelectionRequired,
    selectedBackendOption,
  });

  useEffect(() => {
    primeBackendCapabilities();
  }, [primeBackendCapabilities]);

  useEffect(() => {
    if (!backendSelectionRequired) return;
    primeBackendCapabilities();
  }, [backendSelectionRequired, primeBackendCapabilities]);

  useEffect(() => {
    if (resolvedBackendName === selectedBackendName) return;
    setSelectedBackendName(resolvedBackendName);
  }, [resolvedBackendName, selectedBackendName, setSelectedBackendName]);

  return {
    ensureBackendCapabilitiesLoaded,
    backendOptions,
    ibmBackends,
    backendSelectionRequired,
    backendReady,
    backendHelperText,
    resolvedBackendName,
  };
}
