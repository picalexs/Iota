"""Quantum Filter Diagonalization (QFD) runner."""

from __future__ import annotations

import time
import numpy as np
from scipy.linalg import eigh

from quantum_diag.config import ExperimentSpec
from quantum_diag.metrics import BenchmarkMetrics
from quantum_diag.reproducibility import SeedManager
from quantum_diag.test_fixtures import MoleculeGeometry
from quantum_diag.time_evolution import exact_time_evolution
from quantum_diag.overlap_measurement import estimate_overlap
from quantum_diag.chemistry_pipeline import build_hamiltonian_bundle


class QFDRunner:
    """Quantum Filter Diagonalization (QFD) runner.

    Builds a filter/correlation matrix from time-evolved reference state overlaps,
    constructs a Hermitian surrogate Hamiltonian, and returns the lowest eigenvalue
    as an energy estimate.
    """

    def __init__(self, experiment_spec: ExperimentSpec, reference_energy: float):
        """Initialize QFD runner.

        Args:
            experiment_spec: ExperimentSpec with configuration.
            reference_energy: Reference (ground truth) energy in Hartree.
        """
        self.experiment_spec = experiment_spec
        self.reference_energy = reference_energy
        self.seed_manager = SeedManager()
        self.seed_manager.set_global_seed(experiment_spec.seed)

    def _sample_time_points(self, max_time: float, num_points: int) -> np.ndarray:
        """Sample time points for filter construction.

        Generates num_points equally spaced time values from 0 to max_time.

        Args:
            max_time: Maximum time value.
            num_points: Number of time points to generate.

        Returns:
            Array of shape (num_points,) with time values.
        """
        return np.linspace(0, max_time, num_points)

    def _build_filter_matrix(
        self, hamiltonian: np.ndarray, time_points: np.ndarray
    ) -> np.ndarray:
        """Build filter/correlation matrix from time-evolved overlaps.

        For each time point t_j, compute |psi(t_j)> = exp(-i H t_j) |psi_0>
        where |psi_0> is the reference state |00...0>.
        Then filter_matrix[i, j] = <psi(t_i) | psi(t_j)>.

        Args:
            hamiltonian: Hamiltonian matrix of shape (n, n).
            time_points: Array of time points for evolution.

        Returns:
            Hermitian filter matrix of shape (len(time_points), len(time_points)).
        """
        num_points = len(time_points)
        dim = hamiltonian.shape[0]

        # Reference state |00...0>
        psi_0 = np.zeros(dim, dtype=complex)
        psi_0[0] = 1.0

        # Evolve reference state at each time point
        evolved_states = []
        for t in time_points:
            u_t = exact_time_evolution(hamiltonian, t)
            psi_t = u_t @ psi_0
            evolved_states.append(psi_t)

        # Build correlation matrix
        filter_mat = np.zeros((num_points, num_points), dtype=complex)
        for i in range(num_points):
            for j in range(num_points):
                filter_mat[i, j] = estimate_overlap(evolved_states[i], evolved_states[j])

        return filter_mat

    def _build_projected_hamiltonian(
        self,
        hamiltonian: np.ndarray,
        time_points: np.ndarray,
    ) -> np.ndarray:
        """Build projected Hamiltonian matrix in the time-evolved basis.

        Computes H_proj[i, j] = <psi(t_i) | H | psi(t_j)>.
        """
        num_points = len(time_points)
        dim = hamiltonian.shape[0]

        psi_0 = np.zeros(dim, dtype=complex)
        psi_0[0] = 1.0

        evolved_states: list[np.ndarray] = []
        for t in time_points:
            u_t = exact_time_evolution(hamiltonian, t)
            evolved_states.append(u_t @ psi_0)

        h_proj = np.zeros((num_points, num_points), dtype=complex)
        for i in range(num_points):
            for j in range(num_points):
                h_proj[i, j] = np.vdot(evolved_states[i], hamiltonian @ evolved_states[j])

        return h_proj

    def run(
        self,
        molecule_geometry: MoleculeGeometry,
        max_time: float = 1.0,
        num_points: int = 6,
    ) -> tuple[float, BenchmarkMetrics]:
        """Run QFD algorithm.

        Args:
            molecule_geometry: MoleculeGeometry specifying the molecule.
            max_time: Maximum time for filter construction.
            num_points: Number of time points to sample.

        Returns:
            Tuple of (ground_state_energy_estimate, BenchmarkMetrics).

        Raises:
            ValueError: If num_points < 2.
        """
        if num_points < 2:
            raise ValueError(f"num_points must be >= 2, got {num_points}")

        start_time = time.time()

        bundle = build_hamiltonian_bundle(
            molecule_name=self.experiment_spec.molecule_name,
            geometry=molecule_geometry,
            basis_set=self.experiment_spec.basis_set,
        )
        hamiltonian = bundle.sector_hamiltonian_matrix

        # Sample time points
        time_points = self._sample_time_points(max_time, num_points)

        # Build overlap/filter matrix S and projected Hamiltonian H in sampled basis.
        filter_matrix = self._build_filter_matrix(hamiltonian, time_points)
        projected_hamiltonian = self._build_projected_hamiltonian(
            hamiltonian,
            time_points,
        )

        # Regularize overlap matrix for numerical stability in generalized EVP.
        s_reg = filter_matrix + 1e-8 * np.eye(filter_matrix.shape[0], dtype=complex)

        # Solve generalized eigenproblem H c = E S c.
        eigenvalues, _ = eigh(projected_hamiltonian, s_reg)
        ground_estimate = float(np.real(np.min(eigenvalues)))

        wall_time = time.time() - start_time

        # Convergence history represented as best estimate from full sampled basis.
        convergence_history = [ground_estimate]

        # Build metrics
        energy_error = abs(ground_estimate - self.reference_energy)
        metrics = BenchmarkMetrics(
            final_energy=ground_estimate,
            reference_energy=self.reference_energy,
            energy_error=energy_error,
            iterations=num_points,
            wall_time_seconds=wall_time,
            converged=True,
            convergence_history=convergence_history,
            shots_used=0,
            chemistry_pipeline="pyscf+ffsim",
            num_qubits=bundle.num_qubits,
            hamiltonian_dimension=int(hamiltonian.shape[0]),
            active_space=bundle.active_space,
            convergence_criterion="fixed_time_grid_completed",
        )

        return ground_estimate, metrics
