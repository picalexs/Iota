import { describe, expect, it } from "vitest";

import type {
  ApiBackendListResponse,
  ApiBasisSetListResponse,
  ApiBenchmarkRunCreate,
  ApiBenchmarkRunListResponse,
  ApiBenchmarkRunResponse,
  ApiBenchmarkRunUpdate,
  ApiExportBundle,
  ApiIbmCredentialProfileCreate,
  ApiIbmCredentialProfileListResponse,
  ApiIbmCredentialProfileResponse,
  ApiIbmCredentialProfileTestResponse,
  ApiIbmCredentialProfileUpdate,
  ApiJsonRequestBody,
  ApiJsonResponse,
  ApiMoleculeImportPreviewResponse,
  ApiMoleculeListResponse,
  ApiMoleculeCreate,
  ApiMoleculeResponse,
  ApiMoleculeSummaryListResponse,
  ApiMoleculeUpdate,
  ApiPubChemImportRequest,
  ApiPubChemSearchResponse,
  ApiRunActionResponse,
  ApiRunCancelResponse,
  ApiRunCreate,
  ApiRunEventListResponse,
  ApiRunListResponse,
  ApiRunResponse,
  ApiRunResultResponse,
  ApiRunSummaryListResponse,
  ApiRunValidationRequest,
  ApiRunValidationResponse,
  ApiStatusResponse,
  ApiTranspilePreviewRequest,
  ApiTranspilePreviewResponse,
  ApiXYZImportRequest,
  ApiXYZPreviewRequest,
} from "@/types/api";
import type { fetchBackendCapabilities, previewTranspilation } from "./backends";
import type { createBenchmarkRun } from "./benchmarks";
import type { createMolecule } from "./molecules";
import type { createIbmCredentialProfile } from "./profiles";
import type {
  createRun,
  exportRun,
  getRun,
  getRunResult,
  listRuns,
  pauseRun,
  validateRunRequest,
} from "./runs";
import type { getStatus } from "./status";

const RUN_ID = "3fa85f64-5717-4562-b3fc-2c963f66afa6";

type Equal<Left, Right> =
  (<Type>() => Type extends Left ? 1 : 2) extends <Type>() => Type extends Right ? 1 : 2
    ? true
    : false;

type Assert<Condition extends true> = Condition;

type ListRunsParameters = NonNullable<Parameters<typeof listRuns>[0]>;

