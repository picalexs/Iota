import { fetchMolecules } from "@/api/molecules";
import type { MoleculeResponse, UUID } from "@/types/run";
import { getBenchmarkMoleculeBlocker, moleculeToPreset } from "./benchmark-utils";

export const RANDOM_LIBRARY_TARGET = 6;
const RANDOM_LIBRARY_PAGE_SIZE = 50;
const RANDOM_LIBRARY_ATTEMPTS = 4;

function randomInt(maxExclusive: number): number {
  if (maxExclusive <= 1) return 0;

  const values = new Uint32Array(1);
  const limit = Math.floor(2 ** 32 / maxExclusive) * maxExclusive;
  let value = 0;
  do {
    globalThis.crypto.getRandomValues(values);
    value = values[0] ?? 0;
  } while (value >= limit);

  return value % maxExclusive;
}

function pickRandomMolecules(
  molecules: MoleculeResponse[],
  targetCount: number,
): MoleculeResponse[] {
  const shuffled = [...molecules];
  for (let index = shuffled.length - 1; index > 0; index -= 1) {
    const swapIndex = randomInt(index + 1);
    const current = shuffled[index];
    const replacement = shuffled[swapIndex];
    if (current === undefined || replacement === undefined) {
      continue;
    }
    shuffled[index] = replacement;
    shuffled[swapIndex] = current;
  }
  return shuffled.slice(0, targetCount);
}

function addEligibleLibraryMolecules(
  eligible: Map<UUID, MoleculeResponse>,
  molecules: MoleculeResponse[],
): void {
  for (const molecule of molecules) {
    const preset = moleculeToPreset(molecule);
    if (getBenchmarkMoleculeBlocker(preset) === null) {
      eligible.set(molecule.id, molecule);
    }
  }
}

export async function loadEligibleLibraryMolecules(): Promise<MoleculeResponse[]> {
  const firstPage = await fetchMolecules({ limit: 1, offset: 0 });
  const total = Math.max(firstPage.total, firstPage.items.length);
  const eligible = new Map<UUID, MoleculeResponse>();

  addEligibleLibraryMolecules(eligible, firstPage.items);

  for (
    let attempt = 0;
    attempt < RANDOM_LIBRARY_ATTEMPTS && eligible.size < RANDOM_LIBRARY_TARGET;
    attempt += 1
  ) {
    const maxOffset = Math.max(0, total - RANDOM_LIBRARY_PAGE_SIZE);
    const offset = maxOffset > 0 ? randomInt(maxOffset + 1) : 0;
    const response = await fetchMolecules({
      limit: RANDOM_LIBRARY_PAGE_SIZE,
      offset,
    });

    addEligibleLibraryMolecules(eligible, response.items);
  }

  return pickRandomMolecules([...eligible.values()], RANDOM_LIBRARY_TARGET);
}

export function buildSelectedMoleculeKeysWithRandomLibrary({
  selectedMolecules,
  randomLibraryMoleculeIds,
  picked,
}: Readonly<{
  selectedMolecules: ReadonlySet<string>;
  randomLibraryMoleculeIds: readonly UUID[];
  picked: readonly MoleculeResponse[];
}>): string[] {
  return Array.from(
    new Set([
      ...Array.from(selectedMolecules).filter(
        (key) => !randomLibraryMoleculeIds.some((id) => key === `custom:${id}`),
      ),
      ...picked.map((molecule) => `custom:${molecule.id}`),
    ]),
  );
}
