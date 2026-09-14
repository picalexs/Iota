import { Checkbox } from "@/components/ui/checkbox";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import type { MoleculeDeleteProgress } from "./molecule-bulk-delete";

interface MoleculeDeleteDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onClose: () => void;
  selectedCount: number;
  selectedAssociatedRunCount: number;
  deleteAssociatedRuns: boolean;
  onDeleteAssociatedRunsChange: (checked: boolean) => void;
  deleteProgress: MoleculeDeleteProgress | null;
  onConfirm: () => void | Promise<void>;
  loading: boolean;
}

function getDeleteDialogTitle(selectedCount: number): string {
  return selectedCount === 1
    ? "Delete selected molecule?"
    : `Delete ${selectedCount} selected molecules?`;
}

function getDeleteDialogStatus(progress: MoleculeDeleteProgress | null): string | undefined {
  if (!progress) {
    return undefined;
  }

  return `Deleting ${progress.completed} of ${progress.total}...`;
}

function getDeleteDialogConfirmText(selectedCount: number): string {
  return selectedCount === 1 ? "Delete molecule" : "Delete molecules";
}

export function MoleculeDeleteDialog({
  open,
  onOpenChange,
  onClose,
  selectedCount,
  selectedAssociatedRunCount,
  deleteAssociatedRuns,
  onDeleteAssociatedRunsChange,
  deleteProgress,
  onConfirm,
  loading,
}: MoleculeDeleteDialogProps) {
  function handleOpenChange(nextOpen: boolean) {
    onOpenChange(nextOpen);
    if (!nextOpen) {
      onClose();
    }
  }

  return (
    <ConfirmDialog
      open={open}
      onOpenChange={handleOpenChange}
      title={getDeleteDialogTitle(selectedCount)}
      description={
        selectedAssociatedRunCount > 0
          ? "This permanently removes the selected molecules from the library. You can also delete their associated runs from the runs history."
          : "This permanently removes the selected molecules from the library."
      }
      status={getDeleteDialogStatus(deleteProgress)}
      confirmText={getDeleteDialogConfirmText(selectedCount)}
      cancelText="Keep molecules"
      variant="destructive"
      onConfirm={onConfirm}
      loading={loading}
      disabled={selectedCount === 0}
    >
      {selectedAssociatedRunCount > 0 ? (
        <label className="flex items-start gap-3 rounded-md border p-3 text-sm">
          <Checkbox
            aria-label="Also delete associated runs"
            checked={deleteAssociatedRuns}
            onCheckedChange={(checked) => onDeleteAssociatedRunsChange(checked === true)}
          />
          <span>
            Also delete {selectedAssociatedRunCount} associated run(s) from the runs history.
          </span>
        </label>
      ) : null}
    </ConfirmDialog>
  );
}
