import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";

import { ThemeToggle } from "./theme-toggle";
import { SidebarProvider } from "@/components/ui/sidebar";

const mockSetTheme = vi.fn();
let mockTheme: "light" | "dark" | "system" = "light";
let mockResolvedTheme: "light" | "dark" = "light";

vi.mock("@/hooks/use-theme", () => ({
  useTheme: () => ({
    theme: mockTheme,
    resolvedTheme: mockResolvedTheme,
    setTheme: mockSetTheme,
  }),
}));

describe("ThemeToggle", () => {
  beforeEach(() => {
    mockSetTheme.mockClear();
    mockTheme = "light";
    mockResolvedTheme = "light";
  });

  function renderToggle() {
    return render(
      <SidebarProvider>
        <ThemeToggle />
      </SidebarProvider>,
    );
  }

  it("renders a button with the current theme label", () => {
    renderToggle();
    expect(
      screen.getByRole("button", { name: "Theme: Light. Click to switch to Dark" }),
    ).toBeInTheDocument();
  });

  it("shows the system label when the stored preference is system", () => {
    mockTheme = "system";
    mockResolvedTheme = "dark";
    renderToggle();

    expect(
      screen.getByRole("button", {
        name: "Theme: System. Click to switch to Light. Following system (Dark)",
      }),
    ).toBeInTheDocument();
  });

  it('cycles from "light" to "dark" on click', async () => {
    const user = userEvent.setup();
    renderToggle();

    await user.click(screen.getByRole("button", { name: "Theme: Light. Click to switch to Dark" }));

    expect(mockSetTheme).toHaveBeenCalledWith("dark");
  });

  it('cycles from "dark" to "system" on click', async () => {
    const user = userEvent.setup();
    mockTheme = "dark";
    mockResolvedTheme = "dark";
    renderToggle();

    await user.click(
      screen.getByRole("button", { name: "Theme: Dark. Click to switch to System" }),
    );

    expect(mockSetTheme).toHaveBeenCalledWith("system");
  });

  it('cycles from "system" to "light" on click', async () => {
    const user = userEvent.setup();
    mockTheme = "system";
    mockResolvedTheme = "dark";
    renderToggle();

    await user.click(
      screen.getByRole("button", {
        name: "Theme: System. Click to switch to Light. Following system (Dark)",
      }),
    );

    expect(mockSetTheme).toHaveBeenCalledWith("light");
  });
});
