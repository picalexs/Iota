import { expect, test } from "@playwright/test";

const moleculeSummary = {
  id: "00000000-0000-0000-0000-000000000001",
  name: "Water",
  charge: 0,
  atom_count: 3,
  run_count: 0,
  formula: "H2O",
  iupac_name: "oxidane",
  eligibility: {
    selectable: true,
    label: "Ready",
    reason: null,
    capability_labels: ["All algorithms", "12 qubits"],
  },
  visualizable: true,
  runnable_algorithms: ["vqe"],
  blocking_reasons: [],
  warnings: [],
};

test.beforeEach(async ({ page }) => {
  await page.route(/\/api\//, (route) => {
    const url = new URL(route.request().url());
    if (!url.pathname.startsWith("/api/")) {
      return route.continue();
    }

    if (url.pathname === "/api/settings/ibm-profiles") {
      return route.fulfill({
        status: 400,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Invalid host header" }),
      });
    }
    if (url.pathname === "/api/backends") {
      return route.fulfill({ json: { backends: [], warnings: [] } });
    }
    if (url.pathname === "/api/molecules/summaries") {
      return route.fulfill({ json: { items: [moleculeSummary], total: 1 } });
    }

    return route.fulfill({ json: {} });
  });
});

test("loads molecules when IBM profiles are unavailable", async ({ page }) => {
  await page.goto("/molecules");

  await expect(page.getByRole("heading", { name: "Molecule Library" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Water" })).toBeVisible();
  await expect(page.getByText("H2O")).toBeVisible();
  await expect(page.getByText("IBM Profiles Unavailable")).not.toBeVisible();
  await expect(page.getByText("An unexpected error occurred")).not.toBeVisible();

  await page.getByRole("button", { name: /IBM profiles/i }).click();
  await expect(page.getByRole("link", { name: "Open IBM profile settings" })).toBeVisible();
  await expect(page.getByText("Profiles unavailable")).toBeVisible();
});
