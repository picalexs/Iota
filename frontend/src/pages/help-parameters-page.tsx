import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

type HelpSection = {
  id: string;
  title: string;
  summary: string;
};

const SECTIONS: HelpSection[] = [
  {
    id: "molecule",
    title: "Molecule",
    summary:
      "Select the molecule you want to simulate. It determines the geometry, electron count, and the default chemistry metadata used by the run form.",
  },
  {
    id: "algorithm",
    title: "Algorithm",
    summary:
      "Choose the algorithm family that will drive the calculation. The available settings shown below depend on this choice.",
  },
  {
    id: "mode",
    title: "Mode",
    summary:
      "Easy mode keeps the configuration compact and focused on a goal. Advanced mode exposes the lower-level parameters directly.",
  },
  {
    id: "goal",
    title: "Preset goal",
    summary:
      "Easy-mode presets bundle algorithm-specific defaults around a runtime-versus-accuracy target. The selected preset changes the concrete controls that are sent for the active algorithm.",
  },
  {
    id: "backend_target",
    title: "Backend target",
    summary:
      "Pick the execution backend. Local simulator targets are typically faster to iterate on, while runtime targets send jobs to IBM Quantum hardware or managed services.",
  },
  {
    id: "backend_name",
    title: "Backend",
    summary:
      "Select the concrete Aer or IBM backend device. Policy choices such as least-error or least-busy are resolved at submission time against the currently available calibrated devices.",
  },
  {
    id: "shots",
    title: "Shots",
    summary:
      "Sets how many repeated circuit samples are taken on shot-based backends. More shots usually reduce sampling noise but increase runtime and queue cost.",
  },
  {
    id: "optimization_level",
    title: "Optimization level",
    summary:
      "Controls how aggressively the transpiler rewrites and maps circuits before execution. Higher levels can reduce circuit cost, but they may take longer to compile.",
  },
  {
    id: "aer_method",
    title: "Aer method",
    summary:
      "Chooses the internal simulation strategy used by Aer. Dense statevector and density-matrix paths are straightforward, while matrix-product-state and stabilizer methods can be better fits for specific circuit structures.",
  },
  {
    id: "seed_simulator",
    title: "Simulator seed",
    summary:
      "Seeds Aer's random-number generation for sampling and noisy simulation so repeated runs can be made reproducible.",
  },
  {
    id: "seed_transpiler",
    title: "Transpiler seed",
    summary:
      "Seeds stochastic transpiler passes, which helps reproduce layout and routing decisions when multiple valid mappings exist.",
  },
  {
    id: "basis_set",
    title: "Basis set",
    summary:
      "Controls the orbital basis used to represent the molecule. Leave it empty to use the molecule default, or choose a preset when you want to override it.",
  },
  {
    id: "ansatz",
    title: "Ansatz",
    summary:
      "Defines the parameterized circuit template used by variational algorithms. For VQE, Quantum Studio currently exposes hardware-efficient templates such as EfficientSU2, RealAmplitudes, and TwoLocal, with depth (`reps`) controlling the circuit-cost tradeoff.",
  },
  {
    id: "chemical_accuracy_target_ha",
    title: "Chemical accuracy target",
    summary:
      "Sets the per-run threshold used when run detail compares the final energy against the available CASCI active-space reference. If this value is absent, the frontend falls back to 1.6e-3 Ha (1.60 mHa).",
  },
  {
    id: "optimizer",
    title: "Optimizer",
    summary:
      "Selects the classical optimizer that updates variational parameters between iterations. Some optimizers are more stable, while others converge faster on easy landscapes.",
  },
  {
    id: "optimizer_options",
    title: "Optimizer options",
    summary:
      "Optional JSON object passed into the selected optimizer after frontend validation. Use it for supported low-level knobs such as tolerances or trust-region settings.",
  },
  {
    id: "initial_point_strategy",
    title: "Initial point strategy",
    summary:
      "Controls how VQE chooses starting parameters before optimization. Evaluating several starts can avoid poor local minima.",
  },
  {
    id: "initial_point_candidates",
    title: "Starting candidates",
    summary:
      "Sets how many VQE starting points are scored before the optimizer starts from the best one.",
  },
  {
    id: "reps",
    title: "Ansatz depth",
    summary:
      "Sets how many repeated layers are used in the chosen ansatz circuit. Larger depths can express more states, but they also increase parameter count and circuit cost.",
  },
  {
    id: "max_iterations",
    title: "Max iterations",
    summary:
      "Limits how many optimization or SQD recovery rounds the job may take before stopping. Fixed-work methods like KQD, QFD, QSE, and SKQD use their own subspace, sampling, or Krylov settings.",
  },
  {
    id: "seed",
    title: "Seed",
    summary:
      "Fixes the algorithm-level random seed used by stochastic initialization or sampling paths so a run can be reproduced more closely.",
  },
  {
    id: "convergence_threshold",
    title: "Convergence threshold",
    summary:
      "Optional stopping threshold for variational progress. Smaller values demand tighter convergence before the solver stops early.",
  },
  {
    id: "max_function_evaluations",
    title: "Max function evaluations",
    summary:
      "Hard cap on VQE objective-energy evaluations, including starting-point checks. Gradient-based optimizers can use many evaluations per optimizer step.",
  },
  {
    id: "initial_parameters",
    title: "Initial parameters",
    summary:
      "Optional JSON array of explicit variational parameters used instead of relying only on the configured start strategy.",
  },
  {
    id: "parameter_bounds",
    title: "Parameter bounds",
    summary:
      "Optional JSON array of `[min, max]` pairs that clamps each variational parameter during optimization.",
  },
  {
    id: "samples_per_batch",
    title: "Samples per batch",
    summary:
      "Controls one factor of the SQD sampling budget. Current SQD multiplies this by the number of batches to decide total samples per iteration.",
  },
  {
    id: "samples_per_state",
    title: "Samples per Krylov state",
    summary:
      "Controls how many computational-basis samples SKQD collects from each sampled Krylov state before it merges the determinant union.",
  },
  {
    id: "num_batches",
    title: "Number of batches",
    summary:
      "Controls the other factor of the SQD sampling budget. It is used as a total-sample multiplier, not as separate backend jobs.",
  },
  {
    id: "max_dim",
    title: "Selected-CI cap",
    summary:
      "Caps how many determinants the SQD or SKQD selected-CI refinement keeps. You can use one shared cap or separate alpha and beta sector limits.",
  },
  {
    id: "sci_solver_options",
    title: "Selected-CI solver JSON",
    summary:
      "Optional JSON object forwarded to the selected-CI solver for expert-level overrides that are not promoted to first-class form controls.",
  },
  {
    id: "krylov_dim",
    title: "Krylov dimension",
    summary:
      "Defines the size of the Krylov subspace used by Krylov-based methods. Higher values can improve accuracy at the cost of extra work.",
  },
  {
    id: "time_step",
    title: "Time step",
    summary:
      "Chooses the numerical step size for time evolution. Smaller steps are more accurate but usually require more evaluations.",
  },
  {
    id: "evolution_method",
    title: "Evolution method",
    summary:
      "Selects the strategy used to approximate or simulate time evolution. The best option depends on the target algorithm and backend constraints.",
  },
  {
    id: "trotter_steps",
    title: "Trotter steps",
    summary:
      "Controls how finely KQD or QFD real-time evolution is split when a Trotterized evolution path is used. It is capped at 32.",
  },
  {
    id: "residual_tolerance",
    title: "Residual tolerance",
    summary:
      "Threshold used to mark fixed-work subspace solvers converged after they finish their configured basis or time-grid work.",
  },
  {
    id: "num_time_points",
    title: "Number of time points",
    summary:
      "Sets how many output samples are taken across the evolution interval. Use more points when you want a finer time series.",
  },
  {
    id: "max_time",
    title: "Max time",
    summary:
      "Defines the upper bound of the simulation window. Combined with the time step, this determines the overall duration of the evolution scan.",
  },
  {
    id: "reference_method",
    title: "Reference method",
    summary:
      "Specifies the QSE reference. VQE and full provided-state references are small-system paths; HF is the scalable fixed-sector option.",
  },
  {
    id: "provided_state_vector",
    title: "Provided state vector",
    summary:
      "Supplies a full dense QSE reference state as JSON amplitudes. This is intended for small systems where you already know or generated the complete statevector externally.",
  },
  {
    id: "excitation_level",
    title: "Excitation level",
    summary:
      "Controls how many excitations are included in excitation-based ansatz families. Higher levels are more expressive but can be harder to optimize.",
  },
  {
    id: "max_subspace_dim",
    title: "Max subspace dimension",
    summary:
      "Caps the projected QSE basis size. Large HF/provided-sector QSE uses the same cap while avoiding full dense Hamiltonian matrices.",
  },
  {
    id: "vqe_reference_max_iterations",
    title: "Reference VQE iterations",
    summary: "Sets the VQE optimization budget used to build a QSE reference state.",
  },
  {
    id: "vqe_reference_reps",
    title: "Reference VQE depth",
    summary: "Controls the ansatz depth used during the QSE reference-state VQE solve.",
  },
  {
    id: "regularization",
    title: "Regularization",
    summary:
      "Adds an optional diagonal stabilizer to the QSE overlap solve when you need extra numerical damping.",
  },
  {
    id: "overlap_threshold",
    title: "Overlap threshold",
    summary:
      "Filters very small-overlap candidate basis states out of the projected QSE solve to keep the subspace numerically stable.",
  },
  {
    id: "krylov_extension_dim",
    title: "Krylov extension dimension",
    summary:
      "Sets how many sampled Krylov states SKQD includes in its cumulative determinant union. Larger values can improve coverage but increase circuit and selected-CI work.",
  },
  {
    id: "time_grid_type",
    title: "Time grid type",
    summary:
      "Chooses how time samples are spaced across the evolution window. Use a uniform linear grid or a geometric grid with more resolution near zero.",
  },
];

export function HelpParametersPage() {
  return (
    <main className="mx-auto flex w-full max-w-5xl flex-col gap-8 px-4 py-12 md:px-8">
      <header className="space-y-3">
        <p className="text-sm font-medium uppercase tracking-[0.2em] text-muted-foreground">
          Parameter Help
        </p>
        <h1 className="text-3xl font-semibold tracking-tight">Run configuration glossary</h1>
        <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
          Hover the ? icons in the run form for a short hint, or use this page for the full
          glossary. Each section below has a stable anchor so the tooltip links can jump directly to
          the right explanation, while the bigger chemistry and VQE controls now also have longer
          articles under the Reference area.
        </p>
      </header>

      <div className="grid gap-4">
        {SECTIONS.map(({ id, title, summary }) => (
          <section key={id} id={id} className="scroll-mt-24">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">{title}</CardTitle>
                <CardDescription className="text-sm">
                  Anchor: <code className="rounded bg-muted px-1.5 py-0.5 text-xs">{id}</code>
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-2 text-sm leading-6 text-muted-foreground">
                <p>{summary}</p>
              </CardContent>
            </Card>
          </section>
        ))}
      </div>
    </main>
  );
}

export default HelpParametersPage;
