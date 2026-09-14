import { DashboardTile } from "@/components/results/dashboard-tile";
import { SpectrumLadder } from "@/components/results/charts/spectrum-ladder";
import { ChartEmptyState } from "@/components/results/charts/chart-empty-state";
import { WorkflowRail } from "@/components/results/workflow-rail";
import type { KqdMetrics } from "@/lib/results/parse-algorithm-metrics";

interface KqdRitzTileProps {
  readonly metrics: KqdMetrics;
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

function suppressionNote(metrics: KqdMetrics): string | null {
  const state = metrics.stability_summary?.["stability_state"];
  const droppedRank = metrics.stability_summary?.["dropped_rank"];
  const rawCount = metrics.raw_ritz_values.length;
  if (
    (typeof droppedRank === "number" && droppedRank > 0) ||
    state === "stabilized" ||
    rawCount > metrics.ritz_values.length
  ) {
    return "Raw unstable levels hidden after overlap stabilization.";
  }
  return null;
}

export function KqdRitzTile({ metrics, isRunning = false, editMode }: KqdRitzTileProps) {
  const orthogonality = metrics.orthogonality_metrics;
  const overlapCondition = numberMetric(orthogonality, "overlap_condition");
  const relativeResidual =
    numberMetric(orthogonality, "relative_ritz_residual") ??
    numberMetric(orthogonality, "relative_residual");
  const note = suppressionNote(metrics);

  return (
    <DashboardTile
      title="KQD Ritz Values"
      helpText="Krylov-space Ritz spectrum and workflow diagnostics for the projected solve."
      editMode={editMode}
    >
      <div className="flex h-full min-h-0 flex-col gap-3">
        <div className="min-h-0 flex-1">
          {metrics.ritz_values.length > 0 ? (
            <SpectrumLadder energies={metrics.ritz_values} />
          ) : (
            <ChartEmptyState
              message="No Ritz values recorded"
              pending={isRunning}
              pendingMessage="Awaiting Ritz values"
            />
          )}
        </div>
        <WorkflowRail
          steps={[
            {
              label: "Reference",
              value: "HF state",
              hint: "Initialize the Krylov seed",
            },
            {
              label: "Evolve",
              value: "Time propagation",
              hint: "Build Krylov basis vectors",
            },
            {
              label: "Solve",
              value: "Projected Ritz solve",
              hint: `Rank ${metrics.krylov_rank}`,
            },
          ]}
        />
        <div className="flex shrink-0 flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <span>Krylov rank: {metrics.krylov_rank}</span>
          <span>Overlap cond: {formatResidual(overlapCondition)}</span>
          <span>Residual: {formatResidual(relativeResidual)}</span>
        </div>
        {note ? <p className="text-xs text-muted-foreground">{note}</p> : null}
      </div>
    </DashboardTile>
  );
}
