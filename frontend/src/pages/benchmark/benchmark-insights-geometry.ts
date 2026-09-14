import { formatRuntimeMinutes } from "./benchmark-insights-formatters";
import type { RuntimeScatterMetrics, ScatterLabelLayout } from "./benchmark-scatter-panel";
import type { CompletedPoint } from "./benchmark-scatter-data";

interface ScatterPlacedPoint {
  point: CompletedPoint;
  pointX: number;
  pointY: number;
  label: string;
}

interface ScatterLabelPlacement {
  layout: ScatterLabelLayout;
  rect: ReturnType<typeof scatterLabelRect>;
}

type InsightsPanelMode = "embedded" | "fullscreen";

const SCATTER_LABEL_CHAR_WIDTH = 6.1;
const SCATTER_LABEL_HEIGHT = 13;
const SCATTER_LABEL_MARGIN = 4;
const SCATTER_LABEL_POINT_GAP = 10;
const SCATTER_LABEL_VERTICAL_OFFSETS = [14, -10, 28, -24, 42, -38] as const;
const SCATTER_RUNTIME_TICK_LABEL_CHAR_WIDTH = 6.6;
const SCATTER_RUNTIME_TICK_MIN_GAP = 18;
const MAX_SCATTER_INLINE_LABELS = 12;

function estimateScatterLabelWidth(label: string): number {
  return Math.max(32, label.length * SCATTER_LABEL_CHAR_WIDTH);
}

function scatterLabelRect(
  labelX: number,
  labelY: number,
  labelWidth: number,
  textAnchor: "start" | "end",
) {
  const left = textAnchor === "start" ? labelX : labelX - labelWidth;
  const right = textAnchor === "start" ? labelX + labelWidth : labelX;
  return {
    left,
    right,
    top: labelY - SCATTER_LABEL_HEIGHT,
    bottom: labelY + 3,
  };
}

function scatterRectsOverlap(
  left: ReturnType<typeof scatterLabelRect>,
  right: ReturnType<typeof scatterLabelRect>,
): boolean {
  return !(
    left.right + SCATTER_LABEL_MARGIN < right.left ||
    right.right + SCATTER_LABEL_MARGIN < left.left ||
    left.bottom + SCATTER_LABEL_MARGIN < right.top ||
    right.bottom + SCATTER_LABEL_MARGIN < left.top
  );
}

function buildScatterPlacedPoints({
  points,
  xForRuntime,
  yForError,
}: Readonly<{
  points: readonly CompletedPoint[];
  xForRuntime: (runtime: number) => number;
  yForError: (error: number) => number;
}>): ScatterPlacedPoint[] {
  return points
    .map((point) => ({
      point,
      pointX: xForRuntime(point.runtime),
      pointY: yForError(point.absErrorMha),
      label: `${point.moleculeShort} ${point.algorithm}`,
    }))
    .sort(
      (left, right) =>
        left.pointX - right.pointX ||
        left.pointY - right.pointY ||
        left.point.absErrorMha - right.point.absErrorMha,
    );
}

function isScatterLabelRectInBounds({
  rect,
  width,
  height,
  pad,
}: Readonly<{
  rect: ReturnType<typeof scatterLabelRect>;
  width: number;
  height: number;
  pad: number;
}>): boolean {
  return !(
    rect.left < pad + 2 ||
    rect.right > width - pad + 2 ||
    rect.top < pad + 2 ||
    rect.bottom > height - pad - 2
  );
}

function buildScatterLabelSides(
  preferRight: boolean,
): readonly ["right", "left"] | readonly ["left", "right"] {
  return preferRight ? ["right", "left"] : ["left", "right"];
}

function findScatterLabelPlacement({
  pointX,
  pointY,
  labelWidth,
  preferRight,
  width,
  height,
  pad,
  placedRects,
}: Readonly<{
  pointX: number;
  pointY: number;
  labelWidth: number;
  preferRight: boolean;
  width: number;
  height: number;
  pad: number;
  placedRects: ReadonlyArray<ReturnType<typeof scatterLabelRect>>;
}>): ScatterLabelPlacement | null {
  for (const side of buildScatterLabelSides(preferRight)) {
    const textAnchor = side === "right" ? "start" : "end";
    const labelX =
      side === "right" ? pointX + SCATTER_LABEL_POINT_GAP : pointX - SCATTER_LABEL_POINT_GAP;

    for (const offsetY of SCATTER_LABEL_VERTICAL_OFFSETS) {
      const labelY = pointY + offsetY;
      const rect = scatterLabelRect(labelX, labelY, labelWidth, textAnchor);

      if (!isScatterLabelRectInBounds({ rect, width, height, pad })) {
        continue;
      }
      if (placedRects.some((placedRect) => scatterRectsOverlap(placedRect, rect))) {
        continue;
      }

      return {
        layout: { x: labelX, y: labelY, textAnchor },
        rect,
      };
    }
  }

  return null;
}

