from __future__ import annotations

import warnings

from quantum_diag.benchmark_matrix import BenchmarkMatrixRunner
from quantum_diag.config import ExperimentSpec
from quantum_diag.optimizers import get_optimizer


def test_get_optimizer_warns_for_low_cobyla_budget() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        opt = get_optimizer("COBYLA", maxiter=3, num_vars=5)

    assert opt is not None
    assert any("COBYLA maxiter is lower" in str(w.message) for w in caught)


def test_matrix_captures_warnings_and_flags_cobyla_adjustment() -> None:
    base_spec = ExperimentSpec(
        molecule_name="H2",
        basis_set="sto-3g",
        method="VQE",
        ansatz_type="RealAmplitudes",
        optimizer="COBYLA",
        max_iterations=1,
        shots=128,
        seed=11,
        backend_name="qasm_simulator",
    )

    runner = BenchmarkMatrixRunner(
        base_spec=base_spec,
        reference_energy_map={"H2": -1.13730604},
    )

    rows = runner.run_matrix(
        methods=["VQE"],
        molecules=["H2"],
        seeds=[11],
        ansatz_types=["RealAmplitudes"],
        optimizers=["COBYLA"],
        max_iterations=1,
        progress=False,
    )

    assert len(rows) == 1
    row = rows[0]

    assert "warnings" in row
    assert "warnings_count" in row
    assert "warnings_total_count" in row
    assert "cobyla_maxfun_adjusted" in row
    assert row["warnings_count"] >= 1
    assert row["warnings_total_count"] >= row["warnings_count"]
    assert row["cobyla_maxfun_adjusted"] is True
    assert any("Invalid MAXFUN" in msg for msg in row["warnings"])
