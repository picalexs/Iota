import { DashboardTile } from "@/components/results/dashboard-tile";
import { MeasurementOutcomesPanel } from "@/components/results/measurement-outcomes-panel";
import { ChartEmptyState } from "@/components/results/charts/chart-empty-state";
import type { VqeMetrics } from "@/lib/results/parse-algorithm-metrics";
import type { CircuitArtifact } from "@/types/run";

interface VqeParametersTileProps {
  readonly metrics: VqeMetrics;
  readonly isRunning?: boolean;
  readonly editMode?: boolean;
}

function artifactLabel(artifact: CircuitArtifact): string {
  switch (artifact.role) {
    case "ansatz":
      return "Ansatz";
    case "final":
      return artifact.label ?? "Reported";
    case "optimizer_final":
      return artifact.label ?? "Final";
    default:
      return artifact.label ?? "Circuit";
  }
}

export function VqeParametersTile({
  metrics,
  isRunning = false,
  editMode,
}: VqeParametersTileProps) {
  const artifacts = metrics.circuit_artifacts;

  return (
    <DashboardTile
      title="VQE Circuit"
      helpText="Logical ansatz plus the reported VQE circuit; when the optimizer's last point differs from the best observed point, the final optimizer circuit is kept as a separate artifact."
      editMode={editMode}
    >
      <div className="h-full min-h-0">
        {artifacts.length > 0 ? (
          <MeasurementOutcomesPanel
            outcomes={[]}
            artifacts={artifacts}
            stateKey="vqe-circuit"
            artifactSelectorLabel="View"
            artifactLabelFormatter={artifactLabel}
            emptyMessage="No VQE circuit artifacts recorded"
          />
        ) : (
          <ChartEmptyState
            message="No VQE circuit artifacts recorded"
            pending={isRunning}
            pendingMessage="Awaiting VQE circuit artifacts"
          />
        )}
      </div>
    </DashboardTile>
  );
}
