"""Lazy public surface for the worker chemistry package.

Import algorithm implementations from their explicit package modules when
possible. The lazy map keeps existing convenience imports available without
loading every solver during package import.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    "AlgorithmResult": ("worker.chemistry.types", "AlgorithmResult"),
    "ChemistryInput": ("worker.chemistry.types", "ChemistryInput"),
    "PreparedMolecule": ("worker.chemistry.types", "PreparedMolecule"),
    "HamiltonianBundle": ("worker.chemistry.types", "HamiltonianBundle"),
    "VQEResult": ("worker.chemistry.types", "VQEResult"),
    "SQDResult": ("worker.chemistry.types", "SQDResult"),
    "KQDResult": ("worker.chemistry.types", "KQDResult"),
    "QFDResult": ("worker.chemistry.types", "QFDResult"),
    "QSEResult": ("worker.chemistry.types", "QSEResult"),
    "SKQDResult": ("worker.chemistry.types", "SKQDResult"),
    "build_ansatz": ("worker.chemistry.ansatz_registry", "build_ansatz"),
    "supported_ansatzes": ("worker.chemistry.ansatz_registry", "supported_ansatzes"),
    "build_optimizer": ("worker.chemistry.optimizer_registry", "build_optimizer"),
    "supported_optimizers": (
        "worker.chemistry.optimizer_registry",
        "supported_optimizers",
    ),
    "chemistry_cache_key": ("worker.chemistry.chemistry_cache", "chemistry_cache_key"),
    "ChemistryCache": ("worker.chemistry.chemistry_cache", "ChemistryCache"),
    "build_molecule": ("worker.chemistry.molecule_builder", "build_molecule"),
    "build_qubit_hamiltonian": (
        "worker.chemistry.hamiltonian_builder",
        "build_qubit_hamiltonian",
    ),
    "run_vqe": ("worker.chemistry.algorithms.vqe.workflow", "run_vqe"),
    "run_sqd": ("worker.chemistry.algorithms.sqd.workflow", "run_sqd"),
    "run_kqd": ("worker.chemistry.algorithms.kqd.workflow", "run_kqd"),
    "run_qfd": ("worker.chemistry.algorithms.qfd.workflow", "run_qfd"),
    "run_qse": ("worker.chemistry.algorithms.qse.workflow", "run_qse"),
    "run_skqd": ("worker.chemistry.skqd_solver", "run_skqd"),
}


def __getattr__(name: str) -> Any:
    """Load a public chemistry symbol only when a caller requests it."""
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = target
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Include lazy public symbols in interactive module inspection."""
    return sorted({*globals(), *_LAZY_EXPORTS})


def select_backend(*args: Any, **kwargs: Any) -> Any:
    """Select a backend without importing backend adapters at package import."""
    from worker.chemistry.backend_selector import select_backend as _select_backend

    return _select_backend(*args, **kwargs)


__all__ = [*sorted(_LAZY_EXPORTS), "select_backend"]