function buildFallbackScatterLabelPlacement({
  pointX,
  pointY,
  labelWidth,
  preferRight,
  width,
  height,
  pad,
}: Readonly<{
  pointX: number;
  pointY: number;
  labelWidth: number;
  preferRight: boolean;
  width: number;
  height: number;
  pad: number;
}>): ScatterLabelPlacement {
  const textAnchor = preferRight ? "start" : "end";
  const unclampedX = preferRight
    ? pointX + SCATTER_LABEL_POINT_GAP
    : pointX - SCATTER_LABEL_POINT_GAP;
  const labelX =
    textAnchor === "start"
      ? Math.min(unclampedX, width - pad - labelWidth - 2)
      : Math.max(unclampedX, pad + labelWidth + 2);
  const labelY = Math.min(Math.max(pointY + 14, pad + 14), height - pad - 6);
  const layout = { x: labelX, y: labelY, textAnchor } satisfies ScatterLabelLayout;

  return {
    layout,
    rect: scatterLabelRect(labelX, labelY, labelWidth, textAnchor),
  };
}

function buildScatterLabelLayouts({
  points,
  width,
  height,
  pad,
  xForRuntime,
  yForError,
  allowFallback,
}: Readonly<{
  points: readonly CompletedPoint[];
  width: number;
  height: number;
  pad: number;
  xForRuntime: (runtime: number) => number;
  yForError: (error: number) => number;
  allowFallback: boolean;
}>): Map<string, ScatterLabelLayout> {
  const layouts = new Map<string, ScatterLabelLayout>();
  const placedRects: Array<ReturnType<typeof scatterLabelRect>> = [];
  const placedPoints = buildScatterPlacedPoints({
    points,
    xForRuntime,
    yForError,
  });

  for (const { point, pointX, pointY, label } of placedPoints) {
    const labelWidth = estimateScatterLabelWidth(label);
    const preferRight = pointX + SCATTER_LABEL_POINT_GAP + labelWidth <= width - pad;
    const placement = findScatterLabelPlacement({
      pointX,
      pointY,
      labelWidth,
      preferRight,
      width,
      height,
      pad,
      placedRects,
    });

    if (placement) {
      layouts.set(point.id, placement.layout);
      placedRects.push(placement.rect);
      continue;
    }

    if (!allowFallback) {
      continue;
    }

    const fallbackPlacement = buildFallbackScatterLabelPlacement({
      pointX,
      pointY,
      labelWidth,
      preferRight,
      width,
      height,
      pad,
    });

    layouts.set(point.id, fallbackPlacement.layout);
    placedRects.push(fallbackPlacement.rect);
  }

  return layouts;
}

export function buildLogTicks(minValue: number, maxValue: number, targetValue: number): number[] {
  const candidates = new Set<number>([minValue, targetValue, maxValue]);
  const startPower = Math.floor(Math.log10(minValue));
  const endPower = Math.ceil(Math.log10(maxValue));

  for (let power = startPower; power <= endPower; power += 1) {
    const base = 10 ** power;
    for (const multiplier of [1, 2, 5]) {
      const tick = multiplier * base;
      if (tick > minValue && tick < maxValue) {
        candidates.add(tick);
      }
    }
  }

  const sorted = Array.from(candidates).sort((left, right) => left - right);
  if (sorted.length <= 6) return sorted;

  const anchors = new Set<number>([minValue, targetValue, maxValue]);
  const remaining = sorted.filter((value) => !anchors.has(value));
  const slots = Math.max(0, 6 - anchors.size);
  const stride = slots > 0 ? Math.ceil(remaining.length / slots) : remaining.length;
  const sampled = remaining.filter((_, index) => index % Math.max(1, stride) === 0).slice(0, slots);

  return Array.from(new Set([...anchors, ...sampled])).sort((left, right) => left - right);
}

export function buildRuntimeLogTicks(minValue: number, maxValue: number): number[] {
  if (maxValue <= minValue) return [minValue];

  const candidates = new Set<number>([minValue, maxValue]);
  const startPower = Math.floor(Math.log10(minValue));
  const endPower = Math.ceil(Math.log10(maxValue));

  for (let power = startPower; power <= endPower; power += 1) {
    const base = 10 ** power;
    for (const multiplier of [1, 2, 5]) {
      const tick = multiplier * base;
      if (tick > minValue && tick < maxValue) {
        candidates.add(tick);
      }
    }
  }

  const sorted = Array.from(candidates).sort((left, right) => left - right);
  if (sorted.length <= 6) return sorted;

  const anchors = new Set<number>([minValue, maxValue]);
  const remaining = sorted.filter((value) => !anchors.has(value));
  const slots = Math.max(0, 6 - anchors.size);
  const stride = slots > 0 ? Math.ceil(remaining.length / slots) : remaining.length;
  const sampled = remaining.filter((_, index) => index % Math.max(1, stride) === 0).slice(0, slots);

  return Array.from(new Set([...anchors, ...sampled])).sort((left, right) => left - right);
}

