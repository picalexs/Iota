import { type KeyboardEvent } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { AlertCircle, CheckCircle2, Clock, Loader2, Pause, XCircle } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { containerSurfaceClassName } from "@/lib/interactive-styles";
import type { MoleculePreset } from "@/lib/benchmark-presets";
import { formatDuration } from "@/lib/format-duration";
import { isTimedOutFailureMessage } from "@/lib/run-failure";
import { cn } from "@/lib/utils";
import type { BenchmarkEntry } from "./benchmark-utils";
import { assessBenchmarkEntry } from "./benchmark-utils";
import {
  BenchmarkResultRowActions,
  type BenchmarkResultsRowAction,
} from "./benchmark-results-row-actions";

export type { BenchmarkResultsRowAction } from "./benchmark-results-row-actions";

interface BenchmarkResultsTableProps {
  grouped: Array<{ preset: MoleculePreset; rows: BenchmarkEntry[] }>;
  selectedBasis: string;
  chemicalAccuracyHa: number;
  pendingAction?: BenchmarkResultsRowAction | null;
  onRunAction?: (entry: BenchmarkEntry, action: BenchmarkResultsRowAction) => void | Promise<void>;
  onBeforeOpenRun?: () => void;
}

type BenchmarkGroupedRows = BenchmarkResultsTableProps["grouped"][number];
type OpenRunHandler = (runId: string) => void;

function StatusIndicator({
  icon: Icon,
  label,
  iconClassName,
  ariaLabel = label,
  spin = false,
}: {
  icon: typeof CheckCircle2;
  label: string;
  iconClassName: string;
  ariaLabel?: string;
  spin?: boolean;
}) {
  return (
    <div aria-label={ariaLabel} className="inline-flex items-center gap-1.5">
      <Icon className={cn("h-4 w-4", iconClassName, spin && "animate-spin")} />
      <span className="text-xs text-muted-foreground">{label}</span>
    </div>
  );
}

function benchmarkStatusIndicator(entry: BenchmarkEntry) {
  switch (entry.status) {
    case "idle":
      return <StatusIndicator icon={Clock} label="Waiting" iconClassName="text-muted-foreground" />;
    case "acquiring_molecule":
      return <StatusIndicator icon={Loader2} label="Molecule..." iconClassName="text-info" spin />;
    case "submitting":
      return (
        <StatusIndicator icon={Loader2} label="Submitting..." iconClassName="text-info" spin />
      );
    case "queued":
      return <StatusIndicator icon={Loader2} label="Queued" iconClassName="text-info" spin />;
    case "running":
      return <StatusIndicator icon={Loader2} label="Running" iconClassName="text-warning" spin />;
    case "pausing":
      return <StatusIndicator icon={Loader2} label="Pausing" iconClassName="text-warning" spin />;
    case "paused":
      return <StatusIndicator icon={Pause} label="Paused" iconClassName="text-warning" />;
    case "completed":
      return entry.converged === false ? (
        <StatusIndicator
          icon={AlertCircle}
          label="Done"
          ariaLabel="Done, convergence gate not satisfied"
          iconClassName="text-warning"
        />
      ) : (
        <StatusIndicator icon={CheckCircle2} label="Done" iconClassName="text-success" />
      );
    case "failed":
      return isTimedOutFailureMessage(entry.errorMessage) ? (
        <StatusIndicator icon={Clock} label="Timed out" iconClassName="text-warning" />
      ) : (
        <StatusIndicator icon={XCircle} label="Failed" iconClassName="text-destructive" />
      );
    case "cancelled":
      return (
        <StatusIndicator
          icon={AlertCircle}
          label="Cancelled"
          iconClassName="text-muted-foreground"
        />
      );
    case "planned":
      return <StatusIndicator icon={Clock} label="Planned" iconClassName="text-muted-foreground" />;
    case "excluded":
      return (
        <StatusIndicator icon={XCircle} label="Excluded" iconClassName="text-muted-foreground" />
      );
  }
}

