import { beforeEach, describe, expect, it } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { useLocalStorage } from "@/hooks/use-local-storage";

describe("useLocalStorage", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("should initialize with default value", () => {
    const { result } = renderHook(() => useLocalStorage<string>("test-key", "default"));
    expect(result.current[0]).toBe("default");
  });

  it("should update state when setter is called", () => {
    const { result } = renderHook(() => useLocalStorage<string>("test-key", "default"));

    act(() => {
      result.current[1]("updated");
    });

    expect(result.current[0]).toBe("updated");
  });

  it("should persist to localStorage on update", () => {
    const { result } = renderHook(() => useLocalStorage<string>("test-key", "default"));

    act(() => {
      result.current[1]("persisted");
    });

    expect(localStorage.getItem("test-key")).toBe('"persisted"');
  });

  it("should read from localStorage on mount", () => {
    localStorage.setItem("test-key", '"existing"');

    const { result } = renderHook(() => useLocalStorage<string>("test-key", "default"));

    expect(result.current[0]).toBe("existing");
  });

  it("should handle complex objects", () => {
    const testObj = { viewMode: "3d", bonds: true };
    const { result } = renderHook(() =>
      useLocalStorage<typeof testObj>("test-obj", { viewMode: "2d", bonds: false }),
    );

    act(() => {
      result.current[1](testObj);
    });

    expect(result.current[0]).toEqual(testObj);
    expect(JSON.parse(localStorage.getItem("test-obj") || "{}")).toEqual(testObj);
  });

  it("should handle JSON errors gracefully", () => {
    localStorage.setItem("bad-json", "{invalid json}");

    const { result } = renderHook(() => useLocalStorage<string>("bad-json", "fallback"));

    expect(result.current[0]).toBe("fallback");
  });
});
