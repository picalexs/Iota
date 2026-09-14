import "./run-form.test-mocks";

import { screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { runKeys } from "@/hooks/query-keys";
import {
  api,
  createRunResponse,
  getAlgorithmButton,
  getBackendButton,
  getRunFormTestMocks,
  hasLegacyConfigKey,
  neverSettles,
  renderRunForm,
  resetRunFormTestState,
} from "./run-form.test-support";
import type { RunResponse } from "./run-form.test-support";

const { invalidateQueries: mockInvalidateQueries, navigate: mockNavigate } = getRunFormTestMocks();

beforeEach(resetRunFormTestState);

describe("RunForm submission", () => {
  it("submits easy mode with algorithm-aware payload only", async () => {
    const user = userEvent.setup();
    vi.mocked(api.createRun).mockResolvedValue(createRunResponse("run-easy"));

    renderRunForm();
    await screen.findByText("Create Simulation Run");

    const moleculeSelect = screen.getByRole("combobox", { name: /molecule/i });
    await user.click(moleculeSelect);
    await user.click(screen.getByRole("option", { name: /H2.*sto-3g/i }));
    await user.click(getBackendButton());
    await user.click(getAlgorithmButton());

    const submitButton = screen.getByRole("button", { name: /create run/i });
    await waitFor(() => {
      expect(submitButton).toBeEnabled();
    });

    await user.click(submitButton);

    await waitFor(() => {
      expect(api.createRun).toHaveBeenCalledTimes(1);
    });

    expect(api.createRun).toHaveBeenCalledWith(
      expect.objectContaining({
        molecule_id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        algorithm: "vqe",
        mode: "easy",
        backend_target: "statevector",
        backend_options: expect.objectContaining({
          selection_policy: "manual",
          shots: 4096,
          optimization_level: 1,
        }),
        noise_profile: null,
        easy_options: { goal: "balanced" },
      }),
    );
    expect(mockInvalidateQueries).toHaveBeenCalledTimes(2);
    expect(mockInvalidateQueries).toHaveBeenNthCalledWith(1, {
      queryKey: runKeys.listPrefix,
      refetchType: "all",
    });
    expect(mockInvalidateQueries).toHaveBeenNthCalledWith(2, {
      queryKey: runKeys.summariesPrefix,
      refetchType: "all",
    });

    const submittedPayload = vi.mocked(api.createRun).mock.calls[0]?.[0];
    expect(hasLegacyConfigKey(submittedPayload)).toBe(false);
  });

  it("navigates to the created run and marks it as coming from the form", async () => {
    const user = userEvent.setup();
    vi.mocked(api.createRun).mockResolvedValue(createRunResponse("run-history"));

    renderRunForm();
    await screen.findByText("Create Simulation Run");

    const moleculeSelect = screen.getByRole("combobox", { name: /molecule/i });
    await user.click(moleculeSelect);
    await user.click(screen.getByRole("option", { name: /H2.*sto-3g/i }));
    await user.click(getBackendButton());
    await user.click(getAlgorithmButton());

    const submitButton = screen.getByRole("button", { name: /create run/i });
    await waitFor(() => {
      expect(submitButton).toBeEnabled();
    });

    await user.click(submitButton);

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith({
        to: "/runs/$runId",
        params: { runId: "run-history" },
        state: expect.any(Function),
      });
    });
    expect(mockNavigate).not.toHaveBeenCalledWith(expect.objectContaining({ replace: true }));
  });

  it("submits advanced VQE with advanced_config payload", async () => {
    const user = userEvent.setup();
    vi.mocked(api.createRun).mockResolvedValue(createRunResponse("run-advanced"));

    renderRunForm();
    await screen.findByText("Create Simulation Run");

    const moleculeSelect = screen.getByRole("combobox", { name: /molecule/i });
    await user.click(moleculeSelect);
    await user.click(screen.getByRole("option", { name: /H2.*sto-3g/i }));
    await user.click(getBackendButton());
    await user.click(getAlgorithmButton());

    await user.click(screen.getByRole("button", { name: /manual/i }));

    const maxIterationsInput = await screen.findByLabelText(/max iterations/i);
    await user.clear(maxIterationsInput);
    await user.type(maxIterationsInput, "250");
    await user.tab();

    const submitButton = screen.getByRole("button", { name: /create run/i });
    await waitFor(() => {
      expect(submitButton).toBeEnabled();
    });

    await user.click(submitButton);

    await waitFor(() => {
      expect(api.createRun).toHaveBeenCalledTimes(1);
    });

    expect(api.createRun).toHaveBeenCalledWith(
      expect.objectContaining({
        mode: "advanced",
        algorithm: "vqe",
        advanced_config: expect.objectContaining({
          algorithm: "vqe",
          max_iterations: 250,
        }),
      }),
    );
  });

  it("submits advanced KQD values at the supported Trotter-step limit", async () => {
    const user = userEvent.setup();
    vi.mocked(api.createRun).mockResolvedValue(createRunResponse("run-kqd"));

    renderRunForm();
    await screen.findByText("Create Simulation Run");

    const moleculeSelect = screen.getByRole("combobox", { name: /molecule/i });
    await user.click(moleculeSelect);
    await user.click(screen.getByRole("option", { name: /H2.*sto-3g/i }));
    await user.click(getBackendButton());
    await user.click(getAlgorithmButton("kqd"));
    await user.click(screen.getByRole("button", { name: /manual/i }));

    const timeStepInput = await screen.findByLabelText(/time step/i);
    await user.clear(timeStepInput);
    await user.type(timeStepInput, "0.001");
    await user.tab();

    await user.click(screen.getByRole("combobox", { name: /evolution method/i }));
    await user.click(screen.getByRole("option", { name: /trotter/i }));

    const trotterStepsInput = screen.getByLabelText(/trotter steps/i);
    await user.clear(trotterStepsInput);
    await user.type(trotterStepsInput, "32");
    await user.tab();

    await user.click(screen.getByRole("button", { name: /create run/i }));

    await waitFor(() => {
      expect(api.createRun).toHaveBeenCalledTimes(1);
    });

    expect(api.createRun).toHaveBeenCalledWith(
      expect.objectContaining({
        algorithm: "kqd",
        mode: "advanced",
        advanced_config: expect.objectContaining({
          algorithm: "kqd",
          evolution_method: "trotter",
          time_step: 0.001,
          trotter_steps: 32,
        }),
      }),
    );
  });

  it("submits advanced QFD max time above the slider-era cap", async () => {
    const user = userEvent.setup();
    vi.mocked(api.createRun).mockResolvedValue(createRunResponse("run-qfd"));

    renderRunForm();
    await screen.findByText("Create Simulation Run");

    const moleculeSelect = screen.getByRole("combobox", { name: /molecule/i });
    await user.click(moleculeSelect);
    await user.click(screen.getByRole("option", { name: /H2.*sto-3g/i }));
    await user.click(getBackendButton());
    await user.click(getAlgorithmButton("qfd"));
    await user.click(screen.getByRole("button", { name: /manual/i }));

    const maxTimeInput = await screen.findByLabelText(/max time/i);
    await user.clear(maxTimeInput);
    await user.type(maxTimeInput, "12.5");
    await user.tab();

    await user.click(screen.getByRole("button", { name: /create run/i }));

    await waitFor(() => {
      expect(api.createRun).toHaveBeenCalledTimes(1);
    });

    expect(api.createRun).toHaveBeenCalledWith(
      expect.objectContaining({
        algorithm: "qfd",
        mode: "advanced",
        advanced_config: expect.objectContaining({
          algorithm: "qfd",
          max_time: 12.5,
        }),
      }),
    );
  });

  it("shows loading state during submission", async () => {
    const user = userEvent.setup();

    vi.mocked(api.createRun).mockImplementation(() => neverSettles<RunResponse>());

    renderRunForm();

    await waitFor(() => {
      expect(screen.getByText("Create Simulation Run")).toBeInTheDocument();
    });

    const moleculeSelect = screen.getByRole("combobox", { name: /molecule/i });
    await user.click(moleculeSelect);
    await user.click(screen.getByRole("option", { name: /H2.*sto-3g/ }));
    await user.click(getBackendButton());
    await user.click(getAlgorithmButton());

    const submitButton = screen.getByRole("button", { name: /create run/i });
    await waitFor(() => {
      expect(submitButton).toBeEnabled();
    });
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /creating run/i })).toBeDisabled();
    });

    expect(document.querySelector("[data-slot='spinner']")).toBeInTheDocument();
  });

  it("handles API errors during molecule fetch", async () => {
    const { toast } = await import("sonner");
    vi.mocked(api.fetchMolecules).mockRejectedValue(
      new api.ApiError("NOT_FOUND", "Not found", 404),
    );

    renderRunForm();

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("Error", { description: "Not found" });
    });
  });
});
