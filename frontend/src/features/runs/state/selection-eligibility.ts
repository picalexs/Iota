import type { RunSummaryResponse, UUID } from "@/types/run";

const PAUSABLE_STATUSES = new Set<RunSummaryResponse["status"]>([
  "CREATED",
  "QUEUED",
  "RUNNING",
  "SUBMITTED_TO_IBM",
]);
const RESUMABLE_STATUSES = new Set<RunSummaryResponse["status"]>(["PAUSED", "FAILED"]);
const RESTARTABLE_STATUSES = new Set<RunSummaryResponse["status"]>([
  "COMPLETED",
  "FAILED",
  "CANCELLED",
  "EXCLUDED",
  "PAUSED",
]);
const CANCELLABLE_STATUSES = new Set<RunSummaryResponse["status"]>([
  "CREATED",
  "RUNNING",
  "QUEUED",
  "PAUSING",
  "PAUSED",
  "SUBMITTED_TO_IBM",
]);

export interface RunSelectionEligibility {
  readonly selectedRuns: RunSummaryResponse[];
  readonly pausableSelectedRuns: RunSummaryResponse[];
  readonly resumableSelectedRuns: RunSummaryResponse[];
  readonly restartableSelectedRuns: RunSummaryResponse[];
  readonly cancellableSelectedRuns: RunSummaryResponse[];
}

export function getRunSelectionEligibility(
  runs: readonly RunSummaryResponse[],
  selectedRunIds: ReadonlySet<UUID>,
): RunSelectionEligibility {
  const selectedRuns = runs.filter((run) => selectedRunIds.has(run.id));

  return {
    selectedRuns,
    pausableSelectedRuns: selectedRuns.filter((run) => PAUSABLE_STATUSES.has(run.status)),
    resumableSelectedRuns: selectedRuns.filter((run) => RESUMABLE_STATUSES.has(run.status)),
    restartableSelectedRuns: selectedRuns.filter((run) => RESTARTABLE_STATUSES.has(run.status)),
    cancellableSelectedRuns: selectedRuns.filter((run) => CANCELLABLE_STATUSES.has(run.status)),
  };
}
