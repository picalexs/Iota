import { DashboardTile } from "@/components/results/dashboard-tile";
import { ChartEmptyState } from "@/components/results/charts/chart-empty-state";
import { ChartLegend } from "@/components/results/charts/chart-legend";
import { LinePlot, type LinePlotPoint } from "@/components/results/charts/line-plot";
import { useChartTheme } from "@/components/results/charts/use-chart-theme";
import {
  subspaceGrowthFromEvents,
  type SubspaceGrowthAlgorithm,
} from "@/lib/results/subspace-growth";
import type { RunEventResponse } from "@/types/run";

interface SubspaceGrowthTileProps {
  readonly algorithm: SubspaceGrowthAlgorithm;
  readonly events: RunEventResponse[];
  readonly finalEnergy?: number | null;
  readonly isRunning?: boolean;
  readonly editMode?: boolean;
}

const TILE_COPY: Record<
  SubspaceGrowthAlgorithm,
  { title: string; xLabel: string; helpText: string }
> = {
  kqd: {
    title: "Krylov Growth",
    xLabel: "Krylov rank",
    helpText:
      "Tracks the lowest projected energy as the KQD basis grows. A flat tail usually means additional Krylov vectors are no longer adding much low-energy information.",
  },
  qfd: {
    title: "Filter Build",
    xLabel: "Time points",
    helpText:
      "Tracks the lowest projected energy as QFD accumulates its time-grid states. Useful for seeing whether more filter points are still improving the projected chemistry.",
  },
  qse: {
    title: "Subspace Growth",
    xLabel: "Subspace dim",
    helpText:
      "Tracks the lowest projected energy as the QSE basis expands. It helps separate real reference corrections from subspace sizes that only add conditioning cost.",
  },
  skqd: {
    title: "Extension Growth",
    xLabel: "Extension rank",
    helpText:
      "Tracks the selected Krylov-extension energy as SKQD grows beyond its SQD seed. A quick plateau usually means the extension has captured most of the useful correction already.",
  },
};

function integerTick(value: number): string {
  return String(Math.round(value));
}

function buildTooltipLines(point: ReturnType<typeof subspaceGrowthFromEvents>[number]): string[] {
  const lines: string[] = [];
  if (point.timePoint !== undefined) {
    lines.push(`t = ${point.timePoint.toFixed(3)}`);
  }
  if (point.relativeResidual !== undefined) {
    lines.push(`rel residual ${point.relativeResidual.toExponential(2)}`);
  }
  return lines;
}

function finalEnergyReference(finalEnergy: number | null | undefined, color: string) {
  if (finalEnergy != null) {
    return [
      {
        y: finalEnergy,
        label: `Final ${finalEnergy.toFixed(5)} Ha`,
        color,
        dashed: true,
      },
    ];
  }
  return undefined;
}

function finalEnergyLegendItem(finalEnergy: number | null | undefined, color: string) {
  if (finalEnergy != null) {
    return [
      {
        label: `Final ${finalEnergy.toFixed(5)} Ha`,
        color,
        dashed: true,
      },
    ];
  }
  return [];
}

export function SubspaceGrowthTile({
  algorithm,
  events,
  finalEnergy,
  isRunning = false,
  editMode,
}: Readonly<SubspaceGrowthTileProps>) {
  const theme = useChartTheme();
  const copy = TILE_COPY[algorithm];
  const trace = subspaceGrowthFromEvents(events, algorithm);

  const data: LinePlotPoint[] = trace.map((point) => ({
    x: point.stepIndex,
    y: point.energy,
    displayY: point.energy,
    tooltipTitle: `${copy.title} · ${copy.xLabel.toLowerCase()} ${point.stepIndex}`,
    tooltipValue: `${point.energy.toFixed(6)} Ha`,
    tooltipLines: buildTooltipLines(point),
  }));
  const referenceLines = finalEnergyReference(finalEnergy, theme.chart3);
  const legendItems = [
    { label: "Projected energy", color: theme.chart1 },
    ...finalEnergyLegendItem(finalEnergy, theme.chart3),
  ];

  return (
    <DashboardTile title={copy.title} helpText={copy.helpText} editMode={editMode}>
      <div className="flex h-full min-h-0 flex-col gap-2">
        {data.length === 0 ? (
          <ChartEmptyState
            message="No subspace-growth trace recorded yet"
            pending={isRunning}
            pendingMessage="Awaiting subspace-growth trace"
          />
        ) : (
          <>
            <div className="min-h-0 flex-1">
              <LinePlot
                data={data}
                xLabel={copy.xLabel}
                yLabel="Energy (Ha)"
                xTickFormat={integerTick}
                yTickFormat={(value) => value.toFixed(5)}
                referenceLines={referenceLines}
                primarySeriesLabel={copy.title}
              />
            </div>
            <ChartLegend items={legendItems} />
          </>
        )}
      </div>
    </DashboardTile>
  );
}
