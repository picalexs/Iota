import { toast } from "sonner";

export interface ApiErrorLike {
  code?: string;
  field?: string;
  message: string;
  name?: string;
  status?: number;
}

interface ToastMessageOptions {
  description?: string | null;
  fallbackDescription?: string;
  title: string;
}

const API_UNAVAILABLE_ERROR_PATTERNS = [
  "Unable to reach the API",
  "Failed to fetch",
  "NetworkError",
  "Load failed",
] as const;

const API_UNAVAILABLE_TOAST_ID = "api-unavailable";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function isApiErrorLike(error: unknown): error is ApiErrorLike {
  if (!isRecord(error)) return false;
  return (
    typeof error.message === "string" &&
    (error.name === undefined || typeof error.name === "string") &&
    (error.status === undefined || typeof error.status === "number") &&
    (error.code === undefined || typeof error.code === "string") &&
    (error.field === undefined || typeof error.field === "string") &&
    (typeof error.status === "number" ||
      typeof error.code === "string" ||
      typeof error.field === "string" ||
      error.name === "ApiError")
  );
}

export function getErrorMessage(error: unknown, fallback = "An unexpected error occurred") {
  if (isApiErrorLike(error) && error.message.trim().length > 0) {
    return error.message;
  }

  if (error instanceof Error && error.message.trim().length > 0) {
    return error.message;
  }

  if (typeof error === "string" && error.trim().length > 0) {
    return error;
  }

  return fallback;
}

export function getApiErrorMessage(error: unknown, fallback: string) {
  if (isApiErrorLike(error) && error.message.trim().length > 0) {
    return error.message;
  }

  return fallback;
}

export function isApiUnavailableError(error: unknown): boolean {
  if (isApiErrorLike(error) && error.status != null && [502, 503, 504].includes(error.status)) {
    return true;
  }

  const message = getErrorMessage(error, "");
  return (
    message.length > 0 &&
    API_UNAVAILABLE_ERROR_PATTERNS.some((pattern) => message.includes(pattern))
  );
}

export function showErrorToast(error: unknown, options: ToastMessageOptions) {
  if (isApiUnavailableError(error)) {
    toast.error("The API is unavailable right now", {
      id: API_UNAVAILABLE_TOAST_ID,
      description:
        "The frontend is still running, but live data and actions will stay unavailable until the backend responds again.",
    });
    return;
  }

  if (options.description === null) {
    toast.error(options.title);
    return;
  }

  const description = options.description ?? getErrorMessage(error, options.fallbackDescription);

  toast.error(options.title, { description });
}
