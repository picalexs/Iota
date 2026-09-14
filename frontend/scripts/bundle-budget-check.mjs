#!/usr/bin/env node

/**
 * Bundle Budget Check
 *
 * Validates the production build against MVP-scale bundle size budgets.
 * Reads dist/ output and checks:
 * - Total JS bundle size
 * - Largest chunk size
 * - CSS bundle size
 *
 * Exits with code 1 if budgets are exceeded.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const distDir = path.join(__dirname, "..", "dist");

// Approved bundle budgets (in KB).
// Baseline measured on 2026-09-07 with the required 3Dmol molecular viewer.
// appJs is the sum of all non-viewer application chunks, including lazy routes.
// Budgets keep approximately 10% headroom over the measured core JS and CSS.
// 3Dmol remains a separate third-party budget and warning policy.
const BUNDLE_BUDGETS = {
  appJs: 2200, // All non-viewer application chunks
  viewerJs: 1500, // The 3Dmol chunk itself; keep this within the established baseline
  mainChunk: 750, // Largest non-viewer chunk in the core app
  totalCss: 180, // Total CSS
};

/**
 * @typedef {Object} BundleResult
 * @property {string} file
 * @property {number} size
 * @property {number} sizeKb
 * @property {string} type - "js" | "css" | "other"
 */

/**
 * @returns {BundleResult[]}
 */
function getBundleFiles() {
  if (fs.existsSync(distDir) === false) {
    console.error(`dist/ directory not found at ${distDir}`);
    console.log("   Run 'npm run build' first.");
    process.exit(1);
  }

  const files = fs.readdirSync(distDir);
  const assets = fs.readdirSync(path.join(distDir, "assets")) || [];

  /** @type {BundleResult[]} */
  const results = [];

  // Check root JS files
  files
    .filter((f) => f.endsWith(".js"))
    .forEach((file) => {
      const filePath = path.join(distDir, file);
      const size = fs.statSync(filePath).size;
      results.push({
        file,
        size,
        sizeKb: size / 1024,
        type: "js",
      });
    });

  // Check assets directory
  assets.forEach((file) => {
    const filePath = path.join(distDir, "assets", file);
    const size = fs.statSync(filePath).size;
    const type = getBundleFileType(file);
    results.push({
      file: path.join("assets", file),
      size,
      sizeKb: size / 1024,
      type,
    });
  });

  return results;
}

function getBundleFileType(file) {
  if (file.endsWith(".js")) {
    return "js";
  }

  if (file.endsWith(".css")) {
    return "css";
  }

  return "other";
}

/**
 * @param {BundleResult[]} files
 */
function analyzeBundle(files) {
  const jsFiles = files.filter((f) => f.type === "js");
  const cssFiles = files.filter((f) => f.type === "css");
  const viewerJsFiles = jsFiles.filter((f) => f.file.includes("3Dmol"));
  const coreJsFiles = jsFiles.filter((f) => !f.file.includes("3Dmol"));

  const totalJs = jsFiles.reduce((sum, f) => sum + f.sizeKb, 0);
  const viewerJs = viewerJsFiles.reduce((sum, f) => sum + f.sizeKb, 0);
  const appJs = coreJsFiles.reduce((sum, f) => sum + f.sizeKb, 0);
  const totalCss = cssFiles.reduce((sum, f) => sum + f.sizeKb, 0);
  const largestCoreChunk = Math.max(...coreJsFiles.map((f) => f.sizeKb), 0);

  console.log("\nBundle Size Analysis (MVP Budgets)\n");
  console.log("JS Files:");
  jsFiles.forEach((f) => {
    console.log(`  ${f.file.padEnd(40)} ${f.sizeKb.toFixed(1).padStart(7)}KB`);
  });

  console.log("\nCSS Files:");
  cssFiles.forEach((f) => {
    console.log(`  ${f.file.padEnd(40)} ${f.sizeKb.toFixed(1).padStart(7)}KB`);
  });

  console.log("\nSummary:");
  console.log(`  Total JS:      ${totalJs.toFixed(1).padStart(7)}KB (informational)`);
  console.log(
    `  Core JS:       ${appJs.toFixed(1).padStart(7)}KB (budget: ${BUNDLE_BUDGETS.appJs}KB)`,
  );
  console.log(
    `  3Dmol Chunk:   ${viewerJs.toFixed(1).padStart(7)}KB (budget: ${BUNDLE_BUDGETS.viewerJs}KB)`,
  );
  console.log(
    `  Largest Core:  ${largestCoreChunk.toFixed(1).padStart(7)}KB (budget: ${BUNDLE_BUDGETS.mainChunk}KB)`,
  );
  console.log(
    `  Total CSS:     ${totalCss.toFixed(1).padStart(7)}KB (budget: ${BUNDLE_BUDGETS.totalCss}KB)`,
  );

  let passed = true;
  const failures = [];

  if (appJs > BUNDLE_BUDGETS.appJs) {
    failures.push(`Core JS (${appJs.toFixed(1)}KB) exceeds budget (${BUNDLE_BUDGETS.appJs}KB)`);
    passed = false;
  }

  if (viewerJs > BUNDLE_BUDGETS.viewerJs) {
    failures.push(
      `3Dmol chunk (${viewerJs.toFixed(1)}KB) exceeds budget (${BUNDLE_BUDGETS.viewerJs}KB)`,
    );
    passed = false;
  }

  if (largestCoreChunk > BUNDLE_BUDGETS.mainChunk) {
    failures.push(
      `Largest core chunk (${largestCoreChunk.toFixed(1)}KB) exceeds budget (${BUNDLE_BUDGETS.mainChunk}KB)`,
    );
    passed = false;
  }

  if (totalCss > BUNDLE_BUDGETS.totalCss) {
    failures.push(
      `Total CSS (${totalCss.toFixed(1)}KB) exceeds budget (${BUNDLE_BUDGETS.totalCss}KB)`,
    );
    passed = false;
  }

  console.log();
  if (passed) {
    console.log("All bundles within budget!");
    process.exit(0);
  } else {
    console.log("Budget exceeded:");
    failures.forEach((f) => console.log(`   - ${f}`));
    process.exit(1);
  }
}

// Main
const files = getBundleFiles();
analyzeBundle(files);
