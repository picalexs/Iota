import {
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type MouseEvent,
  type ReactNode,
} from "react";
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  Clock,
  MoreHorizontal,
  Pause,
  Play,
  Plus,
  RotateCcw,
  Trash2,
  XCircle,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import type { BenchmarkHistoryRun } from "@/features/benchmarks/state/history";
import {
  BENCHMARK_HISTORY_BACKEND_LABELS,
  BENCHMARK_HISTORY_STATUS_LABELS,
  canCancelSavedBenchmark,
  canPauseSavedBenchmark,
  canRestartSavedBenchmark,
  canResumeSavedBenchmark,
  formatSavedBenchmarkDate,
  getSavedBenchmarkStatus,
  summarizeSavedBenchmarkRows,
  type BenchmarkSortField,
  type BenchmarkSortOrder,
} from "@/features/benchmarks/state/history";

type DeleteBenchmarkOptions = {
  deleteAssociatedRuns: boolean;
};

type BenchmarkSavedRunAction = "pause" | "resume" | "restart" | "cancel";

interface BenchmarkSavedRunsListProps {
  readonly savedBenchmarkRuns: readonly BenchmarkHistoryRun[];
  readonly selectedSavedBenchmarkId: string | null;
  readonly sortField?: BenchmarkSortField;
  readonly sortOrder?: BenchmarkSortOrder;
  readonly toolbarContent?: ReactNode;
  readonly selectionContent?: ReactNode;
  readonly selectionMode?: boolean;
  readonly selectedRunIds?: ReadonlySet<string>;
  readonly disabled?: boolean;
  readonly onCreate?: () => void | Promise<void>;
  readonly onLoad: (savedRunId: string) => void | Promise<void>;
  readonly onDelete: (savedRunId: string, options: DeleteBenchmarkOptions) => void | Promise<void>;
  readonly onRunAction?: (
    run: BenchmarkHistoryRun,
    action: BenchmarkSavedRunAction,
  ) => void | Promise<void>;
  readonly onToggleSelected?: (savedRunId: string) => void;
  readonly onSort?: (field: BenchmarkSortField) => void;
}

interface SortHeaderProps {
  readonly label: string;
  readonly field: BenchmarkSortField;
  readonly sortField: BenchmarkSortField;
  readonly sortOrder: BenchmarkSortOrder;
  readonly onSort?: (field: BenchmarkSortField) => void;
}

function SortIcon({
  active,
  order,
}: {
  readonly active: boolean;
  readonly order: BenchmarkSortOrder;
}) {
  if (active && order === "asc") {
    return <ArrowUp className="size-3" />;
  }
  if (active) {
    return <ArrowDown className="size-3" />;
  }
  return <ArrowUpDown className="size-3 opacity-40" />;
}

function SortHeader({ label, field, sortField, sortOrder, onSort }: SortHeaderProps) {
  const isActive = sortField === field;
  return (
    <button
      type="button"
      className="inline-flex items-center gap-1 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground transition-colors hover:text-foreground"
      onClick={() => onSort?.(field)}
      aria-label={`Sort by ${label}`}
    >
      {label}
      <SortIcon active={isActive} order={sortOrder} />
    </button>
  );
}

function statusBadge(run: BenchmarkHistoryRun) {
  const status = getSavedBenchmarkStatus(run);
  if (status === "running") {
    return <Badge variant="info">{BENCHMARK_HISTORY_STATUS_LABELS[status]}</Badge>;
  }
  if (status === "paused") {
    return <Badge variant="warning">{BENCHMARK_HISTORY_STATUS_LABELS[status]}</Badge>;
  }
  if (status === "finished") {
    return <Badge variant="success">{BENCHMARK_HISTORY_STATUS_LABELS[status]}</Badge>;
  }
  if (status === "partial") {
    return <Badge variant="warning">{BENCHMARK_HISTORY_STATUS_LABELS[status]}</Badge>;
  }
  if (status === "failed") {
    return <Badge variant="destructive">{BENCHMARK_HISTORY_STATUS_LABELS[status]}</Badge>;
  }
  if (status === "cancelled") {
    return <Badge variant="info">{BENCHMARK_HISTORY_STATUS_LABELS[status]}</Badge>;
  }
  return <Badge variant="secondary">{BENCHMARK_HISTORY_STATUS_LABELS[status]}</Badge>;
}

function stopRowInteraction(event: MouseEvent<HTMLElement> | ReactKeyboardEvent<HTMLElement>) {
  event.stopPropagation();
}

