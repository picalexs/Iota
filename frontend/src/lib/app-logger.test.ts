import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api/http";
import { allowConsoleCall } from "@/test/console-policy";
import { logAppError } from "./app-logger";

describe("app-logger", () => {
  let consoleError: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    allowConsoleCall("error", "[run-detail.load] Failed to load run detail.");
    consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
  });

  it("includes custom ApiError metadata in error logs", () => {
    const error = new ApiError("NOT_FOUND", "Run not found", 404, undefined, {
      method: "GET",
      url: "/api/runs/run-123",
      statusText: "Not Found",
      cause: new TypeError("Failed to fetch"),
    });

    logAppError("run-detail.load", "Failed to load run detail.", error, {
      runId: "run-123",
    });

    expect(consoleError).toHaveBeenCalledWith("[run-detail.load] Failed to load run detail.", {
      runId: "run-123",
      error: expect.objectContaining({
        name: "ApiError",
        message: "Run not found",
        code: "NOT_FOUND",
        status: 404,
        method: "GET",
        url: "/api/runs/run-123",
        statusText: "Not Found",
        cause: expect.objectContaining({
          name: "TypeError",
          message: "Failed to fetch",
        }),
      }),
    });
  });
});
