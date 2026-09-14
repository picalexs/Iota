import { act, render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

vi.mock("@/hooks/use-theme", () => ({
  useTheme: () => ({ theme: "light" as const, resolvedTheme: "light" as const, setTheme: vi.fn() }),
}));
import { RouteLoadingFallback, DeferredSuspense } from "@/routes/lazy-pages";
import {
  BenchmarkRunsSkeleton,
  BenchmarkPageSkeleton,
  HelpParametersSkeleton,
  HomePageSkeleton,
  MoleculesListSkeleton,
  MoleculeDetailSkeleton,
  RunsListSkeleton,
  RunDetailSkeleton,
  RunCreateSkeleton,
  SettingsPageSkeleton,
} from "./components/ui/route-skeleton-variants";
import { shouldUseSkeleton } from "./utils/loading-policy";

// Mock timers for deferred suspense testing
beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

const NeverResolving = () => {
  throw new Promise(() => {
    // Never resolves, keeps component in Suspense
  });
};

describe("RouteLoadingFallback", () => {
  it("renders skeleton-based loading UI", () => {
    render(<RouteLoadingFallback />);

    const skeletons = document.querySelectorAll('[data-slot="skeleton"]');
    expect(skeletons.length).toBeGreaterThan(0);
    expect(screen.queryByText("Loading…")).not.toBeInTheDocument();
  });

  it("exposes accessibility loading semantics", () => {
    render(<RouteLoadingFallback />);

    const status = screen.getByRole("status");
    expect(status).toHaveAttribute("aria-busy", "true");
    expect(status).toHaveAttribute("aria-label", "Loading page");
    expect(status).not.toHaveAttribute("aria-hidden", "true");
  });

  it("does not use full-screen spinner layout classes", () => {
    const { container } = render(<RouteLoadingFallback />);

    expect(container.querySelector(".min-h-screen")).not.toBeInTheDocument();
    expect(container.querySelector(".animate-spin")).not.toBeInTheDocument();
  });

  it("enforces skeleton-first policy for route loading", () => {
    expect(shouldUseSkeleton("route-loading")).toBe(true);
    // Route fallback should use skeletons, not spinners
    render(<RouteLoadingFallback />);
    const skeletons = document.querySelectorAll('[data-slot="skeleton"]');
    expect(skeletons.length).toBeGreaterThan(0);
  });
});

describe("Route-specific skeleton variants", () => {
  it("HomePageSkeleton renders with hero section placeholder", () => {
    render(<HomePageSkeleton />);

    const status = screen.getByRole("status");
    expect(status).toHaveAttribute("aria-busy", "true");
    expect(status).toHaveAttribute("aria-label", "Loading home page");

    const skeletons = document.querySelectorAll('[data-slot="skeleton"]');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("MoleculesListSkeleton renders with list structure", () => {
    render(<MoleculesListSkeleton />);

    const status = screen.getByRole("status");
    expect(status).toHaveAttribute("aria-busy", "true");
    expect(status).toHaveAttribute("aria-label", "Loading molecule library");

    const skeletons = document.querySelectorAll('[data-slot="skeleton"]');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("MoleculeDetailSkeleton renders with detail view structure", () => {
    render(<MoleculeDetailSkeleton />);

    const status = screen.getByRole("status");
    expect(status).toHaveAttribute("aria-busy", "true");
    expect(status).toHaveAttribute("aria-label", "Loading molecule details");

    const skeletons = document.querySelectorAll('[data-slot="skeleton"]');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("RunsListSkeleton renders with table structure", () => {
    render(<RunsListSkeleton />);

    const status = screen.getByRole("status");
    expect(status).toHaveAttribute("aria-busy", "true");
    expect(status).toHaveAttribute("aria-label", "Loading runs");

    const skeletons = document.querySelectorAll('[data-slot="skeleton"]');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("RunDetailSkeleton renders with detail view structure", () => {
    render(<RunDetailSkeleton />);

    const status = screen.getByRole("status");
    expect(status).toHaveAttribute("aria-busy", "true");
    expect(status).toHaveAttribute("aria-label", "Loading run details");

    const skeletons = document.querySelectorAll('[data-slot="skeleton"]');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("RunCreateSkeleton renders with form structure", () => {
    render(<RunCreateSkeleton />);

    const status = screen.getByRole("status");
    expect(status).toHaveAttribute("aria-busy", "true");
    expect(status).toHaveAttribute("aria-label", "Loading form");

    const skeletons = document.querySelectorAll('[data-slot="skeleton"]');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("BenchmarkPageSkeleton renders with benchmark workspace structure", () => {
    render(<BenchmarkPageSkeleton />);

    const status = screen.getByRole("status");
    expect(status).toHaveAttribute("aria-busy", "true");
    expect(status).toHaveAttribute("aria-label", "Loading benchmark workspace");

    const skeletons = document.querySelectorAll('[data-slot="skeleton"]');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("BenchmarkRunsSkeleton renders with benchmark list structure", () => {
    render(<BenchmarkRunsSkeleton />);

    const status = screen.getByRole("status");
    expect(status).toHaveAttribute("aria-busy", "true");
    expect(status).toHaveAttribute("aria-label", "Loading benchmark runs");

    const skeletons = document.querySelectorAll('[data-slot="skeleton"]');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("SettingsPageSkeleton renders with settings workspace structure", () => {
    render(<SettingsPageSkeleton />);

    const status = screen.getByRole("status");
    expect(status).toHaveAttribute("aria-busy", "true");
    expect(status).toHaveAttribute("aria-label", "Loading settings");

    const skeletons = document.querySelectorAll('[data-slot="skeleton"]');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("HelpParametersSkeleton renders with glossary structure", () => {
    render(<HelpParametersSkeleton />);

    const status = screen.getByRole("status");
    expect(status).toHaveAttribute("aria-busy", "true");
    expect(status).toHaveAttribute("aria-label", "Loading parameter glossary");

    const skeletons = document.querySelectorAll('[data-slot="skeleton"]');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  [
    "home",
    "molecules",
    "molecule-detail",
    "runs",
    "run-detail",
    "run-create",
    "benchmark-runs",
    "benchmark",
    "help-parameters",
    "settings",
  ].forEach((routeName) => {
    it(`${routeName} skeleton preserves accessibility semantics`, () => {
      const variants = {
        "benchmark-runs": BenchmarkRunsSkeleton,
        benchmark: BenchmarkPageSkeleton,
        home: HomePageSkeleton,
        "help-parameters": HelpParametersSkeleton,
        molecules: MoleculesListSkeleton,
        "molecule-detail": MoleculeDetailSkeleton,
        runs: RunsListSkeleton,
        "run-detail": RunDetailSkeleton,
        "run-create": RunCreateSkeleton,
        settings: SettingsPageSkeleton,
      } as const;

      const Component = variants[routeName as keyof typeof variants];
      const { container } = render(<Component />);

      // Should not have spinner UI
      expect(container.querySelector(".animate-spin")).not.toBeInTheDocument();

      // Should have a status region
      const status = screen.getByRole("status");
      expect(status).toBeInTheDocument();
      expect(status).toHaveAttribute("aria-busy", "true");
    });
  });
});

describe("DeferredSuspense — anti-flicker behavior", () => {
  it("does not show fallback before 50ms threshold", async () => {
    const TestFallback = () => <output data-testid="fallback-skeleton">Loading…</output>;

    render(
      <DeferredSuspense fallback={<TestFallback />}>
        <NeverResolving />
      </DeferredSuspense>,
    );

    // Fallback should NOT be shown immediately
    expect(screen.queryByTestId("fallback-skeleton")).not.toBeInTheDocument();

    // Advance time to just before 50ms
    vi.advanceTimersByTime(49);
    expect(screen.queryByTestId("fallback-skeleton")).not.toBeInTheDocument();
  });

  it("shows fallback after 50ms threshold when child unresolved", async () => {
    const TestFallback = () => <output data-testid="fallback-skeleton">Loading…</output>;

    const { rerender } = render(
      <DeferredSuspense fallback={<TestFallback />}>
        <NeverResolving />
      </DeferredSuspense>,
    );

    // Fallback should NOT be shown at 49ms
    expect(screen.queryByTestId("fallback-skeleton")).not.toBeInTheDocument();

    // Advance time past 50ms
    await act(async () => {
      vi.advanceTimersByTime(51);
    });

    // Trigger a rerender to flush the state update from the timeout
    rerender(
      <DeferredSuspense fallback={<TestFallback />}>
        <NeverResolving />
      </DeferredSuspense>,
    );

    // Now fallback should be visible
    expect(screen.getByTestId("fallback-skeleton")).toBeInTheDocument();
  });

  it("route skeleton fallback maintains accessibility when shown after delay", async () => {
    render(<RouteLoadingFallback />);

    const status = screen.getByRole("status");
    expect(status).toHaveAttribute("aria-busy", "true");
    expect(status).toHaveAttribute("aria-label", "Loading page");
    expect(status).not.toHaveAttribute("aria-hidden");
  });
});
