export interface SpectrumLabelPoint {
  readonly index: number;
  readonly energy: number;
  readonly lineY: number;
}

export interface SpectrumLabelLayout extends SpectrumLabelPoint {
  labelY: number;
}

const LABEL_GAP = 14;

function shiftLabelsBackward(sorted: SpectrumLabelLayout[], height: number, gap: number): void {
  const lastPoint = sorted.at(-1);
  if (!lastPoint) return;
  const overflow = lastPoint.labelY - height;
  if (overflow <= 0) return;
  lastPoint.labelY -= overflow;
  for (let i = sorted.length - 2; i >= 0; i -= 1) {
    const point = sorted[i];
    const nextPoint = sorted[i + 1];
    if (point && nextPoint) point.labelY = Math.min(point.labelY, nextPoint.labelY - gap);
  }
}

function shiftLabelsForward(sorted: SpectrumLabelLayout[]): void {
  const firstPoint = sorted[0];
  if (!firstPoint || firstPoint.labelY >= 0) return;
  const underflow = -firstPoint.labelY;
  for (const point of sorted) point.labelY += underflow;
}

export function spectrumDecimalPlaces(values: number[]): number {
  const finiteValues = values.filter(Number.isFinite).sort((a, b) => a - b);
  if (finiteValues.length < 2) return 6;

  let minDiff = Number.POSITIVE_INFINITY;
  for (let i = 1; i < finiteValues.length; i += 1) {
    const current = finiteValues[i];
    const previous = finiteValues[i - 1];
    if (current === undefined || previous === undefined) {
      continue;
    }
    const diff = Math.abs(current - previous);
    if (diff > 0 && diff < minDiff) minDiff = diff;
  }

  if (!Number.isFinite(minDiff)) return 6;
  return Math.min(Math.max(Math.ceil(-Math.log10(minDiff)) + 2, 4), 8);
}

export function formatSpectrumEnergy(value: number, decimals: number): string {
  return value.toFixed(decimals);
}

export function layoutSpectrumLabels(
  points: SpectrumLabelPoint[],
  height: number,
  minGap = LABEL_GAP,
): SpectrumLabelLayout[] {
  if (points.length === 0) return [];

  const effectiveGap =
    points.length > 1 ? Math.min(minGap, height / Math.max(points.length - 1, 1)) : 0;
  const sorted = points
    .map((point) => ({
      ...point,
      labelY: Math.min(Math.max(point.lineY, 0), height),
    }))
    .sort((a, b) => a.labelY - b.labelY || a.index - b.index);

  let previousY = Number.NEGATIVE_INFINITY;
  for (const point of sorted) {
    point.labelY = Math.max(point.labelY, previousY + effectiveGap);
    previousY = point.labelY;
  }

  shiftLabelsBackward(sorted, height, effectiveGap);
  shiftLabelsForward(sorted);

  return sorted.sort((a, b) => a.index - b.index);
}