function BenchmarkSavedRunActions({
  run,
  disabled,
  onRunAction,
  onDelete,
}: {
  readonly run: BenchmarkHistoryRun;
  readonly disabled: boolean;
  readonly onRunAction?: (
    run: BenchmarkHistoryRun,
    action: BenchmarkSavedRunAction,
  ) => void | Promise<void>;
  readonly onDelete: (run: BenchmarkHistoryRun) => void;
}) {
  const [open, setOpen] = useState(false);
  const actionButtonClassName =
    "h-8 w-full justify-start px-2 text-xs font-medium text-foreground hover:bg-accent/70";
  const canPause = canPauseSavedBenchmark(run);
  const canResume = canResumeSavedBenchmark(run);
  const canRestart = canRestartSavedBenchmark(run);
  const canCancel = canCancelSavedBenchmark(run);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="size-8 text-muted-foreground hover:text-foreground"
          aria-label={`Benchmark actions for ${run.name}`}
          disabled={disabled}
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
          {canPause ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className={actionButtonClassName}
              disabled={disabled}
              onClick={() => {
                setOpen(false);
                void Promise.resolve(onRunAction?.(run, "pause")).catch(() => undefined);
              }}
            >
              <Pause className="size-4" />
              Pause benchmark
            </Button>
          ) : null}
          {canResume ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className={actionButtonClassName}
              disabled={disabled}
              onClick={() => {
                setOpen(false);
                void Promise.resolve(onRunAction?.(run, "resume")).catch(() => undefined);
              }}
            >
              <Play className="size-4" />
              Resume benchmark
            </Button>
          ) : null}
          {canRestart ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className={actionButtonClassName}
              disabled={disabled}
              onClick={() => {
                setOpen(false);
                void Promise.resolve(onRunAction?.(run, "restart")).catch(() => undefined);
              }}
            >
              <RotateCcw className="size-4" />
              Restart benchmark
            </Button>
          ) : null}
          {canCancel ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className={actionButtonClassName}
              disabled={disabled}
              onClick={() => {
                setOpen(false);
                void Promise.resolve(onRunAction?.(run, "cancel")).catch(() => undefined);
              }}
            >
              <XCircle className="size-4" />
              Cancel benchmark
            </Button>
          ) : null}
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className={`${actionButtonClassName} text-destructive hover:bg-destructive/10 hover:text-destructive`}
            disabled={disabled}
            onClick={() => {
              setOpen(false);
              onDelete(run);
            }}
          >
            <Trash2 className="size-4" />
            Delete benchmark
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}

