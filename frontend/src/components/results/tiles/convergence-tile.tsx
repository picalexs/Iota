import { useState, type ComponentProps, type ReactNode } from "react";
import { DashboardTile } from "@/components/results/dashboard-tile";
import {
  LinePlot,
  type LinePlotPoint,
  type ReferenceLineSpec,
} from "@/components/results/charts/line-plot";
import { ChartLegend } from "@/components/results/charts/chart-legend";
import { ChartEmptyState } from "@/components/results/charts/chart-empty-state";
import { useChartTheme } from "@/components/results/charts/use-chart-theme";
import { ConvergenceTileLoadingContent } from "@/components/results/tile-loading-content";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { RunEventResponse, RunResultResponse } from "@/types/run";
import { mergeConvergenceTrace } from "@/lib/results/convergence-from-events";

const formatIterationTick = (value: number) => String(Math.round(value));
const LOG_DELTA_FLOOR = 1e-8;
const formatLogDeltaTick = (value: number) => value.toFixed(3);

type EnergyAxisMode = "linear" | "log_delta";
type ChartTheme = ReturnType<typeof useChartTheme>;
type EnergySeriesPoint = { readonly x: number; readonly energy: number };
type LegendItem = ComponentProps<typeof ChartLegend>["items"][number];
type ConvergenceModel = ReturnType<typeof buildConvergenceModel>;
type EnergyPoint = { readonly iteration: number; readonly energy: number };

function buildIterationTicks(data: LinePlotPoint[]): number[] | undefined {
  if (data.length === 0) return undefined;

  const min = Math.ceil(Math.min(...data.map((point) => point.x)));
  const max = Math.floor(Math.max(...data.map((point) => point.x)));
  const firstPoint = data[0];
  if (!firstPoint) return undefined;
  if (max < min) return [Math.round(firstPoint.x)];

  const step = Math.max(1, Math.ceil((max - min) / 4));
  const ticks: number[] = [];
  for (let tick = min; tick <= max; tick += step) {
    ticks.push(tick);
  }
  if (ticks.at(-1) !== max) ticks.push(max);
  return ticks;
}

interface ConvergenceTileProps {
  readonly events: RunEventResponse[];
  readonly result: RunResultResponse | null;
  readonly algorithm?: string;
  readonly hfEnergy?: number;
  readonly fciEnergy?: number;
  readonly chemicalAccuracyHa?: number;
  readonly isRunning?: boolean;
  readonly pending?: boolean;
  readonly editMode?: boolean;
}

interface ChartControlGroupProps {
  readonly label: string;
  readonly children: ReactNode;
}

function ChartControlGroup({ label, children }: ChartControlGroupProps) {
  return (
    <div className="flex flex-wrap items-center gap-1 rounded-lg border border-border/60 bg-muted/20 p-1">
      <span className="px-1 text-[10px] font-medium uppercase tracking-[0.08em] text-muted-foreground">
        {label}
      </span>
      {children}
    </div>
  );
}

function ChartToggleButton({
  active,
  children,
  ...props
}: ComponentProps<typeof Button> &
  Readonly<{
    readonly active: boolean;
  }>) {
  return (
    <Button
      type="button"
      size="xs"
      variant="ghost"
      className={cn(
        "h-6 rounded-md px-2.5 text-[11px] shadow-none transition-colors hover:scale-100 hover:shadow-none active:scale-100",
        active
          ? "border border-border/70 bg-background text-foreground hover:bg-background"
          : "border border-transparent bg-transparent text-muted-foreground hover:bg-background/70 hover:text-foreground",
      )}
      aria-pressed={active}
      {...props}
    >
      {children}
    </Button>
  );
}

function shouldShowRawByDefault(algorithm?: string) {
  return algorithm !== "qse";
}

function buildBestEnergyTrace(points: EnergyPoint[]): EnergySeriesPoint[] {
  let runMin = Number.POSITIVE_INFINITY;
  return points.map((point) => {
    if (point.energy < runMin) {
      runMin = point.energy;
    }
    return { x: point.iteration, energy: runMin };
  });
}

function buildRawEnergyTrace(points: EnergyPoint[]): EnergySeriesPoint[] {
  return points.map((point) => ({ x: point.iteration, energy: point.energy }));
}

