import { useState, type KeyboardEvent, type MouseEvent } from "react";
import { MoreHorizontal, Pause, Play, RotateCcw, type LucideIcon, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";
import type { BenchmarkEntry } from "./benchmark-utils";

export type BenchmarkResultsRowAction = "pause" | "resume" | "restart" | "retry" | "cancel";
type ConfirmableBenchmarkResultsRowAction = Exclude<BenchmarkResultsRowAction, "resume">;

const PAUSABLE_STATUSES = new Set<BenchmarkEntry["status"]>(["queued", "running", "pausing"]);
const RESUMABLE_STATUSES = new Set<BenchmarkEntry["status"]>(["paused", "failed"]);
const RESTARTABLE_STATUSES = new Set<BenchmarkEntry["status"]>([
  "completed",
  "failed",
  "cancelled",
  "paused",
]);
const CANCELLABLE_STATUSES = new Set<BenchmarkEntry["status"]>([
  "queued",
  "running",
  "pausing",
  "paused",
  "acquiring_molecule",
  "submitting",
]);

function stopRowInteraction(event: MouseEvent<HTMLElement> | KeyboardEvent<HTMLElement>) {
  event.stopPropagation();
}

interface BenchmarkRowActionAvailability {
  actionPending: boolean;
  pauseInProgress: boolean;
  canPause: boolean;
  canResume: boolean;
  canRestart: boolean;
  canRetry: boolean;
  canCancel: boolean;
}

interface BenchmarkRowActionMenuItem {
  action: BenchmarkResultsRowAction;
  label: string;
  icon: LucideIcon;
  disabled: boolean;
  destructive?: boolean;
  onSelect: () => void;
}

interface BenchmarkRowActionDialogsProps {
  entry: BenchmarkEntry;
  pendingAction: BenchmarkResultsRowAction | null;
  confirmingAction: ConfirmableBenchmarkResultsRowAction | null;
  onConfirmingActionChange: (action: ConfirmableBenchmarkResultsRowAction | null) => void;
  onRunAction: (entry: BenchmarkEntry, action: BenchmarkResultsRowAction) => void | Promise<void>;
}

function getBenchmarkRowActionAvailability(
  entry: BenchmarkEntry,
  pendingAction: BenchmarkResultsRowAction | null,
): BenchmarkRowActionAvailability {
  const runId = entry.runId;
  return {
    actionPending: pendingAction !== null,
    pauseInProgress: pendingAction === "pause" || entry.status === "pausing",
    canPause: PAUSABLE_STATUSES.has(entry.status),
    canResume: runId !== null && RESUMABLE_STATUSES.has(entry.status),
    canRestart:
      runId !== null && RESTARTABLE_STATUSES.has(entry.status) && entry.status !== "failed",
    canRetry: entry.status === "failed",
    canCancel: runId !== null && CANCELLABLE_STATUSES.has(entry.status),
  };
}

function retryDialogDescription(runId: string | null): string {
  return runId === null
    ? "A new run will be submitted from the saved benchmark row configuration."
    : "A new run will be created from the stored configuration.";
}

function actionPendingLabel(
  pendingAction: BenchmarkResultsRowAction | null,
  action: BenchmarkResultsRowAction,
  idleLabel: string,
  pendingLabel: string,
): string {
  return pendingAction === action ? pendingLabel : idleLabel;
}

function buildBenchmarkRowActionMenuItems({
  availability,
  pendingAction,
  openPauseConfirm,
  openRestartConfirm,
  openRetryConfirm,
  openCancelConfirm,
  onResume,
}: {
  availability: BenchmarkRowActionAvailability;
  pendingAction: BenchmarkResultsRowAction | null;
  openPauseConfirm: () => void;
  openRestartConfirm: () => void;
  openRetryConfirm: () => void;
  openCancelConfirm: () => void;
  onResume: () => void;
}): BenchmarkRowActionMenuItem[] {
  const items: BenchmarkRowActionMenuItem[] = [];

  if (availability.canPause) {
    items.push({
      action: "pause",
      label: availability.pauseInProgress ? "Pausing..." : "Pause run",
      icon: Pause,
      disabled: availability.actionPending || availability.pauseInProgress,
      onSelect: openPauseConfirm,
    });
  }
  if (availability.canResume) {
    items.push({
      action: "resume",
      label: actionPendingLabel(pendingAction, "resume", "Resume run", "Resuming..."),
      icon: Play,
      disabled: availability.actionPending,
      onSelect: onResume,
    });
  }
  if (availability.canRestart) {
    items.push({
      action: "restart",
      label: actionPendingLabel(pendingAction, "restart", "Restart run", "Restarting..."),
      icon: RotateCcw,
      disabled: availability.actionPending,
      onSelect: openRestartConfirm,
    });
  }
  if (availability.canRetry) {
    items.push({
      action: "retry",
      label: actionPendingLabel(pendingAction, "retry", "Retry run", "Retrying..."),
      icon: RotateCcw,
      disabled: availability.actionPending,
      onSelect: openRetryConfirm,
    });
  }
  if (availability.canCancel) {
    items.push({
      action: "cancel",
      label: actionPendingLabel(pendingAction, "cancel", "Cancel run", "Cancelling..."),
      icon: XCircle,
      disabled: availability.actionPending,
      destructive: true,
      onSelect: openCancelConfirm,
    });
  }

  return items;
}

function BenchmarkRowActionMenuButton({
  item,
  className,
}: {
  item: BenchmarkRowActionMenuItem;
  className: string;
}) {
  const Icon = item.icon;
  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      className={cn(
        className,
        item.destructive && "text-destructive hover:bg-destructive/10 hover:text-destructive",
      )}
      disabled={item.disabled}
      onClick={(event) => {
        event.stopPropagation();
        item.onSelect();
      }}
      onKeyDown={stopRowInteraction}
    >
      <Icon className="size-4" />
      {item.label}
    </Button>
  );
}

