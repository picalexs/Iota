# Pydantic Schemas

## Overview

All API request and response bodies are typed with Pydantic v2 models defined in
`backend/app/schemas/`. The base model for ORM-backed responses uses:

```python
model_config = ConfigDict(from_attributes=True)
```

This enables SQLAlchemy ORM objects to be passed directly to
`Model.model_validate()` without explicit `.model_dump()` conversion.

Extra fields are `"forbid"` on most input schemas and `"allow"` only where
extensibility is explicitly required (e.g. `ActiveSpaceSchema`).

---

## Common Schemas (`schemas/common.py`)

### `BaseORMModel`

Extended by all response schemas that wrap SQLAlchemy ORM rows.

```python
class BaseORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
```

### `ErrorDetail`

| Field     | Type          | Notes                                                     |
| --------- | ------------- | --------------------------------------------------------- |
| `code`    | `str`         | Machine-readable error code, e.g. `NOT_FOUND`, `CONFLICT` |
| `message` | `str`         | Human-readable description                                |
| `field`   | `str \| None` | Offending field name for validation errors                |

### `ErrorResponse`

The standard error envelope returned by all exception handlers:

```json
{
  "detail": {
    "code": "VALIDATION_ERROR",
    "message": "Field must be non-empty",
    "field": "name"
  }
}
```

---

## Molecule Schemas (`schemas/molecule.py`)

### `AtomSchema`

Represents a single atom in Cartesian coordinates. Used inside `atoms` lists.

| Field    | Type    | Constraints                                                           |
| -------- | ------- | --------------------------------------------------------------------- |
| `symbol` | `str`   | min_length=1; stripped, canonicalized, and validated against `H`–`Xe` |
| `x`      | `float` | must be finite (`math.isfinite`)                                      |
| `y`      | `float` | must be finite                                                        |
| `z`      | `float` | must be finite                                                        |

`extra = "forbid"` — no additional fields accepted.

### `ActiveSpaceSchema`

Defines the active space for correlated calculations.

| Field         | Type  | Constraints |
| ------------- | ----- | ----------- |
| `n_electrons` | `int` | ≥ 1         |
| `n_orbitals`  | `int` | ≥ 1         |

`extra = "allow"` — additional implementation-specific keys (e.g.
`n_frozen_core`) may be included and are persisted to the `active_space` JSONB
column.

### `MoleculeEligibilityResponse`

Derived label contract attached to molecule reads, summaries, and import
previews.

| Field               | Type          | Notes                                            |
| ------------------- | ------------- | ------------------------------------------------ |
| `selectable`        | `bool`        | Whether the enabled backend set can select it    |
| `label`             | `str`         | Short UI label such as `Ready` or `Not runnable` |
| `reason`            | `str \| None` | Optional explanation for disabled/limited cases  |
| `capability_labels` | `list[str]`   | Algorithm/qubit capability labels for badges     |

### `MoleculeCreate`

Inherits all fields from `MoleculeBase`. Used as the request body for
`POST /api/molecules`.

| Field          | Type                        | Constraints                      |
| -------------- | --------------------------- | -------------------------------- |
| `name`         | `str`                       | 1–255 chars; stripped; non-empty |
| `atoms`        | `list[AtomSchema]`          | min 1 atom                       |
| `charge`       | `int`                       | default `0`                      |
| `multiplicity` | `int`                       | ≥ 1; default `1`                 |
| `active_space` | `ActiveSpaceSchema \| None` | optional                         |
| `pubchem_cid`  | `int \| None`               | optional                         |
| `iupac_name`   | `str \| None`               | max 255 chars, optional          |
| `description`  | `str \| None`               | max 500 chars, optional          |
| `synonyms`     | `list[str] \| None`         | optional                         |
| `smiles`       | `str \| None`               | max 500 chars, optional          |
| `inchi`        | `str \| None`               | max 500 chars, optional          |
| `inchi_key`    | `str \| None`               | max 27 chars, optional           |

`extra = "forbid"` on `MoleculeBase`.

### `MoleculeUpdate`

Used as the request body for `PATCH /api/molecules/{id}`. All fields are
optional (omit to leave unchanged). Explicit `null` for non-nullable fields
raises a `422` error rather than silently converting to a DB error.

| Field          | Type                        | Notes                                   |
| -------------- | --------------------------- | --------------------------------------- |
| `name`         | `str \| None`               | PATCH only; must not be explicitly null |
| `atoms`        | `list[AtomSchema] \| None`  | PATCH only; must not be explicitly null |
| `charge`       | `int \| None`               | PATCH only; must not be explicitly null |
| `multiplicity` | `int \| None`               | PATCH only; must not be explicitly null |
| `active_space` | `ActiveSpaceSchema \| None` | `null` clears the active space          |
| `pubchem_cid`  | `int \| None`               | optional                                |
| `iupac_name`   | `str \| None`               | optional                                |
| `description`  | `str \| None`               | optional                                |
| `synonyms`     | `list[str] \| None`         | optional                                |
| `smiles`       | `str \| None`               | optional                                |
| `inchi`        | `str \| None`               | optional                                |
| `inchi_key`    | `str \| None`               | optional                                |

### `MoleculeResponse`

Returned by all molecule read/write endpoints. Inherits `MoleculeBase` and
`BaseORMModel`.

| Additional field | Type                          |
| ---------------- | ----------------------------- |
| `id`             | `UUID`                        |
| `created_at`     | `datetime`                    |
| `updated_at`     | `datetime`                    |
| `eligibility`    | `MoleculeEligibilityResponse` |

### `MoleculeSummaryResponse`

Returned by `GET /api/molecules/summaries` for high-volume list UIs that do not
need full atom coordinates.

| Field         | Type                          | Notes                                     |
| ------------- | ----------------------------- | ----------------------------------------- |
| `id`          | `UUID`                        | Molecule identifier                       |
| `name`        | `str`                         | Display name                              |
| `charge`      | `int`                         | Molecular charge                          |
| `atom_count`  | `int`                         | Number of atoms in the stored geometry    |
| `run_count`   | `int`                         | Number of persisted runs for the molecule |
| `formula`     | `str`                         | Precomputed compact Hill-style formula    |
| `iupac_name`  | `str \| None`                 | Optional IUPAC systematic name            |
| `eligibility` | `MoleculeEligibilityResponse` | Derived selectability/capability labels   |

