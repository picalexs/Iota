"""
Pydantic schemas for molecule resources.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from app.core.active_space_capacity import minimum_basis_active_orbital_limit
from app.schemas.common import BaseORMModel

MAX_ATOMS_PER_MOLECULE = 5_000
MAX_DESCRIPTION_LENGTH = 20_000
MAX_SYNONYMS = 64
MAX_SYNONYM_LENGTH = 512
MAX_INCHI_LENGTH = 4_096

SUPPORTED_ATOM_SYMBOLS = frozenset(
    {
        "H",
        "He",
        "Li",
        "Be",
        "B",
        "C",
        "N",
        "O",
        "F",
        "Ne",
        "Na",
        "Mg",
        "Al",
        "Si",
        "P",
        "S",
        "Cl",
        "Ar",
        "K",
        "Ca",
        "Sc",
        "Ti",
        "V",
        "Cr",
        "Mn",
        "Fe",
        "Co",
        "Ni",
        "Cu",
        "Zn",
        "Ga",
        "Ge",
        "As",
        "Se",
        "Br",
        "Kr",
        "Rb",
        "Sr",
        "Y",
        "Zr",
        "Nb",
        "Mo",
        "Tc",
        "Ru",
        "Rh",
        "Pd",
        "Ag",
        "Cd",
        "In",
        "Sn",
        "Sb",
        "Te",
        "I",
        "Xe",
    }
)
MOLECULE_RESPONSE_VALIDATION_CONTEXT = {"allow_unsupported_symbols": True}


def _validate_synonym_lengths(value: list[str] | None) -> None:
    """Bound each synonym so a short list cannot carry huge strings."""
    if value is None:
        return
    for synonym in value:
        if len(synonym) > MAX_SYNONYM_LENGTH:
            raise ValueError(f"each synonym must not exceed {MAX_SYNONYM_LENGTH} characters")


def _unsupported_atom_symbols(
    atoms: list["AtomSchema"] | list[dict[str, Any]] | None,
) -> list[str]:
    if not atoms:
        return []

    unsupported: set[str] = set()
    for atom in atoms:
        symbol_raw = atom.symbol if isinstance(atom, AtomSchema) else atom.get("symbol")
        symbol = str(symbol_raw or "").strip()
        if not symbol:
            continue
        normalized = symbol[0].upper() + symbol[1:].lower()
        if normalized not in SUPPORTED_ATOM_SYMBOLS:
            unsupported.add(normalized)

    return sorted(unsupported)


class AtomSchema(BaseModel):
    """A single atom in Cartesian coordinates."""

    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(..., min_length=1, description="Atomic symbol (e.g. H, O, Li)")
    x: float = Field(..., description="X coordinate")
    y: float = Field(..., description="Y coordinate")
    z: float = Field(..., description="Z coordinate")

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, value: str, info: ValidationInfo) -> str:
        """Reject blank or unsupported atom symbols."""
        symbol = value.strip()
        if not symbol:
            raise ValueError("Atom symbol must be non-empty")
        normalized = symbol[0].upper() + symbol[1:].lower()
        allow_unsupported_symbols = isinstance(info.context, dict) and info.context.get(
            "allow_unsupported_symbols"
        )
        if normalized not in SUPPORTED_ATOM_SYMBOLS and not allow_unsupported_symbols:
            raise ValueError(
                f"Atom symbol '{symbol}' is not supported. Use a valid element from H through Xe."
            )
        return normalized

    @field_validator("x", "y", "z")
    @classmethod
    def validate_finite_coordinate(cls, value: float) -> float:
        """Ensure coordinates are finite numeric values."""
        if not math.isfinite(value):
            raise ValueError("Atom coordinates must be finite numbers")
        return value


class ActiveSpaceSchema(BaseModel):
    """Typed active space definition with extensible optional keys."""

    model_config = ConfigDict(extra="allow")

    n_electrons: int = Field(..., ge=1, description="Number of active electrons")
    n_orbitals: int = Field(..., ge=1, description="Number of active orbitals")


class MoleculeEligibilityResponse(BaseModel):
    """Derived rollout eligibility labels for molecule selection UIs."""

    selectable: bool
    label: str
    reason: str | None = None
    capability_labels: list[str] = Field(default_factory=list)


def _active_space_numbers(
    active_space: ActiveSpaceSchema | dict[str, Any] | None,
) -> tuple[int | None, int | None]:
    if active_space is None:
        return None, None
    payload = (
        active_space.model_dump() if isinstance(active_space, ActiveSpaceSchema) else active_space
    )
    n_electrons = payload.get("n_electrons")
    n_orbitals = payload.get("n_orbitals")
    return (
        n_electrons if isinstance(n_electrons, int) and n_electrons > 0 else None,
        n_orbitals if isinstance(n_orbitals, int) and n_orbitals > 0 else None,
    )


def build_molecule_eligibility(
    *,
    multiplicity: int,
    active_space: ActiveSpaceSchema | dict[str, Any] | None,
    atoms: list[AtomSchema] | list[dict[str, Any]] | None = None,
    charge: int = 0,
) -> MoleculeEligibilityResponse:
    """Build frontend-facing molecule eligibility and capability labels."""
    unsupported_symbols = _unsupported_atom_symbols(atoms)
    if unsupported_symbols:
        joined_symbols = ", ".join(unsupported_symbols)
        return MoleculeEligibilityResponse(
            selectable=False,
            label="Unsupported atoms",
            reason=(
                "This molecule contains unsupported atom symbols: "
                f"{joined_symbols}. Supported elements currently range from H through Xe."
            ),
            capability_labels=[],
        )

    n_electrons, n_orbitals = _active_space_numbers(active_space)
    active_space_payload = (
        active_space.model_dump() if isinstance(active_space, ActiveSpaceSchema) else active_space
    )
    derived_active_space = isinstance(active_space_payload, dict) and active_space_payload.get(
        "method"
    ) in {"automatic_valence", "automatic_frontier_estimate"}

    if multiplicity != 1:
        return MoleculeEligibilityResponse(
            selectable=False,
            label="Not runnable",
            reason="Only singlet molecules are supported in the current rollout.",
            capability_labels=[],
        )

    if n_electrons is not None and n_electrons % 2 != 0:
        return MoleculeEligibilityResponse(
            selectable=False,
            label="Needs even active electrons",
            reason="Odd active-space electron counts are not supported for closed-shell runs.",
            capability_labels=[],
        )

    if n_electrons is not None and n_orbitals is not None and n_electrons > 2 * n_orbitals:
        return MoleculeEligibilityResponse(
            selectable=False,
            label="Invalid active space",
            reason="Active-space electrons cannot exceed twice the active orbitals.",
            capability_labels=[],
        )

    if derived_active_space and n_electrons is not None and n_orbitals is not None and atoms:
        capacity = minimum_basis_active_orbital_limit(
            atoms,
            active_electrons=n_electrons,
            charge=charge,
        )
        if capacity is not None and n_orbitals > capacity:
            return MoleculeEligibilityResponse(
                selectable=False,
                label="Invalid active space",
                reason=(
                    "The active space exceeds the available STO-3G orbital capacity "
                    f"after frozen-core orbitals are accounted for (maximum {capacity})."
                ),
                capability_labels=[],
            )

    if n_electrons is None or n_orbitals is None:
        return MoleculeEligibilityResponse(
            selectable=True,
            label="Active space unset",
            reason="A bounded active space has not been derived yet.",
            capability_labels=["Run validation required"],
        )

    if n_orbitals > 6:
        return MoleculeEligibilityResponse(
            selectable=True,
            label="Large active space",
            capability_labels=[
                "VQE",
                "SQD",
                "QSE",
                "SKQD",
                "KQD/QFD projected paths",
            ],
        )

    return MoleculeEligibilityResponse(
        selectable=True,
        label="Ready",
        capability_labels=["All algorithms", f"{2 * n_orbitals} qubits"],
    )


def build_molecule_capability_fields(
    *,
    multiplicity: int,
    active_space: ActiveSpaceSchema | dict[str, Any] | None,
    atoms: list[AtomSchema] | list[dict[str, Any]] | None = None,
    charge: int = 0,
) -> dict[str, Any]:
    """Build explicit visualization/run capability fields from backend validation rules."""
    eligibility = build_molecule_eligibility(
        multiplicity=multiplicity,
        active_space=active_space,
        atoms=atoms,
        charge=charge,
    )
    blocking_reasons = (
        [eligibility.reason] if eligibility.reason and not eligibility.selectable else []
    )
    warnings = [eligibility.reason] if eligibility.reason and eligibility.selectable else []
    return {
        "visualizable": True,
        "runnable_algorithms": (
            ["vqe", "qse", "kqd", "qfd", "sqd", "skqd"] if eligibility.selectable else []
        ),
        "blocking_reasons": blocking_reasons,
        "warnings": warnings,
    }


class MoleculeBase(BaseModel):
    """Base molecule schema with common fields."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=255, description="Molecule name")
    atoms: list[AtomSchema] = Field(
        ...,
        min_length=1,
        max_length=MAX_ATOMS_PER_MOLECULE,
        description="Atomic coordinates",
    )
    charge: int = Field(0, description="Net molecular charge")
    multiplicity: int = Field(1, ge=1, description="Spin multiplicity (2S+1)")
    active_space: ActiveSpaceSchema | None = Field(
        None,
        description="Optional active space definition",
    )
    pubchem_cid: int | None = Field(
        None,
        description="PubChem Compound ID",
    )
    iupac_name: str | None = Field(
        None,
        max_length=512,
        description="IUPAC chemical name",
    )
    description: str | None = Field(
        None,
        max_length=MAX_DESCRIPTION_LENGTH,
        description="Full text description",
    )
    synonyms: list[str] | None = Field(
        None,
        max_length=MAX_SYNONYMS,
        description="List of alternative names (JSONB)",
    )
    smiles: str | None = Field(
        None,
        max_length=512,
        description="SMILES string representation",
    )
    inchi: str | None = Field(
        None,
        max_length=MAX_INCHI_LENGTH,
        description="InChI string",
    )
    inchi_key: str | None = Field(
        None,
        description="InChIKey (27 characters when present)",
    )

    @field_validator("name")
    @classmethod
    def validate_non_empty_trimmed(cls, value: str) -> str:
        """Reject blank strings after trimming whitespace."""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Field must be non-empty")
        if cleaned.lower() == "default":
            raise ValueError("Field must not use placeholder name 'default'")
        return cleaned

    @field_validator("iupac_name")
    @classmethod
    def validate_iupac_name_length(cls, value: str | None) -> str | None:
        """IUPAC name must not exceed 512 characters."""
        if value is not None and len(value) > 512:
            raise ValueError("iupac_name must not exceed 512 characters")
        return value

    @field_validator("smiles")
    @classmethod
    def validate_smiles_length(cls, value: str | None) -> str | None:
        """SMILES string must not exceed 512 characters."""
        if value is not None and len(value) > 512:
            raise ValueError("smiles must not exceed 512 characters")
        return value

    @field_validator("synonyms")
    @classmethod
    def validate_synonym_lengths(cls, value: list[str] | None) -> list[str] | None:
        _validate_synonym_lengths(value)
        return value

    @field_validator("inchi_key")
    @classmethod
    def validate_inchi_key_length(cls, value: str | None) -> str | None:
        """InChIKey must be exactly 27 characters when provided."""
        if value is not None and len(value) != 27:
            raise ValueError("inchi_key must be exactly 27 characters")
        return value


