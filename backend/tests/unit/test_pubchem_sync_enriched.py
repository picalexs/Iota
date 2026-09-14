"""
Unit tests for enriched PubChem sync service (Phase 2).

Tests cover:
- Element symbols expansion (Z=1–36)
- CompoundData dataclass
- Internal fetch functions (_resolve_name_to_cid, _fetch_3d_atoms_by_cid, etc.)
- Full compound data fetching
- Integration with sync_from_pubchem and search_pubchem_compounds
"""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from app.services.pubchem_sync import (
    ELEMENT_SYMBOLS,
    CompoundData,
    _fetch_2d_atoms_by_cid,
    _fetch_3d_atoms_by_cid,
    _fetch_compound_description,
    _fetch_compound_properties,
    _fetch_compound_synonyms,
    _fetch_full_compound_data,
    _resolve_name_to_cid,
    search_pubchem_compounds,
)
from app.services.pubchem_sync.search import _fetch_autocomplete_names, _fetch_search_hit

_TEST_REQUEST = httpx.Request("GET", "https://pubchem.ncbi.nlm.nih.gov")


def test_element_symbols_covers_z1_to_54() -> None:
    """ELEMENT_SYMBOLS should have all keys from 1 to 54 (H through Xe)."""
    expected_range = set(range(1, 55))
    actual_range = set(ELEMENT_SYMBOLS.keys())
    assert actual_range == expected_range, (
        f"Missing atomic numbers: {expected_range - actual_range}"
    )


def test_element_symbols_spot_check() -> None:
    """Spot check specific element symbols."""
    assert ELEMENT_SYMBOLS[1] == "H"
    assert ELEMENT_SYMBOLS[6] == "C"
    assert ELEMENT_SYMBOLS[7] == "N"
    assert ELEMENT_SYMBOLS[8] == "O"
    assert ELEMENT_SYMBOLS[26] == "Fe"
    assert ELEMENT_SYMBOLS[36] == "Kr"


def test_compound_data_creation() -> None:
    """CompoundData should be creatable with all fields."""
    atoms = [
        {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.0},
        {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.735},
    ]
    data = CompoundData(
        cid=283,
        atoms=atoms,
        iupac_name="dihydrogen",
        description="Molecular hydrogen",
        synonyms=["H2", "hydrogen molecule", "molecular hydrogen"],
        smiles="[H][H]",
        inchi="InChI=1S/H2/h1H",
        inchi_key="LFQSCWFLJHTTHZ-UHFFFAOYSA-N",
    )

    assert data.cid == 283
    assert len(data.atoms) == 2
    assert data.iupac_name == "dihydrogen"
    assert data.description == "Molecular hydrogen"
    assert len(data.synonyms) == 3
    assert data.smiles == "[H][H]"


