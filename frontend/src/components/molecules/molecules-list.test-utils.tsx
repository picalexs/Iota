import { render, type RenderResult } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { vi } from "vitest";

import { MoleculesList } from "./molecules-list";
import { createQueryClient } from "@/state/query-client";
import type {
  MoleculeImportPreviewResponse,
  MoleculeResponse,
  MoleculeSummaryResponse,
} from "@/types/run";

const moleculesListMocks = vi.hoisted(() => ({
  api: {
    deleteMolecule: vi.fn(),
    importMoleculeFromPubChem: vi.fn(),
    importMoleculeFromXyz: vi.fn(),
    previewMoleculeFromPubChem: vi.fn(),
    previewMoleculeFromXyz: vi.fn(),
    searchPubChem: vi.fn(),
    ApiError: class ApiError extends Error {
      constructor(
        public code: string,
        message: string,
        public status: number,
        public field?: string,
      ) {
        super(message);
        this.name = "ApiError";
      }
    },
  },
  hooks: {
    useFetchMoleculeSummaries: vi.fn(),
    useFetchMolecules: vi.fn(),
    useInvalidateMoleculesList: vi.fn(() => vi.fn()),
    useListRuns: vi.fn(),
    useInvalidateRunsList: vi.fn(),
    useInvalidateRun: vi.fn(),
  },
  navigate: vi.fn(),
  useSearch: vi.fn(() => ({ q: "", page: 1 })),
}));

vi.mock("@/api/molecules", () => ({
  ...moleculesListMocks.api,
}));

vi.mock("@/hooks", () => ({
  ...moleculesListMocks.hooks,
}));

export const mockNavigate = moleculesListMocks.navigate;
vi.mock("@tanstack/react-router", () => ({
  Link: ({
    children,
    to,
    ...rest
  }: {
    readonly children: ReactNode;
    readonly to?: string;
    readonly [key: string]: unknown;
  }) => (
    <a href={typeof to === "string" ? to : "/"} {...rest}>
      {children}
    </a>
  ),
  useNavigate: () => moleculesListMocks.navigate,
  useSearch: moleculesListMocks.useSearch,
}));

export const api = moleculesListMocks.api;
export const hooks = moleculesListMocks.hooks;
export const routerMod = {
  useSearch: moleculesListMocks.useSearch,
};

export function createMolecule(overrides: Partial<MoleculeResponse> = {}): MoleculeResponse {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    name: "H2",
    atoms: [
      { symbol: "H", x: 0, y: 0, z: 0 },
      { symbol: "H", x: 0.7, y: 0, z: 0 },
    ],
    charge: 0,
    multiplicity: 1,
    basis_set: "sto-3g",
    active_space: null,
    eligibility: {
      selectable: true,
      label: "Active space unset",
      reason: "A bounded active space has not been derived yet.",
      capability_labels: ["Run validation required"],
    },
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
    ...overrides,
  };
}

export function createMoleculeSummary(
  overrides: Partial<MoleculeSummaryResponse> = {},
): MoleculeSummaryResponse {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    name: "H2",
    charge: 0,
    atom_count: 2,
    run_count: 0,
    formula: "H2",
    iupac_name: null,
    eligibility: {
      selectable: true,
      label: "Active space unset",
      reason: "A bounded active space has not been derived yet.",
      capability_labels: ["Run validation required"],
    },
    ...overrides,
  };
}

export function createImportPreview(
  overrides: Partial<MoleculeImportPreviewResponse> = {},
): MoleculeImportPreviewResponse {
  return {
    source: "pubchem",
    name: "Water",
    atoms: [
      { symbol: "O", x: 0, y: 0, z: 0 },
      { symbol: "H", x: 0.757, y: 0.586, z: 0 },
      { symbol: "H", x: -0.757, y: 0.586, z: 0 },
    ],
    charge: 0,
    multiplicity: 1,
    active_space: { n_electrons: 8, n_orbitals: 6 },
    atom_count: 3,
    formula: "H2O",
    eligibility: {
      selectable: true,
      label: "Ready",
      reason: null,
      capability_labels: ["All algorithms", "12 qubits"],
    },
    commit_action: "create",
    existing_molecule_id: null,
    existing_molecule_name: null,
    pubchem_cid: 962,
    iupac_name: "oxidane",
    description: null,
    synonyms: ["water"],
    smiles: "O",
    inchi: null,
    inchi_key: null,
    ...overrides,
  };
}

const queryClient = createQueryClient();

export function renderWithQuery(component: ReactElement = <MoleculesList />): RenderResult {
  return render(<QueryClientProvider client={queryClient}>{component}</QueryClientProvider>);
}

export function resetMoleculesListMocks() {
  vi.clearAllMocks();
  queryClient.clear();
  moleculesListMocks.useSearch.mockReturnValue({ q: "", page: 1 });
  moleculesListMocks.api.searchPubChem.mockResolvedValue({ results: [] });
  moleculesListMocks.api.previewMoleculeFromPubChem.mockResolvedValue(createImportPreview());
  moleculesListMocks.api.previewMoleculeFromXyz.mockResolvedValue(
    createImportPreview({ source: "xyz" }),
  );
  moleculesListMocks.api.importMoleculeFromPubChem.mockResolvedValue(
    createMolecule({ id: "22222222-2222-2222-2222-222222222222", name: "Water" }),
  );
  moleculesListMocks.api.importMoleculeFromXyz.mockResolvedValue(
    createMolecule({ id: "33333333-3333-3333-3333-333333333333", name: "Water XYZ" }),
  );
  moleculesListMocks.api.deleteMolecule.mockResolvedValue(undefined);
}
