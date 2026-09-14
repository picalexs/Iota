import { DashboardTile } from "@/components/results/dashboard-tile";
import { SpectrumLadder } from "@/components/results/charts/spectrum-ladder";
import { ChartEmptyState } from "@/components/results/charts/chart-empty-state";
import type { QseMetrics } from "@/lib/results/parse-algorithm-metrics";

interface QseSubspaceTileProps {
  readonly metrics: QseMetrics;
  readonly isRunning?: boolean;
  readonly editMode?: boolean;
}

function formatMaybeNumber(value: number | null, digits = 6): string {
  return value == null ? "-" : value.toFixed(digits);
}

function formatResidual(value: number | null): string {
  return value == null ? "-" : value.toExponential(2);
}

export function QseSubspaceTile({ metrics, isRunning = false, editMode }: QseSubspaceTileProps) {
  return (
    <DashboardTile
      title="QSE Subspace"
      helpText="Projected QSE eigenspectrum and the reference-state diagnostics used for the solve."
      editMode={editMode}
    >
      <div className="flex h-full min-h-0 flex-col gap-3">
        <div className="min-h-0 flex-1">
          {metrics.eigenvalues.length > 0 ? (
            <SpectrumLadder
              energies={metrics.eigenvalues}
              referenceEnergy={metrics.reference_state_energy ?? undefined}
              highlightedIndex={0}
            />
          ) : (
            <ChartEmptyState
              message="No subspace eigenvalues recorded"
              pending={isRunning}
              pendingMessage="Awaiting subspace eigenvalues"
            />
          )}
        </div>
        <div className="flex shrink-0 flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <span>Subspace dim: {metrics.eigenvalues.length}</span>
          <span>Ref energy: {formatMaybeNumber(metrics.reference_state_energy)} Ha</span>
          <span>Overlap cond: {formatResidual(metrics.overlap_condition)}</span>
          <span>Residual: {formatResidual(metrics.relative_residual)}</span>
        </div>
      </div>
    </DashboardTile>
  );
}
