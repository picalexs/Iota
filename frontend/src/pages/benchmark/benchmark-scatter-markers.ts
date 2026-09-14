import type { ChartTheme } from "@/components/results/charts/use-chart-theme";
import type { BenchmarkEntry } from "./benchmark-utils";

export type ScatterMarkerShape = "circle" | "square" | "diamond" | "triangle" | "star" | "hexagon";

export function scatterMarkerShape(family: BenchmarkEntry["algorithm"]): ScatterMarkerShape {
  switch (family) {
    case "vqe":
      return "circle";
    case "sqd":
      return "square";
    case "kqd":
      return "diamond";
    case "qfd":
      return "triangle";
    case "qse":
      return "star";
    case "skqd":
      return "hexagon";
  }
}

export function scatterFamilyColor(
  family: BenchmarkEntry["algorithm"],
  theme: Pick<ChartTheme, "chart1" | "chart2" | "chart5" | "destructive">,
): string {
  switch (family) {
    case "vqe":
      return theme.chart1;
    case "sqd":
      return theme.chart2;
    case "kqd":
      return "#8b5cf6";
    case "qfd":
      return theme.chart5;
    case "qse":
      return "#c026d3";
    case "skqd":
      return theme.destructive;
  }
}

function polarPoint(cx: number, cy: number, radius: number, angleDegrees: number) {
  const angleRadians = ((angleDegrees - 90) * Math.PI) / 180;
  return {
    x: cx + radius * Math.cos(angleRadians),
    y: cy + radius * Math.sin(angleRadians),
  };
}

function buildClosedPath(points: ReadonlyArray<{ x: number; y: number }>): string {
  if (points.length === 0) return "";
  const [first, ...rest] = points;
  if (!first) return "";
  const pathSegments = rest.map((point) => `L ${point.x} ${point.y}`).join(" ");
  return `M ${first.x} ${first.y} ${pathSegments} Z`;
}

export function buildScatterMarkerPath(
  shape: ScatterMarkerShape,
  cx: number,
  cy: number,
  size: number,
): string | null {
  switch (shape) {
    case "circle":
      return null;
    case "square":
      return buildClosedPath([
        { x: cx - size, y: cy - size },
        { x: cx + size, y: cy - size },
        { x: cx + size, y: cy + size },
        { x: cx - size, y: cy + size },
      ]);
    case "diamond":
      return buildClosedPath([
        { x: cx, y: cy - size - 0.4 },
        { x: cx + size + 0.4, y: cy },
        { x: cx, y: cy + size + 0.4 },
        { x: cx - size - 0.4, y: cy },
      ]);
    case "triangle":
      return buildClosedPath([
        polarPoint(cx, cy, size + 1, 0),
        polarPoint(cx, cy, size + 1, 120),
        polarPoint(cx, cy, size + 1, 240),
      ]);
    case "star": {
      const points = Array.from({ length: 10 }, (_, index) =>
        polarPoint(cx, cy, index % 2 === 0 ? size + 0.8 : size * 0.45, index * 36),
      );
      return buildClosedPath(points);
    }
    case "hexagon": {
      const points = Array.from({ length: 6 }, (_, index) =>
        polarPoint(cx, cy, size + 0.4, index * 60),
      );
      return buildClosedPath(points);
    }
  }
}
