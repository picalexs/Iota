import { createMolecule, fetchMolecules, getMolecule, updateMolecule } from "@/api/molecules";
import { isApiErrorLike } from "@/lib/error-handler";
import type { MoleculePreset } from "@/lib/benchmark-presets";
import type { MoleculeResponse, UUID } from "@/types/run";
import { loadMoleculeCache, saveMoleculeCache } from "./benchmark-storage";

export type MoleculeAcquisitionResultKind = "cached" | "existing" | "created";
export type MoleculeAcquisitionAttemptKind =
  | "cache_miss"
  | "server_not_found"
  | "transport_failure"
  | "invalid_response";
export type MoleculeAcquisitionFailureKind = Exclude<MoleculeAcquisitionAttemptKind, "cache_miss">;
export type MoleculeCacheState = "hit" | "missing" | "stale";

export interface MoleculeAcquisitionAttempt {
  kind: MoleculeAcquisitionAttemptKind;
  message?: string;
}

export interface MoleculeAcquisitionResult {
  kind: MoleculeAcquisitionResultKind;
  moleculeId: UUID;
  cacheState: MoleculeCacheState;
  attempts: readonly MoleculeAcquisitionAttempt[];
}

export class MoleculeAcquisitionError extends Error {
  readonly kind: MoleculeAcquisitionFailureKind;
  readonly presetKey: string;
  readonly attempts: readonly MoleculeAcquisitionAttempt[];

  constructor(
    preset: MoleculePreset,
    kind: MoleculeAcquisitionFailureKind,
    attempts: readonly MoleculeAcquisitionAttempt[],
    cause?: unknown,
  ) {
    super(buildFailureMessage(preset, kind), { cause });
    this.name = "MoleculeAcquisitionError";
    this.kind = kind;
    this.presetKey = preset.key;
    this.attempts = attempts;
  }
}

