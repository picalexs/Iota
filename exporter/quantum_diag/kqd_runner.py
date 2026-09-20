"""Krylov Quantum Diagonalization (KQD) runner."""

from __future__ import annotations

import time
import numpy as np
from scipy.linalg import eigh

from quantum_diag.config import ExperimentSpec
from quantum_diag.metrics import BenchmarkMetrics
from quantum_diag.reproducibility import SeedManager
from quantum_diag.test_fixtures import MoleculeGeometry
from quantum_diag.time_evolution import build_trotter_time_evolution
from quantum_diag.chemistry_pipeline import build_hamiltonian_bundle


class KQDRunner:
    """Krylov Quantum Diagonalization runner.

    Builds a Krylov subspace of quantum states through repeated time evolution
    of a reference state, projects the Hamiltonian onto this basis, and
    solves the resulting classical eigenvalue problem.
    """

    def __init__(self, experiment_spec: ExperimentSpec, reference_energy: float):
        """Initialize KQD runner.

        Args:
            experiment_spec: ExperimentSpec with configuration.
            reference_energy: Reference (ground truth) energy in Hartree.
        """
        self.experiment_spec = experiment_spec
        self.reference_energy = reference_energy
        self.seed_manager = SeedManager()
        self.seed_manager.set_global_seed(experiment_spec.seed)

    def _build_krylov_basis(
        self,
        hamiltonian: np.ndarray,
        num_qubits: int,
        krylov_dim: int,
        dt: float,
        trotter_steps: int,
    ) -> list[np.ndarray]:
        """Build Krylov basis vectors via repeated time evolution.

        Starts with reference state |00...0> and applies time evolution
        U(dt) repeatedly to generate krylov_dim basis vectors.

        Args:
            hamiltonian: Hamiltonian matrix of shape (n, n).
            num_qubits: Number of qubits.
            krylov_dim: Dimension of Krylov subspace.
            dt: Time step for each evolution.

        Returns:
            List of krylov_dim orthonormal basis vectors, each of shape (n,).
        """
        dim = hamiltonian.shape[0]
        # Reference state |00...0> (first basis state)
        psi_0 = np.zeros(dim, dtype=complex)
        psi_0[0] = 1.0

        krylov_basis = [psi_0]

        # Generate Krylov vectors
        psi_current = psi_0.copy()

        # Build time evolution operator for one step
        u_dt = build_trotter_time_evolution(
            hamiltonian,
            dt,
            trotter_steps=trotter_steps,
        )

        for _ in range(1, krylov_dim):
            # Apply time evolution
            psi_current = u_dt @ psi_current

            # Orthogonalize against previous vectors (Gram-Schmidt)
            for prev_psi in krylov_basis:
                overlap = np.vdot(prev_psi, psi_current)
                psi_current = psi_current - overlap * prev_psi

            # Normalize
            norm = np.linalg.norm(psi_current)
            if norm > 1e-10:
                psi_current = psi_current / norm
                krylov_basis.append(psi_current)
            else:
                # If orthogonalization produces zero, break
                break

        return krylov_basis[:krylov_dim]

    def _project_hamiltonian(
        self, hamiltonian: np.ndarray, basis: list[np.ndarray]
    ) -> np.ndarray:
        """Project Hamiltonian onto Krylov basis.

        Computes H_proj[i, j] = <phi_i | H | phi_j>.

        Args:
            hamiltonian: Hamiltonian matrix of shape (n, n).
            basis: List of orthonormal basis vectors.

        Returns:
            Projected Hamiltonian of shape (len(basis), len(basis)).
        """
        k = len(basis)
        h_proj = np.zeros((k, k), dtype=complex)

        for i in range(k):
            for j in range(k):
                # <phi_i | H | phi_j>
                h_phi_j = hamiltonian @ basis[j]
                h_proj[i, j] = np.vdot(basis[i], h_phi_j)

        return h_proj

    def run(
        self,
        molecule_geometry: MoleculeGeometry,
        krylov_dim: int = 3,
        dt: float = 0.2,
        trotter_steps: int = 1,
    ) -> tuple[float, BenchmarkMetrics]:
        """Run KQD algorithm.

        Args:
            molecule_geometry: MoleculeGeometry specifying the molecule.
            krylov_dim: Dimension of Krylov subspace.
            dt: Time step for Trotter evolution.
            trotter_steps: Number of Trotter steps per evolution.

        Returns:
            Tuple of (ground_state_energy, BenchmarkMetrics).

        Raises:
            ValueError: If krylov_dim < 1.
        """
        if krylov_dim < 1:
            raise ValueError(f"krylov_dim must be >= 1, got {krylov_dim}")

        start_time = time.time()

        bundle = build_hamiltonian_bundle(
            molecule_name=self.experiment_spec.molecule_name,
            geometry=molecule_geometry,
            basis_set=self.experiment_spec.basis_set,
        )
        hamiltonian = bundle.sector_hamiltonian_matrix
        num_qubits = bundle.num_spatial_orbitals

        # Build Krylov basis incrementally and track convergence
        convergence_history = []
        complete_krylov_basis = []

        for k in range(1, krylov_dim + 1):
            # Build Krylov basis up to dimension k
            basis_k = self._build_krylov_basis(
                hamiltonian,
                num_qubits,
                k,
                dt,
                trotter_steps,
            )

            # Project Hamiltonian onto basis_k
            h_projected_k = self._project_hamiltonian(hamiltonian, basis_k)

            # Diagonalize
            eigenvalues_k, _ = eigh(h_projected_k)
            energy_k = float(np.real(eigenvalues_k[0]))

            convergence_history.append(energy_k)
            complete_krylov_basis = basis_k

        wall_time = time.time() - start_time

        ground_energy = convergence_history[-1]

        # Build metrics
        energy_error = abs(ground_energy - self.reference_energy)
        metrics = BenchmarkMetrics(
            final_energy=ground_energy,
            reference_energy=self.reference_energy,
            energy_error=energy_error,
            iterations=krylov_dim,
            wall_time_seconds=wall_time,
            converged=True,
            convergence_history=convergence_history,
            shots_used=0,
            chemistry_pipeline="pyscf+ffsim",
            num_qubits=bundle.num_qubits,
            hamiltonian_dimension=int(hamiltonian.shape[0]),
            active_space=bundle.active_space,
            convergence_criterion="fixed_krylov_dimension_completed",
        )

        return ground_energy, metrics
