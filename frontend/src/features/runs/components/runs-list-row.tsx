import { useNavigate } from "@tanstack/react-router";
import {
  useState,
  type ComponentPropsWithoutRef,
  type KeyboardEvent as ReactKeyboardEvent,
  type MouseEvent,
} from "react";
import {
  CheckCircle2,
  CircleMinus,
  type LucideIcon,
  MoreHorizontal,
  Pause,
  Play,
  RotateCcw,
  Trash2,
  XCircle,
} from "lucide-react";

import { StatusBadge } from "./status-badge";
import type { RunResponse, RunSummaryResponse } from "@/types/run";
import { formatDuration } from "@/lib/format-duration";
import { formatMeaningfulEta } from "@/lib/run-estimate-display";
import { runtimeSecondsFromRun } from "@/lib/run-runtime";
import { getRunsTableGrid, truncateId } from "./runs-list-row-utils";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

export function formatBackendTarget(run: RunSummaryResponse | RunResponse): string {
  const target = run.backend_target;
  if (target == null) return "—";
  if (target === "statevector") return "Statevector";
  if (target === "aer_simulator") return "Aer Sim";
  if (target === "ibm_runtime") {
    let name: string | null | undefined;
    if ("config_json" in run) {
      name = run.config_json.backend_options?.backend_name;
    } else {
      name = run.backend_name;
    }
    return name ?? "IBM";
  }
  return target;
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleString();
}

function formatEstimatedIterationText(total?: number | null, remaining?: number | null): string {
  if (total === null || total === undefined || remaining === null || remaining === undefined) {
    return "-";
  }

  return `${Math.max(0, total - remaining)}`;
}

function formatEtaSuffix(etaLabel: string | null): string {
  if (etaLabel === null) return "";
  return ` · ETA ${etaLabel}`;
}

type RunProgressSource = Pick<RunResponse, "status" | "latest_estimate"> | Pick<
  RunSummaryResponse,
  "status" | "latest_estimate"
>;

export function formatRuntimeCell(runtimeSeconds: number | null): string {
  if (runtimeSeconds === null) return "—";
  return formatDuration(runtimeSeconds);
}

export function formatRunProgress(
  run: RunProgressSource,
): string | null {
  const showsProgress = ["RUNNING", "PAUSING", "QUEUED", "SUBMITTED_TO_IBM"].includes(run.status);
  if (showsProgress) {
    const estimate = run.latest_estimate;
    if (estimate == null) return null;

    const iterText = formatEstimatedIterationText(
      estimate.estimated_total_iterations,
      estimate.estimated_remaining_iterations,
    );
    const etaSeconds = estimate.estimated_remaining_seconds;
    const etaLabel = formatMeaningfulEta(etaSeconds, estimate.confidence);
    const etaText = formatEtaSuffix(etaLabel);
    return `Iter ${iterText}${etaText}`;
  }

  return null;
}

type ChemicalAccuracy = boolean | null | undefined;

function formatChemicalAccuracyLabel(chemicalAccurate: ChemicalAccuracy): string {
  if (chemicalAccurate == null) {
    return "Chemical accuracy unavailable";
  }

  return chemicalAccurate ? "Chemically accurate" : "Not chemically accurate";
}

export interface RunsListRowProps {
  readonly run: RunSummaryResponse;
  readonly moleculeName: string;
  readonly pendingAction: RunRowAction | null;
  readonly pendingDelete?: boolean;
  readonly selectionMode?: boolean;
  readonly selected?: boolean;
  readonly onToggleSelected?: () => void;
  readonly onAction: (action: RunRowAction) => void | Promise<void>;
  readonly onDelete: () => void | Promise<void>;
}

export type RunRowAction = "pause" | "resume" | "restart" | "cancel";

