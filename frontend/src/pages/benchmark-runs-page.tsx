import { PageErrorState } from "@/components/ui/page-error-state";
import { runAsyncPageAction } from "./benchmark/benchmark-history-toolbar";
import { BenchmarkRunsContent } from "./benchmark/benchmark-history-content";
import { BenchmarkHistoryActionDialogs } from "./benchmark/benchmark-history-action-dialogs";
import { useBenchmarkHistoryController } from "./benchmark/use-benchmark-history-controller";

export function BenchmarkRunsPage() {
  const {
    savedBenchmarkRuns,
    filteredAndSortedRuns,
    loading,
    error,
    refetch,
    sortField,
    sortOrder,
    statusFilter,
    backendFilter,
    hasActiveFilters,
    creating,
    createError,
    actionPending,
    isEditing,
    selectedRunIds,
    selectedCount,
    allVisibleSelected,
    someVisibleSelected,
    bulkActionError,
    pausableCount,
    resumableCount,
    restartableCount,
    cancellableCount,
    confirmingBulkAction,
    confirmingRowAction,
    pendingBulkAction,
    pendingRowAction,
    selectedRuns,
    associatedRunCount,
    deleteSelectionOpen,
    deleteAssociatedRuns,
    deleteProgress,
    deletingSelection,
    clearFilters,
    updateSort,
    setStatusFilter,
    setBackendFilter,
    createNewBenchmark,
    toggleEditing,
    loadBenchmark,
    deleteSavedBenchmark,
    requestRowAction,
    toggleBenchmarkSelection,
    toggleSelectAllVisible,
    clearSelection,
    confirmPauseSelection,
    resumeSelection,
    confirmRestartSelection,
    confirmCancelSelection,
    openDeleteSelection,
    closeActionDialogs,
    confirmBulkAction,
    confirmRowAction,
    handleDeleteSelectionOpenChange,
    setDeleteAssociatedRuns,
    deleteSelectedBenchmarks,
  } = useBenchmarkHistoryController();

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-8">
      <div className="flex min-w-0 flex-col gap-1">
        <h1 className="text-2xl font-bold tracking-tight">Benchmark Runs</h1>
        <p className="text-sm text-muted-foreground">
          Review saved benchmark batches, filter the history, and open their dashboards.
        </p>
      </div>

      {createError ? (
        <PageErrorState
          title="We couldn't create the benchmark"
          description="The draft was not saved. Try again once the backend is reachable."
          detail={createError}
          onReload={null}
          className="rounded-xl p-4"
        />
      ) : null}

      {!isEditing && bulkActionError ? (
        <div
          role="alert"
          className="rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive"
        >
          {bulkActionError}
        </div>
      ) : null}

      <BenchmarkRunsContent
        savedBenchmarkRuns={savedBenchmarkRuns}
        filteredAndSortedRuns={filteredAndSortedRuns}
        loading={loading}
        error={error}
        refetch={() => runAsyncPageAction(refetch)}
        sortField={sortField}
        sortOrder={sortOrder}
        statusFilter={statusFilter}
        backendFilter={backendFilter}
        hasActiveFilters={hasActiveFilters}
        creating={creating}
        actionPending={actionPending}
        isEditing={isEditing}
        selectedRunIds={selectedRunIds}
        selectedCount={selectedCount}
        allVisibleSelected={allVisibleSelected}
        someVisibleSelected={someVisibleSelected}
        bulkActionError={bulkActionError}
        pausableCount={pausableCount}
        resumableCount={resumableCount}
        restartableCount={restartableCount}
        cancellableCount={cancellableCount}
        clearFilters={clearFilters}
        onUpdateSort={updateSort}
        onSelectStatus={setStatusFilter}
        onSelectBackend={setBackendFilter}
        onCreateNewBenchmark={createNewBenchmark}
        onToggleEdit={toggleEditing}
        onLoadBenchmark={loadBenchmark}
        onDeleteBenchmark={deleteSavedBenchmark}
        onRequestRowAction={requestRowAction}
        onToggleBenchmarkSelection={toggleBenchmarkSelection}
        onToggleSelectAllVisible={toggleSelectAllVisible}
        onClearSelection={clearSelection}
        onConfirmPauseSelection={confirmPauseSelection}
        onResumeSelection={resumeSelection}
        onConfirmRestartSelection={confirmRestartSelection}
        onConfirmCancelSelection={confirmCancelSelection}
        onOpenDeleteSelection={openDeleteSelection}
      />

      <BenchmarkHistoryActionDialogs
        confirmingBulkAction={confirmingBulkAction}
        confirmingRowAction={confirmingRowAction}
        pendingBulkAction={pendingBulkAction}
        pendingRowAction={pendingRowAction}
        pausableCount={pausableCount}
        restartableCount={restartableCount}
        cancellableCount={cancellableCount}
        selectedCount={selectedRuns.length}
        associatedRunCount={associatedRunCount}
        deleteSelectionOpen={deleteSelectionOpen}
        deleteAssociatedRuns={deleteAssociatedRuns}
        deleteProgress={deleteProgress}
        deletingSelection={deletingSelection}
        onCloseAction={closeActionDialogs}
        onConfirmBulkAction={confirmBulkAction}
        onConfirmRowAction={confirmRowAction}
        onDeleteSelectionOpenChange={handleDeleteSelectionOpenChange}
        onDeleteAssociatedRunsChange={setDeleteAssociatedRuns}
        onConfirmDelete={deleteSelectedBenchmarks}
      />
    </div>
  );
}

export default BenchmarkRunsPage;
