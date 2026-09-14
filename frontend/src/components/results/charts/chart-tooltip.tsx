import { overlaySurfaceSmClassName } from "@/lib/interactive-styles";
import { cn } from "@/lib/utils";

export interface ChartTooltipRow {
  readonly label: string;
  readonly value: string;
}

export interface ChartTooltipSection {
  readonly title?: string;
  readonly rows: readonly ChartTooltipRow[];
}

interface ChartTooltipProps {
  readonly x: number;
  readonly y: number;
  readonly title: string;
  readonly value?: string;
  readonly sections?: readonly ChartTooltipSection[];
  readonly horizontal?: "start" | "end";
  readonly vertical?: "top" | "bottom";
}

function buildChartTooltipSectionKey(section: ChartTooltipSection): string {
  return [
    section.title ?? "section",
    ...section.rows.map((row) => `${row.label}:${row.value}`),
  ].join("|");
}

export function ChartTooltip({
  x,
  y,
  title,
  value,
  sections,
  horizontal = "start",
  vertical = "top",
}: ChartTooltipProps) {
  const gap = 10;
  const translateX = horizontal === "end" ? "-100%" : "0";
  const translateY = vertical === "top" ? "-100%" : "0";
  const left = horizontal === "end" ? x - gap : x + gap;
  const top = vertical === "top" ? y - gap : y + gap;
  const renderedSections = sections ?? [];

  return (
    <div
      className={cn(
        "pointer-events-none absolute z-50 w-56 rounded-xl border px-3 py-2.5 text-xs text-popover-foreground shadow-lg backdrop-blur-sm",
        overlaySurfaceSmClassName,
      )}
      style={{ left, top, transform: `translate(${translateX}, ${translateY})` }}
    >
      <div className="space-y-2">
        <div className="space-y-1">
          <div className="text-[11px] font-medium text-muted-foreground">{title}</div>
          {value ? (
            <div className="font-mono text-sm font-semibold text-foreground">{value}</div>
          ) : null}
        </div>
        {renderedSections.map((section, index) => (
          <div
            key={buildChartTooltipSectionKey(section)}
            className={cn("space-y-1.5", index > 0 && "border-t border-border/70 pt-2")}
          >
            {section.title ? (
              <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground/80">
                {section.title}
              </div>
            ) : null}
            <div className="space-y-1">
              {section.rows.map((row) => (
                <div
                  key={`${row.label}-${row.value}`}
                  className="grid grid-cols-[4.5rem_minmax(0,1fr)] items-start gap-x-2"
                >
                  <div className="text-muted-foreground">{row.label}</div>
                  <div className="leading-snug text-foreground [overflow-wrap:anywhere]">
                    {row.value}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
