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

SQD retries failed sampler submissions only for adapters that allow local
retries. It uses at most three attempts with requested shot counts of `s`,
`2s`, and `4s`. IBM Runtime disables submission retries because a timeout can
leave the remote submission state unknown. After any sampler returns a job,
SQD retrieves that job's result once and does not submit a replacement if
result retrieval fails. The work ledger counts each worker attempt and its
requested shots. It does not claim that IBM accepted or billed those shots.

SQD measures one sample set for a run and reuses those rows for each recovery
iteration. `max_iterations` controls occupancy updates and selected-CI solves.
It does not request a new measurement set. The base shot request is
`samples_per_batch * num_batches`. A local retry can request more shots after a
submission error. Check the work ledger for the worker's requested total.
For balanced alpha and beta electron counts, an unset `spin_sq_target` uses the
closed-shell singlet target `S^2 = 0`. For open-shell counts, an unset target
does not impose a spin penalty. Set `spin_sq_target` explicitly when the
calculation requires a specific total-spin target.

SKQD uses the public `samples_per_state` limit of 4096. It keeps that number
of rows for every Krylov state. If a sampler returns fewer rows, SKQD stops
with an error. The [SKQD paper](https://arxiv.org/html/2501.09702) defines the
sampling procedure with the same sample count for each Krylov state. SKQD
retries use the same shot request each time. The work
ledger separates raw returned rows from retained rows and counts retries even
when their shot requests do not increase. This prevents a successful retry
from silently changing the sampling weight of one Krylov state.

Branch-estimator KQD and QFD measure projected Hamiltonian and overlap
matrices. Their residual is the residual of that measured generalized
eigenproblem. It is not a full-space Ritz residual. A small projected residual
does not prove scientific convergence. The worker records
`projected_solver_converged` for the projected solve. It leaves
`scientific_converged` unknown when the projected system is stable and keeps
top-level `converged` false because the full-space residual is unavailable. A
stable projected energy can still be reported as an estimate. Dense and
fixed-sector paths calculate residuals against the full dense operator or the
full matrix-free action within the selected particle sector. These residuals
test the projected Ritz state against the corresponding full operator space.
Measured QSE calculates only a projected generalized-eigenproblem residual. It
does not establish convergence in the full operator space.

QSE keeps the configured `regularization` value for compatibility, but its
effect depends on the execution path. Measured QSE uses it as a floor for
overlap-mode selection and for the raw diagnostic spectrum. The retained final
metric is not shifted. Dense exact QSE uses it only for intermediate basis
progress estimates. Fixed-sector QSE records it in overlap diagnostics but
does not use it in the final energy solve. Result metadata keeps the requested
value and reports `regularization_scope` and
`final_metric_diagonal_shift` in `conditioning_summary`. Dense exact QSE uses
it only for intermediate basis-progress estimates. Fixed-sector QSE does not
use it. Neither final solve shifts the projected metric. The
legacy `conditioning_summary.regularization` field
remains path-specific. Use the explicit fields to compare the requested value
with a final metric shift. The nested VQE reference uses the VQE default
absolute energy-delta threshold of `1e-8`. QSE regularization does not change
that threshold.

Measured QSE prepares a Hartree–Fock reference and builds directions
`A_i |psi_ref>` from its fixed excitation pool. The dimension cap includes the
reference direction. The worker skips directions that are zero or linearly
dependent on earlier directions. This is a bounded fixed-pool QSE path. It is
not a full adaptive operator-pool solver.

QSE result metadata records the selected excitation specifications, counts,
selection policy, requested dimension cap, and actual basis dimension under
`matrix_element_summary.basis_selection`. A matching excitation level and cap
do not guarantee the same basis across execution modes. Dense and measured QSE
use generator order. Sector QSE ranks candidates by coupling to the reference
when its dominant determinant probability is at least `0.5`; otherwise, it
uses generator order. Compare the recorded basis selections before comparing
energies from different execution modes.

QFD branch-estimator runs use seven time points when the user omits the count.
The branch path supports at most eight points. The worker rejects larger
explicit values before it creates the estimator primitive. Dense and
fixed-sector QFD keep the sixteen-point default.

KQD exact evolution uses local dense-matrix or fixed-sector matrix-free
evolution. IBM Runtime and noisy Aer paths use branch-estimator circuits and
require `evolution_method="trotter"`. Large ideal-Aer runs also use the branch
estimator when the Hamiltonian cannot use the fixed-sector path. The worker
rejects exact evolution before estimator creation on those paths. Guided form
recommendations know the IBM and noisy-Aer paths. They cannot predict the
large ideal-Aer path before the worker prepares the Hamiltonian.

The branch-estimator path builds a controlled pair of evolved states and
measures ancilla `X` and `Y` observables to reconstruct each upper-triangle
Hamiltonian and overlap entry. This computes the projected matrix elements
directly. It does not implement the symmetry-optimized, single-evolution
Toeplitz circuit used in the [2025 KQD paper's hardware experiment]
(https://www.nature.com/articles/s41467-025-59716-z). Do not apply that
paper's circuit-count or depth estimates to this worker path. The worker sets
each overlap diagonal to one because ideal basis states are normalized. This
is an imposed normalization, not a measured hardware fidelity.

SKQD sample-union results record the same worker-observed sampler fields in
`algorithm_metrics.work_ledger`. Exact local sample oracles record
`local_exact_sampling_runs` and returned rows instead. Do not compare
these counts as provider shots. Use `sampling_source` and `execution_path` to
separate exact local, Aer, and IBM Runtime evidence. For sampler execution,
`sampler_returned_raw_sample_rows` includes excess returned rows, while
`sampler_retained_sample_rows` counts rows used to build the sample union.

The `legacy_statevector_extension` mode is a project-specific local Krylov
extension, not the paper's sampled SKQD circuit path. It seeds the extension
with the complex coefficients from the best selected-CI state. It does not
rebuild a wavefunction from sampled probabilities or occupancies. The worker
keeps this state in memory and does not add its coefficient matrix to the
persisted result. If the state is unavailable or invalid, the extension uses
its Hartree–Fock reference and records `seed_fallback_reason`.

The result labels this path as
`local_statevector_krylov_extension` and records the selected `reference_policy`.
An IBM Runtime sampler used by the preceding SQD step does not make this local
extension an IBM hardware calculation. The direct sample-union mode uses
sampler circuits when the selected backend supports them. Statevector and
analysis-only local runs use an exact local statevector oracle. If Aer or IBM
Runtime is selected but the worker has no sampler, the run fails. It does not
switch to the local oracle.
For sampler circuits, Krylov index `k` uses `k` fixed `time_step` intervals.
The worker scales the Trotter repetition count with `k` so each interval keeps
the configured step size. Circuit metadata records the applied repetition
count.
Supplied SQD circuits must measure every qubit once into its same-index
classical bit. All measurements must be terminal. The worker rejects malformed
non-binary sample strings.

KQD `exact` mode uses exact matrix evolution, including for an Aer target.
Branch-estimator KQD supports Trotter evolution only. The runner validates this
setting before it creates an estimator primitive. Result metadata keeps the
requested target, noise, and optimization settings separate from actual
execution. It reports exact matrix evolution as local. It also states that this
path did not use Aer or IBM Runtime primitives and did not apply noise.

KQD and QFD work estimates count matrix-pair and projected-solve units for IBM
Runtime and noisy Aer. Ideal Aer uses the algorithm-native estimate for the
normal chemistry path, which runs dense or fixed-sector evolution locally. A
large ideal-Aer fallback can depend on the prepared Hamiltonian. The worker
resolves that path after Hamiltonian preparation and uses it for live progress.

VQE records `shot_budget_mode` as `fixed_shots`, `estimator_precision`, or
`exact_expectation`. Statevector execution and Aer EstimatorV2 with zero
precision use exact expectations. Precision-driven estimators report their
precision instead of a fixed shot count. VQE sets `shots_per_pub` and
`primitive_shots` to `null` for both paths. Adapter metadata keeps requested
shots separate from observed effective shots. IBM Runtime metadata does not
infer effective shots from the worker's configured shot value.

`effective_optimizer_max_iterations` limits the initial VQE gradient-based run
and all stationary-start retries. Each retry receives only the remaining
iterations. `optimizer_iterations` and `optimizer_iterations_total` report the
sum across attempts. `optimizer_iterations_by_attempt` reports each attempt,
and `selected_optimizer_iterations` reports the selected start. The objective
evaluation budget remains a separate limit. If an optimizer does not report
its iteration count, the worker skips further retries and records the reason.

VQE counts objective callbacks separately from backend `run()` calls. It counts
`primitive_jobs` when the backend returns a job handle. It counts `primitive_pubs`
for those returned handles. For fixed-shot runs, `primitive_shots` is a nominal
estimate from configured shots per returned PUB. It is not a provider-reported
physical shot total. Check `primitive_shot_count_basis` before comparing totals.
For sampled objectives, VQE reports an independent reevaluation at the final
parameter vector when the evaluation budget allows it. Otherwise, it reports a
sampled observation at that vector and marks the uncertainty status. It does
not select the minimum noisy objective observation as the reported energy.

For measured projected solves, the eigensolver raises its overlap-eigenvalue
cutoff to four times the maximum measured overlap-entry standard error. This is
a rank-selection heuristic, not a matrix-level uncertainty bound. Result
metadata records the method so callers do not treat it as propagated
covariance.

QFD grid metadata records `symmetric_kappa` for the original symmetric variant
and `forward` for the chemistry-forward variant. The configured `max_time` and
`time_grid_type` do not define the symmetric grid.
Result metadata records these values as requested but inactive. It also records
the applied `kappa` grid.
The original symmetric variant requires `kappa` to cover the spectral width
plus an overage. If the user omits `kappa`, the worker derives it from the exact
dense spectrum or a conservative Pauli-coefficient L1 bound. The worker rejects
an explicit value below that bound. Grid metadata records the bound, overage,
and source.

Do not infer actual execution from the requested backend label. A local Aer
run is not IBM hardware evidence. A queued or planned run is not completed
execution evidence.

## VQE particle sector

Molecular VQE uses `NumberPreserving` when the caller omits `ansatz_name`.
This ansatz preserves the declared alpha and beta electron counts. It does not
guarantee total-spin conservation and is not UCCSD. An explicit ansatz choice
remains unchanged. The worker measures ideal ansatz leakage for the selected
reported parameter vector. For circuits with at most 20 qubits, it uses an
ideal statevector. It marks `scientific_converged` false when leakage exceeds
`1e-10`, and records `particle_sector_leakage` as the failure reason. Above
20 qubits, the worker avoids statevector allocation. It accepts the
`NumberPreserving` circuit invariant. It marks other ansatz sectors as
unverified and does not report scientific convergence. This check does not
measure particle leakage on Aer noise or IBM hardware. Optimizer success remains
a separate status. See the
[Qiskit Nature UCC contract](https://qiskit-community.github.io/qiskit-nature/_modules/qiskit_nature/second_q/circuit/library/ansatzes/ucc.html)
and its
[qubit-mapper sector guide](https://qiskit-community.github.io/qiskit-nature/tutorials/06_qubit_mappers.html).

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
