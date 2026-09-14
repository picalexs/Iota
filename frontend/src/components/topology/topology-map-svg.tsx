import { useState, type Dispatch, type SetStateAction } from "react";
import { cn } from "@/lib/utils";

export type TopologyMapNode = Readonly<{
  index: number;
  x: number;
  y: number;
}>;

export type TopologyHoverBubbleFrame = Readonly<{
  x: number;
  y: number;
  width: number;
  height: number;
}>;

export type TopologyHoverState = Readonly<{
  id: string;
  title: string;
  details: readonly string[];
  anchorX: number;
  anchorY: number;
}>;

type TopologyEdgeHoverLine = Readonly<{
  stroke: string;
  strokeWidth: number;
  opacity?: number;
}>;

export type TopologyEdgeRenderSpec = Readonly<{
  interactive?: boolean;
  title?: string;
  details?: readonly string[];
  stroke: string;
  strokeWidth: number;
  opacity?: number;
  hoverLines?: readonly TopologyEdgeHoverLine[];
  hitWidth?: number;
  testId?: string;
}>;

type TopologyNodeCircleSpec = Readonly<{
  radius: number;
  fill: string;
  stroke: string;
  strokeWidth: number;
  opacity?: number;
}>;

type TopologyNodeLabelSpec = Readonly<{
  text: string;
  fill: string;
  dy?: number;
  fontSize?: number;
  fontWeight?: number;
  opacity?: number;
}>;

export type TopologyNodeRenderSpec = Readonly<{
  interactive?: boolean;
  title?: string;
  details?: readonly string[];
  circle: TopologyNodeCircleSpec;
  label: TopologyNodeLabelSpec;
  secondaryLabel?: TopologyNodeLabelSpec;
  hoverRing?: Readonly<{
    radius: number;
    stroke: string;
    strokeWidth: number;
    opacity?: number;
  }>;
  hoverCircle?: TopologyNodeCircleSpec;
  hoverLabelFill?: string;
  testId?: string;
}>;

type TopologyMapSvgProps = Readonly<{
  width: number;
  height: number;
  offsetX: number;
  offsetY: number;
  viewBoxX?: number;
  viewBoxY?: number;
  viewBoxWidth?: number;
  viewBoxHeight?: number;
  nodes: readonly TopologyMapNode[];
  couplings: ReadonlyArray<readonly [number, number]>;
  nodeByIndex: ReadonlyMap<number, TopologyMapNode>;
  ariaLabel: string;
  className?: string;
  svgClassName?: string;
  getEdgeSpec: (
    source: number,
    target: number,
    state: Readonly<{ hovered: boolean }>,
  ) => TopologyEdgeRenderSpec;
  getNodeSpec: (
    node: TopologyMapNode,
    state: Readonly<{ hovered: boolean; edgeEndpoint: boolean }>,
  ) => TopologyNodeRenderSpec;
}>;

const TOPOLOGY_HOVER_POINTER_SIZE = 10;
type TopologyHoverSetter = Dispatch<SetStateAction<TopologyHoverState | null>>;

export function TopologyMapSvg({
  width,
  height,
  offsetX,
  offsetY,
  viewBoxX = 0,
  viewBoxY = 0,
  viewBoxWidth,
  viewBoxHeight,
  nodes,
  couplings,
  nodeByIndex,
  ariaLabel,
  className,
  svgClassName,
  getEdgeSpec,
  getNodeSpec,
}: TopologyMapSvgProps) {
  const [hoveredItem, setHoveredItem] = useState<TopologyHoverState | null>(null);
  const { hoveredNode, hoveredEdge } = resolveHoveredElements(hoveredItem, couplings, nodeByIndex);
  return (
    <div className={cn("relative rounded-md", className)}>
      <svg
        viewBox={`${viewBoxX} ${viewBoxY} ${viewBoxWidth ?? width} ${viewBoxHeight ?? height}`}
        className={cn("relative z-10 block h-full w-full", svgClassName)}
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label={ariaLabel}
      >
        <g transform={`translate(${offsetX} ${offsetY})`}>
          <TopologyEdgeLayer
            couplings={couplings}
            nodeByIndex={nodeByIndex}
            offsetX={offsetX}
            offsetY={offsetY}
            getEdgeSpec={getEdgeSpec}
            setHoveredItem={setHoveredItem}
          />
          <TopologyNodeLayer
            nodes={nodes}
            hoveredNodeIndex={hoveredNode?.index ?? null}
            offsetX={offsetX}
            offsetY={offsetY}
            getNodeSpec={getNodeSpec}
            setHoveredItem={setHoveredItem}
          />
        </g>

        <TopologyHoverOverlay
          hoveredItem={hoveredItem}
          hoveredEdge={hoveredEdge}
          hoveredNode={hoveredNode}
          nodeByIndex={nodeByIndex}
          offsetX={offsetX}
          offsetY={offsetY}
          getEdgeSpec={getEdgeSpec}
          getNodeSpec={getNodeSpec}
        />

        {renderTopologyHoverBubble(hoveredItem, width, height)}
      </svg>
    </div>
  );
}

