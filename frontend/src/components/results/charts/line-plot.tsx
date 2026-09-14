import { useMemo, useState, type FocusEvent, type MouseEvent } from "react";
import { ParentSize } from "@visx/responsive";
import { Group } from "@visx/group";
import { LinePath } from "@visx/shape";
import { scaleLinear } from "@visx/scale";
import { AxisBottom, AxisLeft } from "@visx/axis";
import { GridRows } from "@visx/grid";
import { overlaySurfaceSmClassName } from "@/lib/interactive-styles";
import { cn } from "@/lib/utils";
import { useChartTheme } from "./use-chart-theme";
import { ChartEmptyState } from "./chart-empty-state";

type LinePlotScale = (value: number) => number;
type LinePlotSeries = "primary" | "secondary";

export interface LinePlotPoint {
  readonly x: number;
  readonly y: number;
  readonly displayY?: number;
  readonly tooltipTitle?: string;
  readonly tooltipValue?: string;
  readonly tooltipLines?: string[];
}

export interface ReferenceLineSpec {
  readonly y: number;
  readonly label: string;
  readonly color?: string;
  readonly dashed?: boolean;
}

interface LinePlotInnerProps {
  readonly data: LinePlotPoint[];
  readonly secondaryData?: LinePlotPoint[];
  readonly width: number;
  readonly height: number;
  readonly xLabel?: string;
  readonly yLabel?: string;
  readonly xTickFormat?: (value: number) => string;
  readonly xTickValues?: number[];
  readonly yTickFormat?: (value: number) => string;
  readonly referenceLines?: ReferenceLineSpec[];
  readonly chemAccuracyBand?: { readonly center: number; readonly halfWidth: number };
  readonly color: string;
  readonly secondaryColor?: string;
  readonly primarySeriesLabel?: string;
  readonly secondarySeriesLabel?: string;
  readonly borderColor: string;
  readonly mutedColor: string;
}

const baseMargin = { top: 16, right: 12, bottom: 42, left: 102 };

interface TooltipState {
  readonly x: number;
  readonly y: number;
  readonly pt: LinePlotPoint;
  readonly series: LinePlotSeries;
}

interface PointMarkerStyle {
  readonly r: number;
  readonly fill: string;
  readonly fillOpacity?: number;
  readonly stroke: string;
  readonly strokeWidth: number;
  readonly strokeOpacity?: number;
}

function linePlotPointLabel(point: LinePlotPoint, seriesLabel: string): string {
  return `${seriesLabel} iteration ${point.x}: ${(point.displayY ?? point.y).toFixed(6)}`;
}

function primaryPointStyle(color: string, isHovered: boolean): PointMarkerStyle {
  if (isHovered) {
    return { r: 4.5, fill: color, fillOpacity: 0.95, stroke: color, strokeWidth: 1.5 };
  }
  return { r: 3.2, fill: color, fillOpacity: 0.72, stroke: "none", strokeWidth: 0 };
}

function secondaryPointStyle(color: string, isHovered: boolean): PointMarkerStyle {
  if (isHovered) {
    return { r: 5, fill: "none", stroke: color, strokeWidth: 2, strokeOpacity: 0.9 };
  }
  return { r: 4, fill: "none", stroke: color, strokeWidth: 1.4, strokeOpacity: 0.9 };
}

function pointMarkerStyle(
  series: LinePlotSeries,
  color: string,
  isHovered: boolean,
): PointMarkerStyle {
  return series === "primary"
    ? primaryPointStyle(color, isHovered)
    : secondaryPointStyle(color, isHovered);
}

interface HoverGuidesProps {
  readonly point: LinePlotPoint | null;
  readonly xScale: LinePlotScale;
  readonly yScale: LinePlotScale;
  readonly width: number;
  readonly height: number;
  readonly borderColor: string;
}

function HoverGuides({ point, xScale, yScale, width, height, borderColor }: HoverGuidesProps) {
  if (!point) return null;

  return (
    <g pointerEvents="none">
      <line
        x1={xScale(point.x)}
        x2={xScale(point.x)}
        y1={0}
        y2={height}
        stroke={borderColor}
        strokeOpacity={0.4}
        strokeDasharray="3 3"
      />
      <line
        x1={0}
        x2={width}
        y1={yScale(point.y)}
        y2={yScale(point.y)}
        stroke={borderColor}
        strokeOpacity={0.28}
        strokeDasharray="3 3"
      />
    </g>
  );
}

