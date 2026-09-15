# Worker Chemistry Algorithms

This guide explains how the worker selects and runs chemistry algorithms.
Use it when you maintain an existing algorithm or add a new one.

## Execution flow

The worker follows this flow:

1. `worker/jobs/execute_run.py` prepares the Hamiltonian and backend context.
2. `worker/jobs/dispatcher.py` selects an `AlgorithmDefinition`.
3. The definition selects the required primitive and solver entry point.
4. The algorithm resolves its configuration and runs its workflow.
5. `worker/adapters/result_adapter.py` normalizes the typed result for storage.

The dispatcher owns algorithm registration. It does not own algorithm
mathematics.

## Module ownership

| Module | Owns |
| --- | --- |
| `worker/jobs/dispatcher.py` | Algorithm definitions, supported keys, and primitive creation. |
| `worker/chemistry/projected_execution.py` | KQD/QFD path selection and QSE measurement policy. |
| `worker/chemistry/algorithms/<name>/config.py` | Resolved options and validation for one algorithm. |
| `worker/chemistry/algorithms/<name>/` | Algorithm-specific kernels, execution helpers, and result builders. |
| `worker/chemistry/types.py` | Worker-internal result records and chemistry input records. |
| `worker/adapters/result_adapter.py` | Conversion from worker results to persisted API payloads. |
| `worker/chemistry/*_solver.py` | Current top-level workflow entry points during the extraction transition. |

The package root uses lazy exports. Prefer explicit imports from the owning
module in new code.

## Add an algorithm

Complete these steps in order:

1. Add the algorithm identifier to `shared/contracts/identifiers.py`.
2. Create `worker/chemistry/algorithms/<name>/`.
3. Add `config.py` with one frozen resolved configuration record.
4. Add `workflow.py` for the public algorithm workflow.
5. Add `execution.py` only when the algorithm has a separate execution path.
6. Add `results.py` for result construction and completion progress.
7. Add an `AlgorithmDefinition` entry in `worker/jobs/dispatcher.py`.
8. Declare the primitive requirement in the definition.
9. Add tests for configuration, kernels, workflow, dispatch, and result mapping.
10. Update this guide and the worker capability documentation.

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

The algorithm packages already own many kernels, configuration records, and
result builders. The top-level solver modules still contain workflow
orchestration for several algorithms. Move one workflow at a time. Keep the
old module only as a thin approved facade after all internal imports use the
package workflow.
