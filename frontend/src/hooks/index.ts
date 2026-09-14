import {
  useListRuns as useListRunsBase,
  useListRunSummaries as useListRunSummariesBase,
  useAllRunSummaries as useAllRunSummariesBase,
  useAllMoleculeSummaries as useAllMoleculeSummariesBase,
  useAllMolecules as useAllMoleculesBase,
  useFetchMoleculeSummaries as useFetchMoleculeSummariesBase,
  useFetchMolecules as useFetchMoleculesBase,
  useGetMolecule as useGetMoleculeBase,
  useGetRun as useGetRunBase,
} from "./use-query-hooks";
import {
  listRuns as apiListRuns,
  listRunSummaries as apiListRunSummaries,
  getRun as apiGetRun,
} from "@/api/runs";
import {
  fetchMoleculeSummaries as apiFetchMoleculeSummaries,
  fetchMolecules as apiFetchMolecules,
  getMolecule as apiGetMolecule,
} from "@/api/molecules";
import type { RunListParams, MoleculeListParams, UUID } from "@/types/run";

export function useListRuns(params?: RunListParams) {
  return useListRunsBase(apiListRuns, params);
}

export function useListRunSummaries(params?: RunListParams) {
  return useListRunSummariesBase(apiListRunSummaries, params);
}

export function useAllRunSummaries() {
  return useAllRunSummariesBase(apiListRunSummaries);
}

export function useAllMoleculeSummaries() {
  return useAllMoleculeSummariesBase(apiFetchMoleculeSummaries);
}

export function useFetchMolecules(params: MoleculeListParams) {
  return useFetchMoleculesBase(apiFetchMolecules, params);
}

export function useFetchMoleculeSummaries(params: MoleculeListParams) {
  return useFetchMoleculeSummariesBase(apiFetchMoleculeSummaries, params);
}

export function useAllMolecules() {
  return useAllMoleculesBase(apiFetchMolecules);
}

export function useGetRun(runId: UUID | null) {
  return useGetRunBase(apiGetRun, runId);
}

export function useGetMolecule(moleculeId: UUID | null) {
  return useGetMoleculeBase(apiGetMolecule, moleculeId);
}

export {
  useRunConfigMetadata,
  useInvalidateRunsList,
  useInvalidateMoleculesList,
  useInvalidateRun,
} from "./use-query-hooks";
