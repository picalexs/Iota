import { useEffect, useRef, useState } from "react";
import { Link } from "@tanstack/react-router";
import { BarChart3, FlaskConical, Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Reveal } from "@/components/motion";
import { LogoAtom } from "@/components/motion/molecule-loader";
import { fetchMoleculeSummaries } from "@/api/molecules";
import { listBenchmarkRuns } from "@/api/benchmarks";
import { listRunSummaries } from "@/api/runs";
import { prominentSurfaceHoverClassName } from "@/lib/interactive-styles";
import { buildCacheKey, fetchWithListCache, getCachedData } from "@/state/list-cache";
import { SITE_NAME } from "@/lib/site-metadata";

interface HomeStatsCache {
  moleculeCount: number;
  totalRuns: number;
  totalBenchmarks: number;
}

type HomeStats = HomeStatsCache;

const HOME_STATS_CACHE_KEY = buildCacheKey("home:stats");
const HOME_MOLECULES_CACHE_KEY = buildCacheKey("molecules:summaries", { limit: 1 });
const HOME_RUNS_CACHE_KEY = buildCacheKey("runs:summaries", { limit: 1 });
const HOME_BENCHMARKS_CACHE_KEY = buildCacheKey("benchmarks:list", {
  limit: 1,
});

const FEATURES = [
  {
    icon: FlaskConical,
    title: "Molecule Library",
    description:
      "Define and manage molecular geometries. Configure basis sets and electron counts for your quantum experiments.",
    linkLabel: "Browse Molecules →",
    to: "/molecules",
  },
  {
    icon: Play,
    title: "Quantum Runs",
    description:
      "Execute quantum algorithm jobs. Track progress in real-time and inspect convergence history.",
    linkLabel: "View Runs →",
    to: "/runs",
  },
  {
    icon: BarChart3,
    title: "Benchmarks",
    description:
      "Compare algorithms across molecules, review saved benchmark batches, and inspect accuracy and runtime trends.",
    linkLabel: "Open Benchmarks →",
    to: "/benchmarks",
  },
] as const;

function getCachedHomeStats(): HomeStats | null {
  const cachedStats = getCachedData<HomeStatsCache>(HOME_STATS_CACHE_KEY);

  if (cachedStats) {
    return cachedStats;
  }

  const cachedMolecules = getCachedData<{ total: number }>(HOME_MOLECULES_CACHE_KEY);
  const cachedRuns = getCachedData<{ total: number }>(HOME_RUNS_CACHE_KEY);
  const cachedBenchmarks = getCachedData<{ total: number }>(HOME_BENCHMARKS_CACHE_KEY);

  if (!cachedMolecules || !cachedRuns || !cachedBenchmarks) {
    return null;
  }

  return {
    moleculeCount: cachedMolecules.total,
    totalRuns: cachedRuns.total,
    totalBenchmarks: cachedBenchmarks.total,
  };
}

async function fetchHomeStats(): Promise<HomeStats> {
  return fetchWithListCache(HOME_STATS_CACHE_KEY, async () => {
    const [moleculesData, runsData, benchmarksData] = await Promise.all([
      fetchWithListCache(HOME_MOLECULES_CACHE_KEY, () =>
        fetchMoleculeSummaries({ limit: 1, offset: 0 }),
      ),
      fetchWithListCache(HOME_RUNS_CACHE_KEY, () => listRunSummaries({ limit: 1, offset: 0 })),
      fetchWithListCache(HOME_BENCHMARKS_CACHE_KEY, () =>
        listBenchmarkRuns({ limit: 1, offset: 0 }),
      ),
    ]);

    return {
      moleculeCount: moleculesData.total,
      totalRuns: runsData.total,
      totalBenchmarks: benchmarksData.total,
    };
  });
}

function useHomeStats() {
  const [stats, setStats] = useState<HomeStats | null>(null);
  const [statsTimedOut, setStatsTimedOut] = useState(false);
  const statsTimeoutRef = useRef<ReturnType<typeof globalThis.setTimeout> | null>(null);
  const statsLoadedRef = useRef(false);

  useEffect(() => {
    let cancelled = false;
    const cachedStats = getCachedHomeStats();

    if (cachedStats) {
      setStats(cachedStats);
      statsLoadedRef.current = true;
    }

    statsTimeoutRef.current = globalThis.setTimeout(() => {
      if (cancelled) return;
      if (statsLoadedRef.current) return;
      setStatsTimedOut(true);
    }, 1800);

    const loadStats = async () => {
      try {
        const nextStats = await fetchHomeStats();

        if (cancelled) return;

        setStats(nextStats);
        statsLoadedRef.current = true;
        setStatsTimedOut(false);
      } catch {
        if (cancelled) return;
      }
    };

    void loadStats();

    return () => {
      cancelled = true;
      if (statsTimeoutRef.current !== null) {
        globalThis.clearTimeout(statsTimeoutRef.current);
      }
    };
  }, []);

  return { stats, statsTimedOut };
}

