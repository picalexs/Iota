import { DashboardTile } from "@/components/results/dashboard-tile";
import { SpectrumLadder } from "@/components/results/charts/spectrum-ladder";
import { ChartEmptyState } from "@/components/results/charts/chart-empty-state";
import { WorkflowRail } from "@/components/results/workflow-rail";
import type { SkqdMetrics } from "@/lib/results/parse-algorithm-metrics";

interface SkqdSpectrumTileProps {
  readonly metrics: SkqdMetrics;
  readonly isRunning?: boolean;
  readonly editMode?: boolean;
}

function asNumbers(value: unknown): number[] {
  if (!Array.isArray(value)) return [];
  return value.filter(
    (entry): entry is number => typeof entry === "number" && Number.isFinite(entry),
  );
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function numberMetric(record: Record<string, unknown> | null, key: string): number | null {
  const value = record?.[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function stringMetric(record: Record<string, unknown> | null, key: string): string | null {
  const value = record?.[key];
  return typeof value === "string" && value.length > 0 ? value : null;
}

function formatResidual(value: number | null): string {
  return value == null ? "-" : value.toExponential(2);
}

export function SkqdSpectrumTile({ metrics, isRunning = false, editMode }: SkqdSpectrumTileProps) {
  const diagnostics = asRecord(metrics.krylov_extension_diagnostics);
  const ritzValues = asNumbers(diagnostics?.["ritz_values"]);
  const basisRank =
    numberMetric(diagnostics, "basis_rank") ??
    numberMetric(diagnostics, "krylov_extension_dim") ??
    ritzValues.length;
  const relativeResidual =
    numberMetric(diagnostics, "relative_ritz_residual") ??
    numberMetric(diagnostics, "relative_residual");
  const seedSource = stringMetric(diagnostics, "seed_source")?.replaceAll("_", " ") ?? "SQD seed";

  return (
    <DashboardTile
      title="SKQD Spectrum"
      helpText="Krylov-extension Ritz spectrum produced from the SQD seed, separated from the diagnostic metadata for easier comparison with QFD and KQD spectra."
      editMode={editMode}
    >
      <div className="flex h-full min-h-0 flex-col gap-3">
        <div className="min-h-0 flex-1">
          {ritzValues.length > 0 ? (
            <SpectrumLadder energies={ritzValues} />
          ) : (
            <ChartEmptyState
              message="No Krylov Ritz values recorded"
              pending={isRunning}
              pendingMessage="Awaiting Krylov Ritz values"
            />
          )}
        </div>
        <WorkflowRail
          steps={[
            {
              label: "Seed",
              value: seedSource,
              hint: "SQD-selected state",
            },
            {
              label: "Extend",
              value: "Krylov basis",
              hint: `Rank ${basisRank}`,
            },
            {
              label: "Solve",
              value: "Ritz spectrum",
              hint: `${ritzValues.length} levels`,
            },
          ]}
        />
        <div className="flex shrink-0 flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <span>Ritz levels: {ritzValues.length}</span>
          <span>Basis rank: {basisRank}</span>
          <span>Residual: {formatResidual(relativeResidual)}</span>
        </div>
      </div>
    </DashboardTile>
  );
}
