import { screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api/http";
import {
  hooks,
  mockMoleculeListResponse,
  mockRunListResponse,
  renderWithQuery,
  resetRunsListMocks,
} from "./runs-list.test-utils";

beforeEach(resetRunsListMocks);

describe("RunsList loading and errors", () => {
  it("renders loading skeleton while fetching", async () => {
    // Mock hooks to return loading state
    (hooks.useListRunSummaries as ReturnType<typeof vi.fn>).mockReturnValue({
      isLoading: true,
      isError: false,
      error: null,
      data: undefined,
    });

    (hooks.useAllMoleculeSummaries as ReturnType<typeof vi.fn>).mockReturnValue({
      isLoading: true,
      isError: false,
      error: null,
      data: undefined,
    });

    const { container } = renderWithQuery();

    // Should show skeleton elements
    const skeletons = container.querySelectorAll("[data-slot='skeleton']");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("sets aria-busy=true on the container while loading", async () => {
    (hooks.useListRunSummaries as ReturnType<typeof vi.fn>).mockReturnValue({
      isLoading: true,
      isError: false,
      error: null,
      data: undefined,
    });

    (hooks.useAllMoleculeSummaries as ReturnType<typeof vi.fn>).mockReturnValue({
      isLoading: true,
      isError: false,
      error: null,
      data: undefined,
    });

    const { container } = renderWithQuery();

    const busyEl = container.querySelector("[aria-busy='true']");
    expect(busyEl).toBeInTheDocument();
  });

  it("renders error message if fetch fails", async () => {
    const testError = new ApiError("FETCH_ERROR", "Failed to load runs", 500);

    (hooks.useListRunSummaries as ReturnType<typeof vi.fn>).mockReturnValue({
      isLoading: false,
      isError: true,
      error: testError,
      data: undefined,
    });

    (hooks.useAllMoleculeSummaries as ReturnType<typeof vi.fn>).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: mockMoleculeListResponse.items,
    });

    renderWithQuery();

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
    expect(screen.getByRole("alert")).toHaveTextContent("Failed to load runs");
  });

  it("renders run rows while molecule labels are still loading", async () => {
    (hooks.useListRunSummaries as ReturnType<typeof vi.fn>).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: mockRunListResponse,
    });

    (hooks.useAllMoleculeSummaries as ReturnType<typeof vi.fn>).mockReturnValue({
      isLoading: true,
      isError: false,
      error: null,
      data: undefined,
    });

    renderWithQuery();

    await waitFor(() => {
      expect(screen.getByText("COMPLETED")).toBeInTheDocument();
    });
    expect(screen.getAllByText("bbbbbbbb…")).toHaveLength(2);
    expect(screen.queryByLabelText("Loading runs")).not.toBeInTheDocument();
  });

  it("uses embedded run-summary molecule names before the filter lookup resolves", async () => {
    (hooks.useListRunSummaries as ReturnType<typeof vi.fn>).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: {
        ...mockRunListResponse,
        items: [{ ...mockRunListResponse.items[0], molecule_name: "Inline H2" }],
        total: 1,
      },
    });

    (hooks.useAllMoleculeSummaries as ReturnType<typeof vi.fn>).mockReturnValue({
      isLoading: true,
      isError: false,
      error: null,
      data: undefined,
    });

    renderWithQuery();

    await waitFor(() => {
      expect(screen.getByText("Inline H2")).toBeInTheDocument();
    });
    expect(screen.queryByText("bbbbbbbb…")).not.toBeInTheDocument();
  });

  it("keeps runs visible if the molecule-label lookup fails", async () => {
    (hooks.useListRunSummaries as ReturnType<typeof vi.fn>).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: mockRunListResponse,
    });

    (hooks.useAllMoleculeSummaries as ReturnType<typeof vi.fn>).mockReturnValue({
      isLoading: false,
      isError: true,
      error: new Error("Failed to load molecules"),
      data: undefined,
    });

    renderWithQuery();

    await waitFor(() => {
      expect(screen.getByText("COMPLETED")).toBeInTheDocument();
    });
    expect(screen.getByText(/molecule labels are temporarily unavailable/i)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
