/** Benchmark basis, backend, and chemical-accuracy settings. */

import {
  getChemicalAccuracyTargetOptions,
  type ChemicalAccuracyTargetOption,
} from "@/lib/run-form-recommendations";
import type { BackendDeviceSummary, BasisSetMetadata } from "@/types/run";
import { Button } from "@/components/ui/button";
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
  return (
    <div className="flex h-full min-w-0 w-full flex-col justify-center gap-2 xl:w-fit xl:justify-self-end">
      <Label htmlFor="benchmark-chemical-accuracy" className="text-xs text-muted-foreground">
        Chemical accuracy target
      </Label>
      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-border/70 bg-card p-2">
        <div className="flex h-9 items-center rounded-lg border border-input/80 bg-surface-raised px-3">
          <Input
            id="benchmark-chemical-accuracy"
            type="number"
            inputMode="decimal"
            min={0.1}
            step={0.1}
            value={(chemicalAccuracyHa * 1000).toFixed(1)}
            disabled={workspaceLocked}
            onChange={(event) => {
              const next = Number(event.target.value);
              if (!Number.isFinite(next) || next <= 0) return;
              onChemicalAccuracyChange(next / 1000);
            }}
            className="h-auto w-20 border-0 bg-transparent p-0 text-sm font-medium tabular-nums shadow-none focus-visible:ring-0 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
          />
          <span className="ml-2 text-sm font-medium text-muted-foreground">mHa</span>
        </div>
        <div className="flex flex-wrap gap-2">
          {chemicalAccuracyTargetOptions.map((option) => (
            <Button
              key={option.goal}
              type="button"
              size="sm"
              className={cn(
                "h-9 min-w-[4.75rem] rounded-lg",
                Math.abs(chemicalAccuracyHa - option.thresholdHa) >= 0.00005 &&
                  "bg-surface-raised-hover",
              )}
              variant={
                Math.abs(chemicalAccuracyHa - option.thresholdHa) < 0.00005
                  ? "secondary"
                  : "outline"
              }
              disabled={workspaceLocked}
              onClick={() => onChemicalAccuracyChange(option.thresholdHa)}
            >
              {option.label}
            </Button>
          ))}
        </div>
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
  onBackendNameChange: (backendName: string) => void;
  ibmBackends: readonly BackendDeviceSummary[];
  backendCapabilitiesLoading: boolean;
  backendCapabilitiesRefreshing: boolean;
  chemicalAccuracyHa: number;
  chemicalAccuracyTargetOptions?: readonly ChemicalAccuracyTargetOption[];
  onChemicalAccuracyChange: (thresholdHa: number) => void;
}>) {
  return (
    <div
      data-testid="benchmark-execution-settings"
      className={cn(
        "grid gap-x-3 gap-y-4 border-t border-border/70 pt-4 xl:items-center",
        backendSelectionRequired
          ? "xl:grid-cols-[minmax(0,10rem)_minmax(0,1fr)_minmax(0,1fr)_auto]"
          : "xl:grid-cols-[minmax(0,10rem)_minmax(0,1fr)_auto]",
      )}
    >
      <div className="flex h-full min-w-0 flex-col justify-center gap-2">
        <Label id="benchmark-basis-label" className="text-xs text-muted-foreground">
          Basis set
        </Label>
        <Select
          value={basisIds.has(selectedBasis) ? selectedBasis : basisDefault}
          onValueChange={onBasisChange}
          disabled={workspaceLocked}
        >
          <SelectTrigger aria-labelledby="benchmark-basis-label" className="h-9 w-full">
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

      <div className="flex h-full min-w-0 flex-col justify-center gap-2">
        <Label id="benchmark-backend-label" className="text-xs text-muted-foreground">
          Backend
        </Label>
        <Select
          value={selectedBackendMode}
          onValueChange={(value) => {
            if (isBenchmarkBackendMode(value)) {
              onBackendModeChange(value);
            }
          }}
          onOpenChange={(open) => {
            if (open) onBackendOptionsOpen();
          }}
          disabled={workspaceLocked}
        >
          <SelectTrigger aria-labelledby="benchmark-backend-label" className="h-9 w-full">
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
        <div className="flex h-full min-w-0 flex-col justify-center gap-2">
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

      <BenchmarkChemicalAccuracyControl
        chemicalAccuracyHa={chemicalAccuracyHa}
        chemicalAccuracyTargetOptions={chemicalAccuracyTargetOptions}
        workspaceLocked={workspaceLocked}
        onChemicalAccuracyChange={onChemicalAccuracyChange}
      />
    </div>
  );
}
