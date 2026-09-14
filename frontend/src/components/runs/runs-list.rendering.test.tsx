import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  hooks,
  mockMoleculeListResponse,
  mockNavigate,
  mockRun1,
  mockRun2,
  mockRunListResponse,
  renderWithQuery,
  resetRunsListMocks,
  setRunsListViewport,
} from "./runs-list.test-utils";

beforeEach(resetRunsListMocks);

describe("RunsList rendering and navigation", () => {
  it("renders a row for each run with its molecule name", async () => {
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
      expect(screen.getByText("H2")).toBeInTheDocument();
      expect(screen.getByText("LiH")).toBeInTheDocument();
    });
  });

  it("shows abbreviated molecule_id when molecule not in lookup", async () => {
    const runWithUnknownMolecule = {
      ...mockRun1,
      molecule_id: "cccccccc-0000-0000-0000-000000000099",
    };

    vi.mocked(hooks.useListRunSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: { ...mockRunListResponse, items: [runWithUnknownMolecule], total: 1 },
    });

    vi.mocked(hooks.useAllMoleculeSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: mockMoleculeListResponse.items,
    });

    renderWithQuery();

    await waitFor(() => {
      // Should show abbreviated UUID: first 8 chars
      expect(screen.getByText("cccccccc…")).toBeInTheDocument();
    });
  });

  it("renders empty state when no runs exist", async () => {
    vi.mocked(hooks.useListRunSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: { ...mockRunListResponse, items: [], total: 0 },
    });

    vi.mocked(hooks.useAllMoleculeSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: mockMoleculeListResponse.items,
    });

    renderWithQuery();

    await waitFor(() => {
      expect(screen.getByText(/no runs yet/i)).toBeInTheDocument();
    });
  });

  it("renders correct status badge for COMPLETED runs", async () => {
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

    await waitFor(() => {
      expect(screen.getByText("COMPLETED")).toBeInTheDocument();
    });
  });

  it("renders correct status badge for RUNNING runs", async () => {
    vi.mocked(hooks.useListRunSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: { ...mockRunListResponse, items: [mockRun2], total: 1 },
    });

    vi.mocked(hooks.useAllMoleculeSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: mockMoleculeListResponse.items,
    });

    renderWithQuery();

    await waitFor(() => {
      expect(screen.getByText("RUNNING")).toBeInTheDocument();
    });
  });

  it("navigates to run detail page when row is clicked", async () => {
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

    await waitFor(() => {
      expect(screen.getByText("H2")).toBeInTheDocument();
    });

    // Click the row
    const row = screen.getByRole("row", { name: /aaaaaaaa/i });
    await user.click(row);

    expect(mockNavigate).toHaveBeenCalledWith({
      to: "/runs/$runId",
      params: { runId: mockRun1.id },
    });
  });

  it("does not navigate when the row actions trigger is clicked", async () => {
    const user = userEvent.setup();
    vi.mocked(hooks.useListRunSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: { ...mockRunListResponse, items: [mockRun2], total: 1 },
    });

    vi.mocked(hooks.useAllMoleculeSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: mockMoleculeListResponse.items,
    });

    renderWithQuery();

    await user.click(await screen.findByRole("button", { name: /run actions for aaaaaaaa/i }));

    expect(mockNavigate).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: /pause run/i })).toBeInTheDocument();
  });

  it("renders column headers", async () => {
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
      expect(screen.getByRole("columnheader", { name: /run id/i })).toBeInTheDocument();
      expect(screen.getByRole("columnheader", { name: /molecule/i })).toBeInTheDocument();
      expect(screen.getByRole("columnheader", { name: /status/i })).toBeInTheDocument();
      expect(screen.getByRole("columnheader", { name: /chemical accurate/i })).toBeInTheDocument();
      expect(screen.getByRole("columnheader", { name: /method/i })).toBeInTheDocument();
      expect(screen.getByRole("columnheader", { name: /backend/i })).toBeInTheDocument();
      expect(screen.getByRole("columnheader", { name: /runtime/i })).toBeInTheDocument();
      expect(screen.getByRole("columnheader", { name: /created/i })).toBeInTheDocument();
    });
  });

  it("renders New Run beside Edit in the list toolbar", async () => {
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
      expect(screen.getByRole("button", { name: /^edit$/i })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /new run/i })).toBeInTheDocument();
    });
  });

  it("switches to stacked cards on phone and tablet widths", async () => {
    setRunsListViewport(900);
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

    const list = await screen.findByRole("list", { name: /quantum runs/i });
    expect(screen.queryByRole("table", { name: /quantum runs/i })).not.toBeInTheDocument();

    const card = within(list).getByRole("listitem", { name: /aaaaaaaa/i });
    expect(within(card).getByText("H2")).toBeInTheDocument();
    expect(within(card).getByText("Method")).toBeInTheDocument();
    expect(within(card).getByText("Statevector")).toBeInTheDocument();
    expect(within(card).getByText("Chemically accurate")).toBeInTheDocument();
  });

  it("renders icon-only chemical-accuracy state after the run status", async () => {
    const notConvergedRun = {
      ...mockRun1,
      id: "aaaaaaaa-0000-0000-0000-000000000003",
      converged: false,
      chemical_accurate: false,
    };
    const pendingRun = {
      ...mockRun2,
      id: "aaaaaaaa-0000-0000-0000-000000000004",
      converged: null,
      chemical_accurate: null,
    };

    vi.mocked(hooks.useListRunSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: {
        ...mockRunListResponse,
        items: [mockRun1, notConvergedRun, pendingRun],
        total: 3,
      },
    });

    vi.mocked(hooks.useAllMoleculeSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: mockMoleculeListResponse.items,
    });

    renderWithQuery();

    await waitFor(() => {
      expect(screen.getByLabelText("Chemically accurate")).toBeInTheDocument();
      expect(screen.getByLabelText("Not chemically accurate")).toBeInTheDocument();
      expect(screen.getByLabelText("Chemical accuracy unavailable")).toBeInTheDocument();
    });
    expect(screen.queryByText("Not chemically accurate")).not.toBeInTheDocument();
  });

  it("renders algorithm and runtime columns", async () => {
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

    await waitFor(() => {
      expect(screen.getByText("VQE")).toBeInTheDocument();
      expect(screen.getByText("5m 0s")).toBeInTheDocument();
    });
  });

  it("updates sort state from method and time-ran headers", async () => {
    const user = userEvent.setup();
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

    await user.click(screen.getByRole("button", { name: /sort by method/i }));
    await user.click(screen.getByRole("button", { name: /sort by runtime/i }));

    expect(mockNavigate).toHaveBeenCalledWith({
      to: "/runs",
      search: expect.any(Function),
    });
    const methodSearch = mockNavigate.mock.calls.at(-2)?.[0].search({});
    const runtimeSearch = mockNavigate.mock.calls.at(-1)?.[0].search({});
    expect(methodSearch).toMatchObject({ sort: "algorithm", order: "desc" });
    expect(runtimeSearch).toMatchObject({ sort: "runtime", order: "desc" });
  });

  it("updates route search when backend and chemical-accuracy filters are selected", async () => {
    const user = userEvent.setup();
    const ibmRun = {
      ...mockRun1,
      id: "aaaaaaaa-0000-0000-0000-000000000005",
      backend_target: "ibm_runtime" as const,
      backend_name: "ibm_brisbane",
      converged: false,
      chemical_accurate: false,
    };

    vi.mocked(hooks.useListRunSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: { ...mockRunListResponse, items: [mockRun1, ibmRun], total: 2 },
    });

    vi.mocked(hooks.useAllMoleculeSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: mockMoleculeListResponse.items,
    });

    renderWithQuery();

    await user.click(screen.getByRole("button", { name: /filter by backend/i }));
    await user.click(screen.getByText("IBM Runtime"));
    await user.click(screen.getByRole("button", { name: /filter by chemical accuracy/i }));
    await user.click(screen.getByText("No"));

    const backendSearch = mockNavigate.mock.calls.at(-2)?.[0].search({});
    const chemicalAccuracySearch = mockNavigate.mock.calls.at(-1)?.[0].search({
      backend_target: "ibm_runtime",
    });

    expect(backendSearch).toMatchObject({ backend_target: "ibm_runtime" });
    expect(chemicalAccuracySearch).toMatchObject({
      backend_target: "ibm_runtime",
      chemical_accurate: false,
    });
  });
});
