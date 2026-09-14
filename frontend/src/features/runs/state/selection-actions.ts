import type { cancelRun, pauseRun, restartRun, resumeRun } from "@/api/runs";
import { getErrorMessage } from "@/lib/error-handler";
import type { RunStatus, RunSummaryResponse, UUID } from "@/types/run";
import type { RunRowAction } from "../components/runs-list-row";

export type BulkRunAction = RunRowAction | "delete" | null;
export type ConfirmableRunAction = Extract<RunRowAction, "pause" | "restart" | "cancel">;
export type RunSummaryOverride = Partial<Pick<RunSummaryResponse, "status" | "updated_at">>;
export type RunActionResponse =
  | Awaited<ReturnType<typeof pauseRun>>
  | Awaited<ReturnType<typeof resumeRun>>
  | Awaited<ReturnType<typeof restartRun>>
  | Awaited<ReturnType<typeof cancelRun>>;
export type RunDeleteProgress = { completed: number; total: number };

export const ROW_ACTION_LABELS: Record<RunRowAction, string> = {
  pause: "pause",
  resume: "resume",
  restart: "restart",
  cancel: "cancel",
};

export function runStatusOverride(
  run: RunSummaryResponse,
  action: RunRowAction,
  response: {
    status?: RunStatus;
    child_run_id?: UUID | null;
    new_run_id?: UUID | null;
    target_run_id?: UUID | null;
  },
): RunSummaryOverride {
  if (action === "restart") {
    const restartedToAnotherRun =
      (response.child_run_id != null && response.child_run_id !== run.id) ||
      (response.new_run_id != null && response.new_run_id !== run.id) ||
      (response.target_run_id != null && response.target_run_id !== run.id);

    return {
      status: restartedToAnotherRun ? "QUEUED" : (response.status ?? "QUEUED"),
      updated_at: new Date().toISOString(),
    };
  }

  return {
    status: response.status ?? run.status,
    updated_at: new Date().toISOString(),
  };
}

export function describeRunSelectionAction(
  action: ConfirmableRunAction,
  eligibleCount: number,
  skippedCount: number,
) {
  const runLabel = eligibleCount === 1 ? "run" : "runs";
  const skippedLabel = skippedCount === 1 ? "run is" : "runs are";

  switch (action) {
    case "pause":
      return skippedCount > 0
        ? `This will pause ${eligibleCount} selected ${runLabel}. ${skippedCount} selected ${skippedLabel} not pausable and will be skipped.`
        : `This will pause ${eligibleCount} selected ${runLabel}. IBM Runtime jobs already submitted will finish before the run pauses.`;
    case "restart":
      return skippedCount > 0
        ? `This will restart ${eligibleCount} selected ${runLabel}. ${skippedCount} selected ${skippedLabel} not restartable and will be skipped.`
        : `This will create new runs from the stored configurations for ${eligibleCount} selected ${runLabel}.`;
    case "cancel":
      return skippedCount > 0
        ? `This will cancel ${eligibleCount} selected ${runLabel}. ${skippedCount} selected ${skippedLabel} already terminal and will be skipped.`
        : `This will cancel ${eligibleCount} selected ${runLabel}. This action cannot be undone.`;
  }
}

export function buildBulkActionErrorSummary(
  action: RunRowAction,
  results: PromiseSettledResult<{ run: RunSummaryResponse; response: RunActionResponse }>[],
): string | null {
  const failures = results.filter(
    (result): result is PromiseRejectedResult => result.status === "rejected",
  );
  if (failures.length === 0) {
    return null;
  }

  const firstFailure = failures[0];
  if (!firstFailure) {
    return null;
  }
  const succeededCount = results.length - failures.length;
  const firstError = getErrorMessage(
    firstFailure.reason,
    `Failed to ${action} ${failures.length === 1 ? "run" : "runs"}.`,
  );
  if (succeededCount === 0) {
    return firstError;
  }

  const actionLabel = {
    pause: "Paused",
    resume: "Resumed",
    restart: "Restarted",
    cancel: "Cancelled",
  }[action];
  const runLabel = succeededCount === 1 ? "run" : "runs";
  return `${actionLabel} ${succeededCount} ${runLabel}, ${failures.length} failed. ${firstError}`;
}

export function buildDeleteRunsErrorSummary(
  results: PromiseSettledResult<string>[],
  failedIds: string[],
): string {
  const firstError = getErrorMessage(
    results.find((result) => result.status === "rejected")?.reason,
    "Failed to delete runs.",
  );
  if (failedIds.length === 0) {
    return firstError;
  }

  const deletedCount = results.length - failedIds.length;
  if (deletedCount === 0) {
    return firstError;
  }

  const runLabel = deletedCount === 1 ? "run" : "runs";
  return `Deleted ${deletedCount} ${runLabel}, ${failedIds.length} failed. ${firstError}`;
}

export function getSelectionActionLabel(action: string, count: number): string {
  return count > 0 ? `${action} (${count})` : action;
}

export function getRunsEditButtonLabel(isEditing: boolean): string {
  return isEditing ? "Done Editing" : "Edit";
}

export function getDeleteRunsTitle(selectedCount: number): string {
  return selectedCount === 1 ? "Delete selected run?" : `Delete ${selectedCount} selected runs?`;
}

export function getDeleteRunsDescription(cancellableCount: number): string {
  if (cancellableCount > 0) {
    return "This permanently removes the selected runs from history. Any queued, running, paused, or IBM-submitted work in the selection is cancelled before removal.";
  }

  return "This permanently removes the selected runs from history.";
}

export function getDeleteRunsStatus(progress: RunDeleteProgress | null): string | undefined {
  if (!progress) {
    return undefined;
  }

  return `Deleting ${progress.completed} of ${progress.total}...`;
}

export function getDeleteRunsConfirmText(selectedCount: number): string {
  return selectedCount === 1 ? "Delete run" : "Delete runs";
}