function buildFailureMessage(preset: MoleculePreset, kind: MoleculeAcquisitionFailureKind): string {
  switch (kind) {
    case "server_not_found":
      return `The molecule service could not find or create “${preset.name}”.`;
    case "invalid_response":
      return `The molecule service returned invalid data while preparing “${preset.name}”.`;
    case "transport_failure":
      return `The molecule service was unavailable while preparing “${preset.name}”. Refresh and try again.`;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isMoleculeId(value: unknown): value is UUID {
  return typeof value === "string" && value.trim().length > 0;
}

function readMoleculeId(value: unknown, operation: string): UUID {
  if (isRecord(value) && isMoleculeId(value.id)) {
    return value.id;
  }

  throw Object.assign(new Error(`${operation} returned an invalid molecule response.`), {
    code: "INVALID_RESPONSE",
    name: "ApiError",
    status: 200,
  });
}

function readMoleculeList(value: unknown, operation: string): MoleculeResponse[] {
  if (isRecord(value) && Array.isArray(value.items)) {
    return value.items as MoleculeResponse[];
  }

  throw Object.assign(new Error(`${operation} returned an invalid molecule list response.`), {
    code: "INVALID_RESPONSE",
    name: "ApiError",
    status: 200,
  });
}

function classifyFailure(error: unknown): MoleculeAcquisitionFailureKind {
  if (isApiErrorLike(error)) {
    if (error.code === "INVALID_RESPONSE") return "invalid_response";
    if (error.status === 404) return "server_not_found";
    return "transport_failure";
  }
  if (error instanceof Error && /not found/i.test(error.message)) {
    return "server_not_found";
  }
  return "transport_failure";
}

function recordFailure(
  attempts: MoleculeAcquisitionAttempt[],
  error: unknown,
): MoleculeAcquisitionFailureKind {
  const kind = classifyFailure(error);
  const message = error instanceof Error ? error.message : undefined;
  attempts.push(message ? { kind, message } : { kind });
  return kind;
}

function result(
  kind: MoleculeAcquisitionResultKind,
  moleculeId: UUID,
  cacheState: MoleculeCacheState,
  attempts: MoleculeAcquisitionAttempt[],
): MoleculeAcquisitionResult {
  return { kind, moleculeId, cacheState, attempts: [...attempts] };
}

function sameActiveSpace(
  left: MoleculeResponse["active_space"] | null | undefined,
  right: MoleculePreset["active_space"] | null | undefined,
): boolean {
  if (left == null || right == null) {
    return left == null && right == null;
  }
  return left.n_electrons === right.n_electrons && left.n_orbitals === right.n_orbitals;
}

function isCustomBenchmarkPreset(preset: MoleculePreset): boolean {
  return preset.key.startsWith("custom:");
}

async function refreshBuiltInBenchmarkMolecule(
  preset: MoleculePreset,
  molecule: MoleculeResponse,
): Promise<UUID> {
  if (
    preset.key.startsWith("custom:") ||
    sameActiveSpace(molecule.active_space, preset.active_space)
  ) {
    return readMoleculeId(molecule, "Cached molecule");
  }

  const updated = await updateMolecule(molecule.id, { active_space: preset.active_space });
  return readMoleculeId(updated, "Molecule update");
}

async function resolveCachedCustomMolecule(
  preset: MoleculePreset,
  cache: Record<string, UUID>,
  attempts: MoleculeAcquisitionAttempt[],
): Promise<{ moleculeId: UUID; cacheState: MoleculeCacheState } | null> {
  const cachedId = cache[preset.key];
  if (!cachedId) {
    attempts.push({ kind: "cache_miss" });
    return null;
  }

  try {
    const cached = await getMolecule(cachedId);
    return { moleculeId: readMoleculeId(cached, "Cached molecule"), cacheState: "hit" };
  } catch (error) {
    recordFailure(attempts, error);
    delete cache[preset.key];
    saveMoleculeCache(cache);
    return null;
  }
}

async function resolveCachedBuiltInMolecule(
  preset: MoleculePreset,
  cache: Record<string, UUID>,
  attempts: MoleculeAcquisitionAttempt[],
): Promise<{ moleculeId: UUID; cacheState: MoleculeCacheState } | null> {
  const cachedId = cache[preset.key];
  if (!cachedId) {
    attempts.push({ kind: "cache_miss" });
    return null;
  }

  try {
    const response = readMoleculeList(
      await fetchMolecules({ q: preset.name, limit: 5 }),
      "Cached molecule lookup",
    );
    const match = response.find((molecule) => molecule.id === cachedId);
    if (!match) {
      attempts.push({ kind: "server_not_found" });
      return null;
    }

    return {
      moleculeId: await refreshBuiltInBenchmarkMolecule(preset, match),
      cacheState: "hit",
    };
  } catch (error) {
    recordFailure(attempts, error);
    return null;
  }
}

async function findCustomBenchmarkMolecule(
  preset: MoleculePreset,
  attempts: MoleculeAcquisitionAttempt[],
): Promise<UUID | null> {
  try {
    const response = readMoleculeList(
      await fetchMolecules({ q: preset.name, limit: 10 }),
      "Custom molecule lookup",
    );
    const presetName = preset.name.toLowerCase();
    const presetFormula = preset.formula.toLowerCase();
    const match = response.find(
      (molecule) =>
        molecule.name.toLowerCase() === presetName ||
        (molecule.iupac_name ?? "").toLowerCase() === presetFormula,
    );
    if (!match) {
      attempts.push({ kind: "server_not_found" });
      return null;
    }
    return readMoleculeId(match, "Existing molecule lookup");
  } catch (error) {
    recordFailure(attempts, error);
    return null;
  }
}

async function findBuiltInBenchmarkMolecule(
  preset: MoleculePreset,
  attempts: MoleculeAcquisitionAttempt[],
): Promise<MoleculeResponse | null> {
  try {
    const response = readMoleculeList(
      await fetchMolecules({ q: preset.name, limit: 10 }),
      "Built-in molecule lookup",
    );
    const presetName = preset.name.toLowerCase();
    const match = response.find((molecule) => molecule.name.toLowerCase() === presetName) ?? null;
    if (!match) {
      attempts.push({ kind: "server_not_found" });
    }
    return match;
  } catch (error) {
    recordFailure(attempts, error);
    return null;
  }
}

async function createBenchmarkMolecule(preset: MoleculePreset): Promise<UUID> {
  const created = await createMolecule({
    name: preset.name,
    atoms: preset.atoms,
    charge: preset.charge,
    multiplicity: preset.multiplicity,
    active_space: preset.active_space,
  });
  return readMoleculeId(created, "Molecule creation");
}

export async function acquireMolecule(preset: MoleculePreset): Promise<MoleculeAcquisitionResult> {
  const cache = loadMoleculeCache();
  const attempts: MoleculeAcquisitionAttempt[] = [];
  const cached = isCustomBenchmarkPreset(preset)
    ? await resolveCachedCustomMolecule(preset, cache, attempts)
    : await resolveCachedBuiltInMolecule(preset, cache, attempts);
  if (cached) {
    return result("cached", cached.moleculeId, cached.cacheState, attempts);
  }

  const cacheState: MoleculeCacheState = cache[preset.key] ? "stale" : "missing";
  if (isCustomBenchmarkPreset(preset)) {
    const existingCustomId = await findCustomBenchmarkMolecule(preset, attempts);
    if (existingCustomId) {
      cache[preset.key] = existingCustomId;
      saveMoleculeCache(cache);
      return result("existing", existingCustomId, cacheState, attempts);
    }
  }

  const existing = await findBuiltInBenchmarkMolecule(preset, attempts);
  if (existing) {
    try {
      const existingId = await refreshBuiltInBenchmarkMolecule(preset, existing);
      cache[preset.key] = existingId;
      saveMoleculeCache(cache);
      return result("existing", existingId, cacheState, attempts);
    } catch (error) {
      const kind = recordFailure(attempts, error);
      throw new MoleculeAcquisitionError(preset, kind, attempts, error);
    }
  }

  try {
    const createdId = await createBenchmarkMolecule(preset);
    cache[preset.key] = createdId;
    saveMoleculeCache(cache);
    return result("created", createdId, cacheState, attempts);
  } catch (error) {
    const kind = recordFailure(attempts, error);
    throw new MoleculeAcquisitionError(preset, kind, attempts, error);
  }
}

/** Compatibility helper for callers that only need the database identifier. */
export async function acquireMoleculeId(preset: MoleculePreset): Promise<UUID> {
  const acquisition = await acquireMolecule(preset);
  return acquisition.moleculeId;
}
