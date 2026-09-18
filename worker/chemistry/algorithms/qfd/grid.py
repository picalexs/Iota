"""Named QFD time-grid construction and provenance helpers."""

from __future__ import annotations

import hashlib

import numpy as np

from worker.chemistry.time_evolution import build_time_grid


def build_qfd_time_grid(
    *,
    qfd_variant: str,
    num_time_points: int,
    max_time: float,
    time_grid_type: str,
    kappa: float,
) -> np.ndarray:
    """Build a QFD grid under an explicit published-variant convention."""
    if qfd_variant == "qfd_original_symmetric":
        if num_time_points < 3 or num_time_points % 2 == 0:
            raise ValueError("qfd_original_symmetric requires an odd point count of at least 3")
        if kappa <= 0.0 or not np.isfinite(kappa):
            raise ValueError("qfd_original_symmetric requires positive finite kappa")
        kmax = (num_time_points - 1) // 2
        indices = np.arange(-kmax, kmax + 1, dtype=float)
        return 2.0 * np.pi * indices / float(kappa)
    if qfd_variant != "qfd_chemistry_forward":
        raise ValueError(f"unsupported QFD variant: {qfd_variant}")
    return build_time_grid(
        num_time_points=num_time_points,
        max_time=max_time,
        grid_type=time_grid_type,
    )


def qfd_grid_metadata(time_grid: np.ndarray, *, qfd_variant: str, kappa: float) -> dict[str, object]:
    """Return serializable grid values and a stable provenance hash."""
    grid = np.asarray(time_grid, dtype=np.float64)
    digest = hashlib.sha256(grid.tobytes()).hexdigest()
    return {
        "qfd_variant": qfd_variant,
        "grid_convention": (
            "symmetric_kappa" if qfd_variant == "qfd_original_symmetric" else "forward"
        ),
        "kappa": float(kappa),
        "time_grid_values": [float(value) for value in grid],
        "time_grid_hash": digest,
    }


def qfd_spectral_width_bound(
    *,
    operator_matrix: np.ndarray | None,
    pauli_hamiltonian: object,
    eigenvalues: np.ndarray | None = None,
) -> tuple[float, str]:
    """Return an exact dense width or a safe Pauli-coefficient width bound."""
    if eigenvalues is not None:
        values = np.asarray(eigenvalues, dtype=float).reshape(-1)
        if values.size == 0 or not np.all(np.isfinite(values)):
            raise ValueError("QFD spectral-width eigenvalues must be finite and non-empty")
        return float(np.max(values) - np.min(values)), "exact_dense_spectrum"
    if operator_matrix is not None:
        matrix = np.asarray(operator_matrix, dtype=complex)
        if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
            raise ValueError("QFD spectral-width estimation requires a square operator matrix")
        hermitian = 0.5 * (matrix + matrix.conj().T)
        eigenvalues = np.linalg.eigvalsh(hermitian)
        return float(eigenvalues[-1] - eigenvalues[0]), "exact_dense_spectrum"

    coefficients = getattr(pauli_hamiltonian, "coeffs", None)
    paulis = getattr(pauli_hamiltonian, "paulis", None)
    to_labels = getattr(paulis, "to_labels", None)
    if coefficients is None or not callable(to_labels):
        raise ValueError("QFD cannot bound the spectrum for qfd_original_symmetric")
    labels = to_labels()
    values = np.asarray(coefficients, dtype=complex).reshape(-1)
    if len(labels) != values.size:
        raise ValueError("QFD Pauli coefficients do not match their labels")
    non_identity_norm = sum(
        abs(coefficient)
        for label, coefficient in zip(labels, values, strict=True)
        if any(character != "I" for character in label)
    )
    return float(2.0 * non_identity_norm), "pauli_l1_conservative_bound"


def resolve_qfd_symmetric_kappa(
    requested_kappa: float | None,
    *,
    spectral_width_bound: float,
    bound_source: str,
) -> tuple[float, dict[str, object]]:
    """Resolve a scale that covers the estimated spectral range plus overage."""
    width = float(spectral_width_bound)
    if not np.isfinite(width) or width < 0.0:
        raise ValueError("QFD spectral-width bound must be finite and non-negative")
    margin = max(width * 0.01, 1e-8)
    minimum_kappa = width + margin
    if requested_kappa is None:
        kappa = minimum_kappa
        source = f"automatic_{bound_source}"
    else:
        kappa = float(requested_kappa)
        if not np.isfinite(kappa) or kappa <= 0.0:
            raise ValueError("QFD kappa must be finite and positive")
        if kappa < minimum_kappa:
            raise ValueError(
                "QFD kappa must exceed the spectral-width bound plus overage "
                f"({minimum_kappa:.12g}; bound source: {bound_source})"
            )
        source = "user_supplied"
    return kappa, {
        "spectral_width_bound": width,
        "kappa_safety_margin": margin,
        "minimum_kappa": minimum_kappa,
        "kappa_source": source,
    }


__all__ = [
    "build_qfd_time_grid",
    "qfd_grid_metadata",
    "qfd_spectral_width_bound",
    "resolve_qfd_symmetric_kappa",
]
