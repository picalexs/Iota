import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "@tanstack/react-router";
import { ChevronLeft } from "lucide-react";
import { loadRunFormConfigMetadata } from "@/components/forms/run-form/manual-mode-config";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { BenchmarkPageSkeleton } from "@/components/ui/route-skeleton-variants";
import { PageErrorState } from "@/components/ui/page-error-state";
import { useSmartBack } from "@/hooks/use-smart-back";
import { useRunConfigMetadata } from "@/hooks";
import { getChemicalAccuracyTargetOptions } from "@/lib/run-form-recommendations";
import { BenchmarkControls } from "./benchmark/benchmark-controls";
import { BenchmarkInsights } from "./benchmark/benchmark-insights";
import { BenchmarkResultsTable } from "./benchmark/benchmark-results-table";
import {
  filterBenchmarkRows,
  getAssociatedBenchmarkRunIds,
  getBenchmarkStats,
  sortBenchmarkRows,
  type BenchmarkAccuracyFilter,
  type BenchmarkAccuracySort,
} from "./benchmark/benchmark-utils";
import { useBenchmarkState } from "./benchmark/use-benchmark-state";

export function BenchmarkPage() {
  const params = useParams({ strict: false }) as { benchmarkId?: string };
  const benchmarkId = params.benchmarkId ?? null;
  const benchmarkScrollKey =
    benchmarkId === null ? "benchmark-scroll:new" : `benchmark-scroll:${benchmarkId}`;
  const navigate = useNavigate();
  const goBack = useSmartBack({ to: "/benchmarks" });
  const configMetadata = useRunConfigMetadata(loadRunFormConfigMetadata).data ?? null;
  const chemicalAccuracyTargetOptions = useMemo(
    () => getChemicalAccuracyTargetOptions(configMetadata?.easy_goal_presets),
    [configMetadata?.easy_goal_presets],
  );
  const [accuracyFilter, setAccuracyFilter] = useState<BenchmarkAccuracyFilter>("all");
  const [accuracySort, setAccuracySort] = useState<BenchmarkAccuracySort>("default");
  const [restartConfirmationOpen, setRestartConfirmationOpen] = useState(false);
  const [clearConfirmationOpen, setClearConfirmationOpen] = useState(false);
  const [deleteConfirmationOpen, setDeleteConfirmationOpen] = useState(false);
  const [deleteAssociatedRuns, setDeleteAssociatedRuns] = useState(false);
  const [deleteBenchmarkInProgress, setDeleteBenchmarkInProgress] = useState(false);
  const {
    entries,
    setEntries,
    running,
    hydratingSavedBenchmark,
    savedBenchmarkLoadError,
    benchmarkMode,
    setBenchmarkMode,
    selectedMolecules,
    selectedAlgorithms,
    algorithmVariants,
    disabledAlgorithms,
    selectedBasis,
    setSelectedBasis,
    selectedBackendMode,
    setSelectedBackendMode,
    selectedBackendName,
    setSelectedBackendName,
    shots,
    setShots,
    optimizationLevel,
    setOptimizationLevel,
    seedTranspiler,
    setSeedTranspiler,
    dynamicalDecoupling,
    setDynamicalDecoupling,
    twirling,
    setTwirling,
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
    benchmarkConfirmationDescription,
    ibmConfirmationOpen,
    setIbmConfirmationOpen,
    confirmIbmBenchmarkRun,
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
    handlePauseBenchmark,
    handleResumeBenchmark,
    handleRestartBenchmark,
    handleBenchmarkEntryAction,
    handleBenchmarkMoleculeAction,
    handleDeleteSavedBenchmark,
    handleCancelBenchmark,
  } = useBenchmarkState({ benchmarkId });
  const currentBenchmarkId = selectedSavedBenchmarkId ?? benchmarkId;
  const showDeleteBenchmarkAction = currentBenchmarkId !== null;
  const associatedRunCount = getAssociatedBenchmarkRunIds(entries).length;

  function handleClearBenchmarkResults() {
    setEntries([]);
    setAccuracyFilter("all");
    setAccuracySort("default");
    setClearConfirmationOpen(false);
  }

  async function handleDeleteBenchmark() {
    if (currentBenchmarkId === null) {
      setDeleteConfirmationOpen(false);
      setDeleteAssociatedRuns(false);
      return;
    }

    setDeleteBenchmarkInProgress(true);
    try {
      await handleDeleteSavedBenchmark(currentBenchmarkId, { deleteAssociatedRuns });
      setEntries([]);
      await navigate({ to: "/benchmarks" });
      setDeleteAssociatedRuns(false);
      setDeleteConfirmationOpen(false);
    } finally {
      setDeleteBenchmarkInProgress(false);
    }
  }

  const visibleEntries = useMemo(
    () => entries.filter((entry) => entry.status !== "idle"),
    [entries],
  );
  const visibleStats = useMemo(
    () => getBenchmarkStats(visibleEntries, chemicalAccuracyHa),
    [chemicalAccuracyHa, visibleEntries],
  );
  const filteredGrouped = useMemo(
    () =>
      grouped
        .map(({ preset, rows }) => ({
          preset,
          rows: sortBenchmarkRows(
            filterBenchmarkRows(
              rows.filter((row) => row.status !== "idle"),
              chemicalAccuracyHa,
              accuracyFilter,
            ),
            chemicalAccuracyHa,
            accuracySort,
          ),
        }))
        .filter(({ rows }) => rows.length > 0),
    [accuracyFilter, accuracySort, chemicalAccuracyHa, grouped],
  );
  const moleculeActionEntriesByKey = useMemo(
    () => new Map(grouped.map(({ preset, rows }) => [preset.key, rows] as const)),
    [grouped],
  );

  const filterOptions: Array<{ value: BenchmarkAccuracyFilter; label: string }> = [
    { value: "all", label: "All rows" },
    { value: "accurate", label: "Accurate" },
    { value: "not_accurate", label: "Not accurate" },
    { value: "unscored", label: "Unscored" },
  ];
  const sortOptions: Array<{ value: BenchmarkAccuracySort; label: string }> = [
    { value: "default", label: "Default order" },
    { value: "lowest_error", label: "Lowest error" },
    { value: "highest_error", label: "Highest error" },
  ];

  useEffect(() => {
    if (hydratingSavedBenchmark) return;

    let rawScroll: string | null = null;
    try {
      rawScroll = sessionStorage.getItem(benchmarkScrollKey);
      sessionStorage.removeItem(benchmarkScrollKey);
    } catch {
      return;
    }

    const top = rawScroll === null ? Number.NaN : Number(rawScroll);
    if (!Number.isFinite(top) || top < 0) return;
    window.scrollTo({ top, left: 0, behavior: "auto" });
  }, [benchmarkScrollKey, hydratingSavedBenchmark]);

  function rememberBenchmarkScrollPosition() {
    try {
      sessionStorage.setItem(benchmarkScrollKey, String(window.scrollY));
    } catch {
      // Best-effort only.
    }
  }

  if (hydratingSavedBenchmark) {
    return <BenchmarkPageSkeleton />;
  }

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-8">
      <div>
        <button
          type="button"
          onClick={goBack}
          className="mb-3 flex w-fit items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
          aria-label="Go back"
        >
          <ChevronLeft className="size-4" />
          Back
        </button>
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">Algorithm Benchmark</h1>
        <p className="mt-2 max-w-3xl text-sm text-muted-foreground sm:text-[15px]">
          Compare algorithms on the same molecule set with a shared backend, basis, and accuracy
          target.
        </p>
      </div>

      {savedBenchmarkLoadError ? (
        <PageErrorState
          title="We couldn't restore this benchmark"
          description="The saved dashboard data could not be loaded. Reload the page after the backend is ready and try again."
          detail={savedBenchmarkLoadError}
          onRetry={null}
        />
      ) : null}

      <BenchmarkControls
        benchmarkMode={benchmarkMode}
        selectedMolecules={selectedMolecules}
        selectedAlgorithms={selectedAlgorithms}
        algorithmVariants={algorithmVariants}
        disabledAlgorithms={disabledAlgorithms}
        selectedBasis={selectedBasis}
        selectedBackendMode={selectedBackendMode}
        selectedBackendName={selectedBackendName}
        shots={shots}
        optimizationLevel={optimizationLevel}
        seedTranspiler={seedTranspiler}
        dynamicalDecoupling={dynamicalDecoupling}
        twirling={twirling}
        backendOptions={backendOptions}
        ibmBackends={ibmBackends}
        backendSelectionRequired={backendSelectionRequired}
        backendReady={backendReady}
        chemicalAccuracyHa={chemicalAccuracyHa}
        chemicalAccuracyTargetOptions={chemicalAccuracyTargetOptions}
        customMolecules={customMolecules}
        running={running}
        hasPausedBenchmark={hasPausedBenchmark}
        canPauseBenchmark={canPauseBenchmark}
        pauseInProgress={pauseInProgress}
        resumeInProgress={resumeInProgress}
        restartInProgress={restartInProgress}
        total={visibleStats.total}
        done={visibleStats.done}
        completed={visibleStats.completed}
        failed={visibleStats.failed}
        cancelled={visibleStats.cancelled}
        backendHelperText={backendHelperText}
        backendCapabilitiesLoading={backendCapabilitiesLoading}
        backendCapabilitiesRefreshing={backendCapabilitiesRefreshing}
        onRefreshBackendCapabilities={ensureBackendCapabilitiesLoaded}
        onToggleMolecule={toggleMolecule}
        onToggleAlgorithm={toggleAlgorithm}
        onSetMolecules={setSelectedMolecules}
        onSetAlgorithms={setSelectedAlgorithmValues}
        onBenchmarkModeChange={setBenchmarkMode}
        onAddAdvancedVariant={addAdvancedVariant}
        onSetAdvancedVariantCount={setAdvancedVariantCount}
        onDuplicateAdvancedVariant={duplicateAdvancedVariant}
        onUpdateAdvancedVariant={updateAdvancedVariant}
        onRemoveAdvancedVariant={removeAdvancedVariant}
        onBasisChange={setSelectedBasis}
        onBackendModeChange={setSelectedBackendMode}
        onBackendNameChange={setSelectedBackendName}
        onShotsChange={setShots}
        onOptimizationLevelChange={setOptimizationLevel}
        onSeedTranspilerChange={setSeedTranspiler}
        onDynamicalDecouplingChange={setDynamicalDecoupling}
        onTwirlingChange={setTwirling}
        onBackendOptionsOpen={ensureBackendCapabilitiesLoaded}
        onChemicalAccuracyChange={setChemicalAccuracyHa}
        onAddCustomMolecule={handleAddCustomMolecule}
        onRemoveCustomMolecule={handleRemoveCustomMolecule}
        onRunBenchmark={handleRunBenchmark}
        onPauseBenchmark={handlePauseBenchmark}
        onResumeBenchmark={handleResumeBenchmark}
        onRestartBenchmark={() => setRestartConfirmationOpen(true)}
        onCancelBenchmark={handleCancelBenchmark}
        showDeleteBenchmarkAction={showDeleteBenchmarkAction}
        deleteBenchmarkInProgress={deleteBenchmarkInProgress}
        onDeleteBenchmark={() => setDeleteConfirmationOpen(true)}
        onClear={() => setClearConfirmationOpen(true)}
      />

      {visibleEntries.length > 0 && (
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-3 rounded-xl border border-border/80 bg-card p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-wrap items-center gap-2">
              {filterOptions.map((option) => (
                <Button
                  key={option.value}
                  type="button"
                  size="sm"
                  variant={accuracyFilter === option.value ? "secondary" : "outline"}
                  className="h-8 text-xs"
                  onClick={() => setAccuracyFilter(option.value)}
                >
                  {option.label}
                </Button>
              ))}
            </div>
            <div className="flex flex-wrap items-center gap-2 sm:justify-end">
              {sortOptions.map((option) => (
                <Button
                  key={option.value}
                  type="button"
                  size="sm"
                  variant={accuracySort === option.value ? "secondary" : "outline"}
                  className="h-8 text-xs"
                  onClick={() => setAccuracySort(option.value)}
                >
                  {option.label}
                </Button>
              ))}
            </div>
          </div>

          <BenchmarkInsights grouped={filteredGrouped} chemicalAccuracyHa={chemicalAccuracyHa} />

          <BenchmarkResultsTable
            grouped={filteredGrouped}
            selectedBasis={selectedBasis}
            chemicalAccuracyHa={chemicalAccuracyHa}
            pendingAction={pendingBenchmarkAction}
            onRunAction={handleBenchmarkEntryAction}
            onMoleculeAction={handleBenchmarkMoleculeAction}
            getMoleculeActionEntries={(presetKey) =>
              moleculeActionEntriesByKey.get(presetKey) ?? []
            }
            onBeforeOpenRun={rememberBenchmarkScrollPosition}
          />
        </div>
      )}

      <ConfirmDialog
        open={ibmConfirmationOpen}
        onOpenChange={setIbmConfirmationOpen}
        title="Submit benchmark to IBM Quantum?"
        description={benchmarkConfirmationDescription}
        confirmText="Submit to IBM backend"
        cancelText="Review benchmark"
        onConfirm={confirmIbmBenchmarkRun}
      />

      <ConfirmDialog
        open={clearConfirmationOpen}
        onOpenChange={setClearConfirmationOpen}
        title="Clear benchmark results?"
        description="This removes the current benchmark rows from the workspace so you can edit the configuration and run it again. The saved setup stays in place."
        confirmText="Clear results"
        cancelText="Keep results"
        onConfirm={handleClearBenchmarkResults}
      />

      <ConfirmDialog
        open={restartConfirmationOpen}
        onOpenChange={setRestartConfirmationOpen}
        title="Restart paused benchmark?"
        description="A new run will be created for each paused benchmark row using the stored run configuration."
        confirmText="Restart paused rows"
        cancelText="Keep paused"
        onConfirm={handleRestartBenchmark}
        loading={restartInProgress}
      />

      <ConfirmDialog
        open={deleteConfirmationOpen}
        onOpenChange={(open) => {
          setDeleteConfirmationOpen(open);
          if (!open) {
            setDeleteAssociatedRuns(false);
          }
        }}
        title="Delete this benchmark?"
        description={
          associatedRunCount > 0
            ? "This removes the saved benchmark snapshot. You can also delete the associated runs from the runs history."
            : "This removes the saved benchmark snapshot. The individual runs remain available in the runs history."
        }
        confirmText="Delete benchmark"
        cancelText="Keep benchmark"
        variant="destructive"
        onConfirm={handleDeleteBenchmark}
        loading={deleteBenchmarkInProgress}
        disabled={currentBenchmarkId === null}
      >
        {associatedRunCount > 0 ? (
          <label className="flex items-start gap-3 rounded-md border p-3 text-sm">
            <Checkbox
              aria-label="Also delete associated runs"
              checked={deleteAssociatedRuns}
              onCheckedChange={(checked) => setDeleteAssociatedRuns(checked === true)}
            />
            <span>Also delete {associatedRunCount} associated run(s) from the runs history.</span>
          </label>
        ) : null}
      </ConfirmDialog>
    </div>
  );
}
