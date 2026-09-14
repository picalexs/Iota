"""
Service layer for molecule business logic.
"""

import logging
import math
import re
from typing import Any, Literal
from typing import cast as typing_cast
from uuid import UUID

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.models import Molecule, Run
from app.schemas.molecule import (
    MAX_ATOMS_PER_MOLECULE,
    ActiveSpaceSchema,
    AtomSchema,
    MoleculeCreate,
    MoleculeImportPreviewResponse,
    MoleculeUpdate,
    PubChemImportRequest,
    XYZImportRequest,
    XYZPreviewRequest,
    build_molecule_capability_fields,
    build_molecule_eligibility,
    build_molecule_formula,
)
from app.services.active_space import (
    derive_active_space_from_atoms,
    should_refresh_derived_active_space,
)
from app.services.run import RunService

logger = logging.getLogger(__name__)

_XYZ_SYMBOL_RE = re.compile(r"^[A-Za-z][A-Za-z]?$")


def _canonical_atom_symbol(symbol_raw: str) -> str:
    symbol = symbol_raw.strip()
    if not _XYZ_SYMBOL_RE.match(symbol):
        raise ValidationError(f"Invalid XYZ atom symbol '{symbol_raw}'", field="xyz")
    return symbol[0].upper() + symbol[1:].lower()


def parse_xyz_atoms(xyz_text: str) -> tuple[list[dict[str, float | str]], str | None]:
    """Parse standard XYZ text into atom dictionaries and return its comment line."""
    lines = [line.rstrip() for line in xyz_text.splitlines() if line.strip()]
    if len(lines) < 3:
        raise ValidationError(
            "XYZ text must include atom count, comment, and at least one atom line.",
            field="xyz",
        )

    try:
        expected_atoms = int(lines[0].strip())
    except ValueError as exc:
        raise ValidationError("XYZ first line must be an atom count.", field="xyz") from exc

    if expected_atoms <= 0:
        raise ValidationError("XYZ atom count must be positive.", field="xyz")
    if expected_atoms > MAX_ATOMS_PER_MOLECULE:
        raise ValidationError(
            f"XYZ atom count must not exceed {MAX_ATOMS_PER_MOLECULE} atoms.",
            field="xyz",
        )

    atom_lines = lines[2:]
    if len(atom_lines) != expected_atoms:
        raise ValidationError(
            f"XYZ atom count declares {expected_atoms} atoms but {len(atom_lines)} were provided.",
            field="xyz",
        )

    atoms: list[dict[str, float | str]] = []
    for index, line in enumerate(atom_lines, start=1):
        parts = line.split()
        if len(parts) < 4:
            raise ValidationError(
                f"XYZ atom line {index} must contain symbol and three coordinates.",
                field="xyz",
            )
        symbol = _canonical_atom_symbol(parts[0])
        try:
            x, y, z = (float(parts[1]), float(parts[2]), float(parts[3]))
        except ValueError as exc:
            raise ValidationError(
                f"XYZ atom line {index} contains a non-numeric coordinate.",
                field="xyz",
            ) from exc
        if not all(math.isfinite(value) for value in (x, y, z)):
            raise ValidationError(
                f"XYZ atom line {index} contains a non-finite coordinate.",
                field="xyz",
            )
        atoms.append({"symbol": symbol, "x": x, "y": y, "z": z})

    return atoms, lines[1].strip() or None


