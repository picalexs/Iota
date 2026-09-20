import { useEffect, useMemo, useState } from "react";
import { Minus, Plus } from "lucide-react";

import { fetchBackendCapabilities, getBackendCapabilitiesCached } from "@/api/backends";
import { DashboardTile } from "@/components/results/dashboard-tile";
import { TopologyMapSvg } from "@/components/topology/topology-map-svg";
import {
  buildCouplings,
  buildMapNodes,
  edgeKey,
  inferTotalQubits,
  type TopologyNode,
} from "@/components/forms/run-form/backend-topology-utils";
import { DEFAULT_TOPOLOGY_COLOR } from "@/components/forms/run-form/backend-section-shared";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import type { RunExecutionMetadata } from "@/lib/results/execution-metadata";
import type { BackendCapability, BackendDeviceSummary, UUID } from "@/types/run";

type HardwareMappingView = "map" | "layout";

interface HardwareMappingTileProps {
  readonly execution: RunExecutionMetadata;
  readonly credentialProfileId?: UUID | null;
  readonly editMode?: boolean;
}

export function HardwareMappingTile({
  execution,
  credentialProfileId = null,
  editMode,
}: Readonly<HardwareMappingTileProps>) {
  const [view, setView] = useState<HardwareMappingView>("map");
  const [zoom, setZoom] = useState(1);
  const { capabilities, loading, error } = useBackendCapabilities(
    execution.backendName,
    credentialProfileId,
  );
  const device = useMemo(
    () => findBackendDevice(capabilities, execution.backendName),
    [capabilities, execution.backendName],
  );
  const mapState = useMemo(
    () => buildMapState(device, execution.usedPhysicalQubits),
    [device, execution.usedPhysicalQubits],
  );
  const activeView = mapState == null && view === "map" ? "layout" : view;
  const mappingRows = execution.transpilationLayout;

  return (
    <DashboardTile
      title="Hardware Mapping"
      helpText="IBM Runtime physical qubit layout recorded after transpilation."
      actions={
        <div
          className="inline-flex overflow-hidden rounded-md border border-border"
          role="tablist"
          aria-label="Hardware mapping view"
        >
          {(["map", "layout"] as const).map((item) => (
            <button
              key={item}
              type="button"
              role="tab"
              aria-selected={activeView === item}
              disabled={item === "map" && mapState == null}
              className={cn(
                "h-7 min-w-16 px-2.5 text-xs font-medium text-muted-foreground transition-colors",
                activeView === item
                  ? "bg-primary/10 text-primary"
                  : "bg-background hover:bg-muted hover:text-foreground",
                item === "map" && mapState == null && "cursor-not-allowed opacity-50",
              )}
              onClick={() => {
                if (item === "map" && mapState == null) return;
                setView(item);
              }}
            >
              {item === "map" ? "Map" : "Layout"}
            </button>
          ))}
        </div>
      }
      editMode={editMode}
    >
      <div className="flex h-full min-h-0 flex-col gap-3">
        {activeView === "layout" && mappingRows.length > 0 ? (
          <MappingSummary rows={mappingRows} />
        ) : null}

        {activeView === "map" && mapState != null ? (
          <HardwareMap
            state={mapState}
            execution={execution}
            device={device}
            zoom={zoom}
            onZoomIn={() => setZoom((current) => Math.min(current + 0.2, 2.2))}
            onZoomOut={() => setZoom((current) => Math.max(current - 0.2, 0.6))}
          />
        ) : (
          <LayoutTable
            rows={mappingRows}
            device={device}
            loading={loading}
            error={error}
            backendName={execution.backendName}
          />
        )}
      </div>
    </DashboardTile>
  );
}

function MappingSummary({
  rows,
}: Readonly<{ readonly rows: RunExecutionMetadata["transpilationLayout"] }>) {
  return (
    <div className="shrink-0 border-b border-border/50 pb-3">
      <p className="text-[11px] font-medium text-muted-foreground">Logical to physical</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {rows.map((pair) => (
          <span
            key={`${pair.logical}:${pair.physical}`}
            className="inline-flex items-center rounded-full border border-border/70 bg-muted/40 px-2.5 py-1 font-mono text-[11px] font-semibold"
          >
            q{pair.logical} → {pair.physical}
          </span>
        ))}
      </div>
    </div>
  );
}

