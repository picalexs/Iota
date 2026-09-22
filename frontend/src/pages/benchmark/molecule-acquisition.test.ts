import { beforeEach, describe, expect, it, vi } from "vitest";

import type { MoleculePreset } from "@/lib/benchmark-presets";
import { createMolecule, fetchMolecules, getMolecule } from "@/api/molecules";
import {
  acquireMolecule,
  clearMoleculeAcquisitionCache,
  MoleculeAcquisitionError,
} from "./molecule-acquisition";

vi.mock("@/api/molecules", () => ({
  createMolecule: vi.fn(),
  fetchMolecules: vi.fn(),
  getMolecule: vi.fn(),
  updateMolecule: vi.fn(),
}));

const preset: MoleculePreset = {
  key: "custom:water",
  name: "Water",
  formula: "H2O",
  description: "Custom water",
  atoms: [
    { symbol: "O", x: 0, y: 0, z: 0 },
    { symbol: "H", x: 0, y: 0.757, z: 0.586 },
    { symbol: "H", x: 0, y: -0.757, z: 0.586 },
  ],
  charge: 0,
  multiplicity: 1,
  active_space: { n_electrons: 2, n_orbitals: 2 },
  basis: "sto-3g",
  references: { hf: 0, fci: null, source: "unknown" },
};

describe("molecule acquisition adapter", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    clearMoleculeAcquisitionCache();
  });

  it("reports a valid custom molecule cache hit", async () => {
    localStorage.setItem("benchmark_molecule_ids", JSON.stringify({ [preset.key]: "cached-id" }));
    vi.mocked(getMolecule).mockResolvedValue({ id: "cached-id" } as never);

    await expect(acquireMolecule(preset)).resolves.toEqual({
      kind: "cached",
      moleculeId: "cached-id",
      cacheState: "hit",
      attempts: [],
    });
  });

  it("reports an existing server molecule after a missing cache", async () => {
    vi.mocked(fetchMolecules).mockResolvedValue({
      items: [
        {
          id: "existing-id",
          name: "Water",
          active_space: preset.active_space,
        },
      ],
      total: 1,
    } as never);

    await expect(acquireMolecule(preset)).resolves.toMatchObject({
      kind: "existing",
      moleculeId: "existing-id",
      cacheState: "missing",
    });
  });

  it("reports a created molecule and keeps the acquisition attempts", async () => {
    vi.mocked(fetchMolecules).mockResolvedValue({ items: [], total: 0 } as never);
    vi.mocked(createMolecule).mockResolvedValue({ id: "created-id" } as never);

    const result = await acquireMolecule(preset);

    expect(result).toMatchObject({
      kind: "created",
      moleculeId: "created-id",
      cacheState: "missing",
    });
    expect(result.attempts.map((attempt) => attempt.kind)).toEqual([
      "cache_miss",
      "server_not_found",
      "server_not_found",
    ]);
  });

  it("classifies transport failure after all acquisition fallbacks fail", async () => {
    vi.mocked(fetchMolecules).mockResolvedValue({ items: [], total: 0 } as never);
    vi.mocked(createMolecule).mockRejectedValue(
      Object.assign(new Error("API unavailable"), {
        code: "NETWORK_ERROR",
        name: "ApiError",
        status: 503,
      }),
    );

    await expect(acquireMolecule(preset)).rejects.toMatchObject({
      name: "MoleculeAcquisitionError",
      kind: "transport_failure",
      presetKey: preset.key,
    });
  });

  it("classifies invalid list or create responses separately from transport failures", async () => {
    vi.mocked(fetchMolecules).mockResolvedValue({ items: "invalid" } as never);
    vi.mocked(createMolecule).mockResolvedValue({} as never);

    const error = await acquireMolecule(preset).catch((value: unknown) => value);

    expect(error).toBeInstanceOf(MoleculeAcquisitionError);
    expect(error).toMatchObject({ kind: "invalid_response" });
    expect((error as MoleculeAcquisitionError).attempts[0]?.kind).toBe("cache_miss");
    expect(
      (error as MoleculeAcquisitionError).attempts.some(
        (attempt) => attempt.kind === "invalid_response",
      ),
    ).toBe(true);
  });

  it("shares one acquisition for concurrent requests for the same preset", async () => {
    vi.mocked(fetchMolecules).mockResolvedValue({ items: [], total: 0 } as never);
    vi.mocked(createMolecule).mockResolvedValue({ id: "created-id" } as never);

    const results = await Promise.all([acquireMolecule(preset), acquireMolecule(preset)]);

    expect(results[0]).toEqual(results[1]);
    expect(fetchMolecules).toHaveBeenCalledTimes(2);
    expect(createMolecule).toHaveBeenCalledTimes(1);
  });

  it("reuses a completed acquisition without repeating service calls", async () => {
    vi.mocked(fetchMolecules).mockResolvedValue({ items: [], total: 0 } as never);
    vi.mocked(createMolecule).mockResolvedValue({ id: "created-id" } as never);

    await acquireMolecule(preset);
    await acquireMolecule(preset);

    expect(fetchMolecules).toHaveBeenCalledTimes(2);
    expect(createMolecule).toHaveBeenCalledTimes(1);
  });

  it("does not retain a failed acquisition promise", async () => {
    vi.mocked(fetchMolecules).mockResolvedValue({ items: [], total: 0 } as never);
    vi.mocked(createMolecule)
      .mockRejectedValueOnce(
        Object.assign(new Error("API unavailable"), {
          code: "NETWORK_ERROR",
          name: "ApiError",
          status: 503,
        }),
      )
      .mockResolvedValueOnce({ id: "created-id" } as never);

    await expect(acquireMolecule(preset)).rejects.toBeInstanceOf(MoleculeAcquisitionError);
    await expect(acquireMolecule(preset)).resolves.toMatchObject({
      kind: "created",
      moleculeId: "created-id",
    });

    expect(createMolecule).toHaveBeenCalledTimes(2);
  });
});
