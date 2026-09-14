"""
Low-level PubChem data fetchers.

Async functions for querying the PubChem REST API and parsing responses.
All functions are private (prefixed with `_`) and should not be imported directly.
"""

from __future__ import annotations

import asyncio
import logging
from urllib.parse import quote

import httpx

from app.services.pubchem_sync._curated_data import ELEMENT_SYMBOLS, PUBCHEM_BASE, CompoundData

logger = logging.getLogger(__name__)

_PUBCHEM_TIMEOUT_SECONDS = 15.0
_PUBCHEM_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_PUBCHEM_MAX_ATTEMPTS = 3
_PUBCHEM_INITIAL_BACKOFF_SECONDS = 0.5


async def _get_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    context: str,
) -> dict | None:
    """Fetch JSON from PubChem with small retries for transient upstream failures."""
    backoff = _PUBCHEM_INITIAL_BACKOFF_SECONDS

    for attempt in range(1, _PUBCHEM_MAX_ATTEMPTS + 1):
        try:
            response = await client.get(url, timeout=_PUBCHEM_TIMEOUT_SECONDS)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code == 404:
                return None
            if status_code in _PUBCHEM_RETRYABLE_STATUS_CODES and attempt < _PUBCHEM_MAX_ATTEMPTS:
                logger.info(
                    "PubChem transient HTTP %d for %s; retrying in %.1fs (attempt %d/%d).",
                    status_code,
                    context,
                    backoff,
                    attempt + 1,
                    _PUBCHEM_MAX_ATTEMPTS,
                )
                await asyncio.sleep(backoff)
                backoff *= 2
                continue
            raise
        except httpx.HTTPError as exc:
            if attempt < _PUBCHEM_MAX_ATTEMPTS:
                logger.info(
                    "PubChem request error for %s; retrying in %.1fs (attempt %d/%d): %s",
                    context,
                    backoff,
                    attempt + 1,
                    _PUBCHEM_MAX_ATTEMPTS,
                    exc,
                )
                await asyncio.sleep(backoff)
                backoff *= 2
                continue
            raise
    raise RuntimeError("PubChem retry loop exhausted unexpectedly")


async def _resolve_name_to_cid(
    client: httpx.AsyncClient,
    pubchem_name: str,
) -> int | None:
    """
    Resolve a compound name to its PubChem CID.

    Args:
        client: httpx AsyncClient for requests.
        pubchem_name: Compound name to search for.

    Returns:
        The first matching CID or None if not found or on error.
    """
    encoded = quote(pubchem_name)
    url = f"{PUBCHEM_BASE}/compound/name/{encoded}/cids/JSON"

    try:
        data = await _get_json(client, url, context=f"name lookup '{pubchem_name}'")
        if data is None:
            logger.debug("PubChem: CID not found for '%s'.", pubchem_name)
            return None
    except httpx.HTTPStatusError as exc:
        logger.warning("PubChem HTTP error for '%s': %s", pubchem_name, exc)
        return None
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("PubChem request failed for '%s': %s", pubchem_name, exc)
        return None

    try:
        cids: list[int] = data["IdentifierList"]["CID"]
        if cids:
            return cids[0]
    except (KeyError, IndexError, TypeError) as exc:
        logger.warning("PubChem: could not parse CID for '%s': %s", pubchem_name, exc)

    return None


async def _fetch_3d_atoms_by_cid(
    client: httpx.AsyncClient,
    cid: int,
) -> list[dict[str, float | str]] | None:
    """
    Fetch the 3-D conformer for a given CID from PubChem REST API.

    Args:
        client: httpx AsyncClient for requests.
        cid: PubChem Compound ID.

    Returns:
        List of ``{"symbol": str, "x": float, "y": float, "z": float}`` dicts,
        or None when no 3D data is available.
    """
    url = f"{PUBCHEM_BASE}/compound/cid/{cid}/JSON?record_type=3d"

    try:
        data = await _get_json(client, url, context=f"CID {cid} 3D geometry")
        if data is None:
            logger.debug("PubChem: no 3-D record for CID %d.", cid)
            return None
    except httpx.HTTPStatusError as exc:
        logger.warning("PubChem HTTP error for CID %d: %s", cid, exc)
        return None
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("PubChem request failed for CID %d: %s", cid, exc)
        return None

    try:
        compound = data["PC_Compounds"][0]
        element_list: list[int] = compound["atoms"]["element"]

        # The first entry in coords[] should be the 3-D conformer.
        conformer = compound["coords"][0]["conformers"][0]
        x_list: list[float] = conformer["x"]
        y_list: list[float] = conformer["y"]
        z_list: list[float] = conformer["z"]
    except (KeyError, IndexError, TypeError) as exc:
        logger.warning("PubChem: could not parse 3-D data for CID %d: %s", cid, exc)
        return None

    if not (len(element_list) == len(x_list) == len(y_list) == len(z_list)):
        logger.warning("PubChem: mismatched 3-D coordinate lengths for CID %d.", cid)
        return None

    atoms: list[dict[str, float | str]] = []
    for i, atomic_num in enumerate(element_list):
        symbol = ELEMENT_SYMBOLS.get(atomic_num)
        if symbol is None:
            logger.warning(
                "PubChem: unknown atomic number %d (CID %d) — element not in Z=1–54.",
                atomic_num,
                cid,
            )
            return None
        atoms.append(
            {
                "symbol": symbol,
                "x": round(x_list[i], 6),
                "y": round(y_list[i], 6),
                "z": round(z_list[i], 6),
            }
        )

    return atoms


