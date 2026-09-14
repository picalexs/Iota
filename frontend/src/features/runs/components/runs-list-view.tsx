import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { RunsFilterBar } from "./runs-filter-bar";
import { MoleculeLookupNotice, RunsPagination, RunsTable } from "./runs-table";
import {
  RunsBulkSelectionControls,
  RunsSelectionDialogs,
  RunsToolbarActions,
} from "./runs-selection-controls";
import type { useRunsListController } from "../state/use-runs-list-controller";

type RunsListController = ReturnType<typeof useRunsListController>;

export function RunsListView({ controller }: { readonly controller: RunsListController }) {
  const {
    usesCompactRunsLayout,
    page,
    totalRuns,
    totalPages,
    isRunsLoading,
    isMoleculeLookupLoading,
    error,
    moleculeLookupError,
    molecules,
    refetchRuns,
    filterState,
    actionState,
    bulkSelection,
    selectionEligibility,
  } = controller;
  const {
    filterStatuses,
    filterMoleculeIds,
    filterMethods,
    filterBackendTarget,
    filterChemicalAccurate,
    sortField,
    sortOrder,
    moleculeMap,
    runs,
    handleSort,
    toggleStatus,
    toggleMolecule,
    toggleMethod,
    toggleBackendTarget,
    toggleChemicalAccurate,
    clearFilters,
    goToPage,
  } = filterState;
  const {
    pendingBulkAction,
    confirmingBulkAction,
    deleteSelectionOpen,
    deleteProgress,
    bulkActionError,
    pendingRowActions,
    pendingRowDeletes,
    rowActionInProgress,
    setBulkActionError,
    setConfirmingBulkAction,
    setDeleteSelectionOpen,
    openDeleteSelection,
    handleSelectedRunsAction,
    deleteSelectedRuns,
    handleRunAction,
    handleDeleteRun,
  } = actionState;
  const {
    selectedRuns,
    pausableSelectedRuns,
    resumableSelectedRuns,
    restartableSelectedRuns,
    cancellableSelectedRuns,
  } = selectionEligibility;

  return (
    <Card aria-busy={isRunsLoading || isMoleculeLookupLoading}>
      <CardHeader>
        <div className="space-y-1">
          <CardTitle className="text-base font-semibold">All Runs</CardTitle>
        </div>
      </CardHeader>
      <CardContent className="px-0 pb-0">
        <RunsFilterBar
          filterStatuses={filterStatuses}
          filterMoleculeIds={filterMoleculeIds}
          filterMethods={filterMethods}
          filterBackendTarget={filterBackendTarget}
          filterChemicalAccurate={filterChemicalAccurate}
          molecules={molecules}
          moleculeMap={moleculeMap}
          isMoleculeLookupLoading={isMoleculeLookupLoading}
          hasActiveFilters={filterState.hasActiveFilters}
          toggleStatus={toggleStatus}
          toggleMolecule={toggleMolecule}
          toggleMethod={toggleMethod}
          toggleBackendTarget={toggleBackendTarget}
          toggleChemicalAccurate={toggleChemicalAccurate}
          clearFilters={clearFilters}
          actionSlot={
            <RunsToolbarActions
              isEditing={bulkSelection.isEditing}
              disabled={
                isRunsLoading ||
                isMoleculeLookupLoading ||
                pendingBulkAction !== null ||
                rowActionInProgress
              }
              onToggleEdit={() => bulkSelection.toggleEditing()}
            />
          }
        />
        <RunsBulkSelectionControls
          isEditing={bulkSelection.isEditing}
          runsCount={runs.length}
          selectedCount={bulkSelection.selectedCount}
          allVisibleSelected={bulkSelection.allVisibleSelected}
          someVisibleSelected={bulkSelection.someVisibleSelected}
          bulkActionError={bulkActionError}
          pausableCount={pausableSelectedRuns.length}
          resumableCount={resumableSelectedRuns.length}
          restartableCount={restartableSelectedRuns.length}
          cancellableCount={cancellableSelectedRuns.length}
          actionPending={pendingBulkAction !== null}
          rowActionInProgress={rowActionInProgress}
          onToggleSelectAllVisible={(selected) => {
            setBulkActionError(null);
            bulkSelection.setAllVisibleSelected(selected);
          }}
          onClearSelection={() => {
            setBulkActionError(null);
            bulkSelection.clearSelection();
          }}
          onConfirmPause={() => setConfirmingBulkAction("pause")}
          onResume={() =>
            handleSelectedRunsAction("resume", resumableSelectedRuns, selectedRuns, bulkSelection)
          }
          onConfirmRestart={() => setConfirmingBulkAction("restart")}
          onOpenDelete={openDeleteSelection}
          onConfirmCancel={() => setConfirmingBulkAction("cancel")}
        />
        <RunsTable
          isLoading={isRunsLoading}
          error={error}
          mobile={usesCompactRunsLayout}
          selectionMode={bulkSelection.isEditing}
          selectedRunIds={bulkSelection.selectedIdSet}
          runs={runs}
          moleculeMap={moleculeMap}
          pendingRowActions={pendingRowActions}
          pendingRowDeletes={pendingRowDeletes}
          onToggleRunSelection={(runId) => {
            setBulkActionError(null);
            bulkSelection.toggleSelected(runId);
          }}
          onRunAction={handleRunAction}
          onDeleteRun={handleDeleteRun}
          onRetry={() => void refetchRuns()}
          sortField={sortField}
          sortOrder={sortOrder}
          onSort={handleSort}
        />
        <MoleculeLookupNotice show={!isRunsLoading && !error && Boolean(moleculeLookupError)} />
        <RunsPagination
          show={!isRunsLoading && !error && totalRuns > 0}
          page={page}
          totalPages={totalPages}
          onPageChange={goToPage}
        />
      </CardContent>
      <RunsSelectionDialogs
        confirmingBulkAction={confirmingBulkAction}
        setConfirmingBulkAction={setConfirmingBulkAction}
        pausableCount={pausableSelectedRuns.length}
        restartableCount={restartableSelectedRuns.length}
        cancellableCount={cancellableSelectedRuns.length}
        selectedRunsCount={selectedRuns.length}
        deleteSelectionOpen={deleteSelectionOpen}
        setDeleteSelectionOpen={setDeleteSelectionOpen}
        deleteProgress={deleteProgress}
        pendingBulkAction={pendingBulkAction}
        selectedCount={bulkSelection.selectedCount}
        onConfirmPause={() =>
          handleSelectedRunsAction("pause", pausableSelectedRuns, selectedRuns, bulkSelection)
        }
        onConfirmRestart={() =>
          handleSelectedRunsAction("restart", restartableSelectedRuns, selectedRuns, bulkSelection)
        }
        onConfirmCancel={() =>
          handleSelectedRunsAction("cancel", cancellableSelectedRuns, selectedRuns, bulkSelection)
        }
        onDeleteSelection={() => deleteSelectedRuns(selectedRuns, bulkSelection)}
      />
    </Card>
  );
}
