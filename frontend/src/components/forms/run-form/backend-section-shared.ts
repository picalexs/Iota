import type {
  BackendCapability,
  BackendDeviceSummary,
  BackendOptions,
  BackendTarget,
  NoiseProfile,
} from "@/types/run";

export const POLICY_LEAST_ERROR_VALUE = "policy:least_error";
export const POLICY_LEAST_BUSY_VALUE = "policy:least_busy";
export const DEFAULT_NOISE_REFERENCE_BACKEND = "ibm_brisbane";
export const DEFAULT_TOPOLOGY_COLOR = "#6f8fdc";

type OptionalBackendDevice = BackendDeviceSummary | null | undefined;
type OptionalNumber = number | null | undefined;

export const BACKEND_LABELS: Record<BackendTarget, { label: string; subtitle: string }> = {
  statevector: {
    label: "Statevector",
    subtitle: "Exact local simulator; deterministic and queue-free.",
  },
  aer_simulator: {
    label: "Aer local simulator",
    subtitle: "Local Qiskit AerSimulator with optional IBM-style noise.",
  },
  ibm_runtime: {
    label: "IBM Runtime",
    subtitle: "Hardware backend selected from your IBM Runtime account.",
  },
};

export const IBM_PROCESSOR_OVERRIDES: Record<
  string,
  { family: string; revision?: string; layout: string }
> = {
  ibm_miami: {
    family: "Nighthawk",
    layout: "10 x 12 square lattice",
  },
  ibm_boston: {
    family: "Heron",
    revision: "r3",
    layout: "Heavy-hex lattice",
  },
  ibm_pittsburgh: {
    family: "Heron",
    revision: "r3",
    layout: "Heavy-hex lattice",
  },
  ibm_kingston: {
    family: "Heron",
    revision: "r2",
    layout: "Heavy-hex lattice",
  },
  ibm_fez: {
    family: "Heron",
    revision: "r2",
    layout: "Heavy-hex lattice",
  },
  ibm_marrakesh: {
    family: "Heron",
    layout: "Heavy-hex lattice",
  },
};

export type BackendPolicyChoice = "least_error" | "least_busy";

export type BackendPickerChoice =
  | {
      id: typeof POLICY_LEAST_ERROR_VALUE | typeof POLICY_LEAST_BUSY_VALUE;
      kind: "policy";
      policy: BackendPolicyChoice;
      label: string;
      description: string;
      suggestedDevice: BackendDeviceSummary | null;
    }
  | {
      id: string;
      kind: "device";
      device: BackendDeviceSummary;
    };

export type TopologyMetric = "readout_error" | "t1_us" | "t2_us";
export type TopologySortMode = "none" | "ascending" | "descending";
export type BackendTopologyView = "map" | "graph" | "table";

export function getSelectableDevices(
  target: BackendTarget | null,
  capability: BackendCapability | null,
): BackendDeviceSummary[] {
  if (target == null || target === "statevector") return [];

  const devices =
    capability?.backends?.filter(
      (device): device is BackendDeviceSummary =>
        typeof device?.name === "string" && device.name.trim().length > 0,
    ) ?? [];
  if (devices.length > 0) return devices;

  if (target === "aer_simulator") {
    return [
      {
        name: capability?.default_backend ?? "aer_simulator",
        simulator: true,
        operational: true,
        pending_jobs: 0,
        num_qubits: null,
        error_rate: 0,
      },
    ];
  }

  return [];
}

export function getNoiseReferenceDevices(
  capability: BackendCapability | null | undefined,
): BackendDeviceSummary[] {
  return (
    capability?.backends
      ?.filter(
        (device): device is BackendDeviceSummary =>
          typeof device?.name === "string" && device.name.trim().length > 0,
      )
      .filter((device) => device.operational !== false) ?? []
  );
}

export function getNoiseReferenceDevice(
  noiseProfile: NoiseProfile | null,
  devices: BackendDeviceSummary[],
): BackendDeviceSummary | null {
  if (noiseProfile?.source !== "backend_derived") return null;
  return (
    devices.find((device) => device.name === noiseProfile.reference_backend) ?? {
      name: noiseProfile.reference_backend,
      simulator: false,
      operational: true,
      pending_jobs: null,
      num_qubits: null,
      error_rate: null,
    }
  );
}