### `MoleculeListResponse`

Paginated full-molecule envelope used by `GET /api/molecules`.

- `items`: `list[MoleculeResponse]`
- `total`: `int`

### `MoleculeSummaryListResponse`

Paginated lightweight envelope used by `GET /api/molecules/summaries`.

- `items`: `list[MoleculeSummaryResponse]`
- `total`: `int`

### `XYZPreviewRequest` / `XYZImportRequest`

Request body for `POST /api/molecules/xyz/preview` and
`POST /api/molecules/xyz/import`.

| Field                 | Type                        | Notes                                 |
| --------------------- | --------------------------- | ------------------------------------- |
| `xyz`                 | `str`                       | Standard XYZ text, max 100k chars     |
| `name`                | `str \| None`               | Optional for preview, required import |
| `charge`              | `int`                       | Defaults to `0`                       |
| `multiplicity`        | `int`                       | Defaults to `1`, must be ≥ 1          |
| `active_space`        | `ActiveSpaceSchema \| None` | Optional override                     |
| `derive_active_space` | `bool`                      | Defaults to `true`                    |

### `MoleculeImportPreviewResponse`

Returned by PubChem and XYZ preview endpoints.

| Field                    | Type                                     | Notes                            |
| ------------------------ | ---------------------------------------- | -------------------------------- |
| `source`                 | `"pubchem" \| "xyz"`                     | Preview source                   |
| `name`                   | `str`                                    | Proposed stored name             |
| `atoms`                  | `list[AtomSchema]`                       | Parsed/loaded geometry           |
| `charge`                 | `int`                                    | Molecular charge                 |
| `multiplicity`           | `int`                                    | Spin multiplicity                |
| `active_space`           | `ActiveSpaceSchema \| None`              | Derived or provided active space |
| `atom_count`             | `int`                                    | Number of atoms                  |
| `formula`                | `str`                                    | Compact formula                  |
| `eligibility`            | `MoleculeEligibilityResponse`            | Selection/capability labels      |
| `commit_action`          | `"create" \| "reuse" \| "name_conflict"` | What a commit would do           |
| `existing_molecule_id`   | `UUID \| None`                           | Present for reuse/conflict       |
| `existing_molecule_name` | `str \| None`                            | Present for reuse/conflict       |
| PubChem metadata fields  | `int/str/list \| None`                   | Present for PubChem previews     |

---

## Run Schemas

Run schemas are split by contract responsibility. The historical
app.schemas.run module remains a compatibility facade and must not become a
second definition site.

| Module                   | Responsibility                                                                                     |
| ------------------------ | -------------------------------------------------------------------------------------------------- |
| schemas/run_config.py    | Backend options, noise profiles, easy-mode options, and algorithm-specific advanced configuration  |
| schemas/run_requests.py  | Run creation, update, control, checkpoint, and validation requests                                 |
| schemas/run_responses.py | Run resources, summaries, estimates, control responses, validation responses, and export envelopes |
| schemas/run_results.py   | Circuit artifacts and persisted result responses                                                   |
| schemas/run_events.py    | Event request and response payloads                                                                |
| schemas/run_metadata.py  | Server-owned configuration catalog metadata                                                        |
| schemas/run.py           | Compatibility re-exports only                                                                      |

Backend production modules import their contract types from the owning module
listed above. New code must not add imports from `app.schemas.run`; that module
exists for older callers and for an explicitly tested migration boundary.
The package-level `app.schemas` exports remain a convenience facade, but they
also import each symbol from its owning module directly.

### `RunCreate`

Request body for `POST /api/runs`.

- `molecule_id` (`UUID`, required)
- `algorithm` (`RunAlgorithm`, required)
- `mode` (`RunMode`, required)
- `backend_target` (`BackendTarget`, required)
- `backend_options` (`BackendOptions`, default object)
- `easy_options` (`EasyOptions`, required when `mode=easy`)
- `advanced_config` (`AdvancedConfig`, required when `mode=advanced`)
- `basis_set_override` (`str | None`, optional)
- `chemical_accuracy_target_ha` (`float | None`, optional, `> 0`)
- `noise_profile` (`NoiseProfile | None`, optional)
- `client_request_id` (`UUID | None`, optional idempotency key)

`backend_options` carries shared runtime controls: `selection_policy` (`manual`,
`least_busy`, `least_error`), optional `backend_name`, `shots`,
`optimization_level`, optional simulator/transpiler seeds, optional
`credential_profile_id`, and `aer_method`. Runtime capability checks come from
`Settings.backend_capabilities`; IBM Runtime also requires credentials and is
limited to algorithms with an implemented hardware path. KQD/QFD are allowed on
`aer_simulator` for either ideal statevector-style time evolution or capped
local Aer branch-state Estimator matrix-element runs. Aer KQD/QFD still require
statevector-capable `aer_method` values on the ideal propagation path, while
noisy Aer requests route through the projected-matrix branch path instead of
rejecting `noise_profile`. KQD/QFD are also allowed on IBM Runtime through the
same capped branch-state Estimator matrix-element workflow; the result payload
records the measured workflow under `algorithm_metrics.matrix_element_summary`.
When those noisy branch-estimator paths are used, the worker reports the
stabilized retained-subspace energy at the top level and records the raw
projected spectrum plus stability diagnostics under `algorithm_metrics`. The
retained solve uses an overlap truncation floor of
`max(regularization, 1e-6 * lambda_max(S), lambda_max(S) / 1e3, 4 * max_standard_error)`
so the reported KQD/QFD energy comes from a condition-capped projected subspace
instead of the raw lowest generalized eigenvalue. Large statevector KQD/QFD
avoid full dense Hilbert matrices by using the fixed-particle sector.

When an IBM Runtime run is created with `selection_policy="least_busy"` or
`"least_error"`, the API may populate `config_json.backend_options.backend_name`
with the concrete resolved backend even though the request left that field
empty. The original selection policy still remains in `backend_options`.

