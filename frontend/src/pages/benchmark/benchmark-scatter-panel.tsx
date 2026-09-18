import { useRef } from "react";
import { Button } from "@/components/ui/button";
import { containerSurfaceClassName } from "@/lib/interactive-styles";
import { cn } from "@/lib/utils";
import { ExpandPanelButton } from "./benchmark-panel-expand-button";
import { RuntimeScatterDownloads } from "./benchmark-scatter-downloads";
import { RuntimeScatterChart, RuntimeScatterLegend } from "./benchmark-runtime-scatter-chart";
import type { CompletedPoint } from "./benchmark-scatter-data";
import {
  RuntimeScatterEmptyState,
  RuntimeScatterFilters,
  type ScatterFilterOption,
} from "./benchmark-scatter-filters";

export interface ScatterLabelLayout {
  x: number;
  y: number;
  textAnchor: "start" | "end";
}

export interface RuntimeScatterMetrics {
  width: number;
  height: number;
  topPad: number;
  leftPad: number;
  rightPad: number;
  bottomPad: number;
  plotWidth: number;
  targetMha: number;
  runtimeTicks: readonly number[];
  errorTicks: readonly number[];
  targetY: number;
  reduceInlineLabels: boolean;
  labelLayouts: ReadonlyMap<string, ScatterLabelLayout>;
  xForRuntime: (runtime: number) => number;
  yForError: (error: number) => number;
}

export interface RuntimeScatterPanelProps {
  readonly points: readonly CompletedPoint[];
  readonly totalPoints: number;
  readonly metrics: RuntimeScatterMetrics;
  readonly familyOptions: readonly ScatterFilterOption[];
  readonly algorithmOptions: readonly ScatterFilterOption[];
  readonly moleculeOptions: readonly ScatterFilterOption[];
  readonly hiddenFamilies: ReadonlySet<string>;
  readonly hiddenAlgorithms: ReadonlySet<string>;
  readonly hiddenMolecules: ReadonlySet<string>;
  readonly onToggleFamily: (value: string) => void;
  readonly onToggleAlgorithm: (value: string) => void;
  readonly onToggleMolecule: (value: string) => void;
  readonly onShowAllFamilies: () => void;
  readonly onHideAllFamilies: () => void;
  readonly onShowAllAlgorithms: () => void;
  readonly onHideAllAlgorithms: () => void;
  readonly onShowAllMolecules: () => void;
  readonly onHideAllMolecules: () => void;
  readonly onResetFilters: () => void;
  readonly showLabels: boolean;
  readonly onToggleLabels: () => void;
  readonly mode?: "embedded" | "fullscreen";
  readonly onExpand?: () => void;
}

export function RuntimeScatterPanel({
  points,
  totalPoints,
  metrics,
  familyOptions,
  algorithmOptions,
  moleculeOptions,
  hiddenFamilies,
  hiddenAlgorithms,
  hiddenMolecules,
  onToggleFamily,
  onToggleAlgorithm,
  onToggleMolecule,
  onShowAllFamilies,
  onHideAllFamilies,
  onShowAllAlgorithms,
  onHideAllAlgorithms,
  onShowAllMolecules,
  onHideAllMolecules,
  onResetFilters,
  showLabels,
  onToggleLabels,
  mode = "embedded",
  onExpand,
}: RuntimeScatterPanelProps) {
  const panelRef = useRef<HTMLDivElement | null>(null);
  const hasActiveFilters =
    hiddenFamilies.size > 0 || hiddenAlgorithms.size > 0 || hiddenMolecules.size > 0;
  const showFilterControls =
    hasActiveFilters ||
    familyOptions.length > 1 ||
    algorithmOptions.length > 1 ||
    moleculeOptions.length > 1;
  return (
    <div
      ref={panelRef}
      className={cn(
        "rounded-xl p-4",
        containerSurfaceClassName,
        mode === "fullscreen" && "flex h-full flex-col overflow-hidden",
      )}
    >
      <div
        className="mb-3 flex flex-wrap items-start justify-between gap-3"
        data-scatter-export-exclude=""
      >
        <div>
          <h2 className="text-sm font-semibold">Accuracy vs runtime</h2>
          <p className="text-xs text-muted-foreground">
            Hover a point for molecule and run details.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-8 px-2 text-xs"
            aria-label={`${showLabels ? "Hide" : "Show"} point labels on accuracy-vs-runtime chart`}
            onClick={onToggleLabels}
          >
            {showLabels ? "Hide labels" : "Show labels"}
          </Button>
          <RuntimeScatterDownloads points={points} panel={panelRef.current} />
          {mode === "embedded" && onExpand ? (
            <ExpandPanelButton label="accuracy vs runtime" onClick={onExpand} />
          ) : null}
        </div>
      </div>
      {showFilterControls ? (
        <div data-scatter-export-exclude="">
          <RuntimeScatterFilters
            familyOptions={familyOptions}
            algorithmOptions={algorithmOptions}
            moleculeOptions={moleculeOptions}
            hiddenFamilies={hiddenFamilies}
            hiddenAlgorithms={hiddenAlgorithms}
            hiddenMolecules={hiddenMolecules}
            hasActiveFilters={hasActiveFilters}
            pointsCount={points.length}
            totalPoints={totalPoints}
            onToggleFamily={onToggleFamily}
            onShowAllFamilies={onShowAllFamilies}
            onHideAllFamilies={onHideAllFamilies}
            onToggleAlgorithm={onToggleAlgorithm}
            onToggleMolecule={onToggleMolecule}
            onShowAllAlgorithms={onShowAllAlgorithms}
            onHideAllAlgorithms={onHideAllAlgorithms}
            onShowAllMolecules={onShowAllMolecules}
            onHideAllMolecules={onHideAllMolecules}
            onResetFilters={onResetFilters}
          />
        </div>
      ) : null}
      {points.length === 0 ? (
        <RuntimeScatterEmptyState
          totalPoints={totalPoints}
          hasActiveFilters={hasActiveFilters}
          onResetFilters={onResetFilters}
        />
      ) : (
        <>
          <RuntimeScatterLegend familyOptions={familyOptions} />
          <RuntimeScatterChart
            points={points}
            mode={mode}
            metrics={metrics}
            showLabels={showLabels}
          />
        </>
      )}
    </div>
  );
}