class MoleculeService:
    """
    Business logic for molecule operations.

    Handles CRUD operations and validation for molecules.
    """

    def __init__(self, db: Session):
        """Initialize service with database session."""
        self.db = db

    def _refresh_derived_active_space(self, molecule: Molecule) -> bool:
        """Refresh stale automatic active-space metadata for imported molecules."""
        if not should_refresh_derived_active_space(molecule.active_space):
            return False

        active_space = derive_active_space_from_atoms(
            molecule.atoms,
            charge=molecule.charge,
            multiplicity=molecule.multiplicity,
        )
        if active_space is None:
            return False

        molecule.active_space = active_space
        return True

    def _find_existing_import_target(
        self,
        *,
        name: str,
        pubchem_cid: int | None = None,
    ) -> Molecule | None:
        """Find an existing molecule that an import commit would reuse or conflict with."""
        existing = self.db.scalars(
            select(Molecule).where(func.lower(Molecule.name) == name.lower())
        ).first()
        if existing:
            return existing

        if isinstance(pubchem_cid, int):
            return self.db.scalars(
                select(Molecule).where(Molecule.pubchem_cid == pubchem_cid)
            ).first()

        return None

    def _refresh_existing_import_target(self, molecule: Molecule) -> Molecule:
        if self._refresh_derived_active_space(molecule):
            self.db.commit()
            self.db.refresh(molecule)
        return molecule

    @staticmethod
    def _validate_atom_models(atoms: list[dict[str, Any]]) -> list[AtomSchema]:
        try:
            return [AtomSchema.model_validate(atom) for atom in atoms]
        except PydanticValidationError as exc:
            first_error = exc.errors()[0]
            message = str(first_error.get("msg", "Invalid atom payload"))
            raise ValidationError(
                f"Molecule atom data is invalid: {message}",
                field="atoms",
            ) from exc

    @classmethod
    def _validate_atom_payloads(cls, atoms: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [atom.model_dump() for atom in cls._validate_atom_models(atoms)]

    @staticmethod
    def _get_pubchem_cid(mol_data: dict[str, Any]) -> int | None:
        pubchem_cid = mol_data.get("pubchem_cid")
        return pubchem_cid if isinstance(pubchem_cid, int) else None

    def _find_existing_pubchem_cid(self, pubchem_cid: int | None) -> Molecule | None:
        if pubchem_cid is None:
            return None
        return self.db.scalars(select(Molecule).where(Molecule.pubchem_cid == pubchem_cid)).first()

    @staticmethod
    def _build_pubchem_molecule(mol_data: dict[str, Any], stored_name: str) -> Molecule:
        return Molecule(
            name=stored_name,
            atoms=MoleculeService._validate_atom_payloads(mol_data["atoms"]),
            charge=mol_data["charge"],
            multiplicity=mol_data["multiplicity"],
            active_space=mol_data["active_space"],
            pubchem_cid=mol_data.get("pubchem_cid"),
            iupac_name=mol_data.get("iupac_name"),
            description=mol_data.get("description"),
            synonyms=mol_data.get("synonyms"),
            smiles=mol_data.get("smiles"),
            inchi=mol_data.get("inchi"),
            inchi_key=mol_data.get("inchi_key"),
        )

    def _recover_pubchem_import_conflict(
        self,
        *,
        stored_name: str,
        pubchem_cid: int | None,
    ) -> Molecule | None:
        if pubchem_cid is not None:
            recovered = self.db.scalars(
                select(Molecule).where(Molecule.pubchem_cid == pubchem_cid)
            ).first()
            if recovered is not None:
                return recovered

        return self.db.scalars(
            select(Molecule).where(func.lower(Molecule.name) == stored_name.lower())
        ).first()

    def _build_import_preview(
        self,
        *,
        source: Literal["pubchem", "xyz"],
        name: str,
        atoms: list[dict[str, Any]],
        charge: int,
        multiplicity: int,
        active_space: dict[str, Any] | None,
        existing: Molecule | None = None,
        pubchem_metadata: dict[str, Any] | None = None,
        name_conflict: bool = False,
    ) -> MoleculeImportPreviewResponse:
        action = "create"
        if existing and not name_conflict:
            action = "reuse"
        elif existing or name_conflict:
            action = "name_conflict"
        atom_models = self._validate_atom_models(atoms)
        active_space_model = (
            ActiveSpaceSchema.model_validate(active_space) if active_space is not None else None
        )
        capability_fields = build_molecule_capability_fields(
            multiplicity=multiplicity,
            active_space=active_space,
            atoms=atom_models,
        )
        return MoleculeImportPreviewResponse(
            source=source,
            name=name,
            atoms=atom_models,
            charge=charge,
            multiplicity=multiplicity,
            active_space=active_space_model,
            atom_count=len(atoms),
            formula=build_molecule_formula(atoms),
            eligibility=build_molecule_eligibility(
                multiplicity=multiplicity,
                active_space=active_space,
                atoms=atom_models,
            ),
            visualizable=bool(capability_fields["visualizable"]),
            runnable_algorithms=list(capability_fields["runnable_algorithms"]),
            blocking_reasons=list(capability_fields["blocking_reasons"]),
            warnings=list(capability_fields["warnings"]),
            commit_action=typing_cast(Literal["create", "reuse", "name_conflict"], action),
            existing_molecule_id=getattr(existing, "id", None),
            existing_molecule_name=getattr(existing, "name", None),
            pubchem_cid=(pubchem_metadata or {}).get("pubchem_cid"),
            iupac_name=(pubchem_metadata or {}).get("iupac_name"),
            description=(pubchem_metadata or {}).get("description"),
            synonyms=(pubchem_metadata or {}).get("synonyms"),
            smiles=(pubchem_metadata or {}).get("smiles"),
            inchi=(pubchem_metadata or {}).get("inchi"),
            inchi_key=(pubchem_metadata or {}).get("inchi_key"),
        )

    def create(self, molecule_in: MoleculeCreate) -> Molecule:
        """
        Create a new molecule.

        Args:
            molecule_in: Molecule creation data

        Returns:
            Created molecule

        Raises:
            ConflictError: If molecule with same name exists
        """
        existing = self.db.scalars(
            select(Molecule).where(func.lower(Molecule.name) == molecule_in.name.lower())
        ).first()
        if existing:
            raise ConflictError(f"Molecule with name '{molecule_in.name}' already exists")

        molecule = Molecule(
            name=molecule_in.name,
            atoms=[atom.model_dump() for atom in molecule_in.atoms],
            charge=molecule_in.charge,
            multiplicity=molecule_in.multiplicity,
            active_space=(
                molecule_in.active_space.model_dump()
                if molecule_in.active_space is not None
                else None
            ),
            pubchem_cid=molecule_in.pubchem_cid,
            iupac_name=molecule_in.iupac_name,
            description=molecule_in.description,
            synonyms=molecule_in.synonyms,
            smiles=molecule_in.smiles,
            inchi=molecule_in.inchi,
            inchi_key=molecule_in.inchi_key,
        )

        self.db.add(molecule)
        self.db.commit()
        self.db.refresh(molecule)

        return molecule

    def get_by_id(self, molecule_id: UUID) -> Molecule:
        """
        Get molecule by ID.

        Args:
            molecule_id: Molecule UUID

        Returns:
            Molecule instance

        Raises:
            NotFoundError: If molecule not found
        """
        molecule = self.db.get(Molecule, molecule_id)
        if not molecule:
            raise NotFoundError(f"Molecule {molecule_id} not found")
        return molecule

    def list_all(
        self,
        *,
        q: str | None = None,
        charge: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """
        List molecules with optional search/filter and pagination.

        Args:
            q: Case-insensitive substring filter on molecule name.
            charge: Exact match filter on charge.
            limit: Maximum number of results to return.
            offset: Number of results to skip.

        Returns:
            Dict with ``items`` (list of Molecule) and ``total``
            (total matching filters, before limit/offset).
        """
        query = select(Molecule)

        if q is not None and q.strip() != "":
            pattern = f"%{q.strip()}%"
            query = query.where(
                or_(
                    Molecule.name.ilike(pattern),
                    Molecule.iupac_name.ilike(pattern),
                    cast(Molecule.synonyms, String).ilike(pattern),
                    Molecule.smiles.ilike(pattern),
                    Molecule.inchi.ilike(pattern),
                )
            )
        if charge is not None:
            query = query.where(Molecule.charge == charge)

        total_raw = self.db.scalar(select(func.count()).select_from(query.subquery()))
        total = int(total_raw or 0)

        items = self.db.scalars(
            query.order_by(Molecule.created_at.desc()).offset(offset).limit(limit)
        ).all()

        refreshed = False
        for molecule in items:
            refreshed = self._refresh_derived_active_space(molecule) or refreshed

        if refreshed:
            self.db.commit()
            for molecule in items:
                self.db.refresh(molecule)

        return {"items": items, "total": total}

    def list_associated_runs(self, molecule_id: UUID) -> list[Run]:
        molecule = self.get_by_id(molecule_id)
        return list(molecule.runs)

    async def import_from_pubchem(
        self,
        name: str,
        display_name: str | None = None,
    ) -> tuple[Molecule, bool]:
        """
        Fetch a molecule by name from PubChem and store it in the database.

        Args:
            name: Molecule name to search on PubChem.
            display_name: Optional display name override for the stored record.

        Returns:
            Tuple of (molecule, created) where created=False when an existing
            matching molecule is returned.

        Raises:
            ConflictError: If a molecule with that name already exists.
            NotFoundError: If PubChem has no 3-D record for the name.
        """
        from app.services.pubchem_sync import fetch_molecule_from_pubchem

        stored_name = (display_name or name).strip()
        existing = self._find_existing_import_target(name=stored_name)
        if existing:
            return self._refresh_existing_import_target(existing), False

        mol_data = await fetch_molecule_from_pubchem(name)
        if mol_data is None:
            raise NotFoundError(f"Molecule '{name}' not found on PubChem (no 3-D record)")

        pubchem_cid = self._get_pubchem_cid(mol_data)
        existing_cid = self._find_existing_pubchem_cid(pubchem_cid)
        if existing_cid:
            return self._refresh_existing_import_target(existing_cid), False

        molecule = self._build_pubchem_molecule(mol_data, stored_name)
        self.db.add(molecule)
        try:
            self.db.commit()
            self.db.refresh(molecule)
        except Exception as exc:
            self.db.rollback()

            recovered = self._recover_pubchem_import_conflict(
                stored_name=stored_name,
                pubchem_cid=pubchem_cid,
            )
            if recovered is not None:
                return recovered, False

            logger.exception("PubChem molecule persistence failed for '%s'", stored_name)
            raise ConflictError("Failed to save molecule") from exc
        return molecule, True

    async def preview_pubchem_import(
        self,
        data: PubChemImportRequest,
    ) -> MoleculeImportPreviewResponse:
        """Fetch PubChem data and return a non-persisted import preview."""
        from app.services.pubchem_sync import fetch_molecule_from_pubchem

        stored_name = (data.display_name or data.name).strip()
        mol_data = await fetch_molecule_from_pubchem(data.name)
        if mol_data is None:
            raise NotFoundError(f"Molecule '{data.name}' not found on PubChem (no 3-D record)")

        pubchem_cid = mol_data.get("pubchem_cid")
        existing = self._find_existing_import_target(
            name=stored_name,
            pubchem_cid=pubchem_cid if isinstance(pubchem_cid, int) else None,
        )
        return self._build_import_preview(
            source="pubchem",
            name=stored_name,
            atoms=mol_data["atoms"],
            charge=mol_data["charge"],
            multiplicity=mol_data["multiplicity"],
            active_space=mol_data["active_space"],
            existing=existing,
            pubchem_metadata=mol_data,
        )

    def preview_xyz_import(
        self,
        data: XYZPreviewRequest,
    ) -> MoleculeImportPreviewResponse:
        """Parse XYZ text and return a non-persisted molecule preview."""
        atoms, comment = parse_xyz_atoms(data.xyz)
        active_space = None
        if data.active_space is not None:
            active_space = data.active_space.model_dump()
        elif data.derive_active_space:
            active_space = derive_active_space_from_atoms(
                atoms,
                charge=data.charge,
                multiplicity=data.multiplicity,
            )
        preview_name = (data.name or comment or "XYZ import").strip()
        existing = (
            self._find_existing_import_target(name=preview_name)
            if data.name is not None and preview_name
            else None
        )
        return self._build_import_preview(
            source="xyz",
            name=preview_name,
            atoms=atoms,
            charge=data.charge,
            multiplicity=data.multiplicity,
            active_space=active_space,
            existing=existing,
            name_conflict=existing is not None,
        )

    def import_from_xyz(self, data: XYZImportRequest) -> Molecule:
        """Persist a molecule from standard XYZ text."""
        atoms, _comment = parse_xyz_atoms(data.xyz)
        active_space = None
        if data.active_space is not None:
            active_space = data.active_space.model_dump()
        elif data.derive_active_space:
            active_space = derive_active_space_from_atoms(
                atoms,
                charge=data.charge,
                multiplicity=data.multiplicity,
            )
        molecule_in = MoleculeCreate(
            name=data.name,
            atoms=self._validate_atom_models(atoms),
            charge=data.charge,
            multiplicity=data.multiplicity,
            active_space=(
                ActiveSpaceSchema.model_validate(active_space) if active_space is not None else None
            ),
            pubchem_cid=None,
            iupac_name=None,
            description=None,
            synonyms=None,
            smiles=None,
            inchi=None,
            inchi_key=None,
        )
        return self.create(molecule_in)

    def update(self, molecule_id: UUID, molecule_in: MoleculeUpdate) -> Molecule:
        """
        Update a molecule.

        Args:
            molecule_id: Molecule UUID
            molecule_in: Update data

        Returns:
            Updated molecule

        Raises:
            NotFoundError: If molecule not found
            ConflictError: If name conflicts with another molecule
        """
        molecule = self.get_by_id(molecule_id)

        update_data = molecule_in.model_dump(exclude_unset=True)

        new_name = update_data.get("name", molecule.name)
        if new_name != molecule.name:
            conflict = self.db.scalars(
                select(Molecule).where(
                    func.lower(Molecule.name) == new_name.lower(),
                    Molecule.id != molecule.id,
                )
            ).first()
            if conflict:
                raise ConflictError(f"Molecule with name '{new_name}' already exists")

        if "name" in update_data:
            molecule.name = update_data["name"]
        if "atoms" in update_data:
            molecule.atoms = update_data["atoms"]
        if "charge" in update_data:
            molecule.charge = update_data["charge"]
        if "multiplicity" in update_data:
            molecule.multiplicity = update_data["multiplicity"]
        if "active_space" in update_data:
            molecule.active_space = update_data["active_space"]
        if "pubchem_cid" in update_data:
            molecule.pubchem_cid = update_data["pubchem_cid"]
        if "iupac_name" in update_data:
            molecule.iupac_name = update_data["iupac_name"]
        if "description" in update_data:
            molecule.description = update_data["description"]
        if "synonyms" in update_data:
            molecule.synonyms = update_data["synonyms"]
        if "smiles" in update_data:
            molecule.smiles = update_data["smiles"]
        if "inchi" in update_data:
            molecule.inchi = update_data["inchi"]
        if "inchi_key" in update_data:
            molecule.inchi_key = update_data["inchi_key"]

        self.db.commit()
        self.db.refresh(molecule)

        return molecule

    def delete(
        self, molecule_id: UUID, *, delete_associated_runs: bool = False, redis_client=None
    ) -> None:
        """
        Delete a molecule.

        Args:
            molecule_id: Molecule UUID

        Raises:
            NotFoundError: If molecule not found
            ConflictError: If molecule has associated runs
        """
        molecule = self.get_by_id(molecule_id)

        if delete_associated_runs and molecule.runs:
            run_ids = [run.id for run in molecule.runs]
            run_service = RunService(self.db)
            for run_id in run_ids:
                run_service.delete(run_id, redis_client=redis_client, commit=False)
            self.db.expire(molecule, ["runs"])
            molecule = self.get_by_id(molecule_id)

        if molecule.runs:
            raise ConflictError(
                f"Cannot delete molecule {molecule_id}: it has {len(molecule.runs)} associated runs"
            )

        self.db.delete(molecule)
        self.db.commit()
