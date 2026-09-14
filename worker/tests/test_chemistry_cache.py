"""Tests for bounded chemistry cache behavior."""

from worker.chemistry.chemistry_cache import ChemistryCache, chemistry_cache_key
from worker.chemistry.types import HamiltonianBundle, PreparedMolecule


def _prepared_molecule(*, z: float, basis: str = "sto-3g") -> PreparedMolecule:
    return PreparedMolecule(
        atom_spec=[("H", (0.0, 0.0, 0.0)), ("H", (0.0, 0.0, z))],
        basis=basis,
        charge=0,
        multiplicity=1,
        active_space=(2, 2),
    )


def _bundle(tag: str) -> HamiltonianBundle:
    return HamiltonianBundle(
        num_spatial_orbitals=2,
        num_qubits=4,
        num_electrons_alpha=1,
        num_electrons_beta=1,
        one_body_tensor=[[1.0, 0.0], [0.0, 1.0]],
        two_body_tensor=[[[[0.0]]]],
        constant=0.0,
        pauli_hamiltonian={"tag": tag},
        metadata={"tag": tag},
    )


def test_chemistry_cache_key_is_deterministic_and_sensitive_to_inputs() -> None:
    key_one = chemistry_cache_key(_prepared_molecule(z=0.7414, basis="sto-3g"))
    key_two = chemistry_cache_key(_prepared_molecule(z=0.7414, basis="sto-3g"))
    key_three = chemistry_cache_key(_prepared_molecule(z=0.7414, basis="6-31g*"))

    assert key_one == key_two
    assert key_one != key_three


def test_chemistry_cache_enforces_lru_bounds() -> None:
    cache = ChemistryCache(max_entries=2)

    key_one = chemistry_cache_key(_prepared_molecule(z=0.70))
    key_two = chemistry_cache_key(_prepared_molecule(z=0.75))
    key_three = chemistry_cache_key(_prepared_molecule(z=0.80))

    cache.set(key_one, _bundle("one"))
    cache.set(key_two, _bundle("two"))
    assert len(cache) == 2

    # Touch key_one so key_two becomes LRU.
    assert cache.get(key_one) is not None
    cache.set(key_three, _bundle("three"))

    assert len(cache) == 2
    assert cache.get(key_one) is not None
    assert cache.get(key_three) is not None
    assert cache.get(key_two) is None


def test_chemistry_cache_invalidation_and_no_stale_leakage() -> None:
    cache = ChemistryCache(max_entries=2)
    key = chemistry_cache_key(_prepared_molecule(z=0.7414))
    cache.set(key, _bundle("original"))

    fetched = cache.get(key)
    assert fetched is not None
    fetched.metadata["tag"] = "mutated"

    # Cache should return an isolated copy, not the mutated object.
    fetched_again = cache.get(key)
    assert fetched_again is not None
    assert fetched_again.metadata["tag"] == "original"

    assert cache.invalidate(key) is True
    assert cache.get(key) is None
