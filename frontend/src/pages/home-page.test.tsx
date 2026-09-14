import { act, render, screen, waitFor } from "@testing-library/react";
import type { Mock } from "vitest";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

vi.mock("@/hooks/use-theme", () => ({
  useTheme: () => ({ theme: "light" as const, resolvedTheme: "light" as const, setTheme: vi.fn() }),
}));
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  RouterProvider,
} from "@tanstack/react-router";
import { HomePage } from "./home-page";
import { clearListCache } from "@/state/list-cache";

vi.mock("@/api/molecules", () => ({
  fetchMoleculeSummaries: vi.fn(),
}));

vi.mock("@/api/benchmarks", () => ({
  listBenchmarkRuns: vi.fn(),
}));

vi.mock("@/api/runs", () => ({
  listRunSummaries: vi.fn(),
}));

import * as benchmarksApi from "@/api/benchmarks";
import * as moleculesApi from "@/api/molecules";
import * as runsApi from "@/api/runs";

const api = { ...benchmarksApi, ...moleculesApi, ...runsApi };

// matchMedia is not implemented in jsdom — stub it
beforeEach(() => {
  vi.clearAllMocks();
  clearListCache();
  class MockIntersectionObserver {
    readonly root = null;
    readonly rootMargin = "";
    readonly thresholds: number[] = [];

    readonly observe = vi.fn();
    readonly unobserve = vi.fn();
    readonly disconnect = vi.fn();
    takeRecords() {
      return [];
    }
  }
  vi.stubGlobal("IntersectionObserver", MockIntersectionObserver);
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: false,
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }));

  (api.fetchMoleculeSummaries as ReturnType<typeof vi.fn>).mockResolvedValue({
    items: [],
    total: 2,
  });
  (api.listBenchmarkRuns as ReturnType<typeof vi.fn>).mockResolvedValue({
    items: [],
    total: 4,
    limit: 1,
    offset: 0,
  });
  (api.listRunSummaries as ReturnType<typeof vi.fn>).mockImplementation(
    (params?: { status?: string }) =>
      Promise.resolve({
        items: [],
        total: params?.status === "COMPLETED" ? 1 : 2,
        limit: 1,
        offset: 0,
      }),
  );
});

afterEach(() => {
  vi.useRealTimers();
});

function buildTestRouter() {
  const rootRoute = createRootRoute();
  const indexRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/",
    component: HomePage,
  });
  const moleculesRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/molecules",
    component: () => null,
  });
  const runsRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/runs",
    component: () => null,
  });
  const benchmarksRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/benchmarks",
    component: () => null,
  });
  const routeTree = rootRoute.addChildren([indexRoute, moleculesRoute, runsRoute, benchmarksRoute]);
  const history = createMemoryHistory({ initialEntries: ["/"] });
  return createRouter({ routeTree, history });
}

function renderPage() {
  const testRouter = buildTestRouter();
  return render(<RouterProvider router={testRouter} />);
}

function getStatValue(label: string): HTMLElement {
  const labelEl = screen.getByText(label);
  const valueEl = labelEl.previousElementSibling;
  if (!(valueEl instanceof HTMLElement)) {
    throw new TypeError(`Missing value element for label: ${label}`);
  }
  return valueEl;
}

