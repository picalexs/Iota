import { Link } from "@tanstack/react-router";
import { ListChecks, Pause, Play, Plus, RotateCcw, Trash2, XCircle } from "lucide-react";
import {
  BulkSelectionBar,
  type BulkSelectionAction,
} from "@/components/bulk-actions/bulk-selection-bar";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import {
  describeRunSelectionAction,
  getDeleteRunsConfirmText,
  getDeleteRunsDescription,
  getDeleteRunsStatus,
  getDeleteRunsTitle,
  getRunsEditButtonLabel,
  getSelectionActionLabel,
  type BulkRunAction,
  type ConfirmableRunAction,
  type RunDeleteProgress,
} from "../state/selection-actions";

export function RunsToolbarActions({
  isEditing,
  disabled,
  onToggleEdit,
}: Readonly<{
  isEditing: boolean;
  disabled: boolean;
  onToggleEdit: () => void;
}>) {
  return (
    <div className="flex items-center gap-2">
      <Button
        type="button"
        variant={isEditing ? "secondary" : "outline"}
        size="sm"
        onClick={onToggleEdit}
        aria-pressed={isEditing}
        disabled={disabled}
      >
        <ListChecks className="size-3.5" />
        {getRunsEditButtonLabel(isEditing)}
      </Button>
      <Button asChild className="h-9 shrink-0">
        <Link to="/runs/new">
          <Plus className="size-4" />
          New Run
        </Link>
      </Button>
    </div>
  );
}

export interface RunsBulkSelectionControlsProps {
  readonly isEditing: boolean;
  readonly runsCount: number;
  readonly selectedCount: number;
  readonly allVisibleSelected: boolean;
  readonly someVisibleSelected: boolean;
  readonly bulkActionError: string | null;
  readonly pausableCount: number;
  readonly resumableCount: number;
  readonly restartableCount: number;
  readonly cancellableCount: number;
  readonly actionPending: boolean;
  readonly rowActionInProgress: boolean;
  readonly onToggleSelectAllVisible: (selected: boolean) => void;
  readonly onClearSelection: () => void;
  readonly onConfirmPause: () => void;
  readonly onResume: () => void | Promise<void>;
  readonly onConfirmRestart: () => void;
  readonly onOpenDelete: () => void;
  readonly onConfirmCancel: () => void;
}

export function RunsBulkSelectionControls({
  isEditing,
  runsCount,
  selectedCount,
  allVisibleSelected,
  someVisibleSelected,
  bulkActionError,
  pausableCount,
  resumableCount,
  restartableCount,
  cancellableCount,
  actionPending,
  rowActionInProgress,
  onToggleSelectAllVisible,
  onClearSelection,
  onConfirmPause,
  onResume,
  onConfirmRestart,
  onOpenDelete,
  onConfirmCancel,
}: RunsBulkSelectionControlsProps) {
  if (!isEditing) {
    return null;
  }

  const actions: BulkSelectionAction[] = [
    {
      key: "pause",
      label: getSelectionActionLabel("Pause", pausableCount),
      icon: Pause,
      disabled: pausableCount === 0 || actionPending || rowActionInProgress,
      onClick: onConfirmPause,
    },
    {
      key: "resume",
      label: getSelectionActionLabel("Resume", resumableCount),
      icon: Play,
      disabled: resumableCount === 0 || actionPending || rowActionInProgress,
      onClick: onResume,
    },
    {
      key: "restart",
      label: getSelectionActionLabel("Restart", restartableCount),
      icon: RotateCcw,
      disabled: restartableCount === 0 || actionPending || rowActionInProgress,
      onClick: onConfirmRestart,
    },
    {
      key: "delete",
      label: getSelectionActionLabel("Delete", selectedCount),
      icon: Trash2,
      variant: "destructive",
      disabled: selectedCount === 0 || actionPending || rowActionInProgress,
      onClick: onOpenDelete,
    },
    {
      key: "cancel",
      label: getSelectionActionLabel("Stop", cancellableCount),
      icon: XCircle,
      variant: "destructive",
      disabled: cancellableCount === 0 || actionPending || rowActionInProgress,
      onClick: onConfirmCancel,
    },
  ];

  return (
    <BulkSelectionBar
      itemLabel="runs"
      totalVisibleCount={runsCount}
      selectedCount={selectedCount}
      allVisibleSelected={allVisibleSelected}
      someVisibleSelected={someVisibleSelected}
      onToggleSelectAllVisible={onToggleSelectAllVisible}
      onClearSelection={onClearSelection}
      actionError={bulkActionError}
      actions={actions}
    />
  );
}

