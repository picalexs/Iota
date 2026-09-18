import "./run-form.test-mocks";

import { screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import {
  api,
  getAlgorithmButton,
  getBackendButton,
  getButtonById,
  getSectionChip,
  neverSettles,
  renderRunForm,
  resetRunFormTestState,
  validateRunRequest,
} from "./run-form.test-support";
import type { MoleculeListResponse } from "./run-form.test-support";

beforeEach(resetRunFormTestState);

describe("RunForm shell", () => {
  it("renders the form shell while molecules are still loading", () => {
    vi.mocked(api.fetchMolecules).mockReturnValue(neverSettles<MoleculeListResponse>());
    vi.mocked(api.fetchBasisSets).mockReturnValue(
      neverSettles<Awaited<ReturnType<typeof api.fetchBasisSets>>>(),
    );
    vi.mocked(api.fetchRunConfigMetadata).mockReturnValue(
      neverSettles<Awaited<ReturnType<typeof api.fetchRunConfigMetadata>>>(),
    );
    vi.mocked(api.forceRefreshBackendCapabilities).mockReturnValue(
      neverSettles<Awaited<ReturnType<typeof api.forceRefreshBackendCapabilities>>>(),
    );
    renderRunForm();
    expect(screen.getByText("Create Simulation Run")).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: /molecule/i })).toBeDisabled();
    expect(screen.getByText(/loading molecules/i)).toBeInTheDocument();
    expect(screen.getByText(/^Loading molecule library\.\.\.$/)).toBeInTheDocument();
  });

  it("renders form heading and core controls after loading", async () => {
    renderRunForm();
    await waitFor(() => {
      expect(screen.getByText("Create Simulation Run")).toBeInTheDocument();
    });

    expect(screen.getByRole("group", { name: /algorithm selection/i })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: /mode selection/i })).toBeInTheDocument();
    expect(screen.getByText("Statevector")).toBeInTheDocument();
    expect(screen.getByText("Aer local simulator")).toBeInTheDocument();
    expect(screen.getByText("IBM Runtime")).toBeInTheDocument();
    expect(screen.getByRole("group", { name: /accuracy/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /quick scan/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /production default/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /high accuracy/i })).toBeInTheDocument();
  });

  it("does not render validation warnings from any algorithm", async () => {
    const user = userEvent.setup();
    vi.mocked(validateRunRequest).mockResolvedValue({
      valid: true,
      errors: [],
      warnings: [
        "KQD/QFD IBM Runtime execution measures projected Hamiltonian and overlap matrix elements with branch-state Estimator circuits; the final generalized eigensolve remains local.",
        "Estimated runtime may vary with backend queue depth.",
      ],
      estimate: null,
    });

    renderRunForm();
    await screen.findByText("Create Simulation Run");

    await user.click(getBackendButton());

    const moleculeSelect = screen.getByRole("combobox", { name: /molecule/i });
    await user.click(moleculeSelect);
    await user.click(screen.getByRole("option", { name: /H2.*sto-3g/i }));
    await user.click(getAlgorithmButton());

    await waitFor(() => {
      expect(validateRunRequest).toHaveBeenCalled();
    });

    expect(screen.queryByText("Warnings:")).not.toBeInTheDocument();
    expect(
      screen.queryByText(/KQD\/QFD IBM Runtime execution measures projected Hamiltonian/i),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/Estimated runtime may vary with backend queue depth/i),
    ).not.toBeInTheDocument();
  });

  it("renders form sections in the updated order", async () => {
    renderRunForm();
    await screen.findByText("Create Simulation Run");

    const sectionHeadings = screen
      .getAllByRole("heading", { level: 2 })
      .map((heading) => heading.textContent);

    expect(sectionHeadings).toEqual(["Molecule", "Mode", "Backend", "Algorithm & Guided Preset"]);
  });

  it("starts with backend and algorithm unselected and only turns chips green in order", async () => {
    const user = userEvent.setup();
    renderRunForm();
    await screen.findByText("Create Simulation Run");

    expect(getBackendButton()).toHaveAttribute("aria-pressed", "false");
    expect(getAlgorithmButton()).toHaveAttribute("aria-pressed", "false");
    expect(getSectionChip("Mode")).toHaveAttribute("data-status", "idle");
    expect(getSectionChip("Backend")).toHaveAttribute("data-status", "idle");
    expect(getSectionChip("Algorithm & Guided Preset")).toHaveAttribute("data-status", "idle");

    await user.click(getBackendButton());
    expect(getSectionChip("Backend")).toHaveAttribute("data-status", "idle");

    const moleculeSelect = screen.getByRole("combobox", { name: /molecule/i });
    await user.click(moleculeSelect);
    await user.click(screen.getByRole("option", { name: /H2.*sto-3g/i }));

    expect(getSectionChip("Molecule")).toHaveAttribute("data-status", "ok");
    expect(getSectionChip("Mode")).toHaveAttribute("data-status", "ok");
    expect(getSectionChip("Backend")).toHaveAttribute("data-status", "ok");
    expect(getSectionChip("Algorithm & Guided Preset")).toHaveAttribute("data-status", "idle");

    await user.click(getAlgorithmButton());
    expect(getSectionChip("Algorithm & Guided Preset")).toHaveAttribute("data-status", "ok");
  });

  it("allows Aer selection and enables noise controls", async () => {
    const user = userEvent.setup();
    renderRunForm();
    await screen.findByText("Create Simulation Run");

    const aerButton = getButtonById("backend-option-aer_simulator");
    await waitFor(() => expect(aerButton).toBeEnabled());
    await user.click(aerButton);

    expect(aerButton).toHaveAttribute("aria-pressed", "true");
    const noiseToggle = screen.getByRole("checkbox", { name: /noise model/i });
    expect(noiseToggle).toBeEnabled();

    await user.click(noiseToggle);
    expect(
      screen.getByText(
        /the run stays local on aer while the noise model uses a live calibration snapshot/i,
      ),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /manual/i }));
    expect(await screen.findByRole("combobox", { name: /noise source/i })).toBeInTheDocument();
  });

  it("shows IBM credential state from the backend capability API", async () => {
    renderRunForm();
    await screen.findByText("Create Simulation Run");

    expect(
      await screen.findByText(
        "Save and activate an encrypted IBM profile in Settings to enable hardware backends.",
      ),
    ).toBeInTheDocument();
    expect(document.getElementById("backend-option-ibm_runtime")).toBeDisabled();
  });
});
