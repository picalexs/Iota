export const SITE_NAME = "Quantum Simulation Studio";
export const SITE_SHORT_NAME = "Quantum Studio";
export const SITE_DESCRIPTION =
  "Run reproducible quantum chemistry simulations, compare algorithms, and inspect molecular results with full provenance.";

interface RouteMetadata {
  title: string;
  description: string;
}

const ROUTE_METADATA: Array<[RegExp, RouteMetadata]> = [
  [
    /^\/$/,
    {
      title: SITE_NAME,
      description: SITE_DESCRIPTION,
    },
  ],
  [
    /^\/molecules$/,
    {
      title: `Molecule Library | ${SITE_NAME}`,
      description:
        "Browse, filter, import, and inspect molecules for quantum simulation workflows.",
    },
  ],
  [
    /^\/molecules\/[^/]+$/,
    {
      title: `Molecule Detail | ${SITE_NAME}`,
      description:
        "Inspect molecular structure, identifiers, geometry, and simulation-ready properties.",
    },
  ],
  [
    /^\/runs$/,
    {
      title: `Simulation Runs | ${SITE_NAME}`,
      description:
        "Track quantum simulation runs, statuses, algorithms, runtimes, and result summaries.",
    },
  ],
  [
    /^\/runs\/new$/,
    {
      title: `New Simulation Run | ${SITE_NAME}`,
      description:
        "Configure a molecule, backend, algorithm, and parameters for a new quantum simulation run.",
    },
  ],
  [
    /^\/runs\/[^/]+$/,
    {
      title: `Run Detail | ${SITE_NAME}`,
      description:
        "Review simulation progress, convergence, benchmark comparisons, events, and provenance.",
    },
  ],
  [
    /^\/benchmarks(?:\/.*)?$/,
    {
      title: `Algorithm Benchmark | ${SITE_NAME}`,
      description:
        "Compare quantum algorithms across molecules and score results against reference energies.",
    },
  ],
  [
    /^\/settings$/,
    {
      title: `Settings | ${SITE_NAME}`,
      description: "Manage encrypted IBM Runtime credential profiles.",
    },
  ],
  [
    /^\/help\/parameters$/,
    {
      title: `Parameter Glossary | ${SITE_NAME}`,
      description:
        "Understand backend, algorithm, and advanced configuration parameters for simulation runs.",
    },
  ],
  [
    /^\/info(?:\/.*)?$/,
    {
      title: `Reference | ${SITE_NAME}`,
      description: "Read reference material for supported algorithms, backends, and noise models.",
    },
  ],
];

export function getRouteMetadata(pathname: string): RouteMetadata {
  return (
    ROUTE_METADATA.find(([pattern]) => pattern.test(pathname))?.[1] ?? {
      title: SITE_NAME,
      description: SITE_DESCRIPTION,
    }
  );
}
