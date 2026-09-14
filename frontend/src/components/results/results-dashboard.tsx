import { useMemo } from "react";
import { RotateCcw, Edit2, Lock } from "lucide-react";
import type { LayoutItem } from "react-grid-layout";
import { Button } from "@/components/ui/button";
import { DashboardGrid } from "./dashboard-grid";
import { SummaryTile } from "./tiles/summary-tile";
import { ConvergenceTile } from "./tiles/convergence-tile";
import { BenchmarkBarsTile } from "./tiles/benchmark-bars-tile";
import { HardwareMappingTile } from "./tiles/hardware-mapping-tile";
import { VqeParametersTile } from "./tiles/vqe-parameters-tile";
import { CircuitArtifactsTile } from "./tiles/circuit-artifacts-tile";
import { SqdOccupancyTile } from "./tiles/sqd-occupancy-tile";
import { SqdRecoveryTile } from "./tiles/sqd-recovery-tile";
import { KqdRitzTile } from "./tiles/kqd-ritz-tile";
import { QfdSpectrumTile } from "./tiles/qfd-spectrum-tile";
import { QseSubspaceTile } from "./tiles/qse-subspace-tile";
import { SpectralGapsTile } from "./tiles/spectral-gaps-tile";
import { SkqdDiagnosticsTile } from "./tiles/skqd-diagnostics-tile";
import { SkqdSpectrumTile } from "./tiles/skqd-spectrum-tile";
import { ExportDropdown } from "./tiles/export-tile";
import { TimelineTile } from "./tiles/timeline-tile";
import { useDashboardLayout } from "@/hooks/use-dashboard-layout";
import { buildResultsDashboardModel } from "./results-dashboard-model";
import type {
  RunResponse,
  RunResultResponse,
  RunEventResponse,
  MoleculeResponse,
} from "@/types/run";

interface ResultsDashboardProps {
  readonly run: RunResponse;
  readonly result: RunResultResponse | null;
  readonly events: RunEventResponse[];
  readonly molecule: MoleculeResponse | null;
  readonly moleculePending?: boolean;
  readonly isRunning?: boolean;
  readonly activityLabel?: string | null;
  readonly sseDisconnected?: boolean;
  readonly eventsPending?: boolean;
  readonly resultPending?: boolean;
}

