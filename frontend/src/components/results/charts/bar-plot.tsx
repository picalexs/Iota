import { useMemo } from "react";
import { ParentSize } from "@visx/responsive";
import { Group } from "@visx/group";
import { Bar } from "@visx/shape";
import { scaleBand, scaleLinear } from "@visx/scale";
import { AxisBottom, AxisLeft } from "@visx/axis";
import { useChartTheme } from "./use-chart-theme";
import { ChartEmptyState } from "./chart-empty-state";

export interface BarDatum {
  readonly label: string;
  readonly value: number | null;
  readonly isHighlight?: boolean;
}

const margin = { top: 44, right: 20, bottom: 48, left: 88 };
const STAGGERED_MARGIN = { ...margin, top: 64 };

interface ValueLabelPlacement {
  readonly lane: number;
  readonly x: number;
  readonly y: number;
  readonly anchorY: number;
}

interface LabelLaneState {
  lastRight: number;
  lastBaseY: number;
}

interface BarPlotInnerProps {
  readonly data: BarDatum[];
  readonly width: number;
  readonly height: number;
  readonly yLabel?: string;
  readonly color: string;
  readonly highlightColor: string;
  readonly mutedColor: string;
  readonly borderColor: string;
  readonly avoidValueLabelOverlap?: boolean;
}

function findLabelLane(
  baseLabelY: number,
  centerX: number,
  estimatedWidth: number,
  laneState: LabelLaneState[],
): number {
  for (let lane = 0; lane < laneState.length; lane += 1) {
    const state = laneState[lane];
    if (!state) continue;
    const ySeparated = Math.abs(baseLabelY - state.lastBaseY) > 18;
    const xSeparated = centerX - estimatedWidth / 2 > state.lastRight + 6;
    if (ySeparated || xSeparated) return lane;
  }
  return laneState.length - 1;
}

function placeValueLabel(
  datum: BarDatum,
  xScale: ReturnType<typeof scaleBand<string>>,
  yScale: ReturnType<typeof scaleLinear<number>>,
  laneState: LabelLaneState[],
): ValueLabelPlacement | null {
  if (datum.value === null) return null;
  const bx = xScale(datum.label) ?? 0;
  const centerX = bx + xScale.bandwidth() / 2;
  const anchorY = yScale(datum.value);
  const baseLabelY = anchorY - 10;
  const estimatedWidth = datum.value.toFixed(6).length * 5.5;
  const lane = findLabelLane(baseLabelY, centerX, estimatedWidth, laneState);
  const state = laneState[lane];
  if (!state) return null;
  state.lastRight = centerX + estimatedWidth / 2;
  state.lastBaseY = baseLabelY;
  return {
    lane,
    x: centerX,
    y: Math.max(14, baseLabelY - lane * 14),
    anchorY: anchorY - 3,
  };
}

