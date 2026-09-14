"""Hamiltonian construction helpers."""

from __future__ import annotations

import hashlib
import logging
import os
import struct
import time
from typing import Any

from worker.chemistry.problem_manifest import build_problem_manifest
from worker.chemistry.types import HamiltonianBundle, PreparedMolecule

logger = logging.getLogger(__name__)

_MAX_SAFE_ACTIVE_ORBITALS = 12
_PREFERRED_MAX_ACTIVE_ORBITALS = 8
_MIN_FRONTIER_OCCUPANCY = 0.02
_MAX_FRONTIER_OCCUPANCY = 1.98


def _hamiltonian_sha256(
    *,
    one_body_tensor: Any,
    two_body_tensor: Any,
    constant: float,
    basis: str,
    charge: int,
    multiplicity: int,
    active_space: tuple[int, int],
) -> str:
    """Return a stable digest for the operator and its chemistry definition."""
    import numpy as np

    digest = hashlib.sha256(b"licenta-hamiltonian:v1\0")
    definition = (
        basis,
        int(charge),
        int(multiplicity),
        int(active_space[0]),
        int(active_space[1]),
    )
    digest.update(repr(definition).encode("utf-8"))
    digest.update(b"\0")
    digest.update(struct.pack("<d", float(constant)))
    for label, tensor in (("one_body", one_body_tensor), ("two_body", two_body_tensor)):
        array = np.asarray(tensor, dtype="<f8", order="C")
        digest.update(label.encode("ascii"))
        digest.update(repr(tuple(int(value) for value in array.shape)).encode("ascii"))
        digest.update(b"\0")
        digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


def _source_commit() -> str | None:
    """Read an explicitly injected source revision without guessing from a version label."""
    for variable in ("SOURCE_COMMIT", "GIT_COMMIT"):
        value = os.environ.get(variable)
        if value:
            return value
    return None


def _resolve_active_space(
    molecule: PreparedMolecule,
    *,
    total_electrons: int,
    total_orbitals: int,
) -> tuple[int, int]:
    """Resolve and validate the active space against molecule-level capacities."""
    if molecule.active_space is None:
        return total_electrons, total_orbitals

    n_electrons, n_orbitals = molecule.active_space
    if n_electrons > total_electrons:
        raise ValueError("active_space.n_electrons exceeds total molecule electrons")
    if n_orbitals > total_orbitals:
        raise ValueError("active_space.n_orbitals exceeds total molecular orbitals")
    inactive_electrons = total_electrons - n_electrons
    if inactive_electrons % 2 != 0:
        raise ValueError("active_space.n_electrons leaves an odd number of inactive electrons")
    n_core_orbitals = inactive_electrons // 2
    if n_core_orbitals + n_orbitals > total_orbitals:
        raise ValueError(
            "active_space.n_orbitals plus frozen core orbitals exceeds total molecular orbitals"
        )
    return int(n_electrons), int(n_orbitals)


