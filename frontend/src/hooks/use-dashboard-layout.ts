import { useState, useCallback, useMemo } from "react";
import type { LayoutItem } from "react-grid-layout";
import {
  getPresetLayout,
  type AlgorithmType,
  type DashboardLayoutVariant,
} from "@/lib/results/layout-presets";
import { useLocalStorage } from "./use-local-storage";

const STORAGE_KEY_PREFIX = "vqe-studio:results-layout:v14";
const GRID_COLUMNS = 12;
const MAX_STORED_TILE_HEIGHT = 24;
const MAX_STORED_LAYOUT_Y = 200;
const MIN_STORED_TILE_SIZE_BY_ID = new Map<
  string,
  Readonly<{
    readonly w?: number;
    readonly h?: number;
  }>
>([
  ["benchmark-bars", { h: 6 }],
  ["vqe-circuit", { w: 12, h: 7 }],
  ["sqd-recovery", { w: 12, h: 8 }],
  ["kqd-ritz", { w: 12, h: 8 }],
  ["qse-subspace", { w: 12, h: 8 }],
  ["skqd-diagnostics", { w: 12, h: 8 }],
]);

function storageKey(algorithm: AlgorithmType, variant: DashboardLayoutVariant): string {
  return `${STORAGE_KEY_PREFIX}:${algorithm}:${variant}`;
}

function cloneLayout(layout: LayoutItem[]): LayoutItem[] {
  return layout.map((item) => ({ ...item }));
}

function isFiniteGridNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function sanitizeStoredItem(item: Partial<LayoutItem>, preset: LayoutItem): LayoutItem {
  const { x, y, w, h } = item;
  const minSize = MIN_STORED_TILE_SIZE_BY_ID.get(preset.i);
  const invalid =
    !isFiniteGridNumber(x) ||
    !isFiniteGridNumber(y) ||
    !isFiniteGridNumber(w) ||
    !isFiniteGridNumber(h) ||
    x < 0 ||
    y < 0 ||
    w < 1 ||
    h < 1 ||
    w > GRID_COLUMNS ||
    h > MAX_STORED_TILE_HEIGHT ||
    x + w > GRID_COLUMNS ||
    y > MAX_STORED_LAYOUT_Y;

  if (invalid) return { ...preset };

  const nextWidth = Math.max(w, minSize?.w ?? 0);
  const nextHeight = Math.max(h, minSize?.h ?? 0);
  if (nextWidth > GRID_COLUMNS || x + nextWidth > GRID_COLUMNS) {
    return { ...preset };
  }

  return { ...preset, ...item, i: preset.i, x, y, w: nextWidth, h: nextHeight };
}

function mergeWithPreset(stored: unknown, preset: LayoutItem[]): LayoutItem[] {
  const storedItems = Array.isArray(stored) ? stored : [];
  const presetById = new Map(preset.map((item) => [item.i, item]));
  const seen = new Set<string>();
  // Keep stored items the user explicitly knows; append new preset tiles below.
  const kept = storedItems.flatMap((item) => {
    const presetItem = presetById.get(item.i);
    if (presetItem == null || seen.has(item.i)) return [];
    seen.add(item.i);
    return [sanitizeStoredItem(item, presetItem)];
  });
  if (kept.length === storedItems.length && seen.size === presetById.size) {
    return kept;
  }
  const missing = preset.filter((l) => !seen.has(l.i));
  if (missing.length === 0) return kept;
  // Place new tiles after the deepest existing y so they don't overlap.
  const maxY = kept.reduce((m, l) => Math.max(m, l.y + l.h), 0);
  let cursorLeft = maxY;
  let cursorRight = maxY;
  const appended = missing.map((l) => {
    const side = l.x >= 6 ? 1 : 0;
    const y = side === 0 ? cursorLeft : cursorRight;
    if (side === 0) cursorLeft += l.h;
    else cursorRight += l.h;
    return { ...l, y };
  });
  return [...kept, ...appended];
}

export interface UseDashboardLayout {
  layout: LayoutItem[];
  layoutRevision: number;
  setLayout: (layout: LayoutItem[]) => void;
  resetLayout: () => void;
  editMode: boolean;
  setEditMode: (v: boolean) => void;
}

export function useDashboardLayout(
  algorithm: AlgorithmType,
  variant: DashboardLayoutVariant = "default",
): UseDashboardLayout {
  const defaultLayout = useMemo(
    () => cloneLayout(getPresetLayout(algorithm, variant)),
    [algorithm, variant],
  );

  const [storedLayout, setLayoutStored] = useLocalStorage<LayoutItem[]>(
    storageKey(algorithm, variant),
    defaultLayout,
  );
  const [editMode, setEditMode] = useState(false);
  const [layoutRevision, setLayoutRevision] = useState(0);

  const layout = useMemo(
    () => cloneLayout(mergeWithPreset(storedLayout, defaultLayout)),
    [storedLayout, defaultLayout],
  );

  const setLayout = useCallback(
    (next: LayoutItem[]) => {
      setLayoutStored(cloneLayout(mergeWithPreset(next, defaultLayout)));
    },
    [defaultLayout, setLayoutStored],
  );

  const resetLayout = useCallback(() => {
    setLayoutStored(cloneLayout(getPresetLayout(algorithm, variant)));
    setLayoutRevision((value) => value + 1);
  }, [algorithm, setLayoutStored, variant]);

  return { layout, layoutRevision, setLayout, resetLayout, editMode, setEditMode };
}
