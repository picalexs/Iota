import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, fetchWithApiError, handleApiError, request, trimTrailingSlashes } from "./http";
import { getFetchCall, mockJsonResponse } from "./test-helpers";

describe("HTTP transport boundary", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("removes only trailing slashes from an API base", () => {
    expect(trimTrailingSlashes("https://api.example///")).toBe("https://api.example");
    expect(trimTrailingSlashes("/")).toBe("");
    expect(trimTrailingSlashes("https://api.example/path")).toBe("https://api.example/path");
  });

  it("uses Accept for GET and Content-Type for JSON requests", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(mockJsonResponse({ items: [] }))
      .mockResolvedValueOnce(mockJsonResponse({ ok: true }));

    await request("/api/items");
    await request("/api/items", {
      method: "POST",
      body: JSON.stringify({ name: "item" }),
    });

    expect(new Headers(getFetchCall(0).options.headers).get("Accept")).toBe("application/json");
    expect(new Headers(getFetchCall(0).options.headers).get("Content-Type")).toBeNull();
    expect(new Headers(getFetchCall(1).options.headers).get("Content-Type")).toBe(
      "application/json",
    );
  });

  it("keeps structured API error metadata", async () => {
    const response = {
      ok: false,
      status: 422,
      statusText: "Unprocessable Entity",
      json: vi.fn().mockResolvedValue({
        detail: {
          code: "INVALID_REQUEST",
          message: "Request is invalid",
          field: "config",
        },
      }),
    } as unknown as Response;

    await expect(
      handleApiError(response, { method: "POST", url: "/api/runs" }),
    ).rejects.toMatchObject({
      code: "INVALID_REQUEST",
      message: "Request is invalid",
      status: 422,
      field: "config",
      method: "POST",
      url: "/api/runs",
      statusText: "Unprocessable Entity",
    });
  });

  it("maps validation arrays and string details without exposing raw payloads", async () => {
    const validationResponse = {
      ok: false,
      status: 422,
      json: vi.fn().mockResolvedValue({
        detail: [{ type: "missing", loc: ["body", "name"], msg: "Field required" }],
      }),
    } as unknown as Response;
    await expect(handleApiError(validationResponse)).rejects.toMatchObject({
      code: "missing",
      message: "Field required",
      field: "name",
    });

    const stringResponse = {
      ok: false,
      status: 502,
      json: vi.fn().mockResolvedValue({ detail: "Upstream service unavailable" }),
    } as unknown as Response;
    await expect(handleApiError(stringResponse)).rejects.toMatchObject({
      code: "UNKNOWN_ERROR",
      message: "Upstream service unavailable",
      status: 502,
    });
  });

  it("distinguishes network failures from invalid JSON responses", async () => {
    vi.mocked(fetch).mockRejectedValueOnce(new TypeError("Failed to fetch"));

    await expect(fetchWithApiError("/api/runs", { method: "GET" })).rejects.toMatchObject({
      code: "NETWORK_ERROR",
      message: "Unable to reach the API. Please try again.",
      status: 0,
      method: "GET",
      url: "/api/runs",
      cause: expect.objectContaining({ message: "Failed to fetch" }),
    });

    const invalidJsonResponse = {
      ok: true,
      status: 200,
      json: vi.fn().mockRejectedValue(new Error("Invalid JSON")),
    } as unknown as Response;
    vi.mocked(fetch)
      .mockResolvedValueOnce(invalidJsonResponse)
      .mockResolvedValueOnce(invalidJsonResponse);

    await expect(request("/api/runs")).rejects.toMatchObject({
      code: "INVALID_RESPONSE",
      message: "The server returned an invalid response.",
      status: 200,
    });
    await expect(request("/api/runs")).rejects.toBeInstanceOf(ApiError);
  });
});