function EnergyCell({ entry }: { entry: BenchmarkEntry }) {
  const { energy, status } = entry;
  const displayEnergy = status === "completed" ? energy : entry.currentEnergy;
  if (displayEnergy === null) {
    return <span className="text-muted-foreground">-</span>;
  }
  return (
    <div className="flex flex-col gap-0.5">
      <span className="font-mono text-sm">{displayEnergy.toFixed(6)} Ha</span>
      {status !== "completed" && <span className="text-[10px] text-warning">current energy</span>}
    </div>
  );
}

function RuntimeCell({ entry }: { entry: BenchmarkEntry }) {
  if (entry.elapsedSeconds === null) {
    return <span className="text-muted-foreground">-</span>;
  }
  return (
    <span className="font-mono text-xs text-muted-foreground">
      {formatDuration(entry.elapsedSeconds)}
    </span>
  );
}

function executionPathLabel(entry: BenchmarkEntry): string {
  const metadata = entry.executionMetadata;
  const pathLabels: Record<string, string> = {
    aer_branch_estimator: "Aer branch estimator",
    aer_pauli_lie_trotter: "Aer statevector evolution",
    aer_primitive: "Aer primitive",
    aer_statevector_evolution: "Aer statevector evolution",
    dense_classical: "Local dense classical",
    sector_matrix_free: "Local matrix-free",
  };
  if (metadata?.actualPathClass && pathLabels[metadata.actualPathClass]) {
    return pathLabels[metadata.actualPathClass];
  }
  switch (metadata?.actualExecutionTarget) {
    case "aer_simulator":
      return "Aer simulator";
    case "ibm_runtime":
      return "IBM Runtime";
    case "local_classical":
      return "Local classical";
    default:
      return "Unknown";
  }
}

function ExecutionPathCell({ entry }: { entry: BenchmarkEntry }) {
  const label = executionPathLabel(entry);
  return (
    <span
      className="text-xs text-muted-foreground"
      title={`Reported execution path: ${label}`}
      aria-label={`Execution path: ${label}`}
    >
      {label}
    </span>
  );
}

function ChemicalAccuracyCell({
  entry,
  chemicalAccuracyHa,
}: {
  entry: BenchmarkEntry;
  chemicalAccuracyHa: number;
}) {
  if (entry.status === "failed") {
    return <span className="text-xs text-muted-foreground">-</span>;
  }
  if (entry.status === "cancelled") {
    return (
      <StatusIndicator
        icon={AlertCircle}
        label="Unscored"
        ariaLabel="Chemical accuracy unavailable: benchmark row cancelled"
        iconClassName="text-muted-foreground"
      />
    );
  }
  if (entry.status !== "completed") {
    return <StatusIndicator icon={Clock} label="Pending" iconClassName="text-muted-foreground" />;
  }
  const assessment = assessBenchmarkEntry(entry, chemicalAccuracyHa);
  if (!assessment.isScorable) {
    return (
      <div className="flex items-center gap-3">
        <StatusIndicator
          icon={AlertCircle}
          label="Unknown"
          iconClassName="text-muted-foreground"
          ariaLabel="Chemical accuracy unknown"
        />
        <span className="text-[10px] text-muted-foreground">No FCI/Exact reference</span>
      </div>
    );
  }
  return (
    <div className="flex items-center gap-3">
      {assessment.verdict === "accurate" ? (
        <StatusIndicator
          icon={CheckCircle2}
          label="Yes"
          iconClassName="text-success"
          ariaLabel="Chemically accurate"
        />
      ) : (
        <StatusIndicator
          icon={XCircle}
          label="No"
          iconClassName="text-destructive"
          ariaLabel="Not chemically accurate"
        />
      )}
      <span className="inline-flex items-center gap-1.5 text-[10px] text-muted-foreground">
        <span
          aria-hidden="true"
          className="inline-flex h-4 w-4 items-center justify-center text-[10px] font-semibold leading-none"
        >
          Δ
        </span>
        <span>{assessment.absErrorMha?.toFixed(2)} mHa</span>
      </span>
    </div>
  );
}

