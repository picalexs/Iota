# Current Data Model

## Scope

Document the database contract implemented by the backend models and covered by
backend tests.

## Tables

### `molecules`

| Column         | Type           | Notes                                          |
| -------------- | -------------- | ---------------------------------------------- |
| `id`           | `UUID`         | PK                                             |
| `name`         | `VARCHAR(255)` | unique, non-empty                              |
| `atoms`        | `JSONB`        | list of `{symbol, x, y, z}` objects            |
| `charge`       | `INTEGER`      | default `0`, non-null                          |
| `multiplicity` | `INTEGER`      | default `1`, non-null, check `>= 1`            |
| `active_space` | `JSONB`        | nullable, extensible object                    |
| `pubchem_cid`  | `INTEGER`      | nullable, unique (NULLs excluded); PubChem CID |
| `iupac_name`   | `VARCHAR(512)` | nullable; IUPAC systematic name                |
| `description`  | `TEXT`         | nullable; full description from PubChem        |
| `synonyms`     | `JSONB`        | nullable; list of up to 10 synonym strings     |
| `smiles`       | `VARCHAR(512)` | nullable; canonical SMILES notation            |
| `inchi`        | `TEXT`         | nullable; IUPAC InChI identifier               |
| `inchi_key`    | `VARCHAR(27)`  | nullable; 27-char InChIKey hash                |
| `created_at`   | `TIMESTAMPTZ`  | UTC-aware                                      |
| `updated_at`   | `TIMESTAMPTZ`  | UTC-aware                                      |

Note: `basis_set` is not a molecule column. It is a run-level computational
parameter stored on `runs.basis_set` (default `sto-3g`) and may be overridden
per run via `RunCreate.basis_set_override`.

Chemistry mapping: `Molecule.to_chemistry_input(basis_set)` produces the worker
input shape consumed by `worker/chemistry/molecule_builder.py`:

- `atoms` is copied as a list of `{symbol, x, y, z}` dictionaries
- `basis` is supplied by the run-level basis set
- `charge` and `multiplicity` are copied from the molecule row
- `active_space` is preserved unchanged when present

### `runs`

