import "./run-form.test-mocks";

import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import {
  api,
  getAlgorithmButton,
  getBackendButton,
  mockMolecules,
  renderRunForm,
  resetRunFormTestState,
} from "./run-form.test-support";

beforeEach(resetRunFormTestState);

describe("RunForm molecule and configuration validation", () => {
  it("keeps the error summary hidden until submit is attempted", async () => {
    const user = userEvent.setup();
    renderRunForm();
    await screen.findByText("Create Simulation Run");

    const moleculeSelect = screen.getByRole("combobox", { name: /molecule/i });
    await user.click(moleculeSelect);
    await user.click(screen.getByRole("option", { name: /H2.*sto-3g/i }));
    await user.click(getBackendButton());
    await user.click(getAlgorithmButton());
    await user.click(screen.getByRole("button", { name: /manual/i }));
    await user.click(screen.getByRole("button", { name: /show/i }));

    const optimizerOptionsInput = await screen.findByLabelText(/optimizer options/i);
    fireEvent.change(optimizerOptionsInput, { target: { value: "foo" } });
    await user.tab();

    expect(screen.queryByText(/please fix the following errors/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /create run/i })).toBeEnabled();

    await user.click(screen.getByRole("button", { name: /create run/i }));

    await waitFor(() => {
      expect(screen.getAllByRole("alert").length).toBeGreaterThan(0);
    });
  });

  it("fetches and populates molecules in the dropdown", async () => {
    const user = userEvent.setup();
    renderRunForm();

    await waitFor(() => {
      expect(screen.getByText("Create Simulation Run")).toBeInTheDocument();
    });

    const moleculeSelect = screen.getByRole("combobox", { name: /molecule/i });
    await user.click(moleculeSelect);

    await waitFor(() => {
      const h2Options = screen.getAllByText("H2");
      const h2oOptions = screen.getAllByText("H2O");
      expect(h2Options.length).toBeGreaterThan(0);
      expect(h2oOptions.length).toBeGreaterThan(0);
    });
  });

  it("shows a molecule info link after selection", async () => {
    const user = userEvent.setup();
    renderRunForm();
    await screen.findByText("Create Simulation Run");

    const moleculeSelect = screen.getByRole("combobox", { name: /molecule/i });
    await user.click(moleculeSelect);
    await user.click(screen.getByRole("option", { name: /H2.*sto-3g/i }));

    expect(await screen.findByRole("link", { name: /view molecule info/i })).toHaveAttribute(
      "href",
      "/molecules/a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    );
    expect(screen.getByTestId("molecule-viewer-2d")).toBeInTheDocument();
  });

  it("keeps KQD, QFD, QSE, and SKQD enabled for molecules above 6 active orbitals", async () => {
    const user = userEvent.setup();
    vi.mocked(api.fetchMolecules).mockResolvedValue({
      items: [
        ...mockMolecules,
        {
          id: "c3d4e5f6-a7b8-9012-cdef-123456789012",
          name: "NaCl",
          atoms: [
            { symbol: "Na", x: 0, y: 0, z: 0 },
            { symbol: "Cl", x: 0, y: 0, z: 2.36 },
          ],
          basis_set: "sto-3g",
          charge: 0,
          multiplicity: 1,
          active_space: { n_electrons: 8, n_orbitals: 8 },
          created_at: "2025-06-01T10:00:00Z",
          updated_at: "2025-06-01T10:00:00Z",
        },
      ],
      total: mockMolecules.length + 1,
    });

    renderRunForm();
    await screen.findByText("Create Simulation Run");

    const moleculeSelect = screen.getByRole("combobox", { name: /molecule/i });
    await user.click(moleculeSelect);
    await user.click(screen.getByRole("option", { name: /NaCl.*sto-3g/i }));

    await waitFor(() => {
      expect(getAlgorithmButton("kqd")).toBeEnabled();
      expect(getAlgorithmButton("qfd")).toBeEnabled();
      expect(getAlgorithmButton("qse")).toBeEnabled();
      expect(getAlgorithmButton("skqd")).toBeEnabled();
    });
  });

  it("uses the shared card background for the molecule preview in dark theme", async () => {
    const user = userEvent.setup();
    renderRunForm("dark");
    await screen.findByText("Create Simulation Run");

    const moleculeSelect = screen.getByRole("combobox", { name: /molecule/i });
    await user.click(moleculeSelect);
    await user.click(screen.getByRole("option", { name: /H2.*sto-3g/i }));

    const viewer = screen.getByTestId("molecule-viewer-2d");

    expect(viewer.className).toContain("bg-card");
    expect(viewer.parentElement?.className).toContain("shadow-[var(--shadow-elevation-raised)]");
    expect(viewer.parentElement?.className).not.toContain("shadow-sm");
  });

  it("shows basis selection with the molecule and labels the default by basis name", async () => {
    const user = userEvent.setup();
    renderRunForm();
    await screen.findByText("Create Simulation Run");

    const basisSelect = screen.getByRole("combobox", { name: /basis set/i });
    expect(basisSelect).toHaveTextContent("sto-3g");
    expect(screen.queryByText(/use molecule default/i)).not.toBeInTheDocument();

    const moleculeSelect = screen.getByRole("combobox", { name: /molecule/i });
    await user.click(moleculeSelect);
    await user.click(screen.getByRole("option", { name: /H2O.*6-31g/i }));

    expect(basisSelect).toHaveTextContent("6-31g");
  });

  it("disables submit until the required selections are made", async () => {
    const user = userEvent.setup();
    renderRunForm();
    await screen.findByText("Create Simulation Run");

    const submitButton = screen.getByRole("button", { name: /create run/i });
    expect(submitButton).toBeDisabled();

    const moleculeSelect = screen.getByRole("combobox", { name: /molecule/i });
    await user.click(moleculeSelect);
    await user.click(screen.getByRole("option", { name: /H2.*sto-3g/i }));
    expect(submitButton).toBeDisabled();

    await user.click(getBackendButton());
    expect(submitButton).toBeDisabled();

    await user.click(getAlgorithmButton());

    await waitFor(() => {
      expect(submitButton).toBeEnabled();
    });
  });

  it("renders advanced VQE fields when mode switches to advanced", async () => {
    const user = userEvent.setup();
    renderRunForm();

    await screen.findByText("Create Simulation Run");

    await user.click(getAlgorithmButton());
    await user.click(screen.getByRole("button", { name: /manual/i }));

    expect(await screen.findByRole("combobox", { name: /ansatz/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/optimizer/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/max iterations/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/chemical accuracy target \(ha\)/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /apply recommended settings/i })).toBeEnabled();
  });

  it("falls back to local config metadata when the metadata endpoint is unavailable", async () => {
    const user = userEvent.setup();
    vi.mocked(api.fetchRunConfigMetadata).mockRejectedValueOnce(new Error("metadata unavailable"));
    renderRunForm();

    await screen.findByText("Create Simulation Run");

    await user.click(getAlgorithmButton());
    await user.click(screen.getByRole("button", { name: /manual/i }));

    await waitFor(() => {
      expect(screen.getByRole("combobox", { name: /ansatz/i })).toBeEnabled();
      expect(screen.getByRole("combobox", { name: /optimizer/i })).toBeEnabled();
    });
  });

  it("applies recommended manual settings from the chemical-accuracy target helper", async () => {
    const user = userEvent.setup();
    renderRunForm();

    await screen.findByText("Create Simulation Run");

    await user.click(getAlgorithmButton());
    await user.click(screen.getByRole("button", { name: /manual/i }));

    const targetInput = screen.getByLabelText(/chemical accuracy target \(ha\)/i);
    await user.clear(targetInput);
    await user.type(targetInput, "0.001");
    await user.tab();

    await user.click(screen.getByRole("button", { name: /apply recommended settings/i }));

    await waitFor(() => {
      expect(screen.getByRole("combobox", { name: /ansatz/i })).toHaveTextContent("NumberPreserving");
      expect(screen.getByRole("combobox", { name: /optimizer/i })).toHaveTextContent("COBYLA");
      expect(screen.getByLabelText(/max iterations/i)).toHaveValue(512);
    });
  });

  it("shows QSE provided-state and provided-sector editors in manual mode", async () => {
    const user = userEvent.setup();
    renderRunForm();

    await screen.findByText("Create Simulation Run");

    await user.click(getAlgorithmButton("qse"));
    await user.click(screen.getByRole("button", { name: /manual/i }));

    await user.click(screen.getByRole("combobox", { name: /reference method/i }));
    await user.click(screen.getByRole("option", { name: /provided dense state/i }));
    expect(await screen.findByLabelText(/provided state vector/i)).toBeInTheDocument();

    await user.click(screen.getByRole("combobox", { name: /reference method/i }));
    await user.click(screen.getByRole("option", { name: /provided determinant sector/i }));
    expect(await screen.findByText(/provided determinant amplitudes/i)).toBeInTheDocument();
  });
});
