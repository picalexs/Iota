import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ApiStatusResponse } from "@/types/api";
import { getStatus, parseStatusResponse } from "./status";
import { getFetchCall, mockJsonResponse } from "./test-helpers";

describe("status API transport", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("returns the generated service status response", async () => {
    const statusResponse = {
      api: "ready",
      db: "connected",
      redis: "connected",
    } satisfies ApiStatusResponse;
    vi.mocked(fetch).mockResolvedValueOnce(mockJsonResponse(statusResponse));

    await expect(getStatus()).resolves.toEqual(statusResponse);
    expect(getFetchCall().url).toBe("/api/status");
  });

  it("rejects malformed service status payloads", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      mockJsonResponse({ api: "ready", db: "connected", redis: "broken" }),
    );

    await expect(getStatus()).rejects.toThrow("Invalid service status response");
    expect(() => parseStatusResponse({ api: "not-ready" })).toThrow(
      "Invalid service status response",
    );
  });
});
