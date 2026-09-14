import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  api,
  createMoleculeSummary,
  hooks,
  mockNavigate,
  renderWithQuery,
  resetMoleculesListMocks,
} from "./molecules-list.test-utils";

beforeEach(resetMoleculesListMocks);

describe("MoleculesList bulk editing", () => {
  function mockSummariesQuery(
    items: ReturnType<typeof createMoleculeSummary>[],
    overrides: Partial<ReturnType<typeof hooks.useFetchMoleculeSummaries>> = {},
  ) {
    const refetch = vi.fn().mockResolvedValue(undefined);

    vi.mocked(hooks.useFetchMoleculeSummaries).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: {
        items,
        total: items.length,
      },
      refetch,
      ...overrides,
    });

    return { refetch };
  }

  it("deletes selected molecules after confirmation", async () => {
    const user = userEvent.setup();
    const invalidateMoleculesList = vi.fn().mockResolvedValue(undefined);
    const molecules = [
      createMoleculeSummary({ id: "mol-1", name: "Hydrogen" }),
      createMoleculeSummary({ id: "mol-2", name: "Lithium hydride", formula: "HLi" }),
    ];

    const { refetch } = mockSummariesQuery(molecules);
    vi.mocked(hooks.useInvalidateMoleculesList).mockReturnValue(invalidateMoleculesList);

    renderWithQuery();

    await user.click(await screen.findByRole("button", { name: /^edit$/i }));
    await user.click(screen.getByRole("checkbox", { name: /select hydrogen/i }));
    await user.click(screen.getByRole("checkbox", { name: /select lithium hydride/i }));
    await user.click(screen.getByRole("button", { name: /delete \(2\)/i }));

    expect(refetch).toHaveBeenCalledTimes(1);
    expect(
      screen.getByRole("dialog", { name: /delete 2 selected molecules/i }),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /delete molecules/i }));

    await waitFor(() => {
      expect(api.deleteMolecule).toHaveBeenCalledTimes(2);
      expect(api.deleteMolecule).toHaveBeenNthCalledWith(1, "mol-1", {
        deleteAssociatedRuns: false,
      });
      expect(api.deleteMolecule).toHaveBeenNthCalledWith(2, "mol-2", {
        deleteAssociatedRuns: false,
      });
      expect(invalidateMoleculesList).toHaveBeenCalledTimes(1);
    });
  });

  it("can also delete associated runs for selected molecules", async () => {
    const user = userEvent.setup();
    const invalidateMoleculesList = vi.fn().mockResolvedValue(undefined);

    mockSummariesQuery([createMoleculeSummary({ id: "mol-1", name: "Hydrogen", run_count: 2 })]);
    vi.mocked(hooks.useInvalidateMoleculesList).mockReturnValue(invalidateMoleculesList);

    renderWithQuery();

    await user.click(await screen.findByRole("button", { name: /^edit$/i }));
    await user.click(screen.getByRole("checkbox", { name: /select hydrogen/i }));
    await user.click(screen.getByRole("button", { name: /delete \(1\)/i }));
    await user.click(screen.getByRole("checkbox", { name: /also delete associated runs/i }));
    await user.click(screen.getByRole("button", { name: /delete molecule/i }));

    await waitFor(() => {
      expect(api.deleteMolecule).toHaveBeenCalledWith("mol-1", {
        deleteAssociatedRuns: true,
      });
      expect(invalidateMoleculesList).toHaveBeenCalledTimes(1);
    });
  });

  it("opens bulk delete confirmation when Delete is pressed in edit mode", async () => {
    const user = userEvent.setup();

    const { refetch } = mockSummariesQuery([
      createMoleculeSummary({ id: "mol-1", name: "Hydrogen" }),
    ]);

    renderWithQuery();

    await user.click(await screen.findByRole("button", { name: /^edit$/i }));
    await user.click(screen.getByRole("checkbox", { name: /select hydrogen/i }));
    await user.keyboard("[Delete]");

    expect(refetch).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("dialog", { name: /delete selected molecule\?/i })).toBeInTheDocument();
  });

  it("uses row clicks to select instead of navigating while edit mode is active", async () => {
    const user = userEvent.setup();

    mockSummariesQuery([createMoleculeSummary({ id: "mol-1", name: "Hydrogen" })]);

    renderWithQuery();

    await user.click(await screen.findByRole("button", { name: /^edit$/i }));
    await user.click(screen.getByRole("button", { pressed: false, name: /hydrogen/i }));

    expect(screen.getByText("1 selected")).toBeInTheDocument();
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it("only offers associated-run deletion when the selection has dependent runs", async () => {
    const user = userEvent.setup();

    mockSummariesQuery([createMoleculeSummary({ id: "mol-1", name: "Hydrogen", run_count: 0 })]);

    renderWithQuery();

    await user.click(await screen.findByRole("button", { name: /^edit$/i }));
    await user.click(screen.getByRole("checkbox", { name: /select hydrogen/i }));
    await user.click(screen.getByRole("button", { name: /delete \(1\)/i }));

    expect(
      screen.queryByRole("checkbox", { name: /also delete associated runs/i }),
    ).not.toBeInTheDocument();
  });
});