For easy-mode runs, the original request snapshot remains in `config_json` and
the expanded advanced snapshot is recorded under `metadata.easy_mode` with a
versioned catalog identifier. The expanded snapshot includes the
convergence-related defaults it depends on, such as projected-solver
`residual_tolerance` values and SQD/SKQD `min_selected_configurations`.

VQE advanced payloads can include `initial_point_strategy`,
`initial_point_candidates`, `max_function_evaluations`, `optimizer_options`,
`initial_parameters`, `parameter_bounds`, and `seed` to control deterministic
warm-start selection before optimization. When `initial_parameters` or
`parameter_bounds` are provided, they must match the resolved ansatz parameter
count; `parameter_bounds` also require `[lower, upper]` ordering for every
entry. QSE advanced payloads use `reference_method="hf"`, `"vqe"`,
`"provided_state"`, or `"provided_sector"`. On local runs above the dense
active-space cap, HF and provided-sector references use the fixed-particle-sector
matrix-free path. They are the supported larger-active-space QSE references.
QSE `max_subspace_dim` is capped at 96. QFD
advanced payloads include `trotter_steps` for Pauli-evolution circuit synthesis
on Aer/IBM branch-estimator paths and Aer state-propagation paths.
Measured QSE on noisy Aer or IBM Runtime supports `reference_method="hf"` only,
because its measured circuit prepares the Hartree-Fock reference state. Use
statevector or ideal Aer for non-HF QSE references.
`provided_state_vector` is a list of `QSEReferenceScalar`, where each entry is
either a real number or `{real, imag}`. `provided_sector_amplitudes` is a list
of `{bitstring, amplitude}` determinant entries using the same scalar shape.
Full `provided_state_vector` and embedded VQE references remain small-system
references and are rejected above the dense 6-active-orbital cap. SKQD advanced
payloads include `time_step` in addition to the SQD base-sampling contract and
Krylov extension settings; that value sets the seeded local evolution schedule
used to build the SKQD extension basis.

### `RunConfigMetadataResponse`

Returned by `GET /api/runs/config-metadata`.

- `catalog_version`: `str` - version of the shared public run catalog.
- `algorithms`: `list[RunAlgorithm]`
- `backend_targets`: `list[BackendTarget]`
- `easy_goals`: `list[EasyGoal]`
- `easy_goal_presets`: `list[EasyGoalPresetMetadata]` - target labels and
  chemical accuracy values for easy-mode goal tiers.
- `ansatzes`: `list[ConfigChoiceMetadata]`
- `optimizers`: `list[ConfigChoiceMetadata]`
- `limits`: `dict[str, {minimum?: int | float, maximum: int | float}]`
- `defaults`: `dict[str, str]`
- `capabilities`: `dict[str, dict[str, bool]]` - static public backend
  capability flags; live availability remains backend discovery data.

### `EasyGoalPresetMetadata`

Returned as part of `RunConfigMetadataResponse`.

- `goal`: `EasyGoal`
- `label`: `str` - display label for the target value.
- `chemical_accuracy_target_ha`: positive `float` - target in Hartree.

### `ConfigChoiceMetadata`

Shared registry-backed choice description used by the manual run form.

- `id`: `str`
- `label`: `str`
- `aliases`: `list[str]`
- `description`: `str | None`
- `supported_algorithms`: `list[RunAlgorithm]`
- `metadata`: `dict[str, Any]`

### `RunResponse`

Returned by all run endpoints. Extends `BaseORMModel`.

- `id`: `UUID`.
- `molecule_id`: `UUID`.
- `status`: `RunStatus` - `CREATED`, `QUEUED`, `RUNNING`, `COMPLETED`, `FAILED`,
  `CANCELLED`, `SUBMITTED_TO_IBM`, `PAUSING`, `PAUSED`.
- `algorithm`: `RunAlgorithm` - nullable; first-class persisted algorithm.
- `mode`: `RunMode` - nullable; first-class persisted run mode.
- `backend_target`: `BackendTarget` - nullable; first-class persisted backend
  target.
- `config_json`: `dict` - configuration snapshot from creation time.
- `ibm_job_id`: `str \| None` - set when run is submitted to IBM Quantum.
- `client_request_id`: `UUID \| None` - echoed from
  `RunCreate.client_request_id`.
- `execution_generation`: `int` - increments when a paused run is resumed and is
  copied to restart child runs.
- `restarted_from_run_id`: `UUID \| None` - set on restart child runs.
- `credential_profile_id`: `UUID \| None` - IBM credential profile associated
  with the run, when selected.
- `credential_profile_name`: `str \| None` - snapshot of the IBM profile display
  name used when the run was created; preserved even if the profile is later
  renamed or deleted.
- `basis_set`: `str` - normalized run basis set stored on the run row.
- `versions`: `dict \| None` - dependency version snapshot.
- `metadata`: `dict \| None` - serialised from the ORM attribute `run_metadata`
  via `Field(validation_alias="run_metadata")`; easy-mode runs populate
  `metadata.easy_mode` with `catalog_version`, `goal`, and
  `expanded_advanced_config`; IBM Runtime runs may also include `ibm_job_id`,
  `ibm_backend`, `ibm_status`, `ibm_queue_position`, `ibm_pub_count`,
  `ibm_shots`, and `ibm_timing` where `ibm_timing` contains `created_at`,
  `running_at`, `finished_at`, `pending_seconds`, `usage_seconds`, and
  `total_seconds` when Runtime job metrics are available.
- `initial_estimate`: `RunEstimate \| None` - estimate snapshot generated by
  validation or seeded asynchronously after the run row is created.
- `latest_estimate`: `RunEstimate \| None` - latest estimate snapshot; queued
  runs may receive a seeded value before worker telemetry takes over.
- `created_at`: `datetime`.
- `updated_at`: `datetime`.

### `RunSummaryResponse`

Returned by `GET /api/runs/summaries` for list-heavy run history UIs.

- `id`: `UUID`.
- `molecule_id`: `UUID`.
- `molecule_name`: `str | None` from the related molecule, included so the runs
  list can render visible row labels before the separate molecule-filter lookup
  finishes.
- `status`: `RunStatus`.
- `algorithm`: `RunAlgorithm | None`.
- `backend_target`: `BackendTarget | None`.
- `backend_name`: `str | None` derived from
  `config_json.backend_options.backend_name` when present.
