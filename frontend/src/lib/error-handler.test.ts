import { describe, expect, it, vi, beforeEach } from "vitest";

const { toastError } = vi.hoisted(() => ({
  toastError: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: {
    error: toastError,
  },
}));

import { isApiUnavailableError, showErrorToast } from "./error-handler";

describe("error-handler", () => {
  beforeEach(() => {
    toastError.mockReset();
  });

  it("detects fetch failures as API outages", () => {
    expect(isApiUnavailableError(new TypeError("Failed to fetch"))).toBe(true);
    expect(
      isApiUnavailableError({ message: "Gateway timeout", status: 504, name: "ApiError" }),
    ).toBe(true);
    expect(isApiUnavailableError(new Error("Validation failed"))).toBe(false);
  });

  it("collapses API outages into the shared unavailable toast", () => {
    showErrorToast(new TypeError("Failed to fetch"), {
      title: "Submission Failed",
    });

    expect(toastError).toHaveBeenCalledWith("The API is unavailable right now", {
      id: "api-unavailable",
      description:
        "The frontend is still running, but live data and actions will stay unavailable until the backend responds again.",
    });
  });

  it("keeps non-network errors scoped to their original title and message", () => {
    showErrorToast(new Error("Validation failed"), {
      title: "Submission Failed",
    });

    expect(toastError).toHaveBeenCalledWith("Submission Failed", {
      description: "Validation failed",
    });
  });
});
