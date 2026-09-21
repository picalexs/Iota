import { useMemo } from "react";
import type { BackendDeviceSummary, MoleculeResponse, RunAlgorithm, UUID } from "@/types/run";
import type { AerMethod } from "@/types/run-config";
import {
  getChemicalAccuracyTargetOptions,
  type ChemicalAccuracyTargetOption,
} from "@/lib/run-form-recommendations";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { type BenchmarkBackendMode, type BenchmarkBackendOption } from "./benchmark-utils";
import {
  BenchmarkAlgorithmSection,
  BenchmarkMoleculeSection,
} from "./benchmark-molecule-selection";
import { BenchmarkExecutionSettings } from "./benchmark-execution-settings";
import { BenchmarkActionBar } from "./benchmark-action-bar";
import { BenchmarkAdvancedAlgorithmSection } from "./benchmark-advanced-algorithm-section";
import { BenchmarkModeSection } from "./benchmark-mode-section";
import { useBenchmarkBasisSets } from "./use-benchmark-basis-sets";
import type { BenchmarkAlgorithmVariant, BenchmarkVariantMode } from "./benchmark-variants";
import { kqdRequiresBranchEstimatorForBackendMode } from "./benchmark-variants";
import {
  getBackendNameLabel,
  getBenchmarkCompletionRatio,
  getSelectedBlockedReasons,
  isBenchmarkRunDisabled,
  isBenchmarkWorkspaceLocked,
  shouldShowBenchmarkResetResults,
} from "@/features/benchmarks/state/control-selectors";
import { useBenchmarkMoleculeWorkspace } from "./use-benchmark-molecule-workspace";
import { BackendRefreshButton } from "@/components/forms/run-form/backend-refresh-button";
import { Spinner } from "@/components/ui/spinner";

interface BenchmarkControlsProps {
  benchmarkMode?: BenchmarkVariantMode;
  selectedMolecules: ReadonlySet<string>;
  selectedAlgorithms: ReadonlySet<RunAlgorithm>;
  algorithmVariants?: readonly BenchmarkAlgorithmVariant[];
  disabledAlgorithms: ReadonlyMap<RunAlgorithm, string>;
  selectedBasis: string;
  selectedBackendMode: BenchmarkBackendMode;
  selectedBackendName: string | null;
  backendOptions: readonly BenchmarkBackendOption[];
  ibmBackends: readonly BackendDeviceSummary[];
  backendSelectionRequired: boolean;
  backendReady: boolean;
  chemicalAccuracyHa: number;
  chemicalAccuracyTargetOptions?: readonly ChemicalAccuracyTargetOption[];
  customMolecules: readonly MoleculeResponse[];
  running: boolean;
  hasPausedBenchmark: boolean;
  canPauseBenchmark: boolean;
  pauseInProgress: boolean;
  resumeInProgress: boolean;
  restartInProgress: boolean;
  total: number;
  done: number;
  completed?: number;
  failed?: number;
  cancelled?: number;
  backendHelperText?: string | null;
  backendCapabilitiesLoading?: boolean;
  backendCapabilitiesRefreshing?: boolean;
  onRefreshBackendCapabilities?: () => void;
  onToggleMolecule: (key: string) => void;
  onToggleAlgorithm: (algorithm: RunAlgorithm) => void;
  onSetMolecules: (keys: string[]) => void;
  onSetAlgorithms: (algorithms: RunAlgorithm[]) => void;
  onBenchmarkModeChange?: (mode: BenchmarkVariantMode) => void;
  onAddAdvancedVariant?: (algorithm: RunAlgorithm) => void;
  onSetAdvancedVariantCount?: (algorithm: RunAlgorithm, count: number) => void;
  onDuplicateAdvancedVariant?: (variantId: string) => void;
  onUpdateAdvancedVariant?: (
    variantId: string,
    updater: (variant: BenchmarkAlgorithmVariant) => BenchmarkAlgorithmVariant,
  ) => void;
  onRemoveAdvancedVariant?: (variantId: string) => void;
  onBasisChange: (basis: string) => void;
  onBackendModeChange: (backend: BenchmarkBackendMode) => void;
  onBackendNameChange: (backendName: string) => void;
  onBackendOptionsOpen: () => void;
  onChemicalAccuracyChange: (thresholdHa: number) => void;
  shots?: number;
  onShotsChange?: (shots: number) => void;
  aerMethod?: AerMethod | null;
  device?: "CPU" | "GPU" | null;
  onAerMethodChange?: (method: AerMethod) => void;
  onDeviceChange?: (device: "CPU" | "GPU" | null) => void;
  onAddCustomMolecule: (molecule: MoleculeResponse) => void;
  onRemoveCustomMolecule: (id: UUID) => void;
  onRunBenchmark: () => void;
  onPauseBenchmark: () => void;
  onResumeBenchmark: () => void;
  onRestartBenchmark: () => void;
  onCancelBenchmark: () => void;
  showDeleteBenchmarkAction?: boolean;
  deleteBenchmarkInProgress?: boolean;
  onDeleteBenchmark?: () => void;
  onClear: () => void;
}