function BenchmarkRowActionDialogs({
  entry,
  pendingAction,
  confirmingAction,
  onConfirmingActionChange,
  onRunAction,
}: BenchmarkRowActionDialogsProps) {
  return (
    <>
      <ConfirmDialog
        open={confirmingAction === "pause"}
        onOpenChange={(open) => onConfirmingActionChange(open ? "pause" : null)}
        title="Pause this run?"
        description="IBM Runtime jobs already submitted will finish before the run pauses."
        confirmText="Pause"
        cancelText="Keep running"
        onConfirm={() => onRunAction(entry, "pause")}
        loading={pendingAction === "pause"}
      />
      <ConfirmDialog
        open={confirmingAction === "restart"}
        onOpenChange={(open) => onConfirmingActionChange(open ? "restart" : null)}
        title="Restart this run?"
        description="A new run will be created from the stored configuration when restart is available."
        confirmText="Restart"
        cancelText="Keep current run"
        onConfirm={() => onRunAction(entry, "restart")}
        loading={pendingAction === "restart"}
      />
      <ConfirmDialog
        open={confirmingAction === "retry"}
        onOpenChange={(open) => onConfirmingActionChange(open ? "retry" : null)}
        title="Retry this run?"
        description={retryDialogDescription(entry.runId)}
        confirmText="Retry"
        cancelText="Keep failed run"
        onConfirm={() => onRunAction(entry, "retry")}
        loading={pendingAction === "retry"}
      />
      <ConfirmDialog
        open={confirmingAction === "cancel"}
        onOpenChange={(open) => onConfirmingActionChange(open ? "cancel" : null)}
        title="Cancel this run?"
        description="This action cannot be undone. The run will be marked as cancelled."
        confirmText="Yes, cancel"
        cancelText="No, keep it"
        variant="destructive"
        onConfirm={() => onRunAction(entry, "cancel")}
        loading={pendingAction === "cancel"}
      />
    </>
  );
}

export function BenchmarkResultRowActions({
  entry,
  pendingAction = null,
  onRunAction,
}: {
  entry: BenchmarkEntry;
  pendingAction?: BenchmarkResultsRowAction | null;
  onRunAction: (entry: BenchmarkEntry, action: BenchmarkResultsRowAction) => void | Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [confirmingAction, setConfirmingAction] =
    useState<ConfirmableBenchmarkResultsRowAction | null>(null);
  const availability = getBenchmarkRowActionAvailability(entry, pendingAction);
  const actionButtonClassName =
    "h-8 w-full justify-start px-2 text-xs font-medium text-foreground hover:bg-accent/70";
  const closeAndRunAction = (action: BenchmarkResultsRowAction) => {
    setOpen(false);
    return onRunAction(entry, action);
  };
  const closeMenuAndConfirm = (action: ConfirmableBenchmarkResultsRowAction) => {
    setOpen(false);
    setConfirmingAction(action);
  };
  const menuItems = buildBenchmarkRowActionMenuItems({
    availability,
    pendingAction,
    openPauseConfirm: () => closeMenuAndConfirm("pause"),
    openRestartConfirm: () => closeMenuAndConfirm("restart"),
    openRetryConfirm: () => closeMenuAndConfirm("retry"),
    openCancelConfirm: () => closeMenuAndConfirm("cancel"),
    onResume: () => {
      void Promise.resolve(closeAndRunAction("resume")).catch(() => undefined);
    },
  });

  return (
    <>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="size-8 text-muted-foreground hover:text-foreground"
            aria-label={`Run actions for ${entry.algorithm.toUpperCase()}`}
            onClick={stopRowInteraction}
            onKeyDown={stopRowInteraction}
          >
            <MoreHorizontal className="size-4" />
          </Button>
        </PopoverTrigger>
        <PopoverContent
          align="end"
          className="w-44 p-1"
          onClick={stopRowInteraction}
          onKeyDown={stopRowInteraction}
        >
          <div className="flex flex-col gap-1">
            {menuItems.map((item) => (
              <BenchmarkRowActionMenuButton
                key={item.action}
                item={item}
                className={actionButtonClassName}
              />
            ))}
          </div>
        </PopoverContent>
      </Popover>

      <BenchmarkRowActionDialogs
        entry={entry}
        pendingAction={pendingAction}
        confirmingAction={confirmingAction}
        onConfirmingActionChange={setConfirmingAction}
        onRunAction={onRunAction}
      />
    </>
  );
}
