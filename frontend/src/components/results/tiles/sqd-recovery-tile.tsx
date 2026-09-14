import { useEffect, useMemo, useState } from "react";
import { DashboardTile } from "@/components/results/dashboard-tile";
import { ChartEmptyState } from "@/components/results/charts/chart-empty-state";
import {
  MeasurementOutcomesPanel,
  type BitstringOutcome,
} from "@/components/results/measurement-outcomes-panel";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { formatDuration } from "@/lib/format-duration";
import type { CircuitArtifact, JsonObject } from "@/types/run";
import type { SqdMetrics } from "@/lib/results/parse-algorithm-metrics";

interface SqdRecoveryTileProps {
  readonly metrics: SqdMetrics;
  readonly isRunning?: boolean;
  readonly editMode?: boolean;
}

function getNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function getString(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function asRecordList(value: unknown): JsonObject[] {
  if (!Array.isArray(value)) return [];
  return value.filter(
    (item): item is JsonObject => Boolean(item) && typeof item === "object" && !Array.isArray(item),
  );
}

function extractBitstrings(metrics: SqdMetrics): BitstringOutcome[] {
  const packageRecord = metrics.sci_result_package;
  const selected = asRecordList(packageRecord?.["final_bitstring_probabilities"]);
  const sampled = asRecordList(packageRecord?.["final_sampled_bitstring_distribution"]);
  const source = selected.length > 0 ? selected : sampled;

  return source
    .flatMap((entry) => {
      const bitstring = getString(entry["bitstring"]);
      const probability =
        getNumber(entry["normalized_probability"]) ?? getNumber(entry["probability"]);
      if (bitstring == null || probability == null) return [];
      return [
        {
          bitstring,
          probability,
          count: getNumber(entry["count"]),
        },
      ];
    })
    .sort((left, right) => right.probability - left.probability)
    .slice(0, 8);
}

function latestRecovery(metrics: SqdMetrics): JsonObject | null {
  const recoveryTrace = metrics.configuration_recovery_trace;
  return recoveryTrace.at(-1) ?? null;
}

function formatPercent(value: number | null): string {
  if (value == null) {
    return "-";
  }
  return `${(value * 100).toFixed(1)}%`;
}

function formatMaybeNumber(value: number | null, digits = 2): string {
  if (value == null) {
    return "-";
  }
  return value.toFixed(digits);
}

function formatOptionalCount(value: number | null): string {
  if (value == null) {
    return "-";
  }
  return value.toLocaleString();
}

function formatOptionalDuration(value: number | null): string {
  if (value == null) {
    return "-";
  }
  return formatDuration(value);
}

function StatBox({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <div className="rounded-md border border-border/60 bg-muted/30 px-2.5 py-2">
      <p className="text-[10px] font-medium text-muted-foreground">{label}</p>
      <p className="mt-1 font-mono text-xs font-semibold tabular-nums">{value}</p>
    </div>
  );
}

function artifactOptionLabel(artifact: CircuitArtifact): string {
  if (artifact.iteration != null) {
    return `Iter ${artifact.iteration}`;
  }
  return artifact.label ?? "Circuit";
}

function getRecoverySteps(metrics: SqdMetrics) {
  return metrics.configuration_recovery_trace.filter(
    (entry) => getNumber(entry["iteration"]) != null,
  );
}

function getDefaultArtifactId(artifacts: CircuitArtifact[]): string | null {
  const fallbackArtifact = artifacts.at(-1);
  return artifacts.find((artifact) => artifact.representative)?.id ?? fallbackArtifact?.id ?? null;
}

function getSelectedArtifact(
  artifacts: CircuitArtifact[],
  selectedArtifactId: string | null,
): CircuitArtifact | null {
  const fallbackArtifact = artifacts.at(-1);
  return (
    artifacts.find((artifact) => artifact.id === selectedArtifactId) ?? fallbackArtifact ?? null
  );
}

function buildSubsamplingParts(samplesPerBatch: number | null, numBatches: number | null) {
  const parts: string[] = [];
  if (samplesPerBatch != null) {
    parts.push(`${samplesPerBatch.toLocaleString()} shots/batch`);
  }
  if (numBatches != null) {
    parts.push(`${numBatches.toLocaleString()} batches`);
  }
  return parts;
}

function buildSubsamplingSummary(subsampling: SqdMetrics["subsampling_summary"]): string | null {
  const samplesPerBatch = getNumber(subsampling?.["samples_per_batch"]);
  const numBatches = getNumber(subsampling?.["num_batches"]);

  if (samplesPerBatch == null && numBatches == null) {
    return null;
  }

  return buildSubsamplingParts(samplesPerBatch, numBatches).join(" · ");
}

function buildRecoveryStats(latest: JsonObject | null, metrics: SqdMetrics) {
  const postselection = metrics.postselection_summary;
  const selectedFraction =
    getNumber(latest?.["postselection_weight"]) ?? getNumber(postselection?.["selected_fraction"]);
  const selectedSamples =
    getNumber(latest?.["accepted_samples"]) ??
    getNumber(latest?.["selected_samples"]) ??
    getNumber(postselection?.["selected_samples"]);
  const sampledBitstrings = getNumber(latest?.["sampled_bitstrings"]);
  const sampledConfigurations = getNumber(latest?.["sampled_configurations"]);
  const occupancyDelta = getNumber(latest?.["occupancy_delta"]);
  const energyDelta = getNumber(latest?.["delta_energy"]);
  const iterationWallSeconds = getNumber(latest?.["iter_wall_seconds"]);

  return [
    { label: "Selected", value: formatPercent(selectedFraction) },
    { label: "Configs", value: formatOptionalCount(selectedSamples) },
    { label: "Sampled", value: formatOptionalCount(sampledConfigurations) },
    { label: "Bitstrings", value: formatOptionalCount(sampledBitstrings) },
    { label: "Occ delta", value: formatMaybeNumber(occupancyDelta, 3) },
    { label: "ΔE", value: formatMaybeNumber(energyDelta, 6) },
    {
      label: "Iter time",
      value: formatOptionalDuration(iterationWallSeconds),
    },
  ];
}

function RecoveryIterationSelector({
  artifacts,
  selectedArtifactId,
  onValueChange,
}: {
  readonly artifacts: CircuitArtifact[];
  readonly selectedArtifactId: string | null;
  readonly onValueChange: (value: string) => void;
}) {
  if (artifacts.length <= 1) {
    return null;
  }

  return (
    <div className="rounded-md border border-border/60 bg-muted/20 px-2 py-1.5">
      <p className="mb-1 text-[10px] font-medium text-muted-foreground">Recovery iter</p>
      <Select value={selectedArtifactId ?? undefined} onValueChange={onValueChange}>
        <SelectTrigger size="sm" className="h-8 w-full text-xs">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {artifacts.map((artifact, index) => (
            <SelectItem key={artifact.id ?? index} value={artifact.id ?? String(index)}>
              {artifactOptionLabel(artifact)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

function RecoveryStatsGrid({
  stats,
}: Readonly<{
  readonly stats: Array<{ readonly label: string; readonly value: string }>;
}>) {
  return (
    <div className="grid grid-cols-2 gap-2">
      {stats.map((stat) => (
        <StatBox key={stat.label} label={stat.label} value={stat.value} />
      ))}
    </div>
  );
}

function RecoveryFooter({
  subsamplingSummary,
  artifactCount,
  selectedIteration,
}: Readonly<{
  readonly subsamplingSummary: string | null;
  readonly artifactCount: number;
  readonly selectedIteration: number | null;
}>) {
  let selectedIterationLabel = null;
  if (selectedIteration != null) {
    selectedIterationLabel = ` · iter ${Math.round(selectedIteration)}`;
  }

  return (
    <>
      {subsamplingSummary && (
        <p className="text-[10px] text-muted-foreground">{subsamplingSummary}</p>
      )}
      <p className="text-[10px] text-muted-foreground">
        {artifactCount > 1 ? "Selected recovery step" : "Final recovery step"}
        {selectedIterationLabel}
      </p>
    </>
  );
}

export function SqdRecoveryTile({ metrics, isRunning = false, editMode }: SqdRecoveryTileProps) {
  const recoverySteps = useMemo(() => getRecoverySteps(metrics), [metrics]);
  const artifacts = metrics.circuit_artifacts;
  const defaultArtifactId = getDefaultArtifactId(artifacts);
  const [selectedArtifactId, setSelectedArtifactId] = useState<string | null>(defaultArtifactId);

  useEffect(() => {
    setSelectedArtifactId(defaultArtifactId);
  }, [defaultArtifactId]);

  const selectedArtifact = getSelectedArtifact(artifacts, selectedArtifactId);
  const selectedIteration = selectedArtifact?.iteration ?? null;
  const latest =
    recoverySteps.find((entry) => getNumber(entry["iteration"]) === selectedIteration) ??
    latestRecovery(metrics);
  const bitstrings = extractBitstrings(metrics);
  const stats = buildRecoveryStats(latest, metrics);
  const subsamplingSummary = buildSubsamplingSummary(metrics.subsampling_summary);

  return (
    <DashboardTile
      title="SQD Recovery"
      helpText="Self-consistent recovery diagnostics, dominant sampled outcomes, and the stored SQD recovery circuit for the selected iteration."
      editMode={editMode}
    >
      <div className="grid h-full min-h-[24rem] gap-3 lg:min-h-[28rem] lg:grid-cols-[minmax(0,1fr)_12rem]">
        <div className="min-h-0">
          {bitstrings.length > 0 || selectedArtifact ? (
            <MeasurementOutcomesPanel
              outcomes={bitstrings}
              artifacts={selectedArtifact ? [selectedArtifact] : []}
              stateKey="sqd-recovery"
              emptyMessage="No SQD recovery artifacts recorded"
            />
          ) : (
            <ChartEmptyState
              message="No SQD recovery artifacts recorded"
              pending={isRunning}
              pendingMessage="Awaiting SQD recovery artifacts"
            />
          )}
        </div>
        <div className="flex min-h-0 flex-col gap-2 overflow-auto">
          <RecoveryIterationSelector
            artifacts={artifacts}
            selectedArtifactId={selectedArtifactId}
            onValueChange={setSelectedArtifactId}
          />
          <RecoveryStatsGrid stats={stats} />
          <RecoveryFooter
            subsamplingSummary={subsamplingSummary}
            artifactCount={artifacts.length}
            selectedIteration={selectedIteration}
          />
        </div>
      </div>
    </DashboardTile>
  );
}