- `converged`: `bool | None` copied from the persisted `run_results` row when
  available; `None` means the run has no result yet or no convergence result was
  persisted.
- `chemical_accurate`: `bool | None` derived from the persisted result
  `signed_error` plus the saved per-run `chemical_accuracy_target_ha` (or the
  default `1.6e-3 Ha`) when a scorable reference energy exists.
- `execution_generation`: `int`.
- `restarted_from_run_id`: `UUID | None`.
- `credential_profile_id`: `UUID | None`.
- `credential_profile_name`: `str | None`.
- `basis_set`: `str | None`.
- `metadata`: `dict | None` - serialized from the ORM `run_metadata` attribute.
- `latest_estimate`: `RunEstimate | None`.
- `created_at`: `datetime`.
- `updated_at`: `datetime`.

### `RunEstimate`

Typed estimate envelope used by `RunResponse`, validation responses, and
`estimate_updated` run events.

- `source`: `str` (`config_projection`, `history`, or `telemetry`)
- `algorithm`: `str` (lowercase algorithm id, for example `vqe`)
- `estimated_total_iterations`: `int | None`
- `estimated_remaining_iterations`: `int | None`
- `estimated_total_seconds`: `float | None`
- `estimated_remaining_seconds`: `float | None`
- `confidence`: `float | None` in `[0, 1]`
- `updated_at`: `datetime`

### `BackendTarget` And `NoiseProfile`

`BackendTarget` values are:

| Value           | Current execution status | Notes                                                                                                                                                                                                                                                                                                            |
| --------------- | ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `statevector`   | Enabled                  | Uses local statevector primitives in the worker.                                                                                                                                                                                                                                                                 |
| `aer_simulator` | Enabled                  | Uses Qiskit Aer primitives, `backend_options`, and supported `noise_profile` values; KQD/QFD use direct ideal `AerSimulator` state propagation for small systems, the fixed-particle-sector matrix-free path for larger ideal-Aer systems, and local Aer branch matrix elements when a noise profile is present. |
| `ibm_runtime`   | Credential-gated         | Uses IBM Runtime primitives when credentials are configured and validation accepts the algorithm/options.                                                                                                                                                                                                        |

`NoiseProfile` is a discriminated union on `source`:

| Source            | Fields                                         | Current status                                                         |
| ----------------- | ---------------------------------------------- | ---------------------------------------------------------------------- |
| `custom_preset`   | `preset` plus preset-specific fields | Supported for `aer_simulator`; rejected for non-noise-capable targets. |
| `backend_derived` | `reference_backend`, optional `temperature_mk` | Supported for `aer_simulator`; the reference must be an IBM backend. |

Custom preset fields are:

- `depolarizing_cx`: `strength` in `[0, 1]`, applied to `cx` gates.
- `readout_bias`: `p01` for `P(1|0)` and `p10` for `P(0|1)`, each in `[0, 1]`.
- `thermal_relaxation`: positive `t1_us`, `t2_us`, and `gate_time_us` values.
  The worker requires `t2_us <= 2 * t1_us`.

Backend-derived noise loads the named IBM backend through the active IBM Runtime
credential profile. It passes the selected temperature in milli-Kelvin to Aer
and records the resolved backend name, backend version, basis gates, coupling
map, and model fingerprint in execution metadata. The worker fails the run when
it cannot load the requested backend. It does not substitute a simulator or a
different backend.

Relevant upstream references for these runtime targets are Qiskit Aer
`AerSimulator`, Qiskit Aer noise models, IBM Runtime service docs, and IBM
transpilation docs:
<https://qiskit.github.io/qiskit-aer/stubs/qiskit_aer.AerSimulator.html>,
<https://qiskit.github.io/qiskit-aer/apidocs/aer_noise.html>,
<https://docs.quantum.ibm.com/api/qiskit-ibm-runtime/runtime-service>, and
<https://quantum.cloud.ibm.com/docs/en/guides/qiskit-transpiler-service>.

### `RunListResponse`

Paginated wrapper returned by `GET /api/runs`.

| Field    | Type                |
| -------- | ------------------- |
| `items`  | `list[RunResponse]` |
| `total`  | `int`               |
| `limit`  | `int`               |
| `offset` | `int`               |

### `RunSummaryListResponse`

Paginated wrapper returned by `GET /api/runs/summaries`.

| Field    | Type                       |
| -------- | -------------------------- |
| `items`  | `list[RunSummaryResponse]` |
| `total`  | `int`                      |
| `limit`  | `int`                      |
| `offset` | `int`                      |

### `RunCancelResponse`

Returned by `POST /api/runs/{id}/cancel`.

| Field    | Type        |
| -------- | ----------- |
| `id`     | `UUID`      |
| `status` | `RunStatus` |

### `RunResultResponse`

Returned by `GET /api/runs/{id}/result`. Extends `BaseORMModel`.

| Field                    | Type            | Notes                                                                  |
| ------------------------ | --------------- | ---------------------------------------------------------------------- |
| `run_id`                 | `UUID`          |                                                                        |
| `energy`                 | `float`         | Ground-state energy in Hartree                                         |
| `final_energy`           | `float \| None` | Final solver energy, when distinct from reported                       |
| `best_observed_energy`   | `float \| None` | Best observed or selected reporting energy                             |
| `reported_energy`        | `float \| None` | Energy selected for UI/reporting                                       |
| `reported_energy_source` | `str \| None`   | Source label for the reported energy                                   |
| `reference_energy`       | `float \| None` | Optional comparison/reference energy                                   |
| `reference_basis`        | `str \| None`   | Basis label associated with `reference_energy`                         |
| `signed_error`           | `float \| None` | Signed error against the reference energy                              |
| `iterations`             | `int`           | Solver-reported iterations/evaluations; VQE uses objective evaluations |
| `optimal_parameters`     | `list[float]`   | Variational parameters associated with the reported energy             |
| `converged`              | `bool`          | Whether solver-specific convergence criteria were met                  |
| `algorithm_metrics`      | dict \| None    | Normalized per-algorithm diagnostics                                   |
| `energy_policy`          | dict \| None    | Explains which algorithm energy was reported                           |
| `created_at`             | `datetime`      | Result creation timestamp                                              |

