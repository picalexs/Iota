/** Molecule API calls. */

import type {
  BasisSetListResponse,
  MoleculeEligibilityResponse,
  MoleculeCreate,
  MoleculeImportPreviewResponse,
  MoleculeListParams,
  MoleculeListResponse,
  MoleculeResponse,
  MoleculeSummaryListResponse,
  MoleculeUpdate,
  PubChemImportRequest,
  PubChemSearchResponse,
  UUID,
  XYZImportRequest,
  XYZPreviewRequest,
} from "@/types/run";
import type {
  ApiBasisSetListResponse,
  ApiMoleculeCreate,
  ApiMoleculeImportPreviewResponse,
  ApiMoleculeListResponse,
  ApiMoleculeResponse,
  ApiMoleculeSummaryListResponse,
  ApiMoleculeUpdate,
  ApiPubChemImportRequest,
  ApiPubChemSearchResponse,
  ApiXYZImportRequest,
  ApiXYZPreviewRequest,
} from "@/types/api";
import { isRunAlgorithm } from "@/types/run-status";
import {
  API_BASE,
  fetchWithApiError,
  handleApiError,
  invalidApiResponse,
  isFiniteNumber,
  isOptionalNullableGuard,
  isOptionalNullableNumber,
  isOptionalNullableString,
  isOptionalNullableStringArray,
  isOptionalStringArray,
  isRecord,
  request,
} from "./http";

export interface DeleteMoleculeOptions {
  deleteAssociatedRuns?: boolean;
}

const MOLECULE_PREVIEW_SOURCES = new Set(["pubchem", "xyz"] as const);
const MOLECULE_COMMIT_ACTIONS = new Set(["create", "reuse", "name_conflict"] as const);

type ApiAtom = ApiMoleculeResponse["atoms"][number];
type ApiActiveSpace = NonNullable<ApiMoleculeResponse["active_space"]>;
type ApiMoleculeEligibility = NonNullable<ApiMoleculeResponse["eligibility"]>;
type ApiMoleculeSummary = ApiMoleculeSummaryListResponse["items"][number];
type ApiBasisSet = ApiBasisSetListResponse["basis_sets"][number];
type ApiPubChemResult = ApiPubChemSearchResponse["results"][number];

function isAtom(value: unknown): value is ApiAtom {
  return (
    isRecord(value) &&
    typeof value.symbol === "string" &&
    isFiniteNumber(value.x) &&
    isFiniteNumber(value.y) &&
    isFiniteNumber(value.z)
  );
}

function isActiveSpace(value: unknown): value is ApiActiveSpace {
  return isRecord(value) && isFiniteNumber(value.n_electrons) && isFiniteNumber(value.n_orbitals);
}

function isMoleculeEligibility(value: unknown): value is ApiMoleculeEligibility {
  return (
    isRecord(value) &&
    typeof value.selectable === "boolean" &&
    typeof value.label === "string" &&
    isOptionalNullableString(value, "reason") &&
    isOptionalStringArray(value, "capability_labels")
  );
}

function isMoleculeResponse(value: unknown): value is ApiMoleculeResponse {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.name === "string" &&
    Array.isArray(value.atoms) &&
    value.atoms.every(isAtom) &&
    isFiniteNumber(value.charge) &&
    isFiniteNumber(value.multiplicity) &&
    typeof value.created_at === "string" &&
    typeof value.updated_at === "string" &&
    typeof value.visualizable === "boolean" &&
    isOptionalNullableGuard(value, "active_space", isActiveSpace) &&
    isOptionalStringArray(value, "blocking_reasons") &&
    isOptionalNullableString(value, "description") &&
    (!("eligibility" in value) ||
      value.eligibility === null ||
      isMoleculeEligibility(value.eligibility)) &&
    isOptionalNullableString(value, "inchi") &&
    isOptionalNullableString(value, "inchi_key") &&
    isOptionalNullableString(value, "iupac_name") &&
    isOptionalNullableNumber(value, "pubchem_cid") &&
    isOptionalStringArray(value, "runnable_algorithms") &&
    isOptionalNullableString(value, "smiles") &&
    isOptionalNullableStringArray(value, "synonyms") &&
    isOptionalStringArray(value, "warnings")
  );
}

export function parseMoleculeResponse(value: unknown): ApiMoleculeResponse {
  if (!isMoleculeResponse(value)) {
    throw invalidApiResponse("Invalid molecule response");
  }
  return value;
}

