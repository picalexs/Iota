import { Link, createRootRoute, createRoute } from "@tanstack/react-router";
import { createElement as h } from "react";

import { AppLayout } from "@/components/layout/app-layout";
import {
  BenchmarkRunsSkeleton,
  BenchmarkPageSkeleton,
  HelpParametersSkeleton,
  HomePageSkeleton,
  InfoDetailSkeleton,
  InfoListSkeleton,
  MoleculeDetailSkeleton,
  MoleculesListSkeleton,
  RunCreateSkeleton,
  RunDetailSkeleton,
  RunsListSkeleton,
  SettingsPageSkeleton,
} from "@/components/ui/route-skeleton-variants";
import {
  isBackendTarget,
  type BackendTarget,
  type RunAlgorithm,
  type RunStatus,
} from "@/types/run";
import { getRouteMarkName, markRoute } from "@/utils/web-vitals";

import {
  BenchmarkPage,
  BenchmarkRunsPage,
  HelpParametersPage,
  HomePage,
  InfoAlgorithmDetailPage,
  InfoAlgorithmsPage,
  InfoBackendDetailPage,
  InfoBackendsPage,
  InfoComponentDetailPage,
  InfoComponentsPage,
  InfoHubPage,
  InfoNoiseDetailPage,
  InfoNoiseModelsPage,
  LazyRoute,
  MoleculeDetailPage,
  MoleculesPage,
  RunCreatePage,
  RunDetailPage,
  RunsListPage,
  SettingsPage,
} from "./lazy-pages";

type RunsSearch = {
  statuses?: RunStatus[];
  molecule_ids?: string[];
  methods?: RunAlgorithm[];
  backend_target?: BackendTarget;
  chemical_accurate?: boolean;
  sort?: "created_at" | "updated_at" | "status" | "molecule" | "algorithm" | "backend" | "runtime";
  order?: "asc" | "desc";
  page?: number;
};

const RUN_SORT_FIELDS = new Set<RunsSearch["sort"]>([
  "created_at",
  "updated_at",
  "status",
  "molecule",
  "algorithm",
  "backend",
  "runtime",
]);

function nonEmptyStringList(value: unknown): string[] | undefined {
  if (Array.isArray(value) && value.length > 0) {
    return value.map(String);
  }
  if (typeof value === "string" && value) {
    return [value];
  }
  return undefined;
}

function parseRunsStringList(
  search: Record<string, unknown>,
  primaryKey: string,
  legacyKey: string,
): string[] | undefined {
  return nonEmptyStringList(search[primaryKey]) ?? nonEmptyStringList(search[legacyKey]);
}

function parseRunBackendTarget(value: unknown): BackendTarget | undefined {
  return isBackendTarget(value) ? value : undefined;
}

function parseChemicalAccurate(value: unknown): boolean | undefined {
  if (typeof value === "boolean") {
    return value;
  }
  if (value === "true") {
    return true;
  }
  if (value === "false") {
    return false;
  }
  return undefined;
}

function parseRunsSort(value: unknown): RunsSearch["sort"] {
  return typeof value === "string" && RUN_SORT_FIELDS.has(value as RunsSearch["sort"])
    ? (value as RunsSearch["sort"])
    : undefined;
}

function parseRunsOrder(value: unknown): RunsSearch["order"] {
  return value === "asc" || value === "desc" ? value : undefined;
}

export function parseRunsSearch(search: Record<string, unknown>): RunsSearch {
  return {
    statuses: parseRunsStringList(search, "statuses", "status") as RunStatus[] | undefined,
    molecule_ids: parseRunsStringList(search, "molecule_ids", "molecule_id"),
    methods: parseRunsStringList(search, "methods", "method") as RunAlgorithm[] | undefined,
    backend_target: parseRunBackendTarget(search.backend_target),
    chemical_accurate: parseChemicalAccurate(search.chemical_accurate),
    sort: parseRunsSort(search.sort),
    order: parseRunsOrder(search.order),
    page: typeof search.page === "number" ? search.page : undefined,
  };
}

export function NotFoundPage() {
  return h(
    "div",
    { className: "flex flex-col items-center justify-center gap-4 py-16 text-center" },
    h("h1", { className: "text-2xl font-semibold" }, "Page not found"),
    h("p", { className: "text-muted-foreground text-sm" }, "This page is coming soon."),
    h(
      Link,
      { to: "/", className: "text-sm text-primary hover:underline" },
      "\u2190 Back to Dashboard",
    ),
  );
}

const rootRoute = createRootRoute({
  component: AppLayout,
  notFoundComponent: NotFoundPage,
  beforeLoad: ({ location }) => {
    const routeName = getRouteMarkName(location.pathname);
    markRoute(routeName, "start");
  },
});

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: () => h(LazyRoute, { Component: HomePage, SkeletonComponent: HomePageSkeleton }),
});

const moleculesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/molecules",
  validateSearch: (
    search: Record<string, unknown>,
  ): {
    q?: string;
    page?: number;
    sort?: "name" | "atoms";
    order?: "asc" | "desc";
  } => {
    const sort = search.sort === "name" || search.sort === "atoms" ? search.sort : undefined;
    return {
      q: typeof search.q === "string" ? search.q : undefined,
      page: typeof search.page === "number" ? search.page : undefined,
      sort,
      order: typeof search.order === "string" ? (search.order as "asc" | "desc") : undefined,
    };
  },
  component: () =>
    h(LazyRoute, { Component: MoleculesPage, SkeletonComponent: MoleculesListSkeleton }),
});

const moleculeDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/molecules/$moleculeId",
  component: () =>
    h(LazyRoute, { Component: MoleculeDetailPage, SkeletonComponent: MoleculeDetailSkeleton }),
});

const runsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/runs",
  validateSearch: parseRunsSearch,
  component: () => h(LazyRoute, { Component: RunsListPage, SkeletonComponent: RunsListSkeleton }),
});

const runCreateRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/runs/new",
  validateSearch: (
    search: Record<string, unknown>,
  ): {
    molecule_id?: string;
  } => ({
    molecule_id: typeof search.molecule_id === "string" ? search.molecule_id : undefined,
  }),
  component: () => h(LazyRoute, { Component: RunCreatePage, SkeletonComponent: RunCreateSkeleton }),
});

const runDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/runs/$runId",
  component: () => h(LazyRoute, { Component: RunDetailPage, SkeletonComponent: RunDetailSkeleton }),
});

const helpParametersRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/help/parameters",
  component: () =>
    h(LazyRoute, { Component: HelpParametersPage, SkeletonComponent: HelpParametersSkeleton }),
});

const infoRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/info",
  component: () => h(LazyRoute, { Component: InfoHubPage, SkeletonComponent: InfoListSkeleton }),
});

const infoAlgorithmsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/info/algorithms",
  component: () =>
    h(LazyRoute, { Component: InfoAlgorithmsPage, SkeletonComponent: InfoListSkeleton }),
});

const infoComponentsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/info/components",
  component: () =>
    h(LazyRoute, { Component: InfoComponentsPage, SkeletonComponent: InfoListSkeleton }),
});

const infoComponentDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/info/components/$componentId",
  component: () =>
    h(LazyRoute, { Component: InfoComponentDetailPage, SkeletonComponent: InfoDetailSkeleton }),
});

const infoAlgorithmDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/info/algorithms/$algorithmId",
  component: () =>
    h(LazyRoute, { Component: InfoAlgorithmDetailPage, SkeletonComponent: InfoDetailSkeleton }),
});

const infoBackendsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/info/backends",
  component: () =>
    h(LazyRoute, { Component: InfoBackendsPage, SkeletonComponent: InfoListSkeleton }),
});

const infoBackendDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/info/backends/$backendId",
  component: () =>
    h(LazyRoute, { Component: InfoBackendDetailPage, SkeletonComponent: InfoDetailSkeleton }),
});

const infoNoiseModelsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/info/noise-models",
  component: () =>
    h(LazyRoute, { Component: InfoNoiseModelsPage, SkeletonComponent: InfoListSkeleton }),
});

const infoNoiseDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/info/noise-models/$noiseModelId",
  component: () =>
    h(LazyRoute, { Component: InfoNoiseDetailPage, SkeletonComponent: InfoDetailSkeleton }),
});

const benchmarkRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/benchmarks",
  component: () =>
    h(LazyRoute, { Component: BenchmarkRunsPage, SkeletonComponent: BenchmarkRunsSkeleton }),
});

const benchmarkLegacyRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/benchmark",
  component: () =>
    h(LazyRoute, { Component: BenchmarkPage, SkeletonComponent: BenchmarkPageSkeleton }),
});

const benchmarkNewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/benchmarks/new",
  component: () =>
    h(LazyRoute, { Component: BenchmarkPage, SkeletonComponent: BenchmarkPageSkeleton }),
});

const benchmarkDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/benchmarks/$benchmarkId",
  component: () =>
    h(LazyRoute, { Component: BenchmarkPage, SkeletonComponent: BenchmarkPageSkeleton }),
});

const settingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/settings",
  component: () =>
    h(LazyRoute, { Component: SettingsPage, SkeletonComponent: SettingsPageSkeleton }),
});

export const routeTree = rootRoute.addChildren([
  indexRoute,
  moleculesRoute,
  moleculeDetailRoute,
  runsRoute,
  runCreateRoute,
  runDetailRoute,
  helpParametersRoute,
  infoRoute,
  infoAlgorithmsRoute,
  infoComponentsRoute,
  infoComponentDetailRoute,
  infoAlgorithmDetailRoute,
  infoBackendsRoute,
  infoBackendDetailRoute,
  infoNoiseModelsRoute,
  infoNoiseDetailRoute,
  benchmarkRoute,
  benchmarkLegacyRoute,
  benchmarkNewRoute,
  benchmarkDetailRoute,
  settingsRoute,
]);
