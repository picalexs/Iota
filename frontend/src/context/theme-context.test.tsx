import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, beforeEach, vi } from "vitest";
import { ThemeProvider, useTheme } from "./theme-context";
import { allowConsoleCall } from "@/test/console-policy";

/** Helper component that surfaces the current theme value and setTheme actions. */
function ThemeConsumer() {
  const { theme, resolvedTheme, setTheme } = useTheme();
  return (
    <div>
      <span data-testid="theme">{theme}</span>
      <span data-testid="resolved-theme">{resolvedTheme}</span>
      <button onClick={() => setTheme("dark")}>dark</button>
      <button onClick={() => setTheme("light")}>light</button>
      <button onClick={() => setTheme("system")}>system</button>
    </div>
  );
}

describe("ThemeProvider", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.classList.remove("dark");
    vi.stubGlobal("matchMedia", (query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));
  });

  it("renders children", () => {
    render(
      <ThemeProvider>
        <span data-testid="child">hello</span>
      </ThemeProvider>,
    );
    expect(screen.getByTestId("child")).toBeInTheDocument();
  });

  it('defaults to "system" when localStorage is empty', () => {
    render(
      <ThemeProvider>
        <ThemeConsumer />
      </ThemeProvider>,
    );
    expect(screen.getByTestId("theme").textContent).toBe("system");
  });

  it('setTheme("dark") adds "dark" class to document.documentElement', async () => {
    const user = userEvent.setup();
    render(
      <ThemeProvider>
        <ThemeConsumer />
      </ThemeProvider>,
    );
    await user.click(screen.getByRole("button", { name: "dark" }));
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(document.documentElement.style.colorScheme).toBe("dark");
    expect(screen.getByTestId("resolved-theme").textContent).toBe("dark");
  });

  it('setTheme("light") removes "dark" class from document.documentElement', async () => {
    const user = userEvent.setup();
    document.documentElement.classList.add("dark");
    render(
      <ThemeProvider>
        <ThemeConsumer />
      </ThemeProvider>,
    );
    await user.click(screen.getByRole("button", { name: "light" }));
    expect(document.documentElement.classList.contains("dark")).toBe(false);
    expect(document.documentElement.style.colorScheme).toBe("light");
  });

  it('setTheme("system") tracks the resolved system theme', async () => {
    const user = userEvent.setup();
    vi.stubGlobal("matchMedia", (query: string) => ({
      matches: true,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));

    render(
      <ThemeProvider>
        <ThemeConsumer />
      </ThemeProvider>,
    );

    await user.click(screen.getByRole("button", { name: "system" }));
    expect(screen.getByTestId("theme").textContent).toBe("system");
    expect(screen.getByTestId("resolved-theme").textContent).toBe("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(document.documentElement.style.colorScheme).toBe("dark");
  });

  it('setTheme("dark") writes to localStorage', async () => {
    const user = userEvent.setup();
    render(
      <ThemeProvider storageKey="test-theme">
        <ThemeConsumer />
      </ThemeProvider>,
    );
    await user.click(screen.getByRole("button", { name: "dark" }));
    expect(localStorage.getItem("test-theme")).toBe("dark");
  });

  it("reads theme from localStorage on mount", () => {
    localStorage.setItem("test-theme", "dark");
    render(
      <ThemeProvider storageKey="test-theme">
        <ThemeConsumer />
      </ThemeProvider>,
    );
    expect(screen.getByTestId("theme").textContent).toBe("dark");
    expect(screen.getByTestId("resolved-theme").textContent).toBe("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("useTheme outside provider throws an error", () => {
    // Suppress the React error boundary console output for this test
    allowConsoleCall("error", "useTheme must be used within a ThemeProvider");
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<ThemeConsumer />)).toThrow("useTheme must be used within a ThemeProvider");
    consoleSpy.mockRestore();
  });
});
