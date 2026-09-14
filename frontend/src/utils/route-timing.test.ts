import { describe, it, expect, beforeEach, vi } from "vitest";
import { markRoute } from "./web-vitals";

/**
 * Route Timing Marks Test Suite
 *
 * Tests that route transitions are marked in performance API
 * for measurement and advisory CI checks.
 */

describe("Route Timing Marks", () => {
  let performanceMarkSpy: ReturnType<typeof vi.spyOn>;
  let performanceMeasureSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    performanceMarkSpy = vi.spyOn(performance, "mark");
    performanceMeasureSpy = vi.spyOn(performance, "measure");
  });

  afterEach(() => {
    performanceMarkSpy.mockRestore();
    performanceMeasureSpy.mockRestore();
  });

  describe("markRoute", () => {
    it("should mark route start with correct label", () => {
      markRoute("molecules", "start");

      expect(performanceMarkSpy).toHaveBeenCalledWith("route-molecules-start");
    });

    it("should mark route end with correct label", () => {
      markRoute("runs", "end");

      expect(performanceMarkSpy).toHaveBeenCalledWith("route-runs-end");
    });

    it("should measure route duration when end mark is created", () => {
      // First establish the start mark
      markRoute("home", "start");
      performanceMarkSpy.mockClear();
      performanceMeasureSpy.mockClear();

      // Then mark the end
      markRoute("home", "end");

      expect(performanceMarkSpy).toHaveBeenCalledWith("route-home-end");
      expect(performanceMeasureSpy).toHaveBeenCalledWith(
        "route-home",
        "route-home-start",
        "route-home-end",
      );
    });

    it("should handle multiple concurrent routes", () => {
      markRoute("molecules", "start");
      markRoute("runs", "start");
      markRoute("molecules", "end");
      markRoute("runs", "end");

      expect(performanceMarkSpy).toHaveBeenCalledTimes(4);
      expect(performanceMeasureSpy).toHaveBeenCalledTimes(2);
    });

    it("should not throw if performance API is unavailable", () => {
      const originalPerformance = globalThis.performance;
      delete (globalThis as Record<string, unknown>).performance;

      expect(() => {
        markRoute("test", "start");
      }).not.toThrow();

      (globalThis as Record<string, unknown>).performance = originalPerformance;
    });

    it("should handle missing start mark gracefully", () => {
      // Try to measure without establishing start mark first
      const mockMeasure = vi.fn().mockImplementation(() => {
        throw new Error("Start mark not found");
      });
      performanceMeasureSpy.mockImplementation(mockMeasure);

      expect(() => {
        markRoute("orphan", "end");
      }).not.toThrow();
    });
  });
});
