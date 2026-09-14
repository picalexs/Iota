import { DashboardTile } from "@/components/results/dashboard-tile";
import { SpectrumLadder } from "@/components/results/charts/spectrum-ladder";
import { ChartEmptyState } from "@/components/results/charts/chart-empty-state";
import { WorkflowRail } from "@/components/results/workflow-rail";
import type { QfdMetrics } from "@/lib/results/parse-algorithm-metrics";

interface QfdSpectrumTileProps {
  readonly metrics: QfdMetrics;
  readonly isRunning?: boolean;
  readonly editMode?: boolean;
}

function numberMetric(record: Record<string, unknown> | null, key: string): number | null {
  const value = record?.[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function formatResidual(value: number | null): string {
  return value == null ? "-" : value.toExponential(2);
}

function formatMaybeNumber(value: number | null, digits = 3): string {
  return value == null ? "-" : value.toFixed(digits);
}

function formatSolveHint(maxTime: number | null): string {
  if (maxTime == null) {
    return "Projected eigensystem";
  }
  return `Tmax ${formatMaybeNumber(maxTime)}`;
}

function suppressionNote(metrics: QfdMetrics): string | null {
  const state = metrics.stability_summary?.["stability_state"];
  const droppedRank = metrics.stability_summary?.["dropped_rank"];
  const rawCount = metrics.raw_filter_eigenvalues.length;
  if (
    (typeof droppedRank === "number" && droppedRank > 0) ||
    state === "stabilized" ||
    rawCount > metrics.filter_eigenvalues.length
  ) {
    return "Raw unstable levels hidden after overlap stabilization.";
  }
  return null;
}

export function QfdSpectrumTile({ metrics, isRunning = false, editMode }: QfdSpectrumTileProps) {
  const conditioning = metrics.conditioning_summary;
  const overlapCondition = numberMetric(conditioning, "overlap_condition");
  const relativeResidual =
    numberMetric(conditioning, "relative_ritz_residual") ??
    numberMetric(conditioning, "relative_residual");
  const maxTime = numberMetric(conditioning, "max_time");
  const note = suppressionNote(metrics);

  return (
    <DashboardTile
      title="QFD Spectrum"
      helpText="Filter-diagonalization spectrum with the dense classical time-grid workflow shown directly underneath."
      editMode={editMode}
    >
      <div className="flex h-full min-h-0 flex-col gap-3">
        <div className="min-h-0 flex-1">
          {metrics.filter_eigenvalues.length > 0 ? (
            <SpectrumLadder energies={metrics.filter_eigenvalues} />
          ) : (
            <ChartEmptyState
              message="No filter eigenvalues recorded"
              pending={isRunning}
              pendingMessage="Awaiting filter eigenvalues"
            />
          )}
        </div>
        <WorkflowRail
          steps={[
            {
              label: "Reference",
              value: "HF state",
              hint: "Anchor the filter window",
            },
            {
              label: "Sample",
              value: "Time grid",
              hint: `${metrics.filter_eigenvalues.length} points`,
            },
            {
              label: "Solve",
              value: "Filtered subspace",
              hint: formatSolveHint(maxTime),
            },
          ]}
        />
        <div className="flex shrink-0 flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <span>Time points: {metrics.filter_eigenvalues.length}</span>
          <span>Overlap cond: {formatResidual(overlapCondition)}</span>
          <span>Residual: {formatResidual(relativeResidual)}</span>
          <span>Max time: {formatMaybeNumber(maxTime)}</span>
        </div>
        {note ? <p className="text-xs text-muted-foreground">{note}</p> : null}
      </div>
    </DashboardTile>
  );
}