type GeneratedOperationContracts = {
  backendList: Assert<
    Equal<ApiBackendListResponse, ApiJsonResponse<"get_backends_api_backends_get", 200>>
  >;
  basisSetList: Assert<
    Equal<ApiBasisSetListResponse, ApiJsonResponse<"get_basis_sets_api_basis_sets_get", 200>>
  >;
  transpileRequest: Assert<
    Equal<
      ApiTranspilePreviewRequest,
      ApiJsonRequestBody<"preview_transpile_api_backends_transpile_preview_post">
    >
  >;
  transpileResponse: Assert<
    Equal<
      ApiTranspilePreviewResponse,
      ApiJsonResponse<"preview_transpile_api_backends_transpile_preview_post", 200>
    >
  >;
  benchmarkList: Assert<
    Equal<
      ApiBenchmarkRunListResponse,
      ApiJsonResponse<"list_benchmark_runs_api_benchmarks_get", 200>
    >
  >;
  benchmarkCreateRequest: Assert<
    Equal<ApiBenchmarkRunCreate, ApiJsonRequestBody<"create_benchmark_run_api_benchmarks_post">>
  >;
  benchmarkCreateResponse: Assert<
    Equal<ApiBenchmarkRunResponse, ApiJsonResponse<"create_benchmark_run_api_benchmarks_post", 201>>
  >;
  benchmarkGetResponse: Assert<
    Equal<
      ApiBenchmarkRunResponse,
      ApiJsonResponse<"get_benchmark_run_api_benchmarks__benchmark_id__get", 200>
    >
  >;
  benchmarkUpdateRequest: Assert<
    Equal<
      ApiBenchmarkRunUpdate,
      ApiJsonRequestBody<"update_benchmark_run_api_benchmarks__benchmark_id__patch">
    >
  >;
  benchmarkUpdateResponse: Assert<
    Equal<
      ApiBenchmarkRunResponse,
      ApiJsonResponse<"update_benchmark_run_api_benchmarks__benchmark_id__patch", 200>
    >
  >;
  moleculeList: Assert<
    Equal<ApiMoleculeListResponse, ApiJsonResponse<"list_molecules_api_molecules_get", 200>>
  >;
  moleculeCreateRequest: Assert<
    Equal<ApiMoleculeCreate, ApiJsonRequestBody<"create_molecule_api_molecules_post">>
  >;
  moleculeCreateResponse: Assert<
    Equal<ApiMoleculeResponse, ApiJsonResponse<"create_molecule_api_molecules_post", 201>>
  >;
  moleculeGetResponse: Assert<
    Equal<ApiMoleculeResponse, ApiJsonResponse<"get_molecule_api_molecules__molecule_id__get", 200>>
  >;
  moleculeUpdateRequest: Assert<
    Equal<
      ApiMoleculeUpdate,
      ApiJsonRequestBody<"update_molecule_api_molecules__molecule_id__patch">
    >
  >;
  moleculeUpdateResponse: Assert<
    Equal<
      ApiMoleculeResponse,
      ApiJsonResponse<"update_molecule_api_molecules__molecule_id__patch", 200>
    >
  >;
  moleculeSummaryList: Assert<
    Equal<
      ApiMoleculeSummaryListResponse,
      ApiJsonResponse<"list_molecule_summaries_api_molecules_summaries_get", 200>
    >
  >;
  moleculePubChemImportRequest: Assert<
    Equal<
      ApiPubChemImportRequest,
      ApiJsonRequestBody<"import_molecule_from_pubchem_api_molecules_pubchem_import_post">
    >
  >;
  moleculePubChemImportResponse: Assert<
    Equal<
      ApiMoleculeResponse,
      ApiJsonResponse<"import_molecule_from_pubchem_api_molecules_pubchem_import_post", 201>
    >
  >;
  moleculePubChemPreviewResponse: Assert<
    Equal<
      ApiMoleculeImportPreviewResponse,
      ApiJsonResponse<"preview_molecule_from_pubchem_api_molecules_pubchem_preview_post", 200>
    >
  >;
  moleculePubChemSearchResponse: Assert<
    Equal<
      ApiPubChemSearchResponse,
      ApiJsonResponse<"search_pubchem_api_molecules_pubchem_search_get", 200>
    >
  >;
  moleculeXyzImportRequest: Assert<
    Equal<
      ApiXYZImportRequest,
      ApiJsonRequestBody<"import_molecule_from_xyz_api_molecules_xyz_import_post">
    >
  >;
  moleculeXyzImportResponse: Assert<
    Equal<
      ApiMoleculeResponse,
      ApiJsonResponse<"import_molecule_from_xyz_api_molecules_xyz_import_post", 201>
    >
  >;
  moleculeXyzPreviewRequest: Assert<
    Equal<
      ApiXYZPreviewRequest,
      ApiJsonRequestBody<"preview_molecule_from_xyz_api_molecules_xyz_preview_post">
    >
  >;
  moleculeXyzPreviewResponse: Assert<
    Equal<
      ApiMoleculeImportPreviewResponse,
      ApiJsonResponse<"preview_molecule_from_xyz_api_molecules_xyz_preview_post", 200>
    >
  >;
  runList: Assert<Equal<ApiRunListResponse, ApiJsonResponse<"list_runs_api_runs_get", 200>>>;
  runCreateRequest: Assert<Equal<ApiRunCreate, ApiJsonRequestBody<"create_run_api_runs_post">>>;
  runCreateResponse: Assert<
    Equal<ApiRunResponse, ApiJsonResponse<"create_run_api_runs_post", 201>>
  >;
  runGetResponse: Assert<
    Equal<ApiRunResponse, ApiJsonResponse<"get_run_api_runs__run_id__get", 200>>
  >;
  runSummaryList: Assert<
    Equal<
      ApiRunSummaryListResponse,
      ApiJsonResponse<"list_run_summaries_api_runs_summaries_get", 200>
    >
  >;
  runCancelResponse: Assert<
    Equal<ApiRunCancelResponse, ApiJsonResponse<"cancel_run_api_runs__run_id__cancel_post", 200>>
  >;
  runEvents: Assert<
    Equal<
      ApiRunEventListResponse,
      ApiJsonResponse<"get_run_events_api_runs__run_id__events_get", 200>
    >
  >;
  runExport: Assert<
    Equal<ApiExportBundle, ApiJsonResponse<"export_run_api_runs__run_id__export_get", 200>>
  >;
  runPauseResponse: Assert<
    Equal<ApiRunActionResponse, ApiJsonResponse<"pause_run_api_runs__run_id__pause_post", 200>>
  >;
  runRestartResponse: Assert<
    Equal<ApiRunActionResponse, ApiJsonResponse<"restart_run_api_runs__run_id__restart_post", 200>>
  >;
  runResult: Assert<
    Equal<ApiRunResultResponse, ApiJsonResponse<"get_run_result_api_runs__run_id__result_get", 200>>
  >;
  runResumeResponse: Assert<
    Equal<ApiRunActionResponse, ApiJsonResponse<"resume_run_api_runs__run_id__resume_post", 200>>
  >;
  runValidationRequest: Assert<
    Equal<ApiRunValidationRequest, ApiJsonRequestBody<"validate_config_api_validate_config_post">>
  >;
  runValidationResponse: Assert<
    Equal<
      ApiRunValidationResponse,
      ApiJsonResponse<"validate_config_api_validate_config_post", 200>
    >
  >;
  profileList: Assert<
    Equal<
      ApiIbmCredentialProfileListResponse,
      ApiJsonResponse<"list_ibm_profiles_api_settings_ibm_profiles_get", 200>
    >
  >;
  profileCreateRequest: Assert<
    Equal<
      ApiIbmCredentialProfileCreate,
      ApiJsonRequestBody<"create_ibm_profile_api_settings_ibm_profiles_post">
    >
  >;
  profileCreateResponse: Assert<
    Equal<
      ApiIbmCredentialProfileResponse,
      ApiJsonResponse<"create_ibm_profile_api_settings_ibm_profiles_post", 201>
    >
  >;
  profileUpdateRequest: Assert<
    Equal<
      ApiIbmCredentialProfileUpdate,
      ApiJsonRequestBody<"update_ibm_profile_api_settings_ibm_profiles__profile_id__patch">
    >
  >;
  profileUpdateResponse: Assert<
    Equal<
      ApiIbmCredentialProfileResponse,
      ApiJsonResponse<"update_ibm_profile_api_settings_ibm_profiles__profile_id__patch", 200>
    >
  >;
  profileActivateResponse: Assert<
    Equal<
      ApiIbmCredentialProfileResponse,
      ApiJsonResponse<
        "activate_ibm_profile_api_settings_ibm_profiles__profile_id__activate_post",
        200
      >
    >
  >;
  profileTestResponse: Assert<
    Equal<
      ApiIbmCredentialProfileTestResponse,
      ApiJsonResponse<"test_ibm_profile_api_settings_ibm_profiles__profile_id__test_post", 200>
    >
  >;
  statusResponse: Assert<
    Equal<ApiStatusResponse, ApiJsonResponse<"system_status_api_status_get", 200>>
  >;
  statusFailureResponse: Assert<
    Equal<ApiStatusResponse, ApiJsonResponse<"system_status_api_status_get", 503>>
  >;
};

