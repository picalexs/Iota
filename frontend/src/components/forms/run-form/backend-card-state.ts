import type { IbmBackendStatus, IbmBackendWarmupProgress } from "@/lib/ibm-profile-events";
import type { BackendCapability, BackendTarget } from "@/types/run";
import { BACKEND_LABELS } from "./backend-section-shared";

export interface BackendCardStateInput {
  value: BackendTarget;
  capability: BackendCapability | undefined;
  selectable: boolean;
  capabilitiesLoading?: boolean;
  capabilitiesRefreshing?: boolean;
  capabilitiesWarmupProgress?: IbmBackendWarmupProgress | null;
}

interface BackendCardStateContext extends BackendCardStateInput {
  labels: (typeof BACKEND_LABELS)[BackendTarget];
  warmupLabel: string | null;
  ibmReadyLabel: string | null;
}

interface BackendCardStateRule {
  matches: (context: BackendCardStateContext) => boolean;
  message: (context: BackendCardStateContext) => string;
}

function formatProfileWarmupLabel(progress?: IbmBackendWarmupProgress | null): string | null {
  if (progress == null || progress.totalProfiles <= 1) {
    return null;
  }

  const loadedProfiles = Math.min(progress.loadedProfiles, progress.totalProfiles);
  const noun = progress.totalProfiles === 1 ? "profile" : "profiles";
  return `${loadedProfiles}/${progress.totalProfiles} IBM ${noun} loaded.`;
}

function formatIbmReadyLabel(capability: BackendCapability | undefined): string | null {
  if (capability?.target !== "ibm_runtime") {
    return null;
  }

  const backendCount = capability.backends?.length ?? 0;
  if (backendCount <= 0) {
    return null;
  }

  return `Loaded ${backendCount} IBM backend${backendCount === 1 ? "" : "s"}.`;
}

function formatIbmRefreshingLabel(capability: BackendCapability | undefined): string | null {
  if (capability?.target !== "ibm_runtime") {
    return null;
  }

  const backendCount = capability.backends?.length ?? 0;
  if (backendCount <= 0) {
    return null;
  }

  return `Refreshing IBM Runtime backends${backendCount > 0 ? ` (${backendCount} loaded)` : ""}…`;
}

export function getIbmBackendStatus(
  capability: BackendCapability | undefined,
  options: { loading?: boolean; refreshing?: boolean } = {},
): IbmBackendStatus {
  if (options.loading === true || options.refreshing === true) {
    return "loading";
  }
  if (capability?.credential_configured === false || capability?.credentials_usable === false) {
    return "inactive";
  }
  if ((capability?.backends?.length ?? 0) > 0 && capability?.enabled === true) {
    return "ready";
  }
  return "unavailable";
}

export function isBackendSelectable(capability: BackendCapability | undefined): boolean {
  if (capability?.target === "ibm_runtime") {
    return capability?.enabled === true && capability.credentials_usable !== false;
  }

  return (
    capability?.enabled === true &&
    capability?.available !== false &&
    capability?.credential_configured !== false
  );
}

const BACKEND_CARD_STATE_RULES: readonly BackendCardStateRule[] = [
  {
    matches: ({ capabilitiesLoading, value }) =>
      capabilitiesLoading === true && value === "ibm_runtime",
    message: ({ warmupLabel }) => warmupLabel ?? "Loading IBM hardware backends...",
  },
  {
    matches: ({ capabilitiesRefreshing, value }) =>
      capabilitiesRefreshing === true && value === "ibm_runtime",
    message: ({ warmupLabel, capability }) =>
      warmupLabel ?? formatIbmRefreshingLabel(capability) ?? "Refreshing IBM hardware backends...",
  },
  {
    matches: ({ capabilitiesLoading, value, selectable, ibmReadyLabel }) =>
      capabilitiesLoading !== true &&
      value === "ibm_runtime" &&
      selectable &&
      ibmReadyLabel != null,
    message: ({ ibmReadyLabel }) => ibmReadyLabel ?? "",
  },
  {
    matches: ({ capabilitiesLoading, selectable }) => capabilitiesLoading !== true && selectable,
    message: ({ capability, labels }) => capability?.reason ?? labels.subtitle,
  },
  {
    matches: ({ capabilitiesLoading, capability }) =>
      capabilitiesLoading !== true && capability?.credential_configured === false,
    message: () =>
      "Save and activate an encrypted IBM profile in Settings to enable hardware backends.",
  },
  {
    matches: ({ capabilitiesLoading, capability }) =>
      capabilitiesLoading !== true &&
      capability?.target === "ibm_runtime" &&
      capability.credentials_usable === false,
    message: ({ capability }) =>
      capability?.reason ?? "The saved IBM profile could not be validated.",
  },
  {
    matches: ({ capabilitiesLoading, selectable }) => capabilitiesLoading !== true && !selectable,
    message: ({ capability }) => capability?.reason ?? "This backend is unavailable right now.",
  },
];

export function getBackendCardStateText(input: BackendCardStateInput): string {
  const context: BackendCardStateContext = {
    ...input,
    labels: BACKEND_LABELS[input.value],
    warmupLabel: formatProfileWarmupLabel(input.capabilitiesWarmupProgress),
    ibmReadyLabel: formatIbmReadyLabel(input.capability),
  };
  const matchingRule = BACKEND_CARD_STATE_RULES.find((rule) => rule.matches(context));
  return matchingRule?.message(context) ?? context.labels.subtitle;
}
