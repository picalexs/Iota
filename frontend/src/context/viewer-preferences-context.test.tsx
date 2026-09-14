import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import {
  useViewerPreferences,
  ViewerPreferencesProvider,
} from "@/context/viewer-preferences-context";
import { allowConsoleCall } from "@/test/console-policy";

describe("ViewerPreferencesContext", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("should provide default preferences", () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <ViewerPreferencesProvider>{children}</ViewerPreferencesProvider>
    );

    const { result } = renderHook(() => useViewerPreferences(), { wrapper });

    expect(result.current.preferences.viewMode).toBe("3d");
    expect(result.current.preferences.viewerStyle).toBe("ball-and-stick");
    expect(result.current.preferences.showBonds).toBe(true);
  });

  it("should allow changing viewMode", () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <ViewerPreferencesProvider>{children}</ViewerPreferencesProvider>
    );

    const { result } = renderHook(() => useViewerPreferences(), { wrapper });

    act(() => {
      result.current.setViewMode("2d");
    });

    expect(result.current.preferences.viewMode).toBe("2d");
  });

  it("should allow changing viewerStyle", () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <ViewerPreferencesProvider>{children}</ViewerPreferencesProvider>
    );

    const { result } = renderHook(() => useViewerPreferences(), { wrapper });

    act(() => {
      result.current.setViewerStyle("space-filling");
    });

    expect(result.current.preferences.viewerStyle).toBe("space-filling");
  });

  it("should allow toggling showBonds", () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <ViewerPreferencesProvider>{children}</ViewerPreferencesProvider>
    );

    const { result } = renderHook(() => useViewerPreferences(), { wrapper });

    act(() => {
      result.current.setShowBonds(false);
    });

    expect(result.current.preferences.showBonds).toBe(false);
  });

  it("should persist preferences to localStorage", async () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <ViewerPreferencesProvider>{children}</ViewerPreferencesProvider>
    );

    const { result } = renderHook(() => useViewerPreferences(), { wrapper });

    act(() => {
      result.current.setViewMode("2d");
    });

    await waitFor(() => {
      const stored = JSON.parse(localStorage.getItem("qvs-viewer-preferences-v2") || "{}");
      expect(stored.viewMode).toBe("2d");
    });
  });

  it("should throw error when hook is used outside provider", () => {
    allowConsoleCall("error", "useViewerPreferences must be used within ViewerPreferencesProvider");
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});

    expect(() => {
      renderHook(() => useViewerPreferences());
    }).toThrow("useViewerPreferences must be used within ViewerPreferencesProvider");

    spy.mockRestore();
  });

  it("should restore preferences from localStorage on mount", () => {
    const savedPreferences = {
      viewMode: "2d" as const,
      viewerStyle: "wireframe" as const,
      showBonds: false,
    };

    localStorage.setItem("qvs-viewer-preferences-v2", JSON.stringify(savedPreferences));

    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <ViewerPreferencesProvider>{children}</ViewerPreferencesProvider>
    );

    const { result } = renderHook(() => useViewerPreferences(), { wrapper });

    expect(result.current.preferences.viewMode).toBe("2d");
    expect(result.current.preferences.viewerStyle).toBe("wireframe");
    expect(result.current.preferences.showBonds).toBe(false);
  });
});