interface ChemicalAccuracyBandProps {
  readonly band?: { readonly center: number; readonly halfWidth: number };
  readonly yScale: LinePlotScale;
  readonly width: number;
  readonly color: string;
}

function ChemicalAccuracyBand({ band, yScale, width, color }: ChemicalAccuracyBandProps) {
  if (!band) return null;

  const top = yScale(band.center + band.halfWidth);
  const bottom = yScale(band.center - band.halfWidth);
  return (
    <rect
      x={0}
      y={top}
      width={width}
      height={Math.max(0, bottom - top)}
      fill={color}
      fillOpacity={0.08}
    />
  );
}

interface ReferenceLinesProps {
  readonly referenceLines?: ReferenceLineSpec[];
  readonly yScale: LinePlotScale;
  readonly width: number;
  readonly mutedColor: string;
}

function ReferenceLines({ referenceLines, yScale, width, mutedColor }: ReferenceLinesProps) {
  const dashForLine = (line: ReferenceLineSpec) => {
    if (line.dashed === false) {
      return undefined;
    }
    return "4 2";
  };

  return (
    <>
      {(referenceLines ?? []).map((line) => (
        <g key={`${line.label}-${line.y}`}>
          <line
            x1={0}
            x2={width}
            y1={yScale(line.y)}
            y2={yScale(line.y)}
            stroke={line.color ?? mutedColor}
            strokeWidth={1}
            strokeDasharray={dashForLine(line)}
          />
        </g>
      ))}
    </>
  );
}

interface SeriesPointsProps {
  readonly data?: LinePlotPoint[];
  readonly series: LinePlotSeries;
  readonly hoveredPoint: LinePlotPoint | null;
  readonly xScale: LinePlotScale;
  readonly yScale: LinePlotScale;
  readonly color: string;
  readonly label: string;
  readonly onMousePoint: (
    event: MouseEvent<SVGCircleElement>,
    point: LinePlotPoint,
    series: LinePlotSeries,
  ) => void;
  readonly onFocusPoint: (
    event: FocusEvent<SVGCircleElement>,
    point: LinePlotPoint,
    series: LinePlotSeries,
  ) => void;
  readonly onClear: () => void;
}

function SeriesPoints({
  data,
  series,
  hoveredPoint,
  xScale,
  yScale,
  color,
  label,
  onMousePoint,
  onFocusPoint,
  onClear,
}: SeriesPointsProps) {
  if (!data) return null;

  return (
    <>
      {data.map((point) => {
        const isHovered = hoveredPoint === point;
        const markerStyle = pointMarkerStyle(series, color, isHovered);
        return (
          <circle
            key={`${series}-${point.x}-${point.y}`}
            cx={xScale(point.x)}
            cy={yScale(point.y)}
            r={markerStyle.r}
            fill={markerStyle.fill}
            fillOpacity={markerStyle.fillOpacity}
            stroke={markerStyle.stroke}
            strokeWidth={markerStyle.strokeWidth}
            strokeOpacity={markerStyle.strokeOpacity}
            tabIndex={0}
            aria-label={linePlotPointLabel(point, label)}
            onMouseEnter={(event) => onMousePoint(event, point, series)}
            onMouseLeave={onClear}
            onFocus={(event) => onFocusPoint(event, point, series)}
            onBlur={onClear}
            style={{ cursor: "crosshair" }}
          />
        );
      })}
    </>
  );
}

interface LinePlotTooltipProps {
  readonly tooltip: TooltipState | null;
  readonly primarySeriesLabel: string;
  readonly secondarySeriesLabel: string;
}

