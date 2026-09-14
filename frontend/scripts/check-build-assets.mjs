#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_DIST_DIR = path.resolve(SCRIPT_DIR, "../dist");
const URL_PATTERN = /url\(\s*(?:"([^"]+)"|'([^']+)'|([^)]*?))\s*\)/g;

function walkFiles(directory) {
  if (!fs.existsSync(directory)) {
    return [];
  }

  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const entryPath = path.join(directory, entry.name);
    return entry.isDirectory() ? walkFiles(entryPath) : [entryPath];
  });
}

function isExternalAsset(value) {
  return (
    value.length === 0 ||
    value.startsWith("data:") ||
    value.startsWith("http://") ||
    value.startsWith("https://") ||
    value.startsWith("//") ||
    value.startsWith("#")
  );
}

function resolveAssetReference(value, cssFile, distDir) {
  if (value.startsWith("/")) {
    return path.join(distDir, value.slice(1));
  }

  return path.resolve(path.dirname(cssFile), value);
}

/**
 * Return CSS asset references that do not resolve inside a production build.
 *
 * @param {string} distDir
 * @returns {Array<{file: string, reference: string, resolvedPath: string}>}
 */
export function findMissingAssetReferences(distDir = DEFAULT_DIST_DIR) {
  const cssFiles = walkFiles(distDir).filter((file) => file.endsWith(".css"));
  const missing = [];

  for (const cssFile of cssFiles) {
    const css = fs.readFileSync(cssFile, "utf8");
    for (const match of css.matchAll(URL_PATTERN)) {
      const value = (match[1] ?? match[2] ?? match[3] ?? "").trim();
      if (isExternalAsset(value)) {
        continue;
      }

      const resolvedPath = resolveAssetReference(value, cssFile, distDir);
      if (!fs.existsSync(resolvedPath)) {
        missing.push({
          file: path.relative(distDir, cssFile),
          reference: value,
          resolvedPath,
        });
      }
    }
  }

  return missing;
}

if (path.resolve(process.argv[1] ?? "") === path.resolve(fileURLToPath(import.meta.url))) {
  const missing = findMissingAssetReferences();
  if (missing.length > 0) {
    console.error("Missing production asset references:");
    for (const asset of missing) {
      console.error(`  ${asset.file}: ${asset.reference}`);
    }
    process.exitCode = 1;
  } else {
    console.log("Production asset references resolve");
  }
}
