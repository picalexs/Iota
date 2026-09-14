import type { BackendDeviceSummary, BackendTarget } from "@/types/run";
import {
  DEFAULT_TOPOLOGY_COLOR,
  IBM_PROCESSOR_OVERRIDES,
  type TopologyMetric,
} from "./backend-section-shared";

export type TopologyNode = {
  index: number;
  x: number;
  y: number;
};

type TopologyGridDimensions = {
  columns: number;
  rows: number;
};

type Coupling = [number, number];

type KnownTopologyPattern = {
  rowCount: number;
  maxColumn: number;
  oddRowStart: (row: number) => number;
};

type ProcessorDescriptor = {
  family: string | null;
  revision: string | null;
  layout: string;
  ibmUrl: string | null;
};

type NormalizedProcessorBase = {
  family: string | null;
  revision: string | null;
  ibmUrl: string | null;
  override: (typeof IBM_PROCESSOR_OVERRIDES)[string] | undefined;
};

export type TopologyTableRow = {
  qubit: number;
  readout_error: number | null;
  t1_us: number | null;
  t2_us: number | null;
  operational: boolean | null;
  degree: number;
  bestGateError: number | null;
  worstGateError: number | null;
};

export type TopologyBounds = {
  minX: number;
  maxX: number;
  minY: number;
  maxY: number;
  width: number;
  height: number;
};

export function inferTotalQubits(
  device: BackendDeviceSummary | null,
  target: BackendTarget,
): number | null {
  if (device?.num_qubits != null) return device.num_qubits;
  const maxFromQubits = Math.max(-1, ...(device?.qubit_errors ?? []).map((item) => item.qubit));
  const maxFromCouplings = Math.max(-1, ...(device?.coupling_map ?? []).flat());
  const maxFromGates = Math.max(
    -1,
    ...(device?.gate_errors ?? []).flatMap((item) => [item.source, item.target]),
  );
  const inferred = Math.max(maxFromQubits, maxFromCouplings, maxFromGates);
  if (inferred >= 0) return inferred + 1;
  return target === "aer_simulator" ? 8 : null;
}

export function buildMapNodes(
  count: number,
  couplings: number[][],
  useKnownTopology = true,
): TopologyNode[] {
  const knownCoordinates = useKnownTopology ? buildKnownTopologyCoordinates(count) : null;
  if (knownCoordinates != null) {
    return buildNodesFromCoordinates(
      knownCoordinates,
      count >= 150 ? 44 : 46,
      count >= 150 ? 38 : 40,
    );
  }

  const rectangularGrid = detectRectangularGridDimensions(count, couplings);
  if (rectangularGrid != null) {
    return buildRectangularGridNodes(count, rectangularGrid.columns);
  }

  return buildFallbackMapNodes(count);
}

export function topologyBounds(nodes: TopologyNode[]): TopologyBounds {
  const xs = nodes.map((node) => node.x);
  const ys = nodes.map((node) => node.y);
  const minX = Math.min(...xs) - 18;
  const maxX = Math.max(...xs) + 18;
  const minY = Math.min(...ys) - 18;
  const maxY = Math.max(...ys) + 18;
  return {
    minX,
    maxX,
    minY,
    maxY,
    width: maxX - minX,
    height: maxY - minY,
  };
}

export function inferProcessorDescriptor(
  device: BackendDeviceSummary | null,
  count: number,
  couplings: number[][],
): ProcessorDescriptor | null {
  if (device == null || device.simulator === true) return null;

  const normalizedName = normalizeDeviceName(device.name);
  const { family, revision, ibmUrl, override } = normalizeProcessorBase(device, normalizedName);

  if (override != null) {
    return {
      family,
      revision,
      layout: override.layout,
      ibmUrl,
    };
  }

  const rectangularGrid = detectRectangularGridDimensions(count, couplings);
  if (rectangularGrid != null) {
    return {
      family: family ?? (count === 120 ? "Nighthawk" : null),
      revision,
      layout: `${rectangularGrid.columns} × ${rectangularGrid.rows} square lattice`,
      ibmUrl,
    };
  }

  if (buildKnownTopologyCoordinates(count) != null) {
    return {
      family: family ?? (count >= 133 ? "Heron" : null),
      revision,
      layout: "Heavy-hex lattice",
      ibmUrl,
    };
  }

  return {
    family,
    revision,
    layout: "Backend topology map",
    ibmUrl,
  };
}

