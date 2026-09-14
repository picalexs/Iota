import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { captureWebVitals, emitVital, type VitalMetric } from "./web-vitals";

/**
 * Web Vitals Emission Test Suite
 *
 * Tests that web vitals (CLS, FID, LCP) are captured and emitted correctly.
 * Ensures telemetry is non-blocking and resilient to missing API endpoints.
 */

function emitObservedEntries(
  callback: PerformanceObserverCallback | undefined,
  entries: PerformanceEntry[],
) {
  callback?.(
    {
      getEntries: () => entries,
    } as PerformanceObserverEntryList,
    {} as PerformanceObserver,
  );
}

describe("Web Vitals Emission", () => {
  let consoleLogSpy: ReturnType<typeof vi.spyOn>;
  let fetchMock: ReturnType<typeof vi.spyOn>;

  function installPerformanceObserverMock() {
    const callbacks = new Map<string, PerformanceObserverCallback>();

    class MockPerformanceObserver {
      private readonly callback: PerformanceObserverCallback;

      observe = vi.fn((options: PerformanceObserverInit) => {
        if (options.type) {
          callbacks.set(options.type, this.callback);
        }
      });

      disconnect = vi.fn();

      constructor(callback: PerformanceObserverCallback) {
        this.callback = callback;
      }
    }

    vi.stubGlobal("PerformanceObserver", MockPerformanceObserver);

    return callbacks;
  }

  beforeEach(() => {
    consoleLogSpy = vi.spyOn(console, "log").mockImplementation(() => {});
    fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({ success: true }), { status: 200 }));
    // Clear module cache to reset singleton state
    vi.clearAllMocks();
  });

  afterEach(() => {
    consoleLogSpy.mockRestore();
    fetchMock.mockRestore();
  });

  describe("emitVital", () => {
    it("should emit a vital metric to console in debug mode", () => {
      const vital: VitalMetric = {
        name: "LCP",
        value: 1500,
        rating: "good",
      };

      emitVital(vital);

      expect(consoleLogSpy).toHaveBeenCalledWith(expect.stringContaining("Web Vital:"), vital);
    });

    it("should emit a vital metric to advisory endpoint if available", async () => {
      const vital: VitalMetric = {
        name: "CLS",
        value: 0.05,
        rating: "good",
      };

      // Mock the advisory endpoint
      fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));

      emitVital(vital, { endpoint: "/api/metrics/vitals" });

      // Give the async operation a chance to complete
      await new Promise((resolve) => setTimeout(resolve, 100));

      // Fetch should have been called with the vital
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/api/metrics/vitals"),
        expect.objectContaining({
          method: "POST",
          headers: expect.objectContaining({
            "Content-Type": "application/json",
          }),
        }),
      );
    });

    it("should not throw if advisory endpoint is unavailable", async () => {
      const vital: VitalMetric = {
        name: "FID",
        value: 100,
        rating: "good",
      };

      // Mock fetch to reject
      fetchMock.mockRejectedValueOnce(new Error("Network error"));

      expect(() => {
        emitVital(vital, { endpoint: "/api/metrics/vitals" });
      }).not.toThrow();
    });
  });

  describe("captureWebVitals", () => {
    it("should initialize vital observers and emit metrics", () => {
      // Mock PerformanceObserver constructor and track calls
      let observerCount = 0;

      class MockPerformanceObserver {
        observe = vi.fn(() => {
          observerCount++;
        });
        disconnect = vi.fn();
      }

      vi.stubGlobal("PerformanceObserver", MockPerformanceObserver);

      const onMetric = vi.fn();
      captureWebVitals({ onMetric });

      expect(observerCount).toBe(3);
    });

    it("should handle missing PerformanceObserver gracefully", () => {
      // Simulate missing PerformanceObserver (edge case in older browsers)
      vi.stubGlobal("PerformanceObserver", undefined);

      expect(() => {
        captureWebVitals({ onMetric: vi.fn() });
      }).not.toThrow();
    });

    it("should track aggregated CLS value", () => {
      const callbacks = installPerformanceObserverMock();
      const onMetric = vi.fn();

      captureWebVitals({ onMetric });
      emitObservedEntries(callbacks.get("layout-shift"), [
        { hadRecentInput: false, value: 0.05 } as unknown as PerformanceEntry,
        { hadRecentInput: true, value: 0.4 } as unknown as PerformanceEntry,
        { hadRecentInput: false, value: 0.02 } as unknown as PerformanceEntry,
      ]);

      expect(onMetric).toHaveBeenCalledWith(
        expect.objectContaining({ name: "CLS", value: 0.05, rating: "good" }),
      );
      expect(onMetric).toHaveBeenCalledWith(
        expect.objectContaining({ name: "CLS", value: 0.07, rating: "good" }),
      );
      expect(onMetric).not.toHaveBeenCalledWith(expect.objectContaining({ value: 0.47 }));
    });

    it("should emit FCP only for first-contentful-paint entries", () => {
      const callbacks = installPerformanceObserverMock();
      const onMetric = vi.fn();

      captureWebVitals({ onMetric });
      emitObservedEntries(callbacks.get("paint"), [
        { name: "first-paint", startTime: 500 } as PerformanceEntry,
        { name: "first-contentful-paint", startTime: 900 } as PerformanceEntry,
      ]);

      expect(onMetric).toHaveBeenCalledOnce();
      expect(onMetric).toHaveBeenCalledWith(
        expect.objectContaining({ name: "FCP", value: 900, rating: "good" }),
      );
    });
  });

  describe("integration", () => {
    it("should capture and emit vitals to console and endpoint", async () => {
      const onMetric = vi.fn();
      fetchMock.mockResolvedValue(new Response(null, { status: 204 }));

      captureWebVitals({
        onMetric,
        endpoint: "/api/metrics/vitals",
      });

      // Simulate a route timing emit
      emitVital({ name: "LCP", value: 1200, rating: "good" }, { endpoint: "/api/metrics/vitals" });

      await new Promise((resolve) => setTimeout(resolve, 100));

      // Both console log and fetch should have been called
      expect(consoleLogSpy).toHaveBeenCalled();
      expect(fetchMock).toHaveBeenCalled();
    });
  });
});
