export interface VitalMetric {
  name: string;
  value: number;
  rating?: "good" | "needs-improvement" | "poor";
  id?: string;
}

export interface VitalsOptions {
  endpoint?: string;
  debug?: boolean;
}

export interface CaptureVitalsOptions extends VitalsOptions {
  onMetric?: (vital: VitalMetric) => void;
}

// Local structural types replace DOM entries that TypeScript may not expose.
type LayoutShiftEntry = PerformanceEntry & { hadRecentInput?: boolean; value?: number };
type LargestContentfulPaintEntry = PerformanceEntry & {
  renderTime?: number;
  loadTime?: number;
  startTime?: number;
};

export function emitVital(vital: VitalMetric, options: VitalsOptions = {}): void {
  const { endpoint, debug } = options;

  if (debug || import.meta.env.DEV) {
    console.log("Web Vital:", vital);
  }

  if (endpoint) {
    // Defer optional reporting so telemetry never blocks navigation.
    setTimeout(() => {
      fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(vital),
        keepalive: false,
      }).catch((err) => {
        if (debug || import.meta.env.DEV) {
          console.debug(`Failed to emit vital to ${endpoint}:`, err);
        }
      });
    }, 0);
  }
}

function rateCls(value: number): VitalMetric["rating"] {
  if (value <= 0.1) return "good";
  if (value <= 0.25) return "needs-improvement";
  return "poor";
}

function rateLcp(value: number): VitalMetric["rating"] {
  if (value <= 2500) return "good";
  if (value <= 4000) return "needs-improvement";
  return "poor";
}

function rateFcp(value: number): VitalMetric["rating"] {
  if (value <= 1800) return "good";
  if (value <= 3000) return "needs-improvement";
  return "poor";
}

function shouldDebug(debug?: boolean): boolean {
  return debug === true || import.meta.env.DEV;
}

function debugUnsupportedObserver(debug: boolean | undefined, message: string): void {
  if (shouldDebug(debug)) {
    console.debug(message);
  }
}

function publishVital(vital: VitalMetric, options: CaptureVitalsOptions): void {
  options.onMetric?.(vital);
  emitVital(vital, { endpoint: options.endpoint, debug: options.debug });
}

function observePerformanceEntries(
  type: string,
  callback: PerformanceObserverCallback,
  debug: boolean | undefined,
  unsupportedMessage: string,
): void {
  const observer = new PerformanceObserver(callback);
  try {
    observer.observe({ type, buffered: true });
  } catch {
    debugUnsupportedObserver(debug, unsupportedMessage);
  }
}

function createClsObserverCallback(options: CaptureVitalsOptions): PerformanceObserverCallback {
  let cumulativeCls = 0;
  return (list) => {
    for (const entry of list.getEntries()) {
      const layoutShift = entry as LayoutShiftEntry;
      if (layoutShift.hadRecentInput ?? false) continue;

      cumulativeCls += layoutShift.value ?? 0;
      publishVital(
        {
          name: "CLS",
          value: cumulativeCls,
          rating: rateCls(cumulativeCls),
        },
        options,
      );
    }
  };
}

function createLcpObserverCallback(options: CaptureVitalsOptions): PerformanceObserverCallback {
  return (list) => {
    const entries = list.getEntries();
    const lastEntry = entries.at(-1);
    if (!lastEntry) return;

    const lcpEntry: LargestContentfulPaintEntry = lastEntry;
    const lcpValue = lcpEntry.renderTime || lcpEntry.loadTime || 0;
    publishVital(
      {
        name: "LCP",
        value: lcpValue,
        rating: rateLcp(lcpValue),
      },
      options,
    );
  };
}

function createFcpObserverCallback(options: CaptureVitalsOptions): PerformanceObserverCallback {
  return (list) => {
    for (const entry of list.getEntries()) {
      if (entry.name !== "first-contentful-paint") continue;

      const fcpValue = (entry as PerformancePaintTiming).startTime ?? 0;
      publishVital(
        {
          name: "FCP",
          value: fcpValue,
          rating: rateFcp(fcpValue),
        },
        options,
      );
    }
  };
}

export function captureWebVitals(options: CaptureVitalsOptions = {}): void {
  const { debug } = options;

  if (!("PerformanceObserver" in globalThis)) {
    debugUnsupportedObserver(debug, "PerformanceObserver not available");
    return;
  }

  try {
    observePerformanceEntries(
      "layout-shift",
      createClsObserverCallback(options),
      debug,
      "layout-shift observer not supported",
    );

    observePerformanceEntries(
      "largest-contentful-paint",
      createLcpObserverCallback(options),
      debug,
      "largest-contentful-paint observer not supported",
    );

    observePerformanceEntries(
      "paint",
      createFcpObserverCallback(options),
      debug,
      "paint observer not supported",
    );
  } catch (err) {
    // Telemetry must not break the page.
    if (shouldDebug(debug)) {
      console.debug("Error setting up web vitals observers:", err);
    }
  }
}

export function getRouteMarkName(pathname: string): string {
  const normalized = pathname.replace(/^\/$/, "home").replace(/^\//, "").split("/")[0];
  return normalized || "home";
}

export function markRoute(routeName: string, phase: "start" | "end"): void {
  try {
    if ("performance" in globalThis && globalThis.performance.mark) {
      globalThis.performance.mark(`route-${routeName}-${phase}`);

      if (phase === "end") {
        try {
          globalThis.performance.measure(
            `route-${routeName}`,
            `route-${routeName}-start`,
            `route-${routeName}-end`,
          );
        } catch {
          // First-load routes may not have a matching start mark.
        }
      }
    }
  } catch {
    // Route timing is advisory.
  }
}
