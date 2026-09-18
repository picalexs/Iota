import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { ChevronDown, Copy, Trash2 } from "lucide-react";

import { VQEPanel } from "@/components/forms/run-form/advanced-panels/vqe-panel";
import { SQDPanel } from "@/components/forms/run-form/advanced-panels/sqd-panel";
import { KQDPanel } from "@/components/forms/run-form/advanced-panels/kqd-panel";
import { QFDPanel } from "@/components/forms/run-form/advanced-panels/qfd-panel";
import { QSEPanel } from "@/components/forms/run-form/advanced-panels/qse-panel";
import { SKQDPanel } from "@/components/forms/run-form/advanced-panels/skqd-panel";
import { EasyGoalSlider } from "@/components/forms/run-form/easy-goal-slider";
import { loadRunFormConfigMetadata } from "@/components/forms/run-form/manual-mode-config";
import { useRunConfigMetadata } from "@/hooks";
import { RunFormProvider } from "@/components/forms/run-form/run-form-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SelectableCard } from "@/components/ui/selectable-card";
import { showErrorToast } from "@/lib/error-handler";
import type { RunAlgorithm, RunConfigMetadataResponse, SimulationRunFormData } from "@/types/run";
import { cn } from "@/lib/utils";
import {
  benchmarkVariantSummary,
  buildBenchmarkVariantFormValues,
  buildBenchmarkVariantFromFormValues,
  createAdvancedBenchmarkVariant,
  type BenchmarkAlgorithmVariant,
} from "./benchmark-variants";

interface BenchmarkVariantEditorProps {
  variant: BenchmarkAlgorithmVariant;
  chemicalAccuracyHa: number;
  disabled?: boolean;
  autoCollapse?: boolean;
  onChange: (variant: BenchmarkAlgorithmVariant) => void;
  onDuplicate: () => void;
  onRemove: () => void;
}

const AUTOSAVE_DELAY_MS = 250;

function buildVariantDraftSignature(label: string, values: SimulationRunFormData): string {
  return JSON.stringify({
    label,
    values,
  });
}

function buildPersistedVariantSignature(variant: BenchmarkAlgorithmVariant): string {
  return buildVariantDraftSignature(variant.label, buildBenchmarkVariantFormValues(variant));
}

function benchmarkVariantModeLabel(variant: BenchmarkAlgorithmVariant): string {
  if (variant.mode === "simple") {
    if (variant.easyGoal === "fastest") {
      return "Easy · Fastest";
    }
    if (variant.easyGoal === "best_accuracy") {
      return "Easy · Best accuracy";
    }
    return "Easy · Balanced";
  }

  return "Advanced";
}

function BenchmarkVariantModeToggle({
  selectedMode,
  disabled = false,
  onSelect,
}: Readonly<{
  selectedMode: "easy" | "advanced";
  disabled?: boolean;
  onSelect: (mode: "easy" | "advanced") => void;
}>) {
  return (
    <div className="grid gap-3 md:grid-cols-2">
      <SelectableCard
        selected={selectedMode === "easy"}
        disabled={disabled}
        onClick={() => onSelect("easy")}
        className="min-h-[5.4rem] p-4"
      >
        <div className="space-y-1 text-left">
          <p className="text-sm font-semibold">Easy row</p>
          <p className="text-xs text-muted-foreground">
            Use the shared guided preset for this algorithm.
          </p>
        </div>
      </SelectableCard>
      <SelectableCard
        selected={selectedMode === "advanced"}
        disabled={disabled}
        onClick={() => onSelect("advanced")}
        className="min-h-[5.4rem] p-4"
      >
        <div className="space-y-1 text-left">
          <p className="text-sm font-semibold">Advanced row</p>
          <p className="text-xs text-muted-foreground">
            Reuse the manual run controls and tune this row directly.
          </p>
        </div>
      </SelectableCard>
    </div>
  );
}

