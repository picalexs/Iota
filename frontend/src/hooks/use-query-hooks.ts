import { QueryClient, useQuery, useQueryClient } from "@tanstack/react-query";
import type {
  RunListResponse,
  RunSummaryListResponse,
  MoleculeListResponse,
  MoleculeSummaryListResponse,
  MoleculeResponse,
  RunResponse,
  RunListParams,
  MoleculeListParams,
  RunConfigMetadataResponse,
  UUID,
} from "@/types/run";
import type { BenchmarkRunListResponse, BenchmarkRunSummaryListResponse } from "@/api/benchmarks";
import { fetchAllPages } from "./pagination";
import { DEFAULT_QUERY_OPTIONS, keepPreviousQueryData } from "./query-options";
import { benchmarkKeys, configKeys, moleculeKeys, runKeys } from "./query-keys";

export function useRunConfigMetadata(fetcher: () => Promise<RunConfigMetadataResponse>) {
  return useQuery({
    queryKey: configKeys.metadata,
    queryFn: fetcher,
    ...DEFAULT_QUERY_OPTIONS,
  });
}

export function useListRuns(
  fetcher: (params?: RunListParams) => Promise<RunListResponse>,
  params?: RunListParams,
) {
  return useQuery({
    queryKey: runKeys.list(params),
    queryFn: () => fetcher(params),
    ...DEFAULT_QUERY_OPTIONS,
  });
}

export function useListRunSummaries(
  fetcher: (params?: RunListParams) => Promise<RunSummaryListResponse>,
  params?: RunListParams,
) {
  return useQuery({
    queryKey: runKeys.summaries(params),
    queryFn: () => fetcher(params),
    ...DEFAULT_QUERY_OPTIONS,
    placeholderData: keepPreviousQueryData,
  });
}

export function useAllRunSummaries(
  fetcher: (params?: RunListParams) => Promise<RunSummaryListResponse>,
) {
  return useQuery({
    queryKey: runKeys.allSummaries,
    queryFn: () =>
      fetchAllPages(fetcher, {
        pageSize: 50,
        getKey: (run) => run.id,
      }),
    ...DEFAULT_QUERY_OPTIONS,
    placeholderData: keepPreviousQueryData,
  });
}

export function useListBenchmarkRuns(
  fetcher: (params?: { limit?: number; offset?: number }) => Promise<BenchmarkRunListResponse>,
  params?: { limit?: number; offset?: number },
) {
  return useQuery({
    queryKey: benchmarkKeys.list(params),
    queryFn: () => fetcher(params),
    ...DEFAULT_QUERY_OPTIONS,
    refetchOnMount: "always",
    placeholderData: keepPreviousQueryData,
  });
}

export function useListBenchmarkRunSummaries<TParams extends object>(
  fetcher: (params?: TParams) => Promise<BenchmarkRunSummaryListResponse>,
  params?: TParams,
) {
  return useQuery({
    queryKey: benchmarkKeys.summaryList(params),
    queryFn: () => fetcher(params),
    ...DEFAULT_QUERY_OPTIONS,
    refetchOnMount: "always",
    refetchInterval: (query) =>
      query.state.data?.items.some((summary) => summary.activeCount > 0) ? 3000 : false,
    placeholderData: keepPreviousQueryData,
  });
}

export function useFetchMolecules(
  fetcher: (params: MoleculeListParams) => Promise<MoleculeListResponse>,
  params: MoleculeListParams,
) {
  return useQuery({
    queryKey: moleculeKeys.list(params),
    queryFn: () => fetcher(params),
    ...DEFAULT_QUERY_OPTIONS,
    placeholderData: keepPreviousQueryData,
  });
}

// Summary rows keep the molecule library fast and avoid full coordinate payloads.
export function useFetchMoleculeSummaries(
  fetcher: (params: MoleculeListParams) => Promise<MoleculeSummaryListResponse>,
  params: MoleculeListParams,
) {
  return useQuery({
    queryKey: moleculeKeys.summaries(params),
    queryFn: () => fetcher(params),
    ...DEFAULT_QUERY_OPTIONS,
    placeholderData: keepPreviousQueryData,
  });
}

// Selector UIs need the whole catalog, so this hook walks the paginated API.
export function useAllMolecules(
  fetcher: (params: MoleculeListParams) => Promise<MoleculeListResponse>,
) {
  return useQuery({
    queryKey: moleculeKeys.allMolecules,
    queryFn: () =>
      fetchAllPages(fetcher, {
        pageSize: 200,
        getKey: (molecule) => molecule.id,
      }),
    ...DEFAULT_QUERY_OPTIONS,
  });
}

export function useAllMoleculeSummaries(
  fetcher: (params: MoleculeListParams) => Promise<MoleculeSummaryListResponse>,
) {
  return useQuery({
    queryKey: moleculeKeys.allSummaries,
    queryFn: () =>
      fetchAllPages(fetcher, {
        pageSize: 50,
        getKey: (molecule) => molecule.id,
      }),
    ...DEFAULT_QUERY_OPTIONS,
    placeholderData: keepPreviousQueryData,
  });
}

export function useGetRun(fetcher: (id: string) => Promise<RunResponse>, runId: UUID | null) {
  return useQuery({
    queryKey: runKeys.detail(runId),
    queryFn: () => (runId ? fetcher(runId) : Promise.reject(new Error("Run ID is required"))),
    enabled: Boolean(runId),
    ...DEFAULT_QUERY_OPTIONS,
  });
}

export function useGetMolecule(
  fetcher: (id: string) => Promise<MoleculeResponse>,
  moleculeId: UUID | null,
) {
  return useQuery({
    queryKey: moleculeKeys.detail(moleculeId),
    queryFn: () =>
      moleculeId ? fetcher(moleculeId) : Promise.reject(new Error("Molecule ID is required")),
    enabled: Boolean(moleculeId),
    ...DEFAULT_QUERY_OPTIONS,
  });
}

export function invalidateRunsQueries(queryClient: QueryClient) {
  return Promise.all([
    queryClient.invalidateQueries({
      queryKey: runKeys.listPrefix,
      refetchType: "all",
    }),
    queryClient.invalidateQueries({
      queryKey: runKeys.summariesPrefix,
      refetchType: "all",
    }),
  ]);
}

export function invalidateBenchmarkRunQueries(queryClient: QueryClient) {
  return Promise.all([
    queryClient.invalidateQueries({
      queryKey: benchmarkKeys.listPrefix,
      refetchType: "all",
    }),
    queryClient.invalidateQueries({
      queryKey: benchmarkKeys.summaryListPrefix,
      refetchType: "all",
    }),
  ]);
}

export function invalidateMoleculesQueries(queryClient: QueryClient) {
  return Promise.all([
    queryClient.invalidateQueries({
      queryKey: moleculeKeys.listPrefix,
    }),
    queryClient.invalidateQueries({
      queryKey: moleculeKeys.summariesPrefix,
    }),
  ]);
}

export function useInvalidateRunsList() {
  const queryClient = useQueryClient();
  return () => invalidateRunsQueries(queryClient);
}

export function useInvalidateMoleculesList() {
  const queryClient = useQueryClient();
  return () => invalidateMoleculesQueries(queryClient);
}

export function useInvalidateRun() {
  const queryClient = useQueryClient();
  return (runId: UUID) => {
    return queryClient.invalidateQueries({
      queryKey: runKeys.detail(runId),
    });
  };
}

export function useClearAllQueries() {
  const queryClient = useQueryClient();
  return () => {
    queryClient.clear();
  };
}
