export const API_BASE = normalizeApiBase(import.meta.env.VITE_API_URL);

export function trimTrailingSlashes(value: string): string {
  let end = value.length;
  while (end > 0 && value.codePointAt(end - 1) === 47) {
    end -= 1;
  }
  return value.slice(0, end);
}

function normalizeApiBase(value: string | undefined): string {
  if (value === undefined || value === "") {
    return "";
  }

  return trimTrailingSlashes(value);
}

export function operatorProtectedApiUrl(path: string): string {
  return path;
}

export class ApiError extends Error {
  code: string;
  status: number;
  field?: string;
  method?: string;
  url?: string;
  statusText?: string;
  cause?: unknown;

  constructor(
    code: string,
    message: string,
    status: number,
    field?: string,
    context?: {
      method?: string;
      url?: string;
      statusText?: string;
      cause?: unknown;
    },
  ) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.field = field;
    if (context?.method) {
      this.method = context.method;
    }
    if (context?.url) {
      this.url = context.url;
    }
    if (context?.statusText) {
      this.statusText = context.statusText;
    }
    if (context?.cause !== undefined) {
      this.cause = context.cause;
    }
    Object.setPrototypeOf(this, ApiError.prototype);
  }
}

type ApiErrorData = { code?: string; message?: string; field?: string };
const DEFAULT_API_ERROR_MESSAGE = "An unexpected error occurred";
const DEFAULT_NETWORK_ERROR_MESSAGE = "Unable to reach the API. Please try again.";
const DEFAULT_INVALID_RESPONSE_MESSAGE = "The server returned an invalid response.";

export function invalidApiResponse(message: string): ApiError {
  return new ApiError("INVALID_RESPONSE", message, 0);
}

function parseValidationErrorDetail(detail: unknown[]): ApiErrorData {
  const first = isRecord(detail[0]) ? detail[0] : undefined;
  const loc = first?.loc;

  return {
    code: typeof first?.type === "string" ? first.type : "VALIDATION_ERROR",
    message: typeof first?.msg === "string" ? first.msg : "Request validation failed",
    field: Array.isArray(loc) ? loc.slice(1).join(".") : undefined,
  };
}

function parseApiErrorDetail(detail: Record<string, unknown>): ApiErrorData {
  return {
    code: typeof detail.code === "string" ? detail.code : undefined,
    message: typeof detail.message === "string" ? detail.message : undefined,
    field: typeof detail.field === "string" ? detail.field : undefined,
  };
}

function parseApiErrorData(json: unknown): ApiErrorData {
  if (!isRecord(json)) {
    return {};
  }

  if (typeof json.message === "string") {
    return { message: json.message };
  }

  if (!("detail" in json)) {
    return {};
  }

  const { detail } = json;
  if (Array.isArray(detail)) {
    return parseValidationErrorDetail(detail);
  }
  if (typeof detail === "string") {
    return { message: detail };
  }

  return isRecord(detail) ? parseApiErrorDetail(detail) : {};
}

function toApiError(
  error: unknown,
  fallbackMessage = DEFAULT_NETWORK_ERROR_MESSAGE,
  code = "NETWORK_ERROR",
  status = 0,
  context?: {
    method?: string;
    url?: string;
    statusText?: string;
  },
): ApiError {
  if (error instanceof ApiError) {
    return error;
  }

  if (error instanceof Error && error.name === "AbortError") {
    throw error;
  }

  return new ApiError(code, fallbackMessage, status, undefined, {
    ...context,
    cause: error,
  });
}

export async function fetchWithApiError(
  url: string,
  init: RequestInit | undefined,
  networkMessage = DEFAULT_NETWORK_ERROR_MESSAGE,
): Promise<Response> {
  const method = (init?.method ?? "GET").toUpperCase();
  try {
    return await fetch(url, init);
  } catch (error) {
    throw toApiError(error, networkMessage, "NETWORK_ERROR", 0, {
      method,
      url,
    });
  }
}

export async function handleApiError(
  response: Response,
  context?: { method?: string; url?: string },
): Promise<never> {
  let errorData: ApiErrorData = {};

  try {
    errorData = parseApiErrorData(await response.json());
  } catch {
    // Keep defaults when the body is not JSON.
  }

  const code = errorData.code || "UNKNOWN_ERROR";
  const message = errorData.message || DEFAULT_API_ERROR_MESSAGE;
  const field = errorData.field;

  throw new ApiError(code, message, response.status, field, {
    method: context?.method,
    url: context?.url,
    statusText: response.statusText || undefined,
  });
}

export async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  const method = (init?.method ?? "GET").toUpperCase();
  const hasBody = init?.body != null;
  if ((method !== "GET" || hasBody) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  } else if (method === "GET" && !headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }

  const response = await fetchWithApiError(url, {
    ...init,
    headers,
  });

  if (!response.ok) {
    await handleApiError(response, { method, url });
  }

  try {
    return (await response.json()) as T;
  } catch (error) {
    throw toApiError(error, DEFAULT_INVALID_RESPONSE_MESSAGE, "INVALID_RESPONSE", response.status, {
      method,
      url,
      statusText: response.statusText || undefined,
    });
  }
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

export function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

export function isOptionalNullableString(
  value: Record<string, unknown>,
  key: string,
): boolean {
  return !(key in value) || value[key] === null || typeof value[key] === "string";
}

export function isOptionalNullableNumber(
  value: Record<string, unknown>,
  key: string,
): boolean {
  return !(key in value) || value[key] === null || isFiniteNumber(value[key]);
}

export function isOptionalNullableBoolean(
  value: Record<string, unknown>,
  key: string,
): boolean {
  return !(key in value) || value[key] === null || typeof value[key] === "boolean";
}

export function isOptionalNullableRecord(
  value: Record<string, unknown>,
  key: string,
): boolean {
  return !(key in value) || value[key] === null || isRecord(value[key]);
}

export function isOptionalNullableGuard(
  value: Record<string, unknown>,
  key: string,
  guard: (candidate: unknown) => boolean,
): boolean {
  return !(key in value) || value[key] === null || guard(value[key]);
}

export function isOptionalStringArray(value: Record<string, unknown>, key: string): boolean {
  return !(key in value) || isStringArray(value[key]);
}

export function isOptionalNullableStringArray(
  value: Record<string, unknown>,
  key: string,
): boolean {
  return !(key in value) || value[key] === null || isStringArray(value[key]);
}

export function isRecordArray(value: unknown): value is Record<string, unknown>[] {
  return Array.isArray(value) && value.every(isRecord);
}
