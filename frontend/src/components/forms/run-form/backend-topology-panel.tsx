import { useEffect, useMemo, useRef, useState } from "react";
import type { Dispatch, RefObject, SetStateAction } from "react";
import { Download, ExternalLink, Minus, Plus } from "lucide-react";
import {
  TopologyMapSvg,
  positionTopologyHoverBubble,
  type TopologyHoverState,
} from "@/components/topology/topology-map-svg";

import { Button } from "@/components/ui/button";
import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { overlaySurfaceSmClassName, segmentedSelectionClassName } from "@/lib/interactive-styles";
import { cn } from "@/lib/utils";
import type { BackendDeviceSummary, BackendTarget } from "@/types/run";

import {
  DEFAULT_TOPOLOGY_COLOR,
  type BackendTopologyView,
  type TopologyMetric,
  type TopologySortMode,
} from "./backend-section-shared";
import {
  buildActiveTopologyDiagramSvg,
  buildTopologyCalibrationCsv,
  type TopologyDiagramExportOptions,
} from "./backend-topology-exports";
import {
  buildCouplings,
  buildMapNodes,
  buildTableRows,
  edgeKey,
  hasDetailedTopologyMetrics,
  inferProcessorDescriptor,
  inferTotalQubits,
  metricColor,
  metricPercent,
  metricValue,
  shouldShowGraphLabel,
  topologyBounds,
  type TopologyTableRow,
} from "./backend-topology-utils";

type OptionalNumber = number | null | undefined;

const DEFAULT_TOPOLOGY_METRIC: TopologyMetric = "readout_error";
const DEFAULT_TOPOLOGY_SORT: TopologySortMode = "descending";
const GRAPH_ZOOM_MIN = 0.05;
const GRAPH_ZOOM_MAX = 3;
const GRAPH_ZOOM_STEP = 0.15;
const GRAPH_HEIGHT = 352;
const TOPOLOGY_HOVER_POINTER_SIZE = 10;

function topologyViewLabel(view: BackendTopologyView): string {
  if (view === "map") return "Map view";
  if (view === "graph") return "Graph view";
  return "Table view";
}

const TOPOLOGY_VIEWS: readonly BackendTopologyView[] = ["map", "graph", "table"];

function topologyDetailedViewMessage(
  detailedViewsEnabled: boolean,
  target: BackendTarget,
  mode: "execution" | "noise-reference",
): string | null {
  if (detailedViewsEnabled) return null;
  if (target === "aer_simulator" && mode === "execution") {
    return "Map view stays available locally on Aer. Enable an IBM-derived noise model when you want graph and table calibration views.";
  }
  return "Graph and table views require backend calibration metadata.";
}

function TopologyViewTabs({
  activeView,
  detailedViewsEnabled,
  onViewChange,
}: {
  activeView: BackendTopologyView;
  detailedViewsEnabled: boolean;
  onViewChange: (view: BackendTopologyView) => void;
}) {
  return (
    <div className="flex items-stretch" role="tablist" aria-label="Topology view">
      {TOPOLOGY_VIEWS.map((item, index) => {
        const isFirst = index === 0;
        const isLast = index === TOPOLOGY_VIEWS.length - 1;
        const isActive = activeView === item;
        const disabled = item !== "map" && !detailedViewsEnabled;
        return (
          <button
            key={item}
            type="button"
            role="tab"
            aria-selected={isActive}
            data-selected={isActive ? "true" : "false"}
            disabled={disabled}
            className={cn(
              "inline-flex min-h-9 items-center justify-center border px-3 text-sm font-medium -ml-px first:ml-0",
              segmentedSelectionClassName,
              isFirst && isLast && "rounded-md",
              isFirst && !isLast && "rounded-l-md rounded-r-none",
              isLast && !isFirst && "rounded-r-md rounded-l-none",
              !isFirst && !isLast && "rounded-none",
              !isActive && "border-border bg-surface-raised text-muted-foreground",
              disabled && "cursor-not-allowed opacity-50",
            )}
            onClick={() => {
              if (disabled) return;
              onViewChange(item);
            }}
          >
            {topologyViewLabel(item)}
          </button>
        );
      })}
    </div>
  );
}

