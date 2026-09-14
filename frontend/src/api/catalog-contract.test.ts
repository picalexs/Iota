import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import { parseRunConfigMetadataResponse } from "./runs";

interface SharedCatalogFixture {
  algorithms: string[];
  ansatzes: unknown[];
  backend_targets: string[];
  capabilities: Record<string, Record<string, boolean>>;
  catalog_version: string;
  defaults: Record<string, unknown>;
  easy_goals: string[];
  easy_goal_presets: unknown[];
  limits: Record<string, Record<string, number>>;
  optimizers: unknown[];
}

const sharedCatalogFixture = JSON.parse(
  readFileSync(
    path.resolve(process.cwd(), "..", "shared", "contracts", "identifier-fixtures.json"),
    "utf8",
  ),
) as SharedCatalogFixture;

describe("shared catalog fixture", () => {
  it("passes through the generated metadata response validator", () => {
    const metadata = parseRunConfigMetadataResponse(sharedCatalogFixture);

    expect(metadata.catalog_version).toBe(sharedCatalogFixture.catalog_version);
    expect(metadata.algorithms).toEqual(sharedCatalogFixture.algorithms);
    expect(metadata.backend_targets).toEqual(sharedCatalogFixture.backend_targets);
    expect(metadata.easy_goals).toEqual(sharedCatalogFixture.easy_goals);
    expect(metadata.easy_goal_presets).toEqual(sharedCatalogFixture.easy_goal_presets);
    expect(metadata.ansatzes).toEqual(sharedCatalogFixture.ansatzes);
    expect(metadata.optimizers).toEqual(sharedCatalogFixture.optimizers);
    expect(metadata.limits).toEqual(sharedCatalogFixture.limits);
    expect(metadata.defaults).toEqual(sharedCatalogFixture.defaults);
    expect(metadata.capabilities).toEqual(sharedCatalogFixture.capabilities);
  });
});
