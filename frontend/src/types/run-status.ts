/**
 * Scalar run identifiers, enums, and JSON helper types.
 */

import type {
  ApiBackendTarget,
  ApiEasyGoal,
  ApiRunAlgorithm,
  ApiRunEventType,
  ApiRunMode,
  ApiRunStatus,
  ApiValidationErrorCode,
} from "./api";

/**
 * UUID type - string in UUID format (RFC 4122)
 */
declare const uuidBrand: unique symbol;
export type UUID = string & { readonly [uuidBrand]?: never };

/**
 * Run status enum - matches backend RunStatus
 */
export type RunStatus = ApiRunStatus;

export const RUN_STATUSES = [
  "CREATED",
  "QUEUED",
  "RUNNING",
  "PAUSING",
  "PAUSED",
  "SUBMITTED_TO_IBM",
  "COMPLETED",
  "FAILED",
  "CANCELLED",
  "EXCLUDED",
] as const satisfies readonly RunStatus[];

export function isRunStatus(value: unknown): value is RunStatus {
  return typeof value === "string" && RUN_STATUSES.includes(value as RunStatus);
}

/**
 * Run algorithm enum - matches backend RunAlgorithm
 */
export type RunAlgorithm = ApiRunAlgorithm;

export const RUN_ALGORITHMS = [
  "vqe",
  "qse",
  "kqd",
  "qfd",
  "sqd",
  "skqd",
] as const satisfies readonly RunAlgorithm[];

export function isRunAlgorithm(value: unknown): value is RunAlgorithm {
  return typeof value === "string" && RUN_ALGORITHMS.includes(value as RunAlgorithm);
}

export const BACKEND_TARGETS = [
  "statevector",
  "aer_simulator",
  "ibm_runtime",
] as const satisfies readonly BackendTarget[];

export function isBackendTarget(value: unknown): value is BackendTarget {
  return typeof value === "string" && BACKEND_TARGETS.includes(value as BackendTarget);
}

/**
 * Run mode enum - matches backend RunMode
 */
export type RunMode = ApiRunMode;

/**
 * Backend target enum - matches backend BackendTarget
 */
export type BackendTarget = ApiBackendTarget;

/**
 * Easy-mode goal tiers.
 */
export type EasyGoal = ApiEasyGoal;

export const EASY_GOALS = [
  "fastest",
  "balanced",
  "best_accuracy",
] as const satisfies readonly EasyGoal[];

/**
 * Validation error codes - matches backend ValidationErrorCode.
 */
export type ValidationErrorCode = ApiValidationErrorCode;

/**
 * Run event type enum - matches backend RunEventType
 */
export type RunEventType = ApiRunEventType;

export const RUN_EVENT_TYPES = [
  "status_changed",
  "iteration_update",
  "estimate_updated",
  "control_requested",
  "checkpoint_saved",
  "resume_enqueued",
  "restart_created",
  "error",
  "result",
  "ibm_job_submitted",
  "ibm_status_poll",
] as const satisfies readonly RunEventType[];

export function isRunEventType(value: unknown): value is RunEventType {
  return typeof value === "string" && RUN_EVENT_TYPES.includes(value as RunEventType);
}

export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonValue[] | JsonObject;

export interface JsonObject {
  [key: string]: JsonValue | undefined;
}
