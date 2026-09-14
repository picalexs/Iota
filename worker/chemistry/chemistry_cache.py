"""Bounded cache helpers for chemistry artifacts."""

from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from collections.abc import Callable
from copy import deepcopy

from worker.chemistry.types import HamiltonianBundle, PreparedMolecule


def chemistry_cache_key(molecule: PreparedMolecule) -> str:
    """Build a deterministic cache key from normalized molecule input."""
    payload = {
        "atom_spec": [
            [
                symbol,
                [round(float(x), 10), round(float(y), 10), round(float(z), 10)],
            ]
            for symbol, (x, y, z) in molecule.atom_spec
        ],
        "basis": molecule.basis,
        "charge": molecule.charge,
        "multiplicity": molecule.multiplicity,
        "active_space": list(molecule.active_space) if molecule.active_space is not None else None,
    }
    canonical_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()


class ChemistryCache:
    """Simple LRU cache with explicit invalidation and copy-on-read semantics."""

    def __init__(self, max_entries: int = 32) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be >= 1")
        self._max_entries = max_entries
        self._store: OrderedDict[str, HamiltonianBundle] = OrderedDict()

    def __len__(self) -> int:
        return len(self._store)

    def get(self, key: str) -> HamiltonianBundle | None:
        """Return a cached bundle, moving the key to the most-recent slot."""
        bundle = self._store.get(key)
        if bundle is None:
            return None
        self._store.move_to_end(key)
        return deepcopy(bundle)

    def set(self, key: str, bundle: HamiltonianBundle) -> None:
        """Store a bundle and evict least-recently-used entries beyond capacity."""
        self._store[key] = deepcopy(bundle)
        self._store.move_to_end(key)
        while len(self._store) > self._max_entries:
            self._store.popitem(last=False)

    def get_or_set(self, key: str, builder: Callable[[], HamiltonianBundle]) -> HamiltonianBundle:
        """Get bundle from cache or build and cache it on miss."""
        cached = self.get(key)
        if cached is not None:
            return cached
        built = builder()
        self.set(key, built)
        return deepcopy(built)

    def invalidate(self, key: str) -> bool:
        """Remove a single key from cache if present."""
        return self._store.pop(key, None) is not None

    def clear(self) -> None:
        """Clear all cache entries."""
        self._store.clear()