function HardwareMap({
  state,
  execution,
  device,
  zoom,
  onZoomIn,
  onZoomOut,
}: Readonly<{
  readonly state: HardwareMapState;
  readonly execution: RunExecutionMetadata;
  readonly device: BackendDeviceSummary | null;
  readonly zoom: number;
  readonly onZoomIn: () => void;
  readonly onZoomOut: () => void;
}>) {
  const usedQubits = new Set(execution.usedPhysicalQubits);
  const logicalByPhysical = new Map(
    execution.transpilationLayout.map((pair) => [pair.physical, pair.logical]),
  );
  const qubitMetadata = new Map((device?.qubit_errors ?? []).map((item) => [item.qubit, item]));
  const gateMetadata = new Map(
    (device?.gate_errors ?? []).map((item) => [edgeKey(item.source, item.target), item]),
  );
  const highlightedEdgeKeys = new Set(
    state.couplings.flatMap((coupling) => {
      const [source, target] = coupling;
      if (source === undefined || target === undefined) {
        return [];
      }
      return usedQubits.has(source) && usedQubits.has(target) ? [edgeKey(source, target)] : [];
    }),
  );
  const viewBoxWidth = state.width / zoom;
  const viewBoxHeight = state.height / zoom;
  const viewBoxX = (state.width - viewBoxWidth) / 2;
  const viewBoxY = (state.height - viewBoxHeight) / 2;
  return (
    <div className="min-h-0 flex-1">
      <div className="mb-2 flex items-center justify-end gap-1">
        <button
          type="button"
          className="inline-flex size-8 items-center justify-center rounded-md border border-border bg-background text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          onClick={onZoomOut}
          aria-label="Zoom out hardware map"
        >
          <Minus className="size-4" />
        </button>
        <button
          type="button"
          className="inline-flex size-8 items-center justify-center rounded-md border border-border bg-background text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          onClick={onZoomIn}
          aria-label="Zoom in hardware map"
        >
          <Plus className="size-4" />
        </button>
      </div>
      <div className="flex h-full w-full items-center justify-center">
        <TopologyMapSvg
          width={state.width}
          height={state.height}
          offsetX={state.offsetX}
          offsetY={state.offsetY}
          viewBoxX={viewBoxX}
          viewBoxY={viewBoxY}
          viewBoxWidth={viewBoxWidth}
          viewBoxHeight={viewBoxHeight}
          nodes={state.nodes}
          couplings={state.couplings.map(
            ([source, target]) => [source, target] as [number, number],
          )}
          nodeByIndex={state.nodeByIndex}
          ariaLabel="IBM Runtime physical qubit map"
          className="h-full min-h-[30rem] w-full overflow-hidden bg-muted/25"
          svgClassName="h-full w-full"
          getEdgeSpec={(source, target, state) => {
            const highlighted = highlightedEdgeKeys.has(edgeKey(source, target));
            const edge = gateMetadata.get(edgeKey(source, target));
            return {
              interactive: highlighted,
              title: `${source} ↔ ${target}`,
              details: buildEdgeHoverLines(edge, highlighted),
              stroke: highlighted ? DEFAULT_TOPOLOGY_COLOR : "var(--muted-foreground)",
              strokeWidth: highlighted ? 5 : 3.5,
              opacity: highlighted ? 1 : 0.28,
              hoverLines: state.hovered
                ? [{ stroke: DEFAULT_TOPOLOGY_COLOR, strokeWidth: 7 }]
                : undefined,
              testId: `hardware-map-edge-${source}-${target}`,
            };
          }}
          getNodeSpec={(node, state) => {
            const used = usedQubits.has(node.index);
            const logical = logicalByPhysical.get(node.index);
            const meta = qubitMetadata.get(node.index);
            return {
              interactive: used,
              title:
                logical == null
                  ? `Physical qubit ${node.index}`
                  : `Logical q${logical} → Physical ${node.index}`,
              details: buildQubitHoverLines(meta, logical, used),
              circle: {
                radius: used ? 17 : 11,
                fill: used ? DEFAULT_TOPOLOGY_COLOR : "var(--muted-foreground)",
                stroke: "var(--background)",
                strokeWidth: used ? 4 : 2,
                opacity: used ? 1 : 0.45,
              },
              label: {
                text: String(node.index),
                fill: used ? "#ffffff" : "var(--background)",
                dy: 3.5,
                fontSize: 8,
                opacity: used ? 1 : 0.9,
              },
              secondaryLabel:
                used && execution.transpilationLayout.length <= 16 && logical != null
                  ? {
                      text: `q${logical}`,
                      fill: DEFAULT_TOPOLOGY_COLOR,
                      dy: -24,
                      fontSize: 9,
                    }
                  : undefined,
              hoverRing: {
                radius: state.edgeEndpoint ? 20 : 16,
                stroke: DEFAULT_TOPOLOGY_COLOR,
                strokeWidth: 4,
                opacity: 0.9,
              },
              hoverCircle: {
                radius: used ? 17 : 14,
                fill: used ? DEFAULT_TOPOLOGY_COLOR : "var(--muted-foreground)",
                stroke: "#ffffff",
                strokeWidth: 2.5,
              },
              hoverLabelFill: "#ffffff",
              testId: `hardware-map-node-${node.index}`,
            };
          }}
        />
      </div>
      <p className="mt-2 text-xs text-muted-foreground">
        Hover any qubit or connection for mapping details.
      </p>
    </div>
  );
}

