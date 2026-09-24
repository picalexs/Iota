/**
 * Handwritten names for generated transport contracts.
 *
 * Keep form state and presentation models in their feature-specific modules.
 * This file only gives API code stable aliases over the generated OpenAPI
 * output.
 */

import type { components, operations, paths } from "./generated-api";

export type ApiComponents = components["schemas"];

/** A named schema from the checked-in OpenAPI output. */
export type ApiSchema<Name extends keyof ApiComponents> = ApiComponents[Name];

export type ApiRunStatus = ApiSchema<"RunStatus">;
export type ApiRunAlgorithm = ApiSchema<"RunAlgorithm">;
export type ApiRunMode = ApiSchema<"RunMode">;
export type ApiBackendTarget = ApiSchema<"BackendTarget">;
export type ApiEasyGoal = ApiSchema<"EasyGoal">;
export type ApiRunEventType = ApiSchema<"RunEventType">;
export type ApiValidationErrorCode = ApiSchema<"ValidationErrorCode">;

/** JSON response body for one generated operation/status pair. */
export type ApiJsonResponse<
  OperationName extends keyof operations,
  Status extends keyof operations[OperationName]["responses"],
> = operations[OperationName]["responses"][Status] extends {
  content: { "application/json": infer Body };
}
  ? Body
  : never;

/** JSON request body for one generated operation. */
export type ApiJsonRequestBody<OperationName extends keyof operations> =
  NonNullable<operations[OperationName]["requestBody"]> extends {
    content: { "application/json": infer Body };
  }
    ? Body
    : never;

export type ApiRunCreate = ApiSchema<"RunCreate">;
export type ApiRunResponse = ApiSchema<"RunResponse">;
export type ApiRunListResponse = ApiSchema<"RunListResponse">;
export type ApiRunSummaryListResponse = ApiSchema<"RunSummaryListResponse">;
export type ApiRunSummaryResponse = ApiSchema<"RunSummaryResponse">;
export type ApiRunEstimate = ApiSchema<"RunEstimate">;
export type ApiRunCancelResponse = ApiSchema<"RunCancelResponse">;
export type ApiRunActionResponse = ApiSchema<"RunActionResponse">;
export type ApiRunResultResponse = ApiSchema<"RunResultResponse">;
export type ApiExportBundle = ApiSchema<"ExportBundle">;
export type ApiRunEventResponse = ApiSchema<"RunEventResponse">;
export type ApiRunEventListResponse = ApiSchema<"RunEventListResponse">;
export type ApiRunValidationRequest = ApiSchema<"RunValidationRequest">;
export type ApiRunValidationResponse = ApiSchema<"RunValidationResponse">;
export type ApiRunValidationErrorDetail = ApiSchema<"RunValidationErrorDetail">;
export type ApiRunRestartRequest = ApiSchema<"RunRestartRequest">;

export type ApiMoleculeCreate = ApiSchema<"MoleculeCreate">;
export type ApiMoleculeUpdate = ApiSchema<"MoleculeUpdate">;
export type ApiMoleculeResponse = ApiSchema<"MoleculeResponse">;
export type ApiMoleculeListResponse = ApiSchema<"MoleculeListResponse">;
export type ApiMoleculeSummaryListResponse = ApiSchema<"MoleculeSummaryListResponse">;
export type ApiMoleculeImportPreviewResponse = ApiSchema<"MoleculeImportPreviewResponse">;
export type ApiBasisSetListResponse = ApiSchema<"BasisSetListResponse">;
export type ApiPubChemImportRequest = ApiSchema<"PubChemImportRequest">;
export type ApiPubChemSearchResponse = ApiSchema<"PubChemSearchResponse">;
export type ApiXYZImportRequest = ApiSchema<"XYZImportRequest">;
export type ApiXYZPreviewRequest = ApiSchema<"XYZPreviewRequest">;

export type ApiBenchmarkRunCreate = ApiSchema<"BenchmarkRunCreate">;
export type ApiBenchmarkRunUpdate = ApiSchema<"BenchmarkRunUpdate">;
export type ApiBenchmarkRunResponse = ApiSchema<"BenchmarkRunResponse">;
export type ApiBenchmarkRunListResponse = ApiSchema<"BenchmarkRunListResponse">;
export type ApiBenchmarkRunSummaryResponse = ApiSchema<"BenchmarkRunSummaryResponse">;
export type ApiBenchmarkRunSummaryListResponse = ApiSchema<"BenchmarkRunSummaryListResponse">;

export type ApiIbmCredentialProfileCreate = ApiSchema<"IbmCredentialProfileCreate">;
export type ApiIbmCredentialProfileUpdate = ApiSchema<"IbmCredentialProfileUpdate">;
export type ApiIbmCredentialProfileResponse = ApiSchema<"IbmCredentialProfileResponse">;
export type ApiIbmCredentialProfileListResponse = ApiSchema<"IbmCredentialProfileListResponse">;
export type ApiIbmCredentialProfileTestResponse = ApiSchema<"IbmCredentialProfileTestResponse">;

export type ApiBackendListResponse = ApiSchema<"BackendListResponse">;
export type ApiTranspilePreviewRequest = ApiSchema<"TranspilePreviewRequest">;
export type ApiTranspilePreviewResponse = ApiSchema<"TranspilePreviewResponse">;
export type ApiStatusResponse = ApiSchema<"StatusResponse">;

export type ConfigChoiceMetadata = Required<components["schemas"]["ConfigChoiceMetadata"]>;
export type EasyGoalPresetMetadata = Required<components["schemas"]["EasyGoalPresetMetadata"]>;

type GeneratedRunConfigMetadataResponse = components["schemas"]["RunConfigMetadataResponse"];

export type RunConfigMetadataResponse = Omit<
  Required<GeneratedRunConfigMetadataResponse>,
  "ansatzes" | "optimizers" | "recommendations"
> & {
  ansatzes: ConfigChoiceMetadata[];
  optimizers: ConfigChoiceMetadata[];
  recommendations?: GeneratedRunConfigMetadataResponse["recommendations"];
};

type GeneratedGetRunConfigMetadataResponse =
  operations["get_config_metadata_api_runs_config_metadata_get"]["responses"][200]["content"]["application/json"];

export type GetRunConfigMetadataResponse =
  GeneratedGetRunConfigMetadataResponse extends GeneratedRunConfigMetadataResponse
    ? RunConfigMetadataResponse
    : never;

export type RunConfigMetadataPath = paths["/api/runs/config-metadata"];
