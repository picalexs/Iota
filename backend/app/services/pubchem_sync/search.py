"""
PubChem search and single-molecule fetching.

Functions for searching PubChem and fetching molecules on-demand.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, TypedDict
from urllib.parse import quote

import httpx

from app.services.active_space import derive_active_space_from_atoms
from app.services.pubchem_sync._curated_data import PUBCHEM_BASE
from app.services.pubchem_sync._fetchers import _fetch_full_compound_data

logger = logging.getLogger(__name__)


class PubChemSearchHit(TypedDict):
    """Typed payload returned by PubChem autocomplete search."""

    name: str
    iupac_name: str
    formula: str
    cid: int | None


def _fallback_search_hit(name: str) -> PubChemSearchHit:
    return {"name": name, "iupac_name": name, "formula": "", "cid": None}


def _search_hit_from_props(name: str, props: dict[str, Any]) -> PubChemSearchHit:
    iupac_name = props.get("IUPACName", name)
    formula = props.get("MolecularFormula", "")
    cid = props.get("CID")
    return {
        "name": name,
        "iupac_name": iupac_name if isinstance(iupac_name, str) else name,
        "formula": formula if isinstance(formula, str) else "",
        "cid": cid if isinstance(cid, int) else None,
    }


async def _fetch_autocomplete_names(
    client: httpx.AsyncClient,
    query: str,
    limit: int,
) -> list[str]:
    encoded = quote(query)
    autocomplete_url = (
        f"https://pubchem.ncbi.nlm.nih.gov/rest/autocomplete/compound/{encoded}/json?limit={limit}"
    )

    try:
        resp = await client.get(autocomplete_url, timeout=10.0)
        if resp.status_code != 200:
            return []
        return resp.json().get("dictionary_terms", {}).get("compound", [])[:limit]
    except Exception as exc:
        logger.warning(
            "PubChem autocomplete failed; returning no candidates (%s)",
            type(exc).__name__,
        )
        return []


async def _fetch_search_hit(client: httpx.AsyncClient, name: str) -> PubChemSearchHit:
    try:
        prop_resp = await client.get(
            f"{PUBCHEM_BASE}/compound/name/{quote(name)}/property/IUPACName,MolecularFormula,CID/JSON",
            timeout=10.0,
        )
        if prop_resp.status_code == 200:
            props = prop_resp.json().get("PropertyTable", {}).get("Properties", [{}])[0]
            return _search_hit_from_props(name, props)
    except (httpx.HTTPError, ValueError, TypeError, AttributeError, IndexError) as exc:
        logger.debug(
            "PubChem property lookup returned unusable data; using fallback (%s)",
            type(exc).__name__,
        )
    return _fallback_search_hit(name)


async def fetch_molecule_from_pubchem(name: str) -> dict[str, Any] | None:
    """
    Fetch a single molecule by *name* from the PubChem REST API.

    Args:
        name: The molecule name (sent directly to the PubChem name endpoint).

    Returns:
        A dict with keys: ``name``, ``charge``, ``multiplicity``, ``atoms``,
        ``active_space``, ``pubchem_cid``, ``iupac_name``, ``description``,
        ``synonyms``, ``smiles``, ``inchi``, ``inchi_key``.
        Returns None when PubChem has no geometry (3D or 2D) for the name.

    Raises:
        ValueError: If the molecule contains an element whose atomic number is
            not present in the known periodic table (i.e. Z > 54).
    """
    async with httpx.AsyncClient() as client:
        compound_data = await _fetch_full_compound_data(client, name)

    if compound_data is None:
        return None

    return {
        "name": name,
        "charge": 0,
        "multiplicity": 1,
        "atoms": compound_data.atoms,
        "active_space": derive_active_space_from_atoms(
            compound_data.atoms,
            charge=0,
            multiplicity=1,
        ),
        "pubchem_cid": compound_data.cid,
        "iupac_name": compound_data.iupac_name,
        "description": compound_data.description,
        "synonyms": compound_data.synonyms,
        "smiles": compound_data.smiles,
        "inchi": compound_data.inchi,
        "inchi_key": compound_data.inchi_key,
    }


async def search_pubchem_compounds(query: str, limit: int = 8) -> list[PubChemSearchHit]:
    """
    Search PubChem for compounds matching *query* using the autocomplete API.

    Uses the autocomplete endpoint for typo tolerance, then fetches molecular
    formula, IUPAC name, and CID for each candidate.

    Args:
        query: Search string (handles typos, partial names).
        limit: Maximum number of results to return.

    Returns:
        List of dicts with keys: ``name`` (str), ``iupac_name`` (str),
        ``formula`` (str), ``cid`` (int | None).
    """
    async with httpx.AsyncClient() as client:
        names = await _fetch_autocomplete_names(client, query, limit)
        if not names:
            return []

        results = await asyncio.gather(*[_fetch_search_hit(client, n) for n in names])
        return list(results)
