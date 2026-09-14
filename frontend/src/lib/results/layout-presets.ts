import type { LayoutItem } from "react-grid-layout";

export type DashboardLayoutVariant = "default" | "ibm-runtime";

export type TileKey =
  | "summary"
  | "convergence"
  | "hardware-mapping"
  | "benchmark-bars"
  | "timeline"
  | "spectral-gaps"
  | "vqe-circuit"
  | "qse-circuit"
  | "kqd-circuit"
  | "skqd-circuit"
  | "sqd-occupancy"
  | "sqd-recovery"
  | "kqd-ritz"
  | "qfd-spectrum"
  | "qse-subspace"
  | "skqd-spectrum"
  | "skqd-diagnostics";

export type AlgorithmType = "vqe" | "sqd" | "kqd" | "qfd" | "qse" | "skqd" | "unknown";

const GRID_COLUMNS = 12;
const MAX_LAYOUT_SCAN_ROWS = 160;

const UNIVERSAL_TILES = [
  "summary",
  "convergence",
  "hardware-mapping",
  "timeline",
  "benchmark-bars",
] satisfies readonly TileKey[];

const ALGORITHM_TILES = {
  vqe: ["vqe-circuit"],
  sqd: ["sqd-occupancy", "sqd-recovery"],
  kqd: ["kqd-ritz", "kqd-circuit", "spectral-gaps"],
  qfd: ["qfd-spectrum", "spectral-gaps"],
  qse: ["qse-subspace", "qse-circuit", "spectral-gaps"],
  skqd: ["skqd-diagnostics", "skqd-circuit", "skqd-spectrum", "spectral-gaps"],
  unknown: [],
} satisfies Record<AlgorithmType, readonly TileKey[]>;

const TILE_LAYOUT: Record<TileKey, { w: number; h: number }> = {
  summary: { w: 6, h: 5 },
  convergence: { w: 6, h: 5 },
  "hardware-mapping": { w: 8, h: 8 },
  "benchmark-bars": { w: 6, h: 6 },
  timeline: { w: 6, h: 6 },
  "spectral-gaps": { w: 6, h: 5 },
  "vqe-circuit": { w: 12, h: 7 },
  "qse-circuit": { w: 12, h: 7 },
  "kqd-circuit": { w: 12, h: 7 },
  "skqd-circuit": { w: 12, h: 7 },
  "sqd-occupancy": { w: 6, h: 4 },
  "sqd-recovery": { w: 12, h: 8 },
  "kqd-ritz": { w: 12, h: 8 },
  "qfd-spectrum": { w: 6, h: 5 },
  "qse-subspace": { w: 12, h: 8 },
  "skqd-spectrum": { w: 6, h: 5 },
  "skqd-diagnostics": { w: 12, h: 8 },
};

function overlaps(left: LayoutItem, right: LayoutItem): boolean {
  return !(
    left.x + left.w <= right.x ||
    right.x + right.w <= left.x ||
    left.y + left.h <= right.y ||
    right.y + right.h <= left.y
  );
}

function canPlace(layout: LayoutItem[], candidate: LayoutItem): boolean {
  if (candidate.x < 0 || candidate.y < 0) {
    return false;
  }
  if (candidate.x + candidate.w > GRID_COLUMNS) {
    return false;
  }

  return layout.every((item) => !overlaps(item, candidate));
}

function xCandidates(width: number): number[] {
  if (width >= GRID_COLUMNS) {
    return [0];
  }

  if (width === 6) {
    return [0, 6];
  }

  return Array.from({ length: GRID_COLUMNS - width + 1 }, (_, index) => index);
}

