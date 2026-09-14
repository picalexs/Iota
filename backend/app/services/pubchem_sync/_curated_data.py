"""
Curated reference data for PubChem synchronization.

Contains immutable lookup tables and molecular benchmark definitions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# PubChem REST base URL (no trailing slash)
PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

# ---------------------------------------------------------------------------
# Periodic-table helpers
# ---------------------------------------------------------------------------

#: Map PubChem atomic-number codes → element symbols (Z=1–54, H through Xe).
ELEMENT_SYMBOLS: dict[int, str] = {
    1: "H",
    2: "He",
    3: "Li",
    4: "Be",
    5: "B",
    6: "C",
    7: "N",
    8: "O",
    9: "F",
    10: "Ne",
    11: "Na",
    12: "Mg",
    13: "Al",
    14: "Si",
    15: "P",
    16: "S",
    17: "Cl",
    18: "Ar",
    19: "K",
    20: "Ca",
    21: "Sc",
    22: "Ti",
    23: "V",
    24: "Cr",
    25: "Mn",
    26: "Fe",
    27: "Co",
    28: "Ni",
    29: "Cu",
    30: "Zn",
    31: "Ga",
    32: "Ge",
    33: "As",
    34: "Se",
    35: "Br",
    36: "Kr",
    37: "Rb",
    38: "Sr",
    39: "Y",
    40: "Zr",
    41: "Nb",
    42: "Mo",
    43: "Tc",
    44: "Ru",
    45: "Rh",
    46: "Pd",
    47: "Ag",
    48: "Cd",
    49: "In",
    50: "Sn",
    51: "Sb",
    52: "Te",
    53: "I",
    54: "Xe",
}

# ---------------------------------------------------------------------------
# Compound data structure
# ---------------------------------------------------------------------------


@dataclass
class CompoundData:
    """Structured result from fetching full compound metadata from PubChem."""

    cid: int
    atoms: list[dict[str, float | str]]
    iupac_name: str | None
    description: str | None
    synonyms: list[str]
    smiles: str | None
    inchi: str | None
    inchi_key: str | None


# ---------------------------------------------------------------------------
# Curated molecule list
# ---------------------------------------------------------------------------

#: Quantum-chemistry benchmark molecules to fetch from PubChem.
#: ``pubchem_name`` is the search term sent to the PubChem name endpoint;
#: ``name`` is the display name stored in the local DB.
CURATED_MOLECULES: list[dict[str, Any]] = [
    # ---- Diatomics ----
    {"name": "H2", "pubchem_name": "dihydrogen", "charge": 0, "multiplicity": 1},
    {"name": "LiH", "pubchem_name": "lithium hydride", "charge": 0, "multiplicity": 1},
    {"name": "BeH", "pubchem_name": "beryllium monohydride", "charge": 0, "multiplicity": 2},
    {"name": "BH", "pubchem_name": "boron monohydride", "charge": 0, "multiplicity": 1},
    {"name": "N2", "pubchem_name": "dinitrogen", "charge": 0, "multiplicity": 1},
    {"name": "O2", "pubchem_name": "dioxygen", "charge": 0, "multiplicity": 3},
    {"name": "F2", "pubchem_name": "difluorine", "charge": 0, "multiplicity": 1},
    {"name": "HF", "pubchem_name": "hydrogen fluoride", "charge": 0, "multiplicity": 1},
    {"name": "CO", "pubchem_name": "carbon monoxide", "charge": 0, "multiplicity": 1},
    {"name": "NO", "pubchem_name": "nitric oxide", "charge": 0, "multiplicity": 2},
    {"name": "OH", "pubchem_name": "hydroxyl radical", "charge": 0, "multiplicity": 2},
    {"name": "HCl", "pubchem_name": "hydrogen chloride", "charge": 0, "multiplicity": 1},
    {"name": "NaH", "pubchem_name": "sodium hydride", "charge": 0, "multiplicity": 1},
    {"name": "LiF", "pubchem_name": "lithium fluoride", "charge": 0, "multiplicity": 1},
    {"name": "NaCl", "pubchem_name": "sodium chloride", "charge": 0, "multiplicity": 1},
    {"name": "Li2", "pubchem_name": "dilithium", "charge": 0, "multiplicity": 1},
    {"name": "Na2", "pubchem_name": "disodium", "charge": 0, "multiplicity": 1},
    {"name": "MgO", "pubchem_name": "magnesium oxide", "charge": 0, "multiplicity": 1},
    {"name": "AlH", "pubchem_name": "aluminum monohydride", "charge": 0, "multiplicity": 1},
    {"name": "SiH", "pubchem_name": "silylidyne", "charge": 0, "multiplicity": 2},
    {"name": "KH", "pubchem_name": "potassium hydride", "charge": 0, "multiplicity": 1},
    {"name": "CaH", "pubchem_name": "calcium monohydride", "charge": 0, "multiplicity": 2},
    {"name": "CS", "pubchem_name": "carbon monosulfide", "charge": 0, "multiplicity": 1},
    {"name": "SO", "pubchem_name": "sulfur monoxide", "charge": 0, "multiplicity": 3},
    {"name": "PN", "pubchem_name": "phosphorus mononitride", "charge": 0, "multiplicity": 1},
    # ---- Triatomics ----
    {"name": "H2O", "pubchem_name": "water", "charge": 0, "multiplicity": 1},
    {"name": "CO2", "pubchem_name": "carbon dioxide", "charge": 0, "multiplicity": 1},
    {"name": "N2O", "pubchem_name": "nitrous oxide", "charge": 0, "multiplicity": 1},
    {"name": "HCN", "pubchem_name": "hydrogen cyanide", "charge": 0, "multiplicity": 1},
    {"name": "H2S", "pubchem_name": "hydrogen sulfide", "charge": 0, "multiplicity": 1},
    {"name": "SO2", "pubchem_name": "sulfur dioxide", "charge": 0, "multiplicity": 1},
    {"name": "NO2", "pubchem_name": "nitrogen dioxide", "charge": 0, "multiplicity": 2},
    {"name": "OCS", "pubchem_name": "carbonyl sulfide", "charge": 0, "multiplicity": 1},
    {"name": "BeH2", "pubchem_name": "beryllium hydride", "charge": 0, "multiplicity": 1},
    {"name": "MgH2", "pubchem_name": "magnesium hydride", "charge": 0, "multiplicity": 1},
    {"name": "formaldehyde", "pubchem_name": "formaldehyde", "charge": 0, "multiplicity": 1},
    {"name": "HOF", "pubchem_name": "hypofluorous acid", "charge": 0, "multiplicity": 1},
    # ---- Small polyatomics ----
    {"name": "NH3", "pubchem_name": "ammonia", "charge": 0, "multiplicity": 1},
    {"name": "CH4", "pubchem_name": "methane", "charge": 0, "multiplicity": 1},
    {"name": "PH3", "pubchem_name": "phosphine", "charge": 0, "multiplicity": 1},
    {"name": "SiH4", "pubchem_name": "silane", "charge": 0, "multiplicity": 1},
    {"name": "H2O2", "pubchem_name": "hydrogen peroxide", "charge": 0, "multiplicity": 1},
    {"name": "N2H4", "pubchem_name": "hydrazine", "charge": 0, "multiplicity": 1},
    {"name": "C2H2", "pubchem_name": "acetylene", "charge": 0, "multiplicity": 1},
    {"name": "C2H4", "pubchem_name": "ethylene", "charge": 0, "multiplicity": 1},
    {"name": "C2H6", "pubchem_name": "ethane", "charge": 0, "multiplicity": 1},
    {"name": "HNC", "pubchem_name": "hydrogen isocyanide", "charge": 0, "multiplicity": 1},
    {"name": "formic acid", "pubchem_name": "formic acid", "charge": 0, "multiplicity": 1},
    {"name": "methanol", "pubchem_name": "methanol", "charge": 0, "multiplicity": 1},
    {"name": "CH3F", "pubchem_name": "fluoromethane", "charge": 0, "multiplicity": 1},
    {"name": "AlH3", "pubchem_name": "alane", "charge": 0, "multiplicity": 1},
    {"name": "BH3", "pubchem_name": "borane", "charge": 0, "multiplicity": 1},
    {"name": "LiOH", "pubchem_name": "lithium hydroxide", "charge": 0, "multiplicity": 1},
    {"name": "HNO3", "pubchem_name": "nitric acid", "charge": 0, "multiplicity": 1},
    {"name": "BF3", "pubchem_name": "boron trifluoride", "charge": 0, "multiplicity": 1},
    {"name": "CF4", "pubchem_name": "carbon tetrafluoride", "charge": 0, "multiplicity": 1},
    # ---- Common organic molecules ----
    {"name": "benzene", "pubchem_name": "benzene", "charge": 0, "multiplicity": 1},
    {"name": "ethanol", "pubchem_name": "ethanol", "charge": 0, "multiplicity": 1},
    {"name": "acetone", "pubchem_name": "acetone", "charge": 0, "multiplicity": 1},
    {"name": "acetic acid", "pubchem_name": "acetic acid", "charge": 0, "multiplicity": 1},
    {"name": "urea", "pubchem_name": "urea", "charge": 0, "multiplicity": 1},
    {"name": "propane", "pubchem_name": "propane", "charge": 0, "multiplicity": 1},
    {"name": "pyridine", "pubchem_name": "pyridine", "charge": 0, "multiplicity": 1},
    {"name": "aniline", "pubchem_name": "aniline", "charge": 0, "multiplicity": 1},
    {"name": "toluene", "pubchem_name": "toluene", "charge": 0, "multiplicity": 1},
    {"name": "phenol", "pubchem_name": "phenol", "charge": 0, "multiplicity": 1},
    {"name": "glycine", "pubchem_name": "glycine", "charge": 0, "multiplicity": 1},
    {"name": "alanine", "pubchem_name": "alanine", "charge": 0, "multiplicity": 1},
    {"name": "naphthalene", "pubchem_name": "naphthalene", "charge": 0, "multiplicity": 1},
    {"name": "caffeine", "pubchem_name": "caffeine", "charge": 0, "multiplicity": 1},
    {"name": "aspirin", "pubchem_name": "aspirin", "charge": 0, "multiplicity": 1},
]


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class SyncResult:
    """Summary of one sync operation."""

    added: int = 0
    skipped: int = 0
    failed: list[str] = field(default_factory=list)
