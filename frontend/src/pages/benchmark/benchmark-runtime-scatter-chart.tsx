import { useRef, useState, type ComponentProps } from "react";
import { cn } from "@/lib/utils";
import { ChartTooltip, type ChartTooltipSection } from "@/components/results/charts/chart-tooltip";
import { useChartTheme, type ChartTheme } from "@/components/results/charts/use-chart-theme";
import { formatMetric, formatRuntimeMinutes } from "./benchmark-insights-formatters";
import type { BenchmarkEntry } from "./benchmark-utils";
import {
  buildScatterMarkerPath,
  scatterFamilyColor,
  scatterMarkerShape,
} from "./benchmark-scatter-markers";

interface RuntimeScatterPointData {
  id: string;
  familyKey: BenchmarkEntry["algorithm"];
  familyLabel: string;
  algorithm: string;
  molecule: string;
  moleculeShort: string;
  runtime: number;
  energy: number;
  absErrorMha: number;
  verdict: "accurate" | "not_accurate" | "unscored";
  tooltipSections: readonly ChartTooltipSection[];
}

interface ScatterLabelLayout {
  x: number;
  y: number;
  textAnchor: "start" | "end";
}

interface ScatterFilterOption {
  value: string;
  label: string;
}

interface RuntimeScatterMetrics {
  width: number;
  height: number;
  topPad: number;
  leftPad: number;
  rightPad: number;
  bottomPad: number;
  plotWidth: number;
  runtimeTicks: readonly number[];
  errorTicks: readonly number[];
  targetY: number;
  reduceInlineLabels: boolean;
  labelLayouts: ReadonlyMap<string, ScatterLabelLayout>;
  xForRuntime: (runtime: number) => number;
  yForError: (error: number) => number;
}

type InsightsPanelMode = "embedded" | "fullscreen";

interface ScatterHoveredPoint {
  point: RuntimeScatterPointData;
  plotX: number;
  plotY: number;
  tooltipX: number;
  tooltipY: number;
  tooltipHorizontal: "start" | "end";
  tooltipVertical: "top" | "bottom";
}

function scatterPointRadius(point: RuntimeScatterPointData, hovered: boolean): number {
  if (hovered) return 7;
  return point.verdict === "accurate" ? 6 : 5;
}

function scatterPointInlineLabel(point: RuntimeScatterPointData): string {
  return `${point.moleculeShort} ${point.familyLabel}`;
}

function scatterPointLabelPosition({
  labelLayout,
  x,
  y,
  index,
}: Readonly<{
  labelLayout: ScatterLabelLayout | undefined;
  x: number;
  y: number;
  index: number;
}>): Pick<ComponentProps<"text">, "x" | "y" | "textAnchor"> {
  return {
    x: labelLayout?.x ?? x + 10,
    y: labelLayout?.y ?? y + (index % 2 === 0 ? -10 : 14),
    textAnchor: labelLayout?.textAnchor ?? "start",
  };
}

function useRuntimeScatterHover({
  width,
  height,
  tooltipWidth,
  tooltipHeight,
  tooltipMargin,
}: Readonly<{
  width: number;
  height: number;
  tooltipWidth: number;
  tooltipHeight: number;
  tooltipMargin: number;
}>) {
  const [hoveredPoint, setHoveredPoint] = useState<ScatterHoveredPoint | null>(null);
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);

  const setHoveredScatterPoint = (point: RuntimeScatterPointData, plotX: number, plotY: number) => {
    const wrapperRect = wrapperRef.current?.getBoundingClientRect();
    const svgRect = svgRef.current?.getBoundingClientRect();
    if (wrapperRect && svgRect) {
      const tooltipX = svgRect.left - wrapperRect.left + (plotX / width) * svgRect.width;
      const tooltipY = svgRect.top - wrapperRect.top + (plotY / height) * svgRect.height;
      setHoveredPoint({
        point,
        plotX,
        plotY,
        tooltipX,
        tooltipY,
        tooltipHorizontal:
          tooltipX + tooltipWidth + tooltipMargin > wrapperRect.width ? "end" : "start",
        tooltipVertical: tooltipY - tooltipHeight - tooltipMargin < 0 ? "bottom" : "top",
      });
      return;
    }

    setHoveredPoint({
      point,
      plotX,
      plotY,
      tooltipX: plotX,
      tooltipY: plotY,
      tooltipHorizontal: "start",
      tooltipVertical: "top",
    });
  };

  return {
    hoveredPoint,
    wrapperRef,
    svgRef,
    clearHoveredPoint: () => setHoveredPoint(null),
    setHoveredScatterPoint,
  };
}