def test_compound_data_with_none_fields() -> None:
    """CompoundData should handle None for optional fields."""
    atoms = [{"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.0}]
    data = CompoundData(
        cid=999,
        atoms=atoms,
        iupac_name=None,
        description=None,
        synonyms=[],
        smiles=None,
        inchi=None,
        inchi_key=None,
    )

    assert data.cid == 999
    assert data.iupac_name is None
    assert data.description is None
    assert data.synonyms == []


@pytest.mark.asyncio
async def test_resolve_name_to_cid_success() -> None:
    """_resolve_name_to_cid should extract CID from valid response."""
    cid_response = {
        "IdentifierList": {
            "CID": [283, 284, 285]  # Multiple CIDs, return first
        }
    }

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = lambda: cid_response
    mock_response.raise_for_status = Mock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_response)

    result = await _resolve_name_to_cid(mock_client, "dihydrogen")

    assert result == 283
    mock_client.get.assert_called_once()
    # Verify the endpoint was called correctly
    call_args = mock_client.get.call_args
    assert "compound/name" in call_args[0][0]
    assert "cids/JSON" in call_args[0][0]


@pytest.mark.asyncio
async def test_resolve_name_to_cid_404_returns_none() -> None:
    """_resolve_name_to_cid should return None on 404."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_response = AsyncMock()
    mock_response.status_code = 404
    mock_response.raise_for_status = Mock(
        side_effect=httpx.HTTPStatusError(
            "Not found", request=_TEST_REQUEST, response=mock_response
        )
    )
    mock_client.get.return_value = mock_response

    result = await _resolve_name_to_cid(mock_client, "nonexistent_compound")

    assert result is None


@pytest.mark.asyncio
async def test_resolve_name_to_cid_http_error() -> None:
    """_resolve_name_to_cid should handle HTTP errors gracefully."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_response = AsyncMock()
    mock_response.status_code = 500
    mock_response.raise_for_status = Mock(
        side_effect=httpx.HTTPStatusError(
            "Server error", request=_TEST_REQUEST, response=mock_response
        )
    )
    mock_client.get.return_value = mock_response

    result = await _resolve_name_to_cid(mock_client, "some_compound")

    assert result is None


@pytest.mark.asyncio
async def test_resolve_name_to_cid_retries_transient_503(caplog: pytest.LogCaptureFixture) -> None:
    """_resolve_name_to_cid should retry transient PubChem failures before succeeding."""
    retry_response = AsyncMock()
    retry_response.status_code = 503
    retry_response.raise_for_status = Mock(
        side_effect=httpx.HTTPStatusError(
            "Server busy", request=_TEST_REQUEST, response=retry_response
        )
    )

    success_response = AsyncMock()
    success_response.status_code = 200
    success_response.raise_for_status = Mock()
    success_response.json = Mock(return_value={"IdentifierList": {"CID": [283]}})

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(side_effect=[retry_response, success_response])

    with caplog.at_level(logging.INFO, logger="app.services.pubchem_sync._fetchers"):
        result = await _resolve_name_to_cid(mock_client, "dihydrogen")

    assert result == 283
    assert mock_client.get.await_count == 2
    assert "retrying in" in caplog.text


@pytest.mark.asyncio
async def test_resolve_name_to_cid_json_error() -> None:
    """_resolve_name_to_cid should handle JSON parse errors."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.side_effect = ValueError("Invalid JSON")
    mock_client.get.return_value = mock_response

    result = await _resolve_name_to_cid(mock_client, "some_compound")

    assert result is None


@pytest.mark.asyncio
async def test_resolve_name_to_cid_empty_cid_list() -> None:
    """_resolve_name_to_cid should return None if CID list is empty."""
    cid_response = {"IdentifierList": {"CID": []}}

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = cid_response
    mock_client.get.return_value = mock_response

    result = await _resolve_name_to_cid(mock_client, "nonexistent")

    assert result is None


@pytest.mark.asyncio
async def test_fetch_3d_atoms_by_cid_success() -> None:
    """_fetch_3d_atoms_by_cid should parse atoms from 3D conformer."""
    cid_response = {
        "PC_Compounds": [
            {
                "atoms": {
                    "aid": [1, 2],
                    "element": [1, 1],  # Two hydrogens
                },
                "coords": [
                    {
                        "conformers": [
                            {
                                "x": [0.0, 0.0],
                                "y": [0.0, 0.0],
                                "z": [0.0, 0.735],
                            }
                        ]
                    }
                ],
            }
        ]
    }

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = lambda: cid_response
    mock_response.raise_for_status = Mock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_response)

    result = await _fetch_3d_atoms_by_cid(mock_client, 283)

    assert result is not None
    assert len(result) == 2
    assert result[0]["symbol"] == "H"
    assert result[0]["x"] == pytest.approx(0.0)
    assert result[1]["z"] == pytest.approx(0.735)


@pytest.mark.asyncio
async def test_fetch_3d_atoms_by_cid_no_3d_returns_none() -> None:
    """_fetch_3d_atoms_by_cid should return None on 404."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_response = AsyncMock()
    mock_response.status_code = 404
    mock_response.raise_for_status = Mock(
        side_effect=httpx.HTTPStatusError(
            "Not found", request=_TEST_REQUEST, response=mock_response
        )
    )
    mock_client.get.return_value = mock_response

    result = await _fetch_3d_atoms_by_cid(mock_client, 999)

    assert result is None


@pytest.mark.asyncio
async def test_fetch_3d_atoms_by_cid_unknown_element() -> None:
    """_fetch_3d_atoms_by_cid should return None if element unknown (Z > 36)."""
    cid_response = {
        "PC_Compounds": [
            {
                "atoms": {
                    "aid": [1, 2],
                    "element": [1, 92],  # Uranium (Z=92, not available)
                },
                "coords": [
                    {
                        "conformers": [
                            {
                                "x": [0.0, 0.0],
                                "y": [0.0, 0.0],
                                "z": [0.0, 1.0],
                            }
                        ]
                    }
                ],
            }
        ]
    }

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = cid_response
    mock_client.get.return_value = mock_response

    result = await _fetch_3d_atoms_by_cid(mock_client, 283)

    assert result is None


@pytest.mark.asyncio
async def test_fetch_3d_atoms_by_cid_malformed_response() -> None:
    """_fetch_3d_atoms_by_cid should handle malformed JSON gracefully."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {}  # Missing expected keys
    mock_client.get.return_value = mock_response

    result = await _fetch_3d_atoms_by_cid(mock_client, 283)

    assert result is None


@pytest.mark.asyncio
async def test_fetch_3d_atoms_by_cid_mismatched_coordinates() -> None:
    """_fetch_3d_atoms_by_cid should reject malformed coordinate lengths."""
    cid_response = {
        "PC_Compounds": [
            {
                "atoms": {"element": [1, 1]},
                "coords": [{"conformers": [{"x": [0.0], "y": [0.0, 0.0], "z": [0.0, 0.7]}]}],
            }
        ]
    }
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = cid_response
    mock_client.get.return_value = mock_response

    result = await _fetch_3d_atoms_by_cid(mock_client, 283)

    assert result is None


@pytest.mark.asyncio
async def test_fetch_2d_atoms_by_cid_mismatched_coordinates() -> None:
    """_fetch_2d_atoms_by_cid should reject malformed coordinate lengths."""
    cid_response = {
        "PC_Compounds": [
            {
                "atoms": {"element": [1, 1]},
                "coords": [{"conformers": [{"x": [0.0, 0.0], "y": [0.0]}]}],
            }
        ]
    }
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = cid_response
    mock_client.get.return_value = mock_response

    result = await _fetch_2d_atoms_by_cid(mock_client, 283)

    assert result is None


@pytest.mark.asyncio
async def test_fetch_compound_properties_success() -> None:
    """_fetch_compound_properties should extract IUPAC, SMILES, InChI fields."""
    props_response = {
        "PropertyTable": {
            "Properties": [
                {
                    "IUPACName": "dihydrogen",
                    "CanonicalSMILES": "[H][H]",
                    "InChI": "InChI=1S/H2/h1H",
                    "InChIKey": "LFQSCWFLJHTTHZ-UHFFFAOYSA-N",
                }
            ]
        }
    }

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = lambda: props_response
    mock_response.raise_for_status = Mock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_response)

    result = await _fetch_compound_properties(mock_client, 283)

    assert result["iupac_name"] == "dihydrogen"
    assert result["smiles"] == "[H][H]"
    assert result["inchi"] == "InChI=1S/H2/h1H"
    assert result["inchi_key"] == "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"


@pytest.mark.asyncio
async def test_fetch_compound_properties_partial_fields() -> None:
    """_fetch_compound_properties should handle missing optional fields."""
    props_response = {
        "PropertyTable": {
            "Properties": [
                {
                    "IUPACName": "dihydrogen",
                    # SMILES missing
                }
            ]
        }
    }

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = lambda: props_response
    mock_response.raise_for_status = Mock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_response)

    result = await _fetch_compound_properties(mock_client, 283)

    assert result["iupac_name"] == "dihydrogen"
    assert result["smiles"] is None
    assert result["inchi"] is None


@pytest.mark.asyncio
async def test_fetch_compound_properties_http_error() -> None:
    """_fetch_compound_properties should return empty dict on HTTP error."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_response = AsyncMock()
    mock_response.status_code = 404
    mock_response.raise_for_status = Mock(
        side_effect=httpx.HTTPStatusError(
            "Not found", request=_TEST_REQUEST, response=mock_response
        )
    )
    mock_client.get.return_value = mock_response

    result = await _fetch_compound_properties(mock_client, 999)

    assert result == {"iupac_name": None, "smiles": None, "inchi": None, "inchi_key": None}


@pytest.mark.asyncio
async def test_fetch_compound_properties_empty_properties() -> None:
    """_fetch_compound_properties should handle empty Properties array."""
    props_response = {"PropertyTable": {"Properties": []}}

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = lambda: props_response
    mock_response.raise_for_status = Mock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_response)

    result = await _fetch_compound_properties(mock_client, 283)

    assert result == {"iupac_name": None, "smiles": None, "inchi": None, "inchi_key": None}


