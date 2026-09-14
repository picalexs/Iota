import { DashboardTile } from "@/components/results/dashboard-tile";
import { formatDuration } from "@/lib/format-duration";
import type { RunResponse, RunResultResponse } from "@/types/run";

interface ResourcesTileProps {
  readonly run: RunResponse;
  readonly result: RunResultResponse;
  readonly editMode?: boolean;
}

interface StatRowProps {
  readonly label: string;
  readonly value: React.ReactNode;
}

function safePrimitiveLabel(value: unknown): string | null {
  return ["string", "number", "boolean"].includes(typeof value) ? String(value) : null;
}

function StatRow({ label, value }: StatRowProps) {
  return (
    <div className="flex items-baseline justify-between gap-2 border-b border-border/40 py-1.5 last:border-0">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-xs font-medium tabular-nums">{value}</span>
    </div>
  );
}

export function ResourcesTile({ run, result, editMode }: ResourcesTileProps) {
  const createdAt = new Date(run.created_at);
  const updatedAt = new Date(run.updated_at);
  const totalWall = (updatedAt.getTime() - createdAt.getTime()) / 1000;

  const metadata = run.metadata;
  const numQubits = metadata?.["num_qubits"];
  const circuitDepth = metadata?.["circuit_depth"];
  const numQubitsLabel = safePrimitiveLabel(numQubits);
  const circuitDepthLabel = safePrimitiveLabel(circuitDepth);

  return (
    <DashboardTile
      title="Resources"
      helpText="Runtime breakdown and circuit resource counts for this run."
      editMode={editMode}
    >
      <div className="flex flex-col">
        <StatRow label="Wall time" value={formatDuration(totalWall)} />
        <StatRow label="Backend" value={run.backend_target ?? "—"} />
        {numQubitsLabel !== null && <StatRow label="Qubits" value={numQubitsLabel} />}
        {circuitDepthLabel !== null && <StatRow label="Circuit depth" value={circuitDepthLabel} />}
        <StatRow label="Iterations" value={result.iterations} />
        {run.ibm_job_id && (
          <StatRow
            label="IBM job ID"
            value={<code className="font-mono text-[10px] break-all">{run.ibm_job_id}</code>}
          />
        )}
      </div>
    </DashboardTile>
  );
}