function isMoleculeSummary(value: unknown): value is ApiMoleculeSummary {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.name === "string" &&
    typeof value.formula === "string" &&
    isFiniteNumber(value.atom_count) &&
    isFiniteNumber(value.charge) &&
    isMoleculeEligibility(value.eligibility) &&
    isFiniteNumber(value.run_count) &&
    typeof value.visualizable === "boolean" &&
    isOptionalNullableString(value, "iupac_name") &&
    isOptionalStringArray(value, "blocking_reasons") &&
    isOptionalStringArray(value, "runnable_algorithms") &&
    isOptionalStringArray(value, "warnings")
  );
}

export function parseMoleculeListResponse(value: unknown): ApiMoleculeListResponse {
  if (
    !isRecord(value) ||
    !Array.isArray(value.items) ||
    !value.items.every(isMoleculeResponse) ||
    !isFiniteNumber(value.total)
  ) {
    throw invalidApiResponse("Invalid molecule list response");
  }
  return value as ApiMoleculeListResponse;
}

export function parseMoleculeSummaryListResponse(value: unknown): ApiMoleculeSummaryListResponse {
  if (
    !isRecord(value) ||
    !Array.isArray(value.items) ||
    !value.items.every(isMoleculeSummary) ||
    !isFiniteNumber(value.total)
  ) {
    throw invalidApiResponse("Invalid molecule summary list response");
  }
  return value as ApiMoleculeSummaryListResponse;
}

function isMoleculeImportPreviewResponse(
  value: unknown,
): value is ApiMoleculeImportPreviewResponse {
  return (
    isRecord(value) &&
    MOLECULE_PREVIEW_SOURCES.has(value.source as "pubchem" | "xyz") &&
    MOLECULE_COMMIT_ACTIONS.has(value.commit_action as "create" | "reuse" | "name_conflict") &&
    typeof value.name === "string" &&
    typeof value.formula === "string" &&
    Array.isArray(value.atoms) &&
    value.atoms.every(isAtom) &&
    isFiniteNumber(value.atom_count) &&
    isFiniteNumber(value.charge) &&
    isFiniteNumber(value.multiplicity) &&
    (value.active_space === null || isActiveSpace(value.active_space)) &&
    isMoleculeEligibility(value.eligibility) &&
    isOptionalNullableString(value, "description") &&
    isOptionalNullableString(value, "existing_molecule_id") &&
    isOptionalNullableString(value, "existing_molecule_name") &&
    isOptionalNullableString(value, "inchi") &&
    isOptionalNullableString(value, "inchi_key") &&
    isOptionalNullableString(value, "iupac_name") &&
    isOptionalNullableNumber(value, "pubchem_cid") &&
    isOptionalStringArray(value, "blocking_reasons") &&
    isOptionalStringArray(value, "runnable_algorithms") &&
    isOptionalNullableString(value, "smiles") &&
    isOptionalNullableStringArray(value, "synonyms") &&
    isOptionalStringArray(value, "warnings") &&
    typeof value.visualizable === "boolean"
  );
}

export function parseMoleculeImportPreviewResponse(
  value: unknown,
): ApiMoleculeImportPreviewResponse {
  if (!isMoleculeImportPreviewResponse(value)) {
    throw invalidApiResponse("Invalid molecule import preview response");
  }
  return value;
}

function isBasisSet(value: unknown): value is ApiBasisSet {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.label === "string" &&
    typeof value.family === "string" &&
    typeof value.description === "string" &&
    typeof value.recommended === "boolean" &&
    isOptionalStringArray(value, "supported_elements")
  );
}

export function parseBasisSetListResponse(value: unknown): ApiBasisSetListResponse {
  if (
    !isRecord(value) ||
    !Array.isArray(value.basis_sets) ||
    !value.basis_sets.every(isBasisSet) ||
    typeof value.default_basis_set !== "string"
  ) {
    throw invalidApiResponse("Invalid basis-set list response");
  }
  return value as ApiBasisSetListResponse;
}

function isPubChemResult(value: unknown): value is ApiPubChemResult {
  return (
    isRecord(value) &&
    typeof value.name === "string" &&
    typeof value.formula === "string" &&
    typeof value.iupac_name === "string" &&
    isOptionalNullableNumber(value, "cid")
  );
}

export function parsePubChemSearchResponse(value: unknown): ApiPubChemSearchResponse {
  if (!isRecord(value) || !Array.isArray(value.results) || !value.results.every(isPubChemResult)) {
    throw invalidApiResponse("Invalid PubChem search response");
  }
  return value as ApiPubChemSearchResponse;
}

