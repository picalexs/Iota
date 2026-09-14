"""Focused tests for execute_run Hamiltonian bundle caching."""

from __future__ import annotations

import importlib

import numpy as np
from qiskit.quantum_info import SparsePauliOp

from worker.chemistry.types import ChemistryInput, HamiltonianBundle, PreparedMolecule

execute_run_module = importlib.import_module("worker.jobs.execute_run")


def _chemistry_input(*, basis: str = "sto-3g") -> ChemistryInput:
    return ChemistryInput(
        atoms=[
            {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.0},
            {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.7414},
        ],
        charge=0,
        multiplicity=1,
        basis=basis,
        active_space=(2, 2),
    )


def _bundle(tag: str) -> HamiltonianBundle:
    return HamiltonianBundle(
        num_spatial_orbitals=2,
        num_qubits=4,
        num_electrons_alpha=1,
        num_electrons_beta=1,
        one_body_tensor=np.zeros((2, 2), dtype=float),
        two_body_tensor=np.zeros((2, 2, 2, 2), dtype=float),
        constant=0.0,
        pauli_hamiltonian=SparsePauliOp.from_list([("ZZ", 1.0)]),
        metadata={"tag": tag},
    )


def _prepared_molecule(*, basis: str = "sto-3g") -> PreparedMolecule:
    return PreparedMolecule(
        atom_spec=[("H", (0.0, 0.0, 0.0)), ("H", (0.0, 0.0, 0.7414))],
        basis=basis,
        charge=0,
        multiplicity=1,
        active_space=(2, 2),
    )


def test_build_hamiltonian_bundle_reuses_cached_artifacts(monkeypatch) -> None:
    execute_run_module.clear_hamiltonian_bundle_cache()

    monkeypatch.setattr(execute_run_module, "build_molecule", lambda _: _prepared_molecule())

    call_count = 0

    def _build_bundle(_prepared: PreparedMolecule) -> HamiltonianBundle:
        nonlocal call_count
        call_count += 1
        return _bundle("cached")

    monkeypatch.setattr(execute_run_module, "build_qubit_hamiltonian", _build_bundle)

    chemistry = _chemistry_input()
    first = execute_run_module._build_hamiltonian_bundle(chemistry_input=chemistry)
    second = execute_run_module._build_hamiltonian_bundle(chemistry_input=chemistry)

    assert call_count == 1
    assert first.metadata["tag"] == "cached"
    assert second.metadata["tag"] == "cached"


def test_build_hamiltonian_bundle_cache_key_tracks_basis_override(monkeypatch) -> None:
    execute_run_module.clear_hamiltonian_bundle_cache()

    monkeypatch.setattr(
        execute_run_module,
        "build_molecule",
        lambda ci: _prepared_molecule(basis=ci.basis),
    )

    seen_bases: list[str] = []

    def _build_bundle(prepared: PreparedMolecule) -> HamiltonianBundle:
        seen_bases.append(prepared.basis)
        return _bundle(prepared.basis)

    monkeypatch.setattr(execute_run_module, "build_qubit_hamiltonian", _build_bundle)

    sto = execute_run_module._build_hamiltonian_bundle(
        chemistry_input=_chemistry_input(basis="sto-3g"),
    )
    g631 = execute_run_module._build_hamiltonian_bundle(
        chemistry_input=_chemistry_input(basis="6-31g"),
    )

    assert seen_bases == ["sto-3g", "6-31g"]
    assert sto.metadata["tag"] == "sto-3g"
    assert g631.metadata["tag"] == "6-31g"
