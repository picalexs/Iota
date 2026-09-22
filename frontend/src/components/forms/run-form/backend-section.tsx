import type { IbmBackendWarmupProgress } from "@/lib/ibm-profile-events";
import type {
  BackendCapability,
  BackendOptions,
  BackendTarget,
  NoiseProfile,
  RunMode,
} from "@/types/run";
import {
  backendDefaultsForTarget,
  getNoiseReferenceDevice,
  getNoiseReferenceDevices,
  getSelectableDevices,
  getSelectedBackendDevice,
  resolveNoiseReference,
  type BackendPickerChoice,
} from "./backend-section-shared";
import { BackendSectionExpanded } from "./backend-section-expanded";
import { BackendTargetCards } from "./backend-target-cards";

interface BackendSectionProps {
  value: BackendTarget | null;
  mode: RunMode;
  onChange: (v: BackendTarget) => void;
  backendOptions: BackendOptions;
  onBackendOptionsChange: (next: BackendOptions) => void;
  noiseProfile: NoiseProfile | null;
  onNoiseProfileChange: (next: NoiseProfile | null) => void;
  capabilities: BackendCapability[];
  capabilitiesLoading?: boolean;
  capabilitiesRefreshing?: boolean;
  capabilitiesWarmupProgress?: IbmBackendWarmupProgress | null;
  onRefreshCapabilities?: () => void;
  capabilitiesError?: string | null;
  disabled?: boolean;
  error?: string;
}

export function BackendSection({
  value,
  mode,
  onChange,
  backendOptions,
  onBackendOptionsChange,
  noiseProfile,
  onNoiseProfileChange,
  capabilities,
  capabilitiesLoading,
  capabilitiesRefreshing,
  capabilitiesWarmupProgress,
  onRefreshCapabilities,
  capabilitiesError,
  disabled,
  error,
}: BackendSectionProps) {
  const selectedCapability = value
    ? (capabilities.find((capability) => capability.target === value) ?? null)
    : null;
  const ibmCapability = capabilities.find((capability) => capability.target === "ibm_runtime");
  const selectableDevices = getSelectableDevices(value, selectedCapability);
  const noiseReferenceDevices = getNoiseReferenceDevices(ibmCapability);
  const selectedBackendDevice = getSelectedBackendDevice(value, backendOptions, selectableDevices);
  const selectedNoiseReferenceDevice = getNoiseReferenceDevice(noiseProfile, noiseReferenceDevices);
  const topologyDevice =
    value === "aer_simulator" && noiseProfile?.source === "backend_derived"
      ? selectedNoiseReferenceDevice
      : selectedBackendDevice;
  const topologyMode =
    value === "aer_simulator" && noiseProfile?.source === "backend_derived"
      ? "noise-reference"
      : "execution";
  const topologyPanelKey = [
    value ?? "none",
    topologyMode,
    topologyDevice?.name ?? "none",
    topologyDevice?.num_qubits ?? "unknown",
  ].join(":");
  const noiseSupported = selectedCapability?.supports_noise_profile === true;
  const isExpandedBackend = value === "aer_simulator" || value === "ibm_runtime";

  const updateBackendOptions = (patch: Partial<BackendOptions>) => {
    onBackendOptionsChange({ ...backendOptions, ...patch });
  };

  const updateNumberOption = (key: "shots" | "seed_simulator" | "seed_transpiler", raw: string) => {
    const parsed = raw.trim().length === 0 ? null : Number(raw);
    if (parsed !== null && !Number.isFinite(parsed)) return;
    if (key === "shots") {
      if (parsed === null) return;
      updateBackendOptions({ shots: parsed });
      return;
    }
    updateBackendOptions({ [key]: parsed });
  };

  const defaultNoiseProfile = (options = backendOptions): NoiseProfile => ({
    source: "backend_derived",
    reference_backend: resolveNoiseReference(
      options,
      selectedCapability,
      value,
      noiseReferenceDevices,
    ),
  });

  const handleBackendTargetChange = (nextTarget: BackendTarget) => {
    const nextCapability = capabilities.find((capability) => capability.target === nextTarget);
    const nextOptions = backendDefaultsForTarget(nextTarget, backendOptions, nextCapability);
    onChange(nextTarget);
    onBackendOptionsChange(nextOptions);

    if (nextTarget === "statevector") {
      onNoiseProfileChange(null);
      return;
    }

    if (noiseProfile?.source === "backend_derived") {
      onNoiseProfileChange({
        ...noiseProfile,
        reference_backend: resolveNoiseReference(
          nextOptions,
          nextCapability,
          nextTarget,
          noiseReferenceDevices,
        ),
      });
    }
  };

  const handleBackendChoice = (choice: BackendPickerChoice) => {
    const nextOptions: BackendOptions =
      choice.kind === "policy"
        ? {
            ...backendOptions,
            selection_policy: choice.policy,
            backend_name: null,
          }
        : {
            ...backendOptions,
            selection_policy: "manual",
            backend_name: choice.device.name,
          };

    onBackendOptionsChange(nextOptions);
    if (noiseProfile?.source === "backend_derived") {
      onNoiseProfileChange({
        ...noiseProfile,
        reference_backend: resolveNoiseReference(
          nextOptions,
          selectedCapability,
          value,
          noiseReferenceDevices,
        ),
      });
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <BackendTargetCards
        selectedValue={value}
        disabled={disabled}
        capabilities={capabilities}
        capabilitiesLoading={capabilitiesLoading}
        capabilitiesRefreshing={capabilitiesRefreshing}
        capabilitiesWarmupProgress={capabilitiesWarmupProgress}
        capabilitiesError={capabilitiesError}
        error={error}
        onSelect={handleBackendTargetChange}
      />

      {isExpandedBackend ? (
        <BackendSectionExpanded
          mode={mode}
          value={value}
          backendOptions={backendOptions}
          selectedBackendDevice={selectedBackendDevice}
          selectableDevices={selectableDevices}
          capabilitiesLoading={capabilitiesLoading}
          disabled={disabled}
          error={error}
          onBackendChoice={handleBackendChoice}
          onRefreshCapabilities={onRefreshCapabilities}
          capabilitiesRefreshing={capabilitiesRefreshing}
          noiseSupported={noiseSupported}
          noiseProfile={noiseProfile}
          onNoiseProfileChange={onNoiseProfileChange}
          defaultNoiseProfile={defaultNoiseProfile}
          noiseReferenceDevices={noiseReferenceDevices}
          topologyPanelKey={topologyPanelKey}
          topologyDevice={topologyDevice}
          topologyMode={topologyMode}
          updateNumberOption={updateNumberOption}
          updateBackendOptions={updateBackendOptions}
        />
      ) : null}
    </div>
  );
}