function appendDefinedQueryParam(
  query: URLSearchParams,
  key: string,
  value: string | number | boolean | undefined,
): void {
  if (value !== undefined) {
    query.append(key, String(value));
  }
}

function buildMoleculesQuery(params?: MoleculeListParams): string {
  if (!params) {
    return "";
  }

  const query = new URLSearchParams();
  appendDefinedQueryParam(query, "q", params.q);
  appendDefinedQueryParam(query, "charge", params.charge);
  appendDefinedQueryParam(query, "limit", params.limit);
  appendDefinedQueryParam(query, "offset", params.offset);
  return query.toString();
}

function moleculeUrl(path: string, params?: MoleculeListParams): string {
  const query = buildMoleculesQuery(params);
  return query ? `${API_BASE}${path}?${query}` : `${API_BASE}${path}`;
}

function toRunAlgorithms(values: string[] | undefined) {
  return (values ?? []).filter(isRunAlgorithm);
}

function toEligibility(data: {
  selectable: boolean;
  label: string;
  reason?: string | null;
  capability_labels?: string[];
}): MoleculeEligibilityResponse {
  return {
    ...data,
    capability_labels: data.capability_labels ?? [],
  };
}

function toMolecule(data: ApiMoleculeResponse): MoleculeResponse {
  return {
    ...data,
    id: data.id as UUID,
    active_space: data.active_space ?? null,
    eligibility: data.eligibility ? toEligibility(data.eligibility) : null,
    runnable_algorithms: toRunAlgorithms(data.runnable_algorithms),
    blocking_reasons: data.blocking_reasons ?? [],
    warnings: data.warnings ?? [],
  };
}

function toMoleculeList(data: ApiMoleculeListResponse): MoleculeListResponse {
  return {
    ...data,
    items: data.items.map(toMolecule),
  };
}

function toMoleculeSummary(data: ApiMoleculeSummaryListResponse["items"][number]) {
  return {
    ...data,
    id: data.id as UUID,
    eligibility: toEligibility(data.eligibility),
    runnable_algorithms: toRunAlgorithms(data.runnable_algorithms),
    blocking_reasons: data.blocking_reasons ?? [],
    warnings: data.warnings ?? [],
  };
}

function toMoleculeSummaryList(data: ApiMoleculeSummaryListResponse): MoleculeSummaryListResponse {
  return {
    ...data,
    items: data.items.map(toMoleculeSummary),
  };
}

function toImportPreview(data: ApiMoleculeImportPreviewResponse): MoleculeImportPreviewResponse {
  return {
    ...data,
    eligibility: toEligibility(data.eligibility),
    runnable_algorithms: toRunAlgorithms(data.runnable_algorithms),
    blocking_reasons: data.blocking_reasons ?? [],
    warnings: data.warnings ?? [],
    existing_molecule_id: data.existing_molecule_id ? (data.existing_molecule_id as UUID) : null,
  };
}

function toMoleculeCreate(data: MoleculeCreate): ApiMoleculeCreate {
  return {
    ...data,
    charge: data.charge ?? 0,
    multiplicity: data.multiplicity ?? 1,
  };
}

function toMoleculeUpdate(data: MoleculeUpdate): ApiMoleculeUpdate {
  return { ...data };
}

function toPubChemImport(data: PubChemImportRequest): ApiPubChemImportRequest {
  return {
    name: data.name,
    display_name: data.display_name ?? null,
  };
}

function toXyzPreview(data: XYZPreviewRequest): ApiXYZPreviewRequest {
  return {
    xyz: data.xyz,
    name: data.name ?? null,
    charge: data.charge ?? 0,
    multiplicity: data.multiplicity ?? 1,
    active_space: data.active_space ?? null,
    derive_active_space: data.derive_active_space ?? true,
  };
}

function toXyzImport(data: XYZImportRequest): ApiXYZImportRequest {
  return {
    xyz: data.xyz,
    name: data.name,
    charge: data.charge ?? 0,
    multiplicity: data.multiplicity ?? 1,
    active_space: data.active_space ?? null,
    derive_active_space: data.derive_active_space ?? true,
  };
}

export async function fetchMolecules(params?: MoleculeListParams): Promise<MoleculeListResponse> {
  const response = parseMoleculeListResponse(
    await request<unknown>(moleculeUrl("/api/molecules", params), {
      method: "GET",
    }),
  );
  return toMoleculeList(response);
}

