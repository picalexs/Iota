import { useMemo } from "react";
import { useNavigate, useSearch } from "@tanstack/react-router";

import { runtimeSecondsFromRun } from "@/lib/run-runtime";
import {
  BACKEND_TARGETS,
  RUN_ALGORITHMS,
  RUN_STATUSES,
  type BackendTarget,
  type UUID,
  type RunAlgorithm,
  type RunStatus,
  type RunSummaryResponse,
} from "@/types/run";

export type SortField =
  | "created_at"
  | "updated_at"
  | "status"
  | "molecule"
  | "algorithm"
  | "backend"
  | "runtime";
export type SortOrder = "asc" | "desc";

export const ALL_METHODS: RunAlgorithm[] = [...RUN_ALGORITHMS];
export const ALL_BACKENDS: BackendTarget[] = [...BACKEND_TARGETS];
export const ALL_STATUSES: RunStatus[] = [...RUN_STATUSES];

const ACTIVE_RUN_STATUSES = new Set([
  "CREATED",
  "QUEUED",
  "RUNNING",
  "PAUSING",
  "SUBMITTED_TO_IBM",
]);
const EMPTY_RUN_STATUSES: RunStatus[] = [];
const EMPTY_MOLECULE_IDS: string[] = [];
const EMPTY_RUN_METHODS: RunAlgorithm[] = [];

interface UseRunsListFilterArgs {
  rawRuns: RunSummaryResponse[];
  moleculeItems: {
    id: UUID;
    name: string;
  }[];
}

interface RunListFilters {
  statuses: RunStatus[];
  moleculeIds: string[];
  methods: RunAlgorithm[];
  backendTarget?: BackendTarget;
  chemicalAccurate?: boolean;
}

interface RunSortOptions {
  field: SortField;
  order: SortOrder;
  moleculeMap: Map<UUID, string>;
}

function toggledValue<T>(values: T[], value: T): T[] {
  return values.includes(value) ? values.filter((entry) => entry !== value) : [...values, value];
}

function runMatchesFilters(run: RunSummaryResponse, filters: RunListFilters): boolean {
  return (
    (filters.statuses.length === 0 || filters.statuses.includes(run.status)) &&
    (filters.moleculeIds.length === 0 || filters.moleculeIds.includes(run.molecule_id)) &&
    (filters.methods.length === 0 ||
      (run.algorithm != null && filters.methods.includes(run.algorithm))) &&
    (filters.backendTarget === undefined || run.backend_target === filters.backendTarget) &&
    (filters.chemicalAccurate === undefined || run.chemical_accurate === filters.chemicalAccurate)
  );
}

function stringSortValue(
  run: RunSummaryResponse,
  field: SortField,
  moleculeMap: Map<UUID, string>,
): string {
  switch (field) {
    case "algorithm":
      return run.algorithm ?? "";
    case "backend":
      return run.backend_target ?? "";
    case "updated_at":
      return run.updated_at;
    case "status":
      return run.status;
    case "molecule":
      return moleculeMap.get(run.molecule_id) ?? run.molecule_id;
    default:
      return run.created_at;
  }
}

function compareRuntime(left: RunSummaryResponse, right: RunSummaryResponse, order: SortOrder) {
  const leftRuntime = runtimeSecondsFromRun(left);
  const rightRuntime = runtimeSecondsFromRun(right);
  if (leftRuntime == null && rightRuntime == null) return 0;
  if (leftRuntime == null) return 1;
  if (rightRuntime == null) return -1;
  return order === "asc" ? leftRuntime - rightRuntime : rightRuntime - leftRuntime;
}

function compareRuns(left: RunSummaryResponse, right: RunSummaryResponse, options: RunSortOptions) {
  if (options.field === "runtime") {
    return compareRuntime(left, right, options.order);
  }

  const leftValue = stringSortValue(left, options.field, options.moleculeMap);
  const rightValue = stringSortValue(right, options.field, options.moleculeMap);
  return options.order === "asc"
    ? leftValue.localeCompare(rightValue)
    : rightValue.localeCompare(leftValue);
}

function filteredAndSortedRuns(
  rawRuns: RunSummaryResponse[],
  filters: RunListFilters,
  sortOptions: RunSortOptions,
): RunSummaryResponse[] {
  const items = rawRuns.filter((run) => runMatchesFilters(run, filters));
  if (sortOptions.field === "created_at" && sortOptions.order === "desc") {
    return items;
  }
  return items.sort((left, right) => compareRuns(left, right, sortOptions));
}

