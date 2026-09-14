/** Benchmark molecule and algorithm selection sections. */

import { BENCHMARK_ALGORITHMS, type MoleculePreset } from "@/lib/benchmark-presets";
import type { MoleculeResponse, RunAlgorithm } from "@/types/run";
import { Button } from "@/components/ui/button";
import { SelectableCard } from "@/components/ui/selectable-card";
import { Spinner } from "@/components/ui/spinner";
import { CheckCircle2, Dice6, FlaskConical, SlidersHorizontal, Trash2 } from "lucide-react";
import { elevatedSurfaceClassName, selectableSurfaceClassName } from "@/lib/interactive-styles";
import { cn } from "@/lib/utils";
import { getBenchmarkMoleculeBlocker } from "./benchmark-utils";
import { MoleculeSearchPopover } from "./molecule-search-popover";

const BENCHMARK_TOOLBAR_BUTTON_CLASS =
  "h-9 rounded-lg border-border/80 bg-surface-raised-hover px-4 text-foreground shadow-none hover:bg-surface-raised-hover active:bg-surface-raised-hover";
const BENCHMARK_TOOLBAR_ICON_BUTTON_CLASS =
  "h-9 w-9 rounded-lg border-border/80 bg-surface-raised-hover text-foreground shadow-none hover:bg-surface-raised-hover active:bg-surface-raised-hover";
const BENCHMARK_TOOLBAR_DANGER_ICON_BUTTON_CLASS =
  "h-9 w-9 rounded-lg border-border/80 bg-surface-raised-hover text-muted-foreground shadow-none hover:border-destructive/60 hover:bg-surface-raised-hover hover:text-destructive active:bg-surface-raised-hover";
const ALGORITHM_SUMMARIES: Record<RunAlgorithm, string> = {
  vqe: "Variational",
  sqd: "Sample-based",
  kqd: "Krylov",
  qfd: "Filter",
  qse: "Subspace",
  skqd: "SQD-seeded Krylov",
};

function formatReferenceEnergy(preset: MoleculePreset): string {
  if (preset.references.fci === null) return "No ref";
  return "Ref " + preset.references.fci.toFixed(5) + " Ha";
}

function formatActiveSpace(preset: MoleculePreset): string {
  if (preset.active_space === null || preset.active_space === undefined) return "No active space";
  return (
    String(preset.active_space.n_electrons) + "e / " + String(preset.active_space.n_orbitals) + "o"
  );
}

function formatAsciiFormula(value: string): string {
  return value.replace(/[₀-₉]/g, (digit) => String("₀₁₂₃₄₅₆₇₈₉".indexOf(digit)));
}

function formatMoleculeCardLabel(preset: MoleculePreset): string {
  const formula = formatAsciiFormula(preset.formula || preset.name);
  return formula + " " + preset.name;
}

function formatBaseMoleculeName(name: string): string {
  const trimmed = name.trim();
  if (!trimmed.endsWith(")")) {
    return trimmed;
  }
  const aliasStart = trimmed.lastIndexOf("(");
  if (aliasStart <= 0) {
    return trimmed;
  }
  return trimmed.slice(0, aliasStart).trimEnd();
}

function renderMoleculeAlias(value: string, visibleValue: string) {
  if (value === visibleValue) return null;
  return <span className="sr-only">{value}</span>;
}

function isMoleculeOptionDisabled(
  workspaceLocked: boolean,
  blocker: string | null,
  selected: boolean,
): boolean {
  if (workspaceLocked) return true;
  if (selected) return false;
  return blocker !== null;
}

