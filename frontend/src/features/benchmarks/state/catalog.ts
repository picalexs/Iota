import { useEffect, useMemo, type Dispatch, type SetStateAction } from "react";
import { useIbmBackendCapabilities } from "@/hooks/use-ibm-backend-capabilities";
import type { BackendCapability } from "@/types/run";
import {
  getBenchmarkBackendOptions,
  getBenchmarkIbmBackends,
  requiresIbmBackendSelection,
  resolveBenchmarkBackendNameForMode,
  type BenchmarkBackendMode,
} from "@/pages/benchmark/benchmark-utils";

function getBackendCapabilityHelperText({
  capabilitiesError,
  capabilitiesLoading,
  capabilitiesRefreshing,
  backendSelectionRequired,
  selectedBackendOption,
}: {
  capabilitiesError: string | null;
  capabilitiesLoading: boolean;
  capabilitiesRefreshing: boolean;
  backendSelectionRequired: boolean;
  selectedBackendOption: { warning?: string | null } | undefined;
}) {
  if (capabilitiesError) return capabilitiesError;
  if (capabilitiesLoading && backendSelectionRequired) {
    return "Loading IBM backend availability...";
  }
  if (capabilitiesRefreshing && backendSelectionRequired) {
    return "Refreshing IBM backend availability...";
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
  const {
    backendCapabilities,
    capabilitiesLoading,
    capabilitiesRefreshing,
    capabilitiesError,
    ensureBackendCapabilitiesLoaded,
  } = useIbmBackendCapabilities();

  const ibmCapability = useMemo<BackendCapability | null>(
    () =>
      backendCapabilities?.backends.find((capability) => capability.target === "ibm_runtime") ??
      null,
    [backendCapabilities],
  );
  const ibmCapabilityPending =
    (capabilitiesLoading || capabilitiesRefreshing) && ibmCapability === null;
  const backendOptions = useMemo(
    () => getBenchmarkBackendOptions(ibmCapability, { pending: ibmCapabilityPending }),
    [ibmCapability, ibmCapabilityPending],
  );
  const ibmBackends = useMemo(() => getBenchmarkIbmBackends(ibmCapability), [ibmCapability]);
  const resolvedBackendName = useMemo(
    () =>
      resolveBenchmarkBackendNameForMode(selectedBackendMode, selectedBackendName, ibmCapability),
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
    capabilitiesRefreshing,
    backendSelectionRequired,
    selectedBackendOption,
  });

  useEffect(() => {
    if (resolvedBackendName === selectedBackendName) return;
    setSelectedBackendName(resolvedBackendName);
  }, [resolvedBackendName, selectedBackendName, setSelectedBackendName]);

  return {
    ensureBackendCapabilitiesLoaded,
    backendCapabilitiesLoading: capabilitiesLoading,
    backendCapabilitiesRefreshing: capabilitiesRefreshing,
    backendOptions,
    ibmBackends,
    backendSelectionRequired,
    backendReady,
    backendHelperText,
    resolvedBackendName,
  };
}
