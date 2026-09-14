import { lazy, Suspense } from "react";

import { BackendRefreshButton } from "./backend-refresh-button";
import { BackendPicker } from "./backend-picker";
import { NoiseModelPanel } from "./backend-noise-model-panel";
import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type {
  AerMethod,
  BackendDeviceSummary,
  BackendOptions,
  BackendTarget,
  NoiseProfile,
  RunMode,
} from "@/types/run";

import { type BackendPickerChoice } from "./backend-section-shared";

const BackendTopologyPanel = lazy(() =>
  import("./backend-topology-panel").then((module) => ({
    default: module.BackendTopologyPanel,
  })),
);

const AER_METHODS: Array<{ value: AerMethod; label: string }> = [
  { value: "automatic", label: "Automatic" },
  { value: "statevector", label: "Statevector" },
  { value: "density_matrix", label: "Density matrix" },
  { value: "matrix_product_state", label: "Matrix product state" },
  { value: "stabilizer", label: "Stabilizer" },
];

type NumberOptionKey = "shots" | "seed_simulator" | "seed_transpiler";

interface BackendSectionExpandedProps {
  mode: RunMode;
  value: BackendTarget;
  backendOptions: BackendOptions;
  selectedBackendDevice: BackendDeviceSummary | null;
  selectableDevices: BackendDeviceSummary[];
  disabled?: boolean;
  error?: string;
  onBackendChoice: (choice: BackendPickerChoice) => void;
  onRefreshCapabilities?: () => void;
  capabilitiesRefreshing?: boolean;
  noiseSupported: boolean;
  noiseProfile: NoiseProfile | null;
  onNoiseProfileChange: (next: NoiseProfile | null) => void;
  defaultNoiseProfile: (options?: BackendOptions) => NoiseProfile;
  noiseReferenceDevices: BackendDeviceSummary[];
  topologyPanelKey: string;
  topologyDevice: BackendDeviceSummary | null;
  topologyMode: "execution" | "noise-reference";
  updateNumberOption: (key: NumberOptionKey, raw: string) => void;
  updateBackendOptions: (patch: Partial<BackendOptions>) => void;
}

export function BackendSectionExpanded({
  mode,
  value,
  backendOptions,
  selectedBackendDevice,
  selectableDevices,
  disabled,
  error,
  onBackendChoice,
  onRefreshCapabilities,
  capabilitiesRefreshing,
  noiseSupported,
  noiseProfile,
  onNoiseProfileChange,
  defaultNoiseProfile,
  noiseReferenceDevices,
  topologyPanelKey,
  topologyDevice,
  topologyMode,
  updateNumberOption,
  updateBackendOptions,
}: BackendSectionExpandedProps) {
  return (
    <div className="grid gap-4">
      <div className="flex flex-col gap-4">
        {value === "ibm_runtime" ? (
          <FormField
            label="Backend"
            htmlFor="backend-device-picker"
            required
            error={error}
            help={{
              short:
                "Search devices or pick a suggestion. Least error and least busy are resolved automatically at run time.",
              anchor: "backend_name",
            }}
          >
            <div className="flex gap-2">
              <div className="min-w-0 flex-1">
                <BackendPicker
                  target={value}
                  devices={selectableDevices}
                  backendOptions={backendOptions}
                  disabled={disabled}
                  onSelect={onBackendChoice}
                />
              </div>
              {onRefreshCapabilities && (
                <BackendRefreshButton
                  onClick={onRefreshCapabilities}
                  disabled={disabled}
                  refreshing={capabilitiesRefreshing}
                  aria-label="Refresh backend list"
                />
              )}
            </div>
          </FormField>
        ) : null}

        <BackendExecutionOptions
          mode={mode}
          value={value}
          backendOptions={backendOptions}
          selectedDevice={selectedBackendDevice}
          disabled={disabled}
          updateNumberOption={updateNumberOption}
          updateBackendOptions={updateBackendOptions}
        />
      </div>

      {noiseSupported ? (
        <NoiseModelPanel
          target={value}
          disabled={disabled}
          mode={mode}
          noiseProfile={noiseProfile}
          onNoiseProfileChange={onNoiseProfileChange}
          defaultNoiseProfile={defaultNoiseProfile}
          referenceDevices={noiseReferenceDevices}
          onRefresh={onRefreshCapabilities}
          refreshing={capabilitiesRefreshing}
        />
      ) : null}

      {value !== "aer_simulator" || noiseProfile != null ? (
        <div className="min-w-0">
          <Suspense
            fallback={
              <div className="rounded-lg border border-border/70 bg-card p-5 text-sm text-muted-foreground">
                Loading backend topology…
              </div>
            }
          >
            <BackendTopologyPanel
              key={topologyPanelKey}
              target={value}
              device={topologyDevice}
              mode={topologyMode}
            />
          </Suspense>
        </div>
      ) : null}
    </div>
  );
}