def _select_frontier_active_space(
    mo_occ: Any,
    total_electrons: int,
    total_orbitals: int,
) -> tuple[int, int]:
    """Select a frontier active space from RHF natural orbital occupancies.

    Finds orbitals near the HOMO-LUMO gap (occupancy between
    _MIN_FRONTIER_OCCUPANCY and _MAX_FRONTIER_OCCUPANCY) and caps at
    _MAX_SAFE_ACTIVE_ORBITALS.
    """
    import numpy as np

    _ = total_orbitals
    occupancies = np.asarray(mo_occ, dtype=float)
    frontier_indices = [
        i
        for i, occ in enumerate(occupancies)
        if _MIN_FRONTIER_OCCUPANCY <= occ <= _MAX_FRONTIER_OCCUPANCY
    ]

    if not frontier_indices:
        n_occupied = sum(1 for occ in occupancies if occ > 1.0)
        n_virtual = sum(1 for occ in occupancies if occ < 0.5)
        homo_count = min(n_occupied, _PREFERRED_MAX_ACTIVE_ORBITALS // 2)
        lumo_count = min(n_virtual, _PREFERRED_MAX_ACTIVE_ORBITALS // 2)
        first_lumo = n_occupied
        frontier_indices = list(range(first_lumo - homo_count, first_lumo + lumo_count))

    n_active_orbitals = min(len(frontier_indices), _MAX_SAFE_ACTIVE_ORBITALS)
    frontier_indices = frontier_indices[:n_active_orbitals]

    n_active_electrons = int(sum(round(occupancies[i]) for i in frontier_indices))
    n_active_electrons = min(n_active_electrons, total_electrons)
    if n_active_electrons % 2 != 0:
        n_active_electrons = max(2, n_active_electrons - 1)
    n_active_electrons = min(n_active_electrons, 2 * n_active_orbitals)

    return n_active_electrons, n_active_orbitals


def _resolve_build_active_space(
    molecule: PreparedMolecule,
    mf: Any,
    *,
    preflight_active_space: tuple[int, int] | None,
    total_electrons: int,
    total_orbitals: int,
) -> tuple[int, int, bool, int | None, int | None]:
    """Resolve explicit or frontier-reduced active-space dimensions."""
    if molecule.active_space is not None or total_orbitals <= _MAX_SAFE_ACTIVE_ORBITALS:
        active_space = preflight_active_space or _resolve_active_space(
            molecule,
            total_electrons=total_electrons,
            total_orbitals=total_orbitals,
        )
        return (*active_space, False, None, None)

    logger.warning(
        "Molecule has %d orbitals (> %d safe limit) with no explicit active space; "
        "auto-selecting frontier active space via RHF orbital occupancies.",
        total_orbitals,
        _MAX_SAFE_ACTIVE_ORBITALS,
    )
    mo_occ = getattr(mf, "mo_occ", None)
    if mo_occ is not None:
        n_electrons, n_orbitals = _select_frontier_active_space(
            mo_occ, total_electrons, total_orbitals
        )
    else:
        n_electrons = min(total_electrons, _PREFERRED_MAX_ACTIVE_ORBITALS)
        n_orbitals = _PREFERRED_MAX_ACTIVE_ORBITALS
        if n_electrons % 2 != 0:
            n_electrons = max(2, n_electrons - 1)
    logger.info(
        "Active space auto-reduced: electrons=%d orbitals=%d (from %d electrons / %d orbitals)",
        n_electrons,
        n_orbitals,
        total_electrons,
        total_orbitals,
    )
    return n_electrons, n_orbitals, True, total_electrons, total_orbitals


def build_qubit_hamiltonian(molecule: PreparedMolecule) -> HamiltonianBundle:
    """Build a qubit Hamiltonian bundle via PySCF -> ffsim for a molecule."""
    try:
        import ffsim
        import numpy as np
        from pyscf import ao2mo, gto, mcscf, scf
    except ImportError as exc:  # pragma: no cover - exercised via importorskip tests
        raise RuntimeError("PySCF and ffsim must be installed to build Hamiltonians") from exc

    if molecule.multiplicity != 1:
        raise ValueError("Open-shell molecules are not supported in the current RHF rollout")

    t_start = time.monotonic()

    mol = gto.M(
        atom=molecule.atom_spec,
        basis=molecule.basis,
        charge=molecule.charge,
        spin=molecule.multiplicity - 1,
        verbose=0,
    )
    total_electrons = int(mol.nelectron)
    total_orbitals_from_basis = int(mol.nao_nr())
    preflight_active_space = (
        _resolve_active_space(
            molecule,
            total_electrons=total_electrons,
            total_orbitals=total_orbitals_from_basis,
        )
        if molecule.active_space is not None
        else None
    )

    t_scf = time.monotonic()
    mf = scf.RHF(mol)
    mf.verbose = 0
    mf.kernel()
    scf_elapsed = time.monotonic() - t_scf
    if not mf.converged:
        raise RuntimeError("RHF SCF did not converge for molecule input")

    logger.info(
        "RHF SCF converged for %d-atom molecule (basis=%s, charge=%d, nelectron=%d) "
        "hf_energy=%.6f Ha elapsed=%.3fs",
        len(molecule.atom_spec),
        molecule.basis,
        molecule.charge,
        int(mol.nelectron),
        float(mf.e_tot),
        scf_elapsed,
    )

    mo_coeff = getattr(mf, "mo_coeff", None)
    if mo_coeff is None:
        raise RuntimeError("RHF SCF did not produce molecular orbital coefficients")

    total_orbitals = int(mo_coeff.shape[1])
    (
        n_electrons,
        n_orbitals,
        active_space_auto_reduced,
        original_num_electrons,
        original_num_orbitals,
    ) = _resolve_build_active_space(
        molecule,
        mf,
        preflight_active_space=preflight_active_space,
        total_electrons=total_electrons,
        total_orbitals=total_orbitals,
    )

    logger.info(
        "Active space: %d electrons / %d orbitals (%d qubits)",
        n_electrons,
        n_orbitals,
        2 * n_orbitals,
    )

    t_casci = time.monotonic()
    mc: Any = mcscf.CASCI(mf, n_orbitals, n_electrons)
    mc.verbose = 0
    h1eff, e_core = mc.get_h1eff()
    h2eff = ao2mo.restore(1, mc.get_h2eff(), n_orbitals)
    mc.kernel()
    casci_elapsed = time.monotonic() - t_casci
    logger.info(
        "CASCI completed casci_energy=%.6f Ha elapsed=%.3fs",
        float(mc.e_tot),
        casci_elapsed,
    )

    one_body_tensor = np.asarray(h1eff, dtype=float)
    two_body_tensor = np.asarray(h2eff, dtype=float)
    constant = float(e_core)

    t_pauli = time.monotonic()
    molecular_hamiltonian = ffsim.MolecularHamiltonian(
        one_body_tensor=one_body_tensor,
        two_body_tensor=two_body_tensor,
        constant=constant,
    )

    fermion_operator = ffsim.fermion_operator(molecular_hamiltonian)
    pauli_hamiltonian = ffsim.qiskit.jordan_wigner(
        fermion_operator,
        norb=n_orbitals,
        tol=1e-12,
    ).simplify(atol=1e-12)
    pauli_elapsed = time.monotonic() - t_pauli
    logger.info(
        "Pauli Hamiltonian built: %d terms elapsed=%.3fs",
        len(pauli_hamiltonian),
        pauli_elapsed,
    )

    total_elapsed = time.monotonic() - t_start
    logger.info(
        "Hamiltonian pipeline complete: total_elapsed=%.3fs (scf=%.3fs casci=%.3fs pauli=%.3fs)",
        total_elapsed,
        scf_elapsed,
        casci_elapsed,
        pauli_elapsed,
    )

    hamiltonian_sha256 = _hamiltonian_sha256(
        one_body_tensor=one_body_tensor,
        two_body_tensor=two_body_tensor,
        constant=constant,
        basis=molecule.basis,
        charge=molecule.charge,
        multiplicity=molecule.multiplicity,
        active_space=(n_electrons, n_orbitals),
    )
    problem_manifest = build_problem_manifest(
        molecule=molecule,
        resolved_active_space=(n_electrons, n_orbitals),
        num_spatial_orbitals=n_orbitals,
        num_qubits=2 * n_orbitals,
        num_electrons_alpha=n_electrons // 2,
        num_electrons_beta=n_electrons // 2,
        constant=constant,
        nuclear_repulsion=float(mol.energy_nuc()),
        hamiltonian_sha256=hamiltonian_sha256,
        total_electrons=total_electrons,
        total_molecular_orbitals=total_orbitals,
        active_space_auto_reduced=active_space_auto_reduced,
        original_num_electrons=original_num_electrons,
        original_num_orbitals=original_num_orbitals,
    )

    metadata: dict[str, Any] = {
        "pipeline": "pyscf+ffsim",
        "nuclear_repulsion": float(mol.energy_nuc()),
        "hf_energy": float(mf.e_tot),
        "casci_energy": float(mc.e_tot),
        "active_space": [n_electrons, n_orbitals],
        "active_space_auto_reduced": active_space_auto_reduced,
        "total_electrons": total_electrons,
        "total_molecular_orbitals": total_orbitals,
        "active_space_preflight": "passed",
        "active_space_capacity": {
            "inactive_electrons": total_electrons - n_electrons,
            "frozen_core_orbitals": (total_electrons - n_electrons) // 2,
            "total_molecular_orbitals": total_orbitals,
            "active_orbitals": n_orbitals,
        },
        "reference_method": "CASCI",
        "reference_backend_target": "local_classical",
        "reference_solver_path": "pyscf+ffsim",
        "reference_basis": molecule.basis,
        "reference_active_space": [n_electrons, n_orbitals],
        "reference_precision": None,
        "reference_precision_policy": "deterministic_float64",
        "reference_precision_not_applicable_reason": "classical_reference_not_sampled",
        "source_commit": _source_commit(),
        "hamiltonian_sha256": hamiltonian_sha256,
        "problem_manifest": problem_manifest,
        "problem_manifest_sha256": problem_manifest["manifest_sha256"],
        "reference_validity_status": "valid",
    }
    if active_space_auto_reduced:
        metadata["original_num_orbitals"] = original_num_orbitals
        metadata["original_num_electrons"] = original_num_electrons

    n_alpha = n_electrons // 2
    n_beta = n_electrons // 2

    return HamiltonianBundle(
        num_spatial_orbitals=n_orbitals,
        num_qubits=2 * n_orbitals,
        num_electrons_alpha=n_alpha,
        num_electrons_beta=n_beta,
        one_body_tensor=one_body_tensor,
        two_body_tensor=two_body_tensor,
        constant=constant,
        pauli_hamiltonian=pauli_hamiltonian,
        metadata=metadata,
    )
