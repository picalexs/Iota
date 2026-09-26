import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageErrorState, getErrorPresentation } from "@/components/ui/page-error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { BenchmarkSavedRunsList } from "./benchmark-saved-runs-list";
import type { BenchmarkBackendFilter, BenchmarkStatusFilter } from "./benchmark-history-filters";
import {
  BenchmarkRunsSelectionBar,
  BenchmarkRunsToolbar,
  runAsyncPageAction,
} from "./benchmark-history-toolbar";
import type { BenchmarkExecutableAction } from "@/features/benchmarks/state/history-actions";
import type { BenchmarkSortField, BenchmarkSortOrder } from "@/features/benchmarks/state/history";
import type { BenchmarkHistoryRun } from "@/features/benchmarks/state/history";

export type BenchmarkRunsContentProps = {
  readonly savedBenchmarkRuns: readonly BenchmarkHistoryRun[];
  readonly filteredAndSortedRuns: readonly BenchmarkHistoryRun[];
  readonly loading: boolean;
  readonly error: unknown;
  readonly refetch: () => void | Promise<void>;
  readonly sortField: BenchmarkSortField;
  readonly sortOrder: BenchmarkSortOrder;
  readonly statusFilter: BenchmarkStatusFilter;
  readonly backendFilter: BenchmarkBackendFilter;
  readonly hasActiveFilters: boolean;
  readonly creating: boolean;
  readonly actionPending: boolean;
  readonly isEditing: boolean;
  readonly selectedRunIds: ReadonlySet<string>;
  readonly selectedCount: number;
  readonly allVisibleSelected: boolean;
  readonly someVisibleSelected: boolean;
  readonly bulkActionError: string | null;
  readonly pausableCount: number;
  readonly resumableCount: number;
  readonly restartableCount: number;
  readonly cancellableCount: number;
  readonly page: number;
  readonly pageSize: number;
  readonly total: number;
  readonly canGoPrevious: boolean;
  readonly canGoNext: boolean;
  readonly clearFilters: () => void;
  readonly onUpdateSort: (field: BenchmarkSortField) => void;
  readonly onSelectStatus: (status: BenchmarkStatusFilter) => void;
  readonly onSelectBackend: (backend: BenchmarkBackendFilter) => void;
  readonly onCreateNewBenchmark: () => void | Promise<void>;
  readonly onToggleEdit: () => void;
  readonly onLoadBenchmark: (benchmarkId: string) => void | Promise<void>;
  readonly onDeleteBenchmark: (
    savedRunId: string,
    options: { deleteAssociatedRuns: boolean },
  ) => void | Promise<void>;
  readonly onRequestRowAction: (
    run: BenchmarkHistoryRun,
    action: BenchmarkExecutableAction,
  ) => void | Promise<void>;
  readonly onToggleBenchmarkSelection: (benchmarkId: string) => void;
  readonly onToggleSelectAllVisible: (selected: boolean) => void;
  readonly onClearSelection: () => void;
  readonly onConfirmPauseSelection: () => void;
  readonly onResumeSelection: () => void | Promise<void>;
  readonly onConfirmRestartSelection: () => void;
  readonly onConfirmCancelSelection: () => void;
  readonly onOpenDeleteSelection: () => void;
  readonly onGoPreviousPage: () => void;
  readonly onGoNextPage: () => void;
};

export function BenchmarkRunsContent({
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
  page,
  pageSize,
  total,
  canGoPrevious,
  canGoNext,
  clearFilters,
  onUpdateSort,
  onSelectStatus,
  onSelectBackend,
  onCreateNewBenchmark,
  onToggleEdit,
  onLoadBenchmark,
  onDeleteBenchmark,
  onRequestRowAction,
  onToggleBenchmarkSelection,
  onToggleSelectAllVisible,
  onClearSelection,
  onConfirmPauseSelection,
  onResumeSelection,
  onConfirmRestartSelection,
  onConfirmCancelSelection,
  onOpenDeleteSelection,
  onGoPreviousPage,
  onGoNextPage,
}: BenchmarkRunsContentProps) {
  if (loading) {
    return (
      <div className="rounded-lg border bg-card p-4">
        <Skeleton className="h-8 w-48" />
        <div className="mt-5 space-y-3">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      </div>
    );
  }

  if (error) {
    const presentation = getErrorPresentation(error, "the benchmark history");
    return (
      <PageErrorState
        title={presentation.title}
        description={presentation.description}
        detail={presentation.detail}
        onRetry={() => runAsyncPageAction(refetch)}
      />
    );
  }

  if (savedBenchmarkRuns.length > 0 && filteredAndSortedRuns.length === 0) {
    return (
      <PageErrorState
        title="No benchmarks match these filters"
        description="Try a different status or backend filter to bring saved benchmarks back into view."
        detail={null}
        onReload={null}
        actions={
          <Button type="button" variant="outline" size="sm" onClick={clearFilters}>
            Clear filters
          </Button>
        }
        className="rounded-xl p-6"
      />
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <BenchmarkSavedRunsList
        savedBenchmarkRuns={filteredAndSortedRuns}
        selectedSavedBenchmarkId={null}
        sortField={sortField}
        sortOrder={sortOrder}
        toolbarContent={
          <BenchmarkRunsToolbar
            savedBenchmarkRunsCount={savedBenchmarkRuns.length}
            statusFilter={statusFilter}
            backendFilter={backendFilter}
            hasActiveFilters={hasActiveFilters}
            creating={creating}
            actionPending={actionPending}
            isEditing={isEditing}
            clearFilters={clearFilters}
            onSelectStatus={onSelectStatus}
            onSelectBackend={onSelectBackend}
            onCreateNewBenchmark={onCreateNewBenchmark}
            onToggleEdit={onToggleEdit}
          />
        }
        selectionContent={
          <BenchmarkRunsSelectionBar
            isEditing={isEditing}
            filteredRunsCount={filteredAndSortedRuns.length}
            selectedCount={selectedCount}
            allVisibleSelected={allVisibleSelected}
            someVisibleSelected={someVisibleSelected}
            bulkActionError={bulkActionError}
            pausableCount={pausableCount}
            resumableCount={resumableCount}
            restartableCount={restartableCount}
            cancellableCount={cancellableCount}
            actionPending={actionPending}
            onToggleSelectAllVisible={onToggleSelectAllVisible}
            onClearSelection={onClearSelection}
            onConfirmPauseSelection={onConfirmPauseSelection}
            onResumeSelection={onResumeSelection}
            onConfirmRestartSelection={onConfirmRestartSelection}
            onConfirmCancelSelection={onConfirmCancelSelection}
            onOpenDeleteSelection={onOpenDeleteSelection}
          />
        }
        selectionMode={isEditing}
        selectedRunIds={selectedRunIds}
        disabled={creating || actionPending}
        onCreate={onCreateNewBenchmark}
        onLoad={onLoadBenchmark}
        onDelete={onDeleteBenchmark}
        onRunAction={onRequestRowAction}
        onToggleSelected={onToggleBenchmarkSelection}
        onSort={onUpdateSort}
      />
      {total > pageSize ? (
        <div className="flex items-center justify-between px-1 text-sm text-muted-foreground">
          <span>
            Page {page + 1} of {Math.ceil(total / pageSize)} · {total} benchmarks
          </span>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              aria-label="Previous page"
              disabled={!canGoPrevious || loading}
              onClick={onGoPreviousPage}
            >
              <ChevronLeft className="size-4" />
              Previous
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              aria-label="Next page"
              disabled={!canGoNext || loading}
              onClick={onGoNextPage}
            >
              Next
              <ChevronRight className="size-4" />
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
