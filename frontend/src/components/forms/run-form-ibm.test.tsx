import "./run-form.test-mocks";

import { act, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import {
  api,
  getButtonById,
  notifyIbmCredentialProfilesChanged,
  renderRunForm,
  resetRunFormTestState,
} from "./run-form.test-support";
import type { BackendCapabilitiesResponse } from "./run-form.test-support";

beforeEach(resetRunFormTestState);

describe("RunForm IBM capability refresh", () => {
  it("uses cached IBM hardware without waiting for an extra form-side validation call", async () => {
    const user = userEvent.setup();
    vi.mocked(api.getBackendCapabilitiesCached).mockReturnValue({
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
          enabled: true,
          available: true,
          credential_configured: true,
          credentials_usable: true,
          supports_noise_profile: false,
          default_backend: "ibm_brisbane",
          backends: [
            {
              name: "ibm_brisbane",
              simulator: false,
              operational: true,
              pending_jobs: 1,
              num_qubits: 127,
              error_rate: 0.0012,
            },
          ],
        },
      ],
    });

    renderRunForm();
    await screen.findByText("Create Simulation Run");

    const ibmButton = getButtonById("backend-option-ibm_runtime");
    await waitFor(() => expect(ibmButton).toBeEnabled());
    await user.click(ibmButton);

    expect(ibmButton).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("combobox", { name: /backend/i })).toHaveTextContent(/least error/i);
    expect(api.forceRefreshBackendCapabilities).not.toHaveBeenCalled();
  });

  it("uses cached IBM capability state on first render without forcing a refresh", async () => {
    const user = userEvent.setup();
    vi.mocked(api.getBackendCapabilitiesCached).mockReturnValue({
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
          enabled: true,
          available: true,
          credential_configured: true,
          credentials_usable: true,
          supports_noise_profile: false,
          default_backend: "ibm_brisbane",
          backends: [
            {
              name: "ibm_brisbane",
              simulator: false,
              operational: true,
              pending_jobs: 1,
              num_qubits: 127,
              error_rate: 0.0012,
            },
          ],
        },
      ],
    });

    renderRunForm();
    await screen.findByText("Create Simulation Run");

    const ibmButton = getButtonById("backend-option-ibm_runtime");
    await waitFor(() => expect(ibmButton).toBeEnabled());
    expect(api.forceRefreshBackendCapabilities).not.toHaveBeenCalled();

    await user.click(ibmButton);
    expect(ibmButton).toHaveAttribute("aria-pressed", "true");
  });

  it("keeps IBM disabled when the cached backend state already marks the profile unusable", async () => {
    vi.mocked(api.getBackendCapabilitiesCached).mockReturnValue({
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
          credential_configured: true,
          credentials_usable: false,
          supports_noise_profile: false,
          reason:
            "IBM Runtime validation failed. Check the saved token, instance, channel, and network access.",
          backends: [],
        },
      ],
    });
    renderRunForm();
    await screen.findByText("Create Simulation Run");

    expect(
      await screen.findByText(
        "IBM Runtime validation failed. Check the saved token, instance, channel, and network access.",
      ),
    ).toBeInTheDocument();
    expect(document.getElementById("backend-option-ibm_runtime")).toBeDisabled();
  });

  it("shows an IBM refresh hint without blocking local backends", async () => {
    renderRunForm();
    await screen.findByText("Create Simulation Run");

    await act(async () => {
      notifyIbmCredentialProfilesChanged({
        backendCapabilitiesRefresh: "started",
        backendWarmupProgress: { loadedProfiles: 0, totalProfiles: 2 },
      });
    });

    const ibmButton = getButtonById("backend-option-ibm_runtime");
    expect(ibmButton).toHaveTextContent(/0\/2 ibm profiles loaded/i);
    expect(ibmButton.querySelector('[data-slot="spinner"]')).not.toBeNull();
    expect(getButtonById("backend-option-statevector")).toBeEnabled();
    expect(getButtonById("backend-option-aer_simulator")).toBeEnabled();
  });

  it("shows an IBM loading state on first load and enables it after refresh completes", async () => {
    let resolveRefresh: ((value: BackendCapabilitiesResponse) => void) | null = null;
    const refreshPromise = new Promise<BackendCapabilitiesResponse>((resolve) => {
      resolveRefresh = resolve;
    });
    vi.mocked(api.getBackendCapabilitiesCached).mockReturnValue(null);
    vi.mocked(api.forceRefreshBackendCapabilities).mockReturnValueOnce(refreshPromise);

    renderRunForm();
    await screen.findByText("Create Simulation Run");

    expect(getButtonById("backend-option-ibm_runtime")).toHaveTextContent(
      /loading ibm hardware backends/i,
    );
    expect(getButtonById("backend-option-ibm_runtime")).toBeDisabled();

    await act(async () => {
      resolveRefresh?.({
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
            enabled: true,
            available: true,
            credential_configured: true,
            credentials_usable: true,
            supports_noise_profile: false,
            backends: [
              {
                name: "ibm_brisbane",
                simulator: false,
                operational: true,
                pending_jobs: 3,
                num_qubits: 127,
                error_rate: 0.0011,
              },
            ],
            default_backend: "ibm_brisbane",
          },
        ],
      });
      await refreshPromise;
    });

    await waitFor(() => {
      expect(getButtonById("backend-option-ibm_runtime")).toBeEnabled();
    });
    expect(getButtonById("backend-option-ibm_runtime")).toHaveTextContent(
      /1 ibm hardware backend ready/i,
    );
  });

  it("refreshes IBM backend choices when the active profile changes while IBM is open", async () => {
    const user = userEvent.setup();
    let activeProfileId: string | null = "profile-1";
    const profile1Capabilities: BackendCapabilitiesResponse = {
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
          enabled: true,
          available: true,
          credential_configured: true,
          credentials_usable: true,
          supports_noise_profile: false,
          backends: [
            {
              name: "ibm_aachen",
              simulator: false,
              operational: true,
              pending_jobs: 0,
              num_qubits: 156,
              error_rate: 0.0009,
            },
          ],
          default_backend: "ibm_aachen",
        },
      ],
    };
    const profile2Capabilities: BackendCapabilitiesResponse = {
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
          enabled: true,
          available: true,
          credential_configured: true,
          credentials_usable: true,
          supports_noise_profile: false,
          backends: [
            {
              name: "ibm_berlin",
              simulator: false,
              operational: true,
              pending_jobs: 1,
              num_qubits: 120,
              error_rate: 0.0015,
            },
          ],
          default_backend: "ibm_berlin",
        },
      ],
    };
    vi.mocked(api.getBackendCapabilitiesCached).mockImplementation((profileId?: string | null) => {
      const resolvedProfileId = profileId ?? activeProfileId;
      return resolvedProfileId === "profile-2" ? profile2Capabilities : profile1Capabilities;
    });

    renderRunForm();
    await screen.findByText("Create Simulation Run");

    const ibmButton = getButtonById("backend-option-ibm_runtime");
    await waitFor(() => expect(ibmButton).toBeEnabled());
    await user.click(ibmButton);
    expect(screen.getByRole("combobox", { name: /backend/i })).toHaveTextContent(
      /least error: ibm_aachen/i,
    );

    await act(async () => {
      activeProfileId = "profile-2";
      notifyIbmCredentialProfilesChanged({
        activeProfileId: "profile-2",
        backendCapabilitiesRefresh: "started",
        backendWarmupProgress: { loadedProfiles: 0, totalProfiles: 2 },
      });
    });
    await waitFor(() => {
      expect(getButtonById("backend-option-ibm_runtime")).toHaveTextContent(
        /0\/2 ibm profiles loaded/i,
      );
    });
    await act(async () => {
      notifyIbmCredentialProfilesChanged({
        activeProfileId: "profile-2",
        backendCapabilitiesRefresh: "progress",
        backendWarmupProgress: { loadedProfiles: 1, totalProfiles: 2 },
      });
    });
    await waitFor(() => {
      expect(getButtonById("backend-option-ibm_runtime")).toHaveTextContent(
        /1\/2 ibm profiles loaded/i,
      );
    });
    await waitFor(() => {
      expect(screen.getByRole("combobox", { name: /backend/i })).toHaveTextContent(
        /least error: ibm_berlin/i,
      );
    });

    await act(async () => {
      notifyIbmCredentialProfilesChanged({
        activeProfileId: "profile-2",
        backendCapabilitiesRefresh: "completed",
        backendWarmupProgress: { loadedProfiles: 2, totalProfiles: 2 },
      });
    });

    await waitFor(() => {
      expect(screen.getByRole("combobox", { name: /backend/i })).toHaveTextContent(
        /least error: ibm_berlin/i,
      );
    });
  });

  it("shows backend-focused refresh copy for single-profile IBM refreshes", async () => {
    vi.mocked(api.getBackendCapabilitiesCached).mockReturnValue({
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
          enabled: true,
          available: true,
          credential_configured: true,
          credentials_usable: true,
          supports_noise_profile: false,
          backends: [
            {
              name: "ibm_brisbane",
              simulator: false,
              operational: true,
              pending_jobs: 3,
              num_qubits: 127,
              error_rate: 0.0011,
            },
          ],
          default_backend: "ibm_brisbane",
        },
      ],
    });
    renderRunForm();
    await screen.findByText("Create Simulation Run");

    await act(async () => {
      notifyIbmCredentialProfilesChanged({
        backendCapabilitiesRefresh: "started",
        backendWarmupProgress: { loadedProfiles: 0, totalProfiles: 1 },
      });
    });

    await act(async () => {
      notifyIbmCredentialProfilesChanged({
        backendCapabilitiesRefresh: "progress",
        backendWarmupProgress: { loadedProfiles: 0, totalProfiles: 1 },
      });
    });

    expect(getButtonById("backend-option-ibm_runtime")).toHaveTextContent(
      /refreshing 1 ibm hardware backend/i,
    );
  });
});