| Column                    | Type             | Notes                                                                                                       |
| ------------------------- | ---------------- | ----------------------------------------------------------------------------------------------------------- |
| `id`                      | `UUID`           | PK                                                                                                          |
| `molecule_id`             | `UUID`           | FK -> `molecules.id`                                                                                        |
| `status`                  | `ENUM-as-string` | `CREATED`, `QUEUED`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED`, `SUBMITTED_TO_IBM`, `PAUSING`, `PAUSED` |
| `algorithm`               | `ENUM-as-string` | nullable; `vqe`, `qse`, `kqd`, `qfd`, `sqd`, `skqd`                                                         |
| `mode`                    | `ENUM-as-string` | nullable; `easy`, `advanced`                                                                                |
| `backend_target`          | `ENUM-as-string` | nullable; `statevector`, `aer_simulator`, `ibm_runtime`                                                     |
| `basis_set`               | `VARCHAR(255)`   | basis set used for this run; default `'sto-3g'`                                                             |
| `config_json`             | `JSONB`          | immutable run configuration snapshot (includes `basis_set_override`)                                        |
| `ibm_job_id`              | `VARCHAR(255)`   | nullable                                                                                                    |
| `client_request_id`       | `UUID`           | nullable, unique idempotency key                                                                            |
| `execution_generation`    | `INTEGER`        | non-null, default `1`; incremented by resume/restart control actions                                        |
| `restarted_from_run_id`   | `UUID`           | nullable self-FK -> `runs.id`; source run for restart clones                                                |
| `credential_profile_id`   | `UUID`           | nullable FK -> `ibm_credential_profiles.id`; non-secret IBM profile reference                               |
| `credential_profile_name` | `VARCHAR(255)`   | nullable snapshot of the IBM profile display name used at creation time                                     |
| `versions`                | `JSONB`          | nullable runtime versions snapshot                                                                          |
| `metadata`                | `JSONB`          | nullable arbitrary metadata; mapped to ORM attribute `run_metadata`                                         |
| `initial_estimate`        | `JSONB`          | nullable `RunEstimate` snapshot produced by validation or by the post-create async ETA seeding task         |
| `latest_estimate`         | `JSONB`          | nullable `RunEstimate` snapshot backfilled post-create when still empty, then refreshed by worker telemetry |
| `created_at`              | `TIMESTAMPTZ`    | UTC-aware                                                                                                   |
| `updated_at`              | `TIMESTAMPTZ`    | UTC-aware                                                                                                   |

`backend_target`, `SUBMITTED_TO_IBM`, `ibm_job_id`, `ibm_job_submitted`, and
`ibm_status_poll` are runtime contract fields. Validation can create
`statevector` and `aer_simulator` rows. IBM Runtime rows require credentials and
an algorithm with an implemented hardware path. Missing credentials return
validation errors.

Indexes:

- `idx_runs_status` on `runs(status)`
- `idx_runs_molecule_id` on `runs(molecule_id)`
- `idx_runs_molecule_status` on `runs(molecule_id, status)`
- `idx_runs_client_request_id` on `runs(client_request_id)`
- `idx_runs_restarted_from_run_id` on `runs(restarted_from_run_id)`
- `idx_runs_credential_profile_id` on `runs(credential_profile_id)`

### `benchmark_runs`

| Column                   | Type           | Notes                                                         |
| ------------------------ | -------------- | ------------------------------------------------------------- |
| `id`                     | `UUID`         | PK                                                            |
| `name`                   | `VARCHAR(255)` | saved benchmark display name                                  |
| `selected_molecule_keys` | `JSONB`        | molecule keys selected in the saved workspace                 |
| `selected_algorithms`    | `JSONB`        | algorithm identifiers selected in the saved workspace         |
| `selected_basis`         | `VARCHAR(255)` | shared basis-set choice                                       |
| `selected_backend_mode`  | `VARCHAR(64)`  | shared backend mode                                           |
| `selected_backend_name`  | `VARCHAR(255)` | nullable concrete backend name                                |
| `chemical_accuracy_ha`   | `FLOAT`        | saved chemical-accuracy threshold in Hartree                  |
| `custom_molecules`       | `JSONB`        | benchmark-only molecule definitions                           |
| `entries`                | `JSONB`        | row snapshots, including generated `runId` values when linked |
| `created_at`             | `TIMESTAMPTZ`  | UTC-aware                                                     |
| `updated_at`             | `TIMESTAMPTZ`  | UTC-aware                                                     |

`benchmark_runs.entries` stores row state and generated run identifiers as JSON
so saved dashboards can reopen even when a run row is later deleted. Associated
run deletion is handled by `BenchmarkRunService`, not by a database foreign key.

Indexes:

- `idx_benchmark_runs_created_at` on `benchmark_runs(created_at)`
- `idx_benchmark_runs_updated_at` on `benchmark_runs(updated_at)`

### `run_checkpoints`

| Column                 | Type          | Notes                                                        |
| ---------------------- | ------------- | ------------------------------------------------------------ |
| `id`                   | `UUID`        | PK                                                           |
| `run_id`               | `UUID`        | FK -> `runs.id`, `ON DELETE CASCADE`                         |
| `execution_generation` | `INTEGER`     | generation the checkpoint belongs to                         |
| `algorithm`            | `VARCHAR(32)` | algorithm label captured at checkpoint time                  |
| `checkpoint_version`   | `VARCHAR(32)` | checkpoint payload schema/version marker; default `'1.0'`    |
| `payload`              | `JSONB`       | non-secret algorithm checkpoint payload                      |
| `event_sequence`       | `INTEGER`     | nullable event sequence associated with the checkpoint write |
| `created_at`           | `TIMESTAMPTZ` | UTC-aware                                                    |

Indexes:

- `idx_run_checkpoints_run_generation` on `(run_id, execution_generation)`

### `ibm_credential_profiles`

| Column            | Type           | Notes                                                           |
| ----------------- | -------------- | --------------------------------------------------------------- |
| `id`              | `UUID`         | PK                                                              |
| `name`            | `VARCHAR(255)` | unique display name                                             |
| `encrypted_token` | `TEXT`         | encrypted locally; never returned by API schemas                |
| `encrypted_crn`   | `TEXT`         | encrypted locally; never returned by API schemas                |
| `channel`         | `VARCHAR(64)`  | IBM Runtime channel                                             |
| `active`          | `BOOLEAN`      | active profile used when a run omits profile ID                 |
| `token_hint`      | `VARCHAR(32)`  | legacy nullable hint column; scrubbed and never returned by API |
| `crn_hint`        | `VARCHAR(64)`  | legacy nullable hint column; scrubbed and never returned by API |
| `created_at`      | `TIMESTAMPTZ`  | UTC-aware                                                       |
| `updated_at`      | `TIMESTAMPTZ`  | UTC-aware                                                       |

Indexes:

- `idx_ibm_credential_profiles_active` on `ibm_credential_profiles(active)`
- `idx_ibm_credential_profiles_name` on `ibm_credential_profiles(name)`

### `ibm_runtime_jobs`

| Column                 | Type           | Notes                                          |
| ---------------------- | -------------- | ---------------------------------------------- |
| `id`                   | `UUID`         | PK                                             |
| `run_id`               | `UUID`         | FK -> `runs.id`, `ON DELETE CASCADE`           |
| `execution_generation` | `INTEGER`      | generation that submitted/observed the IBM job |
| `ibm_job_id`           | `VARCHAR(255)` | non-secret IBM Runtime job identifier          |
| `primitive_type`       | `VARCHAR(64)`  | nullable primitive type                        |
| `backend_name`         | `VARCHAR(255)` | nullable backend name                          |
| `status`               | `VARCHAR(64)`  | nullable remote status snapshot                |
| `submitted_at`         | `TIMESTAMPTZ`  | nullable remote submission timestamp           |
| `completed_at`         | `TIMESTAMPTZ`  | nullable remote completion timestamp           |
| `metadata`             | `JSONB`        | nullable non-secret remote metadata            |
| `created_at`           | `TIMESTAMPTZ`  | UTC-aware                                      |
| `updated_at`           | `TIMESTAMPTZ`  | UTC-aware                                      |

Indexes:

- `idx_ibm_runtime_jobs_run_id` on `ibm_runtime_jobs(run_id)`
- `idx_ibm_runtime_jobs_job_id` on `ibm_runtime_jobs(ibm_job_id)`
- `idx_ibm_runtime_jobs_status` on `ibm_runtime_jobs(status)`

### `run_events`

| Column       | Type             | Notes                                                                                                                                                                                              |
| ------------ | ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `id`         | `INTEGER`        | PK, autoincrement                                                                                                                                                                                  |
| `run_id`     | `UUID`           | FK -> `runs.id` with `ON DELETE CASCADE`                                                                                                                                                           |
| `sequence`   | `INTEGER`        | monotonic per run                                                                                                                                                                                  |
| `type`       | `ENUM-as-string` | `status_changed`, `iteration_update`, `error`, `result`, `estimate_updated`, `ibm_job_submitted`, `ibm_status_poll`, `control_requested`, `checkpoint_saved`, `resume_enqueued`, `restart_created` |
| `payload`    | `JSONB`          | event payload                                                                                                                                                                                      |
| `created_at` | `TIMESTAMPTZ`    | UTC-aware                                                                                                                                                                                          |

Constraints and indexes:

- Unique `uq_run_events_run_id_sequence` on `(run_id, sequence)`
- `idx_run_events_run_id` on `run_events(run_id)`
- `idx_run_events_type` on `run_events(type)`

### `run_results`

| Column                   | Type           | Notes                                               |
| ------------------------ | -------------- | --------------------------------------------------- |
| `id`                     | `UUID`         | PK                                                  |
| `run_id`                 | `UUID`         | FK -> `runs.id`, unique, `ON DELETE CASCADE`        |
| `energy`                 | `FLOAT`        | non-null                                            |
| `iterations`             | `INTEGER`      | non-null                                            |
| `optimal_parameters`     | `JSON`         | non-null parameters associated with reported energy |
| `converged`              | `BOOLEAN`      | non-null                                            |
| `algorithm_metrics`      | `JSON`         | nullable normalized algorithm diagnostics           |
| `final_energy`           | `FLOAT`        | nullable final solver energy                        |
| `best_observed_energy`   | `FLOAT`        | nullable best observed or selected energy           |
| `reported_energy`        | `FLOAT`        | nullable UI/reporting energy                        |
| `reported_energy_source` | `VARCHAR(64)`  | nullable source label for reported energy           |
| `reference_energy`       | `FLOAT`        | nullable reference/comparison energy                |
| `reference_basis`        | `VARCHAR(255)` | nullable reference basis label                      |
| `signed_error`           | `FLOAT`        | nullable signed error against reference             |
| `raw_result`             | `JSON`         | nullable                                            |
| `created_at`             | `TIMESTAMPTZ`  | UTC-aware                                           |

## Deletion semantics

- ORM side: `Run.events`, `Run.result`, `Run.checkpoints`, and
  `Run.ibm_runtime_jobs` use `cascade="all, delete-orphan"`.
- DB side: `run_events.run_id`, `run_results.run_id`, `run_checkpoints.run_id`,
  and `ibm_runtime_jobs.run_id` use `ON DELETE CASCADE`.
- Effective behavior: deleting a run removes related events, result,
  checkpoints, and non-secret IBM Runtime job records.

## Migrations

The repository ships the consolidated initial Alembic migration plus focused
follow-up migrations for run controls, IBM profile snapshots, and saved
benchmark dashboards:

- `backend/alembic/versions/20260511_0001_initial_schema.py`
  - `down_revision = None`.
  - Creates `molecules` (with all 7 PubChem enrichment columns, name-unique,
    `pubchem_cid`-unique), `runs` (with first-class `algorithm`/`mode`/
    `backend_target` enum columns, `basis_set` default `sto-3g`,
    `initial_estimate`/`latest_estimate` JSONB snapshots), `run_results` (with
    `algorithm_metrics` and `raw_result` JSONB), and `run_events` (with
    `estimate_updated` in the event-type enum).
  - Defines the enums `run_status`, `run_algorithm`, `run_mode`,
    `backend_target`, and `run_event_type` via
    `sa.Enum(..., native_enum=False, create_constraint=True)` so they are
    portable across Postgres and SQLite.
  - Installs canonical indexes: `idx_runs_status`, `idx_runs_molecule_id`,
    `idx_runs_client_request_id`, `idx_run_events_run_id`,
    `idx_run_events_type`, `idx_run_results_run_id`, plus the unique constraint
    `uq_run_events_run_id_sequence` on `(run_id, sequence)`.
  - Declares cascade FKs: `run_events.run_id` and `run_results.run_id` both
    reference `runs.id` with `ON DELETE CASCADE`; `runs.molecule_id` references
    `molecules.id`.
  - Adds `idx_runs_molecule_status` on `(molecule_id, status)` for filtered run
    list queries.
- `backend/alembic/versions/20260531_0002_controls_profiles_imports.py`
  - Extends `run_status` with `PAUSING` and `PAUSED`.
  - Extends `run_event_type` with `control_requested`, `checkpoint_saved`,
    `resume_enqueued`, and `restart_created`.
  - Adds `execution_generation`, `restarted_from_run_id`, and
    `credential_profile_id` to `runs`.
  - Adds encrypted local `ibm_credential_profiles`, durable `run_checkpoints`,
    and non-secret `ibm_runtime_jobs` tables.
  - Adds run-result provenance columns for final/best/reported/reference energy
    tracking.
- `backend/alembic/versions/20260601_0003_ibm_profile_name_snapshot.py`
  - Adds `runs.credential_profile_name` so historical IBM Runtime runs can keep
    displaying the profile name used at submission time.
- `backend/alembic/versions/20260602_0004_benchmark_runs.py`
  - Creates `benchmark_runs` for saved benchmark workspace snapshots, row
    results, custom molecules, and linked generated run identifiers.

The `20260219_0001`, `20260223_*`, `20260227_0003`, and `20260301_*`
intermediate migrations have been consolidated into this initial-schema
revision. Downgrading past it drops the four base tables.
