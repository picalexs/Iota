import { useMemo, useSyncExternalStore } from "react";

function cssVar(name: string): string {
  if (typeof document === "undefined") return "#888";
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function subscribeToThemeChanges(onStoreChange: () => void): () => void {
  if (typeof document === "undefined" || typeof MutationObserver === "undefined") {
    return () => {};
  }

  const observer = new MutationObserver(() => onStoreChange());
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["class", "style"],
  });
  return () => observer.disconnect();
}

function getThemeSnapshot(): string {
  if (typeof document === "undefined") return "server";

  const root = document.documentElement;
  return `${root.className}|${root.getAttribute("style") ?? ""}`;
}

function readChartTheme(_themeSnapshot: string): ChartTheme {
  return {
    primary: cssVar("--primary"),
    muted: cssVar("--muted-foreground"),
    foreground: cssVar("--foreground"),
    border: cssVar("--border"),
    background: cssVar("--background"),
    card: cssVar("--card"),
    destructive: cssVar("--destructive"),
    success: cssVar("--success"),
    warning: cssVar("--warning"),
    info: cssVar("--info"),
    chart1: cssVar("--chart-1"),
    chart2: cssVar("--chart-2"),
    chart3: cssVar("--chart-3"),
    chart4: cssVar("--chart-4"),
    chart5: cssVar("--chart-5"),
  };
}

export interface ChartTheme {
  primary: string;
  muted: string;
  foreground: string;
  border: string;
  background: string;
  card: string;
  destructive: string;
  success: string;
  warning: string;
  info: string;
  chart1: string;
  chart2: string;
  chart3: string;
  chart4: string;
  chart5: string;
}

export function useChartTheme(): ChartTheme {
  const themeSnapshot = useSyncExternalStore(
    subscribeToThemeChanges,
    getThemeSnapshot,
    () => "server",
  );

  return useMemo(() => readChartTheme(themeSnapshot), [themeSnapshot]);
}
