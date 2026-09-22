"""Matrix-free Hamiltonian actions for fixed electron sectors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.sparse.linalg import expm_multiply

from worker.chemistry.sector_basis import (
    ElectronSector,
    resolve_sector_metadata,
    sector_dimension,
)
from worker.chemistry.time_evolution import is_zero_time


def can_build_hamiltonian_action(hamiltonian: object) -> bool:
    """Return whether a Hamiltonian bundle has the tensors needed for ffsim matvecs."""
    required = (
        "one_body_tensor",
        "two_body_tensor",
        "num_spatial_orbitals",
        "num_electrons_alpha",
        "num_electrons_beta",
    )
    return all(hasattr(hamiltonian, name) for name in required)


@dataclass(frozen=True)
class HamiltonianAction:
    """Matrix-free sector Hamiltonian wrapper around an ffsim LinearOperator."""

    norb: int
    nelec: ElectronSector
    dimension: int
    linear_operator: Any

    def matvec(self, vector: np.ndarray) -> np.ndarray:
        """Apply H to a sector vector."""
        candidate = np.asarray(vector, dtype=complex).reshape(-1)
        if candidate.size != self.dimension:
            raise ValueError("vector size does not match Hamiltonian sector dimension")
        return np.asarray(self.linear_operator.matvec(candidate), dtype=complex)

    def expectation(self, vector: np.ndarray) -> float:
        """Return the real expectation value <v|H|v>/<v|v>."""
        candidate = np.asarray(vector, dtype=complex).reshape(-1)
        norm_sq = float(np.vdot(candidate, candidate).real)
        if not np.isfinite(norm_sq) or norm_sq == 0.0:
            raise ValueError("cannot evaluate expectation of a zero vector")
        value = np.vdot(candidate, self.matvec(candidate)) / norm_sq
        return float(np.real_if_close(value))

    def time_evolve(self, vector: np.ndarray, *, time_point: float) -> np.ndarray:
        """Return exp(-i H t)|vector> without materializing the sector matrix."""
        candidate = np.asarray(vector, dtype=complex).reshape(-1)
        if candidate.size != self.dimension:
            raise ValueError("vector size does not match Hamiltonian sector dimension")
        if is_zero_time(time_point):
            return candidate.copy()
        evolved = expm_multiply(
            (-1j * float(time_point)) * self.linear_operator,
            candidate,
            traceA=0.0,
        )
        return np.asarray(evolved, dtype=complex)

    def to_matrix(self) -> np.ndarray:
        """Materialize the fixed-sector Hamiltonian for an explicit split step."""
        identity = np.eye(self.dimension, dtype=complex)
        matrix = np.column_stack([self.matvec(identity[:, index]) for index in range(self.dimension)])
        return 0.5 * (matrix + matrix.conj().T)

    def project(self, basis_matrix: np.ndarray) -> np.ndarray:
        """Return B^dagger H B for a small column-basis matrix B."""
        basis = np.asarray(basis_matrix, dtype=complex)
        if basis.ndim != 2 or basis.shape[0] != self.dimension or basis.shape[1] < 1:
            raise ValueError("basis_matrix shape is incompatible with Hamiltonian action")
        h_basis = np.column_stack([self.matvec(basis[:, index]) for index in range(basis.shape[1])])
        projected = basis.conj().T @ h_basis
        return 0.5 * (projected + projected.conj().T)

    def residual_diagnostics(
        self,
        basis_matrix: np.ndarray,
        *,
        residual_tolerance: float,
        rank_tolerance: float = 1e-10,
    ) -> tuple[dict[str, float], np.ndarray | None]:
        """Return lowest-Ritz residual diagnostics and the sector Ritz state."""
        basis = np.asarray(basis_matrix, dtype=complex)
        if basis.ndim != 2 or basis.shape[0] != self.dimension or basis.shape[1] < 1:
            raise ValueError("basis_matrix shape is incompatible with Hamiltonian action")

        q_matrix, r_matrix = np.linalg.qr(basis)
        diag = np.abs(np.diag(r_matrix)) if r_matrix.size else np.array([], dtype=float)
        rank = int(np.sum(diag > rank_tolerance))
        if rank < 1:
            raise ValueError("projected basis has zero numerical rank")

        q_matrix = q_matrix[:, :rank]
        projected = self.project(q_matrix)
        eigenvalues, eigenvectors = np.linalg.eigh(projected)
        order = np.argsort(np.real_if_close(eigenvalues).astype(float))
        lowest_energy = float(np.real_if_close(eigenvalues[order[0]]))
        ritz_state = q_matrix @ eigenvectors[:, order[0]]
        residual_vector = self.matvec(ritz_state) - lowest_energy * ritz_state
        residual_norm = float(np.linalg.norm(residual_vector))
        operator_state_norm = float(np.linalg.norm(self.matvec(ritz_state)))
        relative_residual = residual_norm / max(1.0, abs(lowest_energy), operator_state_norm)

        diagnostics = {
            "ritz_energy": lowest_energy,
            "ritz_residual_norm": residual_norm,
            "relative_ritz_residual": float(relative_residual),
            "residual_convergence_threshold": float(residual_tolerance),
            "basis_numerical_rank": float(rank),
        }
        return diagnostics, ritz_state


def build_hamiltonian_action(hamiltonian: object) -> HamiltonianAction:
    """Build a fixed-sector ffsim LinearOperator from Hamiltonian bundle tensors."""
    if not can_build_hamiltonian_action(hamiltonian):
        raise ValueError("Hamiltonian tensors are required for sector matrix-free action")

    import ffsim

    norb, nelec = resolve_sector_metadata(hamiltonian)
    one_body = np.asarray(getattr(hamiltonian, "one_body_tensor"), dtype=float)
    two_body = np.asarray(getattr(hamiltonian, "two_body_tensor"), dtype=float)
    if one_body.shape != (norb, norb):
        raise ValueError("one_body_tensor shape is incompatible with num_spatial_orbitals")
    if two_body.shape != (norb, norb, norb, norb):
        raise ValueError("two_body_tensor shape is incompatible with num_spatial_orbitals")

    molecular_hamiltonian = ffsim.MolecularHamiltonian(
        one_body,
        two_body,
        constant=float(getattr(hamiltonian, "constant", 0.0)),
    )
    linear_operator = ffsim.linear_operator(molecular_hamiltonian, norb, nelec)
    dimension = sector_dimension(norb, nelec)
    if tuple(linear_operator.shape) != (dimension, dimension):
        raise ValueError("ffsim LinearOperator shape does not match sector dimension")
    return HamiltonianAction(
        norb=norb,
        nelec=nelec,
        dimension=dimension,
        linear_operator=linear_operator,
    )
