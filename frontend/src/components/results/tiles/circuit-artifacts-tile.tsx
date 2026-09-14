import { DashboardTile } from "@/components/results/dashboard-tile";
import { MeasurementOutcomesPanel } from "@/components/results/measurement-outcomes-panel";
import { ChartEmptyState } from "@/components/results/charts/chart-empty-state";
import type { CircuitArtifact } from "@/types/run";

interface CircuitArtifactsTileProps {
  readonly title: string;
  readonly helpText: string;
  readonly artifacts: CircuitArtifact[];
  readonly stateKey: string;
  readonly emptyMessage: string;
  readonly pendingMessage: string;
  readonly isRunning?: boolean;
  readonly editMode?: boolean;
}

export function CircuitArtifactsTile({
  title,
  helpText,
  artifacts,
  stateKey,
  emptyMessage,
  pendingMessage,
  isRunning = false,
  editMode,
}: CircuitArtifactsTileProps) {
  return (
    <DashboardTile title={title} helpText={helpText} editMode={editMode}>
      <div className="h-full min-h-0">
        {artifacts.length > 0 ? (
          <MeasurementOutcomesPanel
            outcomes={[]}
            artifacts={artifacts}
            stateKey={stateKey}
            emptyMessage={emptyMessage}
          />
        ) : (
          <ChartEmptyState
            message={emptyMessage}
            pending={isRunning}
            pendingMessage={pendingMessage}
          />
        )}
      </div>
    </DashboardTile>
  );
}
