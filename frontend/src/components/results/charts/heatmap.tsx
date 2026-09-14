import { useMemo } from "react";
import { ParentSize } from "@visx/responsive";
import { Group } from "@visx/group";
import { HeatmapRect } from "@visx/heatmap";
import { scaleLinear } from "@visx/scale";
import { AxisBottom, AxisLeft } from "@visx/axis";
import { useChartTheme } from "./use-chart-theme";
import { ChartEmptyState } from "./chart-empty-state";

export interface HeatmapData {
  readonly rows: number;
  readonly cols: number;
  readonly values: number[];
}

const margin = { top: 12, right: 16, bottom: 36, left: 40 };

interface HeatmapInnerProps {
  readonly data: HeatmapData;
  readonly width: number;
  readonly height: number;
  readonly color: string;
  readonly negativeColor: string;
  readonly neutralColor: string;
  readonly borderColor: string;
  readonly mutedColor: string;
}

function HeatmapInner({
  data,
  width,
  height,
  color,
  negativeColor,
  neutralColor,
  borderColor,
  mutedColor,
}: HeatmapInnerProps) {
  const inner = {
    w: Math.max(width - margin.left - margin.right, 1),
    h: Math.max(height - margin.top - margin.bottom, 1),
  };

  const cellW = inner.w / data.cols;
  const cellH = inner.h / data.rows;

  const min = Math.min(...data.values);
  const max = Math.max(...data.values);

  const colorScale = useMemo(
    () => scaleLinear({ domain: [min, 0, max], range: [negativeColor, neutralColor, color] }),
    [min, max, negativeColor, neutralColor, color],
  );

  const bins = useMemo(() => {
    return Array.from({ length: data.rows }, (_, row) => ({
      bin: row,
      bins: Array.from({ length: data.cols }, (_, col) => ({
        bin: col,
        count: data.values[row * data.cols + col] ?? 0,
      })),
    }));
  }, [data]);

  const xScale = useMemo(
    () => scaleLinear({ domain: [0, data.cols], range: [0, inner.w] }),
    [data.cols, inner.w],
  );
  const yScale = useMemo(
    () => scaleLinear({ domain: [0, data.rows], range: [0, inner.h] }),
    [data.rows, inner.h],
  );

  return (
    <figure>
      <svg width={width} height={height} role="img" aria-label="Parameter heatmap">
        <Group left={margin.left} top={margin.top}>
          <HeatmapRect
            data={bins}
            xScale={(d) => xScale(d) ?? 0}
            yScale={(d) => yScale(d) ?? 0}
            colorScale={colorScale}
            binWidth={cellW}
            binHeight={cellH}
            gap={1}
          >
            {(heatmap) =>
              heatmap.map((heatmapBins) =>
                heatmapBins.map((bin) => (
                  <rect
                    key={`heatmap-rect-${bin.row}-${bin.column}`}
                    x={bin.x}
                    y={bin.y}
                    width={bin.width}
                    height={bin.height}
                    fill={bin.color ?? "#888"}
                    rx={2}
                  />
                )),
              )
            }
          </HeatmapRect>
          <AxisBottom
            scale={xScale}
            top={inner.h}
            stroke={borderColor}
            tickStroke={borderColor}
            tickLabelProps={{ fill: mutedColor, fontSize: 9, textAnchor: "middle" }}
            numTicks={Math.min(data.cols, 8)}
            label="Parameter index"
            labelProps={{ fill: mutedColor, fontSize: 9, textAnchor: "middle" }}
          />
          <AxisLeft
            scale={yScale}
            stroke={borderColor}
            tickStroke={borderColor}
            tickLabelProps={{ fill: mutedColor, fontSize: 9, textAnchor: "end" }}
            numTicks={Math.min(data.rows, 6)}
            label="Layer"
            labelProps={{ fill: mutedColor, fontSize: 9, textAnchor: "middle" }}
          />
        </Group>
      </svg>
    </figure>
  );
}

interface HeatmapChartProps {
  readonly data: HeatmapData;
  readonly className?: string;
}

export function HeatmapChart({ data, className }: HeatmapChartProps) {
  const theme = useChartTheme();
  if (data.values.length === 0) return <ChartEmptyState message="No parameter data" />;

  return (
    <div className={className ?? "h-full w-full"}>
      <ParentSize>
        {({ width, height }) =>
          width > 0 && height > 0 ? (
            <HeatmapInner
              data={data}
              width={width}
              height={height}
              color={theme.chart1}
              negativeColor={theme.chart4}
              neutralColor={theme.card}
              borderColor={theme.border}
              mutedColor={theme.muted}
            />
          ) : null
        }
      </ParentSize>
    </div>
  );
}
