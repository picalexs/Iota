import type { BackendDeviceSummary } from "@/types/run";

import { type BackendTopologyView, type TopologyMetric } from "./backend-section-shared";
import {
  edgeKey,
  metricColor,
  metricPercent,
  metricValue,
  shouldShowGraphLabel,
  type TopologyNode,
  type TopologyTableRow,
} from "./backend-topology-utils";

export interface TopologyDiagramExportOptions {
  activeView: BackendTopologyView;
  graphRows: TopologyTableRow[];
  graphLabelStep: number;
  graphBarWidth: number;
  graphCanvasWidth: number;
  shouldInvertMetricScale: boolean;
  nodes: TopologyNode[];
  couplings: number[][];
  gateMetadata: Map<string, NonNullable<BackendDeviceSummary["gate_errors"]>[number]>;
  qubitMetadata: Map<number, NonNullable<BackendDeviceSummary["qubit_errors"]>[number]>;
  edgeRange: { min: number; max: number };
  qubitMetric: TopologyMetric;
  metricRange: { min: number; max: number };
  invert: boolean;
  mapOffsetX: number;
  mapOffsetY: number;
  width: number;
  height: number;
}

const GRAPH_HEIGHT = 352;

export function buildTopologyCalibrationCsv(
  tableRows: TopologyTableRow[],
  gateErrors: NonNullable<BackendDeviceSummary["gate_errors"]>,
): string {
  const header = [
    "record_type",
    "qubit",
    "source",
    "target",
    "readout_error",
    "t1_us",
    "t2_us",
    "degree",
    "best_gate_error",
    "worst_gate_error",
    "operational",
    "gate",
    "error",
    "length_ns",
  ];
  const qubitRows = tableRows.map((row) => [
    "qubit",
    row.qubit,
    "",
    "",
    row.readout_error ?? "",
    row.t1_us ?? "",
    row.t2_us ?? "",
    row.degree,
    row.bestGateError ?? "",
    row.worstGateError ?? "",
    row.operational ?? "",
    "",
    "",
    "",
  ]);
  const gateRows = gateErrors.map((row) => [
    "gate",
    "",
    row.source,
    row.target,
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    row.gate,
    row.error,
    row.length_ns,
  ]);
  return [header, ...qubitRows, ...gateRows]
    .map((row) => row.map((value) => `"${String(value).replaceAll('"', '""')}"`).join(","))
    .join("\n");
}

export function buildActiveTopologyDiagramSvg({
  activeView,
  graphRows,
  qubitMetric,
  metricRange,
  shouldInvertMetricScale,
  graphLabelStep,
  graphBarWidth,
  graphCanvasWidth,
  ...mapOptions
}: TopologyDiagramExportOptions): string {
  if (activeView === "graph") {
    return buildGraphDiagramSvg(
      graphRows,
      qubitMetric,
      metricRange,
      shouldInvertMetricScale,
      graphLabelStep,
      graphBarWidth,
      graphCanvasWidth,
    );
  }

  return buildMapDiagramSvg({
    ...mapOptions,
    qubitMetric,
    metricRange,
    invert: shouldInvertMetricScale,
  });
}

function buildGraphDiagramSvg(
  rows: TopologyTableRow[],
  qubitMetric: TopologyMetric,
  metricRange: { min: number; max: number },
  invert: boolean,
  graphLabelStep: number,
  graphBarWidth: number,
  graphCanvasWidth: number,
): string {
  const innerHeight = 300;
  const bars = rows
    .map((row, index) => {
      const value = metricValue(row, qubitMetric);
      const heightPercent = metricPercent(value, metricRange);
      const height = Math.max(12, heightPercent * innerHeight);
      const x = 20 + index * (graphBarWidth + 4);
      const y = 20 + (innerHeight - height);
      const fill = metricColor(value, metricRange, invert);
      const label = shouldShowGraphLabel(index, rows.length, graphLabelStep)
        ? `<text x="${x + graphBarWidth / 2}" y="344" text-anchor="middle" font-size="9" fill="#6b7280">${row.qubit}</text>`
        : "";
      return `<rect x="${x}" y="${y}" width="${graphBarWidth}" height="${height}" rx="4" fill="${fill}" />${label}`;
    })
    .join("");
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${graphCanvasWidth} ${GRAPH_HEIGHT}" width="${graphCanvasWidth}" height="${GRAPH_HEIGHT}"><rect width="100%" height="100%" fill="#ffffff" /><line x1="16" y1="20" x2="16" y2="320" stroke="#d4d4d8" /><line x1="16" y1="320" x2="${graphCanvasWidth - 12}" y2="320" stroke="#d4d4d8" />${bars}</svg>`;
}

interface MapDiagramSvgOptions {
  nodes: TopologyNode[];
  couplings: number[][];
  gateMetadata: Map<string, NonNullable<BackendDeviceSummary["gate_errors"]>[number]>;
  qubitMetadata: Map<number, NonNullable<BackendDeviceSummary["qubit_errors"]>[number]>;
  edgeRange: { min: number; max: number };
  qubitMetric: TopologyMetric;
  metricRange: { min: number; max: number };
  invert: boolean;
  mapOffsetX: number;
  mapOffsetY: number;
  width: number;
  height: number;
}

function buildMapDiagramSvg({
  nodes,
  couplings,
  gateMetadata,
  qubitMetadata,
  edgeRange,
  qubitMetric,
  metricRange,
  invert,
  mapOffsetX,
  mapOffsetY,
  width,
  height,
}: MapDiagramSvgOptions): string {
  const nodeByIndex = new Map(nodes.map((node) => [node.index, node]));
  const lines = couplings
    .flatMap((coupling) => {
      const [source, target] = coupling;
      if (source === undefined || target === undefined) return [];
      const start = nodeByIndex.get(source);
      const end = nodeByIndex.get(target);
      if (start == null || end == null) return [];
      const edge = gateMetadata.get(edgeKey(source, target));
      const stroke = metricColor(edge?.error ?? null, edgeRange);
      return [
        `<line x1="${start.x + mapOffsetX}" y1="${start.y + mapOffsetY}" x2="${end.x + mapOffsetX}" y2="${end.y + mapOffsetY}" stroke="${stroke}" stroke-width="5" stroke-linecap="round" />`,
      ];
    })
    .join("");
  const circles = nodes
    .map((node) => {
      const meta = qubitMetadata.get(node.index);
      const value = metricValue(meta, qubitMetric);
      const fill = metricColor(value, metricRange, invert);
      const cx = node.x + mapOffsetX;
      const cy = node.y + mapOffsetY;
      return `<circle cx="${cx}" cy="${cy}" r="14" fill="${fill}" stroke="#ffffff" stroke-width="2.5" /><text x="${cx}" y="${cy + 4}" text-anchor="middle" font-size="10" font-weight="600" fill="#ffffff">${node.index}</text>`;
    })
    .join("");
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" width="${width}" height="${height}"><rect width="100%" height="100%" fill="#ffffff" />${lines}${circles}</svg>`;
}
