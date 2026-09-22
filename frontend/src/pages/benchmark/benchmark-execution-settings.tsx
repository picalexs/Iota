/** Benchmark basis, backend, and chemical-accuracy settings. */

import {
  getChemicalAccuracyTargetOptions,
  type ChemicalAccuracyTargetOption,
} from "@/lib/run-form-recommendations";
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

      <div className="col-span-full grid gap-3 rounded-xl border border-border/70 bg-card p-3 md:grid-cols-2 xl:grid-cols-5">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="benchmark-shots" className="text-xs text-muted-foreground">
            Shots
          </Label>
          <Input
            id="benchmark-shots"
            type="number"
            min={1}
            max={1_000_000}
            step={1}
            value={shots}
            disabled={workspaceLocked}
            onChange={(event) => {
              const next = Number(event.target.value);
              if (Number.isInteger(next) && next >= 1 && next <= 1_000_000) {
                onShotsChange(next);
              }
            }}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="benchmark-optimization-level" className="text-xs text-muted-foreground">
            Optimization level
          </Label>
          <Select
            value={String(optimizationLevel)}
            onValueChange={(value) => onOptimizationLevelChange(Number(value) as 0 | 1 | 2 | 3)}
            disabled={workspaceLocked}
          >
            <SelectTrigger id="benchmark-optimization-level">
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
        <div className="flex flex-col gap-1.5">
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
        <label className="flex items-center gap-2 text-sm">
          <Checkbox
            checked={dynamicalDecoupling}
            disabled={workspaceLocked || selectedBackendMode !== "ibm_runtime"}
            onCheckedChange={(checked) => onDynamicalDecouplingChange(checked === true)}
          />
          <span>Dynamical decoupling</span>
        </label>
        <label className="flex items-center gap-2 text-sm">
          <Checkbox
            checked={twirling}
            disabled={workspaceLocked || selectedBackendMode !== "ibm_runtime"}
            onCheckedChange={(checked) => onTwirlingChange(checked === true)}
          />
          <span>Twirling</span>
        </label>
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
