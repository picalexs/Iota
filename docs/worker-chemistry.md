# Worker Chemistry Algorithms

This guide explains how the worker selects and runs chemistry algorithms.
Use it when you maintain an existing algorithm or add a new one.

## Execution flow

The worker follows this flow:

1. `worker/jobs/execute_run.py` prepares the Hamiltonian and backend context.
2. `worker/jobs/dispatcher.py` looks up a package-owned `AlgorithmDefinition`.
3. The definition selects the required primitive and workflow entry point.
4. The algorithm resolves its configuration and runs its workflow.
5. `worker/adapters/result_adapter.py` normalizes the typed result for storage.

The dispatcher owns the generic dispatch boundary. Each algorithm package owns
its definition, primitive decision, and workflow entry point.

## Module ownership

| Module | Owns |
| --- | --- |
| `worker/chemistry/algorithm_contracts.py` | Shared definition and primitive contracts. |
| `worker/chemistry/algorithms/registry.py` | Static list of package-owned definitions. |
| `worker/jobs/dispatcher.py` | Generic lookup, configuration resolution, and runner call. |
| `worker/adapters/aer_noise.py` | Aer noise validation, model construction, topology, and provenance. |
| `worker/chemistry/projected_execution.py` | KQD/QFD path selection and QSE measurement policy. |
| `worker/chemistry/types.py` | Shared execution-plan and result records. |
| `worker/chemistry/algorithms/<name>/config.py` | Resolved options and validation for one algorithm. |
| `worker/chemistry/algorithms/<name>/` | Algorithm-specific kernels, execution helpers, and result builders. |
| `worker/adapters/result_adapter.py` | Conversion from worker results to persisted API payloads. |
| `worker/chemistry/algorithms/<name>/workflow.py` | Public workflow entry point for one algorithm. |

Algorithm package roots keep no shared workflow exports. Prefer explicit
imports from the owning module in new code.

## Aer noise contract

An absent `noise_profile` uses ideal Aer simulation. A `custom_preset` builds
only the selected synthetic error model. A `backend_derived` profile loads the
named IBM backend through the active credential profile and builds a local Aer
model from its calibration data.

The worker rejects simulator names, missing credentials, unavailable backend
references, unknown fields, and incomplete preset parameters. It records the
requested and resolved backend names, temperature, topology, basis gates, and
model fingerprint in non-secret metadata. It does not substitute another
backend.

## Add an algorithm

Complete these steps in order:

1. Add the algorithm identifier to `shared/contracts/identifiers.py`.
2. Create `worker/chemistry/algorithms/<name>/`.
3. Add `config.py` with one frozen resolved configuration record.
4. Add `workflow.py` for the public algorithm workflow.
5. Add `definition.py` with `ALGORITHM_DEFINITION`, its primitive requirement,
   and its package-owned runner.
6. Add the definition to the static tuple in
   `worker/chemistry/algorithms/registry.py`.
7. Add `execution.py` only when the algorithm has a separate execution path.
8. Add `results.py` for result construction and completion progress.
9. Add tests for configuration, kernels, workflow, dispatch, and result mapping.
10. Update this guide and the worker capability documentation.

Do not add an algorithm-specific branch to `worker/jobs/dispatcher.py`. Keep
backend execution strategies separate from algorithm definitions.

Keep backend execution strategies separate from algorithms. For example,
branch-estimator, sector matrix-free, and dense projected execution are paths
used by KQD or QFD. They are not separate algorithms.

## Required execution metadata

Every algorithm result must preserve these meanings:

- requested backend target;
- actual execution path;
- primitive family, when a primitive ran;
- path selection reason;
- primary energy and iteration units; and
- convergence state and convergence reason.

Branch-estimator KQD and QFD results include a worker-observed
`algorithm_metrics.matrix_element_summary.work_ledger`. It records primitive
run calls, successful runs, PUB count, and observable slots. SQD records its
sampler and recovery work in
`algorithm_metrics.sci_result_package.work_ledger`. These ledgers do not claim
provider billing or hidden runtime retries. Other algorithm work ledgers are
tracked separately before cross-algorithm benchmark comparisons.

