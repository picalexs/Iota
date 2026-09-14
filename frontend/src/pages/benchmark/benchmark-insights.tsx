import { FullscreenPanel } from "@/components/ui/fullscreen-panel";
import { useMemo, useState } from "react";
import type { MoleculePreset } from "@/lib/benchmark-presets";
import type { BenchmarkEntry } from "./benchmark-utils";
import { AccuracyMatrix } from "./benchmark-accuracy-matrix";
import { buildRuntimeScatterMetrics } from "./benchmark-insights-geometry";
import { RuntimeScatterPanel } from "./benchmark-scatter-panel";
import { buildCompletedPoints } from "./benchmark-scatter-data";
import { useBenchmarkScatterFilters } from "./use-benchmark-scatter-filters";

interface BenchmarkInsightsProps {
  readonly grouped: ReadonlyArray<{ preset: MoleculePreset; rows: readonly BenchmarkEntry[] }>;
  readonly chemicalAccuracyHa: number;
}

type ExpandedPanel = "matrix" | "scatter" | null;

export function BenchmarkInsights({
  grouped,
  chemicalAccuracyHa,
}: Readonly<BenchmarkInsightsProps>) {
  const [expandedPanel, setExpandedPanel] = useState<ExpandedPanel>(null);
  const [showScatterLabels, setShowScatterLabels] = useState(true);
  const points = useMemo(
    () => buildCompletedPoints(grouped, chemicalAccuracyHa),
    [chemicalAccuracyHa, grouped],
  );
  const {
    filteredPoints,
    familyOptions,
    algorithmOptions,
    moleculeOptions,
    hiddenFamilies: hiddenFamilySet,
    hiddenAlgorithms: hiddenAlgorithmSet,
    hiddenMolecules: hiddenMoleculeSet,
    toggleFamily,
    toggleAlgorithm,
    toggleMolecule,
    showAllFamilies,
    hideAllFamilies,
    showAllAlgorithms,
    hideAllAlgorithms,
    showAllMolecules,
    hideAllMolecules,
    resetFilters,
  } = useBenchmarkScatterFilters(points);
  const totalRows = grouped.flatMap((item) => item.rows).length;
  if (totalRows === 0) return null;

  const bestPoint = [...filteredPoints].sort(
    (left, right) => left.absErrorMha - right.absErrorMha || left.runtime - right.runtime,
  )[0];
  const bestPointSummary = bestPoint
    ? `${bestPoint.molecule} ${bestPoint.algorithm} is currently the closest scored row to target.`
    : "No scored benchmark rows yet.";

  return (
    <>
      <section className="grid gap-4">
        <AccuracyMatrix
          grouped={grouped}
          chemicalAccuracyHa={chemicalAccuracyHa}
          onExpand={() => setExpandedPanel("matrix")}
        />
        <RuntimeScatterPanel
          points={filteredPoints}
          totalPoints={points.length}
          metrics={buildRuntimeScatterMetrics({
            points: filteredPoints,
            chemicalAccuracyHa,
            mode: "embedded",
          })}
          familyOptions={familyOptions}
          algorithmOptions={algorithmOptions}
          moleculeOptions={moleculeOptions}
          hiddenFamilies={hiddenFamilySet}
          hiddenAlgorithms={hiddenAlgorithmSet}
          hiddenMolecules={hiddenMoleculeSet}
          onToggleFamily={toggleFamily}
          onToggleAlgorithm={toggleAlgorithm}
          onToggleMolecule={toggleMolecule}
          onShowAllFamilies={showAllFamilies}
          onHideAllFamilies={hideAllFamilies}
          onShowAllAlgorithms={showAllAlgorithms}
          onHideAllAlgorithms={hideAllAlgorithms}
          onShowAllMolecules={showAllMolecules}
          onHideAllMolecules={hideAllMolecules}
          onResetFilters={resetFilters}
          showLabels={showScatterLabels}
          onToggleLabels={() => setShowScatterLabels((current) => !current)}
          onExpand={() => setExpandedPanel("scatter")}
        />
        <div className="sr-only" aria-live="polite">
          {bestPointSummary}
        </div>
      </section>

      <FullscreenPanel
        open={expandedPanel === "matrix"}
        onClose={() => setExpandedPanel(null)}
        title="Accuracy matrix"
        bodyClassName="overflow-hidden"
      >
        <AccuracyMatrix
          grouped={grouped}
          chemicalAccuracyHa={chemicalAccuracyHa}
          mode="fullscreen"
        />
      </FullscreenPanel>

      <FullscreenPanel
        open={expandedPanel === "scatter"}
        onClose={() => setExpandedPanel(null)}
        title="Accuracy vs runtime"
        bodyClassName="overflow-hidden"
      >
        <RuntimeScatterPanel
          points={filteredPoints}
          totalPoints={points.length}
          metrics={buildRuntimeScatterMetrics({
            points: filteredPoints,
            chemicalAccuracyHa,
            mode: "fullscreen",
          })}
          familyOptions={familyOptions}
          algorithmOptions={algorithmOptions}
          moleculeOptions={moleculeOptions}
          hiddenFamilies={hiddenFamilySet}
          hiddenAlgorithms={hiddenAlgorithmSet}
          hiddenMolecules={hiddenMoleculeSet}
          onToggleFamily={toggleFamily}
          onToggleAlgorithm={toggleAlgorithm}
          onToggleMolecule={toggleMolecule}
          onShowAllFamilies={showAllFamilies}
          onHideAllFamilies={hideAllFamilies}
          onShowAllAlgorithms={showAllAlgorithms}
          onHideAllAlgorithms={hideAllAlgorithms}
          onShowAllMolecules={showAllMolecules}
          onHideAllMolecules={hideAllMolecules}
          onResetFilters={resetFilters}
          showLabels={showScatterLabels}
          onToggleLabels={() => setShowScatterLabels((current) => !current)}
          mode="fullscreen"
        />
      </FullscreenPanel>
    </>
  );
}
