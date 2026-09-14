/** Benchmark overflow menu items and rendering. */

import { MoreHorizontal, Pause, Play, RotateCcw, Trash2, XCircle } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

type BenchmarkOverflowActionItem = Readonly<{
  key: string;
  label: string;
  icon: typeof Pause;
  disabled: boolean;
  destructive?: boolean;
  onSelect: () => void;
}>;

function closeAndRunBenchmarkAction(onSelect: () => void, setOpen: (open: boolean) => void): void {
  setOpen(false);
  onSelect();
}

type BenchmarkOverflowActionParams = {
  actionInProgress: boolean;
  pauseInProgress: boolean;
  resumeInProgress: boolean;
  restartInProgress: boolean;
  canPauseBenchmark: boolean;
  hasPausedBenchmark: boolean;
  running: boolean;
  showDeleteBenchmarkAction: boolean;
  deleteBenchmarkInProgress: boolean;
  onPauseBenchmark: () => void;
  onResumeBenchmark: () => void;
  onRestartBenchmark: () => void;
  onCancelBenchmark: () => void;
  onDeleteBenchmark?: () => void;
  setOpen: (open: boolean) => void;
};

function pauseBenchmarkOverflowAction(
  params: BenchmarkOverflowActionParams,
): BenchmarkOverflowActionItem | null {
  if (!params.canPauseBenchmark) {
    return null;
  }
  return {
    key: "pause",
    label: params.pauseInProgress ? "Pausing..." : "Pause benchmark",
    icon: Pause,
    disabled: params.actionInProgress || params.pauseInProgress,
    onSelect: () => closeAndRunBenchmarkAction(params.onPauseBenchmark, params.setOpen),
  };
}

function pausedBenchmarkOverflowActions(
  params: BenchmarkOverflowActionParams,
): BenchmarkOverflowActionItem[] {
  if (!params.hasPausedBenchmark) {
    return [];
  }
  return [
    {
      key: "resume",
      label: params.resumeInProgress ? "Resuming..." : "Resume benchmark",
      icon: Play,
      disabled: params.actionInProgress,
      onSelect: () => closeAndRunBenchmarkAction(params.onResumeBenchmark, params.setOpen),
    },
    {
      key: "restart",
      label: params.restartInProgress ? "Restarting..." : "Restart benchmark",
      icon: RotateCcw,
      disabled: params.actionInProgress,
      onSelect: () => closeAndRunBenchmarkAction(params.onRestartBenchmark, params.setOpen),
    },
  ];
}

function cancelBenchmarkOverflowAction(
  params: BenchmarkOverflowActionParams,
): BenchmarkOverflowActionItem | null {
  if (!params.running) {
    return null;
  }
  return {
    key: "cancel",
    label: "Stop benchmark",
    icon: XCircle,
    disabled: params.actionInProgress,
    onSelect: () => closeAndRunBenchmarkAction(params.onCancelBenchmark, params.setOpen),
  };
}

function deleteBenchmarkOverflowAction(
  params: BenchmarkOverflowActionParams,
): BenchmarkOverflowActionItem | null {
  if (!params.showDeleteBenchmarkAction || !params.onDeleteBenchmark) {
    return null;
  }
  const onDeleteBenchmark = params.onDeleteBenchmark;
  return {
    key: "delete",
    label: params.deleteBenchmarkInProgress ? "Deleting..." : "Delete benchmark",
    icon: Trash2,
    disabled: params.deleteBenchmarkInProgress,
    destructive: true,
    onSelect: () => closeAndRunBenchmarkAction(onDeleteBenchmark, params.setOpen),
  };
}

function buildBenchmarkOverflowActions(
  params: BenchmarkOverflowActionParams,
): BenchmarkOverflowActionItem[] {
  return [
    pauseBenchmarkOverflowAction(params),
    ...pausedBenchmarkOverflowActions(params),
    cancelBenchmarkOverflowAction(params),
    deleteBenchmarkOverflowAction(params),
  ].filter((action): action is BenchmarkOverflowActionItem => action !== null);
}

export function BenchmarkOverflowActions({
  hasPausedBenchmark,
  actionInProgress,
  pauseInProgress,
  resumeInProgress,
  restartInProgress,
  canPauseBenchmark,
  running,
  showDeleteBenchmarkAction,
  deleteBenchmarkInProgress,
  onPauseBenchmark,
  onResumeBenchmark,
  onRestartBenchmark,
  onCancelBenchmark,
  onDeleteBenchmark,
}: Readonly<{
  hasPausedBenchmark: boolean;
  actionInProgress: boolean;
  pauseInProgress: boolean;
  resumeInProgress: boolean;
  restartInProgress: boolean;
  canPauseBenchmark: boolean;
  running: boolean;
  showDeleteBenchmarkAction: boolean;
  deleteBenchmarkInProgress: boolean;
  onPauseBenchmark: () => void;
  onResumeBenchmark: () => void;
  onRestartBenchmark: () => void;
  onCancelBenchmark: () => void;
  onDeleteBenchmark?: () => void;
}>) {
  const [open, setOpen] = useState(false);
  const buttonClassName = "h-8 w-full justify-start px-2 text-xs";
  const actions = buildBenchmarkOverflowActions({
    actionInProgress,
    pauseInProgress,
    resumeInProgress,
    restartInProgress,
    canPauseBenchmark,
    hasPausedBenchmark,
    running,
    showDeleteBenchmarkAction,
    deleteBenchmarkInProgress,
    onPauseBenchmark,
    onResumeBenchmark,
    onRestartBenchmark,
    onCancelBenchmark,
    onDeleteBenchmark,
    setOpen,
  });

  if (actions.length === 0) {
    return null;
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button type="button" variant="outline" size="icon" aria-label="Benchmark actions">
          <MoreHorizontal className="h-4 w-4" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-48 p-1">
        <div className="flex flex-col gap-1">
          {actions.map((action) => (
            <Button
              key={action.key}
              type="button"
              variant="ghost"
              size="sm"
              className={cn(
                buttonClassName,
                action.destructive &&
                  "text-destructive hover:bg-destructive/10 hover:text-destructive",
              )}
              disabled={action.disabled}
              onClick={action.onSelect}
            >
              <action.icon className="h-4 w-4" />
              {action.label}
            </Button>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  );
}
