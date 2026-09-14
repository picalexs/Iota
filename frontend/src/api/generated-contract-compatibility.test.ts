import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  ApiJsonResponse,
  ApiSchema,
  GetRunConfigMetadataResponse,
  RunConfigMetadataResponse,
} from "@/types/api";
import { fetchRunConfigMetadata } from "./runs";
import { getFetchCall, mockJsonResponse } from "./test-helpers";

type Equal<Left, Right> =
  (<Type>() => Type extends Left ? 1 : 2) extends <Type>() => Type extends Right ? 1 : 2
    ? true
    : false;

type Assert<Condition extends true> = Condition;
type Extends<Source, Target> = Source extends Target ? true : false;

type MetadataResponseFromOpenApi = ApiJsonResponse<
  "get_config_metadata_api_runs_config_metadata_get",
  200
>;

type MetadataContracts = [
  Assert<Equal<MetadataResponseFromOpenApi, ApiSchema<"RunConfigMetadataResponse">>>,
  Assert<Extends<RunConfigMetadataResponse, MetadataResponseFromOpenApi>>,
  Assert<Extends<GetRunConfigMetadataResponse, RunConfigMetadataResponse>>,
  Assert<Extends<Awaited<ReturnType<typeof fetchRunConfigMetadata>>, GetRunConfigMetadataResponse>>,
];

const metadataContracts: MetadataContracts = [true, true, true, true];

const metadataResponse = {
  algorithms: ["vqe", "qse"],
  ansatzes: [
    {
      id: "hardware_efficient",
      label: "Hardware efficient",
      aliases: ["hea"],
      description: "Layered hardware-efficient ansatz",
      metadata: { layers: 2 },
      supported_algorithms: ["vqe"],
    },
  ],
  backend_targets: ["statevector", "aer_simulator"],
  capabilities: { vqe: { statevector: true, aer_simulator: true } },
  catalog_version: "2026-01",
  defaults: { mode: "easy", backend_target: "statevector" },
  easy_goals: ["balanced"],
  easy_goal_presets: [{ goal: "balanced", label: "1.6 mHa", chemical_accuracy_target_ha: 1.6e-3 }],
  limits: { vqe: { max_qubits: 16 } },
  optimizers: [
    {
      id: "spsa",
      label: "SPSA",
      aliases: [],
      description: null,
      metadata: { maxiter: 100 },
      supported_algorithms: ["vqe"],
    },
  ],
} satisfies MetadataResponseFromOpenApi;

describe("generated metadata contract compatibility", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("keeps the generated response alias aligned with the metadata adapter", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(mockJsonResponse(metadataResponse));

    const result = await fetchRunConfigMetadata();
    const { url, options } = getFetchCall();

    expect(metadataContracts.every(Boolean)).toBe(true);
    expect(url).toBe("/api/runs/config-metadata");
    expect(options.method).toBe("GET");
    expect(options.body).toBeUndefined();
    expect(result).toEqual(metadataResponse);
  });
});