function estimateRuntimeTickLabelWidth(value: number): number {
  return Math.max(24, formatRuntimeMinutes(value).length * SCATTER_RUNTIME_TICK_LABEL_CHAR_WIDTH);
}

export function filterRuntimeTicksBySpacing(
  ticks: readonly number[],
  xForRuntime: (runtime: number) => number,
): number[] {
  const selected: number[] = [];

  ticks.forEach((tick, index) => {
    if (selected.length === 0) {
      selected.push(tick);
      return;
    }

    const isLast = index === ticks.length - 1;
    while (selected.length > 1) {
      const previousTick = selected[selected.length - 1];
      if (previousTick === undefined) {
        return;
      }
      const requiredGap =
        estimateRuntimeTickLabelWidth(previousTick) / 2 +
        estimateRuntimeTickLabelWidth(tick) / 2 +
        SCATTER_RUNTIME_TICK_MIN_GAP;
      if (xForRuntime(tick) - xForRuntime(previousTick) >= requiredGap) {
        break;
      }
      if (!isLast) {
        return;
      }
      selected.pop();
    }

    const previousTick = selected[selected.length - 1];
    if (previousTick === undefined) {
      return;
    }
    const requiredGap =
      estimateRuntimeTickLabelWidth(previousTick) / 2 +
      estimateRuntimeTickLabelWidth(tick) / 2 +
      SCATTER_RUNTIME_TICK_MIN_GAP;

    if (xForRuntime(tick) - xForRuntime(previousTick) >= requiredGap) {
      selected.push(tick);
      return;
    }

    if (isLast && previousTick !== tick) {
      selected[selected.length - 1] = tick;
    }
  });

  return selected;
}

export function buildRuntimeScatterMetrics({
  points,
  chemicalAccuracyHa,
  mode,
}: Readonly<{
  points: readonly CompletedPoint[];
  chemicalAccuracyHa: number;
  mode: InsightsPanelMode;
}>): RuntimeScatterMetrics {
  const width = mode === "fullscreen" ? 1120 : 760;
  const height = mode === "fullscreen" ? 540 : 360;
  const topPad = 88;
  const rightPad = 88;
  const bottomPad = 88;
  const leftPad = mode === "fullscreen" ? 108 : 100;
  const plotWidth = width - leftPad - rightPad;
  const plotHeight = height - topPad - bottomPad;
  const positiveRuntimes = points.map((point) => point.runtime).filter((value) => value > 0);
  const maxRuntime = positiveRuntimes.length > 0 ? Math.max(...positiveRuntimes) : 1;
  const minRuntime = positiveRuntimes.length > 0 ? Math.min(...positiveRuntimes) : 0.01;
  const targetMha = chemicalAccuracyHa * 1000;
  const positiveErrors = points.map((point) => point.absErrorMha).filter((value) => value > 0);
  const minPositiveError = positiveErrors.length > 0 ? Math.min(...positiveErrors) : targetMha / 4;
  const minError = Math.max(0.01, Math.min(targetMha / 4, minPositiveError / 2));
  const maxError = Math.max(
    ...points.map((point) => point.absErrorMha),
    targetMha * 2,
    minError * 10,
  );
  const logRuntimeMin = Math.log10(minRuntime);
  const logRuntimeMax = Math.log10(maxRuntime);
  const logMin = Math.log10(minError);
  const logMax = Math.log10(maxError);
  const reduceInlineLabels = points.length > MAX_SCATTER_INLINE_LABELS;
  const xForRuntime = (runtime: number) => {
    if (Math.abs(logRuntimeMax - logRuntimeMin) <= 1e-9) {
      return leftPad + plotWidth / 2;
    }

    const safeValue = Math.max(runtime, minRuntime);
    const normalized =
      (Math.log10(safeValue) - logRuntimeMin) / Math.max(1e-9, logRuntimeMax - logRuntimeMin);
    return leftPad + normalized * plotWidth;
  };
  const runtimeTicks = filterRuntimeTicksBySpacing(
    buildRuntimeLogTicks(minRuntime, maxRuntime),
    xForRuntime,
  );
  const errorTicks = buildLogTicks(minError, maxError, targetMha);
  const yForError = (error: number) => {
    const safeValue = Math.max(error, minError);
    const normalized = (Math.log10(safeValue) - logMin) / Math.max(1e-9, logMax - logMin);
    return height - bottomPad - normalized * plotHeight;
  };

  return {
    width,
    height,
    topPad,
    leftPad,
    rightPad,
    bottomPad,
    plotWidth,
    targetMha,
    runtimeTicks,
    errorTicks,
    targetY: yForError(targetMha),
    reduceInlineLabels,
    xForRuntime,
    labelLayouts: buildScatterLabelLayouts({
      points,
      width,
      height,
      pad: Math.max(leftPad, topPad, rightPad, bottomPad),
      xForRuntime,
      yForError,
      allowFallback: !reduceInlineLabels,
    }),
    yForError,
  };
}
