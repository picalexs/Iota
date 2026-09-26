import { Checkbox } from "@/components/ui/checkbox";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import type {
  BenchmarkDeleteProgress,
  BenchmarkExecutableAction,
} from "@/features/benchmarks/state/history-actions";
import type { BenchmarkHistoryRun } from "@/features/benchmarks/state/history";
import { runAsyncPageAction } from "./benchmark-history-toolbar";

type ConfirmableBenchmarkAction = Extract<
  BenchmarkExecutableAction,
  "pause" | "restart" | "cancel"
>;

type ConfirmingRowBenchmarkAction = {
  readonly action: ConfirmableBenchmarkAction;
  readonly run: BenchmarkHistoryRun;
};

function getDeleteBenchmarksTitle(selectedCount: number): string {
  return selectedCount === 1
    ? "Delete selected benchmark?"
    : "Delete " + selectedCount + " selected benchmarks?";
}

function getDeleteBenchmarksStatus(progress: BenchmarkDeleteProgress | null): string | undefined {
  if (!progress) {
    return undefined;
  }

  return "Deleting " + progress.completed + " of " + progress.total + "...";
}

function getDeleteBenchmarksConfirmText(selectedCount: number): string {
  return selectedCount === 1 ? "Delete benchmark" : "Delete benchmarks";
}

function getBenchmarkActionDescription(
  action: ConfirmableBenchmarkAction,
  eligibleCount: number,
  skippedCount: number,
): string {
  const benchmarkLabel = eligibleCount === 1 ? "benchmark" : "benchmarks";
  const skippedLabel = skippedCount === 1 ? "benchmark is" : "benchmarks are";

  if (action === "pause") {
    return skippedCount > 0
      ? "This will pause " +
          eligibleCount +
          " selected " +
          benchmarkLabel +
          ". " +
          skippedCount +
          " selected " +
          skippedLabel +
          " not pausable and will be skipped."
      : "This will pause " +
          eligibleCount +
          " selected " +
          benchmarkLabel +
          ". IBM Runtime jobs already submitted will finish before the benchmark pauses.";
  }

  if (action === "restart") {
    return skippedCount > 0
      ? "This will restart " +
          eligibleCount +
          " selected " +
          benchmarkLabel +
          ". " +
          skippedCount +
          " selected " +
          skippedLabel +
          " not restartable and will be skipped."
      : "This will create new runs for each paused benchmark row using the stored configuration.";
  }

  return skippedCount > 0
    ? "This will cancel " +
        eligibleCount +
        " selected " +
        benchmarkLabel +
        ". " +
        skippedCount +
        " selected " +
        skippedLabel +
        " already terminal and will be skipped."
    : "This will cancel the active and queued rows inside " +
        eligibleCount +
        " selected " +
        benchmarkLabel +
        ".";
}

function getBenchmarkActionCancelText(action: ConfirmableBenchmarkAction): string {
  if (action === "pause") {
    return "Keep running";
  }
  if (action === "restart") {
    return "Keep paused";
  }
  return "Keep active";
}

type BenchmarkActionConfirmDialogProps = {
  readonly action: ConfirmableBenchmarkAction;
  readonly confirmingBulkAction: ConfirmableBenchmarkAction | null;
  readonly confirmingRowAction: ConfirmingRowBenchmarkAction | null;
  readonly eligibleCount: number;
  readonly skippedCount: number;
  readonly loading: boolean;
  readonly disabled: boolean;
  readonly onClose: () => void;
  readonly onConfirmBulk: () => void | Promise<void>;
  readonly onConfirmRow: (run: BenchmarkHistoryRun) => void | Promise<void>;
};

export function BenchmarkActionConfirmDialog({
  action,
  confirmingBulkAction,
  confirmingRowAction,
  eligibleCount,
  skippedCount,
  loading,
  disabled,
  onClose,
  onConfirmBulk,
  onConfirmRow,
}: BenchmarkActionConfirmDialogProps) {
  const isRowAction = confirmingRowAction?.action === action;
  const isOpen = confirmingBulkAction === action || isRowAction;
  const actionLabel = action.charAt(0).toUpperCase() + action.slice(1);

  return (
    <ConfirmDialog
      open={isOpen}
      onOpenChange={(open) => {
        if (!open) {
          onClose();
        }
      }}
      title={isRowAction ? actionLabel + " benchmark?" : actionLabel + " selected benchmarks?"}
      description={getBenchmarkActionDescription(
        action,
        isRowAction ? 1 : eligibleCount,
        isRowAction ? 0 : skippedCount,
      )}
      confirmText={isRowAction ? actionLabel + " benchmark" : actionLabel + " benchmarks"}
      cancelText={getBenchmarkActionCancelText(action)}
      variant={action === "cancel" ? "destructive" : "default"}
      onConfirm={() => {
        if (isRowAction && confirmingRowAction) {
          runAsyncPageAction(() => onConfirmRow(confirmingRowAction.run));
          return;
        }
        runAsyncPageAction(onConfirmBulk);
      }}
      loading={loading}
      disabled={isRowAction ? false : disabled}
    />
  );
}

type BenchmarkDeleteSelectionDialogProps = {
  readonly open: boolean;
  readonly selectedCount: number;
  readonly associatedRunCount: number;
  readonly deleteAssociatedRuns: boolean;
  readonly deleteProgress: BenchmarkDeleteProgress | null;
  readonly deletingSelection: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly onDeleteAssociatedRunsChange: (value: boolean) => void;
  readonly onConfirm: () => void | Promise<void>;
};

export function BenchmarkDeleteSelectionDialog({
  open,
  selectedCount,
  associatedRunCount,
  deleteAssociatedRuns,
  deleteProgress,
  deletingSelection,
  onOpenChange,
  onDeleteAssociatedRunsChange,
  onConfirm,
}: BenchmarkDeleteSelectionDialogProps) {
  return (
    <ConfirmDialog
      open={open}
      onOpenChange={onOpenChange}
      title={getDeleteBenchmarksTitle(selectedCount)}
      description={
        associatedRunCount > 0
          ? "This permanently removes the selected saved benchmark snapshots. You can also remove their associated runs from the runs history."
          : "This permanently removes the selected saved benchmark snapshots."
      }
      status={getDeleteBenchmarksStatus(deleteProgress)}
      confirmText={getDeleteBenchmarksConfirmText(selectedCount)}
      cancelText="Keep benchmarks"
      variant="destructive"
      onConfirm={onConfirm}
      loading={deletingSelection}
      disabled={selectedCount === 0}
    >
      {associatedRunCount > 0 ? (
        <label className="flex items-start gap-3 rounded-md border p-3 text-sm">
          <Checkbox
            aria-label="Also delete associated runs"
            checked={deleteAssociatedRuns}
            onCheckedChange={(checked) => onDeleteAssociatedRunsChange(checked === true)}
          />
          <span>Also delete {associatedRunCount} associated run(s) from the runs history.</span>
        </label>
      ) : null}
    </ConfirmDialog>
  );
}