export function detectRectangularGridDimensions(
  count: number,
  couplings: number[][],
): TopologyGridDimensions | null {
  if (count < 4 || couplings.length === 0) return null;

  const undirected = uniqueCouplings(couplings).filter(
    ([source, target]) => source < count && target < count,
  );
  const expectedEdges = undirected.length;
  const degreeByQubit = Array.from({ length: count }, () => 0);

  for (const [source, target] of undirected) {
    degreeByQubit[source] = (degreeByQubit[source] ?? 0) + 1;
    degreeByQubit[target] = (degreeByQubit[target] ?? 0) + 1;
  }

  const edgeKeys = new Set(undirected.map(([source, target]) => edgeKey(source, target)));
  const candidates: TopologyGridDimensions[] = [];

  for (let divisor = 2; divisor <= Math.floor(Math.sqrt(count)); divisor += 1) {
    if (count % divisor !== 0) continue;
    const paired = count / divisor;
    candidates.push({ columns: divisor, rows: paired });
    if (paired !== divisor) {
      candidates.push({ columns: paired, rows: divisor });
    }
  }

  const viable = candidates
    .filter(({ columns, rows }) => {
      const gridEdges = columns * (rows - 1) + rows * (columns - 1);
      return (
        gridEdges === expectedEdges && matchesRectangularGridDegrees(columns, rows, degreeByQubit)
      );
    })
    .sort(
      (left, right) =>
        rectangularGridOrientationScore(count, right.columns, edgeKeys) -
        rectangularGridOrientationScore(count, left.columns, edgeKeys),
    );

  return viable[0] ?? null;
}

export function buildCouplings(device: BackendDeviceSummary | null, count: number): number[][] {
  const reported = validCouplings(device?.coupling_map ?? [], count);
  if (reported.length > 0) return uniqueCouplings(reported);

  // Runtime catalog responses omit coupling_map, but calibration properties
  // retain the endpoints for each calibrated two-qubit gate.
  const calibrated = validCouplings(
    (device?.gate_errors ?? []).map(({ source, target }) => [source, target]),
    count,
  );
  if (calibrated.length > 0) return uniqueCouplings(calibrated);

  return fallbackHeavyGridCouplings(count);
}

export function edgeKey(source: number, target: number): string {
  return source < target ? `${source}:${target}` : `${target}:${source}`;
}

export function hasDetailedTopologyMetrics(device: BackendDeviceSummary | null): boolean {
  return (device?.qubit_errors?.length ?? 0) > 0 || (device?.gate_errors?.length ?? 0) > 0;
}

export function metricValue(
  row: NonNullable<BackendDeviceSummary["qubit_errors"]>[number] | TopologyTableRow | undefined,
  metric: TopologyMetric,
): number | null {
  if (row == null) return null;
  return row[metric] ?? null;
}

export function metricColor(
  value: number | null,
  range: { min: number; max: number },
  invert = false,
) {
  const percent = metricPercent(value, range, invert);
  if (percent <= 0.35) return DEFAULT_TOPOLOGY_COLOR;
  if (percent <= 0.7) return "#9aaedb";
  return "#dbe3f5";
}

export function metricPercent(
  value: number | null,
  range: { min: number; max: number },
  invert = false,
): number {
  if (value == null || range.max <= range.min) return 0.05;
  const raw = (value - range.min) / (range.max - range.min);
  return Math.max(0.04, Math.min(1, invert ? 1 - raw : raw));
}

export function shouldShowGraphLabel(index: number, total: number, interval: number): boolean {
  return index % interval === 0 || index === total - 1;
}

