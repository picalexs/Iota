import { render, screen, waitFor, within } from "@testing-library/react";
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  RouterProvider,
} from "@tanstack/react-router";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BenchmarkInsights } from "./benchmark-insights";
import type { BenchmarkEntry } from "./benchmark-utils";
import type { MoleculePreset } from "@/lib/benchmark-presets";

function buildGroupedRows(): Array<{ preset: MoleculePreset; rows: BenchmarkEntry[] }> {
  const preset: MoleculePreset = {
    key: "h2",
    name: "H2",
    formula: "H2",
    description: "Hydrogen benchmark",
    atoms: [],
    charge: 0,
    multiplicity: 1,
    active_space: { n_electrons: 2, n_orbitals: 2 },
    basis: "sto-3g",
    references: { hf: -1.116, fci: -1.137, source: "test" },
  };

  return [
    {
      preset,
      rows: [
        {
          id: "h2:vqe",
          preset,
          algorithm: "vqe",
          variantLabel: "RealAmplitudes",
          mode: "advanced",
          easyOptions: null,
          advancedConfig: {
            algorithm: "vqe",
            ansatz_name: "RealAmplitudes",
            optimizer_name: "COBYLA",
            max_iterations: 600,
            max_function_evaluations: 6000,
            reps: 2,
          },
          status: "completed",
          moleculeId: "bbbbbbbb-0000-0000-0000-000000000001",
          runId: "aaaaaaaa-0000-0000-0000-000000000001",
          energy: -1.137283,
          currentEnergy: -1.137283,
          converged: true,
          errorMessage: null,
          classicalRefs: { hf: -1.116, fci: -1.137 },
          elapsedSeconds: 12.4,
          latestEventSequence: 5,
        },
      ],
    },
  ];
}

function buildRunningMatrixRows(): Array<{ preset: MoleculePreset; rows: BenchmarkEntry[] }> {
  const preset: MoleculePreset = {
    key: "running-h2",
    name: "H2",
    formula: "H2",
    description: "Hydrogen running benchmark",
    atoms: [],
    charge: 0,
    multiplicity: 1,
    active_space: { n_electrons: 2, n_orbitals: 2 },
    basis: "sto-3g",
    references: { hf: -1.116, fci: -1.137, source: "test" },
  };

  return [
    {
      preset,
      rows: [
        {
          id: "running-h2:vqe",
          preset,
          algorithm: "vqe",
          status: "running",
          moleculeId: "mol-running",
          runId: "run-running",
          energy: null,
          currentEnergy: -1.13,
          converged: false,
          errorMessage: null,
          classicalRefs: { hf: -1.116, fci: -1.137 },
          elapsedSeconds: 3,
          latestEventSequence: 2,
        },
      ],
    },
  ];
}

