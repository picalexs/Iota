import type { LayoutItem } from "react-grid-layout";
import {
  GRID_MOBILE_BREAKPOINT,
  GRID_SMALL_TABLET_BREAKPOINT,
  GRID_TABLET_BREAKPOINT,
} from "@/lib/layout-constants";

export const MOBILE_BREAKPOINT = GRID_MOBILE_BREAKPOINT;
export const SMALL_TABLET_BREAKPOINT = GRID_SMALL_TABLET_BREAKPOINT;
export const TABLET_BREAKPOINT = GRID_TABLET_BREAKPOINT;
export { GRID_ROW_HEIGHT as ROW_HEIGHT } from "@/lib/layout-constants";

/**
 * Get the current layout breakpoint name based on container width
 */
export function getLayoutBreakpoint(
  width: number,
): "mobile" | "small-tablet" | "tablet" | "desktop" {
  if (width < MOBILE_BREAKPOINT) return "mobile";
  if (width < SMALL_TABLET_BREAKPOINT) return "small-tablet";
  if (width < TABLET_BREAKPOINT) return "tablet";
  return "desktop";
}

/**
 * Calculates responsive number of grid columns based on container width
 * @param width Container width in pixels
 * @returns Number of grid columns (1, 6, 8, or 12)
 */
export function calculateResponsiveColumns(width: number): number {
  if (width < MOBILE_BREAKPOINT) return 1;
  if (width < SMALL_TABLET_BREAKPOINT) return 6;
  if (width < TABLET_BREAKPOINT) return 8;
  return 12;
}

/**
 * Mobile layout variant (1 column)
 * All items stack vertically, each spans full width (w: 1)
 */
function getMobileLayout(): LayoutItem[] {
  return [
    { i: "viewer", x: 0, y: 0, w: 1, h: 7, minW: 1, minH: 4 },
    { i: "properties", x: 0, y: 7, w: 1, h: 5, minW: 1, minH: 3 },
    { i: "description", x: 0, y: 12, w: 1, h: 5, minW: 1, minH: 3 },
    { i: "identifiers", x: 0, y: 17, w: 1, h: 5, minW: 1, minH: 3 },
    { i: "atoms", x: 0, y: 22, w: 1, h: 5, minW: 1, minH: 3 },
  ];
}

/**
 * Small-tablet layout variant (6 columns = 2-column layout)
 * Viewer spans full width, other items arranged 2-per-row
 */
function getSmallTabletLayout(): LayoutItem[] {
  return [
    { i: "viewer", x: 0, y: 0, w: 6, h: 7, minW: 3, minH: 4 },
    { i: "properties", x: 0, y: 7, w: 3, h: 5, minW: 2, minH: 3 },
    { i: "description", x: 3, y: 7, w: 3, h: 5, minW: 2, minH: 3 },
    { i: "identifiers", x: 0, y: 12, w: 3, h: 5, minW: 2, minH: 3 },
    { i: "atoms", x: 3, y: 12, w: 3, h: 5, minW: 2, minH: 3 },
  ];
}

/**
 * Tablet layout variant (8 columns)
 * Viewer full-width top row, 2×2 grid below
 */
function getTabletLayout(): LayoutItem[] {
  return [
    { i: "viewer", x: 0, y: 0, w: 8, h: 7, minW: 4, minH: 4 },
    { i: "properties", x: 0, y: 7, w: 4, h: 5, minW: 2, minH: 3 },
    { i: "description", x: 4, y: 7, w: 4, h: 5, minW: 2, minH: 3 },
    { i: "identifiers", x: 0, y: 12, w: 4, h: 5, minW: 2, minH: 3 },
    { i: "atoms", x: 4, y: 12, w: 4, h: 5, minW: 2, minH: 3 },
  ];
}

/**
 * Desktop layout variant (12 columns = 3-column layout)
 * Viewer + properties in first row with matched heights.
 * Description, identifiers, and atoms in second row with matched heights.
 */
function getDesktopLayout(): LayoutItem[] {
  return [
    { i: "viewer", x: 0, y: 0, w: 8, h: 7, minW: 3, minH: 4 },
    { i: "properties", x: 8, y: 0, w: 4, h: 7, minW: 2, minH: 3 },
    { i: "description", x: 0, y: 7, w: 4, h: 5, minW: 2, minH: 3 },
    { i: "identifiers", x: 4, y: 7, w: 4, h: 5, minW: 2, minH: 3 },
    { i: "atoms", x: 8, y: 7, w: 4, h: 5, minW: 2, minH: 3 },
  ];
}

/**
 * Calculates responsive layout based on container width.
 */
export function calculateResponsiveLayout(containerWidth: number): LayoutItem[] {
  if (containerWidth < MOBILE_BREAKPOINT) {
    return getMobileLayout();
  }

  if (containerWidth < SMALL_TABLET_BREAKPOINT) {
    return getSmallTabletLayout();
  }

  if (containerWidth < TABLET_BREAKPOINT) {
    return getTabletLayout();
  }

  return getDesktopLayout();
}