export function RuntimeScatterLegend({
  familyOptions,
}: Readonly<{
  familyOptions: readonly ScatterFilterOption[];
}>) {
  const theme = useChartTheme();

  return (
    <div className="mb-3 flex w-fit flex-col gap-1 rounded-md border bg-background px-2 py-1.5 text-xs text-muted-foreground shadow-sm">
      <span className="font-medium text-foreground">Legend</span>
      {familyOptions.map((option) => {
        const family = option.value as BenchmarkEntry["algorithm"];
        const shape = scatterMarkerShape(family);
        const color = scatterFamilyColor(family, theme);
        const markerPath = buildScatterMarkerPath(shape, 8, 8, 4.2);

        return (
          <div
            key={option.value}
            className="inline-flex items-center gap-1.5"
            data-scatter-legend-item={option.value}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" className="shrink-0">
              {markerPath ? (
                <path d={markerPath} fill={color} stroke={theme.card} strokeWidth="1.2" />
              ) : (
                <circle cx="8" cy="8" r="4.2" fill={color} stroke={theme.card} strokeWidth="1.2" />
              )}
            </svg>
            <span>{option.label}</span>
          </div>
        );
      })}
    </div>
  );
}

function RuntimeScatterPoint({
  point,
  index,
  metrics,
  hovered,
  showLabels,
  theme,
  onHover,
  onLeave,
}: Readonly<{
  point: RuntimeScatterPointData;
  index: number;
  metrics: RuntimeScatterMetrics;
  hovered: boolean;
  showLabels: boolean;
  theme: ChartTheme;
  onHover: (point: RuntimeScatterPointData, x: number, y: number) => void;
  onLeave: () => void;
}>) {
  const x = metrics.xForRuntime(point.runtime);
  const y = metrics.yForError(point.absErrorMha);
  const shape = scatterMarkerShape(point.familyKey);
  const fill = scatterFamilyColor(point.familyKey, theme);
  const radius = scatterPointRadius(point, hovered);
  const markerPath = buildScatterMarkerPath(shape, x, y, radius);
  const labelLayout = metrics.labelLayouts.get(point.id);
  const label = scatterPointInlineLabel(point);
  const labelPosition = scatterPointLabelPosition({ labelLayout, x, y, index });
  const showInlineLabel = showLabels && (hovered || labelLayout !== undefined);
  const commonMarkerProps = {
    fill,
    opacity: hovered ? 1 : 0.86,
    stroke: hovered ? theme.foreground : theme.card,
    strokeWidth: hovered ? 1.8 : 1.2,
    "aria-label": `${point.molecule} ${point.algorithm} benchmark point`,
    "data-scatter-point": "",
    "data-scatter-shape": shape,
    onMouseEnter: () => onHover(point, x, y),
    onMouseLeave: onLeave,
    style: { cursor: "crosshair" },
  } as const;

  return (
    <g key={point.id}>
      {markerPath ? (
        <path d={markerPath} {...commonMarkerProps} />
      ) : (
        <circle cx={x} cy={y} r={radius} {...commonMarkerProps} />
      )}
      {showInlineLabel ? (
        <text
          x={labelPosition.x}
          y={labelPosition.y}
          textAnchor={labelPosition.textAnchor}
          fontSize="11"
          fill="currentColor"
          opacity={hovered ? 0.96 : 0.82}
        >
          {label}
        </text>
      ) : null}
    </g>
  );
}