function BarPlotInner({
  data,
  width,
  height,
  yLabel,
  color,
  highlightColor,
  mutedColor,
  borderColor,
  avoidValueLabelOverlap = false,
}: BarPlotInnerProps) {
  const activeMargin = avoidValueLabelOverlap ? STAGGERED_MARGIN : margin;
  const inner = {
    w: Math.max(width - activeMargin.left - activeMargin.right, 1),
    h: Math.max(height - activeMargin.top - activeMargin.bottom, 1),
  };

  const filled = data.filter((d): d is BarDatum & { value: number } => d.value !== null);

  const xScale = useMemo(
    () =>
      scaleBand({
        domain: data.map((d) => d.label),
        range: [0, inner.w],
        padding: 0.3,
      }),
    [data, inner.w],
  );

  const vals = filled.map((d) => d.value);
  const yMin = Math.min(...vals);
  const yMax = Math.max(...vals);
  const yPad = Math.abs(yMax - yMin) * 0.1 || 0.01;

  const yScale = useMemo(
    () =>
      scaleLinear({
        domain: [yMin - yPad, yMax + yPad],
        range: [inner.h, 0],
      }),
    [yMin, yMax, yPad, inner.h],
  );

  const labelPlacements = useMemo(() => {
    if (!avoidValueLabelOverlap) return new Map<string, ValueLabelPlacement>();

    const placements = new Map<string, ValueLabelPlacement>();
    const laneState: LabelLaneState[] = Array.from({ length: 4 }, () => ({
      lastRight: Number.NEGATIVE_INFINITY,
      lastBaseY: Number.NEGATIVE_INFINITY,
    }));

    for (const datum of data) {
      if (datum.value === null) continue;
      const placement = placeValueLabel(datum, xScale, yScale, laneState);
      if (placement) placements.set(datum.label, placement);
    }

    return placements;
  }, [avoidValueLabelOverlap, data, xScale, yScale]);

  return (
    <figure>
      <svg width={width} height={height} aria-label={`${yLabel ?? "Value"} bar chart`}>
        <Group left={activeMargin.left} top={activeMargin.top}>
          {data.map((d, index) => {
            if (d.value === null) return null;
            const bx = xScale(d.label) ?? 0;
            const bw = xScale.bandwidth();
            const by = yScale(d.value);
            const height = inner.h - by;
            const placement = labelPlacements.get(d.label);
            const labelY = placement?.y ?? Math.max(14, by - 10 - (index % 2 === 0 ? 0 : 12));
            return (
              <g key={d.label}>
                <Bar
                  x={bx}
                  y={by}
                  width={bw}
                  height={Math.max(0, height)}
                  fill={d.isHighlight ? highlightColor : color}
                  fillOpacity={d.isHighlight ? 0.9 : 0.65}
                  rx={2}
                />
                {placement && placement.lane > 0 ? (
                  <line
                    x1={placement.x}
                    y1={placement.anchorY}
                    x2={placement.x}
                    y2={labelY + 2}
                    stroke={borderColor}
                    strokeOpacity={0.55}
                    strokeWidth={1}
                  />
                ) : null}
                <text
                  x={bx + bw / 2}
                  y={labelY}
                  textAnchor="middle"
                  fontSize={9}
                  fill={mutedColor}
                  className="font-mono"
                >
                  {d.value.toFixed(6)}
                </text>
              </g>
            );
          })}
          <AxisBottom
            scale={xScale}
            top={inner.h}
            stroke={borderColor}
            tickStroke={borderColor}
            tickLabelProps={{ fill: mutedColor, fontSize: 11, textAnchor: "middle" }}
          />
          <AxisLeft
            scale={yScale}
            stroke={borderColor}
            tickStroke={borderColor}
            tickLabelProps={{ fill: mutedColor, fontSize: 11, textAnchor: "end", dx: -6 }}
            numTicks={4}
            tickFormat={(v) => Number(v).toFixed(3)}
            label={yLabel}
            labelOffset={58}
            labelProps={{ fill: mutedColor, fontSize: 11, textAnchor: "middle" }}
          />
        </Group>
      </svg>
    </figure>
  );
}

interface BarPlotProps {
  readonly data: BarDatum[];
  readonly yLabel?: string;
  readonly className?: string;
  readonly avoidValueLabelOverlap?: boolean;
}

export function BarPlot({ data, yLabel, className, avoidValueLabelOverlap }: BarPlotProps) {
  const theme = useChartTheme();
  const filled = data.filter((d) => d.value !== null);
  if (filled.length === 0) return <ChartEmptyState message="Reference energies unavailable" />;

  return (
    <div className={className ?? "h-full w-full"}>
      <ParentSize>
        {({ width, height }) =>
          width > 0 && height > 0 ? (
            <BarPlotInner
              data={data}
              width={width}
              height={height}
              yLabel={yLabel}
              color={theme.chart2}
              highlightColor={theme.chart1}
              mutedColor={theme.muted}
              borderColor={theme.border}
              avoidValueLabelOverlap={avoidValueLabelOverlap}
            />
          ) : null
        }
      </ParentSize>
    </div>
  );
}
