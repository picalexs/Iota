import type {
  BenchmarkDeleteProgress,
  BenchmarkExecutableAction,
} from "@/features/benchmarks/state/history-actions";
import {
  BenchmarkActionConfirmDialog,
  BenchmarkDeleteSelectionDialog,
} from "./benchmark-history-dialogs";
import type { BenchmarkHistoryRun } from "@/features/benchmarks/state/history";

export type BenchmarkBulkAction = "pause" | "resume" | "restart" | "cancel" | "delete" | null;
export type BenchmarkConfirmableAction = Extract<
  BenchmarkExecutableAction,
  "pause" | "restart" | "cancel"
>;

export type BenchmarkConfirmingRowAction = {
  readonly action: BenchmarkConfirmableAction;
  readonly run: BenchmarkHistoryRun;
};

type BenchmarkHistoryActionDialogsProps = Readonly<{
  confirmingBulkAction: BenchmarkConfirmableAction | null;
  confirmingRowAction: BenchmarkConfirmingRowAction | null;
  pendingBulkAction: BenchmarkBulkAction;
  pendingRowAction: { readonly runId: string; readonly action: BenchmarkExecutableAction } | null;
  pausableCount: number;
  restartableCount: number;
  cancellableCount: number;
  selectedCount: number;
  associatedRunCount: number;
  deleteSelectionOpen: boolean;
  deleteAssociatedRuns: boolean;
  deleteProgress: BenchmarkDeleteProgress | null;
  deletingSelection: boolean;
  onCloseAction: () => void;
  onConfirmBulkAction: (action: BenchmarkConfirmableAction) => void;
  onConfirmRowAction: (run: BenchmarkHistoryRun, action: BenchmarkConfirmableAction) => void;
  onDeleteSelectionOpenChange: (open: boolean) => void;
  onDeleteAssociatedRunsChange: (value: boolean) => void;
  onConfirmDelete: () => void | Promise<void>;
}>;

export function BenchmarkHistoryActionDialogs({
  confirmingBulkAction,
  confirmingRowAction,
  pendingBulkAction,
  pendingRowAction,
  pausableCount,
  restartableCount,
  cancellableCount,
  selectedCount,
  associatedRunCount,
  deleteSelectionOpen,
  deleteAssociatedRuns,
  deleteProgress,
  deletingSelection,
  onCloseAction,
  onConfirmBulkAction,
  onConfirmRowAction,
  onDeleteSelectionOpenChange,
  onDeleteAssociatedRunsChange,
  onConfirmDelete,
}: BenchmarkHistoryActionDialogsProps) {
  return (
    <>
      <BenchmarkActionConfirmDialog
        action="pause"
        confirmingBulkAction={confirmingBulkAction}
        confirmingRowAction={confirmingRowAction}
        eligibleCount={pausableCount}
        skippedCount={selectedCount - pausableCount}
        loading={pendingBulkAction === "pause" || pendingRowAction?.action === "pause"}
        disabled={pausableCount === 0}
        onClose={onCloseAction}
        onConfirmBulk={() => onConfirmBulkAction("pause")}
        onConfirmRow={(run) => onConfirmRowAction(run, "pause")}
      />

      <BenchmarkActionConfirmDialog
        action="restart"
        confirmingBulkAction={confirmingBulkAction}
        confirmingRowAction={confirmingRowAction}
        eligibleCount={restartableCount}
        skippedCount={selectedCount - restartableCount}
        loading={pendingBulkAction === "restart" || pendingRowAction?.action === "restart"}
        disabled={restartableCount === 0}
        onClose={onCloseAction}
        onConfirmBulk={() => onConfirmBulkAction("restart")}
        onConfirmRow={(run) => onConfirmRowAction(run, "restart")}
      />

      <BenchmarkActionConfirmDialog
        action="cancel"
        confirmingBulkAction={confirmingBulkAction}
        confirmingRowAction={confirmingRowAction}
        eligibleCount={cancellableCount}
        skippedCount={selectedCount - cancellableCount}
        loading={pendingBulkAction === "cancel" || pendingRowAction?.action === "cancel"}
        disabled={cancellableCount === 0}
        onClose={onCloseAction}
        onConfirmBulk={() => onConfirmBulkAction("cancel")}
        onConfirmRow={(run) => onConfirmRowAction(run, "cancel")}
      />

      <BenchmarkDeleteSelectionDialog
        open={deleteSelectionOpen}
        selectedCount={selectedCount}
        associatedRunCount={associatedRunCount}
        deleteAssociatedRuns={deleteAssociatedRuns}
        deleteProgress={deleteProgress}
        deletingSelection={deletingSelection}
        onOpenChange={onDeleteSelectionOpenChange}
        onDeleteAssociatedRunsChange={onDeleteAssociatedRunsChange}
        onConfirm={onConfirmDelete}
      />
    </>
  );
}