async def _fetch_2d_atoms_by_cid(
    client: httpx.AsyncClient,
    cid: int,
) -> list[dict[str, float | str]] | None:
    """
    Fetch the 2D conformer for a given CID, used as a fallback when no 3D data exists.

    Z-coordinates are set to 0.0 for all atoms since 2D conformers are planar.

    Args:
        client: httpx AsyncClient for requests.
        cid: PubChem Compound ID.

    Returns:
        List of atom dicts with z=0.0, or None on failure.
    """
    url = f"{PUBCHEM_BASE}/compound/cid/{cid}/JSON"

    try:
        data = await _get_json(client, url, context=f"CID {cid} 2D geometry")
        if data is None:
            logger.debug("PubChem: no 2D record for CID %d.", cid)
            return None
    except httpx.HTTPStatusError as exc:
        logger.warning("PubChem HTTP error for CID %d (2D): %s", cid, exc)
        return None
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("PubChem request failed for CID %d (2D): %s", cid, exc)
        return None

    try:
        compound = data["PC_Compounds"][0]
        element_list: list[int] = compound["atoms"]["element"]
        conformer = compound["coords"][0]["conformers"][0]
        x_list: list[float] = conformer["x"]
        y_list: list[float] = conformer["y"]
        z_list: list[float] = conformer.get("z", [])
    except (KeyError, IndexError, TypeError) as exc:
        logger.warning("PubChem: could not parse 2D data for CID %d: %s", cid, exc)
        return None

    if not (len(element_list) == len(x_list) == len(y_list)):
        logger.warning("PubChem: mismatched 2D coordinate lengths for CID %d.", cid)
        return None

    atoms: list[dict[str, float | str]] = []
    for i, atomic_num in enumerate(element_list):
        symbol = ELEMENT_SYMBOLS.get(atomic_num)
        if symbol is None:
            logger.warning(
                "PubChem: unknown atomic number %d (CID %d) — element not in Z=1–54.",
                atomic_num,
                cid,
            )
            return None
        atoms.append(
            {
                "symbol": symbol,
                "x": round(x_list[i], 6),
                "y": round(y_list[i], 6),
                "z": round(z_list[i] if i < len(z_list) else 0.0, 6),
            }
        )

    return atoms


async def _fetch_compound_properties(
    client: httpx.AsyncClient,
    cid: int,
) -> dict[str, str | None]:
    """
    Fetch IUPAC name, SMILES, InChI, and InChIKey for a compound.

    Args:
        client: httpx AsyncClient for requests.
        cid: PubChem Compound ID.

    Returns:
        Dict with keys: iupac_name, smiles, inchi, inchi_key (all str | None).
    """
    url = (
        f"{PUBCHEM_BASE}/compound/cid/{cid}/property/IUPACName,CanonicalSMILES,InChI,InChIKey/JSON"
    )

    try:
        data = await _get_json(client, url, context=f"CID {cid} properties")
        if data is None:
            return {
                "iupac_name": None,
                "smiles": None,
                "inchi": None,
                "inchi_key": None,
            }
    except (httpx.HTTPStatusError, httpx.HTTPError, ValueError) as exc:
        logger.debug("PubChem: could not fetch properties for CID %d: %s", cid, exc)
        return {
            "iupac_name": None,
            "smiles": None,
            "inchi": None,
            "inchi_key": None,
        }

    try:
        props = data["PropertyTable"]["Properties"][0]
        # PubChem may return the key as "CanonicalSMILES", "IsomericSMILES",
        # or "ConnectivitySMILES" depending on the API version.
        smiles = (
            props.get("CanonicalSMILES")
            or props.get("IsomericSMILES")
            or props.get("ConnectivitySMILES")
        )
        return {
            "iupac_name": props.get("IUPACName"),
            "smiles": smiles,
            "inchi": props.get("InChI"),
            "inchi_key": props.get("InChIKey"),
        }
    except (KeyError, IndexError, TypeError) as exc:
        logger.debug("PubChem: could not parse properties for CID %d: %s", cid, exc)
        return {
            "iupac_name": None,
            "smiles": None,
            "inchi": None,
            "inchi_key": None,
        }


