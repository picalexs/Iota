/** Service health and component status API calls. */

import type { ApiStatusResponse } from "@/types/api";
import { API_BASE, invalidApiResponse, isRecord, request } from "./http";

const STATUS_COMPONENT_VALUES = new Set<ApiStatusResponse["db"]>([
  "connected",
  "disconnected",
  "unknown",
]);

export function parseStatusResponse(value: unknown): ApiStatusResponse {
  if (
    !isRecord(value) ||
    value.api !== "ready" ||
    !STATUS_COMPONENT_VALUES.has(value.db as ApiStatusResponse["db"]) ||
    !STATUS_COMPONENT_VALUES.has(value.redis as ApiStatusResponse["redis"])
  ) {
    throw invalidApiResponse("Invalid service status response");
  }

  return value as ApiStatusResponse;
}

export async function getStatus(): Promise<ApiStatusResponse> {
  const response = await request<unknown>(`${API_BASE}/api/status`, {
    method: "GET",
  });
  return parseStatusResponse(response);
}
