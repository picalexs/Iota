import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  api,
  hooks,
  mockMoleculeListResponse,
  mockNavigate,
  mockRun1,
  mockRun2,
  mockRunListResponse,
  renderWithQuery,
  resetRunsListMocks,
  setRunsListSearch,
} from "./runs-list.test-utils";

beforeEach(resetRunsListMocks);

afterEach(() => {
  vi.useRealTimers();
});

function requireFixtureAt<T>(items: readonly T[], index: number): T {
  const item = items[index];
  if (item === undefined) {
    throw new Error(`Expected fixture at index ${index}`);
  }
  return item;
}

describe("RunsList background behavior", () => {
  it("requests server pages with a maximum of 50 rows", () => {
    setRunsListSearch({ page: 2 });
    vi.mocked(hooks.useListRunSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: { ...mockRunListResponse, total: 75, offset: 50 },
    });

    vi.mocked(hooks.useAllMoleculeSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: mockMoleculeListResponse.items,
    });

    renderWithQuery();

    expect(hooks.useListRunSummaries).toHaveBeenCalledWith({
      limit: 50,
      offset: 50,
      status: undefined,
      molecule_id: undefined,
      backend_target: undefined,
      chemical_accurate: undefined,
    });
  });

  it("passes backend and chemical-accuracy filters through to the summaries query", () => {
    setRunsListSearch({ backend_target: "ibm_runtime", chemical_accurate: false });
    vi.mocked(hooks.useListRunSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: mockRunListResponse,
    });

    vi.mocked(hooks.useAllMoleculeSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: mockMoleculeListResponse.items,
    });

    renderWithQuery();

    expect(hooks.useListRunSummaries).toHaveBeenCalledWith({
      limit: 50,
      offset: 0,
      status: undefined,
      molecule_id: undefined,
      backend_target: "ibm_runtime",
      chemical_accurate: false,
    });
  });

  it("jumps to an entered runs page number", async () => {
    const user = userEvent.setup();

    vi.mocked(hooks.useListRunSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: { ...mockRunListResponse, total: 200 },
    });

    vi.mocked(hooks.useAllMoleculeSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: mockMoleculeListResponse.items,
    });

    renderWithQuery();

    const pageInput = await screen.findByLabelText("Go to runs page");
    mockNavigate.mockClear();
    await user.clear(pageInput);
    await user.type(pageInput, "3{Enter}");

    expect(mockNavigate).toHaveBeenCalledWith({
      to: "/runs",
      search: expect.any(Function),
    });
    const nextSearch = mockNavigate.mock.calls.at(-1)?.[0].search({});
    expect(nextSearch).toMatchObject({ page: 3 });
  });

  it("clamps entered runs page numbers into range", async () => {
    const user = userEvent.setup();

    vi.mocked(hooks.useListRunSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: { ...mockRunListResponse, total: 120 },
    });

    vi.mocked(hooks.useAllMoleculeSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: mockMoleculeListResponse.items,
    });

    renderWithQuery();

    const pageInput = await screen.findByLabelText("Go to runs page");
    mockNavigate.mockClear();
    await user.clear(pageInput);
    await user.type(pageInput, "99{Enter}");

    const nextSearch = mockNavigate.mock.calls.at(-1)?.[0].search({});
    expect(nextSearch).toMatchObject({ page: 3 });
  });

  it("renders cached data immediately on remount and skips skeleton flash", async () => {
    vi.mocked(hooks.useListRunSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: mockRunListResponse,
    });

    vi.mocked(hooks.useAllMoleculeSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: mockMoleculeListResponse.items,
    });

    const firstRender = renderWithQuery();
    await waitFor(() => {
      expect(screen.getByText("H2")).toBeInTheDocument();
    });
    firstRender.unmount();

    const secondRender = renderWithQuery();

    expect(screen.getByText("H2")).toBeInTheDocument();
    const skeletons = secondRender.container.querySelectorAll("[data-slot='skeleton']");
    expect(skeletons.length).toBe(0);
  });

  it("renders rows without entrance animation classes", async () => {
    const runsWithMultipleEntries = {
      ...mockRunListResponse,
      items: [mockRun1, mockRun2],
      total: 2,
    };

    vi.mocked(hooks.useListRunSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: runsWithMultipleEntries,
    });

    vi.mocked(hooks.useAllMoleculeSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: mockMoleculeListResponse.items,
    });

    const { container } = renderWithQuery();

    await waitFor(() => {
      expect(screen.getByText("COMPLETED")).toBeInTheDocument();
    });

    // Find all run rows (excluding header)
    const rows = container.querySelectorAll("tr[aria-label]");
    expect(rows.length).toBe(2);

    rows.forEach((row) => {
      expect(row.className).not.toContain("animate-in");
      expect(row.className).not.toContain("slide-in-from-bottom");
      expect((row as HTMLElement).style.animationDelay).toBe("");
    });
  });

  it("uses a surfaced card shell so the runs list stands off from the page background", async () => {
    vi.mocked(hooks.useListRunSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: mockRunListResponse,
    });

    vi.mocked(hooks.useAllMoleculeSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: mockMoleculeListResponse.items,
    });

    renderWithQuery();

    const title = await screen.findByText("All Runs");
    const card = title.closest("[data-slot='card']");

    expect(card?.className).toContain("bg-card");
    expect(card?.className).toContain("shadow-[var(--shadow-surface-panel)]");
  });

  it("renders filter bar controls", async () => {
    vi.mocked(hooks.useListRunSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: mockRunListResponse,
    });

    vi.mocked(hooks.useAllMoleculeSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: mockMoleculeListResponse.items,
    });

    renderWithQuery();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /filter by status/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /filter by backend/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /filter by method/i })).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: /filter by chemical accuracy/i }),
      ).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /filter by molecule/i })).toBeInTheDocument();
    });
  });

  it("pauses the selected pausable runs from edit mode", async () => {
    const user = userEvent.setup();
    const invalidateRunsList = vi.fn().mockResolvedValue(undefined);
    const queuedRun = {
      ...mockRun2,
      id: "aaaaaaaa-0000-0000-0000-000000000003",
      status: "QUEUED" as const,
    };

    vi.mocked(hooks.useListRunSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: { ...mockRunListResponse, items: [mockRun1, mockRun2, queuedRun], total: 3 },
    });

    vi.mocked(hooks.useAllMoleculeSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: mockMoleculeListResponse.items,
    });
    vi.mocked(hooks.useInvalidateRunsList).mockReturnValue(invalidateRunsList);

    renderWithQuery();

    await user.click(await screen.findByRole("button", { name: /^edit$/i }));
    const checkboxes = await screen.findAllByRole("checkbox", { name: /select run aaaaaaaa/i });
    await user.click(requireFixtureAt(checkboxes, 1));
    await user.click(requireFixtureAt(checkboxes, 2));
    await user.click(screen.getByRole("button", { name: /pause \(2\)/i }));
    await user.click(screen.getByRole("button", { name: /pause selected/i }));

    await waitFor(() => {
      expect(api.pauseRun).toHaveBeenCalledTimes(2);
      expect(api.pauseRun).toHaveBeenNthCalledWith(1, mockRun2.id);
      expect(api.pauseRun).toHaveBeenNthCalledWith(2, queuedRun.id);
      expect(invalidateRunsList).toHaveBeenCalledTimes(1);
    });
  });

  it("resumes paused and failed runs from edit mode", async () => {
    const user = userEvent.setup();
    const invalidateRunsList = vi.fn().mockResolvedValue(undefined);
    const pausedRun = {
      ...mockRun2,
      id: "aaaaaaaa-0000-0000-0000-000000000004",
      status: "PAUSED" as const,
    };
    const failedRun = {
      ...mockRun1,
      id: "aaaaaaaa-0000-0000-0000-000000000005",
      status: "FAILED" as const,
    };

    vi.mocked(hooks.useListRunSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: { ...mockRunListResponse, items: [pausedRun, failedRun], total: 2 },
    });

    vi.mocked(hooks.useAllMoleculeSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: mockMoleculeListResponse.items,
    });
    vi.mocked(hooks.useInvalidateRunsList).mockReturnValue(invalidateRunsList);

    renderWithQuery();

    await user.click(await screen.findByRole("button", { name: /^edit$/i }));
    const checkboxes = await screen.findAllByRole("checkbox", { name: /select run aaaaaaaa/i });
    await user.click(requireFixtureAt(checkboxes, 0));
    await user.click(requireFixtureAt(checkboxes, 1));
    await user.click(screen.getByRole("button", { name: /resume \(2\)/i }));

    await waitFor(() => {
      expect(api.resumeRun).toHaveBeenCalledTimes(2);
      expect(api.resumeRun).toHaveBeenNthCalledWith(1, pausedRun.id);
      expect(api.resumeRun).toHaveBeenNthCalledWith(2, failedRun.id);
      expect(invalidateRunsList).toHaveBeenCalledTimes(1);
    });
  });

  it("deletes selected runs from edit mode after confirmation", async () => {
    const user = userEvent.setup();
    const invalidateRunsList = vi.fn().mockResolvedValue(undefined);

    vi.mocked(hooks.useListRunSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: { ...mockRunListResponse, items: [mockRun1, mockRun2], total: 2 },
    });

    vi.mocked(hooks.useAllMoleculeSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: mockMoleculeListResponse.items,
    });
    vi.mocked(hooks.useInvalidateRunsList).mockReturnValue(invalidateRunsList);

    renderWithQuery();

    await user.click(await screen.findByRole("button", { name: /^edit$/i }));
    const checkboxes = await screen.findAllByRole("checkbox", { name: /select run aaaaaaaa/i });
    await user.click(requireFixtureAt(checkboxes, 0));
    await user.click(requireFixtureAt(checkboxes, 1));
    await user.click(screen.getByRole("button", { name: /delete \(2\)/i }));

    expect(screen.getByRole("dialog", { name: /delete 2 selected runs/i })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /delete runs/i }));

    await waitFor(() => {
      expect(api.deleteRun).toHaveBeenCalledTimes(2);
      expect(api.deleteRun).toHaveBeenNthCalledWith(1, mockRun1.id);
      expect(api.deleteRun).toHaveBeenNthCalledWith(2, mockRun2.id);
      expect(invalidateRunsList).toHaveBeenCalledTimes(1);
    });
  });

  it("opens bulk delete confirmation when Delete is pressed in edit mode", async () => {
    const user = userEvent.setup();

    vi.mocked(hooks.useListRunSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: { ...mockRunListResponse, items: [mockRun1], total: 1 },
    });

    vi.mocked(hooks.useAllMoleculeSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: mockMoleculeListResponse.items,
    });

    renderWithQuery();

    await user.click(await screen.findByRole("button", { name: /^edit$/i }));
    await user.click(
      requireFixtureAt(await screen.findAllByRole("checkbox", { name: /select run aaaaaaaa/i }), 0),
    );
    await user.keyboard("[Delete]");

    expect(screen.getByRole("dialog", { name: /delete selected run\?/i })).toBeInTheDocument();
  });

  it("shows delete progress inside the confirmation dialog while deleting", async () => {
    const user = userEvent.setup();
    const invalidateRunsList = vi.fn().mockResolvedValue(undefined);
    let resolveDelete: (() => void) | undefined;

    vi.mocked(hooks.useListRunSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: { ...mockRunListResponse, items: [mockRun1], total: 1 },
    });

    vi.mocked(hooks.useAllMoleculeSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: mockMoleculeListResponse.items,
    });
    vi.mocked(hooks.useInvalidateRunsList).mockReturnValue(invalidateRunsList);
    vi.mocked(api.deleteRun).mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          resolveDelete = resolve;
        }),
    );

    renderWithQuery();

    await user.click(await screen.findByRole("button", { name: /^edit$/i }));
    await user.click(
      requireFixtureAt(await screen.findAllByRole("checkbox", { name: /select run aaaaaaaa/i }), 0),
    );
    await user.click(screen.getByRole("button", { name: /delete \(1\)/i }));
    await user.click(screen.getByRole("button", { name: /delete run/i }));

    expect(await screen.findByRole("status")).toHaveTextContent("Deleting 0 of 1...");

    if (resolveDelete) {
      resolveDelete();
    }

    await waitFor(() => {
      expect(invalidateRunsList).toHaveBeenCalledTimes(1);
    });
  });

  it("surfaces one inline error summary when a selected bulk action partially fails", async () => {
    const user = userEvent.setup();
    const invalidateRunsList = vi.fn().mockResolvedValue(undefined);
    const queuedRun = {
      ...mockRun2,
      id: "aaaaaaaa-0000-0000-0000-000000000003",
      status: "QUEUED" as const,
    };

    vi.mocked(hooks.useListRunSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: { ...mockRunListResponse, items: [mockRun2, queuedRun], total: 2 },
    });

    vi.mocked(hooks.useAllMoleculeSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: mockMoleculeListResponse.items,
    });
    vi.mocked(hooks.useInvalidateRunsList).mockReturnValue(invalidateRunsList);
    vi.mocked(api.pauseRun)
      .mockResolvedValueOnce({ id: mockRun2.id, status: "PAUSING" })
      .mockRejectedValueOnce(new Error("Queue cancellation failed"));

    renderWithQuery();

    await user.click(await screen.findByRole("button", { name: /^edit$/i }));
    const checkboxes = await screen.findAllByRole("checkbox", { name: /select run aaaaaaaa/i });
    await user.click(requireFixtureAt(checkboxes, 0));
    await user.click(requireFixtureAt(checkboxes, 1));
    await user.click(screen.getByRole("button", { name: /pause \(2\)/i }));
    await user.click(screen.getByRole("button", { name: /pause selected/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Paused 1 run, 1 failed. Queue cancellation failed",
      );
    });
  });

  it("uses row clicks for selection instead of navigation in edit mode", async () => {
    const user = userEvent.setup();

    vi.mocked(hooks.useListRunSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: { ...mockRunListResponse, items: [mockRun1], total: 1 },
    });

    vi.mocked(hooks.useAllMoleculeSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: mockMoleculeListResponse.items,
    });

    renderWithQuery();

    await user.click(await screen.findByRole("button", { name: /^edit$/i }));
    await user.click(screen.getByRole("row", { name: /aaaaaaaa/i }));

    expect(screen.getByText("1 selected")).toBeInTheDocument();
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it("opens row actions and pauses an individual run with confirmation", async () => {
    const user = userEvent.setup();
    const invalidateRunsList = vi.fn().mockResolvedValue(undefined);
    const runningRun = {
      ...mockRun2,
      id: "aaaaaaaa-0000-0000-0000-000000000006",
      status: "RUNNING" as const,
    };
    const refetchRuns = vi.fn().mockResolvedValue(undefined);

    vi.mocked(hooks.useListRunSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: { ...mockRunListResponse, items: [runningRun], total: 1 },
      refetch: refetchRuns,
    });

    vi.mocked(hooks.useAllMoleculeSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: mockMoleculeListResponse.items,
    });
    vi.mocked(hooks.useInvalidateRunsList).mockReturnValue(invalidateRunsList);
    vi.mocked(api.pauseRun).mockResolvedValueOnce({ id: runningRun.id, status: "PAUSING" });

    renderWithQuery();

    await user.click(await screen.findByRole("button", { name: /run actions for aaaaaaaa/i }));
    await user.click(screen.getByRole("button", { name: /pause run/i }));
    await user.click(screen.getByRole("button", { name: /^pause$/i }));

    await waitFor(() => {
      expect(api.pauseRun).toHaveBeenCalledWith(runningRun.id);
      expect(invalidateRunsList).toHaveBeenCalledTimes(1);
      expect(refetchRuns).toHaveBeenCalled();
    });
    expect(mockNavigate).not.toHaveBeenCalled();
    expect(screen.getByText("PAUSING")).toBeInTheDocument();
  });

  it("restarts a run from the row actions menu without leaving the list", async () => {
    const user = userEvent.setup();
    const invalidateRunsList = vi.fn().mockResolvedValue(undefined);
    const completedRun = {
      ...mockRun1,
      id: "aaaaaaaa-0000-0000-0000-000000000008",
      status: "COMPLETED" as const,
    };
    const refetchRuns = vi.fn().mockResolvedValue(undefined);

    vi.mocked(hooks.useListRunSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: { ...mockRunListResponse, items: [completedRun], total: 1 },
      refetch: refetchRuns,
    });

    vi.mocked(hooks.useAllMoleculeSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: mockMoleculeListResponse.items,
    });
    vi.mocked(hooks.useInvalidateRunsList).mockReturnValue(invalidateRunsList);
    vi.mocked(api.restartRun).mockResolvedValueOnce({
      id: completedRun.id,
      status: "COMPLETED",
      child_run_id: "aaaaaaaa-0000-0000-0000-000000000099",
    });

    renderWithQuery();

    await user.click(await screen.findByRole("button", { name: /run actions for aaaaaaaa/i }));
    await user.click(screen.getByRole("button", { name: /restart run/i }));
    await user.click(screen.getByRole("button", { name: /^restart$/i }));

    await waitFor(() => {
      expect(api.restartRun).toHaveBeenCalledWith(completedRun.id);
      expect(invalidateRunsList).toHaveBeenCalledTimes(1);
      expect(refetchRuns).toHaveBeenCalled();
    });
    expect(mockNavigate).not.toHaveBeenCalled();
    expect(screen.getByText("QUEUED")).toBeInTheDocument();
  });

  it("resumes a paused run from the row actions menu", async () => {
    const user = userEvent.setup();
    const invalidateRunsList = vi.fn().mockResolvedValue(undefined);
    const pausedRun = {
      ...mockRun2,
      id: "aaaaaaaa-0000-0000-0000-000000000007",
      status: "PAUSED" as const,
    };

    vi.mocked(hooks.useListRunSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: { ...mockRunListResponse, items: [pausedRun], total: 1 },
      refetch: vi.fn().mockResolvedValue(undefined),
    });

    vi.mocked(hooks.useAllMoleculeSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: mockMoleculeListResponse.items,
    });
    vi.mocked(hooks.useInvalidateRunsList).mockReturnValue(invalidateRunsList);

    renderWithQuery();

    await user.click(await screen.findByRole("button", { name: /run actions for aaaaaaaa/i }));
    await user.click(screen.getByRole("button", { name: /resume run/i }));

    await waitFor(() => {
      expect(api.resumeRun).toHaveBeenCalledWith(pausedRun.id);
      expect(invalidateRunsList).toHaveBeenCalledTimes(1);
    });
  });

  it("deletes a run from the row actions menu after confirmation", async () => {
    const user = userEvent.setup();
    const invalidateRunsList = vi.fn().mockResolvedValue(undefined);

    vi.mocked(hooks.useListRunSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: { ...mockRunListResponse, items: [mockRun1], total: 1 },
      refetch: vi.fn().mockResolvedValue(undefined),
    });

    vi.mocked(hooks.useAllMoleculeSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: mockMoleculeListResponse.items,
    });
    vi.mocked(hooks.useInvalidateRunsList).mockReturnValue(invalidateRunsList);

    renderWithQuery();

    await user.click(await screen.findByRole("button", { name: /run actions for aaaaaaaa/i }));
    await user.click(screen.getByRole("button", { name: /delete run/i }));
    await user.click(screen.getByRole("button", { name: /delete run/i }));

    await waitFor(() => {
      expect(api.deleteRun).toHaveBeenCalledWith(mockRun1.id);
      expect(invalidateRunsList).toHaveBeenCalledTimes(1);
    });
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it("polls in the background while active runs are present", async () => {
    vi.useFakeTimers();
    const refetch = vi.fn().mockResolvedValue(undefined);

    vi.mocked(hooks.useListRunSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: { ...mockRunListResponse, items: [mockRun2], total: 1 },
      refetch,
    });

    vi.mocked(hooks.useAllMoleculeSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: mockMoleculeListResponse.items,
    });

    renderWithQuery();

    expect(screen.getByText("RUNNING")).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });

    expect(refetch).toHaveBeenCalledTimes(1);
  });
});