function getDeltaAxisLabels(fciEnergy: number | undefined) {
  if (fciEnergy === undefined) {
    return {
      deltaLabel: "|ΔE|",
      logAxisLabel: "log10|ΔE|",
      logReferenceLabel: "best visible energy",
    };
  }

  return {
    deltaLabel: "|E-CASCI|",
    logAxisLabel: "log10|E-CASCI|",
    logReferenceLabel: "CASCI active-space",
  };
}

function buildDeltaTooltipLines({
  delta,
  deltaLabel,
  logReferenceLabel,
  mode,
  logDelta,
}: {
  readonly delta: number | null;
  readonly deltaLabel: string;
  readonly logReferenceLabel: string;
  readonly mode: EnergyAxisMode;
  readonly logDelta: number;
}): string[] {
  const lines: string[] = [];
  if (delta !== null) {
    lines.push(`${deltaLabel} ${delta.toExponential(2)} Ha vs ${logReferenceLabel}`);
  }
  if (mode === "log_delta") {
    lines.push(`log10 ${deltaLabel} ${logDelta.toFixed(2)}`);
  }
  return lines;
}

function absoluteDeltaToReference(energy: number, reference: number | null): number | null {
  if (reference === null) {
    return null;
  }
  return Math.abs(energy - reference);
}

function buildPlotSeries({
  series,
  seriesLabel,
  mode,
  deltaReference,
  deltaLabel,
  logReferenceLabel,
}: {
  readonly series: EnergySeriesPoint[];
  readonly seriesLabel: string;
  readonly mode: EnergyAxisMode;
  readonly deltaReference: number | null;
  readonly deltaLabel: string;
  readonly logReferenceLabel: string;
}): LinePlotPoint[] {
  return series.map((point) => {
    const delta = absoluteDeltaToReference(point.energy, deltaReference);
    const logDelta = Math.log10(Math.max(delta ?? LOG_DELTA_FLOOR, LOG_DELTA_FLOOR));

    return {
      x: point.x,
      y: mode === "linear" ? point.energy : logDelta,
      displayY: point.energy,
      tooltipTitle: `${seriesLabel} · iter ${formatIterationTick(point.x)}`,
      tooltipValue: `${point.energy.toFixed(6)} Ha`,
      tooltipLines: buildDeltaTooltipLines({
        delta,
        deltaLabel,
        logReferenceLabel,
        mode,
        logDelta,
      }),
    };
  });
}

function buildReferenceLines(
  hfEnergy: number | undefined,
  fciEnergy: number | undefined,
  theme: ChartTheme,
): ReferenceLineSpec[] {
  const lines: ReferenceLineSpec[] = [];

  if (hfEnergy !== undefined) {
    lines.push({
      y: hfEnergy,
      label: `HF ${hfEnergy.toFixed(5)} Ha`,
      color: theme.muted,
      dashed: true,
    });
  }

  if (fciEnergy !== undefined) {
    lines.push({
      y: fciEnergy,
      label: `CASCI ${fciEnergy.toFixed(5)} Ha`,
      color: theme.chart3,
      dashed: true,
    });
  }

  return lines;
}

function buildLegendItems({
  energyAxisMode,
  showProbes,
  logAxisLabel,
  hfEnergy,
  fciEnergy,
  theme,
}: {
  readonly energyAxisMode: EnergyAxisMode;
  readonly showProbes: boolean;
  readonly logAxisLabel: string;
  readonly hfEnergy: number | undefined;
  readonly fciEnergy: number | undefined;
  readonly theme: ChartTheme;
}) {
  const items: LegendItem[] = [
    {
      label: energyAxisMode === "linear" ? "Best so far" : `Best so far (${logAxisLabel})`,
      color: theme.chart1,
    },
  ];

  if (showProbes) {
    items.push({ label: "Raw evaluations", color: theme.muted });
  }

  if (energyAxisMode === "linear" && hfEnergy !== undefined) {
    items.push({ label: `HF ${hfEnergy.toFixed(5)} Ha`, color: theme.muted, dashed: true });
  }

  if (energyAxisMode === "linear" && fciEnergy !== undefined) {
    items.push({
      label: `CASCI active-space ${fciEnergy.toFixed(5)} Ha`,
      color: theme.chart3,
      dashed: true,
    });
  }

  return items;
}

