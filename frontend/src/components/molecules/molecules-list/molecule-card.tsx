import { Link } from "@tanstack/react-router";
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";

import { Checkbox } from "@/components/ui/checkbox";
import { preloadMoleculeViewer3D } from "@/components/molecules/molecule-viewer-3d-preload";
import type { MoleculeSummaryResponse } from "@/types/run";
import { cn } from "@/lib/utils";
import { preloadMoleculeDetailPageModule } from "@/routes/lazy-pages";

export const MOLECULE_TABLE_GRID = "grid-cols-[minmax(0,2fr)_minmax(0,0.9fr)_64px]";
export const MOLECULE_TABLE_GRID_WITH_SELECTION =
  "grid-cols-[2.25rem_minmax(0,2fr)_minmax(0,0.9fr)_64px]";

export type MoleculeSortField = "name" | "atoms";
export type SortOrder = "asc" | "desc";

interface MoleculeSortHeaderProps {
  readonly label: string;
  readonly field: MoleculeSortField;
  readonly sortField: MoleculeSortField;
  readonly sortOrder: SortOrder;
  readonly onSort: (field: MoleculeSortField) => void;
  readonly align?: "left" | "right";
}

export function MoleculeSortHeader({
  label,
  field,
  sortField,
  sortOrder,
  onSort,
  align = "left",
}: MoleculeSortHeaderProps) {
  const isActive = sortField === field;
  let Icon = ArrowUpDown;
  if (isActive) {
    Icon = sortOrder === "asc" ? ArrowUp : ArrowDown;
  }

  return (
    <button
      type="button"
      onClick={() => onSort(field)}
      className={cn(
        "flex items-center gap-1 text-xs font-medium text-muted-foreground uppercase tracking-wide hover:text-foreground transition-colors",
        align === "right" && "justify-end w-full",
      )}
    >
      {align === "right" && <Icon className={cn("size-3", !isActive && "opacity-40")} />}
      {label}
      {align === "left" && <Icon className={cn("size-3", !isActive && "opacity-40")} />}
    </button>
  );
}

interface MoleculeCardProps {
  readonly molecule: MoleculeSummaryResponse;
  readonly selectionMode?: boolean;
  readonly selected?: boolean;
  readonly onToggleSelected?: () => void;
}

export function MoleculeCard({
  molecule,
  selectionMode = false,
  selected = false,
  onToggleSelected,
}: MoleculeCardProps) {
  const nameWithDetails = molecule.iupac_name
    ? `${molecule.name} · ${molecule.iupac_name}`
    : molecule.name;
  const preloadDetailView = () => {
    preloadMoleculeDetailPageModule();
    preloadMoleculeViewer3D();
  };
  const rowClassName = cn(
    "grid items-center gap-4 border-b px-4 py-3 last:border-0 transition-colors",
    selectionMode ? MOLECULE_TABLE_GRID_WITH_SELECTION : MOLECULE_TABLE_GRID,
    selectionMode ? "w-full text-left hover:bg-accent/50" : "hover:bg-accent/50 hover:underline",
  );

  const rowContent = (
    <>
      {selectionMode ? (
        <span className="flex justify-center">
          <Checkbox
            aria-label={`Select ${molecule.name}`}
            checked={selected}
            onClick={(event) => event.stopPropagation()}
            onCheckedChange={() => onToggleSelected?.()}
          />
        </span>
      ) : null}
      <span className="min-w-0 truncate text-sm font-semibold" title={nameWithDetails}>
        {nameWithDetails}
      </span>
      <span
        className="min-w-0 truncate text-right text-sm font-mono text-muted-foreground"
        title={molecule.formula}
      >
        {molecule.formula}
      </span>
      <span
        className="text-right text-sm tabular-nums text-muted-foreground"
        title={`${molecule.atom_count} atoms`}
      >
        {molecule.atom_count}
      </span>
    </>
  );

  if (selectionMode) {
    return (
      <div
        role="button"
        tabIndex={0}
        className={rowClassName}
        onClick={() => onToggleSelected?.()}
        aria-pressed={selected}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            onToggleSelected?.();
          }
        }}
      >
        {rowContent}
      </div>
    );
  }

  return (
    <Link
      to="/molecules/$moleculeId"
      params={{ moleculeId: molecule.id }}
      onFocus={preloadDetailView}
      onMouseEnter={preloadDetailView}
      onMouseDown={preloadDetailView}
      onTouchStart={preloadDetailView}
      className={rowClassName}
      aria-label={molecule.name}
    >
      {rowContent}
    </Link>
  );
}
