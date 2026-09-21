/** Benchmark basis, backend, and chemical-accuracy settings. */

import {
  getChemicalAccuracyTargetOptions,
  type ChemicalAccuracyTargetOption,
} from "@/lib/run-form-recommendations";
import type { BackendDeviceSummary, BasisSetMetadata } from "@/types/run";
import type { AerMethod } from "@/types/run-config";
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

const BENCHMARK_SHOT_PRESETS = [256, 1024, 4096] as const;
const BENCHMARK_AER_METHODS: readonly { value: AerMethod; label: string }[] = [
  { value: "automatic", label: "Automatic" },
  { value: "statevector", label: "Statevector" },
  { value: "density_matrix", label: "Density matrix" },
  { value: "matrix_product_state", label: "Matrix product state" },
  { value: "stabilizer", label: "Stabilizer" },
];
const GPU_AER_METHODS = new Set<AerMethod>(["statevector", "density_matrix"]);

function isAerBenchmarkMode(mode: BenchmarkBackendMode): boolean {
  return mode === "aer_simulator" || mode === "aer_simulator_backend_noise";
}

function BenchmarkShotsControl({
  shots,
  selectedBackendMode,
  workspaceLocked,
  onShotsChange,
}: Readonly<{
  shots: number;
  selectedBackendMode: BenchmarkBackendMode;
  workspaceLocked: boolean;
  onShotsChange: (shots: number) => void;
}>) {
  return (
    <div className="flex min-w-0 flex-col justify-center gap-2">
      <Label htmlFor="benchmark-shots" className="text-xs text-muted-foreground">
        Shots per evaluation
      </Label>
      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-border/70 bg-card p-2">
        <Input
          id="benchmark-shots"
          type="number"
          inputMode="numeric"
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
          className="h-9 w-28 bg-surface-raised [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
        />
        <div className="flex flex-wrap gap-1">
          {BENCHMARK_SHOT_PRESETS.map((preset) => (
            <Button
              key={preset}
              type="button"
              size="sm"
              variant={shots === preset ? "secondary" : "outline"}
              className="h-9 px-2.5 tabular-nums"
              disabled={workspaceLocked}
              onClick={() => onShotsChange(preset)}
            >
              {preset}
            </Button>
          ))}
        </div>
      </div>
      <p className="text-[11px] text-muted-foreground">
        {selectedBackendMode === "aer_simulator_backend_noise"
          ? "Default for backend-derived noise: 256 shots. Increase for lower sampling error."
          : "Lower shots reduce sampling work but increase statistical error."}
      </p>
    </div>
  );
}

function BenchmarkAerExecutionControl({
  selectedBackendMode,
  aerMethod,
  device,
  workspaceLocked,
  onAerMethodChange,
  onDeviceChange,
}: Readonly<{
  selectedBackendMode: BenchmarkBackendMode;
  aerMethod: AerMethod | null;
  device: "CPU" | "GPU" | null;
  workspaceLocked: boolean;
  onAerMethodChange: (method: AerMethod) => void;
  onDeviceChange: (device: "CPU" | "GPU" | null) => void;
}>) {
  if (!isAerBenchmarkMode(selectedBackendMode)) return null;

  const availableMethods = BENCHMARK_AER_METHODS.filter(
    (method) => device !== "GPU" || GPU_AER_METHODS.has(method.value),
  );
  const selectedMethod = aerMethod ?? "automatic";

  return (
    <div className="grid min-w-0 gap-3 sm:grid-cols-2">
      <div className="flex min-w-0 flex-col justify-center gap-2">
        <Label htmlFor="benchmark-aer-device" className="text-xs text-muted-foreground">
          Aer execution device
        </Label>
        <Select
          value={device ?? "CPU"}
          onValueChange={(value) => {
            if (value === "GPU") {
              onDeviceChange("GPU");
              if (!GPU_AER_METHODS.has(selectedMethod)) onAerMethodChange("statevector");
            } else {
              onDeviceChange(null);
            }
          }}
          disabled={workspaceLocked}
        >
          <SelectTrigger id="benchmark-aer-device" className="h-9 w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="CPU">CPU worker</SelectItem>
            <SelectItem value="GPU">GPU worker required</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="flex min-w-0 flex-col justify-center gap-2">
        <Label htmlFor="benchmark-aer-method" className="text-xs text-muted-foreground">
          Aer method
        </Label>
        <Select
          value={
            availableMethods.some((method) => method.value === selectedMethod)
              ? selectedMethod
              : "statevector"
          }
          onValueChange={(value) => {
            if (BENCHMARK_AER_METHODS.some((method) => method.value === value)) {
              onAerMethodChange(value as AerMethod);
            }
          }}
          disabled={workspaceLocked}
        >
          <SelectTrigger id="benchmark-aer-method" className="h-9 w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {availableMethods.map((method) => (
              <SelectItem key={method.value} value={method.value}>
                {method.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <p className="text-[11px] text-muted-foreground sm:col-span-2">
        GPU mode uses one dedicated worker and requires an explicit GPU-compatible method. Backend-
        derived noise enables Aer GPU shot batching automatically.
      </p>
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
  shots,
  onShotsChange,
  aerMethod,
  device,
  onAerMethodChange,
  onDeviceChange,
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
  shots: number;
  onShotsChange: (shots: number) => void;
  aerMethod: AerMethod | null;
  device: "CPU" | "GPU" | null;
  onAerMethodChange: (method: AerMethod) => void;
  onDeviceChange: (device: "CPU" | "GPU" | null) => void;
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
      <div className="xl:col-span-full">
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <BenchmarkShotsControl
            shots={shots}
            selectedBackendMode={selectedBackendMode}
            workspaceLocked={workspaceLocked}
            onShotsChange={onShotsChange}
          />
          <BenchmarkAerExecutionControl
            selectedBackendMode={selectedBackendMode}
            aerMethod={aerMethod}
            device={device}
            workspaceLocked={workspaceLocked}
            onAerMethodChange={onAerMethodChange}
            onDeviceChange={onDeviceChange}
          />
        </div>
      </div>
    </div>
  );
}
