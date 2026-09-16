import { useState } from "react";
import { Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { type AccuracyVerdict } from "@/lib/results/accuracy";
import { cn } from "@/lib/utils";

export interface BenchmarkScatterExportPoint {
  moleculeKey: string;
  molecule: string;
  familyLabel: string;
  algorithm: string;
  runtime: number;
  absErrorMha: number;
  energy: number;
  verdict: AccuracyVerdict;
  runId: string | null;
  actualExecutionTarget?: string | null;
  actualPathClass?: string | null;
  primitiveFamily?: string | null;
  noiseSource?: string | null;
  noiseFingerprint?: string | null;
  workLedger?: Record<string, unknown> | null;
}

const SVG_NS = "http://www.w3.org/2000/svg";
const XHTML_NS = "http://www.w3.org/1999/xhtml";
const SCATTER_EXPORT_MARGIN = 12;

function runtimeMinutes(seconds: number): number {
  return seconds / 60;
}

function triggerFileDownload(fileName: string, blob: Blob): void {
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = fileName;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}

function downloadScatterCsv(points: readonly BenchmarkScatterExportPoint[]): void {
  const rows: string[][] = [
    [
      "molecule_key",
      "molecule",
      "family",
      "algorithm",
      "runtime_minutes",
      "abs_error_mha",
      "energy_ha",
      "verdict",
      "run_id",
      "actual_execution_target",
      "actual_path_class",
      "primitive_family",
      "noise_source",
      "noise_fingerprint",
      "work_ledger_json",
    ],
    ...points.map((point) => [
      point.moleculeKey,
      point.molecule,
      point.familyLabel,
      point.algorithm,
      runtimeMinutes(point.runtime).toString(),
      point.absErrorMha.toString(),
      point.energy.toString(),
      point.verdict,
      point.runId ?? "",
      point.actualExecutionTarget ?? "unknown",
      point.actualPathClass ?? "unknown",
      point.primitiveFamily ?? "unknown",
      point.noiseSource ?? "unknown",
      point.noiseFingerprint ?? "",
      point.workLedger == null ? "" : JSON.stringify(point.workLedger),
    ]),
  ];
  const csv = rows
    .map((row) => row.map((value) => `"${value.replaceAll('"', '""')}"`).join(","))
    .join("\n");

  triggerFileDownload(
    "benchmark-accuracy-vs-runtime-visible-points.csv",
    new Blob([csv], { type: "text/csv;charset=utf-8" }),
  );
}

function inlineScatterExportStyles(source: Element, target: Element): void {
  const computedStyle = getComputedStyle(source);
  const styleTarget = target as HTMLElement | SVGElement;
  styleTarget.setAttribute(
    "style",
    Array.from(computedStyle)
      .map((property) => `${property}:${computedStyle.getPropertyValue(property)};`)
      .join(""),
  );

  const sourceChildren = Array.from(source.children);
  const targetChildren = Array.from(target.children);
  sourceChildren.forEach((sourceChild, index) => {
    const targetChild = targetChildren[index];
    if (targetChild) {
      inlineScatterExportStyles(sourceChild, targetChild);
    }
  });
}

function cloneScatterPanelForExport(
  panel: HTMLDivElement,
  width: number,
  height: number,
): HTMLDivElement {
  const clone = panel.cloneNode(true);
  if (!(clone instanceof HTMLDivElement)) {
    throw new TypeError("Expected benchmark panel clone to be an HTMLDivElement");
  }

  inlineScatterExportStyles(panel, clone);
  clone.querySelectorAll("[data-scatter-export-exclude]").forEach((element) => {
    element.remove();
  });
  clone.setAttribute("xmlns", XHTML_NS);
  clone.style.margin = "0";
  clone.style.width = `${width}px`;
  clone.style.height = `${height}px`;
  clone.style.boxSizing = "border-box";
  clone.style.overflow = "hidden";
  return clone;
}

function downloadScatterSvg(panel: HTMLDivElement): void {
  const rect = panel.getBoundingClientRect();
  const width = Math.max(Math.ceil(rect.width), panel.scrollWidth, 1);
  const height = Math.max(Math.ceil(rect.height), panel.scrollHeight, 1);
  const svgWidth = width + SCATTER_EXPORT_MARGIN * 2;
  const svgHeight = height + SCATTER_EXPORT_MARGIN * 2;
  const root = document.createElementNS(SVG_NS, "svg");
  root.setAttribute("xmlns", SVG_NS);
  root.setAttribute("width", svgWidth.toString());
  root.setAttribute("height", svgHeight.toString());
  root.setAttribute("viewBox", `0 0 ${svgWidth} ${svgHeight}`);

  const foreignObject = document.createElementNS(SVG_NS, "foreignObject");
  foreignObject.setAttribute("x", SCATTER_EXPORT_MARGIN.toString());
  foreignObject.setAttribute("y", SCATTER_EXPORT_MARGIN.toString());
  foreignObject.setAttribute("width", width.toString());
  foreignObject.setAttribute("height", height.toString());
  foreignObject.append(cloneScatterPanelForExport(panel, width, height));
  root.append(foreignObject);

  const markup = new XMLSerializer().serializeToString(root);
  triggerFileDownload(
    "benchmark-accuracy-vs-runtime-visible-chart.svg",
    new Blob([markup], { type: "image/svg+xml;charset=utf-8" }),
  );
}

export function RuntimeScatterDownloads({
  points,
  panel,
}: Readonly<{
  points: readonly BenchmarkScatterExportPoint[];
  panel: HTMLDivElement | null;
}>) {
  const [open, setOpen] = useState(false);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          size="icon"
          className="size-8"
          aria-label="Download accuracy-vs-runtime chart exports"
          title="Download accuracy-vs-runtime chart exports"
        >
          <Download className="size-3.5" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-56 p-1" align="end">
        <div className="flex flex-col gap-0.5">
          <button
            type="button"
            className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-left text-sm hover:bg-accent"
            onClick={() => {
              downloadScatterCsv(points);
              setOpen(false);
            }}
          >
            <Download className="size-3.5 shrink-0 text-muted-foreground" />
            CSV (visible points)
          </button>
          <button
            type="button"
            disabled={panel == null}
            className={cn(
              "flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-left text-sm hover:bg-accent",
              panel == null && "cursor-not-allowed opacity-60 hover:bg-transparent",
            )}
            onClick={() => {
              if (panel == null) return;
              downloadScatterSvg(panel);
              setOpen(false);
            }}
          >
            <Download className="size-3.5 shrink-0 text-muted-foreground" />
            SVG (visible chart)
          </button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
