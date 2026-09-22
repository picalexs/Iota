import "./run-form.test-mocks";

import { act, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import type { BackendCapabilitiesResponse } from "@/types/run";
import {
  api,
  getButtonById,
  getTopologyNodeLabelCount,
  notifyIbmCredentialProfilesChanged,
  renderRunForm,
  resetRunFormTestState,
} from "./run-form.test-support";

beforeEach(resetRunFormTestState);

describe("RunForm topology", () => {
  it("does not render a synthetic topology without an IBM profile", async () => {
    const user = userEvent.setup();
    renderRunForm();
    await screen.findByText("Create Simulation Run");

    const aerButton = getButtonById("backend-option-aer_simulator");
    await waitFor(() => expect(aerButton).toBeEnabled());
    await user.click(aerButton);
    await user.click(screen.getByRole("checkbox", { name: /noise model/i }));

    await waitFor(() => {
      expect(screen.queryByText("Backend topology")).not.toBeInTheDocument();
      expect(getTopologyNodeLabelCount()).toBe(0);
    });
  });

  it("updates the topology panel when the active IBM profile changes", async () => {
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
    vi.mocked(api.getBackendCapabilitiesCached).mockImplementation((profileId?: string | null) => {
      const resolvedProfileId = profileId ?? activeProfileId;
      return resolvedProfileId === "profile-2" ? profile2Capabilities : profile1Capabilities;
    });

    renderRunForm();
    await screen.findByText("Create Simulation Run");

    const ibmButton = getButtonById("backend-option-ibm_runtime");
    await waitFor(() => expect(ibmButton).toBeEnabled());
    await user.click(ibmButton);

    await waitFor(() => {
      expect(screen.getByRole("combobox", { name: /backend/i })).toHaveTextContent(
        /least error: ibm_berlin/i,
      );
      expect(getTopologyNodeLabelCount()).toBeGreaterThanOrEqual(120);
      expect(getTopologyNodeLabelCount()).toBeLessThan(156);
    });

    await act(async () => {
      activeProfileId = "profile-2";
      notifyIbmCredentialProfilesChanged({
        activeProfileId: "profile-2",
        backendCapabilitiesRefresh: "completed",
      });
    });

    await waitFor(() => {
      expect(screen.getByRole("combobox", { name: /backend/i })).toHaveTextContent(
        /least error: ibm_aachen/i,
      );
      expect(getTopologyNodeLabelCount()).toBeGreaterThanOrEqual(156);
    });
  });

  it("updates the topology panel when selecting a different IBM backend from the list", async () => {
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
          default_backend: "ibm_berlin",
          backends: [
            {
              name: "ibm_berlin",
              simulator: false,
              operational: true,
              pending_jobs: 1,
              num_qubits: 120,
              error_rate: 0.0015,
            },
            {
              name: "ibm_aachen",
              simulator: false,
              operational: true,
              pending_jobs: 0,
              num_qubits: 156,
              error_rate: 0.0009,
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

    await waitFor(() => {
      expect(screen.getByRole("combobox", { name: /backend/i })).toHaveTextContent(
        /least error: ibm_aachen/i,
      );
      expect(getTopologyNodeLabelCount()).toBeGreaterThanOrEqual(156);
    });

    await user.click(screen.getByRole("combobox", { name: /backend/i }));
    await user.click(screen.getByRole("option", { name: /^ibm_berlin/i }));

    await waitFor(() => {
      expect(screen.getByRole("combobox", { name: /backend/i })).toHaveTextContent(/ibm_berlin/i);
      expect(getTopologyNodeLabelCount()).toBeGreaterThanOrEqual(120);
      expect(getTopologyNodeLabelCount()).toBeLessThan(156);
    });
  });
});