function TopologyControl({
  activeView,
  qubitMetric,
  sortMode,
  search,
  onQubitMetricChange,
  onSortModeChange,
  onSearchChange,
}: {
  activeView: BackendTopologyView;
  qubitMetric: TopologyMetric;
  sortMode: TopologySortMode;
  search: string;
  onQubitMetricChange: (metric: TopologyMetric) => void;
  onSortModeChange: (mode: TopologySortMode) => void;
  onSearchChange: (value: string) => void;
}) {
  if (activeView === "graph") {
    return (
      <FormField label="Sort qubits" htmlFor="topology-sort-select">
        <Select
          value={sortMode}
          onValueChange={(next) => onSortModeChange(next as TopologySortMode)}
        >
          <SelectTrigger id="topology-sort-select" className="w-full">
            <SelectValue placeholder="Metric descending" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="none">Default order</SelectItem>
            <SelectItem value="ascending">Metric ascending</SelectItem>
            <SelectItem value="descending">Metric descending</SelectItem>
          </SelectContent>
        </Select>
      </FormField>
    );
  }

  if (activeView === "table") {
    return (
      <FormField label="Search" htmlFor="topology-search-input">
        <Input
          id="topology-search-input"
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="Qubit number"
        />
      </FormField>
    );
  }

  return (
    <FormField label="Qubit color" htmlFor="qubit-metric-select">
      <Select
        value={qubitMetric}
        onValueChange={(next) => onQubitMetricChange(next as TopologyMetric)}
      >
        <SelectTrigger id="qubit-metric-select">
          <SelectValue placeholder="Readout assignment error" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="readout_error">Readout assignment error</SelectItem>
          <SelectItem value="t1_us">T1</SelectItem>
          <SelectItem value="t2_us">T2</SelectItem>
        </SelectContent>
      </Select>
    </FormField>
  );
}

function TopologyDownloads({
  activeView,
  downloadBaseName,
  tableRows,
  gateErrors,
  onClose,
  diagramExportOptions,
}: {
  activeView: BackendTopologyView;
  downloadBaseName: string;
  tableRows: TopologyTableRow[];
  gateErrors: NonNullable<BackendDeviceSummary["gate_errors"]>;
  onClose: () => void;
  diagramExportOptions: TopologyDiagramExportOptions;
}) {
  const viewWidth =
    activeView === "graph" ? diagramExportOptions.graphCanvasWidth : diagramExportOptions.width;
  const viewHeight = activeView === "graph" ? GRAPH_HEIGHT : diagramExportOptions.height;

  return (
    <div className="grid gap-1">
      <Button
        type="button"
        variant="ghost"
        className="justify-start"
        onClick={() => {
          triggerFileDownload(
            `${downloadBaseName}-calibration.csv`,
            new Blob([buildTopologyCalibrationCsv(tableRows, gateErrors)], {
              type: "text/csv;charset=utf-8",
            }),
          );
          onClose();
        }}
      >
        Download all calibration data (.csv)
      </Button>
      {activeView !== "table" ? (
        <>
          <Button
            type="button"
            variant="ghost"
            className="justify-start"
            onClick={() => {
              const svg = buildActiveTopologyDiagramSvg(diagramExportOptions);
              triggerFileDownload(
                `${downloadBaseName}-${activeView}-view.svg`,
                new Blob([svg], { type: "image/svg+xml;charset=utf-8" }),
              );
              onClose();
            }}
          >
            Download {activeView} view (.svg)
          </Button>
          <Button
            type="button"
            variant="ghost"
            className="justify-start"
            onClick={() => {
              const svg = buildActiveTopologyDiagramSvg(diagramExportOptions);
              void downloadSvgMarkupAsPng(
                `${downloadBaseName}-${activeView}-view.png`,
                svg,
                viewWidth,
                viewHeight,
              );
              onClose();
            }}
          >
            Download {activeView} view (.png)
          </Button>
        </>
      ) : null}
    </div>
  );
}