const statusResponse = {
  api: "ready",
  db: "connected",
  redis: "unknown",
} satisfies ApiStatusResponse;

const runCreateRequest = {
  molecule_id: RUN_ID,
  algorithm: "vqe",
  mode: "easy",
  backend_target: "statevector",
  easy_options: { goal: "balanced" },
  ibm_runtime_confirmed: false,
} satisfies ApiRunCreate;

const runResponse = {
  id: RUN_ID,
  molecule_id: RUN_ID,
  config_json: { algorithm: "vqe", mode: "easy" },
  created_at: "2026-01-01T00:00:00Z",
  execution_generation: 1,
  status: "QUEUED",
  updated_at: "2026-01-01T00:00:00Z",
} satisfies ApiRunResponse;

const runListResponse = {
  items: [runResponse],
  total: 1,
  limit: 50,
  offset: 0,
} satisfies ApiRunListResponse;

const runActionResponse = {
  id: RUN_ID,
  execution_generation: 1,
  status: "PAUSED",
  checkpoint_id: null,
  child_run_id: null,
  message: null,
} satisfies ApiRunActionResponse;

const runResultResponse = {
  run_id: RUN_ID,
  energy: -1.0,
  iterations: 1,
  optimal_parameters: [],
  converged: true,
  created_at: "2026-01-01T00:00:00Z",
} satisfies ApiRunResultResponse;