@pytest.mark.asyncio
async def test_fetch_compound_description_success() -> None:
    """_fetch_compound_description should extract first non-empty description."""
    desc_response = {
        "InformationList": {
            "Information": [
                {
                    "Description": "Dihydrogen is the most abundant element in the universe.",
                },
                {
                    "Description": "Used in many industrial processes.",
                },
            ]
        }
    }

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = lambda: desc_response
    mock_response.raise_for_status = Mock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_response)

    result = await _fetch_compound_description(mock_client, 283)
    assert result is not None

    # Should join the two descriptions
    assert "Dihydrogen is the most abundant element" in result
    assert "Used in many industrial processes" in result


@pytest.mark.asyncio
async def test_fetch_compound_description_skip_pubchem() -> None:
    """_fetch_compound_description should skip entries that are just 'PubChem'."""
    desc_response = {
        "InformationList": {
            "Information": [
                {"Description": "PubChem"},  # Skip this
                {"Description": "Useful molecule"},  # Use this
            ]
        }
    }

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = lambda: desc_response
    mock_response.raise_for_status = Mock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_response)

    result = await _fetch_compound_description(mock_client, 283)

    assert result == "Useful molecule"
    assert result != "PubChem"


@pytest.mark.asyncio
async def test_fetch_compound_description_empty_returns_none() -> None:
    """_fetch_compound_description should return None if no valid description."""
    desc_response = {"InformationList": {"Information": []}}

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = lambda: desc_response
    mock_response.raise_for_status = Mock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_response)

    result = await _fetch_compound_description(mock_client, 283)

    assert result is None


