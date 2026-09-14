import { DashboardTile } from "@/components/results/dashboard-tile";
import { BarPlot, type BarDatum } from "@/components/results/charts/bar-plot";
import { ChartEmptyState } from "@/components/results/charts/chart-empty-state";

interface SpectralGapsTileProps {
  readonly title?: string;
  readonly helpText?: string;
  readonly energies: number[];
  readonly isRunning?: boolean;
  readonly editMode?: boolean;
}

function buildGapBars(energies: number[]): BarDatum[] {
  if (energies.length < 2) return [];
  const ground = energies[0];
  if (ground === undefined) return [];
  return energies.slice(1, 6).map((energy, index) => ({
    label: `ΔE${index + 1}`,
    value: Number((energy - ground).toFixed(6)),
    isHighlight: index === 0,
  }));
}

function firstGapSummary(firstGap: number | null) {
  if (firstGap == null) {
    return null;
  }
  return <p className="mt-2 text-xs text-muted-foreground">First gap: {firstGap.toFixed(6)} Ha</p>;
}

export function SpectralGapsTile({
  title = "Excitation Gaps",
  helpText = "Energy gaps relative to the lowest projected state. In chemistry, gaps are often easier to compare across methods than absolute excited-state energies alone.",
  energies,
  isRunning = false,
  editMode,
}: SpectralGapsTileProps) {
  const gapBars = buildGapBars(energies);
  const firstGap = gapBars[0]?.value ?? null;

  return (
    <DashboardTile title={title} helpText={helpText} editMode={editMode}>
      <div className="h-full min-h-0">
        {gapBars.length === 0 ? (
          <ChartEmptyState
            message="Need at least two projected levels to plot gaps"
            pending={isRunning}
            pendingMessage="Awaiting projected levels"
          />
        ) : (
          <BarPlot data={gapBars} yLabel="Gap (Ha)" avoidValueLabelOverlap />
        )}
      </div>
      {firstGapSummary(firstGap)}
    </DashboardTile>
  );
}
