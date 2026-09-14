import { DashboardTile } from "@/components/results/dashboard-tile";
import { BarPlot } from "@/components/results/charts/bar-plot";
import { ChartEmptyState } from "@/components/results/charts/chart-empty-state";
import { BenchmarkTileLoadingContent } from "@/components/results/tile-loading-content";
import type { RunResultResponse } from "@/types/run";
import { buildBenchmarkBars } from "@/lib/results/benchmarks";
import { assessChemicalAccuracy, formatAccuracyVerdict } from "@/lib/results/accuracy";

interface BenchmarkBarsTileProps {
  readonly result: RunResultResponse | null;
  readonly liveBestEnergy?: number | null;
  readonly hfEnergy?: number;
  readonly fciEnergy?: number;
  readonly chemicalAccuracyHa?: number;
  readonly algorithm?: string;
  readonly isRunning?: boolean;
  readonly pending?: boolean;
  readonly editMode?: boolean;
}

function benchmarkBarsForEnergy(
  resultEnergy: number | null,
  refs: { readonly hf?: number; readonly fci?: number },
  algorithm?: string,
) {
  if (resultEnergy === null) {
    return [];
  }
  return buildBenchmarkBars(resultEnergy, refs, algorithm);
}

export function BenchmarkBarsTile({
  result,
  liveBestEnergy,
  hfEnergy,
  fciEnergy,
  chemicalAccuracyHa,
  algorithm,
  isRunning = false,
  pending = false,
  editMode,
}: BenchmarkBarsTileProps) {
  const resultEnergy = result?.energy ?? liveBestEnergy ?? null;
  const isLive = result === null && resultEnergy !== null;
  const refs = { hf: hfEnergy, fci: fciEnergy };
  const accuracy = assessChemicalAccuracy({
    energy: resultEnergy,
    hf: hfEnergy,
    fci: fciEnergy,
    thresholdHa: chemicalAccuracyHa,
    converged: result?.converged ?? null,
  });
  const benchmarkBars = benchmarkBarsForEnergy(resultEnergy, refs, algorithm);
  const bars = benchmarkBars.map((b) => ({
    label: isLive && b.isResult ? `${b.label} (live)` : b.label,
    value: b.energy,
    isHighlight: b.isResult,
  }));

  return (
    <DashboardTile
      title="Benchmark Comparison"
      helpText="Horizontal comparison of HF, FCI/Exact (when available), and this run's energy. Chemical accuracy is the outcome; the energy trajectory explains how the run got there."
      editMode={editMode}
    >
      {pending ? (
        <BenchmarkTileLoadingContent />
      ) : (
        <div className="h-full min-h-0">
          {bars.length === 0 ? (
            <ChartEmptyState
              message="Waiting for first energy evaluation..."
              pending={pending || isRunning}
              pendingMessage="Awaiting first energy evaluation"
            />
          ) : (
            <BarPlot data={bars} yLabel="Energy (Ha)" />
          )}
        </div>
      )}
      {bars.length > 0 && refs.hf === undefined && refs.fci === undefined && (
        <p className="mt-2 text-xs italic text-muted-foreground">
          Reference energies not available for this run.
        </p>
      )}
      {bars.length > 0 && accuracy.isScorable && accuracy.errorMha !== null && (
        <p className="mt-2 text-xs text-muted-foreground">
          {formatAccuracyVerdict(accuracy.verdict)}. Δ {accuracy.errorMha >= 0 ? "+" : ""}
          {accuracy.errorMha.toFixed(2)} mHa vs FCI/Exact.
        </p>
      )}
    </DashboardTile>
  );
}