function completedAccuracyState(
  entry: BenchmarkEntry,
  chemicalAccuracyHa: number,
): "green" | "amber" | "red" | null {
  if (entry.status !== "completed" || entry.energy === null) return null;
  const assessment = assessBenchmarkEntry(entry, chemicalAccuracyHa);
  switch (assessment.verdict) {
    case "accurate":
      return "green";
    case "not_accurate":
      return "red";
    case "unscored":
      return "amber";
  }
}

function getDisplayReferences({ preset, rows }: BenchmarkGroupedRows) {
  return (
    rows.find((entry) => entry.classicalRefs)?.classicalRefs ?? {
      hf: preset.references.hf,
      fci: preset.references.fci,
    }
  );
}

function runRowClassName({
  entry,
  chemicalAccuracyHa,
  rowClickable,
}: {
  entry: BenchmarkEntry;
  chemicalAccuracyHa: number;
  rowClickable: boolean;
}) {
  const accuracyState = completedAccuracyState(entry, chemicalAccuracyHa);
  return cn(
    entry.status === "failed" &&
      (isTimedOutFailureMessage(entry.errorMessage) ? "bg-amber-500/10" : "bg-destructive/5"),
    accuracyState === "green" && "bg-green-500/5",
    accuracyState === "amber" && "bg-amber-500/10",
    accuracyState === "red" && "bg-red-500/10",
    rowClickable &&
      "cursor-pointer transition-colors hover:bg-accent/40 focus-visible:bg-accent/40 focus-visible:outline-none",
  );
}

function BenchmarkResultRow({
  entry,
  chemicalAccuracyHa,
  pendingAction = null,
  onRunAction,
  onOpenRun,
}: {
  entry: BenchmarkEntry;
  chemicalAccuracyHa: number;
  pendingAction?: BenchmarkResultsRowAction | null;
  onRunAction?: (entry: BenchmarkEntry, action: BenchmarkResultsRowAction) => void | Promise<void>;
  onOpenRun: OpenRunHandler;
}) {
  const runId = entry.runId;
  const rowClickable = Boolean(runId);

  const handleRowClick = () => {
    if (!runId) return;
    onOpenRun(runId);
  };

  const handleRowKeyDown = (event: KeyboardEvent<HTMLTableRowElement>) => {
    if (!runId) return;
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    onOpenRun(runId);
  };

  return (
    <TableRow
      key={entry.id}
      className={runRowClassName({ entry, chemicalAccuracyHa, rowClickable })}
      tabIndex={rowClickable ? 0 : undefined}
      onClick={handleRowClick}
      onKeyDown={handleRowKeyDown}
    >
      <TableCell>
        <div className="space-y-0.5">
          <span className="font-mono text-xs font-semibold uppercase tracking-[0.12em]">
            {entry.algorithm}
          </span>
          <p className="text-[11px] text-muted-foreground">
            {entry.variantLabel ?? entry.algorithm.toUpperCase()}
          </p>
        </div>
      </TableCell>
      <TableCell>
        {benchmarkStatusIndicator(entry)}
        {entry.errorMessage && (
          <p className="text-[10px] text-destructive mt-0.5 max-w-[220px] line-clamp-3 whitespace-normal">
            {entry.errorMessage}
          </p>
        )}
      </TableCell>
      <TableCell>
        <EnergyCell entry={entry} />
      </TableCell>
      <TableCell>
        <RuntimeCell entry={entry} />
      </TableCell>
      <TableCell>
        <ExecutionPathCell entry={entry} />
      </TableCell>
      <TableCell>
        <ChemicalAccuracyCell entry={entry} chemicalAccuracyHa={chemicalAccuracyHa} />
      </TableCell>
      <TableCell>
        {runId && (
          <Link
            to="/runs/$runId"
            params={{ runId }}
            className="text-xs text-primary hover:underline font-mono"
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
              onOpenRun(runId);
            }}
          >
            {runId.slice(0, 6)}...
          </Link>
        )}
      </TableCell>
      <TableCell className="w-12">
        {onRunAction && (runId || entry.status === "failed") ? (
          <BenchmarkResultRowActions
            entry={entry}
            pendingAction={pendingAction}
            onRunAction={onRunAction}
          />
        ) : null}
      </TableCell>
    </TableRow>
  );
}

