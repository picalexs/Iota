import { mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { chromium } from "@playwright/test";

const FRONTEND_BASE_URL = process.env.FRONTEND_BASE_URL ?? "http://localhost:5173";
const OUTPUT_DIR = resolve(dirname(fileURLToPath(import.meta.url)), "../../output/playwright");
const TERMINAL_STATUSES = new Set(["COMPLETED", "FAILED", "CANCELLED"]);
const PREFERRED_MOLECULE_KEYWORDS = [
  "Hydrogen (H₂)",
  "Hydrogen (H2)",
  "Lithium Hydride",
  "Hydrogen Fluoride",
  "Water",
];
const REQUESTED_SCENARIOS = new Set(
  (process.env.AER_MATRIX_SCENARIOS ?? "")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean),
);

/**
 * @typedef {{
 *   name: string;
 *   setup: (page: import("@playwright/test").Page) => Promise<void>;
 * }} Scenario
 */

async function ensureOutputDir() {
  await mkdir(OUTPUT_DIR, { recursive: true });
}

function elapsedSeconds(startedAt) {
  return Number(((Date.now() - startedAt) / 1000).toFixed(1));
}

async function fetchJson(url, timeoutMs = 10000) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, {
      headers: { Accept: "application/json" },
      signal: controller.signal,
    });
    if (!response.ok) {
      throw new Error(`Request failed ${response.status} for ${url}`);
    }
    return await response.json();
  } finally {
    clearTimeout(timeoutId);
  }
}

async function gotoNewRun(page) {
  await page.goto(`${FRONTEND_BASE_URL}/runs/new`, { waitUntil: "domcontentloaded" });
  await page.getByText("Create Simulation Run").waitFor({ timeout: 20000 });
}

async function selectPreferredCompatibleMolecule(page) {
  const combobox = page.getByRole("combobox", { name: /molecule/i });
  await combobox.waitFor({ state: "visible", timeout: 20000 });
  await combobox.click();

  const options = page.getByRole("option");
  await options.first().waitFor({ state: "visible", timeout: 20000 });
  const count = await options.count();
  let firstSelectable = null;
  for (let index = 0; index < count; index += 1) {
    const option = options.nth(index);
    if ((await option.getAttribute("aria-disabled")) === "true") continue;
    const text = (await option.innerText()).trim();
    if (firstSelectable === null) {
      firstSelectable = { option, text };
    }
    if (PREFERRED_MOLECULE_KEYWORDS.some((keyword) => text.includes(keyword))) {
      await option.click();
      return text.split("\n")[0]?.trim() || text;
    }
  }

  if (firstSelectable) {
    await firstSelectable.option.click();
    return firstSelectable.text.split("\n")[0]?.trim() || firstSelectable.text;
  }

  throw new Error("No selectable molecule option was available");
}

async function selectAerBackend(page) {
  const backendCard = page.locator("#backend-option-aer_simulator");
  await backendCard.waitFor({ state: "visible", timeout: 20000 });
  await backendCard.click();
}

async function enableManualMode(page) {
  const button = page.locator("#mode-option-advanced");
  await button.waitFor({ state: "visible", timeout: 10000 });
  await button.click();
}

async function selectAlgorithm(page, algorithm) {
  const button = page.locator(`#algorithm-option-${algorithm}`);
  await button.waitFor({ state: "visible", timeout: 10000 });
  await button.click();
}

async function fillInputById(page, id, value) {
  const input = page.locator(`[id="${id}"]`);
  await input.waitFor({ state: "visible", timeout: 10000 });
  await input.fill(String(value));
  await input.blur();
}

async function chooseSelectValueByTriggerId(page, triggerId, optionLabel) {
  const trigger = page.locator(`[id="${triggerId}"]`);
  await trigger.waitFor({ state: "visible", timeout: 10000 });
  await trigger.click();
  await page.getByRole("option", { name: optionLabel, exact: true }).click();
}

async function submitRun(page) {
  const createRunButton = page.getByRole("button", { name: /create run/i });
  await createRunButton.waitFor({ state: "visible", timeout: 10000 });
  await createRunButton.click();
  await page.waitForURL(/\/runs\/[0-9a-f-]{36}$/i, { timeout: 30000 });

  const match = page.url().match(/\/runs\/([0-9a-f-]{36})$/i);
  if (match?.[1] === undefined) {
    throw new Error(`Unable to extract run id from URL ${page.url()}`);
  }
  return match[1];
}

async function getDetailStatus(page) {
  const badge = page.locator('[aria-label^="Status: "]').first();
  await badge.waitFor({ state: "visible", timeout: 20000 });
  const ariaLabel = await badge.getAttribute("aria-label");
  if (ariaLabel === null || ariaLabel === "") {
    throw new Error("Run status badge missing aria-label");
  }
  return ariaLabel.replace("Status: ", "").trim();
}

async function waitForTerminalStatus(page, timeoutMs) {
  const startedAt = Date.now();
  const seen = [];
  while (Date.now() - startedAt < timeoutMs) {
    const status = await getDetailStatus(page);
    if (seen.at(-1) !== status) {
      seen.push(status);
    }
    if (TERMINAL_STATUSES.has(status)) {
      return { status, seen };
    }
    await page.waitForTimeout(1500);
  }
  throw new Error(`Timed out waiting for terminal status. Seen: ${seen.join(" -> ")}`);
}