export interface RunsSelectionDialogsProps {
  readonly confirmingBulkAction: ConfirmableRunAction | null;
  readonly setConfirmingBulkAction: (action: ConfirmableRunAction | null) => void;
  readonly pausableCount: number;
  readonly restartableCount: number;
  readonly cancellableCount: number;
  readonly selectedRunsCount: number;
  readonly deleteSelectionOpen: boolean;
  readonly setDeleteSelectionOpen: (open: boolean) => void;
  readonly deleteProgress: RunDeleteProgress | null;
  readonly pendingBulkAction: BulkRunAction;
  readonly selectedCount: number;
  readonly onConfirmPause: () => void | Promise<void>;
  readonly onConfirmRestart: () => void | Promise<void>;
  readonly onConfirmCancel: () => void | Promise<void>;
  readonly onDeleteSelection: () => void | Promise<void>;
}

export function RunsSelectionDialogs({
  confirmingBulkAction,
  setConfirmingBulkAction,
  pausableCount,
  restartableCount,
  cancellableCount,
  selectedRunsCount,
  deleteSelectionOpen,
  setDeleteSelectionOpen,
  deleteProgress,
  pendingBulkAction,
  selectedCount,
  onConfirmPause,
  onConfirmRestart,
  onConfirmCancel,
  onDeleteSelection,
}: RunsSelectionDialogsProps) {
  return (
    <>
      <ConfirmDialog
        open={confirmingBulkAction === "pause"}
        onOpenChange={(open) => setConfirmingBulkAction(open ? "pause" : null)}
        title="Pause selected runs?"
        description={describeRunSelectionAction(
          "pause",
          pausableCount,
          selectedRunsCount - pausableCount,
        )}
        confirmText="Pause selected"
        cancelText="Keep running"
        onConfirm={onConfirmPause}
        loading={pendingBulkAction === "pause"}
        disabled={pausableCount === 0}
      />
      <ConfirmDialog
        open={confirmingBulkAction === "restart"}
        onOpenChange={(open) => setConfirmingBulkAction(open ? "restart" : null)}
        title="Restart selected runs?"
        description={describeRunSelectionAction(
          "restart",
          restartableCount,
          selectedRunsCount - restartableCount,
        )}
        confirmText="Restart selected"
        cancelText="Keep current runs"
        onConfirm={onConfirmRestart}
        loading={pendingBulkAction === "restart"}
        disabled={restartableCount === 0}
      />
      <ConfirmDialog
        open={confirmingBulkAction === "cancel"}
        onOpenChange={(open) => setConfirmingBulkAction(open ? "cancel" : null)}
        title="Cancel selected runs?"
        description={describeRunSelectionAction(
          "cancel",
          cancellableCount,
          selectedRunsCount - cancellableCount,
        )}
        confirmText="Stop selected"
        cancelText="Keep runs"
        variant="destructive"
        onConfirm={onConfirmCancel}
        loading={pendingBulkAction === "cancel"}
        disabled={cancellableCount === 0}
      />
      <ConfirmDialog
        open={deleteSelectionOpen}
        onOpenChange={(open) => setDeleteSelectionOpen(open)}
        title={getDeleteRunsTitle(selectedCount)}
        description={getDeleteRunsDescription(cancellableCount)}
        status={getDeleteRunsStatus(deleteProgress)}
        confirmText={getDeleteRunsConfirmText(selectedCount)}
        cancelText="Keep runs"
        variant="destructive"
        onConfirm={onDeleteSelection}
        loading={pendingBulkAction === "delete"}
        disabled={selectedCount === 0}
      />
    </>
  );
}