For KQD/QFD, `algorithm_metrics` can include both the reported retained
projected spectrum (`ritz_values` or `filter_eigenvalues`) and the raw noisy
projected spectrum (`raw_ritz_values` or `raw_filter_eigenvalues`), plus a
`stability_summary` object with overlap-threshold diagnostics and
`selected_level_index` for the retained level used as the canonical energy. On
noisy Aer/IBM branch-estimator KQD/QFD paths, a stabilized retained solve can
still produce the canonical `energy` while leaving `converged=false`; only a
fully stable retained overlap solve is treated as converged on that path.

When present, `algorithm_metrics.circuit_artifacts` is a list of typed
quantum-circuit artifacts:

| Field                   | Type                | Notes                                             |
| ----------------------- | ------------------- | ------------------------------------------------- |
| `schema_version`        | `str`               | Artifact schema version, currently `"2.0"`        |
| `artifact_type`         | `"quantum_circuit"` | Circuit artifact discriminator                    |
| `id`                    | `str \| None`       | Canonical artifact id used by the frontend        |
| `artifact_id`           | `str`               | Stable ID within the run result                   |
| `algorithm`             | `str`               | Algorithm namespace that owns the artifact        |
| `role`                  | `str`               | Examples: `ansatz`, `final`, `sqd_sampling`       |
| `phase`                 | `str \| None`       | Examples: `optimization`, `recovery`, `reference` |
| `representative`        | `bool \| None`      | Marks the default artifact to show first          |
| `source`                | `str \| None`       | Examples: `backend_sampler`, `vqe_reference`      |
| `iteration`             | `int \| None`       | Present for per-iteration artifacts               |
| `qubits`                | `int \| None`       | Logical circuit width                             |
| `classical_bits`        | `int \| None`       | Classical bit width, when the circuit measures    |
| `depth` / `size`        | `int \| None`       | Qiskit circuit summary values                     |
| `operation_counts`      | `dict[str, int]`    | Gate/count summary                                |
| `parameters`            | `dict \| None`      | Algorithm-specific parameter metadata             |
| `logical`               | `dict \| None`      | Logical OpenQASM 3 + SVG preview payload          |
| `preview`               | `dict \| None`      | Compatibility alias for the logical preview       |
| `transpiled`            | `dict \| None`      | Transpiled preview when the backend provides one  |
| `transpiled_preview`    | `dict \| None`      | Compatibility alias for the transpiled preview    |
| `downsampling`          | `dict \| None`      | Why a preview was included or omitted             |
| `backend_target`        | `str \| None`       | Execution target copied from backend metadata     |
| `primitive_family`      | `str \| None`       | Primitive family such as Aer or IBM Runtime       |
| `job_ids`               | `list[str]`         | Primitive job ids when the backend exposes them   |
| `pub_count`             | `int \| None`       | Primitive unified block count                     |
| `shots`                 | `int \| None`       | Effective shot count recorded for the run         |
| `transpilation_summary` | `dict \| None`      | Backend-reported transpilation details            |

VQE emits an `ansatz` artifact plus a representative `final` artifact for the
reported parameter set; when the optimizer's last point differs from that
reported point, it also records an `optimizer_final` artifact for the last
optimizer circuit. SQD emits `sqd_sampling` artifacts for stored recovery
iterations and records the storage policy in
`algorithm_metrics.circuit_artifact_policy`: all iterations are kept up to 32,
and larger runs keep the first 4, last 12, and 16 evenly spaced middle
iterations. The legacy `algorithm_metrics.sci_result_package.circuit_preview` is
still preserved for older consumers. SQD/SKQD SCI packages also include a
`selected_ci` object with the selected-CI cap source, effective dimension, full
sector dimension, and an `exact_sector_solve` flag. SQD result packages include
both final-iteration and best-observed recovery fields (`final_energy`,
`best_energy`, `best_iteration`, `final_occupancies`, `best_occupancies`,
`final_batch_energies`, and `best_batch_energies`); the top-level persisted
energy uses the best observed SQD recovery iteration. SQD postselection
summaries use `selected_samples` and `selected_configurations` for the latest
accepted selected configurations, while `selected_sample_shots_estimate` keeps
the cross-iteration shot estimate. VQE stores the optimizer's last objective
under `final_energy` and the best observed objective under
`best_observed_energy`, while keeping `converged` tied to optimizer success or
SPSA stability rather than "minimum seen once" semantics. VQE diagnostics also
record `reported_iterations_unit="objective_evaluations"` while
`optimizer_iterations` keeps the optimizer-native attempted-step count and SPSA
keeps rejected blocking steps separate under `accepted_steps`. SKQD flattens the
representative SQD seed artifact as a top-level `sqd_seed` artifact. QSE emits
reference artifacts for circuit-defined `reference_method="hf"` and
`reference_method="vqe"`. KQD/QFD branch-estimator results expose retained
projected spectra by default; when unstable raw overlap modes were dropped,
`stability_summary` explains the truncation while the raw levels remain
available only as diagnostics.

All normalized worker results include `algorithm_metrics.energy_policy` and
`RunResultResponse.energy_policy` when available. The policy records the
reported energy field, primary energy source, candidate energy fields, and that
classical references are context only rather than replacement energies.

`run_results.raw_result` is stored in the DB but deliberately **not** exposed on
`RunResultResponse`. Consumers that need the raw worker payload should pull it
from `ExportBundle.run.config_json` or the `result` run event.

### `RunEventCreate`

Used internally by the worker to persist events. Not exposed as an HTTP request
schema.

| Field        | Type           | Constraints                                                                                                         |
| ------------ | -------------- | ------------------------------------------------------------------------------------------------------------------- |
| `run_id`     | `UUID`         |                                                                                                                     |
| `event_type` | `RunEventType` | `status_changed`, `iteration_update`, `error`, `result`, `estimate_updated`, `ibm_job_submitted`, `ibm_status_poll` |
| `sequence`   | `int`          | ≥ 0; monotonically increasing per run                                                                               |
| `payload`    | `dict`         | default `{}`                                                                                                        |

`extra = "forbid"`.

