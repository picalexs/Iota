import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { findMissingAssetReferences } from "./check-build-assets.mjs";

function createFixture() {
  const distDir = fs.mkdtempSync(path.join(os.tmpdir(), "quantum-simulation-studio-build-assets-"));
  const assetsDir = path.join(distDir, "assets");
  fs.mkdirSync(assetsDir, { recursive: true });
  return { distDir, assetsDir };
}

test("accepts relative, root-relative, data, and external assets", () => {
  const { distDir, assetsDir } = createFixture();
  try {
    fs.writeFileSync(path.join(assetsDir, "font.woff2"), "font");
    fs.writeFileSync(
      path.join(assetsDir, "index.css"),
      [
        'a { background: url("./font.woff2"); }',
        'b { background: url(/assets/font.woff2); }',
        'c { background: url(data:image/svg+xml;base64,abc); }',
        'd { background: url(https://example.com/font.woff2); }',
      ].join("\n"),
    );

    assert.deepEqual(findMissingAssetReferences(distDir), []);
  } finally {
    fs.rmSync(distDir, { recursive: true, force: true });
  }
});

test("reports missing relative assets with their CSS file", () => {
  const { distDir, assetsDir } = createFixture();
  try {
    fs.writeFileSync(path.join(assetsDir, "index.css"), "a { background: url(missing.woff2); }");

    const missing = findMissingAssetReferences(distDir);
    assert.equal(missing.length, 1);
    assert.equal(missing[0].file, "assets/index.css");
    assert.equal(missing[0].reference, "missing.woff2");
  } finally {
    fs.rmSync(distDir, { recursive: true, force: true });
  }
});