class MoleculeCreate(MoleculeBase):
    """Schema for creating a new molecule."""

    pass


class MoleculeUpdate(BaseModel):
    """Schema for updating a molecule."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, min_length=1, max_length=255)
    atoms: list[AtomSchema] | None = Field(
        None,
        min_length=1,
        max_length=MAX_ATOMS_PER_MOLECULE,
    )
    charge: int | None = None
    multiplicity: int | None = Field(None, ge=1)
    active_space: ActiveSpaceSchema | None = None
    pubchem_cid: int | None = None
    iupac_name: str | None = None
    description: str | None = Field(None, max_length=MAX_DESCRIPTION_LENGTH)
    synonyms: list[str] | None = Field(None, max_length=MAX_SYNONYMS)
    smiles: str | None = None
    inchi: str | None = Field(None, max_length=MAX_INCHI_LENGTH)
    inchi_key: str | None = None

    @field_validator("name", "atoms", "charge", "multiplicity", mode="before")
    @classmethod
    def forbid_null_for_non_nullable_fields(cls, value: Any) -> Any:
        """
        For PATCH semantics, fields may be omitted but must not be explicitly set to null.
        The corresponding database columns are non-nullable; explicit null values must be
        rejected at the schema level to return a 422 validation error, not a 500 DB error.
        Only active_space and PubChem fields should be clearable via null.
        """
        if value is None:
            raise ValueError("Field may not be null; omit the field to leave it unchanged.")
        return value

    @field_validator("name")
    @classmethod
    def validate_non_empty_trimmed(cls, value: str) -> str:
        """Trim and reject blank strings."""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Field must be non-empty")
        if cleaned.lower() == "default":
            raise ValueError("Field must not use placeholder name 'default'")
        return cleaned

    @field_validator("iupac_name")
    @classmethod
    def validate_iupac_name_length(cls, value: str | None) -> str | None:
        """IUPAC name must not exceed 512 characters."""
        if value is not None and len(value) > 512:
            raise ValueError("iupac_name must not exceed 512 characters")
        return value

    @field_validator("smiles")
    @classmethod
    def validate_smiles_length(cls, value: str | None) -> str | None:
        """SMILES string must not exceed 512 characters."""
        if value is not None and len(value) > 512:
            raise ValueError("smiles must not exceed 512 characters")
        return value

    @field_validator("synonyms")
    @classmethod
    def validate_synonym_lengths(cls, value: list[str] | None) -> list[str] | None:
        _validate_synonym_lengths(value)
        return value

    @field_validator("inchi_key")
    @classmethod
    def validate_inchi_key_length(cls, value: str | None) -> str | None:
        """InChIKey must be exactly 27 characters when provided."""
        if value is not None and len(value) != 27:
            raise ValueError("inchi_key must be exactly 27 characters")
        return value


class MoleculeResponse(MoleculeBase, BaseORMModel):
    """Schema for molecule responses."""

    id: UUID
    created_at: datetime
    updated_at: datetime
    eligibility: MoleculeEligibilityResponse | None = None
    visualizable: bool = True
    runnable_algorithms: list[str] = Field(default_factory=list)
    blocking_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def populate_eligibility(self) -> "MoleculeResponse":
        """Attach derived labels for current frontend selection surfaces."""
        if self.eligibility is None:
            self.eligibility = build_molecule_eligibility(
                multiplicity=self.multiplicity,
                active_space=self.active_space,
                atoms=self.atoms,
                charge=self.charge,
            )
        capability_fields = build_molecule_capability_fields(
            multiplicity=self.multiplicity,
            active_space=self.active_space,
            atoms=self.atoms,
            charge=self.charge,
        )
        self.visualizable = bool(capability_fields["visualizable"])
        self.runnable_algorithms = list(capability_fields["runnable_algorithms"])
        self.blocking_reasons = list(capability_fields["blocking_reasons"])
        self.warnings = list(capability_fields["warnings"])
        return self


def _atom_counts_from_atoms(atoms: list[AtomSchema] | list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for atom in atoms:
        symbol_raw = atom.symbol if isinstance(atom, AtomSchema) else atom.get("symbol")
        symbol = str(symbol_raw).strip()
        if not symbol:
            continue
        counts[symbol] = counts.get(symbol, 0) + 1
    return counts


def build_molecule_formula(atoms: list[AtomSchema] | list[dict[str, Any]]) -> str:
    """Build a compact Hill-style formula for molecule list displays."""
    counts = _atom_counts_from_atoms(atoms)

    def hill_sort_group(symbol: str) -> int:
        if symbol == "C":
            return 0
        if symbol == "H":
            return 1
        return 2

    symbols = sorted(counts, key=lambda symbol: (hill_sort_group(symbol), symbol))
    return "".join(
        symbol if counts[symbol] == 1 else f"{symbol}{counts[symbol]}" for symbol in symbols
    )


class MoleculeSummaryResponse(BaseModel):
    """Lightweight molecule list item used by high-volume list UIs."""

    id: UUID
    name: str
    charge: int
    atom_count: int
    run_count: int = 0
    formula: str
    iupac_name: str | None = None
    eligibility: MoleculeEligibilityResponse
    visualizable: bool = True
    runnable_algorithms: list[str] = Field(default_factory=list)
    blocking_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @classmethod
    def from_molecule(
        cls, molecule: Any, *, run_count: int | None = None
    ) -> "MoleculeSummaryResponse":
        atoms = list(getattr(molecule, "atoms", []) or [])
        active_space = getattr(molecule, "active_space", None)
        multiplicity = int(getattr(molecule, "multiplicity", 1) or 1)
        capability_fields = build_molecule_capability_fields(
            multiplicity=multiplicity,
            active_space=active_space if isinstance(active_space, dict) else None,
            atoms=atoms,
            charge=int(getattr(molecule, "charge", 0) or 0),
        )
        return cls(
            id=getattr(molecule, "id"),
            name=str(getattr(molecule, "name")),
            charge=int(getattr(molecule, "charge", 0) or 0),
            atom_count=len(atoms),
            run_count=int(
                run_count if run_count is not None else len(getattr(molecule, "runs", []))
            ),
            formula=build_molecule_formula(atoms),
            iupac_name=getattr(molecule, "iupac_name", None),
            eligibility=build_molecule_eligibility(
                multiplicity=multiplicity,
                active_space=active_space if isinstance(active_space, dict) else None,
                atoms=atoms,
                charge=int(getattr(molecule, "charge", 0) or 0),
            ),
            visualizable=bool(capability_fields["visualizable"]),
            runnable_algorithms=list(capability_fields["runnable_algorithms"]),
            blocking_reasons=list(capability_fields["blocking_reasons"]),
            warnings=list(capability_fields["warnings"]),
        )


class MoleculeListParams(BaseModel):
    """Query parameters for the molecule list endpoint."""

    model_config = ConfigDict(extra="forbid")

    q: str | None = None
    charge: int | None = None
    limit: int = Field(50, ge=1, le=200)
    offset: int = Field(0, ge=0)


class MoleculeListResponse(BaseModel):
    """Paginated molecule list response."""

    items: list[MoleculeResponse]
    total: int


def validate_molecule_response(molecule: Any) -> MoleculeResponse:
    """Serialize persisted molecules without letting legacy unsupported atoms crash reads."""
    return MoleculeResponse.model_validate(
        molecule,
        context=MOLECULE_RESPONSE_VALIDATION_CONTEXT,
    )


class MoleculeSummaryListResponse(BaseModel):
    """Paginated lightweight molecule list response."""

    items: list[MoleculeSummaryResponse]
    total: int


class PubChemImportRequest(BaseModel):
    """Request body for the on-demand PubChem import endpoint."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=200)
    display_name: str | None = Field(None, min_length=1, max_length=255)