`RunEventType` values: `status_changed`, `iteration_update`, `error`, `result`,
`estimate_updated`, `ibm_job_submitted`, `ibm_status_poll`, `control_requested`,
`checkpoint_saved`, `resume_enqueued`, `restart_created`.

IBM Runtime event payloads are best-effort and additive. `ibm_job_submitted` and
`ibm_status_poll` can include `ibm_job_id`, `backend`, `ibm_status`,
`queue_position`/`queued_count`, `elapsed_seconds`, `pub_count`, `shots`, and
`ibm_timing`. `ibm_timing` uses the same shape as
`RunResponse.metadata.ibm_timing`.

### `RunEventResponse`

Returned by `GET /api/runs/{id}/events` and emitted via SSE. Extends
`BaseORMModel`.

| Field        | Type           |
| ------------ | -------------- |
| `id`         | `int`          |
| `run_id`     | `UUID`         |
| `sequence`   | `int`          |
| `type`       | `RunEventType` |
| `payload`    | `dict`         |
| `created_at` | `datetime`     |

### `RunEventListResponse`

Returned by the polling endpoint.

| Field           | Type                     |
| --------------- | ------------------------ |
| `events`        | `list[RunEventResponse]` |
| `last_sequence` | `int`                    |

### `RunValidationResponse (Reference)`

Returned by `POST /api/validate/config` for algorithm-aware run validation.

| Field      | Type                             | Notes                                |
| ---------- | -------------------------------- | ------------------------------------ |
| `valid`    | `bool`                           | Validation pass/fail                 |
| `errors`   | `list[RunValidationErrorDetail]` | Semantic validation errors           |
| `warnings` | `list[str]`                      | Non-blocking compatibility warnings  |
| `estimate` | `RunEstimate \| None`            | Optional runtime estimate projection |

### `RunActionResponse`

Returned by run control endpoints (`pause`, `resume`, `restart`).

| Field                  | Type           | Notes                                 |
| ---------------------- | -------------- | ------------------------------------- |
| `id`                   | `UUID`         | Source run id                         |
| `status`               | `RunStatus`    | Source run status after the action    |
| `execution_generation` | `int`          | Source generation after the action    |
| `message`              | `str \| None`  | Human-readable action summary         |
| `child_run_id`         | `UUID \| None` | Restart child run id, when applicable |
| `checkpoint_id`        | `UUID \| None` | Reserved for checkpoint-aware actions |

### `RunControlRequest`

Optional body for `pause` and `resume`.

| Field    | Type          | Notes                                |
| -------- | ------------- | ------------------------------------ |
| `reason` | `str \| None` | Optional audit reason, max 500 chars |

### `RunRestartRequest`

Optional body for `restart`.

| Field               | Type           | Notes                                      |
| ------------------- | -------------- | ------------------------------------------ |
| `reason`            | `str \| None`  | Optional audit reason, max 500 chars       |
| `client_request_id` | `UUID \| None` | Optional idempotency key for the child run |
| `cancel_active`     | `bool`         | Cancel an active source run before cloning |

### `RunCheckpointCreate`

Request body for `POST /api/runs/{id}/checkpoints`.

| Field                | Type          | Notes                                    |
| -------------------- | ------------- | ---------------------------------------- |
| `checkpoint_version` | `str`         | Version label, default `"1.0"`           |
| `payload`            | `dict`        | JSON checkpoint payload                  |
| `event_sequence`     | `int \| None` | Optional last event sequence represented |

### `RunCheckpointResponse`

| Field                  | Type       | Notes                                 |
| ---------------------- | ---------- | ------------------------------------- |
| `id`                   | `UUID`     | Checkpoint id                         |
| `run_id`               | `UUID`     | Parent run id                         |
| `execution_generation` | `int`      | Generation represented by the payload |
| `algorithm`            | `str`      | Algorithm label copied from the run   |
| `checkpoint_version`   | `str`      | Checkpoint schema/version label       |
| `payload`              | `dict`     | JSON payload                          |
| `event_sequence`       | `int` null | Optional event sequence marker        |
| `created_at`           | `datetime` | Checkpoint creation time              |

### `RunCheckpointListResponse`

- `items`: `list[RunCheckpointResponse]`
- `total`: `int`

---

## Additional Request And Response Schemas

### `MoleculeListParams`

Query parameters for `GET /api/molecules`.

| Field    | Type          | Default | Constraints |
| -------- | ------------- | ------- | ----------- |
| `q`      | `str \| None` | -       | optional    |
| `charge` | `int \| None` | -       | optional    |
| `limit`  | `int`         | 50      | max 200     |
| `offset` | `int`         | 0       | ≥ 0         |

### `PubChemImportRequest`

Request body for `POST /api/molecules/pubchem/import`.

| Field          | Type  | Required | Notes                 |
| -------------- | ----- | -------- | --------------------- |
| `name`         | `str` | Yes      | PubChem compound name |
| `display_name` | `str` | No       | Override display name |

### `PubChemSearchResult`

Single result from `GET /api/molecules/pubchem/search`.

| Field        | Type          | Notes                   |
| ------------ | ------------- | ----------------------- |
| `name`       | `str`         | Canonical compound name |
| `iupac_name` | `str`         | IUPAC systematic name   |
| `formula`    | `str`         | Molecular formula       |
| `cid`        | `int \| None` | PubChem Compound ID     |

### `PubChemSearchResponse`

Response wrapper for `GET /api/molecules/pubchem/search`.

| Field     | Type                        | Notes          |
| --------- | --------------------------- | -------------- |
| `results` | `list[PubChemSearchResult]` | Search results |

### `RunValidationRequest`

Request body for `POST /api/validate/config`.

| Field         | Type        |
| ------------- | ----------- |
| `molecule_id` | `UUID`      |
| `run`         | `RunCreate` |

### `ValidationErrorCode`

Machine-readable validation error reasons returned by
`RunValidationErrorDetail.code`:

- `missing_required`
- `invalid_range`
- `incompatible_backend`
- `unsupported_option`

### `RunValidationErrorDetail`

Single validation error entry within `RunValidationResponse`.