@pytest.mark.asyncio
async def test_fetch_compound_description_http_error() -> None:
    """_fetch_compound_description should return None on HTTP error."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_response = AsyncMock()
    mock_response.status_code = 404
    mock_response.raise_for_status = Mock(
        side_effect=httpx.HTTPStatusError(
            "Not found", request=_TEST_REQUEST, response=mock_response
        )
    )
    mock_client.get.return_value = mock_response

    result = await _fetch_compound_description(mock_client, 999)

    assert result is None


@pytest.mark.asyncio
async def test_fetch_compound_synonyms_returns_top_10() -> None:
    """_fetch_compound_synonyms should return first 10 unique synonyms."""
    # Provide 15 synonyms, only first 10 should be returned
    synonyms_list = [f"synonym_{i}" for i in range(15)]

    syn_response = {"InformationList": {"Information": [{"Synonym": synonyms_list}]}}

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = lambda: syn_response
    mock_response.raise_for_status = Mock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_response)

    result = await _fetch_compound_synonyms(mock_client, 283)

    assert len(result) == 10
    assert result == synonyms_list[:10]


@pytest.mark.asyncio
async def test_fetch_compound_synonyms_fewer_than_10() -> None:
    """_fetch_compound_synonyms should return all if fewer than 10."""
    syn_response = {
        "InformationList": {
            "Information": [{"Synonym": ["H2", "hydrogen molecule", "molecular hydrogen"]}]
        }
    }

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = lambda: syn_response
    mock_response.raise_for_status = Mock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_response)

    result = await _fetch_compound_synonyms(mock_client, 283)

    assert len(result) == 3
    assert result == ["H2", "hydrogen molecule", "molecular hydrogen"]


@pytest.mark.asyncio
async def test_fetch_compound_synonyms_empty_returns_empty_list() -> None:
    """_fetch_compound_synonyms should return empty list if no synonyms."""
    syn_response = {"InformationList": {"Information": []}}

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = lambda: syn_response
    mock_response.raise_for_status = Mock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_response)

    result = await _fetch_compound_synonyms(mock_client, 283)

    assert result == []


@pytest.mark.asyncio
async def test_fetch_compound_synonyms_http_error() -> None:
    """_fetch_compound_synonyms should return empty list on HTTP error."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_response = AsyncMock()
    mock_response.status_code = 404
    mock_response.raise_for_status = Mock(
        side_effect=httpx.HTTPStatusError(
            "Not found", request=_TEST_REQUEST, response=mock_response
        )
    )
    mock_client.get.return_value = mock_response

    result = await _fetch_compound_synonyms(mock_client, 999)

    assert result == []


