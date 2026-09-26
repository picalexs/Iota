# QSS benchmark exporter

This folder provides three independent commands. Run them in this order:

1. Create a benchmark and submit its runs to the QSS API.
2. Export compact results from the API or from a saved folder.
3. Create plots from the API or from the exported folder.

The commands use separate output directories. You can repeat export and plot
steps without submitting runs again.

## Install

Use Python 3.11 or newer. Install the exporter dependencies in an environment:

```sh
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Use the Python executable from that environment for all commands below.

## 1. Create a benchmark

Start the QSS API. The default API URL is `http://localhost:18000`.

Create a campaign file. The campaign expands to one QSS run for each molecule,
algorithm variant, and seed.

```json
{
  "name": "local-h2-seeds",
  "campaign_id": "local-h2-seeds",
  "molecules": [
    {"id": "<molecule-id>"}
  ],
  "algorithms": [
    {"algorithm": "vqe", "mode": "advanced", "advanced_config": {}},
    {"algorithm": "sqd", "mode": "advanced", "advanced_config": {}}
  ],
  "seeds": [11, 17, 23],
  "basis_set": "sto-3g",
  "backend": {
    "target": "aer_simulator",
    "options": {"optimization_level": 1}
  },
  "metadata": {"purpose": "local seed check"}
}
```

Save the file as `campaign.json`, then run:

```sh
.venv/bin/python create_benchmark.py campaign.json \
  --output-dir output/local-h2-seeds
```

The command writes `campaign.json`, `benchmark.json`, `submission.json`, and
`submission_summary.json` to the checkpoint directory. It updates the
checkpoint after each run. Run the same command again to resume an interrupted
campaign. Add `--wait` when the command must wait for terminal run states.

The command does not acquire molecule data unless the campaign sets
`"acquire_molecules": true`. Use molecule IDs when possible.

### Seed handling

Each seed is a separate QSS run. The checkpoint records the seed and its roles.

- `simulator` sets `backend_options.seed_simulator`.
- `transpiler` sets `backend_options.seed_transpiler`.
- `algorithm` sets `advanced_config.seed` for VQE or SQD. It sets
  `advanced_config.base_sampling_options.seed` for SKQD.
- `sampling` sets SQD's nested VQE seed in
  `advanced_config.sampling_vqe_seed`. Use it only when
  `sampling_state_source` is `vqe`.
- `reference` sets QSE's nested VQE reference seed in
  `advanced_config.vqe_reference_seed`. Use it only when
  `reference_method` is `vqe`.

KQD and QFD do not use algorithm-level randomness. QSE uses the `reference`
role only for a VQE reference solve. QSE with an HF reference, KQD, and QFD
use the simulator and transpiler roles for local targets. Set `seed_roles`
explicitly on a variant to select a supported combination.

The same campaign seed is written to every selected role. Use separate
algorithm variants when you need to vary one role while holding another role
constant. For example:

```json
{
  "algorithm": "sqd",
  "mode": "advanced",
  "seed_roles": ["algorithm", "sampling"],
  "advanced_config": {"sampling_state_source": "vqe"}
}
```

If `noise_profile` is set at the campaign level, the exporter copies it to
each variant that does not define its own profile.

The default workflow targets `statevector` or `aer_simulator`. IBM Runtime
submission is blocked unless the caller passes `--allow-ibm`. Do not pass that
flag for local tests or this workflow.

Backend-derived Aer noise reads IBM backend properties for a local simulation.
It requires an active saved IBM profile and the local operator token. Set
`QSS_LOCAL_OPERATOR_TOKEN` for the exporter process. The exporter sends the
token in the local operator header and does not write it to campaign files.

### Noisy Aer budget

For noisy Aer, omit `estimator_precision` from `backend.options` to use the
automatic policy. The exporter keeps the configured `shots` value and the
worker derives the estimator precision as `1/sqrt(shots)`. The default `4096`
budget gives `0.015625`. Use `1024` (`0.03125`) for a faster development pilot.
Set `estimator_precision` to `0.0` only for an explicit exact diagnostic.

## 2. Export benchmark results

Export a saved QSS benchmark through the API:

```sh
.venv/bin/python export_benchmark.py \
  --benchmark-id <benchmark-id> \
  --output-dir output/local-h2-seeds/export
```

You can also export from an existing campaign or export folder:

```sh
.venv/bin/python export_benchmark.py output/local-h2-seeds \
  --output-dir output/local-h2-seeds/export
```

A create checkpoint exports the run IDs and current statuses that it knows.
Use the benchmark-ID form after runs finish to fetch result fields.

The exporter keeps only the fields needed for comparison and audit:

- benchmark and entry identifiers;
- molecule, algorithm, basis, backend, and seed metadata;
- run status and error message;
- final energy, reference energy, signed error, absolute error, iterations,
  convergence, and runtime.
- requested and effective shot counts;
- requested and effective estimator precision, measurement mode, Aer method,
  noise provenance, and actual execution path.
- reference method, solver path, basis, active space, validity status, and
  Hamiltonian hash;
- convergence termination, convergence value and threshold, basis rank,
  objective-evaluation budget, selected-CI fraction, and full-sector status;
- convergence diagnostics, reported energy source, exclusion reason, execution
  generation, and restart parent.

