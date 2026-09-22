from __future__ import annotations

import numpy as np

from quantum_diag.classical_baselines import ClassicalBaseline
from quantum_diag.config import ExperimentSpec
from quantum_diag.chemistry_pipeline import build_hamiltonian_bundle
from quantum_diag.skqd_runner import SKQDRunner
from quantum_diag.sqd_runner import SQDRunner
from quantum_diag.test_fixtures import (
    get_geometry_provenance,
    get_h2_geometry,
    get_h2o_geometry,
    get_lih_geometry,
    get_nh3_geometry,
)


def _distance(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a - b))


def _angle_deg(center: np.ndarray, a: np.ndarray, b: np.ndarray) -> float:
    va = a - center
    vb = b - center
    cosv = float(np.dot(va, vb) / (np.linalg.norm(va) * np.linalg.norm(vb)))
    cosv = float(np.clip(cosv, -1.0, 1.0))
    return float(np.degrees(np.arccos(cosv)))


def test_geometry_defaults_match_literature_targets() -> None:
    h2 = get_h2_geometry()
    assert np.isclose(_distance(h2.xyz_coords[0], h2.xyz_coords[1]), 0.7414, atol=1e-4)

    lih = get_lih_geometry()
    assert np.isclose(_distance(lih.xyz_coords[0], lih.xyz_coords[1]), 1.5949131, atol=1e-4)

    h2o = get_h2o_geometry()
    o, h1, h2 = h2o.xyz_coords
    assert np.isclose(_distance(o, h1), 0.95784, atol=1e-4)
    assert np.isclose(_distance(o, h2), 0.95784, atol=1e-4)
    assert np.isclose(_angle_deg(o, h1, h2), 104.5, atol=1e-3)

    nh3 = get_nh3_geometry()
    n, h1, h2, h3 = nh3.xyz_coords
    assert np.isclose(_distance(n, h1), 1.012, atol=1e-4)
    assert np.isclose(_distance(n, h2), 1.012, atol=1e-4)
    assert np.isclose(_distance(n, h3), 1.012, atol=1e-4)
    assert np.isclose(_angle_deg(n, h1, h2), 106.7, atol=1e-3)


def test_geometry_provenance_contains_urls() -> None:
    for molecule in ["H2", "LiH", "H2O", "NH3"]:
        provenance = get_geometry_provenance(molecule)
        assert provenance["url"].startswith("http")
        assert provenance["accessed_utc"] == "2026-03-28"


def test_sqd_no_core_collapse_and_tracks_shots() -> None:
    geometry = get_h2_geometry()
    baseline = ClassicalBaseline()
    reference = baseline.compute_casci_energy(geometry, "sto-3g", geometry.active_space)["energy"]

    spec = ExperimentSpec(
        molecule_name="H2",
        basis_set="sto-3g",
        method="SQD",
        ansatz_type="RealAmplitudes",
        optimizer="COBYLA",
        max_iterations=6,
        shots=256,
        seed=11,
        backend_name="qasm_simulator",
    )

    runner = SQDRunner(spec, reference)
    final_energy, metrics = runner.run(
        geometry,
        num_samples=12,
        max_iterations=3,
        samples_per_batch=8,
        num_batches=1,
    )

    bundle = build_hamiltonian_bundle(
        molecule_name="H2",
        geometry=geometry,
        basis_set="sto-3g",
    )

    assert metrics.shots_used > 0
    assert metrics.diagnostics.get("max_unique_bitstrings", 0) > 1
    assert final_energy < bundle.core_energy - 0.05


def test_skqd_convergence_not_hardcoded_and_tracks_shots() -> None:
    geometry = get_h2_geometry()
    baseline = ClassicalBaseline()
    reference = baseline.compute_casci_energy(geometry, "sto-3g", geometry.active_space)["energy"]

    spec = ExperimentSpec(
        molecule_name="H2",
        basis_set="sto-3g",
        method="SKQD",
        ansatz_type="RealAmplitudes",
        optimizer="COBYLA",
        max_iterations=6,
        shots=256,
        seed=11,
        backend_name="qasm_simulator",
    )

    runner = SKQDRunner(spec, reference)
    _, metrics = runner.run(
        geometry,
        num_samples=12,
        krylov_extension_dim=1,
        max_iterations=1,
        energy_tol=0.0,
    )

    assert metrics.shots_used > 0
    assert metrics.converged is False
    assert metrics.convergence_criterion is not None