function buildConvergenceModel({
  events,
  result,
  showAll,
  energyAxisMode,
  showProbes,
  hfEnergy,
  fciEnergy,
  theme,
}: {
  readonly events: RunEventResponse[];
  readonly result: RunResultResponse | null;
  readonly showAll: boolean;
  readonly energyAxisMode: EnergyAxisMode;
  readonly showProbes: boolean;
  readonly hfEnergy: number | undefined;
  readonly fciEnergy: number | undefined;
  readonly theme: ChartTheme;
}) {
  const allPoints = mergeConvergenceTrace(events, result?.algorithm_metrics ?? null);
  const visiblePoints = showAll ? allPoints : allPoints.slice(-50);
  const bestEnergyTrace = buildBestEnergyTrace(visiblePoints);
  const rawEnergyTrace = buildRawEnergyTrace(visiblePoints);
  const iterationTickValues = buildIterationTicks(
    bestEnergyTrace.map((point) => ({ x: point.x, y: point.energy })),
  );
  const bestEnergy =
    visiblePoints.length > 0 ? Math.min(...visiblePoints.map((point) => point.energy)) : null;
  const deltaReference = fciEnergy ?? bestEnergy;
  const { deltaLabel, logAxisLabel, logReferenceLabel } = getDeltaAxisLabels(fciEnergy);

  const bestSoFarData = buildPlotSeries({
    series: bestEnergyTrace,
    seriesLabel: "Best so far",
    mode: energyAxisMode,
    deltaReference,
    deltaLabel,
    logReferenceLabel,
  });
  const rawData = buildPlotSeries({
    series: rawEnergyTrace,
    seriesLabel: "Raw evaluations",
    mode: energyAxisMode,
    deltaReference,
    deltaLabel,
    logReferenceLabel,
  });
  const logDeltaData = buildPlotSeries({
    series: bestEnergyTrace,
    seriesLabel: "Best so far",
    mode: "log_delta",
    deltaReference,
    deltaLabel,
    logReferenceLabel,
  });
  const logDeltaRawData = buildPlotSeries({
    series: rawEnergyTrace,
    seriesLabel: "Raw evaluations",
    mode: "log_delta",
    deltaReference,
    deltaLabel,
    logReferenceLabel,
  });

  return {
    allPoints,
    bestEnergy,
    bestSoFarData,
    rawData,
    logDeltaData,
    logDeltaRawData,
    logAxisLabel,
    iterationTickValues,
    referenceLines: buildReferenceLines(hfEnergy, fciEnergy, theme),
    legend: buildLegendItems({
      energyAxisMode,
      showProbes,
      logAxisLabel,
      hfEnergy,
      fciEnergy,
      theme,
    }),
  };
}

function ConvergenceControls({
  energyAxisMode,
  showProbes,
  showAll,
  showWindowToggle,
  onEnergyAxisModeChange,
  onShowProbesChange,
  onShowAllChange,
}: Readonly<{
  readonly energyAxisMode: EnergyAxisMode;
  readonly showProbes: boolean;
  readonly showAll: boolean;
  readonly showWindowToggle: boolean;
  readonly onEnergyAxisModeChange: (mode: EnergyAxisMode) => void;
  readonly onShowProbesChange: (show: boolean) => void;
  readonly onShowAllChange: (show: boolean) => void;
}>) {
  return (
    <div className="flex flex-wrap items-center justify-center gap-2">
      <ChartControlGroup label="Y axis">
        <ChartToggleButton
          active={energyAxisMode === "linear"}
          onClick={() => onEnergyAxisModeChange("linear")}
        >
          Linear
        </ChartToggleButton>
        <ChartToggleButton
          active={energyAxisMode === "log_delta"}
          onClick={() => onEnergyAxisModeChange("log_delta")}
        >
          Log scale
        </ChartToggleButton>
      </ChartControlGroup>
      <ChartControlGroup label="Trace">
        <ChartToggleButton active={showProbes} onClick={() => onShowProbesChange(true)}>
          Best + raw
        </ChartToggleButton>
        <ChartToggleButton active={showProbes === false} onClick={() => onShowProbesChange(false)}>
          Best only
        </ChartToggleButton>
      </ChartControlGroup>
      {showWindowToggle ? (
        <ChartControlGroup label="Window">
          <ChartToggleButton active={showAll} onClick={() => onShowAllChange(true)}>
            All
          </ChartToggleButton>
          <ChartToggleButton active={showAll === false} onClick={() => onShowAllChange(false)}>
            Last 50
          </ChartToggleButton>
        </ChartControlGroup>
      ) : null}
    </div>
  );
}