function BackendExecutionOptions({
  mode,
  value,
  backendOptions,
  selectedDevice,
  disabled,
  updateNumberOption,
  updateBackendOptions,
}: {
  mode: RunMode;
  value: BackendTarget;
  backendOptions: BackendOptions;
  selectedDevice: BackendDeviceSummary | null;
  disabled?: boolean;
  updateNumberOption: (key: NumberOptionKey, raw: string) => void;
  updateBackendOptions: (patch: Partial<BackendOptions>) => void;
}) {
  if (mode === "easy") {
    return null;
  }

  return (
    <div className="grid gap-4 rounded-lg border border-border/70 bg-card p-4 md:grid-cols-2">
      <FormField
        label="Shots"
        htmlFor="backend-shots-input"
        help={{
          short: "Total circuit repetitions used to estimate observables on shot-based backends.",
          anchor: "shots",
        }}
      >
        <Input
          id="backend-shots-input"
          type="number"
          min={1}
          max={selectedDevice?.max_shots ?? undefined}
          step={1}
          value={backendOptions.shots}
          onChange={(event) => updateNumberOption("shots", event.target.value)}
          disabled={disabled}
        />
      </FormField>

      <FormField
        label="Optimization"
        htmlFor="backend-optimization-level"
        help={{
          short: "Transpiler optimization level for circuit rewriting before execution.",
          anchor: "optimization_level",
        }}
      >
        <Select
          value={String(backendOptions.optimization_level)}
          onValueChange={(next) =>
            updateBackendOptions({
              optimization_level: Number(next) as BackendOptions["optimization_level"],
            })
          }
        >
          <SelectTrigger id="backend-optimization-level" disabled={disabled}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="0">0</SelectItem>
            <SelectItem value="1">1</SelectItem>
            <SelectItem value="2">2</SelectItem>
            <SelectItem value="3">3</SelectItem>
          </SelectContent>
        </Select>
      </FormField>

      {value === "aer_simulator" && (
        <FormField
          label="Aer Method"
          htmlFor="aer-method-select"
          help={{
            short:
              "Simulation method Aer uses internally, such as dense statevector or matrix-product-state paths.",
            anchor: "aer_method",
          }}
        >
          <Select
            value={backendOptions.aer_method ?? "automatic"}
            onValueChange={(next) => updateBackendOptions({ aer_method: next as AerMethod })}
          >
            <SelectTrigger id="aer-method-select" disabled={disabled}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {AER_METHODS.map((method) => (
                <SelectItem key={method.value} value={method.value}>
                  {method.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </FormField>
      )}

      {value === "aer_simulator" && (
        <FormField
          label="Simulator Seed"
          htmlFor="seed-simulator-input"
          help={{
            short: "Random seed for Aer sampling and noise-model stochastic behavior.",
            anchor: "seed_simulator",
          }}
        >
          <Input
            id="seed-simulator-input"
            type="number"
            step={1}
            value={backendOptions.seed_simulator ?? ""}
            onChange={(event) => updateNumberOption("seed_simulator", event.target.value)}
            disabled={disabled}
          />
        </FormField>
      )}

      <FormField
        label="Transpiler Seed"
        htmlFor="seed-transpiler-input"
        help={{
          short:
            "Random seed for transpiler passes that have stochastic layout or routing choices.",
          anchor: "seed_transpiler",
        }}
      >
        <Input
          id="seed-transpiler-input"
          type="number"
          step={1}
          value={backendOptions.seed_transpiler ?? ""}
          onChange={(event) => updateNumberOption("seed_transpiler", event.target.value)}
          disabled={disabled}
        />
      </FormField>
    </div>
  );
}
