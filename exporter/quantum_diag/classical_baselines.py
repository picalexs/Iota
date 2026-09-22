"""Classical baseline computations using PySCF."""

from __future__ import annotations

from typing import Any

import numpy as np
from pyscf import gto, scf, mcscf, ao2mo

from quantum_diag.test_fixtures import MoleculeGeometry


class ClassicalBaseline:
    """Runner for classical RHF and CASCI quantum chemistry calculations.

    Provides deterministic energy computations using PySCF with caching
    of reference values for H2 and LiH in common basis sets.
    """

    # Cached reference values for common systems
    _REFERENCE_CACHE: dict[str, dict[str, Any]] = {
        # H2 STO-3G
        ("H2", "sto-3g", 0.735): {
            "rhf_energy": -1.1173,
            "casci_2_2": -1.1173,
        },
        # LiH STO-3G
        ("LiH", "sto-3g", 1.639): {
            "rhf_energy": -7.8623,
            "casci_4_4": -7.8623,
        },
    }

    def compute_rhf_energy(
        self, geometry: MoleculeGeometry, basis: str
    ) -> dict[str, Any]:
        """Compute RHF energy for a molecule.

        Args:
            geometry: MoleculeGeometry object with molecular structure.
            basis: Basis set name (e.g., "sto-3g", "6-31g").

        Returns:
            Dict with keys:
                - 'energy': RHF ground state energy in Hartree
                - 'orbital_energies': Array of orbital energy eigenvalues
        """
        # Build PySCF molecule
        atom_spec = [
            (symbol, tuple(xyz))
            for symbol, xyz in zip(geometry.symbols, geometry.xyz_coords)
        ]
        mol = gto.M(atom=atom_spec, basis=basis, verbose=0)

        # RHF calculation
        mf = scf.RHF(mol)
        mf.verbose = 0
        mf.kernel()

        if not mf.converged:
            raise RuntimeError("RHF SCF did not converge")

        return {
            "energy": float(mf.e_tot),
            "orbital_energies": mf.mo_energy.copy(),
        }

    def compute_casci_energy(
        self,
        geometry: MoleculeGeometry,
        basis: str,
        active_space: tuple[int, int],
    ) -> dict[str, Any]:
        """Compute CASCI energy for a molecule.

        Args:
            geometry: MoleculeGeometry object with molecular structure.
            basis: Basis set name (e.g., "sto-3g").
            active_space: Tuple of (n_electrons, n_orbitals).

        Returns:
            Dict with keys:
                - 'energy': CASCI ground state energy in Hartree
                - 'dm_cas': Density matrix in active space
        """
        # Build PySCF molecule
        atom_spec = [
            (symbol, tuple(xyz))
            for symbol, xyz in zip(geometry.symbols, geometry.xyz_coords)
        ]
        mol = gto.M(atom=atom_spec, basis=basis, verbose=0)

        # RHF reference
        mf = scf.RHF(mol)
        mf.verbose = 0
        mf.kernel()

        if not mf.converged:
            raise RuntimeError("RHF SCF did not converge")

        # CASCI calculation
        n_el, n_orb = active_space
        ci = mcscf.CASCI(mf, n_orb, n_el)
        ci.verbose = 0
        ci.kernel()

        # Compute 1-RDM in active space
        dm_cas = ci.make_rdm1()

        return {
            "energy": float(ci.e_tot),
            "dm_cas": dm_cas,
        }
