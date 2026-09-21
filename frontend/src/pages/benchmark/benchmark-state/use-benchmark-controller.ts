import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { BENCHMARK_MOLECULE_PRESETS } from "@/lib/benchmark-presets";
import { getDefaultBenchmarkShots, type BenchmarkBackendMode } from "@/types/benchmark";
import { logAppError } from "@/lib/app-logger";
import { showErrorToast } from "@/lib/error-handler";
import type { MoleculeResponse, RunAlgorithm, UUID } from "@/types/run";
import {
  primeCustomMoleculeCache,
  upsertSavedBenchmarkRun,
  useBenchmarkStorage,
  type SavedBenchmarkRun,
} from "../benchmark-storage";
import {
  getBenchmarkAlgorithmBlockers,
  getBenchmarkStats,
  moleculeToPreset,
  normalizeStoredEntry,
  type BenchmarkEntry,
} from "../benchmark-utils";
import {
  buildBenchmarkWorkspaceSnapshotFromSavedRun,
  readBenchmarkWorkspaceViewCache,
  writeBenchmarkWorkspaceViewCache,
} from "@/features/benchmarks/state/normalization";
import {
  buildBenchmarkPayload as buildBenchmarkPayloadData,
  buildBenchmarkSignature as buildBenchmarkSignatureData,
} from "@/features/benchmarks/state/payloads";
import {
  buildGroupedBenchmarkEntries,
  describeBenchmarkBackendMode,
  isPausableBenchmarkEntry,
  isResumableBenchmarkEntry,
} from "@/features/benchmarks/state/selectors";
import { hydrateSavedBenchmarkState } from "@/features/benchmarks/state/hydration";
import { useBenchmarkPollingController } from "@/features/benchmarks/state/polling";
import { useBenchmarkExecutionStartActions } from "@/features/benchmarks/state/execution";
import { useBackendCapabilityState } from "@/features/benchmarks/state/catalog";
import { useBenchmarkVariantSelectionState } from "@/features/benchmarks/state/variant-selection";
import {
  type BenchmarkPendingAction,
  useBenchmarkControlActions,
} from "@/features/benchmarks/state/controls";
import {
  useSavedBenchmarkActions,
  useSavedBenchmarkCatalog,
} from "@/features/benchmarks/state/saved-catalog";
import {
  flushPendingActiveBenchmarkEntriesPersist,
  persistActiveBenchmarkEntries,
  syncSavedBenchmarkRunQueryCache,
  useActiveBenchmarkEntrySync,
  useBenchmarkDraftSync,
  useBenchmarkTimerCleanup,
  useBenchmarkWorkspaceCacheSync,
} from "@/features/benchmarks/state/persistence";
import {
  appendCustomMoleculeIfMissing,
  hasCachedSavedBenchmarkSelection,
  hasInitialPollableBenchmarkEntries,
  initialActiveSavedBenchmarkIdFor,
  toggleDistinctValue,
  useBenchmarkRouteHydration,
  useBenchmarkRouteReset,
  useDeactivateActiveBenchmark,
} from "@/features/benchmarks/state/route-lifecycle";

export { clearBenchmarkWorkspaceViewCache } from "@/features/benchmarks/state/normalization";

function reportBenchmarkActionError(scope: string, title: string, error: unknown): void {
  logAppError(scope, title, error);
  showErrorToast(error, {
    title,
    fallbackDescription: "Please try again.",
  });
}

