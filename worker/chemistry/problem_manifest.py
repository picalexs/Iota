"""Canonical problem-manifest construction for chemistry runs."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
from math import comb
from typing import Any

from worker.chemistry.types import PreparedMolecule

_MANIFEST_SCHEMA = "licenta-problem-manifest:v1"


def _package_version(package_name: str) -> str | None:
    """Return an installed dependency version without making it mandatory."""
    try:
        return importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _canonical_hash(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def build_problem_manifest(
    *,
    molecule: PreparedMolecule,
    resolved_active_space: tuple[int, int],
    **manifest_values: Any,
) -> dict[str, Any]:
    """Build one JSON-safe manifest that identifies the chemistry problem."""
    num_spatial_orbitals = int(manifest_values["num_spatial_orbitals"])
    num_qubits = int(manifest_values["num_qubits"])
    num_electrons_alpha = int(manifest_values["num_electrons_alpha"])
    num_electrons_beta = int(manifest_values["num_electrons_beta"])
    constant = float(manifest_values["constant"])
    nuclear_repulsion = float(manifest_values["nuclear_repulsion"])
    hamiltonian_sha256 = str(manifest_values["hamiltonian_sha256"])
    total_electrons = int(manifest_values["total_electrons"])
    total_molecular_orbitals = int(manifest_values["total_molecular_orbitals"])
    active_space_auto_reduced = bool(manifest_values["active_space_auto_reduced"])
    original_num_electrons = manifest_values.get("original_num_electrons")
    original_num_orbitals = manifest_values.get("original_num_orbitals")
    active_electrons, active_orbitals = resolved_active_space
    frozen_core_orbitals = (total_electrons - active_electrons) // 2
    payload: dict[str, Any] = {
        "schema": _MANIFEST_SCHEMA,
        "molecule": {
            "atoms": [
                {"symbol": symbol, "coordinates": [float(value) for value in coordinates]}
                for symbol, coordinates in molecule.atom_spec
            ],
            "basis": molecule.basis,
            "charge": molecule.charge,
            "multiplicity": molecule.multiplicity,
        },
        "active_space": {
            "requested": (
                [int(value) for value in molecule.active_space]
                if molecule.active_space is not None
                else None
            ),
            "resolved": [int(active_electrons), int(active_orbitals)],
            "auto_reduced": bool(active_space_auto_reduced),
            "active_orbital_indices": list(range(int(num_spatial_orbitals))),
            "frozen_core_orbitals": int(frozen_core_orbitals),
            "total_electrons": int(total_electrons),
            "total_molecular_orbitals": int(total_molecular_orbitals),
            "original_electrons": (
                int(original_num_electrons) if original_num_electrons is not None else None
            ),
            "original_orbitals": (
                int(original_num_orbitals) if original_num_orbitals is not None else None
            ),
        },
        "sector": {
            "num_spatial_orbitals": int(num_spatial_orbitals),
            "num_qubits": int(num_qubits),
            "num_electrons_alpha": int(num_electrons_alpha),
            "num_electrons_beta": int(num_electrons_beta),
            "target_spin_multiplicity": int(molecule.multiplicity),
            "target_spin_projection": 0.0,
            "full_target_sector_dimension": int(
                comb(num_spatial_orbitals, num_electrons_alpha)
                * comb(num_spatial_orbitals, num_electrons_beta)
            ),
        },
        "fermion_to_qubit": {
            "mapping": "jordan_wigner",
            "qubit_order": [
                *[f"alpha_{index}" for index in range(num_spatial_orbitals)],
                *[f"beta_{index}" for index in range(num_spatial_orbitals)],
            ],
            "measurement_bitstring_order": "[beta...][alpha...]",
        },
        "hamiltonian": {
            "sha256": hamiltonian_sha256,
            "one_body_shape": [int(num_spatial_orbitals), int(num_spatial_orbitals)],
            "two_body_shape": [
                int(num_spatial_orbitals),
                int(num_spatial_orbitals),
                int(num_spatial_orbitals),
                int(num_spatial_orbitals),
            ],
            "constant_term": float(constant),
            "nuclear_repulsion": float(nuclear_repulsion),
        },
        "numerical_policy": {
            "coefficient_dtype": "float64",
            "pauli_simplify_atol": 1e-12,
            "finite_value_policy": "reject_non_finite",
        },
        "dependencies": {
            package: _package_version(package)
            for package in (
                "ffsim",
                "pyscf",
                "qiskit",
                "qiskit-aer",
                "qiskit-addon-sqd",
            )
        },
    }
    return {**payload, "manifest_sha256": _canonical_hash(payload)}


def validate_problem_manifest(manifest: dict[str, Any]) -> bool:
    """Check that a manifest hash matches its immutable payload."""
    expected_hash = manifest.get("manifest_sha256")
    if not isinstance(expected_hash, str) or len(expected_hash) != 64:
        return False
    payload = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    return _canonical_hash(payload) == expected_hash


__all__ = ["build_problem_manifest", "validate_problem_manifest"]