export function buildNoiseReferenceOptions(
  devices: BackendDeviceSummary[],
  noiseProfile: NoiseProfile | null,
): BackendDeviceSummary[] {
  if (
    noiseProfile?.source === "backend_derived" &&
    noiseProfile.reference_backend.trim().length > 0 &&
    !devices.some((device) => device.name === noiseProfile.reference_backend)
  ) {
    return [
      {
        name: noiseProfile.reference_backend,
        simulator: false,
        operational: true,
        pending_jobs: null,
        num_qubits: null,
        error_rate: null,
      },
      ...devices,
    ];
  }
  return devices;
}

export function getSuggestedBackendDevices(
  devices: BackendDeviceSummary[],
): BackendDeviceSummary[] {
  const suggested = [leastErrorDevice(devices), leastBusyDevice(devices)].filter(
    (device): device is BackendDeviceSummary => device != null,
  );
  const seen = new Set<string>();

  return suggested.filter((device) => {
    if (seen.has(device.name)) {
      return false;
    }
    seen.add(device.name);
    return true;
  });
}

export function filterSuggestedBackendDevices(
  devices: BackendDeviceSummary[],
): BackendDeviceSummary[] {
  const suggestedNames = new Set(getSuggestedBackendDevices(devices).map((device) => device.name));
  return devices.filter((device) => !suggestedNames.has(device.name));
}

export function backendDefaultsForTarget(
  target: BackendTarget,
  current: BackendOptions,
  capability: BackendCapability | undefined,
): BackendOptions {
  const devices = getSelectableDevices(target, capability ?? null);

  if (target === "statevector") {
    return {
      ...current,
      selection_policy: "manual",
      backend_name: null,
      seed_simulator: null,
      seed_transpiler: null,
    };
  }

  if (target === "aer_simulator") {
    return {
      ...current,
      selection_policy: "manual",
      backend_name: devices[0]?.name ?? "aer_simulator",
      aer_method: current.aer_method ?? "automatic",
    };
  }

  return {
    ...current,
    selection_policy: "least_error",
    backend_name: null,
    seed_simulator: null,
  };
}

export function resolveNoiseReference(
  options: BackendOptions,
  capability: BackendCapability | null | undefined,
  target: BackendTarget | null,
  noiseReferenceDevices: BackendDeviceSummary[],
): string {
  if (target === "aer_simulator") {
    return noiseReferenceDevices[0]?.name ?? DEFAULT_NOISE_REFERENCE_BACKEND;
  }

  return (
    options.backend_name?.trim() ||
    capability?.default_backend ||
    capability?.backends?.[0]?.name ||
    target ||
    DEFAULT_NOISE_REFERENCE_BACKEND
  );
}

export function selectedBackendChoiceId(
  target: BackendTarget,
  options: BackendOptions,
  devices: BackendDeviceSummary[],
): string {
  if (target === "ibm_runtime" && options.selection_policy === "least_error") {
    return POLICY_LEAST_ERROR_VALUE;
  }
  if (target === "ibm_runtime" && options.selection_policy === "least_busy") {
    return POLICY_LEAST_BUSY_VALUE;
  }

  const selectedName = options.backend_name ?? devices[0]?.name;
  return selectedName != null ? backendDeviceChoiceId(selectedName) : "";
}

export function buildBackendChoices(
  target: BackendTarget,
  devices: BackendDeviceSummary[],
): BackendPickerChoice[] {
  const suggestions: BackendPickerChoice[] =
    target === "ibm_runtime"
      ? [
          {
            id: POLICY_LEAST_ERROR_VALUE,
            kind: "policy",
            policy: "least_error",
            label: "Least error",
            description: "Automatically choose the backend with the lowest reported error.",
            suggestedDevice: leastErrorDevice(devices),
          },
          {
            id: POLICY_LEAST_BUSY_VALUE,
            kind: "policy",
            policy: "least_busy",
            label: "Least busy",
            description: "Automatically choose the shortest queue that fits the circuit.",
            suggestedDevice: leastBusyDevice(devices),
          },
        ]
      : [];

  return [
    ...suggestions,
    ...devices.map((device) => ({
      id: backendDeviceChoiceId(device.name),
      kind: "device" as const,
      device,
    })),
  ];
}

