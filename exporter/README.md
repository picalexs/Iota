# Quantum Diag fast benchmark bundle

This folder is a standalone copy of the quantum-diag benchmark tools.

The fast profile runs a bounded local matrix:

- VQE, KQD, and SQD;
- H2 and LiH;
- seeds 11 and 17;
- four iterations per run.

The profile is for quick local checks. It is not a final scientific benchmark.

## Install

Use Python 3.11 or newer. Create an environment in the target repository and
install the bundle dependencies:

```sh
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

The dependency list includes the plotting packages used by the exporter.

## Run the fast benchmark

Run from any directory:

```sh
python /path/to/quantum-diag-fast-bundle/run_fast_benchmark.py
```

The command writes all run files to `output/fast/<UTC timestamp>` inside the
bundle. Use an explicit directory when another repository owns the output:

```sh
python run_fast_benchmark.py --output-dir output/fast/example
```

The command writes raw rows, CSV summaries, plots, runtime metadata, and a
Markdown interpretation report.

## Regenerate plots

Regenerate plots without running the benchmark again:

```sh
python plot_benchmark.py output/fast/example
```

The command writes plots to `output/fast/example/plots_regenerated`.
Use `--error-view signed` when signed energy errors are required.

## Export an existing run

Create canonical row files, grouped summaries, a best-method table, and a
Markdown interpretation report:

```sh
python export_benchmark.py output/fast/example
```

The command writes these files to `output/fast/example/export`.
Use `--output-dir` to select another directory.

## Tests

Run the bundle tests from the bundle root:

```sh
python -m pytest -q
```

## Layout

- `run_fast_benchmark.py`: fast benchmark starter;
- `plot_benchmark.py`: plots-only entry point;
- `export_benchmark.py`: row and summary exporter;
- `quantum_diag/`: benchmark runners, chemistry helpers, plotting, and
  aggregation code;
- `tests/`: copied regression tests;
- `output/`: generated artifacts. This folder is ignored by the bundle's
  package-level `.gitignore` when the bundle is copied into a repository.
