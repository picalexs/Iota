"""Hamiltonian bundle cache seam for run execution."""

from __future__ import annotations

from worker.chemistry.chemistry_cache import ChemistryCache, chemistry_cache_key
from worker.chemistry.hamiltonian_builder import build_qubit_hamiltonian
from worker.chemistry.molecule_builder import build_molecule
from worker.chemistry.types import ChemistryInput, HamiltonianBundle

_HAMILTONIAN_CACHE = ChemistryCache(max_entries=32)


def clear_hamiltonian_bundle_cache() -> None:
    """Clear cached Hamiltonian bundles used by execute_run."""
    _HAMILTONIAN_CACHE.clear()


def _build_hamiltonian_bundle(
    *,
    chemistry_input: ChemistryInput,
    chemistry_options: dict[str, object] | None = None,
) -> HamiltonianBundle:
    """Build Hamiltonian artifacts for a run from a detached chemistry input snapshot."""
    prepared_molecule = build_molecule(chemistry_input)
    resolved_options = dict(chemistry_options or {})
    cache_key = chemistry_cache_key(prepared_molecule, resolved_options)
    if not resolved_options:
        return _HAMILTONIAN_CACHE.get_or_set(
            cache_key,
            lambda: build_qubit_hamiltonian(prepared_molecule),
        )
    return _HAMILTONIAN_CACHE.get_or_set(
        cache_key,
        lambda: build_qubit_hamiltonian(
            prepared_molecule,
            chemistry_options=resolved_options,
        ),
    )
