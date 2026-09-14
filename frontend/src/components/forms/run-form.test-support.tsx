import { render, screen, type RenderResult } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { vi } from "vitest";
import { RunForm } from "./run-form";
import { getRunFormTestMocks } from "./run-form.test-mocks";
export { getRunFormTestMocks } from "./run-form.test-mocks";
import { ThemeProvider } from "@/context/theme-context";
import { TooltipProvider } from "@/components/ui/tooltip";
import * as backendsApi from "@/api/backends";
import * as httpApi from "@/api/http";
import * as moleculesApi from "@/api/molecules";
import * as profilesApi from "@/api/profiles";
import * as runsApi from "@/api/runs";
import { validateRunRequest } from "@/api/runs";
import { notifyIbmCredentialProfilesChanged } from "@/lib/ibm-profile-events";
import type {
  BackendCapabilitiesResponse,
  MoleculeResponse,
  MoleculeListResponse,
  RunResponse,
} from "@/types/run";

const api = {
  ...backendsApi,
  ...httpApi,
  ...moleculesApi,
  ...profilesApi,
  ...runsApi,
};

export const mockMolecules: MoleculeResponse[] = [
  {
    id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    name: "H2",
    atoms: [
      { symbol: "H", x: 0, y: 0, z: 0 },
      { symbol: "H", x: 0, y: 0, z: 0.735 },
    ],
    basis_set: "sto-3g",
    charge: 0,
    multiplicity: 1,
    active_space: null,
    created_at: "2025-06-01T10:00:00Z",
    updated_at: "2025-06-01T10:00:00Z",
  },
  {
    id: "b2c3d4e5-f6a7-8901-bcde-f12345678901",
    name: "H2O",
    atoms: [
      { symbol: "O", x: 0, y: 0, z: 0 },
      { symbol: "H", x: 0, y: 0.757, z: 0.586 },
      { symbol: "H", x: 0, y: -0.757, z: 0.586 },
    ],
    basis_set: "6-31g",
    charge: 0,
    multiplicity: 1,
    active_space: null,
    created_at: "2025-06-01T10:00:00Z",
    updated_at: "2025-06-01T10:00:00Z",
  },
];

export function getSectionChip(title: string) {
  const heading = screen.getByRole("heading", { level: 2, name: title });
  const chip = heading.parentElement?.previousElementSibling;
  if (!(chip instanceof HTMLElement)) {
    throw new TypeError(`Unable to find status chip for ${title}`);
  }
  return chip;
}

export function getButtonById(id: string) {
  const button = document.getElementById(id);
  if (!(button instanceof HTMLButtonElement)) {
    throw new TypeError(`Unable to find button ${id}`);
  }
  return button;
}

export function getBackendButton() {
  return getButtonById("backend-option-statevector");
}

export function getAlgorithmButton(algorithm: string = "vqe") {
  return getButtonById(`algorithm-option-${algorithm}`);
}

export function getTopologyNodeLabelCount() {
  return document.querySelectorAll('svg[aria-label="Backend qubit topology map"] text').length;
}

export function neverSettles<T>() {
  return new Promise<T>(() => {
    // Intentionally pending for loading-state assertions.
  });
}

export function createRunResponse(id: string): RunResponse {
  const molecule = mockMolecules[0];
  if (!molecule) {
    throw new Error("Expected a mock molecule");
  }
  return {
    id,
    molecule_id: molecule.id,
    status: "QUEUED",
    config_json: {},
    ibm_job_id: null,
    client_request_id: null,
    versions: null,
    metadata: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  };
}

export function hasLegacyConfigKey(value: unknown) {
  return typeof value === "object" && value !== null && "config" in value;
}

export function renderRunForm(theme: "light" | "dark" | "system" = "light"): RenderResult {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <ThemeProvider defaultTheme={theme} storageKey="test-theme">
          <RunForm />
        </ThemeProvider>
      </TooltipProvider>
    </QueryClientProvider>,
  );
}

