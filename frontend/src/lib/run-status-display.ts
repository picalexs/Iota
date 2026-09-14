import type { RunStatus } from "@/types/run";

type NullableRunStatus = RunStatus | null | undefined;

const STREAMING_STATUSES = new Set<RunStatus>([
  "CREATED",
  "QUEUED",
  "RUNNING",
  "PAUSING",
  "SUBMITTED_TO_IBM",
]);

const EXECUTING_STATUSES = new Set<RunStatus>(["RUNNING", "PAUSING", "SUBMITTED_TO_IBM"]);

export function isRunStreaming(status: NullableRunStatus): boolean {
  return status != null && STREAMING_STATUSES.has(status);
}

export function isRunExecuting(status: NullableRunStatus): boolean {
  return status != null && EXECUTING_STATUSES.has(status);
}

export function getRunProgressLabel(status: NullableRunStatus): string {
  switch (status) {
    case "CREATED":
      return "Pending";
    case "QUEUED":
      return "Queued";
    case "RUNNING":
      return "Running";
    case "PAUSING":
      return "Pausing";
    case "SUBMITTED_TO_IBM":
      return "IBM pending";
    default:
      return "—";
  }
}

export function getRunActivityLabel(
  status: NullableRunStatus,
  disconnected = false,
): string | null {
  if (status == null || !isRunStreaming(status)) {
    return null;
  }

  if (status === "QUEUED") {
    return "Queued";
  }

  if (status === "CREATED") {
    return "Pending";
  }

  return disconnected ? "Refreshing" : "Live";
}