function buildScatterStressRows(): Array<{ preset: MoleculePreset; rows: BenchmarkEntry[] }> {
  const molecules: MoleculePreset[] = [
    {
      key: "beh2",
      name: "Beryllium Hydride (BeH₂)",
      formula: "BeH₂",
      description: "BeH2 benchmark",
      atoms: [],
      charge: 0,
      multiplicity: 1,
      active_space: { n_electrons: 4, n_orbitals: 4 },
      basis: "sto-3g",
      references: { hf: -15.567, fci: -15.587, source: "test" },
    },
    {
      key: "n2",
      name: "Nitrogen (N₂)",
      formula: "N₂",
      description: "N2 benchmark",
      atoms: [],
      charge: 0,
      multiplicity: 1,
      active_space: { n_electrons: 10, n_orbitals: 8 },
      basis: "sto-3g",
      references: { hf: -107.49, fci: -107.59, source: "test" },
    },
    {
      key: "custom-long",
      name: "1-(4-amino-3,5-dichlorophenyl)-2-(tert-butylamino)ethanol hydrochloride",
      formula: "1-(4-amino-3,5-dichlorophenyl)-2-(tert-butylamino)ethanol hydrochloride",
      description: "Long-name benchmark",
      atoms: [],
      charge: 0,
      multiplicity: 1,
      active_space: { n_electrons: 2, n_orbitals: 2 },
      basis: "sto-3g",
      references: { hf: -1.01, fci: -1.012, source: "test" },
    },
  ];
  const beh2 = molecules[0];
  const n2 = molecules[1];
  const customLong = molecules[2];
  if (!beh2 || !n2 || !customLong) {
    throw new Error("Expected benchmark insight molecule fixtures");
  }

  return [
    {
      preset: beh2,
      rows: [
        {
          id: "beh2:sqd",
          preset: beh2,
          algorithm: "sqd",
          status: "completed",
          moleculeId: "mol-1",
          runId: "run-1",
          energy: -15.5869998,
          currentEnergy: -15.5869998,
          converged: true,
          errorMessage: null,
          classicalRefs: { hf: -15.567, fci: -15.587 },
          elapsedSeconds: 0.01,
          latestEventSequence: 1,
        },
        {
          id: "beh2:kqd",
          preset: beh2,
          algorithm: "kqd",
          status: "completed",
          moleculeId: "mol-1",
          runId: "run-2",
          energy: -15.5859,
          currentEnergy: -15.5859,
          converged: true,
          errorMessage: null,
          classicalRefs: { hf: -15.567, fci: -15.587 },
          elapsedSeconds: 0.03,
          latestEventSequence: 1,
        },
        {
          id: "beh2:vqe",
          preset: beh2,
          algorithm: "vqe",
          status: "completed",
          moleculeId: "mol-1",
          runId: "run-3",
          energy: -15.582,
          currentEnergy: -15.582,
          converged: true,
          errorMessage: null,
          classicalRefs: { hf: -15.567, fci: -15.587 },
          elapsedSeconds: 0.05,
          latestEventSequence: 1,
        },
      ],
    },
    {
      preset: n2,
      rows: [
        {
          id: "n2:sqd",
          preset: n2,
          algorithm: "sqd",
          status: "completed",
          moleculeId: "mol-2",
          runId: "run-4",
          energy: -107.5895,
          currentEnergy: -107.5895,
          converged: true,
          errorMessage: null,
          classicalRefs: { hf: -107.49, fci: -107.59 },
          elapsedSeconds: 0.45,
          latestEventSequence: 1,
        },
        {
          id: "n2:qse",
          preset: n2,
          algorithm: "qse",
          status: "completed",
          moleculeId: "mol-2",
          runId: "run-5",
          energy: -107.588,
          currentEnergy: -107.588,
          converged: true,
          errorMessage: null,
          classicalRefs: { hf: -107.49, fci: -107.59 },
          elapsedSeconds: 0.65,
          latestEventSequence: 1,
        },
      ],
    },
    {
      preset: customLong,
      rows: [
        {
          id: "custom:qse",
          preset: customLong,
          algorithm: "qse",
          status: "completed",
          moleculeId: "mol-3",
          runId: "run-6",
          energy: -1.0109,
          currentEnergy: -1.0109,
          converged: true,
          errorMessage: null,
          classicalRefs: { hf: -1.01, fci: -1.012 },
          elapsedSeconds: 0.55,
          latestEventSequence: 1,
        },
        {
          id: "custom:skqd",
          preset: customLong,
          algorithm: "skqd",
          status: "completed",
          moleculeId: "mol-3",
          runId: "run-7",
          energy: -1.007,
          currentEnergy: -1.007,
          converged: true,
          errorMessage: null,
          classicalRefs: { hf: -1.01, fci: -1.012 },
          elapsedSeconds: 0.75,
          latestEventSequence: 1,
        },
      ],
    },
  ];
}

function buildDenseScatterRows(): Array<{ preset: MoleculePreset; rows: BenchmarkEntry[] }> {
  const preset: MoleculePreset = {
    key: "dense-h2",
    name: "H2",
    formula: "H2",
    description: "Dense scatter benchmark",
    atoms: [],
    charge: 0,
    multiplicity: 1,
    active_space: { n_electrons: 2, n_orbitals: 2 },
    basis: "sto-3g",
    references: { hf: -1.116, fci: -1.137274, source: "test" },
  };

  const algorithms: BenchmarkEntry["algorithm"][] = ["vqe", "sqd", "kqd", "qfd", "qse", "skqd"];
  const rows = Array.from({ length: 15 }, (_, index) => {
    const algorithm = algorithms[index % algorithms.length];
    if (!algorithm) {
      throw new Error("Expected benchmark insight algorithm fixture");
    }
    return {
      id: `dense-${index + 1}`,
      preset,
      algorithm,
      variantLabel: `Variant ${index + 1}`,
      status: "completed" as const,
      moleculeId: "mol-dense",
      runId: `run-dense-${index + 1}`,
      energy: -1.137274 + ((index % 5) - 2) * 0.00008,
      currentEnergy: -1.137274 + ((index % 5) - 2) * 0.00008,
      converged: true,
      errorMessage: null,
      classicalRefs: { hf: -1.116, fci: -1.137274 },
      elapsedSeconds: 0.9 + (index % 6) * 0.18,
      latestEventSequence: index + 1,
    } satisfies BenchmarkEntry;
  });

  return [{ preset, rows }];
}