async function fetchRunAndEvents(runId) {
  const run = await fetchJson(`${FRONTEND_BASE_URL}/api/runs/${runId}`);
  const eventsResponse = await fetchJson(`${FRONTEND_BASE_URL}/api/runs/${runId}/events`);
  const eventMessages = Array.isArray(eventsResponse?.events)
    ? eventsResponse.events
        .slice(-8)
        .map(
          (event) => event?.payload?.message ?? event?.payload?.error ?? event?.event_type ?? null,
        )
        .filter(Boolean)
    : [];
  return { run, eventMessages };
}

/** @type {Scenario[]} */
const scenarios = [
  {
    name: "vqe-advanced-light",
    setup: async (page) => {
      await enableManualMode(page);
      await selectAlgorithm(page, "vqe");
      await fillInputById(page, "advanced-vqe-reps-input", "1");
      await fillInputById(page, "advanced-vqe-max-iterations-input", "4");
      await fillInputById(page, "advanced-vqe-max-function-evaluations-input", "12");
    },
  },
  {
    name: "sqd-advanced-light",
    setup: async (page) => {
      await enableManualMode(page);
      await selectAlgorithm(page, "sqd");
      await fillInputById(page, "advanced_sqd.samples_per_batch", "128");
      await fillInputById(page, "advanced_sqd.num_batches", "4");
      await fillInputById(page, "advanced_sqd.max_iterations", "6");
    },
  },
  {
    name: "kqd-advanced-light",
    setup: async (page) => {
      await enableManualMode(page);
      await selectAlgorithm(page, "kqd");
      await fillInputById(page, "advanced-kqd-krylov-input", "4");
      await fillInputById(page, "advanced-kqd-time-step-input", "0.05");
      await chooseSelectValueByTriggerId(page, "advanced-kqd-evolution-method-select", "exact");
    },
  },
  {
    name: "qfd-advanced-light",
    setup: async (page) => {
      await enableManualMode(page);
      await selectAlgorithm(page, "qfd");
      await fillInputById(page, "advanced-qfd-time-points-input", "8");
      await fillInputById(page, "advanced-qfd-max-time-input", "1.5");
      await chooseSelectValueByTriggerId(page, "advanced-qfd-time-grid-type-select", "linear");
    },
  },
  {
    name: "qse-advanced-light",
    setup: async (page) => {
      await enableManualMode(page);
      await selectAlgorithm(page, "qse");
      await fillInputById(page, "advanced-qse-max-subspace-dim-input", "4");
      await fillInputById(page, "advanced-qse-vqe-reference-max-iterations-input", "16");
    },
  },
];

async function main() {
  await ensureOutputDir();
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  const timestamp = new Date().toISOString().replaceAll(":", "-");
  const activeScenarios =
    REQUESTED_SCENARIOS.size > 0
      ? scenarios.filter((scenario) => REQUESTED_SCENARIOS.has(scenario.name))
      : scenarios;
  const results = [];

  try {
    if (activeScenarios.length === 0) {
      throw new Error(
        `No Aer matrix scenarios matched AER_MATRIX_SCENARIOS=${process.env.AER_MATRIX_SCENARIOS ?? ""}`,
      );
    }

    for (const scenario of activeScenarios) {
      const startedAt = Date.now();
      const result = {
        name: scenario.name,
        molecule: null,
        runId: null,
        finalStatus: null,
        seenStatuses: [],
        durationSeconds: null,
        error: null,
        eventMessages: [],
        screenshot: null,
      };

      try {
        console.log(`[aer-matrix] starting ${scenario.name}`);
        await gotoNewRun(page);
        result.molecule = await selectPreferredCompatibleMolecule(page);
        await selectAerBackend(page);
        await scenario.setup(page);
        result.runId = await submitRun(page);

        const terminal = await waitForTerminalStatus(page, 240_000);
        result.finalStatus = terminal.status;
        result.seenStatuses = terminal.seen;
        result.durationSeconds = elapsedSeconds(startedAt);

        const screenshotPath = resolve(
          OUTPUT_DIR,
          `${timestamp}-${scenario.name}-${result.finalStatus.toLowerCase()}.png`,
        );
        await page.screenshot({ path: screenshotPath, fullPage: true });
        result.screenshot = screenshotPath;

        const { eventMessages } = await fetchRunAndEvents(result.runId);
        result.eventMessages = eventMessages;
      } catch (error) {
        result.error = error instanceof Error ? error.message : String(error);
        result.durationSeconds = elapsedSeconds(startedAt);
        const screenshotPath = resolve(OUTPUT_DIR, `${timestamp}-${scenario.name}-error.png`);
        await page.screenshot({ path: screenshotPath, fullPage: true }).catch(() => {});
        result.screenshot = screenshotPath;
      }

      results.push(result);
      console.log(JSON.stringify(result));
    }
  } finally {
    await browser.close();
  }

  const outputPath = resolve(OUTPUT_DIR, `${timestamp}-aer-run-matrix.json`);
  await writeFile(outputPath, `${JSON.stringify(results, null, 2)}\n`, "utf8");

  const failed = results.filter((result) => result.finalStatus === "FAILED" || result.error);
  if (failed.length > 0) {
    console.error(`Aer run matrix completed with ${failed.length} problematic scenario(s).`);
    process.exitCode = 1;
    return;
  }

  console.log(`Aer run matrix completed successfully. Summary written to ${outputPath}`);
}

try {
  await main();
} catch (error) {
  console.error(error);
  process.exitCode = 1;
}