export function BenchmarkControls({
  benchmarkMode = "simple",
  selectedMolecules,
  selectedAlgorithms,
  algorithmVariants = [],
  disabledAlgorithms,
  selectedBasis,
  selectedBackendMode,
  selectedBackendName,
  backendOptions,
  ibmBackends,
  backendSelectionRequired,
  backendReady,
  chemicalAccuracyHa,
  chemicalAccuracyTargetOptions = getChemicalAccuracyTargetOptions(undefined),
  customMolecules,
  running,
  hasPausedBenchmark,
  canPauseBenchmark,
  pauseInProgress,
  resumeInProgress,
  restartInProgress,
  total,
  done,
  completed = done,
  failed = 0,
  cancelled = 0,
  backendHelperText,
  backendCapabilitiesLoading = false,
  backendCapabilitiesRefreshing = false,
  onRefreshBackendCapabilities,
  onToggleMolecule,
  onToggleAlgorithm,
  onSetMolecules,
  onSetAlgorithms,
  onBenchmarkModeChange = () => undefined,
  onAddAdvancedVariant = () => undefined,
  onSetAdvancedVariantCount = () => undefined,
  onDuplicateAdvancedVariant = () => undefined,
  onUpdateAdvancedVariant = () => undefined,
  onRemoveAdvancedVariant = () => undefined,
  onBasisChange,
  onBackendModeChange,
  onBackendNameChange,
  onBackendOptionsOpen,
  onChemicalAccuracyChange,
  shots = 4096,
  onShotsChange = () => undefined,
  aerMethod = "automatic",
  device = null,
  onAerMethodChange = () => undefined,
  onDeviceChange = () => undefined,
  onAddCustomMolecule,
  onRemoveCustomMolecule,
  onRunBenchmark,
  onPauseBenchmark,
  onResumeBenchmark,
  onRestartBenchmark,
  onCancelBenchmark,
  showDeleteBenchmarkAction = false,
  deleteBenchmarkInProgress = false,
  onDeleteBenchmark,
  onClear,
}: Readonly<BenchmarkControlsProps>) {
  const actionInProgress = pauseInProgress || resumeInProgress || restartInProgress;
  const workspaceLocked = isBenchmarkWorkspaceLocked({
    total,
    running,
    hasPausedBenchmark,
    actionInProgress,
  });
  const { basisIds, basisDefault, orderedBasisOptions } = useBenchmarkBasisSets(
    selectedBasis,
    onBasisChange,
  );
  const {
    moleculeOptions,
    visibleMoleculeOptions,
    randomLibraryLoading,
    randomLibraryMessage,
    hasVisibleMolecules,
    handleRandomLibraryMolecules,
    handleDeleteMolecule,
    handleDeleteAllMolecules,
    deleteAllConfirmationOpen,
    setDeleteAllConfirmationOpen,
  } = useBenchmarkMoleculeWorkspace({
    selectedMolecules,
    customMolecules,
    workspaceLocked,
    onSetMolecules,
    onAddCustomMolecule,
    onRemoveCustomMolecule,
  });
  const selectedBlockedReasons = useMemo(
    () => getSelectedBlockedReasons(moleculeOptions, selectedMolecules),
    [moleculeOptions, selectedMolecules],
  );
  const hasBlockedSelection = selectedBlockedReasons.length > 0;
  const backendNameLabel = getBackendNameLabel(selectedBackendMode);
  const completionRatio = getBenchmarkCompletionRatio(total, done);
  const noAlgorithmsSelected = selectedAlgorithms.size === 0;
  const runDisabled = isBenchmarkRunDisabled({
    workspaceLocked,
    selectedMolecules,
    benchmarkMode,
    selectedAlgorithms,
    algorithmVariants,
    hasBlockedSelection,
    backendReady,
  });
  const showResetResults = shouldShowBenchmarkResetResults({
    total,
    running,
    hasPausedBenchmark,
    actionInProgress,
  });

  return (
    <Card className="overflow-hidden">
      <CardHeader className="border-b border-border/70 pb-4">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-end xl:justify-between">
          <div className="space-y-1">
            <CardTitle>Benchmark workspace</CardTitle>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-5">
        <BenchmarkModeSection
          benchmarkMode={benchmarkMode}
          workspaceLocked={workspaceLocked}
          onBenchmarkModeChange={onBenchmarkModeChange}
        />

        {benchmarkMode === "simple" ? (
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(19rem,0.9fr)]">
            <BenchmarkMoleculeSection
              selectedMolecules={selectedMolecules}
              visibleMoleculeOptions={visibleMoleculeOptions}
              workspaceLocked={workspaceLocked}
              randomLibraryLoading={randomLibraryLoading}
              randomLibraryMessage={randomLibraryMessage}
              hasVisibleMolecules={hasVisibleMolecules}
              onRandomLibrary={() => void handleRandomLibraryMolecules()}
              onDeleteAll={() => setDeleteAllConfirmationOpen(true)}
              onAddCustomMolecule={onAddCustomMolecule}
              onToggleMolecule={onToggleMolecule}
              onDeleteMolecule={handleDeleteMolecule}
            />
            <BenchmarkAlgorithmSection
              noAlgorithmsSelected={noAlgorithmsSelected}
              workspaceLocked={workspaceLocked}
              selectedAlgorithms={selectedAlgorithms}
              disabledAlgorithms={disabledAlgorithms}
              onSetAlgorithms={onSetAlgorithms}
              onToggleAlgorithm={onToggleAlgorithm}
            />
          </div>
        ) : (
          <div className="grid gap-4">
            <BenchmarkMoleculeSection
              selectedMolecules={selectedMolecules}
              visibleMoleculeOptions={visibleMoleculeOptions}
              workspaceLocked={workspaceLocked}
              randomLibraryLoading={randomLibraryLoading}
              randomLibraryMessage={randomLibraryMessage}
              hasVisibleMolecules={hasVisibleMolecules}
              onRandomLibrary={() => void handleRandomLibraryMolecules()}
              onDeleteAll={() => setDeleteAllConfirmationOpen(true)}
              onAddCustomMolecule={onAddCustomMolecule}
              onToggleMolecule={onToggleMolecule}
              onDeleteMolecule={handleDeleteMolecule}
            />
            <BenchmarkAdvancedAlgorithmSection
              workspaceLocked={workspaceLocked}
              running={running}
              total={total}
              disabledAlgorithms={disabledAlgorithms}
              algorithmVariants={algorithmVariants}
              chemicalAccuracyHa={chemicalAccuracyHa}
              requiresBranchEstimator={kqdRequiresBranchEstimatorForBackendMode(
                selectedBackendMode,
              )}
              onAddAdvancedVariant={onAddAdvancedVariant}
              onSetAdvancedVariantCount={onSetAdvancedVariantCount}
              onDuplicateAdvancedVariant={onDuplicateAdvancedVariant}
              onUpdateAdvancedVariant={onUpdateAdvancedVariant}
              onRemoveAdvancedVariant={onRemoveAdvancedVariant}
            />
          </div>
        )}

        <BenchmarkExecutionSettings
          backendSelectionRequired={backendSelectionRequired}
          basisIds={basisIds}
          basisDefault={basisDefault}
          orderedBasisOptions={orderedBasisOptions}
          selectedBasis={selectedBasis}
          workspaceLocked={workspaceLocked}
          onBasisChange={onBasisChange}
          selectedBackendMode={selectedBackendMode}
          onBackendModeChange={onBackendModeChange}
          onBackendOptionsOpen={onBackendOptionsOpen}
          backendOptions={backendOptions}
          backendNameLabel={backendNameLabel}
          selectedBackendName={selectedBackendName}
          onBackendNameChange={onBackendNameChange}
          ibmBackends={ibmBackends}
          backendCapabilitiesLoading={backendCapabilitiesLoading}
          backendCapabilitiesRefreshing={backendCapabilitiesRefreshing}
          chemicalAccuracyHa={chemicalAccuracyHa}
          chemicalAccuracyTargetOptions={chemicalAccuracyTargetOptions}
          onChemicalAccuracyChange={onChemicalAccuracyChange}
          shots={shots}
          onShotsChange={onShotsChange}
          aerMethod={aerMethod}
          device={device}
          onAerMethodChange={onAerMethodChange}
          onDeviceChange={onDeviceChange}
        />

        {backendHelperText ? (
          <div className="flex min-w-0 items-center gap-2 text-xs text-muted-foreground">
            {(backendCapabilitiesLoading || backendCapabilitiesRefreshing) && <Spinner />}
            <p className="min-w-0 flex-1">{backendHelperText}</p>
            {onRefreshBackendCapabilities ? (
              <BackendRefreshButton
                onClick={onRefreshBackendCapabilities}
                refreshing={backendCapabilitiesRefreshing}
                aria-label="Refresh IBM backend availability"
              />
            ) : null}
          </div>
        ) : null}

        <BenchmarkActionBar
          hasPausedBenchmark={hasPausedBenchmark}
          actionInProgress={actionInProgress}
          resumeInProgress={resumeInProgress}
          restartInProgress={restartInProgress}
          pauseInProgress={pauseInProgress}
          canPauseBenchmark={canPauseBenchmark}
          onResumeBenchmark={onResumeBenchmark}
          onRestartBenchmark={onRestartBenchmark}
          runDisabled={runDisabled}
          onRunBenchmark={onRunBenchmark}
          running={running}
          onPauseBenchmark={onPauseBenchmark}
          onCancelBenchmark={onCancelBenchmark}
          showDeleteBenchmarkAction={showDeleteBenchmarkAction}
          deleteBenchmarkInProgress={deleteBenchmarkInProgress}
          onDeleteBenchmark={onDeleteBenchmark}
          total={total}
          completionRatio={completionRatio}
          done={done}
          completed={completed}
          failed={failed}
          cancelled={cancelled}
          showResetResults={showResetResults}
          onClear={onClear}
        />

        {hasBlockedSelection ? (
          <p className="text-xs text-warning">{selectedBlockedReasons[0]}</p>
        ) : null}
      </CardContent>

      <ConfirmDialog
        open={deleteAllConfirmationOpen}
        onOpenChange={setDeleteAllConfirmationOpen}
        title="Delete all molecules from this benchmark?"
        description="This removes custom molecules from the workspace and hides the built-in molecule cards for this session."
        confirmText="Delete all molecules"
        cancelText="Keep molecules"
        variant="destructive"
        onConfirm={handleDeleteAllMolecules}
      />
    </Card>
  );
}