function MoleculeOptionCard({
  preset,
  selected,
  disabled,
  blocker,
  isCustom,
  onToggle,
  onDelete,
}: Readonly<{
  preset: MoleculePreset;
  selected: boolean;
  disabled: boolean;
  blocker: string | null;
  isCustom: boolean;
  onToggle: () => void;
  onDelete?: () => void;
}>) {
  const visibleFormula = preset.formula || preset.name;
  const asciiFormula = formatAsciiFormula(visibleFormula);
  const baseName = formatBaseMoleculeName(preset.name);

  return (
    <div
      data-selected={selected ? "true" : "false"}
      className={cn(
        "group/selectable-card relative flex w-full rounded-xl text-left",
        elevatedSurfaceClassName,
        selectableSurfaceClassName,
        disabled && "cursor-not-allowed opacity-60",
        "min-h-[5.15rem] p-3 data-[selected=false]:!border-border/80 data-[selected=false]:!bg-surface-raised data-[selected=false]:hover:!border-interactive-hover-border data-[selected=false]:hover:!bg-interactive-hover",
      )}
    >
      <button
        type="button"
        data-selected={selected ? "true" : "false"}
        className={cn(
          "absolute inset-0 rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-strong focus-visible:ring-offset-2",
          "data-[selected=false]:!bg-surface-raised",
        )}
        aria-label={formatMoleculeCardLabel(preset)}
        disabled={disabled}
        onClick={onToggle}
      />
      {renderMoleculeAlias(asciiFormula, visibleFormula)}
      {renderMoleculeAlias(baseName, preset.name)}
      <div className="pointer-events-none relative flex w-full items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 items-center gap-2">
            <span className="text-base font-semibold tracking-tight">{visibleFormula}</span>
            <span className="truncate text-xs text-muted-foreground">{preset.name}</span>
          </div>
          <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
            <span>{formatActiveSpace(preset)}</span>
            <span>{formatReferenceEnergy(preset)}</span>
          </div>
          {blocker ? <p className="mt-1 text-[11px] text-warning">{blocker}</p> : null}
        </div>
        <div className="flex items-center gap-1">
          {onDelete ? (
            <button
              type="button"
              className="pointer-events-auto rounded-md p-1 text-[rgb(148,163,184)] opacity-0 transition-[color,opacity] hover:text-[rgb(239,68,68)] focus-visible:opacity-100 group-hover/selectable-card:opacity-100 group-focus-within/selectable-card:opacity-100"
              onClick={(event) => {
                event.stopPropagation();
                onDelete();
              }}
              aria-label={(isCustom ? "Delete" : "Remove") + " " + preset.name + " from benchmark"}
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          ) : null}
          <div
            className={cn(
              "flex h-5 w-5 shrink-0 items-center justify-center rounded-full border",
              selected
                ? "border-primary/40 bg-primary/15 text-primary"
                : "border-border/80 bg-background text-transparent",
            )}
          >
            <CheckCircle2 className="h-3.5 w-3.5" />
          </div>
        </div>
      </div>
    </div>
  );
}