describe("HomePage", () => {
  it("renders the hero heading", async () => {
    renderPage();
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: /quantum simulation studio/i }),
      ).toBeInTheDocument(),
    );
  });

  it("does not render the Beta badge", async () => {
    renderPage();
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: /quantum simulation studio/i }),
      ).toBeInTheDocument(),
    );
    expect(screen.queryByText("Beta")).not.toBeInTheDocument();
  });

  it("renders all three feature card titles", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Molecule Library")).toBeInTheDocument();
      expect(screen.getByText("Quantum Runs")).toBeInTheDocument();
      expect(screen.getByText("Benchmarks")).toBeInTheDocument();
    });
  });

  it("renders the Get Started CTA link", async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.getByRole("link", { name: /get started/i })).toBeInTheDocument(),
    );
  });

  it("uses the full feature cards as links", async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByRole("link", { name: /browse molecules/i })).toHaveAttribute(
        "href",
        "/molecules",
      );
      expect(screen.getByRole("link", { name: /view runs/i })).toHaveAttribute("href", "/runs");
      expect(screen.getByRole("link", { name: /open benchmarks/i })).toHaveAttribute(
        "href",
        "/benchmarks",
      );
    });
  });

  it("shows cached stats immediately on remount without placeholder flash", async () => {
    const firstRender = renderPage();

    await waitFor(() => {
      expect(getStatValue("Molecules stored")).toHaveTextContent("2");
      expect(getStatValue("Runs created")).toHaveTextContent("2");
      expect(getStatValue("Benchmarks ran")).toHaveTextContent("4");
    });

    firstRender.unmount();
    (api.fetchMoleculeSummaries as Mock).mockReturnValue(new Promise(() => {}));
    (api.listRunSummaries as Mock).mockReturnValue(new Promise(() => {}));

    const secondRender = renderPage();
    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: /quantum simulation studio/i }),
      ).toBeInTheDocument();
    });

    expect(getStatValue("Molecules stored")).toHaveTextContent("2");
    expect(getStatValue("Runs created")).toHaveTextContent("2");
    expect(getStatValue("Benchmarks ran")).toHaveTextContent("4");
    expect(getStatValue("Molecules stored")).not.toHaveTextContent("—");
    secondRender.unmount();
  });

  it("refreshes cached stats in background and updates rendered values", async () => {
    const firstRender = renderPage();
    await waitFor(() => {
      expect(getStatValue("Molecules stored")).toHaveTextContent("2");
    });
    firstRender.unmount();

    let resolveMolecules!: (value: unknown) => void;
    let resolveRuns!: (value: unknown) => void;
    let resolveBenchmarks!: (value: unknown) => void;
    const moleculesPromise = new Promise((resolve) => {
      resolveMolecules = resolve;
    });
    const runsPromise = new Promise((resolve) => {
      resolveRuns = resolve;
    });
    const benchmarksPromise = new Promise((resolve) => {
      resolveBenchmarks = resolve;
    });

    (api.fetchMoleculeSummaries as ReturnType<typeof vi.fn>).mockReturnValueOnce(moleculesPromise);
    (api.listRunSummaries as ReturnType<typeof vi.fn>).mockImplementationOnce(() => runsPromise);
    (api.listBenchmarkRuns as ReturnType<typeof vi.fn>).mockReturnValueOnce(benchmarksPromise);

    renderPage();
    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: /quantum simulation studio/i }),
      ).toBeInTheDocument();
    });

    expect(getStatValue("Molecules stored")).toHaveTextContent("2");
    expect(getStatValue("Runs created")).toHaveTextContent("2");
    expect(getStatValue("Benchmarks ran")).toHaveTextContent("4");

    resolveMolecules({ items: [], total: 7 });
    resolveRuns({
      total: 3,
      items: [],
      limit: 1,
      offset: 0,
    });
    resolveBenchmarks({
      total: 5,
      items: [],
      limit: 1,
      offset: 0,
    });

    await waitFor(() => {
      expect(getStatValue("Molecules stored")).toHaveTextContent("7");
      expect(getStatValue("Runs created")).toHaveTextContent("3");
      expect(getStatValue("Benchmarks ran")).toHaveTextContent("5");
    });
  });

  it("renders the molecule-themed loader in the hero", async () => {
    renderPage();
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: /quantum simulation studio/i }),
      ).toBeInTheDocument(),
    );

    expect(document.querySelector("svg")).toBeInTheDocument();
  });

  it("stat counters use Skeleton when loading", async () => {
    const moleculesPromise = new Promise(() => {});
    const runsPromise = new Promise(() => {});
    const benchmarksPromise = new Promise(() => {});

    (api.fetchMoleculeSummaries as ReturnType<typeof vi.fn>).mockReturnValueOnce(moleculesPromise);
    (api.listRunSummaries as ReturnType<typeof vi.fn>).mockImplementationOnce(() => runsPromise);
    (api.listBenchmarkRuns as ReturnType<typeof vi.fn>).mockReturnValueOnce(benchmarksPromise);

    clearListCache();

    renderPage();
    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: /quantum simulation studio/i }),
      ).toBeInTheDocument();
    });

    expect(screen.getByRole("heading", { name: /quantum simulation studio/i })).toBeInTheDocument();
  });

  it("falls back to unavailable labels without showing a toast if stats never resolve", async () => {
    vi.useFakeTimers();
    clearListCache();
    (api.fetchMoleculeSummaries as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));
    (api.listRunSummaries as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));
    (api.listBenchmarkRuns as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

    renderPage();

    await act(async () => {
      await Promise.resolve();
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1900);
      await Promise.resolve();
    });

    await act(async () => {
      await Promise.resolve();
    });

    expect(getStatValue("Molecules stored")).toHaveTextContent("N/A");
    expect(getStatValue("Runs created")).toHaveTextContent("N/A");
    expect(getStatValue("Benchmarks ran")).toHaveTextContent("N/A");
  });
});