@pytest.mark.asyncio
async def test_fetch_full_compound_data_success() -> None:
    """_fetch_full_compound_data should return CompoundData with all fields."""
    cid = 283

    mock_client = AsyncMock(spec=httpx.AsyncClient)

    # Create a mock that returns different responses based on URL
    async def mock_get(url: str, **kwargs):
        await asyncio.sleep(0)
        mock_response = AsyncMock()
        mock_response.status_code = 200

        if "cids/JSON" in url:
            mock_response.json = lambda: {"IdentifierList": {"CID": [cid]}}
        elif "3d" in url:
            mock_response.json = lambda: {
                "PC_Compounds": [
                    {
                        "atoms": {
                            "aid": [1, 2],
                            "element": [1, 1],
                        },
                        "coords": [
                            {
                                "conformers": [
                                    {
                                        "x": [0.0, 0.0],
                                        "y": [0.0, 0.0],
                                        "z": [0.0, 0.735],
                                    }
                                ]
                            }
                        ],
                    }
                ]
            }
        elif "IUPACName" in url:
            mock_response.json = lambda: {
                "PropertyTable": {
                    "Properties": [
                        {
                            "IUPACName": "dihydrogen",
                            "CanonicalSMILES": "[H][H]",
                            "InChI": "InChI=1S/H2/h1H",
                            "InChIKey": "LFQSCWFLJHTTHZ-UHFFFAOYSA-N",
                        }
                    ]
                }
            }
        elif "description" in url:
            mock_response.json = lambda: {
                "InformationList": {
                    "Information": [{"Description": "Dihydrogen is a colorless gas."}]
                }
            }
        elif "synonyms" in url:
            mock_response.json = lambda: {
                "InformationList": {"Information": [{"Synonym": ["H2", "molecular hydrogen"]}]}
            }

        mock_response.raise_for_status = Mock()
        return mock_response

    mock_client.get = mock_get

    result = await _fetch_full_compound_data(mock_client, "dihydrogen")

    assert result is not None
    assert isinstance(result, CompoundData)
    assert result.cid == 283
    assert len(result.atoms) == 2
    assert result.iupac_name == "dihydrogen"
    assert result.description == "Dihydrogen is a colorless gas."
    assert result.smiles == "[H][H]"
    assert result.inchi_key == "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"
    assert len(result.synonyms) == 2


@pytest.mark.asyncio
async def test_fetch_full_compound_data_no_3d_returns_none() -> None:
    """_fetch_full_compound_data should return None if 3D atoms unavailable."""
    cid = 283

    mock_client = AsyncMock(spec=httpx.AsyncClient)

    async def mock_get(url: str, **kwargs):
        await asyncio.sleep(0)
        mock_response = AsyncMock()

        if "cids/JSON" in url:
            mock_response.status_code = 200
            mock_response.json = lambda: {"IdentifierList": {"CID": [cid]}}
        elif "3d" in url:
            # No 3D conformer available
            mock_response.status_code = 404
            mock_response.raise_for_status = Mock(
                side_effect=httpx.HTTPStatusError(
                    "Not found",
                    request=_TEST_REQUEST,
                    response=mock_response,
                )
            )
        else:
            mock_response.status_code = 200
            mock_response.raise_for_status = Mock()

        return mock_response

    mock_client.get = mock_get

    result = await _fetch_full_compound_data(mock_client, "some_compound")

    assert result is None