export function BenchmarkMoleculeSection({
  selectedMolecules,
  visibleMoleculeOptions,
  workspaceLocked,
  randomLibraryLoading,
  randomLibraryMessage,
  hasVisibleMolecules,
  onRandomLibrary,
  onDeleteAll,
  onAddCustomMolecule,
  onToggleMolecule,
  onDeleteMolecule,
}: Readonly<{
  selectedMolecules: ReadonlySet<string>;
  visibleMoleculeOptions: readonly MoleculePreset[];
  workspaceLocked: boolean;
  randomLibraryLoading: boolean;
  randomLibraryMessage: string | null;
  hasVisibleMolecules: boolean;
  onRandomLibrary: () => void;
  onDeleteAll: () => void;
  onAddCustomMolecule: (molecule: MoleculeResponse) => void;
  onToggleMolecule: (key: string) => void;
  onDeleteMolecule: (preset: MoleculePreset) => void;
}>) {
  return (
    <section className="space-y-3 rounded-xl border border-border/80 bg-card p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <FlaskConical className="h-4 w-4 text-muted-foreground" />
            Molecules
          </div>
          {selectedMolecules.size === 0 ? (
            <p className="text-xs text-muted-foreground">No molecules selected yet.</p>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            size="icon"
            variant="outline"
            className={BENCHMARK_TOOLBAR_ICON_BUTTON_CLASS}
            disabled={workspaceLocked || randomLibraryLoading}
            aria-label="Random 6"
            onClick={onRandomLibrary}
          >
            {randomLibraryLoading ? <Spinner /> : <Dice6 className="h-4 w-4" />}
            <span className="sr-only">Random 6</span>
          </Button>
          <MoleculeSearchPopover
            onAdd={onAddCustomMolecule}
            disabled={workspaceLocked}
            triggerClassName={BENCHMARK_TOOLBAR_BUTTON_CLASS}
          />
          {hasVisibleMolecules ? (
            <Button
              type="button"
              size="icon"
              variant="outline"
              className={BENCHMARK_TOOLBAR_DANGER_ICON_BUTTON_CLASS}
              disabled={workspaceLocked}
              aria-label="Delete all molecules"
              onClick={onDeleteAll}
            >
              <Trash2 className="h-4 w-4" />
              <span className="sr-only">Delete all molecules</span>
            </Button>
          ) : null}
        </div>
      </div>
      {randomLibraryMessage ? (
        <p className="text-xs text-muted-foreground">{randomLibraryMessage}</p>
      ) : null}
      <div className="grid gap-3 xl:grid-cols-2">
        {visibleMoleculeOptions.map((preset) => {
          const selected = selectedMolecules.has(preset.key);
          const blocker = getBenchmarkMoleculeBlocker(preset);
          return (
            <MoleculeOptionCard
              key={preset.key}
              preset={preset}
              selected={selected}
              disabled={isMoleculeOptionDisabled(workspaceLocked, blocker, selected)}
              blocker={blocker}
              isCustom={preset.key.startsWith("custom:")}
              onToggle={() => onToggleMolecule(preset.key)}
              onDelete={workspaceLocked ? undefined : () => onDeleteMolecule(preset)}
            />
          );
        })}
      </div>
    </section>
  );
}

function AlgorithmOptionCard({
  algorithm,
  selected,
  disabled,
  disabledReason,
  onToggle,
}: Readonly<{
  algorithm: (typeof BENCHMARK_ALGORITHMS)[number];
  selected: boolean;
  disabled: boolean;
  disabledReason?: string;
  onToggle: () => void;
}>) {
  return (
    <SelectableCard
      selected={selected}
      disabled={disabled}
      onClick={onToggle}
      className="min-h-[4.4rem] p-3 data-[selected=false]:!border-border/80 data-[selected=false]:!bg-surface-raised data-[selected=false]:hover:!border-interactive-hover-border data-[selected=false]:hover:!bg-interactive-hover"
    >
      <div className="flex w-full items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold">{algorithm.label}</span>
            <span className="font-mono text-[11px] uppercase text-muted-foreground">
              {algorithm.value}
            </span>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {disabledReason ?? ALGORITHM_SUMMARIES[algorithm.value]}
          </p>
        </div>
        <div
          className={cn(
            "mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border",
            selected
              ? "border-primary/40 bg-primary/15 text-primary"
              : "border-border/80 bg-background text-transparent",
          )}
        >
          <CheckCircle2 className="h-3.5 w-3.5" />
        </div>
      </div>
    </SelectableCard>
  );
}

export function BenchmarkAlgorithmSection({
  noAlgorithmsSelected,
  workspaceLocked,
  selectedAlgorithms,
  disabledAlgorithms,
  onSetAlgorithms,
  onToggleAlgorithm,
}: Readonly<{
  noAlgorithmsSelected: boolean;
  workspaceLocked: boolean;
  selectedAlgorithms: ReadonlySet<RunAlgorithm>;
  disabledAlgorithms: ReadonlyMap<RunAlgorithm, string>;
  onSetAlgorithms: (algorithms: RunAlgorithm[]) => void;
  onToggleAlgorithm: (algorithm: RunAlgorithm) => void;
}>) {
  const enabledAlgorithmValues = BENCHMARK_ALGORITHMS.filter(
    (algorithm) => !disabledAlgorithms.has(algorithm.value),
  ).map((algorithm) => algorithm.value);
  const allEnabledAlgorithmsSelected =
    selectedAlgorithms.size === enabledAlgorithmValues.length &&
    enabledAlgorithmValues.every((algorithm) => selectedAlgorithms.has(algorithm));

  return (
    <section className="space-y-3 rounded-xl border border-border/80 bg-card p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <SlidersHorizontal className="h-4 w-4 text-muted-foreground" />
          Algorithms
        </div>
        <div className="flex gap-2">
          <Button
            type="button"
            size="sm"
            variant={allEnabledAlgorithmsSelected ? "secondary" : "outline"}
            className={cn(
              "h-9 min-w-16 rounded-lg px-4",
              !allEnabledAlgorithmsSelected && "bg-surface-raised-hover",
            )}
            disabled={workspaceLocked}
            onClick={() => onSetAlgorithms(enabledAlgorithmValues)}
          >
            All
          </Button>
          <Button
            type="button"
            size="sm"
            variant={noAlgorithmsSelected ? "secondary" : "outline"}
            className={cn(
              "h-9 min-w-16 rounded-lg px-4",
              !noAlgorithmsSelected && "bg-surface-raised-hover",
            )}
            disabled={workspaceLocked}
            onClick={() => onSetAlgorithms([])}
          >
            None
          </Button>
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {BENCHMARK_ALGORITHMS.map((algorithm) => {
          const disabledReason = disabledAlgorithms.get(algorithm.value);
          const isDisabled = workspaceLocked || disabledReason !== undefined;
          return (
            <AlgorithmOptionCard
              key={algorithm.value}
              algorithm={algorithm}
              selected={selectedAlgorithms.has(algorithm.value)}
              disabled={isDisabled}
              disabledReason={disabledReason}
              onToggle={() => onToggleAlgorithm(algorithm.value)}
            />
          );
        })}
      </div>
    </section>
  );
}