function mainPlotReferenceLines(
  model: ConvergenceModel,
  energyAxisMode: EnergyAxisMode,
): ReferenceLineSpec[] | undefined {
  if (energyAxisMode !== "linear" || model.referenceLines.length === 0) {
    return undefined;
  }
  return model.referenceLines;
}

function MainConvergencePlot({
  model,
  energyAxisMode,
  showProbes,
}: Readonly<{
  readonly model: ConvergenceModel;
  readonly energyAxisMode: EnergyAxisMode;
  readonly showProbes: boolean;
}>) {
  return (
    <div className="flex-1 min-h-0">
      <LinePlot
        data={model.bestSoFarData}
        secondaryData={showProbes ? model.rawData : undefined}
        xLabel="Iteration"
        yLabel={energyAxisMode === "linear" ? "Energy (Ha)" : model.logAxisLabel}
        xTickFormat={formatIterationTick}
        xTickValues={model.iterationTickValues}
        yTickFormat={energyAxisMode === "linear" ? (value) => value.toFixed(5) : formatLogDeltaTick}
        referenceLines={mainPlotReferenceLines(model, energyAxisMode)}
        primarySeriesLabel="Best so far"
        secondarySeriesLabel="Raw evaluations"
      />
    </div>
  );
}

function logDeltaAccuracyBand({
  fciEnergy,
  bestEnergy,
  chemicalAccuracyHa,
}: Readonly<{
  readonly fciEnergy: number | undefined;
  readonly bestEnergy: number | null;
  readonly chemicalAccuracyHa: number | undefined;
}>) {
  if (fciEnergy === undefined || bestEnergy === null) {
    return undefined;
  }
  return {
    center: Math.log10(chemicalAccuracyHa ?? 1.6e-3),
    halfWidth: 0.15,
  };
}

function SecondaryLogDeltaPlot({
  model,
  showProbes,
  fciEnergy,
  chemicalAccuracyHa,
}: Readonly<{
  readonly model: ConvergenceModel;
  readonly showProbes: boolean;
  readonly fciEnergy: number | undefined;
  readonly chemicalAccuracyHa: number | undefined;
}>) {
  return (
    <div className="flex-1 min-h-0">
      <LinePlot
        data={model.logDeltaData}
        secondaryData={showProbes ? model.logDeltaRawData : undefined}
        xLabel="Iteration"
        yLabel={model.logAxisLabel}
        xTickFormat={formatIterationTick}
        xTickValues={model.iterationTickValues}
        yTickFormat={formatLogDeltaTick}
        primarySeriesLabel="Best so far"
        secondarySeriesLabel="Raw evaluations"
        chemAccuracyBand={logDeltaAccuracyBand({
          fciEnergy,
          bestEnergy: model.bestEnergy,
          chemicalAccuracyHa,
        })}
      />
    </div>
  );
}

function shouldShowSecondaryLogDeltaPlot(model: ConvergenceModel, energyAxisMode: EnergyAxisMode) {
  return energyAxisMode === "linear" && model.logDeltaData.length > 1;
}

