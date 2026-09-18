import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, Minus, Plus, SlidersHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { BENCHMARK_ALGORITHMS } from "@/lib/benchmark-presets";
import type { RunAlgorithm } from "@/types/run";
import { BenchmarkVariantEditor } from "./benchmark-variant-editor";
import type { BenchmarkAlgorithmVariant } from "./benchmark-variants";

function BenchmarkAdvancedVariantGroup({
  algorithm,
  variants,
  chemicalAccuracyHa,
  requiresBranchEstimator,
  disabled,
  collapseEditors,
  onDuplicateAdvancedVariant,
  onUpdateAdvancedVariant,
  onRemoveAdvancedVariant,
}: Readonly<{
  algorithm: RunAlgorithm;
  variants: readonly BenchmarkAlgorithmVariant[];
  chemicalAccuracyHa: number;
  requiresBranchEstimator: boolean;
  disabled: boolean;
  collapseEditors: boolean;
  onDuplicateAdvancedVariant: (variantId: string) => void;
  onUpdateAdvancedVariant: (
    variantId: string,
    updater: (variant: BenchmarkAlgorithmVariant) => BenchmarkAlgorithmVariant,
  ) => void;
  onRemoveAdvancedVariant: (variantId: string) => void;
}>) {
  const [expanded, setExpanded] = useState(!collapseEditors);
  const previousCollapseEditorsRef = useRef(collapseEditors);

  useEffect(() => {
    if (collapseEditors && !previousCollapseEditorsRef.current) {
      setExpanded(false);
    }
    previousCollapseEditorsRef.current = collapseEditors;
  }, [collapseEditors]);

  return (
    <section className="rounded-xl border border-border/80 bg-background/35">
      <div className="flex flex-wrap items-start justify-between gap-3 px-4 py-3">
        <div className="min-w-0 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold">{algorithm.toUpperCase()}</span>
            <span className="font-mono text-[11px] uppercase text-muted-foreground">
              {algorithm}
            </span>
            <span className="rounded-full border border-border/80 bg-background px-2 py-0.5 text-[11px] font-medium text-muted-foreground">
              {variants.length} row{variants.length === 1 ? "" : "s"}
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            {variants.map((variant) => (
              <span
                key={variant.id}
                className="rounded-full border border-border/80 bg-background px-2.5 py-1 text-[11px] font-medium text-muted-foreground"
              >
                {variant.label}
              </span>
            ))}
          </div>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          aria-expanded={expanded}
          aria-label={`${expanded ? "Collapse" : "Expand"} ${algorithm.toUpperCase()} rows`}
          onClick={() => setExpanded((value) => !value)}
        >
          {expanded ? "Collapse rows" : "Expand rows"}
          <ChevronDown className={cn("size-4 transition-transform", expanded && "rotate-180")} />
        </Button>
      </div>

      {expanded ? (
        <div className="grid gap-4 border-t border-border/70 px-4 py-4">
          {variants.map((variant) => (
            <BenchmarkVariantEditor
              key={variant.id}
              variant={variant}
              chemicalAccuracyHa={chemicalAccuracyHa}
              requiresBranchEstimator={requiresBranchEstimator}
              disabled={disabled}
              autoCollapse={collapseEditors}
              onChange={(nextVariant) => onUpdateAdvancedVariant(variant.id, () => nextVariant)}
              onDuplicate={() => onDuplicateAdvancedVariant(variant.id)}
              onRemove={() => onRemoveAdvancedVariant(variant.id)}
            />
          ))}
        </div>
      ) : null}
    </section>
  );
}

