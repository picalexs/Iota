import { render as rtlRender, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import userEvent from "@testing-library/user-event";
import type { ComponentProps, PropsWithChildren, ReactElement } from "react";
import { describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { BenchmarkControls } from "./benchmark-controls";
import type { MoleculeResponse, RunAlgorithm } from "@/types/run";
import type { BenchmarkAlgorithmVariant } from "./benchmark-variants";

function TestQueryProvider({ children }: PropsWithChildren) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        enabled: false,
        retry: false,
      },
    },
  });

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

function render(ui: ReactElement) {
  return rtlRender(ui, { wrapper: TestQueryProvider });
}

async function flushBasisSetLoad() {
  await screen.findByText("Server basis");
}

vi.mock("@/api/molecules", () => ({
  fetchBasisSets: vi.fn().mockResolvedValue({
    default_basis_set: "server-basis",
    basis_sets: [
      {
        id: "server-basis",
        label: "Server basis",
        description: "Server-provided basis",
        family: "minimal",
        recommended: true,
        supported_elements: [],
      },
    ],
  }),
  fetchMolecules: vi.fn(),
}));

function makeMolecule(id: string, name: string): MoleculeResponse {
  return {
    id,
    name,
    iupac_name: name,
    description: `${name} molecule`,
    atoms: [],
    charge: 0,
    multiplicity: 1,
    active_space: { n_electrons: 2, n_orbitals: 2 },
    basis_set: "sto-3g",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  };
}

function makeDefaultProps(overrides: Partial<ComponentProps<typeof BenchmarkControls>> = {}) {
  const selectedAlgorithms = new Set<RunAlgorithm>(["vqe"]);
  return {
    selectedMolecules: new Set<string>(["h2"]),
    selectedAlgorithms,
    disabledAlgorithms: new Map(),
    selectedBasis: "sto-3g",
    selectedBackendMode: "statevector",
    selectedBackendName: null,
    backendOptions: [
      { value: "statevector", label: "Statevector (exact)", enabled: true },
      { value: "aer_simulator", label: "Aer simulator", enabled: true },
      {
        value: "aer_simulator_backend_noise",
        label: "Aer simulator with backend noise",
        enabled: false,
      },
      { value: "ibm_runtime", label: "IBM Quantum backend", enabled: false },
    ],
    ibmBackends: [],
    backendSelectionRequired: false,
    backendReady: true,
    chemicalAccuracyHa: 0.0016,
    customMolecules: [],
    running: false,
    hasPausedBenchmark: false,
    canPauseBenchmark: false,
    pauseInProgress: false,
    resumeInProgress: false,
    restartInProgress: false,
    total: 0,
    done: 0,
    backendHelperText: null,
    onToggleMolecule: vi.fn(),
    onToggleAlgorithm: vi.fn(),
    onSetMolecules: vi.fn(),
    onSetAlgorithms: vi.fn(),
    onBenchmarkModeChange: vi.fn(),
    onAddAdvancedVariant: vi.fn(),
    onSetAdvancedVariantCount: vi.fn(),
    onDuplicateAdvancedVariant: vi.fn(),
    onUpdateAdvancedVariant: vi.fn(),
    onRemoveAdvancedVariant: vi.fn(),
    onBasisChange: vi.fn(),
    onBackendModeChange: vi.fn(),
    onBackendNameChange: vi.fn(),
    onBackendOptionsOpen: vi.fn(),
    onChemicalAccuracyChange: vi.fn(),
    onAddCustomMolecule: vi.fn(),
    onRemoveCustomMolecule: vi.fn(),
    onRunBenchmark: vi.fn(),
    onPauseBenchmark: vi.fn(),
    onResumeBenchmark: vi.fn(),
    onRestartBenchmark: vi.fn(),
    onCancelBenchmark: vi.fn(),
    showDeleteBenchmarkAction: false,
    deleteBenchmarkInProgress: false,
    onDeleteBenchmark: vi.fn(),
    onClear: vi.fn(),
    ...overrides,
  } satisfies ComponentProps<typeof BenchmarkControls>;
}

