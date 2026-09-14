/**
 * 2D Molecule Viewer Component
 * Renders a flat SVG representation of a molecule projected to the XY plane.
 * Uses CPK colour conventions and distance-based bond detection.
 */

import React, { useMemo } from "react";
import { calculateBonds } from "@/lib/chemistry-utils";
import type { AtomSchema } from "@/types/run";

// CPK colour convention (hex, dark-mode-friendly stroke added separately)
const CPK_COLORS: Record<string, string> = {
  H: "#BBBBBB",
  C: "#303030",
  N: "#3050F8",
  O: "#FF0D0D",
  F: "#90E050",
  Cl: "#1FF01F",
  Br: "#A62929",
  I: "#940094",
  S: "#FFFF30",
  P: "#FF8000",
  default: "#FF69B4",
};

// Display radius in SVG user units
const ATOM_RADII: Record<string, number> = {
  H: 7,
  C: 10,
  N: 10,
  O: 10,
  F: 9,
  Cl: 12,
  Br: 13,
  I: 14,
  S: 12,
  P: 12,
  default: 10,
};

const DEFAULT_ATOM_RADIUS = 10;
const DEFAULT_CPK_COLOR = "#FF69B4";

export interface MoleculeViewer2DProps {
  atoms: AtomSchema[];
  showBonds?: boolean;
  isDark?: boolean;
  className?: string;
}

function viewerLabelColor(fill: string): string {
  const hex = fill.replace("#", "");
  const normalized =
    hex.length === 3
      ? hex
          .split("")
          .map((char) => `${char}${char}`)
          .join("")
      : hex;
  const red = Number.parseInt(normalized.slice(0, 2), 16);
  const green = Number.parseInt(normalized.slice(2, 4), 16);
  const blue = Number.parseInt(normalized.slice(4, 6), 16);
  const luminance = (0.2126 * red + 0.7152 * green + 0.0722 * blue) / 255;
  return luminance >= 0.64 ? "#0f172a" : "#ffffff";
}

type MoleculePosition = { x: number; y: number };
type BondLine = { x1: number; y1: number; x2: number; y2: number };
type AtomCircle = {
  id: string;
  cx: number;
  cy: number;
  r: number;
  fill: string;
  stroke: string;
  label: string;
  showLabel: boolean;
};

function projectAtoms(atoms: AtomSchema[]): MoleculePosition[] {
  const SVG_W = 500;
  const SVG_H = 380;
  const PAD = 55;
  const xs = atoms.map((atom) => atom.x);
  const ys = atoms.map((atom) => atom.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const rangeX = maxX - minX || 1;
  const rangeY = maxY - minY || 1;
  const scale = Math.min((SVG_W - PAD * 2) / rangeX, (SVG_H - PAD * 2) / rangeY);
  const offsetX = (SVG_W - (maxX - minX) * scale) / 2;
  const offsetY = (SVG_H - (maxY - minY) * scale) / 2;
  const toX = (x: number) => (maxX === minX ? SVG_W / 2 : (x - minX) * scale + offsetX);
  const toY = (y: number) =>
    maxY === minY ? SVG_H / 2 : SVG_H - ((y - minY) * scale + offsetY);
  return atoms.map((atom) => ({ x: toX(atom.x), y: toY(atom.y) }));
}

function buildBondLines(atoms: AtomSchema[], positions: MoleculePosition[]): BondLine[] {
  return calculateBonds(atoms).flatMap((bond) => {
    const from = positions[bond.from];
    const to = positions[bond.to];
    return from && to ? [{ x1: from.x, y1: from.y, x2: to.x, y2: to.y }] : [];
  });
}

function buildAtomCircles(atoms: AtomSchema[], positions: MoleculePosition[]): AtomCircle[] {
  return atoms.map((atom, index) => {
    const position = positions[index];
    if (!position) {
      throw new Error("Expected a 2D position for every atom");
    }
    return {
      id: `atom-${index}`,
      cx: position.x,
      cy: position.y,
      r: ATOM_RADII[atom.symbol] ?? ATOM_RADII.default ?? DEFAULT_ATOM_RADIUS,
      fill: CPK_COLORS[atom.symbol] ?? CPK_COLORS.default ?? DEFAULT_CPK_COLOR,
      stroke: atom.symbol === "H" ? "#888888" : "#222222",
      label: atom.symbol,
      showLabel: atom.symbol !== "H" || atoms.length <= 6,
    };
  });
}

function buildMoleculeView(atoms: AtomSchema[], showBonds: boolean) {
  if (atoms.length === 0) {
    return { viewBox: "0 0 200 150", bondLines: [], atomCircles: [] };
  }
  const positions = projectAtoms(atoms);
  return {
    viewBox: "0 0 500 380",
    bondLines: showBonds ? buildBondLines(atoms, positions) : [],
    atomCircles: buildAtomCircles(atoms, positions),
  };
}

export const MoleculeViewer2D = React.memo(function MoleculeViewer2D({
  atoms,
  showBonds = true,
  isDark = false,
  className = "",
}: MoleculeViewer2DProps) {
  const { viewBox, bondLines, atomCircles } = useMemo(
    () => buildMoleculeView(atoms, showBonds),
    [atoms, showBonds],
  );

  if (atoms.length === 0) {
    return (
      <div
        data-testid="molecule-viewer-2d"
        className={`flex items-center justify-center text-muted-foreground text-sm ${className}`}
        style={{ width: "100%", height: "100%" }}
      >
        No atoms to display
      </div>
    );
  }

  return (
    <div
      data-testid="molecule-viewer-2d"
      className={`flex items-center justify-center bg-card ${className}`}
      style={{ width: "100%", height: "100%" }}
    >
      <svg
        viewBox={viewBox}
        style={{ width: "100%", height: "100%" }}
        xmlns="http://www.w3.org/2000/svg"
        role="img"
        aria-label="2D molecule structure"
      >
        {/* Bonds drawn first so atoms sit on top */}
        {bondLines.map((b) => (
          <line
            key={`${b.x1}-${b.y1}-${b.x2}-${b.y2}`}
            x1={b.x1}
            y1={b.y1}
            x2={b.x2}
            y2={b.y2}
            stroke={isDark ? "#888888" : "#555555"}
            strokeWidth={2.5}
            strokeLinecap="round"
          />
        ))}

        {/* Atoms */}
        {atomCircles.map((a) => (
          <g key={a.id}>
            <circle cx={a.cx} cy={a.cy} r={a.r} fill={a.fill} stroke={a.stroke} strokeWidth={1} />
            {a.showLabel && (
              <text
                x={a.cx}
                y={a.cy}
                textAnchor="middle"
                dominantBaseline="central"
                fontSize={a.r * 1.1}
                fontWeight="bold"
                fill={viewerLabelColor(a.fill)}
                style={{ userSelect: "none", pointerEvents: "none" }}
              >
                {a.label}
              </text>
            )}
          </g>
        ))}
      </svg>
    </div>
  );
});

export default MoleculeViewer2D;