function TopologyGraphView({
  graphChartRef,
  graphCanvasWidth,
  graphBarWidth,
  graphRows,
  graphLabelStep,
  qubitMetric,
  metricRange,
  shouldInvertMetricScale,
  hoveredGraphItem,
  onHoveredGraphItemChange,
  onZoomOut,
  onZoomIn,
}: {
  graphChartRef: RefObject<HTMLDivElement | null>;
  graphCanvasWidth: number;
  graphBarWidth: number;
  graphRows: TopologyTableRow[];
  graphLabelStep: number;
  qubitMetric: TopologyMetric;
  metricRange: { min: number; max: number };
  shouldInvertMetricScale: boolean;
  hoveredGraphItem: TopologyHoverState | null;
  onHoveredGraphItemChange: Dispatch<SetStateAction<TopologyHoverState | null>>;
  onZoomOut: () => void;
  onZoomIn: () => void;
}) {
  return (
    <div className="relative mt-4 rounded-md bg-muted/30 p-4">
      <div
        className={cn(
          "absolute right-3 top-3 z-20 flex items-center gap-1 rounded-md border p-1",
          overlaySurfaceSmClassName,
        )}
      >
        <Button
          id="topology-graph-zoom-out"
          type="button"
          variant="ghost"
          size="icon"
          className="size-7"
          onClick={onZoomOut}
        >
          <Minus className="size-4" />
        </Button>
        <Button type="button" variant="ghost" size="icon" className="size-7" onClick={onZoomIn}>
          <Plus className="size-4" />
        </Button>
      </div>
      <div className="overflow-x-auto">
        <div
          ref={graphChartRef}
          className="relative border-b border-l border-border/80 px-2 pb-7 pt-6"
          style={{ minWidth: `${graphCanvasWidth}px`, height: "22rem" }}
          onMouseLeave={() => onHoveredGraphItemChange(null)}
        >
          {hoveredGraphItem != null ? (
            <TopologyFloatingHoverBubble
              hover={hoveredGraphItem}
              width={graphCanvasWidth}
              height={GRAPH_HEIGHT}
            />
          ) : null}
          <div className="flex h-full items-end gap-px">
            {graphRows.map((row, index) => {
              const value = metricValue(row, qubitMetric);
              const heightPercent = metricPercent(value, metricRange);
              const barId = `graph:${row.qubit}`;
              const isHovered = hoveredGraphItem?.id === barId;
              return (
                <div
                  key={row.qubit}
                  className="relative flex h-full items-end justify-center"
                  style={{ width: `${graphBarWidth}px`, minWidth: `${graphBarWidth}px` }}
                >
                  <div
                    data-testid={`topology-graph-bar-${row.qubit}`}
                    className="w-full rounded-t-md border border-b-0 border-background/80"
                    style={{
                      height: `${Math.max(12, heightPercent * 100)}%`,
                      backgroundColor: metricColor(value, metricRange, shouldInvertMetricScale),
                      boxShadow: isHovered ? "0 0 0 2px var(--primary)" : undefined,
                    }}
                    onMouseEnter={(event) => {
                      const container = graphChartRef.current?.getBoundingClientRect();
                      const bar = event.currentTarget.getBoundingClientRect();
                      if (container == null) return;
                      onHoveredGraphItemChange({
                        id: barId,
                        title: `Qubit ${row.qubit}`,
                        details: compactQubitHoverLines(row),
                        anchorX: bar.left - container.left + bar.width / 2,
                        anchorY: bar.top - container.top,
                      });
                    }}
                    onMouseLeave={() =>
                      onHoveredGraphItemChange((current) =>
                        current?.id === barId ? null : current,
                      )
                    }
                  />
                  {shouldShowGraphLabel(index, graphRows.length, graphLabelStep) ? (
                    <span className="absolute -bottom-6 left-1/2 -translate-x-1/2 text-[9px] text-muted-foreground">
                      {row.qubit}
                    </span>
                  ) : null}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

function TopologyTableView({ tableRows }: { tableRows: TopologyTableRow[] }) {
  return (
    <div className="mt-4 max-h-96 overflow-auto rounded-md border border-border/70">
      <Table>
        <TableHeader className="sticky top-0 z-10 bg-muted">
          <TableRow>
            <TableHead>Qubit</TableHead>
            <TableHead>Readout error</TableHead>
            <TableHead>T1</TableHead>
            <TableHead>T2</TableHead>
            <TableHead>Connections</TableHead>
            <TableHead>Best CZ/CX error</TableHead>
            <TableHead>Worst CZ/CX error</TableHead>
            <TableHead>Operational</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {tableRows.map((row) => (
            <TableRow key={row.qubit}>
              <TableCell className="font-medium">{row.qubit}</TableCell>
              <TableCell>{formatMaybeScientific(row.readout_error)}</TableCell>
              <TableCell>{formatMaybeFixed(row.t1_us)}</TableCell>
              <TableCell>{formatMaybeFixed(row.t2_us)}</TableCell>
              <TableCell>{row.degree}</TableCell>
              <TableCell>{formatMaybeScientific(row.bestGateError)}</TableCell>
              <TableCell>{formatMaybeScientific(row.worstGateError)}</TableCell>
              <TableCell>{row.operational === false ? "No" : "Yes"}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

interface BackendTopologyPanelProps {
  target: BackendTarget;
  device: BackendDeviceSummary | null;
  mode: "execution" | "noise-reference";
}

export function BackendTopologyPanel({ target, device, mode }: BackendTopologyPanelProps) {
  const [view, setView] = useState<BackendTopologyView>("map");
  const [hoveredGraphItem, setHoveredGraphItem] = useState<TopologyHoverState | null>(null);
  const [qubitMetric, setQubitMetric] = useState<TopologyMetric>(DEFAULT_TOPOLOGY_METRIC);
  const [sortMode, setSortMode] = useState<TopologySortMode>(DEFAULT_TOPOLOGY_SORT);
  const [search, setSearch] = useState("");
  const [graphZoom, setGraphZoom] = useState(0.5);
  const [downloadsOpen, setDownloadsOpen] = useState(false);
  const graphChartRef = useRef<HTMLDivElement | null>(null);

  const totalQubits = inferTotalQubits(device, target);
  const visibleQubits = totalQubits != null ? Math.min(Math.max(totalQubits, 2), 220) : 0;

  const qubitMetadata = useMemo(
    () => new Map((device?.qubit_errors ?? []).map((item) => [item.qubit, item])),
    [device?.qubit_errors],
  );
  const gateMetadata = useMemo(
    () =>
      new Map((device?.gate_errors ?? []).map((item) => [edgeKey(item.source, item.target), item])),
    [device?.gate_errors],
  );
  const detailedViewsEnabled = hasDetailedTopologyMetrics(device);

  useEffect(() => {
    if (!detailedViewsEnabled) {
      setView("map");
    }
  }, [detailedViewsEnabled]);

  useEffect(() => {
    setHoveredGraphItem(null);
    setDownloadsOpen(false);
  }, [device?.name, mode, target]);

  if (visibleQubits === 0) {
    return (
      <div className="rounded-lg border border-border/70 bg-card p-5 text-sm text-muted-foreground">
        Select a backend with qubit metadata to preview its qubit layer.
      </div>
    );
  }

  const activeView = view;
  const shouldInvertMetricScale = qubitMetric === "t1_us" || qubitMetric === "t2_us";
  const metricValues = Array.from({ length: visibleQubits }, (_, qubit) =>
    metricValue(qubitMetadata.get(qubit), qubitMetric),
  ).filter(isNumber);
  const qubitMedian = medianValue(metricValues);
  const metricRange = rangeFor(metricValues);
  const couplings = buildCouplings(device, visibleQubits);
  const nodes = buildMapNodes(
    visibleQubits,
    couplings,
    (device?.coupling_map?.length ?? 0) > 0 || (device?.gate_errors?.length ?? 0) > 0,
  );
  const nodeByIndex = new Map(nodes.map((node) => [node.index, node]));
  const bounds = topologyBounds(nodes);
  const width = Math.max(640, bounds.width + 56);
  const height = Math.max(320, bounds.height + 56);
  const mapOffsetX = (width - bounds.width) / 2 - bounds.minX;
  const mapOffsetY = (height - bounds.height) / 2 - bounds.minY;
  const edgeRange = edgeErrorRange(device);
  const processorDescriptor = inferProcessorDescriptor(device, visibleQubits, couplings);
  const tableRows = buildTableRows(visibleQubits, couplings, qubitMetadata, gateMetadata).filter(
    (row) => search.trim().length === 0 || String(row.qubit).includes(search.trim()),
  );
  const graphRows = [...tableRows].sort((a, b) => {
    const aValue = metricValue(a, qubitMetric) ?? Number.POSITIVE_INFINITY;
    const bValue = metricValue(b, qubitMetric) ?? Number.POSITIVE_INFINITY;
    if (sortMode === "ascending") return aValue - bValue;
    if (sortMode === "descending") return bValue - aValue;
    return a.qubit - b.qubit;
  });
  const graphLabelStep = graphLabelInterval(graphRows.length);
  const graphBarWidth = Math.max(2, Math.round(graphZoom * 16));
  const graphCanvasWidth = Math.max(680, graphRows.length * (graphBarWidth + 1) + 64);
  const detailedViewMessage = topologyDetailedViewMessage(detailedViewsEnabled, target, mode);
  const downloadBaseName = (device?.name ?? target).replace(/[^a-z0-9_-]+/gi, "-").toLowerCase();
  const canShowLegend = activeView !== "table" && metricValues.length > 0;
  const diagramExportOptions: TopologyDiagramExportOptions = {
    activeView,
    graphRows,
    graphLabelStep,
    graphBarWidth,
    graphCanvasWidth,
    shouldInvertMetricScale,
    nodes,
    couplings,
    gateMetadata,
    qubitMetadata,
    edgeRange,
    qubitMetric,
    metricRange,
    invert: shouldInvertMetricScale,
    mapOffsetX,
    mapOffsetY,
    width,
    height,
  };

  return (
    <div className="rounded-lg border border-border/70 bg-card p-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <p className="text-sm font-medium">Backend topology</p>
        </div>
        <div className="flex w-full flex-col items-end gap-2 lg:w-auto">
          <div className="flex items-stretch">
            <TopologyViewTabs
              activeView={activeView}
              detailedViewsEnabled={detailedViewsEnabled}
              onViewChange={setView}
            />
          </div>
          <div className="flex items-center gap-2">
            {processorDescriptor?.ibmUrl != null ? (
              <a
                href={processorDescriptor.ibmUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex h-9 items-center gap-1.5 rounded-md border border-border px-3 text-xs font-medium text-foreground hover:bg-muted"
              >
                View on IBM Quantum
                <ExternalLink className="size-3.5 shrink-0" />
              </a>
            ) : null}
            <Popover open={downloadsOpen} onOpenChange={setDownloadsOpen}>
              <PopoverTrigger asChild>
                <Button variant="outline" size="icon" className="size-9 shrink-0" title="Download">
                  <Download className="size-4" />
                </Button>
              </PopoverTrigger>
              <PopoverContent align="end" className="w-64 p-1">
                <TopologyDownloads
                  activeView={activeView}
                  downloadBaseName={downloadBaseName}
                  tableRows={tableRows}
                  gateErrors={device?.gate_errors ?? []}
                  onClose={() => setDownloadsOpen(false)}
                  diagramExportOptions={diagramExportOptions}
                />
              </PopoverContent>
            </Popover>
          </div>
        </div>
      </div>

      {detailedViewMessage != null ? (
        <p className="mt-3 text-xs text-muted-foreground">{detailedViewMessage}</p>
      ) : null}

      <div
        className={cn(
          "flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between",
          activeView === "table" ? "mt-3" : "mt-1",
        )}
      >
        <div className="grid min-w-[200px] gap-3">
          <TopologyControl
            activeView={activeView}
            qubitMetric={qubitMetric}
            sortMode={sortMode}
            search={search}
            onQubitMetricChange={setQubitMetric}
            onSortModeChange={setSortMode}
            onSearchChange={setSearch}
          />
        </div>

        {canShowLegend ? (
          <MetricLegend
            metric={qubitMetric}
            range={metricRange}
            median={qubitMedian}
            invert={shouldInvertMetricScale}
          />
        ) : null}
      </div>

      {activeView === "map" && (
        <div className="mt-4">
          <div className="flex min-h-[22rem] items-center justify-center">
            <TopologyMapSvg
              width={width}
              height={height}
              offsetX={mapOffsetX}
              offsetY={mapOffsetY}
              nodes={nodes}
              couplings={couplings.map(
                ([source, targetNode]) => [source, targetNode] as [number, number],
              )}
              nodeByIndex={nodeByIndex}
              ariaLabel="Backend qubit topology map"
              className="w-full bg-muted/30"
              svgClassName="h-[min(66vh,46rem)] w-full max-w-full"
              getEdgeSpec={(source, targetNode, state) => {
                const edge = gateMetadata.get(edgeKey(source, targetNode));
                const stroke = metricColor(edge?.error ?? null, edgeRange);
                return {
                  interactive: true,
                  title: `${source} ↔ ${targetNode}`,
                  details: compactEdgeHoverLines(edge),
                  stroke,
                  strokeWidth: 5,
                  testId: `backend-topology-edge-${source}-${targetNode}`,
                  hoverLines: state.hovered
                    ? [{ stroke: "#ef4444", strokeWidth: 7 }]
                    : undefined,
                };
              }}
              getNodeSpec={(node) => {
                const meta = qubitMetadata.get(node.index);
                const fill = metricColor(
                  metricValue(meta, qubitMetric),
                  metricRange,
                  shouldInvertMetricScale,
                );
                return {
                  interactive: true,
                  title: `Qubit ${node.index}`,
                  details: compactQubitHoverLines(meta),
                  circle: {
                    radius: 14,
                    fill,
                    stroke: "var(--background)",
                    strokeWidth: 2.5,
                  },
                  label: {
                    text: String(node.index),
                    fill: topologyNodeLabelColor(fill),
                  },
                  hoverRing: {
                    radius: 16,
                    stroke: DEFAULT_TOPOLOGY_COLOR,
                    strokeWidth: 4,
                    opacity: 0.9,
                  },
                  hoverCircle: {
                    radius: 14,
                    fill,
                    stroke: "#ffffff",
                    strokeWidth: 2.5,
                  },
                  hoverLabelFill: topologyNodeLabelColor(fill),
                  testId: `backend-topology-node-${node.index}`,
                };
              }}
            />
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            Connections are colored by reported CZ/CX error. Hover any qubit or connection for
            details.
          </p>
        </div>
      )}

      {activeView === "graph" ? (
        <TopologyGraphView
          graphChartRef={graphChartRef}
          graphCanvasWidth={graphCanvasWidth}
          graphBarWidth={graphBarWidth}
          graphRows={graphRows}
          graphLabelStep={graphLabelStep}
          qubitMetric={qubitMetric}
          metricRange={metricRange}
          shouldInvertMetricScale={shouldInvertMetricScale}
          hoveredGraphItem={hoveredGraphItem}
          onHoveredGraphItemChange={setHoveredGraphItem}
          onZoomOut={() =>
            setGraphZoom((current) =>
              Math.max(GRAPH_ZOOM_MIN, Number((current - GRAPH_ZOOM_STEP).toFixed(2))),
            )
          }
          onZoomIn={() =>
            setGraphZoom((current) =>
              Math.min(GRAPH_ZOOM_MAX, Number((current + GRAPH_ZOOM_STEP).toFixed(2))),
            )
          }
        />
      ) : null}

      {activeView === "table" ? <TopologyTableView tableRows={tableRows} /> : null}
    </div>
  );
}

function TopologyFloatingHoverBubble({
  hover,
  width,
  height,
}: {
  hover: TopologyHoverState;
  width: number;
  height: number;
}) {
  const { lines, bubbleWidth, bubbleHeight } = topologyHoverBubbleMetrics(hover);
  const frame = positionTopologyHoverBubble({
    anchorX: hover.anchorX,
    anchorY: hover.anchorY,
    bubbleWidth,
    bubbleHeight,
    width,
    height,
  });
  const bubbleAboveAnchor = frame.y < hover.anchorY;
  const pointerOffset = Math.min(frame.width - 22, Math.max(22, hover.anchorX - frame.x));
  const outerPointerTop = bubbleAboveAnchor
    ? `calc(100% - ${TOPOLOGY_HOVER_POINTER_SIZE + 1}px)`
    : "1px";
  const innerPointerTop = bubbleAboveAnchor
    ? `calc(100% - ${TOPOLOGY_HOVER_POINTER_SIZE - 1}px)`
    : "2px";
  const pointerClipPath = bubbleAboveAnchor
    ? "polygon(0 0, 100% 0, 50% 100%)"
    : "polygon(50% 0, 0 100%, 100% 100%)";

  return (
    <div
      className="pointer-events-none absolute left-0 top-0 z-10"
      style={{ transform: `translate(${frame.x}px, ${frame.y}px)`, width: `${frame.width}px` }}
    >
      <div
        className="absolute h-4 w-5 -translate-x-1/2 bg-border"
        style={{
          left: `${pointerOffset}px`,
          top: outerPointerTop,
          clipPath: pointerClipPath,
        }}
      />
      <div
        className="absolute h-3 w-4 -translate-x-1/2 bg-surface-overlay"
        style={{
          left: `${pointerOffset}px`,
          top: innerPointerTop,
          clipPath: pointerClipPath,
        }}
      />
      <div
        className={cn(
          "rounded-lg border px-3 py-2.5 text-sm leading-snug text-foreground",
          overlaySurfaceSmClassName,
        )}
        style={{
          marginTop: bubbleAboveAnchor ? 0 : `${TOPOLOGY_HOVER_POINTER_SIZE}px`,
          marginBottom: bubbleAboveAnchor ? `${TOPOLOGY_HOVER_POINTER_SIZE}px` : 0,
        }}
      >
        <p className="font-semibold text-[1rem]">{hover.title}</p>
        {lines.map((detail) => (
          <p key={detail} className="mt-0.5 text-[0.9rem] text-muted-foreground">
            {detail}
          </p>
        ))}
      </div>
    </div>
  );
}

function topologyHoverBubbleMetrics(hover: TopologyHoverState): {
  lines: string[];
  bubbleWidth: number;
  bubbleHeight: number;
} {
  const lines = hover.details.slice(0, 3);
  return {
    lines,
    bubbleWidth: Math.min(
      256,
      Math.max(152, longestHoverLineLength([hover.title, ...lines]) * 6.8 + 28),
    ),
    bubbleHeight: 40 + lines.length * 20 + TOPOLOGY_HOVER_POINTER_SIZE,
  };
}

function longestHoverLineLength(lines: string[]): number {
  return lines.reduce((longest, line) => Math.max(longest, line.length), 0);
}

function topologyNodeLabelColor(fill: string): string {
  return fill === "#dbe3f5" ? "#0f172a" : "#ffffff";
}

function edgeErrorRange(device: BackendDeviceSummary | null): { min: number; max: number } {
  return rangeFor((device?.gate_errors ?? []).map((item) => item.error).filter(isNumber));
}

function rangeFor(values: number[]): { min: number; max: number } {
  if (values.length === 0) return { min: 0, max: 1 };
  return { min: Math.min(...values), max: Math.max(...values) };
}

function medianValue(values: number[]): number | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  if (sorted.length % 2 === 1) return sorted[middle] ?? null;
  const lower = sorted[middle - 1];
  const upper = sorted[middle];
  if (lower === undefined || upper === undefined) return null;
  return (lower + upper) / 2;
}

function isNumber(value: OptionalNumber): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function compactQubitHoverLines(
  row: NonNullable<BackendDeviceSummary["qubit_errors"]>[number] | TopologyTableRow | undefined,
): string[] {
  return [
    `RO ${formatMaybeScientific(row?.readout_error ?? null)}`,
    `T1 ${formatMaybeFixed(row?.t1_us ?? null)} μs`,
    `T2 ${formatMaybeFixed(row?.t2_us ?? null)} μs`,
  ];
}

function compactEdgeHoverLines(
  row: NonNullable<BackendDeviceSummary["gate_errors"]>[number] | undefined,
): string[] {
  return [
    `${(row?.gate ?? "cz/cx").toUpperCase()} · ${formatMaybeScientific(row?.error ?? null)}`,
    formatMaybeNs(row?.length_ns ?? null),
  ];
}

function graphLabelInterval(total: number): number {
  if (total <= 20) return 1;
  return Math.max(2, Math.ceil(total / 16));
}

function qubitMetricLabel(metric: TopologyMetric): string {
  if (metric === "readout_error") return "Readout assignment error";
  if (metric === "t1_us") return "T1 lifetime";
  return "T2 lifetime";
}

export function formatMaybeScientific(value: OptionalNumber): string {
  if (value == null || !Number.isFinite(value)) return "-";
  if (value === 0) return "0";
  return Math.abs(value) < 0.01 || Math.abs(value) >= 1000
    ? value.toExponential(3)
    : value.toFixed(4);
}

function formatMaybeFixed(value: OptionalNumber): string {
  if (value == null || !Number.isFinite(value)) return "-";
  return value.toFixed(2);
}

function formatMaybeNs(value: OptionalNumber): string {
  if (value == null || !Number.isFinite(value)) return "-";
  return `${value.toFixed(1)} ns`;
}

function MetricLegend({
  metric,
  range,
  median,
  invert,
}: {
  metric: TopologyMetric;
  range: { min: number; max: number };
  median: number | null;
  invert: boolean;
}) {
  const medianPercent = median != null ? metricPercent(median, range, invert) : null;

  return (
    <div className="w-full min-w-0 max-w-[24rem] rounded-md border border-border/70 bg-muted/20 p-3 text-xs text-muted-foreground">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-medium text-foreground">Median {formatMaybeScientific(median)}</span>
        <span className="text-right">{qubitMetricLabel(metric)}</span>
      </div>
      <div className="mt-2">
        <div className="relative h-2 rounded-full bg-gradient-to-r from-blue-500 via-violet-400 to-slate-100">
          {medianPercent != null ? (
            <span
              className="absolute top-1/2 h-4 w-0.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-foreground/80"
              style={{ left: `${medianPercent * 100}%` }}
            />
          ) : null}
        </div>
        <div className="mt-1 flex justify-between gap-3">
          <span>min {formatMaybeScientific(range.min)}</span>
          <span>max {formatMaybeScientific(range.max)}</span>
        </div>
      </div>
    </div>
  );
}

function triggerFileDownload(fileName: string, blob: Blob): void {
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = fileName;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}

async function downloadSvgMarkupAsPng(
  fileName: string,
  svgMarkup: string,
  width: number,
  height: number,
): Promise<void> {
  const svgBlob = new Blob([svgMarkup], { type: "image/svg+xml;charset=utf-8" });
  const objectUrl = URL.createObjectURL(svgBlob);
  try {
    await new Promise<void>((resolve, reject) => {
      const image = new Image();
      image.onload = () => {
        const canvas = document.createElement("canvas");
        canvas.width = Math.max(1, Math.round(width));
        canvas.height = Math.max(1, Math.round(height));
        const context = canvas.getContext("2d");
        if (context == null) {
          reject(new Error("Canvas context unavailable"));
          return;
        }
        context.fillStyle = "#ffffff";
        context.fillRect(0, 0, canvas.width, canvas.height);
        context.drawImage(image, 0, 0, canvas.width, canvas.height);
        canvas.toBlob((pngBlob) => {
          if (pngBlob == null) {
            reject(new Error("PNG export failed"));
            return;
          }
          triggerFileDownload(fileName, pngBlob);
          resolve();
        }, "image/png");
      };
      image.onerror = () => reject(new Error("SVG export failed"));
      image.src = objectUrl;
    });
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}