function matchesRectangularGridDegrees(
  columns: number,
  rows: number,
  degreeByQubit: number[],
): boolean {
  const expectedDegreeCounts = new Map<number, number>([
    [2, 4],
    [3, Math.max(0, 2 * (columns - 2) + 2 * (rows - 2))],
    [4, Math.max(0, (columns - 2) * (rows - 2))],
  ]);
  const actualDegreeCounts = new Map<number, number>();

  for (const degree of degreeByQubit) {
    actualDegreeCounts.set(degree, (actualDegreeCounts.get(degree) ?? 0) + 1);
  }

  const nonZeroExpected = Array.from(expectedDegreeCounts.values()).filter(
    (value) => value > 0,
  ).length;
  if (actualDegreeCounts.size !== nonZeroExpected) return false;

  return Array.from(expectedDegreeCounts.entries()).every(
    ([degree, expectedCount]) =>
      expectedCount === 0 || (actualDegreeCounts.get(degree) ?? 0) === expectedCount,
  );
}

function rectangularGridOrientationScore(
  count: number,
  columns: number,
  edgeKeys: Set<string>,
): number {
  let score = 0;

  for (let index = 0; index < count; index += 1) {
    if ((index + 1) % columns !== 0 && edgeKeys.has(edgeKey(index, index + 1))) {
      score += 3;
    }
    if (index + columns < count && edgeKeys.has(edgeKey(index, index + columns))) {
      score += 2;
    }
  }

  return score;
}

function buildKnownTopologyCoordinates(
  count: number,
): ReadonlyArray<readonly [number, number]> | null {
  const pattern = knownTopologyPattern(count);
  return pattern == null ? null : buildHeavyHexCoordinates(pattern);
}

function buildNodesFromCoordinates(
  coordinates: ReadonlyArray<readonly [number, number]>,
  cellX: number,
  cellY: number,
): TopologyNode[] {
  return coordinates.map(([row, column], index) => ({
    index,
    x: 42 + column * cellX,
    y: 40 + row * cellY,
  }));
}

function buildRectangularGridNodes(count: number, columns: number): TopologyNode[] {
  const cell = count > 90 ? 62 : 68;
  return Array.from({ length: count }, (_, index) => {
    const row = Math.floor(index / columns);
    const column = index % columns;
    return {
      index,
      x: 42 + column * cell,
      y: 40 + row * cell,
    };
  });
}

function buildFallbackMapNodes(count: number): TopologyNode[] {
  const columns = topologyColumns(count);
  const cellX = count > 90 ? 52 : 58;
  const cellY = count > 90 ? 48 : 54;
  return Array.from({ length: count }, (_, index) => {
    const row = Math.floor(index / columns);
    const column = index % columns;
    const offset = row % 2 === 0 ? 0 : cellX * 0.5;
    return {
      index,
      x: 42 + column * cellX + offset,
      y: 40 + row * cellY,
    };
  });
}

function topologyColumns(count: number): number {
  if (count >= 150) return 18;
  if (count >= 120) return 16;
  if (count >= 60) return 12;
  if (count >= 24) return 8;
  return Math.max(3, Math.ceil(Math.sqrt(count)));
}

function fallbackHeavyGridCouplings(count: number): number[][] {
  const columns = topologyColumns(count);
  const edges: number[][] = [];
  for (let index = 0; index < count; index += 1) {
    const column = index % columns;
    if (column < columns - 1 && index + 1 < count) {
      edges.push([index, index + 1]);
    }
    if (column % 4 === 1 && index + columns < count) {
      edges.push([index, index + columns]);
    }
    if (column % 4 === 3 && index + columns < count) {
      edges.push([index, index + columns]);
    }
  }
  return edges;
}

export function uniqueCouplings(edges: number[][]): Coupling[] {
  const seen = new Set<string>();
  const unique: Coupling[] = [];
  for (const coupling of edges) {
    const [source, target] = coupling;
    if (source === undefined || target === undefined) continue;
    const key = edgeKey(source, target);
    if (seen.has(key)) continue;
    seen.add(key);
    unique.push([source, target]);
  }
  return unique;
}

function validCouplings(edges: number[][], count: number): Coupling[] {
  return edges.flatMap((coupling): Coupling[] => {
    const [source, target] = coupling;
    if (
      source === undefined ||
      target === undefined ||
      !Number.isInteger(source) ||
      !Number.isInteger(target) ||
      source < 0 ||
      target < 0 ||
      source >= count ||
      target >= count ||
      source === target
    ) {
      return [];
    }
    return [[source, target]];
  });
}

