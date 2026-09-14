import {
  createElement as h,
  lazy,
  Suspense,
  useEffect,
  useState,
  type ComponentType,
  type ReactNode,
} from "react";
import { useRouterState } from "@tanstack/react-router";

import { ErrorBoundary } from "@/components/error-boundary";
import { MoleculeLoader } from "@/components/motion/molecule-loader";
import { Skeleton } from "@/components/ui/skeleton";

const loadHomePage = () => import("@/pages/home-page").then((m) => ({ default: m.HomePage }));
const loadMoleculesPage = () =>
  import("@/pages/molecules-page").then((m) => ({ default: m.MoleculesPage }));
const loadMoleculeDetailPage = () =>
  import("@/pages/molecule-detail-page").then((m) => ({ default: m.MoleculeDetailPage }));
const loadRunsListPage = () =>
  import("@/pages/runs-list-page").then((m) => ({ default: m.RunsListPage }));
const loadRunCreatePage = () =>
  import("@/pages/run-create-page").then((m) => ({ default: m.RunCreatePage }));
const loadRunDetailPage = () =>
  import("@/pages/run-detail-page").then((m) => ({ default: m.RunDetailPage }));
const loadHelpParametersPage = () =>
  import("@/pages/help-parameters-page").then((m) => ({ default: m.HelpParametersPage }));
const loadInfoHubPage = () =>
  import("@/pages/info/info-hub-page").then((m) => ({ default: m.InfoHubPage }));
const loadInfoAlgorithmsPage = () =>
  import("@/pages/info/info-algorithms-page").then((m) => ({ default: m.InfoAlgorithmsPage }));
const loadInfoComponentsPage = () =>
  import("@/pages/info/info-components-page").then((m) => ({ default: m.InfoComponentsPage }));
const loadInfoComponentDetailPage = () =>
  import("@/pages/info/info-component-detail-page").then((m) => ({
    default: m.InfoComponentDetailPage,
  }));
const loadInfoAlgorithmDetailPage = () =>
  import("@/pages/info/info-algorithm-detail-page").then((m) => ({
    default: m.InfoAlgorithmDetailPage,
  }));
const loadInfoBackendsPage = () =>
  import("@/pages/info/info-backends-page").then((m) => ({ default: m.InfoBackendsPage }));
const loadInfoBackendDetailPage = () =>
  import("@/pages/info/info-backend-detail-page").then((m) => ({
    default: m.InfoBackendDetailPage,
  }));
const loadInfoNoiseModelsPage = () =>
  import("@/pages/info/info-noise-models-page").then((m) => ({ default: m.InfoNoiseModelsPage }));
const loadInfoNoiseDetailPage = () =>
  import("@/pages/info/info-noise-detail-page").then((m) => ({
    default: m.InfoNoiseDetailPage,
  }));
const loadBenchmarkPage = () =>
  import("@/pages/benchmark-page").then((m) => ({ default: m.BenchmarkPage }));
const loadBenchmarkRunsPage = () =>
  import("@/pages/benchmark-runs-page").then((m) => ({ default: m.BenchmarkRunsPage }));
const loadSettingsPage = () =>
  import("@/pages/settings-page").then((m) => ({ default: m.SettingsPage }));

export const HomePage = lazy(loadHomePage);
export const MoleculesPage = lazy(loadMoleculesPage);
export const MoleculeDetailPage = lazy(loadMoleculeDetailPage);
export const RunsListPage = lazy(loadRunsListPage);
export const RunCreatePage = lazy(loadRunCreatePage);
export const RunDetailPage = lazy(loadRunDetailPage);
export const HelpParametersPage = lazy(loadHelpParametersPage);
export const InfoHubPage = lazy(loadInfoHubPage);
export const InfoAlgorithmsPage = lazy(loadInfoAlgorithmsPage);
export const InfoComponentsPage = lazy(loadInfoComponentsPage);
export const InfoComponentDetailPage = lazy(loadInfoComponentDetailPage);
export const InfoAlgorithmDetailPage = lazy(loadInfoAlgorithmDetailPage);
export const InfoBackendsPage = lazy(loadInfoBackendsPage);
export const InfoBackendDetailPage = lazy(loadInfoBackendDetailPage);
export const InfoNoiseModelsPage = lazy(loadInfoNoiseModelsPage);
export const InfoNoiseDetailPage = lazy(loadInfoNoiseDetailPage);
export const BenchmarkPage = lazy(loadBenchmarkPage);
export const BenchmarkRunsPage = lazy(loadBenchmarkRunsPage);
export const SettingsPage = lazy(loadSettingsPage);

export function preloadMoleculeDetailPageModule() {
  void loadMoleculeDetailPage();
}

const pagePreloaders: Partial<Record<string, () => Promise<{ default: ComponentType<object> }>>> = {
  "/": loadHomePage,
  "/molecules": loadMoleculesPage,
  "/runs": loadRunsListPage,
  "/runs/new": loadRunCreatePage,
  "/benchmark": loadBenchmarkPage,
  "/benchmarks": loadBenchmarkRunsPage,
  "/benchmarks/new": loadBenchmarkPage,
  "/info": loadInfoHubPage,
  "/settings": loadSettingsPage,
};

export function preloadPageModule(pathname: string) {
  pagePreloaders[pathname]?.().catch(() => undefined);
}

export function RouteLoadingFallback() {
  return h(
    "div",
    {
      role: "status",
      "aria-busy": true,
      "aria-label": "Loading page",
      className: "flex flex-col gap-4",
    },
    h(MoleculeLoader, { size: "sm" }),
    h(Skeleton, { className: "h-12 w-full rounded-md" }),
    h(
      "div",
      { className: "space-y-3" },
      h(Skeleton, { className: "h-4 w-full" }),
      h(Skeleton, { className: "h-4 w-3/4" }),
      h(Skeleton, { className: "h-4 w-1/2" }),
    ),
  );
}

export function DeferredSuspense({
  children,
  fallback,
}: {
  children: ReactNode;
  fallback: ReactNode;
}) {
  const [showFallback, setShowFallback] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setShowFallback(true), 50);
    return () => clearTimeout(timer);
  }, []);

  return h(Suspense, { fallback: showFallback ? fallback : null }, children);
}

export function LazyRoute({
  Component,
  SkeletonComponent = RouteLoadingFallback,
}: {
  Component: ComponentType<object>;
  SkeletonComponent?: ComponentType<object>;
}) {
  const pathname = useRouterState({ select: (state) => state.location.pathname });
  return h(ErrorBoundary, {
    resetKey: pathname,
    children: h(DeferredSuspense, {
      fallback: h(SkeletonComponent),
      children: h(Component),
    }),
  });
}