| Field        | Type                          | Notes                                                             |
| ------------ | ----------------------------- | ----------------------------------------------------------------- |
| `field`      | `str`                         | Dotted-path field pointer (e.g. `advanced_config.max_iterations`) |
| `code`       | `ValidationErrorCode \| None` | Structured reason; populated for service-level errors             |
| `message`    | `str`                         | Human-readable explanation                                        |
| `suggestion` | `str \| None`                 | Optional remediation hint                                         |

### `RunValidationResponse`

Response from `POST /api/validate/config`. Always returned with `200`.

| Field      | Type                             | Notes                                    |
| ---------- | -------------------------------- | ---------------------------------------- |
| `valid`    | `bool`                           | `true` if `errors` is empty              |
| `errors`   | `list[RunValidationErrorDetail]` | Schema-level or hard semantic violations |
| `warnings` | `list[str]`                      | Non-blocking advisory messages           |
| `estimate` | `RunEstimate \| None`            | Optional runtime estimate projection     |

Each instance gets its own fresh list — defaults are not shared across instances
(validated in `test_run_model_contract.py`).

### `ExportBundle`

The reproducibility export payload returned by `GET /api/runs/{id}/export`.

| Field            | Type                        | Notes                                             |
| ---------------- | --------------------------- | ------------------------------------------------- |
| `export_version` | `str`                       | Always `"1.0"`                                    |
| `exported_at`    | `datetime`                  | UTC timestamp of the export request               |
| `molecule`       | `MoleculeResponse`          | Full molecule definition                          |
| `run`            | `RunResponse`               | Full run object with config snapshot              |
| `versions`       | `dict \| None`              | Dependency versions (qiskit, pyscf, python, etc.) |
| `events`         | `list[RunEventResponse]`    | All events in sequence order                      |
| `result`         | `RunResultResponse \| None` | Final result — `null` if run hasn't completed     |

---

## Health Schemas (`schemas/health.py`)

### `StatusResponse`

Returned by `GET /api/status` (readiness probe). HTTP 200 when all connected,
503 otherwise.

| Field   | Type                                              | Notes                                |
| ------- | ------------------------------------------------- | ------------------------------------ |
| `api`   | `Literal["ready"]`                                | Always `"ready"` while process is up |
| `db`    | `Literal["connected", "disconnected", "unknown"]` | Result of `SELECT 1` probe           |
| `redis` | `Literal["connected", "disconnected", "unknown"]` | `"unknown"` = Redis not configured   |

503 is returned when `db == "disconnected"` or `redis == "disconnected"`.
`redis == "unknown"` is a valid non-error state (Redis simply not configured).

### `HealthResponse`

Internal model used by helper functions (`check_postgres`, `check_redis`,
`check_worker_queue`).

| Field       | Type                                              | Values                                                  |
| ----------- | ------------------------------------------------- | ------------------------------------------------------- |
| `status`    | `Literal["healthy", "degraded", "unhealthy"]`     | Overall status                                          |
| `postgres`  | `Literal["connected", "disconnected", "unknown"]` | Postgres reachability                                   |
| `redis`     | `Literal["connected", "disconnected", "unknown"]` | Redis reachability                                      |
| `worker`    | `Literal["active", "inactive", "unknown"]`        | RQ worker presence                                      |
| `timestamp` | `datetime`                                        | UTC timestamp; defaults to `datetime.now(timezone.utc)` |

---

## Basis Schemas (`schemas/basis.py`)

### `BasisSetMetadata`

| Field                | Type        | Notes                                   |
| -------------------- | ----------- | --------------------------------------- |
| `id`                 | `str`       | API value sent as `basis_set_override`  |
| `label`              | `str`       | Display label                           |
| `description`        | `str`       | UI-safe summary                         |
| `family`             | `str`       | Basis family (`minimal`, `pople`, etc.) |
| `recommended`        | `bool`      | Highlighted selector option             |
| `supported_elements` | `list[str]` | Best-effort element coverage metadata   |

### `BasisSetListResponse`

- `default_basis_set`: `str`
- `basis_sets`: `list[BasisSetMetadata]`

---

## Settings Schemas (`schemas/settings.py`)

### `IbmCredentialProfileCreate`

Write-only request body for encrypted local IBM Runtime profiles.

| Field      | Type   | Notes                                    |
| ---------- | ------ | ---------------------------------------- |
| `name`     | `str`  | Unique display name                      |
| `token`    | `str`  | Write-only; encrypted before persistence |
| `crn`      | `str`  | Runtime instance/CRN; encrypted at rest  |
| `channel`  | `str`  | Defaults to `ibm_quantum_platform`       |
| `activate` | `bool` | Whether to make this profile active      |

### `IbmCredentialProfileResponse`

Safe response shape. It never includes raw credentials, encrypted blobs, or
masked credential previews.

| Field        | Type       | Notes                 |
| ------------ | ---------- | --------------------- |
| `id`         | `UUID`     | Profile id            |
| `name`       | `str`      | Display name          |
| `channel`    | `str`      | Runtime channel       |
| `active`     | `bool`     | Active profile marker |
| `created_at` | `datetime` | Creation time         |
| `updated_at` | `datetime` | Last update time      |

### `IbmCredentialProfileUpdate`

Partial update request for profile metadata and secret rotation.

| Field      | Type           | Notes                                     |
| ---------- | -------------- | ----------------------------------------- |
| `name`     | `str \| None`  | Optional display-name replacement         |
| `token`    | `str \| None`  | Optional write-only token replacement     |
| `crn`      | `str \| None`  | Optional write-only CRN/instance rotation |
| `channel`  | `str \| None`  | Optional Runtime channel replacement      |
| `activate` | `bool \| None` | Optional active/inactive toggle           |

### `IbmCredentialProfileListResponse`

- `profiles`: `list[IbmCredentialProfileResponse]`
- `active_profile_id`: `UUID | None`
- `encryption_key_source`: `str`
- `encryption_warning`: `str | None`

### `IbmCredentialProfileTestResponse`

- `id`: `UUID`
- `ok`: `bool`
- `message`: `str`
- `active_instance`: `str | None`

The implemented test path decrypts the locally stored credentials and then
attempts IBM Runtime validation with those credentials. Success responses
include a backend-specific message such as
`IBM Runtime credentials validated successfully using backend ibm_brisbane.`,
while timeout or runtime failures return a non-secret failure message. The
response still keeps `active_instance` null so the saved instance value is not
echoed back to the caller.