Branch-estimator KQD and QFD measure projected Hamiltonian and overlap
matrices. Their residual is the residual of that measured generalized
eigenproblem. It is not a full-space Ritz residual. A small projected residual
does not prove scientific convergence. The worker records
`projected_solver_converged` for the projected solve. It leaves
`scientific_converged` unknown when the projected system is stable and keeps
top-level `converged` false because the full-space residual is unavailable. A
stable projected energy can still be reported as an estimate. Dense and
fixed-sector paths calculate a full-space residual and can apply their
convergence threshold.

QFD branch-estimator runs use seven time points when the user omits the count.
The branch path supports at most eight points. The worker rejects larger
explicit values before it creates the estimator primitive. Dense and
fixed-sector QFD keep the sixteen-point default.

SKQD sample-union results record the same worker-observed sampler fields in
`algorithm_metrics.work_ledger`. Exact local sample oracles record
`local_exact_sampling_runs` and returned rows instead. Do not compare
these counts as provider shots. Use `sampling_source` and `execution_path` to
separate exact local, Aer, and IBM Runtime evidence.

The `legacy_statevector_extension` mode is a project-specific local Krylov
extension, not the paper's sampled SKQD circuit path. It seeds the extension
with the complex coefficients from the best selected-CI state. It does not
rebuild a wavefunction from sampled probabilities or occupancies. The worker
keeps this state in memory and does not add its coefficient matrix to the
persisted result. If the state is unavailable or invalid, the extension uses
its Hartree–Fock reference and records `seed_fallback_reason`.

The result labels this path as
`local_statevector_krylov_extension` and records the selected `reference_policy`.
An IBM Runtime sampler used by the
preceding SQD step does not make this local extension an IBM hardware
calculation. The direct sample-union mode uses separate sampler circuits when
the selected backend supports them. It uses an exact local statevector oracle
when it has no sampler backend.
For sampler circuits, Krylov index `k` uses `k` fixed `time_step` intervals.
The worker scales the Trotter repetition count with `k` so each interval keeps
the configured step size. Circuit metadata records the applied repetition
count.

VQE records `shot_budget_mode` as `fixed_shots`, `estimator_precision`, or
`exact_expectation`. Statevector execution and Aer EstimatorV2 with zero
precision use exact expectations. Precision-driven estimators report their
precision instead of a fixed shot count. VQE sets `shots_per_pub` and
`primitive_shots` to `null` for both paths. Adapter metadata keeps requested
shots separate from observed effective shots. IBM Runtime metadata does not
infer effective shots from the worker's configured shot value.

VQE counts objective callbacks separately from backend `run()` calls. It counts
`primitive_jobs` when the backend returns a job handle. It counts `primitive_pubs`
for those returned handles. For fixed-shot runs, `primitive_shots` is a nominal
estimate from configured shots per returned PUB. It is not a provider-reported
physical shot total. Check `primitive_shot_count_basis` before comparing totals.

QFD grid metadata records `symmetric_kappa` for the original symmetric variant
and `forward` for the chemistry-forward variant. The configured `max_time` and
`time_grid_type` do not define the symmetric grid.
The original symmetric variant requires `kappa` to cover the spectral width
plus an overage. If the user omits `kappa`, the worker derives it from the exact
dense spectrum or a conservative Pauli-coefficient L1 bound. The worker rejects
an explicit value below that bound. Grid metadata records the bound, overage,
and source.

Do not infer actual execution from the requested backend label. A local Aer
run is not IBM hardware evidence. A queued or planned run is not completed
execution evidence.

## Test tiers

Run the smallest relevant tier during development:

```sh
python3 -m compileall backend worker shared scripts/contracts
ruff check --select E4,E7,E9,F,I backend worker shared scripts/contracts
PYTHONPATH=. .venv/bin/pytest worker/tests/test_<algorithm>*.py -q
```

Before a merge request, run the full worker suite:

```sh
PYTHONPATH=. .venv/bin/pytest worker/tests -q
python3 scripts/checks/check-doc-targets.py
```

Use statevector or local Aer fixtures for algorithm tests. Do not submit an
IBM Runtime job as a test. Mark tests that use noisy Aer as local diagnostic
tests.

Worker configuration resolvers reject non-finite numeric values. They also
reject invalid SPSA step settings and malformed SKQD electron-sector or seed
data before the solver uses them.

## Current transition

The algorithm packages own the workflow entry points, kernels, configuration
records, result builders, and dispatch definitions. Keep shared chemistry
modules focused on cross-algorithm behavior. Remove a compatibility alias only
after all internal imports and tests use the package workflow.