export function resetRunFormTestState() {
  vi.clearAllMocks();
  getRunFormTestMocks().invalidateQueries.mockResolvedValue(undefined);
  vi.mocked(api.fetchMolecules).mockResolvedValue({
    items: mockMolecules,
    total: mockMolecules.length,
  });
  vi.mocked(api.fetchBasisSets).mockResolvedValue({
    default_basis_set: "sto-3g",
    basis_sets: [
      {
        id: "sto-3g",
        label: "STO-3G",
        description: "Minimal basis",
        family: "minimal",
        recommended: true,
        supported_elements: [],
      },
      {
        id: "6-31g",
        label: "6-31G",
        description: "Split-valence basis",
        family: "pople",
        recommended: false,
        supported_elements: [],
      },
    ],
  });
  vi.mocked(api.fetchBackendCapabilities).mockResolvedValue({
    backends: [
      {
        target: "statevector",
        enabled: true,
        available: true,
        supports_noise_profile: false,
      },
      {
        target: "aer_simulator",
        enabled: true,
        available: true,
        supports_noise_profile: true,
        default_backend: "aer_simulator",
        backends: [
          {
            name: "aer_simulator",
            simulator: true,
            operational: true,
            pending_jobs: 0,
            num_qubits: null,
            error_rate: 0,
          },
        ],
      },
      {
        target: "ibm_runtime",
        enabled: false,
        available: false,
        credential_configured: false,
        supports_noise_profile: false,
        reason:
          "Save and activate an encrypted IBM profile in Settings to enable hardware backends.",
      },
    ],
  });
  vi.mocked(api.forceRefreshBackendCapabilities).mockResolvedValue({
    backends: [
      {
        target: "statevector",
        enabled: true,
        available: true,
        supports_noise_profile: false,
      },
      {
        target: "aer_simulator",
        enabled: true,
        available: true,
        supports_noise_profile: true,
        default_backend: "aer_simulator",
        backends: [
          {
            name: "aer_simulator",
            simulator: true,
            operational: true,
            pending_jobs: 0,
            num_qubits: null,
            error_rate: 0,
          },
        ],
      },
      {
        target: "ibm_runtime",
        enabled: false,
        available: false,
        credential_configured: false,
        supports_noise_profile: false,
        reason:
          "Save and activate an encrypted IBM profile in Settings to enable hardware backends.",
      },
    ],
  });
  vi.mocked(api.fetchRunConfigMetadata).mockResolvedValue({
    catalog_version: "2026-09-11-v21",
    algorithms: ["vqe", "qse", "kqd", "qfd", "sqd", "skqd"],
    backend_targets: ["statevector", "aer_simulator", "ibm_runtime"],
    easy_goals: ["fastest", "balanced", "best_accuracy"],
    easy_goal_presets: [
      { goal: "fastest", label: "5.0 mHa", chemical_accuracy_target_ha: 5e-3 },
      { goal: "balanced", label: "1.6 mHa", chemical_accuracy_target_ha: 1.6e-3 },
      { goal: "best_accuracy", label: "0.5 mHa", chemical_accuracy_target_ha: 5e-4 },
    ],
    ansatzes: [
      {
        id: "NumberPreserving",
        label: "NumberPreserving",
        aliases: [],
        description: null,
        supported_algorithms: ["vqe"],
        metadata: {},
      },
      {
        id: "EfficientSU2",
        label: "EfficientSU2",
        aliases: [],
        description: null,
        supported_algorithms: ["vqe", "qse"],
        metadata: {},
      },
      {
        id: "TwoLocal",
        label: "TwoLocal",
        aliases: [],
        description: null,
        supported_algorithms: ["vqe", "qse"],
        metadata: {},
      },
    ],
    optimizers: [
      {
        id: "COBYLA",
        label: "COBYLA",
        aliases: [],
        description: null,
        supported_algorithms: ["vqe", "qse"],
        metadata: {},
      },
      {
        id: "L_BFGS_B",
        label: "L-BFGS-B",
        aliases: [],
        description: null,
        supported_algorithms: ["vqe", "qse"],
        metadata: {},
      },
    ],
    defaults: {},
    limits: {},
    capabilities: {},
  });
  vi.mocked(api.getBackendCapabilitiesCached).mockReturnValue(null);
  vi.mocked(api.listIbmCredentialProfiles).mockResolvedValue({
    profiles: [],
    active_profile_id: null,
    encryption_key_source: "env",
    encryption_warning: null,
  });
  vi.mocked(api.previewTranspilation).mockResolvedValue({
    available: true,
    backend_name: "aer_simulator",
    transpiled_depth: 12,
    num_qubits: 4,
    warnings: [],
  });
  vi.mocked(api.testIbmCredentialProfile).mockResolvedValue({
    id: "profile-1",
    ok: false,
    message:
      "IBM Runtime validation failed. Check the saved token, instance, channel, and network access.",
  });
  vi.mocked(validateRunRequest).mockResolvedValue({
    valid: true,
    errors: [],
    warnings: [],
    estimate: null,
  });
}

export { api, notifyIbmCredentialProfilesChanged, validateRunRequest };
export type { BackendCapabilitiesResponse, MoleculeResponse, MoleculeListResponse, RunResponse };