export function RuntimeScatterChart({
  points,
  mode,
  metrics,
  showLabels,
}: Readonly<{
  points: readonly RuntimeScatterPointData[];
  mode: InsightsPanelMode;
  metrics: RuntimeScatterMetrics;
  showLabels: boolean;
}>) {
  const theme = useChartTheme();
  const tooltipWidth = 176;
  const tooltipHeight = 112;
  const tooltipMargin = 12;
  const { hoveredPoint, wrapperRef, svgRef, clearHoveredPoint, setHoveredScatterPoint } =
    useRuntimeScatterHover({
      width: metrics.width,
      height: metrics.height,
      tooltipWidth,
      tooltipHeight,
      tooltipMargin,
    });

  return (
    <div ref={wrapperRef} className={cn("relative", mode === "fullscreen" && "min-h-0 flex-1")}>
      <svg
        ref={svgRef}
        viewBox={`0 0 ${metrics.width} ${metrics.height}`}
        role="img"
        aria-label="Benchmark accuracy versus runtime scatter plot"
        className={cn("w-full", mode === "fullscreen" ? "h-full min-h-0" : "min-h-[22rem]")}
      >
        <rect
          x={metrics.leftPad}
          y={metrics.targetY}
          width={metrics.plotWidth}
          height={metrics.height - metrics.bottomPad - metrics.targetY}
          fill={theme.success}
          opacity="0.08"
        />
        <line
          x1={metrics.leftPad}
          y1={metrics.height - metrics.bottomPad}
          x2={metrics.width - metrics.rightPad}
          y2={metrics.height - metrics.bottomPad}
          stroke={theme.border}
        />
        <line
          x1={metrics.leftPad}
          y1={metrics.topPad}
          x2={metrics.leftPad}
          y2={metrics.height - metrics.bottomPad}
          stroke={theme.border}
        />
        <line
          x1={metrics.leftPad}
          x2={metrics.width - metrics.rightPad}
          y1={metrics.targetY}
          y2={metrics.targetY}
          stroke={theme.success}
          strokeDasharray="4 4"
        />
        {hoveredPoint ? (
          <g pointerEvents="none">
            <line
              x1={metrics.leftPad}
              x2={hoveredPoint.plotX}
              y1={hoveredPoint.plotY}
              y2={hoveredPoint.plotY}
              stroke={theme.border}
              strokeOpacity="0.35"
              strokeDasharray="3 3"
            />
            <line
              x1={hoveredPoint.plotX}
              x2={hoveredPoint.plotX}
              y1={hoveredPoint.plotY}
              y2={metrics.height - metrics.bottomPad}
              stroke={theme.border}
              strokeOpacity="0.35"
              strokeDasharray="3 3"
            />
          </g>
        ) : null}
        {metrics.runtimeTicks.map((tick) => {
          const x = metrics.xForRuntime(tick);
          return (
            <g key={`runtime-${tick}`}>
              <line
                x1={x}
                x2={x}
                y1={metrics.height - metrics.bottomPad}
                y2={metrics.height - metrics.bottomPad + 5}
                stroke={theme.border}
              />
              <text
                x={x}
                y={metrics.height - metrics.bottomPad + 20}
                textAnchor="middle"
                fontSize="11"
                fill="currentColor"
                opacity="0.7"
              >
                {formatRuntimeMinutes(tick)}
              </text>
            </g>
          );
        })}
        {metrics.errorTicks.map((tick) => {
          const y = metrics.yForError(tick);
          return (
            <g key={`error-${tick}`}>
              <line
                x1={metrics.leftPad - 5}
                x2={metrics.leftPad}
                y1={y}
                y2={y}
                stroke={theme.border}
              />
              <text
                x={metrics.leftPad - 9}
                y={y + 4}
                textAnchor="end"
                fontSize="11"
                fill="currentColor"
                opacity="0.7"
              >
                {formatMetric(tick)}
              </text>
            </g>
          );
        })}
        <text
          x={metrics.width / 2}
          y={metrics.height - 4}
          textAnchor="middle"
          fontSize="13"
          fill="currentColor"
        >
          runtime
        </text>
        <text
          x={18}
          y={metrics.height / 2}
          textAnchor="middle"
          fontSize="12"
          fill="currentColor"
          transform={`rotate(-90 18 ${metrics.height / 2})`}
        >
          abs error mHa (log)
        </text>
        {points.map((point, index) => (
          <RuntimeScatterPoint
            key={point.id}
            point={point}
            index={index}
            metrics={metrics}
            hovered={hoveredPoint?.point.id === point.id}
            showLabels={showLabels}
            theme={theme}
            onHover={setHoveredScatterPoint}
            onLeave={clearHoveredPoint}
          />
        ))}
      </svg>
      {hoveredPoint ? (
        <ChartTooltip
          x={hoveredPoint.tooltipX}
          y={hoveredPoint.tooltipY}
          horizontal={hoveredPoint.tooltipHorizontal}
          vertical={hoveredPoint.tooltipVertical}
          title={`${hoveredPoint.point.molecule} · ${hoveredPoint.point.algorithm}`}
          value={`${hoveredPoint.point.energy.toFixed(6)} Ha`}
          sections={hoveredPoint.point.tooltipSections}
        />
      ) : null}
    </div>
  );
}
