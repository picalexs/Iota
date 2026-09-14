import { useEffect, useMemo, type Dispatch, type ReactNode, type SetStateAction } from "react";
import { ArtifactPanel, type ArtifactPanelTab } from "@/components/results/artifact-panel";
import { ChartEmptyState } from "@/components/results/charts/chart-empty-state";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useLocalStorage } from "@/hooks/use-local-storage";
import { useTheme } from "@/hooks/use-theme";
import { cn } from "@/lib/utils";
import type { CircuitArtifact, CircuitPreview } from "@/types/run";

export interface BitstringOutcome {
  readonly bitstring: string;
  readonly probability: number;
  readonly count?: number | null;
}

type PanelMode = "outcomes" | "bits" | "circuit" | "qiskit" | "transpiled";
type OutcomeRepresentation = "binary" | "hex";
type OptionalCircuitPreview = CircuitPreview | null | undefined;

interface MeasurementOutcomesPanelProps {
  readonly outcomes: BitstringOutcome[];
  readonly artifacts?: CircuitArtifact[];
  readonly circuitPreview?: CircuitPreview | null;
  readonly stateKey: string;
  readonly artifactSelectorLabel?: string;
  readonly artifactLabelFormatter?: (artifact: CircuitArtifact, index: number) => string;
  readonly emptyMessage?: string;
  readonly maxRows?: number;
}

