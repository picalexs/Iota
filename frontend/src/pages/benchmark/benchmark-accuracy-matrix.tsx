import { Link } from "@tanstack/react-router";
import { containerSurfaceClassName } from "@/lib/interactive-styles";
import { type AccuracyVerdict } from "@/lib/results/accuracy";
import { cn } from "@/lib/utils";
import type { MoleculePreset } from "@/lib/benchmark-presets";
import type { BenchmarkEntry } from "./benchmark-utils";
import { assessBenchmarkEntry, benchmarkEntryDisplayLabel } from "./benchmark-utils";
import { ExpandPanelButton } from "./benchmark-panel-expand-button";
import { formatMetric } from "./benchmark-insights-formatters";

type BenchmarkInsightsGroupedRows = ReadonlyArray<{
  preset: MoleculePreset;
  rows: readonly BenchmarkEntry[];
}>;

function splitMatrixHeaderLabel(label: string): { primary: string; secondary: string | null } {
  const [primary = "", ...secondaryParts] = label.split(" · ");
  const secondary = secondaryParts.join(" · ").trim();

  return {
    primary: primary.trim(),
    secondary: secondary.length > 0 ? secondary : null,
  };
}

function formatMatrixStatusLabel(status: BenchmarkEntry["status"]): string {
  if (status === "idle") return "Waiting";
  return status.replaceAll("_", " ");
}

function buildMatrixDetailLabel(
  entry: Pick<BenchmarkEntry, "status" | "elapsedSeconds" | "errorMessage">,
  assessment: ReturnType<typeof assessBenchmarkEntry> | null,
): string | null {
  if (assessment?.absErrorMha != null) {
    return formatMatrixStatusLabel(entry.status);
  }
  if (entry.elapsedSeconds != null) {
    return `${formatMetric(entry.elapsedSeconds)} s`;
  }
  if (entry.errorMessage) {
    return "Needs attention";
  }
  return null;
}

function verdictTone(verdict: AccuracyVerdict): string {
  switch (verdict) {
    case "accurate":
      return "border-success/40 bg-success/10 text-success";
    case "not_accurate":
      return "border-destructive/40 bg-destructive/10 text-destructive";
    case "unscored":
      return "border-warning/40 bg-warning/10 text-warning";
  }
}

function statusTone(entry: BenchmarkEntry, chemicalAccuracyHa: number): string {
  if (entry.status === "completed" && entry.energy !== null) {
    return verdictTone(assessBenchmarkEntry(entry, chemicalAccuracyHa).verdict);
  }
  if (entry.status === "failed") return "border-destructive/40 bg-destructive/10 text-destructive";
  if (entry.status === "cancelled") return "border-border bg-muted/45 text-muted-foreground";
  if (entry.status === "paused") return "border-warning/40 bg-warning/10 text-warning";
  if (entry.status === "running" || entry.status === "pausing") {
    return "border-warning/40 bg-warning/10 text-warning";
  }
  if (entry.status === "queued") {
    return "border-info/40 bg-info/10 text-info";
  }
  return "border-border/70 bg-muted/20 text-muted-foreground";
}

export function AccuracyMatrix({
  grouped,
  chemicalAccuracyHa,
  mode = "embedded",
  onExpand,
}: Readonly<{
  grouped: BenchmarkInsightsGroupedRows;
  chemicalAccuracyHa: number;
  mode?: "embedded" | "fullscreen";
  onExpand?: () => void;
}>) {
  return (
    <div
      className={cn(
        "rounded-xl p-4",
        containerSurfaceClassName,
        mode === "fullscreen" ? "flex h-full flex-col overflow-hidden" : "h-fit self-start",
      )}
    >
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold">Accuracy matrix</h2>
        </div>
        <div className="flex items-center gap-2">
          <p className="text-xs text-muted-foreground">
            Target {(chemicalAccuracyHa * 1000).toFixed(1)} mHa
          </p>
          {mode === "embedded" && onExpand ? (
            <ExpandPanelButton label="accuracy matrix" onClick={onExpand} />
          ) : null}
        </div>
      </div>
      <div
        className={cn("space-y-3", mode === "fullscreen" && "min-h-0 flex-1 overflow-y-auto pr-1")}
      >
        {grouped.map(({ preset, rows }) => (
          <section
            key={preset.key}
            className="rounded-lg border border-border/70 bg-background/35 p-3"
          >
            <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
              <div className="min-w-0">
                <h3 className="text-sm font-semibold">{preset.formula || preset.name}</h3>
                {preset.formula && preset.name !== preset.formula ? (
                  <p className="truncate text-[11px] text-muted-foreground">{preset.name}</p>
                ) : null}
              </div>
              <p className="text-[11px] text-muted-foreground">
                {rows.length} row{rows.length === 1 ? "" : "s"}
              </p>
            </div>
            <div
              className="grid gap-2"
              style={{
                gridTemplateColumns: `repeat(auto-fit, minmax(${mode === "fullscreen" ? "11rem" : "9.5rem"}, 1fr))`,
              }}
            >
              {rows.map((entry) => {
                const displayLabel = benchmarkEntryDisplayLabel(entry);
                const header = splitMatrixHeaderLabel(displayLabel);
                const assessment =
                  entry.status === "completed" && entry.energy !== null
                    ? assessBenchmarkEntry(entry, chemicalAccuracyHa)
                    : null;
                const metricLabel =
                  assessment?.absErrorMha != null
                    ? `${assessment.absErrorMha.toFixed(1)} mHa`
                    : formatMatrixStatusLabel(entry.status);
                const detailLabel = buildMatrixDetailLabel(entry, assessment);
                const cellClasses = cn(
                  "flex min-h-24 flex-col gap-2 rounded-lg border p-2 text-left transition-colors",
                  statusTone(entry, chemicalAccuracyHa),
                );
                const content = (
                  <>
                    <div className="min-w-0">
                      <span className="text-[10px] font-semibold uppercase leading-tight text-muted-foreground">
                        {header.primary}
                      </span>
                      {header.secondary ? (
                        <p
                          className="mt-1 text-[11px] font-medium leading-tight [overflow-wrap:anywhere]"
                          title={header.secondary}
                        >
                          {header.secondary}
                        </p>
                      ) : null}
                    </div>
                    <div className="mt-auto">
                      <p className="text-xs font-semibold">{metricLabel}</p>
                      {detailLabel ? (
                        <p className="text-[10px] uppercase tracking-[0.02em] text-muted-foreground">
                          {detailLabel}
                        </p>
                      ) : null}
                    </div>
                  </>
                );

                if (!entry.runId) {
                  return (
                    <div
                      key={entry.id}
                      className={cellClasses}
                      title={`${preset.name} · ${displayLabel}`}
                    >
                      {content}
                    </div>
                  );
                }

                return (
                  <Link
                    key={entry.id}
                    to="/runs/$runId"
                    params={{ runId: entry.runId }}
                    className={cn(cellClasses, "cursor-pointer no-underline hover:brightness-95")}
                    aria-label={`Open ${preset.name} ${displayLabel} run detail (${metricLabel})`}
                    title={`${preset.name} · ${displayLabel} · ${metricLabel}`}
                  >
                    {content}
                  </Link>
                );
              })}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
