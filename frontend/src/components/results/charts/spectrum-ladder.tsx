import { useMemo } from "react";
import { ParentSize } from "@visx/responsive";
import { Group } from "@visx/group";
import { scaleLinear } from "@visx/scale";
import { AxisLeft } from "@visx/axis";
import { useChartTheme } from "./use-chart-theme";
import { ChartEmptyState } from "./chart-empty-state";
import {
  formatSpectrumEnergy,
  layoutSpectrumLabels,
  spectrumDecimalPlaces,
} from "./spectrum-ladder-utils";

const margin = { top: 16, right: 176, bottom: 16, left: 88 };
const LABEL_RAIL_WIDTH = 160;

interface SpectrumLadderInnerProps {
  readonly energies: number[];
  readonly referenceEnergy?: number;
  readonly highlightedIndex?: number;
  readonly width: number;
  readonly height: number;
  readonly color: string;
  readonly highlightColor: string;
  readonly borderColor: string;
  readonly mutedColor: string;
}

function spectrumDomainValues(energies: number[], referenceEnergy?: number): number[] {
  if (referenceEnergy === undefined) {
    return energies;
  }
  return [...energies, referenceEnergy];
}

function SpectrumLadderInner({
  energies,
  referenceEnergy,
  highlightedIndex,
  width,
  height,
  color,
  highlightColor,
  borderColor,
  mutedColor,
}: SpectrumLadderInnerProps) {
  const inner = {
    w: Math.max(width - margin.left - margin.right, 1),
    h: Math.max(height - margin.top - margin.bottom, 1),
  };

  const allVals = useMemo(
    () => spectrumDomainValues(energies, referenceEnergy),
    [energies, referenceEnergy],
  );
  const min = Math.min(...allVals);
  const max = Math.max(...allVals);
  const pad = Math.abs(max - min) * 0.1 || 0.05;

  const yScale = useMemo(
    () => scaleLinear({ domain: [min - pad, max + pad], range: [inner.h, 0] }),
    [min, max, pad, inner.h],
  );

  const decimals = useMemo(() => spectrumDecimalPlaces(allVals), [allVals]);
  const axisDecimals = Math.min(Math.max(decimals - 1, 3), 6);
  const labelX = Math.max(inner.w - LABEL_RAIL_WIDTH + 8, inner.w * 0.7);
  const lineRight = Math.max(48, labelX - 18);
  const lineLeft = Math.max(0, Math.min(lineRight - 48, inner.w * 0.1));
  const labelLayout = useMemo(
    () =>
      layoutSpectrumLabels(
        energies.map((energy, index) => ({ index, energy, lineY: yScale(energy) })),
        inner.h,
      ),
    [energies, inner.h, yScale],
  );

  return (
    <figure>
      <svg width={width} height={height} aria-label="Energy spectrum ladder">
        <Group left={margin.left} top={margin.top}>
          {energies.map((e, i) => {
            const isHighlighted = highlightedIndex === i;
            const lineY = yScale(e);
            const labelY = labelLayout[i]?.labelY ?? lineY;
            const labelMoved = Math.abs(labelY - lineY) > 1;
            const spectrumColor = isHighlighted ? highlightColor : color;
            const labelColor = isHighlighted ? highlightColor : mutedColor;
            let strokeWidth = 1.5;
            if (isHighlighted) {
              strokeWidth = 3.5;
            } else if (i === 0) {
              strokeWidth = 2.5;
            }
            return (
              <g key={`${e}-${labelY}`}>
                <line
                  x1={lineLeft}
                  x2={lineRight}
                  y1={lineY}
                  y2={lineY}
                  stroke={spectrumColor}
                  strokeWidth={strokeWidth}
                />
                {labelMoved && (
                  <path
                    d={`M${lineRight} ${lineY} L${lineRight + 6} ${lineY} L${labelX - 4} ${labelY}`}
                    fill="none"
                    stroke={isHighlighted ? highlightColor : mutedColor}
                    strokeOpacity={isHighlighted ? 0.7 : 0.45}
                    strokeWidth={isHighlighted ? 1 : 0.75}
                  />
                )}
                <text
                  x={labelX}
                  y={labelY}
                  dominantBaseline="middle"
                  fontFamily="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace"
                  fontSize={isHighlighted ? 11 : 10}
                  fontWeight={isHighlighted ? 700 : 400}
                  fill={labelColor}
                >
                  {formatSpectrumEnergy(e, decimals)}
                </text>
              </g>
            );
          })}
          {referenceEnergy !== undefined && (
            <line
              x1={0}
              x2={lineRight}
              y1={yScale(referenceEnergy)}
              y2={yScale(referenceEnergy)}
              stroke={mutedColor}
              strokeWidth={1}
              strokeDasharray="4 2"
            />
          )}
          <AxisLeft
            scale={yScale}
            stroke={borderColor}
            tickStroke={borderColor}
            tickLabelProps={{ fill: mutedColor, fontSize: 10, textAnchor: "end", dx: -6 }}
            numTicks={4}
            tickFormat={(v) => formatSpectrumEnergy(Number(v), axisDecimals)}
            label="Energy (Ha)"
            labelOffset={58}
            labelProps={{ fill: mutedColor, fontSize: 10, textAnchor: "middle" }}
          />
        </Group>
      </svg>
    </figure>
  );
}

interface SpectrumLadderProps {
  readonly energies: number[];
  readonly referenceEnergy?: number;
  readonly highlightedIndex?: number;
  readonly className?: string;
}

export function SpectrumLadder({
  energies,
  referenceEnergy,
  highlightedIndex,
  className,
}: SpectrumLadderProps) {
  const theme = useChartTheme();
  if (energies.length === 0) return <ChartEmptyState message="No eigenvalues" />;

  return (
    <div className={className ?? "h-full w-full"}>
      <ParentSize>
        {({ width, height }) =>
          width > 0 && height > 0 ? (
            <SpectrumLadderInner
              energies={energies}
              referenceEnergy={referenceEnergy}
              highlightedIndex={highlightedIndex}
              width={width}
              height={height}
              color={theme.chart1}
              highlightColor={theme.success}
              borderColor={theme.border}
              mutedColor={theme.muted}
            />
          ) : null
        }
      </ParentSize>
    </div>
  );
}