const EMPTY_ARTIFACTS: CircuitArtifact[] = [];
const MAX_CIRCUIT_SVG_LENGTH = 200_000;
const PANEL_STORAGE_KEY_PREFIX = "vqe-studio:artifact-panel:v1";
const ALLOWED_SVG_ELEMENTS = new Set([
  "svg",
  "g",
  "defs",
  "title",
  "desc",
  "path",
  "rect",
  "circle",
  "ellipse",
  "line",
  "polyline",
  "polygon",
  "text",
  "tspan",
  "clipPath",
  "mask",
  "linearGradient",
  "radialGradient",
  "stop",
  "style",
  "use",
]);
const ALLOWED_SVG_ATTRIBUTES = new Set([
  "aria-hidden",
  "class",
  "clip-path",
  "cx",
  "cy",
  "d",
  "dx",
  "dy",
  "fill",
  "fill-opacity",
  "font-family",
  "font-size",
  "height",
  "id",
  "mask",
  "offset",
  "opacity",
  "points",
  "r",
  "rx",
  "ry",
  "stroke",
  "stroke-dasharray",
  "stroke-linecap",
  "stroke-linejoin",
  "stroke-miterlimit",
  "stroke-opacity",
  "stroke-width",
  "style",
  "text-anchor",
  "transform",
  "type",
  "version",
  "viewBox",
  "width",
  "x",
  "x1",
  "x2",
  "xmlns",
  "xmlns:xlink",
  "y",
  "y1",
  "y2",
]);
const SVG_URL_ATTRIBUTE_NAMES = new Set(["href", "src", "xlink:href"]);
const UNSAFE_SVG_STYLE_PATTERN = /(?:\\|@import|expression\s*\(|url\s*\(\s*(?!["']?#))/i;

function isAllowedSvgReference(value: string): boolean {
  const trimmed = value.trim();
  return trimmed.length === 0 || trimmed.startsWith("#");
}

function isAllowedSvgAttribute(attribute: Attr): boolean {
  const name = attribute.name;
  if (name.toLowerCase().startsWith("on")) {
    return false;
  }

  if (SVG_URL_ATTRIBUTE_NAMES.has(name)) {
    return isAllowedSvgReference(attribute.value);
  }

  if (!ALLOWED_SVG_ATTRIBUTES.has(name)) {
    return false;
  }

  if (name === "style") {
    return UNSAFE_SVG_STYLE_PATTERN.test(attribute.value) === false;
  }

  return true;
}

function hasAllowedSvgElements(root: Element): boolean {
  return Array.from(root.querySelectorAll("*")).every((element) =>
    ALLOWED_SVG_ELEMENTS.has(element.localName),
  );
}

function hasAllowedSvgAttributes(element: Element): boolean {
  return Array.from(element.attributes).every(isAllowedSvgAttribute);
}

function hasSafeStyleElementContent(element: Element): boolean {
  if (element.localName === "style") {
    return UNSAFE_SVG_STYLE_PATTERN.test(element.textContent ?? "") === false;
  }
  return true;
}

function hasAllowedSvgTree(root: Element): boolean {
  return [root, ...Array.from(root.querySelectorAll("*"))].every(
    (element) => hasAllowedSvgAttributes(element) && hasSafeStyleElementContent(element),
  );
}

function sanitizeSvgMarkup(svg: string): string | null {
  if (typeof DOMParser === "undefined" || typeof XMLSerializer === "undefined") {
    return null;
  }

  const document = new DOMParser().parseFromString(svg, "image/svg+xml");
  if (document.querySelector("parsererror")) {
    return null;
  }

  const root = document.documentElement;
  if (root.localName !== "svg") {
    return null;
  }

  root.querySelectorAll("metadata").forEach((element) => element.remove());

  if (!hasAllowedSvgElements(root) || !hasAllowedSvgTree(root)) {
    return null;
  }

  return new XMLSerializer().serializeToString(root);
}

function groupBitstring(bitstring: string): string {
  return bitstring.replace(/\s+/g, "").replace(/(.{4})(?=.)/g, "$1 ");
}

function asHex(bitstring: string): string {
  const normalized = bitstring.replace(/\s+/g, "");
  const value = Number.parseInt(normalized, 2);
  if (!Number.isFinite(value)) return groupBitstring(bitstring);
  const width = Math.max(1, Math.ceil(normalized.length / 4));
  return `0x${value.toString(16).padStart(width, "0")}`;
}

function formatOutcome(bitstring: string, representation: OutcomeRepresentation): string {
  return representation === "hex" ? asHex(bitstring) : groupBitstring(bitstring);
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function qubitLabels(bitWidth: number): string[] {
  return Array.from({ length: bitWidth }, (_, index) => `q${bitWidth - index - 1}`);
}

function isPreviewAvailable(preview: OptionalCircuitPreview): boolean {
  return Boolean(preview?.diagram_svg || preview?.qasm);
}

function safeSvgImageSrc(svg: string): string | null {
  const trimmed = svg.trim();
  if (trimmed.length === 0 || trimmed.length > MAX_CIRCUIT_SVG_LENGTH) {
    return null;
  }
  const sanitized = sanitizeSvgMarkup(trimmed);
  if (sanitized === null) {
    return null;
  }
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(sanitized)}`;
}

function qiskitPreviewCode(preview: OptionalCircuitPreview): string | null {
  const qasm = preview?.qasm?.replaceAll("\r\n", "\n").trim();
  if (!qasm) return null;
  const escaped = qasm.replaceAll('"""', String.raw`\"\"\"`);
  return [
    '# If OpenQASM 3 import support is missing, install: pip install "qiskit[qasm3-import]"',
    "from qiskit import qasm3",
    "",
    'program = """',
    escaped,
    '"""',
    "",
    "circuit = qasm3.loads(program)",
    'circuit.draw(output="mpl")',
  ].join("\n");
}

function metadataChips(preview: OptionalCircuitPreview): string[] {
  if (!preview) return [];
  return [
    typeof preview.qubits === "number" ? `${preview.qubits}q` : null,
    typeof preview.classical_bits === "number" ? `${preview.classical_bits}c` : null,
    preview.style ?? null,
  ].flatMap((entry) => (entry ? [entry] : []));
}

function previewContent(
  preview: CircuitPreview,
  qiskitCode: string | null,
  dark: boolean,
): ReactNode {
  const svgSrc = preview.diagram_svg ? safeSvgImageSrc(preview.diagram_svg) : null;
  if (svgSrc) {
    return (
      <div
        className={cn(
          "min-h-0 flex-1 overflow-auto rounded-lg border p-2.5 shadow-inner sm:p-3",
          dark ? "border-white/10 bg-[#0f141b]" : "border-slate-200/80 bg-slate-100/85",
        )}
        data-testid="circuit-preview-surface"
      >
        <div
          className={cn(
            "flex min-h-full min-w-0 items-start justify-center rounded-md px-1 py-1 [&_svg]:h-auto [&_svg]:max-w-full [&_svg]:min-w-0 [&_svg]:w-auto",
            dark ? "bg-[#141b24]" : "bg-white/80",
            "[&_svg]:shrink-0 [&_svg_text]:font-sans [&_svg_text]:tracking-normal",
          )}
        >
          <img
            alt="Circuit diagram"
            className="h-auto max-h-full max-w-full object-contain"
            draggable={false}
            src={svgSrc}
          />
        </div>
      </div>
    );
  }

  if (qiskitCode) {
    return (
      <div className="flex h-full min-h-0 flex-col gap-2">
        <p className="text-[10px] leading-4 text-muted-foreground">
          SVG rendering was not persisted for this circuit, but the stored OpenQASM 3 program is
          available and can be reconstructed in Qiskit.
        </p>
        <pre
          className={cn(
            "h-full min-h-0 w-full overflow-auto rounded-lg border p-3 text-xs leading-5",
            dark
              ? "border-white/10 bg-[#0f141b] text-slate-200"
              : "border-slate-200/80 bg-slate-50 text-slate-700",
          )}
        >
          <code>{qiskitCode}</code>
        </pre>
      </div>
    );
  }

  return <ChartEmptyState message="Circuit diagram not available" />;
}

interface PreviewPanelOptions {
  readonly dark: boolean;
}

function previewPanel(preview: CircuitPreview, { dark }: PreviewPanelOptions): ReactNode {
  const chips = metadataChips(preview);
  const qiskitCode = qiskitPreviewCode(preview);
  return (
    <div className="flex h-full min-h-0 flex-col gap-2.5">
      {chips.length > 0 ? (
        <div className="flex flex-wrap items-center gap-1.5 text-[10px] text-muted-foreground">
          {chips.map((chip) => (
            <span
              key={chip}
              className={cn(
                "rounded-md border px-1.5 py-0.5",
                dark ? "border-white/10 bg-white/5 text-slate-300" : "border-slate-200 bg-white",
              )}
            >
              {chip}
            </span>
          ))}
        </div>
      ) : null}
      {previewContent(preview, qiskitCode, dark)}
    </div>
  );
}

function fallbackCircuitArtifacts(
  artifacts: CircuitArtifact[],
  circuitPreview: OptionalCircuitPreview,
): CircuitArtifact[] {
  if (artifacts.length > 0 || !circuitPreview) {
    return artifacts;
  }

  return [
    {
      id: "legacy-preview",
      role: "legacy",
      label: "Circuit",
      representative: true,
      logical: circuitPreview,
      preview: circuitPreview,
    },
  ];
}

function defaultArtifactId(artifacts: CircuitArtifact[]): string | null {
  const fallbackArtifact = artifacts.at(-1);
  return artifacts.find((artifact) => artifact.representative)?.id ?? fallbackArtifact?.id ?? null;
}

function availablePanelModes({
  hasOutcomes,
  logicalPreview,
  qiskitCode,
  transpiledPreview,
}: {
  readonly hasOutcomes: boolean;
  readonly logicalPreview: OptionalCircuitPreview;
  readonly qiskitCode: string | null;
  readonly transpiledPreview: OptionalCircuitPreview;
}): PanelMode[] {
  const modes: PanelMode[] = [];
  if (hasOutcomes) {
    modes.push("outcomes", "bits");
  }
  if (isPreviewAvailable(logicalPreview) && logicalPreview?.diagram_svg) {
    modes.push("circuit");
  }
  if (qiskitCode) {
    modes.push("qiskit");
  }
  if (isPreviewAvailable(transpiledPreview)) {
    modes.push("transpiled");
  }
  return modes;
}

function preferredDefaultPanelMode(availableModes: PanelMode[]): PanelMode | null {
  if (availableModes.length === 0) {
    return null;
  }

  if (availableModes.includes("circuit")) {
    return "circuit";
  }

  return availableModes[0] ?? null;
}

function ArtifactSelector({
  artifacts,
  artifactSelectorLabel,
  artifactLabelFormatter,
  selectedArtifactId,
  setSelectedArtifactId,
}: Readonly<{
  readonly artifacts: CircuitArtifact[];
  readonly artifactSelectorLabel: string;
  readonly artifactLabelFormatter?: (artifact: CircuitArtifact, index: number) => string;
  readonly selectedArtifactId: string | null;
  readonly setSelectedArtifactId: Dispatch<SetStateAction<string | null>>;
}>): ReactNode {
  if (artifacts.length <= 1) {
    return null;
  }

  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] font-medium text-muted-foreground">{artifactSelectorLabel}</span>
      <Select value={selectedArtifactId ?? undefined} onValueChange={setSelectedArtifactId}>
        <SelectTrigger size="sm" className="h-8 min-w-[8.5rem] px-2.5 text-xs">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {artifacts.map((artifact, index) => (
            <SelectItem key={artifact.id ?? index} value={artifact.id ?? String(index)}>
              {artifactLabelFormatter?.(artifact, index) ??
                artifact.label ??
                artifact.id ??
                `Circuit ${index + 1}`}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

function outcomeTab({
  normalizedOutcomes,
  representation,
  setRepresentation,
}: Readonly<{
  readonly normalizedOutcomes: BitstringOutcome[];
  readonly representation: OutcomeRepresentation;
  readonly setRepresentation: Dispatch<SetStateAction<OutcomeRepresentation>>;
}>): ArtifactPanelTab {
  return {
    id: "outcomes",
    label: "Outcomes",
    actions: (
      <div className="flex items-center gap-1 rounded-md border border-border/60 bg-muted/20 p-1">
        {(["binary", "hex"] as const).map((entry) => (
          <Button
            key={entry}
            variant={representation === entry ? "secondary" : "ghost"}
            size="sm"
            className="h-7 px-2.5 text-xs uppercase"
            onClick={() => setRepresentation(entry)}
          >
            {entry}
          </Button>
        ))}
      </div>
    ),
    content: (
      <div className="min-h-0 space-y-2 overflow-auto pr-1">
        {normalizedOutcomes.map((entry) => (
          <div key={entry.bitstring} className="space-y-1.5">
            <div className="flex items-center justify-between gap-3 text-[11px]">
              <code className="min-w-0 truncate rounded bg-muted px-1.5 py-0.5 font-mono">
                {formatOutcome(entry.bitstring, representation)}
              </code>
              <div className="flex items-center gap-2 whitespace-nowrap font-mono tabular-nums text-muted-foreground">
                {outcomeCountLabel(entry.count)}
                <span>{formatPercent(entry.probability)}</span>
              </div>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-muted/50">
              <div
                className="h-full rounded-full bg-[var(--chart-1)]/85"
                style={{ width: `${Math.max(entry.probability * 100, 2)}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    ),
  };
}

function bitsTab({
  normalizedOutcomes,
  bitWidth,
  labels,
}: Readonly<{
  readonly normalizedOutcomes: BitstringOutcome[];
  readonly bitWidth: number;
  readonly labels: string[];
}>): ArtifactPanelTab {
  return {
    id: "bits",
    label: "Bits",
    content: (
      <div className="min-h-0 overflow-auto rounded-md border border-border/60">
        <div
          className="grid min-w-max gap-px bg-border/60 p-px"
          style={{
            gridTemplateColumns: `minmax(7rem,auto) repeat(${bitWidth}, minmax(1.75rem, 1fr)) minmax(4.5rem,auto)`,
          }}
        >
          <div className="bg-background px-2 py-1 text-[10px] font-medium text-muted-foreground">
            Outcome
          </div>
          {labels.map((label) => (
            <div
              key={label}
              className="bg-background px-1 py-1 text-center text-[10px] font-medium text-muted-foreground"
            >
              {label}
            </div>
          ))}
          <div className="bg-background px-2 py-1 text-right text-[10px] font-medium text-muted-foreground">
            Prob.
          </div>

          {normalizedOutcomes.map((entry) => (
            <FragmentRow
              key={entry.bitstring}
              bits={entry.bitstring.replace(/\s+/g, "").split("")}
              bitstring={groupBitstring(entry.bitstring)}
              probability={entry.probability}
            />
          ))}
        </div>
      </div>
    ),
  };
}

function qiskitTab(qiskitCode: string, isDarkTheme: boolean): ArtifactPanelTab {
  return {
    id: "qiskit",
    label: "Qiskit",
    content: (
      <div className="flex h-full min-h-0 flex-col gap-2">
        <p className="text-[10px] leading-4 text-muted-foreground">
          Rebuild the stored OpenQASM 3 program as a Qiskit circuit, then render it with the
          Matplotlib drawer.
        </p>
        <pre
          className={cn(
            "h-full min-h-0 w-full overflow-auto rounded-lg border p-3 text-xs leading-5",
            isDarkTheme
              ? "border-white/10 bg-[#0f141b] text-slate-200"
              : "border-slate-200/80 bg-slate-50 text-slate-700",
          )}
        >
          <code>{qiskitCode}</code>
        </pre>
      </div>
    ),
  };
}

function buildPanelTabs({
  availableModes,
  normalizedOutcomes,
  representation,
  setRepresentation,
  bitWidth,
  labels,
  logicalPreview,
  qiskitCode,
  transpiledPreview,
  isDarkTheme,
}: Readonly<{
  readonly availableModes: PanelMode[];
  readonly normalizedOutcomes: BitstringOutcome[];
  readonly representation: OutcomeRepresentation;
  readonly setRepresentation: Dispatch<SetStateAction<OutcomeRepresentation>>;
  readonly bitWidth: number;
  readonly labels: string[];
  readonly logicalPreview: OptionalCircuitPreview;
  readonly qiskitCode: string | null;
  readonly transpiledPreview: OptionalCircuitPreview;
  readonly isDarkTheme: boolean;
}>): ArtifactPanelTab[] {
  const tabs: ArtifactPanelTab[] = [];
  if (availableModes.includes("outcomes")) {
    tabs.push(outcomeTab({ normalizedOutcomes, representation, setRepresentation }));
  }
  if (availableModes.includes("bits")) {
    tabs.push(bitsTab({ normalizedOutcomes, bitWidth, labels }));
  }
  if (availableModes.includes("circuit") && logicalPreview) {
    tabs.push({
      id: "circuit",
      label: "Circuit",
      content: previewPanel(logicalPreview, { dark: isDarkTheme }),
    });
  }
  if (availableModes.includes("qiskit") && qiskitCode) {
    tabs.push(qiskitTab(qiskitCode, isDarkTheme));
  }
  if (availableModes.includes("transpiled") && transpiledPreview) {
    tabs.push({
      id: "transpiled",
      label: "Transpiled",
      content: previewPanel(transpiledPreview, { dark: isDarkTheme }),
    });
  }
  return tabs;
}

export function MeasurementOutcomesPanel({
  outcomes,
  artifacts = EMPTY_ARTIFACTS,
  circuitPreview,
  stateKey,
  artifactSelectorLabel = "Circuit",
  artifactLabelFormatter,
  emptyMessage = "No measurement outcomes recorded",
  maxRows = 8,
}: MeasurementOutcomesPanelProps) {
  const { resolvedTheme } = useTheme();
  const fallbackArtifacts = useMemo<CircuitArtifact[]>(
    () => fallbackCircuitArtifacts(artifacts, circuitPreview),
    [artifacts, circuitPreview],
  );
  const storageRoot = `${PANEL_STORAGE_KEY_PREFIX}:${stateKey}`;
  const [representation, setRepresentation] = useLocalStorage<OutcomeRepresentation>(
    `${storageRoot}:representation`,
    "binary",
  );
  const [selectedArtifactId, setSelectedArtifactId] = useLocalStorage<string | null>(
    `${storageRoot}:artifact`,
    defaultArtifactId(fallbackArtifacts),
  );
  const [selectedTabId, setSelectedTabId] = useLocalStorage<string | null>(
    `${storageRoot}:tab`,
    null,
  );

  useEffect(() => {
    const nextId = defaultArtifactId(fallbackArtifacts);
    const selectedExists = fallbackArtifacts.some((artifact) => artifact.id === selectedArtifactId);
    if (!selectedExists && selectedArtifactId !== nextId) {
      setSelectedArtifactId(nextId);
    }
  }, [fallbackArtifacts, selectedArtifactId, setSelectedArtifactId]);

  const selectedArtifact =
    fallbackArtifacts.find((artifact) => artifact.id === selectedArtifactId) ??
    fallbackArtifacts[0] ??
    null;
  const logicalPreview =
    selectedArtifact?.logical ?? selectedArtifact?.preview ?? circuitPreview ?? null;
  const qiskitCode = qiskitPreviewCode(logicalPreview);
  const transpiledPreview =
    selectedArtifact?.transpiled ?? selectedArtifact?.transpiled_preview ?? null;
  const isDarkTheme = resolvedTheme === "dark";

  const normalizedOutcomes = useMemo(
    () =>
      [...outcomes]
        .filter((entry) => entry.bitstring.length > 0 && entry.probability > 0)
        .sort((left, right) => right.probability - left.probability)
        .slice(0, maxRows),
    [maxRows, outcomes],
  );
  const bitWidth = normalizedOutcomes[0]?.bitstring.replace(/\s+/g, "").length ?? 0;
  const labels = qubitLabels(bitWidth);

  const availableModes = availablePanelModes({
    hasOutcomes: normalizedOutcomes.length > 0,
    logicalPreview,
    qiskitCode,
    transpiledPreview,
  });
  const defaultTabId = preferredDefaultPanelMode(availableModes);

  useEffect(() => {
    if (!defaultTabId) {
      return;
    }
    if (selectedTabId && availableModes.includes(selectedTabId as PanelMode)) {
      return;
    }
    setSelectedTabId(defaultTabId);
  }, [availableModes, defaultTabId, selectedTabId, setSelectedTabId]);

  if (availableModes.length === 0) {
    return <ChartEmptyState message={emptyMessage} />;
  }

  const headerActions = (
    <ArtifactSelector
      artifacts={fallbackArtifacts}
      artifactSelectorLabel={artifactSelectorLabel}
      artifactLabelFormatter={artifactLabelFormatter}
      selectedArtifactId={selectedArtifact?.id ?? selectedArtifactId}
      setSelectedArtifactId={setSelectedArtifactId}
    />
  );
  const tabs = buildPanelTabs({
    availableModes,
    normalizedOutcomes,
    representation,
    setRepresentation,
    bitWidth,
    labels,
    logicalPreview,
    qiskitCode,
    transpiledPreview,
    isDarkTheme,
  });

  return (
    <ArtifactPanel
      tabs={tabs}
      defaultTabId={defaultTabId ?? undefined}
      activeTabId={selectedTabId}
      onActiveTabChange={setSelectedTabId}
      emptyMessage={emptyMessage}
      contentClassName="overflow-hidden"
      headerActions={headerActions}
      tabsClassName="bg-background/70"
    />
  );
}

function FragmentRow({
  bits,
  bitstring,
  probability,
}: Readonly<{
  readonly bits: string[];
  readonly bitstring: string;
  readonly probability: number;
}>) {
  return (
    <>
      <div className="bg-background px-2 py-1.5 text-[11px]">
        <code className="font-mono">{bitstring}</code>
      </div>
      {bits.map((bit, index) => {
        const bitKey = `${bitstring}-bit-${index}`;
        return (
          <div key={bitKey} className="bg-background p-1">
            <div
              className={cn(
                "flex h-7 items-center justify-center rounded text-[11px] font-semibold",
                bit === "1"
                  ? "bg-[var(--chart-1)]/20 text-foreground"
                  : "bg-muted/50 text-muted-foreground",
              )}
            >
              {bit}
            </div>
          </div>
        );
      })}
      <div className="bg-background px-2 py-1.5 text-right text-[11px] font-mono tabular-nums text-muted-foreground">
        {formatPercent(probability)}
      </div>
    </>
  );
}
function outcomeCountLabel(count: number | null | undefined) {
  if (count == null) {
    return null;
  }
  return <span>{count.toLocaleString()}</span>;
}