export function BenchmarkAdvancedAlgorithmSection({
  workspaceLocked,
  running,
  total,
  disabledAlgorithms,
  algorithmVariants,
  chemicalAccuracyHa,
  requiresBranchEstimator,
  onAddAdvancedVariant,
  onSetAdvancedVariantCount,
  onDuplicateAdvancedVariant,
  onUpdateAdvancedVariant,
  onRemoveAdvancedVariant,
}: Readonly<{
  workspaceLocked: boolean;
  running: boolean;
  total: number;
  disabledAlgorithms: ReadonlyMap<RunAlgorithm, string>;
  algorithmVariants: readonly BenchmarkAlgorithmVariant[];
  chemicalAccuracyHa: number;
  requiresBranchEstimator: boolean;
  onAddAdvancedVariant: (algorithm: RunAlgorithm) => void;
  onSetAdvancedVariantCount: (algorithm: RunAlgorithm, count: number) => void;
  onDuplicateAdvancedVariant: (variantId: string) => void;
  onUpdateAdvancedVariant: (
    variantId: string,
    updater: (variant: BenchmarkAlgorithmVariant) => BenchmarkAlgorithmVariant,
  ) => void;
  onRemoveAdvancedVariant: (variantId: string) => void;
}>) {
  const collapseEditors = running || total > 0;
  const groupedVariants = useMemo(
    () =>
      BENCHMARK_ALGORITHMS.map((algorithm) => ({
        algorithm: algorithm.value,
        variants: algorithmVariants.filter((variant) => variant.algorithm === algorithm.value),
      })).filter((group) => group.variants.length > 0),
    [algorithmVariants],
  );
  const variantCounts = useMemo(
    () =>
      algorithmVariants.reduce(
        (counts, variant) =>
          counts.set(variant.algorithm, (counts.get(variant.algorithm) ?? 0) + 1),
        new Map<RunAlgorithm, number>(),
      ),
    [algorithmVariants],
  );

  return (
    <section className="space-y-4 rounded-xl border border-border/80 bg-card p-4">
      <div className="space-y-1">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <SlidersHorizontal className="h-4 w-4 text-muted-foreground" />
          Advanced rows
        </div>
        <p className="text-xs text-muted-foreground">
          Add one or more rows for each algorithm, then tune each row independently.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {BENCHMARK_ALGORITHMS.map((algorithm) => {
          const disabledReason = disabledAlgorithms.get(algorithm.value);
          const count = variantCounts.get(algorithm.value) ?? 0;
          const controlsDisabled = workspaceLocked || disabledReason !== undefined;
          return (
            <div
              key={algorithm.value}
              data-selected={count > 0}
              className={cn(
                "min-h-[4.8rem] rounded-xl border border-border/80 bg-surface-raised p-3 transition-colors",
                count > 0 && "border-primary/25 bg-primary/[0.06]",
                controlsDisabled && "opacity-70",
              )}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold">{algorithm.label}</span>
                    <span className="font-mono text-[11px] uppercase text-muted-foreground">
                      {algorithm.value}
                    </span>
                    <span className="rounded-full border border-border/80 bg-background px-2 py-0.5 text-[11px] font-medium text-muted-foreground">
                      {count}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {disabledReason ?? "Add another comparison row for this algorithm."}
                  </p>
                </div>
                <div className="flex items-center gap-2 self-center">
                  <Button
                    type="button"
                    size="icon"
                    variant="outline"
                    className="h-9 w-9 rounded-lg bg-background/90"
                    disabled={controlsDisabled || count === 0}
                    aria-label={`Remove ${algorithm.label} comparison row`}
                    onClick={() =>
                      onSetAdvancedVariantCount(algorithm.value, Math.max(0, count - 1))
                    }
                  >
                    <Minus className="h-4 w-4" />
                  </Button>
                  <div className="flex h-9 min-w-[4.75rem] items-center justify-center rounded-lg border border-border/80 bg-background/90 px-2">
                    <Input
                      type="number"
                      min={0}
                      step={1}
                      value={count}
                      disabled={controlsDisabled}
                      aria-label={`${algorithm.label} comparison row count`}
                      onChange={(event) => {
                        const nextCount = Number(event.target.value);
                        if (!Number.isFinite(nextCount) || nextCount < 0) {
                          return;
                        }
                        onSetAdvancedVariantCount(algorithm.value, nextCount);
                      }}
                      className="h-auto w-12 border-0 bg-transparent p-0 text-center text-sm font-semibold tabular-nums shadow-none focus-visible:ring-0 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                    />
                  </div>
                  <Button
                    type="button"
                    size="icon"
                    variant="outline"
                    className="h-9 w-9 rounded-lg bg-background/90"
                    disabled={controlsDisabled}
                    aria-label={`Add ${algorithm.label} comparison row`}
                    onClick={() => onAddAdvancedVariant(algorithm.value)}
                  >
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {algorithmVariants.length > 0 ? (
        <div className="grid gap-4">
          {groupedVariants.map((group) => (
            <BenchmarkAdvancedVariantGroup
              key={group.algorithm}
              algorithm={group.algorithm}
              variants={group.variants}
              chemicalAccuracyHa={chemicalAccuracyHa}
              requiresBranchEstimator={requiresBranchEstimator}
              disabled={workspaceLocked}
              collapseEditors={collapseEditors}
              onDuplicateAdvancedVariant={onDuplicateAdvancedVariant}
              onUpdateAdvancedVariant={onUpdateAdvancedVariant}
              onRemoveAdvancedVariant={onRemoveAdvancedVariant}
            />
          ))}
        </div>
      ) : (
        <div className="rounded-xl border border-dashed border-border/70 bg-muted/15 px-4 py-6 text-sm text-muted-foreground">
          Add an algorithm above to start building advanced benchmark rows.
        </div>
      )}
    </section>
  );
}