export function buildTableRows(
  count: number,
  couplings: number[][],
  qubits: Map<number, NonNullable<BackendDeviceSummary["qubit_errors"]>[number]>,
  gates: Map<string, NonNullable<BackendDeviceSummary["gate_errors"]>[number]>,
): TopologyTableRow[] {
  const neighbors = buildNeighborMap(couplings);
  return Array.from({ length: count }, (_, qubit) =>
    buildTableRow(qubit, neighbors, qubits, gates),
  );
}

function buildNeighborMap(couplings: number[][]): Map<number, number[]> {
  const neighbors = new Map<number, number[]>();
  for (const coupling of couplings) {
    const [source, target] = coupling;
    if (source === undefined || target === undefined) continue;
    neighbors.set(source, [...(neighbors.get(source) ?? []), target]);
    neighbors.set(target, [...(neighbors.get(target) ?? []), source]);
  }
  return neighbors;
}

function buildTableRow(
  qubit: number,
  neighbors: Map<number, number[]>,
  qubits: Map<number, NonNullable<BackendDeviceSummary["qubit_errors"]>[number]>,
  gates: Map<string, NonNullable<BackendDeviceSummary["gate_errors"]>[number]>,
): TopologyTableRow {
  const neighborQubits = neighbors.get(qubit) ?? [];
  const gateErrors = neighborQubits
    .map((other) => gates.get(edgeKey(qubit, other))?.error ?? null)
    .filter(isNumber);
  const meta = qubits.get(qubit);
  return {
    qubit,
    readout_error: meta?.readout_error ?? null,
    t1_us: meta?.t1_us ?? null,
    t2_us: meta?.t2_us ?? null,
    operational: meta?.operational ?? null,
    degree: neighborQubits.length,
    bestGateError: gateErrors.length > 0 ? Math.min(...gateErrors) : null,
    worstGateError: gateErrors.length > 0 ? Math.max(...gateErrors) : null,
  };
}

function isNumber(value: number | null | undefined): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function buildIbmBackendUrl(name: string): string | null {
  if (!name.startsWith("ibm_")) return null;
  return `https://quantum.cloud.ibm.com/computers?tab=systems&system=${encodeURIComponent(name)}`;
}

function normalizeDeviceName(name: string): string {
  return name.trim().toLowerCase();
}

function normalizeProcessorBase(
  device: BackendDeviceSummary,
  normalizedName: string,
): NormalizedProcessorBase {
  const override = IBM_PROCESSOR_OVERRIDES[normalizedName];
  return {
    family: device.processor_type?.family ?? override?.family ?? null,
    revision: device.processor_type?.revision ?? override?.revision ?? null,
    ibmUrl: buildIbmBackendUrl(normalizedName),
    override,
  };
}

function knownTopologyPattern(count: number): KnownTopologyPattern | null {
  if (count === 133) {
    return {
      rowCount: 14,
      maxColumn: 14,
      oddRowStart: (row) => (row % 4 === 1 ? 0 : 2),
    };
  }

  if (count === 156) {
    return {
      rowCount: 15,
      maxColumn: 15,
      oddRowStart: (row) => (row % 4 === 1 ? 3 : 1),
    };
  }

  return null;
}

function buildHeavyHexCoordinates(pattern: KnownTopologyPattern): Array<readonly [number, number]> {
  const coordinates: Array<readonly [number, number]> = [];
  for (let row = 0; row < pattern.rowCount; row += 1) {
    appendHeavyHexRowCoordinates(coordinates, row, pattern);
  }
  return coordinates;
}

function appendHeavyHexRowCoordinates(
  coordinates: Array<readonly [number, number]>,
  row: number,
  pattern: KnownTopologyPattern,
): void {
  if (row % 2 === 0) {
    appendCoordinateRange(coordinates, row, 0, pattern.maxColumn, 1);
    return;
  }

  appendCoordinateRange(coordinates, row, pattern.oddRowStart(row), pattern.maxColumn, 4);
}

function appendCoordinateRange(
  coordinates: Array<readonly [number, number]>,
  row: number,
  start: number,
  end: number,
  step: number,
): void {
  for (let column = start; column <= end; column += step) {
    coordinates.push([row, column]);
  }
}
