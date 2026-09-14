import { useCallback, useEffect, useRef } from "react";
import { useContainerWidth, verticalCompactor } from "react-grid-layout";
import type { Layout, LayoutItem } from "react-grid-layout";
import {
  calculateResponsiveColumns,
  calculateResponsiveLayout,
  getLayoutBreakpoint,
} from "@/lib/responsive-columns";
import { logAppWarning } from "@/lib/app-logger";
import type { GridLayoutItem, LayoutBreakpoint } from "@/context/viewer-preferences-context";
import type { MoleculeResponse } from "@/types/run";

const ELASTIC_MAX_OFFSET_PX = 26;
const ELASTIC_STIFFNESS_PX = 70;

type GridEventCallback = (
  layout: Layout,
  oldItem: LayoutItem | null,
  newItem: LayoutItem | null,
  placeholder: LayoutItem | null,
  event: Event,
  element?: HTMLElement | null,
) => void;

interface UseMoleculeGridOptions {
  molecule: MoleculeResponse | null;
  savedLayout: GridLayoutItem[] | null | undefined;
  savedBreakpoint: LayoutBreakpoint | null | undefined;
  setGridLayout: (layout: GridLayoutItem[], breakpoint: LayoutBreakpoint) => void;
}

export function compactLayoutToTop(layout: LayoutItem[], cols: number): LayoutItem[] {
  return [
    ...verticalCompactor.compact(
      layout.map((item) => ({ ...item })),
      cols,
    ),
  ];
}

function getElasticOffsetPx(overflowPx: number): number {
  if (overflowPx <= 0) return 0;
  return ELASTIC_MAX_OFFSET_PX * (1 - Math.exp(-overflowPx / ELASTIC_STIFFNESS_PX));
}

function setDragElasticOffset(node: HTMLElement, xPx: number, yPx: number): void {
  node.style.setProperty("--drag-elastic-x", `${xPx.toFixed(2)}px`);
  node.style.setProperty("--drag-elastic-y", `${yPx.toFixed(2)}px`);
}

function clearDragElasticOffset(node: HTMLElement): void {
  node.style.removeProperty("--drag-elastic-x");
  node.style.removeProperty("--drag-elastic-y");
}

export function useMoleculeGrid({
  molecule,
  savedLayout,
  savedBreakpoint,
  setGridLayout,
}: UseMoleculeGridOptions) {
  const dragGrabOffsetRef = useRef<{ x: number; y: number } | null>(null);
  const {
    containerRef,
    width: containerWidth,
    mounted,
  } = useContainerWidth({ measureBeforeMount: true });

  useEffect(() => {
    if (!containerRef.current) return;

    const checkOverflow = () => {
      const container = containerRef.current;
      if (!container) return;

      const containerRect = container.getBoundingClientRect();
      const gridItems = container.querySelectorAll(".react-grid-item");

      gridItems.forEach((item) => {
        const itemRect = item.getBoundingClientRect();
        if (itemRect.right > containerRect.right) {
          const overflow = itemRect.right - containerRect.right;
          logAppWarning("molecule.grid", "Grid item overflow detected.", {
            itemId: item.getAttribute("id") || "unknown",
            overflowPx: Number(overflow.toFixed(2)),
            containerWidth: containerRect.width,
            itemWidth: itemRect.width,
          });
        }
      });
    };

    const timer = setTimeout(checkOverflow, 100);
    return () => clearTimeout(timer);
  }, [containerRef, containerWidth, molecule]);

  const buildLayout = useCallback(
    (width: number): LayoutItem[] => {
      const cols = calculateResponsiveColumns(width);
      const responsiveBase = calculateResponsiveLayout(width);
      const currentBreakpoint = getLayoutBreakpoint(width);

      const shouldUseSaved = savedLayout && savedBreakpoint === currentBreakpoint;
      const mergedLayout = responsiveBase.map((def) => {
        if (!shouldUseSaved) return def;
        const saved = savedLayout.find((l) => l.i === def.i);
        return saved ? { ...def, x: saved.x, y: saved.y, w: saved.w, h: saved.h } : def;
      });

      return compactLayoutToTop(mergedLayout, cols);
    },
    [savedBreakpoint, savedLayout],
  );

  const handleGridDragStart = useCallback<GridEventCallback>(
    (_layout, _oldItem, _newItem, _placeholder, e, node) => {
      if (!node) return;
      if (!("clientX" in e) || !("clientY" in e)) return;

      const pointer = e as Event & { clientX: number; clientY: number };
      const rect = node.getBoundingClientRect();
      dragGrabOffsetRef.current = {
        x: pointer.clientX - rect.left,
        y: pointer.clientY - rect.top,
      };
      clearDragElasticOffset(node);
    },
    [],
  );

  const handleGridDrag = useCallback<GridEventCallback>(
    (_layout, _oldItem, _newItem, _placeholder, e, node) => {
      if (!node) return;
      const grab = dragGrabOffsetRef.current;
      if (!grab) return;
      if (!("clientX" in e) || !("clientY" in e)) return;

      const pointer = e as Event & { clientX: number; clientY: number };
      const parent = node.offsetParent as HTMLElement | null;
      if (!parent) return;

      const parentRect = parent.getBoundingClientRect();
      const maxLeftPx = parent.clientWidth - node.offsetWidth;
      const maxTopPx = parent.clientHeight - node.offsetHeight;

      const desiredLeftPx = pointer.clientX - parentRect.left - grab.x;
      const desiredTopPx = pointer.clientY - parentRect.top - grab.y;

      const overflowLeftPx = Math.max(0, -desiredLeftPx);
      const overflowRightPx = Math.max(0, desiredLeftPx - maxLeftPx);
      const overflowTopPx = Math.max(0, -desiredTopPx);
      const overflowBottomPx = Math.max(0, desiredTopPx - maxTopPx);

      const elasticX = getElasticOffsetPx(overflowRightPx) - getElasticOffsetPx(overflowLeftPx);
      const elasticY = getElasticOffsetPx(overflowBottomPx) - getElasticOffsetPx(overflowTopPx);

      setDragElasticOffset(node, elasticX, elasticY);
    },
    [],
  );

  const handleGridDragStop = useCallback<GridEventCallback>(
    (_layout, _oldItem, _newItem, _placeholder, _e, node) => {
      if (!node) return;
      dragGrabOffsetRef.current = null;
      clearDragElasticOffset(node);
    },
    [],
  );

  const handleLayoutChange = useCallback(
    (layout: Layout) => {
      const cols = calculateResponsiveColumns(containerWidth);
      const compacted = compactLayoutToTop([...layout], cols);
      setGridLayout(compacted, getLayoutBreakpoint(containerWidth));
    },
    [containerWidth, setGridLayout],
  );

  const resetLayout = useCallback(() => {
    setGridLayout([], getLayoutBreakpoint(containerWidth));
  }, [containerWidth, setGridLayout]);

  return {
    buildLayout,
    containerRef,
    containerWidth,
    handleGridDrag,
    handleGridDragStart,
    handleGridDragStop,
    handleLayoutChange,
    mounted,
    resetLayout,
  };
}