function renderTopologyHoverBubble(
  hoveredItem: TopologyHoverState | null,
  width: number,
  height: number,
) {
  if (hoveredItem === null) return null;
  return <TopologyHoverBubble hover={hoveredItem} width={width} height={height} />;
}

function resolveHoveredElements(
  hoveredItem: TopologyHoverState | null,
  couplings: ReadonlyArray<readonly [number, number]>,
  nodeByIndex: ReadonlyMap<number, TopologyMapNode>,
) {
  const hoveredNodeId = getHoveredNodeId(hoveredItem);
  const hoveredEdge =
    hoveredItem?.id.startsWith("qubit:") === false
      ? (couplings.find(([source, target]) => edgeKey(source, target) === hoveredItem.id) ?? null)
      : null;
  return {
    hoveredNode: resolveHoveredNode(hoveredNodeId, nodeByIndex),
    hoveredEdge,
  };
}

function resolveHoveredNode(
  hoveredNodeId: number | null,
  nodeByIndex: ReadonlyMap<number, TopologyMapNode>,
): TopologyMapNode | null {
  if (hoveredNodeId === null) return null;
  return nodeByIndex.get(hoveredNodeId) ?? null;
}

function getHoveredNodeId(hoveredItem: TopologyHoverState | null): number | null {
  if (hoveredItem?.id.startsWith("qubit:") === true) {
    return Number(hoveredItem.id.slice("qubit:".length));
  }
  return null;
}

function TopologyEdgeLayer({
  couplings,
  nodeByIndex,
  offsetX,
  offsetY,
  getEdgeSpec,
  setHoveredItem,
}: Readonly<{
  couplings: ReadonlyArray<readonly [number, number]>;
  nodeByIndex: ReadonlyMap<number, TopologyMapNode>;
  offsetX: number;
  offsetY: number;
  getEdgeSpec: TopologyMapSvgProps["getEdgeSpec"];
  setHoveredItem: TopologyHoverSetter;
}>) {
  return couplings.map(([source, target]) => {
    const start = nodeByIndex.get(source);
    const end = nodeByIndex.get(target);
    if (start === undefined || end === undefined) return null;
    return (
      <TopologyEdge
        key={`${source}:${target}`}
        source={source}
        target={target}
        start={start}
        end={end}
        offsetX={offsetX}
        offsetY={offsetY}
        getEdgeSpec={getEdgeSpec}
        setHoveredItem={setHoveredItem}
      />
    );
  });
}

function TopologyEdge({
  source,
  target,
  start,
  end,
  offsetX,
  offsetY,
  getEdgeSpec,
  setHoveredItem,
}: Readonly<{
  source: number;
  target: number;
  start: TopologyMapNode;
  end: TopologyMapNode;
  offsetX: number;
  offsetY: number;
  getEdgeSpec: TopologyMapSvgProps["getEdgeSpec"];
  setHoveredItem: TopologyHoverSetter;
}>) {
  const spec = getEdgeSpec(source, target, { hovered: false });
  const edgeId = edgeKey(source, target);
  const interactive = spec.interactive === true;
  const handleMouseEnter = interactive
    ? () => setHoveredItem(buildEdgeHoverState(source, target, start, end, offsetX, offsetY, spec))
    : undefined;
  const handleMouseLeave = interactive
    ? () => clearHoveredItemById(setHoveredItem, edgeId)
    : undefined;
  return (
    <g
      data-testid={spec.testId}
      className={interactive ? "cursor-pointer" : undefined}
      opacity={1}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <line
        x1={start.x}
        y1={start.y}
        x2={end.x}
        y2={end.y}
        stroke={spec.stroke}
        strokeWidth={spec.strokeWidth}
        strokeLinecap="round"
        opacity={spec.opacity ?? 1}
        pointerEvents="none"
      />
      <line
        x1={start.x}
        y1={start.y}
        x2={end.x}
        y2={end.y}
        stroke="transparent"
        strokeWidth={spec.hitWidth ?? 18}
        strokeLinecap="round"
      />
    </g>
  );
}

