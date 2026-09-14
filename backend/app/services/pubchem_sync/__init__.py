"""
PubChem synchronization package.

Split into focused modules:
- _curated_data: static reference data (ELEMENT_SYMBOLS, CURATED_MOLECULES)
- _fetchers: low-level async PubChem API functions
- sync: main synchronization orchestrator
- search: search and on-demand molecule fetching
"""

from app.services.pubchem_sync._curated_data import (
    CURATED_MOLECULES,
    ELEMENT_SYMBOLS,
    CompoundData,
    SyncResult,
)
from app.services.pubchem_sync._fetchers import (
    _fetch_2d_atoms_by_cid,
    _fetch_3d_atoms_by_cid,
    _fetch_compound_description,
    _fetch_compound_properties,
    _fetch_compound_synonyms,
    _fetch_full_compound_data,
    _resolve_name_to_cid,
)
from app.services.pubchem_sync.search import fetch_molecule_from_pubchem, search_pubchem_compounds
from app.services.pubchem_sync.sync import sync_from_pubchem

__all__ = [
    # Public API
    "sync_from_pubchem",
    "fetch_molecule_from_pubchem",
    "search_pubchem_compounds",
    # Reference data
    "ELEMENT_SYMBOLS",
    "CompoundData",
    "CURATED_MOLECULES",
    "SyncResult",
    # Private fetchers (exported for testing)
    "_resolve_name_to_cid",
    "_fetch_3d_atoms_by_cid",
    "_fetch_2d_atoms_by_cid",
    "_fetch_compound_properties",
    "_fetch_compound_description",
    "_fetch_compound_synonyms",
    "_fetch_full_compound_data",
]