@pytest.mark.asyncio
async def test_fetch_full_compound_data_cid_not_found() -> None:
    """_fetch_full_compound_data should return None if CID not found."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)

    async def mock_get(url: str, **kwargs):
        await asyncio.sleep(0)
        mock_response = AsyncMock()

        if "cids/JSON" in url:
            # CID list is empty
            mock_response.status_code = 200
            mock_response.json = lambda: {"IdentifierList": {"CID": []}}
        else:
            mock_response.status_code = 200
            mock_response.json = lambda: {}

        mock_response.raise_for_status = Mock()
        return mock_response

    mock_client.get = mock_get

    result = await _fetch_full_compound_data(mock_client, "nonexistent")

    assert result is None


@pytest.mark.asyncio
async def test_fetch_full_compound_data_retries_2d_fallback_after_503() -> None:
    """_fetch_full_compound_data should retry transient 2D fallback failures."""
    cid = 5486771

    first_2d_response = AsyncMock()
    first_2d_response.status_code = 503
    first_2d_response.raise_for_status = Mock(
        side_effect=httpx.HTTPStatusError(
            "Server busy", request=_TEST_REQUEST, response=first_2d_response
        )
    )

    success_2d_response = AsyncMock()
    success_2d_response.status_code = 200
    success_2d_response.raise_for_status = Mock()
    success_2d_response.json = Mock(
        return_value={
            "PC_Compounds": [
                {
                    "atoms": {"element": [12, 1, 1]},
                    "coords": [{"conformers": [{"x": [0.0, 1.0, -1.0], "y": [0.0, 0.0, 0.0]}]}],
                }
            ]
        }
    )

    fallback_2d_responses = [first_2d_response, success_2d_response]

    async def mock_get(url: str, **kwargs):
        await asyncio.sleep(0)
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()

        if "cids/JSON" in url:
            mock_response.json = Mock(return_value={"IdentifierList": {"CID": [cid]}})
            return mock_response
        if "record_type=3d" in url:
            mock_response.status_code = 404
            mock_response.raise_for_status = Mock(
                side_effect=httpx.HTTPStatusError(
                    "Not found", request=_TEST_REQUEST, response=mock_response
                )
            )
            return mock_response
        if "/property/" in url:
            mock_response.json = Mock(return_value={"PropertyTable": {"Properties": [{}]}})
            return mock_response
        if "/description/" in url:
            mock_response.json = Mock(return_value={"InformationList": {"Information": []}})
            return mock_response
        if "/synonyms/" in url:
            mock_response.json = Mock(return_value={"InformationList": {"Information": []}})
            return mock_response
        if url.endswith(f"/compound/cid/{cid}/JSON"):
            return fallback_2d_responses.pop(0)

        raise AssertionError(f"Unexpected URL {url}")

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = mock_get

    result = await _fetch_full_compound_data(mock_client, "magnesium hydride")

    assert result is not None
    assert result.cid == cid
    assert len(result.atoms) == 3
    assert result.atoms[0]["symbol"] == "Mg"


@pytest.mark.asyncio
async def test_sync_backfills_active_space_for_existing_null_record() -> None:
    """sync_from_pubchem should derive active_space when an existing molecule is missing it."""
    from app.services.pubchem_sync.sync import sync_from_pubchem

    existing_molecule = Mock()
    existing_molecule.active_space = None
    existing_molecule.atoms = [
        {"symbol": "O", "x": 0.0, "y": 0.0, "z": 0.0},
        {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.9},
        {"symbol": "H", "x": 0.0, "y": 0.8, "z": -0.3},
    ]
    existing_molecule.charge = 0
    existing_molecule.multiplicity = 1

    mock_db = Mock()
    mock_scalars = Mock()
    mock_scalars.first.return_value = existing_molecule
    mock_db.scalars.return_value = mock_scalars
    mock_db.commit = Mock()

    mock_inner_client = AsyncMock()
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_inner_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await sync_from_pubchem(mock_db, molecule_names=["H2O"])

    assert existing_molecule.active_space["n_electrons"] == 8
    assert existing_molecule.active_space["n_orbitals"] == 6
    assert existing_molecule.active_space["method"] == "automatic_valence"
    mock_db.commit.assert_called()
    assert result.skipped == 1
    assert result.added == 0


@pytest.mark.asyncio
async def test_sync_does_not_overwrite_existing_active_space() -> None:
    """sync_from_pubchem should not overwrite explicit active_space choices."""
    from app.services.pubchem_sync.sync import sync_from_pubchem

    existing_molecule = Mock()
    existing_molecule.active_space = {"n_electrons": 6, "n_orbitals": 6, "method": "avas"}

    mock_db = Mock()
    mock_scalars = Mock()
    mock_scalars.first.return_value = existing_molecule
    mock_db.scalars.return_value = mock_scalars
    mock_db.commit = Mock()

    mock_inner_client = AsyncMock()
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_inner_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await sync_from_pubchem(mock_db, molecule_names=["glycine"])

    assert existing_molecule.active_space == {
        "n_electrons": 6,
        "n_orbitals": 6,
        "method": "avas",
    }
    mock_db.commit.assert_not_called()
    assert result.skipped == 1


@pytest.mark.asyncio
async def test_sync_default_seed_only_imports_selectable_singlets() -> None:
    """Default sync should skip curated molecules that are not selectable in the rollout."""
    from app.services.pubchem_sync.sync import sync_from_pubchem

    curated = [
        {"name": "H2", "pubchem_name": "dihydrogen", "charge": 0, "multiplicity": 1},
        {"name": "O2", "pubchem_name": "dioxygen", "charge": 0, "multiplicity": 3},
    ]
    compound = CompoundData(
        cid=783,
        atoms=[
            {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.0},
            {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.7414},
        ],
        iupac_name="molecular hydrogen",
        description="Hydrogen molecule",
        synonyms=["H2", "dihydrogen"],
        smiles="[H][H]",
        inchi="InChI=1S/H2/h1H",
        inchi_key="UFHFLCQGNIYNRP-UHFFFAOYSA-N",
    )

    mock_db = Mock()
    mock_db.scalars.return_value.first.return_value = None
    mock_db.commit = Mock()
    mock_db.refresh = Mock()

    mock_inner_client = AsyncMock()
    fetch_mock = AsyncMock(return_value=compound)
    with (
        patch("app.services.pubchem_sync.sync.CURATED_MOLECULES", curated),
        patch(
            "app.services.pubchem_sync.sync._fetch_full_compound_data",
            fetch_mock,
        ),
        patch("httpx.AsyncClient") as mock_client_cls,
    ):
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_inner_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await sync_from_pubchem(mock_db)

    assert result.added == 1
    assert result.skipped == 1
    fetch_mock.assert_awaited_once_with(mock_inner_client, "dihydrogen")
    inserted = mock_db.add.call_args.args[0]
    assert inserted.name == "H2"
    assert inserted.multiplicity == 1


@pytest.mark.asyncio
async def test_sync_default_seed_skips_molecule_with_incompatible_active_space() -> None:
    """Default sync should skip singlets whose derived active space is not selectable."""
    from app.services.pubchem_sync.sync import sync_from_pubchem

    curated = [
        {"name": "OddShell", "pubchem_name": "odd shell", "charge": 0, "multiplicity": 1},
    ]
    compound = CompoundData(
        cid=424242,
        atoms=[
            {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.0},
            {"symbol": "Li", "x": 0.0, "y": 0.0, "z": 1.5},
        ],
        iupac_name="odd shell",
        description=None,
        synonyms=[],
        smiles=None,
        inchi=None,
        inchi_key=None,
    )

    mock_db = Mock()
    mock_db.scalars.return_value.first.return_value = None
    mock_db.commit = Mock()

    mock_inner_client = AsyncMock()
    fetch_mock = AsyncMock(return_value=compound)
    with (
        patch("app.services.pubchem_sync.sync.CURATED_MOLECULES", curated),
        patch(
            "app.services.pubchem_sync.sync._fetch_full_compound_data",
            fetch_mock,
        ),
        patch(
            "app.services.pubchem_sync.sync.derive_active_space_from_atoms",
            return_value={"n_electrons": 3, "n_orbitals": 2, "method": "mock"},
        ),
        patch("httpx.AsyncClient") as mock_client_cls,
    ):
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_inner_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await sync_from_pubchem(mock_db)

    assert result.added == 0
    assert result.skipped == 1
    mock_db.add.assert_not_called()
    mock_db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_sync_skips_duplicate_pubchem_cid_under_different_existing_name() -> None:
    """Sync should not create a duplicate row when the same CID already exists under another name."""  # noqa: E501
    from app.services.pubchem_sync.sync import sync_from_pubchem

    existing = Mock()
    existing.name = "Hydrogen molecule H2"
    existing.pubchem_cid = 783
    existing.active_space = {"n_electrons": 2, "n_orbitals": 2, "method": "automatic_valence"}

    name_lookup = Mock()
    name_lookup.first.return_value = None
    cid_lookup = Mock()
    cid_lookup.first.return_value = existing

    mock_db = Mock()
    mock_db.scalars.side_effect = [name_lookup, cid_lookup]
    mock_db.commit = Mock()

    compound = CompoundData(
        cid=783,
        atoms=[
            {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.0},
            {"symbol": "H", "x": 0.0, "y": 0.0, "z": 0.7414},
        ],
        iupac_name="molecular hydrogen",
        description="Hydrogen molecule",
        synonyms=["H2", "dihydrogen"],
        smiles="[H][H]",
        inchi="InChI=1S/H2/h1H",
        inchi_key="UFHFLCQGNIYNRP-UHFFFAOYSA-N",
    )

    mock_inner_client = AsyncMock()
    fetch_mock = AsyncMock(return_value=compound)
    with (
        patch(
            "app.services.pubchem_sync.sync._fetch_full_compound_data",
            fetch_mock,
        ),
        patch("httpx.AsyncClient") as mock_client_cls,
    ):
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_inner_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await sync_from_pubchem(mock_db, molecule_names=["H2"])

    assert result.added == 0
    assert result.skipped == 1
    mock_db.add.assert_not_called()


@pytest.mark.asyncio
async def test_search_pubchem_compounds_includes_cid() -> None:
    """search_pubchem_compounds should include CID in results."""
    names = ["H2", "molecular hydrogen"]

    async def mock_get(url: str, **kwargs):
        await asyncio.sleep(0)
        mock_response = AsyncMock()
        mock_response.status_code = 200

        if "autocomplete" in url:
            mock_response.json = lambda: {"dictionary_terms": {"compound": names}}
        elif "IUPACName" in url:
            mock_response.json = lambda: {
                "PropertyTable": {
                    "Properties": [
                        {
                            "IUPACName": "dihydrogen",
                            "MolecularFormula": "H2",
                            "CID": 283,
                        }
                    ]
                }
            }
        else:
            mock_response.json = lambda: {"PropertyTable": {"Properties": []}}

        mock_response.raise_for_status = Mock()
        return mock_response

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = mock_get
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        results = await search_pubchem_compounds("hydrogen", limit=2)

    assert len(results) > 0
    assert "cid" in results[0]
    assert results[0]["cid"] is not None


@pytest.mark.asyncio
async def test_fetch_search_hit_uses_fallback_on_provider_error(caplog) -> None:
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.side_effect = httpx.TimeoutException("timed out")

    with caplog.at_level(logging.DEBUG, logger="app.services.pubchem_sync.search"):
        result = await _fetch_search_hit(mock_client, "hydrogen")

    assert result == {
        "name": "hydrogen",
        "iupac_name": "hydrogen",
        "formula": "",
        "cid": None,
    }
    assert "using fallback (TimeoutException)" in caplog.text


@pytest.mark.asyncio
async def test_fetch_search_hit_uses_fallback_for_empty_properties() -> None:
    mock_response = Mock(status_code=200)
    mock_response.json = Mock(return_value={"PropertyTable": {"Properties": []}})
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_response

    result = await _fetch_search_hit(mock_client, "hydrogen")

    assert result["name"] == "hydrogen"
    assert result["iupac_name"] == "hydrogen"
    assert result["formula"] == ""
    assert result["cid"] is None


@pytest.mark.asyncio
async def test_autocomplete_fallback_does_not_log_exception_details(
    caplog: pytest.LogCaptureFixture,
) -> None:
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.side_effect = RuntimeError("provider detail must stay server-side")

    with caplog.at_level(logging.WARNING, logger="app.services.pubchem_sync.search"):
        result = await _fetch_autocomplete_names(mock_client, "hydrogen", limit=8)

    assert result == []
    assert "RuntimeError" in caplog.text
    assert "provider detail" not in caplog.text