function ConvergenceChartContent({
  model,
  energyAxisMode,
  showProbes,
  showAll,
  setEnergyAxisMode,
  setShowProbes,
  setShowAll,
  fciEnergy,
  chemicalAccuracyHa,
}: Readonly<{
  readonly model: ConvergenceModel;
  readonly energyAxisMode: EnergyAxisMode;
  readonly showProbes: boolean;
  readonly showAll: boolean;
  readonly setEnergyAxisMode: (mode: EnergyAxisMode) => void;
  readonly setShowProbes: (show: boolean) => void;
  readonly setShowAll: (show: boolean) => void;
  readonly fciEnergy: number | undefined;
  readonly chemicalAccuracyHa: number | undefined;
}>) {
  return (
    <div className="flex h-full flex-col gap-2">
      <ConvergenceControls
        energyAxisMode={energyAxisMode}
        showProbes={showProbes}
        showAll={showAll}
        showWindowToggle={model.allPoints.length > 50}
        onEnergyAxisModeChange={setEnergyAxisMode}
        onShowProbesChange={setShowProbes}
        onShowAllChange={setShowAll}
      />
      <MainConvergencePlot model={model} energyAxisMode={energyAxisMode} showProbes={showProbes} />
      {shouldShowSecondaryLogDeltaPlot(model, energyAxisMode) ? (
        <SecondaryLogDeltaPlot
          model={model}
          showProbes={showProbes}
          fciEnergy={fciEnergy}
          chemicalAccuracyHa={chemicalAccuracyHa}
        />
      ) : null}
      <ChartLegend items={model.legend} />
    </div>
  );
}

function ConvergenceTileContent({
  model,
  energyAxisMode,
  showProbes,
  showAll,
  setEnergyAxisMode,
  setShowProbes,
  setShowAll,
  fciEnergy,
  chemicalAccuracyHa,
  isRunning,
  pending,
}: Readonly<{
  readonly model: ConvergenceModel;
  readonly energyAxisMode: EnergyAxisMode;
  readonly showProbes: boolean;
  readonly showAll: boolean;
  readonly setEnergyAxisMode: (mode: EnergyAxisMode) => void;
  readonly setShowProbes: (show: boolean) => void;
  readonly setShowAll: (show: boolean) => void;
  readonly fciEnergy: number | undefined;
  readonly chemicalAccuracyHa: number | undefined;
  readonly isRunning: boolean;
  readonly pending: boolean;
}>) {
  if (model.bestSoFarData.length === 0) {
    return (
      <ChartEmptyState
        message="No iteration data yet"
        pending={pending || isRunning}
        pendingMessage="Awaiting iteration data"
      />
    );
  }
  return (
    <ConvergenceChartContent
      model={model}
      energyAxisMode={energyAxisMode}
      showProbes={showProbes}
      showAll={showAll}
      setEnergyAxisMode={setEnergyAxisMode}
      setShowProbes={setShowProbes}
      setShowAll={setShowAll}
      fciEnergy={fciEnergy}
      chemicalAccuracyHa={chemicalAccuracyHa}
    />
  );
}

export function ConvergenceTile({
  events,
  result,
  algorithm,
  hfEnergy,
  fciEnergy,
  chemicalAccuracyHa,
  isRunning = false,
  pending = false,
  editMode,
}: ConvergenceTileProps) {
  const [showAll, setShowAll] = useState(true);
  const [energyAxisMode, setEnergyAxisMode] = useState<EnergyAxisMode>("linear");
  const [showProbes, setShowProbes] = useState(() => shouldShowRawByDefault(algorithm));
  const theme = useChartTheme();
  const model = buildConvergenceModel({
    events,
    result,
    showAll,
    energyAxisMode,
    showProbes,
    hfEnergy,
    fciEnergy,
    theme,
  });

  return (
    <DashboardTile
      title="Convergence"
      helpText="Energy vs iteration: solid line tracks the best energy seen so far. Convergence is diagnostic; chemical accuracy is the outcome target. Because Hartree energies are often negative, the log scale plots log10 distance to the CASCI active-space reference when available, otherwise to the best visible energy."
      editMode={editMode}
    >
      {pending ? (
        <ConvergenceTileLoadingContent />
      ) : (
        <ConvergenceTileContent
          model={model}
          energyAxisMode={energyAxisMode}
          showProbes={showProbes}
          showAll={showAll}
          setEnergyAxisMode={setEnergyAxisMode}
          setShowProbes={setShowProbes}
          setShowAll={setShowAll}
          fciEnergy={fciEnergy}
          chemicalAccuracyHa={chemicalAccuracyHa}
          isRunning={isRunning}
          pending={pending}
        />
      )}
    </DashboardTile>
  );
}