function BenchmarkResultGroup({
  preset,
  rows,
  selectedBasis,
  chemicalAccuracyHa,
  pendingAction = null,
  onRunAction,
  onOpenRun,
}: BenchmarkGroupedRows &
  Pick<
    BenchmarkResultsTableProps,
    "selectedBasis" | "chemicalAccuracyHa" | "pendingAction" | "onRunAction"
  > & {
    onOpenRun: OpenRunHandler;
  }) {
  const displayRefs = getDisplayReferences({ preset, rows });

  return (
    <div key={preset.key} className={cn("overflow-hidden rounded-xl", containerSurfaceClassName)}>
      <div className="flex flex-col gap-3 border-b border-border/70 bg-muted/25 px-5 py-4 md:flex-row md:items-end md:justify-between">
        <div className="flex min-w-0 flex-1 items-end gap-3 overflow-hidden">
          <span
            title={preset.formula}
            className="min-w-0 flex-1 truncate text-lg font-semibold tracking-tight"
          >
            {preset.formula}
          </span>
          <span
            title={preset.name}
            className="max-w-[16rem] shrink-0 truncate text-sm text-muted-foreground"
          >
            {preset.name}
          </span>
          <span className="shrink-0 font-mono text-[11px] uppercase tracking-[0.12em] text-muted-foreground">
            {selectedBasis}
          </span>
        </div>
        <div className="flex flex-wrap items-end gap-x-4 gap-y-1 text-xs text-muted-foreground md:shrink-0 md:justify-end">
          {displayRefs.hf !== 0 && <span>HF: {displayRefs.hf.toFixed(5)} Ha</span>}
          {displayRefs.fci !== null && <span>Ref: {displayRefs.fci.toFixed(5)} Ha</span>}
          {displayRefs.fci !== null && displayRefs.hf !== 0 && (
            <span>Corr: {((displayRefs.fci - displayRefs.hf) * 1000).toFixed(1)} mHa</span>
          )}
        </div>
      </div>

      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent data-[state=selected]:bg-transparent">
            <TableHead className="w-20">Algorithm</TableHead>
            <TableHead className="w-28">Status</TableHead>
            <TableHead>Energy (Ha)</TableHead>
            <TableHead className="w-28">Runtime</TableHead>
            <TableHead className="w-36">Execution path</TableHead>
            <TableHead className="w-48">Chemical accurate</TableHead>
            <TableHead className="w-16">Run</TableHead>
            <TableHead className="w-12 text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((entry) => (
            <BenchmarkResultRow
              key={entry.id}
              entry={entry}
              chemicalAccuracyHa={chemicalAccuracyHa}
              pendingAction={pendingAction}
              onRunAction={onRunAction}
              onOpenRun={onOpenRun}
            />
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

export function BenchmarkResultsTable({
  grouped,
  selectedBasis,
  chemicalAccuracyHa,
  pendingAction = null,
  onRunAction,
  onBeforeOpenRun,
}: BenchmarkResultsTableProps) {
  const navigate = useNavigate();
  const openRun: OpenRunHandler = (runId) => {
    onBeforeOpenRun?.();
    void navigate({ to: "/runs/$runId", params: { runId } });
  };

  if (grouped.length === 0) {
    return (
      <div className="rounded-lg border bg-card px-4 py-8 text-center text-sm text-muted-foreground">
        No benchmark rows match the current accuracy filter.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {grouped.map((group) =>
        group.rows.length === 0 ? null : (
          <BenchmarkResultGroup
            key={group.preset.key}
            {...group}
            selectedBasis={selectedBasis}
            chemicalAccuracyHa={chemicalAccuracyHa}
            pendingAction={pendingAction}
            onRunAction={onRunAction}
            onOpenRun={openRun}
          />
        ),
      )}
    </div>
  );
}
