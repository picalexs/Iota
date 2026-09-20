"""Shared chemistry pipeline for Hamiltonian construction.

This module is the single source of truth for Hamiltonian generation in the
research benchmark harness. It builds molecular Hamiltonians from
MoleculeGeometry via PySCF and ffsim, then exposes both qubit-operator and
matrix representations for downstream runners.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from typing import Any

import numpy as np
import ffsim
from pyscf import ao2mo, gto, mcscf, scf
from qiskit.quantum_info import SparsePauliOp

from quantum_diag.test_fixtures import MoleculeGeometry


@dataclass(frozen=True)
class HamiltonianBundle:
    """Hamiltonian artifacts produced by the shared chemistry pipeline."""

    molecule_name: str
    basis_set: str
    active_space: tuple[int, int]
    num_spatial_orbitals: int
    num_qubits: int
    num_electrons_alpha: int
    num_electrons_beta: int
    hf_energy: float
    casci_energy: float
    core_energy: float
    one_body_tensor: np.ndarray
    two_body_tensor: np.ndarray
    pauli_hamiltonian: SparsePauliOp
    qubit_hamiltonian_matrix: np.ndarray
    sector_hamiltonian_matrix: np.ndarray
    metadata: dict[str, Any]


def _package_version(name: str) -> str | None:
    """Get installed package version if available."""
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def _geometry_key(geometry: MoleculeGeometry) -> tuple[tuple[str, tuple[float, float, float]], ...]:
    """Convert geometry to a hashable key with stable float precision."""
    atoms: list[tuple[str, tuple[float, float, float]]] = []
    for symbol, xyz in zip(geometry.symbols, geometry.xyz_coords):
        atoms.append(
            (
                str(symbol),
                (
                    round(float(xyz[0]), 10),
                    round(float(xyz[1]), 10),
                    round(float(xyz[2]), 10),
                ),
            )
        )
    return tuple(atoms)


def build_hamiltonian_bundle(
    *,
    molecule_name: str,
    geometry: MoleculeGeometry,
    basis_set: str,
) -> HamiltonianBundle:
    """Build a full Hamiltonian bundle from geometry using PySCF + ffsim.

    Args:
        molecule_name: Logical molecule name used by benchmark orchestration.
        geometry: Molecule geometry and active-space definition.
        basis_set: PySCF basis set name.

    Returns:
        HamiltonianBundle containing qubit and sector Hamiltonians.

    Raises:
        ValueError: If active space is missing or invalid.
        RuntimeError: If RHF or CASCI calculations fail.
    """
    if geometry.active_space is None:
        raise ValueError(
            "Active space is required for chemistry-fidelity Hamiltonian "
            "construction but is missing from MoleculeGeometry."
        )

    n_electrons, n_orbitals = geometry.active_space
    if n_electrons <= 0 or n_orbitals <= 0:
        raise ValueError(
            "Active space values must be positive: "
            f"n_electrons={n_electrons}, n_orbitals={n_orbitals}."
        )
    if n_electrons % 2 != 0:
        raise ValueError(
            "Only closed-shell singlet active spaces are currently supported "
            f"(got n_electrons={n_electrons})."
        )

    atoms_key = _geometry_key(geometry)
    return _build_hamiltonian_bundle_cached(
        molecule_name=molecule_name,
        basis_set=basis_set,
        active_space=(int(n_electrons), int(n_orbitals)),
        atoms_key=atoms_key,
    )


@lru_cache(maxsize=32)
def _build_hamiltonian_bundle_cached(
    *,
    molecule_name: str,
    basis_set: str,
    active_space: tuple[int, int],
    atoms_key: tuple[tuple[str, tuple[float, float, float]], ...],
) -> HamiltonianBundle:
    """Internal cached chemistry builder keyed by molecule geometry and basis."""
    n_electrons, n_orbitals = active_space
    atom_spec = [(sym, xyz) for sym, xyz in atoms_key]

    mol = gto.M(
        atom=atom_spec,
        basis=basis_set,
        charge=0,
        spin=0,
        verbose=0,
    )

    mf = scf.RHF(mol)
    mf.verbose = 0
    mf.kernel()
    if not mf.converged:
        raise RuntimeError(f"RHF SCF did not converge for molecule={molecule_name}")

    mc = mcscf.CASCI(mf, n_orbitals, n_electrons)
    mc.verbose = 0

    h1eff, e_core = mc.get_h1eff()
    h2eff = ao2mo.restore(1, mc.get_h2eff(), n_orbitals)

    try:
        mc.kernel()
        casci_energy = float(mc.e_tot)
    except Exception as exc:
        raise RuntimeError(
            f"CASCI failed for molecule={molecule_name}, active_space={active_space}: {exc}"
        ) from exc

    one_body_tensor = np.asarray(h1eff, dtype=float)
    two_body_tensor = np.asarray(h2eff, dtype=float)
    core_energy = float(e_core)

    molecular_hamiltonian = ffsim.MolecularHamiltonian(
        one_body_tensor=one_body_tensor,
        two_body_tensor=two_body_tensor,
        constant=core_energy,
    )

    fermion_operator = ffsim.fermion_operator(molecular_hamiltonian)
    pauli_hamiltonian = ffsim.qiskit.jordan_wigner(
        fermion_operator,
        norb=n_orbitals,
        tol=1e-12,
    ).simplify(atol=1e-12)

    qubit_hamiltonian_matrix = np.asarray(pauli_hamiltonian.to_matrix(), dtype=complex)

    n_alpha = n_electrons // 2
    n_beta = n_electrons // 2
    sector_linear_operator = ffsim.linear_operator(
        molecular_hamiltonian,
        norb=n_orbitals,
        nelec=(n_alpha, n_beta),
    )
    sector_hamiltonian_matrix = np.asarray(
        sector_linear_operator.matmat(np.eye(sector_linear_operator.shape[1])),
        dtype=complex,
    )

    metadata: dict[str, Any] = {
        "pipeline": "pyscf+ffsim",
        "pyscf_version": _package_version("pyscf"),
        "ffsim_version": _package_version("ffsim"),
        "qiskit_addon_sqd_version": _package_version("qiskit-addon-sqd"),
        "nuclear_repulsion": float(mol.energy_nuc()),
        "num_atomic_orbitals": int(mol.nao),
    }

    return HamiltonianBundle(
        molecule_name=molecule_name,
        basis_set=basis_set,
        active_space=active_space,
        num_spatial_orbitals=n_orbitals,
        num_qubits=2 * n_orbitals,
        num_electrons_alpha=n_alpha,
        num_electrons_beta=n_beta,
        hf_energy=float(mf.e_tot),
        casci_energy=casci_energy,
        core_energy=core_energy,
        one_body_tensor=one_body_tensor,
        two_body_tensor=two_body_tensor,
        pauli_hamiltonian=pauli_hamiltonian,
        qubit_hamiltonian_matrix=qubit_hamiltonian_matrix,
        sector_hamiltonian_matrix=sector_hamiltonian_matrix,
        metadata=metadata,
    )