const moleculeCreateRequest = {
  name: "Hydrogen",
  atoms: [
    { symbol: "H", x: 0, y: 0, z: 0 },
    { symbol: "H", x: 0, y: 0, z: 0.74 },
  ],
  charge: 0,
  multiplicity: 1,
} satisfies ApiMoleculeCreate;

const moleculeResponse = {
  id: RUN_ID,
  name: moleculeCreateRequest.name,
  atoms: moleculeCreateRequest.atoms,
  charge: moleculeCreateRequest.charge,
  multiplicity: moleculeCreateRequest.multiplicity,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  visualizable: true,
} satisfies ApiMoleculeResponse;

const benchmarkCreateRequest = {
  name: "H2 fixture",
  selectedMoleculeKeys: ["h2"],
  selectedAlgorithms: ["vqe"],
  selectedBasis: "sto-3g",
  selectedBackendMode: "statevector",
  selectedBackendName: null,
  shots: 4096,
  chemicalAccuracyHa: 0.0016,
} satisfies ApiBenchmarkRunCreate;

const benchmarkResponse = {
  id: RUN_ID,
  ...benchmarkCreateRequest,
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:00:00Z",
} satisfies ApiBenchmarkRunResponse;

const profileCreateRequest = {
  name: "fixture-profile",
  token: "fixture-token",
  crn: "fixture-crn",
  channel: "ibm_quantum_platform",
  activate: true,
} satisfies ApiIbmCredentialProfileCreate;

const backendListResponse = {
  backends: [
    {
      target: "statevector",
      name: "statevector",
      display_name: "Statevector",
      available: true,
      simulator: true,
      supports_noise_profile: false,
      supports_transpile_preview: true,
    },
  ],
  warnings: [],
} satisfies ApiBackendListResponse;

const transpilePreviewRequest = {
  target: "statevector",
  algorithm: "vqe",
  num_qubits: 2,
  backend_options: {
    aer_method: "automatic",
    estimator_precision: 0,
    optimization_level: 1,
    selection_policy: "manual",
    shots: 4096,
    backend_name: null,
    credential_profile_id: null,
    seed_simulator: null,
    seed_transpiler: null,
  },
} satisfies ApiTranspilePreviewRequest;

const transpilePreviewResponse = {
  target: transpilePreviewRequest.target,
  feasible: true,
  requested_qubits: transpilePreviewRequest.num_qubits,
  metadata: {},
  warnings: [],
} satisfies ApiTranspilePreviewResponse;