export function getSelectedBackendDevice(
  target: BackendTarget | null,
  options: BackendOptions,
  devices: BackendDeviceSummary[],
): BackendDeviceSummary | null {
  if (devices.length === 0) return null;
  if (target === "ibm_runtime" && options.selection_policy === "least_error") {
    return leastErrorDevice(devices);
  }
  if (target === "ibm_runtime" && options.selection_policy === "least_busy") {
    return leastBusyDevice(devices);
  }
  return devices.find((device) => device.name === options.backend_name) ?? devices[0] ?? null;
}

export function backendChoiceLabel(choice: BackendPickerChoice): string {
  if (choice.kind === "device") return choice.device.name;
  return choice.suggestedDevice != null
    ? `${choice.label}: ${choice.suggestedDevice.name}`
    : choice.label;
}

export function backendChoiceSearchValue(choice: BackendPickerChoice): string {
  if (choice.kind === "device") {
    return `${choice.device.name} ${processorTypeLabel(choice.device) ?? ""} ${formatBackendPickerSummary(choice.device)}`;
  }
  return `${choice.label} ${choice.description} ${processorTypeLabel(choice.suggestedDevice) ?? ""} ${formatBackendPickerSummary(choice.suggestedDevice)}`;
}

export function suggestedBackendSummary(
  choice: Extract<BackendPickerChoice, { kind: "policy" }>,
): string {
  if (choice.suggestedDevice == null) return choice.description;
  return formatBackendPickerSummary(choice.suggestedDevice, { includeProcessor: false });
}

export function formatBackendPickerSummary(
  device: OptionalBackendDevice,
  options?: { includeProcessor?: boolean },
): string {
  if (device == null) return "Backend metadata unavailable";
  if (device.simulator === true) return formatBackendDetails(device);

  const parts = [
    options?.includeProcessor === false ? null : processorTypeLabel(device),
    formatQueue(device.pending_jobs),
    formatQubits(device.num_qubits),
    formatErrorRate(device.error_rate),
  ].filter((value): value is string => value != null);
  return parts.join(" · ");
}

export function processorTypeLabel(device: OptionalBackendDevice): string | null {
  const normalizedName = device?.name?.trim().toLowerCase() ?? "";
  const fallback = IBM_PROCESSOR_OVERRIDES[normalizedName];
  const family = device?.processor_type?.family?.trim() ?? fallback?.family ?? null;
  const revision = device?.processor_type?.revision?.trim() ?? fallback?.revision ?? null;
  if (!family) return null;
  return revision ? `${family} ${revision}` : family;
}

export function formatQueue(pendingJobs: OptionalNumber): string {
  if (pendingJobs == null) return "Queue unknown";
  if (pendingJobs === 0) return "No queue";
  return pendingJobs === 1 ? "1 in queue" : `${pendingJobs} in queue`;
}

export function formatQubits(numQubits: OptionalNumber): string {
  if (numQubits == null) return "Qubits flexible";
  return numQubits === 1 ? "1 qubit" : `${numQubits} qubits`;
}

export function formatErrorRate(errorRate: OptionalNumber): string {
  if (errorRate == null) return "Calibration unavailable";
  if (errorRate === 0) return "Ideal/no error";
  const percentage = errorRate * 100;
  return `${percentage < 0.01 ? percentage.toPrecision(2) : percentage.toFixed(2)}% error`;
}

function formatBackendDetails(device: OptionalBackendDevice): string {
  if (device == null) return "Backend metadata unavailable";
  if (device.simulator === true) return "Local simulator · no queue · ideal by default";
  return `${formatQueue(device.pending_jobs)} · ${formatQubits(device.num_qubits)} · ${formatErrorRate(
    device.error_rate,
  )}`;
}

export function leastErrorDevice(devices: BackendDeviceSummary[]): BackendDeviceSummary | null {
  return (
    [...devices]
      .filter((device) => device.error_rate != null)
      .sort((a, b) => (a.error_rate ?? Number.POSITIVE_INFINITY) - (b.error_rate ?? 0))[0] ??
    leastBusyDevice(devices)
  );
}

export function leastBusyDevice(devices: BackendDeviceSummary[]): BackendDeviceSummary | null {
  return (
    [...devices].sort(
      (a, b) =>
        (a.pending_jobs ?? Number.POSITIVE_INFINITY) - (b.pending_jobs ?? Number.POSITIVE_INFINITY),
    )[0] ?? null
  );
}

function backendDeviceChoiceId(name: string): string {
  return `device:${name}`;
}
