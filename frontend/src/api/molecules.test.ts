import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  createMolecule,
  fetchMolecules,
  parseBasisSetListResponse,
  parseMoleculeImportPreviewResponse,
  parseMoleculeListResponse,
  parseMoleculeResponse,
  parseMoleculeSummaryListResponse,
  parsePubChemSearchResponse,
  previewMoleculeFromXyz,
} from "./molecules";

function mockResponse(body: unknown, status = 200): Response {
  return {
    ok: status < 400,
    status,
    json: vi.fn().mockResolvedValue(body),
  } as unknown as Response;
}

const moleculeResponse = {
  id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  name: "H2",
  atoms: [
    { symbol: "H", x: 0, y: 0, z: 0 },
    { symbol: "H", x: 0, y: 0, z: 0.74 },
  ],
  charge: 0,
  multiplicity: 1,
  active_space: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  visualizable: true,
};

describe("molecule API transport adapters", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  it("rejects malformed generated molecule envelopes", () => {
    expect(() => parseMoleculeResponse({ ...moleculeResponse, atoms: [{ symbol: "H" }] })).toThrow(
      "Invalid molecule response",
    );
    expect(() => parseMoleculeListResponse({ items: [moleculeResponse] })).toThrow(
      "Invalid molecule list response",
    );
    expect(() =>
      parseMoleculeSummaryListResponse({
        items: [{ id: moleculeResponse.id, name: moleculeResponse.name }],
        total: 1,
      }),
    ).toThrow("Invalid molecule summary list response");
    expect(() =>
      parseMoleculeImportPreviewResponse({
        source: "xyz",
        commit_action: "create",
        name: "H2",
      }),
    ).toThrow("Invalid molecule import preview response");
    expect(() => parseBasisSetListResponse({ basis_sets: [] })).toThrow(
      "Invalid basis-set list response",
    );
    expect(() => parsePubChemSearchResponse({ results: [{ name: "H2" }] })).toThrow(
      "Invalid PubChem search response",
    );
  });

  it("normalizes optional capability fields and rejects unknown algorithms", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      mockResponse({
        items: [
          {
            ...moleculeResponse,
            eligibility: {
              selectable: true,
              label: "Ready",
            },
            runnable_algorithms: ["vqe", "future_algorithm"],
          },
        ],
        total: 1,
      }),
    );

    const result = await fetchMolecules();

    expect(result.items[0]).toMatchObject({
      id: moleculeResponse.id,
      active_space: null,
      eligibility: {
        selectable: true,
        label: "Ready",
        capability_labels: [],
      },
      runnable_algorithms: ["vqe"],
      blocking_reasons: [],
      warnings: [],
    });
  });

  it("sends server-defaulted molecule fields through the generated request shape", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(mockResponse(moleculeResponse));

    await createMolecule({
      name: "H2",
      atoms: moleculeResponse.atoms,
    });

    const [, options] = vi.mocked(fetch).mock.calls[0] ?? [];
    expect(JSON.parse(String(options?.body))).toEqual({
      name: "H2",
      atoms: moleculeResponse.atoms,
      charge: 0,
      multiplicity: 1,
    });
  });

  it("normalizes XYZ preview defaults before sending the request", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      mockResponse({
        source: "xyz",
        name: "H2",
        atoms: moleculeResponse.atoms,
        charge: 0,
        multiplicity: 1,
        active_space: null,
        atom_count: 2,
        formula: "H2",
        eligibility: { selectable: true, label: "Ready" },
        commit_action: "create",
        visualizable: true,
      }),
    );

    await previewMoleculeFromXyz({ xyz: "H 0 0 0\nH 0 0 0.74" });

    const [, options] = vi.mocked(fetch).mock.calls[0] ?? [];
    expect(JSON.parse(String(options?.body))).toEqual({
      xyz: "H 0 0 0\nH 0 0 0.74",
      name: null,
      charge: 0,
      multiplicity: 1,
      active_space: null,
      derive_active_space: true,
    });
  });
});