function buildFamilyVariantRows(): Array<{ preset: MoleculePreset; rows: BenchmarkEntry[] }> {
  const h2Preset: MoleculePreset = {
    key: "family-h2",
    name: "Hydrogen (H2)",
    formula: "H2",
    description: "Family filter benchmark",
    atoms: [],
    charge: 0,
    multiplicity: 1,
    active_space: { n_electrons: 2, n_orbitals: 2 },
    basis: "sto-3g",
    references: { hf: -1.116, fci: -1.137274, source: "test" },
  };
  const lihPreset: MoleculePreset = {
    key: "family-lih",
    name: "Lithium Hydride (LiH)",
    formula: "LiH",
    description: "Family filter benchmark",
    atoms: [],
    charge: 0,
    multiplicity: 1,
    active_space: { n_electrons: 2, n_orbitals: 3 },
    basis: "sto-3g",
    references: { hf: -7.86204, fci: -7.88229, source: "test" },
  };

  return [
    {
      preset: h2Preset,
      rows: [
        {
          id: "family:vqe-real",
          preset: h2Preset,
          algorithm: "vqe",
          variantLabel: "RealAmplitudes",
          status: "completed",
          moleculeId: "mol-family",
          runId: "run-family-1",
          energy: -1.1371,
          currentEnergy: -1.1371,
          converged: true,
          errorMessage: null,
          classicalRefs: { hf: -1.116, fci: -1.137274 },
          elapsedSeconds: 20,
          latestEventSequence: 1,
        },
        {
          id: "family:qse",
          preset: h2Preset,
          algorithm: "qse",
          status: "completed",
          moleculeId: "mol-family",
          runId: "run-family-2",
          energy: -1.136,
          currentEnergy: -1.136,
          converged: true,
          errorMessage: null,
          classicalRefs: { hf: -1.116, fci: -1.137274 },
          elapsedSeconds: 15,
          latestEventSequence: 2,
        },
      ],
    },
    {
      preset: lihPreset,
      rows: [
        {
          id: "family-lih:vqe-real",
          preset: lihPreset,
          algorithm: "vqe",
          variantLabel: "RealAmplitudes",
          status: "completed",
          moleculeId: "mol-lih",
          runId: "run-family-3",
          energy: -7.8821,
          currentEnergy: -7.8821,
          converged: true,
          errorMessage: null,
          classicalRefs: { hf: -7.86204, fci: -7.88229 },
          elapsedSeconds: 48,
          latestEventSequence: 3,
        },
        {
          id: "family-lih:vqe-efficient",
          preset: lihPreset,
          algorithm: "vqe",
          variantLabel: "EfficientSU2",
          status: "completed",
          moleculeId: "mol-lih",
          runId: "run-family-4",
          energy: -7.88228,
          currentEnergy: -7.88228,
          converged: true,
          errorMessage: null,
          classicalRefs: { hf: -7.86204, fci: -7.88229 },
          elapsedSeconds: 35,
          latestEventSequence: 4,
        },
      ],
    },
  ];
}

function buildWideRuntimeRows(): Array<{ preset: MoleculePreset; rows: BenchmarkEntry[] }> {
  const preset: MoleculePreset = {
    key: "wide-runtime-h2",
    name: "H2",
    formula: "H2",
    description: "Wide runtime spread benchmark",
    atoms: [],
    charge: 0,
    multiplicity: 1,
    active_space: { n_electrons: 2, n_orbitals: 2 },
    basis: "sto-3g",
    references: { hf: -1.116, fci: -1.137274, source: "test" },
  };

  return [
    {
      preset,
      rows: [
        {
          id: "wide-runtime:fast",
          preset,
          algorithm: "vqe",
          variantLabel: "Fast",
          status: "completed",
          moleculeId: "mol-wide-runtime",
          runId: "run-wide-runtime-1",
          energy: -1.13726,
          currentEnergy: -1.13726,
          converged: true,
          errorMessage: null,
          classicalRefs: { hf: -1.116, fci: -1.137274 },
          elapsedSeconds: 0.5,
          latestEventSequence: 1,
        },
        {
          id: "wide-runtime:mid",
          preset,
          algorithm: "vqe",
          variantLabel: "Mid",
          status: "completed",
          moleculeId: "mol-wide-runtime",
          runId: "run-wide-runtime-2",
          energy: -1.13718,
          currentEnergy: -1.13718,
          converged: true,
          errorMessage: null,
          classicalRefs: { hf: -1.116, fci: -1.137274 },
          elapsedSeconds: 30,
          latestEventSequence: 2,
        },
        {
          id: "wide-runtime:slow",
          preset,
          algorithm: "vqe",
          variantLabel: "Slow",
          status: "completed",
          moleculeId: "mol-wide-runtime",
          runId: "run-wide-runtime-3",
          energy: -1.1369,
          currentEnergy: -1.1369,
          converged: true,
          errorMessage: null,
          classicalRefs: { hf: -1.116, fci: -1.137274 },
          elapsedSeconds: 2055,
          latestEventSequence: 3,
        },
      ],
    },
  ];
}

