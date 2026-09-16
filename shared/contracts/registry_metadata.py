"""UI-safe registry metadata shared without importing quantum runtimes."""

from __future__ import annotations

from copy import deepcopy
from typing import TypedDict


class AnsatzMetadata(TypedDict):
    """Public metadata for a worker ansatz choice."""

    label: str
    aliases: list[str]
    description: str
    default_reps: int


class OptimizerMetadata(TypedDict):
    """Public metadata for a worker optimizer choice."""

    label: str
    aliases: list[str]
    description: str
    kind: str
    scipy_method: str | None
    allowed_options: list[str]
    supports_max_function_evaluations: bool


_ANSATZ_METADATA: dict[str, AnsatzMetadata] = {
    "efficientsu2": {
        "label": "EfficientSU2",
        "aliases": ["efficient_su2", "efficientsu2"],
        "description": "Hardware-efficient SU(2) ansatz with single-qubit rotations and CX entanglement.",
        "default_reps": 2,
    },
    "numberpreserving": {
        "label": "NumberPreserving",
        "aliases": ["number_preserving", "numberpreserving"],
        "description": (
            "Hartree-Fock-seeded same-spin excitation-preserving ansatz that stays in the "
            "declared electron sector."
        ),
        "default_reps": 2,
    },
    "realamplitudes": {
        "label": "RealAmplitudes",
        "aliases": ["real_amplitudes", "realamplitudes"],
        "description": "Real-valued Ry/CX ansatz with fewer parameters than EfficientSU2.",
        "default_reps": 2,
    },
    "twolocal": {
        "label": "TwoLocal",
        "aliases": ["two_local", "twolocal"],
        "description": "Two-local Ry/Rz plus CX ansatz for higher-expressibility scans.",
        "default_reps": 2,
    },
}

_OPTIMIZER_METADATA: dict[str, OptimizerMetadata] = {
    "COBYLA": {
        "label": "COBYLA",
        "aliases": [],
        "description": "Derivative-free constrained optimizer; the current default.",
        "kind": "scipy",
        "scipy_method": "COBYLA",
        "allowed_options": ["catol", "f_target", "rhobeg", "rhoend", "tol"],
        "supports_max_function_evaluations": False,
    },
    "SPSA": {
        "label": "SPSA",
        "aliases": [],
        "description": "Stochastic optimizer suited for noisy primitive evaluations.",
        "kind": "spsa",
        "scipy_method": None,
        "allowed_options": ["allowed_increase", "blocking", "learning_rate", "perturbation"],
        "supports_max_function_evaluations": False,
    },
    "SLSQP": {
        "label": "SLSQP",
        "aliases": [],
        "description": "Gradient-based SciPy optimizer for smooth local scans.",
        "kind": "scipy",
        "scipy_method": "SLSQP",
        "allowed_options": ["eps", "ftol", "tol"],
        "supports_max_function_evaluations": False,
    },
    "L_BFGS_B": {
        "label": "L-BFGS-B",
        "aliases": ["L-BFGS-B"],
        "description": "Bound-aware quasi-Newton optimizer for larger parameter vectors.",
        "kind": "scipy",
        "scipy_method": "L-BFGS-B",
        "allowed_options": ["eps", "ftol", "gtol", "maxfun", "maxls", "tol"],
        "supports_max_function_evaluations": True,
    },
}


def supported_ansatz_metadata() -> dict[str, AnsatzMetadata]:
    """Return a defensive copy of public ansatz metadata."""
    return deepcopy(_ANSATZ_METADATA)


def supported_ansatz_aliases() -> dict[str, str]:
    """Return normalized ansatz aliases mapped to canonical worker IDs."""
    return {
        alias.strip().lower(): canonical_id
        for canonical_id, metadata in _ANSATZ_METADATA.items()
        for alias in {canonical_id, *metadata["aliases"]}
    }


def resolve_ansatz_id(value: str) -> str | None:
    """Resolve a public ansatz name while retaining legacy underscore input."""
    normalized = value.strip().lower()
    aliases = supported_ansatz_aliases()
    compact = normalized.replace("_", "").replace("-", "")
    return aliases.get(normalized) or aliases.get(compact)


def supported_optimizer_metadata() -> dict[str, OptimizerMetadata]:
    """Return a defensive copy of public optimizer metadata."""
    return deepcopy(_OPTIMIZER_METADATA)


def supported_optimizer_aliases() -> dict[str, str]:
    """Return normalized optimizer aliases mapped to canonical worker IDs."""
    return {
        alias.strip().upper(): canonical_id
        for canonical_id, metadata in _OPTIMIZER_METADATA.items()
        for alias in {canonical_id, *metadata["aliases"]}
    }


def resolve_optimizer_id(value: str) -> str | None:
    """Resolve an optimizer name to its canonical worker ID."""
    return supported_optimizer_aliases().get(value.strip().upper())
