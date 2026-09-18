"""Static registry of package-owned chemistry algorithm definitions."""

from __future__ import annotations

from worker.chemistry.algorithm_contracts import AlgorithmDefinition
from worker.chemistry.algorithms.kqd.definition import ALGORITHM_DEFINITION as KQD_DEFINITION
from worker.chemistry.algorithms.qfd.definition import ALGORITHM_DEFINITION as QFD_DEFINITION
from worker.chemistry.algorithms.qse.definition import ALGORITHM_DEFINITION as QSE_DEFINITION
from worker.chemistry.algorithms.skqd.definition import ALGORITHM_DEFINITION as SKQD_DEFINITION
from worker.chemistry.algorithms.sqd.definition import ALGORITHM_DEFINITION as SQD_DEFINITION
from worker.chemistry.algorithms.vqe.definition import ALGORITHM_DEFINITION as VQE_DEFINITION

_DEFINITIONS = (
    VQE_DEFINITION,
    SQD_DEFINITION,
    KQD_DEFINITION,
    QFD_DEFINITION,
    QSE_DEFINITION,
    SKQD_DEFINITION,
)

_ALGORITHM_REGISTRY = {definition.algorithm: definition for definition in _DEFINITIONS}
if len(_ALGORITHM_REGISTRY) != len(_DEFINITIONS):
    raise RuntimeError("algorithm registry contains duplicate identifiers")


def algorithm_definitions() -> dict[str, AlgorithmDefinition]:
    """Return a copy of the package-owned algorithm registry."""
    return dict(_ALGORITHM_REGISTRY)


__all__ = ["algorithm_definitions"]