function TopologyNodeLayer({
  nodes,
  hoveredNodeIndex,
  offsetX,
  offsetY,
  getNodeSpec,
  setHoveredItem,
}: Readonly<{
  nodes: readonly TopologyMapNode[];
  hoveredNodeIndex: number | null;
  offsetX: number;
  offsetY: number;
  getNodeSpec: TopologyMapSvgProps["getNodeSpec"];
  setHoveredItem: TopologyHoverSetter;
}>) {
  return nodes.map((node) => {
    return (
      <TopologyNode
        key={node.index}
        node={node}
        hovered={hoveredNodeIndex === node.index}
        offsetX={offsetX}
        offsetY={offsetY}
        getNodeSpec={getNodeSpec}
        setHoveredItem={setHoveredItem}
      />
    );
  });
}

function TopologyNode({
  node,
  hovered,
  offsetX,
  offsetY,
  getNodeSpec,
  setHoveredItem,
}: Readonly<{
  node: TopologyMapNode;
  hovered: boolean;
  offsetX: number;
  offsetY: number;
  getNodeSpec: TopologyMapSvgProps["getNodeSpec"];
  setHoveredItem: TopologyHoverSetter;
}>) {
  const spec = getNodeSpec(node, { hovered, edgeEndpoint: false });
  const nodeId = `qubit:${node.index}`;
  const interactive = spec.interactive === true;
  const handleMouseEnter = interactive
    ? () => setHoveredItem(buildNodeHoverState(node, offsetX, offsetY, spec))
    : undefined;
  const handleMouseLeave = interactive
    ? () => clearHoveredItemById(setHoveredItem, nodeId)
    : undefined;
  return (
    <g
      data-testid={spec.testId}
      className={interactive ? "cursor-pointer" : undefined}
      opacity={1}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <TopologyNodeGlyph node={node} spec={spec} />
    </g>
  );
}

function TopologyHoverOverlay({
  hoveredItem,
  hoveredEdge,
  hoveredNode,
  nodeByIndex,
  offsetX,
  offsetY,
  getEdgeSpec,
  getNodeSpec,
}: Readonly<{
  hoveredItem: TopologyHoverState | null;
  hoveredEdge: readonly [number, number] | null;
  hoveredNode: TopologyMapNode | null;
  nodeByIndex: ReadonlyMap<number, TopologyMapNode>;
  offsetX: number;
  offsetY: number;
  getEdgeSpec: TopologyMapSvgProps["getEdgeSpec"];
  getNodeSpec: TopologyMapSvgProps["getNodeSpec"];
}>) {
  if (hoveredItem === null) {
    return null;
  }

  return (
    <g transform={`translate(${offsetX} ${offsetY})`} pointerEvents="none">
      {renderTopologyHoveredEdge(hoveredEdge, nodeByIndex, getEdgeSpec)}
      {renderTopologyHoveredNode(hoveredNode, getNodeSpec)}
    </g>
  );
}

function renderTopologyHoveredEdge(
  hoveredEdge: readonly [number, number] | null,
  nodeByIndex: ReadonlyMap<number, TopologyMapNode>,
  getEdgeSpec: TopologyMapSvgProps["getEdgeSpec"],
) {
  if (hoveredEdge === null) return null;
  return (
    <TopologyHoveredEdge
      hoveredEdge={hoveredEdge}
      nodeByIndex={nodeByIndex}
      getEdgeSpec={getEdgeSpec}
    />
  );
}

function renderTopologyHoveredNode(
  hoveredNode: TopologyMapNode | null,
  getNodeSpec: TopologyMapSvgProps["getNodeSpec"],
) {
  if (hoveredNode === null) return null;
  return (
    <TopologyNodeGlyph
      node={hoveredNode}
      spec={getNodeSpec(hoveredNode, { hovered: true, edgeEndpoint: false })}
      useHoverAppearance
    />
  );
}

