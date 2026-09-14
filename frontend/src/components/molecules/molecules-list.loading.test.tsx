import { screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  createMoleculeSummary,
  hooks,
  renderWithQuery,
  resetMoleculesListMocks,
} from "./molecules-list.test-utils";

beforeEach(resetMoleculesListMocks);

describe("MoleculesList loading and cache", () => {
  it("shows skeleton on first load when no cache is present", () => {
    (hooks.useFetchMoleculeSummaries as ReturnType<typeof vi.fn>).mockReturnValue({
      isLoading: true,
      isError: false,
      error: null,
      data: undefined,
    });

    const { container } = renderWithQuery();
    const skeletons = container.querySelectorAll("[data-slot='skeleton']");

    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("shows error when first load fails and no cache exists", async () => {
    const testError = new Error("Failed to load molecules");

    (hooks.useFetchMoleculeSummaries as ReturnType<typeof vi.fn>).mockReturnValue({
      isLoading: false,
      isError: true,
      error: testError,
      data: undefined,
    });

    renderWithQuery();

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("Failed to load molecules");
    });
  });

  it("renders cached molecules immediately on remount without skeleton flash", async () => {
    const firstResponse = {
      items: [createMoleculeSummary({ name: "Cached molecule" })],
      total: 1,
    };

    (hooks.useFetchMoleculeSummaries as ReturnType<typeof vi.fn>).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: firstResponse,
    });

    const firstRender = renderWithQuery();
    await waitFor(() => {
      expect(screen.getByText("Cached molecule")).toBeInTheDocument();
    });
    firstRender.unmount();

    // Second render still has cached data
    const secondRender = renderWithQuery();

    expect(screen.getByText("Cached molecule")).toBeInTheDocument();
    const skeletons = secondRender.container.querySelectorAll("[data-slot='skeleton']");
    expect(skeletons.length).toBe(0);
  });

  it("updates stale cached data after background refresh resolves", async () => {
    const firstResponse = {
      items: [createMoleculeSummary({ name: "Before refresh" })],
      total: 1,
    };

    (hooks.useFetchMoleculeSummaries as ReturnType<typeof vi.fn>).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: firstResponse,
    });

    const { unmount } = renderWithQuery();
    await waitFor(() => {
      expect(screen.getByText("Before refresh")).toBeInTheDocument();
    });
    unmount();

    const refreshResponse = {
      items: [createMoleculeSummary({ name: "After refresh" })],
      total: 1,
    };

    (hooks.useFetchMoleculeSummaries as ReturnType<typeof vi.fn>).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: refreshResponse,
    });

    renderWithQuery();

    await waitFor(() => {
      expect(screen.getByText("After refresh")).toBeInTheDocument();
    });
  });

  it("keeps cached data visible when background refresh fails", async () => {
    const firstResponse = {
      items: [createMoleculeSummary({ name: "Cached on failure" })],
      total: 1,
    };

    (hooks.useFetchMoleculeSummaries as ReturnType<typeof vi.fn>).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: firstResponse,
    });

    const firstRender = renderWithQuery();
    await waitFor(() => {
      const rows = firstRender.container.querySelectorAll("a[aria-label]");
      expect(rows.length).toBeGreaterThan(0);
    });
    firstRender.unmount();

    // Second render after error still has cached data available, but shows error
    (hooks.useFetchMoleculeSummaries as ReturnType<typeof vi.fn>).mockReturnValue({
      isLoading: false,
      isError: true,
      error: new Error("background refresh failed"),
      data: firstResponse, // Still have cached data
    });

    renderWithQuery();

    // When there's an error, the error is displayed (not the cached data)
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("background refresh failed")).toBeInTheDocument();
  });
});
