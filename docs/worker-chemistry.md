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

## Current transition

The algorithm packages own the workflow entry points, kernels, configuration
records, result builders, and dispatch definitions. Keep shared chemistry
modules focused on cross-algorithm behavior. Remove a compatibility alias only
after all internal imports and tests use the package workflow.