export function BenchmarkSavedRunsList({
  savedBenchmarkRuns,
  selectedSavedBenchmarkId,
  sortField = "updated",
  sortOrder = "desc",
  toolbarContent,
  selectionContent,
  selectionMode = false,
  selectedRunIds = new Set<string>(),
  disabled = false,
  onCreate,
  onLoad,
  onDelete,
  onRunAction,
  onToggleSelected,
  onSort,
}: Readonly<BenchmarkSavedRunsListProps>) {
  const [deleteTarget, setDeleteTarget] = useState<BenchmarkHistoryRun | null>(null);
  const [deleteAssociatedRuns, setDeleteAssociatedRuns] = useState(false);
  const associatedRunCount = deleteTarget
    ? "rowCount" in deleteTarget
      ? deleteTarget.associatedRunCount
      : new Set(deleteTarget.entries.flatMap((entry) => (entry.runId ? [entry.runId] : []))).size
    : 0;
  let deleteDescription: string | undefined;
  if (deleteTarget) {
    deleteDescription =
      associatedRunCount > 0
        ? `This will permanently delete "${deleteTarget.name}". You can also remove its associated runs from the runs history.`
        : `This will permanently delete "${deleteTarget.name}". This cannot be undone.`;
  }

  return (
    <>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-3">
          <CardTitle className="text-base font-semibold">Saved benchmark runs</CardTitle>
          <Badge variant="outline">{savedBenchmarkRuns.length}</Badge>
        </CardHeader>
        <CardContent className="p-0">
          {toolbarContent ? <div className="border-t px-4 py-3">{toolbarContent}</div> : null}
          {savedBenchmarkRuns.length === 0 ? (
            <div className="flex flex-col items-center gap-4 border-t px-4 py-12 text-center text-sm text-muted-foreground">
              <Clock className="h-4 w-4" />
              <p>Completed and active benchmark batches will appear here.</p>
              {onCreate ? (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={disabled}
                  onClick={() => {
                    Promise.resolve(onCreate()).catch(() => undefined);
                  }}
                >
                  <Plus className="size-3.5 mr-2" />
                  New Benchmark
                </Button>
              ) : null}
            </div>
          ) : (
            <>
              {selectionContent}
              <Table>
                <TableHeader>
                  <TableRow className="bg-muted/40">
                    {selectionMode ? (
                      <TableHead className="w-12 text-center">Select</TableHead>
                    ) : null}
                    <TableHead>
                      <SortHeader
                        label="Name"
                        field="name"
                        sortField={sortField}
                        sortOrder={sortOrder}
                        onSort={onSort}
                      />
                    </TableHead>
                    <TableHead>
                      <SortHeader
                        label="Rows"
                        field="rows"
                        sortField={sortField}
                        sortOrder={sortOrder}
                        onSort={onSort}
                      />
                    </TableHead>
                    <TableHead>
                      <SortHeader
                        label="Backend"
                        field="backend"
                        sortField={sortField}
                        sortOrder={sortOrder}
                        onSort={onSort}
                      />
                    </TableHead>
                    <TableHead>
                      <SortHeader
                        label="Updated"
                        field="updated"
                        sortField={sortField}
                        sortOrder={sortOrder}
                        onSort={onSort}
                      />
                    </TableHead>
                    <TableHead>
                      <SortHeader
                        label="Status"
                        field="status"
                        sortField={sortField}
                        sortOrder={sortOrder}
                        onSort={onSort}
                      />
                    </TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {savedBenchmarkRuns.map((run) => {
                    const summary = summarizeSavedBenchmarkRows(run);
                    const selected = run.id === selectedSavedBenchmarkId;
                    const rowSelected = selectedRunIds.has(run.id);
                    return (
                      <TableRow
                        key={run.id}
                        data-state={selected || rowSelected ? "selected" : undefined}
                        className={cn("cursor-pointer", selected && "bg-muted/60")}
                        onClick={() => {
                          if (disabled) {
                            return;
                          }
                          if (selectionMode) {
                            onToggleSelected?.(run.id);
                            return;
                          }
                          Promise.resolve(onLoad(run.id)).catch(() => undefined);
                        }}
                      >
                        {selectionMode ? (
                          <TableCell className="text-center">
                            <Checkbox
                              aria-label={`Select ${run.name}`}
                              checked={rowSelected}
                              onClick={(event) => event.stopPropagation()}
                              onCheckedChange={() => onToggleSelected?.(run.id)}
                            />
                          </TableCell>
                        ) : null}
                        <TableCell className="max-w-[22rem] whitespace-normal">
                          <div className="flex min-w-0 flex-col gap-1">
                            <span className="font-medium">{run.name}</span>
                            <span className="text-xs text-muted-foreground">
                              {run.selectedMoleculeKeys.length} molecules · {summary.total} rows ·{" "}
                              {run.selectedBasis}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <span className="font-mono text-xs">
                            {summary.done}/{summary.total}
                          </span>
                        </TableCell>
                        <TableCell>
                          {BENCHMARK_HISTORY_BACKEND_LABELS[run.selectedBackendMode] ??
                            run.selectedBackendMode}
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {formatSavedBenchmarkDate(run.updatedAt)}
                        </TableCell>
                        <TableCell>{statusBadge(run)}</TableCell>
                        <TableCell className="text-right">
                          <div className="inline-flex items-center gap-2">
                            {selectionMode ? null : (
                              <BenchmarkSavedRunActions
                                run={run}
                                disabled={disabled}
                                onRunAction={onRunAction}
                                onDelete={(targetRun) => setDeleteTarget(targetRun)}
                              />
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </>
          )}
        </CardContent>
      </Card>

      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (open) {
            return;
          }
          setDeleteAssociatedRuns(false);
          setDeleteTarget(null);
        }}
        title="Delete benchmark run?"
        description={deleteDescription}
        confirmText="Delete"
        variant="destructive"
        disabled={disabled || deleteTarget === null}
        onConfirm={async () => {
          if (deleteTarget) {
            const runId = deleteTarget.id;
            const shouldDeleteAssociatedRuns = deleteAssociatedRuns;
            setDeleteAssociatedRuns(false);
            setDeleteTarget(null);
            await onDelete(runId, { deleteAssociatedRuns: shouldDeleteAssociatedRuns });
          }
        }}
      >
        {associatedRunCount > 0 ? (
          <label className="flex items-start gap-3 rounded-md border p-3 text-sm">
            <Checkbox
              aria-label="Also delete associated runs"
              checked={deleteAssociatedRuns}
              onCheckedChange={(checked) => setDeleteAssociatedRuns(checked === true)}
            />
            <span>Also delete {associatedRunCount} associated run(s) from the runs history.</span>
          </label>
        ) : null}
      </ConfirmDialog>
    </>
  );
}