function renderBenchmarkInsights(
  grouped: Array<{ preset: MoleculePreset; rows: BenchmarkEntry[] }> = buildGroupedRows(),
) {
  const rootRoute = createRootRoute();
  const benchmarkRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/benchmarks",
    component: () => <BenchmarkInsights grouped={grouped} chemicalAccuracyHa={0.0016} />,
  });
  const runDetailRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: "/runs/$runId",
    component: () => <div>Run detail</div>,
  });
  const routeTree = rootRoute.addChildren([benchmarkRoute, runDetailRoute]);
  const history = createMemoryHistory({ initialEntries: ["/benchmarks"] });
  const router = createRouter({ routeTree, history });

  return { router, ...render(<RouterProvider router={router} />) };
}

describe("BenchmarkInsights", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("links accuracy matrix cells to the matching run detail page", async () => {
    const user = userEvent.setup();
    const { router } = renderBenchmarkInsights();

    await user.click(
      await screen.findByRole("link", {
        name: /open h2 vqe .* run detail/i,
      }),
    );

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/runs/aaaaaaaa-0000-0000-0000-000000000001");
    });
  });

  it("renders accuracy matrix entries as wrapped tiles per molecule", async () => {
    renderBenchmarkInsights(buildDenseScatterRows());

    expect(await screen.findByRole("heading", { name: "H2", level: 3 })).toBeInTheDocument();
    expect(screen.getByText("15 rows")).toBeInTheDocument();

    const moleculeSection = screen
      .getByRole("heading", { name: "H2", level: 3 })
      .closest("section");
    expect(moleculeSection).not.toBeNull();

    const tileGrid = moleculeSection?.querySelector(".grid");
    expect(tileGrid?.getAttribute("style")).toContain("repeat(auto-fit, minmax(9.5rem, 1fr))");
    expect(screen.getByText("Variant 1")).toBeInTheDocument();
    expect(screen.getByText("Variant 15")).toBeInTheDocument();
  });

  it("shows the chemical-accuracy target on the runtime scatter", async () => {
    renderBenchmarkInsights();

    expect(
      await screen.findByRole("img", {
        name: /benchmark accuracy versus runtime scatter plot/i,
      }),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Target 1.6 mHa").length).toBeGreaterThan(0);
    expect(screen.getByText(/log runtime and error axes/i)).toBeInTheDocument();
    expect(screen.getByText("runtime")).toBeInTheDocument();
    expect(screen.queryByText(/algorithm snapshot/i)).not.toBeInTheDocument();
  });

  it("uses a log runtime axis so wide runtime ranges do not collapse near the origin", async () => {
    const { container } = renderBenchmarkInsights(buildWideRuntimeRows());

    await screen.findByRole("img", {
      name: /benchmark accuracy versus runtime scatter plot/i,
    });

    const points = Array.from(container.querySelectorAll("circle[data-scatter-point]")).map(
      (node) => Number.parseFloat(node.getAttribute("cx") ?? "0"),
    );
    const [firstPoint, secondPoint, thirdPoint] = points;
    if (firstPoint === undefined || secondPoint === undefined || thirdPoint === undefined) {
      throw new Error("Expected three scatter points");
    }
    expect(points).toHaveLength(3);
    expect(secondPoint - firstPoint).toBeGreaterThan(120);
    expect(thirdPoint - secondPoint).toBeGreaterThan(120);
    expect(screen.queryByText(/^0 s$/)).not.toBeInTheDocument();
    expect(screen.getByText("34 min 15 s")).toBeInTheDocument();
    expect(screen.queryByText("33 min 20 s")).not.toBeInTheDocument();
  });

  it("opens the accuracy matrix in a fullscreen dialog", async () => {
    const user = userEvent.setup();
    renderBenchmarkInsights();

    await user.click(
      await screen.findByRole("button", {
        name: /expand accuracy matrix fullscreen/i,
      }),
    );

    expect(await screen.findByRole("dialog", { name: /accuracy matrix/i })).toBeInTheDocument();
  });

  it("opens the runtime scatter in a fullscreen dialog", async () => {
    const user = userEvent.setup();
    renderBenchmarkInsights();

    await user.click(
      await screen.findByRole("button", {
        name: /expand accuracy vs runtime fullscreen/i,
      }),
    );

    const dialog = await screen.findByRole("dialog", { name: /accuracy vs runtime/i });
    expect(dialog).toBeInTheDocument();
    expect(
      within(dialog).getByRole("img", {
        name: /benchmark accuracy versus runtime scatter plot/i,
      }),
    ).toBeInTheDocument();
  });

  it("uses the warning tone for running accuracy-matrix cells", async () => {
    renderBenchmarkInsights(buildRunningMatrixRows());

    const runningCell = await screen.findByRole("link", {
      name: /open h2 vqe run detail \(running\)/i,
    });

    expect(runningCell.className).toContain("bg-warning/10");
    expect(runningCell.className).toContain("text-warning");
  });

  it("shows a hover tooltip with energy details for scatter points", async () => {
    const user = userEvent.setup();
    const { container } = renderBenchmarkInsights();

    await screen.findByRole("img", {
      name: /benchmark accuracy versus runtime scatter plot/i,
    });

    const point = container.querySelector("[data-scatter-point]");
    expect(point).not.toBeNull();

    await user.hover(point!);

    const tooltipTitle = await screen.findByText("H2 · VQE · RealAmplitudes");
    const tooltip = tooltipTitle.closest(".pointer-events-none");
    expect(tooltip).not.toBeNull();
    if (!(tooltip instanceof HTMLElement)) {
      throw new Error("Expected tooltip container to be an HTMLElement");
    }
    const tooltipScope = within(tooltip);

    expect(tooltipScope.getByText("-1.137283 Ha")).toBeInTheDocument();
    expect(tooltipScope.getByText("Stats")).toBeInTheDocument();
    expect(tooltipScope.getByText(/^Abs\. error$/)).toBeInTheDocument();
    expect(tooltipScope.getByText(/^0\.28 mHa$/)).toBeInTheDocument();
    expect(tooltipScope.getByText(/^Runtime$/)).toBeInTheDocument();
    expect(tooltipScope.getByText(/^12 s$/)).toBeInTheDocument();
    expect(tooltipScope.getByText("Configuration")).toBeInTheDocument();
    expect(tooltipScope.getByText(/^Ansatz$/)).toBeInTheDocument();
    expect(tooltipScope.getByText(/^Optimizer$/)).toBeInTheDocument();
    expect(tooltipScope.getByText(/^Depth$/)).toBeInTheDocument();
    expect(tooltipScope.getByText(/^Budget$/)).toBeInTheDocument();
    expect(tooltipScope.getByText(/^COBYLA$/)).toBeInTheDocument();
    expect(tooltipScope.getByText(/^reps 2$/)).toBeInTheDocument();
    expect(tooltipScope.getByText(/^600 iters · 6000 evals$/)).toBeInTheDocument();
    expect(tooltipScope.queryByText(/Verdict/i)).not.toBeInTheDocument();
  });

  it("flips the hover tooltip inward for points near the right edge", async () => {
    const user = userEvent.setup();
    const { container } = renderBenchmarkInsights();

    await screen.findByRole("img", {
      name: /benchmark accuracy versus runtime scatter plot/i,
    });

    const svg = container.querySelector("svg");
    const wrapper = svg?.parentElement;
    expect(svg).not.toBeNull();
    expect(wrapper).not.toBeNull();

    const rect = {
      x: 0,
      y: 0,
      left: 0,
      top: 0,
      right: 760,
      bottom: 360,
      width: 760,
      height: 360,
      toJSON: () => ({}),
    } as DOMRect;

    vi.spyOn(svg!, "getBoundingClientRect").mockReturnValue(rect);
    vi.spyOn(wrapper!, "getBoundingClientRect").mockReturnValue(rect);

    const point = container.querySelector("[data-scatter-point]");
    expect(point).not.toBeNull();

    await user.hover(point!);

    const tooltip = (await screen.findByText("H2 · VQE · RealAmplitudes")).closest(
      ".pointer-events-none",
    );
    expect(tooltip).not.toBeNull();
    expect(tooltip).toHaveStyle({ transform: "translate(-100%, 0)" });
  });

  it("keeps scatter labels visible for every point and shortens long molecule names", async () => {
    const rootRoute = createRootRoute();
    const benchmarkRoute = createRoute({
      getParentRoute: () => rootRoute,
      path: "/benchmarks",
      component: () => (
        <BenchmarkInsights grouped={buildScatterStressRows()} chemicalAccuracyHa={0.0016} />
      ),
    });
    const routeTree = rootRoute.addChildren([benchmarkRoute]);
    const history = createMemoryHistory({ initialEntries: ["/benchmarks"] });
    const router = createRouter({ routeTree, history });
    const { container } = render(<RouterProvider router={router} />);

    await screen.findByRole("img", {
      name: /benchmark accuracy versus runtime scatter plot/i,
    });

    const scatterLabelTexts = Array.from(container.querySelectorAll("svg text"))
      .map((node) => node.textContent?.trim())
      .filter(Boolean);
    const visibleScatterLabels = Array.from(container.querySelectorAll('svg text[opacity="0.82"]'))
      .map((node) => node.textContent?.trim())
      .filter(Boolean);

    expect(visibleScatterLabels).toContain("BeH₂ KQD");
    expect(scatterLabelTexts).not.toContain("BeH₂ KQD · default");

    const compactQseLabel = scatterLabelTexts.find(
      (text) => text.endsWith(" QSE") && text.startsWith("1-("),
    );
    expect(compactQseLabel).toBeTruthy();
    expect(compactQseLabel).toContain("…");
    expect(compactQseLabel!.length).toBeLessThan(26);

    const compactSkqdLabel = scatterLabelTexts.find(
      (text) => text.endsWith(" SKQD") && text.startsWith("1-("),
    );
    expect(compactSkqdLabel).toBeTruthy();
    expect(compactSkqdLabel).toContain("…");
    expect(scatterLabelTexts.every((text) => !text.includes("EfficientSU2"))).toBe(true);
  });

  it("reduces inline scatter labels automatically on dense charts", async () => {
    const user = userEvent.setup();
    const { container } = renderBenchmarkInsights(buildDenseScatterRows());

    await screen.findByRole("img", {
      name: /benchmark accuracy versus runtime scatter plot/i,
    });

    expect(screen.getByText(/dense charts trim inline labels automatically/i)).toBeInTheDocument();

    const points = Array.from(container.querySelectorAll("[data-scatter-point]"));
    expect(points).toHaveLength(15);

    const visibleLabels = Array.from(container.querySelectorAll('svg text[opacity="0.82"]'))
      .map((node) => node.textContent?.trim())
      .filter(Boolean);
    expect(visibleLabels.length).toBeLessThan(points.length);

    const firstPoint = points.at(0);
    expect(firstPoint).toBeDefined();
    if (!firstPoint) {
      throw new Error("Expected at least one scatter point");
    }

    await user.hover(firstPoint);

    expect(await screen.findByText(/H2 · /i)).toBeInTheDocument();
    const hoveredLabels = Array.from(container.querySelectorAll('svg text[opacity="0.96"]'))
      .map((node) => node.textContent?.trim())
      .filter(Boolean);
    expect(hoveredLabels.length).toBeGreaterThan(0);
  });

  it("toggles inline scatter labels and keeps the fullscreen chart in sync", async () => {
    const user = userEvent.setup();
    const { container } = renderBenchmarkInsights(buildScatterStressRows());

    await screen.findByRole("img", {
      name: /benchmark accuracy versus runtime scatter plot/i,
    });

    expect(container.querySelectorAll('svg text[opacity="0.82"]').length).toBeGreaterThan(0);

    await user.click(
      screen.getByRole("button", {
        name: /hide point labels on accuracy-vs-runtime chart/i,
      }),
    );

    expect(screen.getByText(/point labels are hidden/i)).toBeInTheDocument();
    expect(container.querySelectorAll('svg text[opacity="0.82"]')).toHaveLength(0);
    expect(container.querySelectorAll('svg text[opacity="0.96"]')).toHaveLength(0);

    await user.click(
      screen.getByRole("button", {
        name: /expand accuracy vs runtime fullscreen/i,
      }),
    );

    const dialog = await screen.findByRole("dialog", { name: /accuracy vs runtime/i });
    expect(
      within(dialog).getByRole("button", {
        name: /show point labels on accuracy-vs-runtime chart/i,
      }),
    ).toBeInTheDocument();
    expect(dialog.querySelectorAll('svg text[opacity="0.82"]')).toHaveLength(0);

    await user.click(
      within(dialog).getByRole("button", {
        name: /show point labels on accuracy-vs-runtime chart/i,
      }),
    );

    await waitFor(() => {
      expect(dialog.querySelectorAll('svg text[opacity="0.82"]').length).toBeGreaterThan(0);
    });
  });

  it("renders distinct marker shapes for different algorithm families", async () => {
    const { container } = renderBenchmarkInsights(buildDenseScatterRows());

    await screen.findByRole("img", {
      name: /benchmark accuracy versus runtime scatter plot/i,
    });

    const shapes = new Set(
      Array.from(container.querySelectorAll("[data-scatter-point]"))
        .map((node) => node.getAttribute("data-scatter-shape"))
        .filter(Boolean),
    );

    expect(shapes).toEqual(new Set(["circle", "square", "diamond", "triangle", "star", "hexagon"]));
  });

  it("shows a family legend and outlined markers on the runtime scatter", async () => {
    const { container } = renderBenchmarkInsights(buildDenseScatterRows());

    await screen.findByRole("img", {
      name: /benchmark accuracy versus runtime scatter plot/i,
    });

    expect(screen.getByText("Legend")).toBeInTheDocument();
    expect(container.querySelector('[data-scatter-legend-item="vqe"]')).not.toBeNull();
    expect(container.querySelector('[data-scatter-legend-item="qfd"]')).not.toBeNull();
    expect(container.querySelector('[data-scatter-legend-item="skqd"]')).not.toBeNull();
    const legendContainer = screen.getByText("Legend").closest("div");
    expect(legendContainer?.className).toContain("flex-col");
    expect(legendContainer?.className).not.toContain("absolute");

    const point = container.querySelector("[data-scatter-point]");
    expect(point).not.toBeNull();
    expect(point).toHaveAttribute("stroke");
    expect(point).not.toHaveAttribute("stroke", "none");
    expect(point).not.toHaveAttribute("tabindex");
  });

  it("filters runtime scatter points by family, specific algorithm, and molecule and keeps fullscreen in sync", async () => {
    const user = userEvent.setup();
    const { container } = renderBenchmarkInsights(buildFamilyVariantRows());

    await screen.findByRole("img", {
      name: /benchmark accuracy versus runtime scatter plot/i,
    });

    expect(container.querySelectorAll("[data-scatter-point]")).toHaveLength(4);

    await user.click(
      screen.getByRole("button", {
        name: /filter accuracy-vs-runtime chart by family/i,
      }),
    );

    const qseFamilyOption = screen
      .getAllByText("QSE")
      .find((node) => node.closest("[cmdk-item]") !== null);
    expect(qseFamilyOption).toBeTruthy();
    await user.click(qseFamilyOption!);

    await waitFor(() => {
      expect(container.querySelectorAll("[data-scatter-point]")).toHaveLength(3);
    });

    await user.click(
      screen.getByRole("button", {
        name: /filter accuracy-vs-runtime chart by algorithm/i,
      }),
    );

    const efficientSu2Option = screen
      .getAllByText("VQE · EfficientSU2")
      .find((node) => node.closest("[cmdk-item]") !== null);
    expect(efficientSu2Option).toBeTruthy();
    await user.click(efficientSu2Option!);

    await waitFor(() => {
      expect(container.querySelectorAll("[data-scatter-point]")).toHaveLength(2);
    });

    await user.click(
      screen.getByRole("button", {
        name: /filter accuracy-vs-runtime chart by molecule/i,
      }),
    );

    const moleculeOption = screen
      .getAllByText("H2")
      .find((node) => node.closest("[cmdk-item]") !== null);
    expect(moleculeOption).toBeTruthy();
    await user.click(moleculeOption!);

    await waitFor(() => {
      expect(container.querySelectorAll("[data-scatter-point]")).toHaveLength(1);
    });

    await user.click(screen.getByRole("button", { name: /show all/i }));

    await waitFor(() => {
      expect(container.querySelectorAll("[data-scatter-point]")).toHaveLength(4);
    });

    await user.click(
      screen.getByRole("button", {
        name: /expand accuracy vs runtime fullscreen/i,
      }),
    );

    const dialog = await screen.findByRole("dialog", { name: /accuracy vs runtime/i });
    expect(within(dialog).getByText("Showing 4 of 4 points")).toBeInTheDocument();
    expect(dialog.querySelectorAll("[data-scatter-point]")).toHaveLength(4);
  });

  it("toggles all-options between hiding and restoring every visible point", async () => {
    const user = userEvent.setup();
    const { container } = renderBenchmarkInsights(buildFamilyVariantRows());

    await screen.findByRole("img", {
      name: /benchmark accuracy versus runtime scatter plot/i,
    });

    expect(container.querySelectorAll("[data-scatter-point]")).toHaveLength(4);

    await user.click(
      screen.getByRole("button", {
        name: /filter accuracy-vs-runtime chart by family/i,
      }),
    );

    const allFamiliesOption = screen
      .getAllByText("All families")
      .find((node) => node.closest("[cmdk-item]") !== null);
    expect(allFamiliesOption).toBeTruthy();
    await user.click(allFamiliesOption!);

    await waitFor(() => {
      expect(container.querySelectorAll("[data-scatter-point]")).toHaveLength(0);
    });
    expect(
      screen.getByText(/no completed scored rows match the current chart filters/i),
    ).toBeInTheDocument();

    const allFamiliesOptionAgain = (await screen.findAllByText("All families")).find(
      (node) => node.closest("[cmdk-item]") !== null,
    );
    expect(allFamiliesOptionAgain).toBeTruthy();
    await user.click(allFamiliesOptionAgain!);

    await waitFor(() => {
      expect(container.querySelectorAll("[data-scatter-point]")).toHaveLength(4);
    });

    await user.click(
      screen.getByRole("button", {
        name: /filter accuracy-vs-runtime chart by algorithm/i,
      }),
    );

    const allAlgorithmsOption = screen
      .getAllByText("All algorithms")
      .find((node) => node.closest("[cmdk-item]") !== null);
    expect(allAlgorithmsOption).toBeTruthy();
    await user.click(allAlgorithmsOption!);

    await waitFor(() => {
      expect(container.querySelectorAll("[data-scatter-point]")).toHaveLength(0);
    });

    const allAlgorithmsOptionAgain = (await screen.findAllByText("All algorithms")).find(
      (node) => node.closest("[cmdk-item]") !== null,
    );
    expect(allAlgorithmsOptionAgain).toBeTruthy();
    await user.click(allAlgorithmsOptionAgain!);

    await waitFor(() => {
      expect(container.querySelectorAll("[data-scatter-point]")).toHaveLength(4);
    });
  });

  it("downloads the visible scatter data as CSV", async () => {
    const user = userEvent.setup();
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    const createObjectURL = vi.fn((_: Blob | MediaSource) => "blob:scatter-export");
    const revokeObjectURL = vi.fn();

    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL,
      revokeObjectURL,
    });

    renderBenchmarkInsights(buildFamilyVariantRows());

    await user.click(
      await screen.findByRole("button", {
        name: /download accuracy-vs-runtime chart exports/i,
      }),
    );
    await user.click(screen.getByRole("button", { name: /csv \(visible points\)/i }));

    expect(clickSpy).toHaveBeenCalledOnce();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:scatter-export");

    const blob = createObjectURL.mock.calls[0]?.[0];
    expect(blob).toBeInstanceOf(Blob);
    await expect((blob as Blob).text()).resolves.toContain(
      '"runtime_minutes","abs_error_mha","energy_ha"',
    );
  });

  it("downloads the visible scatter SVG as a styled snapshot of the current panel", async () => {
    const user = userEvent.setup();
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    const createObjectURL = vi.fn((_: Blob | MediaSource) => "blob:scatter-export");
    const revokeObjectURL = vi.fn();

    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL,
      revokeObjectURL,
    });

    renderBenchmarkInsights(buildDenseScatterRows());

    await user.click(
      await screen.findByRole("button", {
        name: /download accuracy-vs-runtime chart exports/i,
      }),
    );
    await user.click(screen.getByRole("button", { name: /svg \(visible chart\)/i }));

    expect(clickSpy).toHaveBeenCalledOnce();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:scatter-export");

    const blob = createObjectURL.mock.calls[0]?.[0];
    expect(blob).toBeInstanceOf(Blob);

    const markup = await (blob as Blob).text();
    expect(markup).toContain("<foreignObject");
    expect(markup).toContain("Legend");
    expect(markup).toContain("background-color:");
    expect(markup).toContain("Benchmark accuracy versus runtime scatter plot");
    expect(markup).not.toContain("Accuracy vs runtime");
    expect(markup).not.toContain("Families");
    expect(markup).not.toContain("Algorithms");
    expect(markup).not.toContain("Molecules");
    expect(markup).not.toContain("Showing 15 of 15 points");
  });
});
