import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ErrorBoundary } from "./error-boundary";
import { allowConsoleCall } from "@/test/console-policy";

function Thrower({ shouldThrow }: Readonly<{ shouldThrow: boolean }>) {
  if (shouldThrow) {
    throw new Error("boom");
  }
  return <div>Recovered</div>;
}

describe("ErrorBoundary", () => {
  it("resets when resetKey changes", async () => {
    allowConsoleCall("error", "[react.error-boundary] Captured a render error.");
    const consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined);

    const { rerender } = render(
      <ErrorBoundary resetKey="one">
        <Thrower shouldThrow />
      </ErrorBoundary>,
    );

    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("This page hit a rendering problem")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reload page" })).toBeInTheDocument();
    expect(consoleErrorSpy).toHaveBeenCalledWith(
      "[react.error-boundary] Captured a render error.",
      expect.objectContaining({
        error: expect.objectContaining({
          message: "boom",
          name: "Error",
        }),
      }),
    );

    rerender(
      <ErrorBoundary resetKey="two">
        <Thrower shouldThrow={false} />
      </ErrorBoundary>,
    );

    await waitFor(() => {
      expect(screen.getByText("Recovered")).toBeInTheDocument();
    });
    consoleErrorSpy.mockRestore();
  });
});
