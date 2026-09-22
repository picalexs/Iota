from __future__ import annotations

from quantum_diag.benchmark_matrix import BenchmarkMatrixRunner
from quantum_diag.classical_baselines import ClassicalBaseline
from quantum_diag.config import ExperimentSpec
from quantum_diag.test_fixtures import get_h2_geometry


def _base_runner() -> BenchmarkMatrixRunner:
    geometry = get_h2_geometry()
    baseline = ClassicalBaseline()
    reference = baseline.compute_casci_energy(
        geometry,
        "sto-3g",
        geometry.active_space,
    )["energy"]

    base_spec = ExperimentSpec(
        molecule_name="H2",
        basis_set="sto-3g",
        method="VQE",
        ansatz_type="RealAmplitudes",
        optimizer="COBYLA",
        max_iterations=3,
        shots=128,
        seed=11,
        backend_name="qasm_simulator",
    )
    return BenchmarkMatrixRunner(base_spec=base_spec, reference_energy_map={"H2": reference})


def test_runtime_schema_fields_present_and_consistent() -> None:
    runner = _base_runner()
    rows = runner.run_matrix(
        methods=["VQE", "SQD"],
        molecules=["H2"],
        seeds=[11],
        ansatz_types=["RealAmplitudes"],
        optimizers=["COBYLA"],
        max_iterations=3,
        progress=False,
    )

    assert len(rows) == 2
    for row in rows:
        assert "algorithm_wall_time_seconds" in row
        assert "end_to_end_wall_time_seconds" in row
        assert "prewarm_share_seconds" in row
        assert row["runtime_measurement_mode"] == "algorithm-primary-with-end-to-end-secondary"

        assert row["algorithm_wall_time_seconds"] is not None
        assert row["end_to_end_wall_time_seconds"] is not None
        assert row["end_to_end_wall_time_seconds"] >= row["algorithm_wall_time_seconds"]


def test_runtime_order_bias_reduced_after_prewarm() -> None:
    runner_a = _base_runner()
    rows_a = runner_a.run_matrix(
        methods=["VQE", "SQD"],
        molecules=["H2"],
        seeds=[11],
        ansatz_types=["RealAmplitudes"],
        optimizers=["COBYLA"],
        max_iterations=3,
        progress=False,
    )

    runner_b = _base_runner()
    rows_b = runner_b.run_matrix(
        methods=["SQD", "VQE"],
        molecules=["H2"],
        seeds=[11],
        ansatz_types=["RealAmplitudes"],
        optimizers=["COBYLA"],
        max_iterations=3,
        progress=False,
    )

    by_method_a = {row["method"]: row for row in rows_a}
    by_method_b = {row["method"]: row for row in rows_b}

    for method in ["VQE", "SQD"]:
        t_a = float(by_method_a[method]["algorithm_wall_time_seconds"])
        t_b = float(by_method_b[method]["algorithm_wall_time_seconds"])
        ratio = max(t_a, t_b) / max(min(t_a, t_b), 1e-9)
        assert ratio < 3.0
