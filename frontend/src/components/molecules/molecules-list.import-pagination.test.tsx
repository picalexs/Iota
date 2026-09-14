import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  api,
  createImportPreview,
  createMolecule,
  createMoleculeSummary,
  hooks,
  mockNavigate,
  renderWithQuery,
  resetMoleculesListMocks,
  routerMod,
} from "./molecules-list.test-utils";

beforeEach(resetMoleculesListMocks);

describe("MoleculesList import and pagination", () => {
  it("keeps spinner feedback for search action in import dialog", async () => {
    const user = userEvent.setup();

    (hooks.useFetchMoleculeSummaries as ReturnType<typeof vi.fn>).mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: { items: [], total: 0 },
    });

    (api.searchPubChem as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

    renderWithQuery();

    await user.click(screen.getByRole("button", { name: /import molecule from pubchem/i }));
    const input = screen.getByLabelText("Compound name to search");
    await user.type(input, "water");
    await user.click(screen.getByRole("button", { name: /^search$/i }));

    expect(screen.getAllByText("Searching…").length).toBeGreaterThan(0);
    expect(document.querySelector(".animate-spin")).toBeInTheDocument();
  });

  describe("Pagination — 50 molecules per page with prev/next controls", () => {
    it("shows no pagination footer when molecules fit on one page", async () => {
      const molecules = Array.from({ length: 25 }, (_, i) =>
        createMoleculeSummary({ id: `mol-${i}`, name: `Molecule-${i}` }),
      );

      (hooks.useFetchMoleculeSummaries as ReturnType<typeof vi.fn>).mockReturnValue({
        isLoading: false,
        isError: false,
        error: null,
        data: { items: molecules, total: 25 },
      });

      renderWithQuery();

      await waitFor(() => {
        expect(screen.queryByLabelText("Go to molecule page")).not.toBeInTheDocument();
        expect(screen.queryByText("Showing 1-25 of 25")).not.toBeInTheDocument();
      });
    });

    it("shows runs-style pagination controls when total exceeds page size (50)", async () => {
      const molecules = Array.from({ length: 50 }, (_, i) =>
        createMoleculeSummary({ id: `mol-${i}`, name: `Molecule-${i}` }),
      );

      (hooks.useFetchMoleculeSummaries as ReturnType<typeof vi.fn>).mockReturnValue({
        isLoading: false,
        isError: false,
        error: null,
        data: { items: molecules, total: 150 }, // 3 pages
      });

      renderWithQuery();

      await waitFor(() => {
        expect(screen.getByText("Showing 1-50 of 150")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Previous page" })).toHaveTextContent("Previous");
        expect(screen.getByLabelText("Go to molecule page")).toHaveValue("1");
        expect(screen.getByText("/ 3")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Next page" })).toHaveTextContent("Next");
      });
    });

    it("jumps to an entered page number", async () => {
      const user = userEvent.setup();
      const molecules = Array.from({ length: 50 }, (_, i) =>
        createMoleculeSummary({ id: `mol-${i}`, name: `Molecule-${i}` }),
      );

      (hooks.useFetchMoleculeSummaries as ReturnType<typeof vi.fn>).mockReturnValue({
        isLoading: false,
        isError: false,
        error: null,
        data: { items: molecules, total: 150 },
      });

      renderWithQuery();

      const pageInput = await screen.findByLabelText("Go to molecule page");
      mockNavigate.mockClear();
      await user.clear(pageInput);
      await user.type(pageInput, "3{Enter}");

      expect(mockNavigate).toHaveBeenCalledWith({
        to: "/molecules",
        search: expect.any(Function),
      });
      const lastNavigateCall = mockNavigate.mock.calls.at(-1);
      const nextSearch = lastNavigateCall?.[0].search({});
      expect(nextSearch).toMatchObject({ page: 3 });
    });

    it("clamps entered molecule pages into range", async () => {
      const user = userEvent.setup();
      const molecules = Array.from({ length: 50 }, (_, i) =>
        createMoleculeSummary({ id: `mol-${i}`, name: `Molecule-${i}` }),
      );

      (hooks.useFetchMoleculeSummaries as ReturnType<typeof vi.fn>).mockReturnValue({
        isLoading: false,
        isError: false,
        error: null,
        data: { items: molecules, total: 150 },
      });

      renderWithQuery();

      const pageInput = await screen.findByLabelText("Go to molecule page");
      mockNavigate.mockClear();
      await user.clear(pageInput);
      await user.type(pageInput, "9{Enter}");

      const lastNavigateCall = mockNavigate.mock.calls.at(-1);
      const nextSearch = lastNavigateCall?.[0].search({});
      expect(nextSearch).toMatchObject({ page: 3 });
    });

    it("next button is disabled on last page", async () => {
      const user = userEvent.setup();
      const moleculesPage2 = Array.from({ length: 50 }, (_, i) =>
        createMoleculeSummary({ id: `mol-1-${i}`, name: `Molecule-P2-${i}` }),
      );

      // Start on page 2 (last page) — simulates URL already at page 2
      vi.mocked(routerMod.useSearch).mockReturnValue({ q: "", page: 2 });

      (hooks.useFetchMoleculeSummaries as ReturnType<typeof vi.fn>).mockReturnValue({
        isLoading: false,
        isError: false,
        error: null,
        data: { items: moleculesPage2, total: 100 }, // 2 pages, currently on last
      });

      renderWithQuery();

      // Page 2 of 2 should show
      await waitFor(() => {
        expect(screen.getByText("Showing 51-100 of 100")).toBeInTheDocument();
        expect(screen.getByLabelText("Go to molecule page")).toHaveValue("2");
        expect(screen.getByText("/ 2")).toBeInTheDocument();
      });

      // Next button should be enabled on page 1 (simulate checking enabled first)
      const nextButton = screen.getByLabelText("Next page");
      expect(nextButton).toBeDisabled();

      // Clicking a disabled Next button should not navigate away from the last page.
      mockNavigate.mockClear();
      await user.click(nextButton);
      expect(mockNavigate).not.toHaveBeenCalled();

      const nextButtonPage2 = screen.getByLabelText("Next page");
      expect(nextButtonPage2).toBeDisabled();
    });

    it("keeps the URL page instead of resetting to page 1 on mount", async () => {
      const moleculesPage3 = Array.from({ length: 50 }, (_, i) =>
        createMoleculeSummary({ id: `mol-p3-${i}`, name: `Molecule-P3-${i}` }),
      );

      vi.mocked(routerMod.useSearch).mockReturnValue({ q: "", page: 3 });

      (hooks.useFetchMoleculeSummaries as ReturnType<typeof vi.fn>).mockReturnValue({
        isLoading: false,
        isError: false,
        error: null,
        data: { items: moleculesPage3, total: 165 },
      });

      renderWithQuery();

      await waitFor(() => {
        expect(hooks.useFetchMoleculeSummaries).toHaveBeenCalledWith(
          expect.objectContaining({ offset: 100 }),
        );
        expect(screen.getByText("Showing 101-150 of 165")).toBeInTheDocument();
      });
      expect(mockNavigate).not.toHaveBeenCalled();
    });

    it("previous button is disabled on first page", async () => {
      const molecules = Array.from({ length: 50 }, (_, i) =>
        createMoleculeSummary({ id: `mol-${i}`, name: `Molecule-${i}` }),
      );

      (hooks.useFetchMoleculeSummaries as ReturnType<typeof vi.fn>).mockReturnValue({
        isLoading: false,
        isError: false,
        error: null,
        data: { items: molecules, total: 100 },
      });

      renderWithQuery();

      await waitFor(() => {
        const prevButton = screen.getByLabelText("Previous page");
        expect(prevButton).toBeDisabled();
      });
    });

    it("resets pagination to page 1 when search query changes", async () => {
      const user = userEvent.setup();

      const molecules = Array.from({ length: 50 }, (_, i) =>
        createMoleculeSummary({ id: `mol-${i}`, name: `Page-0-${i}` }),
      );

      (hooks.useFetchMoleculeSummaries as ReturnType<typeof vi.fn>).mockReturnValue({
        isLoading: false,
        isError: false,
        error: null,
        data: { items: molecules, total: 100 },
      });

      renderWithQuery();

      await waitFor(() => {
        expect(screen.getByLabelText("Go to molecule page")).toHaveValue("1");
        expect(screen.getByText("/ 2")).toBeInTheDocument();
      });

      // Changing search should reset pagination
      const searchInput = screen.getByLabelText("Search molecules");
      await user.type(searchInput, "H2O");

      // After search input changes, should be back on page 1
      await waitFor(() => {
        const hook = hooks.useFetchMoleculeSummaries as ReturnType<typeof vi.fn>;
        const lastCall = hook.mock.calls.at(-1);
        // Verify offset is 0 (first page)
        expect(lastCall?.[0]).toMatchObject({
          offset: 0,
        });
      });
    });

    it("keeps rows visible during pagination transitions", async () => {
      const page1 = Array.from({ length: 50 }, (_, i) =>
        createMoleculeSummary({ id: `mol-p1-${i}`, name: `Page1-${i}` }),
      );

      (hooks.useFetchMoleculeSummaries as ReturnType<typeof vi.fn>).mockReturnValue({
        isLoading: false,
        isError: false,
        error: null,
        data: { items: page1, total: 150 },
      });

      const { container } = renderWithQuery();

      await waitFor(() => {
        const rows = container.querySelectorAll("a[aria-label]");
        expect(rows.length).toBe(50);
      });

      // Rows should remain visible (no skeleton flash)
      const rows = container.querySelectorAll("a[aria-label]");
      rows.forEach((row) => {
        expect(row).toBeVisible();
      });
    });
  });

  describe("Import dialog progressive loading", () => {
    it("previews a PubChem candidate before committing the import", async () => {
      const user = userEvent.setup();

      (hooks.useFetchMoleculeSummaries as ReturnType<typeof vi.fn>).mockReturnValue({
        isLoading: false,
        isError: false,
        error: null,
        data: { items: [], total: 0 },
      });
      (api.searchPubChem as ReturnType<typeof vi.fn>).mockResolvedValue({
        results: [{ name: "water", iupac_name: "oxidane", formula: "H2O", cid: 962 }],
      });
      (api.previewMoleculeFromPubChem as ReturnType<typeof vi.fn>).mockResolvedValue(
        createImportPreview({ name: "water" }),
      );
      (api.importMoleculeFromPubChem as ReturnType<typeof vi.fn>).mockResolvedValue(
        createMolecule({ id: "water-id", name: "water" }),
      );

      renderWithQuery();

      await user.click(screen.getByRole("button", { name: /import molecule from pubchem/i }));
      await user.type(screen.getByLabelText("Compound name to search"), "water");
      await user.click(screen.getByRole("button", { name: /^search$/i }));
      await user.click(await screen.findByRole("button", { name: /water/i }));

      await waitFor(() => expect(api.previewMoleculeFromPubChem).toHaveBeenCalled());
      expect(screen.getByText("H2O")).toBeInTheDocument();
      expect(screen.getByText("Ready")).toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: /^import molecule$/i }));

      expect(api.importMoleculeFromPubChem).toHaveBeenCalledWith({
        name: "water",
        display_name: "water",
      });
    });

    it("previews and imports pasted XYZ coordinates", async () => {
      const user = userEvent.setup();
      const xyz = "3\nwater\nO 0 0 0\nH 0.757 0.586 0\nH -0.757 0.586 0";

      (hooks.useFetchMoleculeSummaries as ReturnType<typeof vi.fn>).mockReturnValue({
        isLoading: false,
        isError: false,
        error: null,
        data: { items: [], total: 0 },
      });
      (api.previewMoleculeFromXyz as ReturnType<typeof vi.fn>).mockResolvedValue(
        createImportPreview({ source: "xyz", name: "Water XYZ" }),
      );

      renderWithQuery();

      await user.click(screen.getByRole("button", { name: /import molecule from pubchem/i }));
      await user.click(screen.getByRole("button", { name: /^xyz$/i }));
      await user.type(screen.getByLabelText("XYZ molecule name"), "Water XYZ");
      await user.type(screen.getByLabelText("XYZ coordinates"), xyz);
      await user.click(screen.getByRole("button", { name: /^preview$/i }));

      await waitFor(() => expect(api.previewMoleculeFromXyz).toHaveBeenCalled());
      expect(screen.getByText("H2O")).toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: /^import molecule$/i }));

      expect(api.importMoleculeFromXyz).toHaveBeenCalledWith({
        name: "Water XYZ",
        xyz,
        charge: 0,
        multiplicity: 1,
        derive_active_space: true,
      });
    }, 20_000);

    it("shows updating indicator when search results are refreshing", async () => {
      const user = userEvent.setup();

      (hooks.useFetchMoleculeSummaries as ReturnType<typeof vi.fn>).mockReturnValue({
        isLoading: false,
        isError: false,
        error: null,
        data: { items: [], total: 0 },
      });

      renderWithQuery();

      await user.click(screen.getByRole("button", { name: /import molecule from pubchem/i }));
      const input = screen.getByLabelText("Compound name to search");

      // Type to trigger search
      (api.searchPubChem as ReturnType<typeof vi.fn>).mockReturnValue(
        new Promise(() => {}), // Never resolves — keeps search pending
      );

      await user.type(input, "water");

      // Manually trigger search (the debounce will fire after 400ms, so we click the button)
      const searchBtn = screen.getByRole("button", { name: /^search$/i });
      await user.click(searchBtn);

      // Should show searching state (button text changes)
      await waitFor(() => {
        const buttons = screen.getAllByRole("button");
        const searchingButton = buttons.find((btn) => btn.textContent?.includes("Searching"));
        expect(searchingButton).toBeTruthy();
      });
    });
  });
});