type EndpointFieldContracts = [
  Assert<Equal<Awaited<ReturnType<typeof getStatus>>, ApiStatusResponse>>,
  Assert<Equal<Awaited<ReturnType<typeof exportRun>>, ApiExportBundle>>,
  Assert<Equal<Parameters<typeof createRun>[0]["algorithm"], ApiRunCreate["algorithm"]>>,
  Assert<Equal<Parameters<typeof createRun>[0]["backend_target"], ApiRunCreate["backend_target"]>>,
  Assert<Equal<Parameters<typeof createRun>[0]["mode"], ApiRunCreate["mode"]>>,
  Assert<Equal<NonNullable<ListRunsParameters["limit"]>, ApiRunListResponse["limit"]>>,
  Assert<Equal<NonNullable<ListRunsParameters["offset"]>, ApiRunListResponse["offset"]>>,
  Assert<Equal<Awaited<ReturnType<typeof getRun>>["status"], ApiRunResponse["status"]>>,
  Assert<Equal<Awaited<ReturnType<typeof getRunResult>>["energy"], ApiRunResultResponse["energy"]>>,
  Assert<
    Equal<Parameters<typeof validateRunRequest>[0]["run"]["algorithm"], ApiRunCreate["algorithm"]>
  >,
  Assert<Equal<Parameters<typeof createMolecule>[0]["name"], ApiMoleculeCreate["name"]>>,
  Assert<Equal<Parameters<typeof createBenchmarkRun>[0]["name"], ApiBenchmarkRunCreate["name"]>>,
  Assert<
    Equal<
      Parameters<typeof previewTranspilation>[0]["algorithm"],
      NonNullable<ApiTranspilePreviewRequest["algorithm"]>
    >
  >,
  Assert<
    Equal<
      Parameters<typeof previewTranspilation>[0]["backend_target"],
      ApiTranspilePreviewRequest["target"]
    >
  >,
  Assert<
    Equal<
      Parameters<typeof previewTranspilation>[0]["num_qubits"],
      ApiTranspilePreviewRequest["num_qubits"]
    >
  >,
  Assert<Equal<Awaited<ReturnType<typeof pauseRun>>["status"], ApiRunActionResponse["status"]>>,
  Assert<
    Equal<
      Parameters<typeof createIbmCredentialProfile>[0]["name"],
      ApiIbmCredentialProfileCreate["name"]
    >
  >,
  Assert<
    Equal<
      Awaited<ReturnType<typeof createIbmCredentialProfile>>["created_at"],
      ApiIbmCredentialProfileResponse["created_at"]
    >
  >,
  Assert<Equal<Awaited<ReturnType<typeof createMolecule>>["name"], ApiMoleculeResponse["name"]>>,
  Assert<
    Equal<Awaited<ReturnType<typeof createBenchmarkRun>>["name"], ApiBenchmarkRunResponse["name"]>
  >,
  Assert<
    Equal<
      Awaited<ReturnType<typeof fetchBackendCapabilities>>["backends"][number]["target"],
      ApiBackendListResponse["backends"][number]["target"]
    >
  >,
];

const generatedOperationContracts: GeneratedOperationContracts = {
  backendList: true,
  basisSetList: true,
  transpileRequest: true,
  transpileResponse: true,
  benchmarkList: true,
  benchmarkCreateRequest: true,
  benchmarkCreateResponse: true,
  benchmarkGetResponse: true,
  benchmarkUpdateRequest: true,
  benchmarkUpdateResponse: true,
  moleculeList: true,
  moleculeCreateRequest: true,
  moleculeCreateResponse: true,
  moleculeGetResponse: true,
  moleculeUpdateRequest: true,
  moleculeUpdateResponse: true,
  moleculeSummaryList: true,
  moleculePubChemImportRequest: true,
  moleculePubChemImportResponse: true,
  moleculePubChemPreviewResponse: true,
  moleculePubChemSearchResponse: true,
  moleculeXyzImportRequest: true,
  moleculeXyzImportResponse: true,
  moleculeXyzPreviewRequest: true,
  moleculeXyzPreviewResponse: true,
  runList: true,
  runCreateRequest: true,
  runCreateResponse: true,
  runGetResponse: true,
  runSummaryList: true,
  runCancelResponse: true,
  runEvents: true,
  runExport: true,
  runPauseResponse: true,
  runRestartResponse: true,
  runResult: true,
  runResumeResponse: true,
  runValidationRequest: true,
  runValidationResponse: true,
  profileList: true,
  profileCreateRequest: true,
  profileCreateResponse: true,
  profileUpdateRequest: true,
  profileUpdateResponse: true,
  profileActivateResponse: true,
  profileTestResponse: true,
  statusResponse: true,
  statusFailureResponse: true,
};

const endpointFieldContracts: EndpointFieldContracts = [
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
];

const representativeFixtures = [
  statusResponse,
  runCreateRequest,
  runResponse,
  runListResponse,
  runActionResponse,
  runResultResponse,
  moleculeCreateRequest,
  moleculeResponse,
  benchmarkCreateRequest,
  benchmarkResponse,
  profileCreateRequest,
  backendListResponse,
  transpilePreviewRequest,
  transpilePreviewResponse,
];

describe("generated API contract fixtures", () => {
  it("keeps representative DTOs and endpoint signatures compile-safe", () => {
    expect(Object.values(generatedOperationContracts).every(Boolean)).toBe(true);
    expect(endpointFieldContracts.every(Boolean)).toBe(true);
    expect(representativeFixtures).toHaveLength(14);
  });
});