function TopologyHoveredEdge({
  hoveredEdge,
  nodeByIndex,
  getEdgeSpec,
}: Readonly<{
  hoveredEdge: readonly [number, number];
  nodeByIndex: ReadonlyMap<number, TopologyMapNode>;
  getEdgeSpec: TopologyMapSvgProps["getEdgeSpec"];
}>) {
  const [source, target] = hoveredEdge;
  const hoverSpec = getEdgeSpec(source, target, { hovered: true });
  return (
    <>
      {hoverSpec.hoverLines?.map((line) => (
        <line
          key={`${source}:${target}:${line.stroke}:${line.strokeWidth}`}
          x1={nodeByIndex.get(source)?.x}
          y1={nodeByIndex.get(source)?.y}
          x2={nodeByIndex.get(target)?.x}
          y2={nodeByIndex.get(target)?.y}
          stroke={line.stroke}
          strokeWidth={line.strokeWidth}
          strokeLinecap="round"
          opacity={line.opacity ?? 1}
        />
      ))}
    </>
  );
}

function TopologyNodeGlyph({
  node,
  spec,
  useHoverAppearance = false,
}: Readonly<{
  node: TopologyMapNode;
  spec: TopologyNodeRenderSpec;
  useHoverAppearance?: boolean;
}>) {
  const circle = useHoverAppearance ? (spec.hoverCircle ?? spec.circle) : spec.circle;
  const primaryLabelFill = useHoverAppearance
    ? (spec.hoverLabelFill ?? spec.label.fill)
    : spec.label.fill;
  const labels = buildTopologyNodeLabels(spec, primaryLabelFill);
  return (
    <g>
      {useHoverAppearance && spec.hoverRing ? (
        <circle
          cx={node.x}
          cy={node.y}
          r={spec.hoverRing.radius}
          fill="none"
          stroke={spec.hoverRing.stroke}
          strokeWidth={spec.hoverRing.strokeWidth}
          opacity={spec.hoverRing.opacity ?? 1}
        />
      ) : null}
      <circle
        cx={node.x}
        cy={node.y}
        r={circle.radius}
        fill={circle.fill}
        stroke={circle.stroke}
        strokeWidth={circle.strokeWidth}
        opacity={circle.opacity ?? 1}
      />
      {labels.map(({ id, label, fill, defaultDy }) => (
        <TopologyNodeLabel
          key={`${node.index}:${id}`}
          node={node}
          label={label}
          fill={fill}
          defaultDy={defaultDy}
        />
      ))}
    </g>
  );
}

function buildTopologyNodeLabels(spec: TopologyNodeRenderSpec, primaryLabelFill: string) {
  const labels = [{ id: "primary", label: spec.label, fill: primaryLabelFill, defaultDy: 4 }];
  if (spec.secondaryLabel !== null && spec.secondaryLabel !== undefined) {
    labels.push({
      id: "secondary",
      label: spec.secondaryLabel,
      fill: spec.secondaryLabel.fill,
      defaultDy: -24,
    });
  }
  return labels;
}

function TopologyNodeLabel({
  node,
  label,
  fill,
  defaultDy,
}: Readonly<{
  node: TopologyMapNode;
  label: TopologyNodeLabelSpec;
  fill: string;
  defaultDy: number;
}>) {
  return (
    <text
      x={node.x}
      y={node.y + (label.dy ?? defaultDy)}
      textAnchor="middle"
      fill={fill}
      opacity={label.opacity ?? 1}
      fontSize={label.fontSize ?? 9}
      fontWeight={label.fontWeight ?? 600}
      className="pointer-events-none"
    >
      {label.text}
    </text>
  );
}

function buildEdgeHoverState(
  source: number,
  target: number,
  start: TopologyMapNode,
  end: TopologyMapNode,
  offsetX: number,
  offsetY: number,
  spec: TopologyEdgeRenderSpec,
): TopologyHoverState {
  return {
    id: edgeKey(source, target),
    title: spec.title ?? `${source} ↔ ${target}`,
    details: spec.details ?? [],
    anchorX: (start.x + end.x) / 2 + offsetX,
    anchorY: (start.y + end.y) / 2 + offsetY,
  };
}