async def _fetch_compound_description(
    client: httpx.AsyncClient,
    cid: int,
) -> str | None:
    """
    Fetch the first non-empty description for a compound.

    Args:
        client: httpx AsyncClient for requests.
        cid: PubChem Compound ID.

    Returns:
        Description text, or None if not available.
    """
    url = f"{PUBCHEM_BASE}/compound/cid/{cid}/description/JSON"

    try:
        data = await _get_json(client, url, context=f"CID {cid} description")
        if data is None:
            return None
    except (httpx.HTTPStatusError, httpx.HTTPError, ValueError) as exc:
        logger.debug("PubChem: could not fetch description for CID %d: %s", cid, exc)
        return None

    try:
        info_list = data["InformationList"]["Information"]
        descriptions = []

        for info in info_list:
            desc = info.get("Description", "").strip()
            # Skip entries that are just "PubChem" or empty
            if desc and desc != "PubChem":
                descriptions.append(desc)

        if descriptions:
            return "\n\n".join(descriptions)
    except (KeyError, IndexError, TypeError) as exc:
        logger.debug("PubChem: could not parse description for CID %d: %s", cid, exc)

    return None


async def _fetch_compound_synonyms(
    client: httpx.AsyncClient,
    cid: int,
) -> list[str]:
    """
    Fetch up to 10 unique synonyms for a compound.

    Args:
        client: httpx AsyncClient for requests.
        cid: PubChem Compound ID.

    Returns:
        List of up to 10 synonym strings, or empty list if none available.
    """
    url = f"{PUBCHEM_BASE}/compound/cid/{cid}/synonyms/JSON"

    try:
        data = await _get_json(client, url, context=f"CID {cid} synonyms")
        if data is None:
            return []
    except (httpx.HTTPStatusError, httpx.HTTPError, ValueError) as exc:
        logger.debug("PubChem: could not fetch synonyms for CID %d: %s", cid, exc)
        return []

    try:
        info_list = data["InformationList"]["Information"]
        if info_list:
            synonyms = info_list[0].get("Synonym", [])
            # Return up to 10 unique synonyms, preserving order
            if not synonyms:
                return []
            seen: set[str] = set()
            unique_synonyms: list[str] = []
            for syn in synonyms:
                if syn not in seen:
                    seen.add(syn)
                    unique_synonyms.append(syn)
                    if len(unique_synonyms) == 10:
                        break
            return unique_synonyms
    except (KeyError, IndexError, TypeError) as exc:
        logger.debug("PubChem: could not parse synonyms for CID %d: %s", cid, exc)

    return []


async def _fetch_full_compound_data(
    client: httpx.AsyncClient,
    pubchem_name: str,
) -> CompoundData | None:
    """
    Fetch all compound metadata from PubChem: CID, atoms, properties, description, synonyms.

    Tries 3D conformer first; falls back to 2D (z=0) if no 3D record exists.
    Calls are executed concurrently via asyncio.gather for efficiency.

    Args:
        client: httpx AsyncClient for requests.
        pubchem_name: Compound name to search for.

    Returns:
        CompoundData with all fields populated, or None if atoms are unavailable.
    """
    # Step 1: Resolve name to CID
    cid = await _resolve_name_to_cid(client, pubchem_name)
    if cid is None:
        return None

    # Step 2: Fetch all metadata concurrently
    atoms, props, description, synonyms = await asyncio.gather(
        _fetch_3d_atoms_by_cid(client, cid),
        _fetch_compound_properties(client, cid),
        _fetch_compound_description(client, cid),
        _fetch_compound_synonyms(client, cid),
    )

    # Fall back to 2D conformer (z=0) if no 3D record available
    if atoms is None:
        logger.info(
            "PubChem: no 3D record for CID %d (%s) — falling back to 2D.", cid, pubchem_name
        )
        atoms = await _fetch_2d_atoms_by_cid(client, cid)

    if atoms is None:
        return None

    return CompoundData(
        cid=cid,
        atoms=atoms,
        iupac_name=props.get("iupac_name"),
        description=description,
        synonyms=synonyms,
        smiles=props.get("smiles"),
        inchi=props.get("inchi"),
        inchi_key=props.get("inchi_key"),
    )