function buildQubitHoverLines(
  row: NonNullable<BackendDeviceSummary["qubit_errors"]>[number] | undefined,
  logical: number | undefined,
  used: boolean,
): string[] {
  let mappingLabel = "Not selected for this run";
  if (logical != null) {
    mappingLabel = `Mapped from q${logical}`;
  } else if (used) {
    mappingLabel = "Selected for this run";
  }

  return [
    mappingLabel,
    `RO ${formatMaybeScientific(row?.readout_error ?? null)}`,
    `T1 ${formatMaybeFixed(row?.t1_us ?? null)} μs`,
    `T2 ${formatMaybeFixed(row?.t2_us ?? null)} μs`,
  ];
}

function buildEdgeHoverLines(
  row: NonNullable<BackendDeviceSummary["gate_errors"]>[number] | undefined,
  highlighted: boolean,
): string[] {
  return [
    highlighted ? "Used by the mapped qubits" : "Available device connection",
    `${(row?.gate ?? "cz/cx").toUpperCase()} error ${formatMaybeScientific(row?.error ?? null)}`,
    formatMaybeNs(row?.length_ns ?? null),
  ];
}

function LayoutTable({
  rows,
  device,
  loading,
  error,
  backendName,
}: Readonly<{
  readonly rows: RunExecutionMetadata["transpilationLayout"];
  readonly device: BackendDeviceSummary | null;
  readonly loading: boolean;
  readonly error: boolean;
  readonly backendName: string | null;
}>) {
  const qubitMetadata = new Map((device?.qubit_errors ?? []).map((item) => [item.qubit, item]));
  let metadataMessage = "Backend topology metadata was not found for this run.";
  if (loading) {
    metadataMessage = `Loading topology metadata for ${backendName ?? "the IBM backend"}.`;
  } else if (error) {
    metadataMessage = "Backend topology metadata is unavailable right now.";
  }

  return (
    <div className="min-h-0 flex-1 overflow-auto rounded-md border border-border/70">
      <Table>
        <TableHeader className="sticky top-0 z-10 bg-muted">
          <TableRow>
            <TableHead>Logical</TableHead>
            <TableHead>Physical</TableHead>
            <TableHead>Readout error</TableHead>
            <TableHead>T1</TableHead>
            <TableHead>T2</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((pair) => {
            const meta = qubitMetadata.get(pair.physical);
            return (
              <TableRow key={`${pair.logical}:${pair.physical}`}>
                <TableCell className="font-mono">q{pair.logical}</TableCell>
                <TableCell className="font-mono">{pair.physical}</TableCell>
                <TableCell>{formatMaybeScientific(meta?.readout_error)}</TableCell>
                <TableCell>{formatMaybeFixed(meta?.t1_us)}</TableCell>
                <TableCell>{formatMaybeFixed(meta?.t2_us)}</TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
      {device == null ? (
        <p className="border-t border-border/60 px-3 py-2 text-xs text-muted-foreground">
          {metadataMessage}
        </p>
      ) : null}
    </div>
  );
}

interface HardwareMapState {
  nodes: TopologyNode[];
  nodeByIndex: Map<number, TopologyNode>;
  couplings: number[][];
  width: number;
  height: number;
  offsetX: number;
  offsetY: number;
}

type OptionalNumber = number | null | undefined;

function buildMapState(
  device: BackendDeviceSummary | null,
  usedPhysicalQubits: number[],
): HardwareMapState | null {
  if (device == null) return null;
  const totalQubits = inferTotalQubits(device, "ibm_runtime");
  const highestUsedQubit = Math.max(-1, ...usedPhysicalQubits);
  if ((totalQubits == null || totalQubits <= 0) && highestUsedQubit < 0) return null;

  const visibleQubits = Math.max(totalQubits ?? 0, highestUsedQubit + 1, 2);
  const couplings = buildCouplings(device, visibleQubits);
  const nodes = buildMapNodes(visibleQubits, couplings);
  if (nodes.length === 0) return null;

  const bounds = topologyBounds(nodes);
  const canvasSize = Math.max(520, bounds.width + 72, bounds.height + 72);
  return {
    nodes,
    nodeByIndex: new Map(nodes.map((node) => [node.index, node])),
    couplings,
    width: canvasSize,
    height: canvasSize,
    offsetX: (canvasSize - bounds.width) / 2 - bounds.minX,
    offsetY: (canvasSize - bounds.height) / 2 - bounds.minY,
  };
}

function topologyBounds(nodes: TopologyNode[]): {
  minX: number;
  minY: number;
  width: number;
  height: number;
} {
  const xs = nodes.map((node) => node.x);
  const ys = nodes.map((node) => node.y);
  const minX = Math.min(...xs) - 28;
  const maxX = Math.max(...xs) + 28;
  const minY = Math.min(...ys) - 34;
  const maxY = Math.max(...ys) + 28;
  return {
    minX,
    minY,
    width: maxX - minX,
    height: maxY - minY,
  };
}

function useBackendCapabilities(
  backendName: string | null,
  credentialProfileId: UUID | null,
): {
  capabilities: BackendCapability[] | null;
  loading: boolean;
  error: boolean;
} {
  const [capabilities, setCapabilities] = useState<BackendCapability[] | null>(
    () => getBackendCapabilitiesCached(credentialProfileId)?.backends ?? null,
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (backendName == null) return;
    let active = true;
    setLoading(true);
    setError(false);

    fetchBackendCapabilities(credentialProfileId)
      .then((data) => {
        if (!active) return;
        setCapabilities(data.backends);
      })
      .catch(() => {
        if (!active) return;
        setError(true);
      })
      .finally(() => {
        if (!active) return;
        setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [backendName, credentialProfileId]);

  return { capabilities, loading, error };
}

function findBackendDevice(
  capabilities: BackendCapability[] | null,
  backendName: string | null,
): BackendDeviceSummary | null {
  const normalizedName = backendName?.trim().toLowerCase();
  if (!normalizedName) return null;

  for (const capability of capabilities ?? []) {
    for (const device of capability.backends ?? []) {
      if (device.name.trim().toLowerCase() === normalizedName) {
        return device;
      }
    }
  }
  return null;
}

function formatMaybeScientific(value: OptionalNumber): string {
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