function placeFirstFit(
  layout: LayoutItem[],
  id: TileKey,
  options?: Readonly<{
    readonly xCandidates?: number[];
  }>,
): void {
  const { w, h } = TILE_LAYOUT[id];
  const candidates = options?.xCandidates ?? xCandidates(w);

  for (let y = 0; y <= MAX_LAYOUT_SCAN_ROWS; y += 1) {
    for (const x of candidates) {
      const nextItem: LayoutItem = { i: id, x, y, w, h };
      if (!canPlace(layout, nextItem)) {
        continue;
      }
      layout.push(nextItem);
      return;
    }
  }

  throw new Error(`Unable to place dashboard tile '${id}'.`);
}

function sortAlgorithmTiles(algorithm: AlgorithmType): TileKey[] {
  const orderedTiles = [...ALGORITHM_TILES[algorithm]] as TileKey[];
  return orderedTiles.sort((left, right) => {
    const leftLayout = TILE_LAYOUT[left];
    const rightLayout = TILE_LAYOUT[right];
    if (rightLayout.w !== leftLayout.w) {
      return rightLayout.w - leftLayout.w;
    }
    if (rightLayout.h !== leftLayout.h) {
      return rightLayout.h - leftLayout.h;
    }
    return orderedTiles.indexOf(left) - orderedTiles.indexOf(right);
  });
}

function stretchTrailingTile(layout: LayoutItem[]): LayoutItem[] {
  if (layout.length === 0) {
    return layout;
  }

  const trailingY = Math.max(...layout.map((item) => item.y));
  const trailingItems = layout.filter((item) => item.y === trailingY);
  if (trailingItems.length !== 1) {
    return layout;
  }

  const [trailingTile] = trailingItems;
  if (
    !trailingTile ||
    typeof trailingTile.i !== "string" ||
    trailingTile.x == null ||
    trailingTile.y == null ||
    trailingTile.w == null ||
    trailingTile.h == null ||
    trailingTile.w >= GRID_COLUMNS
  ) {
    return layout;
  }

  const expandedTile: LayoutItem = {
    ...trailingTile,
    i: trailingTile.i,
    x: 0,
    y: trailingTile.y,
    w: GRID_COLUMNS,
    h: trailingTile.h,
  };
  const overlapsExisting = layout.some(
    (item) => item.i !== trailingTile.i && overlaps(item, expandedTile),
  );
  if (overlapsExisting) {
    return layout;
  }

  return layout.map((item) => (item.i === trailingTile.i ? expandedTile : item));
}

export function tilesForAlgorithm(algorithm: AlgorithmType): TileKey[] {
  return [...UNIVERSAL_TILES, ...(ALGORITHM_TILES[algorithm] ?? [])];
}

export function getPresetLayout(
  algorithm: AlgorithmType,
  variant: DashboardLayoutVariant = "default",
): LayoutItem[] {
  if (variant === "ibm-runtime") {
    return getIbmPresetLayout(algorithm);
  }

  const layout: LayoutItem[] = [
    { i: "summary", x: 0, y: 0, ...TILE_LAYOUT.summary },
    { i: "convergence", x: 6, y: 0, ...TILE_LAYOUT.convergence },
    { i: "timeline", x: 0, y: 5, ...TILE_LAYOUT.timeline },
    { i: "benchmark-bars", x: 6, y: 5, ...TILE_LAYOUT["benchmark-bars"] },
  ];

  for (const id of sortAlgorithmTiles(algorithm)) {
    placeFirstFit(layout, id);
  }

  return stretchTrailingTile(layout);
}

function getIbmPresetLayout(algorithm: AlgorithmType): LayoutItem[] {
  const layout: LayoutItem[] = [
    { i: "summary", x: 0, y: 0, w: 6, h: 7 },
    { i: "convergence", x: 6, y: 0, w: 6, h: 7 },
    { i: "timeline", x: 0, y: 7, w: 4, h: 7 },
    { i: "hardware-mapping", x: 4, y: 7, w: 8, h: 7 },
    { i: "benchmark-bars", x: 0, y: 14, w: 6, h: 6 },
  ];

  for (const id of sortAlgorithmTiles(algorithm)) {
    placeFirstFit(layout, id);
  }

  return stretchTrailingTile(layout);
}