function buildNodeHoverState(
  node: TopologyMapNode,
  offsetX: number,
  offsetY: number,
  spec: TopologyNodeRenderSpec,
): TopologyHoverState {
  return {
    id: `qubit:${node.index}`,
    title: spec.title ?? `Qubit ${node.index}`,
    details: spec.details ?? [],
    anchorX: node.x + offsetX,
    anchorY: node.y + offsetY,
  };
}

function clearHoveredItemById(setHoveredItem: TopologyHoverSetter, id: string) {
  setHoveredItem((current) => (current?.id === id ? null : current));
}

function TopologyHoverBubble({
  hover,
  width,
  height,
}: Readonly<{
  hover: TopologyHoverState;
  width: number;
  height: number;
}>) {
  const lines = hover.details.slice(0, 3);
  const bubbleWidth = Math.min(
    280,
    Math.max(160, longestHoverLineLength([hover.title, ...lines]) * 7.4 + 32),
  );
  const bubbleHeight = 24 + (lines.length + 1) * 18 + TOPOLOGY_HOVER_POINTER_SIZE + 14;
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
  const bodyY = bubbleAboveAnchor ? 0 : TOPOLOGY_HOVER_POINTER_SIZE;
  const bodyHeight = frame.height - TOPOLOGY_HOVER_POINTER_SIZE;
  const pointerPoints = bubbleAboveAnchor
    ? `${pointerOffset - TOPOLOGY_HOVER_POINTER_SIZE},${bodyHeight} ${pointerOffset + TOPOLOGY_HOVER_POINTER_SIZE},${bodyHeight} ${pointerOffset},${frame.height}`
    : `${pointerOffset - TOPOLOGY_HOVER_POINTER_SIZE},${TOPOLOGY_HOVER_POINTER_SIZE} ${pointerOffset + TOPOLOGY_HOVER_POINTER_SIZE},${TOPOLOGY_HOVER_POINTER_SIZE} ${pointerOffset},0`;

  return (
    <g
      pointerEvents="none"
      transform={`translate(${frame.x} ${frame.y})`}
      style={{ filter: "drop-shadow(0 4px 10px rgb(15 23 42 / 0.14))" }}
    >
      <rect
        x={0}
        y={bodyY}
        width={frame.width}
        height={bodyHeight}
        rx={12}
        fill="#ffffff"
        stroke="#dbe2ea"
      />
      <polygon points={pointerPoints} fill="#ffffff" stroke="#dbe2ea" strokeLinejoin="round" />
      <text x={16} y={bodyY + 24} fill="#0f172a" fontSize={14} fontWeight={600}>
        {hover.title}
      </text>
      {lines.map((detail, index) => (
        <text
          key={`${hover.id}:${detail}`}
          x={16}
          y={bodyY + 46 + index * 18}
          fill="#475569"
          fontSize={12}
        >
          {detail}
        </text>
      ))}
    </g>
  );
}

function longestHoverLineLength(lines: string[]): number {
  return lines.reduce((longest, line) => Math.max(longest, line.length), 0);
}

export function positionTopologyHoverBubble({
  anchorX,
  anchorY,
  bubbleWidth,
  bubbleHeight,
  width,
  height,
}: Readonly<{
  anchorX: number;
  anchorY: number;
  bubbleWidth: number;
  bubbleHeight: number;
  width: number;
  height: number;
}>): TopologyHoverBubbleFrame {
  const margin = 8;
  const preferredX = anchorX - bubbleWidth / 2;
  const preferredY = anchorY - bubbleHeight - 18;
  const maxX = Math.max(margin, width - bubbleWidth - margin);
  const x = Math.min(maxX, Math.max(margin, preferredX));

  if (preferredY >= margin) {
    return { x, y: preferredY, width: bubbleWidth, height: bubbleHeight };
  }

  const belowY = anchorY + 18;
  const maxY = Math.max(margin, height - bubbleHeight - margin);
  return {
    x,
    y: Math.min(maxY, Math.max(margin, belowY)),
    width: bubbleWidth,
    height: bubbleHeight,
  };
}

export function edgeKey(source: number, target: number): string {
  return source < target ? `${source}:${target}` : `${target}:${source}`;
}
