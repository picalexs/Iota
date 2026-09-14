import { Pause, Play, RotateCcw, XCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { StatusBadge } from "@/features/runs/components/status-badge";
import { Spinner } from "@/components/ui/spinner";
import type { RunResponse } from "@/types/run";

interface RunHeaderProps {
  readonly run: RunResponse;
  readonly activityLabel: string | null;
  readonly isCancellable: boolean;
  readonly isPausable: boolean;
  readonly isResumable: boolean;
  readonly isRestartable: boolean;
  readonly pendingAction: "cancel" | "pause" | "resume" | "restart" | null;
  readonly confirmingCancel: boolean;
  readonly confirmingPause: boolean;
  readonly confirmingRestart: boolean;
  readonly actionError: string | null;
  readonly onConfirmingCancelChange: (open: boolean) => void;
  readonly onConfirmingPauseChange: (open: boolean) => void;
  readonly onConfirmingRestartChange: (open: boolean) => void;
  readonly onCancelConfirm: () => void | Promise<void>;
  readonly onPauseConfirm: () => void | Promise<void>;
  readonly onResume: () => void | Promise<void>;
  readonly onRestartConfirm: () => void | Promise<void>;
}

export function RunHeader({
  run,
  activityLabel,
  isCancellable,
  isPausable,
  isResumable,
  isRestartable,
  pendingAction,
  confirmingCancel,
  confirmingPause,
  confirmingRestart,
  actionError,
  onConfirmingCancelChange,
  onConfirmingPauseChange,
  onConfirmingRestartChange,
  onCancelConfirm,
  onPauseConfirm,
  onResume,
  onRestartConfirm,
}: RunHeaderProps) {
  const actionPending = pendingAction !== null;
  const pauseInProgress = pendingAction === "pause" || run.status === "PAUSING";
  const showPauseAction = isPausable || run.status === "PAUSING";

  return (
    <div className="flex items-center justify-between gap-4 flex-wrap">
      <div className="flex min-w-0 flex-1 flex-wrap items-center gap-3">
        <StatusBadge status={run.status} metadata={run.metadata} />
        {activityLabel && (
          <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <span className="relative flex size-2" aria-hidden="true">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-yellow-400 opacity-75" />
              <span className="relative inline-flex rounded-full size-2 bg-yellow-500" />
            </span>
            {activityLabel}
          </span>
        )}
      </div>

      <div className="flex flex-col items-end gap-1.5 shrink-0">
        {actionError && (
          <p className="text-xs text-destructive" role="alert">
            {actionError}
          </p>
        )}
        <div className="flex flex-wrap justify-end gap-2">
          {showPauseAction && (
            <>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => onConfirmingPauseChange(true)}
                disabled={actionPending || pauseInProgress}
                aria-busy={pauseInProgress}
              >
                {pauseInProgress ? <Spinner /> : <Pause className="size-4" />}
                {pauseInProgress ? "Pausing" : "Pause Run"}
              </Button>
              <ConfirmDialog
                open={confirmingPause}
                onOpenChange={onConfirmingPauseChange}
                title="Pause this run?"
                description="IBM Runtime jobs already submitted will finish before the run pauses."
                confirmText="Pause"
                cancelText="Keep running"
                onConfirm={onPauseConfirm}
                loading={pendingAction === "pause"}
              />
            </>
          )}
          {isResumable && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onResume}
              disabled={actionPending}
            >
              <Play className="size-4" />
              {pendingAction === "resume" ? "Resuming" : "Resume Run"}
            </Button>
          )}
          {isRestartable && (
            <>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => onConfirmingRestartChange(true)}
                disabled={actionPending}
              >
                <RotateCcw className="size-4" />
                {pendingAction === "restart" ? "Restarting" : "Restart Run"}
              </Button>
              <ConfirmDialog
                open={confirmingRestart}
                onOpenChange={onConfirmingRestartChange}
                title="Restart this run?"
                description="A new run will be created from the stored configuration when the backend supports restart."
                confirmText="Restart"
                cancelText="Keep current run"
                onConfirm={onRestartConfirm}
                loading={pendingAction === "restart"}
              />
            </>
          )}
          {isCancellable && (
            <>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => onConfirmingCancelChange(true)}
                disabled={actionPending}
                className="border-destructive/40 text-destructive hover:bg-destructive/10"
              >
                <XCircle className="size-4" />
                {pendingAction === "cancel" ? "Cancelling" : "Cancel Run"}
              </Button>
              <ConfirmDialog
                open={confirmingCancel}
                onOpenChange={onConfirmingCancelChange}
                title="Cancel this run?"
                description="This action cannot be undone. The run will be marked as cancelled."
                confirmText="Yes, cancel"
                cancelText="No, keep it"
                variant="destructive"
                onConfirm={onCancelConfirm}
                loading={pendingAction === "cancel"}
              />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
