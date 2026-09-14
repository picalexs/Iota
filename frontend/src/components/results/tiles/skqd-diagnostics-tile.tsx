import { DashboardTile } from "@/components/results/dashboard-tile";
import {
  MeasurementOutcomesPanel,
  type BitstringOutcome,
} from "@/components/results/measurement-outcomes-panel";
import type { SkqdMetrics } from "@/lib/results/parse-algorithm-metrics";
import { cn } from "@/lib/utils";

interface SkqdDiagnosticsTileProps {
  readonly metrics: SkqdMetrics;
  readonly editMode?: boolean;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function asBitstringDistribution(value: unknown): BitstringOutcome[] {
  if (!Array.isArray(value)) return [];
  return value
    .flatMap((entry) => {
      const record = asRecord(entry);
      const bitstring = typeof record?.bitstring === "string" ? record.bitstring : null;
      let probability: number | null = null;
      if (typeof record?.normalized_probability === "number") {
        probability = record.normalized_probability;
      } else if (typeof record?.probability === "number") {
        probability = record.probability;
      }
      if (bitstring == null || probability == null) return [];
      return [{ bitstring, probability }];
    })
    .sort((left, right) => right.probability - left.probability)
    .slice(0, 6);
}

function numberMetric(record: Record<string, unknown> | null, key: string): number | null {
  const value = record?.[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function stringMetric(record: Record<string, unknown> | null, key: string): string | null {
  const value = record?.[key];
  return typeof value === "string" && value.length > 0 ? value : null;
}

function booleanMetric(record: Record<string, unknown> | null, key: string): boolean | null {
  const value = record?.[key];
  return typeof value === "boolean" ? value : null;
}

function formatBoolean(value: boolean | null): string {
  if (value == null) return "-";
  return value ? "yes" : "no";
}

function formatResidual(value: number | null): string {
  if (value == null) {
    return "-";
  }
  return value.toExponential(2);
}

function residualTone(relativeResidual: number | null, residualTolerance: number | null) {
  if (relativeResidual == null || residualTolerance == null) {
    return "amber";
  }
  return relativeResidual <= residualTolerance ? "green" : "amber";
}

function DiagnosticPill({
  label,
  value,
  tone = "neutral",
}: Readonly<{
  readonly label: string;
  readonly value: string;
  readonly tone?: "neutral" | "green" | "amber";
}>) {
  return (
    <div
      className={cn(
        "rounded-md border border-border/60 bg-muted/30 px-2.5 py-1.5",
        tone === "green" && "border-success/35 bg-success/12 text-success",
        tone === "amber" && "border-warning/35 bg-warning/12 text-warning",
      )}
    >
      <p className="text-[10px] font-medium text-muted-foreground">{label}</p>
      <p className="mt-0.5 font-mono text-xs font-semibold tabular-nums">{value}</p>
    </div>
  );
}

export function SkqdDiagnosticsTile({ metrics, editMode }: SkqdDiagnosticsTileProps) {
  const kext = asRecord(metrics.krylov_extension_diagnostics);
  const krylov_rank =
    numberMetric(kext, "basis_rank") ?? numberMetric(kext, "krylov_extension_dim") ?? 0;
  const relativeResidual = numberMetric(kext, "relative_ritz_residual");
  const residualTolerance = numberMetric(kext, "residual_tolerance");
  const seedSource = stringMetric(kext, "seed_source");
  const sqdConverged = booleanMetric(kext, "sqd_converged");
  const krylovConverged = booleanMetric(kext, "krylov_converged");
  const overallConverged = booleanMetric(kext, "overall_converged");
  const bitstrings = asBitstringDistribution(kext?.["krylov_state_bitstring_distribution"]);

  return (
    <DashboardTile
      title="SKQD Diagnostics"
      helpText="Krylov extension diagnostics and seeded-state bitstring outcomes separated from the circuit preview."
      editMode={editMode}
    >
      <div className="flex h-full flex-col gap-3">
        <div className="grid gap-2 sm:grid-cols-4">
          <DiagnosticPill label="Basis rank" value={krylov_rank > 0 ? String(krylov_rank) : "-"} />
          <DiagnosticPill
            label="Krylov residual"
            value={formatResidual(relativeResidual)}
            tone={residualTone(relativeResidual, residualTolerance)}
          />
          <DiagnosticPill label="Seed" value={seedSource?.replaceAll("_", " ") ?? "-"} />
          <DiagnosticPill
            label="Overall"
            value={formatBoolean(overallConverged)}
            tone={overallConverged ? "green" : "amber"}
          />
        </div>
        {bitstrings.length > 0 && (
          <div className="min-h-0 flex-1">
            <MeasurementOutcomesPanel
              outcomes={bitstrings}
              stateKey="skqd-diagnostics-outcomes"
              emptyMessage="No Krylov-state outcomes recorded"
              maxRows={6}
            />
          </div>
        )}
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        Krylov rank: {krylov_rank} · SQD converged: {formatBoolean(sqdConverged)} · Krylov
        converged: {formatBoolean(krylovConverged)}
      </p>
    </DashboardTile>
  );
}