export function useBenchmarkController(options: { benchmarkId?: string | null } = {}) {
  const benchmarkId = options.benchmarkId ?? null;
  const initialWorkspaceSnapshot = readBenchmarkWorkspaceViewCache(benchmarkId);
  const queryClient = useQueryClient();
  const {
    selectedMoleculeKeys,
    setSelectedMoleculeKeys,
    benchmarkMode,
    setBenchmarkMode,
    selectedAlgorithms,
    setSelectedAlgorithms,
    algorithmVariants,
    setAlgorithmVariants,
    entries,
    setEntries,
    restoredEntries,
    selectedBasis,
    setSelectedBasis,
    selectedBackendMode,
    setSelectedBackendMode,
    selectedBackendName,
    setSelectedBackendName,
    shots,
    setShots,
    selectedAerMethod,
    setSelectedAerMethod,
    selectedDevice,
    setSelectedDevice,
    customMolecules,
    setCustomMolecules,
    chemicalAccuracyHa,
    setChemicalAccuracyHa,
  } = useBenchmarkStorage(normalizeStoredEntry, initialWorkspaceSnapshot);

  const initialHasPollableEntries = hasInitialPollableBenchmarkEntries(
    initialWorkspaceSnapshot,
    restoredEntries,
  );
  const [running, setRunning] = useState(initialHasPollableEntries);
  const [pendingBenchmarkAction, setPendingBenchmarkAction] =
    useState<BenchmarkPendingAction>(null);
  const [savedBenchmarkRuns, setSavedBenchmarkRuns] = useState<SavedBenchmarkRun[]>([]);
  const [selectedSavedBenchmarkId, setSelectedSavedBenchmarkId] = useState<string | null>(
    benchmarkId ?? null,
  );
  const [activeSavedBenchmarkId, setActiveSavedBenchmarkId] = useState<string | null>(() =>
    initialActiveSavedBenchmarkIdFor(benchmarkId, initialHasPollableEntries),
  );
  const [hydratedBenchmarkId, setHydratedBenchmarkId] = useState<string | null>(
    initialWorkspaceSnapshot ? benchmarkId : null,
  );
  const [savedBenchmarkLoadError, setSavedBenchmarkLoadError] = useState<string | null>(null);
  const [ibmConfirmationOpen, setIbmConfirmationOpen] = useState(false);
  const benchmarkSaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const benchmarkConfigSaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const benchmarkConfigSignatureRef = useRef<string | null>(null);
  const runGenerationRef = useRef(0);

  const selectedMolecules = useMemo(() => new Set(selectedMoleculeKeys), [selectedMoleculeKeys]);

  const handleSelectedBackendModeChange = useCallback(
    (nextMode: BenchmarkBackendMode) => {
      if (shots === getDefaultBenchmarkShots(selectedBackendMode)) {
        setShots(getDefaultBenchmarkShots(nextMode));
      }
      setSelectedBackendMode(nextMode);
    },
    [selectedBackendMode, setSelectedBackendMode, setShots, shots],
  );

  useEffect(() => {
    primeCustomMoleculeCache(customMolecules);
  }, [customMolecules]);

  useBenchmarkWorkspaceCacheSync({
    benchmarkId,
    benchmarkMode,
    selectedMoleculeKeys,
    selectedAlgorithms,
    algorithmVariants,
    selectedBasis,
    selectedBackendMode,
    selectedBackendName,
    shots,
    selectedAerMethod,
    selectedDevice,
    chemicalAccuracyHa,
    customMolecules,
    entries,
  });

  const {
    ensureBackendCapabilitiesLoaded,
    backendOptions,
    ibmBackends,
    backendSelectionRequired,
    backendReady,
    backendHelperText,
    backendCapabilitiesLoading,
    backendCapabilitiesRefreshing,
    resolvedBackendName,
  } = useBackendCapabilityState({
    selectedBackendMode,
    selectedBackendName,
    setSelectedBackendName,
  });

  const { startPolling, stopPolling } = useBenchmarkPollingController({
    restoredEntries,
    runGenerationRef,
    setEntries,
    setRunning,
  });

  const handleAddCustomMolecule = useCallback(
    (mol: MoleculeResponse) => {
      setCustomMolecules((previous) => appendCustomMoleculeIfMissing(previous, mol));
      setSelectedMoleculeKeys((previous) => {
        const next = new Set(previous);
        next.add(`custom:${mol.id}`);
        return Array.from(next);
      });
    },
    [setCustomMolecules, setSelectedMoleculeKeys],
  );

  const handleRemoveCustomMolecule = useCallback(
    (id: UUID) => {
      setCustomMolecules((previous) => previous.filter((molecule) => molecule.id !== id));
      setSelectedMoleculeKeys((previous) => previous.filter((key) => key !== `custom:${id}`));
    },
    [setCustomMolecules, setSelectedMoleculeKeys],
  );

  const allPresets = useMemo(
    () => [...BENCHMARK_MOLECULE_PRESETS, ...customMolecules.map(moleculeToPreset)],
    [customMolecules],
  );
  const selectedPresets = useMemo(
    () => allPresets.filter((preset) => selectedMolecules.has(preset.key)),
    [allPresets, selectedMolecules],
  );
  const disabledAlgorithms = useMemo(
    () => getBenchmarkAlgorithmBlockers(selectedPresets, selectedBackendMode),
    [selectedBackendMode, selectedPresets],
  );
  const {
    activeVariants,
    activeAlgorithmSet,
    setBenchmarkModeValue,
    addAdvancedVariant,
    setAdvancedVariantCount,
    duplicateAdvancedVariant,
    updateAdvancedVariant,
    removeAdvancedVariant,
  } = useBenchmarkVariantSelectionState({
    benchmarkMode,
    selectedBackendMode,
    selectedAlgorithms,
    algorithmVariants,
    selectedPresets,
    entries,
    running,
    pendingBenchmarkAction,
    disabledAlgorithms,
    chemicalAccuracyHa,
    setBenchmarkMode,
    setSelectedAlgorithms,
    setAlgorithmVariants,
    setEntries,
  });

  const hydrateSavedBenchmark = useCallback(
    (savedRun: SavedBenchmarkRun) => {
      writeBenchmarkWorkspaceViewCache(
        savedRun.id,
        buildBenchmarkWorkspaceSnapshotFromSavedRun(savedRun),
      );
      hydrateSavedBenchmarkState({
        savedRun,
        startPolling,
        setSelectedSavedBenchmarkId,
        setSelectedMoleculeKeys,
        setBenchmarkMode,
        setSelectedAlgorithms,
        setAlgorithmVariants,
        setSelectedBasis,
        setSelectedBackendMode,
        setSelectedBackendName,
        setShots,
        setSelectedAerMethod,
        setSelectedDevice,
        setChemicalAccuracyHa,
        setCustomMolecules,
        setEntries,
        setActiveSavedBenchmarkId,
        setRunning,
      });
    },
    [
      setActiveSavedBenchmarkId,
      setChemicalAccuracyHa,
      setCustomMolecules,
      setEntries,
      setBenchmarkMode,
      setRunning,
      setSelectedAlgorithms,
      setAlgorithmVariants,
      setSelectedBackendMode,
      setSelectedBackendName,
      setSelectedAerMethod,
      setSelectedDevice,
      setSelectedBasis,
      setSelectedMoleculeKeys,
      setSelectedSavedBenchmarkId,
      setShots,
      startPolling,
    ],
  );

  useSavedBenchmarkCatalog(setSavedBenchmarkRuns);
  useBenchmarkRouteReset({
    benchmarkId,
    runGenerationRef,
    stopPolling,
    setSelectedSavedBenchmarkId,
    setActiveSavedBenchmarkId,
    setHydratedBenchmarkId,
    setRunning,
    setEntries,
    setSelectedMoleculeKeys,
    setBenchmarkMode,
    setSelectedAlgorithms,
    setAlgorithmVariants,
    setSelectedBasis,
    setSelectedBackendMode,
    setSelectedBackendName,
    setShots,
    setSelectedAerMethod,
    setSelectedDevice,
    setChemicalAccuracyHa,
    setCustomMolecules,
    setSavedBenchmarkLoadError,
  });
  useBenchmarkRouteHydration({
    benchmarkId,
    hydrateSavedBenchmark,
    runGenerationRef,
    setSavedBenchmarkRuns,
    setHydratedBenchmarkId,
    setSavedBenchmarkLoadError,
  });
  const flushPendingActivePersist = useCallback(
    () =>
      flushPendingActiveBenchmarkEntriesPersist({
        benchmarkId: activeSavedBenchmarkId,
        entries,
        benchmarkSaveTimerRef,
        queryClient,
      }),
    [activeSavedBenchmarkId, benchmarkSaveTimerRef, entries, queryClient],
  );
  useBenchmarkTimerCleanup(
    benchmarkSaveTimerRef,
    benchmarkConfigSaveTimerRef,
    flushPendingActivePersist,
  );
  useActiveBenchmarkEntrySync({
    activeSavedBenchmarkId,
    entries,
    savedBenchmarkRuns,
    benchmarkSaveTimerRef,
    queryClient,
    setSavedBenchmarkRuns,
  });
  useDeactivateActiveBenchmark({
    activeSavedBenchmarkId,
    entries,
    pendingBenchmarkAction,
    setActiveSavedBenchmarkId,
  });

  const buildBenchmarkPayload = useCallback(
    (nextEntries: BenchmarkEntry[]) =>
      buildBenchmarkPayloadData(
        {
          selectedPresets,
          selectedAlgorithms: activeAlgorithmSet,
          algorithmCount:
            benchmarkMode === "advanced" ? activeVariants.length : activeAlgorithmSet.size,
          selectedBasis,
          selectedBackendMode,
          selectedBackendName: resolvedBackendName,
          shots,
          selectedAerMethod,
          selectedDevice,
          chemicalAccuracyHa,
          customMolecules,
        },
        nextEntries,
      ),
    [
      chemicalAccuracyHa,
      customMolecules,
      resolvedBackendName,
      selectedAerMethod,
      selectedDevice,
      shots,
      activeAlgorithmSet,
      activeVariants.length,
      benchmarkMode,
      selectedBackendMode,
      selectedBasis,
      selectedPresets,
    ],
  );

  const buildBenchmarkSignature = useCallback(
    (nextEntries: BenchmarkEntry[]) =>
      buildBenchmarkSignatureData(
        {
          selectedPresets,
          selectedAlgorithms: activeAlgorithmSet,
          selectedBasis,
          selectedBackendMode,
          selectedBackendName: resolvedBackendName,
          shots,
          selectedAerMethod,
          selectedDevice,
          chemicalAccuracyHa,
          customMolecules,
        },
        nextEntries,
      ),
    [
      chemicalAccuracyHa,
      customMolecules,
      resolvedBackendName,
      selectedAerMethod,
      selectedDevice,
      shots,
      activeAlgorithmSet,
      selectedBackendMode,
      selectedBasis,
      selectedPresets,
    ],
  );

  useBenchmarkDraftSync({
    benchmarkId,
    selectedSavedBenchmarkId,
    hydratedBenchmarkId,
    activeSavedBenchmarkId,
    pendingBenchmarkAction,
    running,
    entries,
    buildBenchmarkPayload,
    buildBenchmarkSignature,
    benchmarkConfigSaveTimerRef,
    benchmarkConfigSignatureRef,
    queryClient,
    setSavedBenchmarkRuns,
  });

  const { handleRunBenchmark, confirmIbmBenchmarkRun } = useBenchmarkExecutionStartActions({
    benchmarkId,
    selectedSavedBenchmarkId,
    selectedPresets,
    activeVariants,
    selectedBasis,
    selectedBackendMode,
    resolvedBackendName,
    shots,
    selectedAerMethod,
    selectedDevice,
    stopPolling,
    startPolling,
    runGenerationRef,
    benchmarkSaveTimerRef,
    benchmarkConfigSaveTimerRef,
    benchmarkConfigSignatureRef,
    buildBenchmarkPayload,
    buildBenchmarkSignature,
    setEntries,
    setRunning,
    setSavedBenchmarkRuns,
    setSelectedSavedBenchmarkId,
    setActiveSavedBenchmarkId,
    setHydratedBenchmarkId,
    queryClient,
    setIbmConfirmationOpen,
    persistSubmittedEntries: (snapshot, submittedEntries, isCurrentGeneration) => {
      if (!isCurrentGeneration()) return;
      const optimisticSnapshot = {
        ...snapshot,
        updatedAt: new Date().toISOString(),
        entries: submittedEntries,
      };
      setSavedBenchmarkRuns((current) => upsertSavedBenchmarkRun(current, optimisticSnapshot));
      syncSavedBenchmarkRunQueryCache(queryClient, optimisticSnapshot);
      persistActiveBenchmarkEntries(
        snapshot.id,
        submittedEntries,
        queryClient,
        setSavedBenchmarkRuns,
      );
    },
    reportActionError: reportBenchmarkActionError,
  });

  const {
    handleCancelBenchmark,
    handlePauseBenchmark,
    handleResumeBenchmark,
    handleRestartBenchmark,
    handleBenchmarkEntryAction,
    handleBenchmarkMoleculeAction,
  } = useBenchmarkControlActions({
    entries,
    selectedSavedBenchmarkId,
    selectedBasis,
    selectedBackendMode,
    resolvedBackendName,
    setEntries,
    setRunning,
    setPendingBenchmarkAction,
    setActiveSavedBenchmarkId,
    startPolling,
    stopPolling,
    queryClient,
    setIbmConfirmationOpen,
    runGenerationRef,
    reportActionError: reportBenchmarkActionError,
  });

  const { handleLoadSavedBenchmark, handleDeleteSavedBenchmark } = useSavedBenchmarkActions({
    activeSavedBenchmarkId,
    selectedSavedBenchmarkId,
    hydrateSavedBenchmark,
    queryClient,
    runGenerationRef,
    stopPolling,
    setSavedBenchmarkLoadError,
    setSavedBenchmarkRuns,
    setActiveSavedBenchmarkId,
    setSelectedSavedBenchmarkId,
    reportActionError: reportBenchmarkActionError,
  });

  const toggleMolecule = useCallback(
    (key: string) => setSelectedMoleculeKeys((previous) => toggleDistinctValue(previous, key)),
    [setSelectedMoleculeKeys],
  );

  const setSelectedMolecules = useCallback(
    (keys: string[]) => setSelectedMoleculeKeys(Array.from(new Set(keys))),
    [setSelectedMoleculeKeys],
  );

  const toggleAlgorithm = useCallback(
    (algorithm: RunAlgorithm) =>
      setSelectedAlgorithms((previous) => toggleDistinctValue(previous, algorithm)),
    [setSelectedAlgorithms],
  );

  const setSelectedAlgorithmValues = useCallback(
    (algorithms: RunAlgorithm[]) => setSelectedAlgorithms(Array.from(new Set(algorithms))),
    [setSelectedAlgorithms],
  );

  const grouped = useMemo(
    () => buildGroupedBenchmarkEntries(allPresets, selectedMolecules, entries),
    [allPresets, entries, selectedMolecules],
  );

  const stats = useMemo(
    () => getBenchmarkStats(entries, chemicalAccuracyHa),
    [chemicalAccuracyHa, entries],
  );
  const pauseInProgress =
    pendingBenchmarkAction === "pause" || entries.some((entry) => entry.status === "pausing");
  const hasPausedBenchmark = entries.some(isResumableBenchmarkEntry);
  const resumeInProgress = pendingBenchmarkAction === "resume";
  const restartInProgress = pendingBenchmarkAction === "restart";
  const canPauseBenchmark = pauseInProgress || entries.some(isPausableBenchmarkEntry);
  const hasCachedSavedBenchmarkView = hasCachedSavedBenchmarkSelection({
    benchmarkId,
    selectedSavedBenchmarkId,
    entries,
    selectedMoleculeKeys,
  });
  const hydratingSavedBenchmark =
    benchmarkId !== null && hydratedBenchmarkId !== benchmarkId && !hasCachedSavedBenchmarkView;

  return {
    entries,
    setEntries,
    running,
    hydratingSavedBenchmark,
    savedBenchmarkLoadError,
    benchmarkMode,
    setBenchmarkMode: setBenchmarkModeValue,
    selectedMolecules,
    selectedAlgorithms: activeAlgorithmSet,
    algorithmVariants,
    disabledAlgorithms,
    selectedBasis,
    setSelectedBasis,
    selectedBackendMode,
    setSelectedBackendMode: handleSelectedBackendModeChange,
    selectedBackendName: resolvedBackendName,
    shots,
    setShots,
    selectedAerMethod,
    setSelectedAerMethod,
    selectedDevice,
    setSelectedDevice,
    setSelectedBackendName,
    ensureBackendCapabilitiesLoaded,
    backendOptions,
    ibmBackends,
    backendSelectionRequired,
    backendReady,
    chemicalAccuracyHa,
    setChemicalAccuracyHa,
    customMolecules,
    grouped,
    backendHelperText,
    backendCapabilitiesLoading,
    backendCapabilitiesRefreshing,
    benchmarkConfirmationDescription: describeBenchmarkBackendMode(
      selectedBackendMode,
      resolvedBackendName,
      selectedPresets.length * activeVariants.length,
    ),
    ibmConfirmationOpen,
    setIbmConfirmationOpen,
    confirmIbmBenchmarkRun,
    stats,
    savedBenchmarkRuns,
    selectedSavedBenchmarkId,
    hasPausedBenchmark,
    canPauseBenchmark,
    pauseInProgress,
    resumeInProgress,
    restartInProgress,
    pendingBenchmarkAction,
    toggleMolecule,
    toggleAlgorithm,
    setSelectedMolecules,
    setSelectedAlgorithmValues,
    addAdvancedVariant,
    setAdvancedVariantCount,
    duplicateAdvancedVariant,
    updateAdvancedVariant,
    removeAdvancedVariant,
    handleAddCustomMolecule,
    handleRemoveCustomMolecule,
    handleRunBenchmark,
    handleLoadSavedBenchmark,
    handleDeleteSavedBenchmark,
    handlePauseBenchmark,
    handleResumeBenchmark,
    handleRestartBenchmark,
    handleBenchmarkEntryAction,
    handleBenchmarkMoleculeAction,
    handleCancelBenchmark,
  };
}