class _XYZRequestBase(BaseModel):
    """Common fields for XYZ import and preview request bodies."""

    model_config = ConfigDict(extra="forbid")

    xyz: str = Field(..., min_length=1, max_length=100_000)
    charge: int = 0
    multiplicity: int = Field(1, ge=1)
    active_space: ActiveSpaceSchema | None = None
    derive_active_space: bool = True

    @field_validator("xyz")
    @classmethod
    def validate_xyz_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("XYZ text must be non-empty")
        return value


class XYZPreviewRequest(_XYZRequestBase):
    """Request body for non-persisting XYZ geometry previews."""

    name: str | None = Field(None, min_length=1, max_length=255)


class XYZImportRequest(_XYZRequestBase):
    """Request body for committing an XYZ geometry to the molecule library."""

    name: str = Field(..., min_length=1, max_length=255)


class MoleculeImportPreviewResponse(BaseModel):
    """Non-persisted molecule preview shared by PubChem and XYZ import flows."""

    source: Literal["pubchem", "xyz"]
    name: str
    atoms: list[AtomSchema]
    charge: int
    multiplicity: int
    active_space: ActiveSpaceSchema | None
    atom_count: int
    formula: str
    eligibility: MoleculeEligibilityResponse
    visualizable: bool = True
    runnable_algorithms: list[str] = Field(default_factory=list)
    blocking_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    commit_action: Literal["create", "reuse", "name_conflict"]
    existing_molecule_id: UUID | None = None
    existing_molecule_name: str | None = None
    pubchem_cid: int | None = None
    iupac_name: str | None = None
    description: str | None = None
    synonyms: list[str] | None = None
    smiles: str | None = None
    inchi: str | None = None
    inchi_key: str | None = None


class PubChemSearchResult(BaseModel):
    """A single compound result from the PubChem autocomplete search."""

    name: str
    iupac_name: str
    formula: str
    cid: int | None = None


class PubChemSearchResponse(BaseModel):
    """Response schema for the PubChem compound search endpoint."""

    results: list[PubChemSearchResult]