function StatValue({
  statsTimedOut,
  value,
}: Readonly<{ statsTimedOut: boolean; value: number | null }>) {
  if (value !== null) {
    return <span className="font-mono tabular-nums">{String(value)}</span>;
  }

  if (statsTimedOut) {
    return <span className="text-muted-foreground">N/A</span>;
  }

  return <Skeleton data-testid="skeleton" className="h-7 w-12" />;
}

function HeroSection() {
  const [homeLogoHovered, setHomeLogoHovered] = useState(false);

  return (
    <section className="mt-4 flex flex-col items-center gap-5 text-center md:mt-8">
      <button
        type="button"
        className="mx-auto cursor-default rounded-full focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
        onMouseEnter={() => setHomeLogoHovered(true)}
        onMouseLeave={() => setHomeLogoHovered(false)}
        onFocus={() => setHomeLogoHovered(true)}
        onBlur={() => setHomeLogoHovered(false)}
        aria-label="Home entanglement logo"
      >
        <LogoAtom isEntangled={homeLogoHovered} size={96} className="text-primary" />
      </button>
      <h1 className="font-display text-3xl font-semibold tracking-tight md:text-4xl">
        {SITE_NAME}
      </h1>
      <p className="text-muted-foreground text-sm max-w-md">
        Run reproducible quantum chemistry simulations, compare algorithms, and inspect results with
        full provenance tracking.
      </p>
      <Button asChild size="lg">
        <Link to="/runs/new">Get Started →</Link>
      </Button>
    </section>
  );
}

function FeatureCards() {
  return (
    <section className="mx-auto mt-6 grid w-full max-w-7xl grid-cols-1 gap-8 md:mt-20 md:grid-cols-3">
      {FEATURES.map(({ icon: Icon, title, description, linkLabel, to }, idx) => (
        <Reveal key={title} delay={idx * 0.08}>
          <Link
            to={to}
            className="group block h-full rounded-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          >
            <Card
              className={`${prominentSurfaceHoverClassName} h-full cursor-pointer group-hover:shadow-[var(--shadow-elevation-overlay-sm)]`}
            >
              <CardHeader>
                <div className="flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <Icon className="size-5" />
                </div>
                <CardTitle className="text-base font-semibold">{title}</CardTitle>
                <CardDescription>{description}</CardDescription>
              </CardHeader>
              <CardFooter className="mt-auto">
                <span className="text-sm font-medium text-primary">{linkLabel}</span>
              </CardFooter>
            </Card>
          </Link>
        </Reveal>
      ))}
    </section>
  );
}

function StatsSection({
  stats,
  statsTimedOut,
}: Readonly<{
  stats: HomeStats | null;
  statsTimedOut: boolean;
}>) {
  const statsItems = [
    {
      label: "Molecules stored",
      value: stats?.moleculeCount ?? null,
      to: "/molecules" as const,
      search: undefined,
    },
    {
      label: "Runs created",
      value: stats?.totalRuns ?? null,
      to: "/runs" as const,
      search: undefined,
    },
    {
      label: "Benchmarks ran",
      value: stats?.totalBenchmarks ?? null,
      to: "/benchmarks" as const,
      search: undefined,
    },
  ];

  return (
    <section className="flex flex-col items-center gap-4">
      <Separator />
      <div className="flex flex-wrap justify-center gap-8 py-2">
        {statsItems.map(({ label, value, to, search }) => (
          <Link
            key={label}
            to={to}
            search={search}
            className="flex flex-col items-center gap-1 group cursor-pointer"
          >
            <span className="text-2xl font-bold group-hover:underline decoration-accent-2 decoration-[1px] underline-offset-4 transition-all">
              <StatValue statsTimedOut={statsTimedOut} value={value} />
            </span>
            <span className="text-muted-foreground text-sm">{label}</span>
          </Link>
        ))}
      </div>
    </section>
  );
}

function EmptyMoleculesState() {
  return (
    <section className="flex flex-col items-center gap-4 p-6 rounded-lg border border-dashed">
      <div className="text-center">
        <h2 className="text-lg font-semibold mb-2">Get started with molecules</h2>
        <p className="text-muted-foreground text-sm mb-4">
          The curated library is synced from PubChem automatically. You can also import a specific
          compound by name.
        </p>
      </div>
      <div className="flex flex-col gap-2 sm:flex-row">
        <Button asChild variant="outline" size="sm">
          <Link to="/molecules">Import Single Molecule</Link>
        </Button>
      </div>
    </section>
  );
}

export function HomePage() {
  const { stats, statsTimedOut } = useHomeStats();

  return (
    <div className="mx-auto flex w-full max-w-[96rem] flex-col gap-16 px-4 py-12 md:px-8">
      <HeroSection />

      <FeatureCards />

      <StatsSection stats={stats} statsTimedOut={statsTimedOut} />

      {/* Empty state — curated PubChem library is synced automatically at backend startup. */}
      {stats?.moleculeCount === 0 && <EmptyMoleculesState />}
    </div>
  );
}

export default HomePage;