export async function fetchMoleculeSummaries(
  params?: MoleculeListParams,
): Promise<MoleculeSummaryListResponse> {
  const response = parseMoleculeSummaryListResponse(
    await request<unknown>(moleculeUrl("/api/molecules/summaries", params), {
      method: "GET",
    }),
  );
  return toMoleculeSummaryList(response);
}

export async function fetchBasisSets(): Promise<BasisSetListResponse> {
  const response = parseBasisSetListResponse(
    await request<unknown>(`${API_BASE}/api/basis-sets`, {
      method: "GET",
    }),
  );
  return {
    ...response,
    basis_sets: response.basis_sets.map((basisSet) => ({
      ...basisSet,
      supported_elements: basisSet.supported_elements ?? [],
    })),
  };
}

export async function searchPubChem(q: string): Promise<PubChemSearchResponse> {
  const query = new URLSearchParams({ q });
  const response = parsePubChemSearchResponse(
    await request<unknown>(`${API_BASE}/api/molecules/pubchem/search?${query.toString()}`, {
      method: "GET",
    }),
  );
  return {
    ...response,
    results: response.results.map((result) => ({
      ...result,
      cid: result.cid ?? null,
    })),
  };
}

export async function previewMoleculeFromPubChem(
  data: PubChemImportRequest,
): Promise<MoleculeImportPreviewResponse> {
  const response = parseMoleculeImportPreviewResponse(
    await request<unknown>(`${API_BASE}/api/molecules/pubchem/preview`, {
      method: "POST",
      body: JSON.stringify(toPubChemImport(data)),
    }),
  );
  return toImportPreview(response);
}

export async function importMoleculeFromPubChem(
  data: PubChemImportRequest,
): Promise<MoleculeResponse> {
  const response = parseMoleculeResponse(
    await request<unknown>(`${API_BASE}/api/molecules/pubchem/import`, {
      method: "POST",
      body: JSON.stringify(toPubChemImport(data)),
    }),
  );
  return toMolecule(response);
}

export async function previewMoleculeFromXyz(
  data: XYZPreviewRequest,
): Promise<MoleculeImportPreviewResponse> {
  const response = parseMoleculeImportPreviewResponse(
    await request<unknown>(`${API_BASE}/api/molecules/xyz/preview`, {
      method: "POST",
      body: JSON.stringify(toXyzPreview(data)),
    }),
  );
  return toImportPreview(response);
}

export async function importMoleculeFromXyz(data: XYZImportRequest): Promise<MoleculeResponse> {
  const response = parseMoleculeResponse(
    await request<unknown>(`${API_BASE}/api/molecules/xyz/import`, {
      method: "POST",
      body: JSON.stringify(toXyzImport(data)),
    }),
  );
  return toMolecule(response);
}

export async function getMolecule(id: UUID): Promise<MoleculeResponse> {
  const response = parseMoleculeResponse(
    await request<unknown>(`${API_BASE}/api/molecules/${id}`, {
      method: "GET",
    }),
  );
  return toMolecule(response);
}

export async function createMolecule(data: MoleculeCreate): Promise<MoleculeResponse> {
  const response = parseMoleculeResponse(
    await request<unknown>(`${API_BASE}/api/molecules`, {
      method: "POST",
      body: JSON.stringify(toMoleculeCreate(data)),
    }),
  );
  return toMolecule(response);
}

export async function updateMolecule(id: UUID, data: MoleculeUpdate): Promise<MoleculeResponse> {
  const response = parseMoleculeResponse(
    await request<unknown>(`${API_BASE}/api/molecules/${id}`, {
      method: "PATCH",
      body: JSON.stringify(toMoleculeUpdate(data)),
    }),
  );
  return toMolecule(response);
}

export async function deleteMolecule(id: UUID, options: DeleteMoleculeOptions = {}): Promise<void> {
  const query = new URLSearchParams();
  if (options.deleteAssociatedRuns) {
    query.set("delete_associated_runs", "true");
  }
  const path = `/api/molecules/${id}`;
  const url = query.size > 0 ? `${API_BASE}${path}?${query}` : `${API_BASE}${path}`;
  const response = await fetchWithApiError(url, {
    method: "DELETE",
    headers: new Headers(),
  });
  if (!response.ok) {
    await handleApiError(response, { method: "DELETE", url });
  }
}
