import { useState, type KeyboardEvent, type MouseEvent } from "react";
import { MoreHorizontal, Pause, Play, RotateCcw, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  isCancellableBenchmarkEntry,
  isPausableBenchmarkEntry,
  isRestartableBenchmarkEntry,
  isResumableBenchmarkEntry,
} from "@/features/benchmarks/state/selectors";
import type { BenchmarkEntry } from "./benchmark-utils";
import type { BenchmarkResultsRowAction } from "./benchmark-results-row-actions";

type ConfirmableAction = Exclude<BenchmarkResultsRowAction, "resume">;

function stopRowInteraction(event: MouseEvent<HTMLElement> | KeyboardEvent<HTMLElement>) {
  event.stopPropagation();
}

function actionLabel(action: ConfirmableAction): string {
  switch (action) {
    case "pause":
      return "Pause runs";
    case "restart":
      return "Restart runs";
    case "retry":
      return "Retry runs";
    case "cancel":
      return "Cancel runs";
  }
}

function actionDescription(action: ConfirmableAction, moleculeLabel: string): string {
  switch (action) {
    case "pause":
      return `Pause all pausable runs for ${moleculeLabel}.`;
    case "restart":
      return `Restart all restartable runs for ${moleculeLabel}.`;
    case "retry":
      return `Retry all failed runs for ${moleculeLabel}.`;
    case "cancel":
      return `Cancel all active runs for ${moleculeLabel}. This action cannot be undone.`;
  }
}

export function BenchmarkMoleculeActions({
  entries,
  moleculeLabel,
  pendingAction = null,
  onAction,
}: Readonly<{
  entries: readonly BenchmarkEntry[];
  moleculeLabel: string;
  pendingAction?: BenchmarkResultsRowAction | null;
  onAction: (
    entries: readonly BenchmarkEntry[],
    action: BenchmarkResultsRowAction,
  ) => void | Promise<void>;
}>) {
  const [open, setOpen] = useState(false);
  const [confirmingAction, setConfirmingAction] = useState<ConfirmableAction | null>(null);
  const canPause = entries.some(isPausableBenchmarkEntry);
  const canResume = entries.some(isResumableBenchmarkEntry);
  const canRestart = entries.some(isRestartableBenchmarkEntry);
  const canRetry = entries.some((entry) => entry.status === "failed");
  const canCancel = entries.some(isCancellableBenchmarkEntry);
  const hasPendingAction = pendingAction !== null;

  if (!canPause && !canResume && !canRestart && !canRetry && !canCancel) {
    return null;
  }

  const runAction = (action: BenchmarkResultsRowAction) => {
    setOpen(false);
    void Promise.resolve(onAction(entries, action)).catch(() => undefined);
  };

  const openConfirmation = (action: ConfirmableAction) => {
    setOpen(false);
    setConfirmingAction(action);
  };

  return (
    <>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="size-8 text-muted-foreground hover:text-foreground"
            aria-label={`Molecule actions for ${moleculeLabel}`}
            onClick={stopRowInteraction}
            onKeyDown={stopRowInteraction}
          >
            <MoreHorizontal className="size-4" />
          </Button>
        </PopoverTrigger>
        <PopoverContent
          align="end"
          className="w-48 p-1"
          onClick={stopRowInteraction}
          onKeyDown={stopRowInteraction}
        >
          <div className="flex flex-col gap-1">
            {canPause ? (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-8 w-full justify-start px-2 text-xs"
                disabled={hasPendingAction}
                onClick={() => openConfirmation("pause")}
              >
                <Pause className="size-4" />
                {pendingAction === "pause" ? "Pausing..." : "Pause runs"}
              </Button>
            ) : null}
            {canResume ? (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-8 w-full justify-start px-2 text-xs"
                disabled={hasPendingAction}
                onClick={() => runAction("resume")}
              >
                <Play className="size-4" />
                {pendingAction === "resume" ? "Resuming..." : "Resume runs"}
              </Button>
            ) : null}
            {canRestart ? (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-8 w-full justify-start px-2 text-xs"
                disabled={hasPendingAction}
                onClick={() => openConfirmation("restart")}
              >
                <RotateCcw className="size-4" />
                {pendingAction === "restart" ? "Restarting..." : "Restart runs"}
              </Button>
            ) : null}
            {canRetry ? (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-8 w-full justify-start px-2 text-xs"
                disabled={hasPendingAction}
                onClick={() => openConfirmation("retry")}
              >
                <RotateCcw className="size-4" />
                {pendingAction === "retry" ? "Retrying..." : "Retry runs"}
              </Button>
            ) : null}
            {canCancel ? (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-8 w-full justify-start px-2 text-xs text-destructive hover:bg-destructive/10 hover:text-destructive"
                disabled={hasPendingAction}
                onClick={() => openConfirmation("cancel")}
              >
                <XCircle className="size-4" />
                {pendingAction === "cancel" ? "Cancelling..." : "Cancel runs"}
              </Button>
            ) : null}
          </div>
        </PopoverContent>
      </Popover>

      {confirmingAction ? (
        <ConfirmDialog
          open
          onOpenChange={(openValue) => setConfirmingAction(openValue ? confirmingAction : null)}
          title={`${actionLabel(confirmingAction)} for ${moleculeLabel}?`}
          description={actionDescription(confirmingAction, moleculeLabel)}
          confirmText={actionLabel(confirmingAction)}
          cancelText="Keep current runs"
          variant={confirmingAction === "cancel" ? "destructive" : "default"}
          onConfirm={() => runAction(confirmingAction)}
          loading={pendingAction === confirmingAction}
        />
      ) : null}
    </>
  );
}