The exporter retains convergence and diagnostic fields as provenance. A
completed row with a finite terminal energy result is included in summaries
and plots, even when its configured budget did not establish convergence.
Rows without a completed finite terminal result are excluded from result
aggregates.

For noisy Aer Estimator runs, `requested_shots` is the nominal shot-equivalent
budget used to derive precision. Aer Estimator precision is not a literal
sampler-shot count. Sampler algorithms report their own shot ledger when it is
available.

The default output contains:

- `benchmark.json`: compact benchmark metadata;
- `runs.json` and `runs.csv`: one compact row per campaign entry;
- `summaries/`: status-aware algorithm and molecule summaries;
- `summaries/field_presence.csv`: present and missing counts for every exported
  canonical field;
- `manifest.json`: schema version, counts, runtime source, and source digest.

The exporter does not include event streams or raw result payloads by default.
Use `--include-raw` only when those API payloads are required for an audit.

The exporter preserves persisted eligibility decisions by default. Use
`--recompute-eligibility` with a benchmark-ID export only when you want the
documented compatibility rules for legacy API results. The command records
`eligibility_source: compatibility_recomputed` for each changed row. It does
not change the saved benchmark or worker results.

The API source uses QSS read endpoints. It does not connect to the database
directly. This keeps API and database-backed exports consistent.

## 3. Create plots

Create plots from an exported folder:

```sh
.venv/bin/python plot_benchmark.py output/local-h2-seeds/export \
  --output-dir output/local-h2-seeds/plots
```

Create the same plots directly from a saved QSS benchmark:

```sh
.venv/bin/python plot_benchmark.py \
  --benchmark-id <benchmark-id> \
  --output-dir output/local-h2-seeds/plots
```

The command writes three plots and `plot_manifest.json`:

- `error_by_algorithm`: absolute or signed error distributions;
- `runtime_by_algorithm`: terminal-row runtime distributions;
- `error_vs_runtime`: positive runtime and error points on log axes.

Error and runtime plots group rows by algorithm and actual execution path.
This prevents Aer sampler, Aer estimator, and local classical paths from
appearing as one method.

Use `--error-view signed` for signed error plots. Use `--format pdf` for a
manuscript-ready vector figure, `--format svg` for editable vector output, or
`--format both` for PNG and SVG. The plot writer
reserves legend space and saves with a tight bounding box to keep text visible.

Completed rows with finite terminal energy errors remain in the error and
runtime plots, including rows that did not establish scientific convergence.
Rows without a finite result are excluded from the relevant plot. The counts
are reported in `plot_manifest.json`.
Signed error plots use a symlog error axis so negative errors remain visible.

## 4. Export the paper data bundle

After the campaigns finish, export every paper campaign and all report
artifacts to `exporter/output`:

```sh
.venv/bin/python -m exporter.export_paper_data \
  --source-root output \
  --output-dir exporter/output \
  --format both
```

The command writes this structure:

```text
exporter/output/
├── manifest.json
├── campaigns/<campaign-id>/
│   ├── benchmark.json
│   ├── runs.json
│   ├── runs.csv
│   ├── summaries/
│   └── plots/
└── paper-report/
    ├── statistics.json
    ├── rows.csv
    ├── *.tex
    └── plots/
```

The campaign folders contain the complete compact export for each campaign.
The campaign `plots/` folders contain the generic plots. The
`paper-report/` folder contains the combined statistics, LaTeX fragments,
and all figures used by the manuscript. `manifest.json` records every
campaign, row count, and report path.

The `both` format writes vector PDF and 300-dpi PNG files. The PDFs embed
the figure fonts. The plots use marker shapes, line styles, and hatch patterns
in addition to color. This keeps categorical differences visible in grayscale
print.

Every completed row with a finite terminal result contributes to the report.
Non-converged finite rows remain visible as terminal results. Rows without a
completed finite result are counted as incomplete. Convergence and diagnostic
fields remain in the exported rows as provenance and budget information.

For a previous combined paper report that contains `rows.csv`, use the
migration input once:

```sh
.venv/bin/python -m exporter.export_paper_data \
  --combined-report-dir /path/to/old/paper-report \
  --output-dir exporter/output \
  --format both
```

The lower-level `paper_report.py` command remains available for generating
only the combined report from already exported campaign folders.

## Tests

Run the exporter tests from the repository root:

```sh
PYTHONPATH=exporter .venv/bin/python -m pytest -q exporter/tests
```

The tests use fake API clients and local rows. They do not submit QSS runs.

## Files

- `create_benchmark.py`: campaign validation, molecule resolution, run
  submission, checkpointing, and optional polling;
- `export_benchmark.py`: compact export from a folder or QSS API;
- `plot_benchmark.py`: plot generation from a folder or QSS API;
- `benchmark_io.py`: shared row normalization, API access, summaries, and
  manifest helpers. It defines the export eligibility contract;
- `benchmark_plots.py`: layout-safe Matplotlib plot builders;
- `export_paper_data.py`: export all paper campaigns and report artifacts
  under `exporter/output`;
- `paper_report.py`: multi-campaign statistics, LaTeX fragments, and
  publication figures;
- `tests/`: focused exporter tests;