function LinePlotTooltip({
  tooltip,
  primarySeriesLabel,
  secondarySeriesLabel,
}: LinePlotTooltipProps) {
  if (!tooltip) return null;

  const seriesLabel = tooltip.series === "secondary" ? secondarySeriesLabel : primarySeriesLabel;
  const title = tooltip.pt.tooltipTitle ?? `${seriesLabel} · iter ${tooltip.pt.x}`;
  const value = tooltip.pt.tooltipValue ?? `${(tooltip.pt.displayY ?? tooltip.pt.y).toFixed(6)} Ha`;

  return (
    <div
      className={cn(
        "pointer-events-none fixed z-50 max-w-64 rounded-lg border px-2.5 py-2 text-xs backdrop-blur-sm",
        overlaySurfaceSmClassName,
      )}
      style={{ left: tooltip.x + 8, top: tooltip.y - 8 }}
    >
      <div className="text-[11px] font-medium text-muted-foreground">{title}</div>
      <div className="font-mono text-foreground">{value}</div>
      {(tooltip.pt.tooltipLines ?? []).map((line) => (
        <div key={line} className="mt-0.5 text-muted-foreground">
          {line}
        </div>
      ))}
    </div>
  );
}

function LinePlotInner({
  data,
  secondaryData,
  width,
  height,
  xLabel,
  yLabel,
  xTickFormat,
  xTickValues,
  yTickFormat,
  referenceLines,
  chemAccuracyBand,
  color,
  secondaryColor,
  primarySeriesLabel = "Primary series",
  secondarySeriesLabel = "Secondary series",
  borderColor,
  mutedColor,
}: LinePlotInnerProps) {
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);
  const margin = baseMargin;

  const inner = {
    w: Math.max(width - margin.left - margin.right, 1),
    h: Math.max(height - margin.top - margin.bottom, 1),
  };

  const xScale = useMemo(() => {
    const allXValues = [...data.map((d) => d.x), ...(secondaryData ?? []).map((d) => d.x)];
    return scaleLinear({
      domain: [Math.min(...allXValues), Math.max(...allXValues)],
      range: [0, inner.w],
    });
  }, [data, inner.w, secondaryData]);

  const allYValues = [
    ...data.map((d) => d.y),
    ...(secondaryData ?? []).map((d) => d.y),
    ...(referenceLines ?? []).map((l) => l.y),
  ];
  const yMin = Math.min(...allYValues);
  const yMax = Math.max(...allYValues);
  const yPad = Math.abs(yMax - yMin) * 0.08 || 0.01;
  const yScale = useMemo(
    () =>
      scaleLinear({
        domain: [yMin - yPad, yMax + yPad],
        range: [inner.h, 0],
      }),
    [yMin, yMax, yPad, inner.h],
  );

  const setTooltipFromMouse = (
    event: MouseEvent<SVGCircleElement>,
    pt: LinePlotPoint,
    series: LinePlotSeries,
  ) => {
    setTooltip({ x: event.clientX, y: event.clientY, pt, series });
  };

  const setTooltipFromFocus = (
    event: FocusEvent<SVGCircleElement>,
    pt: LinePlotPoint,
    series: LinePlotSeries,
  ) => {
    const rect = event.currentTarget.getBoundingClientRect();
    setTooltip({
      x: rect.left + rect.width / 2,
      y: rect.top,
      pt,
      series,
    });
  };

  const hoveredPrimary = tooltip?.series === "primary" ? tooltip.pt : null;
  const hoveredSecondary = tooltip?.series === "secondary" ? tooltip.pt : null;
  const hoveredPoint = tooltip?.pt ?? null;

  return (
    <figure className="relative">
      <svg
        width={width}
        height={height}
        aria-label={`${yLabel ?? "Value"} vs ${xLabel ?? "iteration"} line chart`}
      >
        <Group left={margin.left} top={margin.top}>
          <GridRows
            scale={yScale}
            width={inner.w}
            stroke={borderColor}
            strokeOpacity={0.4}
            numTicks={4}
          />

          <HoverGuides
            point={hoveredPoint}
            xScale={xScale}
            yScale={yScale}
            width={inner.w}
            height={inner.h}
            borderColor={borderColor}
          />
          <ChemicalAccuracyBand
            band={chemAccuracyBand}
            yScale={yScale}
            width={inner.w}
            color={color}
          />
          <ReferenceLines
            referenceLines={referenceLines}
            yScale={yScale}
            width={inner.w}
            mutedColor={mutedColor}
          />

          <LinePath
            data={data}
            x={(d) => xScale(d.x)}
            y={(d) => yScale(d.y)}
            stroke={color}
            strokeWidth={1.5}
            strokeLinejoin="round"
          />

          {secondaryData && secondaryData.length > 1 && (
            <LinePath
              data={secondaryData}
              x={(d) => xScale(d.x)}
              y={(d) => yScale(d.y)}
              stroke={secondaryColor ?? mutedColor}
              strokeWidth={1}
              strokeDasharray="3 3"
              strokeOpacity={0.55}
            />
          )}

          <SeriesPoints
            data={data}
            series="primary"
            hoveredPoint={hoveredPrimary}
            xScale={xScale}
            yScale={yScale}
            color={color}
            label={primarySeriesLabel}
            onMousePoint={setTooltipFromMouse}
            onFocusPoint={setTooltipFromFocus}
            onClear={() => setTooltip(null)}
          />
          <SeriesPoints
            data={secondaryData}
            series="secondary"
            hoveredPoint={hoveredSecondary}
            xScale={xScale}
            yScale={yScale}
            color={secondaryColor ?? mutedColor}
            label={secondarySeriesLabel}
            onMousePoint={setTooltipFromMouse}
            onFocusPoint={setTooltipFromFocus}
            onClear={() => setTooltip(null)}
          />

          <AxisBottom
            scale={xScale}
            top={inner.h}
            stroke={borderColor}
            tickStroke={borderColor}
            tickLabelProps={{ fill: mutedColor, fontSize: 11, textAnchor: "middle" }}
            numTicks={5}
            tickFormat={xTickFormat ? (v) => xTickFormat(Number(v)) : undefined}
            tickValues={xTickValues}
            label={xLabel}
            labelProps={{ fill: mutedColor, fontSize: 11, textAnchor: "middle" }}
          />
          <AxisLeft
            scale={yScale}
            stroke={borderColor}
            tickStroke={borderColor}
            tickLabelProps={{ fill: mutedColor, fontSize: 11, textAnchor: "end", dx: -6 }}
            numTicks={4}
            tickFormat={yTickFormat ? (v) => yTickFormat(Number(v)) : (v) => Number(v).toFixed(3)}
            label={yLabel}
            labelOffset={70}
            labelProps={{ fill: mutedColor, fontSize: 11, textAnchor: "middle" }}
          />
        </Group>
      </svg>
      <LinePlotTooltip
        tooltip={tooltip}
        primarySeriesLabel={primarySeriesLabel}
        secondarySeriesLabel={secondarySeriesLabel}
      />
    </figure>
  );
}

