/** Benchmark basis, backend, and chemical-accuracy settings. */

import {
  getChemicalAccuracyTargetOptions,
  type ChemicalAccuracyTargetOption,
} from "@/lib/run-form-recommendations";
import { useEffect, useState } from "react";
import type { BackendDeviceSummary, BasisSetMetadata } from "@/types/run";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { BenchmarkBackendPicker } from "./benchmark-backend-picker";
import {
  isBenchmarkBackendMode,
  type BenchmarkBackendMode,
  type BenchmarkBackendOption,
} from "./benchmark-utils";

function BenchmarkChemicalAccuracyControl({
  chemicalAccuracyHa,
  chemicalAccuracyTargetOptions,
  workspaceLocked,
  onChemicalAccuracyChange,
}: Readonly<{
  chemicalAccuracyHa: number;
  chemicalAccuracyTargetOptions: readonly ChemicalAccuracyTargetOption[];
  workspaceLocked: boolean;
  onChemicalAccuracyChange: (thresholdHa: number) => void;
}>) {
  const sortedTargetOptions = [...chemicalAccuracyTargetOptions].sort(
    (left, right) => left.thresholdHa - right.thresholdHa,
  );
  const editableTarget =
    sortedTargetOptions.find((option) => option.goal === "fastest") ?? sortedTargetOptions.at(-1);
  const presetTargetOptions = sortedTargetOptions.filter(
    (option) => option.goal !== editableTarget?.goal,
  );
  const currentTargetIsPreset = presetTargetOptions.some(
    (option) => Math.abs(chemicalAccuracyHa - option.thresholdHa) < 0.00005,
  );
  const [editableTargetValue, setEditableTargetValue] = useState(() =>
    currentTargetIsPreset ? "" : (chemicalAccuracyHa * 1000).toFixed(1),
  );

  if (editableTarget == null) return null;

  return (
    <div className="flex min-w-0 w-full flex-col gap-2 xl:w-fit xl:justify-self-start">
      <Label htmlFor="benchmark-chemical-accuracy" className="text-xs text-muted-foreground">
        Chemical accuracy target
      </Label>
      <div className="flex min-h-10 flex-wrap items-center gap-2">
        {sortedTargetOptions.map((option) => {
          if (option.goal === editableTarget.goal) {
            const selected = !currentTargetIsPreset;
            return (
              <div
                key={option.goal}
                className={cn(
                  "flex h-10 min-w-[4.75rem] items-center justify-center gap-1 rounded-lg border px-2 transition-colors",
                  selected
                    ? "border-interactive-selected-border bg-interactive-selected text-interactive-selected-foreground shadow-[var(--shadow-interactive-selected)]"
                    : "border-input bg-surface-raised hover:border-interactive-hover-border hover:bg-interactive-hover",
                )}
              >
                <Input
                  id="benchmark-chemical-accuracy"
                  type="number"
                  inputMode="decimal"
                  min={0.1}
                  step={0.1}
                  placeholder="5.0"
                  title="Enter a custom target in mHa"
                  value={editableTargetValue}
                  disabled={workspaceLocked}
                  onChange={(event) => {
                    const raw = event.target.value;
                    setEditableTargetValue(raw);
                    const next = Number(raw);
                    if (Number.isFinite(next) && next >= 0.1) {
                      onChemicalAccuracyChange(next / 1000);
                    }
                  }}
                  onBlur={() => {
                    if (editableTargetValue.trim() === "") return;
                    const next = Number(editableTargetValue);
                    if (!Number.isFinite(next) || next < 0.1) {
                      setEditableTargetValue(
                        currentTargetIsPreset ? "" : (chemicalAccuracyHa * 1000).toFixed(1),
                      );
                    } else {
                      setEditableTargetValue(next.toFixed(1));
                    }
                  }}
                  aria-label="Editable chemical accuracy target"
                  className="h-auto w-8 border-0 bg-transparent p-0 text-center text-sm font-medium tabular-nums text-inherit shadow-none focus-visible:ring-0 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                />
                <span className="text-sm font-medium text-inherit">mHa</span>
              </div>
            );
          }

          const selected = Math.abs(chemicalAccuracyHa - option.thresholdHa) < 0.00005;
          return (
            <Button
              key={option.goal}
              type="button"
              size="sm"
              className={cn(
                "!h-10 min-w-[4.75rem] rounded-lg",
                selected
                  ? "border-interactive-selected-border bg-interactive-selected text-interactive-selected-foreground shadow-[var(--shadow-interactive-selected)]"
                  : "bg-surface-raised-hover",
              )}
              variant="outline"
              data-selected={selected}
              aria-pressed={selected}
              disabled={workspaceLocked}
              onClick={() => {
                setEditableTargetValue("");
                onChemicalAccuracyChange(option.thresholdHa);
              }}
            >
              {option.label}
            </Button>
          );
        })}
      </div>
    </div>
  );
}