---

## Frontend TypeScript Types (`src/types/run.ts`)

The checked-in `frontend/src/types/generated-api.ts` file mirrors the public
OpenAPI schema. Feature-specific TypeScript interfaces remain in
`frontend/src/types/run.ts` and the API modules use them at their boundaries.

**`RunCreate`**

Request body for `createRun()`. Maps to backend `RunCreate` (algorithm-aware
shape).

| Field                   | Type                                                | Notes                                               |
| ----------------------- | --------------------------------------------------- | --------------------------------------------------- |
| `molecule_id`           | `UUID`                                              | Required                                            |
| `algorithm`             | `RunAlgorithm`                                      | `vqe` \| `sqd` \| `kqd` \| `qfd` \| `qse` \| `skqd` |
| `mode`                  | `"easy" \| "advanced"`                              | Required                                            |
| `backend_target`        | `"statevector" \| "aer_simulator" \| "ibm_runtime"` | Required                                            |
| `easy_options`          | `EasyOptions` (optional)                            | Required when `mode === "easy"`                     |
| `advanced_config`       | `AdvancedConfig` (optional)                         | Required when `mode === "advanced"`                 |
| `basis_set_override`    | `string` (optional)                                 | Run-level override of the default basis             |
| `noise_profile`         | `NoiseProfile` (optional)                           | Backend-dependent noise configuration               |
| `ibm_runtime_confirmed` | `boolean` (optional)                                | Required as `true` when creating IBM Runtime runs   |
| `client_request_id`     | `UUID` (optional)                                   | Idempotency key                                     |

**`RunCancelResponse`**

Returned by `cancelRun()`. Maps to backend `RunCancelResponse`.

| Field    | Type        |
| -------- | ----------- |
| `id`     | `UUID`      |
| `status` | `RunStatus` |

**`MoleculeCreate`**

Request body for `createMolecule()`. Maps to backend `MoleculeCreate`. Mirrors
the backend shape: no `basis_set` field (basis selection lives on `runs`).

| Field          | Type                                   | Notes                         |
| -------------- | -------------------------------------- | ----------------------------- |
| `name`         | `string`                               | Required                      |
| `atoms`        | `AtomSchema[]`                         | Required; ≥1 atom             |
| `charge`       | `number` (optional)                    | Default `0`                   |
| `multiplicity` | `number` (optional)                    | Default `1`                   |
| `active_space` | `ActiveSpaceSchema \| null` (optional) | Correlated calculation space  |
| `pubchem_cid`  | `number \| null` (optional)            | PubChem CID enrichment        |
| `iupac_name`   | `string \| null` (optional)            |                               |
| `description`  | `string \| null` (optional)            |                               |
| `synonyms`     | `string[] \| null` (optional)          |                               |
| `smiles`       | `string \| null` (optional)            |                               |
| `inchi`        | `string \| null` (optional)            |                               |
| `inchi_key`    | `string \| null` (optional)            | 27-char InChIKey when present |

**`MoleculeUpdate`**

Request body for `updateMolecule()`. Maps to backend `MoleculeUpdate`. All
fields optional — omit to leave unchanged.

| Field          | Type                                   | Notes                             |
| -------------- | -------------------------------------- | --------------------------------- |
| `name`         | `string` (optional)                    |                                   |
| `atoms`        | `AtomSchema[]` (optional)              |                                   |
| `charge`       | `number` (optional)                    |                                   |
| `multiplicity` | `number` (optional)                    |                                   |
| `active_space` | `ActiveSpaceSchema \| null` (optional) | Pass `null` to clear active space |

**`RunValidationRequest`**

Request body for `validateConfig()`. Maps to backend `RunValidationRequest`.

| Field         | Type        | Notes                                 |
| ------------- | ----------- | ------------------------------------- |
| `molecule_id` | `UUID`      |                                       |
| `run`         | `RunCreate` | Full algorithm-aware run payload copy |

**`RunValidationErrorDetail`**

Single validation error in `RunValidationResponse.errors`. Maps to backend
`RunValidationErrorDetail`.

| Field     | Type     |
| --------- | -------- |
| `field`   | `string` |
| `message` | `string` |

**`RunValidationResponse`**

Response from `validateConfig()`. Maps to backend `RunValidationResponse`.
Always returned with HTTP 200.

| Field      | Type                         | Notes                                                                                   |
| ---------- | ---------------------------- | --------------------------------------------------------------------------------------- |
| `valid`    | `boolean`                    | `true` when `errors` is empty                                                           |
| `errors`   | `RunValidationErrorDetail[]` | Schema/semantic violations                                                              |
| `warnings` | `string[]`                   | Non-blocking advisory messages                                                          |
| `estimate` | `RunEstimate \| null`        | Optional runtime projection; ETA fields stay null until history or telemetry is trusted |

**`ExportBundle`**

Returned by `exportRun()`. Maps to backend `ExportBundle`. Reproducibility
export containing the full run snapshot.

| Field            | Type                             | Notes                           |
| ---------------- | -------------------------------- | ------------------------------- |
| `export_version` | `string`                         | Always `"1.0"`                  |
| `exported_at`    | `string`                         | UTC ISO 8601 timestamp          |
| `molecule`       | `MoleculeResponse`               | Full molecule definition        |
| `run`            | `RunResponse`                    | Full run with config snapshot   |
| `versions`       | `Record<string, string> \| null` | Dependency versions             |
| `events`         | `RunEventResponse[]`             | All events in sequence order    |
| `result`         | `RunResultResponse \| null`      | `null` if run has not completed |

**`HealthResponse`**

Simplified frontend type for internal health status objects.

| Field    | Type     |
| -------- | -------- |
| `status` | `string` |

**`StatusResponse`**

Returned by `getStatus()`. Maps to backend `StatusResponse`.

| Field   | Type     | Notes                                            |
| ------- | -------- | ------------------------------------------------ |
| `api`   | `string` | Always `"ready"` while the process is up         |
| `db`    | `string` | `"connected"` \| `"disconnected"` \| `"unknown"` |
| `redis` | `string` | `"connected"` \| `"disconnected"` \| `"unknown"` |
