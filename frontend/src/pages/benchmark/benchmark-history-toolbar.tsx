import { ListChecks, Pause, Play, Plus, RotateCcw, Trash2, XCircle } from "lucide-react";
import { ActiveFilterChip, ClearFiltersButton } from "@/components/filters/filter-primitives";
import { BulkSelectionBar } from "@/components/bulk-actions/bulk-selection-bar";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import {
  BENCHMARK_HISTORY_BACKEND_LABELS,
  BENCHMARK_HISTORY_STATUS_LABELS,
} from "@/features/benchmarks/state/history";
import {
  BackendFilter,
  StatusFilter,
  type BenchmarkBackendFilter,
  type BenchmarkStatusFilter,
} from "./benchmark-history-filters";

export function runAsyncPageAction(action: () => unknown | Promise<unknown>) {
  Promise.resolve(action()).catch(() => undefined);
}

function getEditBenchmarksLabel(isEditing: boolean): string {
  return isEditing ? "Done Editing" : "Edit";
}

function getCreateBenchmarkIcon(creating: boolean) {
  return creating ? <Spinner /> : <Plus className="size-4" />;
}

function getSelectionActionLabel(label: string, count: number): string {
  return count > 0 ? `${label} (${count})` : label;
}

export type BenchmarkRunsToolbarProps = {
  readonly savedBenchmarkRunsCount: number;
  readonly statusFilter: BenchmarkStatusFilter;
  readonly backendFilter: BenchmarkBackendFilter;
  readonly hasActiveFilters: boolean;
  readonly creating: boolean;
  readonly actionPending: boolean;
  readonly isEditing: boolean;
  readonly clearFilters: () => void;
  readonly onSelectStatus: (status: BenchmarkStatusFilter) => void;
  readonly onSelectBackend: (backend: BenchmarkBackendFilter) => void;
  readonly onCreateNewBenchmark: () => void | Promise<void>;
  readonly onToggleEdit: () => void;
};

export function BenchmarkRunsToolbar({
  savedBenchmarkRunsCount,
  statusFilter,
  backendFilter,
  hasActiveFilters,
  creating,
  actionPending,
  isEditing,
  clearFilters,
  onSelectStatus,
  onSelectBackend,
  onCreateNewBenchmark,
  onToggleEdit,
}: BenchmarkRunsToolbarProps) {
  if (savedBenchmarkRunsCount === 0) {
    return null;
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-2">
          <StatusFilter selectedStatus={statusFilter} onSelectStatus={onSelectStatus} />
          <BackendFilter selectedBackend={backendFilter} onSelectBackend={onSelectBackend} />
          {hasActiveFilters ? (
            <ClearFiltersButton
              label="Clear filters"
              ariaLabel="Clear benchmark filters"
              className="px-2"
              onClear={clearFilters}
            />
          ) : null}
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          <Button
            type="button"
            variant={isEditing ? "secondary" : "outline"}
            size="sm"
            className="h-9 shrink-0"
            disabled={creating || actionPending}
            onClick={onToggleEdit}
            aria-pressed={isEditing}
          >
            <ListChecks className="size-3.5" />
            {getEditBenchmarksLabel(isEditing)}
          </Button>
          <Button
            className="h-9 shrink-0"
            disabled={creating || actionPending}
            onClick={() => {
              runAsyncPageAction(onCreateNewBenchmark);
            }}
          >
            {getCreateBenchmarkIcon(creating)}
            New Benchmark
          </Button>
        </div>
      </div>
      {hasActiveFilters ? (
        <div className="flex flex-wrap gap-2">
          {statusFilter !== "all" ? (
            <ActiveFilterChip
              label={`Status: ${BENCHMARK_HISTORY_STATUS_LABELS[statusFilter]}`}
              ariaLabel="Remove status filter"
              onRemove={() => onSelectStatus("all")}
            />
          ) : null}
          {backendFilter !== "all" ? (
            <ActiveFilterChip
              label={`Backend: ${BENCHMARK_HISTORY_BACKEND_LABELS[backendFilter]}`}
              ariaLabel="Remove backend filter"
              onRemove={() => onSelectBackend("all")}
            />
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export type BenchmarkRunsSelectionBarProps = {
  readonly isEditing: boolean;
  readonly filteredRunsCount: number;
  readonly selectedCount: number;
  readonly allVisibleSelected: boolean;
  readonly someVisibleSelected: boolean;
  readonly bulkActionError: string | null;
  readonly pausableCount: number;
  readonly resumableCount: number;
  readonly restartableCount: number;
  readonly cancellableCount: number;
  readonly actionPending: boolean;
  readonly onToggleSelectAllVisible: (selected: boolean) => void;
  readonly onClearSelection: () => void;
  readonly onConfirmPauseSelection: () => void;
  readonly onResumeSelection: () => void | Promise<void>;
  readonly onConfirmRestartSelection: () => void;
  readonly onConfirmCancelSelection: () => void;
  readonly onOpenDeleteSelection: () => void;
};

export function BenchmarkRunsSelectionBar({
  isEditing,
  filteredRunsCount,
  selectedCount,
  allVisibleSelected,
  someVisibleSelected,
  bulkActionError,
  pausableCount,
  resumableCount,
  restartableCount,
  cancellableCount,
  actionPending,
  onToggleSelectAllVisible,
  onClearSelection,
  onConfirmPauseSelection,
  onResumeSelection,
  onConfirmRestartSelection,
  onConfirmCancelSelection,
  onOpenDeleteSelection,
}: BenchmarkRunsSelectionBarProps) {
  if (!isEditing) {
    return null;
  }

  return (
    <BulkSelectionBar
      itemLabel="benchmarks"
      totalVisibleCount={filteredRunsCount}
      selectedCount={selectedCount}
      allVisibleSelected={allVisibleSelected}
      someVisibleSelected={someVisibleSelected}
      onToggleSelectAllVisible={onToggleSelectAllVisible}
      onClearSelection={onClearSelection}
      actionError={bulkActionError}
      actions={[
        {
          key: "pause",
          label: getSelectionActionLabel("Pause", pausableCount),
          icon: Pause,
          disabled: pausableCount === 0 || actionPending,
          onClick: onConfirmPauseSelection,
        },
        {
          key: "resume",
          label: getSelectionActionLabel("Resume", resumableCount),
          icon: Play,
          disabled: resumableCount === 0 || actionPending,
          onClick: () => {
            runAsyncPageAction(onResumeSelection);
          },
        },
        {
          key: "restart",
          label: getSelectionActionLabel("Restart", restartableCount),
          icon: RotateCcw,
          disabled: restartableCount === 0 || actionPending,
          onClick: onConfirmRestartSelection,
        },
        {
          key: "cancel",
          label: getSelectionActionLabel("Cancel", cancellableCount),
          icon: XCircle,
          disabled: cancellableCount === 0 || actionPending,
          onClick: onConfirmCancelSelection,
        },
        {
          key: "delete",
          label: getSelectionActionLabel("Delete", selectedCount),
          icon: Trash2,
          variant: "destructive",
          disabled: selectedCount === 0 || actionPending,
          onClick: onOpenDeleteSelection,
        },
      ]}
    />
  );
}