export function useRunsListFilter({ rawRuns, moleculeItems }: UseRunsListFilterArgs) {
  const navigate = useNavigate();
  const search = useSearch({ from: "/runs" });
  const filterStatuses: RunStatus[] = search.statuses ?? EMPTY_RUN_STATUSES;
  const filterMoleculeIds: string[] = search.molecule_ids ?? EMPTY_MOLECULE_IDS;
  const filterMethods: RunAlgorithm[] = search.methods ?? EMPTY_RUN_METHODS;
  const filterBackendTarget: BackendTarget | undefined = search.backend_target;
  const filterChemicalAccurate: boolean | undefined = search.chemical_accurate;
  const sortField: SortField = search.sort ?? "created_at";
  const sortOrder: SortOrder = search.order ?? "desc";
  const page = Math.max(1, search.page ?? 1);

  const moleculeMap = useMemo(
    () => new Map<UUID, string>(moleculeItems.map((m) => [m.id, m.name])),
    [moleculeItems],
  );

  const runs = useMemo(() => {
    return filteredAndSortedRuns(
      rawRuns,
      {
        statuses: filterStatuses,
        moleculeIds: filterMoleculeIds,
        methods: filterMethods,
        backendTarget: filterBackendTarget,
        chemicalAccurate: filterChemicalAccurate,
      },
      { field: sortField, order: sortOrder, moleculeMap },
    );
  }, [
    rawRuns,
    filterStatuses,
    filterMoleculeIds,
    filterMethods,
    filterBackendTarget,
    filterChemicalAccurate,
    sortField,
    sortOrder,
    moleculeMap,
  ]);

  const hasActiveRuns = rawRuns.some((run) => ACTIVE_RUN_STATUSES.has(run.status));
  const hasActiveFilters =
    filterStatuses.length > 0 ||
    filterMoleculeIds.length > 0 ||
    filterMethods.length > 0 ||
    filterBackendTarget !== undefined ||
    filterChemicalAccurate !== undefined;

  function handleSort(field: SortField) {
    const nextOrder = sortField === field && sortOrder === "asc" ? "desc" : "asc";
    void navigate({
      to: "/runs",
      search: (prev) => ({
        sort: field,
        order: sortField === field ? nextOrder : "desc",
        page: prev.page,
        statuses: prev.statuses,
        molecule_ids: prev.molecule_ids,
        methods: prev.methods,
        backend_target: prev.backend_target,
        chemical_accurate: prev.chemical_accurate,
      }),
    });
  }

  function toggleStatus(status: RunStatus) {
    const next = toggledValue(filterStatuses, status);
    void navigate({
      to: "/runs",
      search: (prev) => ({
        sort: prev.sort as SortField | undefined,
        order: prev.order,
        page: undefined,
        molecule_ids: prev.molecule_ids,
        methods: prev.methods,
        backend_target: prev.backend_target,
        chemical_accurate: prev.chemical_accurate,
        statuses: next.length > 0 ? next : undefined,
      }),
    });
  }

  function toggleMolecule(id: string) {
    const next = toggledValue(filterMoleculeIds, id);
    void navigate({
      to: "/runs",
      search: (prev) => ({
        sort: prev.sort as SortField | undefined,
        order: prev.order,
        page: undefined,
        statuses: prev.statuses,
        methods: prev.methods,
        backend_target: prev.backend_target,
        chemical_accurate: prev.chemical_accurate,
        molecule_ids: next.length > 0 ? next : undefined,
      }),
    });
  }

  function toggleMethod(method: RunAlgorithm) {
    const next = toggledValue(filterMethods, method);
    void navigate({
      to: "/runs",
      search: (prev) => ({
        sort: prev.sort as SortField | undefined,
        order: prev.order,
        page: undefined,
        statuses: prev.statuses,
        molecule_ids: prev.molecule_ids,
        backend_target: prev.backend_target,
        chemical_accurate: prev.chemical_accurate,
        methods: next.length > 0 ? next : undefined,
      }),
    });
  }

  function toggleBackendTarget(backendTarget: BackendTarget) {
    void navigate({
      to: "/runs",
      search: (prev) => ({
        sort: prev.sort as SortField | undefined,
        order: prev.order,
        page: undefined,
        statuses: prev.statuses,
        molecule_ids: prev.molecule_ids,
        methods: prev.methods,
        chemical_accurate: prev.chemical_accurate,
        backend_target: prev.backend_target === backendTarget ? undefined : backendTarget,
      }),
    });
  }

  function toggleChemicalAccurate(nextChemicalAccurate: boolean) {
    void navigate({
      to: "/runs",
      search: (prev) => ({
        sort: prev.sort as SortField | undefined,
        order: prev.order,
        page: undefined,
        statuses: prev.statuses,
        molecule_ids: prev.molecule_ids,
        methods: prev.methods,
        backend_target: prev.backend_target,
        chemical_accurate:
          prev.chemical_accurate === nextChemicalAccurate ? undefined : nextChemicalAccurate,
      }),
    });
  }

  function clearFilters() {
    void navigate({
      to: "/runs",
      search: (prev) => ({
        sort: prev.sort as SortField | undefined,
        order: prev.order,
        page: undefined,
        statuses: undefined,
        molecule_ids: undefined,
        methods: undefined,
        backend_target: undefined,
        chemical_accurate: undefined,
      }),
    });
  }

  function goToPage(nextPage: number) {
    void navigate({
      to: "/runs",
      search: (prev) => ({
        sort: prev.sort as SortField | undefined,
        order: prev.order,
        page: nextPage > 1 ? nextPage : undefined,
        statuses: prev.statuses,
        molecule_ids: prev.molecule_ids,
        methods: prev.methods,
        backend_target: prev.backend_target,
        chemical_accurate: prev.chemical_accurate,
      }),
    });
  }

  return {
    filterStatuses,
    filterMoleculeIds,
    filterMethods,
    filterBackendTarget,
    filterChemicalAccurate,
    sortField,
    sortOrder,
    page,
    moleculeMap,
    runs,
    hasActiveRuns,
    hasActiveFilters,
    handleSort,
    toggleStatus,
    toggleMolecule,
    toggleMethod,
    toggleBackendTarget,
    toggleChemicalAccurate,
    clearFilters,
    goToPage,
  };
}