export function BenchmarkExecutionSettings({
  backendSelectionRequired,
  basisIds,
  basisDefault,
  orderedBasisOptions,
  selectedBasis,
  workspaceLocked,
  onBasisChange,
  selectedBackendMode,
  onBackendModeChange,
  onBackendOptionsOpen,
  backendOptions,
  backendNameLabel,
  selectedBackendName,
  shots,
  optimizationLevel,
  seedTranspiler,
  dynamicalDecoupling,
  twirling,
  onShotsChange,
  onOptimizationLevelChange,
  onSeedTranspilerChange,
  onDynamicalDecouplingChange,
  onTwirlingChange,
  onBackendNameChange,
  ibmBackends,
  backendCapabilitiesLoading,
  backendCapabilitiesRefreshing,
  chemicalAccuracyHa,
  chemicalAccuracyTargetOptions = getChemicalAccuracyTargetOptions(undefined),
  onChemicalAccuracyChange,
}: Readonly<{
  backendSelectionRequired: boolean;
  basisIds: ReadonlySet<string>;
  basisDefault: string;
  orderedBasisOptions: readonly BasisSetMetadata[];
  selectedBasis: string;
  workspaceLocked: boolean;
  onBasisChange: (basis: string) => void;
  selectedBackendMode: BenchmarkBackendMode;
  onBackendModeChange: (backend: BenchmarkBackendMode) => void;
  onBackendOptionsOpen: () => void;
  backendOptions: readonly BenchmarkBackendOption[];
  backendNameLabel: string;
  selectedBackendName: string | null;
  shots: number;
  optimizationLevel: 0 | 1 | 2 | 3;
  seedTranspiler: number | null;
  dynamicalDecoupling: boolean;
  twirling: boolean;
  onShotsChange: (shots: number) => void;
  onOptimizationLevelChange: (level: 0 | 1 | 2 | 3) => void;
  onSeedTranspilerChange: (seed: number | null) => void;
  onDynamicalDecouplingChange: (enabled: boolean) => void;
  onTwirlingChange: (enabled: boolean) => void;
  onBackendNameChange: (backendName: string) => void;
  ibmBackends: readonly BackendDeviceSummary[];
  backendCapabilitiesLoading: boolean;
  backendCapabilitiesRefreshing: boolean;
  chemicalAccuracyHa: number;
  chemicalAccuracyTargetOptions?: readonly ChemicalAccuracyTargetOption[];
  onChemicalAccuracyChange: (thresholdHa: number) => void;
}>) {
  const runtimePoliciesAvailable = selectedBackendMode === "ibm_runtime";
  const [shotsValue, setShotsValue] = useState(() => String(shots));
  const policyCardClassName = cn(
    "flex h-10 min-h-10 cursor-pointer self-end items-center gap-2 rounded-lg border px-3 transition-colors",
    "border-border/80 bg-surface-raised hover:border-interactive-hover-border hover:bg-interactive-hover",
    workspaceLocked && "opacity-70",
  );

  useEffect(() => {
    setShotsValue(String(shots));
  }, [shots]);

  return (
    <div
      data-testid="benchmark-execution-settings"
      className="space-y-4 border-t border-border/70 pt-5"
    >
      <div
        className={cn(
          "grid gap-3",
          backendSelectionRequired
            ? "md:grid-cols-2 xl:grid-cols-[minmax(12rem,0.7fr)_minmax(14rem,1fr)_minmax(10rem,0.65fr)_auto]"
            : "md:grid-cols-2 xl:grid-cols-[minmax(12rem,0.7fr)_minmax(10rem,0.65fr)_auto]",
        )}
      >
        <div className="flex min-w-0 flex-col gap-2">
          <Label id="benchmark-backend-label" className="text-xs text-muted-foreground">
            Backend
          </Label>
          <Select
            value={selectedBackendMode}
            onValueChange={(value) => {
              if (isBenchmarkBackendMode(value)) {
                onBackendModeChange(value);
                if (value !== "ibm_runtime") {
                  onDynamicalDecouplingChange(false);
                  onTwirlingChange(false);
                }
              }
            }}
            onOpenChange={(open) => {
              if (open) onBackendOptionsOpen();
            }}
            disabled={workspaceLocked}
          >
            <SelectTrigger aria-labelledby="benchmark-backend-label" className="!h-10 w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {backendOptions.map((backend) => (
                <SelectItem key={backend.value} value={backend.value} disabled={!backend.enabled}>
                  {backend.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {backendSelectionRequired ? (
          <div className="flex min-w-0 flex-col gap-2">
            <Label id="benchmark-backend-name-label" className="text-xs text-muted-foreground">
              {backendNameLabel}
            </Label>
            <BenchmarkBackendPicker
              devices={ibmBackends}
              loading={backendCapabilitiesLoading}
              refreshing={backendCapabilitiesRefreshing}
              selectedBackendName={selectedBackendName}
              placeholder={
                selectedBackendMode === "aer_simulator_backend_noise"
                  ? "Select noise reference backend"
                  : "Select IBM backend"
              }
              ariaLabelledBy="benchmark-backend-name-label"
              disabled={workspaceLocked || ibmBackends.length === 0}
              onOpen={onBackendOptionsOpen}
              onSelect={onBackendNameChange}
            />
          </div>
        ) : null}

        <div className="flex min-w-0 flex-col gap-2">
          <Label id="benchmark-basis-label" className="text-xs text-muted-foreground">
            Basis set
          </Label>
          <Select
            value={basisIds.has(selectedBasis) ? selectedBasis : basisDefault}
            onValueChange={onBasisChange}
            disabled={workspaceLocked}
          >
            <SelectTrigger
              aria-labelledby="benchmark-basis-label"
              className="!h-10 w-full xl:max-w-[12rem]"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {orderedBasisOptions.map((basis) => (
                <SelectItem key={basis.id} value={basis.id}>
                  {basis.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <BenchmarkChemicalAccuracyControl
          chemicalAccuracyHa={chemicalAccuracyHa}
          chemicalAccuracyTargetOptions={chemicalAccuracyTargetOptions}
          workspaceLocked={workspaceLocked}
          onChemicalAccuracyChange={onChemicalAccuracyChange}
        />
      </div>

      <div
        className={cn(
          "grid gap-3 rounded-xl border border-border/70 bg-card p-3 sm:p-4 md:grid-cols-2",
          runtimePoliciesAvailable
            ? "xl:grid-cols-[minmax(0,1.1fr)_minmax(9rem,0.7fr)_minmax(0,1fr)_minmax(13rem,1fr)_minmax(13rem,1fr)]"
            : "xl:grid-cols-[minmax(0,1.1fr)_minmax(9rem,0.7fr)_minmax(0,1fr)]",
        )}
      >
        <div className="flex min-w-0 flex-col gap-1.5">
          <Label htmlFor="benchmark-shots" className="text-xs text-muted-foreground">
            Shots
          </Label>
          <Input
            id="benchmark-shots"
            type="number"
            min={1}
            max={1_000_000}
            step={1}
            value={shotsValue}
            disabled={workspaceLocked}
            className="h-10"
            onChange={(event) => {
              const raw = event.target.value;
              setShotsValue(raw);
              if (raw.trim() === "") return;

              const next = Number(raw);
              if (Number.isInteger(next) && next >= 1 && next <= 1_000_000) {
                onShotsChange(next);
              }
            }}
            onBlur={() => {
              const next = Number(shotsValue);
              if (!Number.isInteger(next) || next < 1 || next > 1_000_000) {
                setShotsValue(String(shots));
              } else {
                setShotsValue(String(next));
              }
            }}
          />
        </div>
        <div className="flex min-w-0 flex-col gap-1.5">
          <Label htmlFor="benchmark-optimization-level" className="text-xs text-muted-foreground">
            Optimization level
          </Label>
          <Select
            value={String(optimizationLevel)}
            onValueChange={(value) => onOptimizationLevelChange(Number(value) as 0 | 1 | 2 | 3)}
            disabled={workspaceLocked}
          >
            <SelectTrigger id="benchmark-optimization-level" className="!h-10">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {[0, 1, 2, 3].map((level) => (
                <SelectItem key={level} value={String(level)}>
                  Level {level}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex min-w-0 flex-col gap-1.5 xl:max-w-[15rem] xl:justify-self-end">
          <Label htmlFor="benchmark-transpiler-seed" className="text-xs text-muted-foreground">
            Transpiler seed
          </Label>
          <Input
            id="benchmark-transpiler-seed"
            type="number"
            min={0}
            max={4_294_967_295}
            step={1}
            placeholder="Automatic"
            value={seedTranspiler ?? ""}
            disabled={workspaceLocked}
            className="h-10"
            onChange={(event) => {
              const raw = event.target.value.trim();
              if (raw === "") {
                onSeedTranspilerChange(null);
                return;
              }
              const next = Number(raw);
              if (Number.isInteger(next) && next >= 0 && next <= 4_294_967_295) {
                onSeedTranspilerChange(next);
              }
            }}
          />
        </div>
        {runtimePoliciesAvailable ? (
          <>
            <label className={policyCardClassName}>
              <Checkbox
                checked={dynamicalDecoupling}
                disabled={workspaceLocked}
                onCheckedChange={(checked) => onDynamicalDecouplingChange(checked === true)}
                className="size-5 rounded-md border-2 shadow-sm"
              />
              <span className="text-sm font-medium">Dynamical decoupling</span>
            </label>
            <label className={policyCardClassName}>
              <Checkbox
                checked={twirling}
                disabled={workspaceLocked}
                onCheckedChange={(checked) => onTwirlingChange(checked === true)}
                className="size-5 rounded-md border-2 shadow-sm"
              />
              <span className="text-sm font-medium">Twirling</span>
            </label>
          </>
        ) : null}
      </div>
    </div>
  );
}
