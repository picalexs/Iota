import { DashboardTile } from "@/components/results/dashboard-tile";
import { BarPlot, type BarDatum } from "@/components/results/charts/bar-plot";
import { ChartEmptyState } from "@/components/results/charts/chart-empty-state";
import type { SqdMetrics } from "@/lib/results/parse-algorithm-metrics";

interface SqdOccupancyTileProps {
  readonly metrics: SqdMetrics;
  readonly isRunning?: boolean;
  readonly editMode?: boolean;
}

function asNumberArray(value: unknown): number[] {
  if (!Array.isArray(value)) return [];
  return value.filter((entry): entry is number => typeof entry === "number");
}

function labelOccupancies(values: number[]): BarDatum[] {
  if (values.length === 0) return [];

  const half = values.length / 2;
  const isBalancedSpinVector = Number.isInteger(half) && half > 0;

  if (!isBalancedSpinVector) {
    return values.map((value, index) => ({
      label: `o${index + 1}`,
      value,
    }));
  }

  return values.map((value, index) => ({
    label: index < half ? `α${index}` : `β${index - half}`,
    value,
  }));
}

function extractOccupancies(metrics: SqdMetrics): BarDatum[] {
  const resultPackageOccupancies = asNumberArray(metrics.sci_result_package?.["best_occupancies"]);
  if (resultPackageOccupancies.length > 0) {
    return labelOccupancies(resultPackageOccupancies);
  }

  const finalOccupancies = asNumberArray(metrics.sci_result_package?.["final_occupancies"]);
  if (finalOccupancies.length > 0) {
    return labelOccupancies(finalOccupancies);
  }

  const spinDiagnostics = metrics.spin_diagnostics;
  if (!spinDiagnostics) return [];

  const alpha = asNumberArray(spinDiagnostics["alpha_occupancies"]);
  const beta = asNumberArray(spinDiagnostics["beta_occupancies"]);
  return labelOccupancies([...alpha, ...beta]);
}

export function SqdOccupancyTile({ metrics, isRunning = false, editMode }: SqdOccupancyTileProps) {
  const bars = extractOccupancies(metrics);

  return (
    <DashboardTile
      title="Orbital Occupancies"
      helpText="Alpha and beta orbital occupancies from the reported SQD iteration when available, with final-iteration and spin-diagnostic fallbacks."
      editMode={editMode}
    >
      <div className="h-full min-h-0">
        {bars.length > 0 ? (
          <BarPlot data={bars} yLabel="Occupancy" avoidValueLabelOverlap />
        ) : (
          <ChartEmptyState
            message="No occupancy data available"
            pending={isRunning}
            pendingMessage="Awaiting occupancy data"
          />
        )}
      </div>
    </DashboardTile>
  );
}
