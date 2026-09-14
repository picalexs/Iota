import { formatDuration } from "./format-duration";

export const GENERIC_WORKER_FAILURE_MESSAGE =
  "Run execution failed. Check worker logs for details.";
export const WORKER_TIMEOUT_ERROR_CODE = "worker_job_timed_out";

const TIMEOUT_ERROR_TYPES = new Set(["JobTimeoutException"]);
const WORKER_TIMEOUT_MESSAGE_PATTERN = /Task exceeded maximum timeout value/i;
const USER_TIMEOUT_MESSAGE_PATTERN = /^Run timed out after /i;

function trimmedString(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function finiteNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) && value > 0 ? value : null;
}

function errorTextCandidates(payload: Record<string, unknown>): string[] {
  return [
    payload.summary,
    payload.message,
    payload.error_message,
    payload.detail,
    payload.error_detail,
    payload.reason,
    payload.error,
    payload.stack,
  ]
    .map(trimmedString)
    .filter((value): value is string => value !== null);
}

export function formatRunTimedOutMessage(timeoutSeconds?: number | null): string {
  const normalizedTimeoutSeconds =
    typeof timeoutSeconds === "number" && Number.isFinite(timeoutSeconds) && timeoutSeconds > 0
      ? timeoutSeconds
      : null;

  if (normalizedTimeoutSeconds === null) {
    return "Run timed out after reaching the execution time limit.";
  }

  return `Run timed out after reaching the ${formatDuration(normalizedTimeoutSeconds)} execution limit.`;
}

export function isTimedOutFailurePayload(
  payload: Record<string, unknown> | null | undefined,
): boolean {
  if (!payload) return false;

  const errorCode = trimmedString(payload.error_code);
  if (errorCode === WORKER_TIMEOUT_ERROR_CODE) {
    return true;
  }

  const errorType = trimmedString(payload.error_type);
  if (errorType !== null && TIMEOUT_ERROR_TYPES.has(errorType)) {
    return true;
  }

  return errorTextCandidates(payload).some(
    (value) =>
      USER_TIMEOUT_MESSAGE_PATTERN.test(value) || WORKER_TIMEOUT_MESSAGE_PATTERN.test(value),
  );
}

export function getTimedOutFailureMessage(
  payload: Record<string, unknown> | null | undefined,
): string | null {
  if (!isTimedOutFailurePayload(payload)) {
    return null;
  }

  return formatRunTimedOutMessage(finiteNumber(payload?.timeout_seconds));
}

export function isTimedOutFailureMessage(message: string | null | undefined): boolean {
  const normalized = trimmedString(message);
  if (normalized === null) {
    return false;
  }

  return (
    USER_TIMEOUT_MESSAGE_PATTERN.test(normalized) || WORKER_TIMEOUT_MESSAGE_PATTERN.test(normalized)
  );
}
