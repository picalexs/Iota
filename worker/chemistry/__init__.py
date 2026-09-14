"""Chemistry pipeline utilities for worker execution."""

from worker.chemistry.ansatz_registry import build_ansatz, supported_ansatzes
from worker.chemistry.chemistry_cache import ChemistryCache, chemistry_cache_key
from worker.chemistry.hamiltonian_builder import build_qubit_hamiltonian
from worker.chemistry.kqd_solver import run_kqd
from worker.chemistry.molecule_builder import build_molecule
from worker.chemistry.optimizer_registry import build_optimizer, supported_optimizers
from worker.chemistry.qfd_solver import run_qfd
from worker.chemistry.qse_solver import run_qse
from worker.chemistry.skqd_solver import run_skqd
from worker.chemistry.sqd_solver import run_sqd
from worker.chemistry.types import (
    AlgorithmResult,
    ChemistryInput,
    HamiltonianBundle,
    KQDResult,
    PreparedMolecule,
    QFDResult,
    QSEResult,
    SKQDResult,
    SQDResult,
    VQEResult,
)
from worker.chemistry.vqe_solver import run_vqe


def select_backend(*args, **kwargs):
    """Lazily import backend selection to avoid adapter/package import cycles."""
    from worker.chemistry.backend_selector import select_backend as _select_backend

    return _select_backend(*args, **kwargs)


__all__ = [
    "AlgorithmResult",
    "ChemistryInput",
    "PreparedMolecule",
    "HamiltonianBundle",
    "build_ansatz",
    "supported_ansatzes",
    "build_optimizer",
    "supported_optimizers",
    "VQEResult",
    "SQDResult",
    "KQDResult",
    "QFDResult",
    "QSEResult",
    "SKQDResult",
    "chemistry_cache_key",
    "ChemistryCache",
    "build_molecule",
    "build_qubit_hamiltonian",
    "select_backend",
    "run_vqe",
    "run_sqd",
    "run_kqd",
    "run_qfd",
    "run_qse",
    "run_skqd",
]