const CANCELLABLE_STATUSES = new Set<RunSummaryResponse["status"]>([
  "CREATED",
  "RUNNING",
  "QUEUED",
  "PAUSING",
  "PAUSED",
  "SUBMITTED_TO_IBM",
]);
const PAUSABLE_STATUSES = new Set<RunSummaryResponse["status"]>([
  "CREATED",
  "RUNNING",
  "QUEUED",
  "SUBMITTED_TO_IBM",
]);
const RESUMABLE_STATUSES = new Set<RunSummaryResponse["status"]>(["PAUSED", "FAILED"]);
const RESTARTABLE_STATUSES = new Set<RunSummaryResponse["status"]>([
  "COMPLETED",
  "FAILED",
  "CANCELLED",
  "EXCLUDED",
  "PAUSED",
]);

function stopRowNavigation(event: MouseEvent | ReactKeyboardEvent) {
  event.stopPropagation();
}

function shouldHandleRowEvent(
  target: EventTarget | null,
  currentTarget: EventTarget | null,
): boolean {
  if (!(target instanceof Node) || !(currentTarget instanceof Node)) {
    return false;
  }

  return currentTarget.contains(target);
}

export function ChemicalAccuracyIcon({
  chemicalAccurate,
  decorative = false,
}: {
  readonly chemicalAccurate: ChemicalAccuracy;
  readonly decorative?: boolean;
}) {
  const label = formatChemicalAccuracyLabel(chemicalAccurate);
  const accessibilityProps = decorative
    ? { "aria-hidden": true }
    : { title: label, "aria-label": label };
  const iconClassName = chemicalAccuracyClassName(chemicalAccurate);
  const icon = renderChemicalAccuracyIcon(chemicalAccurate);

  return (
    <span {...accessibilityProps} className={cn("inline-flex", iconClassName)}>
      {icon}
    </span>
  );
}

function chemicalAccuracyClassName(chemicalAccurate: boolean | null | undefined): string {
  if (chemicalAccurate == null) {
    return "text-muted-foreground";
  }

  return chemicalAccurate ? "text-emerald-600" : "text-destructive";
}

function renderChemicalAccuracyIcon(chemicalAccurate: boolean | null | undefined) {
  if (chemicalAccurate == null) {
    return <CircleMinus className="size-4" aria-hidden="true" />;
  }

  return chemicalAccurate ? (
    <CheckCircle2 className="size-4" aria-hidden="true" />
  ) : (
    <XCircle className="size-4" aria-hidden="true" />
  );
}

type MobileStatProps = Readonly<{
  label: string;
  value: string;
}> &
  ComponentPropsWithoutRef<"div">;

function MobileStat({ label, value, className }: MobileStatProps) {
  return (
    <div className={cn("min-w-0", className)}>
      <dt className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd className="mt-1 break-words text-sm text-foreground">{value}</dd>
    </div>
  );
}

type RunActionMenuItem = {
  readonly key: string;
  readonly label: string;
  readonly icon: LucideIcon;
  readonly destructive?: boolean;
  readonly disabled: boolean;
  readonly onClick: () => void;
};

function buildRunActionMenuItems({
  canPause,
  pauseInProgress,
  canResume,
  canRestart,
  canCancel,
  actionPending,
  pendingAction,
  pendingDelete,
  closeAndRunAction,
  openPauseConfirmation,
  openRestartConfirmation,
  openCancelConfirmation,
  openDeleteConfirmation,
}: Readonly<{
  canPause: boolean;
  pauseInProgress: boolean;
  canResume: boolean;
  canRestart: boolean;
  canCancel: boolean;
  actionPending: boolean;
  pendingAction: RunRowAction | null;
  pendingDelete: boolean;
  closeAndRunAction: (action: RunRowAction) => void | Promise<void>;
  openPauseConfirmation: () => void;
  openRestartConfirmation: () => void;
  openCancelConfirmation: () => void;
  openDeleteConfirmation: () => void;
}>): RunActionMenuItem[] {
  const items: RunActionMenuItem[] = [];

  if (canPause) {
    items.push({
      key: "pause",
      label: pauseInProgress ? "Pausing..." : "Pause run",
      icon: Pause,
      disabled: actionPending || pauseInProgress,
      onClick: openPauseConfirmation,
    });
  }

  if (canResume) {
    items.push({
      key: "resume",
      label: pendingAction === "resume" ? "Resuming..." : "Resume run",
      icon: Play,
      disabled: actionPending,
      onClick: () => {
        closeAndRunAction("resume");
      },
    });
  }

  if (canRestart) {
    items.push({
      key: "restart",
      label: pendingAction === "restart" ? "Restarting..." : "Restart run",
      icon: RotateCcw,
      disabled: actionPending,
      onClick: openRestartConfirmation,
    });
  }

  if (canCancel) {
    items.push({
      key: "cancel",
      label: pendingAction === "cancel" ? "Cancelling..." : "Cancel run",
      icon: XCircle,
      destructive: true,
      disabled: actionPending,
      onClick: openCancelConfirmation,
    });
  }

  items.push({
    key: "delete",
    label: pendingDelete ? "Deleting..." : "Delete run",
    icon: Trash2,
    destructive: true,
    disabled: actionPending || pendingDelete,
    onClick: openDeleteConfirmation,
  });

  return items;
}