function BenchmarkVariantAlgorithmPanel({
  algorithm,
  metadata,
  onResetRecommended,
}: Readonly<{
  algorithm: RunAlgorithm;
  metadata: RunConfigMetadataResponse | null;
  onResetRecommended: () => void;
}>) {
  switch (algorithm) {
    case "vqe":
      return <VQEPanel metadata={metadata} onResetRecommended={onResetRecommended} />;
    case "sqd":
      return <SQDPanel onResetRecommended={onResetRecommended} />;
    case "kqd":
      return <KQDPanel onResetRecommended={onResetRecommended} />;
    case "qfd":
      return <QFDPanel onResetRecommended={onResetRecommended} />;
    case "qse":
      return <QSEPanel metadata={metadata} onResetRecommended={onResetRecommended} />;
    case "skqd":
      return <SKQDPanel onResetRecommended={onResetRecommended} />;
  }
}

export function BenchmarkVariantEditor({
  variant,
  chemicalAccuracyHa,
  disabled = false,
  autoCollapse = false,
  onChange,
  onDuplicate,
  onRemove,
}: Readonly<BenchmarkVariantEditorProps>) {
  const configMetadata = useRunConfigMetadata(loadRunFormConfigMetadata).data ?? null;
  const [label, setLabel] = useState(variant.label);
  const [expanded, setExpanded] = useState(!autoCollapse);
  const form = useForm<SimulationRunFormData>({
    defaultValues: buildBenchmarkVariantFormValues(variant),
    mode: "onChange",
  });
  const watchedValues =
    (useWatch({
      control: form.control,
    }) as SimulationRunFormData | undefined) ?? form.getValues();
  const incomingValues = useMemo(() => buildBenchmarkVariantFormValues(variant), [variant]);
  const incomingSignature = useMemo(() => buildPersistedVariantSignature(variant), [variant]);
  const lastAppliedSignatureRef = useRef<string>(incomingSignature);
  const lastIncomingSignatureRef = useRef<string>(incomingSignature);
  const previousAutoCollapseRef = useRef(autoCollapse);

  useEffect(() => {
    if (autoCollapse && !previousAutoCollapseRef.current) {
      setExpanded(false);
    }
    previousAutoCollapseRef.current = autoCollapse;
  }, [autoCollapse]);

  useEffect(() => {
    if (lastIncomingSignatureRef.current === incomingSignature) {
      return;
    }

    lastIncomingSignatureRef.current = incomingSignature;
    const currentDraftSignature = buildVariantDraftSignature(label, form.getValues());
    if (currentDraftSignature === incomingSignature) {
      lastAppliedSignatureRef.current = incomingSignature;
      return;
    }

    setLabel(variant.label);
    form.reset(incomingValues);
    lastAppliedSignatureRef.current = incomingSignature;
  }, [form, incomingSignature, incomingValues, label, variant.label]);

  const currentMode = form.watch("mode");

  const applyVariantValues = useCallback(
    (nextValues: SimulationRunFormData, options: { notifyOnError?: boolean } = {}) => {
      try {
        const updated = buildBenchmarkVariantFromFormValues(variant, nextValues);
        const nextLabel = label.trim().length > 0 ? label.trim() : benchmarkVariantSummary(updated);
        onChange({ ...updated, label: nextLabel });
        setLabel(nextLabel);
        const nextSignature = buildPersistedVariantSignature({ ...updated, label: nextLabel });
        lastAppliedSignatureRef.current = nextSignature;
        lastIncomingSignatureRef.current = nextSignature;
        return true;
      } catch (error) {
        if (options.notifyOnError) {
          showErrorToast(error, {
            title: "Couldn't update benchmark row",
            fallbackDescription: "Please review the row settings and try again.",
          });
        }
        return false;
      }
    },
    [label, onChange, variant],
  );

  useEffect(() => {
    if (!watchedValues) {
      return;
    }

    const draftSignature = buildVariantDraftSignature(label, watchedValues);
    if (draftSignature === lastAppliedSignatureRef.current) {
      return;
    }

    const timer = window.setTimeout(() => {
      applyVariantValues(watchedValues);
    }, AUTOSAVE_DELAY_MS);

    return () => {
      window.clearTimeout(timer);
    };
  }, [applyVariantValues, label, watchedValues]);

  function handleModeSelect(mode: "easy" | "advanced") {
    form.setValue("mode", mode, { shouldDirty: true });
    applyVariantValues({ ...form.getValues(), mode }, { notifyOnError: true });
  }

  function handleResetRecommended() {
    const nextValues = buildBenchmarkVariantFormValues(
      createAdvancedBenchmarkVariant(variant.algorithm, chemicalAccuracyHa, configMetadata),
    );
    nextValues.mode = "advanced";
    form.reset(nextValues);
    applyVariantValues(nextValues, { notifyOnError: true });
  }

  return (
    <RunFormProvider form={form}>
      <section className="space-y-4 rounded-xl border border-border/80 bg-card p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                {variant.algorithm}
              </span>
              <span className="truncate text-sm font-semibold">{label}</span>
            </div>
            <div className="flex flex-wrap gap-2">
              <span className="rounded-full border border-border/80 bg-background px-2.5 py-1 text-[11px] font-medium text-muted-foreground">
                {benchmarkVariantModeLabel(variant)}
              </span>
              <span className="rounded-full border border-border/80 bg-background px-2.5 py-1 text-[11px] font-medium text-muted-foreground">
                {benchmarkVariantSummary(variant)}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={disabled}
              onClick={onDuplicate}
            >
              <Copy className="size-4" />
              Duplicate
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={disabled}
              onClick={onRemove}
            >
              <Trash2 className="size-4" />
              Remove
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              aria-expanded={expanded}
              aria-label={`${expanded ? "Collapse" : "Expand"} row details for ${variant.algorithm.toUpperCase()} ${label}`}
              onClick={() => setExpanded((value) => !value)}
            >
              {expanded ? "Collapse" : "Expand"}
              <ChevronDown
                className={cn("size-4 transition-transform", expanded && "rotate-180")}
              />
            </Button>
          </div>
        </div>

        {expanded ? (
          <>
            <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
              <div className="space-y-2">
                <Label
                  htmlFor={`benchmark-variant-label-${variant.id}`}
                  className="text-xs text-muted-foreground"
                >
                  Row label
                </Label>
                <Input
                  id={`benchmark-variant-label-${variant.id}`}
                  value={label}
                  disabled={disabled}
                  onChange={(event) => setLabel(event.target.value)}
                  onBlur={() => applyVariantValues(form.getValues())}
                  placeholder={benchmarkVariantSummary(variant)}
                />
              </div>
              <div className="space-y-2">
                <p className="text-xs text-muted-foreground">Row mode</p>
                <BenchmarkVariantModeToggle
                  selectedMode={currentMode}
                  disabled={disabled}
                  onSelect={handleModeSelect}
                />
              </div>
            </div>

            {currentMode === "easy" ? (
              <div className="space-y-3">
                <div>
                  <p className="text-sm font-semibold">Guided preset</p>
                  <p className="text-xs text-muted-foreground">
                    This row stays compact and uses the shared easy-mode preset family.
                  </p>
                </div>
                <EasyGoalSlider id={`benchmark-variant-easy-${variant.id}`} disabled={disabled} />
              </div>
            ) : (
              <div className={cn("space-y-4", disabled && "pointer-events-none opacity-80")}>
                <BenchmarkVariantAlgorithmPanel
                  algorithm={variant.algorithm}
                  metadata={configMetadata}
                  onResetRecommended={handleResetRecommended}
                />
              </div>
            )}
          </>
        ) : (
          <div className="rounded-xl border border-border/70 bg-muted/15 px-4 py-3 text-sm text-muted-foreground">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium text-foreground">{label}</span>
              <span>/</span>
              <span>{benchmarkVariantModeLabel(variant)}</span>
              <span>/</span>
              <span>{benchmarkVariantSummary(variant)}</span>
            </div>
          </div>
        )}
      </section>
    </RunFormProvider>
  );
}
