import { useState } from "react";
import { Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import type { RunResponse, RunResultResponse, RunEventResponse } from "@/types/run";
import { mergeConvergenceTrace } from "@/lib/results/convergence-from-events";

interface ExportDropdownProps {
  readonly run: RunResponse;
  readonly result: RunResultResponse | null;
  readonly events: RunEventResponse[];
}

function isSlugCharacter(char: string): boolean {
  const code = char.codePointAt(0) ?? 0;
  return (code >= 48 && code <= 57) || (code >= 97 && code <= 122);
}

function slugify(value: string): string {
  let slug = "";
  let pendingSeparator = false;

  for (const char of value.trim().toLowerCase()) {
    if (isSlugCharacter(char)) {
      if (pendingSeparator && slug.length > 0) {
        slug += "-";
      }
      slug += char;
      pendingSeparator = false;
    } else if (slug.length > 0) {
      pendingSeparator = true;
    }
  }

  return slug;
}

function downloadJson(filename: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function downloadCsv(filename: string, rows: string[][]) {
  const csv = rows.map((r) => r.join(",")).join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function downloadSvg(filename: string, svg: SVGSVGElement) {
  const clone = svg.cloneNode(true);
  if (!(clone instanceof SVGSVGElement)) return;
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  const markup = new XMLSerializer().serializeToString(clone);
  const blob = new Blob([markup], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function ExportDropdown({ run, result, events }: ExportDropdownProps) {
  const [open, setOpen] = useState(false);
  const slug = `${run.algorithm ?? "run"}-${run.id.slice(0, 8)}`;

  const handleJsonBundle = () => {
    downloadJson(`${slug}-bundle.json`, { run, result, events });
    setOpen(false);
  };

  const handleCsvConvergence = () => {
    const points = mergeConvergenceTrace(events, result?.algorithm_metrics ?? null);
    const rows: string[][] = [
      ["iteration", "energy_ha", "delta_energy", "parameter_l2_norm"],
      ...points.map((p) => [
        String(p.iteration),
        String(p.energy),
        String(p.deltaEnergy ?? ""),
        String(p.parameterL2Norm ?? ""),
      ]),
    ];
    downloadCsv(`${slug}-convergence.csv`, rows);
    setOpen(false);
  };

  const handleCsvParameters = () => {
    if (!result || result.optimal_parameters.length === 0) return;
    const rows: string[][] = [
      ["index", "value_radians"],
      ...result.optimal_parameters.map((v, i) => [String(i), String(v)]),
    ];
    downloadCsv(`${slug}-parameters.csv`, rows);
    setOpen(false);
  };

  const handleAllPlots = () => {
    const dashboardRoot = document.querySelector("[data-results-dashboard-root]");
    if (dashboardRoot == null) return;

    const plotContainers = Array.from(
      dashboardRoot.querySelectorAll<HTMLElement>("svg[aria-label]"),
    );

    plotContainers.forEach((container, index) => {
      const svg =
        container instanceof SVGSVGElement
          ? container
          : container.querySelector<SVGSVGElement>("svg");
      if (svg == null) return;

      const tile = container.closest<HTMLElement>("[data-dashboard-tile]");
      const tileTitle = tile?.dataset.tileTitle ?? "plot";
      const ariaLabel = container.getAttribute("aria-label") ?? `plot-${index + 1}`;
      downloadSvg(`${slug}-${slugify(tileTitle)}-${slugify(ariaLabel)}.svg`, svg);
    });

    setOpen(false);
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className="h-8 gap-1.5 text-xs">
          <Download className="size-3.5" />
          Export
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-56 p-1" align="end">
        <div className="flex flex-col gap-0.5">
          <button
            type="button"
            className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-left text-sm hover:bg-accent"
            onClick={handleJsonBundle}
          >
            <Download className="size-3.5 shrink-0 text-muted-foreground" />
            JSON bundle
          </button>
          <button
            type="button"
            className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-left text-sm hover:bg-accent"
            onClick={handleCsvConvergence}
          >
            <Download className="size-3.5 shrink-0 text-muted-foreground" />
            CSV (convergence trace)
          </button>
          <button
            type="button"
            className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-left text-sm hover:bg-accent"
            onClick={handleAllPlots}
          >
            <Download className="size-3.5 shrink-0 text-muted-foreground" />
            SVG (all visible plots)
          </button>
          {result && result.optimal_parameters.length > 0 && (
            <button
              type="button"
              className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-left text-sm hover:bg-accent"
              onClick={handleCsvParameters}
            >
              <Download className="size-3.5 shrink-0 text-muted-foreground" />
              CSV (optimal parameters)
            </button>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