describe("BenchmarkControls", () => {
  it("uses the server-provided chemical-accuracy target threshold", async () => {
    render(
      <BenchmarkControls
        {...makeDefaultProps({
          chemicalAccuracyTargetOptions: [
            { goal: "fastest", label: "Server quick target", thresholdHa: 0.005 },
          ],
        })}
      />,
    );

    await flushBasisSetLoad();

    expect(screen.getByLabelText("Editable chemical accuracy target")).toHaveValue(1.6);
    expect(screen.queryByRole("button", { name: "0.5 mHa" })).not.toBeInTheDocument();
  });

  it("shows a custom accuracy placeholder and a bright selected preset", async () => {
    render(<BenchmarkControls {...makeDefaultProps()} />);

    await flushBasisSetLoad();

    expect(screen.getByLabelText("Editable chemical accuracy target")).toHaveValue(null);
    expect(screen.getByLabelText("Editable chemical accuracy target")).toHaveAttribute(
      "placeholder",
      "5.0",
    );
    expect(screen.getByRole("button", { name: "1.6 mHa" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "1.6 mHa" })).toHaveClass("bg-interactive-selected");
  });

  it("allows shots to be cleared before entering a new value", async () => {
    const user = userEvent.setup();
    const onShotsChange = vi.fn();
    const props = makeDefaultProps({ onShotsChange });
    render(<BenchmarkControls {...props} />);

    await flushBasisSetLoad();

    const shotsInput = screen.getByLabelText("Shots");
    await user.clear(shotsInput);
    expect(shotsInput).toHaveValue(null);

    await user.type(shotsInput, "1000");
    expect(shotsInput).toHaveValue(1000);
    expect(onShotsChange).toHaveBeenLastCalledWith(1000);
  });

  it("shows a remove button for built-in molecules and removes them from the benchmark", async () => {
    const user = userEvent.setup();
    const props = makeDefaultProps();

    const { rerender } = render(<BenchmarkControls {...props} />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /remove hydrogen \(h₂\) from benchmark/i }),
      ).toBeInTheDocument();
    });

    await user.click(
      screen.getByRole("button", { name: /remove hydrogen \(h₂\) from benchmark/i }),
    );

    expect(props.onSetMolecules).toHaveBeenCalledWith([]);

    rerender(<BenchmarkControls {...props} selectedMolecules={new Set()} />);
    expect(screen.queryByText("Hydrogen (H₂)")).not.toBeInTheDocument();
  });

  it("shows a remove button for unselected built-in molecules", async () => {
    render(<BenchmarkControls {...makeDefaultProps({ selectedMolecules: new Set() })} />);

    expect(
      await screen.findByRole("button", { name: /remove hydrogen \(h₂\) from benchmark/i }),
    ).toBeInTheDocument();
  });

  it("adds random molecules without clearing the existing selection", async () => {
    const user = userEvent.setup();
    const props = makeDefaultProps();
    const { fetchMolecules } = await import("@/api/molecules");

    vi.mocked(fetchMolecules).mockResolvedValue({
      total: 6,
      items: [
        makeMolecule("random-1", "Random 1"),
        makeMolecule("random-2", "Random 2"),
        makeMolecule("random-3", "Random 3"),
        makeMolecule("random-4", "Random 4"),
        makeMolecule("random-5", "Random 5"),
        makeMolecule("random-6", "Random 6"),
      ],
    });

    render(<BenchmarkControls {...props} />);

    await user.click(await screen.findByRole("button", { name: /random 6/i }));

    expect(props.onAddCustomMolecule).toHaveBeenCalledTimes(6);
    expect(props.onSetMolecules).toHaveBeenCalledTimes(1);
    expect(props.onSetMolecules).toHaveBeenCalledWith(
      expect.arrayContaining([
        "h2",
        "custom:random-1",
        "custom:random-2",
        "custom:random-3",
        "custom:random-4",
        "custom:random-5",
        "custom:random-6",
      ]),
    );
  });

  it("renders the add-from-library trigger with the neutral button surface", async () => {
    render(<BenchmarkControls {...makeDefaultProps()} />);

    const addFromLibrary = await screen.findByRole("button", { name: /add from library/i });
    expect(addFromLibrary.className).toContain("bg-surface-raised");
  });

  it("locks execution controls after a completed benchmark", async () => {
    render(
      <BenchmarkControls
        {...makeDefaultProps({
          total: 1,
          done: 1,
          selectedBackendMode: "ibm_runtime",
        })}
      />,
    );

    await screen.findByLabelText("Shots");

    expect(screen.getByLabelText("Shots")).toBeDisabled();
    expect(screen.getByLabelText("Transpiler seed")).toBeDisabled();
    expect(screen.getByRole("checkbox", { name: "Dynamical decoupling" })).toBeDisabled();
    expect(screen.getByRole("checkbox", { name: "Twirling" })).toBeDisabled();
  });

  it("hides IBM Runtime policy controls for local backends", async () => {
    render(<BenchmarkControls {...makeDefaultProps()} />);

    await screen.findByLabelText("Shots");

    expect(
      screen.queryByRole("checkbox", { name: "Dynamical decoupling" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("checkbox", { name: "Twirling" })).not.toBeInTheDocument();
  });

  it("renders unselected benchmark option cards with the raised surface", async () => {
    render(
      <BenchmarkControls
        {...makeDefaultProps({
          selectedMolecules: new Set(),
          selectedAlgorithms: new Set(),
        })}
      />,
    );

    const moleculeButton = await screen.findByRole("button", { name: /H2\s+Hydrogen/i });
    const moleculeCard = moleculeButton.parentElement;
    const algorithmLabel = screen.getByText("VQE");
    const algorithmCard = algorithmLabel.closest("button");

    expect(moleculeCard?.className).toContain("data-[selected=false]:!bg-surface-raised");
    expect(algorithmCard?.className).toContain("data-[selected=false]:!bg-surface-raised");
  });

  it("keeps KQD and QFD selectable in Aer backend-noise mode", async () => {
    const user = userEvent.setup();
    const props = makeDefaultProps({
      selectedAlgorithms: new Set(),
      disabledAlgorithms: new Map(),
    });

    render(<BenchmarkControls {...props} />);

    const allButton = await screen.findByRole("button", { name: /^all$/i });
    await user.click(allButton);

    expect(props.onSetAlgorithms).toHaveBeenCalledWith(["vqe", "sqd", "kqd", "qfd", "qse", "skqd"]);
    expect(screen.getByText("KQD").closest("button")).not.toBeDisabled();
    expect(screen.getByText("QFD").closest("button")).not.toBeDisabled();
  });

  it("uses +/- row controls in advanced mode instead of adding rows from the card body", async () => {
    const user = userEvent.setup();
    const props = makeDefaultProps({
      benchmarkMode: "advanced",
      selectedAlgorithms: new Set(),
      algorithmVariants: [],
    });

    render(<BenchmarkControls {...props} />);

    await user.click(screen.getByText("VQE"));
    expect(props.onAddAdvancedVariant).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: /add vqe comparison row/i }));
    expect(props.onAddAdvancedVariant).toHaveBeenCalledWith("vqe");
  });

  it("auto-collapses advanced rows while a benchmark is running and lets them be reopened", async () => {
    const user = userEvent.setup();
    const vqeVariant: BenchmarkAlgorithmVariant = {
      id: "variant-1",
      algorithm: "vqe",
      mode: "advanced",
      label: "Fastest",
      easyGoal: null,
      advancedConfig: {
        algorithm: "vqe",
        ansatz_name: "EfficientSU2",
        optimizer_name: "COBYLA",
        max_iterations: 120,
        max_function_evaluations: 1200,
        reps: 1,
        optimizer_options: null,
        initial_parameters: null,
        initial_point_strategy: "zero_plus_seeded_random",
        initial_point_candidates: 2,
        seed: null,
        convergence_threshold: null,
        parameter_bounds: null,
      },
    };
    render(
      <TooltipProvider>
        <BenchmarkControls
          {...makeDefaultProps({
            benchmarkMode: "advanced",
            running: true,
            selectedAlgorithms: new Set(),
            algorithmVariants: [vqeVariant],
          })}
        />
      </TooltipProvider>,
    );

    const groupToggle = await screen.findByRole("button", { name: /expand vqe rows/i });
    expect(groupToggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("textbox", { name: /row label/i })).not.toBeInTheDocument();

    await user.click(groupToggle);

    const toggle = await screen.findByRole("button", {
      name: /expand row details for vqe fastest/i,
    });
    expect(toggle).toHaveAttribute("aria-expanded", "false");

    await user.click(toggle);

    expect(screen.getByRole("textbox", { name: /row label/i })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /collapse row details for vqe fastest/i }),
    ).toHaveAttribute("aria-expanded", "true");
  });

  it("keeps advanced rows collapsed after a benchmark has already been launched", async () => {
    const vqeVariant: BenchmarkAlgorithmVariant = {
      id: "variant-1",
      algorithm: "vqe",
      mode: "advanced",
      label: "Fastest",
      easyGoal: null,
      advancedConfig: {
        algorithm: "vqe",
        ansatz_name: "EfficientSU2",
        optimizer_name: "COBYLA",
        max_iterations: 120,
        max_function_evaluations: 1200,
        reps: 1,
        optimizer_options: null,
        initial_parameters: null,
        initial_point_strategy: "zero_plus_seeded_random",
        initial_point_candidates: 2,
        seed: null,
        convergence_threshold: null,
        parameter_bounds: null,
      },
    };

    render(
      <TooltipProvider>
        <BenchmarkControls
          {...makeDefaultProps({
            benchmarkMode: "advanced",
            total: 1,
            selectedAlgorithms: new Set(),
            algorithmVariants: [vqeVariant],
          })}
        />
      </TooltipProvider>,
    );

    await flushBasisSetLoad();

    expect(screen.getByRole("button", { name: /expand vqe rows/i })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    expect(screen.queryByRole("textbox", { name: /row label/i })).not.toBeInTheDocument();
  });

  it("groups advanced rows inside collapsible algorithm tiles", async () => {
    const user = userEvent.setup();
    const firstVqeVariant: BenchmarkAlgorithmVariant = {
      id: "variant-1",
      algorithm: "vqe",
      mode: "simple",
      label: "Fastest",
      easyGoal: "fastest",
      advancedConfig: null,
    };
    const secondVqeVariant: BenchmarkAlgorithmVariant = {
      id: "variant-2",
      algorithm: "vqe",
      mode: "simple",
      label: "Balanced",
      easyGoal: "balanced",
      advancedConfig: null,
    };

    render(
      <TooltipProvider>
        <BenchmarkControls
          {...makeDefaultProps({
            benchmarkMode: "advanced",
            selectedAlgorithms: new Set(),
            algorithmVariants: [firstVqeVariant, secondVqeVariant],
          })}
        />
      </TooltipProvider>,
    );

    expect(screen.getByText("2 rows")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /collapse vqe rows/i })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    expect(screen.getAllByText("Fastest").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Balanced").length).toBeGreaterThan(0);

    await user.click(screen.getByRole("button", { name: /collapse vqe rows/i }));

    expect(screen.getByRole("button", { name: /expand vqe rows/i })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    expect(screen.queryByRole("textbox", { name: /row label/i })).not.toBeInTheDocument();
  });

  it("locks advanced benchmark configuration after results exist and exposes clear results", async () => {
    const vqeVariant: BenchmarkAlgorithmVariant = {
      id: "variant-1",
      algorithm: "vqe",
      mode: "simple",
      label: "Fastest",
      easyGoal: "fastest",
      advancedConfig: null,
    };

    render(
      <TooltipProvider>
        <BenchmarkControls
          {...makeDefaultProps({
            benchmarkMode: "advanced",
            total: 1,
            selectedAlgorithms: new Set(),
            algorithmVariants: [vqeVariant],
          })}
        />
      </TooltipProvider>,
    );

    await flushBasisSetLoad();

    expect(screen.getByRole("button", { name: /clear results/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /add vqe comparison row/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /advanced benchmark/i })).toBeDisabled();
  });

  it("confirms before deleting all visible molecules", async () => {
    const user = userEvent.setup();
    const props = makeDefaultProps({
      selectedMolecules: new Set(["h2", "custom:custom-1"]),
      customMolecules: [makeMolecule("custom-1", "Custom 1")],
    });

    render(<BenchmarkControls {...props} />);

    await user.click(await screen.findByRole("button", { name: /delete all molecules/i }));

    expect(
      screen.getByRole("heading", { name: /delete all molecules from this benchmark/i }),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /^delete all molecules$/i }));

    expect(props.onSetMolecules).toHaveBeenCalledWith([]);
    expect(props.onRemoveCustomMolecule).toHaveBeenCalledWith("custom-1");
  });

  it("shows benchmark-wide actions in the overflow menu", async () => {
    const user = userEvent.setup();
    const props = makeDefaultProps({
      hasPausedBenchmark: true,
      showDeleteBenchmarkAction: true,
    });

    render(<BenchmarkControls {...props} />);

    await user.click(await screen.findByRole("button", { name: /benchmark actions/i }));

    expect(screen.getByRole("button", { name: /resume benchmark/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /restart benchmark/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /delete benchmark/i })).toBeInTheDocument();
  });

  it("keeps backend, basis, and accuracy controls grouped when a backend is required", async () => {
    render(
      <BenchmarkControls
        {...makeDefaultProps({
          selectedBackendMode: "aer_simulator_backend_noise",
          selectedBackendName: "ibm_pittsburgh",
          backendSelectionRequired: true,
          ibmBackends: [
            {
              name: "ibm_pittsburgh",
              simulator: false,
              operational: true,
              pending_jobs: 3,
              num_qubits: 127,
              error_rate: 0.001,
            },
          ],
        })}
      />,
    );

    const executionSettings = await screen.findByTestId("benchmark-execution-settings");
    expect(executionSettings.className).toContain("border-t");
    expect(screen.getByRole("combobox", { name: "Backend" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Basis set" })).toBeInTheDocument();
    expect(screen.getByLabelText("Editable chemical accuracy target")).toBeInTheDocument();
    expect(screen.getByText("Noise reference backend")).toBeInTheDocument();
  });

  it("shows least-error and least-busy benchmark suggestions without repeating those backends below", async () => {
    const user = userEvent.setup();
    const props = makeDefaultProps({
      selectedBackendMode: "ibm_runtime",
      selectedBackendName: "ibm_brisbane",
      backendSelectionRequired: true,
      ibmBackends: [
        {
          name: "ibm_berlin",
          simulator: false,
          operational: true,
          pending_jobs: 3,
          num_qubits: 120,
          error_rate: 0.0015,
        },
        {
          name: "ibm_brisbane",
          simulator: false,
          operational: true,
          pending_jobs: 0,
          num_qubits: 127,
          error_rate: 0.0012,
        },
        {
          name: "ibm_aachen",
          simulator: false,
          operational: true,
          pending_jobs: 1,
          num_qubits: 156,
          error_rate: 0.0009,
        },
      ],
    });

    render(<BenchmarkControls {...props} />);

    await user.click(await screen.findByRole("combobox", { name: /ibm backend/i }));

    expect(screen.getByRole("option", { name: /least error: ibm_aachen/i })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /least busy: ibm_brisbane/i })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /^ibm_berlin/i })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: /^ibm_aachen$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("option", { name: /^ibm_brisbane$/i })).not.toBeInTheDocument();
  });
});