export function ResultsDashboard({
  run,
  result,
  events,
  molecule,
  moleculePending = false,
  isRunning = false,
  activityLabel = null,
  sseDisconnected = false,
  eventsPending = false,
  resultPending = false,
}: ResultsDashboardProps) {
  const algorithm = run.algorithm ?? "unknown";
  const layoutVariant = run.backend_target === "ibm_runtime" ? "ibm-runtime" : "default";
  const { layout, layoutRevision, setLayout, resetLayout, editMode, setEditMode } =
    useDashboardLayout(algorithm, layoutVariant);
  const model = useMemo(
    () =>
      buildResultsDashboardModel({
        run,
        result,
        events,
        layout,
        moleculePending,
        eventsPending,
        resultPending,
      }),
    [run, result, events, layout, moleculePending, eventsPending, resultPending],
  );
  const {
    execution,
    parsed,
    currentIteration,
    currentEnergy,
    liveBestEnergy,
    refs,
    runtimeSeconds,
    chemicalAccuracyHa,
    visibleTileIds,
    visibleLayout,
    hiddenLayout,
    activeTiles,
    pending,
  } = model;
  const visibleTileKey = visibleTileIds.join(",");

  function handleVisibleLayoutChange(nextVisibleLayout: LayoutItem[]) {
    setLayout([...nextVisibleLayout, ...hiddenLayout]);
  }

  return (
    <div className="flex flex-col gap-4" data-results-dashboard-root="">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-end gap-2">
        <div>
          <ExportDropdown run={run} result={result} events={events} />
        </div>
        <Button
          variant={editMode ? "default" : "outline"}
          size="sm"
          className="h-8 gap-1.5 text-xs"
          onClick={() => setEditMode(!editMode)}
          aria-label={editMode ? "Lock layout" : "Edit layout"}
        >
          {editMode ? <Lock className="size-3.5" /> : <Edit2 className="size-3.5" />}
          {editMode ? "Lock" : "Edit layout"}
        </Button>
        {editMode ? (
          <Button
            variant="ghost"
            size="sm"
            className="h-8 gap-1.5 text-xs text-muted-foreground"
            onClick={resetLayout}
            aria-label="Reset layout"
          >
            <RotateCcw className="size-3.5" />
            Reset
          </Button>
        ) : null}
      </div>

      {/* Grid */}
      <DashboardGrid
        layout={visibleLayout}
        layoutKey={`${algorithm}:${layoutRevision}:${visibleTileKey}`}
        onLayoutChange={handleVisibleLayoutChange}
        editMode={editMode}
      >
        {activeTiles.has("summary") && (
          <div key="summary">
            <SummaryTile
              run={run}
              result={result}
              events={events}
              molecule={molecule}
              currentIteration={currentIteration}
              currentEnergy={currentEnergy}
              liveBestEnergy={liveBestEnergy}
              runtimeSeconds={runtimeSeconds}
              hfEnergy={refs.hf}
              fciEnergy={refs.fci}
              chemicalAccuracyHa={chemicalAccuracyHa}
              isRunning={isRunning}
              pending={pending.summary}
              editMode={editMode}
            />
          </div>
        )}

        {activeTiles.has("convergence") && (
          <div key="convergence">
            <ConvergenceTile
              events={events}
              result={result}
              algorithm={run.algorithm ?? undefined}
              hfEnergy={refs.hf}
              fciEnergy={refs.fci}
              chemicalAccuracyHa={chemicalAccuracyHa}
              isRunning={isRunning}
              pending={pending.convergence}
              editMode={editMode}
            />
          </div>
        )}

        {activeTiles.has("hardware-mapping") && (
          <div key="hardware-mapping">
            <HardwareMappingTile
              execution={execution}
              credentialProfileId={run.credential_profile_id ?? null}
              editMode={editMode}
            />
          </div>
        )}

        {activeTiles.has("timeline") && (
          <div key="timeline">
            <TimelineTile
              events={events}
              algorithm={run.algorithm ?? undefined}
              isRunning={isRunning || activityLabel !== null}
              activityLabel={activityLabel}
              sseDisconnected={sseDisconnected}
              pending={pending.timeline}
              editMode={editMode}
            />
          </div>
        )}

        {activeTiles.has("benchmark-bars") && (
          <div key="benchmark-bars">
            <BenchmarkBarsTile
              result={result}
              liveBestEnergy={liveBestEnergy}
              hfEnergy={refs.hf}
              fciEnergy={refs.fci}
              chemicalAccuracyHa={chemicalAccuracyHa}
              algorithm={run.algorithm ?? undefined}
              isRunning={isRunning}
              pending={pending.benchmark}
              editMode={editMode}
            />
          </div>
        )}

        {parsed.type === "vqe" && activeTiles.has("vqe-circuit") && (
          <div key="vqe-circuit">
            <VqeParametersTile
              metrics={parsed.metrics}
              isRunning={isRunning || resultPending}
              editMode={editMode}
            />
          </div>
        )}

        {parsed.type === "sqd" && activeTiles.has("sqd-occupancy") && (
          <div key="sqd-occupancy">
            <SqdOccupancyTile
              metrics={parsed.metrics}
              isRunning={isRunning || resultPending}
              editMode={editMode}
            />
          </div>
        )}

        {parsed.type === "sqd" && activeTiles.has("sqd-recovery") && (
          <div key="sqd-recovery">
            <SqdRecoveryTile
              metrics={parsed.metrics}
              isRunning={isRunning || resultPending}
              editMode={editMode}
            />
          </div>
        )}

        {parsed.type === "kqd" && activeTiles.has("kqd-ritz") && (
          <div key="kqd-ritz">
            <KqdRitzTile
              metrics={parsed.metrics}
              isRunning={isRunning || resultPending}
              editMode={editMode}
            />
          </div>
        )}

        {parsed.type === "kqd" && activeTiles.has("kqd-circuit") && (
          <div key="kqd-circuit">
            <CircuitArtifactsTile
              title="KQD Circuit"
              helpText="Reference and time-evolution circuit artifacts recorded for the KQD solve."
              artifacts={parsed.metrics.circuit_artifacts}
              stateKey="kqd-associated-circuit"
              emptyMessage="No KQD circuit recorded"
              pendingMessage="Awaiting KQD circuit artifacts"
              isRunning={isRunning || resultPending}
              editMode={editMode}
            />
          </div>
        )}

        {parsed.type === "kqd" && activeTiles.has("spectral-gaps") && (
          <div key="spectral-gaps">
            <SpectralGapsTile
              title="KQD Excitation Gaps"
              energies={parsed.metrics.ritz_values}
              isRunning={isRunning || resultPending}
              editMode={editMode}
            />
          </div>
        )}

        {parsed.type === "qfd" && activeTiles.has("qfd-spectrum") && (
          <div key="qfd-spectrum">
            <QfdSpectrumTile
              metrics={parsed.metrics}
              isRunning={isRunning || resultPending}
              editMode={editMode}
            />
          </div>
        )}

        {parsed.type === "qfd" && activeTiles.has("spectral-gaps") && (
          <div key="spectral-gaps">
            <SpectralGapsTile
              title="QFD Excitation Gaps"
              energies={parsed.metrics.filter_eigenvalues}
              isRunning={isRunning || resultPending}
              editMode={editMode}
            />
          </div>
        )}

        {parsed.type === "qse" && activeTiles.has("qse-subspace") && (
          <div key="qse-subspace">
            <QseSubspaceTile
              metrics={parsed.metrics}
              isRunning={isRunning || resultPending}
              editMode={editMode}
            />
          </div>
        )}

        {parsed.type === "qse" && activeTiles.has("qse-circuit") && (
          <div key="qse-circuit">
            <CircuitArtifactsTile
              title="QSE Reference Circuit"
              helpText="The state-preparation circuit used to build the QSE reference state."
              artifacts={parsed.metrics.circuit_artifacts}
              stateKey="qse-reference-circuit"
              emptyMessage="No reference circuit recorded"
              pendingMessage="Awaiting QSE reference circuit"
              isRunning={isRunning || resultPending}
              editMode={editMode}
            />
          </div>
        )}

        {parsed.type === "qse" && activeTiles.has("spectral-gaps") && (
          <div key="spectral-gaps">
            <SpectralGapsTile
              title="QSE Excitation Gaps"
              energies={parsed.metrics.eigenvalues}
              isRunning={isRunning || resultPending}
              editMode={editMode}
            />
          </div>
        )}

        {parsed.type === "skqd" && activeTiles.has("skqd-diagnostics") && (
          <div key="skqd-diagnostics">
            <SkqdDiagnosticsTile metrics={parsed.metrics} editMode={editMode} />
          </div>
        )}

        {parsed.type === "skqd" && activeTiles.has("skqd-circuit") && (
          <div key="skqd-circuit">
            <CircuitArtifactsTile
              title="SKQD Seed Circuit"
              helpText="The SQD seed circuit artifact that feeds the Krylov extension workflow."
              artifacts={parsed.metrics.circuit_artifacts}
              stateKey="skqd-seed-circuit"
              emptyMessage="No SKQD seed circuit recorded"
              pendingMessage="Awaiting SKQD seed circuit"
              isRunning={isRunning || resultPending}
              editMode={editMode}
            />
          </div>
        )}

        {parsed.type === "skqd" && activeTiles.has("skqd-spectrum") && (
          <div key="skqd-spectrum">
            <SkqdSpectrumTile
              metrics={parsed.metrics}
              isRunning={isRunning || resultPending}
              editMode={editMode}
            />
          </div>
        )}

        {parsed.type === "skqd" && activeTiles.has("spectral-gaps") && (
          <div key="spectral-gaps">
            <SpectralGapsTile
              title="SKQD Excitation Gaps"
              energies={model.skqdSpectrumEnergies}
              isRunning={isRunning || pending.algorithm}
              editMode={editMode}
            />
          </div>
        )}
      </DashboardGrid>
    </div>
  );
}