interface LinePlotProps {
  readonly data: LinePlotPoint[];
  readonly secondaryData?: LinePlotPoint[];
  readonly xLabel?: string;
  readonly yLabel?: string;
  readonly xTickFormat?: (value: number) => string;
  readonly xTickValues?: number[];
  readonly yTickFormat?: (value: number) => string;
  readonly referenceLines?: ReferenceLineSpec[];
  readonly chemAccuracyBand?: { readonly center: number; readonly halfWidth: number };
  readonly primarySeriesLabel?: string;
  readonly secondarySeriesLabel?: string;
  readonly className?: string;
}

export function LinePlot({
  data,
  secondaryData,
  xLabel,
  yLabel,
  xTickFormat,
  xTickValues,
  yTickFormat,
  referenceLines,
  chemAccuracyBand,
  primarySeriesLabel,
  secondarySeriesLabel,
  className,
}: LinePlotProps) {
  const theme = useChartTheme();
  if (data.length === 0) return <ChartEmptyState />;

  return (
    <div className={className ?? "h-full w-full"}>
      <ParentSize>
        {({ width, height }) =>
          width > 0 && height > 0 ? (
            <LinePlotInner
              data={data}
              secondaryData={secondaryData}
              width={width}
              height={height}
              xLabel={xLabel}
              yLabel={yLabel}
              xTickFormat={xTickFormat}
              xTickValues={xTickValues}
              yTickFormat={yTickFormat}
              referenceLines={referenceLines}
              chemAccuracyBand={chemAccuracyBand}
              color={theme.chart1}
              secondaryColor={theme.muted}
              primarySeriesLabel={primarySeriesLabel}
              secondarySeriesLabel={secondarySeriesLabel}
              borderColor={theme.border}
              mutedColor={theme.muted}
            />
          ) : null
        }
      </ParentSize>
    </div>
  );
}
