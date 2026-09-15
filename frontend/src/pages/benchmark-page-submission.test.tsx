import "./benchmark-page.test-mocks";

import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { benchmarkKeys, runKeys } from "@/hooks/query-keys";
import type { BenchmarkEntry } from "./benchmark/benchmark-utils";
import {
  backendCapabilitiesResponse,
  createBenchmarkRun,
  createRun,
  fetchBackendCapabilities,
  forceRefreshBackendCapabilities,
  getBackendCapabilitiesCached,
  mockBenchmarkDetail,
  getBenchmarkPageMocks,
  renderBenchmarkPage,
  resetBenchmarkPageTestState,
  runId,
  savedBenchmarkWithEntries,
  selectOnlyHydrogenVqe,
  updateBenchmarkRun,
} from "./benchmark-page.test-support";

const { invalidateQueries: mockInvalidateQueries } = getBenchmarkPageMocks();

beforeEach(resetBenchmarkPageTestState);

describe("BenchmarkPage submission", () => {
  it("invalidates cached runs history after submitting a benchmark run", async () => {
    renderBenchmarkPage();
    await selectOnlyHydrogenVqe();

    const runButton = await screen.findByRole("button", { name: /run benchmark/i });
    expect(runButton).toBeEnabled();

    fireEvent.click(runButton);

    await waitFor(() => expect(createRun).toHaveBeenCalledTimes(1));
    await waitFor(() =>
      expect(mockInvalidateQueries).toHaveBeenCalledWith({
        queryKey: runKeys.summariesPrefix,
        refetchType: "all",
      }),
    );
    expect(mockInvalidateQueries).toHaveBeenCalledWith({
      queryKey: runKeys.listPrefix,
      refetchType: "all",
    });
  });

  it("updates an existing benchmark draft with selected config and submitted rows when run starts", async () => {
    mockBenchmarkDetail(
      savedBenchmarkWithEntries([], {
        id: "saved-benchmark-1",
        name: "Draft benchmark",
        selectedMoleculeKeys: [],
        selectedAlgorithms: ["vqe", "sqd", "kqd", "qfd", "qse", "skqd"],
      }),
    );

    renderBenchmarkPage("/benchmarks/saved-benchmark-1");

    await selectOnlyHydrogenVqe();
    await userEvent.click(await screen.findByRole("button", { name: /run benchmark/i }));

    await waitFor(() => expect(createRun).toHaveBeenCalledTimes(1));
    await waitFor(() => {
      const savedSubmission = (updateBenchmarkRun as ReturnType<typeof vi.fn>).mock.calls.find(
        ([id, patch]) => {
          const entries = (patch as { entries?: BenchmarkEntry[] }).entries;
          return (
            id === "saved-benchmark-1" &&
            entries?.some((entry) => entry.runId === runId && entry.status === "queued")
          );
        },
      );
      expect(savedSubmission).toBeTruthy();
    });

    await new Promise((resolve) => setTimeout(resolve, 350));

    const submittedCallIndex = (
      updateBenchmarkRun as ReturnType<typeof vi.fn>
    ).mock.calls.findIndex(([id, patch]) => {
      const entries = (patch as { entries?: BenchmarkEntry[] }).entries;
      return (
        id === "saved-benchmark-1" &&
        entries?.some((entry) => entry.runId === runId && entry.status === "queued")
      );
    });
    expect(submittedCallIndex).toBeGreaterThanOrEqual(0);
    const staleOverwrite = (updateBenchmarkRun as ReturnType<typeof vi.fn>).mock.calls
      .slice(submittedCallIndex + 1)
      .find(([id, patch]) => {
        const entries = (patch as { entries?: BenchmarkEntry[] }).entries;
        return id === "saved-benchmark-1" && entries?.every((entry) => entry.runId === null);
      });
    expect(staleOverwrite).toBeUndefined();

    const allPatches = (updateBenchmarkRun as ReturnType<typeof vi.fn>).mock.calls.map(
      ([, patch]) => patch as Record<string, unknown>,
    );
    expect(allPatches.every((patch) => !("createdAt" in patch))).toBe(true);
    expect(allPatches.every((patch) => !("updatedAt" in patch))).toBe(true);
    expect(createBenchmarkRun).not.toHaveBeenCalled();
  });

  it("persists submitted run ids even if benchmark launch is cancelled before submission settles", async () => {
    mockBenchmarkDetail(
      savedBenchmarkWithEntries([], {
        id: "saved-benchmark-1",
        name: "Draft benchmark",
        selectedMoleculeKeys: [],
        selectedAlgorithms: ["vqe", "sqd", "kqd", "qfd", "qse", "skqd"],
      }),
    );

    let resolveRun: ((value: { id: string; status: "QUEUED" }) => void) | undefined;
    (createRun as ReturnType<typeof vi.fn>).mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveRun = resolve;
        }),
    );

    renderBenchmarkPage("/benchmarks/saved-benchmark-1");

    await selectOnlyHydrogenVqe();
    await userEvent.click(await screen.findByRole("button", { name: /run benchmark/i }));

    await waitFor(() => expect(createRun).toHaveBeenCalledTimes(1));
    await userEvent.click(await screen.findByRole("button", { name: "Cancel" }));

    expect(resolveRun).toBeDefined();
    resolveRun!({ id: runId, status: "QUEUED" });

    await waitFor(() => {
      const savedSubmission = (updateBenchmarkRun as ReturnType<typeof vi.fn>).mock.calls.find(
        ([id, patch]) => {
          const entries = (patch as { entries?: BenchmarkEntry[] }).entries;
          return (
            id === "saved-benchmark-1" &&
            entries?.some((entry) => entry.runId === runId && entry.status === "queued")
          );
        },
      );
      expect(savedSubmission).toBeTruthy();
    });
  });

  it("submits Aer benchmark runs with backend-derived noise from the selected IBM backend", async () => {
    (getBackendCapabilitiesCached as ReturnType<typeof vi.fn>).mockReturnValue(
      backendCapabilitiesResponse,
    );
    mockBenchmarkDetail(
      savedBenchmarkWithEntries([], {
        id: "saved-benchmark-1",
        selectedMoleculeKeys: ["h2"],
        selectedAlgorithms: ["vqe"],
        selectedBackendMode: "aer_simulator_backend_noise",
        selectedBackendName: "ibm_kyiv",
      }),
    );

    renderBenchmarkPage("/benchmarks/saved-benchmark-1");

    await userEvent.click(await screen.findByRole("button", { name: /run benchmark/i }));

    await waitFor(() => expect(createRun).toHaveBeenCalledTimes(1));
    expect(createRun).toHaveBeenCalledWith(
      expect.objectContaining({
        backend_target: "aer_simulator",
        backend_options: expect.objectContaining({
          backend_name: "ibm_kyiv",
        }),
        noise_profile: {
          source: "backend_derived",
          reference_backend: "ibm_kyiv",
        },
        ibm_runtime_confirmed: false,
      }),
    );
  });

  it("persists successful benchmark rows even when another submission never settles", async () => {
    const pendingResolvers: {
      qfd: ((value: { id: string; status: "QUEUED" }) => void) | null;
    } = { qfd: null };
    (createRun as ReturnType<typeof vi.fn>).mockImplementation((config) => {
      if (config.algorithm === "qfd") {
        return new Promise<{ id: string; status: "QUEUED" }>((resolve) => {
          pendingResolvers.qfd = resolve;
        });
      }
      return new Promise(() => undefined);
    });

    mockBenchmarkDetail(
      savedBenchmarkWithEntries([], {
        id: "saved-benchmark-1",
        selectedMoleculeKeys: ["h2"],
        selectedAlgorithms: ["kqd", "qfd"],
        selectedBackendMode: "aer_simulator_backend_noise",
        selectedBackendName: "ibm_kyiv",
      }),
    );

    renderBenchmarkPage("/benchmarks/saved-benchmark-1");

    const runButton = await screen.findByRole("button", { name: /run benchmark/i });
    await waitFor(() => expect(runButton).toBeEnabled());
    await userEvent.click(runButton);

    await waitFor(() => expect(createRun).toHaveBeenCalledTimes(2));
    const benchmarkInvalidationsBeforePartialPersist = mockInvalidateQueries.mock.calls.filter(
      ([payload]) =>
        JSON.stringify(payload) ===
        JSON.stringify({
          queryKey: benchmarkKeys.listPrefix,
          refetchType: "all",
        }),
    ).length;
    const findPartialPersist = () =>
      (updateBenchmarkRun as ReturnType<typeof vi.fn>).mock.calls.find(
        ([id, patch]) =>
          id === "saved-benchmark-1" &&
          (patch as { entries?: BenchmarkEntry[] }).entries?.some(
            (entry) =>
              entry.algorithm === "qfd" && entry.runId === "qfd-run-1" && entry.status === "queued",
          ),
      );

    expect(findPartialPersist()).toBeUndefined();
    pendingResolvers.qfd?.({ id: "qfd-run-1", status: "QUEUED" });
    await waitFor(() => expect(findPartialPersist()).toBeTruthy());

    const benchmarkInvalidationsAfterPartialPersist = mockInvalidateQueries.mock.calls.filter(
      ([payload]) =>
        JSON.stringify(payload) ===
        JSON.stringify({
          queryKey: benchmarkKeys.listPrefix,
          refetchType: "all",
        }),
    ).length;
    expect(benchmarkInvalidationsAfterPartialPersist).toBe(
      benchmarkInvalidationsBeforePartialPersist,
    );
  });

  it("caps concurrent benchmark run submissions during launch", async () => {
    let inFlight = 0;
    let maxInFlight = 0;
    (createRun as ReturnType<typeof vi.fn>).mockImplementation(async (config) => {
      inFlight += 1;
      maxInFlight = Math.max(maxInFlight, inFlight);
      await new Promise((resolve) => setTimeout(resolve, 20));
      inFlight -= 1;
      return { id: `run-${config.algorithm}`, status: "QUEUED" };
    });

    mockBenchmarkDetail(
      savedBenchmarkWithEntries([], {
        id: "saved-benchmark-1",
        selectedMoleculeKeys: ["h2"],
        selectedAlgorithms: ["vqe", "sqd", "kqd", "qfd", "qse", "skqd"],
      }),
    );

    renderBenchmarkPage("/benchmarks/saved-benchmark-1");

    await userEvent.click(await screen.findByRole("button", { name: /run benchmark/i }));

    await waitFor(() => expect(createRun).toHaveBeenCalledTimes(6));
    await waitFor(() => expect(inFlight).toBe(0));
    expect(maxInFlight).toBeLessThanOrEqual(3);
  });

  it("refreshes stale cached IBM capability data when the backend picker is opened", async () => {
    (getBackendCapabilitiesCached as ReturnType<typeof vi.fn>).mockReturnValue({
      backends: [
        {
          target: "statevector",
          enabled: true,
          available: true,
          credential_configured: true,
          supports_noise_profile: false,
          backends: [],
          default_backend: "statevector",
        },
        {
          target: "aer_simulator",
          enabled: true,
          available: true,
          credential_configured: true,
          supports_noise_profile: true,
          backends: [{ name: "aer_simulator", simulator: true, operational: true }],
          default_backend: "aer_simulator",
        },
        {
          target: "ibm_runtime",
          enabled: false,
          available: false,
          credential_configured: true,
          supports_noise_profile: false,
          reason: "IBM backend data is unavailable right now.",
          backends: [],
          default_backend: null,
        },
      ],
    });

    renderBenchmarkPage();

    const backendTrigger = await screen.findByRole("combobox", { name: "Backend" });
    await userEvent.click(backendTrigger);

    await waitFor(() => expect(forceRefreshBackendCapabilities).toHaveBeenCalledTimes(1));
    await waitFor(() =>
      expect(
        screen.getByRole("option", { name: "Aer simulator with backend noise" }),
      ).not.toHaveAttribute("aria-disabled", "true"),
    );
  });

  it("warms IBM capability data while the benchmark page is idle and shows pending labels meanwhile", async () => {
    let resolveCapabilities: ((value: typeof backendCapabilitiesResponse) => void) | undefined;
    (fetchBackendCapabilities as ReturnType<typeof vi.fn>).mockImplementation(
      () =>
        new Promise<typeof backendCapabilitiesResponse>((resolve) => {
          resolveCapabilities = resolve;
        }),
    );

    renderBenchmarkPage();

    await waitFor(() => expect(fetchBackendCapabilities).toHaveBeenCalledTimes(1));

    await userEvent.click(await screen.findByRole("combobox", { name: "Backend" }));
    expect(
      screen.getByRole("option", { name: "Aer simulator with backend noise (Checking IBM...)" }),
    ).toHaveAttribute("aria-disabled", "true");
    expect(
      screen.getByRole("option", { name: "IBM Quantum backend (Checking IBM...)" }),
    ).toHaveAttribute("aria-disabled", "true");

    if (resolveCapabilities) {
      resolveCapabilities(backendCapabilitiesResponse);
    }

    await waitFor(() =>
      expect(
        screen.getByRole("option", { name: "Aer simulator with backend noise" }),
      ).not.toHaveAttribute("aria-disabled", "true"),
    );
    await waitFor(() =>
      expect(screen.getByRole("option", { name: "IBM Quantum backend" })).not.toHaveAttribute(
        "aria-disabled",
        "true",
      ),
    );
  });

  it("requires confirmation before submitting benchmark runs to a real IBM backend", async () => {
    (getBackendCapabilitiesCached as ReturnType<typeof vi.fn>).mockReturnValue(
      backendCapabilitiesResponse,
    );
    mockBenchmarkDetail(
      savedBenchmarkWithEntries([], {
        id: "saved-benchmark-1",
        selectedMoleculeKeys: ["h2"],
        selectedAlgorithms: ["vqe"],
        selectedBackendMode: "ibm_runtime",
        selectedBackendName: "ibm_kyiv",
      }),
    );

    renderBenchmarkPage("/benchmarks/saved-benchmark-1");

    await userEvent.click(await screen.findByRole("button", { name: /run benchmark/i }));

    expect(await screen.findByText("Submit benchmark to IBM Quantum?")).toBeInTheDocument();
    expect(createRun).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: "Submit to IBM backend" }));

    await waitFor(() => expect(createRun).toHaveBeenCalledTimes(1));
    expect(createRun).toHaveBeenCalledWith(
      expect.objectContaining({
        backend_target: "ibm_runtime",
        backend_options: expect.objectContaining({
          backend_name: "ibm_kyiv",
        }),
        ibm_runtime_confirmed: true,
      }),
    );
  });
});
