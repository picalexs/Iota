"""Benchmark matrix harness for running multiple methods across molecules and seeds."""

from __future__ import annotations

import time
import traceback
import warnings
from typing import Any

from quantum_diag.config import ExperimentSpec
from quantum_diag.test_fixtures import (
    MoleculeGeometry,
    get_h2_geometry,
    get_lih_geometry,
    get_h2o_geometry,
    get_beh2_geometry,
    get_nh3_geometry,
)
from quantum_diag.vqe_runner import VQERunner
from quantum_diag.kqd_runner import KQDRunner
from quantum_diag.qfd_runner import QFDRunner
from quantum_diag.sqd_runner import SQDRunner
from quantum_diag.skqd_runner import SKQDRunner
from quantum_diag.adapt_vqe_runner import ADAPTVQERunner
from quantum_diag.qse_qeom_runner import QSERunner
from quantum_diag.chemistry_pipeline import build_hamiltonian_bundle


class BenchmarkMatrixRunner:
    """Runner for benchmark matrix across methods, molecules, and seeds."""

    def __init__(
        self,
        base_spec: ExperimentSpec,
        reference_energy_map: dict[str, float],
    ) -> None:
        """Initialize benchmark matrix runner.

        Args:
            base_spec: Base ExperimentSpec to use as template.
            reference_energy_map: Dict mapping molecule name to reference energy.
        """
        self.base_spec = base_spec
        self.reference_energy_map = reference_energy_map

    def _resolve_runner(self, method: str) -> type:
        """Resolve runner class for a method name.

        Args:
            method: Method name (e.g., "VQE", "KQD", "QFD", etc.).

        Returns:
            Runner class (not instantiated).

        Raises:
            ValueError: If method is unknown.
        """
        method_map = {
            "VQE": VQERunner,
            "KQD": KQDRunner,
            "QFD": QFDRunner,
            "SQD": SQDRunner,
            "SKQD": SKQDRunner,
            "ADAPT-VQE": ADAPTVQERunner,
            "QSE": QSERunner,
        }

        if method not in method_map:
            raise ValueError(
                f"Unknown method '{method}'. "
                f"Supported methods: {list(method_map.keys())}"
            )

        return method_map[method]

    def _build_spec_for_case(
        self,
        molecule_name: str,
        seed: int,
        method: str,
        ansatz_type: str | None = None,
        optimizer: str | None = None,
    ) -> ExperimentSpec:
        """Build ExperimentSpec for a specific case.

        Args:
            molecule_name: Name of molecule.
            seed: Random seed.
            method: Method name.
            ansatz_type: Ansatz type (if None, use base_spec's ansatz_type).
            optimizer: Optimizer type (if None, use base_spec's optimizer).

        Returns:
            ExperimentSpec customized for this case.
        """
        ansatz = ansatz_type if ansatz_type is not None else self.base_spec.ansatz_type
        opt = optimizer if optimizer is not None else self.base_spec.optimizer

        spec = ExperimentSpec(
            molecule_name=molecule_name,
            basis_set=self.base_spec.basis_set,
            method=method,
            ansatz_type=ansatz,
            optimizer=opt,
            max_iterations=self.base_spec.max_iterations,
            shots=self.base_spec.shots,
            seed=seed,
            backend_name=self.base_spec.backend_name,
        )

        return spec

    def _get_molecule_geometry(self, molecule_name: str) -> MoleculeGeometry:
        """Get molecule geometry by name.

        Args:
            molecule_name: Name of molecule (e.g., "H2", "LiH", "H2O", "BeH2", "NH3").

        Returns:
            MoleculeGeometry for the molecule.

        Raises:
            ValueError: If molecule is unknown.
        """
        if molecule_name == "H2":
            return get_h2_geometry()
        elif molecule_name == "LiH":
            return get_lih_geometry()
        elif molecule_name == "H2O":
            return get_h2o_geometry()
        elif molecule_name == "BeH2":
            return get_beh2_geometry()
        elif molecule_name == "NH3":
            return get_nh3_geometry()
        else:
            raise ValueError(f"Unknown molecule: {molecule_name}")

    @staticmethod
    def _format_seconds(seconds: float | None) -> str:
        """Format seconds into a compact human-readable duration string."""
        if seconds is None:
            return "n/a"
        if seconds < 60:
            return f"{seconds:.1f}s"
        minutes = int(seconds // 60)
        rem_seconds = seconds % 60
        if minutes < 60:
            return f"{minutes}m{rem_seconds:04.1f}s"
        hours = int(minutes // 60)
        rem_minutes = minutes % 60
        return f"{hours}h{rem_minutes:02d}m"

    def _prewarm_chemistry_cache(self, molecules: list[str]) -> dict[str, float]:
        """Pre-build Hamiltonians once per molecule to reduce method-order bias."""
        timings: dict[str, float] = {}

        for molecule in molecules:
            geometry = self._get_molecule_geometry(molecule)
            start = time.perf_counter()
            build_hamiltonian_bundle(
                molecule_name=molecule,
                geometry=geometry,
                basis_set=self.base_spec.basis_set,
            )
            timings[molecule] = max(0.0, time.perf_counter() - start)

        return timings

    def run_matrix(
        self,
        methods: list[str],
        molecules: list[str],
        seeds: list[int],
        ansatz_types: list[str] | None = None,
        optimizers: list[str] | None = None,
        max_iterations: int = 20,
        progress: bool = False,
        progress_every: int = 1,
    ) -> list[dict[str, Any]]:
        """Run benchmark matrix across methods, molecules, seeds, ansatze, and optimizers.

        Executes a cartesian product of:
        methods × molecules × seeds × ansatz_types × optimizers

        Args:
            methods: List of method names.
            molecules: List of molecule names.
            seeds: List of random seeds.
            ansatz_types: List of ansatz types (if None, uses base_spec's ansatz_type).
            optimizers: List of optimizers (if None, uses base_spec's optimizer).
            max_iterations: Maximum iterations for each run.
            progress: If True, print per-case progress logs with elapsed time and ETA.
            progress_every: Print a progress line every N completed runs.

        Returns:
            List of dicts, one per run, with fields:
            - method, molecule, seed, ansatz_type, optimizer
            - final_energy, reference_energy, energy_error
            - iterations, wall_time_seconds, converged, shots_used
            - algorithm_wall_time_seconds, end_to_end_wall_time_seconds
            - convergence_criterion, runtime_measurement_mode
            - error (if run failed)
        """
        # Use defaults only if None is explicitly passed (not if empty list is passed)
        if ansatz_types is None:
            ansatz_types = [self.base_spec.ansatz_type]
        if optimizers is None:
            optimizers = [self.base_spec.optimizer]

        # Guard against invalid progress interval.
        progress_every = max(1, progress_every)

        rows: list[dict[str, Any]] = []
        total_runs = (
            len(methods)
            * len(molecules)
            * len(seeds)
            * len(ansatz_types)
            * len(optimizers)
        )
        matrix_start = time.perf_counter()
        success_count = 0
        error_count = 0
        chemistry_prewarm_timings: dict[str, float] = {}
        chemistry_prewarm_total_seconds = 0.0

        if progress:
            print(
                "Starting benchmark matrix: "
                f"{len(methods)} methods x {len(molecules)} molecules x "
                f"{len(seeds)} seeds x {len(ansatz_types)} ansatze x "
                f"{len(optimizers)} optimizers = {total_runs} runs"
            )

        if total_runs == 0:
            if progress:
                print("No benchmark runs were scheduled (empty matrix).")
            return rows

        chemistry_prewarm_timings = self._prewarm_chemistry_cache(molecules)
        chemistry_prewarm_total_seconds = sum(chemistry_prewarm_timings.values())
        runs_per_molecule = len(methods) * len(seeds) * len(ansatz_types) * len(optimizers)
        if runs_per_molecule < 1:
            runs_per_molecule = 1

        for method in methods:
            for molecule in molecules:
                for seed in seeds:
                    for ansatz_type in ansatz_types:
                        for optimizer in optimizers:
                            row = self._run_single_case(
                                method=method,
                                molecule=molecule,
                                seed=seed,
                                ansatz_type=ansatz_type,
                                optimizer=optimizer,
                                max_iterations=max_iterations,
                                prewarm_share_seconds=(
                                    chemistry_prewarm_timings.get(molecule, 0.0)
                                    / runs_per_molecule
                                ),
                            )
                            rows.append(row)

                            is_ok = row.get("error") is None
                            if is_ok:
                                success_count += 1
                            else:
                                error_count += 1

                            completed = len(rows)
                            should_print = (
                                progress
                                and (
                                    completed % progress_every == 0
                                    or completed == total_runs
                                )
                            )
                            if should_print:
                                elapsed = time.perf_counter() - matrix_start
                                avg_per_run = elapsed / completed
                                eta = avg_per_run * (total_runs - completed)

                                err_val = row.get("energy_error")
                                if isinstance(err_val, (int, float)):
                                    err_str = f"{float(err_val):.3e}"
                                else:
                                    err_str = "n/a"

                                run_time = row.get("wall_time_seconds")
                                run_time_str = (
                                    self._format_seconds(float(run_time))
                                    if isinstance(run_time, (int, float))
                                    else "n/a"
                                )

                                iter_val = row.get("iterations")
                                iter_str = str(iter_val) if iter_val is not None else "n/a"
                                warn_count = int(row.get("warnings_count", 0) or 0)
                                warn_str = f" warn={warn_count}" if warn_count > 0 else ""

                                status = "OK" if is_ok else "ERR"
                                print(
                                    f"[{completed:>3}/{total_runs}] {status:<3} "
                                    f"method={method:<9} molecule={molecule:<5} "
                                    f"seed={seed:<4} ansatz={ansatz_type:<14} "
                                    f"optimizer={optimizer:<6} iter={iter_str:<4} "
                                    f"err={err_str:<12} run={run_time_str:<8} "
                                    f"elapsed={self._format_seconds(elapsed)} "
                                    f"eta={self._format_seconds(eta)}{warn_str}"
                                )

        if progress:
            total_elapsed = time.perf_counter() - matrix_start
            print(
                "Benchmark matrix finished: "
                f"success={success_count}, errors={error_count}, "
                f"elapsed={self._format_seconds(total_elapsed)}"
            )
            print(
                "Runtime metadata: "
                f"chemistry_prewarm_total={self._format_seconds(chemistry_prewarm_total_seconds)}"
            )

        return rows

    def _run_single_case(
        self,
        method: str,
        molecule: str,
        seed: int,
        ansatz_type: str,
        optimizer: str,
        max_iterations: int,
        prewarm_share_seconds: float = 0.0,
    ) -> dict[str, Any]:
        """Run a single benchmark case.

        Args:
            method: Method name.
            molecule: Molecule name.
            seed: Random seed.
            ansatz_type: Ansatz type.
            optimizer: Optimizer name.
            max_iterations: Maximum iterations.

        Returns:
            Dict with results or error info.
        """
        row: dict[str, Any] = {
            "method": method,
            "molecule": molecule,
            "seed": seed,
            "ansatz_type": ansatz_type,
            "optimizer": optimizer,
            "runtime_measurement_mode": "algorithm-primary-with-end-to-end-secondary",
            "algorithm_wall_time_seconds": None,
            "end_to_end_wall_time_seconds": None,
            "prewarm_share_seconds": prewarm_share_seconds,
            "convergence_criterion": None,
            "warnings": [],
            "warnings_count": 0,
            "warnings_total_count": 0,
            "cobyla_maxfun_adjusted": False,
            "chemistry_pipeline": None,
            "num_qubits": None,
            "hamiltonian_dimension": None,
            "active_space": None,
        }

        try:
            # Get reference energy
            if molecule not in self.reference_energy_map:
                raise ValueError(
                    f"No reference energy for molecule '{molecule}'"
                )
            reference_energy = self.reference_energy_map[molecule]

            # Resolve runner class
            runner_class = self._resolve_runner(method)

            # Build customized spec
            spec = self._build_spec_for_case(
                molecule_name=molecule,
                seed=seed,
                method=method,
                ansatz_type=ansatz_type,
                optimizer=optimizer,
            )
            spec = ExperimentSpec(
                molecule_name=molecule,
                basis_set=spec.basis_set,
                method=spec.method,
                ansatz_type=spec.ansatz_type,
                optimizer=spec.optimizer,
                max_iterations=max_iterations,
                shots=spec.shots,
                seed=seed,
                backend_name=spec.backend_name,
            )

            # Instantiate runner
            runner = runner_class(spec, reference_energy)

            # Get molecule geometry
            geometry = self._get_molecule_geometry(molecule)

            # Run the benchmark
            start_time = time.perf_counter()
            try:
                with warnings.catch_warnings(record=True) as caught_warnings:
                    warnings.simplefilter("always")

                    if method in {"SQD", "SKQD"}:
                        # Sample-based runners now consume molecule geometry
                        final_energy, metrics = runner.run(
                            geometry,
                            num_samples=10,
                            max_iterations=max_iterations,
                        )
                    elif method == "ADAPT-VQE":
                        # ADAPT runner returns BenchmarkMetrics directly.
                        # Use very low gradient threshold to encourage multiple iterations
                        metrics = runner.run(
                            geometry,
                            max_iterations=max_iterations,
                            gradient_threshold=1e-6,
                            pool_size=6,
                        )
                        final_energy = metrics.final_energy
                    elif method == "QSE":
                        # QSE runner returns BenchmarkMetrics directly.
                        metrics = runner.run(
                            geometry,
                            max_excitation_level=2,
                            num_basis_states=3,
                        )
                        final_energy = metrics.final_energy
                    else:
                        # VQE/KQD/QFD runners return (final_energy, BenchmarkMetrics).
                        run_output = runner.run(geometry)
                        if isinstance(run_output, tuple):
                            final_energy, metrics = run_output
                        else:
                            metrics = run_output
                            final_energy = metrics.final_energy

                warning_messages_raw = [
                    f"{w.category.__name__}: {w.message}" for w in caught_warnings
                ]
                warning_messages = list(dict.fromkeys(warning_messages_raw))
                maxfun_adjusted = any("Invalid MAXFUN" in msg for msg in warning_messages_raw)
                row["warnings"] = warning_messages
                row["warnings_count"] = len(warning_messages)
                row["warnings_total_count"] = len(warning_messages_raw)
                row["cobyla_maxfun_adjusted"] = maxfun_adjusted

                if hasattr(metrics, "warnings"):
                    metrics.warnings = warning_messages
                if hasattr(metrics, "cobyla_maxfun_adjusted"):
                    metrics.cobyla_maxfun_adjusted = maxfun_adjusted

            except Exception as e:
                # If runner fails but we can continue, capture the error
                raise RuntimeError(f"Runner failed: {str(e)}") from e

            end_to_end_case_wall_time_seconds = max(0.0, time.perf_counter() - start_time)
            algorithm_wall_time_seconds = max(
                0.0,
                float(
                    getattr(metrics, "wall_time_seconds", end_to_end_case_wall_time_seconds)
                ),
            )
            end_to_end_wall_time_seconds = (
                end_to_end_case_wall_time_seconds + max(0.0, prewarm_share_seconds)
            )

            # Populate row with results
            row.update({
                "final_energy": final_energy,
                "reference_energy": reference_energy,
                "energy_error": metrics.energy_error,
                "iterations": metrics.iterations,
                "wall_time_seconds": algorithm_wall_time_seconds,
                "algorithm_wall_time_seconds": algorithm_wall_time_seconds,
                "end_to_end_wall_time_seconds": end_to_end_wall_time_seconds,
                "converged": metrics.converged,
                "shots_used": metrics.shots_used,
                "convergence_criterion": getattr(metrics, "convergence_criterion", None),
                "warnings": row.get("warnings", []),
                "warnings_count": row.get("warnings_count", 0),
                "warnings_total_count": row.get("warnings_total_count", 0),
                "cobyla_maxfun_adjusted": row.get("cobyla_maxfun_adjusted", False),
                "chemistry_pipeline": getattr(metrics, "chemistry_pipeline", None),
                "num_qubits": getattr(metrics, "num_qubits", None),
                "hamiltonian_dimension": getattr(metrics, "hamiltonian_dimension", None),
                "active_space": getattr(metrics, "active_space", None),
            })

        except Exception as e:
            # Capture error but continue
            row["error"] = str(e)
            row["traceback"] = traceback.format_exc()
            # Fill in default/None values for missing fields
            for field in [
                "final_energy",
                "reference_energy",
                "energy_error",
                "iterations",
                "wall_time_seconds",
                "algorithm_wall_time_seconds",
                "end_to_end_wall_time_seconds",
                "converged",
                "shots_used",
                "convergence_criterion",
                "warnings",
                "warnings_count",
                "warnings_total_count",
                "cobyla_maxfun_adjusted",
                "chemistry_pipeline",
                "num_qubits",
                "hamiltonian_dimension",
                "active_space",
            ]:
                if field not in row:
                    row[field] = None

        return row