function RunsListRowActions({
  run,
  pendingAction,
  pendingDelete = false,
  onAction,
  onDelete,
}: Readonly<{
  run: RunSummaryResponse;
  pendingAction: RunRowAction | null;
  pendingDelete?: boolean;
  onAction: (action: RunRowAction) => void | Promise<void>;
  onDelete: () => void | Promise<void>;
}>) {
  const [open, setOpen] = useState(false);
  const [confirmingPause, setConfirmingPause] = useState(false);
  const [confirmingRestart, setConfirmingRestart] = useState(false);
  const [confirmingCancel, setConfirmingCancel] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const actionPending = pendingAction !== null;
  const pauseInProgress = pendingAction === "pause" || run.status === "PAUSING";
  const canPause = PAUSABLE_STATUSES.has(run.status) || run.status === "PAUSING";
  const canResume = RESUMABLE_STATUSES.has(run.status);
  const canRestart = RESTARTABLE_STATUSES.has(run.status);
  const canCancel = CANCELLABLE_STATUSES.has(run.status);

  const actionButtonClassName =
    "h-8 w-full justify-start px-2 text-xs font-medium text-foreground hover:bg-accent/70";
  const closeAndRunAction = (action: RunRowAction) => {
    setOpen(false);
    return onAction(action);
  };
  const menuItems = buildRunActionMenuItems({
    canPause,
    pauseInProgress,
    canResume,
    canRestart,
    canCancel,
    actionPending,
    pendingAction,
    pendingDelete,
    closeAndRunAction,
    openPauseConfirmation: () => {
      setOpen(false);
      setConfirmingPause(true);
    },
    openRestartConfirmation: () => {
      setOpen(false);
      setConfirmingRestart(true);
    },
    openCancelConfirmation: () => {
      setOpen(false);
      setConfirmingCancel(true);
    },
    openDeleteConfirmation: () => {
      setOpen(false);
      setConfirmingDelete(true);
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
            aria-label={`Run actions for ${truncateId(run.id)}`}
            onClick={stopRowNavigation}
            onKeyDown={stopRowNavigation}
          >
            <MoreHorizontal className="size-4" />
          </Button>
        </PopoverTrigger>
        <PopoverContent
          align="end"
          className="w-44 p-1"
          onClick={stopRowNavigation}
          onKeyDown={stopRowNavigation}
        >
          <div className="flex flex-col gap-1">
            {menuItems.map((item) => {
              const Icon = item.icon;
              return (
                <Button
                  key={item.key}
                  type="button"
                  variant="ghost"
                  size="sm"
                  className={cn(
                    actionButtonClassName,
                    item.destructive &&
                      "text-destructive hover:bg-destructive/10 hover:text-destructive",
                  )}
                  disabled={item.disabled}
                  onClick={item.onClick}
                >
                  <Icon className="size-4" />
                  {item.label}
                </Button>
              );
            })}
          </div>
        </PopoverContent>
      </Popover>

      <ConfirmDialog
        open={confirmingPause}
        onOpenChange={setConfirmingPause}
        title="Pause this run?"
        description="IBM Runtime jobs already submitted will finish before the run pauses."
        confirmText="Pause"
        cancelText="Keep running"
        onConfirm={() => onAction("pause")}
        loading={pendingAction === "pause"}
      />
      <ConfirmDialog
        open={confirmingRestart}
        onOpenChange={setConfirmingRestart}
        title="Restart this run?"
        description="A new run will be created from the stored configuration when restart is available."
        confirmText="Restart"
        cancelText="Keep current run"
        onConfirm={() => onAction("restart")}
        loading={pendingAction === "restart"}
      />
      <ConfirmDialog
        open={confirmingCancel}
        onOpenChange={setConfirmingCancel}
        title="Cancel this run?"
        description="This action cannot be undone. The run will be marked as cancelled."
        confirmText="Yes, cancel"
        cancelText="No, keep it"
        variant="destructive"
        onConfirm={() => onAction("cancel")}
        loading={pendingAction === "cancel"}
      />
      <ConfirmDialog
        open={confirmingDelete}
        onOpenChange={setConfirmingDelete}
        title="Delete this run?"
        description={
          CANCELLABLE_STATUSES.has(run.status)
            ? "This permanently removes the run from history. Any queued, running, paused, or IBM-submitted work is cancelled before removal."
            : "This permanently removes the run from history."
        }
        confirmText="Delete run"
        cancelText="Keep run"
        variant="destructive"
        onConfirm={onDelete}
        loading={pendingDelete}
      />
    </>
  );
}

export function RunsListRow({
  run,
  moleculeName,
  pendingAction,
  pendingDelete = false,
  selectionMode = false,
  selected = false,
  onToggleSelected,
  onAction,
  onDelete,
}: RunsListRowProps) {
  const navigate = useNavigate();
  const progressLine = formatRunProgress(run);
  const runtimeSeconds = runtimeSecondsFromRun(run);
  const navigateToRun = () => void navigate({ to: "/runs/$runId", params: { runId: run.id } });
  const rowGridClassName = getRunsTableGrid(selectionMode);

  return (
    <tr
      aria-label={truncateId(run.id)}
      tabIndex={0}
      onClick={(event) => {
        if (!shouldHandleRowEvent(event.target, event.currentTarget)) {
          return;
        }
        if (selectionMode) {
          onToggleSelected?.();
          return;
        }
        navigateToRun();
      }}
      onKeyDown={(event) => {
        if (!shouldHandleRowEvent(event.target, event.currentTarget)) {
          return;
        }
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          if (selectionMode) {
            onToggleSelected?.();
            return;
          }
          navigateToRun();
        }
      }}
      className={cn(
        `grid w-full ${rowGridClassName} items-center gap-4 border-b px-4 py-3 text-left transition-colors last:border-0 focus-visible:bg-accent/50 focus-visible:outline-none`,
        "cursor-pointer hover:bg-accent/50",
        selected && "bg-accent/35",
      )}
    >
      {selectionMode ? (
        <td className="flex justify-center">
          <Checkbox
            aria-label={`Select run ${truncateId(run.id)}`}
            checked={selected}
            onClick={(event) => event.stopPropagation()}
            onCheckedChange={() => onToggleSelected?.()}
          />
        </td>
      ) : null}
      <td className="font-mono text-sm text-muted-foreground">{truncateId(run.id)}</td>
      <td className="flex min-w-0 flex-col gap-0.5">
        <span className="truncate text-sm font-medium">{moleculeName}</span>
        {progressLine && (
          <span className="text-xs text-muted-foreground tabular-nums">{progressLine}</span>
        )}
      </td>
      <td>
        <StatusBadge status={run.status} metadata={run.metadata} />
      </td>
      <td className="flex justify-center">
        <ChemicalAccuracyIcon chemicalAccurate={run.chemical_accurate} />
      </td>
      <td className="text-sm">{run.algorithm?.toUpperCase() ?? "—"}</td>
      <td className="text-sm text-muted-foreground">{formatBackendTarget(run)}</td>
      <td className="font-mono text-sm text-muted-foreground">
        {formatRuntimeCell(runtimeSeconds)}
      </td>
      <td className="text-sm text-muted-foreground">{formatDate(run.created_at)}</td>
      <td className="flex justify-end">
        {selectionMode ? null : (
          <RunsListRowActions
            run={run}
            pendingAction={pendingAction}
            pendingDelete={pendingDelete}
            onAction={onAction}
            onDelete={onDelete}
          />
        )}
      </td>
    </tr>
  );
}

export function RunsMobileCard({
  run,
  moleculeName,
  pendingAction,
  pendingDelete = false,
  selectionMode = false,
  selected = false,
  onToggleSelected,
  onAction,
  onDelete,
}: RunsListRowProps) {
  const navigate = useNavigate();
  const progressLine = formatRunProgress(run);
  const runtimeSeconds = runtimeSecondsFromRun(run);
  const chemicalAccuracyLabel = formatChemicalAccuracyLabel(run.chemical_accurate);
  const navigateToRun = () => void navigate({ to: "/runs/$runId", params: { runId: run.id } });

  return (
    <li aria-label={truncateId(run.id)}>
      <div
        tabIndex={0}
        role={selectionMode ? "checkbox" : "button"}
        aria-checked={selectionMode ? selected : undefined}
        onClick={(event) => {
          if (!shouldHandleRowEvent(event.target, event.currentTarget)) {
            return;
          }
          if (selectionMode) {
            onToggleSelected?.();
            return;
          }
          navigateToRun();
        }}
        onKeyDown={(event) => {
          if (!shouldHandleRowEvent(event.target, event.currentTarget)) {
            return;
          }
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            if (selectionMode) {
              onToggleSelected?.();
              return;
            }
            navigateToRun();
          }
        }}
        className={cn(
          "rounded-xl border border-border/70 bg-card px-4 py-3 shadow-sm transition-colors focus-visible:bg-accent/40 focus-visible:outline-none",
          "cursor-pointer hover:bg-accent/40",
          selected && "bg-accent/30",
        )}
      >
        <div className="flex items-start gap-3">
          {selectionMode ? (
            <div className="pt-0.5">
              <Checkbox
                aria-label={`Select run ${truncateId(run.id)}`}
                checked={selected}
                onClick={(event) => event.stopPropagation()}
                onCheckedChange={() => onToggleSelected?.()}
              />
            </div>
          ) : null}

          <div className="min-w-0 flex-1 space-y-3">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-foreground">{moleculeName}</p>
                <p className="mt-1 font-mono text-xs text-muted-foreground">{truncateId(run.id)}</p>
                {progressLine && (
                  <p className="mt-1 text-xs text-muted-foreground tabular-nums">{progressLine}</p>
                )}
              </div>

              {selectionMode ? null : (
                <div className="-mr-1 -mt-1 shrink-0">
                  <RunsListRowActions
                    run={run}
                    pendingAction={pendingAction}
                    pendingDelete={pendingDelete}
                    onAction={onAction}
                    onDelete={onDelete}
                  />
                </div>
              )}
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge status={run.status} metadata={run.metadata} />
              <span className="inline-flex items-center gap-1.5 rounded-full border border-border/60 bg-muted/35 px-2 py-1 text-xs text-muted-foreground">
                <ChemicalAccuracyIcon chemicalAccurate={run.chemical_accurate} decorative />
                <span>{chemicalAccuracyLabel}</span>
              </span>
            </div>

            <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
              <MobileStat label="Method" value={run.algorithm?.toUpperCase() ?? "—"} />
              <MobileStat label="Backend" value={formatBackendTarget(run)} />
              <MobileStat label="Runtime" value={formatRuntimeCell(runtimeSeconds)} />
              <MobileStat
                label="Created"
                value={formatDate(run.created_at)}
                className="col-span-2"
              />
            </dl>
          </div>
        </div>
      </div>
    </li>
  );
}
