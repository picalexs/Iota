import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.route(/\/api\//, (route) => {
    const requestUrl = new URL(route.request().url());
    if (!requestUrl.pathname.startsWith("/api/")) {
      return route.continue();
    }
    const url = requestUrl.pathname;

    if (url.includes("/settings/ibm-profiles")) {
      return route.fulfill({ json: { profiles: [], active_profile_id: null } });
    }
    if (url.includes("/backends")) {
      return route.fulfill({ json: { backends: [], warnings: [] } });
    }
    if (url.includes("/molecules/summaries")) {
      return route.fulfill({ json: { items: [], total: 0 } });
    }
    if (url.includes("/runs/summaries")) {
      return route.fulfill({ json: { items: [], total: 0, limit: 1, offset: 0 } });
    }
    if (url.includes("/benchmarks")) {
      return route.fulfill({ json: { items: [], total: 0, limit: 1, offset: 0 } });
    }

    return route.fulfill({ json: {} });
  });
});

test("home page renders the primary navigation", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Quantum Simulation Studio" })).toBeVisible();
  await expect(page.getByRole("link", { name: /Browse Molecules/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /View Runs/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /Open Benchmarks/ })).toBeVisible();
});

test("primary navigation opens the main list routes", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("link", { name: /Browse Molecules/ }).click();
  await expect(page).toHaveURL(/\/molecules$/);
  await expect(page.getByRole("heading", { name: "Molecule Library" })).toBeVisible();

  await page.getByRole("link", { name: "Runs" }).click();
  await expect(page).toHaveURL(/\/runs$/);
  await expect(page.getByRole("heading", { name: "Quantum Runs" })).toBeVisible();

  await page.getByRole("link", { name: "Benchmarks" }).click();
  await expect(page).toHaveURL(/\/benchmarks$/);
  await expect(page.getByRole("heading", { name: "Benchmark Runs" })).toBeVisible();
});
